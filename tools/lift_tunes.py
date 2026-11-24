"""Brings a staged take's tune up over its rhythm in the parts where the desk's lift stood at its most, without making the take again (2026-11-23, 23:30: the
first songs of the bands' own sounds were made with the house band's most, 5 dB; a saxophone or the oohs played softly wanted 10; and the house band's own songs
whose tune is not the guitar's, 00:15, `build.tune_caps`). The desk's own measure (`build.tune_lift`) taken on the staged stems, whatever the take was given counted
in; the lead stem written back as it was staged (FLAC, 24 bits), and the lift noted in the track's measurements. A take that needs less than
half a decibel anywhere is left as it is.

    cd app && uv run --no-sync python ../tools/lift_tunes.py knight [family/take ...]     (all the style's takes)
    ... --out FOLDER      the lifted takes written there (the other stems linked), the staged ones left as they are: to be judged
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile

from freerock.studio import build

VAR = Path(__file__).resolve().parents[1] / "var"
RATE = build.RATE


def lift(folder: Path, out: Path | None = None) -> str:
    sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))
    if not sheet["about"].get("band"):
        return "an orchestra's"
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    measured = meta.setdefault("measured", {})
    if measured.get("tune lift again"):
        return "already brought up (%s)" % measured["tune lift again"]
    bar, edges, bars = float(meta["bar_frames"]), [0], 0
    for section in meta["sections"]:
        bars += section["bars"]
        edges.append(int(round(bars * bar)))
    beat = 60.0 / float(sheet["tempo"]) * RATE
    solo = [note for name, part in sheet["parts"].get("lead", {}).items() if name.endswith(" solo") for note in part["notes"]]
    solos = build.solos_of([(note[0], note[1]) for note in solo], float(sheet["beats"]), beat)
    parts = {}
    for channel in ("lead", "rhythm", "bass"):
        if not (folder / (channel + ".flac")).is_file():
            continue                                             # (a song may have no bass line; without a lead or a rhythm nothing is lifted)
        parts[channel], rate = soundfile.read(str(folder / (channel + ".flac")), dtype="float32", always_2d=True)
        if rate != RATE:
            raise RuntimeError("%s/%s.flac is at %d Hz, not %d" % (folder, channel, rate, RATE))
    spans = build.sung_spans(sheet["form"], edges, solos)
    given = list(measured.get("tune lift") or [])
    if len(given) != len(spans):
        given = [build.TUNE_MOST] * len(spans)                    # (cut by another rule: as if the most were given everywhere)
    sings: dict[str, list[float]] = {}
    for part in sheet["parts"].get("lead", {}).values():
        sings.setdefault(part["instrument"], []).extend(note[0] for note in part["notes"])
    band = sheet["about"].get("sounds") or ""
    caps = [max(cap - had, 0.0) for cap, had in zip(build.tune_caps(band, sings, spans, beat), given)]
    lifts, curve = build.tune_lift(parts, spans, int(beat), most=caps, bass=bool(band))
    if curve is None or max(lifts) < 0.5:
        return "its tune stands over its rhythm"
    lifted = parts["lead"] * curve[:, None]
    peak = float(np.abs(lifted).max())
    if peak > 0.99:
        return "NOT DONE: the stem would clip (peak %.2f)" % peak
    if out is not None:
        to = out / folder.parent.parent.name / folder.parent.name / folder.name
        to.mkdir(parents=True, exist_ok=True)
        for each in folder.iterdir():
            (to / each.name).unlink(missing_ok=True)
            if each.suffix == ".flac" and each.name != "lead.flac":
                os.link(each, to / each.name)
            elif each.suffix != ".flac":
                shutil.copy2(each, to / each.name)
        soundfile.write(str(to / "lead.flac"), lifted, RATE, format="FLAC", subtype="PCM_24")
        return "written beside, by part: %s dB" % ", ".join("%.1f" % each for each in lifts)
    scratch = folder / "lead.part.flac"
    soundfile.write(str(scratch), lifted, RATE, format="FLAC", subtype="PCM_24")
    scratch.replace(folder / "lead.flac")
    measured["tune lift"] = [round(a + b, 2) for a, b in zip(given, lifts)]
    measured["tune lift again"] = lifts
    (folder / "track.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return "brought up by part: %s dB" % ", ".join("%.1f" % each for each in lifts)


def main() -> int:
    argv = sys.argv[1:]
    out = None
    if "--out" in argv:
        at = argv.index("--out")
        out = Path(argv[at + 1])
        argv = argv[:at] + argv[at + 2:]
    style, names = argv[0], argv[1:]
    root = VAR / "studio" / style
    folders = [root / name for name in names] if names else sorted(path.parent for path in root.glob("*/*/sheet.json"))
    for folder in folders:
        said = lift(folder, out)
        if names or said != "an orchestra's":
            print("%-40s %s" % (folder.parent.name + "/" + folder.name, said), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
