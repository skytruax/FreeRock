"""The music side of the server: from game state on the hub to messages and phrases for the player."""
import asyncio
import json

from aiohttp.test_utils import TestClient, TestServer

from freerock import conductor as music
from freerock import forever
from freerock import state as game
from freerock.server import ServerConfig, create_app
from freerock.settings import Settings
from test_forever import fill

# A loose phrase for each pool the music cannot start without: a drone, a tune, a rhythm part,
# drums and bass.
STARTING = [("texture", 0), ("lead", 0), ("rhythm", 1), ("drums", 1), ("bass", 1)]


class Clock:
    """A clock the tests can move forward, so a wait of several seconds takes no time."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


async def running(tmp_path, clock=None, settings=None):
    """A server with the music side attached, its buckets in the test's own folder. Nothing it
    writes goes outside that folder."""
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    settings = settings or Settings(var_dir=tmp_path / "var")
    conductor = music.attach(app, settings=settings, **({"clock": clock} if clock else {}))
    client = TestClient(TestServer(app))
    await client.start_server()
    return client, app, conductor


def publish(app, **fields):
    """Says the game is in this state, as the link would after reading the strip."""
    hub = app["hub"]
    if hub.link is not game.Link.LIVE:
        hub.publish(game.LinkChanged(link=game.Link.LIVE, previous=hub.link))
    previous = hub.state
    state = game.GameState(**{"daytime": True, **fields})
    hub.publish(game.StateChanged(state=state, previous=previous, changed=frozenset(fields)))


async def next_of(socket, kind, timeout=3.0):
    """The next message of one kind, skipping the once-a-second nudges."""
    while True:
        message = json.loads(await asyncio.wait_for(socket.receive_str(), timeout))
        if message["type"] == kind:
            return message


async def until(condition, timeout=5.0):
    for _ in range(int(timeout / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("it never happened")


async def test_a_player_is_told_the_bucket_and_the_target(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), STARTING)
        socket = await client.ws_connect("/ws/player")
        assert (await next_of(socket, "hello"))["type"] == "hello"
        publish(app, zone_name="Elwynn Forest", subzone_name="Goldshire")
        described = (await next_of(socket, "bucket"))["bucket"]
        assert described["key"] == "knight/elwynn-forest" and described["style"] == "Knight Rock"
        assert described["rate"] == 48000 and described["bar_frames"] == 48000 * 240 // described["bpm"]
        assert [clip["channel"] for clip in described["clips"]] == [channel for channel, _ in STARTING]
        target = await next_of(socket, "target")
        assert target["target"]["place"] == "wander" and target["target"]["bass"] == 0.0
        assert set(target["target"]["channels"]) == set(forever.CHANNELS)
        assert target["where"] == {"zone": "Elwynn Forest", "subzone": "Goldshire", "instance": None}
        assert target["link"] == "live"
        assert any("Playing the Knight Rock song" in note for note in conductor.notes)

        # A fight against an elite: the bass and the drums come up whole, and play their hard phrases.
        publish(app, zone_name="Elwynn Forest", in_combat=True, target_class="elite")
        fight = (await next_of(socket, "target"))["target"]
        assert fight["bass"] == 1.0 and fight["drums"] == 1.0 and fight["intensity"] >= 0.8
        assert fight["channels"]["drums"] == {"level": 1.0, "tier": 2}
        await socket.close()
    finally:
        await client.close()


async def test_a_player_that_joins_late_is_brought_up_to_date(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), STARTING)
        publish(app, zone_name="Elwynn Forest", indoors=True)
        await until(lambda: conductor.target is not None and conductor.bucket is not None)
        socket = await client.ws_connect("/ws/player")
        # What the game asks for comes before the music, so that the page knows where the player
        # is before it chooses what to play.
        target = await next_of(socket, "target")
        assert target["target"]["lowpass_hz"] == 2500.0
        assert (await next_of(socket, "bucket"))["bucket"]["key"] == "knight/elwynn-forest"
        await socket.close()
    finally:
        await client.close()


async def test_the_phrases_and_parts_are_there_to_be_fetched_whole(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        bucket = conductor.buckets.get("Elwynn Forest", "knight")
        fill(bucket, STARTING)
        clip = bucket.clips[0]
        response = await client.get("/phrase/knight/elwynn-forest/" + clip.id)
        assert response.status == 200 and len(await response.read()) == clip.frames * 4
        assert (await client.get("/phrase/knight/elwynn-forest/nothing")).status == 404
        assert (await client.get("/phrase/knight/nowhere/nothing")).status == 404
    finally:
        await client.close()


async def test_the_player_page_and_its_files_are_served(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        page = await client.get("/player")
        assert page.status == 200 and "FreeRock" in await page.text()
        for name in ("forever.js", "player.js", "player.css"):
            assert (await client.get("/player/" + name)).status == 200
        assert (await client.get("/player/secrets.txt")).status == 404
    finally:
        await client.close()


async def test_skip_from_the_game_moves_the_player_on(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        app["hub"].publish(game.CommandReceived(name="skip", count=1))
        assert (await next_of(socket, "skip"))["type"] == "skip"
        await socket.close()
    finally:
        await client.close()


async def test_losing_sight_of_the_game_fades_the_music_out(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        assert (await next_of(socket, "target"))["target"]["silent"] is False
        app["hub"].publish(game.LinkChanged(link=game.Link.LOST, previous=game.Link.LIVE))
        gone = await next_of(socket, "target")
        assert gone["target"]["silent"] is True and gone["link"] == "lost"
        await socket.close()
    finally:
        await client.close()


async def test_the_pretend_game_moves_the_music_like_the_real_one(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), STARTING)
        socket = await client.ws_connect("/ws/player")
        answer = await client.post("/api/pretend", json={"zone_name": "Elwynn Forest", "daytime": True, "indoors": True})
        assert answer.status == 200
        assert (await next_of(socket, "bucket"))["bucket"]["key"] == "knight/elwynn-forest"
        target = await next_of(socket, "target")
        assert target["target"]["lowpass_hz"] == 2500.0 and target["link"] == "live"
        await client.post("/api/pretend", json={"zone_name": "Elwynn Forest", "daytime": True, "in_combat": True})
        assert (await next_of(socket, "target"))["target"]["bass"] == 1.0
        assert (await client.post("/api/pretend", json={"health": 12})).status == 400
        zones = await (await client.get("/api/zones")).json()
        assert len(zones) == 50 and "Elwynn Forest" in zones and zones == sorted(zones)
        await socket.close()
    finally:
        await client.close()


async def test_the_volume_set_in_the_game_reaches_the_player(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        assert (await next_of(socket, "target"))["game_volume"] == 70       # the addon's starting volume
        publish(app, zone_name="Elwynn Forest", volume=35)
        assert (await next_of(socket, "target"))["game_volume"] == 35
        await socket.close()
    finally:
        await client.close()


async def test_the_game_link_knows_whether_anything_can_be_heard(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        assert (await (await client.get("/api/snapshot")).json())["player"] == {"connected": 0, "playing": 0}
        socket = await client.ws_connect("/ws/player")
        await next_of(socket, "hello")
        assert (await (await client.get("/api/snapshot")).json())["player"] == {"connected": 1, "playing": 0}
        await socket.send_str(json.dumps({"type": "status", "context": "running", "started": True}))
        await asyncio.sleep(0.2)
        assert (await (await client.get("/api/snapshot")).json())["player"] == {"connected": 1, "playing": 1}
        await socket.close()
        await asyncio.sleep(0.2)
        shot = await (await client.get("/api/snapshot")).json()
        assert shot["player"] == {"connected": 0, "playing": 0}
        said = [entry["text"] for entry in shot["log"] if entry["kind"] == "player"]
        assert said == ["A player page was opened from 127.0.0.1.", "The player page at 127.0.0.1 was closed."]
    finally:
        await client.close()


async def test_a_moment_in_the_game_brings_the_whole_band_in(tmp_path):
    client, app, conductor = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        calm = await next_of(socket, "target")
        assert calm["target"]["bass"] == 0.0
        app["hub"].publish(game.MomentReceived("level_up", 1))
        while True:
            target = (await next_of(socket, "target"))["target"]
            if target["bass"] == 1.0:
                break
        assert target["intensity"] == 1.0 and "a level gained" in target["why"]
        assert "A moment in the game: level up." in conductor.notes
        await socket.close()
    finally:
        await client.close()


async def test_a_page_left_playing_over_a_restart_plays_on_for_half_a_minute_and_is_then_told_to_be_quiet(tmp_path):
    """After a restart the program has not seen the game yet. A player page that reconnects (it
    may still be playing what it had) is left to it while the game's sensor finds the new
    server, and is sent silence if the game has still not been seen half a minute on."""
    clock = Clock()
    client, app, conductor = await running(tmp_path, clock=clock)
    try:
        socket = await client.ws_connect("/ws/player")
        await conductor.step()
        assert conductor.target is None, "a page that was playing was told to be quiet the moment the server came back"
        clock.now += music.RESTART_GRACE_S + 1.0
        quiet = await next_of(socket, "target")
        assert quiet["target"]["silent"] is True and quiet["target"]["why"] == ["the game has not been seen yet"]
        assert quiet["where"] == {"zone": None, "subzone": None, "instance": None}
        late = await client.ws_connect("/ws/player")
        assert (await next_of(late, "target"))["target"]["silent"] is True, "a page that connects later hears it too"
        publish(app, zone_name="Elwynn Forest")
        while True:
            target = (await next_of(socket, "target"))["target"]
            if not target["silent"]:
                break
        assert target["place"] == "wander"
        await socket.close()
        await late.close()
    finally:
        await client.close()


async def test_the_player_is_told_how_often_the_song_falls_silent_and_for_how_long(tmp_path):
    settings = Settings(var_dir=tmp_path / "var", rest_every_minutes=9.0, rest_seconds=45.0)
    client, app, conductor = await running(tmp_path, settings=settings)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), STARTING)
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        described = (await next_of(socket, "bucket"))["bucket"]
        assert described["rest"] == {"every_s": 540.0, "for_s": 45.0}
        await socket.close()
    finally:
        await client.close()
