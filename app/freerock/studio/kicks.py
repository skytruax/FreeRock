"""House's own kick, designed here for the Geonkick drum synthesiser (2026-11-21: "i think mainly your instruments suck for
house", "and design yourself").

House struck the TR-8's 909 kick as it comes. A progressive house kick is a sine that falls from a couple of hundred hertz
to the bottom in a few dozen milliseconds and holds there a moment (the body, felt), with a short click on top (the
attack, heard on small loudspeakers), a little saturation for the harmonics, and short enough that the bass can roll
between the beats. Geonkick keeps a drum as JSON; the designs here are written onto one of its own presets (Harald
Revery's F kick, for its shape of the format) with every oscillator but the body and the click switched off.

An envelope is a list of points (time as a share of the drum's length, value 0 to 1) times its amplitude; a frequency
envelope's value is read on a logarithmic scale from 20 Hz up to its amplitude (`freq`).

    desk.geonkick("own/house kick")      the drum, as a REAPER track writes it
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

TEMPLATE = "HaraldReveryKicks/F-Kick"
TOP = 1000.0                     # the frequency envelopes' amplitude: their value 1 is this many hertz


def freq(hz: float) -> float:
    """A frequency as a point's value on the logarithmic scale from 20 Hz to TOP."""
    return math.log(hz / 20.0) / math.log(TOP / 20.0)


# Each design: its length in ms, the body's pitch (ms, Hz) and level (ms, 0-1) as it falls, the click's level and
# how long it lasts, and the drive.
DESIGNS: dict[str, dict] = {
    # The body: a sine from 240 Hz to 52 Hz (between G#1 and A1), slower through the punch (105 Hz at 25 ms, 72 at 45) than a
    # bare drop, at full for 35 ms, half down by 120 ms and gone at 320 ms, so that at 110 to 124 beats a minute the bass
    # has the back of each beat to itself. The punch: a triangle on the same fall, its odd harmonics the 100 to 250 Hz a
    # small loudspeaker plays, gone in 150 ms. The click: white noise high-passed at 1.8 kHz, gone in 8 ms. Driven, for
    # the rest of the harmonics. (2026-11-21, the first try, a sine alone with a quieter click: everything over 120 Hz 48 dB
    # under its body against the 909's 20 to 24; its tail at -12 dB 200 ms on against the 909's 120 to 140. The second, with
    # the triangle and the slower fall: 60 to 120 Hz and the tail as the 909's, over 120 Hz still 13 to 17 dB clean. The
    # third, driven through an open input: within 1 to 4 dB of the 909 up to 2 kHz, the click 11 dB short, the drive's hold
    # stretching the tail to 187 ms at -12 dB: the body falls sooner now, and the click is louder and longer.)
    "house kick": {"length": 300.0,
                   "pitch": [(0.0, 240.0), (10.0, 160.0), (25.0, 105.0), (45.0, 72.0), (80.0, 56.0), (300.0, 52.0)],
                   "level": [(0.0, 0.0), (1.0, 1.0), (35.0, 1.0), (100.0, 0.42), (180.0, 0.1), (280.0, 0.0)],
                   "punch": 0.55, "punch_level": [(0.0, 0.0), (1.0, 1.0), (30.0, 0.6), (90.0, 0.15), (150.0, 0.0)],
                   "click": 1.0, "click_ms": 10.0, "click_hz": 2200.0, "drive": 3.0, "drive_in": 0.6, "drive_out": 0.5},
    # (2026-11-22, night: the one kick above stood in for all four machines.) Each machine's own, drawn after its kick as the
    # TR-8 plays it and read alongside it (to -12, -24 and -40 dB from its peak; its body's pitch at 5, 15, 30 and 60 ms;
    # 120-500 Hz, 500 Hz-2 kHz and 2-8 kHz against its body at 40-120 Hz). Driven harder than the 909's for the harmonics an
    # analogue drum has in its middle, and so falling sooner, since the drive holds a tail up.
    # The 808: 54, 159, 296 ms; 84, 58, 49, 46 Hz, the deepest body and the least fall; 120-500 Hz 11 dB under its body,
    # 2-8 kHz 43: round, the punch and the click soft. Drawn: 76, 172, 260 ms; 76, 61, 52 Hz; -13, -29, -40 dB.
    "house kick 808": {"length": 320.0,
                       "pitch": [(0.0, 95.0), (6.0, 80.0), (15.0, 60.0), (30.0, 50.0), (60.0, 47.0), (320.0, 45.0)],
                       "level": [(0.0, 0.0), (1.0, 1.0), (15.0, 1.0), (50.0, 0.33), (120.0, 0.1), (220.0, 0.03), (300.0, 0.0)],
                       "punch": 0.8, "punch_level": [(0.0, 0.0), (1.0, 1.0), (25.0, 0.6), (80.0, 0.15), (140.0, 0.0)],
                       "click": 0.06, "click_ms": 5.0, "click_hz": 1500.0, "drive": 4.5, "drive_in": 0.6, "drive_out": 0.45},
    # The 707: 42, 51, 71 ms, a knock and gone; 108 to 55 Hz in 30 ms; its middle and top only 19 dB under its body: the
    # knock is half of it, a burst of noise round 2 kHz. Drawn: 27, 38, 71 ms; 105, 84, 61 Hz; -11, -22, -17 dB.
    "house kick 707": {"length": 110.0,
                       "pitch": [(0.0, 140.0), (5.0, 110.0), (15.0, 82.0), (30.0, 60.0), (110.0, 55.0)],
                       "level": [(0.0, 0.0), (1.0, 1.0), (28.0, 1.0), (45.0, 0.25), (62.0, 0.06), (100.0, 0.0)],
                       "punch": 0.3, "punch_level": [(0.0, 0.0), (1.0, 1.0), (15.0, 0.5), (40.0, 0.0)],
                       "click": 1.2, "click_ms": 40.0, "click_hz": 2000.0, "click_type": 2, "drive": 3.5, "drive_in": 0.5, "drive_out": 0.5},
    # The 606: 93, 290, 546 ms, the longest boom; a body at 55 Hz from the first, hardly falling; 120-500 Hz 13 dB under it,
    # 2-8 kHz 41: dark, a soft click. Drawn: 108, 316, 546 ms; 73, 61, 52 Hz; -13, -30, -40 dB.
    "house kick 606": {"length": 560.0,
                       "pitch": [(0.0, 75.0), (8.0, 62.0), (25.0, 56.0), (560.0, 54.0)],
                       "level": [(0.0, 0.0), (1.0, 1.0), (15.0, 1.0), (55.0, 0.26), (190.0, 0.075), (400.0, 0.025), (546.0, 0.01), (556.0, 0.0)],
                       "punch": 0.9, "punch_level": [(0.0, 0.0), (1.0, 1.0), (30.0, 0.5), (110.0, 0.0)],
                       "click": 0.06, "click_ms": 5.0, "click_hz": 1500.0, "drive": 5.0, "drive_in": 0.6, "drive_out": 0.42},
    # The hard songs' (2026-11-24, "house is a little better keep iterating"). Read alone through a hard act's drum bus, the kick above is a knock and a sine: 19 dB from its loudness to its peak, its body
    # 12 dB down by 170 ms, so that what the other instruments left of it was a click. A hard one is driven into a ceiling at the desk (club.HARD_KICK, sounds.clip): as tall, 2 to 3 dB
    # louder, 12 to 14 dB from its loudness to its peak, its body held 190 to 350 ms. These are drawn for that: a fall from higher, the triangle's knock as tall as the body and longer, a harder
    # click, and gone before the next beat. The 909's is the hammer, the 606's a boom torn as far as it goes, the 808's round. (The 606's and the 808's clicks at first as soft as their machines': with
    # the old kick's click gone Blast Furnace's drums were 6 dB short over 5 kHz.) Each is tuned where its song is ("house kick hard@46.2": `design`).
    "house kick hard": {"length": 300.0,
                        "pitch": [(0.0, 460.0), (6.0, 235.0), (15.0, 138.0), (30.0, 88.0), (55.0, 61.0), (100.0, 51.5), (300.0, 49.0)],
                        "level": [(0.0, 0.0), (1.0, 1.0), (38.0, 1.0), (80.0, 0.4), (130.0, 0.12), (190.0, 0.03), (270.0, 0.0)],
                        "punch": 1.0, "punch_level": [(0.0, 0.0), (1.0, 1.0), (45.0, 0.8), (110.0, 0.25), (180.0, 0.0)],
                        "click": 2.2, "click_ms": 16.0, "click_hz": 2600.0, "drive": 6.0, "drive_in": 0.8, "drive_out": 0.42},
    "house kick hard 606": {"length": 360.0,
                            "pitch": [(0.0, 300.0), (8.0, 170.0), (20.0, 105.0), (40.0, 70.0), (80.0, 55.0), (130.0, 50.0), (360.0, 49.0)],
                            "level": [(0.0, 0.0), (1.0, 1.0), (45.0, 1.0), (95.0, 0.4), (150.0, 0.13), (215.0, 0.03), (320.0, 0.0)],
                            "punch": 1.2, "punch_level": [(0.0, 0.0), (1.0, 1.0), (60.0, 0.8), (130.0, 0.2), (200.0, 0.0)],
                            "click": 2.4, "click_ms": 18.0, "click_hz": 2400.0, "drive": 10.0, "drive_in": 0.9, "drive_out": 0.38},
    "house kick hard 808": {"length": 360.0,
                            "pitch": [(0.0, 220.0), (8.0, 120.0), (20.0, 78.0), (45.0, 58.0), (90.0, 50.0), (360.0, 49.0)],
                            "level": [(0.0, 0.0), (1.0, 1.0), (45.0, 1.0), (110.0, 0.42), (180.0, 0.14), (260.0, 0.03), (340.0, 0.0)],
                            "punch": 0.9, "punch_level": [(0.0, 0.0), (1.0, 1.0), (40.0, 0.7), (110.0, 0.2), (180.0, 0.0)],
                            "click": 1.9, "click_ms": 14.0, "click_hz": 2400.0, "drive": 5.0, "drive_in": 0.7, "drive_out": 0.45},
}
REACH = (41.0, 59.0)             # where a kick may come to rest, Hz: E1 to A#1


def rest(tonic: int) -> float:
    """Where a hard song's kick comes to rest: on the song's root, or where that is under or over a kick's reach on its fifth."""
    for step in (0, 7):
        hz = 440.0 * 2.0 ** (((tonic + step) % 12 + 24 - 69) / 12.0)
        if REACH[0] <= hz <= REACH[1]:
            return hz
    return 49.0


def design(name: str, presets: Path) -> dict:
    """The design as a Geonkick drum (one preset file's JSON). "house kick hard@46.2": its whole fall moved so that it comes to rest at 46.2 Hz."""
    plain, _, tail = name.partition("@")
    spec = DESIGNS[plain]
    if tail:
        moved = float(tail) / spec["pitch"][-1][1]
        spec = dict(spec, pitch=[(ms, hz * moved) for ms, hz in spec["pitch"]])
    drum = json.loads((presets / (TEMPLATE + ".gkick")).read_text(encoding="utf-8"))
    out = copy.deepcopy(drum)
    length = spec["length"]
    at = lambda ms: min(max(ms / length, 0.0), 1.0)          # noqa: E731
    kick = out["kick"]
    kick["name"] = name
    kick["layers"] = [0]
    kick["layers_amplitude"] = [1.0, 0.0, 0.0]
    kick["ampl_env"] = {"amplitude": 1.0, "length": length, "points": [[0.0, 1.0], [1.0, 1.0]]}
    # (The drive works on what its input lets through: Harald Revery's kick has it at 0.02, which left the first try's drive
    # doing nothing; 0.6 here, and the output taken down.)
    kick["distortion"].update(enabled=spec["drive"] > 1.0, drive=spec["drive"], in_limiter=spec.get("drive_in", 0.2),
                              volume=spec.get("drive_out", 1.0))
    kick["compressor"]["enabled"] = False
    kick["filter"]["enabled"] = False
    for index in range(9):
        out["osc%d" % index]["enabled"] = False
    body = out["osc1"]
    body.update(enabled=True, is_fm=False, function=0, phase=0.0)
    body["ampl_env"] = {"amplitude": 1.0, "apply_type": 0, "points": [[at(ms), value] for ms, value in spec["level"]]}
    body["freq_env"] = {"amplitude": TOP, "apply_type": 1, "points": [[at(ms), freq(hz)] for ms, hz in spec["pitch"]]}
    body["filter"]["enabled"] = False
    punch = out["osc0"]                                     # the layer's other oscillator: a triangle on the body's fall
    punch.update(enabled=spec["punch"] > 0.0, is_fm=False, function=2, phase=0.0)
    punch["ampl_env"] = {"amplitude": spec["punch"], "apply_type": 0, "points": [[at(ms), value] for ms, value in spec["punch_level"]]}
    punch["freq_env"] = copy.deepcopy(body["freq_env"])
    punch["filter"]["enabled"] = False
    click = out["osc2"]
    click.update(enabled=True, is_fm=False, function=4, phase=0.0)
    click["ampl_env"] = {"amplitude": spec["click"], "apply_type": 0,
                         "points": [[0.0, 1.0], [at(spec["click_ms"]), 0.0], [1.0, 0.0]]}
    click["filter"].update(enabled=True, type=spec.get("click_type", 1), cutoff=spec["click_hz"])     # 1 high-pass, 2 band-pass
    return out
