"""Brings the middle of an old House song's drums up in its stem, where its claps and snares are (2026-11-25: at 900 Hz and 1.8 kHz they stood 8 to 17 dB under the liked stems' in every old song read, the hole that makes a
backbeat soft; the desk's fix for what is made after it is club.SOFT_TOPS). One wide bell, as high as the song needs and no higher than 9 dB; the drums' stem written back as it was staged (FLAC, 24 bits) and the bell noted
in the track's measurements, so that it can be taken out again by its opposite. A song whose act drives its drums is left as it is, and one that needs less than 3 dB.

    cd app && uv run --no-sync python ../tools/open_drums.py [family/take ...]      (all the style's takes; --dry says what it would do)
    ... --back family/take                                                          (the bell's opposite)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import sosfilt

from freerock.studio import club, ear

VAR = Path(__file__).resolve().parents[1] / "var"
AT, WIDTH, MOST, LEAST, SHARE = 1200.0, 0.6, 9.0, 3.0, 0.75          # the bell's middle (Hz) and Q, the most and the least it gives (dB), and how much of what is missing


def bell(gain: float, rate: int) -> np.ndarray:
    lift = 10 ** (gain / 40.0)
    turn = 2.0 * np.pi * AT / rate
    alpha = np.sin(turn) / (2.0 * WIDTH)
    whole = 1.0 + alpha / lift
    return np.array([[(1.0 + alpha * lift) / whole, -2.0 * np.cos(turn) / whole, (1.0 - alpha * lift) / whole, 1.0, -2.0 * np.cos(turn) / whole, (1.0 - alpha / lift) / whole]])


def held(audio: np.ndarray, ceiling: float, rate: int) -> np.ndarray:
    """What goes over a ceiling held under it, from five milliseconds before a peak to five after: a limiter that looks ahead. (The smallest gain any sample nearby needs, averaged over the same window, is never
    more than the sample itself needs.)"""
    near = 2 * int(0.005 * rate) + 1
    need = np.minimum(ceiling / np.maximum(np.abs(audio).max(axis=1), 1e-9), 1.0)
    return audio * uniform_filter1d(minimum_filter1d(need, near), near)[:, None]


def missing(drums: np.ndarray, rate: int) -> float:
    """How far the drums' two octaves about the bell's middle stand under the liked stems' (dB, on average)."""
    mine, want = ear.profile(drums, rate), ear.reference("", style="house", channel="drums")
    octaves = [k for k, centre in enumerate(ear.CENTRES) if 700.0 <= centre <= 2300.0]
    return float(np.mean([want.bands[k] - mine.bands[k] for k in octaves]))


def write(folder: Path, audio: np.ndarray, rate: int, meta: dict) -> None:
    for name, put in (("drums.flac", lambda path: soundfile.write(str(path), audio, rate, subtype="PCM_24", format="FLAC")),
                      ("track.json", lambda path: path.write_text(json.dumps(meta, indent=1), encoding="utf-8"))):
        fresh = folder / (name + ".new")
        put(fresh)
        os.replace(fresh, folder / name)


def open_up(folder: Path, dry: bool = False, back: bool = False) -> str:
    sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))
    act = sheet["about"].get("sounds") or ""
    if act and club.ACTS[act].drive > 0.5:
        return "its act drives its own"
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    measured = meta.setdefault("measured", {})
    had = float(measured.get("drums opened", 0.0))
    drums, rate = soundfile.read(str(folder / "drums.flac"), dtype="float32", always_2d=True)
    if back:
        if not had:
            return "never opened"
        gain = -had
    else:
        if had:
            return "already opened (%.1f dB)" % had
        gain = round(min(SHARE * missing(drums, rate), MOST), 1)
        if gain < LEAST:
            return "no thinner than %.1f dB" % (gain / SHARE)
    out = sosfilt(bell(gain, rate), drums.astype(np.float64), axis=0)
    top, was = float(np.abs(out).max()), float(np.abs(drums).max())
    if top > was:
        out = held(out, was, rate)                           # (no higher than it stood: the claps come up under the kick's own peak)
    said = "%+.1f dB at %d Hz%s" % (gain, AT, ", its peaks held %.1f dB" % (20 * np.log10(top / was)) if top > was * 1.001 else "")
    if not dry:
        if back:
            measured.pop("drums opened", None)
        else:
            measured["drums opened"] = gain
        write(folder, out.astype(np.float32), rate, meta)
    return said


def main() -> int:
    asked = [each for each in sys.argv[1:] if not each.startswith("--")]
    folders = [VAR / "studio" / "house" / name for name in asked] or sorted(path.parent for path in (VAR / "studio" / "house").glob("*/*/sheet.json"))
    for folder in folders:
        print("%-24s %s" % (folder.parent.name + "/" + folder.name, open_up(folder, dry="--dry" in sys.argv, back="--back" in sys.argv)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
