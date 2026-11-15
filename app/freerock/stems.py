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
    return Layers(bed=bed, drums=drums, bass=bass, rate=rate, vocal_leak_db=leak,
                  seconds=time.perf_counter() - started, model=model_name)
