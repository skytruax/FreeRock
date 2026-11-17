"""The server with a sensor attached.

The sensor here is FreeRock's real sensor loop and its real WebSocket client, run in a thread and
talking to the real server over a real local connection. Only the game and the screen copy are
pretend (freerock.sim).
"""
import asyncio
import io
import json
import zipfile

import aiohttp
import pytest
from aiohttp.test_utils import TestServer

from freerock import server, sim, state
from freerock.web import sensor


@pytest.fixture
async def running(tmp_path):
    config = server.ServerConfig(var_dir=tmp_path / "var", lost_after=0.3)
    app = server.create_app(config)
    host = TestServer(app)  # picks a free port
    await host.start_server()
    try:
        yield app, f"http://127.0.0.1:{host.port}"
    finally:
        await host.close()


async def play(scenario, address, speed=25.0):
    said = []
    await asyncio.to_thread(sim.play, scenario, address, speed=speed, say=said.append)
    return said


async def get_json(address, path):
    async with aiohttp.ClientSession() as session:
        async with session.get(address + path) as response:
            assert response.status == 200, await response.text()
            return await response.json()


WALK = {
    "screen": [1920, 1080], "cell": 3, "edge": "top", "inset": [16, 0],
    "start": {"zone": "Elwynn Forest", "subzone": "Goldshire", "map_id": 1429, "x": 0.42, "y": 0.65},
    "steps": [
        {"at": 1.0, "test": 1.0},
        {"at": 3.0, "set": {"subzone": "Fargodeep Mine", "indoors": True}},
        {"at": 4.0, "set": {"combat": True, "target": "elite"}},
        {"at": 5.0, "command": "skip"},
        {"at": 6.0, "moment": "level_up"},
        {"at": 7.0, "set": {"combat": False, "target": None}},
        {"at": 9.0},
    ],
}


async def test_pages_and_files_point_back_at_the_server(running):
    app, address = running
    host = address.removeprefix("http://")
    async with aiohttp.ClientSession() as session:
        async with session.get(address + "/") as response:
            assert response.status == 200
            page = await response.text()
            assert "<title>FreeRock: game link</title>" in page and "/static/link.js" in page
        for name, kind in (("link.js", "javascript"), ("link.css", "css")):
            async with session.get(f"{address}/static/{name}") as response:
                assert response.status == 200 and kind in response.headers["Content-Type"]
        async with session.get(address + "/static/sensor.py") as response:
            assert response.status == 404, "only the page's own files are served from /static"

        async with session.get(address + "/sensor.py") as response:
            assert response.status == 200
            source = await response.text()
        assert f'DEFAULT_SERVER = "{address}"' in source, "the script is handed out knowing where it came from"
        assert source.splitlines()[0] == "# /// script"
        compile(source, "sensor.py", "exec")

        async with session.get(address + "/addon.zip") as response:
            assert response.status == 200
            names = zipfile.ZipFile(io.BytesIO(await response.read())).namelist()
        assert sorted(names) == ["FreeRock/Beacon.lua", "FreeRock/CVars.lua", "FreeRock/Core.lua",
                                 "FreeRock/FreeRock.toc", "FreeRock/Options.lua", "FreeRock/Signals.lua"]

        async with session.get(address + "/FreeRock.cmd") as response:
            launcher = await response.text()
        assert f"uv run http://{host}/sensor.py" in launcher
        assert f"--app=http://{host}/ " in launcher and "--autoplay-policy=no-user-gesture-required" in launcher
        assert "\r\n" in launcher and "\n" not in launcher.replace("\r\n", ""), "Windows line endings"

        async with session.get(address + "/api/strip.png") as response:
            assert response.status == 404, "nothing captured yet"
    shot = await get_json(address, "/api/snapshot")
    assert shot["link"] == "never" and shot["state"] is None and shot["sensor"] is None
    assert shot["strip"]["found"] is False and shot["counts"]["pictures"] == 0


async def test_the_addon_archive_unpacks_with_the_sensors_own_installer(running, tmp_path):
    app, address = running
    async with aiohttp.ClientSession() as session:
        async with session.get(address + "/addon.zip") as response:
            archive = await response.read()
    addons = tmp_path / "_forever_" / "Interface" / "AddOns"
    assert sensor.unpack_addon(archive, addons) == 6
    assert (addons / "FreeRock" / "FreeRock.toc").read_text().startswith("## Interface: 16001")


async def test_a_session_end_to_end(running):
    app, address = running
    hub: state.Hub = app["hub"]
    heard = hub.subscribe()
    pushed = []

    async def watch_page():
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(address + "/ws/ui") as socket:
                async for message in socket:
                    pushed.append(json.loads(message.data))

    page = asyncio.create_task(watch_page())
    await asyncio.sleep(0.05)
    said = await play(WALK, address)
    await asyncio.sleep(0.4)  # one more push to the page

    assert pushed[0]["link"] == "never", "a page gets the whole picture as soon as it opens"
    shot = await get_json(address, "/api/snapshot")
    game = shot["state"]
    assert game["zone_name"] == "Elwynn Forest" and game["subzone_name"] == "Fargodeep Mine"
    assert game["map_id"] == 1429 and game["indoors"] is True and game["in_combat"] is False
    assert game["position"] == pytest.approx([0.42, 0.65], abs=1e-4)
    assert shot["strip"]["found"] is True
    assert shot["strip"]["box"] == [18, 2, 1032, 6] and shot["strip"]["pitch"] == 3.0
    assert shot["counts"]["read"] > 20 and shot["counts"]["checksum"] == 0 and shot["counts"]["names_rejected"] == 0
    assert shot["counts"]["read"] >= shot["counts"]["pictures"] - 1, "only the bottom search band had no strip"
    assert shot["test_pattern_seconds_ago"] is not None

    texts = [entry["text"] for entry in shot["log"]]
    kinds = {entry["kind"] for entry in shot["log"]}
    assert any(text.startswith("Sensor connected") for text in texts)
    assert any(text.startswith("Strip found at 18, 2: 1032 x 6 px, squares of 3.00 px") for text in texts)
    assert "Indoors: no -> yes" in texts
    assert "In combat: no -> yes" in texts and "In combat: yes -> no" in texts
    assert "Target: none -> elite" in texts
    assert "Subzone: not known -> Fargodeep Mine" in texts
    assert "Command from the game: skip (number 1)." in texts
    assert "Moment in the game: level_up (number 1)." in texts
    assert any("test pattern was read" in text for text in texts)
    assert texts[-1].startswith("Sensor at") and texts[-1].endswith("disconnected.")
    assert {"sensor", "strip", "state", "command", "moment", "test", "link"} <= kinds
    assert all(entry["at"] and entry["since_start"] >= 0 for entry in shot["log"])
    assert not any(text.split(":")[0] in ("position", "game_minutes", "has_subzone", "has_target") for text in texts), "the log is not flooded"
    assert all(text[0].isupper() for text in texts), "every line is in plain words"

    assert any(line.endswith("sensor: FreeRock found the strip and is reading it.") for line in said)

    # The page was kept up to date, and the hub heard everything in order.
    assert pushed[-1]["state"]["subzone_name"] == "Fargodeep Mine"
    assert any(shot["sensor"] and shot["sensor"]["mode"] == "track" for shot in pushed)
    rates = [shot["sensor"]["copy_rate"] for shot in pushed if shot["sensor"] and shot["sensor"]["copy_rate"]]
    assert rates and max(rates) > 100, "the sensor's copy rate is worked out (20 a second of game time, played 25 times as fast)"
    events = []
    while not heard._queue.empty():
        events.append(await heard.get())
    assert isinstance(events[0], state.LinkChanged) and events[0].link == state.Link.LIVE
    assert [event.name for event in events if isinstance(event, state.CommandReceived)] == ["skip"]
    assert [event.name for event in events if isinstance(event, state.MomentReceived)] == ["level_up"]
    assert sum(isinstance(event, state.TestPatternSeen) for event in events) == 1
    assert hub.state.subzone_name == "Fargodeep Mine" and hub.link == state.Link.LIVE

    async with aiohttp.ClientSession() as session:
        async with session.get(address + "/api/strip.png") as response:
            assert response.status == 200
            data = await response.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    log_files = list((app["config"].var_dir / "log").glob("link-*.jsonl"))
    assert len(log_files) == 1
    lines = [json.loads(line) for line in log_files[0].read_text().splitlines()]
    assert [line["text"] for line in lines][-len(texts):] == texts

    page.cancel()
    with pytest.raises(asyncio.CancelledError):
        await page


async def test_the_strip_going_away_is_held_then_looked_for_and_found_again(running):
    app, address = running
    scenario = {
        "screen": [1920, 1080], "cell": 4, "edge": "bottom", "inset": [40, 3],
        "steps": [
            {"at": 2.0, "hidden": True},
            {"at": 16.0, "hidden": False, "set": {"indoors": True}},
            {"at": 20.0},
        ],
    }
    await play(scenario, address, speed=20.0)  # the strip is gone for 14 s of game time, 0.7 s of ours
    shot = await get_json(address, "/api/snapshot")
    texts = [entry["text"] for entry in shot["log"]]
    found = [text for text in texts if text.startswith("Strip found at")]
    assert len(found) == 2, texts
    assert found[0].startswith("Strip found at 42, 1067: 1376 x 8 px, squares of 4.00 px"), "along the bottom edge"
    assert any(text.startswith("The strip can no longer be read (no strip); looking for it again.") for text in texts)
    assert shot["state"]["indoors"] is True, "the change made while it was away shows once it is back"
    assert shot["counts"]["no_strip"] > 0


async def test_a_strip_that_moved_while_out_of_sight_is_found_in_its_new_place(running):
    app, address = running
    scenario = {
        "screen": [1920, 1080], "cell": 3, "edge": "top", "inset": [16, 0],
        "steps": [
            {"at": 2.0, "hidden": True},
            {"at": 12.0, "hidden": False, "strip": {"edge": "bottom", "inset": [200, 5], "cell": 4}},
            {"at": 18.0},
        ],
    }
    said = await play(scenario, address, speed=20.0)
    shot = await get_json(address, "/api/snapshot")
    found = [entry["text"] for entry in shot["log"] if entry["text"].startswith("Strip found at")]
    assert found[0].startswith("Strip found at 18, 2: 1032 x 6 px, squares of 3.00 px")
    assert found[1].startswith("Strip found at 202, 1065: 1376 x 8 px, squares of 4.00 px"), found
    assert shot["strip"]["box"] == [202, 1065, 1376, 8] and shot["link"] == "live"
    assert any(line.endswith("sensor: FreeRock lost sight of the strip and is looking for it again.") for line in said)


async def test_the_link_goes_stale_while_nothing_is_read_and_the_state_is_kept(tmp_path):
    clock = {"now": 50.0}
    app = server.create_app(server.ServerConfig(var_dir=tmp_path / "var"), clock=lambda: clock["now"])
    link: server.LinkService = app["link"]
    session = sim.SimSession({"screen": [1920, 1080]}, say=lambda *_: None)
    connection = link.sensor_connected("test")
    band = sensor.BAND
    picture = sensor.Picture(sensor.PART_TOP, 1920, band, 0, 0, 1920, 1080, 1, session.copy(0, 0, 1920, band))
    order = link.take_picture(picture, connection)
    assert order == {"type": "mode", "mode": "track", "roi": [12, 0, 1044, 11]}
    assert link.snapshot()["link"] == "live"
    held = link.tracker.state
    clock["now"] += 2.0
    link.tick()
    shot = link.snapshot()
    assert shot["link"] == "stale" and shot["seconds_since_read"] == 2.0
    assert link.tracker.state is held and shot["state"]["zone_name"] is None  # names had not arrived yet
    assert shot["read_rate"] == 0.2
    clock["now"] += 40.0
    link.tick()
    assert link.snapshot()["link"] == "stale", "half a minute with the interface hidden is held through"
    clock["now"] += 90.0
    link.tick()
    assert link.snapshot()["link"] == "lost"
    assert [entry["text"] for entry in link.log][-2:] == [
        "The strip cannot be read; the last state is being held.", "The strip has not been read for a long time."]
    link.close()


async def test_something_that_is_not_a_picture_is_logged_and_ends_that_connection(running):
    app, address = running
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(address + "/ws/sensor") as socket:
            await socket.send_bytes(b"this is not a picture at all")
            message = await socket.receive(timeout=2)
            assert message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING)
    await asyncio.sleep(0.05)
    texts = [entry["text"] for entry in app["link"].log]
    assert any(text.startswith("The sensor sent something that is not a picture") for text in texts)
    assert texts[-1].endswith("disconnected.")
    assert app["link"].sensors == []


async def test_a_server_that_is_stopping_lets_go_of_the_sensor_and_the_pages_at_once(tmp_path):
    """Left open, a connection holds a stopping server up for a minute, and the sensor goes on
    talking to it while a new server waits to be found (a minute and a half without music,
    2026-11-16)."""
    app = server.create_app(server.ServerConfig(var_dir=tmp_path / "var", lost_after=0.3))
    host = TestServer(app)
    await host.start_server()
    address = f"http://127.0.0.1:{host.port}"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(address + "/ws/sensor") as sensor_side, session.ws_connect(address + "/ws/ui") as page:
            await page.receive(timeout=2)                      # the page's first picture of things
            assert len(app["link"]._sensor_sockets) == 1
            stopping = asyncio.ensure_future(host.close())
            for socket in (sensor_side, page):
                message = await socket.receive(timeout=2)
                assert message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED), message
            await asyncio.wait_for(stopping, timeout=5)
    assert app["link"].sensors == [] and not app["link"]._sensor_sockets


async def test_the_sensor_waiting_for_the_game_shows_on_the_page(running):
    app, address = running
    scenario = {"screen": [1920, 1080], "steps": [{"at": 0.0, "in_front": False}, {"at": 4.0}]}
    await play(scenario, address, speed=10.0)
    shot = await get_json(address, "/api/snapshot")
    texts = [entry["text"] for entry in shot["log"]]
    assert "Sensor: the game is not the window in front." in texts
    assert shot["counts"]["pictures"] == 0, "nothing is copied while the game is in the background"


async def test_switching_away_from_the_game_stops_the_copying_at_once(running):
    app, address = running
    scenario = {"screen": [1920, 1080], "steps": [{"at": 3.0, "in_front": False}, {"at": 8.0}]}
    await play(scenario, address, speed=10.0)
    link = app["link"]
    texts = [entry["text"] for entry in link.log]
    assert "Sensor: the game is not the window in front." in texts
    before = [entry for entry in link.log if entry["text"].startswith("Strip found")]
    assert len(before) == 1
    # While the game was in front the strip was read steadily; after the switch nothing more came.
    assert link.counts["read"] == link.counts["pictures"] - 1
    assert link.counts["no_strip"] == 1, "only the bottom band of the first look had no strip"


async def test_a_faint_strip_is_found_and_followed_end_to_end(running):
    """The real sensor loop against a pretend game that draws its strip a fifth as bright, in
    squares of two pixels: found within a second or so, then read as steadily as a bright one."""
    app, address = running
    scenario = {"screen": [1920, 1080], "cell": 2, "ink": 20,
                "steps": [{"at": 3.0, "set": {"indoors": True}}, {"at": 6.0}]}
    await play(scenario, address, speed=10.0)
    shot = await get_json(address, "/api/snapshot")
    assert shot["strip"]["found"] and shot["strip"]["faint"] is True and shot["strip"]["pitch"] == 2.0
    assert shot["state"]["indoors"] is True and shot["counts"]["checksum"] == 0
    texts = [entry["text"] for entry in shot["log"]]
    assert "The strip's squares are faint now; it is read all the same." in texts
    assert any(text.startswith("Strip found at 18, 2: 688 x 4 px") for text in texts)


async def test_the_sensor_window_is_told_when_nothing_can_be_heard(tmp_path):
    """The sound comes out of a player page. With the game being read and no such page open,
    FreeRock looks as if it were working while nothing can be heard, so the sensor's window,
    which is what the person at the gaming PC is looking at, is told. Once for each change."""
    clock = {"now": 50.0}
    app = server.create_app(server.ServerConfig(var_dir=tmp_path / "var"), clock=lambda: clock["now"])
    link: server.LinkService = app["link"]
    assert link.snapshot()["player"] is None, "a server without the music side says nothing about sound"
    heard = {"connected": 0, "playing": 0}
    link.music = lambda: heard
    session = sim.SimSession({"screen": [1920, 1080]}, say=lambda *_: None)
    connection = link.sensor_connected("test")
    connection.server_address = "http://192.168.1.5:8765"

    def look(seconds):
        clock["now"] += seconds
        picture = sensor.Picture(sensor.PART_TOP, 1920, sensor.BAND, 0, 0, 1920, 1080, 1,
                                 session.copy(0, 0, 1920, sensor.BAND))
        link.take_picture(picture, connection)
        link.tick()
        said, connection.orders = [order["text"] for order in connection.orders], []
        return said

    assert look(0) == [], "a sensor that has just connected: the player page may be on its way"
    said = look(11)
    assert len(said) == 1 and "no player page is open" in said[0] and "http://192.168.1.5:8765/player" in said[0]
    assert look(5) == [] and look(5) == [], "said once"
    heard["connected"] = 1
    assert look(1) == ["the player page is open but has not started playing. Click Start the music on it "
                       "(http://192.168.1.5:8765/player)."]
    heard["playing"] = 1
    assert look(1) == ["the player page is playing."]
    assert look(30) == []
    heard["connected"] = heard["playing"] = 0
    assert "no player page is open" in look(1)[0]
    assert link.snapshot()["player"] == {"connected": 0, "playing": 0}
    link.close()


async def test_a_sensor_that_finds_the_player_already_playing_is_told_nothing(tmp_path):
    clock = {"now": 50.0}
    app = server.create_app(server.ServerConfig(var_dir=tmp_path / "var"), clock=lambda: clock["now"])
    link: server.LinkService = app["link"]
    link.music = lambda: {"connected": 1, "playing": 1}
    session = sim.SimSession({"screen": [1920, 1080]}, say=lambda *_: None)
    connection = link.sensor_connected("test")
    for _ in range(3):
        clock["now"] += 11
        link.take_picture(sensor.Picture(sensor.PART_TOP, 1920, sensor.BAND, 0, 0, 1920, 1080, 1,
                                         session.copy(0, 0, 1920, sensor.BAND)), connection)
        link.tick()
    assert connection.orders == []
    link.close()


async def test_the_game_closing_ends_the_link_at_once(running):
    app, address = running
    scenario = {"screen": [1920, 1080], "steps": [{"at": 3.0}]}
    await play(scenario, address, speed=10.0)
    link = app["link"]
    assert link.tracker.link in (state.Link.LIVE, state.Link.STALE)
    connection = link.sensor_connected("after")
    link.take_status({"type": "status", "window": None, "in_front": False, "note": "no window"}, connection)
    assert link.tracker.link is state.Link.LOST
    link.sensor_disconnected(connection)
