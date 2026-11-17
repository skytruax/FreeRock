"""Studies real orchestral scores (the public-domain ones in var/scores: Beethoven, Brahms,
Dvorak, Bruckner, Bach, Beach and others) for how an orchestra is used, so that the studio's
writing can be held against them: how many instruments sound at once and how that moves; how
often the texture changes (which instruments are playing); what share of the bars each family
plays in; how often the tune is doubled, and by what; how wide the gap is between the bass and
the voice above it, against the gap at the top of the chord; how often the dynamics change.

    cd app && uv run --no-sync --with music21 python ../tools/orchestra_study.py [how many scores]

Writes var/passes/orchestra-study.json and prints the figures.
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

VAR = Path(__file__).resolve().parents[1] / "var"
FAMILIES = (("woodwinds", ("flute", "piccolo", "oboe", "english horn", "cor anglais", "clarinet", "bassoon", "contrabassoon")),
            ("brass", ("horn", "trumpet", "trombone", "tuba", "cornet")),
            ("percussion", ("timpani", "drum", "cymbal", "triangle", "percussion", "glockenspiel", "bells")),
            ("harp and keys", ("harp", "piano", "celesta", "organ", "harpsichord")),
            ("voices", ("soprano", "alto", "tenor", "bass voice", "choir", "chorus", "voice")),
            ("strings", ("violin", "viola", "violoncello", "cello", "contrabass", "double bass", "bass")))


def family_of(name: str) -> str:
    name = name.lower()
    for family, words in FAMILIES:
        if any(word in name for word in words):
            return family
    return "other"


def study(path: Path) -> dict | None:
    from music21 import converter, dynamics, note, chord as m21chord
    score = converter.parse(str(path))
    parts = list(score.parts)
    if len(parts) < 6:
        return None                                    # a solo or a small group: not an orchestra
    bars = max(len(part.getElementsByClass("Measure")) for part in parts)
    sounding = [set() for _ in range(bars)]           # which parts play in each bar
    pitches = [collections.defaultdict(list) for _ in range(bars)]       # bar -> part -> pitches
    dynamic_marks = 0
    for index, part in enumerate(parts):
        name = (part.partName or part.instrumentName or "") if hasattr(part, "partName") else ""
        for number, measure in enumerate(part.getElementsByClass("Measure")):
            if number >= bars:
                break
            for element in measure.recurse().notes:
                sounding[number].add(index)
                if isinstance(element, note.Note):
                    pitches[number][index].append(element.pitch.midi)
                elif isinstance(element, m21chord.Chord):
                    pitches[number][index].extend(p.midi for p in element.pitches)
            dynamic_marks += len(list(measure.recurse().getElementsByClass(dynamics.Dynamic)))
    names = [(part.partName or "") for part in parts]
    families = [family_of(name) for name in names]
    at_once = [len(each) for each in sounding]
    changes = sum(1 for a, b in zip(sounding, sounding[1:]) if a != b)
    share = collections.defaultdict(list)
    for index, family in enumerate(families):
        share[family].append(sum(1 for each in sounding if index in each) / max(bars, 1))
    doubled, gaps_low, gaps_high = [], [], []
    for bar in pitches:
        tops = {part: max(found) for part, found in bar.items() if found}
        if len(tops) < 2:
            continue
        melody = max(tops.values())
        doubled.append(sum(1 for value in tops.values() if value != melody and (melody - value) % 12 == 0 and melody - value <= 24))
        lows = sorted(min(found) for found in bar.values() if found)
        everything = sorted({p for found in bar.values() for p in found})
        if len(lows) >= 2:
            gaps_low.append(lows[1] - lows[0])
        if len(everything) >= 3:
            gaps_high.append(everything[-1] - everything[-2])
    return {"score": path.stem, "parts": len(parts), "bars": bars, "at_once": statistics.mean(at_once) / len(parts),
            "at_once_spread": (statistics.pstdev(at_once) / len(parts)) if len(at_once) > 1 else 0.0,
            "texture_change_every": bars / max(changes, 1),
            "share": {family: statistics.mean(values) for family, values in share.items()},
            "octave_doublings": statistics.mean(doubled) if doubled else 0.0,
            "gap_at_bottom": statistics.mean(gaps_low) if gaps_low else 0.0, "gap_at_top": statistics.mean(gaps_high) if gaps_high else 0.0,
            "dynamics_per_100_bars": 100.0 * dynamic_marks / max(bars, 1) / len(parts)}


def main(argv: list[str]) -> int:
    limit = int(argv[0]) if argv else 40
    sources = sorted((VAR / "scores").rglob("*.mxl"))[:limit]
    found = []
    for path in sources:
        try:
            result = study(path)
        except Exception as error:                  # a score music21 cannot read is said and passed over
            print("could not read %s: %s" % (path.name, str(error)[:120]))
            continue
        if result:
            found.append(result)
            print("%-34s %2d parts %4d bars | at once %3.0f%% (spread %2.0f%%) | texture changes every %.1f bars | octave doublings %.1f | gaps bottom %4.1f top %4.1f" % (
                result["score"][:34], result["parts"], result["bars"], 100 * result["at_once"], 100 * result["at_once_spread"],
                result["texture_change_every"], result["octave_doublings"], result["gap_at_bottom"], result["gap_at_top"]))
    if not found:
        return 1
    families = collections.defaultdict(list)
    for result in found:
        for family, value in result["share"].items():
            families[family].append(value)
    summary = {"scores": len(found),
               "at_once": statistics.mean(r["at_once"] for r in found), "at_once_spread": statistics.mean(r["at_once_spread"] for r in found),
               "texture_change_every": statistics.median(r["texture_change_every"] for r in found),
               "octave_doublings": statistics.mean(r["octave_doublings"] for r in found),
               "gap_at_bottom": statistics.mean(r["gap_at_bottom"] for r in found), "gap_at_top": statistics.mean(r["gap_at_top"] for r in found),
               "dynamics_per_100_bars": statistics.mean(r["dynamics_per_100_bars"] for r in found),
               "share_of_bars": {family: statistics.mean(values) for family, values in families.items()}}
    (VAR / "passes").mkdir(parents=True, exist_ok=True)
    (VAR / "passes" / "orchestra-study.json").write_text(json.dumps({"summary": summary, "scores": found}, indent=1), encoding="utf-8")
    print("\nacross %d orchestral scores:" % len(found))
    print("  part of the orchestra playing at once: %.0f%% on average, moving by %.0f%% from bar to bar" % (100 * summary["at_once"], 100 * summary["at_once_spread"]))
    print("  the texture (who plays) changes every %.1f bars (median)" % summary["texture_change_every"])
    print("  the top line doubled at the octave or two by %.1f other parts on average" % summary["octave_doublings"])
    print("  gap between the two lowest parts %.1f semitones; between the two highest notes %.1f" % (summary["gap_at_bottom"], summary["gap_at_top"]))
    print("  dynamic marks per part per 100 bars: %.1f" % summary["dynamics_per_100_bars"])
    print("  share of bars each family plays in: %s" % ", ".join("%s %.0f%%" % (f, 100 * v) for f, v in sorted(summary["share_of_bars"].items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
