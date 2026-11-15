"""Shared by the experiment scripts: where results go, and a few helpers.

Run an experiment from the app folder, so it uses FreeRock's environment:

    cd app && uv run --no-sync python ../tools/spikes/s0_format.py

Every paid call goes through freerock.eleven.Gateway, so the experiments count against the same
allowance and appear in the same ledger as everything else.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from freerock import analysis
from freerock.audio import encode_mp3, write_flac
from freerock.eleven import Gateway
from freerock.settings import VAR_DIR, Settings

OUT = VAR_DIR / "spikes"

# The knight-rock recipe as style words. ElevenLabs rejects band names, so the sound is described.
ROCK = [
    "instrumental",
    "riff-driven late-1970s arena hard rock",
    "two crunchy overdriven rhythm guitars playing open-chord riffs with space between the hits",
    "prominent driving eighth-note bass guitar on the root",
    "plain hard-hitting live drum kit with a heavy backbeat",
    "raw dry live-room sound",
]
KNIGHT = ["medieval colour: lute and hurdy-gurdy"]
NEVER = ["vocals", "singing", "choir", "spoken word", "synthesizer", "electronic drums",
         "orchestra", "tempo changes", "swing feel", "fade out"]


def gateway() -> Gateway:
    return Gateway(Settings())


def save(name: str, audio: np.ndarray, rate: int) -> dict[str, str]:
    """Stores a clip losslessly, and as an MP3 the listening page can play. Returns both paths
    relative to the experiments folder."""
    OUT.mkdir(parents=True, exist_ok=True)
    write_flac(OUT / (name + ".flac"), audio, rate)
    (OUT / (name + ".mp3")).write_bytes(encode_mp3(audio, rate))
    return {"flac": name + ".flac", "mp3": name + ".mp3"}


def write_report(name: str, report: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"experiment": name, "written": time.strftime("%Y-%m-%d %H:%M:%S"), **report}
    path = OUT / (name + ".json")
    path.write_text(json.dumps(report, indent=2, default=_plain) + "\n", encoding="utf-8")
    return path


def read_report(name: str) -> dict[str, Any]:
    return json.loads((OUT / (name + ".json")).read_text(encoding="utf-8"))


def _plain(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError("Cannot write %r to a report" % type(value))


def describe(audio: np.ndarray, rate: int, bpm: float | None = None,
             tonic: str | None = None) -> dict[str, Any]:
    """The standard measurements of a clip, as a dictionary ready for a report."""
    found: dict[str, Any] = {
        "seconds": round(len(audio) / rate, 3),
        "peak": round(analysis.peak(audio), 4),
        "loudness_lufs": round(analysis.loudness_lufs(audio, rate), 2) if len(audio) >= rate // 2 else None,
    }
    if bpm:
        grid = analysis.fit_grid(audio, rate, bpm)
        found["tempo"] = {
            "asked_bpm": bpm, "measured_bpm": round(grid.bpm, 3),
            "off_percent": round((grid.bpm / bpm - 1) * 100, 3),
            "first_beat_s": round(grid.first_beat_s, 4), "jitter_ms": round(grid.jitter_ms, 2),
            "outliers": grid.outliers, "beats_checked": grid.beats_checked,
            "contrast": round(grid.contrast, 2),
        }
    if tonic:
        key = analysis.estimate_key(audio, rate)
        found["key"] = {
            "asked": tonic, "heard_as": key.name, "agrees": key.agrees_with(analysis.parse_tonic(tonic)),
            "tuning_cents": round(key.tuning_cents, 1),
            "rank_of_asked_tonic": key.rank_of(analysis.parse_tonic(tonic)),
        }
    return found
