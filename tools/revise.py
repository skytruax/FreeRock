"""Revises a staged song's music sheet and has it performed again (docs/songwriting.md 0.2, the standing cycle's old songs): a
change to the music, made as a musician would, written into the sheet's history with why, and the take before it kept beside it
so that the two can be heard and judged at one loudness; it stays only if the numbers and the judges agree it is better.

    cd app && uv run --no-sync --with numba python ../tools/revise.py knight/anywhere-barroom-blues-2/2 --recipe <file> [--dry]
        the recipe is a Python file with `revise(sheet) -> (what, why)`, which changes the sheet it is given; --dry changes
        nothing on the drive and says what it would change; --later changes the sheet and keeps the take of before, and leaves the
        performing to the next list that comes to the song (a night's lane, with the renders' processors)
    ... revise.py knight/anywhere-barroom-blues-2/2 --back
        puts the take as it was before the revision back, and its sheet's

A revised sheet is what the song is: a lane that comes to the song again (a list of it, a re-render) performs the revised sheet,
not a new first draft (`studio.sheet.revised_of`).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

from freerock.studio import sheet as sheets
from freerock.studio.score import Sheet

VAR = sheets.VAR


def recipe_of(path: Path):
    spec = importlib.util.spec_from_file_location("recipe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.revise


def counts(sheet: Sheet) -> dict[str, tuple[int, float]]:
    """Every part's notes and how loud they are on average, for saying what a revision moved."""
    out = {}
    for channel, parts in sheet.parts.items():
        for name, voice in parts.items():
            if voice.notes:
                out["%s: %s" % (channel, name)] = (len(voice.notes), sum(note.loud for note in voice.notes) / len(voice.notes))
    return out


def played(sheet: Sheet) -> dict[str, tuple]:
    """What each part is played by and every note of it, to see that a change is one though it leaves the count of notes and their strength as they were (a chord's third, 2026-11-25; a voice)."""
    return {"%s: %s" % (channel, name): (voice.instrument, tuple((round(note.start, 4), round(note.length, 4), note.pitch, round(note.loud, 4)) for note in voice.notes))
            for channel, parts in sheet.parts.items() for name, voice in parts.items() if voice.notes}


def before_of(track: str) -> Path:
    return VAR / "studio-demo" / "before-revise" / track


def revised(track: str, recipe) -> tuple[Sheet, str, str, list[str]]:
    """The song's sheet with the recipe's change in it (nothing saved), what it is, why, and the parts it moved."""
    sheet = Sheet.load(sheets.path_of(track))
    had, was = counts(sheet), played(sheet)
    what, why = recipe(sheet)
    sheet.revised(what, why, by="the musician")
    now, plays = counts(sheet), played(sheet)
    moved = []
    for name in sorted(set(had) | set(now)):
        a, b = had.get(name, (0, 0.0)), now.get(name, (0, 0.0))
        if a[0] != b[0] or abs(a[1] - b[1]) > 1e-9:
            moved.append("%-34s %d notes at %.2f -> %d notes at %.2f" % (name, a[0], a[1], b[0], b[1]))
        elif was.get(name) != plays.get(name):
            moved.append("%-34s %d notes, other pitches or another voice" % (name, b[0]))
    if not moved:
        raise ValueError("The recipe changed nothing in %s" % track)
    return sheet, what, why, moved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revise a song's music sheet and perform it again.")
    parser.add_argument("track", help="style/family/take")
    parser.add_argument("--recipe", help="a Python file with revise(sheet) -> (what, why)")
    parser.add_argument("--dry", action="store_true", help="say what would change; change nothing")
    parser.add_argument("--later", action="store_true", help="change the sheet now; the next list that comes to the song performs it")
    parser.add_argument("--back", action="store_true", help="put the take of before the revision back")
    args = parser.parse_args(argv)
    folder = sheets.path_of(args.track).parent
    kept = before_of(args.track)
    if args.back:
        if not (kept / "track.json").is_file():
            raise FileNotFoundError("Nothing is kept from before the revision of %s (%s)" % (args.track, kept))
        for path in kept.iterdir():
            shutil.copy2(path, folder / (path.name + ".back"))
            (folder / (path.name + ".back")).replace(folder / path.name)
        print("%s: the take of before its revision is back" % args.track)
        return 0
    if not args.recipe:
        parser.error("say which recipe, or --back")
    sheet, what, why, moved = revised(args.track, recipe_of(Path(args.recipe)))
    print("%s, revision %d: %s (%s)" % (args.track, sheet.revision, what, why))
    print("\n".join("  " + row for row in moved))
    if args.dry:
        return 0
    # The take as it is, kept whole (copied, not linked: the performance writes over the files it has).
    if not (kept / "track.json").is_file():
        kept.mkdir(parents=True, exist_ok=True)
        for path in folder.iterdir():
            if path.suffix == ".flac" or path.name in ("track.json", "sheet.json", "measured.json"):
                shutil.copy2(path, kept / path.name)
    if args.later:
        sheet.save(sheets.path_of(args.track))
        print("%s: its sheet is revised and the take of before kept; the next list that comes to it performs it" % args.track)
        return 0
    from freerock.studio import reaper
    reaper.configure()
    made = sheets.perform(sheet)
    print("performed: %s" % json.dumps({key: value for key, value in made.items() if key in ("title", "seconds", "problems")}, ensure_ascii=False))
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
