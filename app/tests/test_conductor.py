"""The music side of the server: from game state on the hub to messages and audio for the player."""
import asyncio
import json

import numpy as np
import pytest
from aiohttp.test_utils import TestClient, TestServer

from freerock import conductor as music
from freerock import state as game
from freerock.composer import ZoneProfile, core_suite
from freerock.library import Library
from freerock.server import ServerConfig, create_app
from test_library import made_up_track

ZONE = ZoneProfile(key="elwynn-forest", bpm=120, tonic="G mixolydian", colours=["fiddle"])


async def running(tmp_path, zones=("elwynn-forest",)):
    """A server with the music side attached and made-up music for `zones` in its library."""
    library = Library(tmp_path / "library")
    assets = {}
    for zone in zones:
        request = core_suite(ZONE, seed=3)
        mix, layers = made_up_track(request)
        assets[zone] = library.add(zone=zone, set_name="core", request=request, mix=mix, layers=layers)
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    conductor = music.attach(app, library=library)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client, app, conductor, assets


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


async def test_a_player_is_told_the_music_and_the_target(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        assert (await next_of(socket, "hello"))["type"] == "hello"
        publish(app, zone_name="Elwynn Forest", subzone_name="Goldshire")
        asset = await next_of(socket, "asset")
        assert asset["asset"]["id"] == assets["elwynn-forest"].id and asset["borrowed"] is False
        assert asset["asset"]["bar_frames"] == 96000 and len(asset["asset"]["sections"]) == 6
        target = await next_of(socket, "target")
        assert target["target"]["place"] == "wander" and target["target"]["bass"] == 0.0
        assert target["where"] == {"zone": "Elwynn Forest", "subzone": "Goldshire", "instance": None}
        assert target["link"] == "live"

        publish(app, zone_name="Elwynn Forest", in_combat=True, target_class="elite")
        fight = await next_of(socket, "target")
        assert fight["target"]["bass"] == 1.0 and fight["target"]["intensity"] >= 0.8
        battle = await next_of(socket, "target", timeout=5.0)        # two seconds against an elite
        assert battle["target"]["place"] == "battle"
        await socket.close()
    finally:
        await client.close()


async def test_a_player_that_joins_late_is_brought_up_to_date(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        publish(app, zone_name="Elwynn Forest", indoors=True)
        await asyncio.sleep(0.6)
        socket = await client.ws_connect("/ws/player")
        assert (await next_of(socket, "asset"))["asset"]["id"] == assets["elwynn-forest"].id
        target = await next_of(socket, "target")
        assert target["target"]["lowpass_hz"] == 6000.0
        await socket.close()
    finally:
        await client.close()


async def test_a_zone_without_music_borrows_and_says_so(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Westfall")
        asset = await next_of(socket, "asset")
        assert asset["borrowed"] is True and asset["asset"]["zone"] == "elwynn-forest"
        status = await (await client.get("/api/music")).json()
        assert "Westfall has no music of its own yet" in " ".join(status["notes"])
        await socket.close()
    finally:
        await client.close()


async def test_each_zone_gets_its_own_music_when_it_has_some(tmp_path):
    client, app, conductor, assets = await running(tmp_path, zones=("elwynn-forest", "westfall"))
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Westfall")
        assert (await next_of(socket, "asset"))["asset"]["id"] == assets["westfall"].id
        publish(app, zone_name="Elwynn Forest")
        assert (await next_of(socket, "asset"))["asset"]["id"] == assets["elwynn-forest"].id
        await socket.close()
    finally:
        await client.close()


async def test_audio_is_what_the_library_holds(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        asset = assets["elwynn-forest"]
        response = await client.get("/audio/%s/drums?start=96000&end=96480" % asset.id)
        assert response.status == 200
        assert await response.read() == conductor.library.samples(asset, "drums", 96000, 96480)
        assert (await client.get("/audio/%s/vocals?start=0&end=10" % asset.id)).status == 400
        assert (await client.get("/audio/nope/bed?start=0&end=10")).status == 400
        assert (await client.get("/audio/%s/bed?start=0&end=99999999" % asset.id)).status == 400
    finally:
        await client.close()


async def test_the_player_page_and_its_files_are_served(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        page = await client.get("/player")
        assert page.status == 200 and "FreeRock" in await page.text()
        for name in ("engine.js", "player.js", "player.css"):
            assert (await client.get("/player/" + name)).status == 200
        assert (await client.get("/player/secrets.txt")).status == 404
    finally:
        await client.close()


async def test_love_and_ban_from_the_game_mark_the_music(tmp_path):
    client, app, conductor, assets = await running(tmp_path, zones=("elwynn-forest", "westfall"))
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        playing = (await next_of(socket, "asset"))["asset"]["id"]
        app["hub"].publish(game.CommandReceived(name="love", count=1))
        await asyncio.sleep(0.4)
        assert conductor.library.get(playing).loved
        app["hub"].publish(game.CommandReceived(name="ban", count=2))
        other = await next_of(socket, "asset")                     # banned music is not played again
        assert other["asset"]["id"] != playing and conductor.library.get(playing).banned
        app["hub"].publish(game.CommandReceived(name="skip", count=3))
        assert (await next_of(socket, "skip"))["type"] == "skip"
        await socket.close()
    finally:
        await client.close()


async def test_losing_sight_of_the_game_fades_the_music_out(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
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


def test_slug():
    assert music.slug("Elwynn Forest") == "elwynn-forest" and music.slug("Un'Goro Crater") == "un-goro-crater"
    assert music.slug(None) is None and music.slug("!!!") is None
