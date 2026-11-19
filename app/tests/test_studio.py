"""The studio: keys and chords, the orchestra's writer, staging a track and putting it in a bucket."""
import random

import numpy as np
import pytest

from freerock import forever, kinds, studio
from freerock.studio import build, orchestra, score
from freerock.studio.theory import Key, tones, voiced

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
            assert name in orchestra.INSTRUMENTS, "%s: %s" % (character.name, name)
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
        singer = "guitar" if character.band and (character.weight >= 0.8 or take.hush == "lead guitar") else take.hush
        assert min(valley, key=lambda each: each[1].start)[0] == singer != stated
        ordered = sorted(valley, key=lambda each: each[1].start)
        assert all(later[1].start >= earlier[1].start + earlier[1].length * 0.5 for earlier, later in zip(ordered, ordered[1:])), \
            "%s: more than one line is sung in the valley" % character.name


def test_a_bands_fight_breaks_down_in_its_valley_and_comes_back_before_the_climb():
    # (2026-11-17, morning: the band's fight pieces went only 4 to 5 dB between their quietest part and their loudest,
    # the whole band playing on through the valley.)
    for name in ("storm rider", "battle cry", "war machine", "dragon"):
        character = next(each for each in orchestra.CHARACTERS if each.name == name)
        assert character.band and character.role in orchestra.FIGHTS
        fam = orchestra.family(character, 21, "f", "F")
        take = orchestra.Take(fam, 1)
        first, last = spans_of(take)["valley"]
        middle = first + (last - first) / 2
        riff = [note for _, note in played(take, "rhythm", "valley")]
        assert riff and all(note.start >= middle - 1e-6 for note in riff), "%s: the riff plays through the breakdown" % name
        held = [note for _, note in played(take, "bass", "valley") if note.start < middle - 1e-6]
        assert held and all(note.length >= fam.beats - 1e-6 for note in held), "%s: the bass does not hold its roots" % name
        snare = orchestra.KITS[character.kit]["snare"]
        kit = [note for player, note in played(take, "drums", "valley") if player == "kit"]
        assert not any(note.pitch == snare for note in kit if note.start < middle - 1e-6), "%s: the backbeat goes on" % name
        assert any(note.pitch == snare for note in kit if note.start >= middle - 1e-6), "%s: the groove does not come back" % name
        # The clean guitar sings the theme over it.
        assert {player for player, _ in played(take, "lead", "valley")} == {"guitar"}


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
        assert (inst.low, inst.high) == (low, high) and not inst.held
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
        # (Walking music of some weight has war drums too since 2026-11-17's "just a bit light and wimpy in general",
        # "dont hear much war drums": softer, later up its rises, the boom at its summit only; and from "go a little
        # harder this is not world of fairy craft" the rhythmic lighter music too, not the delicate.)
        lively = (character.weight >= 0.6 and character.busy >= 0.55) or (
            character.weight >= 0.5 and character.busy >= 0.35 and not set(character.grooves) <= set(orchestra.DELICATE))
        war = fight or heavy or (walk and lively and not set(character.grooves) & set(orchestra.DANCE_GROOVES))
        if war:
            want |= {"war drums", "boom"}
        if not character.band and (war or (character.weight >= 0.6 and hand)):
            want.add("frame drums")
        # (Grim heavy music has the tam-tam at its summit in the gong's place, and so has a boss: see `colours`.)
        kinds = set(character.kinds) if len(character.kinds) < len(orchestra.KINDS_ALL) else set()
        grim = heavy and (bool(kinds & {"haunted", "infernal"}) or character.role == "boss")
        if not character.band and (fight or heavy) and character.weight >= 0.9 and not grim:
            want.add("gong")
        if forge or (not character.band and war and len(character.kinds) < len(orchestra.KINDS_ALL)
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


def test_lively_lighter_music_of_the_desert_has_frame_drums_and_soft_war_drums_and_a_village_dance_has_neither():
    # (Its war drums since 2026-11-17's "just a bit light and wimpy in general", "dont hear much war drums": softer than a
    # heavy piece's, from part of the way up its rises; the frame drums give them the summit.)
    caravan = orchestra.Take(orchestra.family(character_called("caravan"), 5, "f", "F"), 1)
    assert caravan.soft_war
    assert set(drums_of(caravan)) == {"frame drums", "swell", "war drums", "boom"}
    assert {part for part in orchestra.PARTS if any(name == "frame drums" for name, _ in played(caravan, "drums", part))} \
        == {"second", "build", "arrival", "climb"}
    dance = orchestra.Take(orchestra.family(character_called("village dance"), 5, "f", "F"), 1)
    assert set(drums_of(dance)) == {"swell"}
    # The kit's own bass drum is still the kit's: the deep stroke of the same name is another thing.
    boom = orchestra.KITS[dance.ch.kit]["boom"]
    assert any(note.pitch == boom for note in dance.voices["drums"]["kit"].notes) and "boom" not in dance.voices["drums"]


def test_where_the_war_drums_play_the_orchestras_low_drums_make_room():
    take = orchestra.Take(orchestra.family(character_called("skirmish"), 5, "f", "F"), 1)
    kit, boom = take.voices["drums"]["kit"].notes, orchestra.KITS[take.ch.kit]["boom"]
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
    kick = orchestra.KITS[band.ch.kit]["boom"]
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
    ting = orchestra.KITS[forge.ch.kit]["ting"]
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


def test_a_take_staged_again_without_a_channel_leaves_no_old_recording_of_it(tmp_path):
    folder = tmp_path / "warcraft" / "test-family" / "1"
    meta = made_track(folder)
    (folder / "bass.mp3").write_bytes(b"from the night the tracks were MP3")
    studio.write_track(folder, meta, {"lead": tone(11 * RATE, 440, 0.1)})               # the drums are silent this time
    assert not (folder / "drums.flac").exists() and not (folder / "bass.mp3").exists()
    assert set(studio.read_track(folder)[1]) == {"lead"}


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

    def wired(voice):
        return voice.instrument in orchestra.INSTRUMENTS and orchestra.INSTRUMENTS[voice.instrument].wired

    assert "rhythm guitar" in riffs and wired(riffs["rhythm guitar"]) and riffs["rhythm guitar"].notes
    # The band's first theme is the lead guitar's; its second is sung by the organ.
    assert take.solo == "lead guitar" and wired(take.voices["lead"]["lead guitar"])
    assert take.other == "rock organ" and not wired(take.voices["lead"]["rock organ"])
    # (...and the valley's tune is the clean guitar's, played straight.)
    assert {name for name, voice in take.voices["lead"].items() if not wired(voice)} == {"rock organ", "rock organ under", "guitar"}
    assert not any(wired(voice) for channel in ("texture", "bass", "drums") for voice in take.voices[channel].values())
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
    # (Knight Rock has music for every kind of moment since 2026-11-18, its towns and battlegrounds among them.)
    assert {fam.character.role for fam in knight} == set(studio.ROLES)
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


def test_a_whole_build_keeps_what_was_played_loved_and_banned(tmp_path):
    # (2026-11-18: "make sure whats played is marked as played". A whole build took every piece out and put it in again
    # at no plays: the player took them all for new, and a love or a ban would have been forgotten.)
    from freerock import pieces
    made_track(tmp_path / "studio" / "warcraft" / "test-family" / "1")
    made_track(tmp_path / "studio" / "warcraft" / "test-family" / "2", take=2)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    for folder in studio.staged(tmp_path, "warcraft"):
        studio.import_track(bucket, folder)
    first, last = bucket.clips[0], bucket.clips[-1]
    where = lambda clip: (bucket.pieces[clip.piece]["track"], clip.channel, clip.tier, clip.order, bucket.pieces[clip.piece]["story"])  # noqa: E731
    bucket.played([first.id])
    bucket.played([first.id])
    bucket.mark([last.id], banned=True, loved=False)
    bucket.mark([bucket.clips[1].id], loved=True)
    kept = {where(clip): (clip.plays, clip.loved, clip.banned) for clip in bucket.clips}
    marks = pieces.marks_of(bucket)                    # (a love or a ban is the whole piece's: each of its parts has it)
    marked = sum(1 for clip in bucket.clips if clip.plays or clip.loved or clip.banned)
    assert len(marks) == marked >= 3
    pieces.drop_from(bucket, "warcraft/")
    for folder in studio.staged(tmp_path, "warcraft"):
        studio.import_track(bucket, folder)
    assert all(clip.plays == 0 and not clip.loved and not clip.banned for clip in bucket.clips)
    assert pieces.restore_marks(bucket, marks) == marked
    assert {where(clip): (clip.plays, clip.loved, clip.banned) for clip in bucket.clips} == kept
    again = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    assert sorted(clip.plays for clip in again.clips if clip.plays) == [2]


def test_the_play_book_keeps_what_was_heard_through_any_build(tmp_path):
    # ("make a db so nightly bucket builds dont reset our playlist", 2026-11-18.) Plays, loves and bans go into a book
    # beside the buckets as they happen; a bucket whose pieces are all taken out and put in again, or loaded afresh from
    # its folder, takes them back from the book.
    from freerock import pieces
    from freerock.playbook import PlayBook
    made_track(tmp_path / "studio" / "warcraft" / "test-family" / "1")
    made_track(tmp_path / "studio" / "warcraft" / "test-family" / "2", take=2)
    shelf = forever.Buckets(tmp_path / "buckets")
    bucket = shelf.get("Duskwood", "warcraft")
    assert bucket.book is not None and bucket.book.path == tmp_path / "plays.sqlite3"
    for folder in studio.staged(tmp_path, "warcraft"):
        studio.import_track(bucket, folder)
    first, last = bucket.clips[0], bucket.clips[-1]
    bucket.played([first.id])
    bucket.played([first.id])
    bucket.mark([last.id], banned=True)
    book = PlayBook(tmp_path / "plays.sqlite3").marks("warcraft")
    assert sorted(plays for plays, _, _ in book.values() if plays) == [2]
    assert sum(1 for _, _, banned in book.values() if banned) == sum(1 for clip in bucket.clips if clip.banned) >= 1
    # Every piece out and in again, as a whole build does it, without the build's own carrying over: the book alone.
    pieces.drop_from(bucket, "warcraft/")
    for folder in studio.staged(tmp_path, "warcraft"):
        studio.import_track(bucket, folder)
    assert all(clip.plays == 0 and not clip.banned for clip in bucket.clips)
    assert bucket.sync_book() >= 2
    assert sorted(clip.plays for clip in bucket.clips if clip.plays) == [2]
    banned = [clip for clip in bucket.clips if clip.banned]
    assert banned and all(bucket.pieces[clip.piece].get("banned") for clip in banned)
    # A bucket loaded from its folder after its plays were lost there takes them back too.
    for clip in bucket.clips:
        clip.plays, clip.banned = 0, False
    bucket._save()
    again = forever.Buckets(tmp_path / "buckets").by_key(bucket.key)
    assert sorted(clip.plays for clip in again.clips if clip.plays) == [2] and any(clip.banned for clip in again.clips)


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


def test_every_character_has_ground_the_atlas_knows():
    # The player prefers the piece written for the ground underfoot (woods, water, heights...): every character of every
    # style must say its ground, or that never reaches it (2026-11-18: 23 of Knight Rock's characters and 24 of
    # Warcraft's had none).
    from freerock import atlas
    from freerock.studio import orchestra
    names = {name for name, _ in atlas.SETTINGS}
    for character in orchestra.CHARACTERS:
        ground = orchestra.settings_of(character)
        assert ground, "%s has no ground" % character.name
        assert set(ground) <= names, "%s: %s" % (character.name, ground)


def test_an_effect_moves_through_the_piece():
    # Effects over time (2026-11-18, "yes you need effects over time"): an envelope inside the effect's place in the
    # chain, its points on the project's clock and kept inside the setting's range.
    from freerock.studio import desk
    effect = desk.automated(desk.js("filters/resonantlowpass", 300, 0.3), 0, [(0.0, 300.0), (10.0, 99999.0)], 20, 20000)
    head, envelope = effect.split("<PARMENV", 1)
    assert head.startswith("<JS filters/resonantlowpass") and effect.endswith("WAK 0 0")
    assert envelope.startswith(" 0 20 20000 300")
    points = [row.split() for row in envelope.splitlines() if row.startswith("PT ")]
    assert [(float(at), float(value)) for _, at, value, _ in points] == [(desk.LEAD, 300.0), (desk.LEAD + 10.0, 20000.0)]
    steps = desk.sweep(0.0, 8.0, 250, 16000, steps=6)
    ratios = {round(b[1] / a[1], 6) for a, b in zip(steps, steps[1:])}
    assert len(ratios) == 1 and steps[0][1] == 250 and round(steps[-1][1]) == 16000      # the same step in pitch each time


# ---------------------------------------------------------------------------------------------
# The music sheet (2026-11-18: "the music sheet should be a separate concept and asset for every track, and updating it
# should be the golden rule", "remember your music sheets are your core principal and most important asset")
# ---------------------------------------------------------------------------------------------
def _a_sheet() -> score.Sheet:
    lead = score.Voice(instrument="lead guitar", pan=0.2, shift=0.012, swells=[(0.0, 0.4), (8.0, 0.9)])
    lead.add(0.0, 1.5, 64, 0.81234567)
    lead.add(1.5 + 1e-7, 0.25, 66, 0.5)
    lead.mark("wah", [(0.0, 0.0), (4.0, 1.0)])
    lead.set("wah beats", 0.5)
    kit = score.Voice(instrument="kit rock", drums=True)
    kit.add(0.0, 0.5, 36, 0.9)
    return score.Sheet(style="knight", family="a-family-1", take=2, title="A Title", tempo=104.0, beats=4.0,
                       form=[{"story": "open", "part": "open", "first": 0, "bars": 2, "key": "D dorian", "chords": ["i", "i"], "level": [0.3, 0.5]}],
                       parts={"lead": {"lead guitar": lead}, "drums": {"kit": kit}}, about={"band": True, "ducks under": [[0.0, 0.9]]})


def test_a_sheet_reads_back_exactly_as_it_was_written_and_keeps_the_revision_it_replaces(tmp_path):
    sheet = _a_sheet()
    sheet.revised("the first draft", "a test", by="the writer")
    path = tmp_path / "sheet.json"
    sheet.save(path)
    again = score.Sheet.load(path)
    assert again == sheet
    assert again.parts["lead"]["lead guitar"].notes[1].start == 1.5 + 1e-7       # every number exactly as written
    again.parts["lead"]["lead guitar"].notes[0].pitch = 62
    again.revised("the first note a tone lower", "it clashed with the chord", by="the loop")
    again.save(path)
    assert score.Sheet.load(path).revision == 2
    assert score.Sheet.load(tmp_path / "sheet.r1.json").parts["lead"]["lead guitar"].notes[0].pitch == 64


def test_only_the_effect_marks_and_settings_the_desk_knows_can_be_written():
    voice = score.Voice(instrument="lead guitar")
    with pytest.raises(ValueError):
        voice.mark("chorus", [(0.0, 1.0)])
    with pytest.raises(ValueError):
        voice.set("wah speed", 1.0)
    voice.mark("wah", [(4.0, 1.0)])
    voice.mark("wah", [(0.0, 0.0)])
    assert voice.effects["wah"] == [(0.0, 0.0), (4.0, 1.0)]           # marks join in time order


def test_the_desk_plays_a_parts_effect_marks_on_its_tracks():
    from freerock.studio import desk, sounds
    voice = score.Voice(instrument="lead guitar")
    voice.mark("wah", [(0.0, 0.0), (8.0, 1.0)])
    voice.mark("lowpass", [(0.0, 400.0), (8.0, 20000.0)])
    voice.set("wah beats", 0.5)
    pedals, sweep = sounds.marked(voice, 120.0)
    assert pedals.startswith("<JS freerock/pedals") and sweep.startswith("<JS freerock/sweep")
    settings = pedals.splitlines()[1].split()
    assert float(settings[1]) == 0.5                                      # the wah rocked in eighths
    points = [(float(at), float(value)) for _, at, value, _ in (row.split() for row in pedals.splitlines() if row.startswith("PT "))]
    assert points == [(desk.LEAD, 0.0), (desk.LEAD + 4.0, 1.0)]           # beats at 120 to the minute: seconds
    assert "<PARMENV 0 20 20000" in sweep
    assert sounds.marked(score.Voice(instrument="lead guitar"), 120.0) == []
    with pytest.raises(ValueError):
        sounds.marked(score.Voice(instrument="lead guitar", effects={"chorus": [(0.0, 1.0)]}), 120.0)


def test_a_long_openings_bass_goes_with_its_chords():
    # (2026-11-18, the boredom meter: Gull's Edge's basses held the key note 27 bars of its 28-bar opening.) Where a long
    # opening's harmony leaves home, the held bass goes with the chord, and comes back with it.
    take = orchestra.Take(_family("highland-cliffside-wind-1"), 1)
    beats = take.beats
    section, first, key, chords = take.spans[0]
    assert section.part == "open" and section.bars >= 16
    notes = sorted((note for voice in take.voices["bass"].values() for note in voice.notes if note.start < first + section.bars * beats),
                   key=lambda note: note.start)
    away = [bar for bar, chord in enumerate(chords) if chord.root % 7 != 0]
    assert away
    for bar in away:
        under = [note.pitch for note in notes if bar * beats <= note.start - first < (bar + 1) * beats]
        assert under and all((pitch - key.pitch(chords[bar].root, 40)) % 12 == 0 for pitch in under)
    home = [note.pitch for note in notes if note.start - first < beats]
    assert home and all((pitch - key.tonic) % 12 == 0 for pitch in home)


def test_a_solo_is_brought_up_over_the_rhythm_guitars_where_it_plays():
    # (2026-11-19: Barnyard Jamboree's solo came out 3.4 dB under the rhythm guitars.) The lead is brought up where the
    # solo plays until it stands SOLO_OVER dB over them, eased in and out, and no further than SOLO_MOST; a solo already
    # over them is left as it is.
    from freerock import analysis
    from freerock.studio import build
    rate = build.RATE
    t = np.arange(rate * 8) / rate
    tone = lambda hz, db: (np.sin(2 * np.pi * hz * t) * 10 ** (db / 20)).astype(np.float32)[:, None].repeat(2, axis=1)  # noqa: E731
    span = (2 * rate, 6 * rate)
    parts = {"lead": tone(880.0, -26.0), "rhythm": tone(220.0, -20.0)}
    lift, curve = build.solo_lift(parts, span, rate // 2)
    assert 0 < lift <= build.SOLO_MOST and curve is not None
    lifted = parts["lead"] * curve[:, None]
    over = analysis.loudness_lufs(lifted[span[0]:span[1]], rate) - analysis.loudness_lufs(parts["rhythm"][span[0]:span[1]], rate)
    assert abs(over - build.SOLO_OVER) < 0.3 or lift == build.SOLO_MOST
    assert curve[0] == 1.0 and curve[-1] == 1.0 and 1.0 < curve[span[0] - rate // 4] < curve[span[0]]      # eased in
    loud = {"lead": tone(880.0, -12.0), "rhythm": tone(220.0, -20.0)}
    assert build.solo_lift(loud, span, rate // 2) == (0.0, None)
    assert build.solo_lift({"lead": tone(880.0, -40.0), "rhythm": tone(220.0, -10.0)}, span, rate // 2)[0] == build.SOLO_MOST


def test_a_part_can_stand_louder_than_its_instrument(monkeypatch):
    # (2026-11-18: the sung solo, played at the lead's own level, was 2 dB under the rhythm guitars.) A part's "gain db"
    # turns every track that plays it up by that much; a part without it is as its instrument stands.
    from freerock.studio import desk, sounds
    made = [desk.Line("a", desk.bare("a", []), volume=0.5), desk.Line("b", desk.bare("b", []), volume=0.25)]
    monkeypatch.setattr(sounds, "_lines", lambda voice, title, bpm, **_: [desk.Line(line.name, line.template, volume=line.volume) for line in made])
    plain = sounds.lines(score.Voice(instrument="lead guitar"), "plain", 120.0)
    lifted_voice = score.Voice(instrument="lead guitar")
    lifted_voice.set("gain db", 6.0)
    lifted = sounds.lines(lifted_voice, "solo", 120.0)
    assert [line.volume for line in plain] == [0.5, 0.25]
    assert [round(line.volume / before.volume, 3) for line, before in zip(lifted, plain)] == [round(10 ** (6.0 / 20), 3)] * 2
    take = orchestra.Take(_family("anywhere-banner-war-2"), 1)
    assert take.voices["lead"]["lead guitar solo"].settings["gain db"] == orchestra.SOLO_LIFT > 0


def _family(name: str) -> orchestra.Family:
    return next(fam for fam, _ in build.plan() if fam.name == name)


def test_a_bands_guitars_are_marked_where_their_own_music_asks(monkeypatch):
    # (2026-11-18: "guitars should have effects in the 70s bro", "the music itself should denote the effects it shouldnt
    # be standard".) Hammer Thunder: its lead rocks a wah only through the summit, where it runs, and cries on the long
    # notes of its first arrival; its rhythm guitar's jets end on the arrivals; the second guitar in harmony is dry.
    monkeypatch.setattr(orchestra, "BAND_PEDALS", True)
    monkeypatch.setattr(orchestra, "SOLOS", False)              # (with its solo, the summit has no pedal: see the solo's test)
    take = orchestra.Take(_family("infernal-forge-anthem-1"), 3)
    beats = take.beats
    starts = {section.part: first for section, first, _, _ in take.spans}
    ends = {section.part: first + section.bars * beats for section, first, _, _ in take.spans}
    lead = take.voices["lead"]["lead guitar"]
    wah = lead.effects["wah"]
    on = lambda at: float(np.interp(at, [a for a, _ in wah], [v for _, v in wah]))       # noqa: E731
    assert on((starts["summit"] + ends["summit"]) / 2) == 1.0
    long_notes = [note for note in lead.notes if starts["arrival"] <= note.start < ends["arrival"] and note.length >= 2.0]
    assert long_notes and all(on(note.start + note.length / 2) == 1.0 for note in long_notes)
    between = [note for note in lead.notes if starts["arrival"] <= note.start < ends["arrival"] and note.length < 1.0
               and not any(other.start <= note.start < other.start + other.length for other in long_notes)]
    assert between and all(on(note.start) == 0.0 for note in between)
    assert not take.voices["lead"]["lead guitar twin"].effects
    jets = take.voices["rhythm"]["rhythm guitar"].effects["flanger"]
    for at, value in jets:
        if value > 0:
            assert any(starts["build"] <= at <= ends["build"] or starts["climb"] <= at <= ends["climb"] for _ in [0])
    assert max(at for at, _ in jets) in (ends["build"], ends["climb"])


def test_a_bands_long_rise_opens_on_a_wah_and_its_drummer_turns_to_the_ride():
    # (2026-11-18, the boredom meter on Bridge Charge: its rhythm guitar kept one colour through a 36-bar rise, its drums
    # one through a whole theme.) The wah is rocked back as a long rise begins and opened by hand to the toe by its end,
    # let go before the arrival; the drummer keeps time on the hat for sixteen bars of a theme and on the ride for the next.
    take = orchestra.Take(_family("anywhere-banner-war-2"), 1)
    beats = take.beats
    rhythm = take.voices["rhythm"]["rhythm guitar"]
    wah, where = rhythm.effects["wah"], rhythm.effects["wah position"]
    at = lambda points, x: float(np.interp(x, [a for a, _ in points], [v for _, v in points]))       # noqa: E731
    rises = [(first, first + section.bars * beats) for section, first, _, _ in take.spans if section.story == "rise" and section.bars >= 16]
    assert len(rises) == 2
    for first, last in rises:
        middle = (first + last) / 2
        assert at(wah, middle) > 0.5
        assert at(where, first + beats) < 0.2 < at(where, middle) < at(where, last - 2 * beats)
        assert at(wah, last) == 0.0                                       # the moment comes in open and dry
    assert all(value == 0.0 for _, value in rhythm.effects["wah depth"])  # by hand, never rocked
    kit = take.voices["drums"]["kit"]
    theme = next(first for section, first, _, _ in take.spans if section.part == "first")
    strokes = lambda a, b: {note.pitch for note in kit.notes if theme + a * beats <= note.start < theme + b * beats}  # noqa: E731
    ride = orchestra.KITS[take.ch.kit]["ride"]
    assert ride not in strokes(0, 16) and ride in strokes(16, 32) and ride not in strokes(32, 40)    # its groove is on the toms
    assert strokes(0, 16) <= strokes(16, 32)                                                         # ...which go on under it
    rock = orchestra.Take(_family("infernal-forge-anthem-1"), 3)                                     # a groove on the hat
    kit, beats = rock.voices["drums"]["kit"], rock.beats
    theme = next(first for section, first, _, _ in rock.spans if section.part == "first")
    hat, ride = orchestra.KITS[rock.ch.kit]["hat"], orchestra.KITS[rock.ch.kit]["ride"]
    if any(layer[0] == "hat" for layer in rock.groove["theme"]):
        assert hat in strokes(0, 16) and ride not in strokes(0, 16)
        assert ride in strokes(16, 32) and hat not in strokes(16, 32)


def test_a_heavy_bands_drummer_rides_out_a_long_moment_on_the_bell():
    # (The boredom meter on Bridge Charge: its drums 18 bars of a 40-bar last moment without a change.) The ride's bell
    # joins its groove of the toms for the moment's second sixteen bars, and leaves for the last eight.
    take = orchestra.Take(_family("anywhere-banner-war-2"), 1)
    kit, beats = take.voices["drums"]["kit"], take.beats
    bell = orchestra.KITS[take.ch.kit]["bell"]
    summit = next(first for section, first, _, _ in take.spans if section.part == "summit")
    struck = lambda a, b: {note.pitch for note in kit.notes if summit + a * beats <= note.start < summit + b * beats}  # noqa: E731
    assert bell not in struck(0, 16) and bell in struck(16, 32) and bell not in struck(32, 40)
    # A light band's moment is left as it is.
    light = orchestra.Take(_family("anywhere-tavern-rock-1"), 1)
    moments = [(first, first + section.bars * light.beats) for section, first, _, _ in light.spans if section.part in ("arrival", "summit")]
    assert not any(note.pitch == orchestra.KITS[light.ch.kit]["bell"] and any(a <= note.start < b for a, b in moments)
                   for note in light.voices["drums"]["kit"].notes)


def test_a_light_bands_clean_guitar_shimmers_from_its_second_theme():
    # (2026-11-18, Lantern Walk: a light band whose clean guitar is its whole accompaniment had no mark at all.) Dry
    # through the first theme, the vibe from the second theme on and through the moments, the rises left as they are; a band
    # with a rhythm guitar keeps the vibe for its quiet passages alone.
    def shimmer(name: str, take: int) -> dict[str, float]:
        made = orchestra.Take(_family(name), take)
        guitar = next(voice for parts in made.voices.values() for voice in parts.values() if voice.instrument == "guitar")
        lane = guitar.effects.get("phaser", [])
        at = lambda x: float(np.interp(x, [a for a, _ in lane], [v for _, v in lane])) if lane else 0.0      # noqa: E731
        return {section.part: at(first + section.bars * made.beats / 2) for section, first, _, _ in made.spans}
    light = shimmer("haunted-lantern-walk-1", 4)
    assert light["first"] == 0.0 and light["build"] == 0.0 and light["climb"] == 0.0
    assert light["second"] > 0.4 and light["arrival"] > 0.4 and light["summit"] > 0.4
    band = shimmer("pastoral-banner-ride-1", 5)
    assert all(value == 0.0 for part, value in band.items() if part not in ("valley", "open", "close"))


def test_a_long_openings_lone_guitar_opens_on_a_wah_as_the_band_comes_in():
    # (2026-11-18, Cobra Fever: its lone opening riff went 20 bars without a change.) Dry for the opening's first half,
    # the wah opened by hand across the second, let go as the band comes in.
    take = orchestra.Take(_family("desert-sand-rider-1"), 4)
    single = next(voice for parts in take.voices.values() for voice in parts.values() if voice.instrument == "single guitar" and voice.notes)
    wah, where = single.effects["wah"], single.effects["wah position"]
    at = lambda points, x: float(np.interp(x, [a for a, _ in points], [v for _, v in points]))       # noqa: E731
    section, first = next((section, first) for section, first, _, _ in take.spans if section.story == "open")
    beats, last = take.beats, first + section.bars * take.beats
    assert section.bars >= 16
    assert at(wah, first + 0.25 * (last - first)) == 0.0 and at(wah, first + 0.75 * (last - first)) > 0.5
    assert at(where, first + 0.55 * (last - first)) < at(where, last - 2 * beats)
    assert at(wah, last + beats) == 0.0
    assert all(value == 0.0 for _, value in single.effects["wah depth"])


def test_a_long_opening_played_by_the_whole_band_opens_on_the_rhythm_guitars_wah():
    # (2026-11-18, Hammer Thunder's fifth take: the band opens together and the rhythm guitar carried the 16 bars.) The
    # guitar that carries the riff takes the opening's wah; one that only counts the band in at the end stays dry.
    at = lambda points, x: float(np.interp(x, [a for a, _ in points], [v for _, v in points])) if points else 0.0   # noqa: E731
    take = orchestra.Take(_family("infernal-forge-anthem-1"), 5)
    section, first = next((section, first) for section, first, _, _ in take.spans if section.story == "open")
    last = first + section.bars * take.beats
    rhythm = take.voices["rhythm"]["rhythm guitar"]
    assert not any(voice.instrument == "single guitar" and voice.notes for parts in take.voices.values() for voice in parts.values())
    assert at(rhythm.effects["wah"], first + 0.25 * (last - first)) == 0.0
    assert at(rhythm.effects["wah"], first + 0.75 * (last - first)) > 0.5
    lone = orchestra.Take(_family("desert-sand-rider-1"), 4)
    section, first = next((section, first) for section, first, _, _ in lone.spans if section.story == "open")
    last = first + section.bars * lone.beats
    assert at(lone.voices["rhythm"]["rhythm guitar"].effects.get("wah", []), first + 0.75 * (last - first)) == 0.0


def test_a_wind_player_breathes():
    # (2026-11-18, Moonshine Blues: its harmonica held one chord a minute, notes 16 and 24 bars long, as an organ would.)
    # A held note longer than a breath is played as breaths of whole bars, each let go half a beat before the bar line
    # and taken up again on it; a bagpipe's bag holds its drone on.
    take = orchestra.Take(_family("marsh-bayou-boogie-1"), 4)
    bar_s = take.beats * 60.0 / take.fam.bpm
    harmonicas = [voice for parts in take.voices.values() for voice in parts.values() if voice.instrument == "harmonica" and voice.notes]
    assert harmonicas
    for voice in harmonicas:
        assert max(note.length for note in voice.notes) * bar_s / take.beats <= orchestra.BREATH["harmonica"] + 0.01
    texture = take.voices["texture"]["harmonica"]
    pitches = {}
    for note in texture.notes:
        pitches.setdefault(note.pitch, []).append(note)
    breaths = [b.start - (a.start + a.length) for notes in pitches.values() for a, b in zip(notes, notes[1:])
               if abs(b.start - (a.start + a.length)) < 1.0]
    assert sum(1 for gap in breaths if abs(gap - 0.5) < 0.01) >= 10    # the breaths: half a beat, before a bar line
    assert "bagpipe" not in orchestra.BREATH


def test_a_bands_lead_guitar_takes_a_solo_at_the_summit():
    # ("i want fucking guitar solos in my knight rock, study eddie vedder and pearl jam"; of the first one, runs and bends
    # under a wah from end to end: "all wammy no chill", "thats not a guitar solo thats a solo effect track", 2026-11-18.)
    # The summit's first time round is the lead guitar's solo, sung: sentences with a breath between them, notes held over
    # the chords, in the key's own five notes, one quick run, the highest note held near the end and the key note last; no
    # pedal on it, an echo behind it; then the theme comes back with the twin guitars.
    for name, number in (("anywhere-banner-war-2", 1), ("pastoral-free-company-2", 4)):
        take = orchestra.Take(_family(name), number)
        beats, period = take.beats, take.fam.period
        first = next(first for section, first, _, _ in take.spans if section.part == "summit")
        key = next(key for section, _, key, _ in take.spans if section.part == "summit")
        voice = take.voices["lead"]["lead guitar solo"]
        solo = sorted(voice.notes, key=lambda note: note.start)
        assert solo and all(first <= note.start < first + period * beats for note in solo)
        bright = orchestra.MODES[key.mode][2] == 4
        five = {0, 2, 4, 7, 9} if bright else {0, 3, 5, 7, 10}
        assert sum((note.pitch - key.tonic) % 12 in five for note in solo) >= 0.85 * len(solo)
        breaths, reached = 0, solo[0].start + solo[0].length
        for note in solo[1:]:
            breaths += note.start - reached >= 0.5 - 1e-6
            reached = max(reached, note.start + note.length)
        assert breaths >= period // 2 - 2, "sentences without a breath between them: %d" % breaths
        assert sum(note.length >= 1.5 for note in solo) >= period // 4
        assert sum(note.length < 0.4 for note in solo) <= 0.2 * len(solo), "it shreds"
        top = max(solo, key=lambda note: (note.pitch, -note.start))
        assert top.start >= first + 0.5 * period * beats and top.length >= 2.0
        assert (solo[-1].pitch - key.tonic) % 12 == 0 and solo[-1].length >= 1.5
        assert "wah" not in voice.effects and "echo" in voice.effects
        lead = take.voices["lead"]["lead guitar"]
        assert not [point for point in lead.effects.get("wah", []) if point[0] >= first and point[1] > 0]
        twin = take.voices["lead"]["lead guitar twin"]
        assert not [note for note in twin.notes if first <= note.start < first + period * beats]      # no twin under the solo...
        assert [note for note in twin.notes if note.start >= first + period * beats]                   # ...and the twins after it
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "SOLOS", False)
        plain = orchestra.Take(_family("anywhere-banner-war-2"), 1)
    first = next(first for section, first, _, _ in plain.spans if section.part == "summit")
    assert "lead guitar solo" not in plain.voices["lead"]
    assert [note for note in plain.voices["lead"]["lead guitar twin"].notes if first <= note.start < first + plain.fam.period * plain.beats]


def test_a_heavy_bands_second_theme_rings():
    # (2026-11-18, the boredom meter: a heavy band's rhythm guitar had one distorted colour through both its themes, 42 to 64
    # bars.) In the second theme each chord is struck once and held, with no chugs between; the first theme is as it was,
    # and a light band is left alone.
    def themes(name: str, take: int) -> dict[str, list]:
        made = orchestra.Take(_family(name), take)
        out = {}
        for section, first, _, _ in made.spans:
            if section.part in ("first", "second"):
                last = first + section.bars * made.beats
                out[section.part] = [(voice_name, note) for voice_name, voice in made.voices["rhythm"].items()
                                     for note in voice.notes if first <= note.start < last]
        return out
    heavy = themes("anywhere-banner-war-2", 1)
    chords = [note for name, note in heavy["second"] if name == "rhythm guitar"]
    assert chords and float(np.median([note.length for note in chords])) >= 2.5
    assert not [name for name, _ in heavy["second"] if name == "muted guitar"]
    assert float(np.median([note.length for name, note in heavy["first"] if name == "rhythm guitar"])) < 1.5
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "RING_SECOND", False)
        plain = themes("anywhere-banner-war-2", 1)
    assert float(np.median([note.length for name, note in plain["second"] if name == "rhythm guitar"])) < 1.5
    assert [(name, note.start, note.pitch) for name, note in plain["first"]] == [(name, note.start, note.pitch) for name, note in heavy["first"]]
    light = themes("highland-hill-country-1", 5)
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "RING_SECOND", False)
        light_plain = themes("highland-hill-country-1", 5)
    assert [(name, note.start, note.pitch, note.length) for name, note in light["second"]] == \
        [(name, note.start, note.pitch, note.length) for name, note in light_plain["second"]]


def test_a_heavy_bands_long_rise_climbs():
    # (2026-11-19, the boredom meter: in a fight's 36-bar build Warlord Fury's bass played one note 17 bars and Lightning
    # Runner's rhythm guitar one riff.) Where a heavy band's rise holds a chord nine bars or more, its second half has the riff
    # an octave up over the muted string chugging low and the bass pumping its octaves, and its last bar runs by step into the
    # next bar's note: down where the chords step down (Warlord Fury's build: Bb, Ab, Gb, then F), up where they rise. (Since
    # 08:20 the climb is one of three ways a take plays a long hold: `Take.rise_way`.)
    import pytest as _pytest
    def build_of(name: str, take: int) -> tuple:
        with _pytest.MonkeyPatch.context() as climbing:
            climbing.setattr(orchestra.Take, "rise_way", property(lambda self: "climb"))     # the take's way drawn as a climb
            made = orchestra.Take(_family(name), take)
        section, first, _, _ = next(span for span in made.spans if span[0].part == "build")
        def bar(index: int, voice: str, channel: str) -> list:
            at = first + index * made.beats
            found = made.voices[channel].get(voice)
            return [] if found is None else [note.pitch for note in found.notes if at <= note.start < at + made.beats]
        return section, bar
    section, bar = build_of("desert-warlord-2", 3)
    assert section.chords[:18] == ["4"] * 9 + ["3"] * 9 and section.chords[18:] == ["2"] * 18
    low, high = bar(2, "rhythm guitar", "rhythm"), bar(6, "rhythm guitar", "rhythm")
    assert low and high and min(high) == min(low) + 12                  # the riff's chords an octave up the neck...
    assert set(bar(6, "muted guitar", "rhythm")) <= set(bar(2, "muted guitar", "rhythm"))      # ...over the chug, still low
    assert len(set(bar(2, "picked bass", "bass"))) == 1                 # the first half as it was: the root in eighths
    pump = bar(6, "picked bass", "bass")
    assert pump[1] == pump[0] + 12 and pump[2] == pump[0]               # the octaves pumped
    stair, after = bar(8, "picked bass", "bass"), bar(9, "picked bass", "bass")
    assert stair[0] > stair[2] > stair[4] > stair[6] > after[0] and stair[6] - after[0] <= 2      # runs down into Ab
    assert min(bar(9, "rhythm guitar", "rhythm")) < min(high)           # the next chord brings the riff down again
    section, bar = build_of("anywhere-storm-rider-1", 4)
    assert section.chords == ["4"] * 18 + ["5+"] * 18
    stair, after = bar(17, "picked bass", "bass"), bar(18, "picked bass", "bass")
    assert stair[0] < stair[2] < stair[4] < stair[6] < after[0]         # climbs from under the next chord's root
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "CLIMBS", False)
        section, plain = build_of("desert-warlord-2", 3)
        assert len(set(plain(6, "picked bass", "bass"))) == 1 and min(plain(6, "rhythm guitar", "rhythm")) == min(low)
    assert orchestra.held_runs(["1", "1", "4", "4", "4", "1"]) == [(0, 2), (1, 2), (0, 3), (1, 3), (2, 3), (0, 1)]


def test_a_heavy_bands_second_theme_opens_out_and_its_long_moments_dig_in():
    # (2026-11-19, the boredom meter on King's Oath and Banner Oath, made again with everything of the night before: the drums
    # one colour 34 to 68 bars across both themes, the bass and the drums 32 bars of an arrival or a summit.) The second theme
    # keeps time on the open hat as its guitars ring, then the ride; a moment of 24 bars or more digs in from its sixteenth
    # bar: the crash every other bar over the ride's bell, and the bass pumping its octaves. A light band is left alone.
    from freerock.studio.orchestra import KITS
    def take_of(name: str, number: int) -> tuple:
        made = orchestra.Take(_family(name), number)
        names = {pitch: sound for sound, pitch in KITS[made.ch.kit].items()} if made.ch.kit in KITS else {}
        def at(part: str, bar: int, what: str) -> list:
            section, first, _, _ = next(span for span in made.spans if span[0].part == part)
            start = first + bar * made.beats
            if what == "kit":
                return sorted({names.get(note.pitch, "") for note in made.voices["drums"]["kit"].notes
                               if start <= note.start < start + made.beats})
            return [note.pitch for note in made.voices["bass"]["picked bass"].notes if start <= note.start < start + made.beats]
        return made, at
    made, at = take_of("pastoral-banner-ride-1", 5)
    assert "hat" in at("first", 2, "kit") and "hat open" not in at("first", 2, "kit")
    assert "hat open" in at("second", 2, "kit") and "hat" not in at("second", 2, "kit")
    assert "ride" in at("second", 18, "kit")
    section = next(span[0] for span in made.spans if span[0].part == "summit")
    assert section.bars == 32
    crashes = [bar for bar in range(section.bars) if "crash" in at("summit", bar, "kit")]
    assert crashes == [0, 4, 8, 12] + list(range(16, 32, 2))
    early, late = at("summit", 4, "bass"), at("summit", 20, "bass")
    assert len(set(early)) == 1 and late[1] == late[0] + 12
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "OPENS_OUT", False)
        patch.setattr(orchestra, "DIGS_IN", False)
        _, plain = take_of("pastoral-banner-ride-1", 5)
        assert "hat" in plain("second", 2, "kit") and "hat open" not in plain("second", 2, "kit")
        assert len(set(plain("summit", 20, "bass"))) == 1
    light, light_at = take_of("highland-hill-country-1", 5)
    assert not light.heavy and not any(light.digs_in(span[0].part, span[0].bars, bar) for span in light.spans
                                       for bar in range(span[0].bars))


def test_a_band_take_answers_its_riff_with_fills_of_its_own():
    # (2026-11-19: "hearing that same guitar riff climb in too many knight songs", "cant you study acdc and do different
    # licks".) Every band song had the one walk up to the fifth (b3, 4, b5, 5) at the end of every fourth bar of its riff,
    # about 32 times a song. Each take now draws its own answer and two turns that take turns; none plays the old walk-up;
    # a turn chord is the flat seventh's power chord on the last beat; a take that rings holds its last chord to the bar line.
    fams = [fam for fam, _ in build.plan() if fam.character.style == "knight" and fam.character.band][:24]
    takes = [orchestra.Take(fam, take) for fam in fams for take in (1, 2)]
    assert len({made.fills for made in takes}) >= 0.9 * len(takes)
    def runs_of(made, shape):
        found = 0
        for name in ("rhythm guitar", "single guitar"):
            voice = made.voices["rhythm"].get(name)
            notes = sorted(voice.notes, key=lambda note: note.start) if voice else []
            for a, b, c, d in zip(notes, notes[1:], notes[2:], notes[3:]):
                if d.start - a.start <= 1.0 and (b.pitch - a.pitch, c.pitch - a.pitch, d.pitch - a.pitch) == shape:
                    found += 1
        return found
    assert sum(runs_of(made, (2, 3, 4)) for made in takes) == 0
    turning = next(made for made in takes if made.fills[1][0] == "turn chord" and made.heavy)
    section, first, key, chords = next(span for span in turning.spans if span[0].part == "first")
    bar = 3                                                       # the end of the fourth bar: the first turn
    at = first + bar * turning.beats + turning.beats - 1.0
    struck = sorted(note.pitch for note in turning.voices["rhythm"]["rhythm guitar"].notes if abs(note.start - at) < 0.05)
    root = key.pitch(chords[bar].root, 45)
    root += 12 if root < 40 else -12 if root > 52 else 0
    assert struck and (struck[0] - root) % 12 == 10 and struck[1] - struck[0] == 7
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "OWN_LICKS", False)
        old = orchestra.Take(_family("pastoral-banner-ride-1"), 5)          # a riff band (a strumming band has no licks)
    assert runs_of(old, (2, 3, 4)) > 10


def test_a_bands_pedals_can_be_switched_off():
    # A new sound is heard as a demo before it is used (the plan's principles): the switch that held the pedals back until
    # the demos were heard ("k keep going", 2026-11-18) still takes every mark away.
    assert orchestra.BAND_PEDALS is True and orchestra.ORCHESTRA_MARKS is True
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(orchestra, "BAND_PEDALS", False)
        take = orchestra.Take(_family("infernal-forge-anthem-1"), 3)
    assert not any(voice.effects for parts in take.voices.values() for voice in parts.values())


def test_an_orchestra_is_not_given_a_bands_pedals(monkeypatch):
    monkeypatch.setattr(orchestra, "BAND_PEDALS", True)
    take = orchestra.Take(_family("frozen-whiteout-2"), 2)
    assert not any(voice.effects for parts in take.voices.values() for voice in parts.values())


def test_a_take_is_written_down_whole_as_its_sheet():
    fam = _family("infernal-forge-anthem-1")
    sheet = build.write(fam, 3)
    assert (sheet.style, sheet.family, sheet.take, sheet.title, sheet.tempo) == ("knight", fam.name, 3, fam.title, fam.bpm)
    assert sheet.bars == fam.bars and [section["story"] for section in sheet.form] == [section.story for section in fam.sections]
    assert {"band", "hall", "weight", "seed", "tonic", "ducks under", "soft war", "character", "metre"} <= set(sheet.about)
    assert sheet.history[0]["by"] == "the writer"
    assert sheet.parts["bass"]["sub at the moments"].notes                                # what the desk stacks is on it too


def test_a_valleys_drone_is_held_low_and_not_by_a_reed():
    # (2026-11-18: King's Oath's valley held A4 and E4 on the english horn for 24 bars, pushed up from A2 and E3 by the old
    # bagpipe's floor, and whined over the soft guitar, 12.7 dB over it at pianissimo as at piano: "sometimes when one synth
    # stays in when youre sitting its whiny". The drone goes to the organ, low.)
    sheet = build.write(_family("pastoral-banner-ride-1"), 4)
    valley = next(section for section in sheet.form if section["part"] == "valley")
    a, b = valley["first"] * sheet.beats, (valley["first"] + valley["bars"]) * sheet.beats
    held = [(part.instrument, note.pitch) for part in sheet.parts["texture"].values() for note in part.notes
            if a <= note.start < b and note.length >= 8.0]
    assert held and all(instrument not in orchestra.REEDS and pitch <= 57 for instrument, pitch in held)
    assert orchestra.INSTRUMENTS["pipe drone"].low == 52             # where the english horn really goes down to


def test_a_surge_patch_is_tuned_up_in_its_own_state():
    # (2026-11-18: Argitoth's Trance Lead 1, chosen as House's drop lead, played 22 cents flat as it comes.)
    import base64
    from freerock.studio import desk
    patch = "patches_3rdparty/Argitoth/Leads/Trance Lead 1.fxp"
    plain, tuned = (base64.b64decode(desk.surge(name)["chunk"]) for name in (patch, patch + "@+22"))
    assert len(plain) == len(tuned) and b'<a_pitch type="2" value="0.220000" />' in tuned and b'value="0.220000"' not in plain
    with pytest.raises(ValueError):
        desk.surge(patch + "@-5")                      # only up, where the bytes stay as many
