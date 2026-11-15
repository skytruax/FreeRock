"""Splitting a track into three layers on this machine: drums, bass, and everything else.

The split is done by Demucs, a free separator that runs locally, so it costs no ElevenLabs
minutes. The third layer (the "bed") is not taken from the separator. It is defined as the
original minus the drums and the bass, so the three layers always add up exactly to what
ElevenLabs produced, whatever the separator got wrong. And because all three come from one
performance, they are locked together to the sample.

The separator also reports a vocals layer. FreeRock asks for instrumental music, so how much ends
up there is a check on the track, not something that is played.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from scipy import signal

from .audio import db, resample, rms, to_stereo

DEFAULT_MODEL = "htdemucs"


@dataclass
class Layers:
    bed: np.ndarray       # everything that is not drums or bass
    drums: np.ndarray
    bass: np.ndarray
    rate: int
    vocal_leak_db: float  # level of what the separator took for singing, relative to the whole mix
    seconds: float        # how long the split took
    model: str
    # The same, counting only the part of it between 2.5 and 8 kHz, where the consonants of sung
    # words are. A whistle or a flute, which the separator also takes for a voice, has next to
    # nothing there.
    vocal_words_db: float = -120.0

    def mix(self) -> np.ndarray:
        return self.bed + self.drums + self.bass


@lru_cache(maxsize=2)
def _load(model_name: str):
    from demucs.pretrained import get_model  # imported late: PyTorch takes a moment to load

    model = get_model(model_name)
    model.cpu()
    model.eval()
    return model


def _fit_length(audio: np.ndarray, frames: int) -> np.ndarray:
    """Resampling can leave a layer a sample or two long or short; make it match the original."""
    if len(audio) == frames:
        return audio
    if len(audio) > frames:
        return audio[:frames]
    return np.concatenate([audio, np.zeros((frames - len(audio), audio.shape[1]), dtype=audio.dtype)])


WORDS_BAND_HZ = (2500.0, 8000.0)


def words_level_db(vocals: np.ndarray, mix: np.ndarray, rate: int) -> float:
    """Level of the part of `vocals` where sung words have their consonants and their edge,
    relative to the whole of `mix`. Measured on the spectrum, not with a filter, so that a loud
    whistle just below the band does not spill into it."""
    mono = np.asarray(vocals, dtype=np.float64)
    mono = mono.mean(axis=1) if mono.ndim == 2 else mono
    if len(mono) < 8192:
        raise ValueError("too short to measure: %d frames" % len(mono))
    freqs, power = signal.welch(mono, fs=rate, nperseg=8192, window="hann")
    inside = (freqs >= WORDS_BAND_HZ[0]) & (freqs <= WORDS_BAND_HZ[1])
    in_band = float(np.sum(power[inside]) * (freqs[1] - freqs[0]))   # mean square of that part
    whole = np.asarray(mix, dtype=np.float64)
    whole = whole.mean(axis=1) if whole.ndim == 2 else whole
    return float(db(np.sqrt(in_band) / (np.sqrt(np.mean(whole ** 2)) + 1e-12)))


def split(mix: np.ndarray, rate: int, model_name: str = DEFAULT_MODEL) -> Layers:
    """Splits `mix` (frames, channels) into bed, drums and bass at the same rate and length."""
    import torch
    from demucs.apply import apply_model

    started = time.perf_counter()
    model = _load(model_name)
    stereo = to_stereo(np.asarray(mix, dtype=np.float32))
    at_model_rate = resample(stereo, rate, model.samplerate)

    wave = torch.from_numpy(np.ascontiguousarray(at_model_rate.T))
    # Demucs expects audio scaled to a standard spread; the scaling is undone afterwards.
    reference = wave.mean(0)
    centre, spread = reference.mean(), reference.std() + 1e-8
    with torch.no_grad():
        separated = apply_model(model, ((wave - centre) / spread)[None], device="cpu",
                                shifts=1, split=True, overlap=0.25, progress=False)[0]
    separated = separated * spread + centre

    by_name = {name: separated[index].numpy().T for index, name in enumerate(model.sources)}
    missing = {"drums", "bass", "vocals"} - set(by_name)
    if missing:
        raise RuntimeError("The separator %s has no %s layer" % (model_name, ", ".join(sorted(missing))))

    frames = len(stereo)
    drums = _fit_length(resample(by_name["drums"], model.samplerate, rate), frames).astype(np.float32)
    bass = _fit_length(resample(by_name["bass"], model.samplerate, rate), frames).astype(np.float32)
    bed = (stereo - drums - bass).astype(np.float32)
    leak = db(rms(by_name["vocals"]) / (rms(at_model_rate) + 1e-12))
    words = words_level_db(by_name["vocals"], at_model_rate, model.samplerate)
    return Layers(bed=bed, drums=drums, bass=bass, rate=rate, vocal_leak_db=leak,
                  seconds=time.perf_counter() - started, model=model_name, vocal_words_db=words)
