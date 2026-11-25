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
from contextlib import contextmanager
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
    # (2026-11-24, heard as sweet still: a loop of four chords is a song's; hard music stands on one and leans on another.) One chord and its shadow: the
    # phrygian's second, the minor's seventh, the fourth, and one that never moves.
    "H1": ("phrygian", 2, ((0, ""), (0, ""), (0, ""), (1, ""))),
    "H2": ("minor", 2, ((0, ""), (0, ""), (6, ""), (0, ""))),
    "H3": ("minor", 4, ((0, ""), (3, ""))),
    "H4": ("phrygian", 4, ((0, ""), (0, ""))),
    "H5": ("dorian", 2, ((0, ""), (0, ""), (0, ""), (6, ""))),
    "H6": ("minor", 2, ((0, ""), (0, ""), (5, ""), (0, ""))),          # (the same night: the sixth under it; and the phrygian's second as soon as it can be)
    "H7": ("phrygian", 2, ((0, ""), (1, ""), (0, ""), (0, ""))),
    "P1": ("phrygian", 2, ((0, ""), (1, ""), (0, ""), (6, ""))),
    "P2": ("phrygian", 2, ((0, ""), (1, ""), (2, ""), (1, ""))),
    "P3": ("phrygian dominant", 2, ((0, ""), (1, ""), (0, ""), (6, ""))),
    "P4": ("phrygian dominant", 2, ((0, ""), (3, ""), (1, ""), (0, ""))),
}
# Where in the bar the kick falls, in sixteenths. A family has one, and every take keeps to it:
# everything but the drums ducks under the kick, so the kick is part of the changes.
KICKS = {"four": (0, 4, 8, 12), "broken": (0, 6, 10), "broken2": (0, 6, 8, 14), "broken3": (0, 3, 8, 10),
         "half": (0, 10), "none": (), "step": (0, 10), "breaks": (0, 2, 10)}          # (the last two since 2026-11-25: a two-step's, its claps on two and four over a half's kick, and a break's)
# How much is going on through each part of the story, from 0 to 1, at its beginning and its end.
ARCS = {
    "wander": {"open": (0.2, 0.5), "theme": (0.6, 0.72), "rise": (0.4, 0.95), "moment": (1.0, 1.0), "close": (0.72, 0.2)},
    "ember": {"open": (0.2, 0.4), "theme": (0.5, 0.6), "rise": (0.4, 0.66), "moment": (0.78, 0.78), "close": (0.55, 0.2)},
    "storm": {"open": (0.45, 0.65), "theme": (0.75, 0.8), "rise": (0.5, 1.0), "moment": (1.0, 1.0), "close": (0.8, 0.4)},
    "battle": {"open": (0.8, 0.88), "theme": (0.86, 0.9), "rise": (0.6, 1.0), "moment": (1.0, 1.0), "close": (0.9, 0.7)},
}
BREAKDOWN = (0.3, 0.5)          # the breakdown's energy, from its first bar to its last (see Take.breakdown)
# (2026-11-19, the judges: House's rises scored TuneJury 0.22 on the House brief and -0.30 on none, against 1.1 to 1.3 for
# the grooves either side of them, in all thirteen takes judged. A rise was twelve bars of the tune alone over nothing, the
# pulse gone, and a roll in its last four, under a sweep eight bars long.) A rise keeps the groove's top: the hats go on,
# from a little under the theme and growing with it, and the first percussion figure until the build, while the kick (a
# fight's after the rise's first half), the backbeat and the bass are out; and it builds over its last eight bars (four of
# a short one), the roll, the bass's eighths and the late chords together with the sweep.
# Left off (2026-11-19, 20:55, the judges on two takes, eight rises): the House brief edged up in every rise (+0.04 to +0.09)
# and SongEval rose on one take (musicality 2.64 to 2.88), but Audiobox's enjoyment fell in all eight (-0.28 on average) and the
# score with no brief went down on one take and up on the other; with the four-bar build of before instead of eight it was
# worse, so the hats were what the judges liked less. The open hats and the ride of The Long Watch II fell the furthest: a
# quieter pulse (the closed hat alone) is the next to try.
RISE_PULSE = False
# The quieter pulse (2026-11-20): the closed hat alone on the eighths, soft and growing with the rise, no percussion, with the
# eight-bar build. The judges, before and after on The Long Watch II and Harbour Lights II, four rises: the House brief up in
# all four (+0.07 to +0.17), the score with none up on Harbour Lights (+0.14, +0.23) and level on The Long Watch, Audiobox's
# enjoyment within its noise (-0.07 to -0.14, where the full hats had cost 0.28): in.
RISE_CLOSED_HAT = True
RISE_LONG_BUILD = True     # the build eight bars with the sweep; False: four, the sweep eight as before (Take.build_bars)
# (2026-11-20, the judges: House's rises still the lowest of its parts, TuneJury -0.25 with no brief on average over sixteen
# takes, where its themes have 0.76 and its drops 1.13. A rise had no kick from its first bar: the four on the floor that
# says house was gone for twelve to sixteen bars, where a house record keeps it through the build-up and takes it away only
# for the last bars before the drop.) A rise keeps the kick until its build (`build_bars`), everything but the drums ducking
# under it as in a groove; the build into the drop goes without it, the roll and the sweep alone, so that the drop's kick
# lands after its absence. A calm rise (an inn, the night, a camp) is left as it was, without one.
RISE_KICK = True
# (2026-11-20, the render's own check: Cool of the Evening II's rise louder than its moment again with no closed hat in it: its
# bass -15.3 dB through the rise against -20.3 at its moment, the build's eighths on one note four bars of an eight-bar rise
# since the build grew with the sweep, with no kick to duck under.) A calm piece has no drop to roll into, and no roll of the
# chords into it: the bass's eighths into its moment are half as loud, so that its rise stays under its moment.
# Left off (2026-11-21, 00:13, the judges on Cool of the Evening II's rise and the moment's first bars, before and after): the
# render's own check passed, but TuneJury fell 0.933 to 0.788 with the House brief and 1.202 to 0.885 with none, enjoyment
# level: a rise with less lift. Its bass was an organ, which House no longer has; its takes made again without it will say
# whether a calm rise still comes over its moment.
CALM_BUILD_SOFT = False
# (2026-11-20, the boredom meter: a long drop's last sixteen bars one groove, Mirage I, Hollow Road III, River Drums III and
# The Old Swamp III; the drop's third block's percussion and crashes, tried louder (DROP_PEAK), moved its stem 0.3 dB: under
# the kick, the clap and the hats they are not heard.) A drop of thirty-two bars or more drops out for the bar before its last
# eight: the kick, the bass, the chords, the tune and the percussion stop, the clap and the hats go on with a snare's pickup
# under a one-bar sweep, and everything slams back in on a crash and the drop's thud. Not in a calm piece, which has no drop.
DROP_OUT = True
# (2026-11-20, the boredom meter on House's fights made again: Ambush III's drums the same 20 bars from its first bar, Charge
# III's 15 and Blades I's 16 of the first theme. A fight's open plays its theme's whole groove, and its clap and percussion
# are in from the first bar, where walking music's come in a few bars into the theme: nothing in the drums changes until the
# hats turn sixteen bars in.) A fight's drums grow: its open is the kick, the clap and its roll; the hats come in with the
# theme, and the first percussion figure at its ninth bar.
FIGHT_DRUMS_GROW = True
# (2026-11-20, the boredom meter: a theme's drums the same sixteen bars from where its hats turned, in walking music as in the
# fights: The Deep Road III, Drowned Halls III, Stand Fast I, By the Fire II. The hats and the percussion turned on the same
# bar, every sixteen.) In a theme the percussion turns eight bars after the hats: the hats at the seventeenth bar, the other
# figure at the twenty-fifth, and so on, so that something in the drums changes every eight bars. Not in a calm piece.
THEME_STAGGERS = True
# (2026-11-20, the boredom meter: Mill Stream II's last drop the same 39 bars from its first, The Old Swamp III's 23; DROP_OUT
# breaks a long drop's end only (Mirage I's 20 bars there gone with it, the judges up on both), and the turn of the hats and
# the percussion figures at the drop's second block sits too far under the kick, the clap and the hats to be heard, DROP_PEAK
# showed.) A drop of thirty-two bars or more opens up at its second block: a ride comes in on the beat, a wash over the top
# that is heard, as a long house drop brings in a layer after its first sixteen bars (not where the palette's percussion is a
# ride already). Not in a calm piece.
LONG_DROP_GROWS = True
# (2026-11-21, the boredom meter on House made again on 0a807e7: Breakwater I's drums the same 40 bars from its theme's ninth
# bar, Dripstone I's 23, Ash Wind III's, River Drums III's, Parrots III's and Mirage III's 16; Thunderhead III's 44 the night
# before. Every sixteen-bar turn of a House groove is in the top, a hat figure for another and one high percussion for
# another, under the same kick and the same backbeat from a theme's first bar to its last: the meter heard none of them,
# deaf then to the hats' ring, which an ear hears.) The backbeat turns with the hats: in every second sixteen bars of a theme
# or a drop it is thickened (a clap
# with a snare under it) or, where it was thick, thinned to the clap alone (MIDS_TURN), a turn in the mids every sixteen bars.
# Not in a calm piece.
# Left off (2026-11-21, 05:26, the demo on Breakwater I): the meter heard it (its drums the same 40 bars before, 16 at the most
# after), but the judges on the theme's bars 8 to 24: TuneJury with the House brief 1.07 to 0.85, with none 1.10 to 1.04,
# enjoyment and SongEval level: a snare under the clap is less progressive house (claps, not snares, on two and four).
THEME_MIDS = False
MIDS_TURN = {("clap",): ("clap", "snare"), ("clap", "snare"): ("clap",), ("snare2",): ("snare2", "clap")}
# The house ways of turning the mids every second sixteen bars: "snap", a finger snap laid on the backbeat; "clap2", a second
# clap laid on it; "ghost", a soft kick on the bar's last eighth. "" for none. Left off (2026-11-21, 06:52, Breakwater I's
# theme bars 8 to 24 side by side): the snap level (TuneJury with the House brief 1.02 to 1.08), the second clap down (1.02 to
# 0.86 with no brief, SongEval down on every axis), the ghost kick not heard; the meter heard neither. The drums turn every
# eight bars in the hats all along, which the meter hears since it hears their ring (tools/boredom.py, 2026-11-21).
MIDS_WAY = ""
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
# How big a lead voice is, for which plays the drops and which the quiet places (`Take.lead`): the saws and the brass
# carry a drop, a plucked or struck voice sits between, a hollow square, a pipe or a whistle is the gentle one.
LEAD_WEIGHT = {"super": 3, "saw": 3, "brass": 3, "oud": 2, "keys": 2, "glass": 2, "bell": 2, "pluck": 2, "string": 2,
               "harp": 1, "marimba": 1, "hollow": 1, "pipe": 1, "flute": 1, "whistle": 1}
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
# (2026-11-20, 21:46, playing House: "No organs in the house music".) House has no organ: not as its bass, its chords or its
# pad. Each palette's organ became a sound of its own world in the same place among its choices, so that only the takes that
# had drawn the organ changed: a square or FM bass, a piano, an electric piano, a stab, a pluck or a harp for the chords, and
# strings, a warm, hollow or glass pad.
PALETTES: dict[str, dict[str, Any]] = {
    "pastoral": dict(bass=("pluck", "square", "sub", "fm"), bass_style=("offbeat", "tresillo", "offbeat_oct", "synco"),
                     keys=("string", "keys", "pluck", "harp", "piano"), keys_style=("strum", "stabs", "arp", "broken"),
                     lead=("whistle", "keys", "string", "flute"), pad=("warm", "strings", "hollow", "glass"),
                     perc=("tambourine", "maracas", "clap2", "snap"), hats=("eighths", "off", "shuffle", "sixteenths"),
                     atmos="", voicing="close"),
    "pastoral-deep": dict(bass=("saw", "pluck", "reese", "square"), bass_style=("rolling", "offbeat", "synco"),
                          keys=("pluck", "piano", "string", "stab"), keys_style=("arp", "stabs", "broken"),
                          lead=("saw", "flute", "pluck", "hollow"), pad=("super", "warm", "strings", "hollow"),
                          perc=("maracas", "tambourine", "rim"), hats=("sixteenths", "off", "eighths"), atmos="", voicing="close"),
    "highland": dict(bass=("sub", "square", "pluck"), bass_style=("offbeat", "long", "tresillo"),
                     keys=("harp", "pluck", "piano", "string"), keys_style=("arp", "broken", "pumpchords", "strum"),
                     lead=("pipe", "whistle", "flute", "hollow"), pad=("warm", "hollow", "strings", "glass"),
                     perc=("rim", "tambourine", "tom", "snap"), hats=("eighths", "shuffle", "off"), atmos="wind", voicing="open"),
    "highland-deep": dict(bass=("reese", "saw", "sub"), bass_style=("driving", "rolling", "long"),
                          keys=("brass", "pluck", "harp", "stab"), keys_style=("stabs", "arp", "pumpchords"),
                          lead=("pipe", "saw", "hollow", "super"), pad=("hollow", "super", "warm"),
                          perc=("tom", "rim", "maracas"), hats=("sixteenths", "eighths", "sparse"), atmos="wind", voicing="open"),
    "haunted-light": dict(bass=("sub", "fm", "square"), bass_style=("long", "offbeat", "dub"),
                          keys=("bell", "keys", "marimba", "glass"), keys_style=("arp", "broken", "stabs"),
                          lead=("glass", "whistle", "keys", "bell"), pad=("glass", "strings", "warm", "hollow"),
                          perc=("rim", "chime", "snap"), hats=("sparse", "eighths", "off"), atmos="wind", voicing="close"),
    "haunted-dark": dict(bass=("reese", "sub", "saw"), bass_style=("dub", "long", "rolling"),
                         keys=("bell", "stab", "pluck", "glass"), keys_style=("stabs", "arp", "pumpchords"),
                         lead=("hollow", "bell", "saw", "glass"), pad=("strings", "hollow", "glass"),
                         perc=("rim", "chime", "clave"), hats=("sparse", "sixteenths", "off"), atmos="wind", voicing="close"),
    "desert": dict(bass=("pluck", "fm", "square"), bass_style=("tresillo", "synco", "offbeat"),
                   keys=("oud", "string", "marimba", "pluck"), keys_style=("strum", "arp", "broken"),
                   lead=("oud", "flute", "hollow", "pipe"), pad=("warm", "hollow", "glass"),
                   perc=("bongo", "tambourine", "agogo", "timbale"), hats=("shuffle", "eighths", "sparse"), atmos="wind", voicing="open"),
    "desert-dark": dict(bass=("saw", "reese", "fm"), bass_style=("synco", "driving", "tresillo"),
                        keys=("oud", "pluck", "brass", "marimba"), keys_style=("arp", "strum", "stabs"),
                        lead=("hollow", "oud", "saw", "flute"), pad=("hollow", "warm", "super"),
                        perc=("bongo", "timbale", "clave"), hats=("sixteenths", "shuffle", "eighths"), atmos="wind", voicing="open"),
    "jungle": dict(bass=("pluck", "square", "fm"), bass_style=("rolling", "tresillo", "synco"),
                   keys=("marimba", "pluck", "string", "piano"), keys_style=("arp", "broken", "stabs"),
                   lead=("flute", "marimba", "whistle", "pluck"), pad=("warm", "glass", "strings"),
                   perc=("conga", "agogo", "cabasa", "bongo"), hats=("shuffle", "sixteenths", "eighths"), atmos="", voicing="close"),
    "jungle-dark": dict(bass=("reese", "saw", "pluck"), bass_style=("rolling", "synco", "dub"),
                        keys=("marimba", "pluck", "keys", "stab"), keys_style=("arp", "stabs", "broken"),
                        lead=("flute", "hollow", "pluck", "saw"), pad=("hollow", "warm", "glass"),
                        perc=("conga", "quijada", "bongo", "clave"), hats=("sixteenths", "shuffle", "sparse"), atmos="", voicing="close"),
    "infernal-light": dict(bass=("saw", "square", "pluck"), bass_style=("driving", "offbeat", "rolling"),
                           keys=("brass", "stab", "piano", "pluck"), keys_style=("stabs", "pumpchords", "arp"),
                           lead=("saw", "brass", "hollow", "super"), pad=("super", "hollow", "strings"),
                           perc=("cowbell", "clave", "tom"), hats=("sixteenths", "off", "eighths"), atmos="fire", voicing="close"),
    "infernal-dark": dict(bass=("reese", "saw", "square"), bass_style=("driving", "rolling", "synco"),
                          keys=("stab", "brass", "pluck", "piano"), keys_style=("stabs", "arp", "pumpchords"),
                          lead=("saw", "hollow", "super", "brass"), pad=("hollow", "super", "strings"),
                          perc=("cowbell", "tom", "clave"), hats=("sixteenths", "eighths", "off"), atmos="fire", voicing="close"),
    "regal": dict(bass=("saw", "fm", "pluck"), bass_style=("offbeat_oct", "offbeat", "driving"),
                  keys=("brass", "piano", "stab", "harp"), keys_style=("stabs", "pumpchords", "broken"),
                  lead=("super", "brass", "saw", "keys"), pad=("strings", "super", "warm"),
                  perc=("clap2", "tambourine", "ride", "snap"), hats=("off", "eighths", "sixteenths"), atmos="", voicing="close"),
    "regal-deep": dict(bass=("reese", "saw", "square"), bass_style=("rolling", "driving", "offbeat"),
                       keys=("brass", "stab", "pluck"), keys_style=("pumpchords", "stabs", "arp"),
                       lead=("saw", "super", "hollow"), pad=("strings", "hollow", "super"),
                       perc=("ride", "tom", "rim"), hats=("sixteenths", "off", "eighths"), atmos="", voicing="close"),
    "mystic": dict(bass=("sub", "fm", "pluck"), bass_style=("long", "offbeat", "tresillo"),
                   keys=("harp", "glass", "bell", "keys"), keys_style=("arp", "broken", "strum"),
                   lead=("glass", "whistle", "harp", "bell"), pad=("glass", "strings", "warm", "hollow"),
                   perc=("chime", "rim", "maracas"), hats=("sparse", "eighths", "off"), atmos="sea", voicing="close"),
    "mystic-deep": dict(bass=("sub", "reese", "fm"), bass_style=("long", "dub", "rolling"),
                        keys=("glass", "harp", "pluck"), keys_style=("arp", "pumpchords", "broken"),
                        lead=("hollow", "glass", "saw"), pad=("glass", "hollow", "super"),
                        perc=("chime", "rim", "clave"), hats=("sparse", "sixteenths", "eighths"), atmos="sea", voicing="close"),
    "ember": dict(bass=("sub", "square", "fm"), bass_style=("long", "dub", "offbeat"),
                  keys=("keys", "string", "harp", "glass"), keys_style=("broken", "strum", "arp"),
                  lead=("whistle", "keys", "glass", "flute"), pad=("warm", "strings", "glass"),
                  perc=("snap", "maracas", "rim"), hats=("sparse", "eighths", "shuffle"), atmos="fire", voicing="close"),
    "night": dict(bass=("sub", "fm", "pluck"), bass_style=("long", "offbeat", "dub"),
                  keys=("bell", "glass", "keys", "harp"), keys_style=("arp", "broken", "stabs"),
                  lead=("glass", "flute", "whistle", "keys"), pad=("glass", "warm", "hollow"),
                  perc=("rim", "maracas", "chime"), hats=("sparse", "eighths", "shuffle"), atmos="crickets", voicing="close"),
    "depths": dict(bass=("sub", "reese", "fm"), bass_style=("dub", "long", "synco"),
                   keys=("stab", "pluck", "bell", "glass"), keys_style=("dub", "stabs", "arp"),
                   lead=("hollow", "glass", "bell", "saw"), pad=("hollow", "warm", "glass"),
                   perc=("rim", "clave", "chime"), hats=("sparse", "off", "eighths"), atmos="drips", voicing="close"),
    "storm": dict(bass=("reese", "saw", "square"), bass_style=("driving", "rolling", "synco"),
                  keys=("stab", "pluck", "brass"), keys_style=("arp", "stabs", "pumpchords"),
                  lead=("saw", "hollow", "super"), pad=("super", "hollow", "strings"),
                  perc=("tom", "ride", "maracas"), hats=("sixteenths", "eighths", "off"), atmos="rain", voicing="close"),
    "battle": dict(bass=("reese", "saw", "pluck"), bass_style=("driving", "rolling", "synco"),
                   keys=("stab", "brass", "pluck"), keys_style=("stabs", "arp", "pumpchords"),
                   lead=("saw", "super", "hollow"), pad=("super", "hollow", "strings"),
                   perc=("tom", "cowbell", "ride"), hats=("sixteenths", "off", "eighths"), atmos="", voicing="close"),
    # Hard (2026-11-24). Nothing sweet in it: no maracas, chimes, tambourines or snaps, no harp, bell, glass or whistle; a bass that drives, stabs with no third
    # ("open"), a riff low down, toms and rims and claves.
    "hard": dict(bass=("saw", "reese", "square"), bass_style=("driving", "rolling"), keys=("stab",), keys_style=("stabs",),
                 lead=("saw", "hollow", "super"), pad=("hollow",), perc=("tom", "rim", "clave"), hats=("off", "sixteenths"), atmos="", voicing="open", low=True),
    "hard-broken": dict(bass=("reese", "saw"), bass_style=("synco", "rolling"), keys=("stab", "pluck"), keys_style=("stabs", "dub", "stabs"),
                        lead=("hollow", "saw", "super"), pad=("hollow",), perc=("rim", "tom", "quijada"), hats=("sixteenths", "off"), atmos="", voicing="open", low=True),
    "hard-slow": dict(bass=("sub", "reese"), bass_style=("dub", "long"), keys=("stab",), keys_style=("dub", "stabs"),
                      lead=("hollow", "saw"), pad=("hollow",), perc=("rim", "clave"), hats=("sparse", "off"), atmos="", voicing="open", low=True),
    # (2026-11-25: sixty hard songs on one set of drums.) Skins, and hats in threes; a gallop, with a ride.
    "hard-tribal": dict(bass=("reese", "saw"), bass_style=("tresillo", "rolling"), keys=("stab",), keys_style=("stabs", "dub"),
                        lead=("saw", "hollow", "super"), pad=("hollow",), perc=("conga", "timbale", "bongo"), hats=("thirds", "shuffle"), atmos="", voicing="open", low=True),
    "hard-gallop": dict(bass=("saw", "square", "reese"), bass_style=("driving", "synco"), keys=("stab", "pluck"), keys_style=("stabs", "dub"),
                        lead=("saw", "super", "hollow"), pad=("hollow",), perc=("ride", "rim", "tom"), hats=("gallop", "off"), atmos="", voicing="open", low=True),
    # ...and what is left when the hard ones have gone home: an inn's, a camp's, a night's. A low tune sung, not a riff; low chords with no third; a rim and a clave.
    "after-hours": dict(bass=("sub", "reese"), bass_style=("dub", "long"), keys=("keys",), keys_style=("broken", "stabs"),
                        lead=("hollow", "saw"), pad=("hollow",), perc=("rim", "clave"), hats=("sparse", "off"), atmos="", voicing="open", low=True, grim=True),
    # The new kinds of place (2026-11-17, evening: "make sure all genres got the updates around new place categories"): the
    # marsh's dub bass, marimba and glass, a jawbone rattle and drips; the coast's harp and strummed strings, whistle and the
    # sea; the snow's bells and glass and wind. Each a light one and a deep one, as the others are.
    "marsh": dict(bass=("sub", "fm", "pluck"), bass_style=("dub", "long", "offbeat"),
                  keys=("marimba", "pluck", "glass", "keys"), keys_style=("arp", "broken", "dub"),
                  lead=("flute", "hollow", "pipe", "glass"), pad=("hollow", "warm", "glass"),
                  perc=("quijada", "conga", "rim", "cabasa"), hats=("sparse", "shuffle", "eighths"), atmos="drips", voicing="close"),
    "marsh-dark": dict(bass=("reese", "sub", "saw"), bass_style=("dub", "rolling", "long"),
                       keys=("stab", "pluck", "glass", "marimba"), keys_style=("stabs", "arp", "dub"),
                       lead=("hollow", "glass", "saw", "pipe"), pad=("hollow", "warm", "glass"),
                       perc=("quijada", "rim", "clave"), hats=("sparse", "sixteenths", "off"), atmos="rain", voicing="close"),
    "coast": dict(bass=("pluck", "sub", "fm"), bass_style=("offbeat", "tresillo", "offbeat_oct"),
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
    act: str = ""                  # whose instruments its first take has (club.ACTS), where it says
    bpm: int = BPM                 # how fast it goes (`at`)
    hook: str = ""                 # how a hard song's riff is made (HOOKS_OF); "" hammered

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


# The dark families that had no take when the hard ones were written (2026-11-24): a dark palette's percussion is a light one's still (chimes in the haunted, shakers in the caves, a
# cowbell in the infernal), and an act plays what is written for it. These have none of it. Those that were made keep theirs.
GRIM = frozenset(("camp-07", "depths-05", "depths-06", "depths-07", "depths-08", "boss-04", "boss-05", "boss-06", "night-07", "night-08", "town-08", "town-09", "ember-11", "ember-12", "camp-11", "camp-12",
                  "night-11", "night-12", "depths-10", "storm-08"))
SWEET = ("chime", "maracas", "tambourine", "snap", "clap2", "cabasa", "agogo", "cowbell")


def grim(palette: dict) -> dict:
    """A palette with nothing sweet struck in it."""
    struck = tuple(each for each in palette["perc"] if each not in SWEET)
    return dict(palette, perc=struck if len(struck) > 1 else struck + tuple(each for each in ("rim", "tom", "clave") if each not in struck)[:2 - len(struck)], grim=True)


@contextmanager
def at(bpm: float):
    """House at another tempo, for as long as a song of it is written or played: the writer's and the desk's beat are these (2026-11-24: every song was at 110)."""
    from . import club
    kept = {name: globals()[name] for name in ("BPM", "BEAT", "STEP", "BAR", "BAR_FRAMES")}
    beat = 60.0 / bpm
    try:
        globals().update(BPM=int(bpm) if float(bpm).is_integer() else bpm, BEAT=beat, STEP=beat / 4.0, BAR=4.0 * beat, BAR_FRAMES=RATE * 240.0 / bpm)
        club.BEAT = beat
        yield
    finally:
        globals().update(kept)
        club.BEAT = kept["BEAT"]


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
    # (2026-11-22: "lets work on filling that drive with more music for every scenario, following everything weve learned".) A
    # new set: a family more for each kind of place, its key, changes, shape, groove and machine none of its kind's; and the
    # marsh's, the coast's and the snow's own inn, night, cave, camp, storm, fight, boss and town, which had the nearest of the
    # others' until now; and a third battleground.
    Family("pastoral-05", "Hay Bale Sunset", ("pastoral",), W, S01, True, 2, "M5", (16, 16, 8, 24, 16), "four", 0.08, "707", "pastoral"),
    Family("highland-06", "Cairn Wind", ("highland", "frozen"), W, S01, False, 4, "N4", (16, 24, 8, 24, 8), "four", 0.0, "808", "highland-deep"),
    Family("haunted-06", "Gaslight", ("haunted",), W, S01, False, 10, "N5", T8, "broken", 0.0, "909", "haunted-dark"),
    Family("desert-06", "Salt Caravan", ("desert",), W, S01, True, 3, "P4", (16, 16, 8, 24, 16), "broken3", 0.1, "707", "desert"),
    Family("jungle-06", "Monsoon Drums", ("jungle", "marsh"), W, S01, False, 2, "N6", T8, "broken2", 0.06, "808", "jungle-dark"),
    Family("infernal-05", "Cinder Bloom", ("infernal",), W, S01, True, 9, "D4", E5, "four", 0.0, "707", "infernal-light"),
    Family("regal-05", "Gilded Halls", ("regal",), W, S01, True, 7, "M3", T8, "four", 0.04, "909", "regal"),
    Family("mystic-05", "Moth Wings", ("mystic",), W, S01, True, 1, "L2", (16, 16, 8, 24, 16), "broken", 0.08, "606", "mystic"),
    Family("marsh-04", "Willow Lanterns", ("marsh",), W, S01, True, 4, "D1", E5, "four", 0.06, "707", "marsh"),
    Family("coast-04", "Tidepools", ("coast",), W, S01, True, 11, "L1", T8, "broken", 0.08, "606", "coast"),
    Family("frozen-04", "Hoarfrost", ("frozen",), W, S01, False, 6, "N2", (16, 24, 8, 24, 8), "four", 0.0, "808", "frozen-deep"),
    Family("ember-04", "Driftwood Hearth", ("marsh", "coast", "frozen"), "ember", S01, True, 2, "M4", (8, 16, 8, 16, 8), "half", 0.12, "707", "ember"),
    Family("night-04", "Moonlit Ebb", ("marsh", "coast", "frozen"), "night", S01, True, 9, "L1", E5, "four", 0.04, "808", "night"),
    Family("depths-04", "Sunken Grotto", ("marsh", "coast", "frozen"), "depths", S01, False, 4, "N6", (16, 24, 8, 24, 8), "broken2", 0.0, "909", "depths"),
    Family("camp-04", "Tide Camp", ("marsh", "coast", "frozen"), "camp", S01, True, 7, "L3", (8, 16, 8, 16, 8), "half", 0.1, "606", "ember"),
    Family("storm-03", "Squall", ("marsh", "coast", "frozen"), "storm", S01, False, 0, "N3", (8, 16, 16, 24, 8), "broken", 0.0, "909", "storm"),
    Family("battle-05", "Breakers", ("marsh", "coast", "frozen"), "battle", S2, False, 2, "P3", (4, 16, 8, 16, 8), "four", 0.0, "909", "battle"),
    Family("boss-03", "The Leviathan", ("marsh", "coast", "frozen"), "boss", S2, False, 3, "N5", (8, 16, 8, 24, 8), "four", 0.0, "909", "battle"),
    Family("town-03", "Fishmarket", ("marsh", "coast", "frozen"), "town", S01, True, 10, "M6", (8, 16, 8, 16, 8), "broken2", 0.1, "707", "coast"),
    Family("battleground-03", "Siege Bells", ANY, "battleground", S012, False, 6, "N4", (4, 16, 8, 24, 8), "four", 0.0, "909", "battle"),
    # (2026-11-22, night: the drive at 12%, "more music for every scenario"; and since the 17th, "lots of options of inns
    # camping, caves dungeons and just a not repetative experienxe".) Every group of places had one inn, one camp, one cave,
    # one night and one boss of House's own, three takes of each, while its walking music had five or six families: a second
    # of each, its key, changes, groove and machine none of its sibling's (the family of the same moment for the same places),
    # and a second town for the green lands. The inns all light, the caves and the bosses all heavy, the camps and the nights
    # light where their sibling was heavy and heavy where it was light ("light and heavy take turns").
    Family("ember-05", "Low Rafters", ("pastoral", "regal", "highland"), "ember", S01, True, 9, "D2", (8, 16, 8, 16, 8), "none", 0.1, "707", "ember"),
    Family("ember-06", "Hushed Parlour", ("haunted", "mystic", "jungle"), "ember", S01, True, 3, "D4", (8, 16, 8, 16, 8), "broken", 0.12, "808", "ember"),
    Family("ember-07", "Mint Tea", ("desert", "jungle", "infernal"), "ember", S01, True, 10, "P4", (8, 16, 8, 16, 8), "none", 0.14, "606", "desert"),
    Family("ember-08", "Mended Nets", ("marsh", "coast", "frozen"), "ember", S01, True, 11, "X2", (8, 16, 8, 16, 8), "broken", 0.08, "808", "coast"),
    Family("camp-05", "Bedroll Sky", ("pastoral", "regal", "highland"), "camp", S01, True, 5, "M1", (8, 16, 8, 16, 8), "none", 0.06, "808", "night"),
    Family("camp-06", "Ghostfire", ("haunted", "infernal", "mystic"), "camp", S01, True, 0, "L3", (8, 16, 8, 16, 8), "half", 0.06, "606", "ember"),
    Family("camp-07", "Nomad Fire", ("desert", "jungle", "mystic"), "camp", S01, False, 8, "N5", (8, 16, 8, 16, 8), "none", 0.0, "808", "night"),
    Family("camp-08", "Ice Fishing", ("marsh", "coast", "frozen"), "camp", S01, True, 1, "D1", (8, 16, 8, 16, 8), "broken", 0.08, "707", "frozen"),
    Family("depths-05", "Lodestone", ("highland", "regal", "infernal"), "depths", S01, False, 7, "P1", (16, 16, 16, 24, 8), "broken3", 0.0, "909", "depths"),
    Family("depths-06", "Glowworm Hollow", ("haunted", "mystic", "jungle"), "depths", S01, False, 10, "N1", E5, "four", 0.0, "808", "depths"),
    Family("depths-07", "Sandstone Hollow", ("desert", "pastoral"), "depths", S01, False, 5, "P4", (16, 24, 8, 24, 8), "broken", 0.06, "909", "desert-dark"),
    Family("depths-08", "Frozen Echoes", ("marsh", "coast", "frozen"), "depths", S01, False, 0, "D3", T8, "four", 0.0, "808", "frozen-deep"),
    Family("boss-04", "Throne of Ash", ("haunted", "infernal", "desert", "jungle"), "boss", S2, False, 8, "N2", (8, 16, 8, 24, 8), "broken2", 0.0, "808", "battle"),
    Family("boss-05", "The Usurper", ("pastoral", "regal", "highland", "mystic"), "boss", S2, False, 1, "N1", (8, 16, 8, 24, 8), "broken3", 0.0, "909", "battle"),
    Family("boss-06", "Drowned King", ("marsh", "coast", "frozen"), "boss", S2, False, 10, "N3", (8, 16, 8, 24, 8), "broken", 0.0, "808", "battle"),
    Family("night-05", "Dewfall", ("pastoral", "regal", "highland", "mystic"), "night", S01, True, 3, "L2", E5, "broken", 0.06, "606", "night"),
    Family("night-06", "Whispering Boughs", ("haunted", "mystic", "jungle"), "night", S01, True, 11, "D2", T8, "four", 0.04, "808", "night"),
    Family("night-07", "Desert Nocturne", ("desert", "highland", "infernal"), "night", S01, False, 9, "P3", (16, 16, 8, 24, 16), "broken3", 0.0, "707", "desert-dark"),
    Family("night-08", "Black Water", ("marsh", "coast", "frozen"), "night", S01, False, 6, "N4", (16, 24, 8, 24, 8), "broken2", 0.0, "909", "coast-deep"),
    Family("town-04", "Guildhall Steps", ("regal", "pastoral", "highland"), "town", S01, True, 0, "M3", (8, 16, 8, 16, 8), "broken2", 0.08, "909", "regal"),
    # ("need some darker stuff", 2026-11-23: 65 of 100 of the walking music and every inn and town was light; minor and phrygian,
    # the deep and dark palettes, one for each kind of place and for an inn, a camp, a night and a town.)
    Family("pastoral-06", "Gallows Meadow", ("pastoral",), W, S01, False, 1, "N2", (16, 24, 8, 24, 8), "four", 0.0, "909", "pastoral-deep"),
    Family("pastoral-07", "Scarecrow Road", ("pastoral", "highland"), W, S01, False, 10, "P1", T8, "broken3", 0.0, "808", "pastoral-deep"),
    Family("regal-06", "The Headsman's Walk", ("regal",), W, S01, False, 9, "N2", E5, "four", 0.0, "909", "regal-deep"),
    Family("regal-07", "Empty Throne", ("regal", "mystic"), W, S01, False, 3, "N6", (16, 24, 8, 24, 8), "broken2", 0.0, "808", "regal-deep"),
    Family("coast-05", "Wreckers' Lantern", ("coast", "marsh"), W, S01, False, 7, "N3", (16, 16, 16, 24, 8), "four", 0.0, "808", "coast-deep"),
    Family("coast-06", "Keelhaul", ("coast",), W, S01, False, 2, "P2", T8, "four", 0.0, "909", "coast-deep"),
    Family("frozen-05", "White Grave", ("frozen", "highland"), W, S01, False, 8, "N4", E5, "broken", 0.0, "808", "frozen-deep"),
    Family("highland-07", "Standing Dead", ("highland",), W, S01, False, 11, "N2", (16, 24, 8, 24, 8), "four", 0.0, "909", "highland-deep"),
    Family("mystic-06", "Eclipse Gate", ("mystic",), W, S01, False, 4, "N2", T8, "broken3", 0.0, "909", "mystic-deep"),
    Family("jungle-07", "Strangler Fig", ("jungle", "marsh"), W, S01, False, 8, "P1", (16, 16, 16, 24, 8), "four", 0.04, "909", "jungle-dark"),
    Family("haunted-07", "Bone Procession", ("haunted",), W, S01, False, 9, "P1", E5, "four", 0.0, "808", "haunted-dark"),
    Family("infernal-06", "Furnace Psalm", ("infernal", "haunted"), W, S01, False, 6, "P2", (16, 24, 8, 24, 8), "four", 0.0, "909", "infernal-dark"),
    Family("desert-07", "Vulture Sky", ("desert",), W, S01, False, 2, "P1", T8, "broken", 0.0, "909", "desert-dark"),
    Family("ember-09", "Undertaker's Table", ("haunted", "infernal", "marsh"), "ember", S01, False, 1, "N4", (8, 16, 8, 16, 8), "half", 0.06, "808", "night"),
    Family("camp-09", "No Fire Tonight", ("pastoral", "regal", "highland", "frozen"), "camp", S01, False, 8, "N6", (8, 16, 8, 16, 8), "none", 0.0, "808", "night"),
    Family("night-09", "Moonless", ("pastoral", "regal", "highland", "coast"), "night", S01, False, 10, "N2", (16, 24, 8, 24, 8), "broken3", 0.0, "909", "haunted-dark"),
    Family("town-05", "Curfew Bell", ("regal", "pastoral", "highland"), "town", S01, False, 8, "N1", (8, 16, 8, 16, 8), "broken2", 0.04, "909", "regal-deep"),
    # (Round one of the standing cycle, 2026-11-23: House's storms and towns had seven songs each, its camps, nights, caves and inns ten.)
    Family("storm-04", "Cannonade", ("pastoral", "regal", "highland", "coast"), "storm", S01, False, 7, "N5", (8, 24, 8, 24, 8), "broken3", 0.0, "909", "infernal-dark"),
    Family("storm-05", "Black Rain", ("haunted", "marsh", "jungle"), "storm", S01, False, 3, "N4", (8, 16, 16, 24, 8), "four", 0.0, "808", "haunted-dark"),
    Family("storm-06", "Sandblast", ("desert", "infernal", "jungle"), "storm", S01, False, 8, "P3", (8, 24, 8, 24, 8), "broken2", 0.0, "909", "desert-dark"),
    Family("storm-07", "Ice Fang", ("frozen", "coast", "highland"), "storm", S01, False, 6, "N3", (8, 16, 16, 24, 8), "four", 0.0, "808", "frozen-deep"),
    Family("town-06", "Smog Quarter", ("infernal", "haunted", "marsh", "jungle"), "town", S01, False, 3, "N2", (8, 16, 8, 16, 8), "broken2", 0.08, "909", "infernal-dark"),
    Family("town-07", "Customs Wall", ("coast", "marsh", "frozen"), "town", S01, False, 11, "P1", (8, 16, 8, 16, 8), "four", 0.06, "808", "coast-deep"),
    Family("camp-10", "Dead Radio", ("haunted", "mystic", "infernal", "jungle"), "camp", S01, False, 5, "P2", (8, 16, 8, 16, 8), "none", 0.0, "909", "haunted-dark"),
    Family("night-10", "Sleepless Shift", ("coast", "marsh", "regal"), "night", S01, False, 7, "N6", (16, 24, 8, 24, 8), "broken", 0.04, "606", "coast-deep"),
    Family("ember-10", "Cellar Door", ("pastoral", "regal", "highland"), "ember", S01, False, 9, "N5", (8, 16, 8, 16, 8), "half", 0.1, "808", "regal-deep"),
    Family("depths-09", "Ossuary", ("haunted", "mystic", "infernal"), "depths", S01, False, 9, "N4", E5, "broken3", 0.0, "909", "haunted-dark"),
    # (Round two, 2026-11-23, written down then and held for the leads: where House's dark music was missing: the desert's and the mystic lands' towns, the inns of
    # the desert, the jungle, the mystic lands, the coast and the snow, two camps, two nights, a cave for the desert and the fields, a storm for the cities. Each
    # in an act of its own: club.ACTS.)
    Family("town-08", "Knife Bazaar", ("desert", "jungle", "mystic"), "town", S01, False, 5, "P3", (8, 16, 8, 16, 8), "broken2", 0.08, "808", "desert-dark"),
    Family("town-09", "Black Market", ("regal", "highland", "pastoral"), "town", S01, False, 1, "N6", (8, 16, 8, 16, 8), "four", 0.04, "909", "regal-deep"),
    Family("ember-11", "Speakeasy", ("desert", "jungle", "infernal"), "ember", S01, False, 2, "P4", (8, 16, 8, 16, 8), "half", 0.1, "808", "desert-dark"),
    Family("ember-12", "Low Ceiling", ("mystic", "frozen", "coast"), "ember", S01, False, 8, "N3", (8, 16, 8, 16, 8), "broken", 0.08, "606", "coast-deep"),
    Family("camp-11", "Wet Powder", ("marsh", "coast", "jungle"), "camp", S01, False, 9, "P2", (8, 16, 8, 16, 8), "none", 0.0, "808", "marsh-dark"),
    Family("camp-12", "Frostbite", ("frozen", "highland", "desert"), "camp", S01, False, 5, "N6", (8, 16, 8, 16, 8), "half", 0.04, "606", "frozen-deep"),
    Family("night-11", "Blackout", ("haunted", "infernal", "marsh"), "night", S01, False, 0, "P1", (16, 24, 8, 24, 8), "four", 0.0, "909", "infernal-dark"),
    Family("night-12", "Red Moon", ("desert", "jungle", "frozen", "highland"), "night", S01, False, 10, "P3", (16, 24, 8, 24, 8), "broken", 0.04, "808", "desert-dark"),
    Family("depths-10", "Buried Machine", ("desert", "jungle", "pastoral", "highland"), "depths", S01, False, 11, "N3", E5, "broken3", 0.0, "909", "jungle-dark"),
    Family("storm-08", "Voltage", ("mystic", "regal", "frozen"), "storm", S01, False, 1, "N5", (8, 24, 8, 24, 8), "broken2", 0.0, "909", "mystic-deep"),
    # (Hard, 2026-11-24: the House in the player was counted: 76 of 193 songs in major, lydian or mixolydian, 102 light, maracas in 103, glass plucks in 74, all at 110. Faster,
    # on one chord and its shadow, no third in the stabs, a riff low down, the drums and the bass driven, an act of the hard ones.)
    Family("pastoral-08", "Gravel Pit", ("pastoral", "highland"), W, S01, False, 4, "H1", (16, 16, 8, 16, 8), "four", 0.1, "909", "hard", "warehouse", 126),
    Family("highland-08", "Strip Mine", ("highland", "frozen"), W, S01, False, 7, "H2", (8, 16, 4, 24, 8), "four", 0.0, "606", "hard", "foundry", 128),
    Family("haunted-08", "Meat Locker", ("haunted", "marsh"), W, S01, False, 1, "H4", (8, 24, 8, 24, 8), "broken2", 0.0, "808", "hard-broken", "cyborg", 122),
    Family("desert-08", "Scrap Yard", ("desert", "infernal"), W, S01, False, 9, "H1", (8, 16, 8, 24, 8), "four", 0.0, "808", "hard", "junkyard", 127),
    Family("jungle-08", "Chain Gang", ("jungle", "marsh"), W, S01, False, 2, "H5", (8, 24, 8, 16, 8), "broken3", 0.14, "909", "hard-broken", "signal", 124),
    Family("infernal-07", "Blast Furnace", ("infernal",), W, S01, False, 6, "H1", (8, 16, 8, 24, 8), "four", 0.0, "909", "hard", "foundry", 130),
    Family("regal-08", "Riot Line", ("regal", "pastoral"), W, S01, False, 11, "H2", (8, 16, 8, 24, 8), "four", 0.0, "909", "hard", "warehouse", 128),
    Family("mystic-07", "Cold Storage", ("mystic", "frozen"), W, S01, False, 8, "H4", (16, 16, 8, 24, 16), "broken", 0.16, "808", "hard-broken", "undercroft", 123),
    Family("coast-07", "Rail Yard", ("coast", "marsh"), W, S01, False, 3, "H3", (8, 16, 8, 16, 8), "four", 0.1, "909", "hard", "monolith", 125),
    Family("battle-06", "Bone Saw", ANY, "battle", S2, False, 0, "H1", (4, 16, 8, 24, 8), "four", 0.0, "909", "hard", "warehouse", 132),
    Family("storm-09", "Power Cut", ("desert", "coast", "highland", "infernal"), "storm", S01, False, 5, "H2", (8, 8, 8, 24, 8), "broken3", 0.12, "909", "hard-broken", "signal", 128),
    Family("depths-11", "Boiler Room", ("infernal", "regal", "highland"), "depths", S01, False, 10, "H4", (8, 24, 8, 24, 8), "broken2", 0.18, "808", "hard-slow", "undercroft", 118),
    # (The second set, the same day, "house is a little better keep iterating": the moments the first had one of or none.)
    Family("boss-07", "Iron Lung", ANY, "boss", S2, False, 1, "H1", (4, 16, 4, 24, 4), "four", 0.0, "909", "hard", "foundry", 132),
    Family("battle-07", "Knuckle Duster", ANY, "battle", S2, False, 10, "H2", (4, 8, 8, 24, 4), "four", 0.06, "808", "hard", "junkyard", 130),
    Family("battleground-04", "Trench Line", ANY, "battleground", S012, False, 7, "H1", (4, 16, 8, 24, 8), "four", 0.0, "909", "hard", "monolith", 131),
    Family("storm-10", "Dead Reckoning", ("coast", "marsh", "haunted", "frozen"), "storm", S01, False, 4, "H4", (8, 16, 8, 16, 8), "broken3", 0.1, "909", "hard-broken", "undercroft", 126),
    Family("depths-12", "Drop Shaft", ("haunted", "frozen", "mystic", "marsh"), "depths", S01, False, 0, "H1", (16, 24, 8, 16, 8), "broken2", 0.12, "808", "hard-slow", "cyborg", 120),
    Family("town-10", "Night Shift", ("regal", "infernal", "highland"), "town", S01, False, 9, "H5", (8, 16, 8, 16, 8), "four", 0.1, "909", "hard", "signal", 122),
    Family("marsh-05", "Sump", ("marsh", "haunted"), W, S01, False, 2, "H4", (8, 24, 4, 24, 8), "broken", 0.16, "808", "hard-broken", "undercroft", 121),
    Family("frozen-06", "Cold Iron", ("frozen", "highland"), W, S01, False, 8, "H2", (16, 16, 4, 24, 8), "four", 0.08, "606", "hard", "foundry", 127),
    Family("camp-13", "Burn Barrel", ("infernal", "desert", "highland", "marsh"), "camp", S01, False, 5, "H5", (8, 16, 8, 16, 8), "half", 0.08, "808", "after-hours", "chamber", 104),
    Family("ember-13", "Back Room", ("regal", "pastoral", "highland", "infernal"), "ember", S01, False, 3, "H2", (8, 16, 8, 16, 8), "broken", 0.12, "606", "after-hours", "velvet", 108),
    Family("night-13", "Dead Hours", ("regal", "infernal", "haunted", "marsh"), "night", S01, False, 6, "H4", (16, 24, 8, 24, 8), "broken", 0.08, "808", "after-hours", "vesper", 106),
    # (The third set, 17:25 the same day, where the player says House is heard the most per song: its towns, camps, inns, nights, storms and caves; and four more to walk to.)
    Family("town-11", "Pawn Shop", ("pastoral", "coast", "marsh"), "town", S01, False, 2, "H4", (8, 16, 8, 16, 8), "broken2", 0.14, "808", "hard-broken", "undercroft", 118),
    Family("town-12", "Dim Lamp Alley", ("haunted", "mystic", "frozen"), "town", S01, False, 10, "H3", (8, 16, 8, 16, 8), "four", 0.08, "909", "hard", "cyborg", 120),
    Family("camp-14", "Ash Bucket", ("pastoral", "regal", "frozen"), "camp", S01, False, 1, "H3", (8, 16, 8, 16, 8), "none", 0.06, "606", "after-hours", "vesper", 98),
    Family("camp-15", "Rust Water", ("coast", "jungle", "mystic", "haunted"), "camp", S01, False, 8, "H2", (8, 16, 8, 16, 8), "broken", 0.1, "707", "after-hours", "velvet", 102),
    Family("ember-14", "Closing Time", ("coast", "marsh", "frozen"), "ember", S01, False, 11, "H5", (8, 16, 8, 16, 8), "half", 0.12, "808", "after-hours", "chamber", 100),
    Family("ember-15", "Smoke Break", ("haunted", "desert", "jungle", "mystic"), "ember", S01, False, 4, "H3", (8, 16, 8, 16, 8), "broken", 0.1, "606", "after-hours", "vesper", 104),
    Family("night-14", "Graveyard Shift", ("pastoral", "coast", "frozen"), "night", S01, False, 9, "H1", (16, 24, 8, 24, 8), "broken3", 0.1, "808", "after-hours", "gallows", 108),
    Family("night-15", "Insomnia", ("desert", "jungle", "mystic", "highland"), "night", S01, False, 2, "H2", (16, 16, 8, 24, 16), "four", 0.06, "606", "after-hours", "cellar", 109),
    Family("storm-11", "Short Circuit", ("pastoral", "regal", "mystic", "jungle"), "storm", S01, False, 3, "H1", (8, 8, 8, 24, 8), "four", 0.0, "909", "hard", "monolith", 132),
    Family("depths-13", "Crawlspace", ("pastoral", "coast", "regal", "jungle", "desert"), "depths", S01, False, 6, "H4", (8, 24, 8, 16, 8), "broken", 0.14, "606", "hard-slow", "foundry", 118),
    Family("pastoral-09", "Barbed Wire", ("pastoral",), W, S01, False, 8, "H2", (8, 16, 4, 24, 8), "four", 0.0, "808", "hard", "junkyard", 124),
    Family("coast-08", "Dry Dock", ("coast",), W, S01, False, 5, "H5", (16, 16, 8, 16, 8), "broken2", 0.1, "909", "hard-broken", "foundry", 122),
    Family("marsh-06", "Backwater", ("marsh", "jungle"), W, S01, False, 0, "H1", (8, 24, 8, 16, 8), "broken3", 0.16, "808", "hard-broken", "cyborg", 119),
    Family("frozen-07", "Black Frost", ("frozen", "mystic"), W, S01, False, 11, "H3", (8, 16, 8, 24, 8), "four", 0.06, "909", "hard", "signal", 126),
    # (The fourth set, 22:10 the same night, where House is heard most per song still: its towns, camps, nights, inns and storms, the calm ones by the two acts that are not sweet (club.ACTS: cellar, gallows);
    # and the walks that have the fewest. From here on a riff has other cells and a drop two other shapes to draw from: LATER.)
    Family("town-13", "Lock-Up", ("regal", "highland", "desert"), "town", S01, False, 7, "H6", (8, 16, 8, 16, 8), "broken3", 0.12, "808", "hard-broken", "junkyard", 121),
    Family("town-14", "Toll Booth", ("coast", "jungle", "infernal"), "town", S01, False, 1, "H1", (8, 16, 8, 16, 8), "four", 0.1, "909", "hard", "warehouse", 124),
    Family("camp-16", "Cold Ashes", ("pastoral", "highland", "frozen"), "camp", S01, False, 4, "H4", (8, 16, 8, 16, 8), "half", 0.1, "808", "after-hours", "gallows", 96),
    Family("camp-17", "Oil Drum", ("desert", "jungle", "infernal"), "camp", S01, False, 11, "H2", (8, 16, 8, 16, 8), "broken", 0.12, "606", "after-hours", "cellar", 105),
    Family("ember-16", "Basement Bar", ("pastoral", "regal", "highland"), "ember", S01, False, 6, "H5", (8, 16, 8, 16, 8), "broken2", 0.14, "606", "after-hours", "cellar", 110),
    Family("ember-17", "Bad Debt", ("infernal", "haunted", "marsh", "desert"), "ember", S01, False, 9, "H7", (8, 16, 8, 16, 8), "half", 0.08, "808", "after-hours", "gallows", 99),
    Family("night-16", "Last Bus", ("regal", "coast", "pastoral"), "night", S01, False, 3, "H6", (16, 24, 8, 24, 8), "four", 0.1, "606", "after-hours", "cellar", 109),
    Family("night-17", "Hanging Tree", ("haunted", "frozen", "jungle"), "night", S01, False, 8, "H4", (16, 24, 8, 24, 8), "broken3", 0.06, "808", "after-hours", "gallows", 101),
    Family("storm-12", "Brownout", ("haunted", "marsh", "frozen", "coast"), "storm", S01, False, 10, "H7", (8, 8, 8, 24, 8), "broken2", 0.08, "808", "hard-broken", "junkyard", 127),
    Family("coast-09", "Bilge Pump", ("coast",), W, S01, False, 2, "H6", (8, 16, 4, 24, 8), "four", 0.0, "909", "hard", "warehouse", 125),
    Family("pastoral-10", "Grain Silo", ("pastoral", "highland"), W, S01, False, 5, "H7", (8, 24, 8, 16, 8), "broken", 0.14, "909", "hard-broken", "monolith", 122),
    Family("highland-09", "Rockfall", ("highland",), W, S01, False, 0, "H3", (16, 16, 8, 24, 8), "four", 0.06, "909", "hard", "signal", 128),
    Family("frozen-08", "Ice Drill", ("frozen",), W, S01, False, 6, "H1", (8, 16, 8, 24, 8), "broken3", 0.1, "606", "hard-broken", "foundry", 124),
    # (The fifth set, 2026-11-25: the five acts whose riffs are cut up or led by a machine of another kind (club.ACTS, "cut"), and three calm ones for the two that had none.)
    Family("town-15", "Slot Machine", ("desert", "regal", "infernal"), "town", S01, False, 10, "H3", (8, 16, 8, 16, 8), "four", 0.08, "606", "hard", "arcade", 122),
    Family("town-16", "Guard Dog", ("highland", "haunted", "pastoral"), "town", S01, False, 3, "H7", (8, 16, 8, 16, 8), "broken2", 0.12, "808", "hard-broken", "kennel", 119),
    Family("storm-13", "Wrecking Ball", ("highland", "infernal", "regal", "desert"), "storm", S01, False, 8, "H2", (8, 8, 8, 24, 8), "four", 0.0, "909", "hard", "chopshop", 130),
    Family("depths-14", "Third Rail", ("haunted", "mystic", "infernal"), "depths", S01, False, 4, "H4", (8, 24, 8, 16, 8), "broken", 0.14, "606", "hard-slow", "tunnel", 118),
    Family("depths-15", "Rock Crusher", ("highland", "frozen", "desert"), "depths", S01, False, 9, "H1", (16, 16, 8, 24, 8), "four", 0.06, "909", "hard", "quarry", 121),
    Family("coast-10", "Loading Bay", ("coast",), W, S01, False, 6, "H6", (8, 16, 8, 24, 8), "four", 0.06, "909", "hard", "chopshop", 124),
    Family("jungle-09", "Stray Dogs", ("jungle", "marsh"), W, S01, False, 1, "H1", (8, 24, 8, 16, 8), "broken3", 0.12, "808", "hard-broken", "kennel", 123),
    Family("infernal-08", "Slag Heap", ("infernal",), W, S01, False, 11, "H7", (16, 16, 8, 24, 8), "four", 0.0, "909", "hard", "quarry", 127),
    Family("mystic-08", "Dead Pixel", ("mystic", "haunted"), W, S01, False, 5, "H5", (8, 16, 4, 24, 8), "broken2", 0.1, "606", "hard-broken", "arcade", 120),
    Family("regal-09", "Weigh Station", ("regal",), W, S01, False, 2, "H3", (8, 24, 4, 24, 8), "four", 0.0, "606", "hard", "tunnel", 126),
    Family("camp-18", "Night Watchman", ("marsh", "coast", "haunted"), "camp", S01, False, 2, "H4", (8, 16, 8, 16, 8), "half", 0.1, "606", "after-hours", "mortuary", 94),
    Family("night-18", "Signal Box", ("highland", "mystic", "desert"), "night", S01, False, 7, "H2", (16, 24, 8, 24, 8), "broken", 0.1, "808", "after-hours", "switchyard", 103),
    Family("ember-18", "Flat Beer", ("frozen", "mystic", "coast"), "ember", S01, False, 0, "H6", (8, 16, 8, 16, 8), "broken2", 0.12, "808", "after-hours", "switchyard", 101),
    # (The sixth set, 2026-11-25, the tenth round: the ten acts of what was found in the synthesiser's wavetables and two calm ones, each with a song or two; their riffs made six other ways than by the hammer (HOOKS_OF),
    # a two-step's kick and a break's, skins, and a gallop.)
    Family("town-17", "Crowbar", ("regal", "coast", "frozen"), "town", S01, False, 4, "H2", (8, 16, 8, 16, 8), "step", 0.2, "606", "hard-gallop", "smelter", 124, "power"),
    Family("town-18", "Pit Boss", ("infernal", "desert", "jungle"), "town", S01, False, 9, "H7", (8, 16, 8, 16, 8), "broken2", 0.16, "808", "hard-tribal", "sluice", 119, "line"),
    Family("storm-14", "Tin Roof", ("coast", "marsh", "jungle", "pastoral"), "storm", S01, False, 1, "H1", (8, 8, 8, 24, 8), "breaks", 0.08, "909", "hard-gallop", "drydock", 131, "odd"),
    Family("storm-15", "Lightning Rod", ("highland", "frozen", "regal", "haunted"), "storm", S01, False, 6, "H3", (8, 8, 8, 24, 8), "four", 0.0, "909", "hard", "powerhouse", 128, "line"),
    Family("depths-16", "Coal Chute", ("infernal", "highland", "regal", "frozen"), "depths", S01, False, 0, "H4", (8, 24, 8, 16, 8), "broken", 0.14, "808", "hard-slow", "catacomb", 118, "toll"),
    Family("pastoral-11", "Rendering Plant", ("pastoral",), W, S01, False, 10, "H6", (8, 16, 8, 24, 8), "four", 0.06, "606", "hard", "icehouse", 125, "call"),
    Family("coast-11", "Fog Signal", ("coast",), W, S01, False, 3, "H5", (16, 16, 8, 16, 8), "step", 0.18, "909", "hard-broken", "millrace", 120, "glide"),
    Family("frozen-09", "Cold Chisel", ("frozen", "highland"), W, S01, False, 8, "H2", (8, 16, 4, 24, 8), "four", 0.0, "909", "hard-gallop", "faultline", 129, "power"),
    Family("highland-10", "Chain Hoist", ("highland",), W, S01, False, 5, "H7", (8, 24, 8, 16, 8), "broken3", 0.1, "909", "hard-tribal", "drydock", 123, "odd"),
    Family("marsh-07", "Sump Pump", ("marsh", "jungle"), W, S01, False, 2, "H1", (8, 16, 8, 24, 8), "breaks", 0.12, "606", "hard-broken", "pressroom", 121, "call"),
    Family("haunted-09", "Black Van", ("haunted", "mystic"), W, S01, False, 11, "H4", (16, 16, 8, 24, 8), "step", 0.2, "808", "hard-slow", "catacomb", 118, "glide"),
    Family("desert-09", "Open Cast", ("desert", "infernal"), W, S01, False, 7, "H3", (8, 24, 4, 24, 8), "four", 0.04, "808", "hard-tribal", "brickyard", 127, "line"),
    Family("regal-10", "Debt Collector", ("regal",), W, S01, False, 1, "H5", (8, 16, 8, 24, 8), "broken", 0.1, "909", "hard-gallop", "faultline", 124, "power"),
    Family("camp-19", "Cinder Block", ("highland", "infernal", "regal", "frozen"), "camp", S01, False, 3, "H6", (8, 16, 8, 16, 8), "half", 0.1, "606", "after-hours", "flophouse", 97),
    Family("camp-20", "Coal Smoke", ("coast", "marsh", "mystic"), "camp", S01, False, 8, "H3", (8, 16, 8, 16, 8), "broken2", 0.12, "808", "after-hours", "pumphouse", 101),
    Family("ember-19", "Grease Trap", ("pastoral", "coast", "jungle"), "ember", S01, False, 10, "H2", (8, 16, 8, 16, 8), "broken", 0.12, "808", "after-hours", "pumphouse", 106),
    Family("night-19", "Street Sweeper", ("regal", "highland", "desert"), "night", S01, False, 5, "H5", (16, 24, 8, 24, 8), "broken3", 0.08, "606", "after-hours", "flophouse", 105),
)
LATER = tuple(each.name for each in PLAN)[[each.name for each in PLAN].index("town-13"):]          # (the families from the fourth set of hard ones on: HAMMERS_LATER, SCENES_LATER)
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
# Riffs: cells of three sixteenths over the four beats, resolved by two eighths at the end of the phrase, every note on
# the chord (2026-11-18: "the lead is still lame"; the house study: deadmau5's hooks, "Strobe", "Phantoms Can't Hang",
# cells of three sixteenths over 4/4; the singing hooks above have long notes, a melody, where a house lead is a riff).
# (2026-11-19, 14:15: "your house suck", "study house on the loop with the same scrutiny".) A riff is a cell of three or
# four notes of the chord in an order drawn for the tune, said over the riff's rhythm again and again (Tune._riff_cell):
# the riffs had followed a slow curve with a note coming again for nothing, and settled on the chord's third and fifth,
# F F F F A A A A A (The Forge at Rest I), G G G D D D D (Canopy I); SongEval heard memorability 2.4 to 2.8 against Knight
# Rock's 2.9 to 3.0. False: the riff of 11-17.
RIFF_CELLS = True
# (The same study: a theme, the part heard most while walking about, had its hook only from halfway, two bars in every
# four: eight bars of tune in thirty-two, the rest groove alone.) The first half of a theme sings too, softly: the tune's
# first eight bars a phrase at a time, every four bars from the fifth (Take.lead). Not a fight's (its hook is there from
# the first bar) nor a calm piece's. False: the hook from halfway, as on 11-18.
THEME_SINGS = True
# (2026-11-24, 22:30: the hard songs' drops measure +1 to +13 and their themes, which are most of what is heard, -7 to +1: a theme's hook is the act's soft lead's.) A later hard song's (LATER) theme
# says its riff in the big lead's own voice, softly, coming up.
THEME_MAIN = True          # (on two songs, hard against sweet, the theme +4.0 and +4.8 with the soft lead's and +4.5 and +5.9 with the big one's, the drops no lower: in)
RIFFS = (
    ((0, 2), (3, 2), (6, 2), (9, 2), (12, 2), (14, 2), (16, 2), (19, 2), (22, 2), (25, 2), (28, 4)),
    ((0, 1), (3, 1), (6, 1), (8, 1), (11, 1), (14, 1), (16, 1), (19, 1), (22, 1), (24, 1), (27, 1), (30, 2)),
    ((0, 2), (3, 2), (6, 2), (8, 2), (10, 2), (12, 4), (16, 2), (19, 2), (22, 2), (24, 2), (26, 2), (28, 4)),
    ((0, 3), (3, 3), (6, 3), (9, 3), (12, 2), (14, 2), (16, 3), (19, 3), (22, 3), (25, 7)),
)
# A hard song's riff (2026-11-24, Riot Line read by the sheet: its riff was the chord's notes up and down over the bar, a trance lead's on a hard band): one note
# hammered, two bars of it, and three or four of its strokes somewhere else: the step over it, the step under it, the octave. A bar each, "x" a stroke, "-" the
# stroke held; the second bar of the two is the first's, or another's.
HAMMERS = ("x..x..x...x.x...", "x.xx..x.x.xx..x.", "x---x.xxx---x.x.", "xx.x.xx.x.x.xx..", "x.x.x.x.x.x.xxxx", "..x...x...x.x.xx", "x..xx..xx..xx.x.", "x-.x-.x-.x-.x.xx", "x.......x..x..x.")
# (...and the later families' (LATER): fifty hard songs on nine cells would have come round.)
HAMMERS_LATER = ("x..x.x..x..x.x..", "x.x..x.x..x.x..x", "x---..x.x---..xx", ".x.x..x..x.x..x.", "xxx...xxx...xx..", "x.....x.x.....x.", "x.xxx.x.x.xxx.x.", "x-.xx-.xx-.xx-.x")
# (2026-11-25, read through: every hard song hammered one note.) Six other ways a hard riff is made, each two bars said and answered as the hammer is (`Tune._phrased`): "line", a machine's sixteen steps;
# "glide", a few long notes, each slid into the next; "call", three or four strokes low down and an answer over them by the second synth; "power", a guitarist's riff with its holes; "toll", a stroke or two in
# a bar and the floor between them; "odd", a cell of three, five or seven sixteenths over the four.
HOOKS_OF = ("", "line", "glide", "call", "power", "toll", "odd")
GLIDES = (((0, 6), (6, 4), (10, 6), (16, 10), (26, 4)), ((0, 10), (10, 6), (16, 6), (22, 2), (24, 6)), ((0, 3), (3, 9), (12, 4), (16, 12), (28, 3)),
          ((0, 8), (8, 3), (11, 5), (16, 8), (24, 3), (27, 3)), ((2, 6), (8, 8), (18, 6), (24, 6)), ((0, 4), (6, 10), (16, 4), (22, 8)))
GLIDED = ((0, -1, 0, 2, 1), (0, 7, 6, 4, 2), (0, 1, 0, -2, -1), (0, 2, 3, 2, -1), (0, 7, 8, 7, 1), (0, -3, -1, 0, 1))          # where each of them goes, over the chord's root
CALLS = ("x.x...x.x.......", "x..x..x.........", "xx.x..xx........", "x...x.xx.x......", "..x.x.xx........", "x.xx....x.x.....", "x..x.x..x-......")
ANSWERS = (("....x.x.x---x...", (9, 8, 7, 4)), ("..x..x..x---....", (7, 8, 11)), ("x-x-x---........", (8, 7, 4)), ("....xxx.x---x---", (7, 7, 9, 8, 7)),
           ("..x.x.x.x-----..", (11, 9, 8, 7)), ("x..x..x-x-------", (7, 9, 8, 7)), ("......x.x.x.x---", (4, 7, 8, 9)))
# A riff as a guitarist has one: (sixteenth, how long, where over the root).
POWERS = (((0, 2, 0), (3, 1, 0), (4, 2, 0), (8, 2, 2), (10, 2, 3), (14, 2, 2), (16, 2, 0), (19, 1, 0), (20, 2, 0), (24, 2, -1), (26, 3, 0)),
          ((0, 3, 0), (4, 1, 0), (6, 2, -1), (8, 3, 0), (12, 2, 2), (14, 2, 0), (16, 3, 0), (20, 1, 0), (22, 2, 3), (24, 3, 2), (28, 2, -1)),
          ((0, 1, 0), (1, 1, 0), (2, 2, 0), (6, 2, 3), (8, 2, 2), (11, 1, 0), (12, 2, -1), (16, 1, 0), (17, 1, 0), (18, 2, 0), (22, 2, 1), (24, 4, 0)),
          ((0, 4, 0), (6, 2, 0), (8, 2, 2), (10, 2, 1), (12, 3, 0), (16, 4, 0), (22, 2, -2), (24, 2, -1), (26, 4, 0)),
          ((2, 2, 0), (4, 2, 0), (7, 1, 2), (8, 3, 3), (12, 2, 2), (14, 1, 0), (18, 2, 0), (20, 2, 0), (23, 1, -1), (24, 5, 0)),
          ((0, 2, 0), (2, 1, 7), (4, 2, 0), (6, 1, 6), (8, 2, 0), (10, 1, 4), (12, 3, 2), (16, 2, 0), (18, 1, 7), (20, 2, 0), (22, 1, 6), (24, 4, -1)),
          ((0, 3, 0), (3, 3, 0), (6, 2, 2), (10, 2, 2), (12, 4, 1), (16, 3, 0), (19, 3, 0), (22, 2, -1), (24, 4, -2)),
          ((0, 1, 0), (3, 1, 0), (6, 1, 0), (9, 1, 0), (12, 3, 2), (16, 1, 0), (19, 1, 0), (22, 1, 0), (25, 1, 0), (27, 3, -1)))
TOLLS = (((0, 3, 0), (10, 2, 1), (16, 3, 0), (26, 3, -1)), ((0, 6, 0), (12, 3, -1), (16, 6, 0)), ((0, 2, 0), (6, 8, 2), (22, 4, 1)), ((4, 3, 0), (12, 3, 0), (20, 3, 1), (24, 4, 0)),
         ((0, 8, 0), (14, 2, 7), (16, 8, 0), (27, 2, -1)), ((0, 2, 0), (3, 2, 0), (16, 2, 1), (19, 2, 0)))
ODDS = ("xx.", "x.x", "xx.x.", "x..x.", "xxx.x", "x.x.xx.", "xx.xx..", "x..xx.x")
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
    voice: int = 0                 # 1: said by the second synth in a drop (a riff that is called and answered)


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

    def __init__(self, changes: Changes, rng: random.Random, home: int = 67, riff: bool = False, hammer: bool = False, hook: str = ""):
        # (The middle of the tune at G4, not D5 as it was: 2026-11-17, morning, "your house needs some work". Against
        # the liked house stems the leads had nothing under 320 Hz and 6 to 19 dB too much from 900 Hz to 3.5 kHz, where
        # the liked leads have their weight at 200 to 450 Hz: a house hook sits in the warm middle, not over the band.)
        self.changes, self.rng = changes, rng
        # The step of the scale nearest `home` (a MIDI note) is the middle of the tune's range.
        self.centre = min(range(-7, 22), key=lambda degree: abs(changes.pitch(degree) - home))
        self.low, self.high = self.centre - 6, self.centre + 7
        # A riff (RIFFS) or a singing hook (HOOKS): the riff is a house lead's, every note on the chord.
        self.riff = riff
        if hammer and hook:
            self._phrased(hook)
            return
        if hammer:
            self._hammered()
            return
        hook = rng.choice(RIFFS if riff else HOOKS)
        other = rng.choice(FLOWS + LONGS)
        shape = rng.choice(("arch", "rising", "valley", "wave", "arch"))
        a = self._riff_cell(hook, 0) if riff and RIFF_CELLS else self._write(hook, 0, shape, 0, riff=riff)
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
        return [Tone(note.at + by, note.length, note.degree, note.loud, note.voice) for note in notes]

    def _chord(self, bar: int, at: float) -> tuple[int, str]:
        return self.changes.chord(bar + int(at // 16))

    @staticmethod
    def _strong(at: float, length: float) -> bool:
        return at % 8 == 0 or length >= 4

    def _write(self, rhythm: tuple[tuple[int, int], ...], bar: int, shape: str, lift: int, riff: bool = False) -> list[Tone]:
        """Two bars over the chords from `bar`: each note the one that best follows the shape,
        moves by step from the last, and sits on the chord where it is strong. In a riff every
        note is on the chord (the riff spells it out), a note may come again, and the first of
        each cell of three sixteenths is the one leaned on."""
        curve, out, before, leapt, same = SHAPES[shape], [], None, 0, 0
        for index, (at, length) in enumerate(rhythm):
            chord = self._chord(bar, at)
            strong = riff or self._strong(at, length) or index == len(rhythm) - 1
            want = self.centre + lift + curve(at / 32.0)
            best, least = None, 1e9
            for degree in range(self.low, self.high + 1):
                if strong and not self.changes.within(chord, degree):
                    continue
                cost = 0.9 * abs(degree - want) + self.rng.random() * 0.8
                if before is not None:
                    step = abs(degree - before)
                    again = (0.4 + 0.8 * same) if riff else (1.1 if strong else 2.0) + 3.0 * same
                    cost += 0.0 if step == 1 else 0.5 if step == 2 else 0.9 * (step - 1) if step else again
                    if leapt and (degree - before) * leapt >= 0:
                        cost += 1.5                      # after a leap, back the other way
                if cost < least:
                    best, least = degree, cost
            leapt = 0 if before is None or abs(best - before) < 3 else (1 if best > before else -1)
            same = same + 1 if best == before else 0
            if riff:
                out.append(Tone(at, length, best, 0.85 if at % 16 in (0, 3, 6, 9) or at % 16 == 8 else 0.68))
            else:
                out.append(Tone(at, length, best, 0.82 if strong else 0.64))
            before = best
        return out

    def _riff_cell(self, rhythm: tuple[tuple[int, int], ...], bar: int) -> list[Tone]:
        """A house riff (RIFF_CELLS): a cell of three or four notes of the chord, counted up from the chord's note nearest a
        little under the middle of the tune, in an order drawn for this tune (no note twice running, three of them at least,
        reaching a third of the chord or more above its lowest), said over the riff's rhythm again and again: up and back,
        a leap to the octave and down, a pedal against two that move, within about an octave. Over each chord the same cell on that chord's own
        notes, so the hook keeps its shape as the chords change. The cell's first note is the one leaned on."""
        rng = self.rng
        size = rng.choice((3, 4, 4))
        for _ in range(200):
            cell = [rng.randrange(4) for _ in range(size)]          # (within about an octave: five had leapt a tenth)
            if len(set(cell)) >= 3 and max(cell) - min(cell) >= 2 and all(a != b for a, b in zip(cell, cell[1:])) \
                    and cell[0] != cell[-1]:
                break
        out = []
        for index, (at, length) in enumerate(rhythm):
            chord = self._chord(bar, at)
            tones = [degree for degree in range(self.low - 3, self.high + 4) if self.changes.within(chord, degree)]
            base = min(range(len(tones)), key=lambda each: (abs(tones[each] - (self.centre - 2)), tones[each]))
            base = max(min(base, len(tones) - 1 - max(cell)), 0)       # the whole cell fits: no two of its notes made one
            degree = tones[min(base + cell[index % size], len(tones) - 1)]
            out.append(Tone(at, length, degree, 0.85 if index % size == 0 else 0.68))
        return out

    def _hammered(self) -> None:
        """A hard song's tune (HAMMERS): one note hammered for two bars and turned at their end, said again; another rhythm of it a third or a fourth up for two bars;
        the first again with its last half bar left out, for the breath. Its second eight bars put the octave where the first had the step."""
        rng = self.rng
        shapes = rng.sample(HAMMERS + HAMMERS_LATER if self.changes.family.name in LATER else HAMMERS, 3)
        moves = rng.choice(((1, -1, 7), (1, 7, 1), (-1, 2, 1), (7, 1, -1), (2, 1, -2), (-2, -1, 1)))       # where its few strokes go, by turns
        away = sorted(rng.sample(range(1, 8), 3))                                                         # and which of the phrase's strokes those are, of eight

        def said(bars: tuple[str, str], bar: int, up: int, moved: tuple[int, ...]) -> list[Tone]:
            strokes = [(16 * half + at, 1 + len(text[at + 1:]) - len(text[at + 1:].lstrip("-"))) for half, text in enumerate(bars) for at in range(16) if text[at] == "x"]
            count, out = len(strokes), []
            for index, (at, length) in enumerate(strokes):
                root = self._chord(bar, at)[0]
                root = self.centre + (root - 7 if root > 3 else root) - self.centre % 7 + up
                place = index * 8 // count
                turn = moved[away.index(place) % len(moved)] if place in away and (index == 0 or place != (index - 1) * 8 // count) else 0
                degree = min(max(root + turn, self.low - 3), self.high + 3)
                out.append(Tone(at, min(length, 4) if length > 1 else 1, degree, 0.95 if turn else 0.85 if at % 16 == 0 else 0.68))
            return out
        lift = rng.choice((2, 3))
        a, turned = said((shapes[0], shapes[0]), 0, 0, moves), said((shapes[0], shapes[1]), 2, 0, moves[::-1])
        b = said((shapes[2], shapes[2]), 4, lift, moves)
        a3 = [note for note in said((shapes[0], shapes[0]), 6, 0, moves) if note.at < 24]
        octave = tuple(7 if each == 1 else each for each in moves)
        self.idea = a
        self.first = a + self._moved(turned, 32) + self._moved(b, 64) + self._moved(a3, 96)
        self.second = (self._moved(said((shapes[0], shapes[0]), 8, 0, octave), 128) + self._moved(said((shapes[0], shapes[1]), 10, 0, octave[::-1]), 160)
                       + self._moved(said((shapes[2], shapes[1]), 12, lift, octave), 192) + self._moved([note for note in said((shapes[0], shapes[0]), 14, 0, octave) if note.at < 24], 224))
        self.notes = self.first + self.second

    def _step(self, bar: int, at: float, over: int) -> int:
        """A step over the root of the chord at a place in a phrase, near the middle of the tune."""
        root = self._chord(bar, at)[0]
        return min(max(self.centre + (root - 7 if root > 3 else root) - self.centre % 7 + over, self.low - 3), self.high + 3)

    @staticmethod
    def _tied(length: float) -> float:
        """How long a note is written to run on into the next, half a sixteenth past it, so that it slides (a lead of House's own slides between notes that are tied; `Take.lead` plays a note a little short)."""
        return (length + 0.5) / (0.96 if length + 0.5 < 4 else 0.9)

    def _phrased(self, hook: str) -> None:
        """A hard song's tune made another way than by the hammer (HOOKS_OF): two bars said, and said again with their end turned; the same up a third or a fourth, for two; the first again with its last half
        bar left out. The second eight bars say it changed. Each way of making one draws what it is made of once, so that the phrase is one phrase however often it comes."""
        rng = self.rng
        lift = rng.choice((2, 3))
        if hook == "line":
            while True:
                on = [True] + [rng.random() < 0.74 for _ in range(15)]
                if 10 <= sum(on) <= 13 and not any(not on[k] and not on[k + 1] and not on[k + 2] for k in range(14)):
                    break
            drawn = [0] + rng.choices((0, 7, 1, 2, -1, 4, -3), weights=(9, 4, 2, 2, 2, 1, 1), k=15)
            slid, struck = set(rng.sample([k for k in range(15) if on[k] and on[k + 1]], 4)), {0} | set(rng.sample(range(1, 16), 4))

            def turned(steps: list[int], where: tuple[int, ...]) -> list[int]:
                return [rng.choice([each for each in (0, 7, 1, 2, -1, 4) if each != step]) if k in where and k else step for k, step in enumerate(steps)]
            sounding = [k for k in range(1, 16) if on[k]]
            ends = turned(drawn, (12, 13, 14, 15))
            again = turned(drawn, tuple(rng.sample(sounding, 3)))
            high = [7 if step == 0 and k in rng.sample(sounding, 3) else step for k, step in enumerate(again)]

            def said(bars: tuple[list[int], list[int]], bar: int, up: int) -> list[Tone]:
                out = []
                for half, steps in enumerate(bars):
                    for k in range(16):
                        if on[k]:
                            at = 16 * half + k
                            degree, after = self._step(bar, at, steps[k] + up), self._step(bar, at, steps[(k + 1) % 16] + up)
                            out.append(Tone(at, self._tied(1) if k in slid and degree != after else 1, degree, 0.95 if k in struck else 0.68))
                return out
            plain, changed = (said((drawn, drawn), 0, 0), said((drawn, ends), 2, 0)), (said((again, again), 8, 0), said((again, high), 10, 0))
            middle, middle2 = said((drawn, ends), 4, lift), said((high, ends), 12, lift)
            last, last2 = said((drawn, drawn), 6, 0), said((again, again), 14, 0)
        elif hook == "odd":
            cells = rng.sample(ODDS, 2)
            moved = rng.choice(((0, 1), (0, 2), (0, -1), (7, 0), (2, 1)))

            def said(cell: str, bar: int, up: int, over: tuple[int, int]) -> list[Tone]:
                out = []
                for at in range(32):
                    k, turn = at % len(cell), at // len(cell)
                    if cell[k] == "x":
                        step = over[0] if k else 0
                        if turn % 4 == 3:
                            step = over[1] if k == 0 else step
                        out.append(Tone(at, 1, self._step(bar, at, step + up), 0.95 if k == 0 else 0.68))
                return out
            plain, changed = (said(cells[0], 0, 0, moved), said(cells[0], 2, 0, moved[::-1])), (said(cells[0], 8, 0, (moved[0], 7)), said(cells[0], 10, 0, (7, moved[1])))
            middle, middle2 = said(cells[1], 4, lift, moved), said(cells[1], 12, lift, (moved[0], 7))
            last, last2 = said(cells[0], 6, 0, moved), said(cells[0], 14, 0, (moved[0], 7))
        else:
            # Strokes written out: (sixteenth, how long, where over the root, whose).
            def written(kind: int, way: int) -> list[tuple[float, float, int, int]]:
                if hook == "glide":
                    rhythm, where = GLIDES[kind % len(GLIDES)], GLIDED[way % len(GLIDED)]
                    starts = {at for at, _ in rhythm}
                    return [(at, self._tied(length) if at + length in starts else length, where[k % len(where)], 0) for k, (at, length) in enumerate(rhythm)]
                if hook == "power":
                    return [(at, length, step, 0) for at, length, step in POWERS[kind % len(POWERS)]]
                if hook == "toll":
                    return [(at, length, step, 0) for at, length, step in TOLLS[kind % len(TOLLS)]]
                low, (text, where) = CALLS[kind % len(CALLS)], ANSWERS[way % len(ANSWERS)]
                strokes = lambda row: [(at, 1 + len(row[at + 1:]) - len(row[at + 1:].lstrip("-"))) for at in range(16) if row[at] == "x"]      # noqa: E731
                turns = (0, 0, 0, -1, 0, 2)
                return ([(at, length, turns[(k + way) % 6] if k else 0, 0) for k, (at, length) in enumerate(strokes(low))]
                        + [(16 + at, length, where[k % len(where)], 1) for k, (at, length) in enumerate(strokes(text))])
            kinds = {"glide": len(GLIDES), "power": len(POWERS), "toll": len(TOLLS), "call": len(CALLS)}[hook]
            one, two = rng.sample(range(kinds), 2)
            way, other = rng.sample(range({"glide": len(GLIDED), "call": len(ANSWERS)}.get(hook, 2)), 2)

            def said(kind: int, how: int, bar: int, up: int, turn: int = 0, end: int = 0) -> list[Tone]:
                strokes = written(kind, how)
                out = []
                for index, (at, length, step, voice) in enumerate(strokes):
                    if end and index == len(strokes) - 1:
                        step += end
                    if turn and voice == 0 and index and index % 3 == 2:
                        step += turn
                    out.append(Tone(at, length, self._step(bar, at, step + up), 0.9 if at % 4 == 0 else 0.74, voice))
                return out
            end, leap = rng.choice((1, -1, 2)), 7 if hook in ("call", "toll") else 0          # (a riff's and a glide's notes do not leap an octave here and there: they come back with another end)
            plain, changed = (said(one, way, 0, 0), said(one, other if hook == "call" else way, 2, 0, end=end)), (said(one, way, 8, 0, turn=leap, end=-end), said(one, other, 10, 0, end=end))
            middle, middle2 = said(two, other, 4, lift), said(two, way, 12, lift, end=end)
            last, last2 = said(one, way, 6, 0), said(one, way, 14, 0, turn=leap)
        breath = lambda notes: [Tone(note.at, min(note.length, 24 - note.at), note.degree, note.loud, note.voice) for note in notes if note.at < 24]      # noqa: E731
        self.idea = plain[0]
        self.first = plain[0] + self._moved(plain[1], 32) + self._moved(middle, 64) + self._moved(breath(last), 96)
        self.second = self._moved(changed[0], 128) + self._moved(changed[1], 160) + self._moved(middle2, 192) + self._moved(breath(last2), 224)
        self.notes = self.first + self.second

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
    # (2026-11-25, the later hard songs': cells of three over the four; a gallop.)
    "thirds": {"hat": ((0, 0.5), (3, 0.75), (6, 0.75), (9, 0.75), (12, 0.5), (14, 0.75)), "open": ((15, 0.35),)},
    "gallop": {"hat": ((0, 0.4), (2, 0.8), (3, 0.5), (4, 0.4), (6, 0.8), (7, 0.5), (8, 0.4), (10, 0.8), (11, 0.5), (12, 0.4), (14, 0.8), (15, 0.5))},
}
# What a hat figure turns into every second sixteen bars of a groove (2026-11-18, the boredom meter: Breakwater's drums
# sounded the same for 40 bars of its theme and 52 of its last drop; "still some boring sounds in house"; the house study:
# a layer enters or leaves, or a pattern varies, every 16 bars).
HAT_TURNS = {"eighths": "off", "off": "eighths", "sixteenths": "off", "shuffle": "sparse", "sparse": "off", "thirds": "off", "gallop": "sparse"}
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
# A hard song's toms, in the second half of its drops: two bars, the second an answer, under everything (2026-11-24, "house is a little better keep iterating": what was left of a festival
# in the hard songs was taken out one by one: the snare's roll into every drop, the note that climbs two octaves, the sweep's glare, the straightness).
HARD_TOMS = (((3, "tom_low", 0.8), (6, "tom_low", 0.5), (11, "tom_mid", 0.7), (14, "tom_low", 0.6)),
             ((2, "tom_low", 0.5), (3, "tom_low", 0.8), (6, "tom_mid", 0.6), (10, "tom_low", 0.6), (13, "tom_mid", 0.7), (14, "tom_low", 0.5)))
# How a hard song is arranged (2026-11-24, the five that were made read block by block: the stabs the same bar from the first to the last, the whole tune given away in the rise
# before its drop could bring it, the chords' roll and the bass's eighths opening into the drop as a festival's do, the groove whole from the theme's first bar, now and then a third
# over the riff). The layers of a drop, eight bars at a time: L the riff; C the riff's first two bars of every four and no more; U the second synth on it, an octave under; H the
# second synth an octave over; S the stabs; A the stabs in the two bars of four the riff leaves; s the stabs to their other figure; B the bass to its other figure; T the toms. With no
# riff in a block its hats are sparse: the floor. `rise`: "hammer", the riff's one note hammered and opening; "machine", the bass going on under a closed filter; "stab", one chord
# struck in threes. `stabs` and `bass`: how many bars of the first theme they wait.
HARD_SCENES: dict[str, dict] = {
    "stacked": dict(first=("L", "LS", "LSU"), last=("LS", "LSU", "sBT", "LS", "LSH", "LsHT"), rise="hammer", stabs=8, bass=0),
    "held": dict(first=("S", "LS", "LST"), last=("LS", "LST", "sB", "LB", "LSH", "LsHT"), rise="machine", stabs=16, bass=4),
    "answered": dict(first=("CA", "CAT", "LS"), last=("CA", "CAU", "sBT", "LS", "CAH", "LSHT"), rise="stab", stabs=0, bass=8),
    "lone": dict(first=("L", "LU", "LS"), last=("L", "LUT", "BT", "LSB", "LH", "LsHT"), rise="machine", stabs=24, bass=0),
}
# (The later families' drops have two shapes more: the riff kept back until the first drop's last eight bars; the second synth there before it.)
SCENES_LATER: dict[str, dict] = {
    "late": dict(first=("SB", "SBT", "L"), last=("L", "LS", "LSU", "BT", "LSH", "LsHT"), rise="hammer", stabs=8, bass=0),
    "shadow": dict(first=("U", "LU", "LUS"), last=("LS", "UT", "LU", "sB", "LSH", "LsHT"), rise="stab", stabs=16, bass=0),
}
WAITS = ("held", "late", "shadow")                # the shapes whose riff is not there from their first drop's first bar: no fight's and no storm's
THREES = ((0, 2.0), (3, 2.0), (6, 2.0), (9, 2.0), (12, 2.0), (14, 1.5))
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
# (2026-11-21, the study: Stone and Sky III, The Forge at Rest III and Ash Wind I's bass one colour 31 to 40 bars through a
# theme, its figure the same from the eighth bar to the rise.) In a walking or fighting piece's theme of 32 bars or more, the
# bass lifts at the theme's half, as a house bassline does on its way to the drop: its roots on the off-beats of two and
# four pop up an octave (`lifted`). The long and the dub figures stay as they are. Off until the judges have heard it.
THEME_BASS_TURNS = False
LIFT_STEPS = (6, 14)            # the sixteenths of the off-beats of two and four


def lifted(figure: tuple) -> tuple:
    """A bass figure lifted for the second half of a long theme: its roots on the off-beats of two and four an octave up;
    a figure that pops its octave there already puts its fifth on the third off-beat instead."""
    out = tuple((step, length, "O" if which == "R" and step in LIFT_STEPS else which) for step, length, which in figure)
    if out == tuple(figure):
        out = tuple((step, length, "F" if which == "R" and step == 10 else which) for step, length, which in figure)
    return out
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
        self.palette = grim(PALETTES[fam.palette]) if fam.name in GRIM else PALETTES[fam.palette]
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
        # Walking music, the moments and the fights have a riff for a hook two takes in three; the calm moments sing.
        low = bool(self.palette.get("low"))              # (a hard song's tune is always a riff, hammered, an octave under the others'; a calm one's is sung, as low)
        self.tune = Tune(self.changes, self.rng("tune"), home=55 if low else 67, riff=(low and fam.role not in CALM_ROLES) or (fam.role not in CALM_ROLES and self.pick("riff", (True, True, False))),
                         hammer=low and fam.role not in CALM_ROLES, hook=fam.hook)
        # A hard song's arrangement (HARD_SCENES); a fight's and a storm's riff is there from its drop's first bar.
        self.scene: dict | None = None
        if low and fam.role not in CALM_ROLES:
            scenes = {**HARD_SCENES, **SCENES_LATER} if fam.name in LATER else HARD_SCENES
            few = fam.hook in ("glide", "toll", "call")          # (a riff of few strokes has nothing to hammer a rise with)
            self.scene = scenes[self.pick("scene", tuple(each for each in scenes if (each not in WAITS or not (fam.hard or fam.role == "storm")) and not (few and scenes[each]["rise"] == "hammer")))]

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

    def layers(self, inside: int, count: int, first: int) -> str:
        """What plays in a bar of a hard song's drop (HARD_SCENES): a drop of fewer blocks than the scene has goes through it faster, and ends where it ends."""
        drops = [at for story, at, _ in self.sections if story == "moment"]
        wanted = self.scene["last" if len(drops) > 1 and first == drops[-1] else "first"]
        blocks = max((count + 7) // 8, 1)
        at = min(inside // 8, blocks - 1)
        return wanted[at if blocks == len(wanted) else round(at * (len(wanted) - 1) / max(blocks - 1, 1))]

    def blank(self) -> np.ndarray:
        return np.zeros((self.frames, 2), dtype=np.float32)

    def broken(self, story: str, first: int) -> bool:
        """Whether a section is the breakdown (see `__init__`)."""
        return story == "theme" and first == self.breakdown

    @staticmethod
    def build_bars(count: int) -> int:
        """How many of a rise's last bars build to the drop (the roll, the bass's eighths, the late chords): as many as the
        sweep has (RISE_PULSE), where they were half as many."""
        if (RISE_PULSE or RISE_CLOSED_HAT) and RISE_LONG_BUILD:
            return 8 if count >= 16 else 4
        return 4 if count >= 16 else 2

    def dropped_out(self, story: str, bar: int, count: int) -> bool:
        """Whether a bar of a section is a long drop's drop-out (DROP_OUT): the bar before the last eight of a drop of
        thirty-two bars or more, in anything but a calm piece."""
        return DROP_OUT and story == "moment" and count >= 32 and bar == count - 9 and self.family.role not in CALM_ROLES

    def kick_plays(self, story: str, bar: int, count: int, first: int = -1) -> bool:
        """Whether the kick is in at a bar of a section (beginning at bar `first`). The same for every take of a family."""
        if not self.kick or self.broken(story, first) or self.dropped_out(story, bar, count):
            return False
        if self.family.hard:
            return story != "rise" or bar < (count - self.build_bars(count) if RISE_KICK else count // 2)
        if story in ("theme", "moment"):
            return True
        if RISE_KICK and story == "rise" and self.family.role not in CALM_ROLES:
            return bar < count - self.build_bars(count)
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
                             else (("rim",), ("clap",)) if self.palette.get("grim") else (("snap",), ("rim",), ("clap",)))
        back_steps = (8,) if fam.groove in ("half", "none") else (4, 12)
        hat_figure = self.pick("hats", self.palette["hats"])
        hats = HATS[hat_figure]
        kinds = self.palette["perc"]
        first_perc = self.pick("perc", kinds)
        second_perc = kinds[(kinds.index(first_perc) + 1) % len(kinds)]
        clap_in = self.pick("clap-in", (0, 4, 8)) if not fam.hard else 0
        grows = FIGHT_DRUMS_GROW and fam.hard               # a fight's drums: the hats with the theme, the percussion after
        perc_in = self.pick("perc-in", (8, 4, 0)) if not fam.hard else 8 if grows else 0
        fill = self.pick("fill", ("snare", "toms", "lift"))
        roll = self.pick("roll", ("snare", "clap", "crack")) if fam.role not in CALM_ROLES else self.pick("roll", ("rim", "hat") if self.palette.get("grim") else ("maracas", "rim", "hat"))
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

        drops = 0                                     # drops already heard: a theme after one starts on the other figure
        for story, first, count in self.sections:
            build = self.build_bars(count)
            # (2026-11-19, the boredom meter: Ambush III's drums were the same 32 bars from its first drop through the theme
            # after it, each section counting its sixteen bars from its own start: a theme after a drop now begins where the
            # drop's figure turns, so the change lands at the drop's end.)
            shift = drops % 2 if story == "theme" else 0
            if story == "moment":
                drops += 1
            for inside in range(count):
                bar, energy = first + inside, self.energy(story, inside / count, first)
                groove = (story in ("theme", "moment") and not self.broken(story, first)) or (story == "close" and inside < count - 2) \
                    or (fam.hard and story == "open")
                last = inside == count - 1
                # Every second sixteen bars of a theme or a drop, the mids turn with the hats (THEME_MIDS, MIDS_WAY).
                turns = (THEME_MIDS or MIDS_WAY) and story in ("theme", "moment") and fam.role not in CALM_ROLES \
                    and (inside // 16 + shift) % 2 == 1
                # A long drop's drop-out (DROP_OUT): the clap and the hats alone, and a pickup on the snare into the slam.
                out_bar = self.dropped_out(story, inside, count)
                filling = (groove and inside % 8 == 7 and not (story == "close")) or out_bar
                this_fill = "snare" if out_bar else fill
                if self.kick_plays(story, inside, count, first):
                    for step in self.kick:
                        if filling and this_fill == "lift" and step >= 12:
                            continue
                        hit(dry, kick, bar, step, 0.92, 0.0, kick_speed)
                    if turns and MIDS_WAY == "ghost" and 14 not in self.kick:
                        hit(dry, kick, bar, 14, 0.55, 0.0, kick_speed)      # a ghost kick on the bar's last eighth
                if groove:
                    if story != "theme" or inside >= clap_in:
                        if not (story == "close" and inside >= count // 2):
                            # The backbeat turns with the hats, in the mids (THEME_MIDS; MIDS_WAY's snap or second clap).
                            sounds = backbeat
                            if turns and THEME_MIDS:
                                sounds = MIDS_TURN.get(backbeat, backbeat)
                            elif turns and MIDS_WAY in ("snap", "clap2") and MIDS_WAY not in backbeat:
                                sounds = backbeat + (MIDS_WAY,)
                            for step in back_steps:
                                for sound in sounds:
                                    hit(wet, sound, bar, step, 0.56 if sound != "snap" else 0.5)
                    # Every second sixteen bars the hats turn to another figure, and back (HAT_TURNS). As the close
                    # begins they thin to two strokes and an open hat: the first of the band to leave (2026-11-19, the
                    # boredom meter: Mirage I's and III's last drop ran on into the close in one groove for 20 bars).
                    turned = HAT_TURNS.get(hat_figure, hat_figure) if (inside // 16 + shift) % 2 == 1 else hat_figure
                    if story == "close":
                        turned = "sparse" if hat_figure != "sparse" else "off"
                    if self.scene and story == "moment" and not set("LC") & set(self.layers(inside, count, first)):
                        turned = "sparse"                        # the floor: the kick, the bass and the toms, and hardly a hat
                    for sound, steps in (HATS[turned] if not (grows and story == "open") else {}).items():
                        if sound == "open" and story == "theme" and inside < 8 and len(HATS[turned]) > 1:
                            continue
                        for step, loud in steps:
                            if filling and step >= 12 and this_fill != "lift":
                                continue
                            # (2026-11-18: "too much high hat and not enough dynamic sound". The sixteenths between the
                            # eighths come only at a drop; every hat is 3 dB softer there and follows the story further
                            # under it: a theme's first bars 3 dB under the drop's, were 1.5.)
                            if turned == "sixteenths" and sound == "hat" and step % 2 and story != "moment":
                                continue
                            hit(wet, sound, bar, step, 0.27 * loud * (0.3 + 0.7 * energy), 0.18 if sound == "hat" else -0.12)
                    # One bright layer at a time (the house study; the boredom meter: Breakwater's maracas ran their
                    # sixteenths under everything for the whole theme): outside a drop the two percussion figures take
                    # turns, sixteen bars each; at a drop both play.
                    odd = (inside // 16 + shift) % 2 == 1
                    block = inside // 16
                    if story == "moment":
                        # A drop builds block by block: the first figure, then both, then the second alone.
                        first_on, second_on = block % 3 != 2, block % 3 != 0
                    elif story == "theme" and THEME_STAGGERS and fam.role not in CALM_ROLES:
                        # The percussion turns eight bars after the hats (THEME_STAGGERS).
                        later = (max(inside - 8, 0) // 16 + shift) % 2 == 1
                        first_on, second_on = inside >= perc_in and not later, inside >= perc_in and later
                    else:
                        begins = 0 if grows and story == "close" else perc_in
                        first_on, second_on = inside >= begins and not (odd and story == "theme"), story == "theme" and odd
                    floor = self.scene and story == "moment" and not set("LC") & set(self.layers(inside, count, first))
                    if LONG_DROP_GROWS and story == "moment" and count >= 32 and inside >= 16 and not out_bar and "ride" not in kinds \
                            and fam.role not in CALM_ROLES and not floor:
                        # A long drop from its second block: the ride on the beat (LONG_DROP_GROWS). (Not on a hard song's floor: it rang straight through it, and the meter heard the drums the same 23 bars.)
                        for step in (0, 4, 8, 12):
                            hit(wet, "ride", bar, step, 0.2 if step % 8 == 0 else 0.16, 0.3)
                    if first_on and not out_bar:
                        figure(first_perc, bar, 0.34 * (0.6 + 0.4 * energy), -0.35)
                    if second_on and not out_bar:
                        figure(second_perc, bar, 0.32 * (0.6 + 0.4 * energy), 0.4)
                    if self.scene and not out_bar and not filling and ((story == "moment" and "T" in self.layers(inside, count, first))
                                                                       or (story == "theme" and ((inside // 8) % 4 == 3 or (count >= 40 and inside >= count - 8)))):
                        # (A theme's fourth eight bars, and a long one's last, have them too: 2026-11-24, the first nineteen read: in twelve the second half of a theme was one groove of sixteen bars.)
                        for step, sound, loud in HARD_TOMS[inside % 2]:
                            hit(wet, sound, bar, step, (0.42 if story == "moment" else 0.34) * loud, {"tom_mid": -0.25, "tom_low": 0.2}[sound])
                    if filling:
                        if this_fill == "snare":
                            for index, step in enumerate((12, 13, 14, 15)):
                                hit(wet, "snare", bar, step, 0.3 + 0.1 * index)
                        elif this_fill == "toms":
                            for step, sound, pan in ((10, "tom_high", -0.4), (12, "tom_mid", 0.0), (14, "tom_low", 0.4)):
                                hit(wet, sound, bar, step, 0.5, pan)
                        else:
                            hit(wet, "open", bar, 14, 0.4, -0.12)
                elif story == "rise" and RISE_PULSE:
                    # The groove's top goes on through a rise (RISE_PULSE): the family's hats (sixteenths thinned to
                    # eighths, as everywhere but a drop) growing with the rise, and the first percussion figure until the
                    # build. Both hold their breath with the roll.
                    breath = pause and last
                    for sound, steps in HATS[hat_figure].items():
                        for step, loud in steps:
                            if (hat_figure == "sixteenths" and sound == "hat" and step % 2) or (breath and step >= 12):
                                continue
                            hit(wet, sound, bar, step, 0.27 * loud * (0.3 + 0.7 * energy), 0.18 if sound == "hat" else -0.12)
                    if inside < count - build:
                        figure(first_perc, bar, 0.34 * (0.6 + 0.4 * energy), -0.35)
                elif story == "rise" and RISE_CLOSED_HAT and fam.role not in CALM_ROLES:
                    # The quieter pulse (RISE_CLOSED_HAT): the closed hat alone on the eighths, the off-beat a little over
                    # the beat, soft at first and growing with the rise; it holds its breath with the roll. Not in a calm
                    # rise (2026-11-20, House's calm takes made again with it: an inn's or a camp's rise came up to its
                    # moment, Embers under Stars I level with it, Cool of the Evening II over it: the render's own check):
                    # an inn's rise stays the tune over a shaker stirring, as it was.
                    for step in range(0, 16, 2):
                        if pause and last and step >= 12:
                            continue
                        hit(wet, "hat", bar, step, 0.2 * (0.25 + 0.75 * energy) * (1.0 if step % 4 == 2 else 0.7), 0.18)
                elif story == "open" and sneak and inside >= count // 2:
                    # Before the groove: a shaker or the hats, far off, coming closer.
                    near = (inside - count // 2) / max(count - count // 2, 1)
                    for step, sound, loud in PERCUSSION[first_perc if first_perc in ("maracas", "cabasa", "tambourine", "rim", "snap")
                                                        else "rim" if self.palette.get("low") or self.palette.get("grim") else "maracas"]:
                        hit(wet, sound, bar, step, 0.12 + 0.16 * near * loud, -0.3)
                elif story == "close" and inside >= count - 2 and self.kick:
                    hit(wet, "hat", bar, 2, 0.12, 0.18)
                    hit(wet, "hat", bar, 10, 0.1, 0.18)
                if story == "rise" and self.palette.get("low") and fam.role not in CALM_ROLES:
                    # A hard song's rise has no roll: the floor tom on the beat, coming nearer, and half a bar of nothing before the drop.
                    for step in (0, 4, 8, 12):
                        if not (last and step >= 8):
                            hit(wet, "tom_low", bar, step, 0.16 + 0.34 * inside / max(count - 1, 1), 0.0, 0.94)
                elif story == "rise" and inside >= count - build:
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
                    hit(wet, "crash", bar, 0, 0.5 if self.dropped_out(story, inside - 1, count) else 0.34, 0.25)
                if fam.hard and story == "open" and inside == 0:
                    hit(wet, "crash", bar, 0, 0.5, -0.2)
                if fam.hard and story == "open" and last:
                    for step in range(8, 16):
                        hit(wet, "snare", bar, step, 0.25 + 0.05 * (step - 8), 0.0, 1.0 + 0.02 * (step - 8))
        return (dry + synth.hall(wet, seconds=0.9, wet=0.1, bright=10000.0)).astype(np.float32)

    # --- bass --------------------------------------------------------------------------------
    def bass_note(self, chord: tuple[int, str], which: str, after: tuple[int, str] | None = None) -> int:
        """A note of a chord for the bass, low: its root, fifth, octave, or a step up to the next root."""
        floor = 28 if self.palette.get("low") else 31            # (a hard song's roots from E1: an F sharp's root stood at 92 Hz, over where a kick's weight is)

        def low(pitch: int) -> int:
            while pitch < floor:
                pitch += 12
            while pitch >= floor + 12:
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
        scene = self.scene
        other = BASSES[next((each for each in self.palette["bass_style"] if each != style), style)]
        one = next((at for story, at, _ in self.sections if story == "theme"), None)           # where the first theme begins
        for story, first, count in self.sections:
            build = self.build_bars(count)
            for inside in range(count):
                bar, energy = first + inside, self.energy(story, inside / count, first)
                chord, after = self.changes.chord(inside), self.changes.chord(inside + 1)
                bright = 0.4 + 0.6 * energy
                if self.dropped_out(story, inside, count):
                    continue                                   # the drop-out: the bass out for the bar
                if scene and story == "theme" and first == one and inside < scene["bass"] and not fam.hard:
                    continue                                   # a hard song's kick and hats alone first
                if scene and story == "rise":
                    # A hard song's rise: the bass going on under a closed filter that opens, or one long note to a bar, far down; nothing in its last half bar.
                    along, ends = inside / count, inside == count - 1
                    if scene["rise"] == "machine":
                        for step, length, which in figure:
                            if not (ends and step >= 8):
                                synth.play(out, sound, self.at(bar, step), length * STEP * 0.92, self.bass_note(chord, "R" if which == "O" else which, after),
                                           loud * (0.24 + 0.2 * along) * (0.85 + rng.random() * 0.15), seed=self.seed + bar * 16 + int(step), bright=0.15 + 0.7 * along ** 1.5)
                    else:
                        held = sound if not isinstance(sound, Patch) or sound.sustain > 0.5 else BASS["sub"]
                        synth.play(out, held, self.at(bar, 0), (7 if ends else 15) * STEP, self.bass_note(chord, "R"), trim(held, 40) * 0.16 * (0.5 + energy),
                                   seed=self.seed + bar, bright=0.35)
                    continue
                if (story in ("theme", "moment") and not self.broken(story, first)) or (fam.hard and story in ("open", "close")) \
                        or (story == "close" and self.kick_plays(story, inside, count, first)):
                    notes = figure
                    if (scene and story == "moment" and "B" in self.layers(inside, count, first)) or (self.palette.get("low") and not scene and inside >= count // 2):
                        notes = other                          # (HARD_SCENES; and an after-hours song's bass turns at the half of a theme and of a moment: Dead Hours' was one colour for 52 bars)
                    elif story == "theme" and inside < 4 and style in ("rolling", "synco", "tresillo"):
                        notes = BASSES["offbeat"]              # it starts plainly and fills in
                    elif (THEME_BASS_TURNS and story == "theme" and count >= 32 and inside >= count // 2 and style not in ("long", "dub")
                          and fam.role not in CALM_ROLES):
                        notes = lifted(figure)                 # a long theme's second half: the bass lifts
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
                    calm = 0.5 if CALM_BUILD_SOFT and fam.role in CALM_ROLES else 1.0       # an inn has no drop to roll into
                    for step in range(0, 16, 2):
                        synth.play(out, sound, self.at(bar, step), 1.5 * STEP, self.bass_note(self.changes.chord(count - 1), "R"),
                                   loud * (0.25 + 0.3 * along) * calm, seed=self.seed + bar * 16 + step, bright=0.25 + 0.7 * along)
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
        scene = self.scene
        second = self.rng("stabs-second").choice([each for each in STABS if each is not stabs])
        turned = self.rng("arp-second").choice([each for each in ARPS if each != arp])
        one = next((at for story, at, _ in self.sections if story == "theme"), None)           # where the first theme begins
        voiced: list[int] | None = None
        spread, low = self.palette["voicing"], bool(self.palette.get("low"))      # (a hard song's chords are an octave under the others')
        for story, first, count in self.sections:
            build = self.build_bars(count)
            for inside in range(count):
                bar, energy = first + inside, self.energy(story, inside / count, first)
                chord = self.changes.chord(inside)
                voiced = self.changes.voicing(chord, 43 if low else 55, 64 if low else 76, voiced, spread)
                notes = list(voiced)
                if story == "moment" and not low:
                    notes = notes + [notes[-1] + 12 if notes[-1] + 12 <= 84 else notes[0] + 12]       # fuller at the drop
                # (2026-11-18: a theme half an octave to an octave darker than the drop, opening across it, as the records
                # studied do: "the theme is darker than the drop".)
                bright = {"open": 0.12 + 0.33 * inside / count, "theme": 0.5 + 0.2 * inside / count, "rise": 0.4 + 0.6 * (inside / count) ** 2,
                          "moment": 1.0, "close": 0.85 - 0.6 * inside / count}[story]
                if story == "moment" and inside % 16 == 15 and count - inside > 1:
                    bright = 0.8           # the filter breathes: half an octave down on a block's last bar, open on the next
                if self.broken(story, first):
                    # (2026-11-18: the breakdown was as bright as a theme.) Dark, and opening only a little across it.
                    bright = 0.22 + 0.18 * inside / count
                level = 0.2 * (0.35 + 0.65 * energy) * trim(sound, 64)
                if story == "open" and inside < (count // 4 if not fam.hard else 0):
                    continue
                if story == "rise" and not through_rise and inside < count - build:
                    continue
                if self.dropped_out(story, inside, count):
                    continue                                   # the drop-out: the last chord rings on in the echo and the hall
                struck, way = stabs, arp
                if self.palette.get("low") and not scene and story in ("theme", "moment") and inside >= count // 2:
                    struck, way = second, turned               # (an after-hours song's chords turn at the half: the same 22 bars in Dead Hours)
                if scene:
                    # A hard song's stabs come and go (HARD_SCENES): they wait in the first theme, leave the rise unless it is theirs, and have a second figure, the breakdown's too.
                    now = self.layers(inside, count, first) if story == "moment" else ""
                    if (story == "theme" and first == one and inside < scene["stabs"]) or (story == "rise" and scene["rise"] != "stab") \
                            or (story == "moment" and (not set("SsA") & set(now) or ("A" in now and inside % 4 < 2))):
                        continue
                    if "s" in now or self.broken(story, first):
                        struck = second
                    elif story == "rise":
                        struck = tuple(each for each in THREES if inside < count - 1 or each[0] < 8)
                thin = (story == "open" and inside < count // 2) or (story == "close" and inside >= count // 2)
                # The chords' roll into the drop: in the last two bars of a rise, eighths and then sixteenths. A calm piece
                # has no roll into its moment (2026-11-18, Cold Stars I, a night piece: a bell's sixteenths had rung into
                # each other 6 dB over its own drop).
                building = story == "rise" and inside >= count - 2 and fam.role not in CALM_ROLES and not scene
                if style == "dub" and not (scene and story == "rise"):
                    # One chord thrown into the echo, and left to ring.
                    if inside % 2 == 0 or story == "moment":
                        for index, pitch in enumerate(notes):
                            synth.play(out, sound, self.at(bar, 3 if inside % 4 else 6), 1.4 * STEP, pitch, level * 1.3,
                                       pan=(index - 1.5) * 0.25, seed=self.seed + bar + index, bright=bright)
                elif style in ("stabs", "strum") or (building and style != "arp") or (scene and story == "rise"):
                    places = tuple((step, 0.9) for step in range(0, 16, 1 if inside == count - 1 else 2)) if building else struck
                    for number, (step, length) in enumerate(places):
                        if thin and number % 2:
                            continue
                        order = notes if number % 2 == 0 else notes[::-1]
                        for index, pitch in enumerate(order):
                            late = index * 0.014 if style == "strum" else 0.0
                            hard = level * (1.0 if step % 4 == 0 or len(places) < 5 else 0.82) * (0.9 + 0.1 * rng.random())
                            if building:
                                # The roll climbs to the drop and no higher: each stroke softer as they come faster (eighths,
                                # then sixteenths ringing into each other), swelling across the bar.
                                hard *= (0.62 if inside == count - 1 else 0.8) * (0.75 + 0.25 * step / 15.0)
                            synth.play(out, sound, self.at(bar, step) + late, length * STEP * 0.9, pitch, hard,
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
                        if way == "up":
                            pitch = pool[turn % len(pool)]
                        elif way == "down":
                            pitch = pool[-1 - turn % len(pool)]
                        elif way == "updown":
                            wave = turn % (2 * len(pool) - 2) if len(pool) > 1 else 0
                            pitch = pool[wave if wave < len(pool) else 2 * len(pool) - 2 - wave]
                        elif way == "pedal":
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
        gentle = names[(names.index(chosen) + 1) % len(names)]
        main = LEADS[chosen]
        soft = LEADS[gentle]      # the same tune in a gentler voice, for the quiet places
        if LEAD_WEIGHT.get(gentle, 1) > LEAD_WEIGHT.get(chosen, 1):
            # The bigger voice at the drops (2026-11-19: Hammerfall III's drops had the hollow square and its themes the
            # seven-saw super; the lead was 12 dB louder outside the drop than in it).
            main, soft = soft, main
        doubled = self.pick("lead-double", ("octave", "third", "octave")) if fam.role not in CALM_ROLES else ""
        tune = self.tune
        late = None
        if tune.riff:
            # A riff is a pluck's through the echo where it is quiet and the big saw's at the drops, and in the second half
            # of a drop a second synth joins it an octave up, the drop's new thing (the house study: a harsher twin
            # crossfaded in late in a drop, something never heard before in the last drop's second half).
            big = self.pick("riff-lead", ("saw", "super", "saw"))
            main, soft = LEADS[big], LEADS[self.pick("riff-soft", ("pluck", "glass", "pluck"))]
            late = LEADS["super" if big == "saw" else "saw"]

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
            return [Tone(note.at - first, note.length, note.degree, note.loud, note.voice) for note in notes if first <= note.at < last]

        for story, first, count in self.sections:
            if story == "open":
                # The end of the idea, far away, once or twice.
                ending = cut(tune.idea, 16, 32)
                for inside in range(count // 2 + 2, count, 4):
                    say(ending[-3:] if len(ending) >= 3 else ending, first + inside - 1, soft, 0.22, 0.3)
            elif story == "theme":
                # The hook, stated and left; then answered.
                half = count // 2 if not fam.hard else 0
                if THEME_SINGS and not fam.hard and fam.role not in CALM_ROLES and not self.scene:
                    # The first half sings too, softly under the groove: the tune's opening phrases in their order, one
                    # every four bars from the fifth, so that the theme is a tune and not a groove waiting for one.
                    for index, inside in enumerate(range(4, half - 1, 4)):
                        say(cut(tune.notes, 32 * (index % 4), 32 * (index % 4) + 32), first + inside, soft, 0.34, 0.5)
                for index, inside in enumerate(range(half, count - 1, 4)):
                    hook = cut(tune.notes, 32 * (index % 2), 32 * (index % 2) + 32) if index < 2 else cut(tune.notes, 96, 128)
                    if THEME_MAIN and self.scene and fam.name in LATER and not fam.hard:
                        along = (inside - half) / max(count - half, 1)
                        say([note for note in hook if not note.voice], first + inside, main, 0.4 + 0.12 * along, 0.34 + 0.22 * along)
                        say([note for note in hook if note.voice], first + inside, soft, 0.4 + 0.12 * along, 0.4 + 0.22 * along)
                        continue
                    say(hook, first + inside, soft if not fam.hard else main, 0.42, 0.6)
            elif story == "rise" and self.scene:
                # A hard song's does not give its riff away: its one note hammered, opening up, or nothing of it (HARD_SCENES).
                if self.scene["rise"] == "hammer":
                    struck = [note.degree for note in tune.idea]
                    most = max(sorted(set(struck)), key=struck.count)
                    for inside in range(0, count, 2):
                        say([Tone(note.at, note.length, most, note.loud) for note in tune.idea if inside + 2 < count or note.at < 24], first + inside, main,
                            0.3 + 0.25 * inside / count, 0.15 + 0.75 * inside / count)
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
                    # (2026-11-18, the boredom meter: the lead's colour held 23 bars at the end of a 48-bar drop.) In the last
                    # sixteen bars of a long drop the tune answers itself: the main voice and the second synth alone take
                    # turns, phrase by phrase.
                    answering = late is not None and count >= 32 and inside >= count - 16 and (inside // 8) % 2 == 1
                    if self.dropped_out(story, inside + 7, count):
                        # The phrase's last bar is the drop-out: what is begun before it ends as it begins.
                        notes = [Tone(note.at, min(note.length, 112 - note.at), note.degree, note.loud, note.voice) for note in notes if note.at < 112]
                    if self.scene:
                        # A hard song's, by its layers (HARD_SCENES): the second synth, never the riff's own, says it an octave under or over.
                        now = self.layers(inside, count, first)
                        if "C" in now:
                            notes = [note for note in notes if note.at % 64 < 32]
                        called = [note for note in notes if not note.voice]
                        if set("LC") & set(now):
                            say(called, first + inside, main, 0.62, 1.0)
                            if late is not None:
                                say([note for note in notes if note.voice], first + inside, late, 0.55, 1.0)          # (the answer is the second synth's)
                        if late is not None and set("UH") & set(now):
                            say(called, first + inside, late, 0.3, 0.95, shift=-7 if "U" in now else 7)
                        continue
                    if not answering:
                        say(notes, first + inside, main, 0.62, 1.0)
                    if late is not None and inside >= count // 2:
                        say(notes, first + inside, late, 0.42 if answering else 0.24, 1.0, shift=7)
                    elif doubled and (inside // 8) % 2 == 1:
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
                # (A hard song's air is darker, and nothing in it climbs.)
                out.append(Air("sweep", end - build, build, 1.1 * gentle, 250.0, 3600.0 if self.palette.get("low") else 9000.0, True, seed=self.seed + 1))
                if tonal and not self.palette.get("low"):
                    out.append(Air("climb", end - build, build, 0.16 * gentle, 600.0, 5600.0, True, pitch=self.changes.pitch(0, 4)))
            if story == "moment":
                out.append(Air("thud", start, 2.5, 0.5 * gentle))
                out.append(Air("sweep", start, 2 * BAR, 0.7 * gentle, 400.0, 9000.0, False, seed=self.seed + 2))
                gap = next((inside for inside in range(count) if self.dropped_out(story, inside, count)), None)
                if gap is not None:
                    # The drop-out's bar of air rising into the slam, and the drop's thud again as it lands.
                    out.append(Air("sweep", self.at(first + gap, 0), BAR, 0.8, 300.0, 8000.0, True, seed=self.seed + 5 + first))
                    out.append(Air("thud", self.at(first + gap + 1, 0), 2.5, 0.5))
            if story in ("theme", "close") and not fam.hard:
                out.append(Air("sweep", start, BAR, 0.35, 500.0, 6000.0, False, seed=self.seed + 3 + first))
                out.append(Air("sweep", start - 2 * BAR, 2 * BAR, 0.3, 300.0, 5000.0, True, seed=self.seed + 4 + first))
            if self.palette["atmos"] and (story in ("open", "close") or (story == "rise" and count >= 16) or fam.role == "storm"):
                seconds = count * BAR if story != "rise" else count * BAR / 2
                # A storm's rain falls all the way through, under the band where it is full (2026-11-18, Thunderhead I: over a
                # bright pad its rain at 0.4 in every section stood over the music, the texture centred at 4.8 kHz against
                # the liked 422 Hz; Rain on the Roofs, heard and liked, had it under a warm pad).
                level = 0.3 if fam.role != "storm" else (0.4 if story in ("open", "rise", "close") else 0.25)
                out.append(Air(self.palette["atmos"], start, seconds + 2.0, level, fade=1.5, seed=self.seed + 9 + first))
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
