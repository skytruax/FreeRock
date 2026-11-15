"""The music side of the server: from game state on the hub to messages and audio for the player."""
import asyncio
import json

import numpy as np
import pytest
from aiohttp.test_utils import TestClient, TestServer

from freerock import atlas
from freerock import conductor as music
from freerock import state as game
from freerock.composer import ZoneProfile, core_suite, fresh_set, second_set
from freerock.eleven import AllowanceExceeded
from freerock.ingest import Made, TrackFailedChecks
from freerock.library import Library
from freerock.playtime import Playtime
from freerock.server import ServerConfig, create_app
from freerock.settings import Settings
from test_library import made_up_track

ZONE = ZoneProfile(key="elwynn-forest", bpm=120, tonic="G mixolydian", colours=["fiddle"])


class Clock:
    """A clock the tests can move forward, so a wait of several seconds takes no time."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class StandInIngest:
    """Makes made-up music for a zone the way the real ingest would, without ElevenLabs.
    `failures` are raised, one per call, before it starts succeeding."""

    def __init__(self, library, failures=()):
        self.library = library
        self.failures = list(failures)
        self.calls = []

    async def core_suite(self, name, *, reroll=False):
        self.calls.append((name, reroll))
        await asyncio.sleep(0.05)
        if self.failures:
            raise self.failures.pop(0)
        profile = atlas.profile_for(name)
        request = core_suite(profile, seed=5, part_bars=atlas.part_bars(profile.bpm))
        mix, layers = made_up_track(request)
        asset = self.library.add(zone=profile.key, set_name="core", request=request, mix=mix, layers=layers)
        return Made(asset=asset, first_audio_s=5.8, total_s=11.6, split_s=77.0)

    async def later_set(self, core, name, kind, *, reroll=False):
        self.calls.append((name, kind))
        await asyncio.sleep(0.05)
        if self.failures:
            raise self.failures.pop(0)
        asset = add_set(self.library, core.zone, kind, seed=len(self.calls) + 10)
        return Made(asset=asset, first_audio_s=5.8, total_s=11.6, split_s=77.0)


def add_set(library, zone, kind, seed=3):
    """Puts a made-up set of one kind into the library for a zone."""
    request = {"core": core_suite, "second": second_set, "fresh": fresh_set}[kind](ZONE, seed=seed)
    mix, layers = made_up_track(request, seed=seed)
    return library.add(zone=zone, set_name=kind, request=request, mix=mix, layers=layers)


async def running(tmp_path, zones=("elwynn-forest",), failures=None, clock=None, sets=("core",)):
    """A server with the music side attached and made-up music for `zones` in its library. With
    `failures` (a list, possibly empty) it can also make music for zones that have none. Nothing
    it writes goes outside the test's own folder."""
    library = Library(tmp_path / "library")
    assets = {}
    for zone in zones:
        for kind in sets:
            made = add_set(library, zone, kind)
            assets.setdefault(zone, made)
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    ingest = StandInIngest(library, failures) if failures is not None else None
    settings = Settings(var_dir=tmp_path / "var")
    conductor = music.attach(app, library=library, ingest=ingest, settings=settings,
                             playtime=Playtime(tmp_path / "var" / "playtime.json"),
                             **({"clock": clock} if clock else {}))
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
        assert target["target"]["lowpass_hz"] == 2500.0
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
        assert (await next_of(socket, "target"))["music"] == {"zone": "elwynn-forest", "borrowed": True}
        status = await (await client.get("/api/music")).json()
        assert "Westfall has no music of its own yet" in " ".join(status["notes"])
        # Walking home, then on into another zone that also has none: the same music carries on,
        # and the player is told each time whether the place is borrowing it.
        publish(app, zone_name="Elwynn Forest")
        home = await next_of(socket, "target")
        assert home["music"] == {"zone": "elwynn-forest", "borrowed": False}
        publish(app, zone_name="Duskwood")
        away = await next_of(socket, "target")
        assert away["music"] == {"zone": "elwynn-forest", "borrowed": True}
        notes = (await (await client.get("/api/music")).json())["notes"]
        assert notes[-1] == "Duskwood has no music of its own yet; playing elwynn-forest's."
        assert notes.count("Westfall has no music of its own yet; playing elwynn-forest's.") == 1
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


async def test_music_is_made_for_a_zone_that_has_none(tmp_path):
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Westfall")
        assert (await next_of(socket, "asset"))["borrowed"] is True
        await asyncio.sleep(0.6)
        assert conductor.ingest.calls == [], "music was asked for before the player had stayed a moment"
        clock.now += 5
        own = await next_of(socket, "asset", timeout=10)
        assert own["borrowed"] is False and own["asset"]["zone"] == "westfall" and own["asset"]["bpm"] == 96
        assert conductor.ingest.calls == [("Westfall", False)]
        clock.now += 60
        await asyncio.sleep(0.6)
        assert len(conductor.ingest.calls) == 1, "music was made twice for one zone"
        notes = " ".join((await (await client.get("/api/music")).json())["notes"])
        assert "Making music for Westfall." in notes and "New music for Westfall is ready" in notes
        await socket.close()
    finally:
        await client.close()


async def test_nothing_is_made_on_a_flight_path_or_before_the_name_arrives(tmp_path):
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock)
    try:
        await client.ws_connect("/ws/player")               # somebody is listening
        publish(app, zone_name="Westfall", on_taxi=True, flying=True)
        await asyncio.sleep(0.4)
        clock.now += 30
        await asyncio.sleep(0.6)
        assert conductor.ingest.calls == []
        publish(app, zone_name=None)                         # a zone whose name has not arrived yet
        clock.now += 30
        await asyncio.sleep(0.6)
        assert conductor.ingest.calls == []
        publish(app, zone_name="Westfall")                   # landed: the wait starts from here
        await asyncio.sleep(0.6)
        assert conductor.ingest.calls == []
        clock.now += 5
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [("Westfall", False)]
    finally:
        await client.close()


async def test_a_track_that_fails_its_checks_is_tried_once_more(tmp_path):
    clock = Clock()
    bad = {"failed": ["Battle is 2.50% off tempo"]}
    failures = [TrackFailedChecks("westfall", bad), TrackFailedChecks("westfall", bad)]
    client, app, conductor, assets = await running(tmp_path, failures=failures, clock=clock)
    try:
        await client.ws_connect("/ws/player")               # somebody is listening
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.4)
        clock.now += 5
        await asyncio.sleep(1.5)
        assert conductor.ingest.calls == [("Westfall", False), ("Westfall", True)]
        clock.now += 600
        await asyncio.sleep(0.8)
        assert len(conductor.ingest.calls) == 2, "a third try was made"
        notes = " ".join(conductor.notes)
        assert "off tempo" in notes and "Trying once more." in notes and "Not trying again today." in notes
        assert conductor.library.assets("westfall") == []
    finally:
        await client.close()


async def test_at_the_allowance_it_waits_and_says_why(tmp_path):
    clock = Clock()
    refusal = AllowanceExceeded("FreeRock did not make this call (core suite): 2.80 min asked for, 1.20 left of today's allowance.")
    client, app, conductor, assets = await running(tmp_path, failures=[refusal], clock=clock)
    try:
        await client.ws_connect("/ws/player")               # somebody is listening
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.4)
        clock.now += 5
        await asyncio.sleep(1.0)
        assert len(conductor.ingest.calls) == 1 and "today's allowance" in " ".join(conductor.notes)
        clock.now += 300
        await asyncio.sleep(0.8)
        assert len(conductor.ingest.calls) == 1, "it asked again inside the pause"
        clock.now += 400
        await asyncio.sleep(1.2)
        assert conductor.ingest.calls == [("Westfall", False), ("Westfall", False)]
        assert [asset.zone for asset in conductor.library.assets("westfall")] == ["westfall"]
    finally:
        await client.close()


async def test_the_pretend_game_moves_the_music_like_the_real_one(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        answer = await client.post("/api/pretend", json={"zone_name": "Elwynn Forest", "daytime": True, "indoors": True})
        assert answer.status == 200
        assert (await next_of(socket, "asset"))["asset"]["zone"] == "elwynn-forest"
        target = await next_of(socket, "target")
        assert target["target"]["lowpass_hz"] == 2500.0 and target["link"] == "live"
        await client.post("/api/pretend", json={"zone_name": "Elwynn Forest", "daytime": True, "in_combat": True})
        assert (await next_of(socket, "target"))["target"]["bass"] == 1.0
        assert (await client.post("/api/pretend", json={"health": 12})).status == 400
        zones = await (await client.get("/api/zones")).json()
        assert len(zones) == 50
        assert {"name": "Elwynn Forest", "has_music": True} in zones and {"name": "Westfall", "has_music": False} in zones
        await socket.close()
    finally:
        await client.close()


async def test_the_volume_set_in_the_game_reaches_the_player(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        assert (await next_of(socket, "target"))["game_volume"] == 70       # the addon's starting volume
        publish(app, zone_name="Elwynn Forest", volume=35)
        assert (await next_of(socket, "target"))["game_volume"] == 35
        await socket.close()
    finally:
        await client.close()


async def test_the_pretend_game_makes_new_music_only_when_asked_to(tmp_path):
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock)
    try:
        await client.ws_connect("/ws/player")               # somebody is listening
        await client.post("/api/pretend", json={"zone_name": "Westfall", "daytime": True})
        await asyncio.sleep(0.4)
        clock.now += 30
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [], "a page spent the allowance without being asked to"
        await client.post("/api/pretend", json={"zone_name": "Westfall", "daytime": True, "make_new_music": True})
        await asyncio.sleep(0.4)
        clock.now += 5
        await asyncio.sleep(1.0)
        assert conductor.ingest.calls == [("Westfall", False)]
    finally:
        await client.close()


async def test_nothing_is_made_while_no_player_page_is_open(tmp_path):
    """Music nobody can hear is not paid for: with the game in sight but no player page open,
    a zone without music waits. It is made once somebody is listening."""
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock)
    try:
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.4)
        clock.now += 60
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [], "music was made with nobody listening"
        socket = await client.ws_connect("/ws/player")
        await asyncio.sleep(0.6)
        assert conductor.ingest.calls == [], "the wait starts when the page opens"
        clock.now += 5
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [("Westfall", False)]
        await socket.close()
    finally:
        await client.close()


async def test_music_turned_away_twice_is_not_asked_for_again_after_a_restart(tmp_path):
    """The count of requests is kept in a file for the day, so restarting the server does not
    spend the allowance on a zone whose music has just failed its checks twice."""
    clock = Clock()
    bad = {"failed": ["there seems to be singing (-21.9 dB)"]}
    failures = [TrackFailedChecks("westfall", bad), TrackFailedChecks("westfall", bad)]
    client, app, conductor, assets = await running(tmp_path, failures=failures, clock=clock)
    try:
        await client.ws_connect("/ws/player")
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.4)
        clock.now += 5
        await asyncio.sleep(1.5)
        assert len(conductor.ingest.calls) == 2
    finally:
        await client.close()
    kept = json.loads((tmp_path / "var" / "tries.json").read_text())
    assert kept["tries"] == {"westfall:core": 2}

    client, app, again, assets = await running(tmp_path, zones=(), failures=[], clock=clock)
    try:
        await client.ws_connect("/ws/player")
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.4)
        clock.now += 60
        await asyncio.sleep(0.8)
        assert again.ingest.calls == [], "it asked again after the restart"
    finally:
        await client.close()

    # The next day the count starts again.
    kept["day"] = "2001-01-01"
    (tmp_path / "var" / "tries.json").write_text(json.dumps(kept))
    client, app, next_day, assets = await running(tmp_path, zones=(), failures=[], clock=clock)
    try:
        await client.ws_connect("/ws/player")
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.4)
        clock.now += 5
        await asyncio.sleep(0.8)
        assert next_day.ingest.calls == [("Westfall", False)]
    finally:
        await client.close()


async def test_the_game_link_knows_whether_anything_can_be_heard(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
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
    client, app, conductor, assets = await running(tmp_path)
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


async def test_a_place_with_little_music_rests_sooner(tmp_path):
    """Rests come after about twice round what a place has for exploring, never later than the
    setting: 96 s of riffs and calm part in a core suite at 120 beats a minute."""
    client, app, conductor, assets = await running(tmp_path)
    try:
        assert conductor.director.rules.rest_every_s == 360.0
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        await next_of(socket, "asset")
        assert conductor.director.rules.rest_every_s == pytest.approx(192.0)
        add_set(conductor.library, "elwynn-forest", "second")
        add_set(conductor.library, "elwynn-forest", "fresh")
        await next_of(socket, "asset")
        assert conductor.director.rules.rest_every_s == 360.0, "plenty of music: the setting is the limit"
        await socket.close()
    finally:
        await client.close()


# --- a place's music growing with the time spent there --------------------------------------------

async def test_a_place_with_several_sets_is_played_as_one_body_of_music(tmp_path):
    client, app, conductor, assets = await running(tmp_path, sets=("core", "second"))
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        asset = (await next_of(socket, "asset"))["asset"]
        ids = [a.id for a in conductor.library.usable("elwynn-forest")]
        assert asset["id"] == "+".join(ids) and asset["set"] == "core + second" and len(ids) == 2
        names = [section["name"] for section in asset["sections"]]
        assert names[:2] == ["Arrival", "Wander A"] and {"Storm", "Night", "Boss", "Wander D"} <= set(names)
        assert {section["asset_id"] for section in asset["sections"]} == set(ids)
        await socket.close()
    finally:
        await client.close()


async def test_ten_minutes_in_a_place_earns_it_a_second_set(tmp_path):
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        first = (await next_of(socket, "asset"))["asset"]
        clock.now += 30
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [], "more music was made before the place had earned it"
        conductor.playtime.add("elwynn-forest", 600)                  # ten minutes there
        clock.now += 1
        grown = (await next_of(socket, "asset", timeout=10))["asset"]
        assert conductor.ingest.calls == [("Elwynn Forest", "second")]
        assert grown["id"].startswith(first["id"] + "+") and grown["set"] == "core + second"
        notes = " ".join(conductor.notes)
        assert "Making more music for Elwynn Forest (a second set)." in notes
        assert "More music (a second set) for Elwynn Forest is ready" in notes
        assert conductor.playtime.since_set("elwynn-forest") < 5 and conductor.playtime.growth_minutes() == pytest.approx(3.2)
        clock.now += 600
        await asyncio.sleep(0.8)
        assert len(conductor.ingest.calls) == 1, "a fresh set was made before two more hours there"
        await socket.close()
    finally:
        await client.close()


async def test_growth_is_paced_by_the_hours_played(tmp_path):
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock)
    try:
        await client.ws_connect("/ws/player")               # somebody is listening
        assert conductor.growth_left() == pytest.approx(6.0)          # the float, before any hours
        conductor.playtime.data["growth_minutes"] = 5.0                # most of it already used
        conductor.playtime.add("elwynn-forest", 600)
        assert conductor.growth_left() == pytest.approx(6.0 + 180 * (600 / 3600) / 100 - 5.0)
        publish(app, zone_name="Elwynn Forest")
        await asyncio.sleep(0.4)
        clock.now += 30
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [], "growth ran ahead of the hours played"
        conductor.playtime.add(None, 5 * 3600)                         # five more hours played this month
        assert conductor.growth_left() > 3.2
        clock.now += 1
        await asyncio.sleep(1.0)
        assert conductor.ingest.calls == [("Elwynn Forest", "second")]
        conductor.playtime.add(None, 500 * 3600)                       # however much is played...
        assert conductor.growth_left() == pytest.approx(180 - 5.0 - 3.2)   # ...never more than its share of the month
    finally:
        await client.close()


async def test_fresh_sets_come_every_two_hours_and_the_oldest_makes_room(tmp_path):
    clock = Clock()
    client, app, conductor, assets = await running(tmp_path, failures=[], clock=clock,
                                                   sets=("core", "second", "fresh", "fresh", "fresh"))
    try:
        await client.ws_connect("/ws/player")               # somebody is listening
        fresh = [a for a in conductor.library.usable("elwynn-forest") if a.set == "fresh"]
        conductor.library.mark(fresh[0].id, loved=True)                # the oldest is loved, so it stays
        conductor.playtime.add(None, 50 * 3600)
        conductor.playtime.add("elwynn-forest", 7000)
        publish(app, zone_name="Elwynn Forest")
        await asyncio.sleep(0.4)
        clock.now += 30
        await asyncio.sleep(0.8)
        assert conductor.ingest.calls == [], "a fresh set came before two hours since the last"
        conductor.playtime.add("elwynn-forest", 300)
        clock.now += 1
        await asyncio.sleep(1.2)
        assert conductor.ingest.calls == [("Elwynn Forest", "fresh")]
        now = conductor.library.usable("elwynn-forest")
        assert [a.set for a in now] == ["core", "second", "fresh", "fresh", "fresh"]
        assert fresh[0].id in [a.id for a in now] and fresh[1].id not in [a.id for a in now]
        assert conductor.library.get(fresh[1].id).retired
        assert "Set aside an older set (%s)" % fresh[1].id in " ".join(conductor.notes)
    finally:
        await client.close()


async def test_love_and_ban_are_about_the_set_that_is_playing(tmp_path):
    client, app, conductor, assets = await running(tmp_path, sets=("core", "second"))
    try:
        core, second = conductor.library.usable("elwynn-forest")
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        await next_of(socket, "asset")
        await socket.send_str(json.dumps({"type": "status", "started": True, "section": "Storm", "asset_id": second.id}))
        await asyncio.sleep(0.3)
        app["hub"].publish(game.CommandReceived(name="love", count=1))
        await asyncio.sleep(0.4)
        assert conductor.library.get(second.id).loved and not conductor.library.get(core.id).loved
        app["hub"].publish(game.CommandReceived(name="ban", count=2))
        left = (await next_of(socket, "asset"))["asset"]              # the banned set drops out; the rest plays on
        assert left["id"] == core.id and conductor.library.get(second.id).banned
        await socket.close()
    finally:
        await client.close()


async def test_a_rest_reaches_the_player(tmp_path):
    client, app, conductor, assets = await running(tmp_path)
    try:
        conductor.director.rules.rest_every_s = 1.0
        conductor.director.rules.rest_for_s = 1.0
        conductor.director.rules.rest_spread = 0.0
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Elwynn Forest")
        seen = []
        for _ in range(12):
            message = await next_of(socket, "target", timeout=5)
            seen.append(message["target"]["rest"])
            if seen[-2:] == [True, False]:
                break
        assert True in seen and seen[-2:] == [True, False], seen
        await socket.close()
    finally:
        await client.close()
