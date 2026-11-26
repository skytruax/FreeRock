"""The shapes a song can have (orchestra.FORMS), the metres a riff moves in, and the bands that play them."""
import json
import random
import statistics
from dataclasses import replace

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


@pytest.mark.parametrize("character", [each for each in SHAPED if each.form == "jam"], ids=lambda each: each.name)
def test_a_jam_has_a_solo_before_its_last_one_by_someone_else(character):
    for number in range(4):
        fam = made(character, number)
        Take(fam, number)                                                     # (every take of it can be written, whoever leads)
    take = Take(made(character), 0)
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


def test_a_drummer_with_brushes_sweeps_the_snare():
    """(Ragged Beat's second theme: its brushed groove, a side stick and a hat written for the house's kit, stood at -45 LUFS.)"""
    sweep = orchestra.KITS["swept"]["swish"]
    assert all(sweep not in strokes.values() for name, strokes in orchestra.KITS.items() if name != "swept")
    swept = set()
    for character in [each for each in CHARACTERS if each.band and "brushes" in each.grooves]:
        for number in (0, 1):
            take = Take(made(character, number), number)
            kit = take.voices["drums"].get("kit")
            starts = [note.start for note in kit.notes if note.pitch == sweep] if kit else []
            if orchestra.sounded(character.sounds, "kit " + character.kit) != "kit swept":
                assert not starts, "%s has no brushes" % character.name
                continue
            if orchestra.GROOVES["swept"] in (take.groove, take.groove_b):
                swept.add(character.name)
                assert starts and orchestra.GROOVES["brushes"] not in (take.groove, take.groove_b)
                # Swept on the beat: every one falls on a pulse of the song.
                assert all(abs(start / take.pulse - round(start / take.pulse)) < 1e-6 for start in starts), character.name
    assert len(swept) >= 8, swept
    night = next(fam for fam, _ in build.plan() if fam.name == "anywhere-graveyard-shift-1")
    assert build.write(night, 1).parts["drums"]["kit"].instrument == "kit swept"


def test_a_family_past_a_house_band_character_s_third_is_another_band_s_song():
    """(Thirty-six more of the house band's songs stood next in the day's lists: "all the knight rock songs sound like the same song".)"""
    house = {character.name: character for character in CHARACTERS if character.band and not character.sounds}
    old, new = [], []
    for fam, _ in build.plan():
        if fam.character.name in house:
            (old if int(fam.name.rsplit("-", 1)[1]) <= orchestra.FRESH_FROM else new).append(fam)
    assert old and all(fam.character == house[fam.character.name] for fam in old), "a family of its first ones is changed"
    assert len(new) >= 40 and all(fam.character.sounds in BANDS and fam.character.form in ("",) + tuple(FORMS) for fam in new)
    fourth = [fam for fam in new if fam.name.endswith("-4")]
    bands = [fam.character.sounds for fam in fourth]
    assert len(set(bands)) >= 12 and max(bands.count(each) for each in set(bands)) <= 7, bands
    assert len({fam.character.form for fam in fourth}) == 5
    assert len({fam.character.leads[1 % len(fam.character.leads)] for fam in fourth}) >= 12
    assert all(fam.key.mode.startswith(orchestra.FRESH_MODES) for fam in fourth), [fam.key.mode for fam in fourth]
    beside = [fam for fam in fourth if not fam.character.light and fam.character.weight >= 0.7 and fam.character.role not in orchestra.FIGHTS + ("storm",)]
    assert all(one.character.sounds != other.character.sounds for one, other in zip(beside, beside[1:]))
    for fam in fourth[::6]:
        sheet = build.write(fam, 1)
        assert sheet.about["sounds"] == fam.character.sounds == orchestra.band_of(fam, 1)
        played = {voice.instrument for parts in sheet.parts.values() for voice in parts.values() if voice.notes}
        assert not played & {"rhythm guitar", "single guitar", "muted guitar", "picked bass", "lead guitar", "kit rock", "kit room"}, (fam.name, played)
        lead = orchestra.sounded(fam.character.sounds, fam.character.leads[1 % len(fam.character.leads)])
        sings = {lead} | (set(orchestra.SINGS[fam.character.sounds]) if lead in orchestra.SUNG else set())     # (a fiddle in a borrowed song is the band's own singer)
        assert any(voice.instrument in sings and len(voice.notes) > 20 for voice in sheet.parts["lead"].values()), (fam.name, lead)


def test_a_light_song_is_another_song_by_another_band():
    """(The bands' test: an inn's song read the same by all fourteen: what it strummed and who sang it was in no band.)"""
    assert set(orchestra.STRUMS) == set(orchestra.SINGS) == set(BANDS)
    from freerock.studio import sounds
    for band in BANDS:
        assert all(each in INSTRUMENTS or each in sounds.AMPS for each in orchestra.STRUMS[band] + orchestra.SINGS[band]), band
    strums = [orchestra.STRUMS[band][0] for band in BANDS]
    assert len(set(strums)) >= 12
    inn = next(fam for fam, _ in build.plan() if fam.name == "anywhere-tavern-rock-1")
    assert orchestra.borrowed(inn) and not orchestra.borrowed(next(fam for fam, _ in build.plan() if fam.name == "anywhere-rogues-quarter-1"))
    import dataclasses
    heard = {}
    plain = build.write(inn, 1)
    house = {voice.instrument for channel in ("lead", "rhythm") for voice in plain.parts[channel].values() if voice.notes}
    for band in orchestra.FRESH_BANDS["light"]:
        sheet = build.write(dataclasses.replace(inn, character=dataclasses.replace(inn.character, sounds=band)), 1)
        heard[band] = frozenset(voice.instrument for channel in ("lead", "rhythm") for voice in sheet.parts[channel].values() if voice.notes)
        assert not heard[band] & (set(orchestra.STRUMMED) - set(orchestra.STRUMS[band])), (band, heard[band])
        for channel in ("lead", "rhythm"):
            for voice in sheet.parts[channel].values():
                inst = INSTRUMENTS[voice.instrument] if voice.instrument in INSTRUMENTS else None
                assert inst is None or all(inst.low <= note.pitch <= inst.high for note in voice.notes), (band, voice.instrument)
    assert len(set(heard.values())) == len(heard) and all(len(each & house) <= 1 for each in heard.values()), (house, heard)


def test_every_company_is_players_the_desk_knows_and_none_is_another_genre_s():
    """("make sure were using unique bands on all genres".)"""
    from freerock.studio import club, muse, sounds
    assert len(orchestra.COMPANIES) >= 10
    signatures = set()
    for name, company in orchestra.COMPANIES.items():
        assert name not in BANDS and name not in club.ACTS
        table = orchestra.company_table(company)
        for written, plays in table.items():
            if written.startswith("kit "):
                assert plays[4:] in orchestra.KITS
                continue
            assert plays in INSTRUMENTS and (plays in muse.PARTS or plays in sounds.SOUNDS), (name, written, plays)
            assert plays not in sounds.AMPS, "%s: an amplifier is Knight Rock's" % name
        assert "violins" not in table.values() and "harp" not in table.values() and "pizzicato" not in table.values(), "%s is the orchestra" % name
        signatures.add((company.high, company.bed, company.pluck))
    assert len(signatures) == len(orchestra.COMPANIES)


def test_a_bass_is_doubled_by_someone_who_can_play_its_line():
    """(2026-11-25, Whaler's Dole and six songs before it: a company's lyre, xylophone or kalimba, given the plucked celli's doubling of the bass, played the bass's line two and three octaves up in the
    bass's channel, 22 dB over the liked stems at 7 kHz.)"""
    plan = {fam.name: fam for fam, _ in build.plan()}
    assert orchestra.DOUBLES_IN_REACH == 5
    for name in ("coast-whalers-hall-1", "marsh-reed-cutters-rest-1", "haunted-side-show-1"):      # the mead hall's lyre, the winds' kalimba, the carnival's xylophone
        sheet = build.write(plan[name], 1)
        low = {tag: min(note.pitch for note in voice.notes) for tag, voice in sheet.parts["bass"].items() if voice.notes}
        assert low and max(low.values()) < 58 and not any(tag.endswith(" doubled") for tag in low), (name, low)
    # ...an orchestra's plucked celli double its bass as they did, and a company's player that reaches the line (the quartet's piano) does too.
    town = build.write(plan["anywhere-alliance-town-1"], 1)
    assert town.parts["bass"]["celli pizz doubled"].instrument == "celli pizz" and len(town.parts["bass"]["celli pizz doubled"].notes) > 100
    reach = [fam for fam, _ in build.plan() if fam.character.sounds == "quartet" and set(fam.character.basses) & {"acoustic bass", "fretless", "basses pizz"}]
    assert reach and any(tag.endswith(" doubled") and voice.notes and voice.instrument in ("piano", "dream piano") for fam in reach[:6] for tag, voice in build.write(fam, 1).parts["bass"].items())
    was, orchestra.DOUBLES_IN_REACH = orchestra.DOUBLES_IN_REACH, None
    try:
        before = build.write(plan["coast-whalers-hall-1"], 1)
        assert before.parts["bass"]["celli pizz doubled"].instrument == "lyre" and min(note.pitch for note in before.parts["bass"]["celli pizz doubled"].notes) >= 64
    finally:
        orchestra.DOUBLES_IN_REACH = was


def test_a_fourth_family_of_an_orchestra_s_is_a_company_s_song_and_the_first_three_stay():
    own = {character.name for character in CHARACTERS if character.sounds}              # (a character that names its company has it from its first family)
    fams = [(fam, takes) for fam, takes in build.plan() if fam.character.style == "warcraft" and fam.character.name not in own]
    old = [fam for fam, _ in fams if int(fam.name.rsplit("-", 1)[1]) <= orchestra.FRESH_FROM]
    new = [fam for fam, _ in fams if int(fam.name.rsplit("-", 1)[1]) > orchestra.FRESH_FROM]
    assert old and not any(fam.character.sounds for fam in old) and len(new) >= 150
    given = [fam.character.sounds for fam in new]
    assert set(given) == set(orchestra.COMPANIES) and max(given.count(each) for each in set(given)) <= 4 * min(given.count(each) for each in set(given)), given
    assert sum(one == other for one, other in zip(given, given[1:])) <= len(given) // 12
    # A company plays where it belongs.
    for fam in new:
        kinds = fam.character.kinds
        assert len(kinds) >= 5 or fam.character.sounds in orchestra.COMPANY_FOR[kinds[0]], (fam.name, fam.character.sounds)
    assert all(fam.key.mode.startswith(orchestra.FRESH_MODES) for fam in new)
    for fam in new[::23]:
        sheet = build.write(fam, 1)
        assert sheet.about["sounds"] == fam.character.sounds
        table = orchestra.SETS[fam.character.sounds]
        played = {voice.instrument for parts in sheet.parts.values() for voice in parts.values() if voice.notes}
        assert not played & {"violins", "violins slow", "violas", "celli", "harp", "pizzicato", "strings slow", "tremolo"} - set(table.values()), (fam.name, fam.character.sounds, played)
        for parts in sheet.parts.values():
            for voice in parts.values():
                inst = INSTRUMENTS.get(voice.instrument)
                if inst and not voice.drums and voice.instrument in table.values():
                    assert all(inst.low <= note.pitch <= inst.high for note in voice.notes), (fam.name, voice.instrument)


def test_a_long_moment_turns_where_a_character_turns():
    """(The second round's studies: a summit's guitars one colour 27 and 29 bars.) The guitars' figure in the stretch is not the moment's."""
    turning = [character for character in CHARACTERS if character.turns and character.weight >= 0.8]
    assert len(turning) >= 5
    ways = set()
    for character in turning:
        for number in range(3):
            fam = made(character, number)
            take = Take(fam, number)
            for section, first, _, _ in take.spans:
                turned = [bar for bar in range(section.bars) if take.dig_turn(section.like, section.bars, bar)]
                if section.like in ("arrival", "summit") and section.bars >= 16:
                    assert turned and turned[0] >= 8 and turned[-1] < section.bars - 1, (character.name, section.part)
                    assert len(turned) >= section.bars // 6
                    ways.add(take.dig_way)
                else:
                    assert not turned
    assert ways == {"ring", "swap"}
    plain = [character for character in CHARACTERS if character.band and not character.turns][:20]
    assert all(Take(made(character), 0).dig_way in ("up", "ring", "plain") for character in plain)


def test_a_light_bands_summit_turns_by_taking_away(monkeypatch):
    """(2026-11-26: Solder-Smoke Embers, a camp's song in six-eight: its summit's guitars the same for all 24 bars, 66 seconds, twenty strummed notes a bar under a solo sixteen bars long and after it
    alike. A light band's last chorus played harder was judged down, and stop-time heard as a hole. Played again with this: the meter's 24 bars gone, the judges on its summit level to a shade up.)"""
    from freerock.studio import orchestra
    assert orchestra.LIGHT_TURNS
    fam = next(fam for fam, _ in build.plan() if fam.name == "anywhere-tinkers-camp-1")

    def summit(take):
        section, first, _ = span(take, "summit")
        strokes = [sum(1 for name, voice in take.voices["rhythm"].items() if "bell" not in name for note in voice.notes
                       if first + bar * take.beats - 1e-6 <= note.start < first + (bar + 1) * take.beats - 1e-6) for bar in range(section.bars)]
        solo = sorted(note.start for note in lead_notes(take, first, first + section.bars * take.beats, solos=True))
        return strokes, int((solo[-1] - first) // take.beats) + 1

    strokes, under = summit(Take(fam, 1))
    assert len(strokes) == 24 and under == 16, (len(strokes), under)
    breaths = [bar for bar in range(24) if bar % 8 == 7 and bar != 23]
    full = [strokes[bar] for bar in range(under, 24) if bar not in breaths]
    comped = [strokes[bar] for bar in range(under) if bar not in breaths]
    assert min(full) >= 24 and max(comped) <= min(full) // 2, strokes                    # under the solo the strummers comp: half the strokes and fewer
    assert breaths == [7, 15] and all(0 < strokes[bar] <= 8 for bar in breaths), strokes   # and at each eight's end the chord once, left to ring
    monkeypatch.setattr(orchestra, "LIGHT_TURNS", False)
    was, _ = summit(Take(fam, 1))
    assert max(was) - min(was) <= 2 and min(was) >= 24, was                               # as it was: every bar alike
    # A heavy band's song, and a light one's whose character does not grow, are written as they were.
    monkeypatch.setattr(orchestra, "LIGHT_TURNS", True)
    for name in ("sirocco", "last orders"):
        character = next(each for each in CHARACTERS if each.name == name)
        assert (character.weight >= 0.8) != (not character.grows), name
        fam = made(character)
        notes = lambda: [(name, note.start, note.pitch) for name, voice in Take(fam, 1).voices["rhythm"].items() for note in voice.notes]     # noqa: E731
        now = notes()
        monkeypatch.setattr(orchestra, "LIGHT_TURNS", False)
        assert notes() == now, name
        monkeypatch.setattr(orchestra, "LIGHT_TURNS", True)


def told_before(take):
    """How much of a take's tune is a bar heard before."""
    by = {}
    for voice in take.voices["lead"].values():
        for note in voice.notes:
            by.setdefault(int(round(note.start * 12) / 12 // take.beats), set()).add((round(note.start % take.beats, 2), note.pitch))
    seen, again = set(), 0
    for bar in sorted(by):
        each = tuple(sorted(by[bar]))
        again += each in seen
        seen.add(each)
    return again / max(len(by), 1)


def test_a_theme_is_told_another_way_each_time_it_comes_back_where_a_character_grows():
    """(2026-11-24: two of the burn's four songs had 62 and 76% of their tune's bars heard before, the library's middle 46.)"""
    growing = [character for character in CHARACTERS if character.grows]
    assert len(growing) >= 20 and {character.form for character in growing} >= {"riff", "verses", "jam", "burn"}
    heard = [told_before(Take(made(character), 0)) for character in growing]
    assert statistics.median(heard) <= 0.4 and max(heard) <= 0.6, sorted(heard)
    less = []
    for character in growing[::3]:
        plain = replace(character, grows=False)
        fam = made(character)
        was, now = Take(replace(fam, character=plain), 0), Take(fam, 0)
        less.append(told_before(was) - told_before(now))
        # The first time it is told it is the tune as it is, whoever has it; and what is not a tune is played as it was.
        section, first, _ = span(now, "first")
        until = first + fam.period * now.beats / 2
        if section.sings in ("first", "again", "valley"):
            # (By the notes' names: a low character's singer goes an octave down where the middle of ALL its notes is at A4 or over (Take.sing_low), and a song that grows has other notes in it than
            # one that does not: the wreckers' soprano saxophone and the caravan's cello tell the same tune an octave apart with and without.)
            assert [(round(note.start, 3), note.pitch % 12) for note in lead_notes(now, first, until)] == [(round(note.start, 3), note.pitch % 12) for note in lead_notes(was, first, until)]
        assert all(len(now.voices[channel][name].notes) == len(voice.notes) for channel in ("bass",) for name, voice in was.voices[channel].items())
    assert statistics.mean(less) >= 0.08, less


def test_a_phrase_turned_upside_down_keeps_its_rhythm_and_comes_home():
    fam = made(next(character for character in CHARACTERS if character.grows and character.form == "burn"))
    chords = next(section for section in fam.sections if section.whose == "first").chords
    take = Take(fam, 0)
    home = next(chords_ for section, _, _, chords_ in take.spans if section.whose == "first")[:fam.period]
    rng = random.Random(7)
    tune = orchestra.theme(rng, fam, home, 0.5)
    for first, last in ((0, fam.period // 2 - 1), (fam.period // 2, fam.period - 1)):
        told = orchestra.turned(random.Random(3), tune, home, fam.beats, first, last)
        assert [(start, length) for start, length, _, _ in told.notes] == [(start, length) for start, length, _, _ in tune.notes]
        for bar in range(fam.period):
            now, was = told.cut(bar * fam.beats, (bar + 1) * fam.beats).notes, tune.cut(bar * fam.beats, (bar + 1) * fam.beats).notes
            if first <= bar < last and now:
                assert now[0][2] % 7 in {step % 7 for step in home[bar].steps}
        assert told.notes[-1][2] % 7 == tune.notes[-1][2] % 7 and told.top - told.bottom <= 14          # (home, or the octave of it that is nearer)
    ways = orchestra.retold(random.Random(5), tune, orchestra.varied(random.Random(1), tune), orchestra.decorated(random.Random(2), tune), home, fam.beats)
    assert len(ways) == 6 and ways[0] is tune and len({tuple(way.notes) for way in ways}) >= 5 and chords


def test_only_the_families_staged_that_way_are_told_another_way():
    """(2026-11-26, after an evening of them: "most of the music we heard last night sucked, the new bands a lot of time just sound random, it got worse not
    better". Until then every family with no take yet was to be told another way each time its theme came back, 1,032 of the plan's 1,656, to bring down how
    much of a tune had been heard before: a tune that is not known again when it comes back.) The 120 families staged that way keep it (never change a family
    that has takes); every other is told as its first telling was, and more of its tune comes back."""
    plain = next(character for character in CHARACTERS if character.band and not character.sounds)
    court = next(character for character in CHARACTERS if not character.band and not character.sounds)
    for character in (plain, court):
        assert [orchestra.fresh(character, number).grows for number in range(6)] == [False, False, False, False, True, True]     # (what `fresh` says: the plan decides)
    planned = {fam.name: fam for fam, _ in build.plan()}
    assert build.GROWN <= set(planned) and len(build.GROWN) == 120
    assert all(fam.character.grows == (name in build.GROWN) for name, fam in planned.items())
    assert not planned["pastoral-banner-ride-1"].character.grows and not planned["regal-five-black-kings-4"].character.grows
    assert planned["haunted-slow-cortege-1"].character.grows                    # (staged on 2026-11-26 with it: as it was)
    # A family of a character written to grow that has no take yet: its tune comes back more than it would have.
    later = [fam for name, fam in sorted(planned.items()) if name not in build.GROWN and next(each for each in CHARACTERS if each.name == fam.character.name).grows][:8]
    assert len(later) == 8
    more = [told_before(Take(fam, 0)) - told_before(Take(replace(fam, character=replace(fam.character, grows=True)), 0)) for fam in later]
    assert statistics.mean(more) >= 0.08 and min(more) >= 0.0, more


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


def test_a_soft_lead_of_a_band_of_other_sounds_is_brought_up_further(tmp_path):
    """(Casket Roll, the first of them: a saxophone's head 4 dB under the piano with the house band's most, 5 dB, given.)"""
    import importlib.util
    from pathlib import Path

    import numpy as np
    import soundfile
    rate = build.RATE
    t = np.arange(rate * 16) / rate
    tone = lambda hz, db: ((np.sin(2 * np.pi * hz * t) * 10 ** (db / 20)).astype(np.float32))[:, None].repeat(2, axis=1)      # noqa: E731
    spans = [(0, 8 * rate), (8 * rate, 16 * rate)]
    parts = {"lead": tone(880.0, -34.0), "rhythm": tone(220.0, -22.0)}
    house, _ = build.tune_lift(parts, spans, rate // 4)
    bands, curve = build.tune_lift(parts, spans, rate // 4, most=build.TUNE_MOST_BANDS)
    assert house == [build.TUNE_MOST] * 2 and bands[0] > build.TUNE_MOST + 3.0 and max(bands) <= build.TUNE_MOST_BANDS
    form = [{"story": "open", "bars": 2}, {"story": "theme", "bars": 2}, {"story": "moment", "bars": 2}]
    edges = [0, 4 * rate, 8 * rate, 12 * rate]
    assert build.sung_spans(form, edges, [(8 * rate, 9 * rate)]) == [(4 * rate, 8 * rate), (9 * rate, 12 * rate)]

    # ...and a take staged with the house band's most is mended in its stem, once.
    path = Path(__file__).resolve().parents[2] / "tools" / "lift_tunes.py"
    spec = importlib.util.spec_from_file_location("lift_tunes", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    folder = tmp_path / "song" / "1"
    folder.mkdir(parents=True)
    sheet = {"tempo": 60.0, "beats": 4.0, "about": {"sounds": "saloon", "band": True}, "parts": {"lead": {"tenor sax": {"instrument": "tenor sax", "notes": [[0.0, 4.0, 60, 0.5]]}}},
             "form": [{"story": "open", "part": "open", "first": 0, "bars": 2}, {"story": "theme", "part": "first", "first": 2, "bars": 2}]}
    meta = {"bar_frames": 4.0 * rate, "sections": [{"story": "open", "bars": 2}, {"story": "theme", "bars": 2}], "measured": {"tune lift": [5.0]}}
    (folder / "sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
    (folder / "track.json").write_text(json.dumps(meta), encoding="utf-8")
    for channel, audio in (("lead", tone(880.0, -29.0)), ("rhythm", tone(220.0, -22.0))):
        soundfile.write(str(folder / (channel + ".flac")), audio, rate, subtype="PCM_24")
    assert tool.lift(folder).startswith("brought up by part")
    after, _ = soundfile.read(str(folder / "lead.flac"), dtype="float32", always_2d=True)
    assert 20 * np.log10(np.abs(after[12 * rate:15 * rate]).max()) > -27.5 and abs(20 * np.log10(np.abs(after[rate:6 * rate]).max()) + 29.0) < 0.2
    kept = json.loads((folder / "track.json").read_text(encoding="utf-8"))["measured"]
    assert kept["tune lift"][0] > 5.5
    assert tool.lift(folder).startswith("already")


def test_an_amplified_instrument_is_held_together_and_the_others_keep_their_range():
    """(Sentence March's valley tune, a chime guitar's, read -48 LUFS; Keel-Scarred Shove's opening riff -40, under its choir.)"""
    from freerock.studio import muse, sounds
    assert set(muse.SQUEEZE) <= set(muse.PARTS) | set(sounds.SOUNDS) and all(0.0 < hold <= 0.7 for hold in muse.SQUEEZE.values())
    assert set(sounds.AMPS) - {"torn organ"} <= set(muse.SQUEEZE)                  # (an organ has no soft hand)
    notes = [Note(0.0, 1.0, 45, 0.25), Note(1.0, 1.0, 45, 1.0)]
    held = muse.shared("crunch guitar", notes)
    assert all([round(note.loud, 3) for note in mine] == [0.7, 1.0] for _, _, mine, _ in held) and [note.loud for note in notes] == [0.25, 1.0]
    for written in ("rhythm guitar", "cello", "tenor sax", "tuba"):
        assert all([note.loud for note in mine] == [0.25, 1.0] for _, _, mine, _ in muse.shared(written, notes))
    # ...and no band's written guitars, basses or lead guitar are left to fall away: each is held, or never falls (an organ, a harpsichord), or is
    # an acoustic instrument played by itself.
    loose = {"organ", "harpsichord", "celli pizz", "torn organ", "upright piano", "marimba", "clarinet", "trumpet", "war tuba", "bari sax", "fiddle"}
    for name, band in BANDS.items():
        for written in ("rhythm guitar", "single guitar", "muted guitar", "picked bass", "fretless", "lead guitar"):
            assert band[written] in muse.SQUEEZE or band[written] in loose, (name, written, band[written])


def test_a_church_organ_plays_a_band_s_songs_on_its_full_stops():
    """(Black Spire Ward: the organ's first theme on its soft stops, under the guitars after eleven dB of lift.)"""
    voice = Voice(notes=[Note(0.0, 1.0, 60, 0.4), Note(1.0, 1.0, 62, 0.9)], instrument="organ")
    orchestra.held(voice)
    assert [round(note.loud, 2) for note in voice.notes] == [0.7, 0.95]
    other = Voice(notes=[Note(0.0, 1.0, 60, 0.4)], instrument="horns")
    orchestra.held(other)
    assert other.notes[0].loud == 0.4
    quiet = Voice(notes=[Note(0.0, 1.0, 60, 0.4)], instrument="clean guitar")
    orchestra.given("cathedral", quiet)
    assert quiet.instrument == "harpsichord" and quiet.settings["gain db"] == orchestra.NEARER["harpsichord"]


def test_a_valley_s_tune_is_measured_against_the_bass_it_sings_over():
    import numpy as np
    rate = build.RATE
    t = np.arange(rate * 16) / rate
    tone = lambda hz, db: ((np.sin(2 * np.pi * hz * t) * 10 ** (db / 20)).astype(np.float32))[:, None].repeat(2, axis=1)      # noqa: E731
    parts = {"lead": tone(880.0, -44.0), "rhythm": tone(220.0, -70.0), "bass": tone(110.0, -28.0)}
    spans = [(0, 16 * rate)]
    assert build.tune_lift(parts, spans, rate // 4)[1] is None                        # (the house band's measure: no guitars, nothing to stand over)
    lifts, curve = build.tune_lift(parts, spans, rate // 4, most=build.TUNE_MOST_BANDS, bass=True)
    assert curve is not None and 4.0 < lifts[0] <= build.TUNE_MOST_BANDS


def test_a_riff_gives_way_to_a_tune_that_is_under_it_still():
    """(Sleet-Blind Salvo's valley: a held riff at -25 over a solo cello at -39, lifted by thirteen already.)"""
    import numpy as np
    rate = build.RATE
    t = np.arange(rate * 24) / rate
    tone = lambda hz, db: ((np.sin(2 * np.pi * hz * t) * 10 ** (db / 20)).astype(np.float32))[:, None].repeat(2, axis=1)      # noqa: E731
    spans = [(0, 8 * rate), (8 * rate, 16 * rate), (16 * rate, 24 * rate)]
    lead, rhythm = tone(880.0, -20.0), tone(880.0, -26.0)
    lead[8 * rate:16 * rate] *= 10 ** (-24.0 / 20.0)
    lead[16 * rate:] *= 10 ** (-8.0 / 20.0)
    downs, curve = build.riff_gives({"lead": lead, "rhythm": rhythm}, spans, rate // 4)
    assert downs[0] == 0.0 and downs[1] == -build.RIFF_GIVES and abs(downs[2] + 4.0) < 0.3, downs       # (6 over is left; 18 under as far as it goes; 2 under to 2 over)
    assert abs(20 * np.log10(curve[12 * rate]) + build.RIFF_GIVES) < 0.01 and curve[4 * rate] == 1.0 and (np.diff(curve) > -1e-3).all()
    assert build.riff_gives({"lead": tone(880.0, -20.0), "rhythm": rhythm}, spans, rate // 4)[1] is None
    assert build.riff_gives({"lead": tone(880.0, -80.0), "rhythm": rhythm}, spans, rate // 4)[1] is None      # (nobody sings: the riff is the music)
    assert build.riff_gives({"lead": lead}, spans, rate // 4) == ([], None)


def test_an_orchestra_s_tune_stands_over_its_accompaniment(tmp_path, monkeypatch):
    """(Of sixty songs read part by part a theme's tune stood 2 to 14 dB under what accompanies it in four of ten: Forgotten Lullaby's second, Watchful Nocturne's.)"""
    import importlib.util
    from pathlib import Path

    import numpy as np
    import soundfile
    rate = build.RATE
    t = np.arange(rate * 24) / rate
    tone = lambda hz, db: ((np.sin(2 * np.pi * hz * t) * 10 ** (db / 20)).astype(np.float32))[:, None].repeat(2, axis=1)      # noqa: E731
    spans = [(0, 8 * rate), (8 * rate, 16 * rate), (16 * rate, 24 * rate)]
    lead, rhythm, bass = tone(880.0, -26.0), tone(880.0, -26.0), tone(880.0, -40.0)
    lead[:8 * rate] *= 10 ** (-5.0 / 20.0)
    lead[16 * rate:] *= 10 ** (-20.0 / 20.0)
    lifts, _ = build.tune_lift({"lead": lead, "rhythm": rhythm, "bass": bass}, spans, rate // 4, most=6.0, bass=True, over=[-1.5, -1.5, -5.0], under_bass=4.0)
    assert abs(lifts[0] - 3.5) < 0.3 and lifts[1] == 0.0 and lifts[2] == 6.0, lifts               # (5 under: to 1.5 under; level: as it is; 20 under: as far as it goes)
    low, _ = build.tune_lift({"lead": tone(880.0, -40.0), "rhythm": tone(880.0, -60.0), "bass": tone(880.0, -31.0)}, spans, rate // 4, most=6.0, bass=True, over=-1.5, under_bass=4.0)
    assert all(abs(each - 5.0) < 0.4 for each in low), low                            # (in a valley the bass may stand four dB over it, no more)
    # Who leads says how far: what is struck or plucked is heard through more.
    notes = {"flute": [(0.0, 4.0), (9.0, 1.0)], "celesta": [(0.0, 1.0), (8.0, 6.0)]}
    assert build.tune_overs(notes, [(0, 8 * rate), (8 * rate, 16 * rate)], float(rate)) == [build.ORCHESTRA_OVER, build.ORCHESTRA_STRUCK] and build.ORCHESTRA_STRUCK < build.ORCHESTRA_OVER
    # ...and a song staged before is brought up in its lead's stem, once.
    monkeypatch.setattr(build, "ORCHESTRA_MOST", 6.0)
    path = Path(__file__).resolve().parents[2] / "tools" / "lift_tunes.py"
    spec = importlib.util.spec_from_file_location("lift_tunes", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    folder = tmp_path / "song" / "1"
    folder.mkdir(parents=True)
    sheet = {"tempo": 60.0, "beats": 4.0, "about": {"sounds": "", "band": False}, "parts": {"lead": {"flute": {"instrument": "flute", "notes": [[0.0, 4.0, 72, 0.5]]}}},
             "form": [{"story": "open", "part": "open", "first": 0, "bars": 2}, {"story": "theme", "part": "first", "first": 2, "bars": 2}]}
    meta = {"bar_frames": 4.0 * rate, "sections": [{"story": "open", "bars": 2}, {"story": "theme", "bars": 2}], "measured": {}}
    (folder / "sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
    (folder / "track.json").write_text(json.dumps(meta), encoding="utf-8")
    for channel, db in (("lead", -32.0), ("rhythm", -26.0), ("bass", -40.0)):
        soundfile.write(str(folder / (channel + ".flac")), tone(880.0, db), rate, subtype="PCM_24")
    assert tool.lift(folder).startswith("brought up by part")
    after, _ = soundfile.read(str(folder / "lead.flac"), dtype="float32", always_2d=True)
    assert abs(20 * np.log10(np.abs(after[12 * rate:15 * rate]).max()) + 27.5) < 0.4 and abs(20 * np.log10(np.abs(after[rate:6 * rate]).max()) + 32.0) < 0.2
    assert abs(json.loads((folder / "track.json").read_text(encoding="utf-8"))["measured"]["tune lift"][0] - 4.5) < 0.4 and tool.lift(folder).startswith("already")


def test_a_tune_that_is_not_a_distorted_guitar_s_is_lifted_further_in_any_band():
    """(Of 414 songs the first theme stood at the desk's 5 dB in 9 of 259 led by the lead guitar, and in 30 of 60 led by a fiddle.)"""
    spans = [(0, 100), (100, 200), (200, 300)]
    lead = {"lead guitar": [0.5, 1.0, 5.0], "fiddle": [10.5, 11.0, 12.0], "choir": [25.0]}
    assert build.tune_caps("", lead, spans, 10.0) == [build.TUNE_MOST, build.TUNE_MOST_BANDS, build.TUNE_MOST_BANDS]
    assert build.tune_caps("doom", lead, spans, 10.0) == [build.TUNE_MOST_BANDS] * 3
    assert build.tune_caps("", {}, spans, 10.0) == [build.TUNE_MOST] * 3


def test_a_solo_picked_up_in_the_bar_before_leaves_its_part_to_be_lifted():
    """(Keel-Scarred Shove: the climb taken for the solo, and left unlifted.)"""
    rate = build.RATE
    notes = [(47.0, 0.5), (47.5, 0.5), (48.0, 4.0), (56.0, 8.0), (120.0, 2.0)]                     # a pickup, the solo, and another solo later
    spans = build.solos_of(notes, 4.0, float(rate))
    assert spans == [(47 * rate, 64 * rate), (120 * rate, 122 * rate)]
    form = [{"story": "open"}, {"story": "rise"}, {"story": "moment"}, {"story": "close"}]
    edges = [0, 16 * rate, 48 * rate, 80 * rate, 130 * rate]
    assert build.sung_spans(form, edges, spans) == [(16 * rate, 47 * rate), (64 * rate, 80 * rate), (80 * rate, 120 * rate), (122 * rate, 130 * rate)]


def test_a_song_is_heard_from_its_first_bar():
    """(169 of the 521 songs of Warcraft's library opened under -36 LUFS, the first minute of them under a game's own sounds.)"""
    heard = [-43.0, -30.0, -29.5, -27.0, -22.0, -35.0, -27.0, -20.0, -38.0]
    lifts = [min((max(heard) - loud) * build.RIDE, 12.0) for loud in heard]
    out = build.opened(heard, lifts)
    assert build.OPEN_FLOOR == -32.0 and build.FIRST_FLOOR == -30.0
    # (A burn is a stair, and a floor does not lift it: written at -47 and -41 under a second theme of -32, a first theme goes no higher than one under what it leads to and an opening two under that,
    # -32 and -34; the most a first theme is brought up, eight, leaves it one short of that, and its opening two under it. Rime-Sealed Crossing's, heard at -35 and -33.)
    burnt = [-47.0, -41.0, -32.0, -31.0, -30.0, -22.0, -25.0, -20.0, -35.0]
    lifted = [each + lift for each, lift in zip(burnt, build.opened(burnt, [0.0] * 9))]
    assert lifted[:3] == [-41.0 + build.FIRST_MOST - 2.0, -41.0 + build.FIRST_MOST, -31.0] == [-35.0, -33.0, -31.0]
    # (2026-11-26: an opening that is no stair, written 51 LUFS down under a first theme of -25, was held three short of the floor by the twelve that was the most: Hard Coin Song's, at -34.9.)
    lone = [-47.0, -25.5, -25.0, -28.0, -23.0, -34.5, -25.5, -22.0, -32.0]
    assert build.OPEN_MOST == 15.0 and -47.0 + build.opened(lone, [0.0] * 9)[0] == build.OPEN_FLOOR
    assert abs(heard[0] + out[0] - max(-20.0 - build.OPEN_UNDER, build.OPEN_FLOOR)) < 1e-6 and out[1:] == lifts[1:]       # 13 dB under the summit, and no lower than where it is heard
    loud = [each + 4.0 for each in heard[1:]]                                                        # (under a loud song's summit of -16 it is the thirteen that hold)
    assert abs(-38.0 + build.opened([-38.0] + loud, [0.0] * 9)[0] - (-16.0 - build.OPEN_UNDER)) < 1e-6
    assert heard[0] + out[0] < heard[1] + lifts[1] - 1.9                                             # and under the theme it leads to
    low = [heard[0], -36.0] + heard[2:]                                                              # (which holds it down where it is soft itself)
    eased = [min((max(low) - loud) * build.RIDE, 12.0) for loud in low]
    brought = build.opened(low, eased)
    assert abs(low[0] + brought[0] - (low[1] + brought[1] - 2.0)) < 1e-6
    # ...and a first theme that is under hearing is brought up as well, under what comes after it (a slow burn's: Basalt Walk's).
    burn = [-36.0, -37.0, -31.0, -27.0, -26.0, -21.0, -23.0, -20.0, -25.0]
    up = build.opened(burn, [0.0] * 9)
    assert burn[2] + up[2] == -30.5 and burn[1] + up[1] == -31.5 and burn[0] + up[0] == -33.5 and not any(up[3:])
    # ...and in a soft song, whose summit is itself low, they are heard still (Daylight-Starved Echo's and Prospector's Stake's openings at -35 under summits of -22: thirteen under a summit that is as far under
    # a loud song's).
    soft = [-38.0, -36.0, -25.0, -23.0, -27.0, -23.0, -25.0, -22.0, -33.0]
    up = [each + lift for each, lift in zip(soft, build.opened(soft, [0.0] * 9))]
    assert up[1] == build.FIRST_FLOOR and up[0] == build.OPEN_FLOOR and up[2:] == soft[2:]
    # ...and all that comes before a song first arrives, half way, each part under the one after it still (Forlorn Hope's).
    slow = [-37.0, -35.0, -33.0, -33.0, -31.0, -22.0, -24.0, -19.0, -34.0]
    up = [loud + lift for loud, lift in zip(slow, build.opened(slow, [0.0] * 9))]
    assert up[:5] == [-34.0, -32.0, -31.0, -31.0, -30.0] and up[5:] == slow[5:] and up[:5] == sorted(up[:5])
    # ...and a valley that is gone is brought half way back to where it is heard, its close left to go (Bluebell Fold's).
    gone = [-30.0, -27.0, -26.0, -24.0, -21.0, -41.0, -26.0, -20.0, -40.0]
    # (...half way to fifteen under, and no lower than the valley's own floor: 2026-11-25, valleys at -37 under summits of -20 and -21 in two of the evening's songs.)
    assert build.LOW_FLOOR == -35.0 and build.LOW_MOST == 8.0
    assert build.opened(gone, [0.0] * 9) == [0.0] * 5 + [max((-20.0 - build.LOW_UNDER + 41.0) / 2.0, build.LOW_FLOOR + 41.0)] + [0.0] * 3
    soft_valley = [-30.0, -27.0, -26.0, -24.0, -22.0, -37.0, -26.0, -21.0, -40.0]                    # (a soft song's: its summit at -21, fifteen under is -36)
    assert build.opened(soft_valley, [0.0] * 9) == [0.0] * 5 + [2.0] + [0.0] * 3                     # to the floor, -35
    assert build.opened(gone[:5] + [-50.0] + gone[6:], [0.0] * 9)[5] == build.LOW_MOST               # and by no more than this
    assert build.opened(gone[:5] + [-34.0] + gone[6:], [0.0] * 9) == [0.0] * 9 and build.opened(gone[:5] + [-90.0] + gone[6:], [0.0] * 9) == [0.0] * 9
    assert build.opened([-36.0, -60.0] + burn[2:], [0.0] * 9)[1] == build.FIRST_MOST
    assert build.opened([-60.0] + heard[1:], [0.0] + lifts[1:])[0] == build.OPEN_MOST                # so far and no further
    loud = [-30.0] + heard[1:]
    assert build.opened(loud, lifts) == lifts                                                        # one that is heard is left
    soft = [-43.0, -42.0, -20.0]
    assert build.opened(soft, [0.0, 0.0, 0.0]) == [7.0, 8.0, 0.0]                                    # (the theme as far as it goes, the opening never over it)
    assert build.opened([-43.0, -42.0], [0.0, 0.0]) == [0.0, 0.0]
    assert build.opened([-80.0] + heard[1:], lifts) == lifts and build.opened([-40.0], [0.0]) == [0.0]


def test_no_more_characters_are_written_in_five_or_in_seven():
    """(2026-11-26: of the Knight Rock songs begun after the evening of 11-24, 66 in 100 were not in 4/4 and a third in 5/4 or 7/8, where the house band's
    are 95 in 100 in 4/4 and none in five or seven; round thirteen's ten Knight songs had not one in 4/4, and its 5/4 ones the judges' lowest. "The new bands a
    lot of time just sound random.") The characters written in 5/4 or 7/8 until that day stay as they are; no more are added."""
    odd = {style: sum(1 for character in CHARACTERS if character.style == style and set(character.metres) & {"5/4", "7/8"}) for style in ("knight", "warcraft")}
    assert odd["knight"] <= 36 and odd["warcraft"] <= 50, odd
