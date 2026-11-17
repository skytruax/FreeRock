"""The README's listening samples: short excerpts of staged tracks, as they were rendered.

    cd app && uv run --no-sync python ../tools/readme_samples.py

Each excerpt is cut from a staged track's five channels added together, at the bars its story
gives, faded in and out, brought to one loudness, and written as MP3 under docs/samples (small
enough for the repository; the tracks themselves are FLAC and stay out of it).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile

from freerock import analysis, studio

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "var" / "studio"
OUT = ROOT / "docs" / "samples"
LOUDNESS = -16.0               # LUFS: every excerpt as loud as the others
CEILING = 0.89                 # and never over -1 dB
# (style, family/take, file, the part of the story it is found by, bars before that part begins, bars in all)
SAMPLES = (
    ("warcraft", "mystic-twilight-forest-1/1", "twilight-song.mp3", "moment", 8, 20),
    ("knight", "anywhere-storm-rider-1/1", "lightning-runner.mp3", "moment", 12, 28),
    ("house", "regal-01/1", "the-kings-road.mp3", "moment", 12, 24),
    ("warcraft", "pastoral-watchfire-1/1", "watchfire-wait.mp3", "theme", 0, 16),
)


def excerpt(style: str, name: str, story: str, before: int, bars: int) -> tuple[np.ndarray, dict]:
    """A stretch of a staged track: it begins `before` bars ahead of the first part of its story
    called `story`, and runs `bars` bars."""
    meta, parts = studio.read_track(STAGED / style / name)
    length = min(len(audio) for audio in parts.values())
    mix = sum(audio[:length] for audio in parts.values())
    at = 0
    for section in meta["sections"]:
        if section["story"] == story:
            break
        at += section["bars"]
    else:
        raise ValueError("%s/%s has no part of its story called %s" % (style, name, story))
    first = int(round((at - before) * meta["bar_frames"]))
    last = int(round((at - before + bars) * meta["bar_frames"]))
    if first < 0 or last > length:
        raise ValueError("%s/%s: bars %d to %d are outside the track" % (style, name, at - before, at - before + bars))
    cut = mix[first:last].copy()
    fade_in, fade_out = int(1.5 * studio.RATE), int(3.0 * studio.RATE)
    cut[:fade_in] *= np.linspace(0.0, 1.0, fade_in)[:, None]
    cut[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)[:, None] ** 2
    return cut, meta


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for style, name, file, story, before, bars in SAMPLES:
        audio, meta = excerpt(style, name, story, before, bars)
        gain = 10 ** ((LOUDNESS - analysis.loudness_lufs(audio, studio.RATE)) / 20.0)
        gain = min(gain, CEILING / max(analysis.peak(audio), 1e-6))
        soundfile.write(str(OUT / file), np.clip(audio * gain, -1.0, 1.0), studio.RATE, format="MP3",
                        subtype="MPEG_LAYER_III", bitrate_mode="VARIABLE", compression_level=0.1)
        print("%-22s %s, %d bars, %.0f s" % (file, meta["title"], bars, len(audio) / studio.RATE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
