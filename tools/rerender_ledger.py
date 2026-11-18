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
    # (A first House rework, the filters ridden by one rule for every track, reached the files at 09:39 and was replaced
    # by the one below before any House take was made with it: House's lists were held.)
    Change("a music sheet of its own", datetime.datetime(2026, 11, 18, 10, 44), "",
           "every take written down whole as its music sheet beside its recordings, the golden rule ('the music sheet should be "
           "a separate concept and asset for every track'); a take made before has none until it is performed again",
           lambda p: True),
    Change("a reed does not hold the valley's drone", datetime.datetime(2026, 11, 18, 11, 41), "",
           "in the valley a reed's drone (the english horn's pipe drone, a bagpipe, an accordion, a harmonica) goes to the other "
           "pad, an organ's or the strings'; and the pipe drone plays down to its own E3 ('sometimes when one synth stays in when "
           "youre sitting its whiny': King's Oath's valley drone stood 9 dB over the tune, now 2 under)",
           lambda p: p.style != "house" and any(pad in ("pipe drone", "bagpipe", "accordion", "harmonica") for pad in getattr(p.character, "pads", ()))),
    Change("House's lead a riff, its synths bigger", datetime.datetime(2026, 11, 18, 11, 41), "",
           "the tune written as a riff (cells of three sixteenths, every note on the chord) on a pluck and a big synth, its echo "
           "thrown at each phrase's end and a phaser and a second synth in a drop's second half; the synths' low cuts eased and "
           "spread wider ('the lead is still lame', 'it sounds hollow and generic in the synths')",
           lambda p: p.style == "house"),
    Change("House written as sheets, its effects marked by the music", datetime.datetime(2026, 11, 18, 10, 44), "",
           "each part's low-pass follows its notes' brightness (the theme darker than the drop, the breakdown shut), the sub out "
           "of each rise and the breakdown, a rise's last beats thinned from the bottom, the hats on a dry line of their own and "
           "softer, the pump deeper at a drop ('too much high hat and not enough dynamic sound', 'this is boring generic crap')",
           lambda p: p.style == "house"),
    Change("House's drops change, its lead chosen by ear and number", datetime.datetime(2026, 11, 18, 12, 50), "",
           "the groove changes every sixteen bars and a drop builds block by block (the boredom meter: the drums had sounded the "
           "same for 40 bars); the drop's lead Argitoth's Trance Lead 1, the nearest of nine to the liked house leads, its last "
           "sixteen bars answered phrase by phrase, the chords phased there; MuseScore's chords given a gentler top of their own",
           lambda p: p.style == "house"),
    Change("the band's 1970s pedals", datetime.datetime(2026, 11, 18, 14, 47), "",
           "a band's guitars marked where their own notes ask: a jet flanged by hand into an arrival, a wah rocked through a "
           "running solo, a cry across a long note, a vibe in the valley, a phaser on strummed chords where a passage comes back "
           "('guitars should have effects in the 70s bro')",
           lambda p: p.style == "knight" and any(name in getattr(p.character, part, ()) for part in ("leads", "plucks", "strong")
                                                  for name in ("lead guitar", "rhythm guitar", "guitar"))),
    Change("an orchestra's effects that move", datetime.datetime(2026, 11, 18, 14, 47), "",
           "the valley's string and choir pads further off, closing their top and opening at the climb; a harp's, a celesta's, "
           "the bells' last note of each phrase left to hang in an echo ('this might apply to other genres too')",
           lambda p: p.style == "warcraft"),
    Change("a band's rises and drums that move", datetime.datetime(2026, 11, 18, 15, 59), "",
           "a long rise opened on the rhythm guitar's wah by hand; the drummer's cymbal turned every sixteen bars of a theme (the "
           "hat, then the ride; the ride over a groove of the toms) and a heavy band's long moment ridden out on the bell (the "
           "boredom meter: a battle piece's rhythm one colour through a 36-bar rise, its drums one groove through a theme)",
           lambda p: p.style == "knight" and p.character.band),
    Change("House's bass grows harsher through a long drop", datetime.datetime(2026, 11, 18, 15, 59), "",
           "a harsher twin of the bass on its own notes through the second half of every drop of 32 bars or more, in over "
           "eight bars (deadmau5's 'Turning Point'; the boredom meter: Moonwell's bass one colour through 44 bars of a drop)",
           lambda p: p.style == "house" and p.character.role not in ("ember", "night", "camp")),
    Change("House's drawbar organ; the open top for the big synths alone", datetime.datetime(2026, 11, 18, 16, 59), "",
           "the chords' organ the LinnStrument set's Drawbar Organ 1 (Surge's House Organ, loudest two octaves over its note, had "
           "put them 23 to 34 dB over the liked at the top); the open top asked for the saw kept to the drop's saw and super, "
           "the calm melodies and the quiet pluck back to the gentler top",
           lambda p: p.style == "house"),
    Change("House's chord roll climbs to the drop", datetime.datetime(2026, 11, 18, 17, 22), "",
           "the chords' roll into a drop softer as it comes faster, no louder than the drop; none in a calm piece (Cold Stars "
           "I's bell had rung 6 dB over its drop)",
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
