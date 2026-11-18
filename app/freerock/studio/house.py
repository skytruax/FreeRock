"""The dance floor: FreeRock's own progressive house, written here and played by studio.club.

Nobody is asked for anything. A track is made up from a number: its drums, its bass line, its
chords, its tune and its pads are written as notes by the code below. The writer still calls the
studio's own synthesiser (studio.synth) as it writes; studio.club stands in for those calls, takes
every note down, and has real instruments play them in REAPER, each channel alone, so that what is
staged is a recording for each channel (see the studio's own notes for what a staged track is).

A FAMILY is a set of changes: a key, the chords bar by bar, where in the bar the kick falls, and
the lengths of the five parts of the story. Every track tells that story:

    open     pads and a filtered figure, no kick
    theme    the groove: kick, bass, the riff, and the tune's hook stated once or twice
    rise     the breakdown: the drums drop out, the tune is played whole and alone, then a roll
             and a riser build to
    moment   the drop: everything, with the tune on top at its brightest
    close    the band leaves one at a time

A TAKE is a whole track of its own written over a family's changes: its own drum pattern, bass
line, chord figure, tune and pad, in its own sounds. Because every take of a family follows the
same chords and the same kick, any channel of one fits the other channels of another, and the
player swaps them: three takes are 243 different bands.

Families are written for kinds of place (kinds.KINDS) and kinds of moment (the director's
places): each kind of place has its own scales, sounds, grooves and percussion, some families
light and some heavier, and there are families for the inn, the night, the depths, a storm, a
fight and a boss.

Every track is brought to one level before it is staged (its moment to MOMENT_LUFS, its peaks
under CEILING: see `master`), and measured, since nobody is listening while it is made: how loud
each part of the story is, whether the kick is on the beat, whether the parts are in tune and in
the key. What it measured is kept beside it as measured.json.

    uv run --no-sync --with numba python -m freerock.studio.club pastoral-01/1 [...]   write and play tracks (club.py)
    uv run --no-sync --with numba python -m freerock.studio.club --list               what the plan holds
    uv run --no-sync --with numba python -m pytest tests/test_studio_house.py          its tests

(numba compiles the synthesiser's inner loops. It is not one of FreeRock's own requirements,
which is why it is asked for on the command line.)
"""
from __future__ import annotations

import json
import math
import random
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d

from .. import analysis, forever
from . import read_track, stage_root, synth, write_track
from .synth import BAND, HIGH, LOW, SAW, SINE, SQUARE, TRIANGLE, Keys, Patch, String

RATE = synth.RATE
BPM = 110
BEAT = 60.0 / BPM
STEP = BEAT / 4.0              # a sixteenth, in seconds
BAR = 4.0 * BEAT
BAR_FRAMES = RATE * 240.0 / BPM
POST_S = forever.POST_S
MOMENT_LUFS = -13.0            # how loud every track is where it is fullest
CEILING = 0.89                 # and the most the whole of it ever reaches, of full scale
VAR = Path(__file__).resolve().parents[3] / "var"
NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MODES = {
    "major": (0, 2, 4, 5, 7, 9, 11), "lydian": (0, 2, 4, 6, 7, 9, 11), "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10), "minor": (0, 2, 3, 5, 7, 8, 10), "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "phrygian dominant": (0, 1, 4, 5, 7, 8, 10),
}
# What a chord is made of, in steps of the scale above its root.
COLOURS = {"": (0, 2, 4), "7": (0, 2, 4, 6), "9": (0, 2, 4, 8), "sus2": (0, 1, 4), "sus4": (0, 3, 4), "5": (0, 4, 7),
           "6": (0, 2, 4, 5)}
# The changes: a mode, how many bars each chord lasts, and the chords (the step of the scale each
# is built on, and its colour). Each is one turn of a loop that the sections go round.
LOOPS = {
    "M1": ("major", 2, ((0, ""), (4, ""), (5, "7"), (3, ""))),
    "M2": ("major", 2, ((5, "7"), (3, ""), (0, ""), (4, ""))),
    "M3": ("major", 2, ((0, "9"), (5, "7"), (3, "9"), (4, "sus4"))),
    "M4": ("major", 1, ((3, ""), (0, ""), (4, ""), (5, "7"))),
    "M5": ("major", 2, ((0, ""), (2, "7"), (3, ""), (4, ""))),
    "M6": ("major", 2, ((1, "7"), (4, ""), (0, "9"), (5, "7"))),
    "L1": ("lydian", 2, ((0, ""), (1, ""), (0, "9"), (1, ""))),
    "L2": ("lydian", 2, ((0, "9"), (1, ""), (6, "7"), (0, ""))),
    "L3": ("lydian", 1, ((0, ""), (4, ""), (1, ""), (0, "sus2"))),
    "X1": ("mixolydian", 2, ((0, ""), (6, ""), (3, ""), (0, ""))),
    "X2": ("mixolydian", 2, ((0, ""), (4, "7"), (3, ""), (0, "sus4"))),
    "X3": ("mixolydian", 1, ((0, ""), (3, ""), (6, ""), (3, ""))),
    "D1": ("dorian", 2, ((0, "7"), (3, ""), (0, "7"), (3, "9"))),
    "D2": ("dorian", 2, ((0, "7"), (2, ""), (6, ""), (3, ""))),
    "D3": ("dorian", 2, ((0, ""), (6, ""), (3, ""), (0, "sus4"))),
    "D4": ("dorian", 1, ((0, "7"), (1, "7"), (2, ""), (3, ""))),
    "N1": ("minor", 2, ((0, ""), (5, ""), (2, ""), (6, ""))),
    "N2": ("minor", 2, ((0, ""), (6, ""), (5, ""), (6, "sus4"))),
    "N3": ("minor", 2, ((5, ""), (6, ""), (0, ""), (0, "sus4"))),
    "N4": ("minor", 2, ((0, "7"), (3, "7"), (5, ""), (4, "7"))),
    "N5": ("minor", 1, ((0, ""), (2, ""), (6, ""), (5, ""))),
    "N6": ("minor", 2, ((0, "9"), (5, "7"), (3, "7"), (6, ""))),
    "P1": ("phrygian", 2, ((0, ""), (1, ""), (0, ""), (6, ""))),
    "P2": ("phrygian", 2, ((0, ""), (1, ""), (2, ""), (1, ""))),
    "P3": ("phrygian dominant", 2, ((0, ""), (1, ""), (0, ""), (6, ""))),
    "P4": ("phrygian dominant", 2, ((0, ""), (3, ""), (1, ""), (0, ""))),
}
# Where in the bar the kick falls, in sixteenths. A family has one, and every take keeps to it:
# everything but the drums ducks under the kick, so the kick is part of the changes.
KICKS = {"four": (0, 4, 8, 12), "broken": (0, 6, 10), "broken2": (0, 6, 8, 14), "broken3": (0, 3, 8, 10),
         "half": (0, 10), "none": ()}
# How much is going on through each part of the story, from 0 to 1, at its beginning and its end.
ARCS = {
    "wander": {"open": (0.2, 0.5), "theme": (0.6, 0.72), "rise": (0.4, 0.95), "moment": (1.0, 1.0), "close": (0.72, 0.2)},
    "ember": {"open": (0.2, 0.4), "theme": (0.5, 0.6), "rise": (0.4, 0.66), "moment": (0.78, 0.78), "close": (0.55, 0.2)},
    "storm": {"open": (0.45, 0.65), "theme": (0.75, 0.8), "rise": (0.5, 1.0), "moment": (1.0, 1.0), "close": (0.8, 0.4)},
    "battle": {"open": (0.8, 0.88), "theme": (0.86, 0.9), "rise": (0.6, 1.0), "moment": (1.0, 1.0), "close": (0.9, 0.7)},
}
BREAKDOWN = (0.3, 0.5)          # the breakdown's energy, from its first bar to its last (see Take.breakdown)
# The calm moments: an inn, the night, a camp. They have no drop to speak of, no roll into one and no line doubled over the
# tune, and they play under the usual level.
CALM_ROLES = ("ember", "night", "camp")
ARC_OF = {"wander": "wander", "night": "wander", "depths": "wander", "ember": "ember", "camp": "ember", "storm": "storm",
          "battle": "battle", "boss": "battle", "town": "wander", "battleground": "battle"}

# ---------------------------------------------------------------------------------------------
# Sounds
# ---------------------------------------------------------------------------------------------
BASS = {
    # (The sine under a bass is on the note itself: the note is already as low as a bass goes.
    "sub": Patch(wave=SINE, cutoff=2500, attack=0.008, decay=0.2, sustain=0.9, release=0.06, drive=0.5),
    # The filters hardly ring: a filter that rings at 200 Hz makes the third overtone the note.)
    "saw": Patch(wave=SAW, sub=1.1, sub_ratio=1.0, cutoff=330, env=2.0, env_decay=0.12, res=0.05, poles=2, attack=0.004,
                 decay=0.18, sustain=0.75, release=0.05, follow=0.3),
    "reese": Patch(wave=SAW, voices=2, detune=24, sub=1.1, sub_ratio=1.0, cutoff=280, env=1.2, env_decay=0.3, res=0.06, poles=2,
                   attack=0.006, decay=0.3, sustain=0.85, release=0.07, drive=0.15, follow=0.3),
    "pluck": Patch(wave=SQUARE, sub=1.1, sub_ratio=1.0, cutoff=240, env=3.0, env_decay=0.08, res=0.1, poles=2, attack=0.003,
                   decay=0.14, sustain=0.4, release=0.05, follow=0.3),
    "square": Patch(wave=SQUARE, sub=0.8, sub_ratio=1.0, cutoff=420, env=1.0, env_decay=0.2, res=0.04, poles=2, attack=0.005,
                    decay=0.2, sustain=0.8, release=0.05, follow=0.3),
    "fm": Keys(ratio=1.0, index=2.4, index_decay=0.12, index_sustain=0.35, attack=0.003, decay=0.4, sustain=0.5,
               release=0.06, detune=0.0, width=0.0),
    "organ": Keys(ratio=2.0, index=0.0, index_sustain=0.0, second=0.6, third=0.25, attack=0.004, decay=0.25, sustain=0.6,
                  release=0.05, detune=0.0, width=0.0),
}
KEYS = {
    "pluck": Patch(wave=SAW, voices=3, detune=14, spread=0.6, b_level=0.25, b_ratio=2.0, cutoff=420, env=4.2,
                   env_decay=0.11, res=0.3, attack=0.002, decay=0.22, sustain=0.08, release=0.18, highpass=150),
    "stab": Patch(wave=SAW, voices=5, detune=24, spread=0.8, cutoff=1800, env=2.0, env_decay=0.15, res=0.15, attack=0.004,
                  decay=0.25, sustain=0.3, release=0.12, highpass=180),
    "keys": Keys(ratio=1.0, index=1.4, index_decay=0.25, index_sustain=0.15, decay=1.2, sustain=0.0, release=0.25,
                 detune=3.0, width=0.5),
    "piano": Keys(ratio=2.0, index=1.8, index_decay=0.18, index_sustain=0.1, decay=0.9, sustain=0.0, release=0.2,
                  second=0.15, detune=4.0, width=0.6),
    "organ": Keys(ratio=1.0, index=0.0, index_sustain=0.0, second=0.7, third=0.4, attack=0.005, decay=0.3, sustain=0.75,
                  release=0.08, detune=3.0, width=0.4),
    "marimba": Keys(ratio=4.0, index=1.6, index_decay=0.04, index_sustain=0.0, decay=0.35, sustain=0.0, release=0.2,
                    detune=2.0, width=0.4),
    # (A bell whose overtones are whole multiples of the note: a real bell's are not, and four of
    # those in a chord are a clang.)
    "bell": Keys(ratio=4.0, index=1.7, index_decay=0.7, index_sustain=0.05, decay=1.8, sustain=0.0, release=0.8,
                 second=0.12, detune=5.0, width=0.7),
    "glass": Keys(ratio=2.0, index=0.8, index_decay=1.2, index_sustain=0.3, attack=0.02, decay=2.0, sustain=0.2,
                  release=0.6, detune=6.0, width=0.8),
    "string": String(sustain=1.4, bright=0.65, body=0.75),
    "oud": String(sustain=0.7, bright=0.45, body=0.9),
    "harp": String(sustain=2.2, bright=0.55, body=0.5),
    "brass": Patch(wave=SAW, voices=4, detune=16, spread=0.6, cutoff=600, env=2.6, env_decay=0.35, res=0.1, attack=0.03,
                   decay=0.3, sustain=0.7, release=0.15, highpass=150),
}
LEADS = {
    "saw": Patch(wave=SAW, voices=3, detune=14, spread=0.4, cutoff=3200, env=1.2, env_decay=0.25, res=0.15, attack=0.008,
                 decay=0.25, sustain=0.75, release=0.22, vib_rate=5.5, vib_depth=10, vib_delay=0.25, glide=0.035, highpass=200),
    "super": Patch(wave=SAW, voices=7, detune=30, spread=0.9, cutoff=4500, env=0.8, env_decay=0.3, attack=0.01, decay=0.3,
                   sustain=0.8, release=0.3, highpass=250),
    "hollow": Patch(wave=SQUARE, voices=2, detune=8, spread=0.3, cutoff=2400, env=1.0, env_decay=0.3, attack=0.01,
                    decay=0.3, sustain=0.7, release=0.2, vib_rate=5.0, vib_depth=8, glide=0.03, highpass=200),
    "whistle": Patch(wave=SINE, noise=0.035, cutoff=6000, attack=0.04, decay=0.3, sustain=0.85, release=0.18,
                     vib_rate=5.2, vib_depth=16, vib_delay=0.18, glide=0.05, b_level=0.06, b_ratio=2.0, b_wave=SINE),
    "flute": Patch(wave=TRIANGLE, noise=0.05, cutoff=3500, attack=0.05, decay=0.3, sustain=0.8, release=0.2,
                   vib_rate=4.8, vib_depth=12, vib_delay=0.25, glide=0.03),
    "pipe": Patch(wave=SAW, b_level=0.4, b_ratio=1.0, b_wave=SQUARE, cutoff=2200, res=0.4, attack=0.015, decay=0.2,
                  sustain=0.9, release=0.08, glide=0.02, highpass=300),
    "pluck": Patch(wave=SAW, voices=3, detune=12, spread=0.5, b_level=0.3, b_ratio=2.0, cutoff=700, env=3.6,
                   env_decay=0.16, res=0.25, attack=0.002, decay=0.35, sustain=0.15, release=0.25, highpass=200),
    "bell": KEYS["bell"], "keys": KEYS["piano"], "string": KEYS["string"], "glass": KEYS["glass"],
    "marimba": KEYS["marimba"], "oud": KEYS["oud"], "harp": KEYS["harp"], "brass": KEYS["brass"],
}
PADS = {
    # (They let go in about a second: a pad that hangs on sits on top of the next chord.)
    "super": Patch(wave=SAW, voices=7, detune=26, spread=0.95, attack=0.7, decay=1.5, sustain=0.8, release=0.55,
                   cutoff=2400, res=0.08, highpass=180),
    "warm": Patch(wave=SAW, voices=5, detune=18, spread=0.8, attack=1.0, decay=2.0, sustain=0.75, release=0.65,
                  cutoff=900, res=0.1, highpass=120),
    "strings": Patch(wave=SAW, voices=6, detune=22, spread=0.9, attack=0.5, decay=1.0, sustain=0.85, release=0.5,
                     cutoff=3200, highpass=220),
    "glass": Keys(ratio=2.0, index=0.9, index_decay=2.0, index_sustain=0.4, attack=0.6, decay=3.0, sustain=0.6,
                  release=0.7, detune=7.0, width=0.9),
    "organ": Keys(ratio=1.0, index=0.0, index_sustain=0.0, second=0.5, third=0.3, attack=0.3, decay=1.0, sustain=0.8,
                  release=0.4, detune=5.0, width=0.8),
    "hollow": Patch(wave=SQUARE, voices=4, detune=14, spread=0.9, attack=0.8, decay=1.5, sustain=0.8, release=0.6,
                    cutoff=1400, highpass=150),
}

_trims: dict[tuple[int, int], float] = {}


def trim(sound: Any, pitch: int) -> float:
    """What to multiply a sound's level by so that it is as loud as any other. Left alone, a
    plucked string is a fraction as loud as a stack of saws asked for at the same level, and a
    tune that changes voice between two parts of a track would change loudness with it. Each
    sound is played once, a note of half a second at `pitch`, and brought to one level."""
    if (id(sound), pitch) not in _trims:
        out = synth.blank(1.5)
        synth.play(out, sound, 0.0, 0.45, pitch, 1.0, seed=1)
        heard = float(np.sqrt(np.mean(out[:synth.frames(0.5)].astype(np.float64) ** 2)))
        if not heard > 0.0:
            raise ValueError("A sound that makes no sound: %r" % (sound,))
        _trims[(id(sound), pitch)] = 0.2 / heard
    return _trims[(id(sound), pitch)]


# What each kind of place and moment sounds like: for each channel the sounds and the ways of
# playing a take may draw on (the three takes of a family take different ones), the percussion
# beside the kit, and the weather in the gaps.
PALETTES: dict[str, dict[str, Any]] = {
    "pastoral": dict(bass=("pluck", "organ", "sub", "fm"), bass_style=("offbeat", "tresillo", "offbeat_oct", "synco"),
                     keys=("string", "keys", "pluck", "harp", "piano"), keys_style=("strum", "stabs", "arp", "broken"),
                     lead=("whistle", "keys", "string", "flute"), pad=("warm", "strings", "organ", "glass"),
                     perc=("tambourine", "maracas", "clap2", "snap"), hats=("eighths", "off", "shuffle", "sixteenths"),
                     atmos="", voicing="close"),
    "pastoral-deep": dict(bass=("saw", "pluck", "reese", "square"), bass_style=("rolling", "offbeat", "synco"),
                          keys=("pluck", "piano", "string", "stab"), keys_style=("arp", "stabs", "broken"),
                          lead=("saw", "flute", "pluck", "hollow"), pad=("super", "warm", "strings", "hollow"),
                          perc=("maracas", "tambourine", "rim"), hats=("sixteenths", "off", "eighths"), atmos="", voicing="close"),
    "highland": dict(bass=("sub", "square", "pluck"), bass_style=("offbeat", "long", "tresillo"),
                     keys=("harp", "pluck", "organ", "string"), keys_style=("arp", "broken", "pumpchords", "strum"),
                     lead=("pipe", "whistle", "flute", "hollow"), pad=("warm", "hollow", "strings", "organ"),
                     perc=("rim", "tambourine", "tom", "snap"), hats=("eighths", "shuffle", "off"), atmos="wind", voicing="open"),
    "highland-deep": dict(bass=("reese", "saw", "sub"), bass_style=("driving", "rolling", "long"),
                          keys=("brass", "pluck", "harp", "stab"), keys_style=("stabs", "arp", "pumpchords"),
                          lead=("pipe", "saw", "hollow", "super"), pad=("hollow", "super", "warm"),
                          perc=("tom", "rim", "maracas"), hats=("sixteenths", "eighths", "sparse"), atmos="wind", voicing="open"),
    "haunted-light": dict(bass=("sub", "fm", "organ"), bass_style=("long", "offbeat", "dub"),
                          keys=("bell", "keys", "marimba", "glass"), keys_style=("arp", "broken", "stabs"),
                          lead=("glass", "whistle", "keys", "bell"), pad=("glass", "organ", "warm", "hollow"),
                          perc=("rim", "chime", "snap"), hats=("sparse", "eighths", "off"), atmos="wind", voicing="close"),
    "haunted-dark": dict(bass=("reese", "sub", "saw"), bass_style=("dub", "long", "rolling"),
                         keys=("bell", "organ", "pluck", "glass"), keys_style=("stabs", "arp", "pumpchords"),
                         lead=("hollow", "bell", "saw", "glass"), pad=("organ", "hollow", "glass"),
                         perc=("rim", "chime", "clave"), hats=("sparse", "sixteenths", "off"), atmos="wind", voicing="close"),
    "desert": dict(bass=("pluck", "fm", "square"), bass_style=("tresillo", "synco", "offbeat"),
                   keys=("oud", "string", "marimba", "pluck"), keys_style=("strum", "arp", "broken"),
                   lead=("oud", "flute", "hollow", "pipe"), pad=("warm", "hollow", "glass"),
                   perc=("bongo", "tambourine", "agogo", "timbale"), hats=("shuffle", "eighths", "sparse"), atmos="wind", voicing="open"),
    "desert-dark": dict(bass=("saw", "reese", "fm"), bass_style=("synco", "driving", "tresillo"),
                        keys=("oud", "pluck", "brass", "marimba"), keys_style=("arp", "strum", "stabs"),
                        lead=("hollow", "oud", "saw", "flute"), pad=("hollow", "warm", "super"),
                        perc=("bongo", "timbale", "clave"), hats=("sixteenths", "shuffle", "eighths"), atmos="wind", voicing="open"),
    "jungle": dict(bass=("pluck", "organ", "fm"), bass_style=("rolling", "tresillo", "synco"),
                   keys=("marimba", "pluck", "string", "organ"), keys_style=("arp", "broken", "stabs"),
                   lead=("flute", "marimba", "whistle", "pluck"), pad=("warm", "glass", "strings"),
                   perc=("conga", "agogo", "cabasa", "bongo"), hats=("shuffle", "sixteenths", "eighths"), atmos="", voicing="close"),
    "jungle-dark": dict(bass=("reese", "saw", "pluck"), bass_style=("rolling", "synco", "dub"),
                        keys=("marimba", "pluck", "organ", "stab"), keys_style=("arp", "stabs", "broken"),
                        lead=("flute", "hollow", "pluck", "saw"), pad=("hollow", "warm", "glass"),
                        perc=("conga", "quijada", "bongo", "clave"), hats=("sixteenths", "shuffle", "sparse"), atmos="", voicing="close"),
    "infernal-light": dict(bass=("saw", "square", "pluck"), bass_style=("driving", "offbeat", "rolling"),
                           keys=("brass", "stab", "piano", "pluck"), keys_style=("stabs", "pumpchords", "arp"),
                           lead=("saw", "brass", "hollow", "super"), pad=("super", "hollow", "strings"),
                           perc=("cowbell", "clave", "tom"), hats=("sixteenths", "off", "eighths"), atmos="fire", voicing="close"),
    "infernal-dark": dict(bass=("reese", "saw", "square"), bass_style=("driving", "rolling", "synco"),
                          keys=("stab", "brass", "pluck", "piano"), keys_style=("stabs", "arp", "pumpchords"),
                          lead=("saw", "hollow", "super", "brass"), pad=("hollow", "super", "organ"),
                          perc=("cowbell", "tom", "clave"), hats=("sixteenths", "eighths", "off"), atmos="fire", voicing="close"),
    "regal": dict(bass=("saw", "organ", "pluck"), bass_style=("offbeat_oct", "offbeat", "driving"),
                  keys=("brass", "piano", "stab", "organ"), keys_style=("stabs", "pumpchords", "broken"),
                  lead=("super", "brass", "saw", "keys"), pad=("strings", "super", "warm"),
                  perc=("clap2", "tambourine", "ride", "snap"), hats=("off", "eighths", "sixteenths"), atmos="", voicing="close"),
    "regal-deep": dict(bass=("reese", "saw", "square"), bass_style=("rolling", "driving", "offbeat"),
                       keys=("brass", "stab", "pluck"), keys_style=("pumpchords", "stabs", "arp"),
                       lead=("saw", "super", "hollow"), pad=("strings", "hollow", "super"),
                       perc=("ride", "tom", "rim"), hats=("sixteenths", "off", "eighths"), atmos="", voicing="close"),
    "mystic": dict(bass=("sub", "fm", "organ"), bass_style=("long", "offbeat", "tresillo"),
                   keys=("harp", "glass", "bell", "keys"), keys_style=("arp", "broken", "strum"),
                   lead=("glass", "whistle", "harp", "bell"), pad=("glass", "strings", "warm", "organ"),
                   perc=("chime", "rim", "maracas"), hats=("sparse", "eighths", "off"), atmos="sea", voicing="close"),
    "mystic-deep": dict(bass=("sub", "reese", "fm"), bass_style=("long", "dub", "rolling"),
                        keys=("glass", "harp", "pluck"), keys_style=("arp", "pumpchords", "broken"),
                        lead=("hollow", "glass", "saw"), pad=("glass", "hollow", "super"),
                        perc=("chime", "rim", "clave"), hats=("sparse", "sixteenths", "eighths"), atmos="sea", voicing="close"),
    "ember": dict(bass=("sub", "organ", "fm"), bass_style=("long", "dub", "offbeat"),
                  keys=("keys", "string", "harp", "glass"), keys_style=("broken", "strum", "arp"),
                  lead=("whistle", "keys", "glass", "flute"), pad=("warm", "organ", "glass"),
                  perc=("snap", "maracas", "rim"), hats=("sparse", "eighths", "shuffle"), atmos="fire", voicing="close"),
    "night": dict(bass=("sub", "fm", "pluck"), bass_style=("long", "offbeat", "dub"),
                  keys=("bell", "glass", "keys", "harp"), keys_style=("arp", "broken", "stabs"),
                  lead=("glass", "flute", "whistle", "keys"), pad=("glass", "warm", "hollow"),
                  perc=("rim", "maracas", "chime"), hats=("sparse", "eighths", "shuffle"), atmos="crickets", voicing="close"),
    "depths": dict(bass=("sub", "reese", "fm"), bass_style=("dub", "long", "synco"),
                   keys=("stab", "organ", "bell", "glass"), keys_style=("dub", "stabs", "arp"),
                   lead=("hollow", "glass", "bell", "saw"), pad=("hollow", "organ", "glass"),
                   perc=("rim", "clave", "chime"), hats=("sparse", "off", "eighths"), atmos="drips", voicing="close"),
    "storm": dict(bass=("reese", "saw", "square"), bass_style=("driving", "rolling", "synco"),
                  keys=("stab", "pluck", "brass"), keys_style=("arp", "stabs", "pumpchords"),
                  lead=("saw", "hollow", "super"), pad=("super", "hollow", "strings"),
                  perc=("tom", "ride", "maracas"), hats=("sixteenths", "eighths", "off"), atmos="rain", voicing="close"),
    "battle": dict(bass=("reese", "saw", "pluck"), bass_style=("driving", "rolling", "synco"),
                   keys=("stab", "brass", "pluck"), keys_style=("stabs", "arp", "pumpchords"),
                   lead=("saw", "super", "hollow"), pad=("super", "hollow", "strings"),
                   perc=("tom", "cowbell", "ride"), hats=("sixteenths", "off", "eighths"), atmos="", voicing="close"),
    # The new kinds of place (2026-11-17, evening: "make sure all genres got the updates around new place categories"): the
    # marsh's dub bass, marimba and glass, a jawbone rattle and drips; the coast's harp and strummed strings, whistle and the
    # sea; the snow's bells and glass and wind. Each a light one and a deep one, as the others are.
    "marsh": dict(bass=("sub", "fm", "pluck"), bass_style=("dub", "long", "offbeat"),
                  keys=("marimba", "pluck", "glass", "organ"), keys_style=("arp", "broken", "dub"),
                  lead=("flute", "hollow", "pipe", "glass"), pad=("hollow", "warm", "glass"),
                  perc=("quijada", "conga", "rim", "cabasa"), hats=("sparse", "shuffle", "eighths"), atmos="drips", voicing="close"),
    "marsh-dark": dict(bass=("reese", "sub", "saw"), bass_style=("dub", "rolling", "long"),
                       keys=("organ", "pluck", "glass", "marimba"), keys_style=("stabs", "arp", "dub"),
                       lead=("hollow", "glass", "saw", "pipe"), pad=("hollow", "organ", "glass"),
                       perc=("quijada", "rim", "clave"), hats=("sparse", "sixteenths", "off"), atmos="rain", voicing="close"),
    "coast": dict(bass=("pluck", "sub", "organ"), bass_style=("offbeat", "tresillo", "offbeat_oct"),
                  keys=("harp", "string", "pluck", "keys"), keys_style=("strum", "arp", "broken"),
                  lead=("whistle", "flute", "keys", "hollow"), pad=("warm", "glass", "strings"),
                  perc=("tambourine", "maracas", "snap", "clap2"), hats=("eighths", "off", "shuffle"), atmos="sea", voicing="open"),
    "coast-deep": dict(bass=("saw", "reese", "pluck"), bass_style=("rolling", "driving", "offbeat"),
                       keys=("pluck", "string", "brass", "stab"), keys_style=("arp", "stabs", "pumpchords"),
                       lead=("saw", "hollow", "whistle", "super"), pad=("super", "hollow", "warm"),
                       perc=("tom", "rim", "maracas"), hats=("sixteenths", "off", "eighths"), atmos="sea", voicing="open"),
    "frozen": dict(bass=("sub", "fm", "square"), bass_style=("long", "offbeat", "tresillo"),
                   keys=("bell", "glass", "harp", "keys"), keys_style=("arp", "broken", "strum"),
                   lead=("glass", "bell", "flute", "whistle"), pad=("glass", "warm", "hollow"),
                   perc=("chime", "rim", "snap"), hats=("sparse", "eighths", "off"), atmos="wind", voicing="open"),
    "frozen-deep": dict(bass=("reese", "sub", "square"), bass_style=("long", "rolling", "driving"),
                        keys=("bell", "pluck", "glass", "brass"), keys_style=("stabs", "arp", "pumpchords"),
                        lead=("hollow", "glass", "saw", "super"), pad=("hollow", "glass", "super"),
                        perc=("chime", "tom", "rim"), hats=("sparse", "sixteenths", "eighths"), atmos="wind", voicing="open"),
}


# ---------------------------------------------------------------------------------------------
# Families: the plan
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Family:
    name: str
    title: str
    moods: tuple[str, ...]
    role: str
    serves: tuple[int, ...]
    light: bool
    tonic: int                     # 0 is C
    loop: str                      # which of LOOPS
    sections: tuple[int, int, int, int, int]
    groove: str                    # which of KICKS
    swing: float                   # how late the off sixteenths are, as a share of one
    kit: str                       # the drum machine: 909, 808, 707 or 606
    palette: str

    @property
    def mode(self) -> str:
        return LOOPS[self.loop][0]

    @property
    def key(self) -> str:
        return "%s %s" % (NAMES[self.tonic], self.mode.split()[0])

    @property
    def seed(self) -> int:
        return zlib.crc32(self.name.encode("utf-8"))

    @property
    def bars(self) -> int:
        return sum(self.sections)

    @property
    def hard(self) -> bool:
        return self.role in ("battle", "boss", "battleground")

    @property
    def story(self) -> tuple[tuple[str, int], ...]:
        """The track's story in two waves, as a house track is built (2026-11-17, night: the tracks were one wave of
        about three minutes; the night's tracks are about eight): the intro, the theme at twice its length, the rise,
        a first drop; then a breakdown on the theme, the rise again, and the last drop at twice its length; the outro.
        Every part a whole number of eight-bar phrases, as the family's shape has them."""
        opening, theme, rise, moment, close = self.sections
        return (("open", opening), ("theme", 2 * theme), ("rise", rise), ("moment", moment), ("theme", theme), ("rise", rise),
                ("moment", 2 * moment), ("close", close))


ANY = ()
W, S01, S0, S2, S012 = "wander", (0, 1), (0,), (2,), (0, 1, 2)
E5, T8 = (16, 16, 16, 16, 16), (8, 24, 16, 24, 8)          # two of the shapes a story takes, in bars
# (2026-11-17, evening: the marsh, the coast and the snowfields became kinds of place. Until House has families written for
# them, the nearest of its own are theirs too: River Drums, The Old Swamp and Drowned Halls for the marsh; Morning on the Hill,
# Glade at Dusk and Drowned Halls for the coast; the High Moor, Stone and Sky and Larks over the Ridge for the snow.)
PLAN: tuple[Family, ...] = (
    # name, title, kinds of place, kind of moment, strengths, light, key, changes, shape, kick, swing, machine, sounds
    Family("pastoral-01", "Sunlit Fields", ("pastoral",), W, S01, True, 2, "M1", E5, "four", 0.08, "909", "pastoral"),
    Family("pastoral-02", "Morning on the Hill", ("pastoral", "coast"), W, S01, True, 7, "L2", T8, "four", 0.0, "707", "pastoral"),
    Family("pastoral-03", "Mill Stream", ("pastoral",), W, S01, True, 9, "X1", (16, 16, 8, 24, 16), "broken", 0.12, "606", "pastoral"),
    Family("pastoral-04", "Long Road Home", ("pastoral",), W, S01, False, 4, "D2", (16, 16, 16, 24, 8), "four", 0.0, "909", "pastoral-deep"),
    Family("highland-01", "Wind over the Pass", ("highland",), W, S01, True, 4, "X2", E5, "four", 0.0, "909", "highland"),
    Family("highland-02", "Snowmelt", ("highland",), W, S01, True, 0, "M5", (8, 16, 16, 24, 16), "four", 0.1, "707", "highland"),
    Family("highland-03", "The High Moor", ("highland", "frozen"), W, S01, False, 9, "D3", E5, "broken2", 0.0, "808", "highland-deep"),
    Family("highland-04", "Stone and Sky", ("highland", "frozen"), W, S01, False, 6, "N1", (16, 24, 8, 24, 8), "four", 0.0, "909", "highland-deep"),
    Family("highland-05", "Larks over the Ridge", ("highland", "frozen"), W, S01, True, 10, "L2", (16, 16, 8, 24, 16), "four", 0.08, "606", "highland"),
    Family("haunted-01", "Lanterns in the Fog", ("haunted",), W, S01, True, 2, "D1", E5, "four", 0.06, "808", "haunted-light"),
    Family("haunted-02", "The Kind Ghost", ("haunted",), W, S01, True, 11, "N6", (16, 16, 8, 24, 16), "broken", 0.0, "606", "haunted-light"),
    Family("haunted-03", "Bells under the Hill", ("haunted",), W, S01, False, 2, "N2", (16, 16, 16, 24, 8), "four", 0.0, "909", "haunted-dark"),
    Family("haunted-04", "Hollow Road", ("haunted",), W, S01, False, 0, "N4", T8, "four", 0.0, "808", "haunted-dark"),
    Family("haunted-05", "Will-o'-the-Wisp", ("haunted",), W, S01, True, 4, "D4", (8, 16, 16, 24, 16), "broken3", 0.1, "707", "haunted-light"),
    Family("desert-01", "Caravan at Noon", ("desert",), W, S01, True, 4, "P3", E5, "broken3", 0.1, "707", "desert"),
    Family("desert-02", "Oasis", ("desert",), W, S01, True, 2, "X3", (16, 16, 8, 24, 16), "four", 0.12, "606", "desert"),
    Family("desert-03", "Red Rock", ("desert",), W, S01, False, 6, "P1", (16, 24, 8, 24, 8), "four", 0.0, "909", "desert-dark"),
    Family("desert-04", "Mirage", ("desert",), W, S01, False, 11, "P4", T8, "broken", 0.08, "808", "desert-dark"),
    Family("desert-05", "Dunes at Dawn", ("desert",), W, S01, True, 9, "X2", T8, "four", 0.1, "808", "desert"),
    Family("jungle-01", "Canopy", ("jungle",), W, S01, True, 7, "X1", E5, "four", 0.14, "707", "jungle"),
    Family("jungle-02", "River Drums", ("jungle", "marsh"), W, S01, True, 0, "D1", T8, "broken2", 0.1, "808", "jungle"),
    Family("jungle-03", "Night Prowl", ("jungle",), W, S01, False, 9, "N1", (16, 16, 16, 24, 8), "four", 0.06, "909", "jungle-dark"),
    Family("jungle-04", "The Old Swamp", ("jungle", "marsh"), W, S01, False, 7, "N4", (16, 24, 8, 24, 8), "broken3", 0.0, "808", "jungle-dark"),
    Family("jungle-05", "Parrots", ("jungle",), W, S01, True, 5, "M4", E5, "broken", 0.12, "606", "jungle"),
    Family("infernal-01", "The Forge at Rest", ("infernal",), W, S01, True, 2, "D3", E5, "four", 0.0, "909", "infernal-light"),
    Family("infernal-02", "Hammerfall", ("infernal",), W, S01, False, 0, "N2", (16, 16, 8, 24, 16), "four", 0.0, "909", "infernal-dark"),
    Family("infernal-03", "Ash Wind", ("infernal",), W, S01, False, 4, "P2", T8, "broken", 0.0, "808", "infernal-dark"),
    Family("infernal-04", "Bellows and Sparks", ("infernal",), W, S01, True, 7, "D2", (8, 16, 16, 24, 16), "four", 0.0, "707", "infernal-light"),
    Family("regal-01", "The King's Road", ("regal",), W, S01, True, 2, "M2", E5, "four", 0.0, "909", "regal"),
    Family("regal-02", "Banners", ("regal",), W, S01, True, 5, "M4", T8, "four", 0.06, "707", "regal"),
    Family("regal-03", "Market Day", ("regal",), W, S01, True, 10, "X2", (16, 16, 8, 24, 16), "broken2", 0.14, "606", "regal"),
    Family("regal-04", "The Long Watch", ("regal",), W, S01, False, 4, "N3", (16, 16, 16, 24, 8), "four", 0.0, "909", "regal-deep"),
    Family("mystic-01", "Moonwell", ("mystic",), W, S01, True, 4, "L1", E5, "four", 0.0, "808", "mystic"),
    Family("mystic-02", "Starfall", ("mystic",), W, S01, True, 8, "L3", T8, "broken", 0.08, "606", "mystic"),
    Family("mystic-03", "Glade at Dusk", ("mystic", "coast"), W, S01, True, 6, "D4", (16, 16, 8, 24, 16), "four", 0.1, "707", "mystic"),
    Family("mystic-04", "Drowned Halls", ("mystic", "marsh", "coast"), W, S01, False, 11, "N6", (16, 24, 8, 24, 8), "four", 0.0, "808", "mystic-deep"),
    # (The new kinds' own, 2026-11-17, evening.)
    Family("marsh-01", "Bullfrog Bass", ("marsh",), W, S01, True, 7, "D2", T8, "broken2", 0.1, "808", "marsh"),
    Family("marsh-02", "Peat Smoke", ("marsh",), W, S01, False, 2, "N3", (16, 24, 8, 24, 8), "broken3", 0.0, "808", "marsh-dark"),
    Family("marsh-03", "Reedlight", ("marsh",), W, S01, True, 9, "L3", E5, "four", 0.08, "707", "marsh"),
    Family("coast-01", "Seaspray", ("coast",), W, S01, True, 2, "X1", T8, "four", 0.0, "909", "coast"),
    Family("coast-02", "Gull's Morning", ("coast",), W, S01, True, 5, "M5", (16, 16, 8, 24, 16), "four", 0.06, "707", "coast"),
    Family("coast-03", "Breakwater", ("coast",), W, S01, False, 9, "D3", (16, 24, 8, 24, 8), "broken2", 0.0, "909", "coast-deep"),
    Family("frozen-01", "Snowglobe", ("frozen",), W, S01, True, 4, "L1", E5, "four", 0.0, "707", "frozen"),
    Family("frozen-02", "Ice Bridge", ("frozen",), W, S01, False, 11, "N5", (16, 24, 8, 24, 8), "four", 0.0, "909", "frozen-deep"),
    Family("frozen-03", "Northern Lights", ("frozen",), W, S01, True, 1, "D4", T8, "broken", 0.06, "606", "frozen"),
    Family("ember-01", "By the Fire", ("pastoral", "regal", "highland"), "ember", S01, True, 0, "M6", (8, 16, 8, 16, 8), "half", 0.16, "808", "ember"),
    Family("ember-02", "Last Candle", ("haunted", "mystic"), "ember", S01, True, 5, "L1", (8, 16, 8, 16, 8), "none", 0.0, "606", "ember"),
    Family("ember-03", "Cool of the Evening", ("desert", "jungle", "infernal"), "ember", S01, True, 7, "X3", (8, 16, 8, 16, 8), "half", 0.12, "707", "ember"),
    Family("night-01", "Fireflies", ("pastoral", "regal", "highland", "mystic"), "night", S01, True, 4, "M3", E5, "four", 0.06, "808", "night"),
    Family("night-02", "Owl Light", ("haunted", "mystic", "jungle"), "night", S01, False, 5, "N5", (16, 16, 8, 24, 16), "broken", 0.0, "606", "night"),
    Family("night-03", "Cold Stars", ("desert", "highland", "infernal"), "night", S01, True, 11, "D1", T8, "four", 0.0, "808", "night"),
    Family("depths-01", "Under the Mountain", ("highland", "regal", "infernal"), "depths", S01, False, 2, "N2", E5, "four", 0.0, "808", "depths"),
    Family("depths-02", "Dripstone", ("haunted", "mystic", "jungle"), "depths", S01, False, 3, "D1", (16, 24, 8, 24, 8), "broken2", 0.05, "909", "depths"),
    Family("depths-03", "The Deep Road", ("desert", "pastoral"), "depths", S01, False, 1, "N3", T8, "four", 0.0, "808", "depths"),
    Family("storm-01", "Rain on the Roofs", ("pastoral", "regal", "highland", "mystic"), "storm", S01, False, 4, "N1", (8, 16, 16, 24, 8), "four", 0.0, "909", "storm"),
    Family("storm-02", "Thunderhead", ("haunted", "infernal", "desert", "jungle"), "storm", S01, False, 5, "N2", (8, 24, 8, 24, 8), "broken2", 0.0, "909", "storm"),
    Family("battle-01", "Charge", ("pastoral", "regal", "highland"), "battle", S2, False, 9, "N3", (4, 16, 8, 16, 8), "four", 0.0, "909", "battle"),
    Family("battle-02", "Blades", ("haunted", "infernal"), "battle", S2, False, 4, "P1", (4, 16, 8, 16, 8), "four", 0.0, "909", "battle"),
    Family("battle-03", "Ambush", ("desert", "jungle"), "battle", S2, False, 7, "N2", (4, 16, 8, 16, 8), "broken2", 0.0, "808", "battle"),
    Family("battle-04", "Stand Fast", ("mystic", "highland", "regal"), "battle", S2, False, 11, "N1", (4, 16, 8, 24, 8), "four", 0.0, "909", "battle"),
    Family("boss-01", "The Dark Hall", ("haunted", "infernal", "desert", "jungle"), "boss", S2, False, 1, "P2", (8, 16, 8, 24, 8), "four", 0.0, "909", "battle"),
    Family("boss-02", "Last Stand", ("pastoral", "regal", "highland", "mystic"), "boss", S2, False, 2, "N4", (8, 16, 8, 24, 8), "four", 0.0, "909", "battle"),
    # Towns and battlegrounds have music of their own in every style (2026-11-17, night: "Dont forget caves inns pvp ect").
    # A town is light and busy, a market at evening; a battleground is a fight that goes on and on, its own family.
    Family("town-01", "Lanterns on the Square", ("regal", "pastoral", "highland"), "town", S01, True, 5, "M2", (8, 16, 8, 16, 8), "four", 0.06, "707", "regal"),
    Family("town-02", "Harbour Lights", ("desert", "jungle", "mystic", "haunted", "infernal"), "town", S01, True, 9, "X3", (8, 16, 8, 16, 8), "broken2", 0.1, "606", "desert"),
    Family("battleground-01", "Hold the Line", ANY, "battleground", S012, False, 7, "N1", (4, 16, 8, 16, 8), "four", 0.0, "909", "battle"),
    Family("battleground-02", "Capture the Flag", ANY, "battleground", S012, False, 0, "P2", (4, 16, 8, 24, 8), "broken2", 0.0, "808", "battle"),
    # Camping (2026-11-17: "camping should get its own tunes"): a long wait in one spot out of doors. Deep and slow, the
    # kick at half time or none, as the inn's and the night's music are.
    Family("camp-01", "Embers under Stars", ("pastoral", "regal", "highland"), "camp", S01, True, 2, "L2", (8, 16, 8, 16, 8), "half", 0.08, "606", "ember"),
    Family("camp-02", "The Long Wait", ("haunted", "infernal", "mystic"), "camp", S01, False, 9, "D3", (8, 16, 8, 16, 8), "none", 0.0, "808", "night"),
    Family("camp-03", "Heat Haze", ("desert", "jungle", "mystic"), "camp", S01, True, 6, "X1", (8, 16, 8, 16, 8), "half", 0.12, "707", "ember"),
)
TAKES = (1, 2, 3)
NUMERALS = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}


def family(name: str) -> Family:
    for each in PLAN:
        if each.name == name:
            return each
    raise KeyError("No family called %r" % name)


# ---------------------------------------------------------------------------------------------
# Tunes
# ---------------------------------------------------------------------------------------------
# Rhythms for two bars of a tune, in sixteenths: (where a note begins, how long it is).
HOOKS = (
    ((0, 3), (3, 3), (6, 2), (8, 6), (16, 3), (19, 3), (22, 2), (24, 6)),
    ((0, 2), (2, 2), (4, 4), (8, 3), (11, 5), (16, 2), (18, 2), (20, 4), (24, 6)),
    ((0, 6), (6, 2), (8, 4), (12, 4), (16, 6), (22, 2), (24, 6)),
    ((2, 2), (4, 2), (6, 2), (8, 6), (14, 2), (16, 4), (20, 4), (24, 6)),
    ((0, 4), (4, 4), (8, 3), (11, 3), (14, 2), (16, 10)),
    ((0, 3), (3, 1), (4, 4), (8, 3), (11, 1), (12, 4), (16, 3), (19, 3), (22, 2), (24, 6)),
    ((0, 8), (8, 4), (12, 4), (16, 8), (24, 6)),
    ((0, 2), (3, 2), (6, 2), (8, 2), (11, 2), (14, 2), (16, 6), (24, 6)),
)
FLOWS = (
    ((0, 2), (2, 2), (4, 2), (6, 2), (8, 4), (12, 2), (14, 2), (16, 2), (18, 2), (20, 2), (22, 2), (24, 6)),
    ((0, 1), (1, 1), (2, 2), (4, 2), (6, 2), (8, 6), (16, 1), (17, 1), (18, 2), (20, 2), (22, 2), (24, 6)),
    ((0, 3), (3, 3), (6, 3), (9, 3), (12, 4), (16, 3), (19, 3), (22, 3), (25, 5)),
    ((0, 4), (4, 2), (6, 2), (8, 4), (12, 4), (16, 4), (20, 2), (22, 2), (24, 6)),
)
LONGS = (
    ((0, 12), (12, 4), (16, 14)),
    ((0, 8), (8, 8), (16, 10), (26, 4)),
    ((0, 6), (6, 10), (16, 8), (24, 6)),
)
SHAPES = {
    "arch": lambda u: 4.0 * math.sin(math.pi * u) - 1.0,
    "rising": lambda u: -2.0 + 5.0 * u,
    "falling": lambda u: 3.0 - 5.0 * u,
    "valley": lambda u: 1.5 - 3.5 * math.sin(math.pi * u),
    "wave": lambda u: 2.5 * math.sin(2.0 * math.pi * u),
}


@dataclass
class Air:
    """One sound of a track's air, as the writer asks for it: a sweep of noise (between `low` and `high` Hz, `rising`
    or falling), the climb into a drop (a sawtooth from `pitch`), the drop's thud, or weather (wind, sea, rain, fire,
    drips, crickets) faded in and out over `fade` seconds. The house desk plays it in REAPER (studio/jsfx/air); the
    writer's own render makes it here (`Take.air_audio`)."""
    kind: str
    at: float                      # seconds
    seconds: float
    level: float
    low: float = 0.0
    high: float = 0.0
    rising: bool = True
    pitch: int = 60
    fade: float = 0.0
    seed: int = 0


@dataclass
class Tone:
    """One note of a tune: where it begins and how long it is in sixteenths from the tune's own
    beginning, which step of the scale it is (0 is the key note in the tune's home octave), and
    how hard it is played."""
    at: float
    length: float
    degree: int
    loud: float = 0.7


class Changes:
    """A family's harmony: which chord sounds in any bar of a section, and the notes of things."""

    def __init__(self, fam: Family):
        self.family = fam
        self.scale = MODES[fam.mode]
        mode, self.slot, chords = LOOPS[fam.loop]
        self.loop = chords
        self.turn = self.slot * len(chords)           # bars in one turn of the loop

    def chord(self, bar: int) -> tuple[int, str]:
        """The chord in a bar, counted from the beginning of its section: every section starts
        at the top of the loop."""
        return self.loop[(bar // self.slot) % len(self.loop)]

    def pitch(self, degree: int, octave: int = 5) -> int:
        """The MIDI note of a step of the scale: step 0 in octave 5 is the key note at or above middle C."""
        return 12 * octave + self.family.tonic + self.scale[degree % 7] + 12 * (degree // 7)

    def within(self, chord: tuple[int, str], degree: int) -> bool:
        """Whether a step of the scale is one of a chord's notes."""
        return (degree - chord[0]) % 7 in {step % 7 for step in COLOURS[chord[1]]}

    def voicing(self, chord: tuple[int, str], low: int, high: int, before: list[int] | None = None,
                spread: str = "close") -> list[int]:
        """The notes of a chord between two MIDI notes, laid out so that they move as little as
        can be from the chord before. `open` leaves the third out: root, fifth and octave."""
        steps = (0, 4, 7) if spread == "open" else COLOURS[chord[1]]
        tones = sorted({self.pitch(chord[0] + step, 0) % 12 for step in steps})
        best, least = None, 1e9
        centre = (low + high) / 2.0
        for bottom in range(low, low + 12):
            if bottom % 12 not in tones:
                continue
            notes = [note for note in range(bottom, high + 1) if note % 12 in tones][:max(len(tones), 3) + (1 if len(tones) < 4 else 0)]
            if len(notes) < 3:
                continue
            if before:
                # (By the note, so that a thinner chord is not the cheaper one.)
                cost = sum(min(abs(note - old) for old in before) for note in notes) / len(notes) + 0.3 * abs(notes[-1] - before[-1])
            else:
                cost = abs(sum(notes) / len(notes) - centre)
            if cost < least:
                best, least = notes, cost
        if best is None:
            raise ValueError("No way to lay out %r between %d and %d" % (chord, low, high))
        return best


class Tune:
    """A tune of sixteen bars over a family's changes, written from a number.

    It is made the way tunes are: a short idea of two bars (a rhythm and a shape) is stated,
    answered by itself moved to fit the next chord, left for something that climbs higher, and
    comes back to close. The second eight bars say it again with small turns added and the
    climb a third higher. Notes on the strong beats and the long notes are notes of the chord
    under them; the notes between move by step."""

    def __init__(self, changes: Changes, rng: random.Random, home: int = 67):
        # (The middle of the tune at G4, not D5 as it was: 2026-11-17, morning, "your house needs some work". Against
        # the liked house stems the leads had nothing under 320 Hz and 6 to 19 dB too much from 900 Hz to 3.5 kHz, where
        # the liked leads have their weight at 200 to 450 Hz: a house hook sits in the warm middle, not over the band.)
        self.changes, self.rng = changes, rng
        # The step of the scale nearest `home` (a MIDI note) is the middle of the tune's range.
        self.centre = min(range(-7, 22), key=lambda degree: abs(changes.pitch(degree) - home))
        self.low, self.high = self.centre - 6, self.centre + 7
        hook = rng.choice(HOOKS)
        other = rng.choice(FLOWS + LONGS)
        shape = rng.choice(("arch", "rising", "valley", "wave", "arch"))
        a = self._write(hook, 0, shape, 0)
        a2 = self._answer(a, 2)
        b = self._write(other, 4, rng.choice(("arch", "rising")), 2 + rng.randrange(2))
        a3 = self._close(self._answer(a, 6), 6)
        second_a2 = self._turns(self._answer(a, 10))
        second_b = self._answer(b, 12, lift=2)
        a4 = self._close(self._answer(a, 14), 14)
        self.idea = a
        self.first = a + self._moved(a2, 32) + self._moved(b, 64) + self._moved(a3, 96)
        self.second = self._moved(self._answer(a, 8), 128) + self._moved(second_a2, 160) + self._moved(second_b, 192) + self._moved(a4, 224)
        self.notes = self.first + self.second

    @staticmethod
    def _moved(notes: list[Tone], by: float) -> list[Tone]:
        return [Tone(note.at + by, note.length, note.degree, note.loud) for note in notes]

    def _chord(self, bar: int, at: float) -> tuple[int, str]:
        return self.changes.chord(bar + int(at // 16))

    @staticmethod
    def _strong(at: float, length: float) -> bool:
        return at % 8 == 0 or length >= 4

    def _write(self, rhythm: tuple[tuple[int, int], ...], bar: int, shape: str, lift: int) -> list[Tone]:
        """Two bars over the chords from `bar`: each note the one that best follows the shape,
        moves by step from the last, and sits on the chord where it is strong."""
        curve, out, before, leapt, same = SHAPES[shape], [], None, 0, 0
        for index, (at, length) in enumerate(rhythm):
            chord = self._chord(bar, at)
            strong = self._strong(at, length) or index == len(rhythm) - 1
            want = self.centre + lift + curve(at / 32.0)
            best, least = None, 1e9
            for degree in range(self.low, self.high + 1):
                if strong and not self.changes.within(chord, degree):
                    continue
                cost = 0.9 * abs(degree - want) + self.rng.random() * 0.8
                if before is not None:
                    step = abs(degree - before)
                    cost += 0.0 if step == 1 else 0.5 if step == 2 else 0.9 * (step - 1) if step else (1.1 if strong else 2.0) + 3.0 * same
                    if leapt and (degree - before) * leapt >= 0:
                        cost += 1.5                      # after a leap, back the other way
                if cost < least:
                    best, least = degree, cost
            leapt = 0 if before is None or abs(best - before) < 3 else (1 if best > before else -1)
            same = same + 1 if best == before else 0
            out.append(Tone(at, length, best, 0.82 if strong else 0.64))
            before = best
        return out

    def _answer(self, notes: list[Tone], bar: int, lift: int | None = None) -> list[Tone]:
        """The same idea over other chords: moved up or down as a whole to where it fits them
        best, with its strong notes put on the chord."""
        def fit(shift: int) -> float:
            return sum(min(abs(note.degree + shift - degree) for degree in range(self.low - 3, self.high + 4)
                           if self.changes.within(self._chord(bar, note.at), degree))
                       for note in notes if self._strong(note.at, note.length))
        top, bottom = max(note.degree for note in notes), min(note.degree for note in notes)
        inside = [shift for shift in (-2, -1, 1, 2, 0) if top + shift <= self.high and bottom + shift >= self.low] or [0]
        if lift is not None:
            # As far up as asked, or as far as there is room for: squeezed against the top of
            # its range a climb becomes one note said over and over.
            shift = max((shift for shift in range(lift + 1) if top + shift <= self.high), default=0)
        else:
            shift = sorted(inside, key=lambda shift: (fit(shift), abs(shift) == 0, abs(shift)))[0]
        out, before = [], None
        for note in notes:
            degree = min(max(note.degree + shift, self.low), self.high)
            if self._strong(note.at, note.length):
                chord = self._chord(bar, note.at)
                near = [each for each in range(self.low, self.high + 1) if self.changes.within(chord, each)]
                degree = min(near, key=lambda each: (abs(each - degree), abs(each - (before if before is not None else degree))))
            out.append(Tone(note.at, note.length, degree, note.loud))
            before = degree
        return out

    def _close(self, notes: list[Tone], bar: int) -> list[Tone]:
        """The idea brought to rest: its last note long, on the root, third or fifth of the chord."""
        out = [Tone(note.at, note.length, note.degree, note.loud) for note in notes]
        last = out[-1]
        chord = self._chord(bar, last.at)
        rests = [degree for degree in range(self.low, self.high + 1) if (degree - chord[0]) % 7 in (0, 2, 4)
                 and self.changes.within(chord, degree)]
        before = out[-2].degree if len(out) > 1 else last.degree
        last.degree = min(rests, key=lambda degree: (abs(degree - before), (degree - chord[0]) % 7))
        last.length = max(30.0 - last.at, last.length)
        last.loud = 0.85
        return out

    def _turns(self, notes: list[Tone]) -> list[Tone]:
        """The idea with small turns added: a passing note between two notes a third apart."""
        out: list[Tone] = []
        for note, after in zip(notes, notes[1:] + [None]):
            if after is not None and abs(after.degree - note.degree) == 2 and note.length >= 2 and after.at == note.at + note.length:
                out.append(Tone(note.at, note.length - 1, note.degree, note.loud))
                out.append(Tone(note.at + note.length - 1, 1, (note.degree + after.degree) // 2, 0.55))
            else:
                out.append(Tone(note.at, note.length, note.degree, note.loud))
        return out


# ---------------------------------------------------------------------------------------------
# A take
# ---------------------------------------------------------------------------------------------
# Hi-hat figures for one bar: sound -> (sixteenth, how hard).
HATS = {
    "off": {"open": ((2, 0.8), (6, 0.8), (10, 0.8), (14, 0.8))},
    "eighths": {"hat": ((0, 0.45), (2, 0.8), (4, 0.45), (6, 0.8), (8, 0.45), (10, 0.8), (12, 0.45), (14, 0.8))},
    "sixteenths": {"hat": tuple((step, 0.8 if step % 4 == 2 else 0.5 if step % 2 == 0 else 0.32) for step in range(16)),
                   "open": ((14, 0.5),)},
    "shuffle": {"hat": ((0, 0.5), (3, 0.36), (4, 0.5), (6, 0.75), (7, 0.3), (8, 0.5), (11, 0.36), (12, 0.5), (14, 0.75), (15, 0.3))},
    "sparse": {"hat": ((2, 0.6), (10, 0.6)), "open": ((6, 0.55),)},
}
# Percussion figures for one bar: (sixteenth, sound, how hard).
PERCUSSION = {
    "tambourine": ((4, "tambourine", 0.7), (12, "tambourine", 0.7), (14, "tambourine", 0.4)),
    "maracas": tuple((step, "maracas", 0.75 if step % 4 == 2 else 0.45) for step in range(16)),
    "cabasa": tuple((step, "cabasa", 0.7 if step % 4 == 0 else 0.4) for step in range(0, 16, 2)),
    "clap2": ((4, "clap2", 0.5), (12, "clap2", 0.5), (15, "clap2", 0.25)),
    "rim": ((3, "rim", 0.6), (6, "rim", 0.5), (11, "rim", 0.6), (14, "rim", 0.45)),
    "snap": ((4, "snap", 0.7), (12, "snap", 0.7)),
    "clave": ((0, "clave", 0.6), (3, "clave", 0.6), (6, "clave", 0.6), (10, "clave", 0.6), (12, "clave", 0.6)),
    "cowbell": ((2, "cowbell", 0.5), (6, "cowbell", 0.35), (10, "cowbell", 0.5), (14, "cowbell", 0.35)),
    "conga": ((3, "conga_high", 0.7), (6, "conga_mute", 0.5), (7, "conga_mute", 0.4), (11, "conga_high", 0.7),
              (14, "conga_low", 0.75), (15, "conga_low", 0.5)),
    "bongo": ((1, "bongo_high", 0.5), (3, "bongo_low", 0.7), (6, "bongo_high", 0.6), (9, "bongo_high", 0.45),
              (11, "bongo_low", 0.7), (14, "bongo_high", 0.6)),
    "timbale": ((6, "timbale_high", 0.6), (7, "timbale_high", 0.4), (14, "timbale_low", 0.7)),
    "agogo": ((0, "agogo_high", 0.6), (3, "agogo_high", 0.5), (6, "agogo_low", 0.6), (10, "agogo_high", 0.5), (12, "agogo_low", 0.6)),
    "quijada": ((0, "quijada", 0.7),),
    "chime": ((0, "chime", 0.5),),
    "tom": ((10, "tom_high", 0.5), (13, "tom_mid", 0.55), (15, "tom_low", 0.6)),
    "ride": ((0, "ride", 0.4), (4, "ride", 0.55), (8, "ride", 0.4), (12, "ride", 0.55)),
}
EVERY = {"quijada": 4, "chime": 8, "tom": 2, "timbale": 2}          # figures that come only every so many bars
# Bass figures for one bar: (sixteenth, how long, which note of the chord).
BASSES = {
    "offbeat": ((2, 1.6, "R"), (6, 1.6, "R"), (10, 1.6, "R"), (14, 1.6, "R")),
    "offbeat_oct": ((2, 1.5, "R"), (6, 1.5, "O"), (10, 1.5, "R"), (14, 1.5, "O")),
    "rolling": ((1, 0.9, "R"), (2, 0.9, "R"), (3, 0.9, "R"), (5, 0.9, "R"), (6, 0.9, "R"), (7, 0.9, "O"), (9, 0.9, "R"),
                (10, 0.9, "R"), (11, 0.9, "R"), (13, 0.9, "R"), (14, 0.9, "F"), (15, 0.9, "O")),
    "driving": ((0, 1.7, "R"), (2, 1.7, "R"), (4, 1.7, "R"), (6, 1.7, "R"), (8, 1.7, "R"), (10, 1.7, "R"), (12, 1.7, "R"), (14, 1.7, "F")),
    "synco": ((0, 2.5, "R"), (3, 2.5, "R"), (6, 1.8, "R"), (10, 1.6, "O"), (12, 2.5, "R"), (15, 0.9, "A")),
    "tresillo": ((0, 2.8, "R"), (3, 2.8, "R"), (6, 1.8, "R"), (8, 2.8, "R"), (11, 2.8, "F"), (14, 1.8, "O")),
    "long": ((0, 15.0, "R"),),
    "dub": ((0, 3.0, "R"), (7, 1.5, "R"), (10, 3.0, "F")),
}
# Where chords are struck in a bar, by figure: (sixteenth, how long).
STABS = (
    ((2, 1.5), (6, 1.5), (10, 1.5), (14, 1.5)),
    ((0, 2.0), (3, 2.0), (6, 1.5), (8, 2.0), (11, 2.0), (14, 1.5)),
    ((0, 2.5), (6, 2.0), (10, 3.0)),
    ((3, 2.0), (6, 2.0), (11, 2.0), (14, 2.0)),
    ((0, 4.0), (6, 3.0)),
    ((2, 1.5), (5, 1.5), (8, 1.5), (11, 1.5), (14, 1.5)),
)
ARPS = ("up", "down", "updown", "pedal", "skip")



# The ground a House family is written for, as the orchestra's characters have theirs (orchestra.SETTINGS_OF), so that
# the player's preference for the piece written for the ground underfoot reaches House too (2026-11-18: "make sure all
# our new location, song switch, signal stuff, persists across all genres"): by its role where the role is a place of
# its own, otherwise by its first kind of place.
GROUND_OF_ROLE = {"ember": ("settlement",), "camp": ("road", "woods"), "depths": ("works",), "town": ("settlement",),
                  "battleground": ("fields", "fort"), "boss": ("ruins",), "battle": ("fields",)}
GROUND_OF_KIND = {"pastoral": ("fields",), "highland": ("heights",), "frozen": ("heights", "water"), "marsh": ("water",),
                  "coast": ("water",), "jungle": ("woods",), "haunted": ("graves", "woods"), "mystic": ("woods", "sacred"),
                  "regal": ("settlement",), "desert": ("wastes",), "infernal": ("works", "wastes")}


def ground(fam) -> tuple[str, ...]:
    if fam.role in GROUND_OF_ROLE:
        return GROUND_OF_ROLE[fam.role]
    return GROUND_OF_KIND.get(fam.moods[0], ()) if fam.moods else ()


class Take:
    """One whole track over a family's changes."""

    def __init__(self, fam: Family, take: int, bars: tuple[int, int, int, int, int] | None = None):
        self.family, self.take = fam, take
        self.changes = Changes(fam)
        self.palette = PALETTES[fam.palette]
        self.seed = fam.seed * 7 + take
        # The story in two waves (Family.story); a track staged before that, read back with its own lengths, in one.
        if bars is None:
            told = list(fam.story)
        elif len(bars) == len(fam.story):
            told = [(story, count) for (story, _), count in zip(fam.story, bars)]
        else:
            told = list(zip(forever.STORY, bars))
        self.sections: list[tuple[str, int, int]] = []
        first = 0
        for story, count in told:
            self.sections.append((story, first, count))
            first += count
        self.bars = first
        # The second wave's theme is the breakdown (2026-11-17, night: the tracks swung 4 to 9 dB from their quietest to
        # their loudest, the second wave's theme being the first's again, kick and all): the kick and the groove drop
        # out and the bass holds one note to a bar far down, until the rise brings them back for the last drop. A fight
        # does not break down.
        themes = [first for story, first, _ in self.sections if story == "theme"]
        self.breakdown = themes[1] if len(themes) > 1 and not fam.hard else None
        self.frames = int(round(self.bars * BAR_FRAMES)) + int(round(POST_S * RATE))
        self.kick = KICKS[fam.groove]
        self.arc = ARCS[ARC_OF[fam.role]]
        self.tune = Tune(self.changes, self.rng("tune"))

    # --- what a take is made of ----------------------------------------------------------------
    def rng(self, what: str) -> random.Random:
        return random.Random(zlib.crc32(("%d/%s" % (self.seed, what)).encode("utf-8")))

    def pick(self, what: str, options: tuple) -> Any:
        """One of a family's choices for this take: the takes of a family take them in turn, so
        that three takes are three different bands."""
        return options[(self.take - 1 + zlib.crc32((self.family.name + what).encode("utf-8"))) % len(options)]

    def at(self, bar: int, step: float) -> float:
        """When a sixteenth of a bar is, in seconds. The off sixteenths come late by the swing."""
        late = self.family.swing * STEP if float(step).is_integer() and int(step) % 2 == 1 else 0.0
        return (bar * 16 + step) * STEP + late

    def energy(self, story: str, along: float, first_bar: int = -1) -> float:
        # (The breakdown lower than the theme, from little and growing: the kick's going was not enough on its own, a
        # jungle piece's breakdown was a decibel under its theme, 2026-11-17, night.)
        first, last = BREAKDOWN if self.broken(story, first_bar) else self.arc[story]
        if story == "rise":
            return first + (last - first) * along ** 1.8      # it holds back, then goes
        return first + (last - first) * along

    def blank(self) -> np.ndarray:
        return np.zeros((self.frames, 2), dtype=np.float32)

    def broken(self, story: str, first: int) -> bool:
        """Whether a section is the breakdown (see `__init__`)."""
        return story == "theme" and first == self.breakdown

    def kick_plays(self, story: str, bar: int, count: int, first: int = -1) -> bool:
        """Whether the kick is in at a bar of a section (beginning at bar `first`). The same for every take of a family."""
        if not self.kick or self.broken(story, first):
            return False
        if self.family.hard:
            return story != "rise" or bar < count // 2
        if story in ("theme", "moment"):
            return True
        return story == "close" and bar < max(count - 4, count // 2)

    def kicks(self) -> list[float]:
        """Every moment the kick falls, in seconds: what everything else ducks under."""
        return [self.at(first + bar, step) for story, first, count in self.sections for bar in range(count)
                if self.kick_plays(story, bar, count, first) for step in self.kick]

    def pumped(self, audio: np.ndarray, depth: float) -> np.ndarray:
        if not self.kick or depth <= 0:
            return audio
        return audio * synth.pump(len(audio), self.kicks(), depth=depth, release=0.24 if len(self.kick) >= 4 else 0.3)[:, None]

    # --- drums -------------------------------------------------------------------------------
    def drums(self) -> np.ndarray:
        fam, rng = self.family, self.rng("drums")
        dry, wet = self.blank(), self.blank()
        machine = fam.kit
        kick = "punch" if fam.hard else self.pick("kick", ("kick", "kick2", "kick"))
        kick_speed = 0.96 + 0.08 * ((fam.seed % 100) / 100.0)
        backbeat = self.pick("backbeat", (("clap",), ("clap", "snare"), ("snare2",)) if fam.groove != "half" and fam.role not in ("ember", "camp")
                             else (("snap",), ("rim",), ("clap",)))
        back_steps = (8,) if fam.groove in ("half", "none") else (4, 12)
        hat_figure = self.pick("hats", self.palette["hats"])
        hats = HATS[hat_figure]
        kinds = self.palette["perc"]
        first_perc = self.pick("perc", kinds)
        second_perc = kinds[(kinds.index(first_perc) + 1) % len(kinds)]
        clap_in = self.pick("clap-in", (0, 4, 8)) if not fam.hard else 0
        perc_in = self.pick("perc-in", (8, 4, 0)) if not fam.hard else 0
        fill = self.pick("fill", ("snare", "toms", "lift"))
        roll = self.pick("roll", ("snare", "clap", "crack")) if fam.role not in CALM_ROLES else self.pick("roll", ("maracas", "rim", "hat"))
        roll_level = 1.0 if fam.role not in CALM_ROLES else 0.45       # an inn has no drum roll: a shaker stirs
        pause = self.pick("pause", (True, False, True))
        sneak = self.pick("sneak", (True, True, False))

        def hit(buffer: np.ndarray, name: str, bar: int, step: float, level: float, pan: float = 0.0, speed: float = 1.0) -> None:
            synth.hit(buffer, synth.drum(name, machine), self.at(bar, step) + rng.gauss(0.0, 0.0015) * (name not in ("kick", "kick2", "punch")),
                      level * (1.0 + rng.gauss(0.0, 0.04)), pan, speed)

        def figure(name: str, bar: int, level: float, pan: float) -> None:
            if bar % EVERY.get(name, 1) != EVERY.get(name, 1) - 1:
                return
            for step, sound, loud in PERCUSSION[name]:
                if rng.random() < 0.06 and loud < 0.6:
                    continue                             # a ghost of a note left out here and there
                hit(wet, sound, bar, step, level * loud, pan)

        for story, first, count in self.sections:
            build = 4 if count >= 16 else 2
            for inside in range(count):
                bar, energy = first + inside, self.energy(story, inside / count, first)
                groove = (story in ("theme", "moment") and not self.broken(story, first)) or (story == "close" and inside < count - 2) \
                    or (fam.hard and story == "open")
                last = inside == count - 1
                filling = groove and inside % 8 == 7 and not (story == "close")
                if self.kick_plays(story, inside, count, first):
                    for step in self.kick:
                        if filling and fill == "lift" and step >= 12:
                            continue
                        hit(dry, kick, bar, step, 0.92, 0.0, kick_speed)
                if groove:
                    if story != "theme" or inside >= clap_in:
                        if not (story == "close" and inside >= count // 2):
                            for step in back_steps:
                                for sound in backbeat:
                                    hit(wet, sound, bar, step, 0.56 if sound != "snap" else 0.5)
                    for sound, steps in hats.items():
                        if sound == "open" and story == "theme" and inside < 8 and len(hats) > 1:
                            continue
                        for step, loud in steps:
                            if filling and step >= 12 and fill != "lift":
                                continue
                            # (2026-11-18: "too much high hat and not enough dynamic sound". The sixteenths between the
                            # eighths come only at a drop; every hat is 3 dB softer there and follows the story further
                            # under it: a theme's first bars 3 dB under the drop's, were 1.5.)
                            if hat_figure == "sixteenths" and sound == "hat" and step % 2 and story != "moment":
                                continue
                            hit(wet, sound, bar, step, 0.27 * loud * (0.3 + 0.7 * energy), 0.18 if sound == "hat" else -0.12)
                    if story == "moment" or inside >= perc_in:
                        figure(first_perc, bar, 0.34 * (0.6 + 0.4 * energy), -0.35)
                    if story == "moment":
                        figure(second_perc, bar, 0.3, 0.4)
                    if filling:
                        if fill == "snare":
                            for index, step in enumerate((12, 13, 14, 15)):
                                hit(wet, "snare", bar, step, 0.3 + 0.1 * index)
                        elif fill == "toms":
                            for step, sound, pan in ((10, "tom_high", -0.4), (12, "tom_mid", 0.0), (14, "tom_low", 0.4)):
                                hit(wet, sound, bar, step, 0.5, pan)
                        else:
                            hit(wet, "open", bar, 14, 0.4, -0.12)
                elif story == "open" and sneak and inside >= count // 2:
                    # Before the groove: a shaker or the hats, far off, coming closer.
                    near = (inside - count // 2) / max(count - count // 2, 1)
                    for step, sound, loud in PERCUSSION[first_perc if first_perc in ("maracas", "cabasa", "tambourine", "rim", "snap") else "maracas"]:
                        hit(wet, sound, bar, step, 0.12 + 0.16 * near * loud, -0.3)
                elif story == "close" and inside >= count - 2 and self.kick:
                    hit(wet, "hat", bar, 2, 0.12, 0.18)
                    hit(wet, "hat", bar, 10, 0.1, 0.18)
                if story == "rise" and inside >= count - build:
                    # The roll: slow, then twice as fast, then twice as fast again, climbing.
                    turn = inside - (count - build)
                    for step8 in range(32):
                        step = step8 / 2.0
                        along = (turn * 16 + step) / (build * 16.0)
                        every = 4.0 if along < 0.25 else 2.0 if along < 0.5 else 1.0 if along < 0.84 else 0.5
                        if step % every:
                            continue
                        if pause and last and step >= 12:
                            continue                     # the breath before the drop
                        hit(wet, roll, bar, step, (0.12 + 0.5 * along ** 1.4) * roll_level, 0.0, 0.92 + 0.3 * along * roll_level)
                if story in ("theme", "moment") and inside == 0:
                    hit(wet, "crash", bar, 0, 0.5 if story == "moment" else 0.32, -0.2)
                if story == "moment" and inside and inside % 8 == 0:
                    hit(wet, "crash", bar, 0, 0.34, 0.25)
                if fam.hard and story == "open" and inside == 0:
                    hit(wet, "crash", bar, 0, 0.5, -0.2)
                if fam.hard and story == "open" and last:
                    for step in range(8, 16):
                        hit(wet, "snare", bar, step, 0.25 + 0.05 * (step - 8), 0.0, 1.0 + 0.02 * (step - 8))
        return (dry + synth.hall(wet, seconds=0.9, wet=0.1, bright=10000.0)).astype(np.float32)

    # --- bass --------------------------------------------------------------------------------
    def bass_note(self, chord: tuple[int, str], which: str, after: tuple[int, str] | None = None) -> int:
        """A note of a chord for the bass, low: its root, fifth, octave, or a step up to the next root."""
        def low(pitch: int) -> int:
            while pitch < 31:
                pitch += 12
            while pitch >= 43:
                pitch -= 12
            return pitch
        root = low(self.changes.pitch(chord[0], 2))
        if which == "O":
            return root + 12
        if which == "F":
            return root + (self.changes.pitch(chord[0] + 4, 2) - self.changes.pitch(chord[0], 2)) % 12
        if which == "A" and after is not None and after != chord:
            target = low(self.changes.pitch(after[0], 2))
            under = target - (self.changes.pitch(after[0], 3) - self.changes.pitch(after[0] - 1, 3))
            return under if under >= 29 else under + 12
        return root

    def bass(self) -> np.ndarray:
        fam, rng = self.family, self.rng("bass")
        out = self.blank()
        sound_name = self.pick("bass", self.palette["bass"])
        sound = BASS[sound_name]
        style = self.pick("bass-style", self.palette["bass_style"])
        figure = BASSES[style]
        loud = trim(sound, 40)
        early = self.pick("bass-open", (False, True, False))
        builds = self.pick("bass-build", (True, False, True))
        for story, first, count in self.sections:
            build = 4 if count >= 16 else 2
            for inside in range(count):
                bar, energy = first + inside, self.energy(story, inside / count, first)
                chord, after = self.changes.chord(inside), self.changes.chord(inside + 1)
                bright = 0.4 + 0.6 * energy
                if (story in ("theme", "moment") and not self.broken(story, first)) or (fam.hard and story in ("open", "close")) \
                        or (story == "close" and self.kick_plays(story, inside, count, first)):
                    notes = figure
                    if story == "theme" and inside < 4 and style in ("rolling", "synco", "tresillo"):
                        notes = BASSES["offbeat"]              # it starts plainly and fills in
                    for step, length, which in notes:
                        pitch = self.bass_note(chord, which if not (which in ("O", "F") and story == "theme" and inside < 8) else "R", after)
                        synth.play(out, sound, self.at(bar, step), length * STEP * 0.92, pitch, loud * 0.5 * (0.85 + rng.random() * 0.15),
                                   seed=self.seed + bar * 16 + int(step), bright=bright)
                elif story == "close" or self.broken(story, first) or (story == "open" and early and inside >= count // 2):
                    # One long note to a bar, far down (the breakdown's too). (2026-11-17, morning: at a third of full it
                    # came out louder than the drops' bass, a held note being loud all through its bar where a groove is
                    # loud on its notes, and the groove ducked under the kick: now 8 to 10 dB under the groove.)
                    held = sound if not isinstance(sound, Patch) or sound.sustain > 0.5 else BASS["sub"]
                    synth.play(out, held, self.at(bar, 0), 15 * STEP, self.bass_note(chord, "R"), trim(held, 40) * 0.16 * (0.5 + energy),
                               seed=self.seed + bar, bright=0.35)
                elif story == "rise" and builds and inside >= count - build:
                    # Eighths on one note, opening up, through the build.
                    along = (inside - (count - build)) / build
                    for step in range(0, 16, 2):
                        synth.play(out, sound, self.at(bar, step), 1.5 * STEP, self.bass_note(self.changes.chord(count - 1), "R"),
                                   loud * (0.25 + 0.3 * along), seed=self.seed + bar * 16 + step, bright=0.25 + 0.7 * along)
        return self.pumped(out, 0.75 if style == "long" else 0.55).astype(np.float32)

    # --- chords, plucks and arps -----------------------------------------------------------------
    def rhythm(self) -> np.ndarray:
        fam, rng = self.family, self.rng("rhythm")
        out = self.blank()
        sound_name = self.pick("keys", self.palette["keys"])
        sound = KEYS[sound_name]
        style = self.pick("keys-style", self.palette["keys_style"])
        if style == "strum" and not isinstance(sound, String):
            style = "stabs"
        if style == "pumpchords" and isinstance(sound, String):
            style = "broken"
        stabs = STABS[rng.randrange(len(STABS))]
        arp = ARPS[rng.randrange(len(ARPS))]
        through_rise = self.pick("keys-rise", (True, False, True))
        voiced: list[int] | None = None
        spread = self.palette["voicing"]
        for story, first, count in self.sections:
            build = 4 if count >= 16 else 2
            for inside in range(count):
                bar, energy = first + inside, self.energy(story, inside / count, first)
                chord = self.changes.chord(inside)
                voiced = self.changes.voicing(chord, 55, 76, voiced, spread)
                notes = list(voiced)
                if story == "moment":
                    notes = notes + [notes[-1] + 12 if notes[-1] + 12 <= 84 else notes[0] + 12]       # fuller at the drop
                # (2026-11-18: a theme half an octave to an octave darker than the drop, opening across it, as the records
                # studied do: "the theme is darker than the drop".)
                bright = {"open": 0.12 + 0.33 * inside / count, "theme": 0.5 + 0.2 * inside / count, "rise": 0.4 + 0.6 * (inside / count) ** 2,
                          "moment": 1.0, "close": 0.85 - 0.6 * inside / count}[story]
                if self.broken(story, first):
                    # (2026-11-18: the breakdown was as bright as a theme.) Dark, and opening only a little across it.
                    bright = 0.22 + 0.18 * inside / count
                level = 0.2 * (0.35 + 0.65 * energy) * trim(sound, 64)
                if story == "open" and inside < (count // 4 if not fam.hard else 0):
                    continue
                if story == "rise" and not through_rise and inside < count - build:
                    continue
                thin = (story == "open" and inside < count // 2) or (story == "close" and inside >= count // 2)
                building = story == "rise" and inside >= count - 2
                if style == "dub":
                    # One chord thrown into the echo, and left to ring.
                    if inside % 2 == 0 or story == "moment":
                        for index, pitch in enumerate(notes):
                            synth.play(out, sound, self.at(bar, 3 if inside % 4 else 6), 1.4 * STEP, pitch, level * 1.3,
                                       pan=(index - 1.5) * 0.25, seed=self.seed + bar + index, bright=bright)
                elif style in ("stabs", "strum") or (building and style != "arp"):
                    places = tuple((step, 0.9) for step in range(0, 16, 1 if inside == count - 1 else 2)) if building else stabs
                    for number, (step, length) in enumerate(places):
                        if thin and number % 2:
                            continue
                        order = notes if number % 2 == 0 else notes[::-1]
                        for index, pitch in enumerate(order):
                            late = index * 0.014 if style == "strum" else 0.0
                            synth.play(out, sound, self.at(bar, step) + late, length * STEP * 0.9, pitch,
                                       level * (1.0 if step % 4 == 0 or len(places) < 5 else 0.82) * (0.9 + 0.1 * rng.random()),
                                       pan=(notes.index(pitch) - (len(notes) - 1) / 2.0) * 0.28, seed=self.seed + bar * 64 + number * 4 + index,
                                       bright=bright)
                elif style == "pumpchords":
                    for index, pitch in enumerate(notes):
                        for step in ((0,) if thin else (0, 8)):
                            synth.play(out, sound, self.at(bar, step), (15 if thin else 7.5) * STEP, pitch, level * 0.8,
                                       pan=(index - (len(notes) - 1) / 2.0) * 0.3, seed=self.seed + bar * 8 + index, bright=bright * 0.9)
                else:
                    # An arpeggio (sixteenths) or a broken chord (eighths) over two octaves of the chord.
                    pool = sorted(set(notes + [pitch + 12 for pitch in notes[:2]]))
                    every = 2 if style == "broken" or thin else 1
                    for number, step in enumerate(range(0, 16, every)):
                        turn = number + (inside % 2) * (16 // every)
                        if arp == "up":
                            pitch = pool[turn % len(pool)]
                        elif arp == "down":
                            pitch = pool[-1 - turn % len(pool)]
                        elif arp == "updown":
                            wave = turn % (2 * len(pool) - 2) if len(pool) > 1 else 0
                            pitch = pool[wave if wave < len(pool) else 2 * len(pool) - 2 - wave]
                        elif arp == "pedal":
                            pitch = pool[-1] if turn % 2 else pool[(turn // 2) % (len(pool) - 1)]
                        else:
                            pitch = pool[(turn * 2) % len(pool)]
                        accent = 1.0 if step % 16 in (0, 6, 12) else 0.72
                        synth.play(out, sound, self.at(bar, step), every * STEP * 0.85, pitch, level * 1.15 * accent,
                                   pan=0.35 * math.sin(turn * 1.3), seed=self.seed + bar * 16 + step, bright=bright)
        if style in ("arp", "broken", "strum", "dub") or isinstance(sound, String):
            out = synth.echo(out, 3 * STEP, 4 * STEP, feedback=0.5 if style == "dub" else 0.32, mix=0.4 if style == "dub" else 0.22)
        elif isinstance(sound, Patch):
            out = synth.chorus(out, mix=0.35)
        out = synth.hall(out, seconds=1.3, wet=0.16)
        return self.pumped(out, 0.3 if style in ("arp", "broken", "strum") else 0.5).astype(np.float32)

    # --- the tune ----------------------------------------------------------------------------
    def lead(self) -> np.ndarray:
        fam, rng = self.family, self.rng("lead")
        out = self.blank()
        names = self.palette["lead"]
        chosen = self.pick("lead", names)
        main = LEADS[chosen]
        soft = LEADS[names[(names.index(chosen) + 1) % len(names)]]      # the same tune in a gentler voice, for the quiet places
        doubled = self.pick("lead-double", ("octave", "third", "octave")) if fam.role not in CALM_ROLES else ""
        tune = self.tune

        def say(notes: list[Tone], bar: int, sound: Any, level: float, bright: float, shift: int = 0, echo_of: float = 0.0) -> None:
            before = None
            for note in notes:
                pitch = self.changes.pitch(note.degree + shift)
                if pitch > 93:
                    pitch -= 12                          # no higher than this: above it a line is a whistle
                when = self.at(bar + int(note.at // 16), note.at % 16) + echo_of + rng.gauss(0.0, 0.003)
                joined = before is not None and abs(before[0] - note.at) < 1e-6
                synth.play(out, sound, when, note.length * STEP * (0.96 if joined or note.length < 4 else 0.9), pitch,
                           trim(sound, 76) * level * note.loud * (1.0 + rng.gauss(0.0, 0.04)), pan=0.0, seed=self.seed + bar * 64 + int(note.at),
                           glide_from=before[1] if joined else None, bright=bright)
                before = (note.at + note.length, pitch)

        def cut(notes: list[Tone], first: float, last: float) -> list[Tone]:
            return [Tone(note.at - first, note.length, note.degree, note.loud) for note in notes if first <= note.at < last]

        for story, first, count in self.sections:
            if story == "open":
                # The end of the idea, far away, once or twice.
                ending = cut(tune.idea, 16, 32)
                for inside in range(count // 2 + 2, count, 4):
                    say(ending[-3:] if len(ending) >= 3 else ending, first + inside - 1, soft, 0.22, 0.3)
            elif story == "theme":
                # The hook, stated and left; then answered.
                half = count // 2 if not fam.hard else 0
                for index, inside in enumerate(range(half, count - 1, 4)):
                    say(cut(tune.notes, 32 * (index % 2), 32 * (index % 2) + 32) if index < 2 else cut(tune.notes, 96, 128),
                        first + inside, soft if not fam.hard else main, 0.42, 0.6)
            elif story == "rise":
                # The whole tune, alone; then again, opening up, to the edge of the drop.
                for inside in range(0, count - 1, 8):
                    along = inside / count
                    phrase = tune.first if (inside // 8) % 2 == 0 else tune.second
                    notes = cut(phrase, phrase[0].at - phrase[0].at % 128, phrase[0].at - phrase[0].at % 128 + 128)
                    if inside + 8 >= count:
                        notes = [note for note in notes if note.at < 112]           # the last bar is the drop's breath
                    say(notes, first + inside, soft if along < 0.5 else main, 0.4 + 0.25 * along, 0.5 + 0.5 * along)
            elif story == "moment":
                for inside in range(0, count, 8):
                    phrase = tune.first if (inside // 8) % 2 == 0 else tune.second
                    notes = cut(phrase, phrase[0].at - phrase[0].at % 128, phrase[0].at - phrase[0].at % 128 + 128)
                    say(notes, first + inside, main, 0.62, 1.0)
                    if doubled and (inside // 8) % 2 == 1:
                        # The second time round, a line above it: an octave, or a third.
                        say(notes, first + inside, main, 0.26, 0.9, shift=7 if doubled == "octave" else 2)
            else:
                for index, inside in enumerate(range(0, max(count // 2, 2), 4)):
                    say(tune.idea, first + inside, soft, 0.34 - 0.1 * index, 0.5)
        out = synth.echo(out, 3 * STEP, 4 * STEP, feedback=0.34, mix=0.24)
        if isinstance(main, Patch) and main.voices > 1:
            out = synth.chorus(out, mix=0.25)
        out = synth.hall(out, seconds=1.5, wet=0.2)
        return self.pumped(out, 0.25).astype(np.float32)

    # --- pads, sweeps and the weather ----------------------------------------------------------
    def _air(self, kind: str, seconds: float, seed: int) -> np.ndarray:
        """Weather for the gaps: wind, sea, rain, a fire, drips in a cave, crickets."""
        count = synth.frames(seconds)
        rng = np.random.default_rng(seed)
        slow = np.interp(np.arange(count), np.linspace(0, count, max(int(seconds / 2.5), 2) + 1),
                         rng.uniform(0.25, 1.0, max(int(seconds / 2.5), 2) + 1)).astype(np.float32)
        if kind == "wind":
            return synth.sweep(synth.noise(seconds, seed), 350.0 + 900.0 * slow, res=0.3, mode=BAND) * (0.5 * slow[:, None])
        if kind == "sea":
            swell = (0.5 + 0.5 * np.sin(2 * np.pi * np.arange(count) / RATE / 9.0 + seed)).astype(np.float32)
            return synth.sweep(synth.noise(seconds, seed), 300.0 + 700.0 * swell, res=0.05, mode=LOW) * (0.7 * swell[:, None] ** 2)
        if kind == "rain":
            patter = np.interp(np.arange(count), np.arange(0, count + 1600, 1600), rng.uniform(0.4, 1.0, count // 1600 + 2)).astype(np.float32)
            return synth.sweep(synth.noise(seconds, seed), np.full(count, 4500.0, dtype=np.float32), res=0.05, mode=HIGH) * (0.5 * patter[:, None])
        out = np.zeros((count, 2), dtype=np.float32)
        if kind in ("fire", "drips"):
            every = 0.12 if kind == "fire" else 1.7
            for _ in range(int(seconds / every)):
                at = rng.uniform(0.0, max(seconds - 0.6, 0.1))
                if kind == "fire":
                    click = rng.standard_normal(int(0.004 * RATE)) * np.exp(-np.arange(int(0.004 * RATE)) / 40.0)
                    synth.hit(out, click, at, rng.uniform(0.05, 0.3), rng.uniform(-0.8, 0.8))
                else:
                    synth.play(out, Keys(ratio=2.4, index=1.2, index_decay=0.03, decay=0.12, release=0.1, detune=0.0, width=0.0),
                               at, 0.05, rng.choice((84, 88, 91, 96)), rng.uniform(0.1, 0.3), pan=rng.uniform(-0.8, 0.8))
            return synth.hall(out, seconds=2.4, wet=0.5) if kind == "drips" else out
        if kind == "crickets":
            t = np.arange(count) / RATE
            for voice, (pitch, every, pan) in enumerate(((4300.0, 0.9, -0.6), (4750.0, 1.3, 0.5), (3900.0, 2.1, 0.1))):
                chirp = ((t + voice * 0.37) % every) < 0.13
                pulse = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 27.0 * t))
                tone = (np.sin(2 * np.pi * pitch * t) * chirp * pulse * 0.12).astype(np.float32)
                angle = (pan + 1.0) * math.pi / 4.0
                out[:, 0] += tone * math.cos(angle)
                out[:, 1] += tone * math.sin(angle)
            return out
        raise KeyError("No weather called %r" % kind)

    def airs(self) -> list[Air]:
        """Every sound of the track's air, in order: the risers into each drop (a sweep of noise, and in two takes of
        three a note that climbs two octaves), the drop's thud and the air falling away from it, the small sweeps
        that turn a theme, and the weather of the place in the gaps."""
        fam = self.family
        out: list[Air] = []
        tonal = self.pick("riser", (True, False, True))
        gentle = 0.4 if fam.role in CALM_ROLES else 1.0         # an inn does not have a drop
        for story, first, count in self.sections:
            start = self.at(first, 0)
            if story == "rise":
                build = (8 if count >= 16 else 4) * BAR
                end = self.at(first + count, 0)
                out.append(Air("sweep", end - build, build, 1.1 * gentle, 250.0, 9000.0, True, seed=self.seed + 1))
                if tonal:
                    out.append(Air("climb", end - build, build, 0.16 * gentle, 600.0, 5600.0, True, pitch=self.changes.pitch(0, 4)))
            if story == "moment":
                out.append(Air("thud", start, 2.5, 0.5 * gentle))
                out.append(Air("sweep", start, 2 * BAR, 0.7 * gentle, 400.0, 9000.0, False, seed=self.seed + 2))
            if story in ("theme", "close") and not fam.hard:
                out.append(Air("sweep", start, BAR, 0.35, 500.0, 6000.0, False, seed=self.seed + 3 + first))
                out.append(Air("sweep", start - 2 * BAR, 2 * BAR, 0.3, 300.0, 5000.0, True, seed=self.seed + 4 + first))
            if self.palette["atmos"] and (story in ("open", "close") or (story == "rise" and count >= 16) or fam.role == "storm"):
                seconds = count * BAR if story != "rise" else count * BAR / 2
                out.append(Air(self.palette["atmos"], start, seconds + 2.0, 0.3 if fam.role != "storm" else 0.4, fade=1.5,
                               seed=self.seed + 9 + first))
        return sorted(out, key=lambda each: each.at)

    def air_audio(self, air: Air) -> np.ndarray:
        """One sound of the air, made by the writer's own synthesiser (the house desk plays it in REAPER instead)."""
        if air.kind == "sweep":
            count = synth.frames(air.seconds)
            along = np.linspace(0.0, 1.0, count, dtype=np.float32)
            corner = air.low * (air.high / air.low) ** (along ** 1.3 if air.rising else (1.0 - along) ** 1.3)
            loud = (along ** 2.2 if air.rising else (1.0 - along) ** 1.6) * air.level
            return synth.sweep(synth.noise(air.seconds, air.seed), corner, res=0.35, mode=BAND) * loud[:, None]
        if air.kind == "climb":
            frames = synth.frames(air.seconds)
            along = np.linspace(0.0, 1.0, frames)
            pitch = synth.hz(air.pitch) * 2.0 ** (2.0 * along)
            phase = np.cumsum(pitch) / RATE
            saw = (2.0 * (phase % 1.0) - 1.0) * (along ** 2) * air.level
            return synth.sweep(np.stack([saw, saw], axis=1).astype(np.float32), (air.low + (air.high - air.low) * along).astype(np.float32), res=0.2)
        if air.kind == "thud":
            t = np.arange(synth.frames(air.seconds)) / RATE
            thud = np.sin(2 * np.pi * np.cumsum(38.0 + 34.0 * np.exp(-t / 0.12)) / RATE) * np.exp(-t / 0.6) * air.level
            return np.stack([thud, thud], axis=1).astype(np.float32)
        weather = self._air(air.kind, air.seconds, air.seed)
        edge = synth.frames(air.fade)
        weather[:edge] *= np.linspace(0.0, 1.0, edge, dtype=np.float32)[:, None]
        weather[-edge:] *= np.linspace(1.0, 0.0, edge, dtype=np.float32)[:, None]
        return weather * air.level

    def texture(self, air: bool = True) -> np.ndarray:
        """The pad, and (with `air`) the writer's own making of the air (`airs`)."""
        pad, effects = self.blank(), self.blank()
        sound = PADS[self.pick("pad", self.palette["pad"])]
        spread = self.palette["voicing"]
        voiced: list[int] | None = None
        slot = self.changes.slot
        for story, first, count in self.sections:
            for inside in range(0, count, slot):
                bar, along = first + inside, inside / count
                energy = self.energy(story, along, first)
                voiced = self.changes.voicing(self.changes.chord(inside), 48, 69, voiced, spread)
                bright = {"open": 0.25 + 0.25 * along, "theme": 0.47, "rise": 0.45 + 0.5 * along, "moment": 0.92, "close": 0.75 - 0.45 * along}[story]
                if self.broken(story, first):
                    bright = 0.22 + 0.18 * along
                level = 0.2 * trim(sound, 60) * {"open": 0.75 + 0.25 * along, "theme": 0.7, "rise": 0.7 + 0.3 * along, "moment": 1.0,
                                                  "close": 0.95 - 0.45 * along}[story]
                length = min(slot, count - inside) * BAR
                for index, pitch in enumerate(voiced):
                    synth.play(pad, sound, self.at(bar, 0), length + 0.15, pitch, level * (0.6 + 0.4 * energy if story != "open" else 1.0),
                               pan=(index - (len(voiced) - 1) / 2.0) * 0.2, seed=self.seed + bar * 8 + index, bright=bright)
        pad = self.pumped(synth.hall(synth.chorus(pad, mix=0.4), seconds=1.8, wet=0.26), 0.5)

        if air:
            for event in self.airs():
                begin = synth.frames(event.at)
                made = self.air_audio(event)
                stop = min(begin + len(made), self.frames)
                if stop > begin:
                    effects[begin:stop] += made[:stop - begin]
        effects = synth.hall(effects, seconds=2.2, wet=0.3)
        return (pad + self.pumped(effects, 0.3)).astype(np.float32)

    # --- the whole track ---------------------------------------------------------------------
    def meta(self) -> dict[str, Any]:
        fam = self.family
        groove = {"drums": 0.6, "bass": 0.5} if not fam.hard else {"drums": 0.9, "bass": 0.85}
        if fam.role in ("ember", "camp"):
            groove = {"drums": 0.5, "bass": 0.4}
        # (The open, the rise and the close had no floor: standing still, the director takes the drums and the bass out,
        # and there that left the synths all but alone, a pad or a lead whining on its own: "sometimes when one synth
        # stays in when youre sitting its whiny and annoying mix better", 2026-11-17. The bass stays under them
        # everywhere, and a little of the drums.)
        edges = {"drums": round(groove["drums"] * 0.6, 2), "bass": round(groove["bass"] * 0.8, 2)}
        floor = {story: groove if story in ("theme", "moment") else edges for story in forever.STORY}
        if fam.hard:
            floor = {story: groove for story in forever.STORY}
        return {
            "style": "house", "family": fam.name, "take": self.take, "title": "%s %s" % (fam.title, NUMERALS[self.take]),
            "tempo": BPM, "beats": 4, "bar_frames": BAR_FRAMES, "tonic": fam.key, "moods": list(fam.moods), "role": fam.role,
            "serves": list(fam.serves), "light": fam.light, "settings": list(ground(fam)),
            "sections": [{"story": story, "bars": count} for story, _, count in self.sections],
            "floor": floor, "follow": {"rhythm": ["lead"]}, "post_s": POST_S,
            # How far under a track's usual level this one is meant to play: music for an inn or
            # for the night should not be as loud at its fullest as a drop. (The studio's import
            # does not read this yet; it is here for when it does.)
            "level_db": {"ember": -4.0, "camp": -3.0, "night": -2.0}.get(fam.role, 0.0),
            "credit": "Written and played by FreeRock's studio (studio.house): its own synthesiser, and drum-machine recordings "
                      "released into the public domain (MckAudio's TR-8 set, CC0).",
            "seed": self.seed,
        }

    def render(self) -> dict[str, np.ndarray]:
        """Every channel of the track, balanced against each other, the whole kept under full scale."""
        parts = {"drums": synth.tame(self.drums(), 15.0), "bass": self.bass(), "rhythm": synth.tame(self.rhythm()),
                 "lead": synth.tame(self.lead()), "texture": synth.tame(self.texture())}
        # Each part is brought to its place in the mix by how loud it is where the track is fullest.
        story, first, count = next(section for section in reversed(self.sections) if section[0] == "moment")     # the last drop
        a, b = int(round(first * BAR_FRAMES)), int(round((first + count) * BAR_FRAMES))
        want = {"drums": -14.0, "bass": -16.5, "rhythm": -20.0, "lead": -19.0, "texture": -22.0}
        if self.family.role in CALM_ROLES:
            want.update(drums=-18.0, bass=-18.0, lead=-18.0, texture=-20.0)
        if not self.kick:
            want.update(drums=-27.0)             # with no kick the drums are a shaker and a rim: in the corner, not in front
        for channel, audio in parts.items():
            if not np.isfinite(audio).all():
                raise ValueError("The %s of %s take %d has numbers in it that are not numbers" % (channel, self.family.name, self.take))
            have = synth.level_of(audio[a:b])
            if have < -90.0:
                have = synth.level_of(audio)
            if have < -90.0:
                raise ValueError("The %s of %s take %d is silent" % (channel, self.family.name, self.take))
            parts[channel] = (audio * 10.0 ** ((want[channel] - have) / 20.0)).astype(np.float32)
        # What is still ringing two seconds before the recording ends is eased away to nothing.
        last = synth.frames(2.0)
        ease = (0.5 * (1.0 + np.cos(np.linspace(0.0, math.pi, last)))).astype(np.float32)[:, None]
        for channel in parts:
            parts[channel][-last:] *= ease
        parts = master(parts, a, b)
        peak = max(float(np.max(np.abs(audio))) for audio in parts.values())
        if peak > 0.97:                            # one part alone over the top (the others pulling the other way): all come down
            for channel in parts:
                parts[channel] = (parts[channel] * (0.97 / peak)).astype(np.float32)
        return parts


def master(parts: dict[str, np.ndarray], first: int, last: int) -> dict[str, np.ndarray]:
    """A track brought to its level, so that one track is as loud as the next: its moment (from
    sample `first` to `last`) to MOMENT_LUFS, and the peaks of the whole held under CEILING.

    A peak that would pass the ceiling is held under it by turning every part down together,
    by the same amount, for a few thousandths of a second around it: the parts keep their
    balance, and whichever of them the player has up, the whole never passes full scale."""
    up, need = master_gains(parts, first, last)
    gain = (up * need).astype(np.float32)[:, None]
    return {channel: (audio * gain).astype(np.float32) for channel, audio in parts.items()}


def master_gains(parts: dict[str, np.ndarray], first: int, last: int) -> tuple[float, np.ndarray]:
    """What `master` does to a track, as numbers for the desk to do: the gain that brings its moment to MOMENT_LUFS,
    and the gain (one for each sample, 1 nearly everywhere) that holds its peaks under the ceiling."""
    mix = sum(parts.values())
    have = analysis.loudness_lufs(mix[first:last], RATE)
    if have < -60.0:
        raise ValueError("The moment of the track is all but silent (%.0f LUFS)" % have)
    up = 10.0 ** ((MOMENT_LUFS - have) / 20.0)
    need = np.minimum(1.0, CEILING / np.maximum(np.abs(mix).max(axis=1) * up, 1e-9))
    hold = 240                                     # five thousandths of a second either side
    need = uniform_filter1d(minimum_filter1d(need, size=2 * hold + 1, mode="nearest"), size=hold, mode="nearest")
    return float(up), need


# ---------------------------------------------------------------------------------------------
# Checking what was made, since nobody is listening
# ---------------------------------------------------------------------------------------------
def measure(meta: dict[str, Any], parts: dict[str, np.ndarray]) -> dict[str, Any]:
    """What a track measures as: how loud each part of the story is, whether anything clips,
    whether the kick is on the beat, whether the bass is in tune and everything is in the key,
    and whether the bass has its lows and the drums their highs. `problems` lists what is wrong."""
    bar = meta["bar_frames"]
    edges, bars = [0], 0
    for section in meta["sections"]:
        bars += section["bars"]
        edges.append(int(round(bars * bar)))
    mix = sum(parts.values())
    found: dict[str, Any] = {"peak": round(float(np.max(np.abs(mix))), 3), "sections": {}}
    problems: list[str] = []
    spans = [(section["story"], first, last) for section, first, last in zip(meta["sections"], edges, edges[1:])]
    for story, first, last in spans:
        # Each part of the story at its loudest: a house track tells its theme, its rise and its drop twice.
        loud = round(analysis.loudness_lufs(mix[first:last], RATE), 1)
        found["sections"][story] = max(loud, found["sections"].get(story, loud))
    loudest = max(found["sections"], key=lambda story: found["sections"][story])
    if found["sections"]["moment"] < found["sections"][loudest] - 0.5:
        problems.append("its %s is louder than its moment" % loudest)
    if found["peak"] > 0.98 or any(float(np.max(np.abs(audio))) > 0.98 for audio in parts.values()):
        problems.append("it clips")
    drops = [(first, last) for story, first, last in spans if story == "moment"]
    first, last = drops[-1]                       # the last drop, by which the desk places every part
    where = max(index for index, (story, _, _) in enumerate(spans) if story == "moment")
    # No part may be much louder anywhere else than it is where the track is fullest: the parts
    # are balanced by how loud they are there, and one that shouted elsewhere would force the
    # whole track down to make room for it.
    for channel, audio in parts.items():
        at_moment = max(synth.level_of(audio[a:b]) for a, b in drops)
        elsewhere = max(synth.level_of(audio[a:b]) for story, a, b in spans if story != "moment")
        if elsewhere - at_moment > 5.0:
            problems.append("the %s is %.0f dB louder outside the moment than in it" % (channel, elsewhere - at_moment))
    count = meta["sections"][where]["bars"]
    whole = int(round(count * bar))
    if "drums" in parts and synth.level_of(parts["drums"][first:last]) > -60 and meta["role"] not in ("ember", "camp"):
        drums = forever.measure(parts["drums"][first:first + whole], RATE, meta["tempo"], "drums", count)
        found["drums"] = {key: drums.get(key) for key in ("tempo_off", "beat_ms", "dense")}
        problems += ["the drums: " + problem for problem in drums["problems"]]
    scale = MODES[family(meta["family"]).mode]
    tonic = family(meta["family"]).tonic
    for channel in ("rhythm", "lead", "texture"):
        key = analysis.estimate_key(parts[channel][first:last], RATE)
        inside = float(sum(key.chroma[(tonic + step) % 12] for step in scale))
        found[channel] = {"tuning_cents": round(key.tuning_cents, 1), "in_key": round(inside, 3)}
        if abs(key.tuning_cents) > 12.0 and channel != "texture":
            problems.append("the %s is %.0f cents out of tune" % (channel, key.tuning_cents))
        if inside < 0.65:
            problems.append("the %s is only %.0f%% in the key" % (channel, inside * 100))
    # The bass is noted, not judged: a run of short low notes, each starting afresh, cannot be
    # placed to the semitone from the outside (what stands out in three seconds of it is the
    # rate the notes come at as much as the notes). That every bass sound is in tune, and that
    # the bass only ever plays notes of the scale, is tested on the writer itself.
    cents, inside = low_notes(parts["bass"][first:last], tonic, scale)
    found["bass"] = {"tuning_cents": round(cents, 1), "in_key": round(inside, 3)}
    lows = analysis.band_level_db(parts["bass"][first:last], RATE, 30.0, 200.0) - analysis.band_level_db(parts["bass"][first:last], RATE, 200.0, 12000.0)
    highs = analysis.band_level_db(parts["drums"][first:last], RATE, 5000.0, 16000.0) - analysis.band_level_db(parts["drums"][first:last], RATE, 30.0, 16000.0)
    found["bass_lows_db"], found["drum_highs_db"] = round(lows, 1), round(highs, 1)
    if lows < 0.0:
        problems.append("the bass has more above 200 Hz than below")
    if highs < -40.0 and meta["role"] not in ("ember", "camp"):
        problems.append("the drums have no top")
    found["problems"] = problems
    return found


def low_notes(audio: np.ndarray, tonic: int, scale: tuple[int, ...]) -> tuple[float, float]:
    """How far a bass part is from the notes of the keyboard, in cents, and how much of it is on
    notes of the scale. A bass is too low for the usual way of telling (its notes are a few Hz
    apart), so this listens to three seconds at a time, where they can be told apart, and only
    to each stretch's strongest tone: the note itself, not its overtones. Good for a bass of
    long notes; a guide and no more for one of short ones."""
    mono = audio.mean(axis=1)
    size = 1 << 17
    window = np.hanning(size)
    freqs = np.fft.rfftfreq(size, 1.0 / RATE)
    keep = (freqs >= 36.0) & (freqs <= 130.0)
    turn, weight, inside = 0j, 0.0, 0.0
    for start in range(0, max(len(mono) - size, 1), size // 4):
        chunk = mono[start:start + size]
        if len(chunk) < size:
            break
        power = np.abs(np.fft.rfft(chunk * window)) ** 2
        band = np.where(keep, power, 0.0)
        at = int(np.argmax(band))
        if band[at] <= 0.0:
            continue
        a, b, c = (math.log(power[at + shift] + 1e-30) for shift in (-1, 0, 1))
        curve = a - 2.0 * b + c
        exact = freqs[at] + (0.5 * (a - c) / curve if curve < 0 else 0.0) * (freqs[1] - freqs[0])
        semitones = 12.0 * math.log2(exact / 440.0)
        off = semitones - round(semitones)
        turn += band[at] * np.exp(2j * np.pi * off)
        weight += band[at]
        if (int(round(semitones)) + 9 - tonic) % 12 in scale:
            inside += band[at]
    if weight <= 0.0:
        raise ValueError("The bass is silent where the track is fullest")
    return float(np.angle(turn) / (2.0 * np.pi) * 100.0), inside / weight


def stage(name: str, take: int, root: Path | None = None, bars: tuple[int, int, int, int, int] | None = None) -> dict[str, Any]:
    """Writes one take of a family, plays it, checks it and stages it. Returns what it measured."""
    began = time.time()
    track = Take(family(name), take, bars)
    parts = track.render()
    meta = track.meta()
    found = measure(meta, parts)
    folder = (root or stage_root(VAR, "house")) / name / str(take)
    write_track(folder, meta, parts)
    found.update(family=name, take=take, seconds=round(track.bars * BAR, 1), took=round(time.time() - began, 1))
    scratch = folder / "measured.json.new"
    scratch.write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
    scratch.replace(folder / "measured.json")
    return found


def remaster(name: str, take: int, root: Path | None = None) -> dict[str, Any]:
    """Brings a track that is already staged to its level again (see `master`) and checks it
    again, without writing or playing it afresh: for when the level every track is brought to
    has been changed. What the track is (track.json) is written as the plan has it now."""
    began = time.time()
    folder = (root or stage_root(VAR, "house")) / name / str(take)
    was, parts = read_track(folder)
    track = Take(family(name), take, tuple(section["bars"] for section in was["sections"]))
    meta = track.meta()
    story, first, count = next(section for section in reversed(track.sections) if section[0] == "moment")     # the last drop
    parts = master(parts, int(round(first * BAR_FRAMES)), int(round((first + count) * BAR_FRAMES)))
    found = measure(meta, parts)
    write_track(folder, meta, parts)
    found.update(family=name, take=take, seconds=round(track.bars * BAR, 1), took=round(time.time() - began, 1))
    scratch = folder / "measured.json.new"
    scratch.write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
    scratch.replace(folder / "measured.json")
    return found
