"""What was heard on an evening: how many songs, how many of them for the first time, and how new they were.

(2026-11-26, the audit after "most of the music we heard last night sucked ... it got worse not better": nobody had looked at what
had played. Of that evening's 79 songs 49 had come into the player since the evening before, every one of them for the first time,
since a song never heard comes first: two nights' untested songs were three fifths of the evening. This is read each morning, before
anything is said about the night's music.)

    cd app && uv run --no-sync python ../tools/heard.py [--day 2026-11-25] [--from 15:00] [--hours 15] [--new-days 2] [--songs]

It reads the plays (var/plays.sqlite3: when each part was last played) and the staged takes, and changes nothing. A song is its
family (its takes are one song in other hands); it was heard "for the first time" if nothing of it had been played before the
evening began; it is "new" if its first take was written in the `--new-days` days before the evening's day began, or after.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

VAR = Path(__file__).resolve().parent.parent / "var"
GAP = 720.0                    # seconds: a song's parts played further apart than this are two hearings of it
TAIL = 25.0                    # seconds counted after a hearing's last part began


def written(var: Path, song: str) -> tuple[str, str, str]:
    """When a song's first take was written ("" for one from before there were sheets), its title, and whose instruments it has."""
    first, title, sounds = None, "", ""
    for track in sorted((Path(var) / "studio" / song).glob("*/track.json")):
        title = title or json.loads(track.read_text(encoding="utf-8")).get("title", "")
        sheet = track.parent / "sheet.json"
        when = ""
        if sheet.is_file():
            read = json.loads(sheet.read_text(encoding="utf-8"))
            history = read.get("history") or []
            when = str(history[0].get("when") or "") if history else ""
            sounds = sounds or str((read.get("about") or {}).get("sounds") or "")
        first = when if first is None else min(first, when)
    return first or "", title, sounds


def evening(var: Path, begins: datetime.datetime, hours: float, new_days: int = 2) -> dict:
    """The hearings of an evening, in order, and what they add up to."""
    start, end = begins.timestamp(), (begins + datetime.timedelta(hours=hours)).timestamp()
    with sqlite3.connect("file:%s?mode=ro" % (Path(var) / "plays.sqlite3"), uri=True) as db:
        rows = db.execute("select track, last from parts where last is not null and plays > 0").fetchall()
    times: dict[str, list[float]] = {}
    before: set[str] = set()
    for track, last in rows:
        song = track.rsplit("/", 1)[0]
        if start <= last < end:
            times.setdefault(song, []).append(last)
        elif last < start:
            before.add(song)
    new_from = (begins.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=new_days)).isoformat(timespec="seconds")
    hearings = []
    for song, found in times.items():
        found.sort()
        when, title, sounds = written(var, song)
        first = prev = found[0]
        spans = []
        for at in found[1:]:
            if at - prev > GAP:
                spans.append((first, prev))
                first = at
            prev = at
        spans.append((first, prev))
        for first, last in spans:
            hearings.append({"song": song, "title": title, "sounds": sounds, "written": when, "began": first, "seconds": last - first + TAIL,
                             "first time": song not in before, "new": bool(when) and when >= new_from})
    hearings.sort(key=lambda each: each["began"])
    total = sum(each["seconds"] for each in hearings) or 1.0
    share = lambda which: sum(each["seconds"] for each in hearings if each[which]) / total      # noqa: E731
    return {"hearings": hearings, "songs": len({each["song"] for each in hearings}), "seconds": total if hearings else 0.0,
            "first time": len({each["song"] for each in hearings if each["first time"]}), "new": len({each["song"] for each in hearings if each["new"]}),
            "first time share": share("first time") if hearings else 0.0, "new share": share("new") if hearings else 0.0, "new from": new_from}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="What was heard on an evening.")
    parser.add_argument("--day", default="", help="2026-11-25 (yesterday if not said)")
    parser.add_argument("--from", dest="begins", default="15:00")
    parser.add_argument("--hours", type=float, default=15.0)
    parser.add_argument("--new-days", type=int, default=2)
    parser.add_argument("--songs", action="store_true", help="every hearing, in order")
    args = parser.parse_args(argv)
    day = datetime.date.fromisoformat(args.day) if args.day else datetime.date.today() - datetime.timedelta(days=1)
    hour, minute = (int(part) for part in args.begins.split(":"))
    found = evening(VAR, datetime.datetime.combine(day, datetime.time(hour, minute)), args.hours, args.new_days)
    if not found["hearings"]:
        print("%s: nothing was played." % day)
        return 0
    clock = lambda at: datetime.datetime.fromtimestamp(at).strftime("%H:%M")      # noqa: E731
    print("%s, %s to %s: %d songs heard, %.1f hours of them." % (day, clock(found["hearings"][0]["began"]), clock(found["hearings"][-1]["began"]), found["songs"], found["seconds"] / 3600))
    print("  for the first time: %d songs (%.0f%% of the time)" % (found["first time"], 100 * found["first time share"]))
    print("  written since %s: %d songs (%.0f%% of the time)" % (found["new from"][:10], found["new"], 100 * found["new share"]))
    by: dict[str, list[dict]] = {}
    for each in found["hearings"]:
        by.setdefault(each["song"].split("/")[0], []).append(each)
    for style, mine in sorted(by.items()):
        print("  %-9s %3d hearings, %3d of them of new songs, %3d by a band, company or act" % (style, len(mine), sum(each["new"] for each in mine), sum(bool(each["sounds"]) for each in mine)))
    if args.songs:
        for each in found["hearings"]:
            print("  %s %4.1f min  %-5s %-5s %-44s %-28s %-10s %s" % (clock(each["began"]), each["seconds"] / 60, "first" if each["first time"] else "", "new" if each["new"] else "",
                                                                 each["song"], each["title"][:28], each["sounds"], each["written"][:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
