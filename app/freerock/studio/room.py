"""One room for the whole band: the echo that is added to every part of a track.

Each part is recorded dry and alone. The same room is then added to every one of them, so that
when the player puts the parts together they stand in the same hall, and a part that is turned
down takes its echo down with it.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

RATE = 48000
_rooms: dict[tuple, np.ndarray] = {}


def impulse(seconds: float, *, bright: float = 6000.0, early: float = 0.35, seed: int = 7) -> np.ndarray:
    """The sound of a clap in a room that takes `seconds` to die away: a few early echoes off
    the walls, then a wash that fades and darkens. Stereo, the two sides different."""
    key = (seconds, bright, early, seed)
    if key in _rooms:
        return _rooms[key]
    rng = np.random.default_rng(seed)
    length = int(seconds * 1.15 * RATE)
    t = np.arange(length) / RATE
    out = np.zeros((length, 2), dtype=np.float64)
    for side in range(2):
        wash = rng.standard_normal(length) * np.exp(-6.9 * t / seconds)
        wash *= np.minimum(t / 0.012, 1.0)                               # the wash swells in after the first echoes
        # It darkens as it dies: the top goes first.
        dark = sosfilt(butter(2, bright * 0.35, "low", fs=RATE, output="sos"), wash)
        mix = np.clip(t / (seconds * 0.5), 0.0, 1.0)
        wash = sosfilt(butter(2, bright, "low", fs=RATE, output="sos"), wash) * (1.0 - mix) + dark * mix
        wash = sosfilt(butter(2, 180.0, "high", fs=RATE, output="sos"), wash)
        for _ in range(9):
            at = int(rng.uniform(0.008, 0.07) * RATE)
            wash[at] += early * rng.uniform(0.4, 1.0) * rng.choice((-1.0, 1.0)) * 12.0
        out[:, side] = wash
    out /= np.sqrt(np.sum(out ** 2) / 2.0)                                # the same energy whatever the size
    _rooms[key] = out.astype(np.float32)
    return _rooms[key]


def add(audio: np.ndarray, *, seconds: float = 2.2, wet: float = 0.22, bright: float = 6000.0) -> np.ndarray:
    """A part with the room added: as long as it came, so the last echo is cut where the part
    ends (leave room at the end for it to die away in)."""
    room = impulse(seconds, bright=bright)
    echo = np.stack([fftconvolve(audio[:, side], room[:, side])[:len(audio)] for side in range(2)], axis=1)
    return (audio + wet * echo).astype(np.float32)
