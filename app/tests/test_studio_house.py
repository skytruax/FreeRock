"""The dance floor's writer and its synthesiser, on tracks short enough to make in a moment.

The synthesiser's inner loops are compiled by numba, which is not one of FreeRock's own
requirements, so these are skipped where it is not installed. To run them:

    uv run --no-sync --with numba pytest tests/test_studio_house.py
"""
import json

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


def test_the_chorus_and_the_echo_never_make_a_number_that_is_not_one():
    # Hours of silence after a note used to be enough: one sample in millions came out as infinity.
    out = np.zeros((6_152_727, 2), dtype=np.float32)
    synth.play(out, house.PADS["organ"], 0.0, 4.5, 60, 0.2)
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
    assert sum(fam.light for fam in about) > 0.6 * len(about), "the house is meant to be mostly light"
    assert sum(fam.light for fam in house.PLAN) > len(house.PLAN) / 2
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
                assert 29 <= pitch <= 55, "%s: the bass is out of its range at %d" % (fam.name, pitch)
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
    lines = {name: (written, cut) for _, _, name, written, cut, *_ in club.voices(heard)}
    assert lines["fm growl"] == ("house bass saw", 900.0) and "fm sub" not in lines


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
    assert set(again.notes) == set(heard.notes)
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
