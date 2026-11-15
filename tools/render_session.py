"""Renders a scripted minute and a half of play through the real player, with real music.

The game's state changes at set moments (a fight, a mine, stealth); the director turns that into
targets; the player's own engine renders the result in headless Chrome. The clip is written to
var/demos/ and the things that matter are measured. Costs nothing: it plays music already in the
library.

    cd app && uv run --no-sync python ../tools/render_session.py [zone-key]
"""
import asyncio
import json
import sys

import numpy as np

from freerock import analysis, offline
from freerock.audio import encode_mp3, write_flac
from freerock.library import Library
from freerock.settings import VAR_DIR, Settings

SECONDS = 96.0
SESSION = [
    (0.0, {"zone_name": "Elwynn Forest"}),
    (20.0, {"in_combat": True, "has_target": True, "target_class": "normal"}),
    (34.0, {"in_combat": False, "has_target": False, "target_class": "none"}),
    (56.0, {"indoors": True, "subzone_name": "a mine"}),
    (72.0, {"indoors": False, "subzone_name": None}),
    (80.0, {"stealthed": True}),
    (88.0, {"stealthed": False}),
]
STORY = ("0:00 you arrive (Arrival, then Wander with only the bed). 0:20 a fight starts: the bass and "
         "drums come in. About 0:28 the fight has lasted: Battle. 0:34 the fight ends: held for five "
         "seconds, then Ember, then back to Wander. 0:56 you walk into a mine: muffled and echoing, "
         "then Depths. 1:12 you come out. 1:20 stealth: the bass line and quiet drums alone. 1:28 out "
         "of stealth.")


def level(audio, rate, start, end, low, high):
    return analysis.band_level_db(audio[int(start * rate):int(end * rate)], rate, low, high)


async def main() -> None:
    library = Library(Settings().library_dir)
    wanted = sys.argv[1] if len(sys.argv) > 1 else "elwynn-forest"
    assets = library.assets(wanted)
    if not assets:
        raise SystemExit("The library has no music for %r. It has: %s"
                         % (wanted, ", ".join(sorted({a.zone for a in library.assets()})) or "nothing"))
    asset = assets[-1]
    script = offline.timeline(SESSION, SECONDS, asset)
    audio, engine = await offline.render(library, asset, script, SECONDS)
    rate = asset.rate
    # The same session without the mine, up to the moment the music would move to Depths: the
    # same bars of the same music, so the only difference between the two is the muffling.
    no_mine = [change for change in SESSION if change[0] < 56.0]
    control, _ = await offline.render(library, asset, offline.timeline(no_mine, 60.0, asset), 60.0)

    out = VAR_DIR / "demos"
    out.mkdir(parents=True, exist_ok=True)
    write_flac(out / "session.flac", audio, rate)
    (out / "session.mp3").write_bytes(encode_mp3(audio, rate))

    grid = analysis.fit_grid(audio, rate, asset.bpm)
    report = {
        "asset": asset.id, "zone": asset.zone, "seconds": round(len(audio) / rate, 2), "story": STORY,
        "sections": [{"at": round(entry["at"], 2), "section": entry["section"], "cell": entry["cell"]}
                     for entry in engine.get("log", [])],
        "late_cells": engine.get("late"),
        "targets": [{"at": at, "place": target["place"], "bed": target["bed"], "drums": target["drums"],
                     "bass": target["bass"], "lowpass_hz": target["lowpass_hz"], "reverb": target["reverb"],
                     "why": target["why"]} for at, target in script],
        "peak": round(analysis.peak(audio), 4),
        "beat": {"measured_bpm": round(grid.bpm, 3), "jitter_ms": round(grid.jitter_ms, 2),
                 "outliers": grid.outliers, "beats_checked": grid.beats_checked},
        "low_end_db": {"calm_0:13_to_0:19": round(level(audio, rate, 13, 19, 40, 160), 1),
                       "fight_0:21_to_0:27": round(level(audio, rate, 21, 27, 40, 160), 1)},
        # The same bars of Wander with and without having walked into the mine.
        "top_end_db": {"in_the_open_0:57_to_1:00": round(level(control, rate, 56.8, 59.9, 3000, 6000), 1),
                       "just_inside_0:57_to_1:00": round(level(audio, rate, 56.8, 59.9, 3000, 6000), 1)},
        "stealth_db": {"bed_register_before_1:14_to_1:19": round(level(audio, rate, 74, 79, 300, 3000), 1),
                       "bed_register_in_stealth_1:22_to_1:27": round(level(audio, rate, 82, 87, 300, 3000), 1)},
    }
    report["passes"] = {
        "nothing passes full scale": report["peak"] <= 1.0,
        "no cell started late": report["late_cells"] == 0,
        "the beat holds through every change (tempo within 0.05%)": abs(grid.bpm / asset.bpm - 1) <= 0.0005,
        "the bass and drums add at least 12 dB of low end when the fight starts":
            report["low_end_db"]["fight_0:21_to_0:27"] - report["low_end_db"]["calm_0:13_to_0:19"] >= 12,
        "walking into the mine takes at least 6 dB off the top of the same music":
            report["top_end_db"]["in_the_open_0:57_to_1:00"] - report["top_end_db"]["just_inside_0:57_to_1:00"] >= 6,
        "stealth drops the bed by at least 10 dB":
            report["stealth_db"]["bed_register_before_1:14_to_1:19"]
            - report["stealth_db"]["bed_register_in_stealth_1:22_to_1:27"] >= 10,
    }
    (out / "session.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("rendered %.0f s of %s's music -> %s" % (report["seconds"], asset.zone, out / "session.mp3"))
    print("sections:", ", ".join("%s@%.1f" % (s["section"], s["at"]) for s in report["sections"]))
    print("beat: %.3f BPM, %d of %d beats off the grid; peak %.3f; late cells %s"
          % (grid.bpm, grid.outliers, grid.beats_checked, report["peak"], report["late_cells"]))
    print("low end calm/fight:", report["low_end_db"], "| top end open/just inside:", report["top_end_db"],
          "| stealth:", report["stealth_db"])
    for line, passed in report["passes"].items():
        print("  %s  %s" % ("PASS" if passed else "FAIL", line))


if __name__ == "__main__":
    asyncio.run(main())
