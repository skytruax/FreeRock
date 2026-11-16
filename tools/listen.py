"""Every staged track as one file to listen to, and a page that lists them.

    cd app && uv run --no-sync python ../tools/listen.py [style ...]

The studio keeps a track as a recording for each channel, which is what the player wants and
nobody can listen to. This puts the channels of each staged track together and writes the whole
track as a FLAC file under var/listen/<style>/, with index.html beside them: open that in a
browser and every track is a row with its title, what it is for and a play button. A track
that is there already is left alone.
"""
from __future__ import annotations

import html
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import soundfile

from freerock import studio

VAR = Path(__file__).resolve().parents[1] / "var"
STYLES = ("warcraft", "house")
# Older renders kept beside the newest, for comparing: folder under var/listen -> what it is.
ABOUT = {"first-reaper-try": "the first try in REAPER (16 November): bare recordings, hardly any effects",
         "general-midi": "the first night's renders (15 November): a General MIDI sound set"}


def mixed(folder: Path) -> tuple[str, dict]:
    """Writes one staged track as a single file. Returns the file's name and what the track is."""
    meta, parts = studio.read_track(folder)
    out = VAR / "listen" / meta["style"]
    name = "%s - take %s (%s).flac" % (meta["title"], meta["take"], meta["family"])
    if not (out / name).is_file():
        mix = sum(parts.values())
        peak = float(np.abs(mix).max())
        if peak <= 0.0:
            raise ValueError("The track in %s is silent" % folder)
        out.mkdir(parents=True, exist_ok=True)
        scratch = out / (name + ".part")
        soundfile.write(str(scratch), mix * (0.89 / peak), studio.RATE, format="FLAC", subtype="PCM_16")
        scratch.replace(out / name)
    return name, meta


def page(style: str, rows: list[tuple[str, dict]]) -> str:
    def seconds(meta: dict) -> float:
        return sum(section["bars"] for section in meta["sections"]) * meta["bar_frames"] / studio.RATE

    rows = sorted(rows, key=lambda row: (row[1]["role"], row[1]["moods"], not row[1].get("light"), row[1]["title"], row[1]["take"]))
    lines = ["<!doctype html><html><head><meta charset='utf-8'><title>FreeRock: %s tracks</title>" % html.escape(style),
             "<style>body{font:15px sans-serif;margin:24px;background:#16181c;color:#e8e8e8}table{border-collapse:collapse}"
             "td,th{padding:4px 12px;text-align:left;border-bottom:1px solid #333}audio{height:28px;width:340px}"
             ".light{color:#ffd76a}</style></head><body>",
             "<h1>%s: %d tracks, %.0f minutes</h1>" % (html.escape(style), len(rows), sum(seconds(meta) for _, meta in rows) / 60.0),
             "<p>Each row is one whole track with every channel playing. In the game the player turns channels up and down, "
             "cuts to a fight's own track and comes back, and moves from track to track.</p>",
             "<table><tr><th>Track</th><th>For</th><th>Kind of place</th><th></th><th>Key</th><th>Length</th><th>Listen</th></tr>"]
    for name, meta in rows:
        lines.append("<tr><td>%s <small>take %s</small></td><td>%s</td><td>%s</td><td class='light'>%s</td><td>%s</td><td>%d:%02d</td>"
                     "<td><audio controls preload='none' src='%s'></audio></td></tr>" % (
                         html.escape(meta["title"]), meta["take"], html.escape(meta["role"]), html.escape(", ".join(meta["moods"])),
                         "light" if meta.get("light") else "", html.escape(meta["tonic"]), seconds(meta) // 60, seconds(meta) % 60,
                         html.escape(name, quote=True)))
    lines.append("</table></body></html>")
    return "\n".join(lines) + "\n"


def main(styles: list[str]) -> int:
    for style in styles:
        folders = studio.staged(VAR, style)
        with ProcessPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(mixed, folders, chunksize=4))
        out = VAR / "listen" / style
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(page(style, rows), encoding="utf-8")
        print("%s: %d tracks to listen to in %s" % (style, len(rows), out))
    # A front page for whatever styles have been written out so far.
    have = sorted((folder.name for folder in (VAR / "listen").iterdir() if (folder / "index.html").is_file()),
                  key=lambda name: (name in ABOUT, name))
    (VAR / "listen" / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>FreeRock: tracks to listen to</title>"
        "<style>body{font:17px sans-serif;margin:32px;background:#16181c;color:#e8e8e8}a{color:#ffd76a}small{color:#aaa}</style></head><body>"
        "<h1>FreeRock: tracks to listen to</h1><p>Whole tracks as the studio wrote them, every channel playing.</p><ul>"
        + "".join("<li><a href='%s/index.html'>%s</a> <small>%s</small></li>" % (
            html.escape(name, quote=True), html.escape(name), html.escape(ABOUT.get(name, "the newest: played in REAPER")))
                  for name in have)
        + "</ul></body></html>\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(STYLES)))
