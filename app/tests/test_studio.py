"""The studio: keys and chords, the orchestra's writer, staging a track and putting it in a bucket."""
import random
import struct

import numpy as np
import pytest

from freerock import forever, kinds, studio
from freerock.studio import build, fluid, orchestra, score
from freerock.studio.theory import Key, Line, tones, voiced

RATE = forever.RATE


# --- keys and chords -----------------------------------------------------------------------------

def test_a_scale_step_becomes_a_pitch_in_the_key():
    key = Key(2, "minor")                                  # D minor
    assert key.name == "D minor"
    assert [key.pitch(step, 62) for step in range(8)] == [62, 64, 65, 67, 69, 70, 72, 74]
    assert key.pitch(-1, 62) == 60 and key.pitch(7, 62) == 74
    assert key.pitch(0, 50) == 50 and key.pitch(0, 57) == 62          # the key note nearest to where it is asked for
    assert key.lifted(2).name == "E minor"


def test_the_dominant_of_a_minor_key_has_its_third_raised_and_the_tune_follows_it():
    key = Key(9, "minor")                                  # A minor
    plain, raised = key.chord("5"), key.chord("5+")
    assert sorted(pitch % 12 for pitch in tones(key, plain, 60, 71)) == [4, 7, 11]         # E G B
    assert {pitch % 12 for pitch in tones(key, raised, 60, 71)} == {4, 8, 11}              # E G# B
    assert key.pitch(6, 69, raised) == key.pitch(6, 69) + 1                                # the tune's G becomes G#
    assert key.pitch(2, 69, raised) == key.pitch(2, 69)                                    # its C does not move


def test_a_chord_is_laid_out_close_and_the_players_move_as_little_as_they_can():
    key = Key(0, "major")
    first = voiced(key, key.chord("1"), None, 3, 60)
    assert {pitch % 12 for pitch in first} == {0, 4, 7} and max(first) - min(first) <= 12
    second = voiced(key, key.chord("4"), first, 3, 60)
    assert {pitch % 12 for pitch in second} == {5, 9, 0}
    assert sum(abs(now - was) for now, was in zip(second, first)) <= 5, "the players jumped about"


# --- the orchestra's writer ----------------------------------------------------------------------

def test_every_character_names_instruments_and_grooves_that_exist():
    for character in orchestra.CHARACTERS:
        for name in character.leads + character.strong + character.under + character.pads + character.plucks \
                + character.basses + character.drums:
            assert name in orchestra.INSTRUMENTS and name in orchestra.LOUD, "%s: %s" % (character.name, name)
        assert all(groove in orchestra.GROOVES for groove in character.grooves), character.name
        assert all(kind in kinds.KINDS for kind in character.kinds), character.name
        assert character.role in studio.ROLES
        assert all(mode in orchestra.THEMES and mode in orchestra.SECONDS and mode in orchestra.RISES for mode in character.modes)


def test_every_kind_of_place_has_light_and_heavy_music_to_walk_about_to():
    for kind in kinds.KINDS:
        mine = [character for character in orchestra.CHARACTERS if character.role == "wander" and kind in character.kinds]
        assert any(character.light for character in mine), "%s has no light music" % kind
        assert any(not character.light for character in mine), "%s has no heavy music" % kind
        assert len(mine) >= 4
    roles = {character.role for character in orchestra.CHARACTERS}
    assert roles == set(studio.ROLES), "a kind of moment has no music: %s" % (set(studio.ROLES) - roles)


WORDS = ["open", "theme", "theme", "rise", "moment", "theme", "rise", "moment", "close"]


def test_a_family_is_a_story_of_about_eight_minutes_in_two_waves():
    for index, character in enumerate(orchestra.CHARACTERS):
        for seed in (100 + index, 5000 + index):
            fam = orchestra.family(character, seed, "f", "F")
            bar_s = fam.beats * 60.0 / fam.bpm
            # Nine parts, known to the player by its five words, three of them more than once.
            assert [section.part for section in fam.sections] == list(orchestra.PARTS)
            assert [section.story for section in fam.sections] == WORDS
            assert all(len(section.chords) == section.bars for section in fam.sections)
            assert 450 <= fam.seconds <= 510, "%s is %d s long" % (character.name, fam.seconds)
            assert max(section.bars for section in fam.sections) * bar_s <= 70, "a part of %s is well over a minute" % character.name
            # A statement of a theme is eight bars, or sixteen where eight would be over too soon.
            period = fam.period
            assert period in (8, 16) and 15 <= period * bar_s <= 40, "%s states its theme in %d s" % (character.name, period * bar_s)
            first, second, arrival, valley, summit = (fam.section(part) for part in orchestra.THEMATIC)
            for section in (first, second, arrival, valley, summit):
                assert section.bars >= period and section.bars % (period // 2) == 0
            # Both themes come home; the second begins away from home, over changes of its own.
            assert first.chords[period - 1] == "1" and second.chords[period - 1] == "1", "it does not come home"
            assert second.chords[0] != "1" and first.chords[:period] != second.chords[:period]
            if period == 16:
                assert first.chords[7] != "1" and second.chords[7] != "1", "the question is answered before it is asked"
            # The arrival and the summit are over the first theme's changes, the valley over one theme's or the other's.
            assert arrival.chords[:period] == summit.chords[:period] == first.chords[:period]
            assert valley.chords[:period] == (second if fam.valley == "second" else first).chords[:period]
            assert fam.sections[-1].chords[-1] == "1"
            # The summit is the top; the first arrival is clearly under it; the valley is the
            # quietest the story gets between its first theme and its close.
            assert summit.level[0] == max(level for section in fam.sections for level in section.level)
            assert arrival.level[0] <= summit.level[0] - 0.05, "%s arrives as hard the first time as the last" % character.name
            assert max(valley.level) <= min(level for section in (first, second, arrival) for level in section.level)
            # A lift, where there is one, comes with the second wave.
            assert [section.lifted for section in fam.sections] == [bool(fam.lift) and part in ("climb", "summit", "close")
                                                                    for part in orchestra.PARTS]
            if character.role in orchestra.FIGHTS:
                assert fam.section("open").bars * bar_s <= 35 and fam.section("close").bars * bar_s <= 40, "a fight does not wait"


def test_a_tune_is_a_question_and_its_answer_and_never_sits_on_one_note():
    for index, character in enumerate(orchestra.CHARACTERS):
        fam = orchestra.family(character, 300 + index, "f", "F")
        for way in ("first", "second"):
            chords = [fam.key.chord(figure) for figure in fam.section(way).chords[:fam.period]]
            tune = orchestra.theme(random.Random(index), fam, chords, character.busy, way=way, broad=way == "second" and index % 2 == 0)
            starts = [start for start, _, _, _ in tune.notes]
            assert starts == sorted(starts) and starts[0] == 0
            assert max(start + length for start, length, _, _ in tune.notes) <= fam.period * fam.beats + 1e-6
            assert tune.notes[-1][2] % 7 == 0, "%s does not end on the key note" % character.name
            if fam.period == 16:
                asked = next(step for start, _, step, _ in tune.notes if abs(start - 7 * fam.beats) < 1e-6)
                assert asked % 7 != 0, "%s: the first eight bars end on the key note, which is no question" % character.name
                # The answer begins as the question did.
                assert [step for start, _, step, _ in tune.notes if start < fam.beats - 1e-6] \
                    == [step for start, _, step, _ in tune.notes if 8 * fam.beats - 1e-6 <= start < 9 * fam.beats - 1e-6]
            assert len([start for start in starts if start < fam.beats - 1e-6]) >= 2, "a motif of one note"
            assert tune.top - tune.bottom <= 14, "its range is too wide to sing"
            steps = [step for _, _, step, _ in tune.notes]
            assert not any(a == b == c for a, b, c in zip(steps, steps[1:], steps[2:])), "a note three times running"
            assert max(abs(b - a) for a, b in zip(steps, steps[1:])) <= 7
            # A long note on a strong beat is a note of the chord under it.
            for start, length, step, _ in tune.notes:
                bar = int(start / fam.beats + 1e-6)
                if length >= 1.0 and abs(start - bar * fam.beats) < 1e-6:
                    assert step % 7 in {note % 7 for note in chords[bar].steps}, "%s bar %d" % (character.name, bar + 1)
    with pytest.raises(ValueError):
        orchestra.theme(random.Random(1), fam, chords[:5], 0.5)


def test_takes_of_a_family_share_its_changes_and_differ_in_what_they_play():
    fam = orchestra.family(orchestra.CHARACTERS[0], 7, "f", "F")
    one, two = orchestra.Take(fam, 1), orchestra.Take(fam, 2)
    assert one.total == two.total == fam.bars * fam.beats
    assert [(start, step) for start, _, step, _ in one.tune.notes] != [(start, step) for start, _, step, _ in two.tune.notes]
    assert [(start, step) for start, _, step, _ in one.second.notes] != [(start, step) for start, _, step, _ in two.second.notes]
    for take in (one, two):
        for channel in ("lead", "rhythm", "bass", "texture"):
            notes = [note for voice in take.voices[channel].values() for note in voice.notes]
            assert notes, "nothing is written for the %s" % channel
            assert max(note.start for note in notes) < take.total
            assert all(0 <= note.pitch <= 127 for note in notes)


def spans_of(take):
    """Each part of a take's story: its name, the beat it begins at and the beat it ends at."""
    return {section.part: (first, first + section.bars * take.beats) for section, first, _, _ in take.spans}


def played(take, channel, part):
    """The notes a channel plays in one part of the story, with the name of whoever plays each."""
    first, last = spans_of(take)[part]
    return [(name, note) for name, voice in take.voices[channel].items() for note in voice.notes if first - 1e-6 <= note.start < last - 1e-6]


def test_every_take_of_every_character_can_be_written_and_played():
    for index, character in enumerate(orchestra.CHARACTERS):
        fam = orchestra.family(character, 40 + index, "f", "F")
        take = orchestra.Take(fam, 1 + index % 3)
        for channel, voices in take.voices.items():
            assert sum(1 for voice in voices.values() if not voice.drums) <= 15, "%s has too many players for one %s part" % (character.name, channel)
            for name, voice in voices.items():
                # Every player is known by the name of an instrument: the desk finds its sound by it.
                assert voice.instrument, "%s: %s has no instrument" % (character.name, name)
                if voice.drums:
                    assert voice.instrument == "kit " + character.kit
                    continue
                inst = orchestra.INSTRUMENTS[voice.instrument]
                assert all(inst.low <= note.pitch <= inst.high for note in voice.notes), "%s: %s plays out of its range" % (character.name, name)
                assert all(note.start < take.total for note in voice.notes)
        # The tune is never missing: someone sings in every part of the story.
        for part in orchestra.PARTS:
            assert played(take, "lead", part), "%s: nobody sings in the %s" % (character.name, part)
            assert played(take, "texture", part) and (part == "open" or played(take, "bass", part))


def test_a_take_has_two_themes_that_can_be_told_apart():
    for index, character in enumerate(orchestra.CHARACTERS):
        fam = orchestra.family(character, 70 + index, "f", "F")
        take = orchestra.Take(fam, 1 + index % 2)
        first, second = take.tune.notes, take.second.notes
        bar = lambda notes: [length for start, length, _, _ in notes if start < fam.beats - 1e-6]
        assert bar(first) != bar(second), "%s: both themes begin with one rhythm" % character.name
        # The second theme is sung by someone other than the first one's singer, and first by them.
        assert take.other != take.solo, character.name
        singers = {name for name, _ in played(take, "lead", "first")}
        opening = min(played(take, "lead", "second"), key=lambda each: each[1].start)
        assert opening[0] == take.other and take.solo in singers
        # In the valley one of the themes is sung by one player at a time, who has not stated it.
        stated = take.solo if fam.valley == "first" else take.other
        valley = played(take, "lead", "valley")
        # (A heavy band's valley is the clean guitar's: a distorted one is as loud played softly. 2026-11-17, night.)
        singer = "guitar" if character.band and character.weight >= 0.8 else take.hush
        assert min(valley, key=lambda each: each[1].start)[0] == singer != stated
        ordered = sorted(valley, key=lambda each: each[1].start)
        assert all(later[1].start >= earlier[1].start + earlier[1].length * 0.5 for earlier, later in zip(ordered, ordered[1:])), \
            "%s: more than one line is sung in the valley" % character.name


def test_the_second_theme_is_sung_under_the_first_at_the_summit():
    character = next(each for each in orchestra.CHARACTERS if each.name == "long road home")
    fam = orchestra.family(character, 11, "f", "F")
    take = orchestra.Take(fam, 1)
    # It has the second theme's rhythm, note for note, and sits on the first theme's chords.
    assert [(start, length) for start, length, _, _ in take.counter.notes] == [(start, length) for start, length, _, _ in take.second.notes]
    chords = [fam.key.chord(figure) for figure in fam.section("first").chords[:fam.period]]
    for start, length, step, _ in take.counter.notes:
        bar = int(start / fam.beats + 1e-6)
        if abs(start - bar * fam.beats) < 1e-6:
            assert step % 7 in {note % 7 for note in chords[bar].steps}, "bar %d of the second theme does not fit under the first" % (bar + 1)
    # At the summit the strong players have the tune and the players underneath have a line of their own.
    summit = {name for name, _ in played(take, "lead", "summit")}
    assert set(take.strong) <= summit and {name + " under" for name in character.under} <= summit


def test_the_story_rises_twice_and_the_summit_is_the_top():
    def weigh(take, part):
        """How much is going on in a part of the story: notes a second, and how many are playing."""
        first, last = spans_of(take)[part]
        seconds = (last - first) * 60.0 / take.fam.bpm
        notes = sum(len(played(take, channel, part)) for channel in orchestra.CHANNELS)
        players = len({(channel, name) for channel in orchestra.CHANNELS for name, _ in played(take, channel, part)})
        return notes / seconds, players
    walks = [character for character in orchestra.CHARACTERS if character.role == "wander" and not character.band]
    busy, playing = {part: [] for part in orchestra.PARTS}, {part: [] for part in orchestra.PARTS}
    for index, character in enumerate(walks):
        take = orchestra.Take(orchestra.family(character, 20 + index, "f", "F"), 1)
        for part in orchestra.PARTS:
            notes, players = weigh(take, part)
            busy[part].append(notes)
            playing[part].append(players)
        # In every one of them the valley is thinner than what came before it, and the summit is fuller than the arrival.
        assert weigh(take, "valley")[0] < min(weigh(take, "first")[0], weigh(take, "arrival")[0]), character.name
        assert weigh(take, "summit")[1] >= weigh(take, "arrival")[1], character.name
    mean = lambda values: sum(values) / len(values)
    # Taken together: up to the arrival, down into the valley, up again to a summit that is higher.
    assert mean(busy["open"]) < mean(busy["first"]) < mean(busy["build"]) < mean(busy["arrival"]) < mean(busy["summit"])
    assert mean(busy["valley"]) < 0.5 * mean(busy["first"]) and mean(busy["valley"]) < mean(busy["climb"]) < mean(busy["summit"])
    assert mean(playing["summit"]) > mean(playing["arrival"]) > mean(playing["first"]) > mean(playing["valley"])


def test_a_chord_for_the_strings_is_a_line_for_each_section():
    character = next(each for each in orchestra.CHARACTERS if each.name == "city gates")          # its pad is the strings
    fam = orchestra.family(character, 3, "f", "F")
    take = orchestra.Take(fam, 1)
    pad = take.voices["texture"]
    assert "strings" not in pad and {"celli", "violas", "violins"} <= set(pad)
    for name in ("celli", "violas", "violins", "violins seconds"):
        notes = sorted(pad[name].notes, key=lambda note: note.start) if name in pad else []
        assert all(later.start >= earlier.start + earlier.length - 1e-6 for earlier, later in zip(notes, notes[1:])), \
            "the %s are asked for two notes at once" % name
    # The same in the accompaniment, where the strings have it: each section its own note of the chord.
    assert "strings" not in take.voices["rhythm"] and {"celli", "violas", "violins"} <= set(take.voices["rhythm"])
    # And a short note from a bow is short: under a quarter of a second.
    short = [note.length * 60.0 / fam.bpm for name in ("celli", "violas", "violins") for note in take.voices["rhythm"][name].notes]
    assert max(short) < 0.25


def test_the_kettledrums_play_the_key_note_or_the_fourth_below_where_the_chord_has_them():
    character = next(each for each in orchestra.CHARACTERS if each.name == "long road home")
    home = found = 0
    for seed in (11, 12, 13):
        fam = orchestra.family(character, seed, "f", "F")
        take = orchestra.Take(fam, 1)
        drums = take.voices["drums"]["timpani"].notes
        assert len(drums) > 50
        for section, first, key, chords in take.spans:
            last = first + section.bars * take.beats
            for note in drums:
                if not first <= note.start < last:
                    continue
                chord = chords[int((note.start - first) / take.beats + 1e-6)]
                tones = {step % 7 for step in chord.steps}
                # A pair of kettledrums: the key note and the fifth of the key under it. Another
                # note only under a chord that has neither of them, and then the chord's root.
                want = key.tonic if 0 in tones else key.tonic + 7 if 4 in tones else key.pitch(chord.root, 45)
                assert note.pitch % 12 == want % 12
                found += 1
                home += note.pitch % 12 in (key.tonic % 12, (key.tonic + 7) % 12)
    assert home >= 0.25 * found, "the kettledrums are hardly ever on the key note or the fourth below it"


# --- the big drums and what marks an arrival -------------------------------------------------------

NEW = {"war drums": (36, 47), "frame drums": (45, 57), "boom": (36, 36), "gong": (48, 48), "swell": (49, 49), "anvil": (60, 60)}


def drums_of(take):
    """The new drum voices a take has notes for, by name."""
    return {name: take.voices["drums"][name].notes for name in NEW if name in take.voices["drums"] and take.voices["drums"][name].notes}


def character_called(name):
    return next(each for each in orchestra.CHARACTERS if each.name == name)


def test_the_big_drums_are_where_they_should_be_and_nowhere_else():
    for name, (low, high) in NEW.items():
        inst = orchestra.INSTRUMENTS[name]
        assert (inst.low, inst.high) == (low, high) and not inst.held and name in orchestra.LOUD
    hand_places = {"desert", "jungle", "highland"}
    for index, character in enumerate(orchestra.CHARACTERS):
        take = orchestra.Take(orchestra.family(character, 60 + index, "f", "F"), 1 + index % 2)
        have = drums_of(take)
        fight, walk, heavy = character.role in orchestra.FIGHTS, character.role == "wander", character.weight >= 0.8
        if not (fight or walk):
            assert not have, "%s is for the %s and has %s" % (character.name, character.role, sorted(have))
            continue
        hand = len(character.kinds) < len(orchestra.KINDS_ALL) and bool(set(character.kinds) & hand_places)
        forge = any("anvil" in groove for groove in character.grooves)
        want = {"swell"} if fight or character.weight >= 0.6 else set()
        if fight or heavy:
            want |= {"war drums", "boom"}
        if not character.band and (fight or heavy or (character.weight >= 0.6 and hand)):
            want.add("frame drums")
        # (Grim heavy music has the tam-tam at its summit in the gong's place, and so has a boss: see `colours`.)
        kinds = set(character.kinds) if len(character.kinds) < len(orchestra.KINDS_ALL) else set()
        grim = heavy and (bool(kinds & {"haunted", "infernal"}) or character.role == "boss")
        if not character.band and (fight or heavy) and character.weight >= 0.9 and not grim:
            want.add("gong")
        if forge or (not character.band and (fight or heavy) and len(character.kinds) < len(orchestra.KINDS_ALL)
                     and "infernal" in character.kinds):
            want.add("anvil")
        assert set(have) == want, "%s has %s, not %s" % (character.name, sorted(have), sorted(want))
        # Every stroke is a drum the instrument has, and falls inside the track.
        for name, notes in have.items():
            low, high = NEW[name]
            assert all(low <= note.pitch <= high for note in notes), "%s: %s" % (character.name, name)
            assert all(0 <= note.start < take.total for note in notes), "%s: %s" % (character.name, name)
            assert take.voices["drums"][name].instrument == name and not take.voices["drums"][name].drums
        assert len(have.get("gong", [])) <= 2
        # The valley has no drums at all, but in a fight.
        if not fight:
            assert not played(take, "drums", "valley"), "%s has drums in its valley" % character.name


def test_a_fight_has_war_drums_all_the_way_and_heavy_walking_music_from_each_rise_to_its_moment():
    def strokes(take, part):
        first, last = spans_of(take)[part]
        return [note for note in take.voices["drums"]["war drums"].notes if first - 1e-6 <= note.start < last - 1e-6]
    fight = orchestra.Take(orchestra.family(character_called("skirmish"), 5, "f", "F"), 1)
    for part in orchestra.PARTS:
        assert strokes(fight, part), "a fight has no war drums in its %s" % part
    # The tense breather: one low stroke to the bar, on the bar.
    first, _ = spans_of(fight)["valley"]
    breather = strokes(fight, "valley")
    assert len(breather) == fight.fam.section("valley").bars and {note.pitch for note in breather} == {36}
    assert all(abs((note.start - first) % fight.beats) < 1e-6 for note in breather)
    assert {name for name, _ in played(fight, "drums", "valley")} == {"war drums", "frame drums"}
    # The summit is where they are struck most and hardest.
    per_bar = {part: len(strokes(fight, part)) / fight.fam.section(part).bars for part in orchestra.PARTS}
    assert per_bar["summit"] >= per_bar["arrival"] > per_bar["second"] > per_bar["valley"]
    assert max(note.loud for note in strokes(fight, "summit")) >= max(note.loud for note in strokes(fight, "first"))

    walk = orchestra.Take(orchestra.family(character_called("mountain pass"), 5, "f", "F"), 1)
    for part in ("open", "first", "second", "valley"):
        assert not strokes(walk, part), "heavy walking music has war drums in its %s" % part
    for part in ("build", "arrival", "climb", "summit"):
        assert strokes(walk, part), "heavy walking music has no war drums in its %s" % part
    # In a rise they come in part of the way up and are struck harder as it goes.
    first, last = spans_of(walk)["build"]
    build = strokes(walk, "build")
    assert min(note.start for note in build) >= first + 0.25 * (last - first)
    early = [note.loud for note in build if note.pitch == 36 and note.start < first + 0.6 * (last - first)]
    late = [note.loud for note in build if note.pitch == 36 and note.start >= first + 0.6 * (last - first)]
    assert early and late and max(early) < max(late)
    # In the close they fall away: nothing after its first half.
    first, last = spans_of(walk)["close"]
    assert strokes(walk, "close") and max(note.start for note in strokes(walk, "close")) < first + 0.55 * (last - first)
    # The low drum is on the strong beats of the bar, in an ostinato that comes round.
    first, _ = spans_of(walk)["summit"]
    summit = strokes(walk, "summit")
    for bar in range(4):
        low = sorted(round(note.start - first - bar * walk.beats, 3) for note in summit
                     if note.pitch in (36, 38) and bar * walk.beats - 1e-6 <= note.start - first < (bar + 1) * walk.beats - 1e-6)
        assert low and low[0] == 0.0 and set(low) <= set(walk.starts), "bar %d: the low drums are at %s" % (bar + 1, low)
    bars = [sorted((round(note.start - first - bar * walk.beats, 3), note.pitch) for note in summit
                   if bar * walk.beats - 1e-6 <= note.start - first < (bar + 1) * walk.beats - 1e-6) for bar in range(16)]
    assert bars[0] == bars[4] == bars[8] and bars[1] == bars[5], "the ostinato does not come round"
    # Every fourth bar runs down the drums into the next.
    assert bars[3] != bars[1] and {pitch for _, pitch in bars[3]} >= {47, 45, 43}
    # Another take of the family has an ostinato of its own, over the same bars.
    other = orchestra.Take(walk.fam, 2)
    assert sorted((note.start, note.pitch) for note in strokes(other, "summit")) != sorted((note.start, note.pitch) for note in summit)


def test_lighter_music_of_the_desert_has_frame_drums_and_a_village_dance_has_neither():
    caravan = orchestra.Take(orchestra.family(character_called("caravan"), 5, "f", "F"), 1)
    assert set(drums_of(caravan)) == {"frame drums", "swell"}
    assert {part for part in orchestra.PARTS if any(name == "frame drums" for name, _ in played(caravan, "drums", part))} \
        == {"second", "build", "arrival", "climb", "summit"}
    dance = orchestra.Take(orchestra.family(character_called("village dance"), 5, "f", "F"), 1)
    assert set(drums_of(dance)) == {"swell"}
    # The kit's own bass drum is still the kit's: the deep stroke of the same name is another thing.
    boom = orchestra.KITS[dance.ch.kit][1]["boom"]
    assert any(note.pitch == boom for note in dance.voices["drums"]["kit"].notes) and "boom" not in dance.voices["drums"]


def test_where_the_war_drums_play_the_orchestras_low_drums_make_room():
    take = orchestra.Take(orchestra.family(character_called("skirmish"), 5, "f", "F"), 1)
    kit, boom = take.voices["drums"]["kit"].notes, orchestra.KITS[take.ch.kit][1]["boom"]
    war = {int(note.start / take.beats + 1e-6) for note in take.voices["drums"]["war drums"].notes}       # the bars they play in
    assert len(war) > 0.9 * take.fam.bars
    assert not [note for note in kit if note.pitch == boom and int(note.start / take.beats + 1e-6) in war], \
        "the bass drum plays under the war drums"
    assert not any(name in take.voices["drums"] for name in ("taiko", "great drum"))
    # The kettledrums stay, and only mark the bar.
    first, _ = spans_of(take)["summit"]
    timpani = [note for name, note in played(take, "drums", "summit") if name == "timpani"]
    assert timpani and all(abs((note.start - first) % take.beats) < 1e-6 for note in timpani)
    # A band keeps its kit as it is: its bass drum goes on under its war drums.
    band = orchestra.Take(orchestra.family(character_called("war machine"), 5, "f", "F"), 1)
    kick = orchestra.KITS[band.ch.kit][1]["boom"]
    assert any(name == "war drums" for name, _ in played(band, "drums", "build"))
    assert any(name == "kit" and note.pitch == kick for name, note in played(band, "drums", "build"))


def test_a_rise_ends_in_a_roll_and_a_breath_before_the_arrival():
    for name in ("mountain pass", "village dance", "lullaby", "banner ride"):
        take = orchestra.Take(orchestra.family(character_called(name), 5, "f", "F"), 1)
        beat_s = 60.0 / take.fam.bpm
        ends = [spans_of(take)[part][1] for part in ("build", "climb")]
        assert [last for _, last in take.gaps] == ends and 0.4 <= take.breath * beat_s <= 1.2, name
        for first, last in take.gaps:
            # Nobody but the pad and the drums strikes a note in the breath...
            for channel in ("lead", "rhythm", "bass"):
                assert not [note for voice in take.voices[channel].values() for note in voice.notes if first - 1e-6 <= note.start < last - 1e-6], \
                    "%s: the %s plays in the breath before an arrival" % (name, channel)
            # ...the tune has been running up to it, and the pad holds through.
            assert [note for voice in take.voices["lead"].values() for note in voice.notes if first - take.beats <= note.start < first], name
            assert [note for voice in take.voices["texture"].values() for note in voice.notes if note.start < first < note.start + note.length], name
            # And on the arrival's first beat the tune is back.
            assert [note for voice in take.voices["lead"].values() for note in voice.notes if abs(note.start - last) < 1e-6], name
    # Where there are war drums they roll through it, quicker than seven strokes a second and harder all the way.
    take = orchestra.Take(orchestra.family(character_called("mountain pass"), 5, "f", "F"), 1)
    beat_s = 60.0 / take.fam.bpm
    for first, last in take.gaps:
        before = sorted((note for note in take.voices["drums"]["war drums"].notes if last - 2 * take.beats - 1e-6 <= note.start < last - 1e-6),
                        key=lambda note: note.start)
        roll = [before[-1]]                                 # the run of quick strokes that ends at the arrival
        for note in reversed(before[:-1]):
            if (roll[0].start - note.start) * beat_s > 1.0 / 7.0 + 1e-6:
                break
            roll.insert(0, note)
        assert len(roll) >= 8 and roll[-1].start >= first and (last - roll[0].start) >= take.beats - 1e-6
        assert all(later.loud >= earlier.loud for earlier, later in zip(roll, roll[1:])) and roll[-1].loud > 2 * roll[0].loud
        # Then every drum together, and the deep stroke, on the arrival's first beat.
        assert {note.pitch for note in take.voices["drums"]["war drums"].notes if abs(note.start - last) < 1e-6} >= {36, 43, 47}
        assert [note for note in take.voices["drums"]["boom"].notes if abs(note.start - last) < 1e-6]


def test_a_cymbal_swells_into_each_arrival_and_ends_on_its_first_beat():
    def swells(name):
        take = orchestra.Take(orchestra.family(character_called(name), 5, "f", "F"), 1)
        parts = {round(first, 6): part for part, (first, _) in spans_of(take).items()}
        found = {}
        for note in take.voices["drums"]["swell"].notes if "swell" in take.voices["drums"] else []:
            assert abs(round(note.start + note.length, 6) - (note.start + note.length)) < 1e-6
            into = parts[round(note.start + note.length, 6)]                 # it ends exactly where a part begins
            seconds = note.length * 60.0 / take.fam.bpm
            assert 2.0 <= seconds <= 8.0, "%s: a swell of %.1f s into the %s" % (name, seconds, into)
            found[into] = (seconds, note.loud)
        return found
    big = swells("mountain pass")
    assert set(big) == {"second", "arrival", "summit"}
    assert big["summit"][0] > big["arrival"][0] > big["second"][0] and big["summit"][1] > big["arrival"][1] > big["second"][1]
    assert set(swells("riverside waltz")) == {"arrival", "summit"}                # not into the second theme of a lighter piece
    assert set(swells("banner ride")) == {"arrival", "summit"}                    # a band has them too
    assert not swells("lullaby") and not swells("snowfall")


def test_a_deep_stroke_lands_on_each_arrival_and_a_gong_at_the_summit_of_the_heaviest():
    take = orchestra.Take(orchestra.family(character_called("mountain pass"), 5, "f", "F"), 1)
    period = take.fam.period
    for part in ("arrival", "summit"):
        first, last = spans_of(take)[part]
        booms = sorted(note.start for note in take.voices["drums"]["boom"].notes if first - 1e-6 <= note.start < last)
        # On the first beat, and again each time the theme comes round: never more often.
        assert booms[0] == pytest.approx(first) and all(((start - first) / take.beats) % period == pytest.approx(0) for start in booms)
        assert 1 <= len(booms) <= take.fam.section(part).bars // period
    assert len(take.voices["drums"]["boom"].notes) == len([note for part in ("arrival", "summit") for name, note in played(take, "drums", part)
                                                           if name == "boom"])
    hardest = max(take.voices["drums"]["boom"].notes, key=lambda note: note.loud)
    assert hardest.start == pytest.approx(spans_of(take)["summit"][0])
    gongs = take.voices["drums"]["gong"].notes
    first, last = spans_of(take)["summit"]
    assert 1 <= len(gongs) <= 2 and min(note.start for note in gongs) == pytest.approx(first) and all(note.start < last for note in gongs)
    assert "gong" not in orchestra.Take(orchestra.family(character_called("long road home"), 5, "f", "F"), 1).voices["drums"]


def test_an_anvil_is_struck_in_a_forge_and_in_music_of_the_fire():
    forge = orchestra.Take(orchestra.family(character_called("the forge"), 5, "f", "F"), 1)
    anvil = forge.voices["drums"]["anvil"].notes
    ting = orchestra.KITS[forge.ch.kit][1]["ting"]
    assert len(anvil) > 50 and not any(note.pitch == ting for note in forge.voices["drums"]["kit"].notes)
    # On the back beats of the bar: a slow ostinato.
    first, _ = spans_of(forge)["first"]
    assert {round((note.start - first) % forge.beats, 3) for name, note in played(forge, "drums", "first") if name == "anvil"} <= {1.0, 3.0}
    # Music of the fire that is no forge has single strokes at its arrival and its summit.
    march = orchestra.Take(orchestra.family(character_called("ash march"), 5, "f", "F"), 1)
    strokes = march.voices["drums"]["anvil"].notes
    assert 4 <= len(strokes) <= 40
    assert {part for part in orchestra.PARTS if any(name == "anvil" for name, _ in played(march, "drums", part))} == {"arrival", "summit"}
    # And nowhere else is there an anvil.
    assert "anvil" not in orchestra.Take(orchestra.family(character_called("coronation"), 5, "f", "F"), 1).voices["drums"]
    assert "anvil" not in orchestra.Take(orchestra.family(character_called("deep mine"), 5, "f", "F"), 1).voices["drums"]


# --- the MIDI file -------------------------------------------------------------------------------

def test_a_midi_file_holds_every_voice_and_ends_a_note_before_striking_it_again(tmp_path):
    voice = score.Voice(48)
    voice.add(0.0, 4.0, 60, 0.8)
    voice.add(2.0, 4.0, 60, 0.8)                           # the same note again while the first still sounds
    kit = score.Voice(0, drums=True)
    kit.add(0.0, 0.5, 36, 0.9)
    path = tmp_path / "t.mid"
    score.write_midi(path, [voice, kit], 120, 8)
    data = path.read_bytes()
    assert data[:4] == b"MThd"
    assert struct.unpack(">HHH", data[8:14]) == (1, 3, score.TICKS)         # the tempo track and the two voices
    track = data.split(b"MTrk")[2]
    ons = [index for index in range(len(track) - 2) if track[index] == 0x90 and track[index + 1] == 60]
    offs = [index for index in range(len(track) - 2) if track[index] == 0x80 and track[index + 1] == 60]
    assert len(ons) == 2 and len(offs) == 2 and offs[0] < ons[1], "the first note was not ended before the second began"
    assert b"\x99\x24" in data, "the drums are not on the drum channel"


@pytest.mark.skipif(not (fluid.HOME / "usr" / "bin" / "fluidsynth").is_file(), reason="FluidSynth is not unpacked on this machine")
def test_the_sampled_orchestra_plays_a_part(tmp_path):
    voice = score.Voice(48)
    for beat in range(4):
        voice.add(beat, 0.9, 60 + beat, 0.7)
    score.write_midi(tmp_path / "t.mid", [voice], 120, 6)
    audio = fluid.render(tmp_path / "t.mid", tmp_path / "t.wav")
    assert audio.shape[1] == 2 and len(audio) / RATE >= 2.9          # it plays on until the last note has died away
    assert float(np.abs(audio[:RATE]).max()) > 0.01, "nothing came out"


# --- staging a track and putting it in a bucket --------------------------------------------------

def tone(frames, hz, level=0.2):
    wave = level * np.sin(2 * np.pi * hz * np.arange(frames) / RATE)
    return np.stack([wave, wave], axis=1).astype(np.float32)


def made_track(folder, take=1, quiet_drums=True):
    """A staged track of five two-second sections at a bar a second, with a second of ringing-on."""
    bar = RATE
    sections = [{"story": story, "bars": 2} for story in forever.STORY]
    sections[3]["tonic"] = "E minor"
    frames = 10 * bar + RATE
    drums = tone(frames, 90, 0.3)
    if quiet_drums:
        drums[:2 * bar] = 0.0                              # nothing in the opening
    lead = tone(frames, 440 + 20 * take, 0.1)
    lead[6 * bar:8 * bar] *= 4.0                           # the moment is the loudest
    meta = {"style": "warcraft", "family": "test-family", "take": take, "title": "Test Piece", "tempo": 240.0, "beats": 4,
            "bar_frames": float(bar), "tonic": "D minor", "moods": ["haunted"], "role": "wander", "serves": [0, 1],
            "light": False, "sections": sections, "floor": {"moment": {"drums": 0.9}}, "follow": {"rhythm": ["lead"]},
            "post_s": 1.0, "credit": "a test", "seed": 1}
    studio.write_track(folder, meta, {"lead": lead, "drums": drums})
    return meta


def test_a_staged_track_is_read_back_as_it_was_written(tmp_path):
    meta = made_track(tmp_path / "warcraft" / "test-family" / "1")
    back, parts = studio.read_track(tmp_path / "warcraft" / "test-family" / "1")
    assert back == meta
    assert set(parts) == {"lead", "drums"} and len(parts["lead"]) == 11 * RATE
    with pytest.raises(ValueError):
        studio.write_track(tmp_path / "bad", meta, {"lead": tone(RATE, 440)})          # not the length the story says


def test_a_staged_track_becomes_the_pieces_of_its_story_each_going_into_the_next(tmp_path, monkeypatch):
    folder = tmp_path / "studio" / "warcraft" / "test-family" / "1"
    made_track(folder)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    ids = studio.import_track(bucket, folder)
    assert len(ids) == 5
    pieces = [bucket.pieces[piece_id] for piece_id in ids]
    assert [piece["story"] for piece in pieces] == list(forever.STORY)
    assert [piece["next"] for piece in pieces] == ids[1:] + [""]
    assert [piece["tonic"] for piece in pieces] == ["D minor"] * 3 + ["E minor", "D minor"]
    assert all(piece["family"] == "warcraft/test-family" and piece["track"] == "warcraft/test-family/1" for piece in pieces)
    assert pieces[3]["floor"] == {"drums": 0.9} and pieces[0]["floor"] == {}
    # One gain for the whole track, so the story keeps its shape.
    clips = [clip for clip in bucket.clips if clip.piece]
    assert len({clip.gain_db for clip in clips}) == 1
    # The drums are silent in the opening, so the opening has no drums.
    assert {clip.channel for clip in clips if clip.piece == ids[0]} == {"lead"}
    assert {clip.channel for clip in clips if clip.piece == ids[1]} == {"lead", "drums"}
    # Every recording is the piece and then what the music went on to.
    for clip in clips:
        samples = bucket.audio(clip.id)
        assert samples.dtype == np.dtype("<i2") and len(bucket.samples(clip.id)) == 4 * len(samples)
        assert len(samples) == clip.frames + clip.post
        assert clip.frames == 2 * RATE
        # ...up to six seconds of it, or as much as there is: the last piece has only the ringing-on.
        left = (4 - ids.index(clip.piece)) * 2 * RATE + RATE
        assert clip.post == min(int(forever.POST_S * RATE), left)
    # A second time adds nothing, and does not so much as open the recordings (with a bucketful
    # of eight-minute tracks staged, reading them all again took four minutes).
    def never(*told, **more):
        raise AssertionError("the recordings of a track already in the bucket were read")
    with monkeypatch.context() as patched:
        patched.setattr(studio.soundfile, "read", never)
        assert studio.import_track(bucket, folder) == []
    # And another take of the family is its kin.
    other = tmp_path / "studio" / "warcraft" / "test-family" / "2"
    made_track(other, take=2)
    assert len(studio.import_track(bucket, other)) == 5
    assert studio.staged(tmp_path, "warcraft") == [folder, other]


def test_a_long_track_keeps_each_piece_in_its_place_in_the_story(tmp_path):
    """Nine parts, and the story's words more than once: the bucket notes how many pieces come
    before each, so that the player can tell the first theme from the second and the valley."""
    folder = tmp_path / "studio" / "warcraft" / "long-family" / "1"
    bar = RATE
    frames = 2 * len(WORDS) * bar + RATE
    meta = {"style": "warcraft", "family": "long-family", "take": 1, "title": "Long Piece", "tempo": 240.0, "beats": 4,
            "bar_frames": float(bar), "tonic": "D minor", "moods": ["haunted"], "role": "wander", "serves": [0, 1],
            "light": False, "sections": [{"story": story, "bars": 2} for story in WORDS], "floor": {}, "follow": {},
            "post_s": 1.0, "credit": "a test", "seed": 1}
    studio.write_track(folder, meta, {"lead": tone(frames, 440, 0.1), "drums": tone(frames, 90, 0.3)})
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    ids = studio.import_track(bucket, folder)
    assert len(ids) == len(WORDS) == 9
    assert [bucket.pieces[piece]["story"] for piece in ids] == WORDS
    assert [bucket.pieces[piece]["next"] for piece in ids] == ids[1:] + [""]
    assert [bucket.pieces[piece]["place"] for piece in ids] == list(range(9))
    assert [bucket.describe()["pieces"][piece]["place"] for piece in ids] == list(range(9))
    again = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    assert [again.pieces[piece]["place"] for piece in ids] == list(range(9))
    # A piece that was put in before places were kept is told of without one: the player then
    # counts the pieces that lead to it.
    del again.pieces[ids[2]]["place"]
    assert again.describe()["pieces"][ids[2]]["place"] is None


def test_the_player_is_told_of_pieces_and_a_ban_is_on_the_whole_piece(tmp_path):
    folder = tmp_path / "studio" / "warcraft" / "test-family" / "1"
    made_track(folder)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    ids = studio.import_track(bucket, folder)
    told = bucket.describe()
    assert set(told["pieces"]) == set(ids)
    assert told["pieces"][ids[3]]["story"] == "moment" and told["pieces"][ids[3]]["serves"] == [0, 1]
    parts = [clip for clip in told["clips"] if clip.get("piece")]
    assert parts and all({"piece", "order", "post", "plays"} <= set(clip) for clip in parts)
    # Parts of pieces are in no pool: the feed asks for loose phrases as if they were not there.
    assert all(not bucket.pool(channel, tier) for channel, tier in forever.FIRST)
    assert bucket.wanted() is not None
    # Banning one part bans the piece, and the bucket remembers after it is read again.
    one = next(clip for clip in bucket.clips if clip.piece == ids[1])
    marked = bucket.mark([one.id], banned=True)
    assert {clip.piece for clip in marked} == {ids[1]} and len(marked) == 2
    again = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    assert ids[1] not in again.describe()["pieces"]
    assert not any(clip.get("piece") == ids[1] for clip in again.describe()["clips"])
    again.drop_piece(ids[4])
    assert again.pieces[ids[3]]["next"] == "" and ids[4] not in again.pieces


def test_a_long_part_is_kept_in_stretches(tmp_path):
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    bar = RATE * 2
    audio = tone(40 * bar + RATE, 220)                     # forty bars of two seconds, and a second after
    piece = bucket.add_piece({("rhythm", 1): audio, ("drums", 1): audio}, title="Long", bar_frames=bar, bars=16, post=RATE)
    clips = sorted((clip for clip in bucket.clips if clip.piece == piece and clip.channel == "rhythm"), key=lambda clip: clip.order)
    assert [clip.bars for clip in clips] == [16, 16, 8]
    assert [clip.frames for clip in clips] == [16 * bar, 16 * bar, 8 * bar]
    assert clips[0].post == int(forever.POST_S * RATE) and clips[2].post == RATE
    assert bucket.pieces[piece]["windows"] == 3 and bucket.pieces[piece]["frames"] == 40 * bar
    with pytest.raises(ValueError):
        bucket.add_piece({("rhythm", 1): audio, ("drums", 1): audio[:-5]}, title="Uneven", bar_frames=bar, bars=16)


# --- the band ------------------------------------------------------------------------------------

def test_a_band_plays_riffs_on_wired_guitars_and_the_bass_in_eighths():
    character = next(each for each in orchestra.CHARACTERS if each.name == "banner ride")
    assert character.band and character.style == "knight"
    fam = orchestra.family(character, 5, "f", "F")
    take = orchestra.Take(fam, 1)
    riffs = take.voices["rhythm"]
    assert "rhythm guitar" in riffs and riffs["rhythm guitar"].wired and riffs["rhythm guitar"].notes
    # The band's first theme is the lead guitar's; its second is sung by the organ.
    assert take.solo == "lead guitar" and take.voices["lead"]["lead guitar"].wired
    assert take.other == "rock organ" and not take.voices["lead"]["rock organ"].wired
    # (...and the valley's tune is the clean guitar's, played straight, not through the amplifier.)
    assert {name for name, voice in take.voices["lead"].items() if not voice.wired} == {"rock organ", "rock organ under", "guitar"}
    assert not any(voice.wired for channel in ("texture", "bass", "drums") for voice in take.voices[channel].values())
    # The summit has the tune twice: twin guitars a third apart.
    assert "lead guitar twin" in take.voices["lead"]
    assert {name for name, _ in played(take, "lead", "summit")} >= {"lead guitar", "lead guitar twin", "rock organ under"}
    # In the valley the guitars that play the riff rest.
    assert not played(take, "rhythm", "valley") and played(take, "lead", "valley")
    # The bass sits on the root in eighths through the theme.
    theme = next(span for span in take.spans if span[0].story == "theme")
    first = theme[1]
    bar = [note for voice in take.voices["bass"].values() for note in voice.notes if first - 0.05 <= note.start < first + fam.beats - 0.05]
    assert len(bar) == int(fam.beats * 2) and len({note.pitch for note in bar}) == 1


def test_the_plan_has_a_band_for_knight_rock_beside_the_orchestra():
    families = build.plan()
    styles = {fam.character.style for fam, _ in families}
    assert styles == {"warcraft", "knight"}
    knight = [fam for fam, _ in families if fam.character.style == "knight"]
    assert {kind for fam in knight for kind in fam.character.kinds} == set(kinds.KINDS)
    # (A town's streets and a battleground have Warcraft music first, 2026-11-16; where a style has nothing written for a
    # kind of moment the player plays its walking music.)
    assert {fam.character.role for fam in knight} == set(studio.ROLES) - {"town", "battleground"}
    assert all(build.folder_of(fam, 1).parts[-3] == "knight" for fam in knight)


def test_the_pieces_from_one_source_can_be_taken_out_again(tmp_path):
    from freerock import pieces
    made_track(tmp_path / "studio" / "warcraft" / "test-family" / "1")
    made_track(tmp_path / "studio" / "warcraft" / "test-family" / "2", take=2)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    for folder in studio.staged(tmp_path, "warcraft"):
        studio.import_track(bucket, folder)
    assert len(bucket.pieces) == 10
    assert pieces.drop_from(bucket, "warcraft/test-family/2") == 5
    assert len(bucket.pieces) == 5 and all(piece["source"].endswith("/1") for piece in bucket.pieces.values())
    assert not [clip for clip in bucket.clips if clip.piece not in bucket.pieces]
    assert len(list((bucket.folder / "clips").iterdir())) == len(bucket.clips), "a recording was left behind"
    with pytest.raises(ValueError):
        pieces.drop_from(bucket, "")


def test_the_bass_moves_through_the_chords_as_a_real_bass_does():
    # Measured against 72 movements of the orchestral repertoire, a bass line repeats its note about one time in four
    # and moves by step two times in five (tools/orchestra_study.py). The written bass of the orchestra's walking music
    # keeps near that, and is on something other than the chord's root a good part of the time.
    repeats, moves, off = 0, 0, 0
    notes_seen = 0
    for index, character in enumerate(orchestra.CHARACTERS):
        if character.band or character.role != "wander" or index % 5:
            continue
        fam = orchestra.family(character, 70 + index, "f", "F")
        take = orchestra.Take(fam, 1)
        line = sorted(max(take.voices["bass"].values(), key=lambda voice: len(voice.notes)).notes, key=lambda note: note.start)
        steps = [abs(b.pitch - a.pitch) for a, b in zip(line, line[1:])]
        repeats += sum(1 for step in steps if step == 0)
        moves += len(steps)
        roots = {}
        for section, first, key, chords in take.spans:
            for bar, chord in enumerate(chords):
                roots[int(round(first / fam.beats)) + bar] = key.pitch(chord.root, 0) % 12
        off += sum(1 for note in line if note.pitch % 12 != roots.get(int(note.start // fam.beats), note.pitch % 12))
        notes_seen += len(line)
    assert repeats / moves < 0.4, "the bass repeats its note %.0f%% of the time" % (100 * repeats / moves)
    assert off / notes_seen > 0.15, "the bass is on the root %.0f%% of the time" % (100 - 100 * off / notes_seen)
