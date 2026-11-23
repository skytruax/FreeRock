"""A track's music sheet: read, revised and performed (2026-11-18: "the music sheet should be a separate concept and
asset for every track, and updating it should be the golden rule", "remember your music sheets are your core principal
and most important asset").

Every staged track keeps its sheet beside its recordings (var/studio/<style>/<family>/<take>/sheet.json), with every
revision it replaced (sheet.r<N>.json). A song is made better by revising its sheet (a part re-voiced, a passage
varied, an effect marked where the music asks for it), saying why in its history (`Sheet.revised`), and performing it
again; what a performance needs that is not music is the desk's business.

    cd app && uv run --no-sync --with numba python -m freerock.studio.sheet show knight/infernal-forge-anthem-1/3
    ... perform knight/infernal-forge-anthem-1/3       plays the take's sheet again and stages what it makes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import stage_root
from .score import EFFECTS, Sheet

VAR = Path(__file__).resolve().parents[3] / "var"
NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
SHORT = {"wah": "w", "wah depth": "", "wah position": "", "phaser": "p", "flanger": "f", "flanger depth": "", "flanger position": "",
         "echo": "e", "lowpass": "l", "highpass": "h", "bend": "b"}
assert set(SHORT) == set(EFFECTS)


def path_of(key: str) -> Path:
    """The sheet of a staged take: "knight/infernal-forge-anthem-1/3"."""
    style, family, take = key.strip("/").split("/")
    return stage_root(VAR, style) / family / take / "sheet.json"


def revised_of(style: str, family: str, take: int) -> Sheet | None:
    """A song's sheet if a musician has revised it since the writer's first draft: that is what the song is, and whoever stages it
    again performs it as it stands. None for a first draft (written again, so that a change in the writer reaches it) and for a
    song with no sheet."""
    path = path_of("%s/%s/%d" % (style, family, take))
    if not path.is_file():
        return None
    sheet = Sheet.load(path)
    return sheet if sheet.revision > 1 else None


def note_name(pitch: int) -> str:
    return "%s%d" % (NAMES[pitch % 12], pitch // 12 - 1)


def _marked_in(points: list[tuple[float, float]], first: float, last: float, effect: str) -> bool:
    """Whether a mark is in (or moving) anywhere in a stretch: a pedal more than a little way in, a filter off open."""
    if not points:
        return False
    import numpy as np
    times = [at for at, _ in points]
    values = [value for _, value in points]
    inside = [value for at, value in points if first <= at < last]
    probe = [float(np.interp(first + (last - first) * share, times, values)) for share in (0.1, 0.5, 0.9)] + inside
    if effect == "lowpass":
        return min(probe) < 12000.0
    if effect == "highpass":
        return max(probe) > 40.0
    if effect == "bend":
        return max(abs(value) for value in probe) > 0.05
    return max(probe) > 0.05


def show(sheet: Sheet) -> str:
    """The sheet as a musician reads it at a glance: the form across the top; for each part, how many notes it plays a
    bar in each section (blank where it rests) and which effects are marked there (w a wah, p a phaser, f a flanger, e an
    echo thrown, l the low-pass closed, h the high-pass in, b notes bent); then the history."""
    lines = ["%s (%s/%s/%d), revision %d: %g to the minute, %g beats a bar, %d bars" % (
        sheet.title, sheet.style, sheet.family, sheet.take, sheet.revision, sheet.tempo, sheet.beats, sheet.bars)]
    heads = ["%s %d" % (section.get("part") or section["story"], section["bars"]) for section in sheet.form]
    width = max(9, max(len(head) for head in heads) + 1)
    lines.append("%-34s %s" % ("", "".join(head.ljust(width) for head in heads)))
    for channel, parts in sheet.parts.items():
        for name, part in parts.items():
            if not part.notes:
                continue
            cells = []
            for section in sheet.form:
                first = section["first"] * sheet.beats
                last = first + section["bars"] * sheet.beats
                count = sum(1 for note in part.notes if first <= note.start < last)
                marks = "".join(SHORT[effect] for effect, points in sorted(part.effects.items())
                                if SHORT[effect] and _marked_in(points, first, last, effect))
                cells.append(("%.1f" % (count / section["bars"]) if count else "") + (" " + marks if marks else ""))
            low, high = min(note.pitch for note in part.notes), max(note.pitch for note in part.notes)
            label = "%s/%s" % (channel, name)
            span = "" if part.drums else " %s-%s" % (note_name(low), note_name(high))
            lines.append("%-34s %s" % ((label + span)[:34], "".join(cell.ljust(width) for cell in cells)))
    lines.append("history:")
    for entry in sheet.history:
        lines.append("  r%d %s, %s: %s (%s)" % (entry["revision"], entry["when"], entry["by"], entry["what"], entry["why"]))
    return "\n".join(lines)


def perform(sheet: Sheet) -> dict:
    """Plays a sheet and stages what it makes, as its style's desk does (studio.club for House, studio.build for the
    orchestra and the band)."""
    if sheet.style == "house":
        from . import club
        return club.perform(sheet)
    from . import build
    return build.perform(sheet)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read or perform a track's music sheet.")
    parser.add_argument("what", choices=("show", "perform"))
    parser.add_argument("take", help='a staged take ("knight/infernal-forge-anthem-1/3") or a sheet file')
    args = parser.parse_args(argv)
    path = Path(args.take) if args.take.endswith(".json") else path_of(args.take)
    sheet = Sheet.load(path)
    if args.what == "show":
        print(show(sheet))
        return 0
    from . import reaper
    reaper.configure()
    found = perform(sheet)
    print("%s/%s/%d %s: performed from revision %d" % (sheet.style, sheet.family, sheet.take, sheet.title, sheet.revision))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
