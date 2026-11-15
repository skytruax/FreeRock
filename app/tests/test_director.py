"""The rules from game state to sound, against scripted sessions."""
import dataclasses
import random

import pytest

from freerock.director import Director, Rules, playable
from freerock.state import GameState

STEP = 0.25


def play(script, until, rules=None, start=None, seed=1):
    """Runs a session. `script` is a list of (time, {field: value}) changes. Returns a function
    that gives the Target that was current at a moment."""
    director = Director(rules, rng=random.Random(seed))
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
    assert calm.intensity == pytest.approx(0.25) and not calm.silent and not calm.rest


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
    assert inside.lowpass_hz == 2500.0 and inside.reverb == 0.40 and inside.place == "wander"
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
    assert inn.lowpass_hz == 2500.0 and inn.intensity == pytest.approx(0.0, abs=0.01)


def test_under_water_stealth_mounted_and_flight():
    at = play([(2, {"swimming": True, "submerged": True}), (4, {"swimming": False, "submerged": False}),
               (6, {"stealthed": True}), (8, {"stealthed": True, "in_combat": True}),
               (9, {"stealthed": False, "in_combat": False}), (20, {"mounted": True}),
               (24, {"mounted": False, "on_taxi": True, "flying": True})], 26)
    assert at(2).lowpass_hz == 500.0 and at(2).fade_s == 0.15 and at(4).lowpass_hz == 20000.0
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
        assert fallen.lowpass_hz == 1200.0 and fallen.reverb == 0.6 and fallen.volume == pytest.approx(0.4)
        assert fallen.intensity == 0.0
    assert at(31).place == "wander" and at(31).volume == 1.0 and at(31).lowpass_hz == 20000.0


def test_rain_brings_the_drums_and_a_rain_storm_the_whole_band():
    at = play([(2, {"weather": "rain", "weather_intensity": 0.2}),
               (6, {"weather_intensity": 0.5}),
               (10, {"weather_intensity": 0.8}), (40, {"weather_intensity": 0.2}),
               (70, {"weather": "clear", "weather_intensity": 0.0})], 75)
    drizzle = at(2)
    assert drizzle.lowpass_hz == 20000.0, "rain must not muffle the music"
    assert drizzle.reverb == pytest.approx(0.104) and (drizzle.drums, drizzle.bass) == (0.0, 0.0)
    steady = at(6)
    assert steady.drums == 0.6 and steady.bass == 0.0 and steady.lowpass_hz == 20000.0
    storm = at(10)                                       # the moment it becomes a storm
    assert storm.bass == 1.0 and storm.drums >= 0.75 and storm.intensity == pytest.approx(0.7)
    assert storm.lowpass_hz == 20000.0 and storm.bed_highpass_hz == 20.0
    assert "a rain storm: the whole band" in storm.why and storm.place == "wander"
    assert at(19.75).place == "wander" and at(20).place == "storm"       # it has set in
    assert at(39.75).bass == 1.0
    assert at(46).bass == 0.0 and at(46).drums == 0.0                    # the rain eases and the band leaves
    assert at(59.75).place == "storm" and at(60).place == "wander"       # twenty seconds of calm
    assert at(72).reverb == 0.0


def test_a_storm_at_night_still_rocks_and_a_storm_outside_a_cave_does_not_reach_in():
    night = play([(1, {"weather": "rain", "weather_intensity": 1.0, "daytime": False})], 3)(3)
    assert night.bass == 1.0 and night.lowpass_hz == 20000.0 and night.intensity == pytest.approx(0.8)
    assert "darker at night" not in night.why
    cave = play([(1, {"weather": "rain", "weather_intensity": 1.0, "indoors": True})], 3)(3)
    assert cave.bass == 0.0 and cave.lowpass_hz == 2500.0 and "rain" not in " ".join(cave.why)
    inn = play([(1, {"weather": "rain", "weather_intensity": 1.0, "resting": True})], 3)(3)
    assert inn.bass == 0.0


def test_snow_sandstorm_and_weather_the_game_does_not_report():
    snow = play([(1, {"weather": "snow", "weather_intensity": 1.0})], 2)(2)
    assert snow.reverb == pytest.approx(0.45) and snow.lowpass_hz == 6000.0
    sand = play([(1, {"weather": "sandstorm", "weather_intensity": 1.0})], 2)(2)
    assert sand.lowpass_hz == pytest.approx(3000.0) and sand.highpass_hz == pytest.approx(300.0)
    silent_game = play([(1, {"weather": None, "weather_intensity": None})], 2)(2)
    assert silent_game.lowpass_hz == 20000.0 and silent_game.reverb == 0.0
    off_the_scale = play([(1, {"weather": "rain", "weather_intensity": 7.0})], 2)(2)
    assert off_the_scale.intensity == pytest.approx(0.8)                # held inside 0 to 1


def test_night_cinematic_and_switched_off():
    night = play([(1, {"daytime": False})], 3)(3)
    assert night.place == "night" and night.lowpass_hz == 5000.0
    unknown = play([(1, {"daytime": None})], 3)(3)
    assert unknown.place == "wander" and unknown.lowpass_hz == 20000.0  # no day or night signal: leave it be
    assert play([(1, {"cinematic": True})], 2)(2).silent
    off = play([(1, {"enabled": False})], 2)(2)
    assert off.silent and "switched off" in off.why[0]
    loading = play([(1, {"loading": True})], 2)(2)
    assert loading.lowpass_hz == 800.0 and loading.volume == pytest.approx(0.5)


def test_each_reason_is_given_once():
    inn_at_night = play([(1, {"indoors": True, "resting": True, "daytime": False})], 6)(6)
    assert len(inn_at_night.why) == len(set(inn_at_night.why))
    assert "quieter while resting" in inn_at_night.why and "darker at night" in inn_at_night.why
    cave = play([(1, {"indoors": True})], 6)(6)
    assert cave.why == ("indoors for a while", "indoors: muffled and echoing")


def test_tints_combine_lowest_lowpass_and_largest_reverb():
    both = play([(1, {"indoors": True, "weather": "snow", "weather_intensity": 1.0, "daytime": False})], 2)(2)
    assert both.lowpass_hz == 2500.0 and both.reverb == pytest.approx(0.45)
    drowned = play([(1, {"indoors": True, "submerged": True, "dead": True})], 2)(2)
    assert drowned.lowpass_hz == 500.0 and drowned.reverb == 0.6


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


# --- rests ----------------------------------------------------------------------------------------

RESTS = Rules(rest_every_s=20, rest_for_s=6, rest_spread=0.0, calm_before_rest_s=10)


def test_after_a_stretch_of_calm_music_there_is_a_rest_and_then_music_again():
    at = play([], 60, rules=RESTS)
    assert not at(19.75).rest
    resting = at(20)
    assert resting.rest and resting.fade_s == 8.0 and "a rest, as the game has between pieces" in resting.why
    assert at(25.75).rest and not at(26).rest
    assert not at(45.75).rest and at(46).rest and not at(52).rest          # and round again


def test_a_fight_ends_a_rest_at_once_and_puts_off_the_next_one():
    at = play([(22, {"in_combat": True, "target_class": "normal"}), (25, {"in_combat": False})], 60, rules=RESTS)
    assert at(21.75).rest
    fight = at(22)
    assert not fight.rest and fight.bass == 1.0
    # The fight is over at 25, held until 30, and the music has settled by about 35. The next rest
    # waits for ten calm seconds after that, not for the clock it was on before.
    assert not any(at(moment).rest for moment in (26, 30, 35, 40, 44))
    assert at(46).rest


def test_a_new_place_stealth_or_a_storm_end_a_rest():
    place = play([(22, {"zone_name": "Westfall", "map_id": 52})], 30, rules=RESTS,
                 start=GameState(daytime=True, zone_name="Elwynn Forest", map_id=37))
    assert place(21.75).rest and not place(22).rest
    sneak = play([(22, {"stealthed": True})], 30, rules=RESTS)
    assert sneak(21.75).rest and not sneak(22).rest
    storm = play([(22, {"weather": "rain", "weather_intensity": 0.9})], 30, rules=RESTS)
    assert storm(21.75).rest and not storm(22).rest and storm(22).bass == 1.0


def test_nothing_rests_while_something_is_going_on():
    stormy = play([(1, {"weather": "rain", "weather_intensity": 0.9})], 80, rules=RESTS)
    assert not any(stormy(moment).rest for moment in range(2, 80))
    dungeon_fight = play([(1, {"in_combat": True, "encounter": True})], 80, rules=RESTS)
    assert not any(dungeon_fight(moment).rest for moment in range(2, 80))


def test_rests_can_be_switched_off_and_do_not_come_like_clockwork():
    never = play([], 200, rules=Rules(rest_every_s=0))
    assert not any(never(moment).rest for moment in range(0, 200))
    starts = set()
    for seed in range(6):
        at = play([], 40, rules=Rules(rest_every_s=20, rest_for_s=6, rest_spread=0.3), seed=seed)
        starts.add(next(moment for moment in [m * 0.25 for m in range(160)] if at(moment).rest))
    assert all(14 <= start <= 26.25 for start in starts) and len(starts) >= 4


def test_an_inn_and_a_cave_can_rest_too():
    inn = play([(0, {"resting": True, "indoors": True})], 30, rules=RESTS)
    assert inn(21).rest and inn(21).place == "ember"
    cave = play([(0, {"indoors": True})], 30, rules=RESTS)
    assert cave(21).rest and cave(21).lowpass_hz == 2500.0
