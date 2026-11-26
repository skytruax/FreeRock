"""Brings a staged take's tune up over its rhythm in the parts where the desk's lift stood at its most, without making the take again (2026-11-23, 23:30: the
first songs of the bands' own sounds were made with the house band's most, 5 dB; a saxophone or the oohs played softly wanted 10; and the house band's own songs
whose tune is not the guitar's, 00:15, `build.tune_caps`). The desk's own measure (`build.tune_lift`) taken on the staged stems, whatever the take was given counted
in; the lead stem written back as it was staged (FLAC, 24 bits), and the lift noted in the track's measurements. A take that needs less than
half a decibel anywhere is left as it is.

    cd app && uv run --no-sync python ../tools/lift_tunes.py knight [family/take ...]     (all the style's takes)
    ... --out FOLDER      the lifted takes written there (the other stems linked), the staged ones left as they are: to be judged
    ... --back            takes it back, from what was written down: the lead stem (and the rhythm's, where THIS TOOL made the riff give way)
                          as it was before, to the hundredth of a decibel the track keeps; with no take named, every take of the style that
                          was lifted. A take that is refused is said and the others go on; the command ends with 1 if any was

(2026-11-26, the audit: in the night of 24 to 25 November this was run over the older library in place, 137 takes' lead stems up by 5 dB
in the middle and 8 at the most, with no way back and no reading of before and after by anyone who listens.)
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


def sung(sheet: dict, meta: dict) -> tuple[list[tuple[int, int]], list[int], float]:
    """Where a take's tune sings, in samples (`build.sung_spans`), the edges of its parts, and a beat in samples."""
    bar, edges, bars = float(meta["bar_frames"]), [0], 0
    for section in meta["sections"]:
        bars += section["bars"]
        edges.append(int(round(bars * bar)))
    beat = 60.0 / float(sheet["tempo"]) * RATE
    solo = [note for name, part in sheet["parts"].get("lead", {}).items() if name.endswith(" solo") for note in part["notes"]]
    solos = build.solos_of([(note[0], note[1]) for note in solo], float(sheet["beats"]), beat)
    return build.sung_spans(sheet["form"], edges, solos), edges, beat


def curve_of(frames: int, spans: list[tuple[int, int]], dbs: list[float], ramp: int) -> np.ndarray:
    """The gain for each sample that the desk laid on a stem, made again from what it wrote down for each part (dB): the part's dB through its span, then
    eased over `ramp` samples to each side of every edge, the edges in their order: as `build.tune_lift` and `build.riff_gives` make theirs. (They write a
    part's dB down to the hundredth and lay it on unrounded: what comes back is the stem as it was to within that hundredth of a decibel.)"""
    db = np.zeros(frames, dtype=np.float32)
    for (first, last), each in zip(spans, dbs):
        db[first:last] = each
    for edge in sorted({edge for span in spans for edge in span}):
        low, high = max(edge - ramp, 0), min(edge + ramp, frames)
        if high - low > 1:
            db[low:high] = np.linspace(db[low], db[high - 1], high - low, dtype=np.float32)
    return (10.0 ** (db / 20.0)).astype(np.float32)


def back(folder: Path) -> str:
    """Takes back what `lift` did to a staged take, from what it wrote down in the track's measurements ("tune lift again": the lead's stem; "riff gives": the
    rhythm's): each stem divided by the gain it was given, written as it is staged (FLAC, 24 bits; a .part file put in its place), "tune lift" put back to
    what stood before the lift, and the two notes taken out. A take whose sheet sings in other parts now than when it was lifted is refused."""
    sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    measured = meta.get("measured") or {}
    # (2026-11-26, an hour after --back was written: "riff gives" is also what the DESK writes when it performs a band's song (build.perform), with the rhythm
    # already taken down in the performance: 61 staged takes carry it that this tool never touched, and --back would have brought their rhythm up by what the
    # desk had taken off. Only what this tool laid in place is its to take back: "tune lift again", and "riff gives again" from now on. The four takes whose riff
    # this tool made give way before that day carry "riff gives" alone, as the desk's do: their rhythm stays as it is.)
    again, gives = measured.get("tune lift again"), measured.get("riff gives again")
    if not again and not gives:
        return "nothing to take back"
    spans, _, beat = sung(sheet, meta)
    for said in (again, gives):
        if said and len(said) != len(spans):
            raise ValueError("%s: its tune sings in %d parts by its sheet now, and %d were lifted: the sheet was revised since, and nothing is taken back" % (folder, len(spans), len(said)))
    done = []
    for channel, said in (("lead", again), ("rhythm", gives)):
        if not said or not any(abs(each) >= 0.005 for each in said):
            continue
        audio, rate = soundfile.read(str(folder / (channel + ".flac")), dtype="float32", always_2d=True)
        if rate != RATE:
            raise RuntimeError("%s/%s.flac is at %d Hz, not %d" % (folder, channel, rate, RATE))
        was = audio / curve_of(len(audio), spans, said, int(beat))[:, None]
        peak = float(np.abs(was).max())
        if peak > 0.999:
            raise ValueError("%s: its %s would clip as it was (peak %.3f): nothing is taken back" % (folder, channel, peak))
        soundfile.write(str(folder / (channel + ".part.flac")), was, RATE, format="FLAC", subtype="PCM_24")
        done.append(channel)
    for channel in done:                         # (both written before either takes its place)
        (folder / (channel + ".part.flac")).replace(folder / (channel + ".flac"))
    if again and measured.get("tune lift") and len(measured["tune lift"]) == len(again):
        measured["tune lift"] = [round(now - up, 2) for now, up in zip(measured["tune lift"], again)]
    measured.pop("tune lift again", None)
    if gives:
        measured.pop("riff gives again", None)
        measured.pop("riff gives", None)
    scratch = folder / "track.json.part"
    scratch.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    scratch.replace(folder / "track.json")
    return "taken back: %s" % (", ".join("its %s by part %s dB" % (channel, ", ".join("%+.1f" % -each for each in (again if channel == "lead" else gives))) for channel in done) or "its notes alone")


def lift(folder: Path, out: Path | None = None) -> str:
    sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))
    orchestra = not sheet["about"].get("band")
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    measured = meta.setdefault("measured", {})
    if measured.get("tune lift again"):
        return "already brought up (%s)" % measured["tune lift again"]
    spans, edges, beat = sung(sheet, meta)
    parts = {}
    for channel in ("lead", "rhythm", "bass"):
        if not (folder / (channel + ".flac")).is_file():
            continue                                             # (a song may have no bass line; without a lead or a rhythm nothing is lifted)
        parts[channel], rate = soundfile.read(str(folder / (channel + ".flac")), dtype="float32", always_2d=True)
        if rate != RATE:
            raise RuntimeError("%s/%s.flac is at %d Hz, not %d" % (folder, channel, rate, RATE))
    given = list(measured.get("tune lift") or [])
    if len(given) != len(spans):
        given = [build.TUNE_MOST] * len(spans)                    # (cut by another rule: as if the most were given everywhere)
    sings: dict[str, list[float]] = {}
    for part in sheet["parts"].get("lead", {}).values():
        sings.setdefault(part["instrument"], []).extend(note[0] for note in part["notes"])
    band = "" if orchestra else sheet["about"].get("sounds") or ""
    if orchestra:
        # (2026-11-25: an orchestra's tune over its accompaniment, build.ORCHESTRA_OVER; none was brought up before.)
        caps = [max(build.ORCHESTRA_MOST - had, 0.0) for had in (given if measured.get("tune lift") else [0.0] * len(spans))]
        notes: dict[str, list[tuple[float, float]]] = {}
        for part in sheet["parts"].get("lead", {}).values():
            notes.setdefault(part["instrument"], []).extend((note[0], note[1]) for note in part["notes"])
        lifts, curve = build.tune_lift(parts, spans, int(beat), most=caps, bass=True, over=build.tune_overs(notes, spans, beat), under_bass=build.ORCHESTRA_UNDER_BASS)
        given = given if measured.get("tune lift") else [0.0] * len(spans)
    else:
        caps = [max(cap - had, 0.0) for cap, had in zip(build.tune_caps(band, sings, spans, beat), given)]
        lifts, curve = build.tune_lift(parts, spans, int(beat), most=caps, bass=bool(band))
    if band and not measured.get("riff gives"):
        # (2026-11-25: and where the tune, lifted as far as it goes, stands under its riff still, the riff gives way: build.riff_gives, in the rhythm's stem.)
        now = dict(parts, lead=parts["lead"] * curve[:, None]) if curve is not None and "lead" in parts else parts
        downs, gives = build.riff_gives(now, spans, int(beat))
        if gives is not None and out is None:
            scratch = folder / "rhythm.part.flac"
            soundfile.write(str(scratch), parts["rhythm"] * gives[:, None], RATE, format="FLAC", subtype="PCM_24")
            scratch.replace(folder / "rhythm.flac")
            measured["riff gives"] = downs
            measured["riff gives again"] = downs          # laid in place by this tool, not by the desk at the performance: `back` takes this back, and no other
            (folder / "track.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            if curve is None or max(lifts) < 0.5:
                return "its riff gives way by part: %s dB" % ", ".join("%.1f" % each for each in downs)
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
    undo = "--back" in argv
    argv = [each for each in argv if each != "--back"]
    if undo and out is not None:
        raise SystemExit("--back takes back what was done to the staged takes: it has no --out")
    style, names = argv[0], argv[1:]
    root = VAR / "studio" / style
    folders = [root / name for name in names] if names else sorted(path.parent for path in root.glob("*/*/sheet.json"))
    refused = 0
    for folder in folders:
        if undo:
            try:
                said = back(folder)
            except (ValueError, RuntimeError, OSError, soundfile.SoundFileError) as problem:
                # One take that cannot be taken back (its sheet revised since, a stem that cannot be read) is said and the others go on.
                refused += 1
                said = "NOT TAKEN BACK: %s: %s" % (type(problem).__name__, problem)
        else:
            said = lift(folder, out)
        if undo and not names and said == "nothing to take back":
            continue                                             # (every take of the style was asked: only those that were lifted are said)
        print("%-40s %s" % (folder.parent.name + "/" + folder.name, said), flush=True)
    if refused:
        print("%d not taken back (said above)" % refused, flush=True)
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
