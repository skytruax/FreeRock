"""Building audio offline: joining pieces, fading layers, and the tone changes the player makes.

The player in the browser does these things live. Doing the same here, away from the browser,
gives demo clips to listen to and lets tests measure what a change does to the sound.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt


def frames(seconds: float, rate: int) -> int:
    return int(round(seconds * rate))


def equal_power_fades(length: int) -> tuple[np.ndarray, np.ndarray]:
    """(fade out, fade in) curves that keep the loudness steady while one sound replaces another."""
    position = np.linspace(0.0, np.pi / 2, length, dtype=np.float32)
    return np.cos(position)[:, None], np.sin(position)[:, None]


def join(pieces: list[np.ndarray], rate: int, fade_ms: float = 15.0) -> np.ndarray:
    """Plays `pieces` one after another, crossfading over `fade_ms` at each join.

    Each join keeps the pieces' own lengths: the fade is taken from the last few milliseconds of
    the earlier piece and the first few of the later one, laid over each other, so a join costs
    `fade_ms` of total length. That is how the player cuts between cells, a hair before the bar
    line.
    """
    overlap = frames(fade_ms / 1000.0, rate)
    if not pieces:
        raise ValueError("Nothing to join")
    out = pieces[0].astype(np.float32).copy()
    fade_out, fade_in = equal_power_fades(overlap)
    for piece in pieces[1:]:
        if len(piece) < overlap or len(out) < overlap:
            raise ValueError("A piece is shorter than the crossfade")
        out[-overlap:] = out[-overlap:] * fade_out + piece[:overlap] * fade_in
        out = np.concatenate([out, piece[overlap:].astype(np.float32)])
    return out


def sequence(source: np.ndarray, spans: list[tuple[int, int]], rate: int, fade_ms: float = 15.0,
             lead_ms: float = 10.0) -> np.ndarray:
    """Plays stretches of `source` back to back the way the player cuts between cells.

    `spans` are (start frame, end frame) pairs, normally whole bars. Every stretch keeps its full
    length, so the beat never shifts: at each cut the earlier stretch carries on a few
    milliseconds past its end (the audio that followed it in `source`) and fades out while the
    next one fades in. The cut sits `lead_ms` before the bar line, so a note struck just ahead of
    the beat is not chopped.
    """
    overlap = frames(fade_ms / 1000.0, rate)
    lead = frames(lead_ms / 1000.0, rate)
    total = sum(end - start for start, end in spans)
    out = np.zeros((total + overlap, source.shape[1]), dtype=np.float32)
    fade_out, fade_in = equal_power_fades(overlap)
    position = 0
    for index, (start, end) in enumerate(spans):
        begin, finish = start - lead, end - lead + overlap     # shifted early, plus the ring-out
        if begin < 0 or finish > len(source):
            raise ValueError("The stretch %d-%d does not fit inside the source with its fades" % (start, end))
        piece = source[begin:finish].astype(np.float32).copy()
        if index > 0:
            piece[:overlap] *= fade_in
        if index < len(spans) - 1:
            piece[-overlap:] *= fade_out
        out[position:position + len(piece)] += piece
        position += end - start
    return out[:total]


def ramp(length: int, start_gain: float, end_gain: float, at: int, over: int) -> np.ndarray:
    """A gain curve `length` frames long: `start_gain` until frame `at`, then a straight move to
    `end_gain` over `over` frames, then `end_gain`. Shaped (length, 1) to multiply stereo audio."""
    curve = np.full(length, start_gain, dtype=np.float32)
    stop = min(at + over, length)
    if at < length:
        curve[at:stop] = np.linspace(start_gain, end_gain, over, dtype=np.float32)[:stop - at]
        curve[stop:] = end_gain
    return curve[:, None]


def lowpass(audio: np.ndarray, rate: int, hz: float, order: int = 2) -> np.ndarray:
    sos = butter(order, hz / (rate / 2.0), btype="lowpass", output="sos")
    return sosfilt(sos, audio, axis=0).astype(np.float32)


def highpass(audio: np.ndarray, rate: int, hz: float, order: int = 2) -> np.ndarray:
    sos = butter(order, hz / (rate / 2.0), btype="highpass", output="sos")
    return sosfilt(sos, audio, axis=0).astype(np.float32)


def room(audio: np.ndarray, rate: int, seconds: float = 1.6, wet: float = 0.3,
         seed: int = 7) -> np.ndarray:
    """A plain echoing space: the audio plus `wet` of itself smeared through a decaying burst of
    noise. Good enough to hear what "in a cave" does; the player uses the browser's own reverb."""
    rng = np.random.default_rng(seed)
    length = frames(seconds, rate)
    decay = np.exp(-6.9 * np.arange(length) / length)          # down 60 dB by the end
    tail = np.zeros_like(audio, dtype=np.float32)
    for channel in range(audio.shape[1]):
        impulse = (rng.normal(0, 1, length) * decay).astype(np.float32)
        impulse /= np.sqrt(np.sum(impulse ** 2))
        tail[:, channel] = fftconvolve(audio[:, channel], impulse)[:len(audio)]
    return (audio + wet * tail).astype(np.float32)


def limit(audio: np.ndarray, ceiling: float = 0.98) -> np.ndarray:
    """Turns the whole clip down just enough that nothing passes `ceiling`."""
    top = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio if top <= ceiling else (audio * (ceiling / top)).astype(np.float32)
