"""The songs made since a time, on one page to listen to (2026-11-18: "show me the listener with new house songs",
"all the new songs"): every staged track of every style made since then, newest first, with what it is for and a play
button. It plays the whole-track files that tools/listen.py writes for each style's own page; a song whose file is not
written yet says so. The page is var/listen/new.html, which the server shows at http://<this machine>:8765/listen/new.html.

    cd app && uv run --no-sync python ../tools/new_songs.py [--since "2026-11-17 22:00"]   (default: the last 24 hours)
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
from pathlib import Path

VAR = Path(__file__).resolve().parent.parent / "var"
STYLES = (("knight", "Knight Rock"), ("warcraft", "Warcraft"), ("house", "Progressive House"))


def file_of(meta: dict) -> str:
    """The whole track's file on its style's list (the name tools/listen.py gives it)."""
    return "%s - take %s (%s).flac" % (meta["title"], meta["take"], meta["family"])


def main() -> int:
    parser = argparse.ArgumentParser(description="One page of the songs made since a time.")
    parser.add_argument("--since", default="", help='"YYYY-MM-DD HH:MM" (default: 24 hours ago)')
    args = parser.parse_args()
    since = datetime.datetime.fromisoformat(args.since) if args.since else datetime.datetime.now() - datetime.timedelta(hours=24)
    rows, counts = [], []
    for style, label in STYLES:
        made = []
        for path in (VAR / "studio" / style).glob("*/*/track.json"):
            at = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            if at >= since:
                made.append((at, json.loads(path.read_text(encoding="utf-8"))))
        made.sort(key=lambda each: each[0], reverse=True)
        counts.append("%s %d" % (label, len(made)))
        rows.append("<h2>%s <span class='n'>%d new</span></h2><table><tr><th>song</th><th>for</th><th>made</th><th>listen</th></tr>"
                    % (html.escape(label), len(made)))
        for at, meta in made:
            name = file_of(meta)
            whole = VAR / "listen" / style / name
            what = "%s, %s%s" % (meta.get("role", ""), " and ".join(meta.get("moods") or []) or "anywhere", ", light" if meta.get("light") else "")
            play = ("<audio controls preload='none' src='%s/%s'></audio>" % (style, html.escape(name, quote=True))
                    if whole.is_file() else "<span class='wait'>being written</span>")
            rows.append("<tr><td><b>%s</b><br><span class='fam'>%s, take %s</span></td><td>%s</td><td>%s</td><td>%s</td></tr>"
                        % (html.escape(meta["title"]), html.escape(meta["family"]), meta["take"], html.escape(what), at.strftime("%d %b %H:%M"), play))
        rows.append("</table>")
    page = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
            "<title>FreeRock: new songs</title><style>body{font:15px sans-serif;margin:16px;background:#16181c;color:#e8e8e8}"
            "h2{margin-top:28px}.n{font-size:14px;color:#9aa0a6;font-weight:normal}table{border-collapse:collapse;width:100%}"
            "td,th{padding:6px 8px;border-bottom:1px solid #333;text-align:left;vertical-align:middle}audio{height:30px;width:280px;max-width:100%}"
            ".fam{color:#9aa0a6;font-size:13px}.wait{color:#c9a227}</style></head><body>",
            "<h1>New songs</h1><p>Made since %s: %s. Each style's whole list is on its own page (<a href='knight/index.html'>Knight Rock</a>, "
            "<a href='warcraft/index.html'>Warcraft</a>, <a href='house/index.html'>House</a>).</p>" % (since.strftime("%d %b %H:%M"), ", ".join(counts))]
    page += rows + ["</body></html>"]
    out = VAR / "listen" / "new.html"
    out.write_text("\n".join(page), encoding="utf-8")
    print("%s: %s" % (out, ", ".join(counts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
