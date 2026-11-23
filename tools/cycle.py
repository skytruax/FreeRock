"""The standing cycle (docs/plan.md, "The standing cycle"): in each round, ten new songs and ten old ones in every style.

(2026-11-23: "update the plans and recursive loop to make this process more iterative and recursive", "focus on expanding the
options of music in every area type, on all the genres", "there should be a standard process, like 10 new songs from each
genre, test 10 old songs from each genre, iterate on those", "loop".)

    cd app && uv run --no-sync python ../tools/cycle.py gaps [--style knight] [--n 10]
        where songs are few or come round most often: each kind of place, and each kind of moment, with how many songs it has,
        how often they were heard, and how many were never heard; those with the greatest need first
    ... cycle.py old [--style house] [--n 10]
        the old songs to test: tested the fewest times, then heard the most, then judged the lowest (the mean of SongEval's
        five scores, when a song has been judged)
    ... cycle.py mark <style/family/take> pass|revise|revised ["what was found"]
        keeps the result of a test (var/passes/cycle.json), so the next round takes others
    ... cycle.py round [begin|end] ["what was made, what was learnt"]
        writes down where a round stands; with nothing said, the last ones

It reads the plays (var/plays.sqlite3), the staged takes and the judges' log, and changes none of them.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

VAR = Path(__file__).resolve().parent.parent / "var"
STYLES = ("knight", "warcraft", "house")
# The kinds of moment besides walking about: a place of its own, or a thing that happens (studio.ROLES); walking is told by the
# kinds of place it is for.
MOMENTS = ("night", "ember", "camp", "depths", "storm", "battle", "boss", "town", "battleground")
EMPTY = 1000.0                 # a place or moment with no song at all: before any other


def staged(var: Path, style: str) -> dict[str, dict]:
    """Every staged song of a style, by its name (style/family/take), with what it says of itself."""
    out = {}
    for path in (var / "studio" / style).glob("*/*/track.json"):
        out["%s/%s/%s" % (style, path.parent.parent.name, path.parent.name)] = json.loads(path.read_text(encoding="utf-8"))
    return out


def plays(var: Path) -> dict[str, int]:
    """How many times each song was heard from its opening (the most of any channel's)."""
    book = var / "plays.sqlite3"
    if not book.is_file():
        return {}
    with sqlite3.connect("file:%s?mode=ro" % book, uri=True) as db:
        return {track: int(count) for track, count in db.execute("select track, max(plays) from parts where place = 0 group by track")}


def cells(songs: dict[str, dict]) -> dict[tuple[str, str], list[str]]:
    """The places and moments a style has music for, each with its songs: a walking song belongs to every kind of place it is
    for, the rest to their moment."""
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name, meta in songs.items():
        if meta.get("role") == "wander":
            for kind in meta.get("moods") or ["any"]:
                out["walk", kind].append(name)
        else:
            out["moment", str(meta.get("role"))].append(name)
    return dict(out)


def gaps(var: Path, style: str, kinds: tuple[str, ...]) -> list[dict]:
    """Each kind of place and kind of moment of a style, those most in need first: none at all, then heard the most per song."""
    songs, heard = staged(var, style), plays(var)
    found = cells(songs)
    rows = []
    for sort, what in [("walk", kind) for kind in kinds] + [("moment", moment) for moment in MOMENTS]:
        names = found.get((sort, what), [])
        counted = sum(heard.get(name, 0) for name in names)
        never = sum(heard.get(name, 0) == 0 for name in names)
        rows.append({"kind": "%s %s" % (sort, what), "songs": len(names), "plays": counted, "never": never,
                     "dark": sum(1 for name in names if not songs[name].get("light")),
                     "need": EMPTY if not names else (counted + 1.0) / len(names)})
    return sorted(rows, key=lambda row: (-row["need"], row["songs"]))


def scores(var: Path) -> dict[str, float]:
    """What each judged song scored (the mean of SongEval's five), the latest time it was judged."""
    log = var / "passes" / "judged3.jsonl"
    out: dict[str, float] = {}
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            row = json.loads(line) if line.strip() else {}
            if row.get("songeval") and row.get("style") and row.get("label") == "watch":
                out["%s/%s" % (row["style"], row["take"])] = sum(row["songeval"].values()) / len(row["songeval"])
    return out


def state(var: Path) -> dict:
    path = var / "passes" / "cycle.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"tested": {}, "rounds": []}


def keep(var: Path, told: dict) -> None:
    path = var / "passes" / "cycle.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + ".new")
    scratch.write_text(json.dumps(told, indent=1) + "\n", encoding="utf-8")
    scratch.replace(path)


def old(var: Path, style: str, n: int) -> list[dict]:
    """The old songs to test in a round: those tested the fewest times, then heard the most, then judged the lowest."""
    tested, heard, judged = state(var)["tested"], plays(var), scores(var)
    rows = []
    for name, meta in staged(var, style).items():
        rows.append({"name": name, "title": meta.get("title", "?"), "role": meta.get("role"), "tested": int(tested.get(name, {}).get("times", 0)),
                     "plays": heard.get(name, 0), "judged": judged.get(name)})
    rows.sort(key=lambda row: (row["tested"], -row["plays"], row["judged"] if row["judged"] is not None else 9.0, row["name"]))
    # One take of a family is enough to say what is wrong with it; the others come when the families have run out.
    first, rest, families = [], [], set()
    for row in rows:
        family = row["name"].rsplit("/", 1)[0]
        (first if family not in families else rest).append(row)
        families.add(family)
    return (first + rest)[:n]


def mark(var: Path, name: str, result: str, note: str, now: datetime.datetime) -> dict:
    """Keeps what a test of a song came to."""
    if result not in ("pass", "revise", "revised"):
        raise ValueError("A test comes to pass, revise or revised, not %r" % result)
    told = state(var)
    was = told["tested"].get(name, {"times": 0})
    was["times"] = int(was["times"]) + 1
    was.update({"last": now.isoformat(timespec="minutes"), "result": result, "note": note})
    told["tested"][name] = was
    keep(var, told)
    return was


def main(argv: list[str] | None = None, now: datetime.datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="The standing cycle: ten new songs and ten old ones in every style.")
    parser.add_argument("--var", default=str(VAR), help="the var folder (default: the repository's)")
    what = parser.add_subparsers(dest="what", required=True)
    for name, about in (("gaps", "where songs are few or come round often"), ("old", "the old songs to test")):
        each = what.add_parser(name, help=about)
        each.add_argument("--style", choices=STYLES)
        each.add_argument("--n", type=int, default=10)
    each = what.add_parser("mark", help="keeps the result of a test")
    each.add_argument("song", help="style/family/take")
    each.add_argument("result", choices=("pass", "revise", "revised"))
    each.add_argument("note", nargs="?", default="")
    each = what.add_parser("round", help="where a round stands")
    each.add_argument("part", nargs="?", choices=("begin", "end"), default=None)
    each.add_argument("note", nargs="?", default="")
    args = parser.parse_args(argv)
    var, now = Path(args.var), now or datetime.datetime.now()
    if args.what == "gaps":
        # (The kinds of place are the atlas's; read here only, so the tool needs no other part of FreeRock to list a round.)
        kinds = ("pastoral", "highland", "haunted", "desert", "jungle", "infernal", "regal", "mystic", "marsh", "coast", "frozen")
        for style in [args.style] if args.style else STYLES:
            print("%s: the places and moments most in need (songs; heard, all together; per song; never heard; not light)" % style)
            for row in gaps(var, style, kinds)[:args.n]:
                print("  %-18s %4d songs  heard %4d  %.1f a song  %3d never  %3d heavy%s" % (
                    row["kind"], row["songs"], row["plays"], row["plays"] / max(1, row["songs"]), row["never"], row["dark"],
                    "   NONE" if row["need"] == EMPTY else ""))
    elif args.what == "old":
        for style in [args.style] if args.style else STYLES:
            print("%s: the old songs to test (tested; heard; judged)" % style)
            for row in old(var, style, args.n):
                print("  %-36s %-26s %d times  heard %2d  %s" % (row["name"], row["title"][:26], row["tested"], row["plays"],
                                                                  "%.2f" % row["judged"] if row["judged"] is not None else "not judged"))
    elif args.what == "mark":
        was = mark(var, args.song, args.result, args.note, now)
        print("%s: %s, tested %d times" % (args.song, args.result, was["times"]))
    else:
        told = state(var)
        if args.part:
            rounds = told["rounds"]
            if args.part == "begin":
                rounds.append({"number": len(rounds) + 1, "began": now.isoformat(timespec="minutes"), "said": args.note, "ended": None})
            elif rounds and rounds[-1]["ended"] is None:
                rounds[-1].update({"ended": now.isoformat(timespec="minutes"), "said": (rounds[-1]["said"] + " | " + args.note).strip(" |")})
            else:
                print("there is no round to end: begin one first")
                return 1
            keep(var, told)
        for each in told["rounds"][-3:]:
            print("round %d: %s to %s  %s" % (each["number"], each["began"], each["ended"] or "now", each["said"]))
        if not told["rounds"]:
            print("no round has begun")
    return 0


if __name__ == "__main__":
    sys.exit(main())
