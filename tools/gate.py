"""The gate: a new song against the liked library, like for like, before it comes into the player.

(2026-11-26, the audit after "most of the music we heard last night sucked ... it got worse not better": the judges that listen had
scored the new bands' songs under the library for two nights, and it was explained away, since each new song was read against the
others of its round, a window of it against whole songs of the library, and no number kept a song out of the player. Round thirteen's
ten Knight Rock songs read 2.76 by SongEval where the same windows of ten older songs read 3.19.)

A song is read one of two ways, and held to the liked library read the same way, in its own style:

  whole     SongEval's reading of a whole staged take, which is of its two minutes from the first theme on (tools/judges.py, `song_of`).
            The library's are the whole takes the judges' watch read until 2026-11-23 (the label "watch": 130 Knight Rock songs, 62
            Warcraft, 69 House), so nothing has to be judged again to have something to hold a song to; and with `judges.py --only
            songeval` a new song is read in a minute or two, where all three judges take twenty over a whole song.
  windows   its first theme's last 32 bars and its last moment's first 32 (tools/windows.py; a row for each window, its folder naming
            which). The library's are the same windows of older songs (the labels LIBRARY): few still.

A song passes when the mean of SongEval's five scores, and its Memorability, are each at or over the library's lower quartile: no worse
than three in four of the songs that are liked. One that does not stays out (tools/rest.py). A song read both ways has to pass both.
(SongEval hears a song's first two minutes, or a window: it does not hear whether a tune comes back four minutes later. That is the
sheet's to say: tools/study.py, "the tune's phrases that come back".)

    cd app && uv run --no-sync python ../tools/gate.py library                 what a song is held to, style by style, and from how many songs
    ... gate.py check <label> [--style knight]                                   each song judged under that label: its scores, and pass or hold
    ... gate.py check <label> --passed                                           only the names of those that pass (family/take, a line each: for rest.py back)
    ... gate.py pick knight [--n 24]                                             the library's songs to read for it: the most played, one take of each, not resting
    ... gate.py read <label> knight --tag audit-1126 [--threads 2] [--n 40]      has the judges read (SongEval alone, whole takes) the songs resting under a tag
                                                                                 that have no reading under the label yet; then `check <label>` says which pass

A reading counts for the take as it is staged: one made before the take was performed again (`performed_since`) is left out by `check`,
and `read` has that take read again.

It reads the judges' log and changes nothing.
"""
from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

VAR = Path(__file__).resolve().parent.parent / "var"
LIBRARY = ("library", "revold-before")      # windows of older songs as they are staged
LIBRARY_WHOLE = ("watch", "library")        # whole takes of older songs as they are staged
WINDOWS = ("theme", "summit")
WAYS = ("whole", "windows")
QUARTER = 0.25
THIN = 20                      # a library read from fewer songs than this is said to be thin
MINUTE = 60.0                  # a reading's time is kept to the minute (tools/judges.py, "at")


def rows_of(log: Path) -> list[dict]:
    return [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines() if line.strip()]


def window_of(row: dict) -> str:
    """Which window of its song a row is ("theme", "summit"): what the folder its style's folder stands in is called (windows-round13/summit/knight/family/take,
    windows-rev1126/before-theme/warcraft/family/take); "" for a whole song or anything else."""
    said = str(row.get("folder", "")).replace("\\", "/").lower().rstrip("/").split("/")
    if len(said) < 4 or said[-3] != str(row.get("style", said[-3])).lower():
        return ""
    return next((which for which in WINDOWS if which in said[-4].split("-")), "")


def whole(row: dict) -> bool:
    """Whether a row is of a whole staged take: its folder is <style>/<family>/<take> of a stage (var/studio, or a demo's), not a window's."""
    said = str(row.get("folder", "")).replace("\\", "/").rstrip("/").split("/")
    return not window_of(row) and len(said) >= 3 and "%s/%s" % (said[-2], said[-1]) == row.get("take")


def performed_since(row: dict) -> bool:
    """Whether the take a reading is of was performed again after it was read: its track.json, the last thing a performance writes
    (studio.write_track), is newer than the reading by more than the minute a reading's time is kept to. Such a reading is of recordings that
    are no longer there, or of half of each where the judges read a take while its stems were being put in. (2026-11-26: the resting songs
    written again plainly are performed over their takes by day, and the judges read what rests by night under one label.) False where the
    row has no time, or the take is not staged where it was read: nothing is known against the reading."""
    at, folder = row.get("at"), row.get("folder")
    if not at or not folder:
        return False
    meta = Path(folder) / "track.json"
    if not meta.is_file():
        return False
    return meta.stat().st_mtime >= datetime.datetime.fromisoformat(at).timestamp() + MINUTE


def standing(rows: list[dict], label: str) -> tuple[list[dict], list[str]]:
    """The judges' rows without a label's whole readings of takes performed again since (`performed_since`), and the songs (style/family/take)
    that are left with no reading by it: those are read again. The library's own readings are not looked at: they are of its songs as they
    were liked."""
    kept, gone = [], set()
    for row in rows:
        if row.get("label") == label and whole(row) and performed_since(row):
            gone.add((row.get("style"), row.get("take")))
        else:
            kept.append(row)
    still = {(row.get("style"), row.get("take")) for row in kept if row.get("label") == label and whole(row)}
    return kept, sorted("%s/%s" % key for key in gone - still)


def songs(rows: list[dict], labels: tuple[str, ...], way: str = "windows") -> dict[tuple[str, str], dict]:
    """The songs judged under these labels and read this way ("windows" or "whole"), by (style, family/take): the mean of SongEval's
    five scores over its readings, its Memorability, and what was read. A reading made more than once counts by its latest."""
    latest: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        if row.get("label") not in labels or not row.get("songeval"):
            continue
        which = window_of(row) if way == "windows" else ("whole" if whole(row) else "")
        if which:
            latest[(row["style"], row["take"], which)] = row
    by: dict[tuple[str, str], list[tuple[str, dict]]] = defaultdict(list)
    for (style, take, which), row in latest.items():
        by[(style, take)].append((which, row))
    out = {}
    for key, found in by.items():
        out[key] = {"score": statistics.fmean(statistics.fmean(row["songeval"].values()) for _, row in found),
                    "memorability": statistics.fmean(row["songeval"]["Memorability"] for _, row in found),
                    "windows": sorted(which for which, _ in found), "title": found[0][1].get("title", "")}
    return out


def quartile(values: list[float]) -> float:
    """The lower quartile: the value a quarter of the way up (between two where it falls between)."""
    ordered = sorted(values)
    at = QUARTER * (len(ordered) - 1)
    low = int(at)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (at - low)


def library(rows: list[dict], way: str = "windows") -> dict[str, dict]:
    """What a song of each style is held to, read this way: the lower quartile of the library's scores and of its Memorability, and how many songs they are read from."""
    by: dict[str, list[dict]] = defaultdict(list)
    for (style, _), found in songs(rows, LIBRARY if way == "windows" else LIBRARY_WHOLE, way).items():
        by[style].append(found)
    return {style: {"score": quartile([each["score"] for each in found]), "memorability": quartile([each["memorability"] for each in found]),
                    "middle": statistics.median(each["score"] for each in found), "songs": len(found)} for style, found in by.items()}


def check(rows: list[dict], label: str, style: str = "") -> list[dict]:
    """Each song judged under a label against its style's library, each way it was read: pass, or hold with what is under. A song
    read both ways is two entries, and passes only if both do (`passed`)."""
    out = []
    for way in WAYS:
        held_to = library(rows, way)
        for (its_style, take), found in sorted(songs(rows, (label,), way).items()):
            if style and its_style != style:
                continue
            bar = held_to.get(its_style)
            if bar is None:             # nothing to hold it to: it does not pass, and the reason is said
                out.append({"style": its_style, "take": take, "way": way, **found, "passes": False,
                            "under": ["no library: nothing of %s's older songs read by %s" % (its_style, way)], "bar": None})
                continue
            under = [name for name in ("score", "memorability") if found[name] < bar[name]]
            out.append({"style": its_style, "take": take, "way": way, **found, "passes": not under, "under": under, "bar": bar})
    return sorted(out, key=lambda each: (each["style"], each["take"], each["way"]))


def passed(found: list[dict]) -> list[str]:
    """The songs (family/take) every one of whose readings passes."""
    by: dict[str, list[bool]] = defaultdict(list)
    for each in found:
        by[each["take"]].append(each["passes"])
    return sorted(take for take, all_of in by.items() if all(all_of))


def pick(var: Path, style: str, n: int = 24) -> list[str]:
    """The songs of a style's library to have judged as what new songs are held to (label "library"): those heard the most from their
    openings, one take of a family (its most played), none that is resting and none that has no recordings staged."""
    import sqlite3
    resting = set()
    listed = Path(var) / "studio" / style / "resting.txt"
    if listed.is_file():
        resting = {line.split(" ", 1)[0] for line in listed.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    with sqlite3.connect("file:%s?mode=ro" % (Path(var) / "plays.sqlite3"), uri=True) as db:
        heard = db.execute("select track, max(plays) from parts where style = ? and place = 0 group by track order by max(plays) desc, track", (style,)).fetchall()
    out, families = [], set()
    for track, plays in heard:
        name = track.split("/", 1)[1]
        family = name.rsplit("/", 1)[0]
        if plays and name not in resting and family not in families and (Path(var) / "studio" / style / name / "track.json").is_file():
            families.add(family)
            out.append(name)
        if len(out) == n:
            break
    return out


def to_read(var: Path, rows: list[dict], label: str, style: str, tag: str) -> list[str]:
    """The songs (family/take) resting under a tag in a style that have no whole reading under the label yet, in the list's order."""
    listed = Path(var) / "studio" / style / "resting.txt"
    names = []
    for line in listed.read_text(encoding="utf-8").splitlines() if listed.is_file() else ():
        name, _, said = line.partition(" ")
        if line.strip() and not line.startswith("#") and said.startswith("[%s]" % tag):
            names.append(name)
    done = {take for (its_style, take) in songs(rows, (label,), "whole") if its_style == style}
    return [name for name in names if name not in done]


def read(var: Path, label: str, style: str, names: list[str], threads: int = 2) -> int:
    """Has the judges' own Python read these staged takes by SongEval alone (tools/judges.py --only songeval), one process for them all; what it
    says goes to this command's output, and its status is returned. (The judges live in a virtual environment of their own, var/tools/judges.)"""
    import os
    import subprocess
    python = Path(var) / "tools" / "judges" / ".venv" / "bin" / "python"
    if not python.is_file():
        raise FileNotFoundError("The judges' Python is not there: %s" % python)
    root = Path(__file__).resolve().parent.parent
    command = [str(python), "tools/judges.py", "--threads", str(threads), "--only", "songeval", "--label", label] + ["%s/%s" % (style, name) for name in names]
    return subprocess.run(command, cwd=str(root), env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A new song against the liked library, like for like.")
    sub = parser.add_subparsers(dest="what", required=True)
    sub.add_parser("library")
    checked = sub.add_parser("check")
    checked.add_argument("label")
    checked.add_argument("--style", default="")
    checked.add_argument("--passed", action="store_true")
    reading = sub.add_parser("read")
    reading.add_argument("label")
    reading.add_argument("style")
    reading.add_argument("--tag", required=True)
    reading.add_argument("--threads", type=int, default=2)
    reading.add_argument("--n", type=int, default=0, help="no more than this many now (the rest at the next call)")
    picked = sub.add_parser("pick")
    picked.add_argument("style")
    picked.add_argument("--n", type=int, default=24)
    parser.add_argument("--log", default=str(VAR / "passes" / "judged3.jsonl"))
    args = parser.parse_args(argv)
    if args.what == "read":
        rows, again = standing(rows_of(Path(args.log)), args.label)
        again = [name for name in again if name.startswith(args.style + "/")]
        if again:
            print("%s: %d read under %s before they were performed again, to be read again: %s" % (args.style, len(again), args.label, ", ".join(again)), flush=True)
        names = to_read(VAR, rows, args.label, args.style, args.tag)
        if args.n:
            names = names[:args.n]
        if not names:
            print("%s: no song resting under [%s] is unread under %s" % (args.style, args.tag, args.label))
            return 0
        print("%s: %d songs resting under [%s] to be read under %s" % (args.style, len(names), args.tag, args.label), flush=True)
        return read(VAR, args.label, args.style, names, args.threads)
    if args.what == "pick":
        print("\n".join(pick(VAR, args.style, args.n)))
        return 0
    rows = rows_of(Path(args.log))
    again: list[str] = []
    if args.what == "check":
        rows, again = standing(rows, args.label)
        again = [name for name in again if not args.style or name.startswith(args.style + "/")]
    if args.what == "library":
        for way in WAYS:
            for style, bar in sorted(library(rows, way).items()):
                print("%-8s %-9s a song passes at %.2f or over (SongEval's five, the mean) and %.2f in Memorability; the library's middle %.2f; from %d songs%s" % (
                    way, style, bar["score"], bar["memorability"], bar["middle"], bar["songs"], "  (THIN: under %d)" % THIN if bar["songs"] < THIN else ""))
        return 0
    found = check(rows, args.label, args.style)
    if args.passed:
        print("\n".join(passed(found)))
        return 0
    for each in found:
        bar = each["bar"] or {"score": float("nan"), "memorability": float("nan")}
        print("%-5s %-9s %-40s %-26s %.2f (bar %.2f)  memorability %.2f (bar %.2f)  %s%s" % (
            "pass" if each["passes"] else "HOLD", each["style"], each["take"], each["title"][:26], each["score"], bar["score"], each["memorability"],
            bar["memorability"], "+".join(each["windows"]), "" if each["passes"] else "  under in: " + ", ".join(each["under"])))
    names = {each["take"] for each in found}
    print("%d songs: %d pass, %d held" % (len(names), len(passed(found)), len(names) - len(passed(found))))
    if again:
        print("%d not counted, read before they were performed again (gate.py read reads them again): %s" % (len(again), ", ".join(again)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
