"""The boredom meter (tools/boredom.py) hears the turns an ear hears."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import soundfile
from scipy import signal

REPO = Path(__file__).resolve().parents[2]


def _meter():
    spec = importlib.util.spec_from_file_location("boredom", REPO / "tools" / "boredom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _take(folder: Path, open_bars: int, closed_bars: int, rate: int = 48000, bpm: float = 120.0) -> Path:
    """A take of drums alone: a kick on every beat, a bright clap on two and four, and a hat on every off-beat, ringing (an
    open hat) for its first bars and ticking (a closed hat) for the rest, on the same strokes at the same strength."""
    rng = np.random.default_rng(7)
    beat = rate * 60.0 / bpm
    bar = 4 * beat
    bars = open_bars + closed_bars
    total = int(bars * bar)
    out = rng.normal(0.0, 1e-4, total)
    t = np.arange(int(0.6 * rate)) / rate
    noise = rng.normal(0.0, 1.0, len(t))
    kick = 0.9 * np.sin(2 * np.pi * 55.0 * t) * np.exp(-t / 0.12)
    clap = 0.5 * noise * np.exp(-t / 0.06)
    hiss = signal.sosfilt(signal.butter(4, 7000.0, "highpass", fs=rate, output="sos"), noise)
    open_hat, closed_hat = 0.12 * hiss * np.exp(-t / 0.12), 0.12 * hiss * np.exp(-t / 0.012)

    def put(at: float, sound: np.ndarray) -> None:
        a = int(at)
        n = min(len(sound), total - a)
        out[a:a + n] += sound[:n]
    for index in range(bars):
        for k in range(4):
            put(index * bar + k * beat, kick)
            put(index * bar + (k + 0.5) * beat, open_hat if index < open_bars else closed_hat)
        for k in (1, 3):
            put(index * bar + k * beat, clap)
    folder.mkdir(parents=True)
    soundfile.write(str(folder / "drums.flac"), np.stack([out, out], axis=1).astype(np.float32), rate)
    (folder / "track.json").write_text(json.dumps({"title": folder.name, "bar_frames": bar,
                                                   "sections": [{"story": "theme", "bars": bars}]}), encoding="utf-8")
    return folder


def test_the_meter_hears_the_hats_open_and_close(tmp_path):
    # (2026-11-21: Breakwater I's theme turned from the open hats on the off-beats to the closed hats and back every eight
    # bars, but the meter read its drums the same 40 bars: under the clap the strokes stood within 1 to 3 dB of each other
    # in every sixteenth, and the sizzle between them, which an ear hears, was not measured.)
    meter = _meter()
    turned = meter.meter(_take(tmp_path / "turned", 8, 8), 1.5)["channels"]["drums"]
    assert turned["longest"][1] <= 8 and turned["colour"][1] <= 8
    steady = meter.meter(_take(tmp_path / "steady", 16, 0), 1.5)["channels"]["drums"]
    assert steady["longest"] == (0, 16) and steady["colour"] == (0, 16)
