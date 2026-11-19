"""Brings a staged take's guitar solo up over the rhythm guitars where it plays, without making the take again
(2026-11-19: the night's first takes with the sung solo were rendered before the desk measured it, and some of their
solos came out level with the rhythm guitars or under them, Barnyard Jamboree's 3.4 dB under). The solo's span is read
from the take's sheet; the lead stem is brought up there as the desk now does (`build.solo_lift`), eased in and out over
a beat, and written back as it was staged (FLAC, 24 bits). The lift is noted in the track's measurements. A take whose
solo already stands over the rhythm guitars is left as it is.

    cd app && uv run --no-sync python ../tools/lift_solos.py knight [family/take ...]     (all the style's takes with a solo)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile

from freerock.studio import build

VAR = Path(__file__).resolve().parents[1] / "var"
RATE = build.RATE


def lift(folder: Path) -> str:
    sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8"))
    solo = (sheet.get("parts", {}).get("lead") or {}).get("lead guitar solo")
    if not solo or not solo.get("notes"):
        return "no solo"
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    if "solo lift" in meta.get("measured", {}):
        return "already lifted (%.1f dB)" % meta["measured"]["solo lift"]
    beat_frames = 60.0 / float(sheet["tempo"]) * RATE
    span = (int(min(note[0] for note in solo["notes"]) * beat_frames),
            int(max(note[0] + note[1] for note in solo["notes"]) * beat_frames))
    parts = {}
    for channel in ("lead", "rhythm"):
        parts[channel], rate = soundfile.read(str(folder / (channel + ".flac")), dtype="float32", always_2d=True)
        if rate != RATE:
            raise RuntimeError("%s/%s.flac is at %d Hz, not %d" % (folder, channel, rate, RATE))
    db, curve = build.solo_lift(parts, span, int(beat_frames))
    if curve is None:
        meta.setdefault("measured", {})["solo lift"] = 0.0
        (folder / "track.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return "stands over the rhythm guitars already"
    lifted = parts["lead"] * curve[:, None]
    peak = float(np.abs(lifted).max())
    if peak > 0.99:
        # (Never clipped: the lift is held back to what the stem has room for.)
        room = 20 * np.log10(0.99 / float(np.abs(parts["lead"][span[0]:span[1]]).max()))
        db, curve = build.solo_lift(parts, span, int(beat_frames))
        db = min(db, room)
        gain = np.float32(10 ** (db / 20.0))
        curve = np.where(curve > 1.0, 1.0 + (curve - 1.0) * (gain - 1.0) / max(float(curve.max()) - 1.0, 1e-6), curve).astype(np.float32)
        lifted = parts["lead"] * curve[:, None]
    scratch = folder / "lead.part.flac"
    soundfile.write(str(scratch), np.clip(lifted, -1.0, 1.0), RATE, format="FLAC", subtype="PCM_24")
    scratch.replace(folder / "lead.flac")
    meta.setdefault("measured", {})["solo lift"] = round(float(db), 2)
    (folder / "track.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return "brought up %.1f dB where its solo plays" % db


def main() -> int:
    style = sys.argv[1]
    names = sys.argv[2:]
    root = VAR / "studio" / style
    folders = [root / name for name in names] if names else sorted(path.parent for path in root.glob("*/*/sheet.json"))
    for folder in folders:
        print("%-40s %s" % (folder.parent.name + "/" + folder.name, lift(folder)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
