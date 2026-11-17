"""Studies real orchestral scores (the public-domain OpenScore orchestra in var/scores:
Beethoven, Brahms, Bruckner, Schubert, Haydn, Bach, Beach and others) for how the parts that the
studio's channels stand for move, so that the writer can be held against them:

- the bass (the lowest strings): notes to the bar, how often it repeats a note, moves by a step,
  or leaps, and how often a bar of it is like one heard before;
- the inner voices (violas, second violins): the same, and how often they hold a note through
  the bar;
- the texture: how many of the orchestra's parts play at once, how much that moves, and how
  many bars the same parts go on playing before the scoring changes;
- the percussion (timpani and the rest): in how many bars it plays.

Reads MusicXML directly (a plain reader, many times faster than music21 on a symphony).

    cd app && uv run --no-sync python ../tools/orchestra_study.py [how many scores]

Writes var/passes/orchestra-study.json and prints the figures.
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

VAR = Path(__file__).resolve().parents[1] / "var"
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def role_of(name: str) -> str:
    name = name.lower()
    if any(word in name for word in ("contrabass", "double bass", "kontrabass", "basso", "bässe", "basses")) or name.strip() in ("bass", "b.", "cb."):
        return "bass"
    if any(word in name for word in ("violoncell", "cello", "vc.")):
        return "cello"
    if any(word in name for word in ("viola", "bratsche", "vla")):
        return "viola"
    if "violin" in name or "violino" in name or name.startswith("vn") or "violine" in name:
        return "violin"
    if any(word in name for word in ("timpan", "pauke", "drum", "cymbal", "triangle", "percussion", "becken", "tamb")):
        return "percussion"
    return "other"


def read(path: Path) -> list[tuple[str, list[list[tuple[float, int | None, float]]]]]:
    """Every part of a score: its name and its bars, each bar its notes (onset in quarters, MIDI pitch, length)."""
    with zipfile.ZipFile(path) as packed:
        inner = next(name for name in packed.namelist() if name.endswith((".xml", ".musicxml")) and not name.startswith("META-INF"))
        root = ET.fromstring(packed.read(inner))
    names = {part.get("id"): (part.findtext("part-name") or "") for part in root.iter("score-part")}
    out = []
    for part in root.iter("part"):
        divisions, bars = 1, []
        for measure in part.iter("measure"):
            found, at, last_start = [], 0.0, 0.0
            for element in measure:
                if element.tag == "attributes" and element.findtext("divisions"):
                    divisions = int(float(element.findtext("divisions")))
                elif element.tag == "backup":
                    at -= float(element.findtext("duration") or 0) / divisions
                elif element.tag == "forward":
                    at += float(element.findtext("duration") or 0) / divisions
                elif element.tag == "note":
                    length = float(element.findtext("duration") or 0) / divisions
                    chord = element.find("chord") is not None
                    start = last_start if chord else at
                    if element.find("rest") is None:
                        pitch = element.find("pitch")
                        midi = None
                        if pitch is not None:
                            midi = 12 * (int(pitch.findtext("octave")) + 1) + STEPS[pitch.findtext("step")] + int(float(pitch.findtext("alter") or 0))
                        tied_in = any(tie.get("type") == "stop" for tie in element.findall("tie"))
                        if not tied_in:
                            found.append((start, midi, length))
                    if not chord:
                        last_start = at
                        at += length
            bars.append(found)
        out.append((names.get(part.get("id"), ""), bars))
    return out


def line_figures(bars: list[list[tuple[float, int | None, float]]]) -> dict | None:
    """How a single line moves: its lowest note at each onset."""
    notes, held, heard = [], 0, 0
    patterns = collections.Counter()
    for bar in bars:
        pitched = [(on, p, length) for on, p, length in bar if p is not None]
        if not pitched:
            continue
        heard += 1
        lowest = {}
        for on, p, length in pitched:
            lowest[on] = min(lowest.get(on, 999), p)
        notes += [lowest[on] for on in sorted(lowest)]
        if len(lowest) == 1 and max(length for _, _, length in pitched) >= 2.0:
            held += 1
        patterns[tuple(sorted((round(on, 2), p) for on, p, _ in pitched))] += 1
    if heard < 8 or len(notes) < 16:
        return None
    moves = [abs(b - a) for a, b in zip(notes, notes[1:])]
    return {"per_bar": len(notes) / heard, "repeat": sum(1 for m in moves if m == 0) / len(moves),
            "step": sum(1 for m in moves if 1 <= m <= 2) / len(moves), "skip": sum(1 for m in moves if 3 <= m <= 5) / len(moves),
            "leap": sum(1 for m in moves if m >= 6) / len(moves), "held": held / heard, "different_bars": len(patterns) / heard}


def study(path: Path) -> dict | None:
    parts = read(path)
    if len(parts) < 8:
        return None                                           # chamber music, not an orchestra
    bars = max(len(b) for _, b in parts)
    roles = [role_of(name) for name, _ in parts]
    playing = [frozenset(index for index, (_, b) in enumerate(parts) if bar < len(b) and any(p is not None for _, p, _ in b[bar]))
               for bar in range(bars)]
    counts = [len(each) / len(parts) for each in playing]
    runs, run = [], 1
    for before, now in zip(playing, playing[1:]):
        if now == before:
            run += 1
        else:
            runs.append(run)
            run = 1
    runs.append(run)
    figures = {}
    for role in ("bass", "cello", "viola", "violin"):
        lines = [line_figures(b) for (name, b), r in zip(parts, roles) if r == role]
        lines = [each for each in lines if each]
        if lines:
            figures[role] = {key: statistics.mean(each[key] for each in lines) for key in lines[0]}
    percussion = [index for index, r in enumerate(roles) if r == "percussion"]
    beating = sum(1 for each in playing if any(index in each for index in percussion)) / bars if percussion else None
    return {"score": path.parent.name, "parts": len(parts), "bars": bars, "at_once": statistics.mean(counts),
            "at_once_spread": statistics.pstdev(counts), "same_scoring_bars": statistics.mean(runs), "lines": figures,
            "percussion_bars": beating}


def main(argv: list[str]) -> int:
    limit = int(argv[0]) if argv else 80
    sources = sorted((VAR / "scores" / "openscore").glob("*/score.mxl"))[:limit]
    found = []
    for path in sources:
        try:
            result = study(path)
        except (ET.ParseError, KeyError, ValueError, StopIteration, zipfile.BadZipFile) as error:
            print("could not read %s: %s" % (path.parent.name, error))     # said, and passed over
            continue
        if not result:
            continue
        found.append(result)
        bass = result["lines"].get("bass") or result["lines"].get("cello") or {}
        print("%-30s %2d parts %4d bars | at once %3.0f%% (+-%2.0f) | same scoring %4.1f bars | bass %.1f/bar rep %2.0f%% step %2.0f%% leap %2.0f%% diff %2.0f%% | perc %s" % (
            result["score"][:30], result["parts"], result["bars"], 100 * result["at_once"], 100 * result["at_once_spread"],
            result["same_scoring_bars"], bass.get("per_bar", 0), 100 * bass.get("repeat", 0), 100 * bass.get("step", 0), 100 * bass.get("leap", 0),
            100 * bass.get("different_bars", 0), "%.0f%%" % (100 * result["percussion_bars"]) if result["percussion_bars"] is not None else "-"))
    if not found:
        return 1
    summary = {"scores": len(found), "at_once": statistics.mean(r["at_once"] for r in found),
               "at_once_spread": statistics.mean(r["at_once_spread"] for r in found),
               "same_scoring_bars": statistics.median(r["same_scoring_bars"] for r in found),
               "percussion_bars": statistics.mean(r["percussion_bars"] for r in found if r["percussion_bars"] is not None)}
    for role in ("bass", "cello", "viola", "violin"):
        rows = [r["lines"][role] for r in found if role in r["lines"]]
        if rows:
            summary[role] = {key: round(statistics.mean(row[key] for row in rows), 3) for key in rows[0]}
    (VAR / "passes").mkdir(parents=True, exist_ok=True)
    (VAR / "passes" / "orchestra-study.json").write_text(json.dumps({"summary": summary, "scores": found}, indent=1), encoding="utf-8")
    print("\nacross %d orchestral movements:" % len(found))
    print("  share of the orchestra playing in a bar: %.0f%%, moving by %.0f%% about that" % (100 * summary["at_once"], 100 * summary["at_once_spread"]))
    print("  the same instruments go on playing for %.1f bars (median) before the scoring changes" % summary["same_scoring_bars"])
    print("  the percussion plays in %.0f%% of the bars" % (100 * summary["percussion_bars"]))
    for role in ("bass", "cello", "viola", "violin"):
        if role in summary:
            s = summary[role]
            print("  %-6s %.1f notes/bar; repeats %.0f%%, steps %.0f%%, skips %.0f%%, leaps %.0f%%; holds a bar %.0f%%; different bars %.0f%%" % (
                role, s["per_bar"], 100 * s["repeat"], 100 * s["step"], 100 * s["skip"], 100 * s["leap"], 100 * s["held"], 100 * s["different_bars"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
