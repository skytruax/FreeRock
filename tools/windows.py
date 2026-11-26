"""Cuts the two windows of a take the judges are given: its first theme's last bars and its last moment's first bars.

(The judges that listen take twenty minutes over a whole song here and four over a window, so a round is read by windows; the
gate, tools/gate.py, reads a new song's windows against the same windows of the liked library. Until 2026-11-26 this was a
script in a scratch folder that a reboot clears.)

    cd app && uv run --no-sync python ../tools/windows.py <take's folder> <root> [--bars 32]

Writes <root>/theme/<style>/<family>/<take> and <root>/summit/<style>/<family>/<take>, each a take's folder cut down to the
window (its recordings and a track.json that says so), and prints the two folders: what tools/judges.py --folder is given.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import soundfile

WINDOWS = ("theme", "summit")


def span(sections: list[dict], which: str, bars: int) -> tuple[str, int, int]:
    """Where a window lies: the story it is of, its first bar and how many bars. The theme's is the first theme's last `bars`
    bars (the tune as the song has settled into it); the summit's is the last moment's first `bars`."""
    at, edges = 0, []
    for section in sections:
        edges.append((section["story"], at, int(section["bars"])))
        at += int(section["bars"])
    if which == "theme":
        found = [each for each in edges if each[0] == "theme"]
        if not found:
            raise ValueError("The take has no theme: %s" % [story for story, _, _ in edges])
        story, first, count = found[0]
        return story, first + max(count - bars, 0), min(bars, count)
    if which == "summit":
        found = [each for each in edges if each[0] == "moment"]
        if not found:
            raise ValueError("The take has no moment: %s" % [story for story, _, _ in edges])
        story, first, count = found[-1]
        return story, first, min(bars, count)
    raise ValueError("A window is one of %s, not %r" % (", ".join(WINDOWS), which))


def cut(source: Path, root: Path, which: str, bars: int = 32) -> Path:
    """Cuts one window of the take in `source` into <root>/<which>/<style>/<family>/<take>; returns that folder."""
    source = Path(source)
    meta = json.loads((source / "track.json").read_text(encoding="utf-8"))
    story, start, count = span(meta["sections"], which, bars)
    out = Path(root) / which / source.parent.parent.name / source.parent.name / source.name
    out.mkdir(parents=True, exist_ok=True)
    first, last = int(round(start * meta["bar_frames"])), int(round((start + count) * meta["bar_frames"]))
    recordings = sorted(source.glob("*.flac"))
    if not recordings:
        raise ValueError("No recordings in %s" % source)
    for recording in recordings:
        audio, rate = soundfile.read(str(recording), dtype="float32", always_2d=True, start=first, stop=last)
        soundfile.write(str(out / recording.name), audio, rate, subtype="PCM_24")
    meta["sections"] = [dict(meta["sections"][0], story="open", bars=0), dict(meta["sections"][0], story=story, bars=count)]
    (out / "track.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cut a take's two windows for the judges.")
    parser.add_argument("take", help="the take's folder (var/studio/knight/family/1)")
    parser.add_argument("root", help="where the windows go")
    parser.add_argument("--bars", type=int, default=32)
    args = parser.parse_args(argv)
    for which in WINDOWS:
        print(cut(Path(args.take), Path(args.root), which, args.bars))
    return 0


if __name__ == "__main__":
    sys.exit(main())
