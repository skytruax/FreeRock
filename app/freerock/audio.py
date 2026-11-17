"""Audio in and out: writing music to keep, and the plain sums the measurements need.

Inside FreeRock audio is a NumPy array of float32, shaped (frames, channels), with a sample rate
carried beside it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def to_mono(audio: np.ndarray) -> np.ndarray:
    return audio if audio.ndim == 1 else audio.mean(axis=1)


# Music that is kept (the studio's tracks, the buckets' parts, the listening pages) is kept as MP3 at the encoder's
# best variable rate: about a quarter of the room of FLAC for a full part, much less for a sparse one ("save stems to
# mp3 so theres more room", "do great quality", 2026-11-16). This machine's encoder and decoder give back exactly as
# many samples as went in, each where it was (tried that night: a click came back on the same sample), so the parts
# of a piece stay in step and its stretches join without a seam.
def write_mp3(path: Path, audio: np.ndarray, rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(audio, -1.0, 1.0), rate, format="MP3", subtype="MPEG_LAYER_III", compression_level=0.0,
             bitrate_mode="VARIABLE")


def db(value: float) -> float:
    """A linear amplitude ratio in decibels; silence is reported as -200 rather than minus infinity."""
    return 20.0 * float(np.log10(max(value, 1e-10)))


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0
