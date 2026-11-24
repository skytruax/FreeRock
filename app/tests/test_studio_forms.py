"""The shapes a song can have (orchestra.FORMS), the metres a riff moves in, and the bands that play them."""
import json
import statistics

import pytest

from freerock import studio
from freerock.studio import build, orchestra
from freerock.studio.orchestra import BANDS, CHARACTERS, FORMS, INSTRUMENTS, LONG, LONGEST, PARTS, SHORTEST, WORD, Take, family
from freerock.studio.score import Note, Voice

SHAPED = [character for character in CHARACTERS if character.form]


def made(character, number=0):
    return family(character, 4100 + 10 * CHARACTERS.index(character) + number, "try-%s-%d" % (character.name.replace(" ", "-"), number), "Try")


def span(take, part):
    """A part of a take's story: the section, its first beat and its last."""
    return next((section, first, first + section.bars * take.beats) for section, first, _, _ in take.spans if section.part == part)


def lead_notes(take, first, last, *, solos=False):
    return [note for name, voice in take.voices["lead"].items() if name.endswith(" solo") == solos
            for note in voice.notes if first - 1e-6 <= note.start < last - 1e-6]


@pytest.mark.parametrize("form", sorted(FORMS))
def test_a_form_says_everything_about_the_nine_parts(form):
    made_of = FORMS[form]
    assert set(made_of.shares) == set(made_of.levels) == set(PARTS)
    assert sum(made_of.shares.values()) == pytest.approx(1.0, abs=0.02)
    for part, (like, sings, whose) in made_of.parts.items():
        assert part in PARTS and like in PARTS
        assert sings in PARTS + ("again", "call", "solo", "rest")
        assert whose in ("", "first", "second")
        assert bool(whose) == (like in orchestra.THEMATIC)
    themes = {orchestra.told(form, part, "first")[2] for part in PARTS}
    assert {"first", "second"} <= themes                     # both of a song's themes are heard
    # Its last two parts are a moment and the close, and a rise comes before that moment: a fight drives a song on to its next rise.
    words = [WORD[orchestra.told(form, part, "first")[0]] for part in PARTS]
    assert words[0] == "open" and words[-2:] == ["moment", "close"] and words[-3] == "rise"


def test_the_story_is_the_form_of_every_character_that_names_none():
    for character in [each for each in CHARACTERS if not each.form][::7]:
        fam = made(character)
        assert [section.part for section in fam.sections] == list(PARTS)
        assert all(section.like == section.sings == section.part for section in fam.sections)
        assert SHORTEST <= fam.seconds <= LONGEST


@pytest.mark.parametrize("character", SHAPED, ids=lambda each: each.name)
def test_a_song_of_a_form_is_as_long_as_its_form_and_every_note_is_in_it(character):
    form = FORMS[character.form]
    for number in range(2):
        fam = made(character, number)
        assert [section.part for section in fam.sections] == list(PARTS)
        assert SHORTEST * form.long / LONG - 1 <= fam.seconds <= LONGEST * form.long / LONG + 1
        for take in range(2):
            written = Take(fam, take)
            for channel, voices in written.voices.items():
                assert any(voice.notes for voice in voices.values()), channel
                for name, voice in voices.items():
                    assert all(note.length > 0 and note.start >= -1e-6 and note.start < written.total + 4 for note in voice.notes), name


@pytest.mark.parametrize("character", SHAPED, ids=lambda each: each.name)
def test_a_song_of_a_form_keeps_the_story_s_manners(character):
    """What holds of the story holds of every shape: whole statements, both themes home, the summit the top, a part under seventy seconds."""
    for number in range(3):
        fam = made(character, number)
        bar_s = fam.beats * 60.0 / fam.bpm
        assert all(len(section.chords) == section.bars for section in fam.sections)
        assert max(section.bars for section in fam.sections) * bar_s <= 70
        assert fam.period in (8, 16) and 15 <= fam.period * bar_s <= 40
        themed = [section for section in fam.sections if section.like in orchestra.THEMATIC]
        for section in themed:
            assert section.bars >= fam.period and section.bars % (fam.period // 2) == 0, section.part
            assert section.chords[fam.period - 1] == "1", "%s does not come home" % section.part
        by = {whose: [section.chords[:fam.period] for section in themed if section.whose == whose] for whose in ("first", "second")}
        assert by["first"] and by["second"] and all(each == by[whose][0] for whose in by for each in by[whose])
        assert by["first"][0] != by["second"][0] and by["second"][0][0] != "1"
        summit = fam.section("summit")
        assert summit.level[0] == max(level for section in fam.sections for level in section.level)
        assert all(section.level[0] <= summit.level[0] - 0.02 for section in fam.sections if section.part != "summit")
        assert fam.sections[-1].chords[-1] == "1"
        assert [section.lifted for section in fam.sections] == [bool(fam.lift) and part in ("climb", "summit", "close") for part in PARTS]
        if character.role in orchestra.FIGHTS:
            assert fam.section("open").bars * bar_s <= 35 and fam.section("close").bars * bar_s <= 40, "a fight does not wait"


def shaped(form):
    return next(character for character in SHAPED if character.form == form)


def test_a_slow_burn_only_rises():
    fam = made(shaped("burn"))
    levels = [section.level for section in fam.sections]
    for before, after in zip(levels[:-1], levels[1:-1]):
        assert after[0] >= before[0] and after[1] >= before[1] - 1e-6          # each part over the one before it, to the summit
    take = Take(fam, 0)
    loud = [statistics.mean(note.loud for voice in take.voices["bass"].values() for note in voice.notes
                            if span(take, part)[1] <= note.start < span(take, part)[2]) for part in ("first", "second", "arrival", "summit")]
    assert loud == sorted(loud)


def test_a_riff_song_leaves_its_opening_to_the_riff_and_answers_its_singer():
    take = Take(made(shaped("riff")), 0)
    section, first, last = span(take, "open")
    assert not lead_notes(take, first, last)
    section, first, last = span(take, "first")
    sung = lead_notes(take, first, last)
    bars = [int((note.start - first) // take.beats) for note in sung]
    assert sung and all(bar % 4 in (0, 1) for bar in bars)                     # two bars called, two left to the riff
    assert min(section.level[0] for section in take.fam.sections if section.part in ("open", "first")) >= 0.45
    assert take.breaks


def test_a_chorus_is_the_same_song_each_time_it_comes_round():
    character = shaped("verses")
    fam = made(character)
    assert fam.section("second").chords[:fam.period] == fam.section("arrival").chords[:fam.period] == fam.section("summit").chords[:fam.period]
    assert fam.section("first").chords[:fam.period] == fam.section("build").chords[:fam.period]
    assert fam.section("first").chords[:fam.period] != fam.section("second").chords[:fam.period]
    assert [fam.section(part).story for part in ("first", "second", "build", "arrival")] == ["theme", "moment", "theme", "moment"]
    assert fam.section("second").level[0] > fam.section("build").level[1]      # the second verse comes down from the chorus


def test_a_jam_has_a_solo_before_its_last_one_by_someone_else():
    take = Take(made(shaped("jam")), 0)
    _, first, last = span(take, "second")
    _, summit, end = span(take, "summit")
    early = {name for name, voice in take.voices["lead"].items() if name.endswith(" solo") and any(first <= note.start < last for note in voice.notes)}
    late = {name for name, voice in take.voices["lead"].items() if name.endswith(" solo") and any(summit <= note.start < end for note in voice.notes)}
    assert early and late and not early & late
    assert not lead_notes(take, first, last)                                   # nobody sings over it


def test_a_moving_riff_fills_its_bar_in_every_metre():
    for metre, (heads, tails, tail_at) in orchestra.RIFF_SHAPES.items():
        beats = orchestra.METRES[metre][0]
        for head in heads:
            assert head[0][0] == 0.0 and all(on + length <= tail_at + 1e-6 for on, length in head)
        for tail in tails:
            assert all(tail_at <= on and on + length <= beats + 1e-6 for on, length in tail)
    for character in [each for each in SHAPED if "low riff" in each.figures]:
        take = Take(made(character), 1)
        assert len(take.moving) == 2
        for riff in take.moving:
            assert len(riff) == 4
            for bar in riff:
                assert bar[0][0] == 0.0 and all(on + length <= take.beats + 1e-6 for on, length, _, _ in bar)
            assert riff[0] != riff[1] or riff[0] != riff[3]


def test_a_song_can_open_on_its_drums_or_its_bass():
    opened = {opening: next(character for character in CHARACTERS if character.opening == opening) for opening in ("drums", "bass")}
    for opening, character in opened.items():
        take = Take(made(character), 0)
        section, first, last = span(take, "open")
        half = first + (section.bars // 2) * take.beats
        def struck(channel, since, until):
            return [note for voice in take.voices[channel].values() for note in voice.notes if since - 1e-6 <= note.start < until - 1e-6]
        assert not struck("rhythm", first, half) and struck("rhythm", half, last)
        assert len(struck(opening, first, half)) >= 2 * (section.bars // 2)               # it plays, not only marks, every bar
    assert all(character.band for character in CHARACTERS if character.opening)
    assert all("low riff" in character.figures for character in CHARACTERS if character.opening == "bass")


def test_no_drum_is_struck_faster_than_a_drummer_can():
    """Six-eight's halves are sixteenths: at a gallop's pace a tom on them is a blur, so the fast songs' grooves have none."""
    for character in [each for each in SHAPED if set(each.metres) & {"6/8", "7/8"}]:
        fam = made(character)
        take = Take(fam, 0)
        kit = take.voices["drums"]["kit"]
        struck = {}
        for note in kit.notes:
            struck.setdefault(note.pitch, []).append(note.start)
        for pitch, starts in struck.items():
            starts = sorted(set(round(each, 3) for each in starts))
            gaps = [(after - before) * 60.0 / fam.bpm for before, after in zip(starts, starts[1:])]
            quick = [gap for gap in gaps if gap < 0.075]
            assert len(quick) <= 0.02 * max(len(gaps), 1), (character.name, pitch, len(quick), len(gaps))


def test_a_band_s_instruments_play_within_their_ranges():
    for character in [each for each in CHARACTERS if each.sounds]:
        take = Take(made(character), 0)
        for channel, voices in take.voices.items():
            for voice in voices.values():
                orchestra.given(character.sounds, voice)
                inst = INSTRUMENTS.get(voice.instrument)
                if inst is not None and not voice.drums and channel in ("lead", "texture", "bass"):
                    assert all(inst.low <= note.pitch <= inst.high for note in voice.notes), (character.name, voice.instrument)
    voice = Voice(notes=[Note(0.0, 1.0, 80), Note(1.0, 1.0, 30)], instrument="rock organ")
    orchestra.given("doom", voice)
    assert voice.instrument == "horns" and [note.pitch for note in voice.notes] == [68, 42]
    assert {"cellos", "cathedral", "saloon"} <= set(BANDS)


def test_what_plays_a_song_is_kept_with_it(tmp_path):
    def track(name, parts):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "sheet.json").write_text(json.dumps({"beats": 4.0, "form": [{"story": "theme", "first": 0, "bars": 4}], "about": {"sounds": "twang"}, "parts": parts}), encoding="utf-8")
        return folder

    notes = [[0.0, 1.0, 60, 0.5]] * 4
    band = track("band", {"lead": {"lead guitar": {"instrument": "sweet lead", "notes": notes}, "lead guitar solo": {"instrument": "sweet lead", "notes": notes * 9}},
                          "rhythm": {"rhythm guitar": {"instrument": "twang guitar", "notes": notes * 3}, "banjo": {"instrument": "banjo", "notes": notes}},
                          "texture": {"oohs": {"instrument": "oohs", "notes": notes}},
                          "drums": {"war drums": {"instrument": "war drums", "notes": notes * 5}, "kit": {"instrument": "kit brushed", "notes": notes}},
                          "bass": {"fretless": {"instrument": "round bass", "notes": notes}}})
    assert studio.lead_of(band) == "sweet lead"
    assert studio.sounds_of(band) == ["choir", "sweet lead", "twang guitar", "kit brushed", "round bass"]
    assert studio.band_of(band) == "twang"
    assert studio.sounds_of(tmp_path / "none") == [] and studio.band_of(tmp_path / "none") == ""


def test_each_band_has_a_balance_of_its_own_near_the_band_s():
    assert set(build.BAND_BALANCE) == set(BANDS)
    for name, places in build.BAND_BALANCE.items():
        assert set(places) <= set(build.BAND) and all(0 < abs(more) <= 1.5 for more in places.values()), name
    assert len({tuple(sorted(places.items())) for places in build.BAND_BALANCE.values()}) == len(BANDS)


def test_every_band_is_played_by_something_the_desk_knows():
    from freerock.studio import muse, sounds
    for name, players in BANDS.items():
        for written, played in players.items():
            if played.startswith("kit "):
                assert played[4:] in sounds.KIT_STROKES, (name, played)
            else:
                assert played in muse.PARTS or played in sounds.SOUNDS, (name, written, played)
