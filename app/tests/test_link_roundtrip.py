"""Across the language line: the real addon draws, the real reader reads.

FreeRock/*.lua runs under the stand-in client (tools/tests/wowmock.lua). What it draws is turned
into a picture of the edge of the screen, and app/freerock/beacon.py and state.py have to get back
what the game "said". Nothing here is shared between the two sides except protocol/beacon.md.
"""
import dataclasses

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from freerock import beacon, state
import link_helpers as lh
from link_helpers import GameClient


def read_strip(client: GameClient, **options) -> beacon.Reading:
    picture = client.photograph(**options)
    assert picture is not None, "no strip on screen"
    return beacon.read(picture)


def follow(client: GameClient, seconds: float, tracker: state.StateTracker | None = None, spoil=None):
    """Watches the strip for a while, a picture every twentieth of a second, as the sensor does."""
    tracker = tracker or state.StateTracker(clock=lambda: client.mock.time)
    events = []
    for _ in range(round(seconds / 0.05)):
        client.advance(0.05)
        picture = client.photograph()
        if picture is None:
            events += tracker.tick()
            continue
        if spoil is not None:
            picture = lh.as_picture(spoil(picture.astype(np.float32)))
        reading = beacon.read(picture)
        assert reading.ok, reading.problem
        events += tracker.feed(reading.frame)
    assert client.errors() == []
    return tracker, events


def test_what_is_read_is_what_the_addon_drew():
    client = GameClient()
    client.advance(0.3)
    reading = read_strip(client)
    assert reading.ok, reading.problem
    assert dataclasses.asdict(reading.frame) == {**dataclasses.asdict(beacon.Frame()), **client.addon_frame()}
    assert reading.pitch == pytest.approx(3.0, abs=0.01)
    assert reading.box[0] == 16 + 2 and reading.box[2] == 344 * 3


@pytest.mark.parametrize("screen", [(1920, 1080), (2560, 1440), (3440, 1440), (3840, 2160)])
@pytest.mark.parametrize("ui_scale", [0.64, 1.0, 1.15])
def test_pixel_exact_on_every_screen_and_interface_scale(screen, ui_scale):
    client = GameClient(screen=screen, ui_scale=ui_scale)
    client.advance(0.3)
    reading = read_strip(client)
    assert reading.ok, reading.problem
    assert reading.pitch == pytest.approx(3.0, abs=0.01), "squares are not whole pixels"


@pytest.mark.parametrize("cell", [2, 3, 4, 5, 6])
@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_every_square_size_on_either_edge(cell, edge):
    client = GameClient(saved={"cell": cell, "edge": edge, "insetX": 40, "insetY": 4})
    client.advance(0.3)
    reading = read_strip(client)
    assert reading.ok, reading.problem
    assert reading.pitch == pytest.approx(cell, abs=0.01)
    assert reading.box[0] == 40 + 2
    assert reading.frame.flags & beacon.FLAG_ENABLED


def test_the_game_state_comes_through_whole():
    client = GameClient()
    client.set(indoors=True, subzone="Fargodeep Mine", combat=True, target="elite",
               weather={"type": 1, "intensity": 0.45}, day=False, hour=21, minute=50)
    client.fire("ZONE_CHANGED_INDOORS")
    client.fire("PLAYER_TARGET_CHANGED")
    client.fire("WEATHER_CHANGED")
    client.fire("DIEL_CYCLE_CHANGED", False)
    tracker, _ = follow(client, 1.5)
    game = tracker.state
    assert tracker.link == state.Link.LIVE
    assert game.enabled
    assert game.map_id == 1429
    assert game.zone_name == "Elwynn Forest"
    assert game.subzone_name == "Fargodeep Mine"
    assert game.position == pytest.approx((0.42, 0.653), abs=1e-4)
    assert game.indoors and game.in_combat and game.has_target
    assert game.target_class == "elite"
    assert game.weather == "rain"
    assert game.weather_intensity == pytest.approx(0.45)
    assert game.daytime is False
    assert game.game_minutes == 21 * 60 + 50
    assert game.pvp_kind == "friendly"
    assert not game.in_instance and game.instance_kind == "none"
    assert not (game.resting or game.swimming or game.submerged or game.mounted or game.flying or game.on_taxi)
    assert not (game.stealthed or game.dead or game.ghost or game.encounter or game.cinematic or game.loading)
    assert game.volume == 70


def test_a_dungeon_boss_fight_comes_through_whole():
    client = GameClient()
    client.set(inInstance=True, instanceKind="party", instanceName="The Deadmines", difficulty=1, instanceID=36,
               zone="The Deadmines", realZone="The Deadmines", subzone="", mapID=0, x=None, y=None,
               indoors=True, pvp=None, group=True, boss=True, encounter=True, target="worldboss", combat=True)
    client.fire("PLAYER_ENTERING_WORLD", False, False)
    client.fire("ENCOUNTER_START", 1144, "Edwin VanCleef", 1, 5)
    client.fire("PLAYER_TARGET_CHANGED")
    tracker, _ = follow(client, 2.0)
    game = tracker.state
    assert game.in_instance and game.instance_kind == "party"
    assert game.instance_id == 36 and game.difficulty == 1
    assert game.instance_name == "The Deadmines"
    assert game.position is None and game.map_id == 0
    assert game.encounter and game.encounter_id == 1144 and game.encounter_name == "Edwin VanCleef"
    assert game.boss_present and game.in_group and game.target_class == "worldboss"
    assert game.subzone_name is None and not game.has_subzone
    assert game.pvp_kind == "unknown"


def test_weather_the_game_does_not_report_arrives_as_not_reported():
    client = GameClient(game={"hasWeather": False, "hasDay": False})
    client.mock.SyncApis()
    client.fire("WEATHER_CHANGED")
    client.fire("DIEL_CYCLE_CHANGED", True)
    tracker, _ = follow(client, 0.5)
    assert tracker.state.weather is None
    assert tracker.state.weather_intensity is None
    assert tracker.state.daytime is None


def test_commands_and_moments_arrive_exactly_once():
    client = GameClient(saved={"commandCount": 254, "command": 2})
    tracker, events = follow(client, 0.5)
    assert [event for event in events if isinstance(event, (state.CommandReceived, state.MomentReceived))] == [], \
        "what was in the strip before we started watching is not a new command"
    client.slash("skip")
    _, events = follow(client, 0.5, tracker)
    client.slash("ban")
    client.fire("PLAYER_LEVEL_UP", 12)
    _, more = follow(client, 0.5, tracker)
    commands = [event for event in events + more if isinstance(event, state.CommandReceived)]
    moments = [event for event in events + more if isinstance(event, state.MomentReceived)]
    assert commands == [state.CommandReceived("skip", 255), state.CommandReceived("ban", 0)]
    assert [moment.name for moment in moments] == ["level_up"]


def test_a_new_subzone_shows_in_the_first_picture_and_its_name_within_a_second():
    client = GameClient()
    tracker, _ = follow(client, 1.0)
    assert tracker.state.subzone_name == "Goldshire"
    client.set(subzone="Fargodeep Mine", indoors=True)
    client.fire("ZONE_CHANGED_INDOORS")
    _, events = follow(client, 0.05, tracker)
    assert tracker.state.indoors, "the cave shows in the very next picture"
    assert tracker.state.has_subzone and tracker.state.subzone_name is None, "the old name is not shown for the new place"
    follow(client, 1.0, tracker)
    assert tracker.state.subzone_name == "Fargodeep Mine"
    assert tracker.name_rejects == 0


def test_names_with_accents_and_long_names():
    long_name = "The Temple of Atal'Hakkar, where the old gods sleep under green water"
    client = GameClient(game={"zone": "Château d'Œx", "realZone": "Château d'Œx", "subzone": long_name})
    tracker, _ = follow(client, 3.0)
    assert tracker.state.zone_name == "Château d'Œx"
    assert tracker.state.subzone_name == long_name.encode()[:48].decode()
    assert tracker.name_rejects == 0


def test_the_test_pattern_is_recognised():
    client = GameClient()
    tracker, _ = follow(client, 0.3)
    client.slash("test")
    _, events = follow(client, 1.0, tracker)
    assert sum(isinstance(event, state.TestPatternSeen) for event in events) == 1
    _, events = follow(client, 10.0, tracker)
    assert tracker.last_frame.kind == beacon.KIND_STATE
    assert tracker.link == state.Link.LIVE


def test_turning_freerock_off_says_off_then_the_strip_goes():
    client = GameClient()
    tracker, _ = follow(client, 0.5)
    client.slash("off")
    _, events = follow(client, 1.0, tracker)
    assert tracker.link == state.Link.OFF
    assert not tracker.state.enabled
    client.advance(3.0)
    assert client.photograph() is None, "the strip is gone"
    client.slash("on")
    follow(client, 0.5, tracker)
    assert tracker.link == state.Link.LIVE and tracker.state.enabled


def test_a_spoiled_screen_still_carries_the_state():
    client = GameClient(saved={"cell": 3})
    client.set(stealth=True, mounted=True)
    spoil = lambda picture: lh.noise(lh.dim_across(lh.gamma(picture, 1.7), 0.45, 1.0, lift=35), 8)
    tracker, _ = follow(client, 1.2, spoil=spoil)
    assert tracker.state.stealthed and tracker.state.mounted
    assert tracker.state.zone_name == "Elwynn Forest"


flag_names = ["indoors", "resting", "swimming", "submerged", "mounted", "flying", "taxi", "stealth", "combat", "boss", "group"]


@given(
    flags=st.sets(st.sampled_from(flag_names)),
    target=st.sampled_from([None, "normal", "elite", "rare", "rareelite", "worldboss", "trivial", "minus"]),
    x=st.floats(0, 1), y=st.floats(0, 1),
    weather=st.one_of(st.none(), st.tuples(st.integers(0, 4), st.floats(0, 5))),
    day=st.booleans(), hour=st.integers(0, 23), minute=st.integers(0, 59),
    map_id=st.integers(1, 65535), volume=st.integers(0, 100),
    cell=st.integers(2, 6),
)
@settings(max_examples=40, deadline=None)
def test_any_game_state_reads_back(flags, target, x, y, weather, day, hour, minute, map_id, volume, cell):
    client = GameClient(saved={"cell": cell, "volume": volume})
    client.set(**{name: True for name in flags})
    client.set(target=target, x=x, y=y, day=day, hour=hour, minute=minute, mapID=map_id,
               weather={"type": weather[0], "intensity": weather[1]} if weather else None)
    client.fire("ZONE_CHANGED")
    client.fire("PLAYER_TARGET_CHANGED")
    tracker, _ = follow(client, 0.3)
    game = tracker.state
    expected = {
        "indoors": game.indoors, "resting": game.resting, "swimming": game.swimming, "submerged": game.submerged,
        "mounted": game.mounted, "flying": game.flying, "taxi": game.on_taxi, "stealth": game.stealthed,
        "combat": game.in_combat, "boss": game.boss_present, "group": game.in_group,
    }
    assert {name for name, on in expected.items() if on} == flags
    assert game.target_class == (target or "none")
    assert game.position == pytest.approx((x, y), abs=1 / 65534)
    assert game.daytime is day
    assert game.game_minutes == hour * 60 + minute
    assert game.map_id == map_id
    assert game.volume == volume
    if weather is None:
        assert game.weather is None
    else:
        assert game.weather == state.WEATHER_KINDS[weather[0]]
        assert game.weather_intensity == pytest.approx(weather[1], abs=0.0006)
