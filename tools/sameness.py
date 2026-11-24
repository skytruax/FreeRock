"""How alike a style's songs sound (2026-11-23: "all the knight rock songs sound like the same song", "too much of the
same instrument sounds"): a number to bring down, and the pairs of songs that are nearest to each other.

Each song is heard by LAION-CLAP-Music (one of the judges' two encoders, tools/judges.py) in three places, ten seconds from the middle of its first theme, of
its valley and of its summit, its five stems summed and set to one loudness: what plays and how, much more than which notes. Two songs are as alike as the
cosine of the angle between what it makes of them, part for part. A family is one song: its first staged take stands for it (a take in another band's sounds,
orchestra.BANDS, is a song of its own). What was heard is kept (var/passes/sameness-<style>.json) and only heard again when the take is made again.

    "var/tools/judges/.venv/bin/python" tools/sameness.py knight                  how alike: all pairs, each song's nearest, the nearest pairs
    ... knight --new 24                                                           and what was staged in the last 24 hours against the rest
    ... warcraft house knight --pairs 10 --threads 2                              (to hold the styles side by side)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile

from judges import CHANNELS, JUDGES, VAR, level

WINDOW_S = 10.0
PARTS = ("first", "valley", "summit")
CLAP_RATE = 48000


def window(folder: Path, meta: dict, names: list[str], part: str) -> np.ndarray | None:
    """Ten seconds of the whole mix from the middle of a part, mono at CLAP's rate; None where the song has no such part."""
    if part not in names:
        return None
    at = sum(section["bars"] for section in meta["sections"][:names.index(part)])
    bars = meta["sections"][names.index(part)]["bars"]
    bar = float(meta["bar_frames"])
    first, frames = int(round(at * bar)), int(round(bars * bar))
    out, rate = None, CLAP_RATE
    for channel in CHANNELS:
        path = folder / (channel + ".flac")
        if not path.is_file():
            continue
        info = soundfile.info(str(path))
        rate = info.samplerate
        keep = min(int(WINDOW_S * rate), frames)
        start = first + (frames - keep) // 2
        audio, _ = soundfile.read(str(path), start=start, frames=keep, dtype="float32", always_2d=True)
        out = audio if out is None else out[:len(audio)] + audio[:len(out)]
    if out is None or rate != CLAP_RATE:
        raise ValueError("%s: no stems at %d Hz" % (folder, CLAP_RATE))
    return level(out).mean(axis=1)


def staged(style: str) -> list[Path]:
    """One take for each song of a style: a family's first, and each of its takes in another band's sounds than that one's."""
    out = []
    for family in sorted((VAR / "studio" / style).iterdir()):
        bands = set()
        for folder in sorted((each for each in family.iterdir() if (each / "track.json").is_file() and (each / "sheet.json").is_file()),
                             key=lambda each: int(each.name)) if family.is_dir() else ():
            band = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))["about"].get("sounds") or ""
            if band not in bands:
                bands.add(band)
                out.append(folder)
    return out


def heard(style: str, folders: list[Path], threads: int) -> dict[str, dict]:
    """What CLAP makes of each song's three places, from what was kept and from the recordings."""
    book = VAR / "passes" / ("sameness-%s.json" % style)
    kept = json.loads(book.read_text(encoding="utf-8")) if book.is_file() else {}
    due = [folder for folder in folders if (kept.get(name := "%s/%s" % (folder.parent.name, folder.name)) or {}).get("stamp")
           != (folder / "track.json").stat().st_mtime]
    if due:
        import torch
        torch.set_num_threads(threads)
        sys.path.insert(0, str(JUDGES / "TuneJury"))
        import laion_clap
        from tunejury.score import _resolve_clap_ckpt
        clap = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base")
        clap.load_ckpt(ckpt=_resolve_clap_ckpt(str(JUDGES / "TuneJury" / "checkpoints" / "tunejury.pt")))
        clap.to("cpu").eval()
        began = time.time()
        for index, folder in enumerate(due):
            meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
            sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))
            names = [section["part"] for section in sheet["form"]]
            row = {"stamp": (folder / "track.json").stat().st_mtime, "title": meta["title"], "light": bool(meta.get("light")),
                   "band": sheet["about"].get("sounds") or "", "parts": {}}
            for part in PARTS:
                audio = window(folder, meta, names, part)
                if audio is not None:
                    with torch.no_grad():
                        found = clap.get_audio_embedding_from_data(x=audio.astype(np.float32)[None, :], use_tensor=False)[0]
                    row["parts"][part] = [round(float(value), 5) for value in found / np.linalg.norm(found)]
            kept["%s/%s" % (folder.parent.name, folder.name)] = row
            if index % 10 == 9 or index == len(due) - 1:
                new = book.with_suffix(".json.new")
                new.write_text(json.dumps(kept), encoding="utf-8")
                new.replace(book)
                print("%s: %d of %d heard, %.1f s each" % (style, index + 1, len(due), (time.time() - began) / (index + 1)), file=sys.stderr, flush=True)
    return {name: kept[name] for name in ("%s/%s" % (folder.parent.name, folder.name) for folder in folders)}


def alike(songs: dict[str, dict]) -> tuple[list[str], np.ndarray]:
    """The songs' names and how alike each two are: the mean of the parts' cosines."""
    names = [name for name, row in songs.items() if set(row["parts"]) == set(PARTS)]
    total = np.zeros((len(names), len(names)))
    for part in PARTS:
        vectors = np.array([songs[name]["parts"][part] for name in names])
        total += vectors @ vectors.T
    return names, total / len(PARTS)


def report(style: str, songs: dict[str, dict], pairs: int, since: float) -> None:
    names, matrix = alike(songs)
    count = len(names)
    upper = matrix[np.triu_indices(count, 1)]
    off = matrix - 2.0 * np.eye(count)
    print("%s: %d songs; two of them are alike by %.3f (the middle pair %.3f, one pair in ten over %.3f); a song and its nearest %.3f" % (
        style, count, upper.mean(), np.median(upper), np.percentile(upper, 90), off.max(axis=1).mean()))
    for label, chosen in (("light", [i for i in range(count) if songs[names[i]]["light"]]), ("heavy", [i for i in range(count) if not songs[names[i]]["light"]])):
        if len(chosen) > 2:
            part = matrix[np.ix_(chosen, chosen)]
            print("  %-6s %3d songs %.3f" % (label, len(chosen), part[np.triu_indices(len(chosen), 1)].mean()))
    bands = sorted({songs[name]["band"] for name in names})
    if len(bands) > 1:
        house = [i for i in range(count) if not songs[names[i]]["band"]]
        for band in bands:
            mine = [i for i in range(count) if songs[names[i]]["band"] == band]
            inner = matrix[np.ix_(mine, mine)][np.triu_indices(len(mine), 1)].mean() if len(mine) > 1 else float("nan")
            print("  band %-10s %3d songs, alike by %.3f among themselves, %.3f to the house band's" % (
                band or "(house)", len(mine), inner, matrix[np.ix_(mine, house)].mean() if band else inner))
    if since:
        fresh = [i for i in range(count) if songs[names[i]]["stamp"] >= since]
        old = [i for i in range(count) if songs[names[i]]["stamp"] < since]
        if fresh and old:
            print("  %d new: alike by %.3f among themselves, %.3f to the %d before them (which are alike by %.3f)" % (
                len(fresh), matrix[np.ix_(fresh, fresh)][np.triu_indices(len(fresh), 1)].mean() if len(fresh) > 1 else float("nan"),
                matrix[np.ix_(fresh, old)].mean(), len(old), matrix[np.ix_(old, old)][np.triu_indices(len(old), 1)].mean()))
    order = np.dstack(np.unravel_index(np.argsort(-np.triu(matrix, 1), axis=None), matrix.shape))[0][:pairs]
    for one, other in order:
        print("  %.3f  %s (%s) and %s (%s)" % (matrix[one, other], songs[names[one]]["title"], names[one], songs[names[other]]["title"], names[other]))
    crowd = np.argsort(-((matrix.sum(axis=1) - 1.0) / max(count - 1, 1)))
    print("  most like all the others: " + ", ".join("%s %.3f" % (songs[names[i]]["title"], (matrix[i].sum() - 1.0) / max(count - 1, 1)) for i in crowd[:pairs]))
    print("  least like the others: " + ", ".join("%s %.3f" % (songs[names[i]]["title"], (matrix[i].sum() - 1.0) / max(count - 1, 1)) for i in crowd[::-1][:pairs]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="How alike a style's songs sound.")
    parser.add_argument("styles", nargs="+", choices=("knight", "warcraft", "house"))
    parser.add_argument("--pairs", type=int, default=12, help="how many of the nearest pairs to name")
    parser.add_argument("--new", type=float, default=0.0, help="hours: what was staged since, against the rest")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args(argv)
    for style in args.styles:
        report(style, heard(style, staged(style), args.threads), args.pairs, time.time() - args.new * 3600.0 if args.new else 0.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
