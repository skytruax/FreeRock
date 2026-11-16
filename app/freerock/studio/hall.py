"""The hall the orchestra sits in: impulse responses for REAPER's convolution reverb (ReaVerb).

A convolution reverb plays every sound through the recorded answer of a room to a single clap.
The halls here are not recordings of any real room: they are made the way a concert hall
behaves. A handful of early reflections from the walls in the first tenth of a second, then a
dense wash that dies away evenly, the high notes sooner than the low ones as the air and the
seats take them (a good hall rings about two seconds in the middle of the range, a little
longer in the bass, half as long at the top), and different in each ear so that it is wide.

    cd app && uv run --no-sync python -m freerock.studio.hall        writes the halls to var/reaper/halls
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile
from scipy import signal

RATE = 48000
HALLS = Path(__file__).resolve().parents[3] / "var" / "reaper" / "halls"
# How long each band rings, as a part of the middle's time: (centre in Hz, part).
BANDS = ((63, 1.2), (125, 1.18), (250, 1.1), (500, 1.04), (1000, 1.0), (2000, 0.9), (4000, 0.72), (8000, 0.5), (14000, 0.33))
SIZES = (1.4, 1.8, 2.2, 2.6, 3.0, 3.6, 4.4)       # seconds the middle of the range rings: a chamber to a cathedral


def impulse(seconds: float, *, seed: int = 7, early: float = 1.0) -> np.ndarray:
    """A hall that rings `seconds` in the middle of its range: stereo, as loud coming out as going in."""
    rng = np.random.default_rng(seed + int(seconds * 100))
    length = int(RATE * seconds * 1.6)
    time = np.arange(length) / RATE
    out = np.zeros((length, 2))
    # The wash: noise in bands an octave wide, each dying away at its own rate.
    edges = [0.0] + [np.sqrt(BANDS[index][0] * BANDS[index + 1][0]) for index in range(len(BANDS) - 1)] + [RATE / 2]
    for side in range(2):
        noise = rng.standard_normal(length)
        spectrum = np.fft.rfft(noise)
        hz = np.fft.rfftfreq(length, 1.0 / RATE)
        for index, (_, part) in enumerate(BANDS):
            window = np.zeros(len(hz))
            low, high = edges[index], edges[index + 1]
            window[(hz >= low) & (hz < high)] = 1.0
            # Soft edges between the bands, so no band can be heard starting or stopping.
            window = signal.convolve(window, np.hanning(max(int(len(hz) * 0.004), 3)), mode="same")
            band = np.fft.irfft(spectrum * window / max(window.max(), 1e-9), length)
            out[:, side] += band * np.exp(-6.908 * time / (seconds * part))
    # A hall takes a moment to fill: the wash swells in over the first twentieth of a second.
    swell = int(0.05 * RATE)
    out[:swell] *= (np.linspace(0.0, 1.0, swell) ** 1.5)[:, None]
    out /= np.abs(out).max()
    # The first reflections: single echoes off the walls, coming from one side and then the other.
    taps = np.zeros((length, 2))
    size = 0.012 + 0.016 * seconds                  # a bigger hall's walls are further away
    count = 14
    for index in range(count):
        at = size * (1.0 + 4.5 * (index / count) ** 1.3) + rng.uniform(-0.002, 0.002)
        frame = int(at * RATE)
        loud = 0.8 * (0.86 ** index) * rng.choice((-1.0, 1.0))
        side = index % 2
        lean = rng.uniform(0.15, 0.6)
        taps[frame, side] += loud
        taps[frame + int(rng.uniform(8, 28)), 1 - side] += loud * lean
    soften = signal.firwin(31, 7000, fs=RATE)
    for side in range(2):
        taps[:, side] = signal.lfilter(soften, 1.0, taps[:, side])
    whole = out * 0.55 + taps * early
    # The last twentieth fades to nothing, so that the end is not a click.
    fade = int(0.05 * length)
    whole[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    # As much comes out of the hall as goes in: a sound sent to it at full strength comes back
    # about as loud as it went, so how much hall there is is set by how much is sent.
    whole /= np.sqrt(np.square(whole).sum(axis=0).mean())
    return whole.astype(np.float32)


def path(seconds: float) -> Path:
    """The file of the hall that rings nearest to `seconds`."""
    nearest = min(SIZES, key=lambda size: abs(size - seconds))
    return HALLS / ("hall %.1f s.wav" % nearest)


def write() -> list[Path]:
    HALLS.mkdir(parents=True, exist_ok=True)
    out = []
    for size in SIZES:
        soundfile.write(str(path(size)), impulse(size), RATE, subtype="PCM_24")
        out.append(path(size))
    return out


def rings(audio: np.ndarray, rate: int = RATE) -> float:
    """How long a sound takes to die away by sixty decibels (measured over its fall from five
    to thirty-five decibels down, as halls are)."""
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    energy = np.cumsum(mono[::-1].astype(np.float64) ** 2)[::-1]
    curve = 10 * np.log10(energy / energy[0] + 1e-30)
    first, last = int(np.argmax(curve < -5.0)), int(np.argmax(curve < -35.0))
    return 2.0 * (last - first) / rate


if __name__ == "__main__":
    for made in write():
        audio, rate = soundfile.read(str(made), always_2d=True)
        print("%s: %.2f s long, rings %.2f s" % (made.name, len(audio) / rate, rings(audio, rate)))
    sys.exit(0)
