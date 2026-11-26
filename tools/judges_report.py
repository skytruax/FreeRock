"""What the judges say for the next pass to work on (2026-11-19: "looks like your scores went down in some places put into
the loop ways to work on each score with each pass"). From var/passes/judged3.jsonl (tools/judges.py), for each style:

- every score across its takes, and the takes lowest on each;
- the part of the story each score falls lowest in, across the takes (where a style's songs weaken);
- each change's before and after (a demo's two folders, "before-<change>" and "<change>"), and every score that moved by more
  than its judge's noise (TuneJury 0.05, SongEval 0.08, Audiobox 0.15): a fall is a target for the next pass;
- the targets, first the falls, then the weakest part, then the weakest score, each with the levers that answer it
  (docs/songwriting.md 7.7, the README's "How the songs are judged").

    python3 tools/judges_report.py [knight|warcraft|house]
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

VAR = Path(__file__).resolve().parents[1] / "var"
NOISE = {"TuneJury": 0.05, "TuneJury plain": 0.05, "musicality": 0.08, "memorability": 0.08, "coherence": 0.08, "clarity": 0.08,
         "enjoyment": 0.15, "quality": 0.15}
LEVERS = {
    "TuneJury": "the style's own sound forward in that part; the part's energy right for its role; an ending that lands",
    "TuneJury plain": "as TuneJury, and the desk",
    "musicality": "the tune's shape and the chords; the counter-melody",
    "memorability": "the theme's opening at every moment; a riff of the song's own; fewer unrelated figures",
    "coherence": "variations of one idea rather than many (a song's fills from one figure); smooth ways between parts",
    "clarity": "stops and fills into each part; contrast between parts",
    "enjoyment": "the desk: balance, tone, punch",
    "quality": "the desk: nothing harsh or muddy, a clear top",
}


# Targets already worked on, by (change, score): what answered each. A target answered is listed with its answer and not
# taken again until a new pair of that change says it still falls.
ANSWERED = {
    ("licks", "coherence"): "the second turn a variation of the first (2026-11-19, 50afba7)",
    ("licks", "musicality"): "the second turn a variation of the first (2026-11-19, 50afba7)",
}


def scores(record: dict) -> dict[str, float]:
    song, box = record["songeval"], record["audiobox"]["mean"]
    return {"TuneJury": record["tunejury"]["brief"], "TuneJury plain": record["tunejury"]["plain"],
            "musicality": song["Musicality"], "memorability": song["Memorability"], "coherence": song["Coherence"],
            "clarity": song["Clarity"], "enjoyment": box["CE"], "quality": box["PQ"]}


def part_scores(record: dict) -> dict[str, dict[str, float]]:
    out = {}
    for part, tune in record["tunejury"]["parts"].items():
        box = record["audiobox"]["parts"].get(part, {})
        out[part] = {"TuneJury": tune["brief"], "TuneJury plain": tune["plain"], "enjoyment": box.get("CE"), "quality": box.get("PQ")}
    return out


def change_of(folder: str) -> tuple[str, str] | None:
    """("climb", "before") for .../studio-demo/before-climb/..., ("climb", "after") for .../studio-demo/climb/..."""
    if "/studio-demo/" not in folder:
        return None
    kind = folder.split("/studio-demo/")[1].split("/")[0]
    return (kind[len("before-"):], "before") if kind.startswith("before-") else (kind, "after")


def main(argv: list[str]) -> int:
    only = argv[1] if len(argv) > 1 else ""
    every = [json.loads(line) for line in (VAR / "passes" / "judged3.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in every if "tunejury" in row and "audiobox" in row]
    if len(rows) < len(every):
        print("(%d records of SongEval alone, made for the gate, are not in this report: tools/gate.py reads them)" % (len(every) - len(rows)))
    styles = sorted({row["style"] for row in rows if not only or row["style"] == only})
    for style in styles:
        mine = [row for row in rows if row["style"] == style]
        staged = {}
        for row in mine:
            if change_of(row["folder"]) is None:
                staged[row["folder"]] = row                      # the latest record of each staged take
        print("== %s: %d records, %d staged takes" % (style, len(mine), len(staged)))
        targets = []
        # Each change's before and after.
        pairs: dict[tuple[str, str], dict[str, dict]] = {}
        for row in mine:
            found = change_of(row["folder"])
            if found:
                pairs.setdefault((found[0], row["take"]), {})[found[1]] = row
        falls: dict[tuple[str, str], list[tuple[float, str]]] = {}
        for (change, take), sides in sorted(pairs.items()):
            if "before" not in sides or "after" not in sides:
                continue
            before, after = scores(sides["before"]), scores(sides["after"])
            moved = {name: after[name] - before[name] for name in before if abs(after[name] - before[name]) > NOISE[name]}
            text = ", ".join("%s %+.2f" % (name, delta) for name, delta in moved.items()) or "nothing beyond the noise"
            print("   %-12s %-28s %s" % (change, sides["after"]["title"][:28], text))
            for name, delta in moved.items():
                if delta < 0:
                    falls.setdefault((change, name), []).append((delta, sides["after"]["title"]))
        # A fall is a target where it shows on two takes, or on one by twice the judge's noise (2026-11-19: two demos of one
        # take, the same notes in SongEval's two minutes, came back 0.08 apart when the accompaniment's draws had moved).
        for (change, name), found in sorted(falls.items()):
            worst = min(delta for delta, _ in found)
            titles = ", ".join(title for _, title in found)
            if (change, name) in ANSWERED:
                print("   (answered: %s fell up to %.2f after %s; %s)" % (name, -worst, change, ANSWERED[(change, name)]))
            elif len(found) >= 2 or -worst > 2 * NOISE[name]:
                targets.append((0, "%s fell up to %.2f after %s (%s): %s" % (name, -worst, change, titles, LEVERS[name])))
            else:
                print("   (watch: %s fell %.2f after %s on %s alone, within twice its noise)" % (name, -worst, change, titles))
        pool = list(staged.values()) or mine
        # The part of the story each score falls lowest in.
        by_part: dict[str, dict[str, list[float]]] = {}
        for row in pool:
            for part, values in part_scores(row).items():
                for name, value in values.items():
                    if value is not None:
                        by_part.setdefault(name, {}).setdefault(part, []).append(value)
        for name in ("TuneJury", "enjoyment"):
            if name in by_part:
                means = {part: statistics.mean(values) for part, values in by_part[name].items()}
                weakest = min(means, key=means.get)
                print("   %-12s by part: %s; weakest: %s" % (name, " ".join("%s %.2f" % kv for kv in means.items()), weakest))
                targets.append((1, "%s lowest in the %s (%.2f against %.2f at best): %s" % (
                    name, weakest, means[weakest], max(means.values()), LEVERS[name])))
        # The weakest score: each score's spread, and the takes lowest on it.
        all_scores = {name: [(scores(row)[name], row["title"]) for row in pool] for name in NOISE}
        for name, values in all_scores.items():
            low = min(values)
            print("   %-14s median %+.2f, lowest %s %+.2f" % (name, statistics.median(v for v, _ in values), low[1], low[0]))
        for priority, text in sorted(targets)[:4]:
            print("   TARGET: " + text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
