"""Writes and plays a chosen list of tracks, several at a time, and keeps going past a failure.

    cd app && uv run --no-sync python ../tools/render_some.py --workers 3 --until 16:10 highland-snowfall-1/1 pastoral-tavern-1/1 ...

Each name is a family and a take. Tracks are begun in the order given, `--workers` at a time;
none is begun after `--until` (so an evening's music is ready by a known time). A track that
fails is reported with its error when it fails and again at the end, the others go on, and the
command ends with 1 if any failed.
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timedelta
from multiprocessing import Pool

from freerock.studio import build, reaper, sounds


def deadline_of(until: str) -> float | None:
    """When `--until` is: the next time the clock shows it, so that a queue begun at 23:00 with --until 08:00 runs
    through the night (found 2026-11-16: comparing the time of day alone, 23:06 was already past 08:00)."""
    if not until:
        return None
    hour, minute = (int(part) for part in until.split(":"))
    now = datetime.now()
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if at <= now:
        at += timedelta(days=1)
    return at.timestamp()


def one(job: tuple[str, int, str, float | None]) -> tuple[str, int, str, str]:
    name, take, until, deadline = job
    if deadline is not None and time.time() >= deadline:
        return name, take, "not begun", "it was past %s" % until
    try:
        fam = next(fam for fam, _ in build.plan() if fam.name == name)
        began = time.time()
        made = build.stage(fam, take)
        return name, take, "done", "%s, %d s of music, in %.0f s" % (made["title"], made["seconds"], time.time() - began)
    except Exception:
        return name, take, "FAILED", traceback.format_exc()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write and play some tracks, several at a time.")
    parser.add_argument("tracks", nargs="+", help="family/take, in the order they are to be begun")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--until", default="", help="begin none after this time of day (HH:MM)")
    args = parser.parse_args(argv)
    deadline = deadline_of(args.until)
    jobs = [(name.rsplit("/", 1)[0], int(name.rsplit("/", 1)[1]), args.until, deadline) for name in args.tracks]
    known = {fam.name for fam, _ in build.plan()}
    unknown = [name for name, _, _ in jobs if name not in known]
    if unknown:
        raise SystemExit("There are no such families: %s" % ", ".join(unknown))
    reaper.configure()
    from freerock.studio.orchestra import KITS
    for player in sounds.wanted() + ["kit " + kit for kit in KITS]:
        sounds.track_of(player)                    # every instrument written out before anything renders: a render must not see one change
    failed = []
    with Pool(processes=args.workers) as pool:
        for name, take, how, said in pool.imap_unordered(one, jobs):
            print("%s  %-10s %s/%d  %s" % (datetime.now().strftime("%H:%M:%S"), how, name, take, said), flush=True)
            if how == "FAILED":
                failed.append((name, take, said))
    if failed:
        print("\n%d failed:" % len(failed), flush=True)
        for name, take, said in failed:
            print("--- %s/%d\n%s" % (name, take, said), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
