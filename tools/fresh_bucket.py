"""Out with a style's old written pieces, in with what is staged now.

    cd app && uv run --no-sync python ../tools/fresh_bucket.py warcraft          (the server must be stopped)
    cd app && uv run --no-sync python ../tools/fresh_bucket.py knight --keep-style

When the way the studio's tracks are played changes for the better, the bucket should hold
only the new ones: this takes every written piece whose source begins with "<style>/" out of
the style's bucket for good (the studio's own tracks and the real scores; the loose phrases,
and any pieces cut from the first design's songs, stay), then puts every staged track of the
style in, and makes the style the one in force (with `--keep-style` the style in force is left
as it is: a second style is made ready while the first goes on being played). `freerock pieces
drop` does the first part too, but saves the bucket after every piece, which for two thousand
pieces is minutes; here it is saved once.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from freerock import pieces

VAR = Path(__file__).resolve().parents[1] / "var"
PORT = 8765


def main(argv: list[str]) -> int:
    keep = "--keep-style" in argv
    argv = [each for each in argv if each != "--keep-style"]
    if len(argv) != 1:
        print(__doc__)
        return 2
    style = argv[0]
    if pieces.server_is_up(PORT):
        print("The FreeRock server is running (port %d): stop it first, it keeps the buckets in memory." % PORT)
        return 1
    bucket = pieces.home_bucket(VAR, style)
    before = pieces.summary(bucket)
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
    after = pieces.summary(bucket)
    print("%s: %d tracks put in; the bucket now has %d pieces in %d tracks, %.0f minutes" % (style, put, after["pieces"], after["tracks"], after["minutes"]))
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
