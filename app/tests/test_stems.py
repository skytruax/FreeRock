"""Layer splitting on a small synthetic band. Runs the real separator, so it takes a few seconds
and, the very first time, downloads the separator's model."""
import numpy as np
import pytest

from freerock import analysis
from freerock.stems import split

RATE = 48000


def band(seconds=8.0, seed=5):
    """A stand-in band: a kick and snare, a bass line under 120 Hz, and a chord above it."""
    rng = np.random.default_rng(seed)
    frames = int(seconds * RATE)
    t = np.arange(frames) / RATE
    drums = np.zeros(frames, dtype=np.float32)
    for beat in np.arange(0, seconds, 0.5):
        start = int(beat * RATE)
        length = min(4800, frames - start)
        decay = np.exp(-np.arange(length) / 900.0)
        if int(round(beat / 0.5)) % 2 == 0:
            hit = np.sin(2 * np.pi * (55 + 60 * decay) * np.arange(length) / RATE) * decay   # kick
        else:
            hit = rng.normal(0, 0.6, length) * decay                                        # snare
        drums[start:start + length] += (0.6 * hit).astype(np.float32)
    notes = [55.0, 55.0, 65.4, 73.4]
    bass = np.zeros(frames, dtype=np.float32)
    for index, moment in enumerate(np.arange(0, seconds, 0.25)):
        start = int(moment * RATE)
        length = min(int(0.24 * RATE), frames - start)
        freq = notes[(index // 4) % len(notes)]
        n = np.arange(length) / RATE
        bass[start:start + length] += (0.35 * (np.sin(2 * np.pi * freq * n) + 0.3 * np.sin(4 * np.pi * freq * n))
                                       * np.exp(-n * 4)).astype(np.float32)
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 261.6, 329.6)).astype(np.float32) * 0.08
    mono = drums + bass + chord
    return np.stack([mono, mono * 0.9], axis=1).astype(np.float32)


@pytest.fixture(scope="module")
def layers_and_mix():
    mix = band()
    return split(mix, RATE), mix


def test_layers_add_up_exactly_to_the_original(layers_and_mix):
    layers, mix = layers_and_mix
    assert layers.bed.shape == layers.drums.shape == layers.bass.shape == mix.shape
    assert layers.rate == RATE
    assert np.max(np.abs(layers.mix() - mix)) < 1e-6
    assert all(np.isfinite(part).all() for part in (layers.bed, layers.drums, layers.bass))


def test_the_bass_layer_carries_the_low_end(layers_and_mix):
    layers, mix = layers_and_mix
    with_bass = analysis.band_level_db(mix, RATE, 40, 160)
    without_bass = analysis.band_level_db(layers.bed + layers.drums, RATE, 40, 160)
    assert layers.seconds > 0 and np.isfinite(layers.vocal_leak_db)
    # On a real band the bar is 6 dB; this synthetic one only has to show the split does something.
    assert with_bass - without_bass > 1.5


def test_words_are_told_from_a_whistle():
    """The part of the vocals layer where sung words have their consonants: a pure high tone has
    nothing there, a voice-like sound with hiss on top has plenty."""
    from freerock.stems import words_level_db

    rate = 44100
    t = np.arange(rate * 4) / rate
    mix = np.stack([0.3 * np.sin(2 * np.pi * 220 * t)] * 2, axis=1).astype(np.float32)
    whistle = np.stack([0.1 * np.sin(2 * np.pi * 1475 * t)] * 2, axis=1).astype(np.float32)
    rng = np.random.default_rng(1)
    voice = 0.1 * np.sin(2 * np.pi * 180 * t) + 0.03 * np.sin(2 * np.pi * 3100 * t) + 0.02 * rng.normal(size=t.size)
    voice = np.stack([voice, voice], axis=1).astype(np.float32)
    assert words_level_db(whistle, mix, rate) < -80
    assert -25 < words_level_db(voice, mix, rate) < -10
    assert words_level_db(np.zeros_like(mix), mix, rate) < -100
