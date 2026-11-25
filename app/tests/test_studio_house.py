"""The dance floor's writer and its synthesiser, on tracks short enough to make in a moment.

The synthesiser's inner loops are compiled by numba, which is not one of FreeRock's own
requirements, so these are skipped where it is not installed. To run them:

    uv run --no-sync --with numba pytest tests/test_studio_house.py
"""
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from freerock import analysis, forever, kinds, studio          # noqa: E402
from freerock.studio import house, synth                       # noqa: E402

SHORT = (2, 4, 2, 4, 2)        # the five parts of the story, in bars: half a minute in all
RATE = synth.RATE


def _cents(audio: np.ndarray, pitch: float) -> float:
    """How far the strongest tone near a MIDI pitch is from it."""
    mono = audio[:, 0] + audio[:, 1]
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    freqs = np.fft.rfftfreq(len(mono), 1.0 / RATE)
    want = synth.hz(pitch)
    at = int(np.argmax(np.where((freqs > want * 0.94) & (freqs < want * 1.06), spectrum, 0.0)))
    a, b, c = (np.log(spectrum[at + shift] + 1e-12) for shift in (-1, 0, 1))
    return float(1200.0 * np.log2((freqs[at] + 0.5 * (a - c) / (a - 2 * b + c) * (freqs[1] - freqs[0])) / want))


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    """One short take, written, played, checked and staged."""
    root = tmp_path_factory.mktemp("house")
    found = house.stage("pastoral-01", 1, root, SHORT)
    return root / "pastoral-01" / "1", found


@pytest.mark.parametrize("patch,slack", [(synth.Patch(), 1.0), (synth.Patch(wave=synth.SQUARE, cutoff=3000), 1.0),
                                         (synth.Patch(wave=synth.SINE, sub=0.5, sub_ratio=1.0), 1.0),
                                         (synth.Keys(detune=0.0), 1.0), (synth.Keys(), 6.0), (synth.String(), 1.5)])
def test_every_kind_of_voice_plays_the_note_it_is_asked_for(patch, slack):
    for pitch in (45, 57, 69, 81):
        out = synth.blank(2.5)
        synth.play(out, patch, 0.1, 2.0, pitch, 0.5, seed=3)
        assert np.abs(out).max() > 0.01, "nothing came out"
        assert abs(_cents(out[RATE // 4:RATE * 2], pitch)) <= slack, "pitch %d is out of tune" % pitch


def test_a_bass_sits_on_its_note_not_an_octave_under_it():
    out = synth.blank(2.5)
    synth.play(out, house.BASS["saw"], 0.1, 2.0, 36, 0.5)          # the C at 65 Hz
    mono = out[:, 0]
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    freqs = np.fft.rfftfreq(len(mono), 1.0 / RATE)
    assert abs(freqs[int(np.argmax(spectrum))] - synth.hz(36)) < 1.0, "the strongest tone is not the note"


@pytest.mark.parametrize("name", sorted(house.BASS))
def test_every_bass_sound_is_in_tune(name):
    for pitch in (33, 40):
        out = synth.blank(3.5)
        synth.play(out, house.BASS[name], 0.1, 3.0, pitch, 0.5, seed=5)
        assert np.isfinite(out).all()
        # Two saws a shade apart are each a shade off: that is the sound, and it is the only one allowed it.
        assert abs(_cents(out[RATE // 2:RATE * 3], pitch)) <= (14.0 if name == "reese" else 2.0)


def test_house_plays_no_organ():
    # (2026-11-20, 21:46, playing House: "No organs in the house music".) No table of House's sounds has an organ, no palette
    # draws one, and the desk plays every sound a palette draws on an instrument of its own that is no organ.
    from freerock.studio import club
    tables = {"bass": house.BASS, "keys": house.KEYS, "lead": house.LEADS, "pad": house.PADS}
    for table in tables.values():
        assert not [name for name in table if "organ" in name]
    for name, palette in house.PALETTES.items():
        for field, table in tables.items():
            for sound in palette[field]:
                assert sound in table and "organ" not in sound, (name, field, sound)
                assert "organ" not in club.PLAYED[(field, sound)].lower(), (name, field, sound, club.PLAYED[(field, sound)])
    assert not [instrument for instrument in club.PLAYED.values() if "organ" in instrument.lower()]


def _surge_there() -> bool:
    from freerock.studio import desk, patches
    return (desk.SURGE / patches.BASE).is_file()


@pytest.mark.skipif(not _surge_there(), reason="Surge XT's patches are not installed here")
def test_houses_own_patches_are_written_as_designed():
    # (2026-11-21: "i think mainly your instruments suck for house", "and design yourself".) Each of House's own patches is
    # Surge's empty saw with its design's settings and modulations, in a state Surge reads: its header names the XML's size.
    import re
    import struct
    import xml.etree.ElementTree as ET
    from freerock.studio import desk, patches
    for name, (values, routes) in patches.DESIGNS.items():
        state = patches.state(name, desk.SURGE)
        assert state[:4] == b"sub3"
        size = struct.unpack("<I", state[4:8])[0]
        root = ET.fromstring(state[32:32 + size].decode("utf-8"))
        assert root.find("meta").get("name") == name
        params = root.find("parameters")
        for key, value in values.items():
            assert abs(float(params.find(key).get("value")) - value) < 1e-5, (name, key)
        for key, wanted in routes.items():
            got = [(int(each.get("source")), float(each.get("depth"))) for each in params.find(key).findall("modrouting")]
            assert got == [(patches.SOURCES[source], depth) for source, depth in wanted], (name, key)
        assert re.search(r'<a_filter1_type type="0" value="[1-9]', state.decode("utf-8", "replace")), name    # each is filtered
    # The pluck dies away and the pad swells: their envelopes as designed, in Surge's log2 seconds.
    pluck, pad = patches.DESIGNS["house pluck"][0], patches.DESIGNS["house pad"][0]
    assert pluck["a_env1_sustain"] == 0.0 and pluck["a_env2_sustain"] == 0.0 and pluck["a_filter1_envmod"] >= 36.0
    assert pad["a_env1_attack"] >= patches.seconds(0.5) and pad["a_env1_release"] >= patches.seconds(1.5)


def test_every_act_is_played_by_something_the_desk_knows_and_none_by_an_organ():
    # (2026-11-24: "house still needs to work on that main synth lead sound", "and also should use differrent bands".)
    from freerock.studio import club, muse, patches, sounds
    assert len(club.ACTS) >= 10
    for name, act in club.ACTS.items():
        for instrument in (act.big, act.late, act.soft, *act.keys, *act.bass, *act.pad):
            assert instrument in sounds.SOUNDS or instrument in muse.PARTS, (name, instrument)
            assert "organ" not in instrument, "no organs in House"
        assert act.machine in ("909", "808", "707", "606") and act.big != act.late, name
    bigs = [act.big for act in club.ACTS.values()]
    assert len(set(bigs)) == len(bigs), "no two acts have one lead"
    # Each lead of House's own is one of the designs, or some of them laid together with the first in front.
    for name, layers in sounds.HOUSE_LEADS.items():
        assert layers[0][1] == 0.0 and all("house lead " + design in patches.DESIGNS for design, _ in layers), name
        assert all(db < 0.0 for _, db in layers[1:]) and len(sounds.SOUNDS[name].players) == len(layers)
    assert all(act in club.ACTS for acts in club.ACTS_FOR.values() for act in acts) and set(club.ACTS) == {act for acts in club.ACTS_FOR.values() for act in acts}


def test_an_act_plays_a_song_of_its_own_and_the_first_takes_stay():
    from freerock.studio import club, sounds
    plain = house.family("pastoral-01")
    assert club.act_of(plain, 1) == "" and {club.act_of(plain, take) for take in (2, 3)} <= set(club.ACTS)
    assert club.act_of(house.family("boss-04"), 1) in club.ACTS_FOR["fight"] and club.act_of(house.family("night-05"), 1) in club.ACTS_FOR["calm"]
    given = [club.act_of(house.family(name), 1) for name in sorted(club.ACTS_ALSO)]
    assert len(set(given)) >= 9 and max(given.count(each) for each in set(given)) <= 5, given
    # The sheet says what plays it, and is played as it says.
    sheet = club.write("boss-04", 1)
    act = club.ACTS[sheet.about["sounds"]]
    leads = {part.instrument for part in sheet.parts["lead"].values()}
    assert leads <= {act.big, act.late, act.soft} and act.big in leads
    assert sheet.about["machine"] == act.machine and all(part.instrument == "house kit " + act.machine for part in sheet.parts["drums"].values())
    heard = club.heard_from(sheet)
    assert {heard.played[key] for key in heard.notes if key[0] == "lead"} == leads
    assert {written for channel, _, _, written, *_ in club.voices(heard) if channel == "lead"} == leads
    was = club.write("pastoral-01", 1)
    assert was.about["sounds"] == "" and all(part.instrument == club.PLAYED[tuple(name.split(" ", 1))] for channel, parts in was.parts.items()
                                             if channel != "drums" for name, part in parts.items())


def test_a_hard_song_has_nothing_sweet_in_it_and_goes_at_its_own_pace():
    # (2026-11-24: of the 193 House songs in the player 102 light, 76 in major keys, maracas in 103.)
    from freerock.studio import club
    hard = [fam for fam in house.PLAN if fam.palette.startswith("hard")]
    assert len(hard) >= 10 and len({fam.bpm for fam in hard}) >= 6 and all(118 <= fam.bpm <= 132 for fam in hard)
    assert all(fam.loop.startswith("H") and not fam.light and club.ACTS[fam.act].drive for fam in hard)
    late = [fam for fam in house.PLAN if fam.palette == "after-hours"]
    assert late and all(fam.role in house.CALM_ROLES and fam.loop.startswith("H") and fam.bpm <= 110 and fam.act in club.ACTS_FOR["calm"] for fam in late)
    assert all(fam.bpm == 110 and not fam.act for fam in house.PLAN if fam not in hard and fam not in late)
    for fam in late:
        sheet = club.write(fam.name, 1)
        assert sheet.about["sounds"] == fam.act and sheet.tempo == fam.bpm and not house.Take(fam, 1).tune.riff
        assert not set(sheet.parts["drums"]) & {"maracas", "snap", "chime", "tambourine", "cabasa"}, (fam.name, set(sheet.parts["drums"]))
        sung = [note.pitch for part in sheet.parts["lead"].values() for note in part.notes]
        assert sung and sum(sung) / len(sung) < 66, (fam.name, sum(sung) / len(sung))
        assert club.act_of(fam, 2) != fam.act and club.act_of(fam, 2) in club.ACTS_FOR["calm"]
    before = (house.BPM, house.BEAT, house.STEP, house.BAR, house.BAR_FRAMES, club.BEAT)
    for fam in hard[::4]:
        sheet = club.write(fam.name, 1)
        assert sheet.tempo == fam.bpm and sheet.about["sounds"] == fam.act and abs(sheet.about["meta"]["bar_frames"] - house.RATE * 240.0 / fam.bpm) < 1e-6
        assert (house.BPM, house.BEAT, house.STEP, house.BAR, house.BAR_FRAMES, club.BEAT) == before         # the pace is the song's, and no other's
        assert not set(sheet.parts["drums"]) & {"maracas", "tambourine", "chime", "snap", "clap2", "agogo", "cabasa"}, set(sheet.parts["drums"])
        played = {part.instrument for channel, parts in sheet.parts.items() if channel != "drums" for part in parts.values()}
        assert not played & {"harp", "marimba", "guitar", "house bell", "house glass", "house piano", "house lead sine", "strings slow", "wurly", "electric piano"}, (fam.name, played)
        big = [note.pitch for part in sheet.parts["lead"].values() if part.instrument == club.ACTS[fam.act].big for note in part.notes]
        assert big and sum(big) / len(big) < 64, (fam.name, sum(big) / len(big))
        # Every note is inside the song, and on its sixteenths at its own pace.
        last = max(note.start for parts in sheet.parts.values() for part in parts.values() for note in part.notes)
        assert last < sheet.bars * 4.0 + 1.0
        kick = next(part for name, part in sheet.parts["drums"].items() if name in club.KICKS)
        assert len(kick.notes) > 200 and all(abs(note.start * 4 - round(note.start * 4)) < 0.05 + fam.swing for note in kick.notes)
        # No roll into its drops, and nothing that climbs: the floor tom coming nearer and half a bar of nothing.
        for section, after in zip(sheet.form, sheet.form[1:]):
            if section["story"] == "rise" and after["story"] == "moment":
                a, b = section["first"] * 4.0, after["first"] * 4.0
                rolled = [note for name in ("snare", "clap", "crack") if name in sheet.parts["drums"] for note in sheet.parts["drums"][name].notes if a - 0.05 <= note.start < b - 0.05]
                beats = [note for note in sheet.parts["drums"]["tom_low"].notes if a - 0.05 <= note.start < b - 0.05]
                assert not rolled and len(beats) == section["bars"] * 4 - 2 and beats[-1].loud > beats[0].loud, (fam.name, len(rolled), len(beats))
        assert not any(air["kind"] == "climb" for air in sheet.airs)
        # A riff hammered on one note: more of it on one pitch than on all the others.
        phrase = house.Take(fam, 1).tune
        assert phrase.riff and all(note.at == int(note.at) and note.length >= 1 for note in phrase.notes)
        counted = [sum(note.degree == each for note in phrase.idea) for each in {note.degree for note in phrase.idea}]
        assert max(counted) * 2 > sum(counted) and len(counted) >= 3, (fam.name, counted)
        # Its chords stand low, a root and its fifth.
        stabs = [note.pitch for part in sheet.parts["rhythm"].values() for note in part.notes]
        assert stabs and max(stabs) <= 79 and sum(stabs) / len(stabs) < 62, (fam.name, max(stabs), sum(stabs) / len(stabs))


def test_a_dark_song_of_tonight_has_nothing_sweet_struck_in_it():
    """(A dark palette's percussion was a light one's: chimes in the haunted, shakers in the caves.)"""
    from freerock.studio import club
    names = {fam.name: fam for fam in house.PLAN}
    assert house.GRIM <= set(names) and all(not names[name].light and club.act_of(names[name], 1) for name in house.GRIM)
    for name, palette in house.PALETTES.items():
        made = house.grim(palette)
        assert len(made["perc"]) >= 2 and not set(made["perc"]) & set(house.SWEET) and set(made["perc"]) <= set(house.PERCUSSION)
        assert palette.get("grim") is None or name == "after-hours"
    for name in sorted(house.GRIM)[::4]:
        sheet = club.write(name, 1)
        assert not set(sheet.parts["drums"]) & {"chime", "maracas", "tambourine", "snap", "cabasa", "cowbell", "agogo_high", "agogo_low"}, (name, set(sheet.parts["drums"]))
        played = {part.instrument for channel in ("lead", "rhythm", "texture") for part in sheet.parts[channel].values()}
        assert not played & {"house bell", "house glass", "harp", "marimba", "house lead sine", "kalimba"}, (name, played)


def test_a_hard_acts_themes_are_held_under_its_drops():
    from freerock.studio import club
    sections = [("open", 0, 4), ("theme", 4, 8), ("rise", 12, 4), ("moment", 16, 8), ("close", 24, 4)]
    frames = int(28 * house.BAR_FRAMES)
    at = lambda curve, bar: float(curve[int(bar * house.BAR_FRAMES)])                             # noqa: E731
    curve = club.held_back(sections, "lead", frames)
    assert len(curve) == frames and abs(at(curve, 8) - 10 ** (club.HELD_BACK["lead"] / 20.0)) < 1e-3
    assert all(abs(at(curve, bar) - 1.0) < 1e-3 for bar in (1, 14, 17, 22, 26)) and np.all(np.diff(curve[int(10 * house.BAR_FRAMES):int(14 * house.BAR_FRAMES)]) >= -1e-6)
    assert np.allclose(club.held_back(sections, "texture", frames), 1.0)
    assert np.allclose(club.held_back(sections, "lead", frames, np.full(frames, 0.5, dtype=np.float32)), 0.5 * curve)
    # (Any other song that is not calm has them held too, less.)
    softer = club.held_back(sections, "lead", frames, held=club.HELD_BACK_SOFTER)
    assert at(curve, 8) < at(softer, 8) < 1.0 and at(softer, 17) > 0.999


def test_a_lead_of_houses_own_is_played_with_accents_and_opens_over_the_drop():
    from freerock.studio import club
    from freerock.studio.score import Note
    form = [{"story": "theme", "first": 0, "bars": 8}, {"story": "moment", "first": 8, "bars": 16}]
    notes = [Note(32.0 + step * 0.25, 0.2, 60 + step % 5, 0.5) for step in range(256)]
    club.accented(notes, form)
    on = [note.loud for note in notes if abs(note.start - round(note.start)) < 0.01]
    between = [note.loud for note in notes if abs(note.start * 2 - round(note.start * 2)) > 0.1]
    assert min(on[-4:]) > 1.4 * max(between[-4:]) and on[-1] > 1.6 * on[0]
    # A hard song's riff is hammered: its strokes between the beats within a decibel of the beat's.
    even = [Note(32.0 + step * 0.25, 0.2, 60, 0.5) for step in range(64)]
    club.accented(even, form, hammered=True)
    assert 1.0 < even[-4].loud / even[-3].loud < 1.13 and even[-4].loud > even[-2].loud > even[-3].loud
    tied = [(note, after) for note, after in zip(notes, notes[1:]) if note.start + note.length > after.start]
    assert tied and all(after.pitch != note.pitch for note, after in tied) and len(tied) < len(notes) / 3


def test_a_dub_chord_has_its_third():
    # (2026-11-24: a bare fifth behind a band-pass rang as a major second and a major third over a phrygian root.)
    from freerock.studio import club
    from freerock.studio.score import Note
    phrygian = {(2 + step) % 12 for step in (0, 1, 3, 5, 7, 8, 10)}                 # D
    notes = [Note(0.0, 0.5, pitch, 0.5) for pitch in (50, 57, 62)] + [Note(1.0, 0.5, pitch, 0.5) for pitch in (51, 58, 63)] + [Note(2.0, 0.5, pitch, 0.5) for pitch in (50, 57)]
    club.with_thirds(notes, phrygian)
    assert [note.pitch for note in notes] == [50, 57, 65, 51, 58, 67, 50, 57]         # D minor, E flat major, and a fifth left alone
    sheet = club.write("marsh-05", 1)
    chords = next(part for part in sheet.parts["rhythm"].values() if part.instrument == "house stab dub")
    struck: dict = {}
    for note in chords.notes:
        struck.setdefault(round(note.start * 16), []).append(note.pitch)
    full = [sorted(chord) for chord in struck.values() if len(chord) >= 3]
    assert len(full) > 50 and sum(any((pitch - chord[0]) % 12 in (3, 4) for pitch in chord) for chord in full) > 0.95 * len(full)


def test_houses_own_oscillators_are_the_waves_they_say():
    # (2026-11-21, afternoon: the classic oscillator's Shape -1 is a pulse and +1 a double saw, an octave up; the designs had
    # read them the other way about.) A classic oscillator is a saw or a pulse, a triangle is the modern oscillator's, and an
    # oscillator of another kind is written with its own settings' kinds: the FM2's ratios as whole numbers.
    import struct
    import xml.etree.ElementTree as ET
    from freerock.studio import desk, patches
    with pytest.raises(ValueError):
        patches.osc(1, shape=1.0)
    for name, (values, _) in patches.DESIGNS.items():
        state = patches.state(name, desk.SURGE)
        size = struct.unpack("<I", state[4:8])[0]
        params = ET.fromstring(state[32:32 + size].decode("utf-8")).find("parameters")
        for n in (1, 2, 3):
            kind = int(params.find("a_osc%d_type" % n).get("value"))
            if params.find("a_mute_o%d" % n).get("value") == "1":
                continue
            if kind == patches.CLASSIC:
                assert float(params.find("a_osc%d_param0" % n).get("value")) in (patches.SAW, patches.PULSE), (name, n)
            elif kind == patches.FM2:
                assert params.find("a_osc%d_param1" % n).get("type") == "0" == params.find("a_osc%d_param3" % n).get("type"), name
            elif kind == patches.MODERN:
                assert float(params.find("a_osc%d_param2" % n).get("value")) == 1.0, name     # its triangle all the way in
    # As described: the hollow pad's squares, the glass pad's triangles, the lead's square an octave under it.
    hollow, glass, lead = (patches.DESIGNS[name][0] for name in ("house pad hollow", "house pad glass", "house lead"))
    assert hollow["a_osc1_param0"] == patches.PULSE and hollow["a_osc1_param1"] == 0.5
    assert glass["a_osc1_type"] == patches.MODERN
    assert lead["a_osc2_param0"] == patches.PULSE and lead["a_osc2_octave"] == -1


def test_houses_whistle_has_its_edge():
    # (2026-11-22, night: Morning on the Hill III's whistle lead 22 dB under the liked stems at its top.) The whistle written
    # for House plays the whistle with its edge: the pure one's sine and triangle, the sine leaned toward a saw, the triangle
    # louder, a soft saturation, the low-pass opened; a template of its own beside the pure whistle's.
    from freerock.studio import patches, sounds
    pure, edge = (patches.DESIGNS[name][0] for name in ("house lead sine", "house lead whistle"))
    assert edge["a_osc1_type"] == pure["a_osc1_type"] == patches.SINE and edge["a_osc2_type"] == pure["a_osc2_type"] == patches.MODERN
    assert edge["a_osc1_param1"] > pure["a_osc1_param1"] and edge["a_level_o2"] > pure["a_level_o2"]
    assert edge["a_ws_type"] == patches.WS_SOFT and "a_ws_type" not in pure
    assert edge["a_filter1_cutoff"] > pure["a_filter1_cutoff"]
    assert sounds.OWN_PATCHES["house lead sine"] == ("own:house lead whistle" if sounds.WHISTLE_EDGE else "own:house lead sine")
    assert sounds.template_of("surge:own/house lead whistle") != sounds.template_of("surge:own/house lead sine")


def test_each_machine_has_its_own_kick(monkeypatch):
    # (2026-11-22, night: House's own kick was the 909's for every machine.) The 808, the 707 and the 606 each have a kick of
    # House's own drawn after the TR-8's (club.MACHINE_KICKS): the 808's body the deepest and falling least, the 707's the
    # shortest with a band-passed knock, the 606's the longest; the 909 keeps its own, and every one is a Geonkick drum.
    from freerock.studio import club, desk, kicks
    designs = {machine: kicks.DESIGNS[name] for machine, (name, _) in club.MACHINE_KICK.items()}
    assert designs["909"] is kicks.DESIGNS["house kick"] and club.MACHINE_KICK["909"][1] == club.KICK_TRIM
    assert designs["808"]["pitch"][0][1] < designs["909"]["pitch"][0][1] and designs["808"]["pitch"][-1][1] < designs["909"]["pitch"][-1][1]
    assert designs["707"]["length"] < min(each["length"] for machine, each in designs.items() if machine != "707")
    assert designs["707"].get("click_type") == 2 and "click_type" not in designs["909"]
    assert designs["606"]["length"] > max(each["length"] for machine, each in designs.items() if machine != "606")
    if (desk.GEONKICK / (kicks.TEMPLATE + ".gkick")).is_file():
        for name in ("house kick 808", "house kick 707", "house kick 606"):
            drum = kicks.design(name, desk.GEONKICK)
            assert drum["kick"]["name"] == name and drum["osc2"]["filter"]["type"] == kicks.DESIGNS[name].get("click_type", 1)


def test_house_plays_its_own_patches():
    # (2026-11-21) Where House leaned on the factory patches most, it plays its own (sounds.OWN_HOUSE): the desk loads them
    # from their designs, at the note written.
    from freerock.studio import desk, sounds
    assert sounds.OWN_HOUSE
    for written, design in sounds.OWN_PATCHES.items():
        player = sounds.SOUNDS[written].players[0]
        assert player.name == "surge:own/" + design[4:] and player.octave == 0, written
        if _surge_there():
            loaded = desk.surge(player.name[6:])
            assert loaded["name"] == "CLAPi: Surge XT" and loaded["chunk"]


@pytest.mark.skipif(not Path("/usr/share/geonkick/presets/HaraldReveryKicks/F-Kick.gkick").is_file(), reason="Geonkick is not installed here")
def test_houses_own_kick_is_a_body_a_punch_and_a_click():
    # (2026-11-21, "and design yourself".) House's kick is designed for Geonkick: a sine falling from 240 Hz to 52 Hz (the
    # body), a triangle on the same fall (the punch) and a short burst of high-passed noise (the click), nothing else, and
    # it is played in the machine's sample's place (club.OWN_KICK).
    from freerock.studio import club, desk, kicks
    drum = kicks.design("house kick", desk.GEONKICK)
    on = sorted(name for name in drum if name.startswith("osc") and drum[name]["enabled"])
    assert on == ["osc0", "osc1", "osc2"] and drum["kick"]["layers"] == [0]
    body, punch, click = drum["osc1"], drum["osc0"], drum["osc2"]
    assert (body["function"], punch["function"], click["function"]) == (0, 2, 4)
    top = kicks.TOP
    first, last = body["freq_env"]["points"][0][1], body["freq_env"]["points"][-1][1]
    assert abs(20.0 * (top / 20.0) ** first - 240.0) < 1.0 and abs(20.0 * (top / 20.0) ** last - 52.0) < 1.0
    assert click["filter"]["enabled"] and click["ampl_env"]["points"][1][0] * drum["kick"]["ampl_env"]["length"] <= 12.0
    assert desk.geonkick("own/house kick").startswith('<LV2 "LV2i: Geonkick Single')
    assert club.OWN_KICK and club.KICK_TRIM > 0.0


def test_the_chorus_and_the_echo_never_make_a_number_that_is_not_one():
    # Hours of silence after a note used to be enough: one sample in millions came out as infinity.
    out = np.zeros((6_152_727, 2), dtype=np.float32)
    synth.play(out, house.PADS["warm"], 0.0, 4.5, 60, 0.2)
    assert np.isfinite(synth.chorus(out, mix=0.4)).all()
    assert np.isfinite(synth.echo(out, 0.1, 0.15)).all()


def test_a_sound_is_the_same_every_time_and_another_number_is_another_sound():
    first, again, other = synth.blank(1.0), synth.blank(1.0), synth.blank(1.0)
    patch = synth.Patch(voices=5, detune=20, spread=0.8, noise=0.02)
    synth.play(first, patch, 0.0, 0.5, 60, seed=11)
    synth.play(again, patch, 0.0, 0.5, 60, seed=11)
    synth.play(other, patch, 0.0, 0.5, 60, seed=12)
    assert np.array_equal(first, again)
    assert not np.array_equal(first, other)


def test_the_drums_are_the_recordings_or_made_here_and_start_on_their_first_sample():
    for name in ("kick", "clap", "hat", "open", "snare", "crash", "ride", "rim", "conga_high", "tambourine", "chime"):
        for machine in ("909", "808", "707", "606"):
            sound = synth.drum(name, machine)
            assert 0.02 * RATE < len(sound) < 5 * RATE
            assert np.abs(sound).max() > 0.5
            assert np.argmax(np.abs(sound) > 0.05 * np.abs(sound).max()) < 0.004 * RATE, "%s starts late" % name
    with pytest.raises(KeyError):
        synth.drum("gong")


def test_everything_ducks_under_the_kick_and_comes_back():
    gain = synth.pump(RATE, [0.25, 0.75], depth=0.6)
    assert gain.max() == pytest.approx(1.0) and gain.min() == pytest.approx(0.4, abs=0.01)
    assert gain[int(0.26 * RATE)] < 0.45 and gain[int(0.7 * RATE)] > 0.99
    assert np.abs(np.diff(gain)).max() < 0.02, "the duck is a click"


def test_a_spike_is_rounded_off_and_the_body_of_the_sound_is_left_alone():
    t = np.arange(RATE) / RATE
    body = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    spiked = body.copy()
    spiked[1000] = 0.9
    tamed = synth.tame(np.stack([spiked, spiked], axis=1))[:, 0]
    assert abs(tamed[1000]) < 0.3, "the spike is still there"
    quiet = np.delete(tamed, 1000)
    assert np.allclose(quiet, np.delete(body, 1000), atol=0.05 * 0.045), "the body of the sound was changed by more than a third of a dB"


def test_every_sound_is_as_loud_as_every_other():
    levels = {}
    for group, pitch in ((house.BASS, 40), (house.KEYS, 64), (house.LEADS, 76), (house.PADS, 60)):
        for name, sound in group.items():
            out = synth.blank(1.5)
            synth.play(out, sound, 0.0, 0.45, pitch, house.trim(sound, pitch), seed=1)
            levels[name] = float(np.sqrt(np.mean(out[:RATE // 2].astype(np.float64) ** 2)))
    assert max(levels.values()) / min(levels.values()) < 1.01, levels


def test_the_plan_covers_every_kind_of_place_and_moment():
    names = [fam.name for fam in house.PLAN]
    assert len(names) == len(set(names)) and len(names) >= 45
    wander = [fam for fam in house.PLAN if fam.role == "wander"]
    for kind in kinds.KINDS:
        mine = [fam for fam in wander if kind in fam.moods]
        assert len(mine) >= 3, "too few families for %s" % kind
        assert any(fam.light for fam in mine) and any(not fam.light for fam in mine), "%s has no light or no heavy music" % kind
    assert {fam.role for fam in house.PLAN} == set(studio.ROLES)
    about = [fam for fam in house.PLAN if fam.role in ("wander", "ember", "night")]
    # ("need some darker stuff", 2026-11-23. It was "mostly light", six in ten of these, from the house's first night on, 2026-11-15.)
    assert 0.4 * len(about) < sum(fam.light for fam in about) < 0.6 * len(about), "the house is meant to be as dark as it is light"
    for role in ("ember", "camp", "night", "town"):
        mine = [fam for fam in house.PLAN if fam.role == role]
        assert any(not fam.light and fam.mode in ("minor", "phrygian", "phrygian dominant", "dorian") for fam in mine), "no dark %s" % role
    for fam in house.PLAN:
        assert fam.loop in house.LOOPS and fam.groove in house.KICKS and fam.palette in house.PALETTES
        assert all(mood in kinds.KINDS for mood in fam.moods)
        # (Two waves since 2026-11-17: four and a half to seven minutes.)
        assert 240.0 <= sum(count for _, count in fam.story) * house.BAR <= 480.0, "%s is not a track of four to eight minutes" % fam.name
        assert (fam.serves == (2,)) == (fam.role in ("battle", "boss"))
        assert (fam.serves == (0, 1, 2)) == (fam.role == "battleground")      # a battleground's music, through its fights too
        palette = house.PALETTES[fam.palette]
        assert all(name in house.BASS for name in palette["bass"]) and all(name in house.BASSES for name in palette["bass_style"])
        assert all(name in house.KEYS for name in palette["keys"]) and all(name in house.LEADS for name in palette["lead"])
        assert all(name in house.PADS for name in palette["pad"]) and all(name in house.HATS for name in palette["hats"])
        assert all(name in house.PERCUSSION for name in palette["perc"])
    assert len({(fam.tonic, fam.loop) for fam in house.PLAN}) >= 40, "the families are too alike"
    assert len({fam.tonic for fam in house.PLAN}) == 12


def test_a_tune_is_an_idea_stated_answered_and_closed_on_the_chords():
    fam = house.family("regal-01")
    changes = house.Changes(fam)
    for take in house.TAKES:
        tune = house.Take(fam, take, SHORT).tune
        again = house.Take(fam, take, SHORT).tune
        assert [(n.at, n.length, n.degree) for n in tune.notes] == [(n.at, n.length, n.degree) for n in again.notes]
        assert max(note.at + note.length for note in tune.notes) <= 256, "the tune is longer than sixteen bars"
        assert min(note.at for note in tune.second) >= 128
        for note in tune.notes:
            assert tune.low <= note.degree <= tune.high
            if note.at % 8 == 0 or note.length >= 4:
                assert changes.within(changes.chord(int(note.at // 16)), note.degree), "a strong note is off the chord"
        # The answer has the idea's rhythm: that is what makes it an answer.
        idea = [(note.at, note.length) for note in tune.first if note.at < 32]
        answer = [(note.at - 32, note.length) for note in tune.first if 32 <= note.at < 64]
        assert idea == answer
        assert len({note.degree for note in tune.first}) >= 4, "the tune has no shape"
    tunes = {tuple(note.degree for note in house.Take(fam, take, SHORT).tune.notes) for take in house.TAKES}
    assert len(tunes) == 3, "the takes of a family have the same tune"


def test_the_bass_only_ever_plays_notes_of_the_scale_and_stays_low():
    for fam in house.PLAN:
        take = house.Take(fam, 1, SHORT)
        scale = {(fam.tonic + step) % 12 for step in house.MODES[fam.mode]}
        loop = take.changes.loop
        for chord, after in zip(loop, loop[1:] + loop[:1]):
            for which in ("R", "F", "O", "A"):
                pitch = take.bass_note(chord, which, after)
                assert pitch % 12 in scale, "%s: the bass leaves the key on %r of %r" % (fam.name, which, chord)
                assert (28 if house.PALETTES[fam.palette].get("low") else 29) <= pitch <= 55, "%s: the bass is out of its range at %d" % (fam.name, pitch)
            assert take.bass_note(chord, "R") % 12 == take.changes.pitch(chord[0], 0) % 12, "the root is not the root"


def test_every_chord_is_laid_out_in_the_key_and_close_to_the_one_before():
    for fam in house.PLAN:
        changes = house.Changes(fam)
        scale = {(fam.tonic + step) % 12 for step in house.MODES[fam.mode]}
        before = None
        for bar in range(0, 2 * changes.turn, changes.slot):
            notes = changes.voicing(changes.chord(bar), 55, 76, before, house.PALETTES[fam.palette]["voicing"])
            assert 3 <= len(notes) <= 5 and all(55 <= note <= 76 for note in notes)
            assert all(note % 12 in scale for note in notes), "%s: a chord leaves the key" % fam.name
            if before:
                assert abs(notes[-1] - before[-1]) <= 7, "%s: the top of the chords leaps about" % fam.name
            before = notes


def test_a_short_track_is_staged_whole(staged):
    folder, found = staged
    meta, parts = studio.read_track(folder)
    assert set(parts) == set(forever.CHANNELS)
    frames = int(round(sum(SHORT) * house.BAR_FRAMES)) + int(round(house.POST_S * RATE))
    assert all(len(audio) == frames for audio in parts.values())
    assert meta["style"] == "house" and meta["family"] == "pastoral-01" and meta["take"] == 1
    assert meta["tempo"] == 110 and meta["bar_frames"] == pytest.approx(RATE * 240 / 110)
    assert [section["story"] for section in meta["sections"]] == list(forever.STORY)
    assert [section["bars"] for section in meta["sections"]] == list(SHORT)
    assert meta["tonic"] == "D major" and meta["moods"] == ["pastoral"] and meta["light"] is True
    # (The quiet edges keep the bass and a little of the drums: standing still once left a synth on its own there.)
    assert meta["floor"]["moment"] == {"drums": 0.6, "bass": 0.5} and meta["floor"]["open"] == {"drums": 0.36, "bass": 0.4}
    assert json.loads((folder / "measured.json").read_text())["family"] == "pastoral-01"


def test_every_track_is_brought_to_one_level_and_its_peaks_held_under_the_ceiling(staged):
    folder, found = staged
    assert found["sections"]["moment"] == pytest.approx(house.MOMENT_LUFS, abs=0.4)
    _, parts = studio.read_track(folder)
    # A track far too loud comes down to the same place, with every part turned down alike.
    loud = {channel: audio * 4.0 for channel, audio in parts.items()}
    bar = house.BAR_FRAMES
    first, last = int(round(8 * bar)), int(round(12 * bar))
    done = house.master(loud, first, last)
    mix = sum(done.values())
    assert np.abs(mix).max() <= house.CEILING + 1e-3
    assert analysis.loudness_lufs(mix[first:last], RATE) == pytest.approx(house.MOMENT_LUFS, abs=0.5)
    ratios = [float(np.abs(done[channel][first:last]).sum() / np.abs(loud[channel][first:last]).sum()) for channel in done]
    assert max(ratios) - min(ratios) < 0.02 * max(ratios), "the parts lost their balance"


def test_a_staged_track_can_be_brought_to_its_level_again_without_being_made_again(staged, tmp_path):
    folder, found = staged
    import shutil
    copy = tmp_path / "pastoral-01" / "1"
    shutil.copytree(folder, copy)
    again = house.remaster("pastoral-01", 1, tmp_path)
    assert again["sections"]["moment"] == pytest.approx(found["sections"]["moment"], abs=0.3)
    meta, parts = studio.read_track(copy)
    assert meta["level_db"] == 0.0 and [section["bars"] for section in meta["sections"]] == list(SHORT)
    # Read back from MP3 (tracks are kept as MP3 since 2026-11-16, night): the encoder's overshoot, summed over five
    # channels, can take the mix a fraction of a decibel over the ceiling it was mastered to (measured: 0.15 dB). Half
    # a decibel is allowed, and nothing near full scale.
    peak = float(np.abs(sum(parts.values())).max())
    assert peak <= house.CEILING * 10 ** (0.5 / 20) and peak < 0.98, "the remastered track peaks at %.4f" % peak


def test_nothing_clips_and_the_parts_die_away_in_the_time_left_for_them(staged):
    folder, found = staged
    _, parts = studio.read_track(folder)
    mix = sum(parts.values())
    # (Read back from MP3: half a decibel is allowed for the encoder's overshoot, as above; what was measured before
    # the track was written is held to the ceiling itself.)
    assert np.abs(mix).max() <= 0.9 * 10 ** (0.5 / 20) and all(np.abs(audio).max() <= 0.98 for audio in parts.values())
    assert found["peak"] <= 0.9
    for channel, audio in parts.items():
        assert np.abs(audio[-RATE // 4:]).max() < 0.004, "the %s is still ringing where the recording ends" % channel


def test_the_kick_lands_on_the_beat_and_the_bass_and_the_tune_are_in_tune_and_in_the_key(staged):
    folder, found = staged
    meta, parts = studio.read_track(folder)
    bar = meta["bar_frames"]
    first, last = int(round(8 * bar)), int(round(12 * bar))          # the moment
    drums = forever.measure(parts["drums"][first:last], RATE, 110, "drums", 4)
    assert drums["problems"] == []
    assert abs(drums["tempo_off"]) < 0.2 and abs(drums["beat_ms"]) < 12.0          # four bars: as near as four bars can say
    scale = house.MODES["major"]
    cents, inside = house.low_notes(parts["bass"][int(round(2 * bar)):last], 2, scale)
    # (Short notes a beat apart cannot be placed nearer than this down there; each bass sound
    # has a test of its own on long notes.)
    assert abs(cents) < 25.0 and inside > 0.9
    for channel in ("rhythm", "lead"):
        key = analysis.estimate_key(parts[channel][first:last], RATE)
        assert abs(key.tuning_cents) < 10.0, "the %s is out of tune" % channel
        assert sum(key.chroma[(2 + step) % 12] for step in scale) > 0.8, "the %s is not in D major" % channel
    assert found["bass_lows_db"] > 6.0, "the bass has no bottom"
    assert found["drum_highs_db"] > -30.0, "the drums have no top"


def test_the_takes_of_a_family_share_its_changes_and_nothing_else():
    fam = house.family("jungle-02")
    takes = [house.Take(fam, take, SHORT) for take in house.TAKES]
    assert len({tuple(take.sections) for take in takes}) == 1
    assert len({tuple(take.kicks()) for take in takes}) == 1, "the takes do not agree where the kick falls"
    assert takes[0].kicks(), "no kick at all"
    basses = [take.bass() for take in takes]
    assert all(len(bass) == takes[0].frames for bass in basses)
    for one, other in ((0, 1), (0, 2), (1, 2)):
        assert not np.allclose(basses[one], basses[other], atol=1e-3), "two takes have the same bass line"
    sounds = {(take.pick("bass", take.palette["bass"]), take.pick("keys", take.palette["keys"]), take.pick("lead", take.palette["lead"]))
              for take in takes}
    assert len(sounds) == 3, "the takes are played on the same instruments"


def test_a_staged_track_goes_into_a_bucket_as_five_pieces_in_a_row(staged, tmp_path):
    folder, _ = staged
    bucket = forever.Bucket(tmp_path, "anywhere", "house", 110, "D major")
    ids = studio.import_track(bucket, folder)
    assert len(ids) == 5
    pieces = [bucket.pieces[piece] for piece in ids]
    assert [piece["story"] for piece in pieces] == list(forever.STORY)
    assert [piece["next"] for piece in pieces] == ids[1:] + [""]
    assert all(piece["family"] == "house/pastoral-01" and piece["light"] and piece["serves"] == [0, 1] for piece in pieces)
    assert pieces[3]["floor"] == {"drums": 0.6, "bass": 0.5} and pieces[0]["floor"] == {"drums": 0.36, "bass": 0.4}
    channels = {clip.channel for clip in bucket.clips if clip.piece == ids[3]}
    assert channels == set(forever.CHANNELS), "the moment is missing a part"
    assert studio.import_track(bucket, folder) == [], "the same track went in twice"


def test_the_air_is_played_in_reaper_by_the_studios_instrument_each_sound_a_note_and_its_sweep_a_controller():
    from freerock.studio import club
    track = house.Take(house.family("highland-01"), 1)           # wind in its gaps, risers into its drops
    airs = track.airs()
    assert {air.kind for air in airs} >= {"sweep", "thud", "wind"}
    lines = club.air_lines(airs)
    assert all('<JS freerock/air ""' in line.template for line in lines)
    by_name = {line.name: line for line in lines}
    rising = by_name["air sweep 250-9000 Hz"]
    first = sorted(rising.controls)
    sweep = [value for _, number, value in first if number == 1]
    assert sweep[0] == 0 and max(sweep) == 127                      # from the low corner to the high one
    # Weather that runs on into more of the same is one sound, faded in once and out once.
    wind = by_name["air wind"]
    starts = sorted(note.start for note in wind.notes)
    assert all(later - earlier > 0 for earlier, later in zip(starts, starts[1:]))
    assert len(wind.notes) < sum(1 for air in airs if air.kind == "wind") + 1
    assert all(0.0 < note.loud <= 1.0 for line in lines for note in line.notes)


def test_a_synth_voice_plays_its_bars_as_loud_as_they_were_written_and_its_notes_only_stand_out_in_them(monkeypatch):
    # (2026-11-17, morning: Surge XT's patches play a note alike however hard it is struck, and the house tracks came out
    # level from end to end: a breakdown's pad written 5 dB under the drop's came out over it.)
    from freerock.studio import club
    monkeypatch.setattr(club.muse, "available", lambda: True)
    heard = club.Heard()
    bar = house.BAR
    for index in range(8):                       # four bars of the drop's groove, then four of a soft breakdown
        level = 0.5 if index < 4 else 0.25
        for step in range(4):
            accent = 1.0 if step == 0 else 0.8
            heard.notes[("bass", "bass", "saw")].append((index * bar + step * bar / 4, bar / 8, 40.0, level * accent, 0.0, 1.0))
    heard.notes[("lead", "lead", "keys")].append((0.0, bar, 64.0, 0.5, 0.0, 1.0))       # the Wurlitzer: MuseScore's
    heard.notes[("lead", "lead", "keys")].append((4 * bar, bar, 64.0, 0.25, 0.0, 1.0))
    found = {(channel, name): (mine, taste, ride) for channel, _, name, _, _, mine, taste, ride in club.voices(heard)}
    notes, taste, ride = found[("bass", "saw")]
    assert taste == 1.0 and ("bass", "saw under") not in found
    assert ride[0] == (0.0, 1.0) and ride[-1] == (16.0, pytest.approx(0.5))       # the fifth bar (beat 16) at half
    assert ride[-2] == (pytest.approx(15.9), 1.0)                                # got to over a tenth of a beat
    # The same accent in a loud bar and in a soft one is struck as hard: the four bars' level is the volume's.
    assert notes[0].loud == pytest.approx(notes[16].loud) and notes[1].loud == pytest.approx(notes[17].loud)
    assert notes[1].loud < notes[0].loud
    wurly, _, wurly_ride = found[("lead", "keys")]
    assert wurly_ride == [] and wurly[1].loud < wurly[0].loud                  # Muse Sounds play softer when struck softer


def test_a_line_written_under_the_tune_is_a_track_of_its_own_and_does_not_take_the_tune_down(monkeypatch):
    # (2026-11-17, morning: the drop's second time round has a line over the tune at 0.26 to its 0.62; read by their mean,
    # the four bars it was in were played 5 dB down, the drop shrinking where it should grow.)
    from freerock.studio import club
    monkeypatch.setattr(club.muse, "available", lambda: True)
    heard = club.Heard()
    bar = house.BAR
    for index in range(8):
        heard.notes[("lead", "lead", "saw")].append((index * bar, bar / 2, 72.0, 0.62, 0.0, 1.0))
        if index >= 4:                           # the second time round, an octave over it
            heard.notes[("lead", "lead", "saw")].append((index * bar, bar / 2, 84.0, 0.26, 0.0, 1.0))
    found = {name: (mine, taste, ride) for _, _, name, _, _, mine, taste, ride in club.voices(heard)}
    tune, taste, ride = found["saw"]
    over, quiet, over_ride = found["saw under"]
    assert ride == [(0.0, 1.0)] and over_ride == ride                    # the tune as loud the second time as the first
    assert len(tune) == 8 and len(over) == 4 and all(note.pitch == 84 for note in over)
    assert quiet == pytest.approx(taste * 0.26 / 0.62)


def test_the_voices_of_a_channel_are_set_against_each_other_where_each_is_loudest(monkeypatch):
    from freerock.studio import club
    monkeypatch.setattr(club.muse, "available", lambda: False)
    heard = club.Heard()
    bar = house.BAR
    # The drop's tune at 0.6 for one bar of eight; the theme's softer voice at 0.4 all through.
    heard.notes[("lead", "lead", "saw")].append((0.0, bar, 64.0, 0.6, 0.0, 1.0))
    heard.notes[("lead", "lead", "saw")] += [(index * bar, bar, 64.0, 0.06, 0.0, 1.0) for index in range(1, 8)]
    heard.notes[("lead", "lead", "hollow")] += [(index * bar, bar, 64.0, 0.4, 0.0, 1.0) for index in range(8)]
    found = {name: taste for _, _, name, _, _, _, taste, _ in club.voices(heard)}
    assert found["saw"] == 1.0 and found["hollow"] == pytest.approx(0.4 / 0.6)


def test_a_performance_is_measured_where_it_is_played_firmest():
    from freerock.studio import sounds
    from freerock.studio.score import Note
    rate, bpm = 48000, 120.0
    seconds = np.arange(8 * rate) / rate
    tone = np.sin(2 * np.pi * 440.0 * seconds).astype(np.float32)
    audio = np.stack([tone, tone], axis=1)
    audio[4 * rate:] *= 0.5                              # its last four seconds played 6 dB softer (20 would be gated out anyway)
    notes = [Note(0.0, 8.0, 69, 0.9), Note(8.0, 8.0, 69, 0.3)]          # beats: four seconds each at 120
    firm = sounds.firm_loudness(audio, rate, notes, bpm)
    from freerock import analysis
    assert firm == pytest.approx(analysis.loudness_lufs(audio[:4 * rate], rate), abs=0.2)
    assert firm > analysis.loudness_lufs(audio, rate) + 1.0


def test_a_house_tracks_two_drops_are_both_its_moment(staged):
    folder, _ = staged
    meta, parts = studio.read_track(folder)
    two = dict(meta, sections=meta["sections"] + [dict(section) for section in meta["sections"]])
    doubled = {channel: np.concatenate([audio[:-int(meta["post_s"] * RATE)], audio]) for channel, audio in parts.items()}
    found = house.measure(two, doubled)
    once = house.measure(meta, parts)
    assert found["sections"]["moment"] == pytest.approx(once["sections"]["moment"], abs=0.5)
    assert not any("outside the moment" in problem for problem in found["problems"])


def test_a_plucked_bass_has_a_sub_under_it_on_the_same_notes_and_a_sub_bass_none(monkeypatch):
    # (2026-11-17, morning: the plucked and sawtooth basses were 6 to 8 dB heavy in their middle against the liked stems.)
    from freerock.studio import club
    monkeypatch.setattr(club.muse, "available", lambda: False)
    heard = club.Heard()
    bar = house.BAR
    for index in range(8):
        heard.notes[("bass", "bass", "pluck")].append((index * bar, bar / 4, 40.0, 0.5, 0.0, 1.0))
    lines = {name: (written, mine, taste, ride) for _, _, name, written, _, mine, taste, ride in club.voices(heard)}
    written, notes, taste, ride = lines["pluck sub"]
    plucked = lines["pluck"]
    assert written == "house sub" and [note.start for note in notes] == [note.start for note in plucked[1]]
    assert [note.pitch for note in notes] == [note.pitch for note in plucked[1]]
    assert taste == pytest.approx(plucked[2] * club.SUB_UNDER) and ride == plucked[3]
    alone = club.Heard()
    alone.notes[("bass", "bass", "sub")].append((0.0, bar, 40.0, 0.5, 0.0, 1.0))
    assert not any(name.endswith(" sub") for _, _, name, *_ in club.voices(alone))


def test_the_fm_bass_has_a_growl_beside_it_as_the_sub_has(monkeypatch):
    # (2026-11-17, morning: the FM bass was 17 to 30 dB short from 450 Hz up against the liked house stems.)
    from freerock.studio import club
    monkeypatch.setattr(club.muse, "available", lambda: False)
    heard = club.Heard()
    heard.notes[("bass", "bass", "fm")].append((0.0, house.BAR, 40.0, 0.5, 0.0, 1.0))
    heard.notes[("bass", "bass", "sub")].append((0.0, house.BAR, 40.0, 0.5, 0.0, 1.0))
    monkeypatch.setattr(club, "FM_GROWL", True)
    lines = {name: (written, cut) for _, _, name, written, cut, *_ in club.voices(heard)}
    assert lines["fm growl"] == ("house bass saw", 900.0) and "fm sub" not in lines
    # (2026-11-21, the study: House's own FM bass has the middle the factory one lacked; with the growl under it Sunlit Fields
    # II's bass stood 6.3 dB over the liked stems there.) FM_GROWL off: the growl under the sub alone, where the FM bass is
    # House's own.
    from freerock.studio import sounds
    monkeypatch.setattr(club, "FM_GROWL", False)
    lines = {name: (written, cut) for _, _, name, written, cut, *_ in club.voices(heard)}
    assert lines["sub growl"] == ("house bass saw", 900.0)
    assert ("fm growl" in lines) == (not sounds.HOUSE["house bass fm"].startswith("own:"))


def test_a_lone_sub_is_heard(monkeypatch):
    # (2026-11-22, midday: the sub playing a camp's bass alone 6.8 to 7.5 dB thin in its middle, three of three; with only the
    # harsh twin over it 3.4 on average.) Where the sub is the bass with nothing over it but its harsh twin, its growl is
    # SUB_ALONE_GROWL of the bass's level (the voice's last field but one is how far under the line it plays); beside another
    # bass, or with the switch off, 0.45 as before.
    from freerock.studio import club
    monkeypatch.setattr(club.muse, "available", lambda: False)

    def growl(*sounds: str) -> float:
        heard = club.Heard()
        for sound in sounds:
            heard.notes[("bass", "bass", sound)].append((0.0, house.BAR, 40.0, 0.5, 0.0, 1.0))
        levels = {name: level for _, _, name, _, _, _, level, _ in club.voices(heard)}
        return levels["sub growl"] / levels["sub"]
    monkeypatch.setattr(club, "SUB_ALONE_GROWL", 0.8)
    assert abs(growl("sub") - 0.8) < 1e-9
    assert abs(growl("sub", "harsh") - 0.8) < 1e-9
    assert abs(growl("sub", "pluck") - 0.45) < 1e-9
    assert abs(growl("sub", "pluck", "harsh") - 0.45) < 1e-9
    monkeypatch.setattr(club, "SUB_ALONE_GROWL", None)
    assert abs(growl("sub") - 0.45) < 1e-9


def test_a_hard_acts_kick_is_its_own_tuned_to_the_song_and_clipped(monkeypatch, tmp_path):
    # (2026-11-24: a knock and a sine, 19 dB from its loudness to its peak, under songs meant to be hard.)
    from freerock.studio import club, desk, kicks
    assert all(kicks.REACH[0] <= kicks.rest(tonic) <= kicks.REACH[1] for tonic in range(12))
    assert round(kicks.rest(4), 1) == 41.2 and round(kicks.rest(9), 1) == 55.0 and round(kicks.rest(0), 1) == 49.0 and round(kicks.rest(11), 1) == 46.2      # E, A; C's fifth, B's
    assert set(club.HARD_KICK) == {act.machine for act in club.ACTS.values() if act.drive}
    for name, _, _ in club.HARD_KICK.values():
        spec = kicks.DESIGNS[name]
        assert spec["level"][-1][1] == 0.0 and spec["length"] <= 420.0 and spec["pitch"][0][1] > 200.0
        if (desk.GEONKICK / (kicks.TEMPLATE + ".gkick")).is_file():
            plain, moved = kicks.design(name, desk.GEONKICK), kicks.design(name + "@46.2", desk.GEONKICK)
            assert abs(moved["osc1"]["freq_env"]["points"][-1][1] - kicks.freq(46.2)) < 1e-9 < abs(plain["osc1"]["freq_env"]["points"][-1][1] - kicks.freq(46.2))
    if not club.house.synth.TR8.is_dir() or not (desk.GEONKICK / (kicks.TEMPLATE + ".gkick")).is_file():
        return
    monkeypatch.setattr(club.muse, "available", lambda: False)

    def kick(drive: float) -> str:
        heard = club.Heard(hits=[("kick", "909", 0.0, 0.9, 0.0), ("clap", "909", 0.5, 0.6, 0.0)], drive=drive, rest=46.2)
        out, strokes = club.lines(heard, 1, tmp_path)
        assert len(strokes) == 1 and {line.name for line in out["drums"]} == {"house kick", "house room"}
        return "\n".join(next(line for line in out["drums"] if line.name == "house kick").effects)
    assert "freerock/clip" in kick(0.8) and "freerock/clip" not in kick(0.0)


def test_the_own_fm_bass_middle_is_cut(monkeypatch, tmp_path):
    # (2026-11-22, the day's House studies: the own FM bass 3 to 8 dB heavy at 450 to 900 Hz in all eleven takes that drew it.)
    # FM_MIDDLE cuts it an octave wide at 600 Hz at the desk, in the bass's own equaliser; off, the band is flat.
    from freerock.studio import club, sounds
    assert club.FM_MIDDLE == -4.0                      # (judged in, fm1)
    monkeypatch.setattr(club.muse, "available", lambda: False)
    heard = club.Heard()
    heard.notes[("bass", "bass", "fm")].append((0.0, house.BAR, 40.0, 0.5, 0.0, 1.0))

    def bands(value) -> str:
        monkeypatch.setattr(club, "FM_MIDDLE", value)
        out, _ = club.lines(heard, 1, tmp_path)
        line = next(line for line in out["bass"] if "fm" in line.name)
        return next(effect for effect in line.effects if "channel_eq" in effect)
    if not sounds.HOUSE["house bass fm"].startswith("own:"):
        return
    assert " 600 -4 1 " in bands(-4.0)
    assert " 600 " not in bands(None)


def test_the_own_fm_bass_can_be_held_lighter():
    # (2026-11-23, night: still 4.6 to 7.9 dB heavy over the liked stems at 450 to 900 Hz after the desk's cut.) The FM bass
    # held lighter is a design of its own, its first modulation, its feedback and the waveshaper's drive less and nothing
    # else changed, with a track template of its own: a design's settings reach a render only through its template, built
    # once (sounds.build), so a lighter FM bass is another player, as the whistle's edge is. Off, the FM bass is as designed.
    from freerock.studio import patches, sounds
    designed, lighter = patches.DESIGNS["house bass fm"], patches.DESIGNS["house bass fm light"]
    assert {key for key in designed[0] if designed[0][key] != lighter[0].get(key)} == {"a_osc1_param0", "a_osc1_param6", "a_ws_drive"}
    assert set(designed[0]) == set(lighter[0]) and designed[1] == lighter[1]
    assert (lighter[0]["a_osc1_param0"], lighter[0]["a_osc1_param6"], lighter[0]["a_ws_drive"]) == (0.25, 0.06, 1.5)
    assert sounds.FM_LIGHT is False
    if sounds.HOUSE["house bass fm"].startswith("own:"):
        assert sounds.HOUSE["house bass fm"] == "own:house bass fm"


def test_the_own_bell_can_be_given_a_body(monkeypatch, tmp_path):
    # (2026-11-22: the own bell 37 dB over the liked stems at its top and 8 thin in its middle, four takes of four.) BELL_BODY
    # gives it a body at 450 Hz and eases its top from 4 kHz in the chords' equaliser; off, its top is kept open.
    from freerock.studio import club, sounds
    monkeypatch.setattr(club.muse, "available", lambda: False)
    heard = club.Heard()
    heard.notes[("rhythm", "keys", "bell")].append((0.0, house.BAR, 64.0, 0.5, 0.0, 1.0))

    def eq(value) -> str:
        monkeypatch.setattr(club, "BELL_BODY", value)
        out, _ = club.lines(heard, 1, tmp_path)
        line = next(line for line in out["rhythm"] if "bell" in line.name)
        return next(effect for effect in line.effects if "channel_eq" in effect)
    if not sounds.HOUSE["house bell"].startswith("own:"):
        return
    assert " 450 4 1.5 " in eq((4.0, -6.0)) and " 4000 -6 " in eq((4.0, -6.0))
    assert " 450 " not in eq(None) and " 9000 -2 " in eq(None)


def test_every_house_family_has_ground_the_atlas_knows():
    # As every orchestra character does (test_studio), so that the player's preference for the ground underfoot reaches
    # House (2026-11-18: none of House's pieces had one).
    from freerock import atlas
    names = {name for name, _ in atlas.SETTINGS}
    for fam in house.PLAN:
        ground = house.ground(fam)
        assert ground and set(ground) <= names, "%s: %s" % (fam.name, ground)


def _envelope(effect: str) -> list[tuple[float, float]]:
    """The points of the one parameter envelope in an effect as the desk writes it: (seconds into the piece, value)."""
    from freerock.studio import desk
    return [(float(at) - desk.LEAD, float(value)) for at, value in
            (line.split()[1:3] for line in effect.splitlines() if line.startswith("PT "))]


def _value_at(points: list[tuple[float, float]], seconds: float) -> float:
    return float(np.interp(seconds, [at for at, _ in points], [value for _, value in points]))


def test_a_parts_filter_is_marked_on_its_sheet_open_at_a_drop_and_shut_for_the_breakdown():
    # (2026-11-18: "not enough dynamic sound", "yes you need effects over time", "the music itself should denote the
    # effects": each part's low-pass follows its own notes' brightness, as the writer opens the track.)
    from freerock.studio import club
    fam = next(each for each in house.PLAN if not each.hard and each.role not in house.CALM_ROLES)
    sheet = club.write(fam.name, 1)
    breakdown = next(section for section in sheet.form if section.get("breakdown"))
    drops = [section for section in sheet.form if section["story"] == "moment"]
    chords = [part for name, part in sheet.parts["rhythm"].items() if "lowpass" in part.effects]
    assert chords
    for part in chords:
        lane = part.effects["lowpass"]
        assert [at for at, _ in lane] == sorted(at for at, _ in lane)
        middle = lambda section: (section["first"] + section["bars"] / 2) * 4.0      # noqa: E731
        assert all(_value_at(lane, middle(drop)) >= 19000.0 for drop in drops)
        assert _value_at(lane, middle(breakdown)) < 1500.0
        assert _value_at(lane, middle(breakdown)) < _value_at(lane, middle(sheet.form[1])) < _value_at(lane, middle(drops[0]))
    # The bass loses its bottom through each rise and over its last seven beats more, and has it all back on the drop.
    bass = next(part for part in sheet.parts["bass"].values() if "highpass" in part.effects).effects["highpass"]
    for section in sheet.form:
        if section["story"] == "rise":
            end = (section["first"] + section["bars"]) * 4.0
            assert _value_at(bass, end - 0.1) > 200.0
            assert _value_at(bass, section["first"] * 4.0 + 0.5) >= 100.0
            assert _value_at(bass, end + 0.01) == 20.0
    assert _value_at(bass, (breakdown["first"] + breakdown["bars"] / 2) * 4.0) >= 150.0
    # ...and nothing of the kind in a calm piece.
    calm = next(each for each in house.PLAN if each.role in house.CALM_ROLES)
    assert not any("highpass" in part.effects for parts in club.write(calm.name, 1).parts.values() for part in parts.values())


def test_a_house_sheet_reads_back_and_is_played_as_it_was_written(tmp_path):
    from freerock.studio import club
    fam = house.PLAN[0]
    sheet = club.write(fam.name, 1)
    sheet.save(tmp_path / "sheet.json")
    again = club.heard_from(type(sheet).load(tmp_path / "sheet.json"))
    heard = club.listen(house.Take(fam, 1))
    # The sheet is the writer's music and what its first draft adds (the bass's harsh twin late in a long drop, `harsher`).
    added = {key for key in again.notes if key[2].startswith("harsh")}
    assert set(again.notes) - added == set(heard.notes)
    for key, notes in heard.notes.items():
        assert [(round(at, 6), round(length, 6), round(pitch), round(level, 6)) for at, length, pitch, level, _, _ in notes] == \
               [(round(at, 6), round(length, 6), round(pitch), round(level, 6)) for at, length, pitch, level, _, _ in again.notes[key]]
    assert sorted((name, round(at, 6), round(level, 6)) for name, _, at, level, _ in heard.hits) == \
           sorted((name, round(at, 6), round(level, 6)) for name, _, at, level, _ in again.hits)
    assert len(again.airs) == len(heard.airs)


def test_the_pump_is_deepest_at_a_drop():
    from freerock.studio import club
    assert club.PUMP["moment"] == max(club.PUMP.values()) == 1.0
    track = house.Take(house.PLAN[0], 1)
    for story, first, count in track.sections:
        assert club.story_at(track.sections, (first + count / 2) * 4.0) == story


def test_the_hats_between_the_eighths_come_only_at_a_drop():
    # (2026-11-18: "too much high hat".)
    from freerock.studio import club
    for fam in house.PLAN:
        track = house.Take(fam, 1)
        if track.pick("hats", track.palette["hats"]) == "sixteenths" and fam.kit:
            break
    else:
        pytest.skip("no family plays sixteenths in its first take")
    heard = club.listen(track)
    per_bar: dict[tuple[str, int], int] = {}
    for name, _, at, _, _ in heard.hits:
        if name == "hat":
            bar = int((at + 0.02) // house.BAR)
            story = club.story_at(track.sections, bar * 4.0)
            per_bar[(story, bar)] = per_bar.get((story, bar), 0) + 1
    assert max(count for (story, _), count in per_bar.items() if story == "moment") >= 14
    assert max(count for (story, _), count in per_bar.items() if story != "moment") <= 8


def test_a_riff_is_a_cell_of_the_chords_notes_said_again_with_a_shape_of_its_own(monkeypatch):
    # (2026-11-19, 14:15: "your house suck", "study house on the loop with the same scrutiny". The riffs had followed a slow
    # curve with a note coming again for nothing and settled on the chord's third and fifth: F F F F A A A A A.) A riff is
    # a cell of three or four notes of the chord, said over its rhythm again and again: three notes at least in its two
    # bars, none twice running, within about an octave, and over the next chord the same shape on that chord's notes.
    riffs = 0
    for fam in house.PLAN:
        made = house.Take(fam, 1)
        tune = made.tune
        if not tune.riff or made.palette.get("low"):
            continue                    # (a hard song's riff is one note hammered: the rule of its own, below)
        riffs += 1
        idea = [note for note in tune.idea]
        pitches = [made.changes.pitch(note.degree) for note in idea]
        assert len(set(pitches)) >= 3, "%s: a riff of %d notes" % (fam.name, len(set(pitches)))
        assert all(a != b for a, b in zip(pitches, pitches[1:])), "%s: a note twice running" % fam.name
        assert max(pitches) - min(pitches) <= 15, "%s: the riff leaps %d semitones" % (fam.name, max(pitches) - min(pitches))
        for note in idea:
            assert made.changes.within(tune._chord(0, note.at), note.degree), "%s: a riff note off its chord" % fam.name
        # The same shape over each chord: the order of its notes, highest to lowest, is the cell's every time round.
        def ranks(notes):
            return [sorted(set(n.degree for n in notes)).index(n.degree) for n in notes]
        by_chord: dict = {}
        for note in idea:
            by_chord.setdefault(tune._chord(0, note.at), []).append(note)
        orders = [tuple(ranks(notes)[:3]) for notes in by_chord.values() if len(notes) >= 3]
        assert len(orders) >= 1
    assert riffs >= 20
    # A hard song's: one note more than half of its strokes, three different notes at least, and never more than an octave and a step from the hammered one; its second
    # eight bars strike somewhere the first do not.
    hammered = [house.Take(fam, 1).tune for fam in house.PLAN if house.PALETTES[fam.palette].get("low") and fam.role not in house.CALM_ROLES]
    assert len(hammered) >= 20
    for tune in hammered:
        degrees = [note.degree for note in tune.idea]
        most = max(set(degrees), key=degrees.count)
        assert degrees.count(most) * 2 > len(degrees) and len(set(degrees)) >= 3 and max(abs(each - most) for each in degrees) <= 8, degrees
        assert {note.degree for note in tune.second} != {note.degree for note in tune.first}
    monkeypatch.setattr(house, "RIFF_CELLS", False)
    old = house.Take(next(fam for fam in house.PLAN if fam.name == "infernal-01"), 1).tune
    pitches = [note.degree for note in old.idea]
    assert any(a == b for a, b in zip(pitches, pitches[1:]))                    # the riff of 11-17, its notes coming again


def test_a_themes_first_half_sings_softly(monkeypatch):
    # (2026-11-19, the same study: a theme had its hook only from halfway, eight bars of tune in thirty-two.) The first half
    # of a walking piece's theme has the tune's opening phrases too, every four bars from the fifth, in the soft voice; a
    # fight's and a calm piece's themes are as they were.
    from freerock.studio import club
    def sung_bars(name, sings):
        monkeypatch.setattr(house, "THEME_SINGS", sings)
        sheet = club.write(name, 1)
        theme = next(part for part in sheet.form if part["story"] == "theme")
        lo, half = theme["first"] * 4.0, (theme["first"] + theme["bars"] // 2) * 4.0
        return {int((note.start - lo) // 4) for part in sheet.parts["lead"].values() for note in part.notes if lo <= note.start < half - 4}
    walking = next(fam for fam in house.PLAN if not fam.hard and fam.role not in house.CALM_ROLES)
    assert not sung_bars(walking.name, False)
    assert len(sung_bars(walking.name, True)) >= 4
    calm = next(fam for fam in house.PLAN if fam.role in house.CALM_ROLES)
    assert sung_bars(calm.name, True) == sung_bars(calm.name, False)


def test_a_riff_spells_its_chords_in_short_notes_and_its_echo_is_thrown_at_each_phrases_end():
    # (2026-11-18: "the lead is still lame": a house lead is a riff, cells of three sixteenths, every note on the chord.)
    from freerock.studio import club
    fam = next(each for each in house.PLAN if each.role not in house.CALM_ROLES and house.Take(each, 1).tune.riff)
    take = house.Take(fam, 1)
    idea = take.tune.idea
    assert max(note.length for note in idea) <= 7
    assert all(take.changes.within(take.changes.chord(int(note.at // 16)), note.degree) for note in idea)
    sheet = club.write(fam.name, 1)
    lead = max(sheet.parts["lead"].values(), key=lambda part: len(part.notes))
    echo = lead.effects["echo"]
    phrase = min(int(note.start // 16) for note in lead.notes)
    last = max((note for note in lead.notes if int(note.start // 16) == phrase), key=lambda note: note.start)
    assert _value_at(echo, last.start + 0.01) > 0.5 > _value_at(echo, last.start - 0.5)
    assert _value_at(echo, last.start + last.length + 1.0) == 0.0
    calm = next(each for each in house.PLAN if each.role in house.CALM_ROLES)
    assert not house.Take(calm, 1).tune.riff                  # the calm moments sing


def test_a_long_drops_bass_grows_harsher_halfway():
    # (The house study: deadmau5's "Turning Point", a second, harsher bass fading in under the same notes; the boredom
    # meter, 2026-11-18: Moonwell's bass kept one colour through 44 bars of its last drop.) The twin plays the bass's own
    # notes through the second half of every drop of 32 bars or more, stepping in over eight bars, and nowhere else.
    from freerock.studio import club
    sheet = club.write("mystic-01", 1)
    twins = [name for name in sheet.parts["bass"] if name.startswith("bass harsh")]
    assert len(twins) == 1
    twin = sheet.parts["bass"][twins[0]]
    halves = [((section["first"] + section["bars"] // 2) * 4.0, (section["first"] + section["bars"]) * 4.0)
              for section in sheet.form if section["story"] == "moment" and section["bars"] >= 32]
    assert halves and all(any(a <= note.start < b for a, b in halves) for note in twin.notes)
    bass = [note for name, part in sheet.parts["bass"].items() if name not in twins for note in part.notes]
    assert {(note.start, note.pitch) for note in twin.notes} <= {(note.start, note.pitch) for note in bass}
    a, _ = halves[-1]
    first = max(note.loud for note in twin.notes if a <= note.start < a + 16.0)
    last = max(note.loud for note in twin.notes if a + 32.0 <= note.start)
    # (House's own twin, high-passed, comes nearer the bass: club.HARSH_OWN, 2026-11-21.)
    from freerock.studio import sounds
    assert first < 0.6 * last and last <= (club.HARSH_OWN if sounds.OWN_HOUSE else club.HARSH)
    assert twin.instrument != next(part.instrument for name, part in sheet.parts["bass"].items() if name not in twins)
    # ...and none in a calm piece.
    calm = next(each for each in house.PLAN if each.role in house.CALM_ROLES)
    assert not any(name.startswith("bass harsh") for name in club.write(calm.name, 1).parts["bass"])


def test_only_the_drops_big_synths_keep_the_open_top():
    # (2026-11-18: the open top asked for the saw, "i wish i could hear more of that saw synths top end", had reached an
    # inn's sung melody too, 20 dB over the liked leads at the top.) The saw and the super open further than the band; every
    # other lead follows its notes' brightness as the band does.
    from freerock.studio import club
    seen = set()
    for name in ("ember-02", "coast-03"):
        heard = club.listen(house.Take(house.family(name), 1))
        sheet = club.write(name, 1)
        for (channel, table, sound), notes in heard.notes.items():
            if channel != "lead":
                continue
            opened = club.PLAYED[(table, sound)] in club.OPEN_TOP
            seen.add(opened)
            brightest = max(note[5] for note in notes)
            want = club.cutoff(0.35 + 0.65 * brightest if opened else brightest)
            lane = sheet.parts["lead"]["%s %s" % (table, sound)].effects.get("lowpass")
            assert (abs(max(hz for _, hz in lane) - want) < 1.0) if lane else want >= 19999.0
    assert seen == {True, False}


def test_the_chords_roll_climbs_to_the_drop_and_a_calm_piece_has_none():
    # (2026-11-18, Cold Stars I, a night piece: its bell's sixteenths into the drop, ringing into each other, stood 6 dB over
    # its own drop. The calm moments have no roll into one, by their design.) The roll's strokes are softer than the drop's
    # first chord, and a calm piece's rise ends on its ordinary chords.
    from freerock.studio import club

    def bars_of(name: str):
        take = house.Take(house.family(name), 1)
        keys = [note for (channel, _, _), notes in club.listen(take).notes.items() if channel == "rhythm" for note in notes]
        rises = [(first, count) for story, first, count in take.sections if story == "rise"]
        drops = [first for story, first, _ in take.sections if story == "moment"]
        for (first, count), drop in zip(rises, drops):
            last = [note for note in keys if (first + count - 1) * house.BAR <= note[0] < (first + count) * house.BAR]
            hit = [note for note in keys if drop * house.BAR <= note[0] < (drop + 1) * house.BAR]
            yield last, hit
    for last, hit in bars_of("coast-03"):
        assert len(last) > 2 * len(hit)                                            # a roll: sixteenths
        assert max(note[3] for note in last) < 0.7 * max(note[3] for note in hit)
    assert house.family("night-03").role in house.CALM_ROLES
    for last, hit in bars_of("night-03"):
        assert len(last) <= len(hit)                                               # no roll


def test_a_storms_rain_falls_under_the_full_band():
    # (2026-11-18, Thunderhead I: its rain at one level all the way stood over the music where the band was full.)
    take = house.Take(house.family("storm-02"), 1)
    assert take.family.role == "storm"
    story_at = lambda at: next(story for story, first, count in take.sections if first * house.BAR <= at + 1e-6 < (first + count) * house.BAR)  # noqa: E731
    rain = [(story_at(air.at), air.level) for air in take.airs() if air.kind == "rain"]
    full = [level for story, level in rain if story in ("theme", "moment")]
    gaps = [level for story, level in rain if story in ("open", "rise", "close")]
    assert full and gaps and max(full) < min(gaps)


def test_a_house_groove_changes_every_sixteen_bars():
    # (2026-11-18, the boredom meter: Breakwater's drums sounded the same for 40 bars of its theme, its maracas' sixteenths
    # under everything; "still some boring sounds in house". The hats turn and the percussion figures take turns.)
    from freerock.studio import club
    take = house.Take(house.family("coast-03"), 1)
    heard = club.listen(take)
    first, bars = next((first, count) for story, first, count in take.sections if story == "theme")

    def struck(block: int) -> set[str]:
        a, b = (first + 16 * block) * house.BAR, (first + 16 * (block + 1)) * house.BAR
        return {name for name, _, at, _, _ in heard.hits if a <= at < b}
    blocks = [struck(block) for block in range(bars // 16)]
    assert len(blocks) >= 2 and all(here != after for here, after in zip(blocks, blocks[1:]))


def test_the_hats_thin_as_the_close_begins():
    # (2026-11-19, the boredom meter: Mirage I's and III's last drop ran on into the close in one groove for 20 bars.) The
    # hats leave the drop's figure at the close's first bar: two strokes and an open hat, the first of the band to leave.
    from freerock.studio import club
    for name in ("desert-04", "coast-03"):
        take = house.Take(house.family(name), 3)
        heard = club.listen(take)
        sections = list(take.sections)
        drop = max(index for index, (story, _, _) in enumerate(sections) if story == "moment")
        story, close, count = sections[-1]
        assert story == "close" and drop == len(sections) - 2

        def hats(first: int, last: int) -> set[tuple[str, float]]:
            return {(sound, round((at / house.BAR) % 1.0, 3)) for sound, _, at, _, _ in heard.hits
                    if sound in ("hat", "open") and first * house.BAR <= at < last * house.BAR}
        before, after = hats(close - 4, close), hats(close, close + 4)
        assert before and after and before != after
        assert len(after) < len(before)


def test_the_bigger_lead_voice_plays_the_drops():
    # (2026-11-19: Hammerfall III's drops had the hollow square and its themes the seven-saw super: the lead 12 dB louder
    # outside the drop than in it.) Of the two voices a lead has, the bigger plays the drops.
    for name in ("infernal-02", "highland-01", "desert-03", "haunted-01"):
        for take_number in (1, 2, 3):
            take = house.Take(house.family(name), take_number)
            if take.tune.riff:
                continue
            names = take.palette["lead"]
            chosen = take.pick("lead", names)
            gentle = names[(names.index(chosen) + 1) % len(names)]
            drops = chosen if house.LEAD_WEIGHT.get(chosen, 1) >= house.LEAD_WEIGHT.get(gentle, 1) else gentle
            quiet = gentle if drops == chosen else chosen
            assert house.LEAD_WEIGHT.get(drops, 1) >= house.LEAD_WEIGHT.get(quiet, 1)
    assert set(house.LEAD_WEIGHT) >= {voice for palette in house.PALETTES.values() for voice in palette["lead"]}


def test_a_channel_is_ridden_down_only_where_it_would_stand_over_its_place():
    # (2026-11-19: Blades III's riff was 15 dB under its rises at the drops, the whole lead channel turned down by its rises.)
    # The lead stands at its place at the drop; a part that would stand more than 3 dB over it is ridden down to that.
    from freerock import analysis
    from freerock.studio import club
    rate = club.RATE
    t = np.arange(rate * 9) / rate
    loud = [-20.0, -8.0, -20.0]
    audio = np.concatenate([(np.sin(2 * np.pi * 660 * t[:rate * 3]) * 10 ** (db / 20)).astype(np.float32) for db in loud])[:, None].repeat(2, axis=1)
    spans = [(0, rate * 3), (rate * 3, rate * 6), (rate * 6, rate * 9)]
    have = [analysis.loudness_lufs(audio[a:b], rate) for a, b in spans]
    ceiling = have[0] + 3.0
    curve = club.ridden(audio, spans, ceiling, rate // 2)
    assert curve is not None
    after = [analysis.loudness_lufs((audio * curve[:, None])[a:b], rate) for a, b in spans]
    assert abs(after[1] - ceiling) < 0.6 and abs(after[0] - have[0]) < 0.6 and abs(after[2] - have[2]) < 0.6
    assert club.ridden(audio * np.float32(0.01), spans, ceiling, rate // 2) is None


def test_a_theme_after_a_drop_does_not_play_the_drops_groove():
    # (2026-11-19, the boredom meter: Ambush III's drums were the same 32 bars from its first drop through the theme after
    # it.) The theme that follows a drop starts on the other figure: its first bars' hats and percussion are not the drop's.
    from freerock.studio import club
    take = house.Take(house.family("battle-03"), 3)
    heard = club.listen(take)
    sections = list(take.sections)
    index = next(i for i, (story, _, _) in enumerate(sections) if story == "moment")
    story, first, count = sections[index + 1]
    assert story == "theme"
    drop_first, drop_count = sections[index][1], sections[index][2]

    def struck(a: int, b: int) -> set[tuple[str, float]]:
        return {(name, round((at / house.BAR) % 1.0, 3)) for name, _, at, _, _ in heard.hits if a * house.BAR <= at < b * house.BAR
                and name not in ("kick", "kick2", "punch", "crash")}
    assert struck(drop_first + drop_count - 4, drop_first + drop_count) != struck(first, first + 4)


def test_a_rise_keeps_the_kick_on_the_floor_until_its_build(monkeypatch):
    # (2026-11-20, the judges: House's rises still the lowest of its parts, TuneJury -0.25 with no brief over sixteen takes,
    # its themes 0.76 and its drops 1.13: a rise had no kick from its first bar.) A rise keeps the kick in every bar until its
    # build, a fight's as well, and the build into the drop goes without it; a calm rise has none, as before.
    from freerock.studio import club
    assert house.RISE_KICK
    seen = set()
    for name in ("coast-03", "battle-01", "night-03"):
        take = house.Take(house.family(name), 1)
        heard = club.listen(take)

        def kicks(a: int, b: int) -> list[float]:
            return [at for sound, _, at, _, _ in heard.hits
                    if sound in ("kick", "kick2", "punch") and a * house.BAR - 0.05 <= at < b * house.BAR - 0.05]
        for story, first, count in take.sections:
            if story != "rise":
                continue
            build = take.build_bars(count)
            if take.family.role in house.CALM_ROLES:
                assert not kicks(first, first + count), name
                seen.add("calm")
                continue
            assert take.kick, name
            for bar in range(first, first + count - build):
                assert len(kicks(bar, bar + 1)) == len(take.kick), (name, bar)
            assert not kicks(first + count - build, first + count), name
            seen.add("hard" if take.family.hard else "groove")
    assert seen == {"calm", "hard", "groove"}, seen
    # (And no closed hat ticks through a calm rise before its build: its rise stays under its moment.)
    take = house.Take(house.family("night-03"), 1)
    heard = club.listen(take)
    for story, first, count in take.sections:
        if story == "rise":
            ticks = [at for sound, _, at, _, _ in heard.hits
                     if sound == "hat" and first * house.BAR - 0.05 <= at < (first + count - take.build_bars(count)) * house.BAR - 0.05]
            assert not ticks, (first, ticks[:4])
    monkeypatch.setattr(house, "RISE_KICK", False)
    take = house.Take(house.family("coast-03"), 1)
    assert not any(take.kick_plays("rise", bar, count) for story, _, count in take.sections if story == "rise" for bar in range(count))


def test_a_long_drop_drops_out_for_a_bar_and_slams_back_in(monkeypatch):
    # (2026-11-20, the boredom meter: a long drop's last sixteen bars one groove in four takes, Mirage I, Hollow Road III, River
    # Drums III and The Old Swamp III; DROP_PEAK's louder third block moved the drums' stem 0.3 dB.) The bar before the last
    # eight of a drop of thirty-two bars or more: no kick, no bass, no chord and no note of the tune begun, no percussion; the
    # clap and the hats go on and the snare picks up into the slam, under a bar of rising air; the next bar has them back,
    # on a full crash and the drop's thud. Not in a first drop of sixteen or twenty-four bars, nor in a calm piece.
    from freerock.studio import club
    assert house.DROP_OUT
    take = house.Take(house.family("coast-03"), 1)
    heard = club.listen(take)
    drops = [(first, count) for story, first, count in take.sections if story == "moment"]
    assert drops[0][1] < 32 <= drops[-1][1]
    first, count = drops[-1]
    gap = first + count - 9

    def struck(sounds, a: int, b: int) -> list[tuple[str, float, float]]:
        return [(sound, at, loud) for sound, _, at, loud, _ in heard.hits if sound in sounds and a * house.BAR - 0.02 <= at < b * house.BAR - 0.02]

    def begun(channel: str, a: int, b: int) -> list[float]:
        return [note[0] for (each, _, _), notes in heard.notes.items() if each == channel for note in notes
                if a * house.BAR - 0.02 <= note[0] < b * house.BAR - 0.02]
    kicks = ("kick", "kick2", "punch")
    assert take.kick and not struck(kicks, gap, gap + 1)
    assert len(struck(kicks, gap - 1, gap)) == len(take.kick) and len(struck(kicks, gap + 1, gap + 2)) == len(take.kick)
    for channel in ("bass", "rhythm", "lead"):
        assert not begun(channel, gap, gap + 1), channel
        assert begun(channel, gap - 8, gap), channel
    assert begun("bass", gap + 1, gap + 2) and begun("rhythm", gap + 1, gap + 2) and begun("lead", gap + 1, gap + 9)
    assert struck(("hat", "open"), gap, gap + 1)
    assert len([hit for hit in struck(("snare",), gap, gap + 1) if (hit[1] / house.BAR) % 1.0 >= 0.74]) >= 4
    kinds = take.palette["perc"]
    figures = {sound for name in kinds for _, sound, _ in house.PERCUSSION[name]} - {"hat", "open", "clap", "snare"}
    assert not struck(figures, gap, gap + 1)
    assert [hit for hit in struck(("crash",), gap + 1, gap + 2) if hit[2] >= 0.42]
    rising = [air for air in take.airs() if air.kind == "sweep" and air.rising and abs(air.at - gap * house.BAR) < 0.01]
    assert rising and abs(rising[0].seconds - house.BAR) < 0.01
    assert [air for air in take.airs() if air.kind == "thud" and abs(air.at - (gap + 1) * house.BAR) < 0.01]
    # The first drop goes on with its kick in every bar; a calm piece's drops have no drop-out.
    first0, count0 = drops[0]
    assert all(take.kick_plays("moment", bar, count0, first0) for bar in range(count0))
    calm = house.Take(house.family("night-03"), 1)
    assert not any(calm.dropped_out(story, bar, count) for story, _, count in calm.sections for bar in range(count))
    monkeypatch.setattr(house, "DROP_OUT", False)
    assert all(take.kick_plays("moment", bar, count, first) for bar in range(count))


def test_a_fights_drums_grow_from_its_open_through_its_theme(monkeypatch):
    # (2026-11-20, the boredom meter on House's fights made again: Ambush III's drums the same 20 bars from its first bar, the
    # open playing the theme's whole groove and the clap and percussion in from the first bar.) A fight's open is the kick, the
    # backbeat and its roll, with no hats and no percussion; the hats come in with the theme, the first percussion figure at
    # the theme's ninth bar (and, as in every theme, THEME_STAGGERS, the second taking over at its twenty-fifth). Walking
    # music's drums are as they were.
    from freerock.studio import club
    assert house.FIGHT_DRUMS_GROW
    hats = ("hat", "open")                       # (the ride is a percussion figure: house.PERCUSSION)
    others = {"hat", "open", "clap", "snare", "snare2", "crash"}

    def heard_of(name: str, take_number: int):
        take = house.Take(house.family(name), take_number)
        heard = club.listen(take)
        kinds = take.palette["perc"]
        first_kind = take.pick("perc", kinds)
        figures = ({sound for _, sound, _ in house.PERCUSSION[first_kind]} - others,
                   {sound for _, sound, _ in house.PERCUSSION[kinds[(kinds.index(first_kind) + 1) % len(kinds)]]} - others)
        fills = {take.sections[1][1] + bar for bar in range(7, take.sections[1][2], 8)}       # the theme's fills, every eighth bar

        def struck(sounds, a: int, b: int) -> list[float]:
            return [at for sound, _, at, _, _ in heard.hits if sound in sounds and a * house.BAR - 0.02 <= at < b * house.BAR - 0.02
                    and int((at + 0.02) // house.BAR) not in fills]
        return take, figures, struck
    take, (one, two), struck = heard_of("battle-03", 3)
    (story, first, count), (theme, begins, _) = take.sections[0], take.sections[1]
    assert story == "open" and theme == "theme" and take.family.hard and one and two - one, (one, two)
    assert struck(("kick", "kick2", "punch"), first, first + count)
    assert not struck(hats, first, first + count) and not struck(one | two, first, first + count)
    assert struck(hats, begins, begins + 1)
    assert not struck(one | two, begins, begins + 8) and struck(one, begins + 8, begins + 16)
    assert struck(one, begins + 16, begins + 24) and not struck(two - one, begins + 16, begins + 24)
    assert struck(two - one, begins + 24, begins + 32) and not struck(one - two, begins + 24, begins + 32)
    walking, (w_one, w_two), walking_struck = heard_of("coast-03", 1)
    before = sorted(walking_struck(hats + tuple(w_one | w_two), 0, walking.bars))
    monkeypatch.setattr(house, "FIGHT_DRUMS_GROW", False)
    take, (one, two), struck = heard_of("battle-03", 3)
    assert struck(hats, first, first + count) and struck(one, begins, begins + 8)
    walking, (w_one, w_two), walking_struck = heard_of("coast-03", 1)
    assert sorted(walking_struck(hats + tuple(w_one | w_two), 0, walking.bars)) == before


def test_a_themes_percussion_turns_eight_bars_after_its_hats(monkeypatch):
    # (2026-11-20, the boredom meter: a theme's drums the same sixteen bars from where its hats turned, The Deep Road III and
    # Drowned Halls III as in the fights.) In a theme the hats turn at the seventeenth bar and the other percussion figure takes
    # over at the twenty-fifth (THEME_STAGGERS); off, both turn at the seventeenth. Not in a calm piece.
    from freerock.studio import club
    assert house.THEME_STAGGERS
    others = {"hat", "open", "clap", "snare", "snare2", "crash", "tom_high", "tom_mid", "tom_low"}

    def figures_of(name: str, take_number: int):
        take = house.Take(house.family(name), take_number)
        heard = club.listen(take)
        kinds = take.palette["perc"]
        one = {sound for _, sound, _ in house.PERCUSSION[take.pick("perc", kinds)]} - others
        two = {sound for _, sound, _ in house.PERCUSSION[kinds[(kinds.index(take.pick("perc", kinds)) + 1) % len(kinds)]]} - others
        first, count = next((first, count) for story, first, count in take.sections if story == "theme")

        def struck(sounds, a: int, b: int) -> bool:
            return any(sound in sounds and (first + a) * house.BAR - 0.02 <= at < (first + b) * house.BAR - 0.02
                       for sound, _, at, _, _ in heard.hits)
        return take, one, two - one, count, struck
    take, one, two, count, struck = figures_of("depths-03", 3)
    assert not take.family.hard and take.family.role not in house.CALM_ROLES and one and two and count >= 32, (one, two, count)
    assert struck(one, 16, 24) and not struck(two, 16, 24) and struck(two, 24, 32)
    monkeypatch.setattr(house, "THEME_STAGGERS", False)
    take, one, two, count, struck = figures_of("depths-03", 3)
    assert struck(two, 16, 24) and not struck(one - two, 16, 24)


def test_a_long_drop_opens_up_at_its_second_block(monkeypatch):
    # (2026-11-20, the boredom meter: Mill Stream II's last drop the same 39 bars from its first, The Old Swamp III's 23, the
    # turn of the hats and the figures at its second block not heard.) A drop of thirty-two bars or more has a ride on the beat
    # in every bar from its seventeenth but the drop-out's, none before; a first drop of sixteen or twenty-four bars has none
    # (LONG_DROP_GROWS). No ride where the palette's percussion is a ride already, nor in a calm piece.
    from freerock.studio import club
    assert house.LONG_DROP_GROWS
    take = house.Take(house.family("pastoral-03"), 2)
    assert "ride" not in take.palette["perc"] and take.family.role not in house.CALM_ROLES

    def rides_of():
        heard = club.listen(take)
        return lambda a, b: [at for sound, _, at, _, _ in heard.hits if sound == "ride" and a * house.BAR - 0.02 <= at < b * house.BAR - 0.02]
    rides = rides_of()
    drops = [(first, count) for story, first, count in take.sections if story == "moment"]
    first, count = drops[-1]
    assert count >= 32 and not rides(first, first + 16)
    for bar in range(first + 16, first + count):
        assert len(rides(bar, bar + 1)) == (0 if take.dropped_out("moment", bar - first, count) else 4), bar
    assert drops[0][1] < 32 and not rides(drops[0][0], drops[0][0] + drops[0][1])
    calm = house.Take(house.family("night-03"), 1)
    assert not [at for sound, _, at, _, _ in club.listen(calm).hits if sound == "ride"] or "ride" in calm.palette["perc"]
    monkeypatch.setattr(house, "LONG_DROP_GROWS", False)
    rides = rides_of()
    assert not rides(0, take.bars)


def test_a_grooves_backbeat_turns_with_its_hats(monkeypatch):
    # (2026-11-21, the boredom meter: Breakwater I's drums the same 40 bars from its theme's ninth bar, its sixteen-bar turns all
    # in the top under the same kick and backbeat.) In every second sixteen bars of a theme or a drop the backbeat is turned
    # (MIDS_TURN: a clap thickened with a snare, a clap and snare thinned to the clap), with the hats; not in a calm piece.
    from freerock.studio import club
    monkeypatch.setattr(house, "THEME_MIDS", True)        # (left off since the judges heard it: its way is kept, and held here)

    def backbeats(take, first: int, count: int, block: int) -> set[str]:
        heard = club.listen(take)
        a, b = (first + 16 * block) * house.BAR, (first + 16 * block + 16) * house.BAR
        return {sound for sound, _, at, _, _ in heard.hits if a <= at < b and sound in ("clap", "snare", "snare2")
                and round((at / house.BAR) % 1.0 * 16) in (4, 12)}
    take = house.Take(house.family("coast-03"), 1)
    first, count = next((first, count) for story, first, count in take.sections if story == "theme")
    assert count >= 32 and take.family.role not in house.CALM_ROLES
    plain, turned = backbeats(take, first, count, 0), backbeats(take, first, count, 1)
    assert plain and turned and plain != turned, (plain, turned)
    monkeypatch.setattr(house, "THEME_MIDS", False)
    assert backbeats(take, first, count, 1) == plain


@pytest.mark.parametrize("way", ["snap", "clap2", "ghost"])
def test_a_grooves_mids_can_turn_a_house_way(monkeypatch, way):
    # (2026-11-21: THEME_MIDS's snare under the clap left off, the judges hearing it as less progressive house.) Each house way
    # of turning the mids (MIDS_WAY) is heard in every second sixteen bars of a theme and not in the first: a snap or a second
    # clap on the backbeat, or a soft kick on the bar's last eighth. (Left off at 06:52, the snap level and the second clap
    # down to the judges: the ways are kept, and held here.)
    from freerock.studio import club
    assert house.MIDS_WAY == ""
    monkeypatch.setattr(house, "MIDS_WAY", way)
    # (The ghost kick where the kick has no stroke on the last eighth already: a four on the floor.)
    name = "coast-03" if way != "ghost" else next(fam.name for fam in house.PLAN if fam.role not in house.CALM_ROLES
                                                   and house.KICKS[fam.groove] and 14 not in house.KICKS[fam.groove])
    take = house.Take(house.family(name), 1)
    first, count = next((first, count) for story, first, count in take.sections if story == "theme")
    heard = club.listen(take)

    def struck(block: int) -> list[tuple[str, int]]:
        a, b = (first + 16 * block) * house.BAR, (first + 16 * block + 16) * house.BAR
        return [(sound, round((at / house.BAR) % 1.0 * 16)) for sound, _, at, _, _ in heard.hits if a <= at < b - 0.02]
    if way == "ghost":
        added = [hit for hit in struck(1) if hit[0] in ("kick", "kick2", "punch") and hit[1] == 14]
        assert added and not [hit for hit in struck(0) if hit[0] in ("kick", "kick2", "punch") and hit[1] == 14]
    else:
        assert [hit for hit in struck(1) if hit[0] == way and hit[1] in (4, 12)]
        assert not [hit for hit in struck(0) if hit[0] == way and hit[1] in (4, 12)]


def test_a_long_themes_bass_lifts_at_its_half(monkeypatch):
    # (2026-11-21, the study: Stone and Sky III's bass one colour 31 to 40 bars through its 48-bar theme.) With THEME_BASS_TURNS,
    # in the second half of a theme of 32 bars or more the bass's roots on the off-beats of two and four go up an octave (or,
    # where they are there already, its third off-beat goes to the fifth); its first half and every other part as they were.
    from freerock.studio import club

    def bass_of(name: str, number: int) -> tuple:
        take = house.Take(house.family(name), number)
        heard = club.listen(take)
        notes = sorted((round(note[0] / club.BEAT, 3), int(round(note[2]))) for (channel, _, _), each in heard.notes.items()
                       if channel == "bass" for note in each)
        return take, notes

    monkeypatch.setattr(house, "THEME_BASS_TURNS", False)
    take, before = bass_of("highland-04", 3)
    monkeypatch.setattr(house, "THEME_BASS_TURNS", True)
    _, after = bass_of("highland-04", 3)
    assert len(before) == len(after)
    long = [(first * 4.0, (first + count // 2) * 4.0, (first + count) * 4.0) for story, first, count in take.sections
            if story == "theme" and count >= 32 and not take.broken(story, first)]
    assert long
    moved = [(was, now) for was, now in zip(before, after) if was != now]
    assert moved
    for was, now in moved:
        assert was[0] == now[0] and any(half <= was[0] < end for _, half, end in long), (was, now)
        assert round((was[0] % 4.0) * 4.0) in (6, 10, 14), (was, now)       # the off-beats of two and four, or the third
    assert all(was == now for was, now in zip(before, after) if not any(half <= was[0] < end for _, half, end in long))


def test_a_calm_rise_builds_its_bass_softly(monkeypatch):
    # (2026-11-20, the render's own check: Cool of the Evening II's rise louder than its moment, its bass -15.3 dB through the
    # rise against -20.3 at the moment, the build's eighths four bars of eight with no kick to duck under.) A calm piece's bass
    # builds into its moment at half the level (CALM_BUILD_SOFT); walking music's as loud as before.
    from freerock.studio import club
    monkeypatch.setattr(house, "CALM_BUILD_SOFT", True)        # (left off since the judges heard it: its way is kept, and held here)

    def build_levels(name: str, take_number: int) -> list[float]:
        take = house.Take(house.family(name), take_number)
        heard = club.listen(take)
        out = []
        for story, first, count in take.sections:
            if story == "rise":
                a, b = (first + count - take.build_bars(count)) * house.BAR - 0.02, (first + count) * house.BAR - 0.02
                out += [note[3] for (each, _, _), notes in heard.notes.items() if each == "bass" for note in notes if a <= note[0] < b]
        return out
    calm, walking = build_levels("ember-03", 2), build_levels("coast-03", 1)
    assert calm and walking
    monkeypatch.setattr(house, "CALM_BUILD_SOFT", False)
    calm_before, walking_before = build_levels("ember-03", 2), build_levels("coast-03", 1)
    assert len(calm) == len(calm_before) and all(abs(now - 0.5 * then) < 1e-6 for now, then in zip(calm, calm_before))
    assert walking == walking_before


def test_a_rise_can_keep_the_closed_hat_alone(monkeypatch):
    # (2026-11-20: the quieter pulse to try after the judges heard RISE_PULSE: its open hats and ride fell the furthest.) With
    # RISE_CLOSED_HAT, through a rise the closed hat alone plays the eighths, softer than it plays a theme, in every bar; no
    # open hat, ride or percussion; the build is eight bars of a sixteen-bar rise.
    from freerock.studio import club
    monkeypatch.setattr(house, "RISE_PULSE", False)
    monkeypatch.setattr(house, "RISE_CLOSED_HAT", True)
    monkeypatch.setattr(house, "RISE_LONG_BUILD", True)
    take = house.Take(house.family("coast-03"), 1)
    heard = club.listen(take)
    perc = {sound for _, sound, _ in house.PERCUSSION[take.pick("perc", take.palette["perc"])]} - {"hat"}

    def struck(sounds, a: int, b: int) -> list[tuple[float, float]]:
        return [(at, loud) for sound, _, at, loud, _ in heard.hits if sound in sounds and a * house.BAR - 0.05 <= at < b * house.BAR - 0.05]
    rises = [(first, count) for story, first, count in take.sections if story == "rise"]
    assert rises
    for first, count in rises:
        assert take.build_bars(count) == (8 if count >= 16 else 4)
        for bar in range(first, first + count - 1):
            assert len(struck(("hat",), bar, bar + 1)) >= 6, bar
        assert not struck(("open", "ride"), first, first + count) and not struck(perc, first, first + count)


def test_a_rise_keeps_its_hats_going_and_builds_with_the_sweep(monkeypatch):
    # (2026-11-19, the judges: House's rises scored TuneJury 0.22 on the House brief and -0.30 on none, against 1.1 to 1.3 for
    # the grooves either side, in all thirteen takes: twelve bars of the tune over nothing, then a four-bar roll under an
    # eight-bar sweep.) Through a rise the hats go on in every bar, and the first percussion figure until the build; the kick
    # stays out (a fight's plays the first half); the roll begins as the build does, with the sweep: eight bars before the
    # drop of a sixteen-bar rise, four of a shorter one. (Left off since the judges heard it: RISE_PULSE. Its way is kept, and
    # held here, for the quieter pulse to come.)
    from freerock.studio import club
    monkeypatch.setattr(house, "RISE_PULSE", True)
    monkeypatch.setattr(house, "RISE_LONG_BUILD", True)
    monkeypatch.setattr(house, "RISE_KICK", False)
    for name in ("coast-03", "battle-01"):
        take = house.Take(house.family(name), 1)
        heard = club.listen(take)
        roll = take.pick("roll", ("snare", "clap", "crack"))
        perc = {sound for _, sound, _ in house.PERCUSSION[take.pick("perc", take.palette["perc"])]}

        def struck(sounds: tuple[str, ...] | set[str], a: int, b: int) -> list[float]:
            return [at for sound, _, at, _, _ in heard.hits if sound in sounds and a * house.BAR - 0.05 <= at < b * house.BAR - 0.05]
        rises = [(first, count) for story, first, count in take.sections if story == "rise"]
        assert rises
        for first, count in rises:
            build = take.build_bars(count)
            assert build == (8 if count >= 16 else 4)
            end = (first + count) * house.BAR
            sweeps = [air for air in take.airs() if air.kind == "sweep" and air.rising and abs(air.at + air.seconds - end) < 0.01]
            assert sweeps and abs(sweeps[0].seconds - build * house.BAR) < 0.01
            for bar in range(first, first + count):
                assert struck(("hat", "open"), bar, bar + 1), (name, bar)
            assert struck(perc, first, first + count - build) and not struck(perc, first + count - build, first + count)
            kicks = struck(("kick", "kick2", "punch"), first, first + count)
            if take.family.hard:
                assert kicks and max(kicks) < (first + count // 2) * house.BAR
            else:
                assert not kicks
            rolled = struck((roll,), first, first + count)
            assert rolled and (first + count - build) * house.BAR - 0.05 <= min(rolled) < (first + count - build + 1) * house.BAR
