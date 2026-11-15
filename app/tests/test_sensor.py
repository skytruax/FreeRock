"""The sensor script: its wire format, its small WebSocket client, its loop, and the addon installer.

The loop is run here with a pretend window and a pretend screen copy. What cannot be run on this
machine is the Windows part: finding the real game window and copying the real screen.
"""
import io
import json
import pathlib
import zipfile

import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer

from freerock.web import sensor


# -- wire format ------------------------------------------------------------------
def test_pictures_pack_and_unpack():
    picture = sensor.Picture(sensor.PART_STRIP, 5, 2, 18, 0, 2560, 1440, 4_000_000_123, bytes(range(40)))
    for compress in (True, False):
        message = sensor.pack_picture(picture, compress=compress)
        assert message[:4] == b"FRK1"
        unpacked = sensor.unpack_picture(message)
        assert unpacked == dataclass_with(picture, count=picture.count & 0xFFFFFFFF)


def dataclass_with(picture, **changes):
    import dataclasses
    return dataclasses.replace(picture, **changes)


def test_malformed_pictures_are_refused():
    good = sensor.pack_picture(sensor.Picture(0, 2, 2, 0, 0, 100, 100, 1, bytes(16)), compress=False)
    with pytest.raises(ValueError, match="at least"):
        sensor.unpack_picture(good[:10])
    with pytest.raises(ValueError, match="not a FreeRock picture"):
        sensor.unpack_picture(b"NOPE" + good[4:])
    with pytest.raises(ValueError, match="need 16 bytes"):
        sensor.unpack_picture(good[:-3])
    with pytest.raises(ValueError, match="need 16 bytes"):
        sensor.pack_picture(sensor.Picture(0, 2, 2, 0, 0, 100, 100, 1, bytes(15)))


def test_the_script_can_be_run_by_uv_from_a_url():
    source = pathlib.Path(sensor.__file__).read_text(encoding="utf-8")
    lines = source.splitlines()
    assert lines[0] == "# /// script"
    end = lines.index("# ///")
    block = lines[1:end]
    assert any(line.startswith("# requires-python") for line in block)
    assert '# dependencies = ["mss>=9"]' in block, "mss is the only thing the sensor needs installed"
    assert source.count(f'DEFAULT_SERVER = "{sensor.DEFAULT_SERVER}"') == 1, "the line the server fills in"
    compile(source, "sensor.py", "exec")


# -- the WebSocket client ----------------------------------------------------------
async def _echo_app():
    async def handler(request):
        socket = web.WebSocketResponse(max_msg_size=8 * 1024 * 1024)
        await socket.prepare(request)
        await socket.ping(b"are you there")
        async for message in socket:
            if message.type == WSMsgType.TEXT:
                await socket.send_str("you said " + message.data)
            elif message.type == WSMsgType.BINARY:
                await socket.send_bytes(message.data[::-1])
        return socket

    app = web.Application()
    app.router.add_get("/ws/sensor", handler)
    server = TestServer(app)
    await server.start_server()
    return server


async def test_the_websocket_client_talks_to_a_real_server():
    import asyncio

    server = await _echo_app()
    try:
        def talk():
            link = sensor.WebSocket(sensor.websocket_url(f"http://127.0.0.1:{server.port}"))
            link.receive(0.0)  # the server's ping may be waiting; receive answers it and hands nothing back
            link.send_text("hello é")
            assert link.receive(2.0) == "you said hello é"
            small, medium, large = bytes(range(100)), bytes(range(256)) * 20, bytes(range(256)) * 900
            for payload in (small, medium, large):  # the three length encodings
                link.send_binary(payload)
                assert link.receive(2.0) == payload[::-1]
            assert link.receive(0.05) is None, "nothing more to read"
            link.close()

        await asyncio.to_thread(talk)
    finally:
        await server.close()


async def test_a_server_that_is_not_freerock_is_refused_at_the_handshake():
    import asyncio

    async def plain(request):
        return web.Response(text="just a web page")

    app = web.Application()
    app.router.add_get("/ws/sensor", plain)
    server = TestServer(app)
    await server.start_server()
    try:
        with pytest.raises(sensor.LinkClosed, match="did not accept"):
            await asyncio.to_thread(sensor.WebSocket, sensor.websocket_url(f"http://127.0.0.1:{server.port}"))
    finally:
        await server.close()


def test_nothing_listening_is_an_ordinary_connection_error():
    import socket

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    with pytest.raises(OSError):
        sensor.WebSocket(f"ws://127.0.0.1:{port}/ws/sensor", timeout=1.0)


# -- the loop -----------------------------------------------------------------------
class FakeLink:
    def __init__(self):
        self.incoming, self.texts, self.pictures = [], [], []

    def receive(self, wait=0.0):
        return self.incoming.pop(0) if self.incoming else None

    def send_text(self, text):
        self.texts.append(json.loads(text))

    def send_binary(self, data):
        self.pictures.append(sensor.unpack_picture(data))


class FakeScreen:
    def __init__(self, width=2560, height=1440):
        self.window = sensor.Window(100, 50, width, height, True)
        self.reason = None
        self.fill = 7
        self.copies = []

    def find_window(self):
        if self.reason:
            raise sensor.NoWindow(self.reason)
        return self.window

    def copy(self, left, top, width, height):
        self.copies.append((left, top, width, height))
        return bytes([self.fill]) * (width * height * 4)


def make_sensor(**options):
    link, screen = FakeLink(), FakeScreen()
    clock = {"now": 0.0}
    said = []
    loop = sensor.Sensor(link, screen.find_window, screen.copy, clock=lambda: clock["now"], say=said.append, **options)
    return loop, link, screen, clock, said


def test_while_looking_it_sends_a_band_from_each_edge_twice_a_second():
    loop, link, screen, clock, said = make_sensor()
    loop.step()
    top, bottom = link.pictures
    assert (top.part, top.x, top.y, top.width, top.height) == (sensor.PART_TOP, 0, 0, 2560, sensor.BAND)
    assert (bottom.part, bottom.y, bottom.height) == (sensor.PART_BOTTOM, 1440 - sensor.BAND, sensor.BAND)
    assert (top.window_width, top.window_height) == (2560, 1440)
    assert screen.copies[0] == (100, 50, 2560, sensor.BAND), "the copy is taken at the window's place on the screen"
    assert screen.copies[1] == (100, 50 + 1440 - sensor.BAND, 2560, sensor.BAND)
    clock["now"] = 0.3
    loop.step()
    assert len(link.pictures) == 2, "not yet"
    clock["now"] = 0.55
    loop.step()
    assert len(link.pictures) == 4
    assert any("Game window found: 2560 x 1440" in line for line in said)


def test_once_told_where_the_strip_is_it_sends_only_that_and_only_when_it_changes():
    loop, link, screen, clock, said = make_sensor()
    loop.step()
    link.pictures.clear()
    screen.copies.clear()
    link.incoming.append(json.dumps({"type": "mode", "mode": "track", "roi": [12, 0, 1044, 12]}))
    clock["now"] = 0.1
    assert loop.step() == sensor.TRACK_EVERY
    assert loop.mode == "track"
    (picture,) = link.pictures
    assert (picture.part, picture.x, picture.y, picture.width, picture.height) == (sensor.PART_STRIP, 12, 0, 1044, 12)
    assert screen.copies == [(112, 50, 1044, 12)]
    for moment in (0.15, 0.2, 0.25):
        clock["now"] = moment
        loop.step()
    assert len(link.pictures) == 1, "unchanged pixels are not sent again"
    assert loop.unchanged == 3
    screen.fill = 9
    clock["now"] = 0.3
    loop.step()
    assert len(link.pictures) == 2, "changed pixels are sent at once"
    clock["now"] = 1.35
    loop.step()
    assert len(link.pictures) == 3, "and an unchanged strip is still sent once a second"
    assert any("found the strip" in line for line in said)


def test_it_goes_back_to_looking_when_told_or_when_the_window_changes_size():
    loop, link, screen, clock, said = make_sensor()
    loop.step()
    link.incoming.append(json.dumps({"type": "mode", "mode": "track", "roi": [12, 0, 1044, 12]}))
    clock["now"] = 0.1
    loop.step()
    link.incoming.append(json.dumps({"type": "mode", "mode": "search"}))
    clock["now"] = 0.2
    loop.step()
    assert loop.mode == "search" and loop.roi is None
    assert any("lost sight" in line for line in said)
    # A strip position that no longer fits the window.
    link.incoming.append(json.dumps({"type": "mode", "mode": "track", "roi": [2000, 0, 1044, 12]}))
    clock["now"] = 0.3
    loop.step()
    assert loop.mode == "search"


def test_no_window_and_a_window_that_is_not_in_front_copy_nothing_and_say_why():
    loop, link, screen, clock, said = make_sensor()
    screen.reason = 'no window titled "World of Warcraft" is open; start the game'
    loop.step()
    assert link.pictures == [] and screen.copies == []
    status = [text for text in link.texts if text["type"] == "status"][-1]
    assert status["window"] is None and "start the game" in status["note"]
    assert any("Waiting: no window" in line for line in said)

    screen.reason, screen.window = None, sensor.Window(0, 0, 2560, 1440, False)
    clock["now"] = 1.1
    loop.step()
    assert link.pictures == [] and screen.copies == []
    status = [text for text in link.texts if text["type"] == "status"][-1]
    assert status["window"] == [2560, 1440] and status["in_front"] is False
    assert status["note"] == "the game is not the window in front"

    screen.window = sensor.Window(0, 0, 2560, 1440, True)
    clock["now"] = 2.2
    loop.step()
    assert len(link.pictures) == 2, "copying starts again when the game is in front"


def test_switching_away_is_noticed_before_the_next_copy_not_a_second_later():
    in_front = {"now": True}
    link, screen = FakeLink(), FakeScreen()
    clock = {"now": 0.0}
    loop = sensor.Sensor(link, screen.find_window, screen.copy, clock=lambda: clock["now"], say=lambda text: None,
                         in_front=lambda window: in_front["now"])
    loop.step()
    link.incoming.append(json.dumps({"type": "mode", "mode": "track", "roi": [12, 0, 1044, 12]}))
    clock["now"] = 0.1
    loop.step()
    copies = len(screen.copies)
    in_front["now"] = False  # the player switches to another window
    clock["now"] = 0.15       # well inside the second between window look-ups
    loop.step()
    assert len(screen.copies) == copies, "nothing of the other window is copied"
    assert loop.note == "the game is not the window in front"
    in_front["now"] = True
    clock["now"] = 1.2
    loop.step()
    assert len(screen.copies) > copies, "and copying resumes when the game is back in front"


def test_always_keeps_copying_in_the_background():
    loop, link, screen, clock, said = make_sensor(even_in_background=True)
    screen.window = sensor.Window(0, 0, 2560, 1440, False)
    loop.step()
    assert len(link.pictures) == 2


def test_status_goes_out_every_second_with_the_copy_time():
    loop, link, screen, clock, said = make_sensor()
    for moment in (0.0, 0.5, 1.0, 1.5, 2.0):
        clock["now"] = moment
        loop.step()
    statuses = [text for text in link.texts if text["type"] == "status"]
    assert len(statuses) == 3
    assert statuses[-1]["mode"] == "search" and statuses[-1]["sent"] >= 6
    assert statuses[-1]["copy_ms"] is not None


def test_an_order_the_sensor_does_not_know_is_an_error_not_a_shrug():
    loop, link, screen, clock, said = make_sensor()
    link.incoming.append(json.dumps({"type": "mode", "mode": "dance"}))
    with pytest.raises(ValueError, match="does not know"):
        loop.step()


# -- installing the addon --------------------------------------------------------------
def addon_zip(extra=None, toc=True):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as bundle:
        if toc:
            bundle.writestr("FreeRock/FreeRock.toc", "## Interface: 16001\n")
        bundle.writestr("FreeRock/Core.lua", "-- core\n")
        for name, text in (extra or {}).items():
            bundle.writestr(name, text)
    return data.getvalue()


def test_the_addons_folder_is_found_from_the_running_game_then_the_registry_then_the_usual_places(tmp_path):
    game = tmp_path / "World of Warcraft" / "_forever_"
    game.mkdir(parents=True)
    other = tmp_path / "Other" / "World of Warcraft" / "_forever_"
    other.mkdir(parents=True)
    retail = tmp_path / "World of Warcraft" / "_retail_"
    retail.mkdir()
    found = sensor.addon_folders(str(game / "WowF.exe"), str(retail), [other.parent, tmp_path / "missing"])
    assert found == [game / "Interface" / "AddOns", other / "Interface" / "AddOns"]
    # Without the running game, the registry's folder is a sibling of _forever_.
    assert sensor.addon_folders(None, str(retail), [])[0] == game / "Interface" / "AddOns"
    # A game folder that is not Forever is not offered.
    assert sensor.addon_folders(str(retail / "Wow.exe"), None, []) == []


def test_installing_replaces_the_old_addon_folder_and_nothing_else(tmp_path):
    addons = tmp_path / "_forever_" / "Interface" / "AddOns"
    (addons / "FreeRock").mkdir(parents=True)
    (addons / "FreeRock" / "Old.lua").write_text("stale")
    (addons / "SomeoneElse").mkdir()
    (addons / "SomeoneElse" / "keep.lua").write_text("keep")
    count = sensor.unpack_addon(addon_zip(), addons)
    assert count == 2
    assert sorted(path.name for path in (addons / "FreeRock").iterdir()) == ["Core.lua", "FreeRock.toc"]
    assert (addons / "SomeoneElse" / "keep.lua").read_text() == "keep"


def test_installing_creates_the_addons_folder_when_the_game_has_none_yet(tmp_path):
    addons = tmp_path / "_forever_" / "Interface" / "AddOns"
    assert sensor.unpack_addon(addon_zip(), addons) == 2
    assert (addons / "FreeRock" / "FreeRock.toc").is_file()


@pytest.mark.parametrize("name", ["../evil.lua", "FreeRock/../../evil.lua", "/abs/evil.lua", "Other/x.lua", "FreeRock\\..\\evil.lua"])
def test_an_archive_that_reaches_outside_the_addon_folder_is_refused_before_anything_is_touched(tmp_path, name):
    addons = tmp_path / "AddOns"
    (addons / "FreeRock").mkdir(parents=True)
    (addons / "FreeRock" / "Old.lua").write_text("still here")
    with pytest.raises(ValueError, match="outside the FreeRock folder"):
        sensor.unpack_addon(addon_zip({name: "bad"}), addons)
    assert (addons / "FreeRock" / "Old.lua").read_text() == "still here"
    assert not (tmp_path / "evil.lua").exists()


def test_an_archive_without_the_toc_is_not_the_addon(tmp_path):
    with pytest.raises(ValueError, match="no FreeRock.toc"):
        sensor.unpack_addon(addon_zip(toc=False), tmp_path / "AddOns")
