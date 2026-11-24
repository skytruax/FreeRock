"""The rules from game state to sound, against scripted sessions.

One number, the intensity, says how much is going on, and picks both the kind of moment and how
much of the band plays. These tests walk up and down that ladder and through everything that
bends it: caves, inns, weather, night, stealth, death and moments.
"""
import dataclasses

import pytest

from freerock.director import Director, Rules
from freerock.state import GameState

STEP = 0.25


def play(script, until, rules=None, start=None, moments=()):
    """Runs a session. `script` is a list of (time, {field: value}) changes, `moments` a list of
    (time, name) one-off events. Returns a function that gives the Target that was current at a
    moment."""
    director = Director(rules)
    state = start or GameState(daytime=True)
    changes = sorted(script, key=lambda item: item[0])
    events = sorted(moments)
    seen = {}
    ticks = int(round(until / STEP))
    for tick in range(ticks + 1):
        now = tick * STEP
        while changes and changes[0][0] <= now + 1e-9:
            state = dataclasses.replace(state, **changes.pop(0)[1])
        while events and events[0][0] <= now + 1e-9:
            director.moment(events.pop(0)[1], now)
        seen[tick] = director.update(state, now)
    return lambda moment: seen[int(round(moment / STEP))]


STANDING = GameState(daytime=True, speed=0.0)          # an addon that says how fast the player is going
FIGHT = {"in_combat": True, "has_target": True, "target_class": "normal", "target_hostile": True}
NO_FIGHT = {"in_combat": False, "has_target": False, "target_class": "none", "target_hostile": False}


def levels(target):
    return target.drums, target.bass


# --- the ladder: standing, moving, riding ---------------------------------------------------------

def test_standing_is_a_riff_with_the_guitars_alone():
    calm = play([], 10, start=STANDING)(10)
    # (Standing still quiets every channel a little: "and standing still should quiet the tracks", 2026-11-16.)
    assert calm.place == "wander" and calm.also == () and (calm.bed, calm.drums, calm.bass) == (0.85, 0.0, 0.0)
    # (And a little darker, coming down slowly: "sometimes when one synth stays in when youre sitting its whiny and
    # annoying mix better", 2026-11-17.)
    assert calm.bed_highpass_hz == 110.0 and calm.lowpass_hz == 6500.0 and calm.reverb == 0.0 and calm.fade_s == 3.0
    assert calm.intensity == pytest.approx(0.25)
    assert calm.why == ("standing still", "standing still: a little quieter", "standing still: a little darker")
    assert not calm.silent


def test_standing_still_quiets_the_music_and_moving_brings_it_back():
    """("and standing still should quiet the tracks", 2026-11-16.)"""
    at = play([(5, {"speed": 7.0}), (15, {"speed": 0.0}), (40, {"speed": 7.0})], 45, start=STANDING)
    assert at(10).bed == 1.0, "on the move: the whole of it"
    assert at(17).bed == pytest.approx(0.85) and "standing still: a little quieter" in at(17).why
    assert at(35).bed == pytest.approx(0.65) and "stood a while: quieter" in at(35).why
    assert at(41).bed == 1.0, "moving brings it straight back"
    fight = play([(5, FIGHT)], 8, start=STANDING)(8)
    assert fight.bed == 1.0, "not in a fight, standing or not"


def test_standing_and_sitting_darken_the_music_slowly_and_moving_or_a_fight_opens_it_at_once():
    """("sometimes when one synth stays in when youre sitting its whiny and annoying mix better", 2026-11-17, played: a
    drone held all but alone in a quiet stretch, between pulls.)"""
    at = play([(5, {"speed": 7.0}), (15, {"speed": 0.0}), (40, {"speed": 7.0}), (45, {"speed": 0.0}), (70, FIGHT)], 75,
              start=STANDING)
    assert at(10).lowpass_hz == 20000.0 and at(10).fade_s == 0.4, "on the move: open"
    assert at(17).lowpass_hz == 6500.0 and at(17).fade_s == 3.0 and "standing still: a little darker" in at(17).why
    assert at(35).lowpass_hz == 3400.0 and at(35).fade_s == 3.0 and "sat a while: darker" in at(35).why
    assert at(41).lowpass_hz == 20000.0 and at(41).fade_s == 0.4, "getting up opens it at once"
    assert at(62).lowpass_hz == 3400.0
    assert at(70.25).lowpass_hz == 20000.0 and at(70.25).fade_s == 0.4, "a fight opens it at once"
    sizing = play([(20, {"has_target": True, "target_class": "normal", "target_hostile": True})], 22, start=STANDING)(22)
    assert sizing.lowpass_hz == 20000.0, "something to fight in sight: the music leans in, it does not darken"
    cave = play([(2, {"indoors": True})], 30, start=STANDING)(30)
    assert cave.lowpass_hz == 2500.0, "the darker of the two"
    under = play([(20, {"submerged": True})], 22, start=STANDING)(22)
    assert under.lowpass_hz == 500.0 and under.fade_s == 0.15, "under water still moves fast"


def test_moving_brings_the_drums_in_at_once_and_stopping_takes_them_out():
    at = play([(10, {"speed": 7.0}), (20, {"speed": 0.0})], 30, start=STANDING)
    assert at(10).drums == 0.0, "the very first instant is not yet on the move"
    moving = at(10.25)
    assert moving.drums == 0.55 and moving.bass == 0.0 and moving.intensity == pytest.approx(0.40, abs=0.01)
    assert "on the move" in moving.why and moving.place == "wander"
    assert at(21).drums > 0.0, "a short stop changes nothing"
    assert at(21.5).why[0] == "standing still" and at(23).drums == 0.0, "stopped: the drums leave within a few seconds"


def test_keeping_going_fills_the_band_out():
    at = play([(5, {"speed": 7.0})], 40, start=STANDING)
    assert levels(at(6)) == (0.55, 0.0)
    assert at(15).drums > at(6).drums and at(15).bass == 0.0
    filled = at(27)
    assert filled.bass == 0.70 and filled.drums == 0.75 and filled.intensity == pytest.approx(0.57)
    assert "on the move for a while: the band has filled out" in filled.why
    assert filled.place == "wander", "on foot it never reaches the hard-rock part"


def test_riding_is_drums_and_bass_at_once_and_a_long_ride_reaches_the_hard_rock_part():
    at = play([(2, {"speed": 14.0, "mounted": True}), (42, {"speed": 0.0})], 55, start=STANDING)
    riding = at(2.25)
    assert levels(riding) == (0.75, 0.75) and riding.intensity == pytest.approx(0.60, abs=0.01) and "riding" in riding.why
    assert riding.place == "wander"
    assert at(18).place == "wander" and at(19).place == "storm" and at(19).also == ("wander",)
    assert "at full tilt" in at(19).why
    assert at(30).intensity == pytest.approx(0.75) and levels(at(30)) == (0.95, 0.95)
    assert at(44.5).place == "wander", "off the mount for a moment: back to the riffs"
    assert at(47).drums == 0.0 and at(47).bass == 0.0


def test_a_mount_that_is_standing_still_is_not_riding_and_a_flight_path_is_not_moving():
    sitting = play([(0, {"mounted": True})], 6, start=STANDING)(6)
    assert levels(sitting) == (0.0, 0.0)
    flight = play([(0, {"on_taxi": True, "flying": True, "speed": 30.0})], 10, start=STANDING)(10)
    assert flight.drums == 0.0 and flight.bass == 0.0 and flight.highpass_hz == 150.0 and flight.reverb == 0.30


def test_a_flight_path_is_a_journey_not_a_wait():
    at = play([(0, {"on_taxi": True, "flying": True, "speed": 30.0})], 60, start=STANDING)
    flight = at(60)
    assert flight.bed == 1.0 and flight.also == () and flight.intensity == pytest.approx(0.25)
    assert "standing still for a while" not in flight.why and "standing still" not in flight.why and "flight path" in flight.why


def test_standing_still_for_a_while_lets_the_calm_part_in():
    at = play([(40, {"speed": 7.0})], 50, start=STANDING)
    assert at(14).also == () and at(15.25).also == ("ember",) and "standing still for a while" in at(16).why
    assert at(30).intensity == pytest.approx(0.10)
    assert at(41).also == () and at(41).drums == 0.55, "moving again: the riffs alone, drums in"


def test_a_long_wait_out_of_doors_is_a_camp_with_music_of_its_own():
    # (2026-11-17: "camping should get its own tunes": waiting on a spawn, a rare or a friend.)
    at = play([(100, {"speed": 7.0})], 110, start=STANDING)
    assert at(30).place == "wander" and at(44.5).place == "wander"
    camp = at(46)
    assert camp.place == "camp" and camp.sited and set(camp.also) == {"wander", "ember"} and "camping" in camp.why
    assert camp.bed == pytest.approx(0.65), "as quiet as standing a while"
    assert at(101).place == "wander", "moving again: the walking music"
    night = play([], 60, start=dataclasses.replace(STANDING, daytime=False))(50)
    assert night.place == "camp" and "night" in night.also
    # Not on a flight path, in a dungeon, in an inn or a town, nor once a fight has begun (what was waited for has come).
    assert play([(0, {"on_taxi": True})], 60, start=STANDING)(50).place != "camp"
    assert play([], 60, start=dataclasses.replace(STANDING, in_instance=True, instance_kind="party"))(50).place != "camp"
    assert play([], 60, start=dataclasses.replace(STANDING, resting=True, indoors=True))(50).place == "ember"
    assert play([], 60, start=dataclasses.replace(STANDING, resting=True))(50).place == "town"
    assert play([(50, FIGHT)], 60, start=STANDING)(55).place == "wander"


def walking(start, end, origin=(0.40, 0.60), map_id=1429):
    """Position changes every quarter of a second from `start` to `end`, for an addon that does
    not say how fast the player is going."""
    steps = [(0.0, {"map_id": map_id, "position": origin})]
    for index in range(1, int(round((end - start) / STEP)) + 1):
        steps.append((start + index * STEP, {"position": (origin[0] + 0.0004 * index, origin[1])}))
    return steps


def test_an_older_addon_is_followed_by_its_position():
    at = play(walking(10, 20), 30)
    assert at(9).drums == 0.0 and "standing still" in at(9).why
    assert at(11).drums == 0.55 and "on the move" in at(11).why
    assert at(24).drums == 0.0


def test_without_any_word_on_movement_nothing_is_assumed():
    at = play([], 60)
    assert levels(at(50)) == (0.0, 0.0) and at(50).also == () and at(50).why == ()
    assert at(50).intensity == pytest.approx(0.25)
    mounted = play([(5, {"mounted": True})], 8)
    assert mounted(5.5).drums == 0.0 and levels(mounted(6.25)) == (0.75, 0.75) and "mounted" in mounted(6.25).why


# --- a target, a fight, a boss --------------------------------------------------------------------

def test_sizing_up_a_target_brings_the_band_in_before_the_pull():
    at = play([(5, {"has_target": True, "target_class": "normal", "target_hostile": True}),
               (12, {"has_target": False, "target_class": "none", "target_hostile": False})], 20, start=STANDING)
    assert at(5).bass == 0.0, "not at the very instant: a moment later"
    sizing = at(5.25)
    assert levels(sizing) == (0.75, 0.70) and sizing.bed_highpass_hz == 20.0
    assert "a target in your sights" in sizing.why and sizing.place == "wander"
    assert at(13.5).bass == 0.0
    big = play([(5, {"has_target": True, "target_class": "elite", "target_hostile": True})], 8, start=STANDING)(8)
    assert levels(big) == (0.85, 0.85) and "something big in your sights" in big.why


def test_a_friendly_target_or_an_addon_that_does_not_say_changes_nothing():
    friend = play([(5, {"has_target": True, "target_class": "normal", "target_hostile": False})], 8, start=STANDING)(8)
    assert friend.bass == 0.0 and friend.why == ("standing still", "standing still: a little quieter", "standing still: a little darker")
    old_addon = play([(5, {"has_target": True, "target_class": "normal", "target_hostile": None})], 8)(8)
    assert old_addon.bass == 0.0
    in_town = play([(5, {"has_target": True, "target_class": "elite", "target_hostile": True, "resting": True})], 8,
                   start=STANDING)(8)
    assert in_town.bass == 0.0, "not while resting"


def test_a_fight_is_the_whole_band_in_the_song_that_is_playing_and_no_other_piece():
    """("in normal fights dont play a separate battle piece dungeon bosses ONLY", 2026-11-16.)"""
    at = play([(10, FIGHT)], 30, start=STANDING)
    assert at(9.75).bass == 0.0 and at(9.75).place == "wander"
    first = at(10)
    assert levels(first) == (1.0, 1.0) and first.bed_highpass_hz == 20.0 and first.intensity == pytest.approx(0.80)
    assert first.place == "wander" and first.also == () and "a fight has started" in first.why
    assert at(30).intensity == pytest.approx(0.90), "it rises a little and stops at the ceiling"
    assert at(30).place == "wander", "however long it lasts"


def test_an_elite_and_a_boss():
    elite = play([(5, {**FIGHT, "target_class": "elite"})], 12, start=STANDING)
    assert elite(5).intensity == pytest.approx(0.92) and elite(5).place == "wander", "harder, and still the song that is playing"
    boss = play([(5, {"in_combat": True, "encounter": True})], 8)
    assert boss(5).place == "boss" and boss(5).intensity == 1.0
    assert boss(5).also == ("battle",)
    world_boss = play([(5, {"in_combat": True, "target_class": "worldboss"})], 6)
    assert world_boss(5).place == "wander" and world_boss(5).intensity == 1.0, "only a dungeon's boss has music of its own"


def test_more_enemies_in_the_fight_make_it_jump():
    def after(seconds, *script):
        return play(list(script), seconds, start=STANDING)(seconds)

    one = after(3.0, (1.0, {**FIGHT, "fighting": 1}))
    two = after(3.0, (1.0, {**FIGHT, "fighting": 2}))
    three = after(3.0, (1.0, {**FIGHT, "fighting": 3}))
    many = after(3.0, (1.0, {**FIGHT, "fighting": 9}))
    unknown = after(3.0, (1.0, FIGHT))
    assert 0.80 <= one.intensity < 0.84 and one.intensity == unknown.intensity
    assert 0.85 <= two.intensity <= 0.87 and "2 enemies in the fight" in two.why     # and building from there
    assert three.intensity == pytest.approx(0.90, abs=0.011) and "3 enemies in the fight" in three.why
    assert many.intensity == pytest.approx(0.96, abs=0.011)
    # It comes in during the fight too: a third enemy joining three seconds in.
    joined = after(4.5, (1.0, {**FIGHT, "fighting": 1}), (4.0, {"fighting": 3}))
    assert joined.intensity == pytest.approx(0.90, abs=0.011)


def test_a_fight_against_one_enemy_builds_slowly():
    early = play([(1.0, {**FIGHT, "fighting": 1})], 4.0, start=STANDING)(4.0)
    late = play([(1.0, {**FIGHT, "fighting": 1})], 19.0, start=STANDING)(19.0)
    assert early.intensity < 0.84 < late.intensity <= 0.90


def test_enemies_in_view_keep_the_music_from_sitting_right_back():
    def after(change):
        return play([(1.0, change)] if change else [], 30.0, start=STANDING)(30.0)

    alone, company, crowd = after(None), after({"enemies": 4}), after({"enemies": 12})
    assert alone.intensity < 0.3
    assert company.intensity == pytest.approx(0.56, abs=0.011) and "enemies close by" in company.why
    assert crowd.intensity == pytest.approx(0.62, abs=0.011)
    # Two is not company, an inn is not the place, and an addon that does not say changes nothing.
    assert after({"enemies": 2}).intensity == alone.intensity
    assert after({"enemies": 6, "resting": True, "indoors": True}).intensity <= 0.30
    assert after({"enemies": None}).intensity == alone.intensity


def test_a_short_fight_goes_straight_back_with_no_calm_part_after():
    at = play([(5, FIGHT), (8, NO_FIGHT)], 25, start=STANDING)
    assert at(4.75).place == "wander"
    assert all(at(moment).bass == 1.0 for moment in (5, 7, 9, 10.75)), "the fight, then held three seconds"
    assert "holding after the fight" in at(9).why
    assert all(at(moment).place == "wander" for moment in (5, 7, 9, 10.75, 11.25, 12, 14, 20)), "the same song all the way through"
    assert at(12).bass > 0 and at(20).bass == 0.0, "the bass leaves as the intensity comes down"
    assert at(20).intensity <= 0.25


def test_after_a_boss_hold_then_the_calm_part_then_the_riffs():
    long = play([(5, {**FIGHT, "target_class": "elite"}), (20, NO_FIGHT)], 50, start=STANDING)
    assert all(long(moment).place == "wander" for moment in (19.75, 22, 24, 31.25)), "a long fight with an elite has no calm part after it"
    at = play([(5, {"in_combat": True, "encounter": True}), (20, {"in_combat": False, "encounter": False})], 50, start=STANDING)
    assert at(19.75).place == "boss"
    assert at(22).place == "battle" and at(22).bass == 1.0 and "holding after the fight" in at(22).why
    assert at(24).place == "ember" and "after the fight" in at(24).why
    assert not at(24).sited, "the calm after a fight is not a place: the walking track goes on through it"
    assert at(30.75).place == "ember" and at(31.25).place == "wander"
    assert at(50).intensity == pytest.approx(0.10) and at(50).bass == 0.0


def test_a_boss_keeps_its_music_while_the_fight_goes_on_and_the_next_pull_is_an_ordinary_fight():
    adds = play([(5, {"in_combat": True, "encounter": True}), (20, {"encounter": False})], 30, start=STANDING)
    assert adds(19).place == "boss" and adds(21).place == "battle" and adds(21).also == ("storm", "boss"), "the encounter is over and the fight is not"
    at = play([(5, {"in_combat": True, "encounter": True}), (20, {"in_combat": False, "encounter": False}), (22, {"in_combat": True})], 30,
              start=STANDING)
    assert at(19).place == "boss" and all(at(moment).place == "battle" for moment in (21, 21.75)), "its music is not left at once"
    assert all(at(moment).place == "wander" and at(moment).bass == 1.0 for moment in (22, 25))


def test_fights_close_together_keep_the_band_in():
    one = play([(5, FIGHT), (8, NO_FIGHT)], 40, start=STANDING)
    assert one(20).bass == 0.0 and not any("roll" in reason for reason in one(12).why)
    script = []
    for start in (5, 12, 19):
        script += [(start, {"in_combat": True, "target_class": "normal"}), (start + 4, {"in_combat": False})]
    roll = play(script, 150, start=STANDING)
    after = roll(29)                                  # six seconds after the third fight: one fight is let go after three
    assert after.place == "wander" and after.bass == 1.0 and any("roll" in reason for reason in after.why)
    assert one(8 + 6).bass < 1.0, "after a single fight the band has begun to leave by then"
    assert roll(19).intensity > one(5).intensity, "the next fight starts hotter"
    assert roll(140).bass == 0.0, "and it cools"


def test_on_a_roll_and_on_the_move_the_music_stays_at_full_tilt_between_pulls():
    script = [(1, {"speed": 7.0})]
    for start in (5, 12, 19):
        script += [(start, {"in_combat": True}), (start + 4, {"in_combat": False})]
    at = play(script, 60, start=STANDING)
    between = at(40)
    assert between.place == "storm" and between.also == ("wander",) and "at full tilt" in between.why
    assert between.rain_storm is False, "a ride at full tilt is no rain storm: it does not change the song"
    assert between.bass > 0.8


def test_dying_strips_the_music_back_and_ends_the_fight():
    at = play([(2, {**FIGHT, "target_class": "elite"}), (8, {"in_combat": False, "dead": True}),
               (12, {"dead": False, "ghost": True}), (30, {"ghost": False})], 40, start=STANDING)
    for moment in (8, 12, 20):
        fallen = at(moment)
        assert fallen.place == "ember" and fallen.also == ("wander",)
        assert (fallen.bed, fallen.drums, fallen.bass) == (1.0, 0.0, 0.0)
        assert fallen.lowpass_hz == 1200.0 and fallen.reverb == 0.6 and fallen.volume == pytest.approx(0.4)
        assert fallen.intensity == 0.0
    assert at(31).place == "wander" and at(31).volume == 1.0 and at(31).lowpass_hz == 20000.0


# --- moments --------------------------------------------------------------------------------------

def test_a_moment_gets_the_whole_band():
    at = play([], 40, start=STANDING, moments=[(10, "level_up")])
    assert at(9.75).bass == 0.0
    up = at(10)
    assert up.intensity == 1.0 and levels(up) == (1.0, 1.0) and "a level gained" in up.why
    assert at(19).bass == 1.0 and at(30).bass == 0.0
    quest = play([], 20, start=STANDING, moments=[(5, "quest_turned_in")])
    assert quest(6).bass > 0 and quest(6).intensity == pytest.approx(0.7) and "a quest handed in" in quest(6).why
    assert quest(15).bass == 0.0
    assert play([], 12, moments=[(5, "achievement")])(6).intensity == pytest.approx(0.8)
    assert Director().moment("died", 1.0) is False and Director().moment("level_up", 1.0) is True


def test_a_smaller_moment_does_not_cut_a_bigger_one_short():
    at = play([], 20, start=STANDING, moments=[(0, "level_up"), (6, "quest_turned_in")])
    assert at(8).intensity == 1.0 and "a level gained" in at(8).why, "the level's whole band plays its ten seconds"
    bigger = play([], 20, start=STANDING, moments=[(0, "quest_turned_in"), (2, "level_up")])
    assert bigger(3).intensity == 1.0 and bigger(11.5).intensity == 1.0 and "a level gained" in bigger(11.5).why


def test_a_moment_does_not_wake_the_dead():
    dead = play([(1, {"dead": True})], 12, moments=[(5, "level_up")])
    assert dead(6).bass == 0.0 and dead(6).intensity == 0.0


# --- caves, inns, cities, dungeons ----------------------------------------------------------------

def test_walking_indoors_muffles_at_once_and_moves_to_depths_if_you_stay():
    at = play([(5, {"indoors": True}), (15, {"indoors": False})], 25)
    inside = at(5)
    assert inside.lowpass_hz == 2500.0 and inside.reverb == 0.40 and inside.place == "wander"
    assert at(5.75).place == "wander" and at(6).place == "depths"
    assert at(6).sited and not at(5.75).sited, "a cave is a place the player stands in: the music is to go there"
    assert at(6).also == ("wander",), "the cave part takes turns with the zone's riffs"
    out = at(15)
    assert out.lowpass_hz == 20000.0 and out.reverb == 0.0 and out.place == "depths"
    assert at(16.75).place == "depths" and at(17).place == "wander"


def test_a_building_in_a_town_is_not_a_cave():
    """(2026-11-23, played: Menethil Keep and two town halls were given a cave's music: the game says "indoors" of both.) The music outside
    goes on under a town's roof, muffled; a mine, a stronghold that is a cave and a place nothing is known of are as they were."""
    def indoors(zone, place, **more):
        start = GameState(daytime=True, speed=7.0, zone_name=zone, subzone_name=place, has_subzone=place is not None, **more)
        return play([(5, {"indoors": True})], 15, start=start)(12)

    for zone, place in (("Wetlands", "Menethil Keep"), ("Wetlands", "Menethil Harbor"), ("Lakeshire Town Hall", "Lakeshire"),
                        ("Darkshire Town Hall", None), ("Duskwood", "Darkshire"), ("Westfall", "Alexston Farmstead"), ("Redridge Mountains", "Stonewatch Tower")):
        inside = indoors(zone, place)
        assert inside.place == "wander" and not inside.sited, (zone, place, inside.place)
        assert inside.lowpass_hz == 2500.0 and inside.reverb == 0.40, "still heard through the walls"
    for zone, place in (("Westfall", "Jangolode Mine"), ("Loch Modan", "Mo'grosh Stronghold"), ("Redridge Mountains", "Render's Rock"),
                        ("Duskwood", "Dawning Wood Catacombs"), ("Loch Modan", None), (None, None)):
        assert indoors(zone, place).place == "depths", (zone, place)
    inn = indoors("Wetlands", "Deepwater Tavern", resting=True)
    assert inn.place == "ember" and inn.sited, "an inn is an inn"
    as_it_was = play([(5, {"indoors": True})], 15, rules=Rules(buildings=False),
                     start=GameState(daytime=True, speed=7.0, zone_name="Wetlands", subzone_name="Menethil Keep", has_subzone=True))(12)
    assert as_it_was.place == "depths"


def test_ducking_into_a_doorway_does_not_change_the_section():
    at = play([(5, {"indoors": True}), (5.75, {"indoors": False})], 12)
    assert all(at(moment).place == "wander" for moment in (5, 5.5, 6, 7, 9, 12))


def test_a_plain_rare_in_the_fight_is_big_game_as_in_your_sights():
    at = play([(1, {**FIGHT, "target_class": "rare"})], 4, start=STANDING)
    assert at(2).intensity >= 0.92


def test_walking_in_a_dungeon_is_tense_but_not_full_tilt():
    """Full tilt (the hard-rock part out of a fight) is for what the player does: a long ride, fights close together.
    The dungeon's tension alone once got there after seventeen seconds of walking."""
    inside = GameState(daytime=True, in_instance=True, instance_kind="party", indoors=True, speed=7.0)
    walk = play([], 60, start=inside)(60)
    assert walk.place == "wander" and "at full tilt" not in walk.why and walk.intensity == pytest.approx(0.72)
    ride = play([], 40, start=dataclasses.replace(STANDING, speed=14.0, mounted=True))(40)
    assert ride.place == "storm" and "at full tilt" in ride.why, "a long ride out in the world still gets there"


def test_an_inn_is_calm_and_quieter_and_a_citys_streets_are_not():
    inn = play([(5, {"indoors": True, "resting": True})], 12, start=STANDING)(10)
    assert inn.place == "ember" and inn.also == ("wander",) and inn.volume == pytest.approx(0.63) and inn.bass == 0.0
    assert inn.sited, "an inn is a place the player stands in: the music is to go there"
    assert inn.lowpass_hz == 2500.0 and "quieter in an inn" in inn.why
    running_in = play([(1, {"indoors": True, "resting": True, "speed": 7.0})], 30, start=STANDING)(30)
    assert running_in.intensity == pytest.approx(0.30) and running_in.bass == 0.0, "nothing but a fight rises in an inn"
    streets = play([(1, {"resting": True, "speed": 7.0})], 30, start=STANDING)(30)
    assert streets.place == "town" and streets.volume == 1.0 and streets.bass > 0 and streets.drums > 0.7


def test_a_towns_streets_have_the_towns_own_music():
    """("like whenever in an alliance base should be a family of songs", 2026-11-16.)"""
    streets = play([(1, {"resting": True})], 12, start=STANDING)(10)
    assert streets.place == "town" and streets.sited and streets.also == ("wander",) and "in a town" in streets.why
    inn = play([(1, {"resting": True, "indoors": True})], 12, start=STANDING)(10)
    assert inn.place == "ember", "the town's inn is still an inn"
    out = play([(1, {"resting": True}), (6, {"resting": False})], 12, start=STANDING)(10)
    assert out.place == "wander", "out of the town, the walking music again"


def test_a_battleground_has_its_own_music_through_its_fights_and_its_deaths():
    """("or in a battleground, a family", 2026-11-16.)"""
    field = GameState(daytime=True, in_instance=True, instance_kind="battleground")
    calm = play([], 10, start=field)(8)
    assert calm.place == "battleground" and calm.sited and "a battleground" in calm.why
    fight = play([(3, FIGHT)], 10, start=field)(6)
    assert fight.place == "battleground" and fight.bass == 1.0, "a fight there brings the band up in the same music"
    dead = play([(3, {"dead": True})], 10, start=field)(6)
    assert dead.place == "battleground", "dying there does not change the song"
    arena = play([], 10, start=dataclasses.replace(field, instance_kind="arena"))(8)
    assert arena.place == "battleground"


def test_a_dungeon_is_tenser_and_is_not_treated_as_a_cave():
    """A dungeon is indoors from end to end. It is not muffled for an hour and its Depths part
    does not replace everything else; it joins the rotation."""
    inside = GameState(daytime=True, in_instance=True, instance_kind="party", indoors=True)
    blind = play([], 20, start=inside)(20)                    # the game gives no position in there
    assert blind.place == "wander" and blind.also == ("depths",)
    assert blind.lowpass_hz == 20000.0 and blind.reverb == 0.0
    assert blind.intensity == pytest.approx(0.40) and levels(blind) == (0.55, 0.0)
    told = play([(5, {"speed": 7.0})], 12, start=dataclasses.replace(inside, speed=0.0))
    assert levels(told(4)) == (0.55, 0.0) and told(6).bass > 0, "with a speed from the addon it follows the feet"
    fight = play([(3, FIGHT)], 6, start=inside)(4)
    assert fight.place == "wander" and fight.also == ("depths",) and fight.bass == 1.0, "a pull in a dungeon is an ordinary fight"


# --- water, stealth, weather, night ---------------------------------------------------------------

def test_under_water_and_stealth():
    at = play([(2, {"swimming": True, "submerged": True}), (4, {"swimming": False, "submerged": False}),
               (6, {"stealthed": True}), (8, {"stealthed": True, "in_combat": True})], 10)
    assert at(2).lowpass_hz == 500.0 and at(2).fade_s == 0.15 and at(4).lowpass_hz == 20000.0
    sneaking = at(6)
    assert (sneaking.bed, sneaking.drums, sneaking.bass) == (0.0, 0.35, 0.7)
    assert at(8).bed == 1.0 and at(8).bass == 1.0, "the fight takes over from stealth"
    plain = play([(2, {"stealthed": True})], 4, rules=Rules(stealth_bass=False))(3)
    assert plain.bed == 1.0 and plain.bass == 0.0


def test_rain_brings_the_drums_and_a_rain_storm_the_whole_band():
    at = play([(2, {"weather": "rain", "weather_intensity": 0.2}), (10, {"weather_intensity": 0.4}),
               (20, {"weather_intensity": 0.9}), (40, {"weather_intensity": 0.0, "weather": "clear"})], 80)
    drizzle = at(5)
    assert drizzle.drums == 0.0 and drizzle.lowpass_hz == 20000.0 and drizzle.reverb == pytest.approx(0.104)
    assert at(12).drums == 0.6 and at(12).bass == 0.0, "steady rain: the drums"
    storm = at(20)
    assert storm.bass > 0.8 and storm.drums > 0.8 and storm.lowpass_hz == 20000.0, "a storm: the whole band, not muffled"
    assert "a rain storm: the whole band" in storm.why and storm.place == "wander" and storm.rain_storm is False
    assert at(24).place == "storm" and at(24).also == ("wander",)
    # (Once it has set in, the weather's storm is a change of place for the player; a ride at full tilt is called a
    # storm too, and is none.)
    assert at(24).rain_storm is True and at(61).rain_storm is False
    assert at(59).place == "storm" and at(61).place == "wander", "it leaves twenty seconds after the weather clears"


def test_a_storm_at_night_still_rocks_and_a_storm_outside_a_cave_does_not_reach_in():
    night = play([(1, {"daytime": False, "weather": "rain", "weather_intensity": 0.9})], 10)(10)
    assert night.lowpass_hz == 20000.0 and night.bass > 0.8, "a storm is not darkened by the night"
    cave = play([(1, {"indoors": True, "weather": "rain", "weather_intensity": 0.9})], 10)(10)
    assert cave.bass == 0.0 and cave.place == "depths"


def test_a_storm_ends_only_after_the_rain_has_been_light_for_twenty_seconds_together():
    at = play([(1, {"weather": "rain", "weather_intensity": 0.9}), (10, {"weather_intensity": 0.3}),
               (25, {"weather_intensity": 0.5}), (55, {"weather_intensity": 0.3})], 90)
    assert at(9).place == "storm" and at(54).place == "storm"
    assert at(70).place == "storm", "the light rain before the steadier spell does not count towards its end"
    assert at(76).place == "wander"
    snow = play([(1, {"weather": "rain", "weather_intensity": 0.9}), (10, {"weather": "snow", "weather_intensity": 0.9})], 40)
    assert snow(9).place == "storm" and snow(31).place == "wander", "snow, however heavy, is not a rain storm"


def test_snow_sandstorm_and_night_are_for_out_of_doors():
    sand_cave = play([(1, {"indoors": True, "weather": "sandstorm", "weather_intensity": 1.0})], 3)(3)
    assert sand_cave.highpass_hz == 20.0 and "sandstorm" not in sand_cave.why
    snow_cave = play([(1, {"indoors": True, "weather": "snow", "weather_intensity": 1.0})], 3)(3)
    assert "snow" not in snow_cave.why
    dungeon = GameState(daytime=False, in_instance=True, instance_kind="party", indoors=True)
    night_in = play([], 5, start=dungeon)(5)
    assert night_in.also == ("depths",) and night_in.lowpass_hz == 20000.0 and night_in.hush == 1.0 and night_in.volume == 1.0
    cave = play([(1, {"indoors": True})], 5, start=GameState(daytime=False))(5)
    assert cave.place == "depths" and cave.hush == 1.0 and "darker at night" not in cave.why


def test_snow_sandstorm_and_weather_the_game_does_not_report():
    snow = play([(1, {"weather": "snow", "weather_intensity": 1.0})], 3)(3)
    assert snow.lowpass_hz == 6000.0 and snow.reverb == pytest.approx(0.45)
    sand = play([(1, {"weather": "sandstorm", "weather_intensity": 1.0})], 3)(3)
    assert sand.lowpass_hz == 3000.0 and sand.highpass_hz == 300.0
    unknown = play([(1, {"weather": None, "weather_intensity": None})], 3)(3)
    assert unknown.lowpass_hz == 20000.0 and unknown.reverb == 0.0


def test_night_cinematic_and_switched_off():
    night = play([(1, {"daytime": False})], 3)(3)
    # Night out of doors is a place of its own ("night should feel like night", 2026-11-16): its music first, the walking
    # music when that has been heard lately; darker, further off, softer, the drums and the bass well back.
    assert night.place == "night" and night.also == ("wander",) and night.lean == pytest.approx(0.12) and not night.sited
    assert night.lowpass_hz == 3800.0 and night.reverb >= 0.15 and night.volume == pytest.approx(0.89) and night.hush == 0.75
    day = play([(1, {"daytime": True})], 3)(3)
    assert day.place == "wander" and day.lean == 0.0 and day.hush == 1.0
    unknown = play([(1, {"daytime": None})], 3)(3)
    assert unknown.place == "wander" and unknown.lowpass_hz == 20000.0  # no day or night signal: leave it be
    assert play([(1, {"cinematic": True})], 2)(2).silent
    off = play([(1, {"enabled": False})], 2)(2)
    assert off.silent and "switched off" in off.why[0]
    loading = play([(1, {"loading": True})], 2)(2)
    assert loading.lowpass_hz == 800.0 and loading.volume == pytest.approx(0.5)


def test_each_reason_is_given_once_and_tints_combine():
    town_at_night = play([(1, {"resting": True, "daytime": False, "weather": "rain", "weather_intensity": 0.2})], 6)(6)
    assert len(town_at_night.why) == len(set(town_at_night.why))
    assert "rain" in town_at_night.why and "darker at night" in town_at_night.why and town_at_night.reverb == pytest.approx(0.15)
    inn_at_night = play([(1, {"indoors": True, "resting": True, "daytime": False})], 6)(6)
    assert len(inn_at_night.why) == len(set(inn_at_night.why))
    assert "quieter in an inn" in inn_at_night.why and "darker at night" not in inn_at_night.why
    cave = play([(1, {"indoors": True})], 6)(6)
    assert cave.why == ("indoors for a while", "indoors: muffled and echoing")
    both = play([(1, {"weather": "snow", "weather_intensity": 1.0, "daytime": False})], 2)(2)
    assert both.lowpass_hz == 3800.0 and both.reverb == pytest.approx(0.45)
    drowned = play([(1, {"indoors": True, "submerged": True, "dead": True})], 2)(2)
    assert drowned.lowpass_hz == 500.0 and drowned.reverb == 0.6


def test_no_single_part_is_left_to_loop():
    """Where one part used to replace the zone's riffs for as long as something lasted, it now
    takes turns with them."""
    assert play([(1, {"indoors": True})], 6)(6).also == ("wander",)
    assert play([(1, {"resting": True, "indoors": True})], 6)(6).also == ("wander",)
    assert play([(1, {"weather": "rain", "weather_intensity": 0.9})], 15)(15).also == ("wander",)
    assert play([(1, {"in_combat": True, "encounter": True})], 3)(3).also == ("battle",)
    assert play([(1, {"ghost": True})], 3)(3).also == ("wander",)
    assert play([(1, FIGHT)], 3)(3).also == (), "an ordinary fight names no other part: the song that is playing goes on"
    night_standing = play([(0, {"daytime": False})], 40, start=STANDING)(40)
    assert night_standing.place == "night" and night_standing.also == ("wander", "ember")
