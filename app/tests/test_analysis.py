"""The measurements, checked against synthetic audio whose tempo, key and levels are known."""
import numpy as np
import pytest

from freerock import analysis
from freerock.audio import (CompressedStream, PcmStream, decode_bytes, encode_mp3, float_to_pcm16,
                            pcm16_to_float, resample)

RATE = 48000


def click_track(bpm, seconds, first=0.0, jitter_s=0.0, late=(), seed=1):
    """Short noise bursts on every beat, over a quiet hiss. `late` lists beats pushed 80 ms late."""
    rng = np.random.default_rng(seed)
    audio = rng.normal(0, 0.002, int(seconds * RATE)).astype(np.float32)
    burst = (rng.normal(0, 1, 480) * np.exp(-np.arange(480) / 80.0)).astype(np.float32) * 0.5
    period = 60.0 / bpm
    index = 0
    while True:
        moment = first + index * period + (rng.uniform(-jitter_s, jitter_s) if jitter_s else 0.0)
        if index in late:
            moment += 0.080
        start = int(round(moment * RATE))
        if start + len(burst) >= len(audio):
            break
        if start >= 0:
            audio[start:start + len(burst)] += burst
        index += 1
    return audio


def tone(midi, seconds, cents=0.0):
    """A plucked-sounding note with a few overtones."""
    t = np.arange(int(seconds * RATE)) / RATE
    freq = 440.0 * 2 ** ((midi - 69 + cents / 100.0) / 12.0)
    wave = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 6))
    return (wave * np.exp(-t * 1.5)).astype(np.float32)


def progression(chords, seconds_each=1.0, cents=0.0):
    parts = []
    for chord in chords:
        parts.append(sum(tone(midi, seconds_each, cents) for midi in chord) * 0.1)
    return np.concatenate(parts)


A_MINOR = [[45, 57, 60, 64], [50, 57, 62, 65], [40, 52, 56, 59], [45, 57, 60, 64]] * 4   # Am Dm E Am
D_DORIAN = [[38, 50, 53, 57, 60], [43, 55, 59, 62]] * 8                                   # Dm7 G


def test_finds_tempo_and_phase():
    grid = analysis.fit_grid(click_track(120.37, 60, first=0.130), RATE, nominal_bpm=120)
    assert grid.bpm == pytest.approx(120.37, abs=0.02)
    assert abs(grid.distance_to_beat_s(0.130)) < 0.006
    assert grid.jitter_ms < 3 and grid.outliers == 0 and grid.contrast > 3


def test_finds_a_tempo_some_way_from_the_one_asked_for():
    grid = analysis.fit_grid(click_track(117.6, 45), RATE, nominal_bpm=120)   # 2% slow
    assert grid.bpm == pytest.approx(117.6, abs=0.03)


def test_reports_loose_timing_and_late_beats():
    loose = analysis.fit_grid(click_track(100, 60, jitter_s=0.020), RATE, nominal_bpm=100)
    assert 4 < loose.jitter_ms < 16
    stumbles = analysis.fit_grid(click_track(100, 60, late={20, 41, 77}), RATE, nominal_bpm=100)
    assert stumbles.outliers == 3 and stumbles.jitter_ms < 3


def test_a_part_cut_from_a_track_keeps_track_times():
    whole = click_track(96, 80, first=0.0)                 # a bar is 2.5 s, so 32 s is bar 13.8...
    start = 32.5                                           # ...and 32.5 s is exactly a beat
    part = whole[int(start * RATE):int(60 * RATE)]
    grid = analysis.fit_grid(part, RATE, nominal_bpm=96, start_s=start)
    assert grid.first_beat_s >= start
    assert abs(grid.distance_to_beat_s(start)) < 0.006
    assert abs(grid.distance_to_beat_s(start + 0.3)) > 0.2      # 0.3 s after a beat is not a beat
    beats = grid.beat_times(60.0)
    assert np.allclose(np.diff(beats), 60 / grid.bpm) and beats[-1] <= 60.0


def test_too_short_is_an_error_not_a_guess():
    with pytest.raises(ValueError):
        analysis.fit_grid(np.zeros(RATE, dtype=np.float32), RATE, nominal_bpm=120)


def test_key_tonic_and_mode():
    key = analysis.estimate_key(progression(A_MINOR), RATE)
    assert key.name == "A minor" and key.agrees_with(9)
    assert not key.agrees_with(1)                           # C# is nowhere in A minor
    assert abs(key.tuning_cents) < 5


def test_modal_music_agrees_with_its_tonic():
    key = analysis.estimate_key(progression(D_DORIAN), RATE)
    assert key.agrees_with(analysis.parse_tonic("D dorian"))


def test_parent_scale():
    assert [analysis.parent_scale(n) for n in ("C major", "A minor", "D dorian", "G mixolydian", "E phrygian")] == [0] * 5
    assert analysis.parent_scale("D minor") == 5 and analysis.parent_scale("F# phrygian") == 2
    assert analysis.parent_scale("E phrygian dominant") == 0       # the second word names the mode
    with pytest.raises(ValueError):
        analysis.parent_scale("D spooky")


def test_a_piece_is_in_its_keys_family_wherever_its_weight_sits():
    dorian = analysis.estimate_key(progression(D_DORIAN), RATE)
    assert dorian.in_family("D dorian") and dorian.in_family("D minor") and dorian.in_family("A minor")
    assert dorian.in_family("G mixolydian")                    # the same seven notes
    assert not dorian.in_family("E major") and not dorian.in_family("F# minor")
    minor = analysis.estimate_key(progression(A_MINOR), RATE)   # Am Dm E: A harmonic minor
    assert minor.in_family("A minor") and minor.in_family("D minor") and not minor.in_family("B major")
    assert dorian.scale_shares().shape == (12,) and dorian.scale_shares()[0] == pytest.approx(dorian.scale_shares().max())


def test_tuning_offset_is_measured():
    sharp = analysis.estimate_key(progression(A_MINOR, cents=25), RATE)
    assert sharp.tuning_cents == pytest.approx(25, abs=5) and sharp.agrees_with(9)
    flat = analysis.estimate_key(progression(A_MINOR, cents=-30), RATE)
    assert flat.tuning_cents == pytest.approx(-30, abs=5)


def test_parse_tonic():
    assert [analysis.parse_tonic(n) for n in ("A minor", "D dorian", "F# mixolydian", "Bb major", "e minor")] \
        == [9, 2, 6, 10, 4]


def test_band_level_separates_low_from_high():
    t = np.arange(RATE * 2) / RATE
    low = (0.5 * np.sin(2 * np.pi * 80 * t)).astype(np.float32)
    assert analysis.band_level_db(low, RATE, 40, 160) == pytest.approx(-9.0, abs=0.5)
    assert analysis.band_level_db(low, RATE, 300, 3000) < -60


def test_loudness_follows_level():
    quiet = progression(A_MINOR[:4]) * 0.2
    assert analysis.loudness_lufs(quiet * 4, RATE) == pytest.approx(analysis.loudness_lufs(quiet, RATE) + 12.04, abs=0.2)


# --- audio helpers -------------------------------------------------------------------------------

def test_pcm_round_trip_and_stream_in_odd_pieces():
    rng = np.random.default_rng(3)
    audio = rng.uniform(-0.9, 0.9, (1000, 2)).astype(np.float32)
    data = float_to_pcm16(audio)
    assert np.allclose(pcm16_to_float(data, 2), audio, atol=1 / 32768)
    stream = PcmStream(channels=2)
    got = [stream.feed(data[i:i + 7]) for i in range(0, len(data), 7)]   # 7 bytes is never a whole frame
    assert stream.leftover_bytes == 0
    assert np.allclose(np.concatenate(got), audio, atol=1 / 32768)
    with pytest.raises(ValueError):
        pcm16_to_float(data[:-1], 2)


def test_mp3_decodes_whole_and_in_pieces_to_the_same_audio():
    t = np.arange(RATE * 2) / RATE
    audio = np.stack([0.4 * np.sin(2 * np.pi * 440 * t), 0.4 * np.sin(2 * np.pi * 660 * t)], axis=1).astype(np.float32)
    mp3 = encode_mp3(audio, RATE)
    whole, rate = decode_bytes(mp3)
    assert rate == RATE and whole.shape[1] == 2
    assert abs(len(whole) - len(audio)) < 3000                 # MP3 pads the ends
    stream = CompressedStream("mp3")
    pieces = [stream.feed(mp3[i:i + 1000]) for i in range(0, len(mp3), 1000)] + [stream.finish()]
    joined = np.concatenate([p for p in pieces if len(p)])
    assert stream.sample_rate == RATE
    # Decoded in pieces, the encoder's own lead-in and tail stay in (an information frame plus
    # padding, about three MP3 frames); decoded as a file they are trimmed.
    assert 0 <= len(joined) - len(whole) <= 1152 * 3
    middle = slice(RATE // 2, RATE)
    assert np.sqrt(np.mean(whole[middle] ** 2)) == pytest.approx(0.4 / np.sqrt(2), rel=0.1)


def test_resample_keeps_length_and_pitch():
    audio = click_track(120, 4)
    down = resample(audio, 48000, 44100)
    assert len(down) == pytest.approx(len(audio) * 44100 / 48000, abs=2)
    assert resample(audio, 48000, 48000) is audio
