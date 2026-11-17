"""The plain sums the measurements need.

Inside FreeRock audio is a NumPy array of float32, shaped (frames, channels), with a sample rate
carried beside it.
"""
from __future__ import annotations

import numpy as np


def to_mono(audio: np.ndarray) -> np.ndarray:
    return audio if audio.ndim == 1 else audio.mean(axis=1)


def db(value: float) -> float:
    """A linear amplitude ratio in decibels; silence is reported as -200 rather than minus infinity."""
    return 20.0 * float(np.log10(max(value, 1e-10)))


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0
