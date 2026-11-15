"""Renders a scripted stretch of play through the real player, with real music.

The game's state changes at set moments; the director turns that into targets; the player's own
engine renders the result in headless Chrome, with everything the place has in the library (its
core suite and any later sets). The clip is written to var/demos/ and the things that matter are
measured. Costs nothing: it plays music already in the library.

    cd app && uv run --no-sync python ../tools/render_session.py walk  [zone-key]
    cd app && uv run --no-sync python ../tools/render_session.py storm [zone-key]
"""
import asyncio
import json
import sys

from freerock import analysis, offline
from freerock.audio import db, encode_mp3, rms, write_flac
from freerock.director import Rules
from freerock.library import Library
from freerock.settings import VAR_DIR, Settings

# A walk: a fight, a mine, stealth.
WALK = {
    "seconds": 96.0, "rules": Rules(rest_every_s=0),
    "session": [
        (0.0, {"zone_name": "somewhere"}),
        (20.0, {"in_combat": True, "has_target": True, "target_class": "normal"}),
        (34.0, {"in_combat": False, "has_target": False, "target_class": "none"}),
        (56.0, {"indoors": True, "subzone_name": "a mine"}),
        (72.0, {"indoors": False, "subzone_name": None}),
        (80.0, {"stealthed": True}),
        (88.0, {"stealthed": False}),
    ],
    "story": ("0:00 you arrive (Arrival, then Wander with only the bed). 0:20 a fight starts: the bass and "
              "drums come in. About 0:28 the fight has lasted: Battle. 0:34 the fight ends: held for five "
              "seconds, then Ember, then back to Wander. 0:56 you walk into a mine: muffled and echoing, "
              "then Depths. 1:12 you come out. 1:20 stealth: the bass line and quiet drums alone. 1:28 out "
              "of stealth."),
}

# A rain storm, then a rest. The rests are set short here so one fits in the clip; in play they
# come after about six minutes of calm music and last about a minute.
STORM = {
    "seconds": 104.0,
    "rules": Rules(rest_every_s=60, rest_for_s=14, rest_spread=0.0, calm_before_rest_s=10, rest_fade_s=5),
    "session": [
        (0.0, {"zone_name": "somewhere"}),
        (16.0, {"weather": "rain", "weather_intensity": 0.4}),
        (28.0, {"weather_intensity": 0.9}),
        (56.0, {"weather_intensity": 0.2}),
        (60.0, {"weather": "clear", "weather_intensity": 0.0}),
    ],
    "story": ("0:00 you arrive: Arrival, then Wander with only the bed. 0:16 it starts to rain: the drums "
              "come in. 0:28 the rain turns into a storm: the whole band comes in at once, and about ten "
              "seconds later the music moves to the Storm part if this zone has one. 0:56 the storm eases "
              "and the band leaves. About 1:12 a rest: the music fades away and there is nothing for a few "
              "seconds, then it comes back with a fresh opening at about 1:26."),
}
SESSIONS = {"walk": WALK, "storm": STORM}


def cut(audio, rate, start, end):
    return audio[int(start * rate):int(end * rate)]


def level(audio, rate, start, end, low, high):
    return round(analysis.band_level_db(cut(audio, rate, start, end), rate, low, high), 1)


async def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "walk"
    if which not in SESSIONS:
        raise SystemExit("Which session? One of: %s" % ", ".join(SESSIONS))
    wanted = sys.argv[2] if len(sys.argv) > 2 else "elwynn-forest"
    plan = SESSIONS[which]
    library = Library(Settings().library_dir)
    music = library.usable(wanted)
    if not music:
        raise SystemExit("The library has no music for %r. It has: %s"
                         % (wanted, ", ".join(sorted({a.zone for a in library.usable()})) or "nothing"))
    seconds = plan["seconds"]
    script = offline.timeline(plan["session"], seconds, music, rules=plan["rules"])
    audio, engine = await offline.render(library, music, script, seconds)
    rate, bpm = music[0].rate, music[0].bpm

    out = VAR_DIR / "demos"
    out.mkdir(parents=True, exist_ok=True)
    name = "%s-%s" % ("session" if which == "walk" else which, wanted)
    write_flac(out / (name + ".flac"), audio, rate)
    (out / (name + ".mp3")).write_bytes(encode_mp3(audio, rate))

    report = {
        "session": which, "zone": wanted, "music": [(asset.id, asset.set) for asset in music],
        "seconds": round(len(audio) / rate, 2), "story": plan["story"],
        "sections": [{"at": round(entry["at"], 2), "section": entry["section"], "cell": entry["cell"]}
                     for entry in engine.get("log", [])],
        "late_cells": engine.get("late"),
        "targets": [{"at": at, "place": target["place"], "rest": target["rest"], "bed": target["bed"],
                     "drums": target["drums"], "bass": target["bass"], "lowpass_hz": target["lowpass_hz"],
                     "reverb": target["reverb"], "why": target["why"]} for at, target in script],
        "peak": round(analysis.peak(audio), 4),
    }
    passes = {"nothing passes full scale": report["peak"] <= 1.0,
              "no cell started late": report["late_cells"] == 0}

    if which == "walk":
        grid = analysis.fit_grid(audio, rate, bpm)
        # The same session without the mine, up to the moment the music would move to Depths: the
        # same bars of the same music, so the only difference between the two is the muffling.
        no_mine = [change for change in plan["session"] if change[0] < 56.0]
        control, _ = await offline.render(library, music, offline.timeline(no_mine, 60.0, music, rules=plan["rules"]), 60.0)
        report["beat"] = {"measured_bpm": round(grid.bpm, 3)}
        report["low_end_db"] = {"calm_0:13_to_0:19": level(audio, rate, 13, 19, 40, 160),
                                "fight_0:21_to_0:27": level(audio, rate, 21, 27, 40, 160)}
        report["top_end_db"] = {"in_the_open_0:57_to_1:00": level(control, rate, 56.8, 59.9, 3000, 6000),
                                "just_inside_0:57_to_1:00": level(audio, rate, 56.8, 59.9, 3000, 6000)}
        report["stealth_db"] = {"bed_register_before_1:14_to_1:19": level(audio, rate, 74, 79, 300, 3000),
                                "bed_register_in_stealth_1:22_to_1:27": level(audio, rate, 82, 87, 300, 3000)}
        passes.update({
            "the beat holds through every change (tempo within 0.05%)": abs(grid.bpm / bpm - 1) <= 0.0005,
            # How much they add depends on the music: 22 dB over guitars and lute, 7 dB where a
            # church organ already fills the low end of the bed.
            "the bass and drums add at least 6 dB of low end when the fight starts":
                report["low_end_db"]["fight_0:21_to_0:27"] - report["low_end_db"]["calm_0:13_to_0:19"] >= 6,
            "walking into the mine takes at least 6 dB off the top of the same music":
                report["top_end_db"]["in_the_open_0:57_to_1:00"] - report["top_end_db"]["just_inside_0:57_to_1:00"] >= 6,
            "stealth drops the bed by at least 10 dB":
                report["stealth_db"]["bed_register_before_1:14_to_1:19"]
                - report["stealth_db"]["bed_register_in_stealth_1:22_to_1:27"] >= 10,
        })
    else:
        grid = analysis.fit_grid(cut(audio, rate, 0, 70), rate, bpm)
        rests = [at for at, target in script if target["rest"]]
        back = [at for at, target in script if not target["rest"] and rests and at > rests[0]]
        report["beat"] = {"measured_bpm": round(grid.bpm, 3)}
        report["rest"] = {"starts_s": rests[0] if rests else None, "ends_s": back[0] if back else None}
        report["low_end_db"] = {"calm_0:09_to_0:15": level(audio, rate, 9, 15, 40, 160),
                                "storm_0:30_to_0:37": level(audio, rate, 30, 37, 40, 160)}
        report["top_end_db"] = {"calm_0:09_to_0:15": level(audio, rate, 9, 15, 3000, 6000),
                                "rain_0:18_to_0:27": level(audio, rate, 18, 27, 3000, 6000),
                                "storm_0:40_to_0:54": level(audio, rate, 40, 54, 3000, 6000)}
        if rests and back:
            report["level_db"] = {"before_the_rest": round(db(rms(cut(audio, rate, rests[0] - 6, rests[0] - 1))), 1),
                                  "in_the_rest": round(db(rms(cut(audio, rate, rests[0] + 6, back[0] - 0.5))), 1),
                                  "after_it": round(db(rms(cut(audio, rate, back[0] + 3, back[0] + 9))), 1)}
        passes.update({
            "the beat holds up to the rest (tempo within 0.05%)": abs(grid.bpm / bpm - 1) <= 0.0005,
            "the storm brings at least 6 dB of low end": report["low_end_db"]["storm_0:30_to_0:37"]
                - report["low_end_db"]["calm_0:09_to_0:15"] >= 6,
            "rain is not muffled (the top end does not drop)":
                report["top_end_db"]["rain_0:18_to_0:27"] >= report["top_end_db"]["calm_0:09_to_0:15"] - 1.0
                and report["top_end_db"]["storm_0:40_to_0:54"] >= report["top_end_db"]["calm_0:09_to_0:15"] - 1.0,
            "there is a rest, and it is silent": bool(rests and back) and report["level_db"]["in_the_rest"] <= -70,
            "the music comes back after the rest": bool(rests and back) and report["level_db"]["after_it"] >= -40,
        })
    report["passes"] = passes
    (out / (name + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("rendered %.0f s of %s's music (%s) -> %s" % (
        report["seconds"], wanted, " + ".join(asset.set for asset in music), out / (name + ".mp3")))
    print("sections:", ", ".join("%s@%.1f" % (s["section"], s["at"]) for s in report["sections"]))
    for key in ("beat", "rest", "low_end_db", "top_end_db", "stealth_db", "level_db"):
        if key in report:
            print("%s: %s" % (key, report[key]))
    print("peak %.3f; late cells %s" % (report["peak"], report["late_cells"]))
    for line, passed in passes.items():
        print("  %s  %s" % ("PASS" if passed else "FAIL", line))


if __name__ == "__main__":
    asyncio.run(main())
