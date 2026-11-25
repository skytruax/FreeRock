"""The page of what is new (var/listen/now.html, http://<this machine>:8765/listen/now.html), written again whenever a
bucket is built again (var/passes/rebuild.sh; 2026-11-23: "now page is old", "then make its regen part of the rebuild
process for the server"). Newest first:

  - In the player: each style's bucket, when it was built, and the songs that came in with that build, against the songs
    the build before it had (kept in var/listen/now-state.json); the songs made again since that build are folded away
    under them. A style met for the first time has no build before it: its songs staged in the day before the build are
    shown.
  - For the next build: the songs staged after their style's bucket was built, new and made again.
  - Demos and changes: what was tried and how it was heard and judged, written by hand, newest first, in
    var/listen/now-demos.html, put in as it is.

Every song has a play button for the whole-track file tools/listen.py writes; a song whose file is not written yet says so.

    cd app && uv run --no-sync python ../tools/now_page.py [--var <folder>]
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

VAR = Path(__file__).resolve().parent.parent / "var"
STYLES = (("knight", "Knight Rock"), ("warcraft", "Warcraft"), ("house", "Progressive House"))
DAY = 24 * 3600.0
STYLE = ("body{font:15px/1.5 sans-serif;margin:16px;background:#16181c;color:#e8e8e8;max-width:980px}"
         "a{color:#ffd76a}h1{margin-bottom:2px}h2{margin-top:28px}h3{margin:18px 0 4px}.sub{color:#9aa0a6;font-size:13px}.wait{color:#c9a227}"
         "table{border-collapse:collapse;width:100%;margin:8px 0 14px}td{padding:8px;border-bottom:1px solid #333;vertical-align:top}"
         "audio{width:100%;max-width:360px;height:32px}summary{cursor:pointer;color:#9aa0a6;margin:6px 0}"
         # The songs' columns are given their widths: left to the browser, a song's long list of places took the whole row and
         # its play button was drawn no pixels wide (2026-11-23: "no play buttons on most"). On a phone a row's cells stand
         # one under another, the demos' pairs too.
         ".songs{table-layout:fixed}.songs .made{width:100px}.songs .play{width:340px}.songs td{overflow-wrap:anywhere}"
         # A demo's cells (written by hand, up to as many as it has versions) go on to a next line rather than shrink.
         "table:not(.songs),table:not(.songs) tbody{display:block}table:not(.songs) tr{display:flex;flex-wrap:wrap}"
         "table:not(.songs) td{flex:1 1 220px;min-width:0}"
         "@media(max-width:700px){table,tbody,tr,td{display:block;width:auto}col{display:none}td{padding:3px 0;border:0}"
         "table:not(.songs) tr{display:block}"
         "tr{padding:8px 0;border-bottom:1px solid #333}audio{max-width:none}}")


def file_of(meta: dict) -> str:
    """The whole track's file on its style's list (the name tools/listen.py gives it)."""
    return "%s - take %s (%s).flac" % (meta["title"], meta["take"], meta["family"])


def bucket_of(var: Path, style: str) -> Path | None:
    """The style's bucket file (the first bucket folder, as rebuild.sh takes it), if there is one."""
    found = sorted((var / "buckets" / style).glob("*/bucket.json"))
    return found[0] if found else None


def tracks_in(bucket: Path) -> list[str]:
    """Every song (style/family/take) the bucket's pieces are cut from."""
    pieces = json.loads(bucket.read_text(encoding="utf-8")).get("pieces") or {}
    return sorted({piece["track"] for piece in pieces.values()})


def built_at(bucket: Path) -> float:
    """When a bucket was built: its newest piece's time. (2026-11-23: the file's own time was taken, and the server writes the file again as
    it plays, so each evening's page was read against the build itself: 104 new songs became none.) A bucket whose pieces say no time
    is as old as its file."""
    pieces = json.loads(bucket.read_text(encoding="utf-8")).get("pieces") or {}
    times = [piece["created"] for piece in pieces.values() if piece.get("created")]
    return max(times) if times else bucket.stat().st_mtime


def staged(var: Path, track: str) -> tuple[float, dict] | None:
    """When a song was staged and what it is (its track.json), or None if it is not staged."""
    style, family, take = track.split("/")
    path = var / "studio" / style / family / take / "track.json"
    if not path.is_file():
        return None
    return path.stat().st_mtime, json.loads(path.read_text(encoding="utf-8"))


def staged_since(var: Path, style: str, since: float) -> list[str]:
    """The style's songs staged after a time."""
    return sorted("%s/%s/%s" % (style, path.parent.parent.name, path.parent.name)
                  for path in (var / "studio" / style).glob("*/*/track.json") if path.stat().st_mtime > since)


def what(meta: dict) -> str:
    return "%s, %s%s" % (meta.get("role", ""), " and ".join(meta.get("moods") or []) or "anywhere", ", light" if meta.get("light") else "")


def table(var: Path, style: str, tracks: list[str]) -> str:
    """The songs, newest first, each with what it is for, when it was made and its play button."""
    rows = []
    for track in tracks:
        found = staged(var, track)
        if found is None:
            rows.append((0.0, "<tr><td><b>%s</b></td><td colspan='2'><span class='wait'>not staged any more</span></td></tr>"
                         % html.escape(track)))
            continue
        at, meta = found
        name = file_of(meta)
        play = ("<audio controls preload='none' src='%s/%s'></audio>" % (style, quote(name))
                if (var / "listen" / style / name).is_file() else "<span class='wait'>its file is being written</span>")
        rows.append((at, "<tr><td><b>%s</b><br><span class='sub'>%s, take %s: %s</span></td><td class='sub'>%s</td><td>%s</td></tr>"
                     % (html.escape(meta["title"]), html.escape(meta["family"]), html.escape(str(meta["take"])),
                        html.escape(what(meta)), datetime.datetime.fromtimestamp(at).strftime("%d %b %H:%M"), play)))
    rows.sort(key=lambda row: row[0], reverse=True)
    return "<table class='songs'><colgroup><col><col class='made'><col class='play'></colgroup>%s</table>" % "".join(row for _, row in rows)


def when(seconds: float) -> str:
    return datetime.datetime.fromtimestamp(seconds).strftime("%d %b %H:%M")


def builds(var: Path, state: dict) -> dict:
    """Each style's build as it stands, against the one before it: the state to keep for the next time."""
    out = {}
    for style, _ in STYLES:
        bucket = bucket_of(var, style)
        if bucket is None:
            continue
        built, kept = built_at(bucket), state.get(style)
        if kept and kept.get("built") == built:
            out[style] = kept                      # the same build as last time: what came in with it is known already
            continue
        tracks = tracks_in(bucket)
        if kept and kept["tracks"] == tracks and built <= kept["built"]:
            out[style] = kept                      # ...and so it is where the file's time was kept for the build's, before
            continue
        if kept:
            before = set(kept["tracks"])
            came = [track for track in tracks if track not in before]
            again = [track for track in tracks if track in before and (staged(var, track) or (0.0,))[0] > kept["built"]]
            out[style] = {"built": built, "tracks": tracks, "came": came, "again": again, "since": kept["built"]}
        else:
            day = [track for track in tracks if built - DAY < (staged(var, track) or (0.0,))[0] <= built]
            out[style] = {"built": built, "tracks": tracks, "came": day, "again": [], "since": None}
    return out


# A build may bring a hundred songs and more into a player: more than these in a list are closed until they are asked for.
# (2026-11-23: what was new today stood under 383 songs of the last builds.)
LONG_LIST = 30


def page(var: Path, state: dict, now: datetime.datetime) -> str:
    parts = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>FreeRock: Listen Now</title><style>%s</style></head><body>" % STYLE,
             "<h1>Listen now</h1><p class='sub'>What is new, newest first, as of %s (written again whenever a bucket is built "
             "again). Other pages: <a href='new.html'>the songs of the last days</a> &middot; <a href='judges.html'>the judges</a> "
             "&middot; <a href='/player'>the player</a></p>" % now.strftime("%H:%M, %d %B")]
    labels = dict(STYLES)
    parts.append("<h2>For the next build</h2><p class='sub'>Staged since their style's bucket was built: in the player once it "
                 "is built again.</p>")
    for style, label in STYLES:
        build = state.get(style)
        since = build["built"] if build else 0.0
        waiting = staged_since(var, style, since)
        inside = set(build["tracks"]) if build else set()
        fresh = [track for track in waiting if track not in inside]
        again = [track for track in waiting if track in inside]
        parts.append("<h3>%s <span class='sub'>%d new, %d made again</span></h3>" % (html.escape(labels[style]), len(fresh), len(again)))
        if fresh:
            parts.append(table(var, style, fresh))
        if again:
            parts.append("<details><summary>the %d made again</summary>%s</details>" % (len(again), table(var, style, again)))
    demos = var / "listen" / "now-demos.html"
    parts.append("<h2>Demos and changes</h2>")
    parts.append(demos.read_text(encoding="utf-8") if demos.is_file() else "<p class='sub'>none written yet</p>")
    parts.append("<h2>In the player</h2>")
    for style, label in STYLES:
        build = state.get(style)
        if build is None:
            parts.append("<h3>%s</h3><p class='sub'>no bucket</p>" % html.escape(label))
            continue
        if build["since"] is None:
            said = "%d songs staged in the day before it was built" % len(build["came"])
        else:
            said = "%d came in with this build, %d made again (the build before it: %s)" % (
                len(build["came"]), len(build["again"]), when(build["since"]))
        parts.append("<h3>%s <span class='sub'>built %s, %d songs; %s</span></h3>"
                     % (html.escape(label), when(build["built"]), len(build["tracks"]), said))
        if len(build["came"]) > LONG_LIST:
            parts.append("<details><summary>the %d that came in</summary>%s</details>" % (len(build["came"]), table(var, style, build["came"])))
        elif build["came"]:
            parts.append(table(var, style, build["came"]))
        if build["again"]:
            parts.append("<details><summary>the %d made again</summary>%s</details>" % (len(build["again"]), table(var, style, build["again"])))
    parts.append("</body></html>")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The page of what is new, written again after each build.")
    parser.add_argument("--var", default=str(VAR), help="the var folder (default: the repository's)")
    args = parser.parse_args(argv)
    var = Path(args.var)
    path = var / "listen" / "now-state.json"
    state = builds(var, json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {})
    out = var / "listen" / "now.html"
    written = out.with_name("%s.%d.new" % (out.name, os.getpid()))          # (two builds ending at once wrote to one: 2026-11-24)
    written.write_text(page(var, state, datetime.datetime.now()), encoding="utf-8")
    written.replace(out)
    kept = path.with_name("%s.%d.new" % (path.name, os.getpid()))
    kept.write_text(json.dumps(state), encoding="utf-8")
    kept.replace(path)
    print("%s: %s" % (out, ", ".join("%s %d new in the player" % (style, len(build["came"])) for style, build in state.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
