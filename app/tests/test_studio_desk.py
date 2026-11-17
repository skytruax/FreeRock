"""The desk, the sampler instruments and the recorded-instrument reader: everything about them
that can be checked without REAPER (what they write, not how it sounds)."""
from __future__ import annotations

import numpy as np
import pytest
import soundfile

from freerock.studio import desk, samples, sfz
from freerock.studio.samples import Patch, Zone
from freerock.studio.score import Note

RATE = 44100


def tone(hz: float, seconds: float = 2.0, partials: tuple[float, ...] = (1.0, 0.5, 0.33, 0.25)) -> np.ndarray:
    """A steady note: a fundamental and a few overtones, stereo."""
    time = np.arange(int(RATE * seconds)) / RATE
    wave = sum(level * np.sin(2 * np.pi * hz * (number + 1) * time) for number, level in enumerate(partials))
    wave = 0.3 * wave / np.abs(wave).max()
    return np.stack([wave, wave], axis=1).astype(np.float32)


# --- hearing what a recording is ------------------------------------------------------------------
def test_a_recording_is_heard_as_the_note_it_is_and_how_far_out_of_tune():
    note, cents, sure = samples.pitch_of(tone(220.0), RATE, note=9)            # an A, octave not given
    assert note == 57 and abs(cents) < 3 and sure > 0.8
    sharp = 220.0 * 2 ** (12 / 1200)                                            # twelve cents sharp
    note, cents, _ = samples.pitch_of(tone(sharp), RATE, note=9)
    assert note == 57 and 9 < cents < 15


def test_a_low_note_is_not_taken_for_a_high_one():
    # Any smooth sound is like itself a moment later; that must not be read as a very high note.
    note, _, _ = samples.pitch_of(tone(65.41, seconds=3.0), RATE, note=0)
    assert note == 36


def test_a_kettledrum_is_heard_by_its_lowest_strong_partial():
    # A drum's partials are not a harmonic series: 1, 1.5, 2, 2.44 times the note it is tuned to.
    time = np.arange(RATE * 2) / RATE
    drum = sum(level * np.sin(2 * np.pi * 110.0 * ratio * time) * np.exp(-time * 2) for ratio, level in ((1.0, 1.0), (1.5, 0.9), (1.99, 0.6), (2.44, 0.4)))
    assert round(samples.tone_of(np.stack([drum, drum], axis=1), RATE)) == 45  # the A at 110 Hz


@pytest.mark.parametrize("name, expected", [
    ("MOHorn_sus_A#1_v2_1.wav", (10, 2, 1)), ("VlnEns_Spic_G2_v1_rr2.wav", (7, 1, 2)), ("KSHarp_A2_mf1.wav", (9, 5, 1)),
    ("chimes_C3_pp_rr2.wav", (0, 2, 2)), ("b2_ff_1.wav", (11, 7, 1)), ("t22_m_vl7_rr3.flac", (None, 7, 3)),
    ("RopeSnare_low_sn_Main_vl2_rr1.wav", (None, 2, 1)),
])
def test_a_file_name_says_which_note_which_strength_and_which_turn(name, expected):
    assert samples._named(name) == expected


def test_a_folder_of_notes_becomes_zones_that_cover_the_range(tmp_path, monkeypatch):
    monkeypatch.setattr(samples, "SAMPLES", tmp_path)
    folder = tmp_path / "horn"
    folder.mkdir()
    # Named an octave below what they sound (as one of the sets does), two strengths each.
    for name, hz in (("A2", 220.0), ("C3", 261.63), ("E3", 329.63)):
        for layer, level in ((1, 0.3), (2, 1.0)):
            soundfile.write(str(folder / ("Horn_sus_%s_v%d_1.wav" % (name, layer))), tone(hz, 4.0) * level, RATE)
    patch = samples.pitched(folder, "horn")
    assert sorted({zone.root for zone in patch.zones}) == [57, 60, 64]          # heard, not read: an octave above their names
    assert patch.calls == 0 or patch.calls == 12
    for root in (57, 60, 64):
        strengths = sorted((zone.soft, zone.hard) for zone in patch.zones if zone.root == root)
        assert strengths[0][0] == 1 and strengths[-1][1] == 127 and strengths[0][1] + 1 == strengths[1][0]
    covered = sorted((zone.low, zone.high) for zone in patch.zones if zone.soft == 1)
    assert covered[0][0] == 57 - samples.REACH and covered[-1][1] == 64 + samples.REACH
    assert all(first[1] + 1 == second[0] for first, second in zip(covered, covered[1:]))     # no gaps, no overlaps
    assert all(zone.loop > 0 and 0.5 < zone.until < 1.0 for zone in patch.zones)             # held notes go round


# --- instruments for the sampler ------------------------------------------------------------------
@pytest.fixture
def section(tmp_path, monkeypatch) -> Patch:
    monkeypatch.setattr(sfz, "SAMPLES", tmp_path)
    zones = []
    for root in (55, 58, 62):
        for layer, (soft, hard) in enumerate(((1, 64), (65, 127)), start=1):
            file = "s_%d_v%d.wav" % (root, layer)
            soundfile.write(str(tmp_path / file), tone(220.0, 4.0), RATE)
            zones.append(Zone(files=(file,), low=root - 1, high=root + 1, root=root, soft=soft, hard=hard, loop=1400.0, until=0.85))
    return Patch(name="section", zones=zones, attack=70.0, release=330.0)


def test_a_section_fades_between_its_soft_and_hard_recordings_on_the_controller(section):
    text = sfz.held(section, players=1, blend=True)
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    assert len(regions) == 6
    soft, hard = (next(row for row in regions if "s_55_v%d" % layer in row) for layer in (1, 2))
    assert "xfout_locc1" in soft and "xfin_locc1" not in soft and "xfin_locc1" in hard and "xfout_locc1" not in hard
    assert "loop_mode=loop_sustain" in text and "loop_start=61740" in soft             # 1.4 s into the recording
    assert "gain_cc1" in text and "cutoff_cc1" in text                                 # louder is also brighter
    assert "pitch_random" not in text and "pitch_oncc136" in text                      # one draw for all the layers of a note
    assert "fil_keytrack" not in text                                                  # a low note's top is not cut lower than a high one's


def test_one_player_plays_one_recording_which_the_notes_own_strength_picks(section):
    text = sfz.held(section)
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    soft, hard = (next(row for row in regions if "s_55_v%d" % layer in row) for layer in (1, 2))
    assert "lovel=1 hivel=64" in soft and "lovel=65 hivel=127" in hard
    assert "xfin_" not in text and "xfout_" not in text                                # two recordings of one player at once are two players


def test_a_note_begun_while_another_is_held_is_slurred_to_it(section):
    text = sfz.held(section, slur=0.1)
    groups = [row for row in text.split("\n") if row.startswith("<group>")]
    assert len(groups) == 2 and "trigger=first" in groups[0] and "trigger=legato" in groups[1] and "ampeg_attack=0.100" in groups[1]
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    assert len(regions) == 12
    slurred = regions[6:]
    assert all("offset=%d" % round(0.1 * RATE) in row for row in slurred) and not any("offset=" in row for row in regions[:6])


def test_a_section_is_three_players_and_the_others_are_the_neighbouring_recordings(section):
    text = sfz.held(section, players=3)
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    assert len(regions) == 18
    others = [row for row in regions if "pan=" in row and "lokey=54 hikey=56" in row]     # the lowest note's other two players
    assert len(others) == 4 and all("s_58_" in row and "pitch_keycenter=58" in row for row in others)
    assert {row.split("pan=")[1].split()[0] for row in others} == {"-45", "45"}


def test_a_hard_note_of_a_section_starts_with_the_bow_digging_in(section, tmp_path):
    soundfile.write(str(tmp_path / "short.wav"), tone(220.0, 0.4), RATE)
    short = Patch(name="short", held=False, zones=[Zone(files=("short.wav",), low=54, high=63, root=57, soft=65, hard=127)])
    text = sfz.held(section, players=1, bite=short)
    bite = [row for row in text.split("\n") if "short.wav" in row]
    assert len(bite) == 1 and "loop_mode=one_shot" in bite[0] and "xfin_lovel=72" in bite[0]


def test_a_struck_instrument_fades_between_strengths_by_how_hard_it_is_struck(section):
    section.held = False
    text = sfz.struck(section)
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    soft, hard = (next(row for row in regions if "s_55_v%d" % layer in row) for layer in (1, 2))
    assert "lovel=1 " in soft and "hivel=127" in hard and "xfout_lovel" in soft and "xfin_lovel" in hard
    assert "loop_mode=one_shot" in text


def test_a_kit_has_each_stroke_on_its_note_and_the_hats_stop_each_other(section):
    closed = Patch(name="hat", held=False, zones=[Zone(files=("s_55_v1.wav", "s_55_v2.wav"), low=42, high=42, root=42)])
    opened = Patch(name="hat open", held=False, zones=[Zone(files=("s_58_v1.wav",), low=46, high=46, root=46)])
    text = sfz.kit([(42, closed), (46, opened)], chokes={42: 1, 46: 1})
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    assert len(regions) == 3 and all("off_by=1" in row for row in regions)
    assert sum("key=42" in row and "seq_length=2" in row for row in regions) == 2


def test_a_war_drum_is_several_drums_struck_together_by_several_players(section):
    one = Patch(name="big", held=False, zones=[Zone(files=("s_55_v1.wav",), low=43, high=43, root=43, soft=1, hard=127)])
    two = Patch(name="deep", held=False, zones=[Zone(files=("s_58_v1.wav",), low=41, high=41, root=41, soft=1, hard=127)])
    text = sfz.layered([(one, 43, 0.0, 36, 40), (two, 41, -2.0, 38, 47)], players=3)
    regions = [row for row in text.split("\n") if row.startswith("<region>")]
    assert len(regions) == 6 and sum("lokey=36 hikey=40 pitch_keycenter=43" in row for row in regions) == 3      # each drum has its own notes
    assert len({row.split("delay=")[1].split()[0] for row in regions}) == 3                  # each player a little apart in time
    assert "pitch_keytrack=35" in text and "cutoff" not in text                              # hardly moved from where it was recorded, and not filtered


# --- writing a project ----------------------------------------------------------------------------
def test_a_python_value_is_written_as_lua():
    assert desk.lua({"name": 'a "b"', "until": 0.5, "list": [1, True, None], 3: "x"}) == (
        '{\n  name = "a \\"b\\"",\n  ["until"] = 0.5,\n  list = {\n    1,\n    true,\n    nil\n  },\n  [3] = "x"\n}')


def test_notes_and_controller_moves_are_written_in_order():
    notes = [Note(0.0, 1.0, 60, 0.5), Note(0.5, 1.0, 60, 1.0), Note(1.0, 0.5, 64, 0.5)]
    rows = desk._events(notes, bpm=60.0, seconds=4.0, early=0.0, controls=[(0.0, 1, 40), (0.5, 1, 40), (1.0, 1, 90)])
    assert rows[0] == "E 0 b0 01 28"                    # the controller before the note it belongs to
    assert rows[1] == "E 0 90 3c 40"
    assert "E 479 80 3c 00" in rows                    # the first C is ended just before it is struck again
    assert sum(" b0 01 " in row for row in rows) == 2  # a move to where it already is is not written twice
    assert rows[-1].endswith("b0 7b 00") and sum(int(row.split()[1]) for row in rows) == 4 * desk.TICKS


TEMPLATE = "\n".join(["<TRACK {11111111-2222-3333-4444-555555555555}", "NAME old", "VOLPAN 1 0 -1 -1 1", "ISBUS 0 0", "NCHAN 2", "FX 1",
                      "<FXCHAIN", "BYPASS 0 0 0", '<JS first ""', "1 - -", ">", "WAK 0 0", ">", ">"])


def test_a_track_is_its_template_with_its_name_level_notes_effects_and_what_it_is_sent():
    line = desk.Line("violins", TEMPLATE, [Note(0.0, 1.0, 60, 0.7)], volume=0.5, pan=-0.4, effects=[desk.js("second", 3)],
                     clips=[(1.5, 2.0, "/a/b.wav")])
    text = desk.track(line, bpm=120.0, seconds=8.0, folder=-1, selected=True, receives=[(3, 0.25)])
    rows = text.split("\n")
    assert 'NAME "violins"' in rows and "VOLPAN 0.500000 -0.4000 -1 -1 1" in rows and "ISBUS 2 -1" in rows and "SEL 1" in rows
    assert "AUXRECV 3 0 0.250000 0 0 0 0 0 0 -1:U 0 -1 ''" in rows
    assert rows.index('<JS first ""') < rows.index('<JS second ""') < rows.index("<ITEM".rjust(9))     # its own effect, then the added one, inside the chain
    assert '        FILE "/a/b.wav"' in rows and "      POSITION 2.500000" in rows            # everything is a second later: the lead-in
    assert "      POSITION 1.000000" in rows                                                # where the notes begin
    assert "{11111111-2222-3333-4444-555555555555}" not in text                       # every track gets identifiers of its own


def test_every_folder_gets_a_hall_that_its_tracks_send_to():
    hall = desk.bare("hall", [desk.js("reverb", 1)])
    one = desk.Line("a", TEMPLATE, [Note(0.0, 1.0, 60, 0.7)], send=0.3)
    two = desk.Line("b", TEMPLATE, [Note(0.0, 1.0, 62, 0.7)])
    text = desk.project([(desk.Line("lead", desk.bare("lead", [])), [one, two])], bpm=100.0, seconds=10.0, out=desk.VAR, tail=6.0, hall=hall)
    names = [row.split('"')[1] for row in text.split("\n") if row.startswith("NAME ")]
    assert names == ["lead", "a", "b", "lead hall"]
    assert text.count("AUXRECV") == 1 and "AUXRECV 1 0 0.300000" in text               # only the one that sends; counted from 0 down the project
    assert "RENDER_RANGE 0 0 17.000000 0 0" in text and "RENDER_STEMS 3" in text and text.count("SEL 1") == 1     # the lead-in, the music, the tail


def test_a_line_of_single_notes_is_slurred_and_chords_are_not():
    from freerock.studio import sounds
    line = [Note(0.0, 0.98, 60, 0.5), Note(1.0, 0.98, 62, 0.5), Note(2.0, 0.5, 64, 0.5), Note(3.0, 1.0, 64, 0.5)]
    joined = sounds._slurred(line, 1.0)
    assert joined[0].length > 1.0 and joined[1].length > 1.0        # each reaches a little into the next
    assert joined[2].length == 0.5                                  # a gap: the next note starts afresh
    assert sounds._slurred([Note(0.0, 2.0, 60, 0.5), Note(0.0, 2.0, 64, 0.5)], 1.0) is None       # together: a chord
    assert sounds._slurred([Note(0.0, 2.0, 60, 0.5), Note(1.0, 2.0, 64, 0.5)], 1.0) is None       # one over the other
