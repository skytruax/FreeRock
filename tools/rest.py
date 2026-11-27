"""Rests staged songs (they stay staged and on the listening pages, and are kept out of the player) and brings them back.

(2026-11-26, the audit after "most of the music we heard last night sucked, the new bands a lot of time just sound random, it got
worse not better": of the 79 songs heard that evening 49 had come into the player since the evening before, each one for the first
time, since a song never heard comes first. What came in between the last evening that was liked and the one that was not is
taken out again as a whole, and comes back song by song as it is tested against the library: tools/gate.py.)

    cd app && uv run --no-sync python ../tools/rest.py since knight 2026-11-24T08:40 --tag audit-1126 --why "what was found"
        rests every take of the families whose first take was written at that time or after it
    ... rest.py back knight --tag audit-1126 [family/take ...]
        brings back the songs rested under a tag: all of them, or the ones named (and writes them down as let in: admitted.txt)
    ... rest.py new knight --tag new-1127 --why "new: not through the gate yet"
        rests every staged take the style's bucket does not have, a new family's and a further take of an older one alike,
        unless it was let in by hand (admitted.txt). var/passes/rebuild.sh does this before every build, so that nothing
        is in the player before it has been held to the library
    ... rest.py tag knight --tag audit-1126 --to retold-1126 --why "told another way each time: out until written again" [family/take ...]
        moves resting songs to another tag (all under the tag, or the ones named; with --since 2026-11-26T14:11 only those whose
        sheet was written then or after: the ones written again). A song is brought back by its tag, and the judges are given a
        tag to read: what is to stay out whatever they say rests under a word of its own
    ... rest.py these knight --tag audit-1126 --why "came in unread" family/take ...
        rests the songs named, whether the player has them or not (2026-11-26: fifteen further takes that came into the player with the
        morning's builds unread, before every take the player did not have was rested; and what the listener lets in and wants out again)
    ... rest.py list knight

A style's resting songs are the lines of var/studio/<style>/resting.txt (freerock.pieces.resting reads them when the style's
bucket is built): "family/take [tag] why". A change is heard after the bucket is built again (var/passes/rebuild.sh <style>).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

VAR = Path(__file__).resolve().parent.parent / "var"
HEAD = "# Songs staged and kept out of the player for now, one a line (family/take and why). A line taken out brings its song back at the next build.\n"


def path_of(var: Path, style: str) -> Path:
    return Path(var) / "studio" / style / "resting.txt"


def written(folder: Path) -> str:
    """When a staged take was first written (its sheet's first revision), or "" for one from before there were sheets."""
    sheet = Path(folder) / "sheet.json"
    if not sheet.is_file():
        return ""
    history = json.loads(sheet.read_text(encoding="utf-8")).get("history") or []
    return str(history[0].get("when") or "") if history else ""


def begun_since(var: Path, style: str, since: str) -> list[str]:
    """Every staged take (family/take) of the families whose first take was written at `since` or after it: the songs that are
    new since then. A new take of an older family is not one of them, nor a take from before there were sheets."""
    first: dict[str, str] = {}
    takes: dict[str, list[str]] = {}
    for track in sorted((Path(var) / "studio" / style).glob("*/*/track.json")):
        folder = track.parent
        when = written(folder)
        family = folder.parent.name
        takes.setdefault(family, []).append("%s/%s" % (family, folder.name))
        first[family] = min(first.get(family, when), when)       # (a take with no sheet is older than any: "")
    return sorted(name for family, names in takes.items() if first[family] >= since for name in names)


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".txt.part")
    part.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    os.replace(part, path)


def rest(var: Path, style: str, names: list[str], tag: str, why: str) -> list[str]:
    """Adds a line for each named song that has none yet; returns the songs added."""
    if not tag or " " in tag or "]" in tag:
        raise ValueError("A tag is one word (audit-1126), not %r" % tag)
    path = path_of(var, style)
    lines = lines_of(path) or [HEAD.rstrip("\n")]
    resting = {line.split(" ", 1)[0] for line in lines if line.strip() and not line.startswith("#")}
    added = [name for name in names if name not in resting]
    for name in added:
        if name.count("/") != 1:
            raise ValueError("A song is said as its family and take (meadow-01/2), not %r" % name)
    _write(path, lines + ["%s [%s] %s" % (name, tag, why) for name in added])
    return added


def back(var: Path, style: str, tag: str, names: list[str] | None = None) -> list[str]:
    """Takes out the lines of a tag (all of them, or those of the songs named); returns the songs brought back."""
    path = path_of(var, style)
    kept, out = [], []
    for line in lines_of(path):
        name, _, said = line.partition(" ")
        if not line.startswith("#") and said.startswith("[%s]" % tag) and (names is None or name in names):
            out.append(name)
        else:
            kept.append(line)
    if out:
        _write(path, kept)
        # What is brought back is let in: the next build's look for new songs (`new_songs`) does not rest it again.
        let_in = path.with_name("admitted.txt")
        _write(let_in, (lines_of(let_in) or ["# Songs let into the player by hand or by the gate (family/take, from which tag): tools/rest.py new does not rest these."])
               + ["%s [%s]" % (name, tag) for name in out if name not in names_in(let_in)])
    return out


def retag(var: Path, style: str, tag: str, to: str, names: list[str] | None = None, why: str = "", since: str = "") -> list[str]:
    """Moves songs resting under one tag to another: all of them, or the ones named; with `since`, only those whose sheet was first written at
    that time or after it (the ones written again since). The reason is said anew where one is given, and kept where not. Returns the songs moved.
    (2026-11-26: the takes told another way each time rest with the other new songs, and are to stay out even where the judges pass them, until
    they are written again plainly: `back` brings back by tag, and tools/gate.py reads by tag.)"""
    if not to or " " in to or "]" in to:
        raise ValueError("A tag is one word (retold-1126), not %r" % to)
    path = path_of(var, style)
    kept, moved = [], []
    for line in lines_of(path):
        name, _, said = line.partition(" ")
        if (not line.startswith("#") and said.startswith("[%s]" % tag) and (names is None or name in names)
                and (not since or written(Path(var) / "studio" / style / name) >= since)):
            kept.append(("%s [%s] %s" % (name, to, why or said[len(tag) + 2:].strip())).rstrip())
            moved.append(name)
        else:
            kept.append(line)
    if moved:
        _write(path, kept)
    return moved


def names_in(path: Path) -> set[str]:
    return {line.split(" ", 1)[0] for line in lines_of(path) if line.strip() and not line.startswith("#")}


def in_player(var: Path, style: str) -> set[str]:
    """The songs (family/take) the style's bucket has, as its index says."""
    indexes = sorted((Path(var) / "buckets" / style).glob("*/bucket.json"))
    if not indexes:
        raise ValueError("The %s style has no bucket (%s): there is nothing to tell a new song from" % (style, Path(var) / "buckets" / style))
    found = set()
    for index in indexes:
        for piece in json.loads(index.read_text(encoding="utf-8"))["pieces"].values():
            source = str(piece.get("source") or "")
            if source.startswith(style + "/"):
                found.add(source.split("/", 1)[1])
    return found


def new_songs(var: Path, style: str) -> list[str]:
    """The staged takes that are new to the player: every one the bucket does not have, that is neither resting nor let in (admitted.txt). A new
    family's take and a further take of a family the player has are held alike: a further take is written and mixed by the writer and the desk as
    they are that night, days on from the take that is liked, and until 2026-11-26 it went in unread like everything else."""
    resting = names_in(path_of(var, style))
    let_in = names_in(path_of(var, style).with_name("admitted.txt"))
    has = in_player(var, style)
    out = []
    for track in sorted((Path(var) / "studio" / style).glob("*/*/track.json")):
        name = "%s/%s" % (track.parent.parent.name, track.parent.name)
        if name not in resting and name not in let_in and name not in has:
            out.append(name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rest staged songs, and bring them back.")
    sub = parser.add_subparsers(dest="what", required=True)
    since = sub.add_parser("since")
    since.add_argument("style")
    since.add_argument("when", help="2026-11-24T08:40: families whose first take was written then or after")
    since.add_argument("--tag", required=True)
    since.add_argument("--why", required=True)
    since.add_argument("--dry", action="store_true", help="say which songs, and rest none")
    again = sub.add_parser("back")
    again.add_argument("style")
    again.add_argument("--tag", required=True)
    again.add_argument("songs", nargs="*")
    fresh = sub.add_parser("new")
    fresh.add_argument("style")
    fresh.add_argument("--tag", required=True)
    fresh.add_argument("--why", default="new: not held to the library yet (tools/gate.py)")
    fresh.add_argument("--dry", action="store_true", help="say which songs, and rest none")
    moved = sub.add_parser("tag")
    moved.add_argument("style")
    moved.add_argument("--tag", required=True, help="the tag they rest under now")
    moved.add_argument("--to", required=True, help="the tag they are to rest under")
    moved.add_argument("--why", default="", help="the reason said anew (kept as it is where none is given)")
    moved.add_argument("--since", default="", help="2026-11-26T14:11: only the songs whose sheet was written then or after")
    moved.add_argument("songs", nargs="*")
    named = sub.add_parser("these")
    named.add_argument("style")
    named.add_argument("--tag", required=True)
    named.add_argument("--why", required=True)
    named.add_argument("songs", nargs="+")
    listed = sub.add_parser("list")
    listed.add_argument("style")
    args = parser.parse_args(argv)
    if args.what == "since":
        names = begun_since(VAR, args.style, args.when)
        if args.dry:
            print("\n".join(names))
            print("%s: %d songs begun since %s (none rested: --dry)" % (args.style, len(names), args.when))
            return 0
        added = rest(VAR, args.style, names, args.tag, args.why)
        print("%s: %d songs begun since %s; %d rested now under [%s]. Heard after: var/passes/rebuild.sh %s" % (args.style, len(names), args.when, len(added), args.tag, args.style))
    elif args.what == "new":
        names = new_songs(VAR, args.style)
        if args.dry:
            print("\n".join(names))
            print("%s: %d songs new to the player (none rested: --dry)" % (args.style, len(names)))
            return 0
        added = rest(VAR, args.style, names, args.tag, args.why)
        print("%s: %d songs new to the player rested under [%s], until they are through the gate" % (args.style, len(added), args.tag))
    elif args.what == "back":
        out = back(VAR, args.style, args.tag, args.songs or None)
        print("%s: %d songs brought back from [%s]. Heard after: var/passes/rebuild.sh %s" % (args.style, len(out), args.tag, args.style))
    elif args.what == "these":
        missing = [name for name in args.songs if not (VAR / "studio" / args.style / name / "track.json").is_file()]
        if missing:
            parser.error("not staged in %s: %s" % (args.style, " ".join(missing)))
        added = rest(VAR, args.style, args.songs, args.tag, args.why)
        print("%s: %d songs rested under [%s]%s. Heard after: var/passes/rebuild.sh %s" % (
            args.style, len(added), args.tag, "" if len(added) == len(args.songs) else " (%d were resting already)" % (len(args.songs) - len(added)), args.style))
    elif args.what == "tag":
        out = retag(VAR, args.style, args.tag, args.to, args.songs or None, args.why, args.since)
        print("%s: %d songs moved from [%s] to [%s]" % (args.style, len(out), args.tag, args.to))
        missing = [name for name in args.songs if name not in out]
        if missing:
            print("%s: not moved (not resting under [%s]%s): %s" % (args.style, args.tag, ", or not written since %s" % args.since if args.since else "", " ".join(missing)))
    else:
        lines = [line for line in lines_of(path_of(VAR, args.style)) if line.strip() and not line.startswith("#")]
        print("\n".join(lines))
        print("%s: %d songs resting" % (args.style, len(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
