"""What every staged take still lacks: the re-render ledger (2026-11-18: "move re-rendering to the end when the drives are
full but fully detail and keep track of what needs to be rerendered eventually this is a long tail project").

Until the drive is full the nights make new music; a change to the writer or the desk reaches the takes made after it,
and every take made before it that it would change is kept here, with what it lacks, until it is rendered again. A render
keeps the code its run began with, so a take's code is dated by when its list began (the lane logs), or for a run
outside the lanes by when its first take began (its log's "in N s").

    cd app && uv run --no-sync python ../tools/rerender_ledger.py          prints the ledger's counts
    ... --write                                                            and writes var/passes/rerender-ledger.json and .md

A new change is one more entry in CHANGES: its name, when it reached the files that render, the commit, what it does and
which pieces it changes (a test on the piece's character or House family).
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from freerock.studio import build, house
from freerock.studio.orchestra import DANCE_GROOVES, DELICATE

ROOT = Path(__file__).resolve().parent.parent
PASSES = ROOT / "var" / "passes"
STUDIO = ROOT / "var" / "studio"
SNOW = {"frozen cavern", "frozen lake", "ice fields", "aurora", "ice cave", "frost camp"}


@dataclass(frozen=True)
class Piece:
    style: str
    key: str            # family/take
    family: str
    character: object   # an orchestra character, or a House family
    meta: dict


def plays(piece: Piece, instrument: str, parts: tuple[str, ...] = ("leads", "strong", "under", "pads", "plucks")) -> bool:
    return any(instrument in getattr(piece.character, part, ()) for part in parts)


def lively_walk(piece: Piece, busy_from: float = 0.45) -> bool:
    """Walking music that has soft war drums (orchestra.Take: `lively`), by the rule of its day: busy from 0.45 until
    2026-11-18, from 0.35 since."""
    ch = piece.character
    if piece.style == "house" or getattr(ch, "role", "") != "wander":
        return False
    return (((ch.weight >= 0.6 and ch.busy >= 0.55) or (ch.weight >= 0.5 and ch.busy >= busy_from and not set(ch.grooves) <= set(DELICATE)))
            and not set(ch.grooves) & set(DANCE_GROOVES))


@dataclass(frozen=True)
class Change:
    name: str
    at: datetime.datetime           # when it reached the files the renders load
    commit: str
    what: str
    touches: Callable[[Piece], bool]


CHANGES = [
    Change("light levels and soft war drums", datetime.datetime(2026, 11, 17, 20, 40), "2ce1bdd",
           "light pieces' drums and bass nearer in all three desks; lively lighter walking music gets soft war drums",
           lambda p: bool(p.meta.get("light")) or lively_walk(p)),
    Change("a little harder, and the valley's pad", datetime.datetime(2026, 11, 17, 21, 52), "",
           "harder story levels for walking music and the desk's levels ('this is not world of fairy craft'), the valley's "
           "pad under the tune (the whine left when sitting), House's kick and bass",
           lambda p: True),
    Change("rowdy inns walk", datetime.datetime(2026, 11, 18, 1, 8), "ef907e1",
           "an inn of busy 0.6 or more takes the walking shape instead of the quiet room's",
           lambda p: p.style != "house" and p.character.role == "ember" and p.character.busy >= 0.6),
    Change("no tuba under a band", datetime.datetime(2026, 11, 18, 3, 45), "469a811",
           "the desk's low brass at the moments no longer doubles a band's bass (it read 8 to 15 dB over at 450 Hz-1.8 kHz)",
           lambda p: p.style == "knight" and bool(getattr(p.character, "band", False)) and not p.meta.get("light")),
    Change("the snow's plucks given a middle", datetime.datetime(2026, 11, 18, 4, 41), "97b2af4",
           "pizzicato for the glockenspiel, and a guitar at the frost camp (the all-bell accompaniment read 21 dB short in the middle)",
           lambda p: p.style != "house" and p.character.name in SNOW),
    Change("a real accordion", datetime.datetime(2026, 11, 18, 5, 19), "8b95ce3",
           "TinySOL's accordion for the harmonica that stood in for it (out of its range below C4, reedy)",
           lambda p: p.style != "house" and plays(p, "accordion")),
    Change("House's clap knocks", datetime.datetime(2026, 11, 18, 7, 16), "7820310",
           "the clap's and snare's knock lifted 3 dB at 900 Hz (3 to 6 dB short in every take)",
           lambda p: p.style == "house"),
    Change("the bagpipe's tunes on a real chanter", datetime.datetime(2026, 11, 18, 8, 18), "8759cca",
           "FreePats' chanter plays the bagpipe's tunes, chosen by ear; held drones stay the english horn",
           lambda p: p.style != "house" and plays(p, "bagpipe", ("leads", "strong", "under"))),
    Change("soft war drums for the slower light walks", datetime.datetime(2026, 11, 18, 8, 55), "",
           "the lighter walking music busy from 0.35 has soft war drums too (snowfall, mirage, frozen lake, desert shrine, ice fields)",
           lambda p: lively_walk(p, 0.35) and not lively_walk(p, 0.45)),
    Change("House's filters ride the story", datetime.datetime(2026, 11, 18, 9, 39), "",
           "the chords, pads and tune through a low-pass that opens as a track builds, is wide open at a drop and shuts for the "
           "breakdown; the bass's bottom taken away before a drop; the pump deeper at a drop, lighter in a theme; the hats 3 dB "
           "softer, the sixteenths between the eighths only at a drop ('too much high hat and not enough dynamic sound')",
           lambda p: p.style == "house"),
]


def code_dates() -> dict[str, datetime.datetime]:
    """When the code that made each staged take was loaded: its list's beginning, by the lane logs."""
    begun: dict[str, list[str]] = {}
    for lane_log in PASSES.glob("lane-*.log"):
        for line in lane_log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\d\d:\d\d:\d\d) begun (\S+) \(", line)
            if m:
                begun.setdefault(lane_log.stem + "/" + m.group(2), []).append(m.group(1))
    out: dict[str, datetime.datetime] = {}
    for log in sorted(list(PASSES.glob("lane-*/*.log")) + list(PASSES.glob("lane-*/*.log.carried")), key=lambda p: p.stat().st_mtime):
        ended = datetime.datetime.fromtimestamp(log.stat().st_mtime)
        dones = re.findall(r"(\d\d:\d\d:\d\d)\s+done\s+(\S+)\s.*?in (\d+) s", log.read_text(encoding="utf-8", errors="replace"))
        if not dones:
            continue
        name = log.parent.name + "/" + log.name.split(".log")[0]

        def dated(clock: str, before: datetime.datetime) -> datetime.datetime:
            at = datetime.datetime.combine(before.date(), datetime.time.fromisoformat(clock))
            return at - datetime.timedelta(days=1) if at > before + datetime.timedelta(minutes=1) else at

        first_done = min(dated(clock, ended) - datetime.timedelta(seconds=int(took)) for clock, _, took in dones)
        starts = [dated(clock, ended) for clock in begun.get(name, [])]
        starts = [at for at in starts if at <= first_done + datetime.timedelta(minutes=2)]
        start = max(starts) if starts else first_done
        for clock, key, took in dones:
            out[key] = start            # the latest run that made it wins (logs are read oldest first)
    return out


def pieces() -> list[Piece]:
    families = {fam.name: fam.character for fam, _ in build.plan()}
    families.update({fam.name: fam for fam in house.PLAN})
    found = []
    for style in ("knight", "warcraft", "house"):
        for path in sorted((STUDIO / style).glob("*/*/track.json")):
            family = path.parent.parent.name
            if family in families:
                found.append(Piece(style, family + "/" + path.parent.name, family, families[family],
                                   json.loads(path.read_text(encoding="utf-8"))))
    return found


def ledger() -> list[dict]:
    dates = code_dates()
    rows = []
    for piece in pieces():
        folder = STUDIO / piece.style / piece.key / "track.json"
        made = dates.get(piece.key) or datetime.datetime.fromtimestamp(folder.stat().st_mtime) - datetime.timedelta(minutes=30)
        lacks = [change.name for change in CHANGES if made < change.at and change.touches(piece)]
        if lacks:
            rows.append({"style": piece.style, "take": piece.key, "title": piece.meta.get("title", ""), "role": piece.meta.get("role", ""),
                         "kinds": list(piece.meta.get("moods") or []), "light": bool(piece.meta.get("light")),
                         "code_from": made.strftime("%Y-%m-%d %H:%M"), "lacks": lacks})
    return rows


def main() -> int:
    rows = ledger()
    total = len(pieces())
    by_style = {style: sum(1 for row in rows if row["style"] == style) for style in ("knight", "warcraft", "house")}
    print("%d of %d staged takes lack a change: %s" % (len(rows), total, ", ".join("%s %d" % kv for kv in by_style.items())))
    for change in CHANGES:
        print("  %-42s %4d takes" % (change.name, sum(1 for row in rows if change.name in row["lacks"])))
    if "--write" in sys.argv:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        (PASSES / "rerender-ledger.json").write_text(json.dumps({"written": stamp, "changes": [
            {"name": c.name, "at": c.at.strftime("%Y-%m-%d %H:%M"), "commit": c.commit, "what": c.what} for c in CHANGES],
            "takes": rows}, indent=1), encoding="utf-8")
        lines = ["# What the staged takes still lack (written %s)" % stamp, "",
                 "Re-rendering waits for the end, when the drive is full; until then this is kept up to date (`tools/rerender_ledger.py --write`).",
                 "%d of %d staged takes lack at least one change." % (len(rows), total), "", "## The changes", ""]
        for c in CHANGES:
            lines.append("- **%s** (%s%s): %s. Takes lacking it: %d." % (c.name, c.at.strftime("%Y-%m-%d %H:%M"), ", " + c.commit if c.commit else "",
                                                                       c.what, sum(1 for row in rows if c.name in row["lacks"])))
        for style in ("knight", "warcraft", "house"):
            mine = [row for row in rows if row["style"] == style]
            lines += ["", "## %s (%d)" % ({"knight": "Knight Rock", "warcraft": "Warcraft", "house": "House"}[style], len(mine)), "",
                      "| take | title | role | code from | lacks |", "|---|---|---|---|---|"]
            for row in sorted(mine, key=lambda r: r["take"]):
                lines.append("| %s | %s | %s | %s | %s |" % (row["take"], row["title"], row["role"], row["code_from"], "; ".join(row["lacks"])))
        (PASSES / "rerender-ledger.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("written:", PASSES / "rerender-ledger.json", PASSES / "rerender-ledger.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
