"""Every staged track as one file to listen to, and a page that lists them.

    cd app && uv run --no-sync python ../tools/listen.py [style ...]

The studio keeps a track as a recording for each channel, which is what the player wants and
nobody can listen to. This puts the channels of each staged track together and writes the whole
track as an MP3 file under var/listen/<style>/, with index.html beside them: open that in a
browser and every track is a row with its title, what it is for and a play button. A track
that is there already, and is no older than the staged track, is left alone.

Beside each whole track its channels are written out as well, for the mixer page
(tools/mixer.html, copied to var/listen/mixer.html): the five channels side by side with meters,
faders, mute and solo, and a slider that does to the drums and the bass what the game does.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from urllib.parse import quote
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import soundfile

from freerock import studio
from freerock.audio import write_mp3

VAR = Path(__file__).resolve().parents[1] / "var"
STYLES = ("warcraft", "house")
# Older renders kept beside the newest, for comparing: folder under var/listen -> what it is.
ABOUT = {"instruments": "every instrument alone: the bare recording, how it was, how it is now",
         "second-reaper-try": "the second try in REAPER (16 November, midday): every instrument filtered dull, a chorus on the strings, war drums tuned an octave down",
         "first-reaper-try": "the first try in REAPER (16 November): bare recordings, hardly any effects",
         "general-midi": "the first night's renders (15 November): a General MIDI sound set"}


PIECE = 12.0                   # seconds: for the mixer page a channel is kept as pieces this long, laid end to end by the page
ORDER = ("texture", "lead", "rhythm", "drums", "bass")


def channels(desk: Path, meta: dict, parts: dict[str, np.ndarray], peak: float) -> None:
    """Writes a track's channels for the mixer page: each channel as pieces of PIECE seconds
    (<channel>-<number>.mp3), and track.json, which says what there is and is written last."""
    desk.mkdir(parents=True, exist_ok=True)
    frames = max(len(audio) for audio in parts.values())
    size = int(PIECE * studio.RATE)
    count = -(-frames // size)
    for channel, audio in parts.items():
        for index in range(count):
            write_mp3(desk / ("%s-%03d.mp3" % (channel, index)), audio[index * size:(index + 1) * size], studio.RATE)
    at, sections = 0.0, []
    for section in meta["sections"]:
        long = section["bars"] * meta["bar_frames"] / studio.RATE
        sections.append({"story": section["story"], "start": round(at, 3), "end": round(at + long, 3)})
        at += long
    sections[-1]["end"] = round(frames / studio.RATE, 3)          # what rings on after the last bar belongs to the close
    told = {"title": "%s (take %s)" % (meta["title"], meta["take"]),
            "about": "%s, %s; %s; %.0f beats a minute" % (meta["role"], ", ".join(meta["moods"]), meta["tonic"], meta["tempo"]),
            "channels": [channel for channel in ORDER if channel in parts], "rate": studio.RATE, "piece": PIECE, "pieces": count,
            "seconds": round(frames / studio.RATE, 3), "gain": round(0.89 / peak, 4), "sections": sections, "floor": meta.get("floor", {})}
    (desk / "track.json").write_text(json.dumps(told), encoding="utf-8")


def mixed(folder: Path) -> tuple[str, dict]:
    """Writes one staged track as a single file, and its channels for the mixer page. Returns
    the file's name and what the track is."""
    meta, parts = studio.read_track(folder)
    out = VAR / "listen" / meta["style"]
    name = "%s - take %s (%s).mp3" % (meta["title"], meta["take"], meta["family"])
    staged = (folder / "track.json").stat().st_mtime
    desk = out / name[:-5]

    def stale(path: Path) -> bool:
        return not path.is_file() or path.stat().st_mtime < staged

    if stale(out / name) or stale(desk / "track.json"):
        mix = sum(parts.values())
        peak = float(np.abs(mix).max())
        if peak <= 0.0:
            raise ValueError("The track in %s is silent" % folder)
        out.mkdir(parents=True, exist_ok=True)
        scratch = out / (name + ".part")
        write_mp3(scratch, mix * (0.89 / peak), studio.RATE)
        scratch.replace(out / name)
        channels(desk, meta, parts, peak)
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
             "<p><b>channels</b> opens a track on a mixing desk: its five channels side by side, with meters, faders, mute "
             "and solo, and a slider that does to the drums and the bass what the game does.</p>",
             "<table><tr><th>Track</th><th>For</th><th>Kind of place</th><th></th><th>Key</th><th>Length</th><th>Listen</th><th></th></tr>"]
    for name, meta in rows:
        lines.append("<tr><td>%s <small>take %s</small></td><td>%s</td><td>%s</td><td class='light'>%s</td><td>%s</td><td>%d:%02d</td>"
                     "<td><audio controls preload='none' src='%s'></audio></td>"
                     "<td><a href='../mixer.html?track=%s'>channels</a></td></tr>" % (
                         html.escape(meta["title"]), meta["take"], html.escape(meta["role"]), html.escape(", ".join(meta["moods"])),
                         "light" if meta.get("light") else "", html.escape(meta["tonic"]), seconds(meta) // 60, seconds(meta) % 60,
                         html.escape(name, quote=True), quote("%s/%s" % (style, name[:-5]), safe="/")))
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
    shutil.copyfile(Path(__file__).resolve().parent / "mixer.html", VAR / "listen" / "mixer.html")
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
