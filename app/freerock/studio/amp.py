"""A guitar amplifier: what turns a clean sampled guitar into a rhythm guitar.

A power chord sounds the way it does because the two notes go through one overdriven amplifier
together and beat against each other in it. Samples of single distorted notes laid side by side
do not do that, so the studio plays its guitars clean and puts the whole part through this:
tightened lows, valves driven hard, a speaker cabinet that passes nothing above five thousand
cycles, and for a rhythm part the same playing on both sides a hair apart, as two guitarists.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

RATE = 48000


def _peak(signal: np.ndarray, hz: float, db: float, q: float) -> np.ndarray:
    """A hump (or a dip) in the response around one frequency."""
    a = 10 ** (db / 40.0)
    w = 2 * np.pi * hz / RATE
    alpha = np.sin(w) / (2 * q)
    b = np.array([1 + alpha * a, -2 * np.cos(w), 1 - alpha * a])
    den = np.array([1 + alpha / a, -2 * np.cos(w), 1 - alpha / a])
    return sosfilt(np.array([[b[0] / den[0], b[1] / den[0], b[2] / den[0], 1.0, den[1] / den[0], den[2] / den[0]]]), signal)


def drive(audio: np.ndarray, *, gain: float = 9.0, top: float = 4800.0, wide: float = 0.013, bark: float = 5.0,
          bite: float = 4.0) -> np.ndarray:
    """A part played through the amplifier. `gain` is how hard the valves are driven, `top` where
    the cabinet stops, `wide` how far apart in seconds the two sides are (0 for one guitar in
    the middle), `bark` the push in the middle before the valves and `bite` the edge the
    cabinet adds, both in decibels. What comes back is as long as what went in; whoever asked
    sets its level."""
    dry = audio.mean(axis=1).astype(np.float64)
    loud = float(np.percentile(np.abs(dry), 99.7))
    if loud < 1e-6:
        return np.zeros_like(audio, dtype=np.float32)
    tight = sosfilt(butter(2, 130.0, "high", fs=RATE, output="sos"), dry / loud)
    tight = _peak(tight, 900.0, bark, 0.8)                         # the push in the middle that makes it bark
    # The valves, at four times the rate so that what they add does not fold back as hash.
    over = resample_poly(tight, 4, 1)
    over = np.tanh(gain * over + 0.12) - np.tanh(0.12)             # a little lopsided, as valves are
    over = np.tanh(1.6 * over)
    driven = resample_poly(over, 1, 4)[:len(dry)]
    if len(driven) < len(dry):
        driven = np.concatenate([driven, np.zeros(len(dry) - len(driven))])

    def cabinet(signal: np.ndarray, stop: float) -> np.ndarray:
        signal = sosfilt(butter(2, 85.0, "high", fs=RATE, output="sos"), signal)
        signal = sosfilt(butter(4, stop, "low", fs=RATE, output="sos"), signal)
        return _peak(_peak(signal, 2600.0, bite, 1.4), 420.0, -3.0, 1.0)

    one = cabinet(driven, top)
    if wide > 0:
        # Two guitars: mostly one on each side, each a little in the other, so that the pair
        # is wide without falling apart when the two sides are heard as one.
        late = int(wide * RATE)
        other = cabinet(np.concatenate([np.zeros(late), driven[:-late]]), top * 0.88) * 0.96
        left, right = 0.82 * one + 0.4 * other, 0.4 * one + 0.82 * other
    else:
        left = right = one
    return np.stack([left, right], axis=1).astype(np.float32)


def echo(audio: np.ndarray, seconds: float, *, again: float = 0.35, mix: float = 0.28) -> np.ndarray:
    """A lead guitar's echo: the part again `seconds` later and quieter, and again after that."""
    out = audio.astype(np.float32).copy()
    step = int(seconds * RATE)
    if step <= 0:
        return out
    level, shift = mix, step
    while level > 0.02 and shift < len(audio):
        out[shift:] += level * audio[:-shift]
        level *= again
        shift += step
    return out
