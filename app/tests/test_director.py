"""The rules from game state to sound, against scripted sessions."""
import dataclasses

import pytest

from freerock.director import Director, Rules, playable
from freerock.state import GameState

STEP = 0.25


def play(script, until, rules=None, start=None):
    """Runs a session. `script` is a list of (time, {field: value}) changes. Returns a function
    that gives the Target that was current at a moment."""
    director = Director(rules)
    state = start or GameState(daytime=True)
    changes = sorted(script, key=lambda item: item[0])
    seen = {}
    ticks = int(round(until / STEP))
    for tick in range(ticks + 1):
        now = tick * STEP
        while changes and changes[0][0] <= now + 1e-9:
            state = dataclasses.replace(state, **changes.pop(0)[1])
        seen[tick] = director.update(state, now)
    return lambda moment: seen[int(round(moment / STEP))]


def test_nothing_happening_is_the_bed_alone():
    at = play([], 10)
    calm = at(10)
    assert calm.place == "wander" and (calm.bed, calm.drums, calm.bass) == (1.0, 0.0, 0.0)
    assert calm.bed_highpass_hz == 110.0 and calm.lowpass_hz == 20000.0 and calm.reverb == 0.0
    assert calm.intensity == pytest.approx(0.25) and not calm.silent


def test_a_fight_brings_the_bass_in_at_once_and_battle_if_it_lasts():
    at = play([(10, {"in_combat": True, "has_target": True, "target_class": "normal"})], 30)
    assert at(9.75).bass == 0.0
    first = at(10)
    assert first.bass == 1.0 and first.drums >= 0.75 and first.bed_highpass_hz == 20.0
    assert first.place == "wander" and "a fight has started" in first.why
    assert at(15).place == "wander"                      # five seconds in: still the same music
    assert at(18).place == "battle" and at(18).intensity >= 0.75
    assert at(30).intensity == pytest.approx(0.8)        # it stops rising at the ceiling


def test_an_elite_gets_to_battle_sooner_and_a_boss_at_once():
    elite = play([(5, {"in_combat": True, "target_class": "elite"})], 12)
    assert elite(5).intensity == pytest.approx(0.8) and elite(5).place == "wander"
    assert elite(7).place == "battle"
    boss = play([(5, {"in_combat": True, "encounter": True})], 8)
    assert boss(5).place == "boss" and boss(5).cut == "beat" and boss(5).intensity == 1.0
    world_boss = play([(5, {"in_combat": True, "target_class": "worldboss"})], 6)
    assert world_boss(5).place == "boss"


def test_after_a_long_fight_hold_then_ember_then_wander():
    at = play([(5, {"in_combat": True, "target_class": "elite"}), (20, {"in_combat": False})], 50)
    assert at(19.75).place == "battle"
    assert at(22).place == "battle" and at(22).bass == 1.0 and "holding after the fight" in at(22).why
    assert at(26).place == "ember" and "after the fight" in at(26).why
    assert at(34).place == "wander"
    assert at(29).bass == 1.0 and at(31).bass == 0.0     # the bass leaves as the intensity falls away
    assert at(50).intensity == pytest.approx(0.25)


def test_a_second_pull_inside_the_hold_stays_in_battle():
    at = play([(5, {"in_combat": True, "target_class": "elite"}), (20, {"in_combat": False}),
               (23, {"in_combat": True})], 30)
    assert all(at(moment).place == "battle" for moment in (19, 21, 22.75))
    assert at(23).bass == 1.0


def test_a_short_fight_never_leaves_the_wander_music():
    at = play([(5, {"in_combat": True, "target_class": "normal"}), (8, {"in_combat": False})], 25)
    assert all(at(moment).place == "wander" for moment in (5, 7, 9, 12, 14, 20))
    assert at(7).bass == 1.0 and at(12).bass == 1.0 and at(20).bass == 0.0


def test_walking_indoors_muffles_at_once_and_moves_to_depths_if_you_stay():
    at = play([(5, {"indoors": True}), (15, {"indoors": False})], 25)
    inside = at(5)
    assert inside.lowpass_hz == 6000.0 and inside.reverb == 0.30 and inside.place == "wander"
    assert at(7).place == "wander" and at(7.5).place == "depths"
    out = at(15)
    assert out.lowpass_hz == 20000.0 and out.reverb == 0.0 and out.place == "depths"
    assert at(18.75).place == "depths" and at(19).place == "wander"


def test_ducking_into_a_doorway_does_not_change_the_section():
    at = play([(5, {"indoors": True}), (6.5, {"indoors": False})], 12)
    assert all(at(moment).place == "wander" for moment in (5, 6, 7, 9, 12))


def test_an_inn_is_ember_and_quieter_not_depths():
    at = play([(5, {"indoors": True, "resting": True})], 12)
    inn = at(10)
    assert inn.place == "ember" and inn.volume == pytest.approx(0.63) and inn.bass == 0.0
    assert inn.lowpass_hz == 6000.0 and inn.intensity == pytest.approx(0.0, abs=0.01)


def test_under_water_stealth_mounted_and_flight():
    at = play([(2, {"swimming": True, "submerged": True}), (4, {"swimming": False, "submerged": False}),
               (6, {"stealthed": True}), (8, {"stealthed": True, "in_combat": True}),
               (9, {"stealthed": False, "in_combat": False}), (20, {"mounted": True}),
               (24, {"mounted": False, "on_taxi": True, "flying": True})], 26)
    assert at(2).lowpass_hz == 700.0 and at(2).fade_s == 0.15 and at(4).lowpass_hz == 20000.0
    sneaking = at(6)
    assert (sneaking.bed, sneaking.drums, sneaking.bass) == (0.0, 0.35, 0.7)
    assert at(8).bed == 1.0 and at(8).bass == 1.0                  # the fight takes over from stealth
    assert at(20).drums == 0.0 and at(21.25).drums == 0.6 and "mounted" in at(21.25).why
    flight = at(24)
    assert flight.highpass_hz == 150.0 and flight.reverb == 0.30 and flight.bass == 0.0


def test_stealth_bass_can_be_switched_off():
    at = play([(2, {"stealthed": True})], 4, rules=Rules(stealth_bass=False))
    assert at(3).bed == 1.0 and at(3).bass == 0.0


def test_dying_strips_the_music_back_and_ends_the_fight():
    at = play([(2, {"in_combat": True, "target_class": "elite"}),
               (8, {"in_combat": False, "dead": True}), (12, {"dead": False, "ghost": True}),
               (30, {"ghost": False})], 40)
    for moment in (8, 12, 20):
        fallen = at(moment)
        assert fallen.place == "ember" and (fallen.bed, fallen.drums, fallen.bass) == (1.0, 0.0, 0.0)
        assert fallen.lowpass_hz == 1500.0 and fallen.reverb == 0.6 and fallen.volume == pytest.approx(0.4)
        assert fallen.intensity == 0.0
    assert at(31).place == "wander" and at(31).volume == 1.0 and at(31).lowpass_hz == 20000.0


def test_weather_tints_follow_the_intensity_and_a_storm_needs_to_last():
    at = play([(2, {"weather": "rain", "weather_intensity": 0.5}),
               (10, {"weather_intensity": 0.8}), (40, {"weather_intensity": 0.2}),
               (70, {"weather": "clear", "weather_intensity": 0.0})], 75)
    drizzle = at(2)
    assert drizzle.lowpass_hz == pytest.approx(8500.0) and drizzle.reverb == pytest.approx(0.175)
    assert drizzle.place == "wander"
    assert at(19.75).place == "wander" and at(20).place == "storm" and at(20).lowpass_hz == pytest.approx(6400.0)
    assert at(59.75).place == "storm" and at(60).place == "wander"      # twenty seconds of calm
    assert at(72).lowpass_hz == 20000.0 and at(72).reverb == 0.0


def test_snow_sandstorm_and_weather_the_game_does_not_report():
    snow = play([(1, {"weather": "snow", "weather_intensity": 1.0})], 2)(2)
    assert snow.reverb == pytest.approx(0.45) and snow.lowpass_hz == 10000.0
    sand = play([(1, {"weather": "sandstorm", "weather_intensity": 1.0})], 2)(2)
    assert sand.lowpass_hz == pytest.approx(3500.0) and sand.highpass_hz == pytest.approx(300.0)
    silent_game = play([(1, {"weather": None, "weather_intensity": None})], 2)(2)
    assert silent_game.lowpass_hz == 20000.0 and silent_game.reverb == 0.0
    off_the_scale = play([(1, {"weather": "rain", "weather_intensity": 7.0})], 2)(2)
    assert off_the_scale.lowpass_hz == pytest.approx(5000.0)            # held inside 0 to 1


def test_night_cinematic_and_switched_off():
    night = play([(1, {"daytime": False})], 3)(3)
    assert night.place == "night" and night.lowpass_hz == 8000.0
    unknown = play([(1, {"daytime": None})], 3)(3)
    assert unknown.place == "wander" and unknown.lowpass_hz == 20000.0  # no day or night signal: leave it be
    assert play([(1, {"cinematic": True})], 2)(2).silent
    off = play([(1, {"enabled": False})], 2)(2)
    assert off.silent and "switched off" in off.why[0]
    loading = play([(1, {"loading": True})], 2)(2)
    assert loading.lowpass_hz == 800.0 and loading.volume == pytest.approx(0.5)


def test_tints_combine_lowest_lowpass_and_largest_reverb():
    both = play([(1, {"indoors": True, "weather": "snow", "weather_intensity": 1.0, "daytime": False})], 2)(2)
    assert both.lowpass_hz == 6000.0 and both.reverb == pytest.approx(0.45)
    drowned = play([(1, {"indoors": True, "submerged": True, "dead": True})], 2)(2)
    assert drowned.lowpass_hz == 700.0 and drowned.reverb == 0.6


def test_a_dungeon_starts_from_a_higher_base():
    at = play([], 8, start=GameState(daytime=True, in_instance=True, instance_kind="party"))
    assert at(8).intensity == pytest.approx(0.35) and at(8).bass == 0.0


def test_playable_falls_back_until_something_fits():
    core = {"arrival", "wander", "battle", "ember", "depths"}
    assert playable("boss", core) == "battle" and playable("storm", core) == "wander"
    assert playable("night", core) == "ember" and playable("depths", core) == "depths"
    assert playable("boss", {"wander"}) == "wander" and playable("night", {"wander"}) == "wander"
    with pytest.raises(ValueError):
        playable("wander", {"battle"})
