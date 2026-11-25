"""Brings the opening of songs that are staged already, and all that comes before they first arrive, up to where the desk now puts it (studio/build.py `opened`, 2026-11-24: 169 of Warcraft's 521 songs opened
under -36 LUFS, a minute of them under a game's own sounds; a slow burn's first four minutes were): the same ride on the same stems, never over what comes after, eased from part to part over three seconds.
Nothing is played again. Each stem is written beside, read back and compared before it takes the old one's place; the dB of each part are kept in track.json ("opened"), so a song is never brought up twice
and `--back` takes it away again.

    cd app && uv run --no-sync --with numba python ../tools/open_up.py warcraft/mystic-ancient-ruins-2/1 ...       what it would do
    ... open_up.py --go <takes>          does it              ... open_up.py --go --all warcraft     every staged take of a style that needs it
    ... open_up.py --back <takes>        puts them back

It waits while a bucket is being built (fresh_bucket reads the stems). A take whose stems are not FLAC is left alone."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile

from freerock import analysis, forever
from freerock.studio import build

VAR = Path(__file__).resolve().parents[1] / "var"
EASE_S = 1.5


def building() -> bool:
    return subprocess.run(["pgrep", "-f", "fresh_bucket[.]py"], stdout=subprocess.DEVNULL).returncode == 0


def read(folder: Path) -> tuple[dict, dict[str, np.ndarray], int]:
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    parts, rate = {}, build.RATE
    for channel in forever.CHANNELS:
        if (folder / (channel + ".flac")).is_file():
            parts[channel], rate = soundfile.read(str(folder / (channel + ".flac")), dtype="float32", always_2d=True)
        elif (folder / (channel + ".mp3")).is_file():
            raise ValueError("its %s is not FLAC" % channel)
    return meta, parts, rate


def edges_of(meta: dict) -> list[int]:
    out, bars = [0], 0
    for section in meta["sections"]:
        bars += section["bars"]
        out.append(int(round(bars * meta["bar_frames"])))
    return out


def ride(frames: int, edges: list[int], lifts: list[float], rate: int) -> np.ndarray:
    """Each part's dB over it, eased from part to part over three seconds."""
    curve = np.full(frames, lifts[-1], dtype=np.float32)
    for first, last, db in zip(edges, edges[1:], lifts):
        curve[first:last] = db
    for at, edge in enumerate(edges[1:-1]):
        low, high = max(edge - int(EASE_S * rate), 0), min(edge + int(EASE_S * rate), frames)
        curve[low:high] = np.linspace(lifts[at], lifts[at + 1], high - low, dtype=np.float32)
    return (10.0 ** (curve / 20.0)).astype(np.float32)


def needs(meta: dict, parts: dict[str, np.ndarray], rate: int) -> tuple[list[float], list[float]]:
    edges = edges_of(meta)
    mix = sum(parts.values())
    heard = [analysis.loudness_lufs(mix[a:b], rate) for a, b in zip(edges, edges[1:])]
    return [round(db, 1) for db in build.opened(heard, [0.0] * len(heard))], heard


def had(meta: dict) -> list[float]:
    """The dB a track has been given already, part by part (one number was its opening's alone)."""
    before, count = meta.get("opened"), len(meta["sections"])
    if before is None:
        return [0.0] * count
    return [float(each) for each in before] if isinstance(before, list) else [float(before)] + [0.0] * (count - 1)


def lay(folder: Path, meta: dict, parts: dict[str, np.ndarray], rate: int, lifts: list[float]) -> None:
    """Every stem with the ride on it, each read back before it takes its place; then what the track says of itself."""
    new, curve = {}, None
    for channel, audio in parts.items():
        curve = ride(len(audio), edges_of(meta), lifts, rate) if curve is None or len(curve) != len(audio) else curve
        out = audio * curve[:, None]
        if float(np.abs(out).max()) > 0.999:
            raise ValueError("its %s would clip" % channel)
        scratch = folder / (channel + ".opening.flac")
        soundfile.write(str(scratch), out, rate, format="FLAC", subtype="PCM_24")
        back, _ = soundfile.read(str(scratch), dtype="float32", always_2d=True)
        if back.shape != out.shape or float(np.abs(back - out).max()) > 2e-6:
            scratch.unlink()
            raise ValueError("its %s did not come back as it was written" % channel)
        new[channel] = out
    for channel in parts:
        (folder / (channel + ".opening.flac")).replace(folder / (channel + ".flac"))
    mix, edges = sum(new.values()), edges_of(meta)
    measured = meta.setdefault("measured", {})
    if isinstance(measured.get("sections"), list):
        for index in range(len(measured["sections"])):
            measured["sections"][index] = round(analysis.loudness_lufs(mix[edges[index]:edges[index + 1]], rate), 1)
    now = [round(a + b, 1) for a, b in zip(had(meta), lifts)]
    if any(abs(each) >= 0.05 for each in now):
        meta["opened"] = now
    else:
        meta.pop("opened", None)
    scratch = folder / "track.json.opening"
    scratch.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    scratch.replace(folder / "track.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Songs' openings brought up to where they are heard.")
    parser.add_argument("takes", nargs="*", help='staged takes: "warcraft/mystic-ancient-ruins-2/1"')
    parser.add_argument("--all", default="", help="every staged take of this style that needs it")
    parser.add_argument("--go", action="store_true")
    parser.add_argument("--back", action="store_true")
    parser.add_argument("--least", type=float, default=1.5, help="dB under which a song is left as it is")
    args = parser.parse_args(argv)
    takes = list(args.takes)
    if args.all:
        # (By what the track says of itself first: only those read whose opening is said to stand far under their loudest.)
        for path in sorted((VAR / "studio" / args.all).glob("*/*/track.json")):
            meta = json.loads(path.read_text(encoding="utf-8"))
            said = meta.get("measured", {}).get("sections")
            if meta.get("opened") is None and isinstance(said, list) and len(said) > 2 and max(build.opened([float(each) for each in said], [0.0] * len(said))) >= args.least:
                takes.append("/".join(path.parts[-4:-1]))
    done, wrong = 0, []
    for take in takes:
        folder = VAR / "studio" / take
        while (args.go or args.back) and building():
            time.sleep(20)
        try:
            meta, parts, rate = read(folder)
            if args.back:
                if meta.get("opened"):
                    lay(folder, meta, parts, rate, [-each for each in had(meta)])
                    print("%s  put back" % take, flush=True)
                continue
            if isinstance(meta.get("opened"), list):
                print("%s  brought up already" % take, flush=True)
                continue
            lifts, heard = needs(meta, parts, rate)
            if max(lifts) < args.least:
                continue
            if args.go:
                lay(folder, meta, parts, rate, lifts)
                done += 1
            print("%s  %-24s %s stood at %s, %s at %s" % (
                take, meta["title"][:24], "its parts", " ".join("%.0f" % each for each in heard), "stand" if args.go else "would stand", " ".join("%.0f" % (a + b) for a, b in zip(heard, lifts))), flush=True)
        except (ValueError, KeyError, OSError, soundfile.SoundFileError) as problem:
            wrong.append((take, problem))
            print("%s  LEFT ALONE: %s: %s" % (take, type(problem).__name__, problem), flush=True)
    print("%d brought up, %d left alone" % (done, len(wrong)))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
