"""Out with a style's old written pieces, in with what is staged now.

    cd app && uv run --no-sync python ../tools/fresh_bucket.py warcraft          (the server must be stopped)
    cd app && uv run --no-sync python ../tools/fresh_bucket.py knight --keep-style
    cd app && uv run --no-sync python ../tools/fresh_bucket.py house --zone "Elwynn Forest"   (a style with no bucket yet: begun at that zone's tempo and key)

    ... fresh_bucket.py knight --beside     builds it beside the one that plays; the server runs on
    ... fresh_bucket.py knight --swap       puts that one in its place (the server must be stopped: seconds)
    ... fresh_bucket.py knight --swap-back  puts the one before it back (the server must be stopped)

When the way the studio's tracks are played changes for the better, the bucket should hold
only the new ones: this takes every written piece whose source begins with "<style>/" out of
the style's bucket for good, then puts every staged track of the style in, and makes the style
the one in force (with `--keep-style` the style in force is left
as it is: a second style is made ready while the first goes on being played). `freerock pieces
drop` does the first part too, but saves the bucket after every piece, which for two thousand
pieces is minutes; here it is saved once.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from freerock import pieces

VAR = Path(__file__).resolve().parents[1] / "var"
PORT = int(os.environ.get("FREEROCK_PORT", "8765"))


def beside(style: str) -> int:
    bucket, done = pieces.build_beside(VAR, style)
    after = pieces.summary(bucket)
    print("%s: %d tracks put in; the bucket now has %d pieces in %d tracks, %.0f minutes" % (
        style, done["put"], after["pieces"], after["tracks"], after["minutes"]))
    print("%s: %d of them as they were (their recordings linked), %d cut from what is staged" % (
        style, done["taken"], done["put"] - done["taken"]))
    print("%s: %d parts kept what they had been: their plays, loves and bans (%d had any)" % (style, done["carried"], done["marks"]))
    print("%s: built beside the one that plays, in %s" % (style, bucket.folder))
    for folder, problem in done["wrong"]:
        print("NOT put in: %s: %s" % (folder, problem))
    return 1 if done["wrong"] else 0


def main(argv: list[str]) -> int:
    for flag, does in (("--beside", beside), ("--swap", pieces.swap), ("--swap-back", pieces.swap_back)):
        if flag not in argv:
            continue
        argv = [each for each in argv if each not in (flag, "--keep-style")]
        if len(argv) != 1 or argv[0].startswith("-"):
            print(__doc__)
            return 2
        if flag == "--beside":
            return beside(argv[0])
        if pieces.server_is_up(PORT):
            print("The FreeRock server is running (port %d): stop it first, it keeps the buckets in memory." % PORT)
            return 1
        print("%s: %s" % (argv[0], "the bucket built beside is in its place; the one before it is kept in" if flag == "--swap" else
                          "the bucket as it was is back in its place; the one that was swapped in is in"), does(VAR, argv[0]))
        return 0
    keep = "--keep-style" in argv
    argv = [each for each in argv if each != "--keep-style"]
    zone = None
    if "--zone" in argv:
        # A style with no bucket yet (the drive was cleared, 2026-11-16, night) begins one at this zone's tempo and
        # key. It is named "all" all the same (forever.ALL): the song goes wherever the player goes.
        at = argv.index("--zone")
        zone = argv[at + 1]
        argv = argv[:at] + argv[at + 2:]
    if len(argv) != 1:
        print(__doc__)
        return 2
    style = argv[0]
    if pieces.server_is_up(PORT):
        print("The FreeRock server is running (port %d): stop it first, it keeps the buckets in memory." % PORT)
        return 1
    bucket = pieces.home_bucket(VAR, style, zone)
    before = pieces.summary(bucket)
    marks = pieces.marks_of(bucket)               # what was played, loved and banned, given back once the tracks are in again
    save = bucket._save
    bucket._save = lambda: None                    # saved once, when every piece is out
    try:
        gone = pieces.drop_from(bucket, style + "/")
    finally:
        bucket._save = save
    bucket._save()
    print("%s: %d old pieces taken out (there were %d pieces in %d tracks)" % (style, gone, before["pieces"], before["tracks"]))
    wrong = []
    put = 0
    for folder, made, problem in pieces.add_staged(bucket, VAR, style):
        if problem:
            wrong.append((folder, problem))
        elif made:
            put += 1
    carried = pieces.restore_marks(bucket, marks)
    carried += bucket.sync_book()                 # and what the play book has kept, from builds before this one
    after = pieces.summary(bucket)
    print("%s: %d tracks put in; the bucket now has %d pieces in %d tracks, %.0f minutes" % (style, put, after["pieces"], after["tracks"], after["minutes"]))
    print("%s: %d parts kept what they had been: their plays, loves and bans (%d had any)" % (style, carried, len(marks)))
    settings = VAR / "settings.json"
    told = json.loads(settings.read_text(encoding="utf-8"))
    if keep:
        print("the style in force is left as it is: %s" % told.get("genre"))
    else:
        told["genre"] = style
        settings.write_text(json.dumps(told, indent=1), encoding="utf-8")
        print("the style in force is now %s" % style)
    for folder, problem in wrong:
        print("NOT put in: %s: %s" % (folder, problem))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
