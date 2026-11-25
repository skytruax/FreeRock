"""House's own instruments, designed here as Surge XT patches (2026-11-21: "why does my house sound like generic shit", "i
think mainly your instruments suck for house", "and design yourself").

House had played Surge's factory patches as they come, and every guide to the genre names that first among what makes a
track sound generic. Each patch here is drawn on Surge's empty saw (its "Init Saw" template) with the settings a
progressive house producer reaches for, and the reasons beside them; Surge's own effects stay off, and the effects are
the desk's, where every setting can be read (club.py, by the part's role).

Surge keeps a patch as XML, every parameter in its own units: an envelope's times are log2 seconds (-8 is 4 ms, 0 is one
second), a filter's cutoff is semitones from A440, an LFO's rate log2 Hz. A modulation is a `modrouting` child of the
parameter it moves, its depth in that parameter's units, from a source numbered as Surge numbers them (`SOURCES`).

    desk.surge("own/house pluck")      the patch's state, for a REAPER track (see `state`)
"""
from __future__ import annotations

import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

BASE = "patches_factory/Templates/Init Saw.fxp"

# Surge XT 1.3's numbers (src/common/SurgeStorage.h, ModulationSource.h; sst-filters' FilterConfiguration.h).
CLASSIC = 0                                         # the classic oscillator: a saw, or a pulse (see `osc`)
SINE, FM3, FM2, MODERN = 1, 5, 6, 8                 # the sine, the two FM oscillators (each a sine modulated by sines), the modern
WAVETABLE, WINDOW, TWIST, ALIAS = 2, 7, 10, 11      # a table of waves gone through (`table`), a wave under a window (`window`), a machine of many models (`twist`), an eight-bit machine's wave
# The classic oscillator's Shape: 0 a saw; -1 a pulse as wide as its Width 1, a square at 0.5 (Surge's own "Init Square"
# template). Its +1 is a double saw, at the default widths a saw an octave over the note, and no design uses it.
# (2026-11-21, afternoon: the first two sets of designs had read -1 as a triangle and +1 as a square. Played alone and
# their harmonics read, -1 at 0.5 had only the odd harmonics, a square's, and +1 only the even ones: their "squares" had
# been saws an octave up, and their "triangles" squares. A triangle is the modern oscillator's: `triangle`.)
SAW, PULSE = 0.0, -1.0
LP12, LP24, LADDER, HP12, BP12, OBXD4 = 1, 2, 3, 4, 6, 12    # filters; the legacy ladder's subtype 3 is 24 dB
WS_SOFT, WS_HARD = 1, 2                             # the waveshaper's soft saturation and its hard clip (after the first filter); its drive in dB
NOTCH12, K35 = 7, 13                                # a notch; the filter of a Korg 35, which breaks up as it resonates
WS_FOLD = 17                                        # ...and the west coast's: a wave folded back on itself, further the harder it is driven
SOURCES = {"velocity": 1, "keytrack": 2, "amp env": 15, "filter env": 16, "lfo1": 17, "lfo2": 18, "scene lfo1": 23,
           "scene lfo2": 24, "random": 31}
# An oscillator of another kind keeps its seven settings in other units, some of them whole numbers where the saw's are
# fractions, and starts from other values (the saw's unison of one voice would be the FM2's feedback turned all the way
# up). It takes all seven, kinds and values, from a patch that has it as its first oscillator, and the design's on top:
# Surge's empty sine and empty FM2, and for the FM3, which has no empty patch, the factory's "FM Bass 5" (whose values
# the design replaces, every one: see `fm3`).
KINDS = {SINE: "patches_factory/Templates/Init Sine.fxp", FM2: "patches_factory/Templates/Init FM2.fxp",
         FM3: "patches_factory/Basses/FM Bass 5.fxp", MODERN: "patches_factory/Templates/Init Modern.fxp",
         ALIAS: "patches_3rdparty/Altenberg/Basses/Rampage.fxp", WAVETABLE: "patches_factory/Templates/Init Wavetable.fxp",
         WINDOW: "patches_3rdparty/Jacky Ligon/Templates/Window.fxp", TWIST: "patches_3rdparty/Jacky Ligon/Templates/Twist.fxp"}


def seconds(value: float) -> float:
    return math.log2(value)


def hz(value: float) -> float:
    """A cutoff in Surge's units: semitones from A440."""
    return 12.0 * math.log2(value / 440.0)


def rate(value: float) -> float:
    return math.log2(value)


def osc(n: int, *, shape: float = SAW, octave: int = 0, pitch: float = 0.0, voices: int = 1, detune: float = 0.1,
        level: float = 1.0, width: float = 0.5) -> dict:
    """The classic oscillator: a saw (`SAW`) or a pulse `width` wide (`PULSE`, a square at 0.5). With more than one voice
    the outermost are `detune` semitones either side of the note and the rest between."""
    if shape not in (SAW, PULSE):
        raise ValueError("the classic oscillator is drawn as a saw or a pulse here, not Shape %r" % shape)
    p = "a_osc%d_" % n
    return {p + "type": CLASSIC, p + "octave": octave, p + "pitch": pitch, p + "param0": shape, p + "param1": width,
            p + "param5": detune, p + "param6": voices, "a_level_o%d" % n: level, "a_mute_o%d" % n: 0}


def triangle(n: int, *, octave: int = 0, pitch: float = 0.0, voices: int = 1, detune: float = 0.1, level: float = 1.0) -> dict:
    """A triangle: the modern oscillator with its saw and pulse out and its third wave (a triangle) all the way in."""
    p = "a_osc%d_" % n
    return {p + "type": MODERN, p + "octave": octave, p + "pitch": pitch, p + "param0": 0.0, p + "param1": 0.0, p + "param2": 1.0,
            p + "param3": 0.5, p + "param4": 0.0, p + "param5": detune, p + "param6": voices, "a_level_o%d" % n: level,
            "a_mute_o%d" % n: 0}


def sine(n: int, *, feedback: float = 0.0, octave: int = 0, pitch: float = 0.0, level: float = 1.0) -> dict:
    """The sine oscillator (its shape 0, the pure sine); feedback leans it toward a saw."""
    p = "a_osc%d_" % n
    return {p + "type": SINE, p + "octave": octave, p + "pitch": pitch, p + "param0": 0, p + "param1": feedback,
            p + "retrigger": 1, "a_level_o%d" % n: level, "a_mute_o%d" % n: 0}


def fm2(n: int, *, m1: float, r1: int = 1, m2: float = 0.0, r2: int = 1, feedback: float = 0.0, octave: int = 0,
        pitch: float = 0.0, level: float = 1.0) -> dict:
    """The FM2 oscillator: a sine modulated by two sines at whole-number ratios of its note. An amount `m` is a
    modulation index of 32 pi m cubed (0.2 is 0.8, 0.3 is 2.7, 0.4 is 6.4): the higher, the more harmonics. Its phase
    starts again with every note, so every note has the same attack."""
    p = "a_osc%d_" % n
    return {p + "type": FM2, p + "octave": octave, p + "pitch": pitch, p + "param0": m1, p + "param1": r1, p + "param2": m2,
            p + "param3": r2, p + "param4": 0.0, p + "param5": 0.0, p + "param6": feedback, p + "retrigger": 1,
            "a_level_o%d" % n: level, "a_mute_o%d" % n: 0}


def fm3(n: int, *, m1: float, r1: float = 1.0, m2: float = 0.0, r2: float = 1.0, feedback: float = 0.0, octave: int = 0,
        pitch: float = 0.0, level: float = 1.0) -> dict:
    """The FM3 oscillator: as the FM2, its ratios any number (3.5 is a bell's), its third modulator left off."""
    p = "a_osc%d_" % n
    return {p + "type": FM3, p + "octave": octave, p + "pitch": pitch, p + "param0": m1, p + "param1": r1, p + "param2": m2,
            p + "param3": r2, p + "param4": 0.0, p + "param5": 0.0, p + "param6": feedback, p + "retrigger": 1,
            "a_level_o%d" % n: level, "a_mute_o%d" % n: 0}


def alias(n: int, *, shape: int = 1, wrap: float = 0.0, mask: float = 0.0, threshold: float = 0.5, bits: float = 8.0, voices: int = 1, detune: float = 0.1,
          octave: int = 0, pitch: float = 0.0, level: float = 1.0) -> dict:
    """The alias oscillator: a sine (shape 0), a ramp (1) or a pulse (2) as an eight-bit machine draws it, wrapped over itself, its bits turned over by a mask past `threshold`, and crushed to `bits`."""
    p = "a_osc%d_" % n
    return {p + "type": ALIAS, p + "octave": octave, p + "pitch": pitch, p + "param0": shape, p + "param1": wrap, p + "param2": mask, p + "param3": threshold,
            p + "param4": bits, p + "param5": detune, p + "param6": voices, p + "retrigger": 1, "a_level_o%d" % n: level, "a_mute_o%d" % n: 0}


def table(n: int, file: str, *, at: float = 0.0, saturate: float = 0.0, formant: float = 0.0, bend: float = 0.0, voices: int = 1, detune: float = 0.1,
          octave: int = 0, pitch: float = 0.0, level: float = 1.0) -> dict:
    """The wavetable oscillator: one of Surge's tables (a path under its folders), the place in it where it stands (0 its first wave, 1 its last), each wave
    one turn of the note, so whatever is in it is in tune."""
    p = "a_osc%d_" % n
    return {p + "type": WAVETABLE, p + "octave": octave, p + "pitch": pitch, p + "param0": at, p + "param1": 0.0, p + "param2": saturate, p + "param3": formant,
            p + "param4": bend, p + "param5": detune, p + "param6": voices, p + "retrigger": 1, "a_level_o%d" % n: level, "a_mute_o%d" % n: 0, "table %d" % n: file}


def env(which: int, attack: float, decay: float, sustain: float, release: float) -> dict:
    p = "a_env%d_" % which
    return {p + "attack": seconds(attack), p + "decay": seconds(decay), p + "sustain": sustain, p + "release": seconds(release)}


# A lead's slow vibrato, which waits, and its one voice that slides only between notes that are tied (Surge's fingered portamento).
VIBRATO = {"a_lfo0_shape": 0, "a_lfo0_rate": rate(5.2), "a_lfo0_delay": seconds(0.4), "a_lfo0_attack": seconds(0.5)}
MONO = {"a_polymode": 3, "a_portamento": seconds(0.06), "polylimit": 2}
def _scanned(file: str, *, at: float = 0.08, depth: float = 0.75, cutoff: float = 1500.0, opened: float = 22.0, drive: float = 9.0, under: float = 0.45, top: float = 5200.0,
             soft: bool = False, glide: float = 0.06, wobble: tuple[float, float, float] | None = None) -> tuple[dict, dict]:
    """A lead that goes through a table with every stroke: from `depth` past where it stands (`at`) back to it, with the filter, harder as it is struck harder; a pulse an octave under it; clipped, and shut at `top`.
    `soft`: sung and not struck. `wobble`: to and fro so many times a beat, how far through the table, how many semitones of the filter."""
    values = {**table(1, file, at=at), **osc(2, shape=PULSE, octave=-1, width=0.4, level=under), "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(cutoff), "a_filter1_resonance": 0.2,
              "a_filter1_envmod": opened, "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT if soft else WS_HARD, "a_ws_drive": drive, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(top),
              **(env(2, 0.03, 0.5, 0.45, 0.25) if soft else env(2, 0.002, 0.22, 0.25, 0.1)), **(env(1, 0.02, 0.5, 0.9, 0.18) if soft else env(1, 0.002, 0.5, 0.9, 0.08)),
              **MONO, "a_portamento": seconds(glide), **(VIBRATO if soft else {})}
    routes = {"a_osc1_param0": [("filter env", depth), ("velocity", 0.12)], "a_filter1_cutoff": [("velocity", 12.0)]}
    if soft:
        routes["a_pitch"] = [("lfo1", 0.16)]
    if wobble:
        times, through, semitones = wobble
        values.update({"a_lfo0_shape": 0, "a_lfo0_rate": rate(2.0 * times), "a_lfo0_trigmode": 1, "sync a_lfo0_rate": 1})
        routes["a_osc1_param0"].append(("lfo1", through))
        routes["a_filter1_cutoff"].append(("lfo1", semitones))
    return values, routes


def _struck(file: str, *, at: float = 0.08, depth: float = 0.6, cutoff: float = 560.0, opened: float = 32.0) -> tuple[dict, dict]:
    """A stab from a table: two of it a little apart and a triangle an octave under, thrown open and shut within an eighth. (A pulse under it, as the leads have, has its fifth overtone, a major third, as loud as what is struck:
    Tin Roof's stabs, the first of these, 64% in C sharp phrygian, 2026-11-25; and they were opened a third as far again.)"""
    return ({**table(1, file, at=at, voices=2, detune=0.06), **triangle(2, octave=-1, level=0.8), "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(cutoff),
             "a_filter1_resonance": 0.2, "a_filter1_envmod": opened, "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 10.0, "a_filter2_type": LP12, "a_filter2_subtype": 0,
             "a_filter2_cutoff": hz(4200.0), **env(2, 0.001, 0.12, 0.06, 0.1), **env(1, 0.001, 0.3, 0.12, 0.13), "polylimit": 12},
            {"a_osc1_param0": [("filter env", depth)], "a_filter1_cutoff": [("velocity", 14.0)]})


def _sunk(file: str, *, at: float = 0.06, depth: float = 0.5, cutoff: float = 320.0) -> tuple[dict, dict]:
    """A bass from a table: one of it and a pulse on the note, shut low, opened by each stroke for a sixteenth or two; the sub is a track of its own (club.SUBBED)."""
    return ({**table(1, file, at=at), **osc(2, shape=PULSE, pitch=0.05, level=0.4), "a_osc2_retrigger": 1, "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(cutoff),
             "a_filter1_resonance": 0.18, "a_filter1_envmod": 28.0, "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 9.0,
             **env(2, 0.002, 0.15, 0.22, 0.08), **env(1, 0.002, 0.5, 0.85, 0.07), "polylimit": 4},
            {"a_osc1_param0": [("filter env", depth)], "a_filter1_cutoff": [("velocity", 12.0)]})


# Each design: its parameters (on the empty saw) and its modulations, {parameter: [(source, depth), ...]}.
# (The first two sets were measured, refined against the factory patches and judged while their squares were saws an octave
# up and their triangles squares (see SAW, PULSE); the measurements beside them are of those. Drawn as they are described
# from the afternoon of 2026-11-21, measured and judged again.)
DESIGNS: dict[str, tuple[dict, dict]] = {
    # The rolling bass's body (the sub plays under it on its own track): a saw and a square a few cents apart, through a
    # 24 dB ladder low-pass that opens on each note and closes within a sixteenth or two, so a line of eighths or sixteenths
    # rolls rather than drones, its notes ending clean so the kick's duck can breathe between them.
    # (2026-11-21, the first demo: its middle 10 dB under the factory saw's at 320 to 640 Hz, where a bass is heard on small
    # loudspeakers, and weighed by loudness it took 2.6 dB more of the lows: the ladder a little more open, the envelope
    # leaving more of itself, and a soft waveshaper after the filter for the harmonics that carry it.)
    "house bass": ({**osc(1), **osc(2, shape=PULSE, pitch=0.07, level=0.55),
                    "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(450.0), "a_filter1_resonance": 0.25,
                    "a_filter1_envmod": 30.0, "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 6.0,
                    **env(2, 0.004, 0.16, 0.22, 0.08), **env(1, 0.002, 0.5, 0.8, 0.07), "polylimit": 4},
                   {}),
    # The harsh twin (club.harsher): what comes in under a long drop's second half on the bass's own notes, heard as the
    # bass turning harsher. Three detuned saws and a square driven hard through a soft waveshaper, opened to 2.4 kHz, and a
    # 12 dB high-pass at 180 Hz after it, so that it adds the grit and leaves the low end to the bass and the sub.
    "house bass harsh": ({**osc(1, voices=3, detune=0.15), **osc(2, shape=PULSE, level=0.5),
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(2400.0), "a_filter1_resonance": 0.1,
                          "a_filter1_envmod": 12.0, "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(180.0),
                          "a_ws_type": WS_SOFT, "a_ws_drive": 9.0,
                          **env(2, 0.004, 0.3, 0.6, 0.1), **env(1, 0.003, 0.5, 0.9, 0.08), "polylimit": 4},
                         {}),
    # The pluck: three detuned saws and a quieter one an octave up, through a driven 24 dB low-pass shut low and thrown
    # open by a short envelope (a quarter of a second down to nothing), the note itself gone in under a second: the
    # sound the dotted-eighth delay and the room are written for. Played harder, it opens further.
    "house pluck": ({**osc(1, voices=3, detune=0.12), **osc(2, octave=1, level=0.35),
                     "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(300.0), "a_filter1_resonance": 0.3,
                     "a_filter1_envmod": 48.0, "a_filter1_keytrack": 0.5,
                     **env(2, 0.003, 0.22, 0.0, 0.2), **env(1, 0.002, 0.7, 0.0, 0.35), "polylimit": 16},
                    {"a_filter1_cutoff": [("velocity", 12.0)]}),
    # The pad: a seven-voice supersaw over a five-voice one an octave down and a little triangle an octave up for air,
    # through a soft 12 dB low-pass that a slow scene LFO (one turn in about twelve seconds) opens and closes by an octave
    # each way: a pad that breathes on its own under the chords, never the same two bars running. Slow in and slow out.
    "house pad": ({**osc(1, voices=7, detune=0.28), **osc(2, octave=-1, voices=5, detune=0.2, level=0.5),
                   **triangle(3, octave=1, level=0.2),
                   "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1400.0), "a_filter1_resonance": 0.15,
                   "a_filter1_keytrack": 0.3, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.08), "a_lfo6_trigmode": 0,
                   **env(1, 0.9, 1.0, 0.9, 2.2), "polylimit": 16},
                  {"a_filter1_cutoff": [("scene lfo1", 14.0)]}),
    # The lead: a nine-voice supersaw with a square an octave under it for body, a 24 dB low-pass high up that the
    # envelope lifts a little more as each note starts, a glide of 40 ms between notes and a vibrato that waits a third of
    # a second before it begins: a lead that sings over the drop rather than buzzing.
    # (2026-11-21, the demos: open to 2.5 kHz the leads came out 5 to 5.6 dB quieter in the mix and 7 to 10 dB short at 1.25 to
    # 2.5 kHz, the loudness's weighting taking a very bright sound down whole, its middle with it; 13 to 16 dB brighter at
    # 10 kHz. Shut lower and opened by the envelope at each note: the middle back, the fizz gone, the attack bright.)
    "house lead": ({**osc(1, voices=9, detune=0.18), **osc(2, shape=PULSE, octave=-1, level=0.3),
                    "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1800.0), "a_filter1_resonance": 0.2,
                    "a_filter1_envmod": 18.0, "a_filter1_keytrack": 0.6,
                    **env(2, 0.004, 0.5, 0.4, 0.3), **env(1, 0.005, 0.6, 0.85, 0.3), "a_portamento": seconds(0.04),
                    "a_lfo0_shape": 0, "a_lfo0_rate": rate(5.5), "a_lfo0_delay": seconds(0.35), "a_lfo0_attack": seconds(0.3),
                    "polylimit": 8},
                   {"a_pitch": [("lfo1", 0.15)]}),
    # The big lead for the drops (house.LEAD_WEIGHT's bigger voice): sixteen saws spread wide, seven more an octave up for
    # the anthem's shine and a square an octave down for its body, open high, a short glide: the drop's lead, wider and
    # brighter than the theme's.
    "house lead super": ({**osc(1, voices=16, detune=0.3), **osc(2, octave=1, voices=7, detune=0.2, level=0.2),
                          **osc(3, shape=PULSE, octave=-1, level=0.25),
                          "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(2200.0), "a_filter1_resonance": 0.15,
                          "a_filter1_envmod": 16.0, "a_filter1_keytrack": 0.5,
                          **env(2, 0.004, 0.6, 0.5, 0.4), **env(1, 0.006, 0.8, 0.9, 0.4), "a_portamento": seconds(0.02),
                          "polylimit": 8},
                         {}),
    # The glass pluck (arpeggios and bells over the chords): a narrow pulse and a triangle an octave up, through a 24 dB
    # low-pass thrown open and shut in a sixth of a second: hollow and bright, a bell's ring without a bell's clang.
    "house glass": ({**osc(1, shape=PULSE, width=0.3), **triangle(2, octave=1, level=0.5),
                     "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1800.0), "a_filter1_resonance": 0.2,
                     "a_filter1_envmod": 36.0, "a_filter1_keytrack": 0.7,
                     **env(2, 0.002, 0.15, 0.0, 0.2), **env(1, 0.002, 0.5, 0.0, 0.4), "polylimit": 16},
                    {"a_filter1_cutoff": [("velocity", 10.0)]}),
    # The warm pad: five saws over a triangle an octave down through a soft low-pass well under a kilohertz, opening and
    # closing half an octave each way in about seventeen seconds: the pad of the calm places, a bed rather than a shine.
    "house pad warm": ({**osc(1, voices=5, detune=0.15), **triangle(2, octave=-1, level=0.6),
                        "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(900.0), "a_filter1_resonance": 0.1,
                        "a_filter1_keytrack": 0.3, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.06), "a_lfo6_trigmode": 0,
                        **env(1, 1.2, 1.0, 0.9, 2.5), "polylimit": 16},
                       {"a_filter1_cutoff": [("scene lfo1", 8.0)]}),
    # The hollow pad: squares, three a little apart and one an octave down, through a resonant 24 dB low-pass; a slow
    # triangle moves the squares' width (the hollowness itself breathing) and a slower sine the filter.
    "house pad hollow": ({**osc(1, shape=PULSE, width=0.5, voices=3, detune=0.12), **osc(2, shape=PULSE, width=0.5, octave=-1, level=0.5),
                         "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1200.0), "a_filter1_resonance": 0.35,
                         "a_filter1_keytrack": 0.4, "a_lfo6_shape": 1, "a_lfo6_rate": rate(0.1), "a_lfo6_trigmode": 0,
                         "a_lfo7_shape": 0, "a_lfo7_rate": rate(0.05), "a_lfo7_trigmode": 0,
                         **env(1, 0.8, 1.0, 0.85, 2.0), "polylimit": 16},
                        {"a_osc1_param1": [("scene lfo1", 0.3)], "a_filter1_cutoff": [("scene lfo2", 6.0)]}),
    # The glass pad: triangles a little apart and narrow pulses an octave up, high-passed at 250 Hz and open on top, its
    # filter turning slowly: air and shimmer over the chords, nothing under them.
    "house pad glass": ({**triangle(1, voices=3, detune=0.08), **osc(2, shape=PULSE, width=0.25, octave=1, voices=3, detune=0.15, level=0.35),
                        "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(3000.0), "a_filter1_resonance": 0.1,
                        "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(200.0),
                        "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.12), "a_lfo6_trigmode": 0,
                        **env(1, 1.0, 1.0, 0.9, 3.0), "polylimit": 16},
                       {"a_filter1_cutoff": [("scene lfo1", 7.0)]}),     # (14 to 16 dB brighter than the factory pad at 5-10 kHz, open to 5 kHz: shut lower)
    # The chord stab: three saws and a square through a 24 dB ladder, a quick envelope snapping it open and the note gone
    # in under half a second, so the chords are struck and leave room: a deep house stab, not a held organ.
    "house stab": ({**osc(1, voices=3, detune=0.1), **osc(2, shape=PULSE, pitch=0.05, level=0.5),
                    "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(500.0), "a_filter1_resonance": 0.2,
                    "a_filter1_envmod": 36.0, "a_filter1_keytrack": 0.4,
                    **env(2, 0.003, 0.18, 0.1, 0.15), **env(1, 0.002, 0.4, 0.0, 0.2), "polylimit": 16},
                   {}),
    # ----- the third set (2026-11-21, afternoon): the rest of what House still played as Surge's factory made it, by how
    # much it plays them: the FM bass, the plucked bass, the whistle's lead, the reese, the square bass, the hollow lead
    # and the bell. (The sub stays Surge's: a sine, whose whole job is to be one.)
    # The FM bass: one sine modulated by two, at the note and an octave over it, with a little feedback toward a saw. The
    # filter envelope throws both modulations up at each note (an index of about 6 for a moment, 2.5 held), so a note
    # starts bright and woody and settles round: the FM bass of the deep house records, where the factory's had been a
    # sine with a little on top, 17 to 30 dB short of the liked stems from 450 Hz up. Harder notes start brighter.
    "house bass fm": ({**fm2(1, m1=0.27, r1=1, m2=0.2, r2=2, feedback=0.15),
                       "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(3000.0), "a_filter1_keytrack": 0.5,
                       "a_ws_type": WS_SOFT, "a_ws_drive": 3.0,
                       **env(2, 0.001, 0.15, 0.2, 0.1), **env(1, 0.0015, 0.5, 0.7, 0.06), "polylimit": 4},
                      {"a_osc1_param0": [("filter env", 0.12), ("velocity", 0.05)], "a_osc1_param2": [("filter env", 0.08)]}),
    # The FM bass held lighter (2026-11-23, night: eased 4 dB at 600 Hz at the desk, club.FM_MIDDLE, it still stood 4.6 to
    # 7.9 dB over the liked stems there, its weight spread from 226 Hz to 3.5 kHz: what its feedback toward a saw and the
    # waveshaper's drive put over the note's first few harmonics). The same note, a little less modulated (0.25 for 0.27),
    # the saw's feedback and the grit less (0.06 for 0.15, 1.5 dB of drive for 3): sounds.FM_LIGHT plays it for the FM bass.
    "house bass fm light": ({**fm2(1, m1=0.25, r1=1, m2=0.2, r2=2, feedback=0.06),
                             "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(3000.0), "a_filter1_keytrack": 0.5,
                             "a_ws_type": WS_SOFT, "a_ws_drive": 1.5,
                             **env(2, 0.001, 0.15, 0.2, 0.1), **env(1, 0.0015, 0.5, 0.7, 0.06), "polylimit": 4},
                            {"a_osc1_param0": [("filter env", 0.12), ("velocity", 0.05)], "a_osc1_param2": [("filter env", 0.08)]}),
    # The plucked bass: a saw and a square through a resonant 24 dB ladder shut at 180 Hz and thrown open four octaves by
    # an envelope gone in a tenth of a second, the note itself dying away over half a second: the squelch of a deep house
    # pluck, its quack the resonance. (The sub goes under it on its own track: club.SUBBED.)
    "house bass pluck": ({**osc(1), **osc(2, shape=PULSE, pitch=0.04, level=0.5), "a_osc1_retrigger": 1, "a_osc2_retrigger": 1,
                          "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(180.0), "a_filter1_resonance": 0.45,
                          "a_filter1_envmod": 40.0, "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 4.0,
                          **env(2, 0.001, 0.09, 0.05, 0.08), **env(1, 0.001, 0.45, 0.1, 0.06), "polylimit": 4},
                         {"a_filter1_cutoff": [("velocity", 8.0)]}),
    # The reese: two pairs of saws pulled apart, a quarter of a semitone and a seventh (the outer voices 12 and 7 cents
    # either side of the note; at 32 and 21, as first drawn, the beating was a wobble), their beating a slow turning in the
    # bass, through a driven 24 dB low-pass at 650 Hz that a slow LFO (one turn in eight seconds) opens and closes by
    # half an octave, and a soft waveshaper's grit: a bass that moves while it holds.
    "house bass wide": ({**osc(1, voices=2, detune=0.12), **osc(2, voices=2, detune=0.07, pitch=-0.03, level=0.7),
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(650.0), "a_filter1_resonance": 0.2,
                         "a_filter1_envmod": 10.0, "a_filter1_keytrack": 0.3, "a_ws_type": WS_SOFT, "a_ws_drive": 8.0,
                         "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.125), "a_lfo6_trigmode": 0,
                         **env(2, 0.005, 0.4, 0.5, 0.2), **env(1, 0.003, 1.0, 1.0, 0.12), "polylimit": 4},
                        {"a_filter1_cutoff": [("scene lfo1", 7.0)]}),
    # The square bass: two squares a few cents apart through a 24 dB low-pass at 500 Hz that each note opens two octaves
    # and lets settle to a third of that: hollow and woody, the odd harmonics a square has, the bass of the organ-bass
    # records without the organ.
    "house bass square": ({**osc(1, shape=PULSE), **osc(2, shape=PULSE, pitch=0.06, level=0.6), "a_osc1_retrigger": 1,
                           "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(500.0), "a_filter1_resonance": 0.2,
                           "a_filter1_envmod": 24.0, "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 4.0,
                           **env(2, 0.001, 0.22, 0.35, 0.1), **env(1, 0.0015, 0.6, 0.8, 0.07), "polylimit": 4},
                          {}),
    # The whistle's lead (the whistle and the flute written for House): a sine with a breath of noise under it and a
    # quiet triangle an octave up, soft in (30 ms), a slide of 60 ms between notes and a vibrato that waits for the note
    # to settle: a tune whistled, not a synth's beep. The breath is kept under 4.5 kHz and over 200 Hz.
    "house lead sine": ({**sine(1, feedback=0.05), **triangle(2, octave=1, level=0.12),
                         "a_mute_noise": 0, "a_level_noise": 0.05, "a_noisecol": 0.3,
                         "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(4500.0), "a_filter1_keytrack": 0.5,
                         "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(200.0),
                         **env(1, 0.03, 1.0, 0.9, 0.3), "a_portamento": seconds(0.06),
                         "a_lfo0_shape": 0, "a_lfo0_rate": rate(5.0), "a_lfo0_delay": seconds(0.35), "a_lfo0_attack": seconds(0.4),
                         "polylimit": 4},
                        {"a_pitch": [("lfo1", 0.18)]}),
    # (2026-11-21, night: Morning on the Hill III's study, its whistle lead 8.6 dB thin in its middle and 22 under the liked
    # stems at its top: a sine is too pure to carry a tune over a full band, and a fifth of House's takes lead with it.) The
    # whistle with its edge, the sound of the air splitting on the lip: the sine leaned toward a saw (feedback 0.12), the
    # triangle an octave up nearly twice as loud, more breath, a soft saturation for the odd harmonics a real whistle's
    # edge tone has (4 dB), and the low-pass opened to 6 kHz. The same slide, the same late vibrato (sounds.WHISTLE_EDGE).
    "house lead whistle": ({**sine(1, feedback=0.12), **triangle(2, octave=1, level=0.22),
                            "a_mute_noise": 0, "a_level_noise": 0.08, "a_noisecol": 0.3,
                            "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(6000.0), "a_filter1_keytrack": 0.5,
                            "a_ws_type": WS_SOFT, "a_ws_drive": 4.0,
                            "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(200.0),
                            **env(1, 0.03, 1.0, 0.9, 0.3), "a_portamento": seconds(0.06),
                            "a_lfo0_shape": 0, "a_lfo0_rate": rate(5.0), "a_lfo0_delay": seconds(0.35), "a_lfo0_attack": seconds(0.4),
                            "polylimit": 4},
                           {"a_pitch": [("lfo1", 0.18)]}),
    # The hollow lead (the hollow and the pipe): two squares a little apart and a narrow pulse, through a 24 dB low-pass
    # at 2 kHz that each note lifts a little: odd harmonics, a reed's hollowness, with the lead's slide and late vibrato.
    "house lead hollow": ({**osc(1, shape=PULSE, voices=2, detune=0.06), **osc(2, shape=PULSE, width=0.25, pitch=-0.05, level=0.35),
                           "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(2000.0), "a_filter1_resonance": 0.3,
                           "a_filter1_envmod": 10.0, "a_filter1_keytrack": 0.6,
                           **env(2, 0.004, 0.4, 0.5, 0.3), **env(1, 0.008, 0.6, 0.85, 0.3), "a_portamento": seconds(0.04),
                           "a_lfo0_shape": 0, "a_lfo0_rate": rate(5.5), "a_lfo0_delay": seconds(0.35), "a_lfo0_attack": seconds(0.3),
                           "polylimit": 8},
                          {"a_pitch": [("lfo1", 0.15)]}),
    # The bell: a sine modulated at three and a half times its note, partials no string or pipe has, and at its note for
    # the body; the strike throws the bell's modulation up and lets it fall over most of a second, so each note clangs
    # and then sings, ringing two seconds. A sine an octave up for its shimmer. Harder notes clang more.
    "house bell": ({**fm3(1, m1=0.26, r1=3.5, m2=0.18, r2=1.0), **sine(2, octave=1, level=0.15),
                    "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(7000.0), "a_filter1_keytrack": 0.3,
                    **env(2, 0.001, 0.8, 0.0, 1.0), **env(1, 0.001, 2.0, 0.0, 1.2), "polylimit": 16},
                   {"a_osc1_param0": [("filter env", 0.12), ("velocity", 0.06)], "a_osc1_param2": [("filter env", 0.06)]}),
    # ----- the leads (2026-11-24: "house still needs to work on that main synth lead sound"). Measured, the saw and the supersaw were one sound, within 1 dB
    # of each other in every octave, dull from 5 kHz and as open on a drop's first bar as on its last, and 135 of 196 songs had one of them. Each of these is
    # played harder or softer and opens as it is; those with a bend of their own slide between notes that meet (a mono voice, its slide on tied notes only).
    # The body: two saws and a square an octave under through a driven ladder that each note throws open and lets fall.
    "house lead ladder": ({**osc(1), **osc(2, pitch=0.08, level=0.9), **osc(3, shape=PULSE, octave=-1, level=0.55),
                           "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(620.0), "a_filter1_resonance": 0.38,
                           "a_filter1_envmod": 38.0, "a_filter1_keytrack": 0.6, "a_ws_type": WS_SOFT, "a_ws_drive": 8.0,
                           **env(2, 0.002, 0.3, 0.32, 0.2), **env(1, 0.002, 0.5, 0.9, 0.16), **VIBRATO, **MONO},
                          {"a_filter1_cutoff": [("velocity", 16.0)], "a_pitch": [("lfo1", 0.16)]}),
    # The width beside it: nine saws spread far and seven an octave up, nothing of them under 400 Hz.
    "house lead width": ({**osc(1, voices=9, detune=0.34), **osc(2, octave=1, voices=7, detune=0.26, level=0.5),
                          "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(2600.0), "a_filter1_resonance": 0.1,
                          "a_filter1_envmod": 16.0, "a_filter1_keytrack": 0.6, "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(420.0),
                          **env(2, 0.004, 0.4, 0.5, 0.3), **env(1, 0.004, 0.6, 0.8, 0.22), "polylimit": 8},
                         {"a_filter1_cutoff": [("velocity", 16.0)]}),
    # The bite: each note's first fiftieth of a second, an octave up, and gone.
    "house lead bite": ({**osc(1, octave=1), **osc(2, shape=PULSE, octave=2, width=0.3, level=0.5), "a_filter1_type": LP12, "a_filter1_subtype": 0,
                         "a_filter1_cutoff": hz(7000.0), "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(900.0),
                         **env(1, 0.001, 0.07, 0.0, 0.05), "polylimit": 8},
                        {}),
    # Hard sync: a saw restarted by another's clock, the clock swept down by each note's envelope: a scream at the start of it. (Swept 22 half-steps in half a second, a riff's short
    # stroke was all sweep: overtones sliding at 3.97, 4.42 and 8.4 times the note, read 19 cents flat in two songs. Six, from a little higher, and a stroke has a pitch.)
    "house lead sync": ({**osc(1), "a_osc1_param4": 7.0, **osc(2, shape=PULSE, octave=-1, level=0.5), "a_filter1_type": LADDER, "a_filter1_subtype": 3,
                         "a_filter1_cutoff": hz(1500.0), "a_filter1_resonance": 0.2, "a_filter1_envmod": 18.0, "a_filter1_keytrack": 0.6,
                         "a_ws_type": WS_SOFT, "a_ws_drive": 6.0, **env(2, 0.004, 0.45, 0.25, 0.25), **env(1, 0.003, 0.5, 0.9, 0.16), **VIBRATO, **MONO},
                        {"a_osc1_param4": [("filter env", 6.0), ("velocity", 3.0)], "a_filter1_cutoff": [("velocity", 12.0)], "a_pitch": [("lfo1", 0.18)]}),
    # Two pulses whose widths turn against each other over an octave's square: the dark, wide lead of a polysynth.
    "house lead pwm": ({**osc(1, shape=PULSE, width=0.5, voices=2, detune=0.07), **osc(2, shape=PULSE, width=0.35, pitch=-0.06, level=0.9),
                        **osc(3, shape=PULSE, octave=-1, level=0.4), "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(1050.0),
                        "a_filter1_resonance": 0.3, "a_filter1_envmod": 22.0, "a_filter1_keytrack": 0.6, "a_lfo6_shape": 1, "a_lfo6_rate": rate(0.7), "a_lfo6_trigmode": 0,
                        **env(2, 0.004, 0.4, 0.4, 0.25), **env(1, 0.004, 0.6, 0.9, 0.2), **VIBRATO, "a_portamento": seconds(0.03), "polylimit": 4},
                       {"a_osc1_param1": [("scene lfo1", 0.32)], "a_osc2_param1": [("scene lfo1", -0.22)], "a_filter1_cutoff": [("velocity", 14.0)],
                        "a_pitch": [("lfo1", 0.12)]}),
    # A voice: two band-passes side by side where a throat has its two formants, turning between an "oh" and an "ah" in eighths.
    "house lead vox": ({**osc(1, voices=3, detune=0.1), **osc(2, shape=PULSE, width=0.3, octave=-1, level=0.5), "a_fb_config": 3,
                        "a_filter1_type": BP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(620.0), "a_filter1_resonance": 0.62, "a_filter1_envmod": 4.0,
                        "a_filter2_type": BP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(1250.0), "a_filter2_resonance": 0.6, "a_filter2_envmod": 10.0,
                        "a_ws_type": WS_SOFT, "a_ws_drive": 6.0, "a_lfo0_shape": 0, "a_lfo0_rate": rate(1.83), "a_lfo0_trigmode": 1,
                        **env(2, 0.02, 0.35, 0.3, 0.2), **env(1, 0.006, 0.5, 0.9, 0.18), **MONO},
                       {"a_filter1_cutoff": [("lfo1", 4.0), ("velocity", 4.0)], "a_filter2_cutoff": [("lfo1", -7.0), ("velocity", 7.0)]}),
    # Struck metal that holds its note: two modulated sines, one at an odd ratio, the strike throwing both up.
    "house lead metal": ({**fm2(1, m1=0.24, r1=1, m2=0.16, r2=5, feedback=0.25), **fm3(2, m1=0.2, r1=2.76, m2=0.1, r2=1.0, level=0.5),
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(1700.0), "a_filter1_resonance": 0.2, "a_filter1_envmod": 26.0,
                          "a_filter1_keytrack": 0.6, "a_ws_type": WS_SOFT, "a_ws_drive": 6.0,
                          **env(2, 0.001, 0.22, 0.18, 0.2), **env(1, 0.001, 0.45, 0.55, 0.2), "polylimit": 4},
                         {"a_osc1_param0": [("filter env", 0.14), ("velocity", 0.06)], "a_osc1_param2": [("filter env", 0.1)], "a_filter1_cutoff": [("velocity", 12.0)]}),
    # The acid line: one saw through a ladder turned nearly to its own note, slammed open by each note's envelope, an accent further.
    "house lead acid": ({**osc(1), "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(300.0), "a_filter1_resonance": 0.82,
                         "a_filter1_envmod": 44.0, "a_filter1_keytrack": 0.25, "a_ws_type": WS_SOFT, "a_ws_drive": 11.0,
                         **env(2, 0.002, 0.2, 0.0, 0.1), **env(1, 0.002, 0.5, 0.7, 0.06), **MONO},
                        {"a_filter1_cutoff": [("velocity", 18.0)]}),
    # The squelch (2026-11-24: of every act on one song warehouse, the acid one, stood 8 to 11 over the others): the acid line's other voice, a square through the same ladder, duller, driven harder:
    # what joins two other acts' leads.
    "house lead squelch": ({**osc(1, shape=PULSE), "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(240.0), "a_filter1_resonance": 0.78,
                            "a_filter1_envmod": 38.0, "a_filter1_keytrack": 0.3, "a_ws_type": WS_SOFT, "a_ws_drive": 14.0,
                            **env(2, 0.002, 0.16, 0.0, 0.1), **env(1, 0.002, 0.45, 0.7, 0.06), **MONO},
                           {"a_filter1_cutoff": [("velocity", 20.0)]}),
    # The growl: saws and squares driven hard, a low-pass opened and shut on the eighths.
    "house lead growl": ({**osc(1, voices=2, detune=0.12), **osc(2, shape=PULSE, voices=2, detune=0.07, pitch=-0.03, octave=-1, level=0.7),
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(520.0), "a_filter1_resonance": 0.35, "a_filter1_envmod": 18.0,
                          "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 12.0, "a_lfo0_shape": 0, "a_lfo0_rate": rate(3.667), "a_lfo0_trigmode": 1,
                          **env(2, 0.004, 0.35, 0.3, 0.2), **env(1, 0.004, 0.6, 0.9, 0.15), **MONO},
                         {"a_filter1_cutoff": [("lfo1", 14.0), ("velocity", 10.0)]}),
    # Hard ones (2026-11-24: what was played was counted, bells, glass and plucks over major chords; these stand under a hard song's riff).
    # The hoover: saws, a pulse whose width turns and a square an octave under, bent up into each note from a semitone and a half under it in a thirtieth of a second (from three, in a
    # twentieth, it took half of a quick note to arrive).
    "house lead hoover": ({**osc(1, voices=5, detune=0.26), **osc(2, shape=PULSE, width=0.4, voices=2, detune=0.1, level=0.8), **osc(3, shape=PULSE, octave=-1, level=0.6),
                           "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(1500.0), "a_filter1_resonance": 0.18, "a_filter1_envmod": 10.0,
                           "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 8.0, "a_lfo6_shape": 1, "a_lfo6_rate": rate(2.2), "a_lfo6_trigmode": 0,
                           **env(2, 0.001, 0.03, 0.0, 0.1), **env(1, 0.003, 0.5, 0.9, 0.12), **MONO},
                          {"a_pitch": [("filter env", -1.5)], "a_osc2_param1": [("scene lfo1", 0.28)], "a_filter1_cutoff": [("velocity", 14.0)]}),
    # The razor (the foundry's, in the place of struck metal, which rings as a bell does: without its lead Blast Furnace measured darker and rawer than with it): saws and a narrow pulse an octave under,
    # shut low, thrown half open by each stroke and clipped hard.
    "house lead razor": ({**osc(1, voices=3, detune=0.14), **osc(2, shape=PULSE, width=0.22, octave=-1, voices=2, detune=0.08, level=0.85),
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(620.0), "a_filter1_resonance": 0.3, "a_filter1_envmod": 20.0,
                          "a_filter1_keytrack": 0.45, "a_ws_type": WS_HARD, "a_ws_drive": 18.0, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(4600.0),
                          **env(2, 0.001, 0.14, 0.15, 0.1), **env(1, 0.001, 0.4, 0.85, 0.09), **MONO},
                         {"a_filter1_cutoff": [("velocity", 16.0)]}),
    # A reed: two narrow pulses through a band-pass low in the throat, a slow vibrato that waits: a dark, nasal line, no bell in it.
    "house lead reed": ({**osc(1, shape=PULSE, width=0.12), **osc(2, shape=PULSE, width=0.2, pitch=0.06, level=0.7), **osc(3, shape=PULSE, octave=-1, width=0.3, level=0.35),
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(900.0), "a_filter1_resonance": 0.42, "a_filter1_envmod": 14.0,
                         "a_filter1_keytrack": 0.6, "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(140.0), "a_ws_type": WS_SOFT, "a_ws_drive": 7.0,
                         **env(2, 0.008, 0.3, 0.45, 0.2), **env(1, 0.006, 0.5, 0.9, 0.14), **VIBRATO, **MONO},
                        {"a_filter1_cutoff": [("velocity", 14.0)], "a_pitch": [("lfo1", 0.2)]}),
    # The fifth: a saw, another a fifth over it and a square an octave under, one key a bare power chord.
    "house lead fifth": ({**osc(1, voices=2, detune=0.08), **osc(2, pitch=7.0, voices=2, detune=0.08, level=0.75), **osc(3, shape=PULSE, octave=-1, level=0.55),
                          "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(560.0), "a_filter1_resonance": 0.32, "a_filter1_envmod": 34.0,
                          "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 9.0,
                          **env(2, 0.002, 0.28, 0.25, 0.2), **env(1, 0.002, 0.5, 0.85, 0.14), "polylimit": 4},
                         {"a_filter1_cutoff": [("velocity", 16.0)]}),
    # Five more (2026-11-25: "house is a little better keep iterating"): what a riff cut up among several voices is said by (club.ACTS, `cut`), each a machine of another kind.
    # The talker: two band-passes side by side, as a throat has its formants, opened by each stroke from an "oo" to an "ah" and back, clipped.
    "house lead talk": ({**osc(1, voices=2, detune=0.06), **osc(2, shape=PULSE, width=0.28, octave=-1, level=0.7), "a_fb_config": 3,
                         "a_filter1_type": BP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(340.0), "a_filter1_resonance": 0.55, "a_filter1_envmod": 15.0,
                         "a_filter2_type": BP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(800.0), "a_filter2_resonance": 0.6, "a_filter2_envmod": 18.0,
                         "a_ws_type": WS_HARD, "a_ws_drive": 10.0, **env(2, 0.04, 0.15, 0.15, 0.1), **env(1, 0.002, 0.5, 0.9, 0.08), **MONO},
                        {"a_filter1_cutoff": [("velocity", 4.0)], "a_filter2_cutoff": [("velocity", 7.0)]}),
    # The fold: a saw and a square an octave under it, folded over on themselves by each stroke and let out again, shut low after. (Of two sines, as first drawn, it rang as a bell does: -1 on the song
    # the other four stood at +5 to +10 on.)
    "house lead fold": ({**osc(1), **osc(2, shape=PULSE, octave=-1, width=0.4, level=0.7), "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1800.0), "a_filter1_keytrack": 0.4,
                         "a_ws_type": WS_FOLD, "a_ws_drive": 5.0, "a_filter2_type": LP24, "a_filter2_subtype": 1, "a_filter2_cutoff": hz(1700.0), "a_filter2_resonance": 0.2,
                         "a_filter2_envmod": 18.0, **env(2, 0.001, 0.13, 0.15, 0.1), **env(1, 0.001, 0.45, 0.88, 0.08), **MONO},
                        {"a_ws_drive": [("filter env", 12.0), ("velocity", 4.0)], "a_filter2_cutoff": [("velocity", 12.0)]}),
    # The chip: an eight-bit ramp whose bits are turned over, further as it is struck, crushed to five, over a pulse an octave under.
    "house lead chip": ({**alias(1, shape=1, wrap=0.05, mask=0.2, threshold=0.5, bits=5.0), **osc(2, shape=PULSE, width=0.35, octave=-1, level=0.5),
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(1500.0), "a_filter1_resonance": 0.25, "a_filter1_envmod": 24.0,
                         "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 11.0, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(6500.0),
                         **env(2, 0.001, 0.12, 0.2, 0.08), **env(1, 0.001, 0.4, 0.85, 0.06), **MONO},
                        {"a_osc1_param2": [("filter env", 0.3)], "a_filter1_cutoff": [("velocity", 16.0)]}),
    # The scream: two saws and a square under them through a filter resonating on the note's own fourth overtone, whatever the note, and broken up.
    "house lead scream": ({**osc(1), **osc(2, pitch=0.09, level=0.9), **osc(3, shape=PULSE, octave=-1, level=0.5),
                           "a_filter1_type": K35, "a_filter1_subtype": 2, "a_filter1_cutoff": hz(1046.5), "a_filter1_resonance": 0.75, "a_filter1_keytrack": 1.0,
                           "a_ws_type": WS_HARD, "a_ws_drive": 14.0, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(4600.0),
                           **env(2, 0.002, 0.2, 0.3, 0.1), **env(1, 0.002, 0.5, 0.9, 0.08), **MONO},
                          {"a_ws_drive": [("velocity", 6.0)]}),
    # The reese: saws that beat slowly against one another, a thread of one an octave under, a notch going through them, clipped. (Its octave at 0.8 and its saws a fifth of a half-step apart, the hardest and the darkest drop
    # of any act, and the least liked of nine by every judge: the bottom of a lead in the bass's own octave, 2026-11-25.)
    "house lead reese": ({**osc(1, voices=3, detune=0.08), **osc(2, octave=-1, level=0.4), **osc(3, pitch=0.05, level=0.6),
                          "a_filter1_type": NOTCH12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(900.0), "a_filter1_resonance": 0.25, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.5),
                          "a_lfo6_trigmode": 0, "a_ws_type": WS_HARD, "a_ws_drive": 11.0, "a_filter2_type": LP24, "a_filter2_subtype": 1, "a_filter2_cutoff": hz(2300.0),
                          "a_filter2_envmod": 16.0, **env(2, 0.002, 0.2, 0.3, 0.1), **env(1, 0.002, 0.5, 0.9, 0.09), **MONO},
                         {"a_filter1_cutoff": [("scene lfo1", 12.0)], "a_filter2_cutoff": [("velocity", 12.0)]}),
    # Leads of another kind (2026-11-25: "house is a little better keep iterating", "find more instruments!"): the seven hundred wavetables that came with the synthesiser, none of them played before. Thirty-six were
    # given one riff in one drop (Bilge Pump's), the rest of it the same, and measured: hard against sweet, and how much of what they sound is in the song's key. The hardest were the ones that are hardly a note: gone
    # all the way through by every stroke a torn saxophone's table stood at +10.9 with 54% in the key, dragged chains +10.2 with 61%, a scraped brick +9.3 with 60%, where the acid line is +11.0 with 72%. Gone a
    # sixth of the way through, with more of the pulse an octave under them, the chains and the brick are notes again (67%, 68%), and those are what is here; five growls drawn for a bass were the sweetest (+4.4 to
    # +5.4) and two tables not in tune in themselves (the saxophone's, a run-away pulse's) are left out. Each wave is one turn of the note, whatever it was recorded from.
    # A filter swept over a saw, with what a filter does to its own edge:
    "house lead sweep": _scanned("wavetables_3rdparty/Philippe Favre/Filtering/Filtering 6.wav", depth=0.4, cutoff=900.0, opened=24.0, under=0.65, top=3600.0),
    # chains dragged:
    "house lead chain": _scanned("wavetables_3rdparty/Emu VSCO/Misc/SUS Chains Low.wav", at=0.5, depth=0.1, under=0.8),
    # a brick scraped along a wall:
    "house lead brick": _scanned("wavetables_3rdparty/Emu VSCO/Misc/ENV Brick Scrape.wav", at=0.5, depth=0.18, under=0.65),
    # a throat, far down:
    "house lead gullet": _scanned("wavetables_3rdparty/Layzer/Vocal/Vocal 18.wt", at=0.1, depth=0.18, under=0.65),
    # the first digital synthesiser's own, glass that has been broken:
    "house lead shard": _scanned("wavetables_3rdparty/Layzer/PPG/PPG 32.wt", at=0.5, depth=0.18, under=0.65),
    # a mouth, opened all the way:
    "house lead maw": _scanned("wavetables_3rdparty/Layzer/Vocal/Vocal 8.wt", under=0.5),
    # a formant pushed up over a clock that stays:
    "house lead charge": _scanned("wavetables_3rdparty/A.Liv/Crust PD/Harmonic7.wav", at=0.1, depth=0.18, under=0.65),
    # something that croaks:
    "house lead croak": _scanned("wavetables_3rdparty/Qonundrai/Articulate Croak.wav", under=0.5),
    # one wave turning into another:
    "house lead shift": _scanned("wavetables_3rdparty/Layzer/Morphs/Morph 17.wt", at=0.1, depth=0.18, under=0.65),
    # the jaw of a machine, a robot's throat, a gremlin: what joins those or sings their themes.
    "house lead jaw": _scanned("wavetables_3rdparty/A.Liv/Exocat's Metalodon/Exocat's Metalodon 1.wav", depth=0.6, under=0.5),
    "house lead droid": _scanned("wavetables_3rdparty/TNMG/Humanoid.wav", depth=0.35, under=0.6),
    "house lead gremlin": _scanned("wavetables_3rdparty/Qonundrai/Gremlin Mode.wav", depth=0.4, cutoff=900.0, opened=24.0, under=0.65, top=3600.0),
    # The wobble: a growl's table gone to and fro twice in a beat, with the filter, for a few long notes to be held through (house.HOOKS_OF, "glide").
    "house lead wobble": _scanned("wavetables_3rdparty/Venus Theory/Growl/VT Growl 7.wav", at=0.45, depth=0.15, cutoff=1100.0, opened=10.0, drive=11.0, under=0.6, wobble=(2.0, 0.4, 15.0)),
    # Two for a calm act: a low "ah" that is nobody's, hummed; a trombone that buzzes, slid from note to note.
    "house lead murmur": _scanned("wavetables/Waldorf/Male AhPG.wt", at=0.1, depth=0.35, cutoff=750.0, opened=12.0, drive=5.0, under=0.3, top=3600.0, soft=True),
    "house lead slide": _scanned("wavetables_3rdparty/Emu VSCO/Brass/SUS Trombone Buzzy.wav", at=0.2, depth=0.15, cutoff=900.0, opened=13.0, drive=6.0, under=0.4, top=3800.0, soft=True, glide=0.11),
    # Stabs. The rave's: five saws and a pulse an octave under, driven, thrown open and shut within an eighth.
    "house stab rave": ({**osc(1, voices=5, detune=0.2), **osc(2, shape=PULSE, octave=-1, level=0.6), **osc(3, octave=1, voices=3, detune=0.15, level=0.3),
                         "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(420.0), "a_filter1_resonance": 0.28, "a_filter1_envmod": 40.0,
                         "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 10.0,
                         **env(2, 0.001, 0.13, 0.08, 0.1), **env(1, 0.001, 0.3, 0.12, 0.12), "polylimit": 12},
                        {"a_filter1_cutoff": [("velocity", 16.0)]}),
    # The clang: a hammer on plate, the strike alone bright. (At an odd ratio, 2.76, as a plate's is, its chords read 59% in the key: at whole ones it is plate in tune.)
    "house stab clang": ({**fm3(1, m1=0.24, r1=3.0, m2=0.16, r2=1.0, feedback=0.1), **fm2(2, m1=0.22, r1=1, m2=0.14, r2=3, octave=-1, level=0.7),
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(900.0), "a_filter1_resonance": 0.15, "a_filter1_envmod": 30.0,
                          "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 9.0,
                          **env(2, 0.001, 0.1, 0.0, 0.1), **env(1, 0.001, 0.35, 0.0, 0.16), "polylimit": 12},
                         {"a_osc1_param0": [("filter env", 0.14), ("velocity", 0.05)], "a_filter1_cutoff": [("velocity", 12.0)]}),
    # The dub's: a dark minor-less chord behind a band-pass, left to ring a little, for the echo to repeat.
    "house stab dub": ({**osc(1, voices=2, detune=0.1), **osc(2, shape=PULSE, width=0.35, pitch=0.05, level=0.6),
                        "a_filter1_type": BP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(480.0), "a_filter1_resonance": 0.35, "a_filter1_envmod": 20.0,
                        "a_filter1_keytrack": 0.3, "a_ws_type": WS_SOFT, "a_ws_drive": 7.0, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.15), "a_lfo6_trigmode": 0,
                        **env(2, 0.002, 0.2, 0.15, 0.3), **env(1, 0.002, 0.4, 0.25, 0.45), "polylimit": 12},
                       {"a_filter1_cutoff": [("scene lfo1", 7.0), ("velocity", 10.0)]}),
    # Three stabs of the tables', and three basses and a pad (2026-11-25): a wave with a crust on it, dry as a bone (two trombones' tables were tried, and a root and its fifth by either sounded their own major third, second and
    # seventh: 62 and 64% in two phrygian songs' keys); the chains', short; the digital's. A bass whose middle is a machine's jaw, one with a crust on it, one that
    # rasps; voices that are none, held under everything.
    "house stab bone": _struck("wavetables_3rdparty/A.Liv/Crust Wave/Crust Wave 1.wav", at=0.06, depth=0.0, cutoff=420.0, opened=24.0),
    "house stab chain": _struck("wavetables_3rdparty/Emu VSCO/Misc/SUS Chains Low.wav", at=0.5, depth=0.1, cutoff=380.0, opened=22.0),
    "house stab shard": _struck("wavetables_3rdparty/Layzer/PPG/PPG 32.wt", at=0.1, depth=0.1, cutoff=400.0, opened=22.0),
    "house bass jaw": _sunk("wavetables_3rdparty/A.Liv/Exocat's Metalodon/Exocat's Metalodon 1.wav"),
    "house bass crust": _sunk("wavetables_3rdparty/A.Liv/Crust Wave/Crust Wave 1.wav", cutoff=420.0),
    "house bass rasp": _sunk("wavetables_3rdparty/Qonundrai/Abrasive Warmth.wav", cutoff=360.0, depth=0.6),
    "house pad crypt": ({**table(1, "wavetables/Waldorf/Male AhPG.wt", at=0.25, voices=3, detune=0.12), **osc(2, octave=-1, voices=2, detune=0.08, level=0.35),
                         "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(640.0), "a_filter1_resonance": 0.15, "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 6.0,
                         "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.06), "a_lfo6_trigmode": 0, **env(1, 0.9, 1.0, 0.9, 1.5), "polylimit": 12},
                        {"a_osc1_param0": [("scene lfo1", 0.2)], "a_filter1_cutoff": [("scene lfo1", 6.0)]}),
    # The slab (2026-11-24, 22:38: the monolith's second stab was a brass section's, and a fifth of it sounded its own overtone, a major second, as loud as the root: Boiler Room II's 63% in the key of it):
    # saws and a square an octave under, shut at 420 Hz, opened two octaves by the stroke for a tenth of a second: a weight put down, little of it over 1.5 kHz.
    "house stab slab": ({**osc(1, voices=3, detune=0.12), **osc(2, shape=PULSE, octave=-1, level=0.7), **osc(3, shape=PULSE, width=0.3, pitch=-0.06, level=0.4),
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(420.0), "a_filter1_resonance": 0.14, "a_filter1_envmod": 24.0,
                         "a_filter1_keytrack": 0.35, "a_ws_type": WS_SOFT, "a_ws_drive": 11.0, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(2600.0),
                         **env(2, 0.001, 0.1, 0.05, 0.12), **env(1, 0.001, 0.32, 0.1, 0.16), "polylimit": 12},
                        {"a_filter1_cutoff": [("velocity", 12.0)]}),
    # The drone (2026-11-24, 19:25: two hard acts had the supersaw pad still, and were the two whose songs measured least dark): a saw and a narrow pulse an octave apart, beating slowly, shut low and
    # driven, a slow sine moving the filter: a machine's hum and not a pad.
    "house pad drone": ({**osc(1, octave=-1, voices=2, detune=0.1), **osc(2, shape=PULSE, width=0.25, pitch=0.07, level=0.55), **osc(3, shape=PULSE, octave=-1, width=0.4, pitch=-0.05, level=0.5),
                         "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(420.0), "a_filter1_resonance": 0.35,
                         "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 12.0, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.07), "a_lfo6_trigmode": 0,
                         **env(1, 0.6, 1.0, 0.9, 1.4), "polylimit": 12},
                        {"a_filter1_cutoff": [("scene lfo1", 9.0)]}),
    # Basses. The acid's: the acid lead's ladder an octave down, its resonance less, so that its low end stays.
    "house bass acid": ({**osc(1), **osc(2, shape=PULSE, pitch=0.03, level=0.35), "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(220.0),
                         "a_filter1_resonance": 0.62, "a_filter1_envmod": 36.0, "a_filter1_keytrack": 0.3, "a_ws_type": WS_SOFT, "a_ws_drive": 9.0,
                         **env(2, 0.001, 0.14, 0.04, 0.08), **env(1, 0.001, 0.4, 0.65, 0.05), **MONO},
                        {"a_filter1_cutoff": [("velocity", 14.0)]}),
    # The grinder: two pulses and a saw beating slowly, driven into the shaper and cut again after it.
    "house bass grind": ({**osc(1, shape=PULSE, width=0.35, voices=2, detune=0.1), **osc(2, voices=2, detune=0.08, pitch=-0.04, level=0.8),
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(850.0), "a_filter1_resonance": 0.15, "a_filter1_envmod": 14.0,
                          "a_filter1_keytrack": 0.3, "a_ws_type": WS_SOFT, "a_ws_drive": 14.0, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(3200.0),
                          **env(2, 0.001, 0.2, 0.3, 0.1), **env(1, 0.001, 0.5, 0.85, 0.06), "polylimit": 4},
                         {"a_filter1_cutoff": [("velocity", 10.0)]}),
    # A pluck that can sing: three saws, a pulse an octave up and a square under, thrown open by a driven ladder and left a quarter open.
    "house lead pluck": ({**osc(1, voices=3, detune=0.1), **osc(2, shape=PULSE, width=0.28, octave=1, level=0.4), **osc(3, shape=PULSE, octave=-1, level=0.35),
                          "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(420.0), "a_filter1_resonance": 0.3, "a_filter1_envmod": 44.0,
                          "a_filter1_keytrack": 0.6, "a_ws_type": WS_SOFT, "a_ws_drive": 5.0,
                          **env(2, 0.001, 0.26, 0.06, 0.25), **env(1, 0.001, 0.55, 0.25, 0.3), "polylimit": 8},
                         {"a_filter1_cutoff": [("velocity", 20.0)]}),
    # ----- the calm ones' (2026-11-24, 22:00: the soft acts measured as sweet as the sweetest old songs, -13 to -21, on a dark song as on a light one). An inn's, a camp's and a night's: low, worn, close,
    # and no bell, pluck or glass among them. Smoke: a narrow reed with a breath over it and a triangle an octave under, shut low; its tied notes slide slowly.
    "house lead smoke": ({**osc(1, shape=PULSE, width=0.18), **triangle(2, octave=-1, level=0.6), **osc(3, shape=PULSE, width=0.3, pitch=-0.07, level=0.35),
                          "a_level_noise": 0.1, "a_mute_noise": 0, "a_noisecol": -0.35,
                          "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(640.0), "a_filter1_resonance": 0.3, "a_filter1_envmod": 10.0,
                          "a_filter1_keytrack": 0.6, "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(110.0), "a_ws_type": WS_HARD, "a_ws_drive": 11.0,
                          **env(2, 0.03, 0.4, 0.5, 0.3), **env(1, 0.02, 0.5, 0.9, 0.2), **VIBRATO, **MONO, "a_portamento": seconds(0.09)},
                         {"a_filter1_cutoff": [("velocity", 12.0)], "a_pitch": [("lfo1", 0.14)]}),
    # A foghorn: two saws, a square an octave under, a low-pass that takes a breath to open and never opens far.
    "house lead horn": ({**osc(1, voices=2, detune=0.06), **osc(2, shape=PULSE, octave=-1, width=0.4, level=0.8), **triangle(3, level=0.4),
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(360.0), "a_filter1_resonance": 0.28, "a_filter1_envmod": 20.0,
                         "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 12.0,
                         **env(2, 0.14, 0.6, 0.45, 0.5), **env(1, 0.03, 0.6, 0.92, 0.28), **VIBRATO, **MONO},
                        {"a_filter1_cutoff": [("velocity", 10.0)], "a_pitch": [("lfo1", 0.08)]}),
    # A bow drawn near the bridge: a saw and a thread of a pulse, hiss on it, thin under 220 Hz, clipped; it takes a twentieth of a second to speak.
    "house lead bow": ({**osc(1, voices=2, detune=0.05), **osc(2, shape=PULSE, width=0.08, level=0.5), **osc(3, octave=-1, level=0.4),
                        "a_level_noise": 0.07, "a_mute_noise": 0, "a_noisecol": 0.2,
                        "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(1050.0), "a_filter1_resonance": 0.35, "a_filter1_envmod": 8.0,
                        "a_filter1_keytrack": 0.6, "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(220.0), "a_ws_type": WS_HARD, "a_ws_drive": 10.0,
                        **env(2, 0.08, 0.5, 0.6, 0.3), **env(1, 0.05, 0.5, 0.92, 0.22), **VIBRATO, **MONO},
                       {"a_filter1_cutoff": [("velocity", 12.0)], "a_pitch": [("lfo1", 0.12)]}),
    # A worn tape: a triangle and a sine an octave under that will not stay still (a slow wow and a quick flutter), dull, a little hiss.
    "house lead tape": ({**triangle(1), **sine(2, feedback=0.2, octave=-1, level=0.5), **osc(3, shape=PULSE, level=0.25),
                         "a_level_noise": 0.04, "a_mute_noise": 0, "a_noisecol": -0.5,
                         "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(860.0), "a_filter1_resonance": 0.15, "a_filter1_envmod": 8.0,
                         "a_filter1_keytrack": 0.6, "a_ws_type": WS_SOFT, "a_ws_drive": 7.0, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.55), "a_lfo6_trigmode": 0,
                         "a_lfo7_shape": 0, "a_lfo7_rate": rate(5.8), "a_lfo7_trigmode": 0, **env(2, 0.01, 0.5, 0.5, 0.3), **env(1, 0.015, 0.6, 0.85, 0.3), **MONO},
                        {"a_filter1_cutoff": [("velocity", 12.0)], "a_pitch": [("scene lfo1", 0.1), ("scene lfo2", 0.03)]}),
    # Ash: an electric piano's tines struck low and driven, the strike dull, the note left to die.
    "house keys ash": ({**fm2(1, m1=0.2, r1=1, m2=0.1, r2=3, feedback=0.08), **fm2(2, m1=0.14, r1=1, octave=-1, level=0.5),
                        "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(1100.0), "a_filter1_resonance": 0.12, "a_filter1_envmod": 16.0,
                        "a_filter1_keytrack": 0.4, "a_ws_type": WS_HARD, "a_ws_drive": 12.0,
                        **env(2, 0.001, 0.4, 0.1, 0.4), **env(1, 0.002, 1.6, 0.0, 0.5), "polylimit": 12},
                       {"a_osc1_param0": [("filter env", 0.08), ("velocity", 0.05)], "a_filter1_cutoff": [("velocity", 12.0)]}),
    # Bone: a dry knock with a note in it, a quarter of a second of it (the mortuary's, whose parlour piano measured as sweet as any: its theme -16).
    "house keys bone": ({**fm2(1, m1=0.17, r1=4, m2=0.12, r2=1, feedback=0.06), **triangle(2, octave=-1, level=0.75),
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(700.0), "a_filter1_resonance": 0.16, "a_filter1_envmod": 26.0,
                         "a_filter1_keytrack": 0.4, "a_ws_type": WS_SOFT, "a_ws_drive": 10.0,
                         **env(2, 0.001, 0.07, 0.0, 0.08), **env(1, 0.001, 0.36, 0.0, 0.22), "polylimit": 12},
                        {"a_osc1_param0": [("filter env", 0.09), ("velocity", 0.04)], "a_filter1_cutoff": [("velocity", 12.0)]}),
    # Breath: wind across a pipe at the note's own pitch (noise through a band that follows the key), a low triangle and a thread of reed beside it.
    "house pad breath": ({**triangle(1, voices=2, detune=0.06), **osc(2, shape=PULSE, width=0.14, octave=-1, voices=2, detune=0.08, level=0.7),
                          "a_level_noise": 0.45, "a_mute_noise": 0, "a_noisecol": 0.0, "a_fb_config": 3, "a_route_noise": 0, "a_route_o1": 2, "a_route_o2": 2,
                          "a_filter1_type": BP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(523.25), "a_filter1_resonance": 0.82, "a_filter1_keytrack": 1.0,
                          "a_filter2_type": LP24, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(560.0), "a_filter2_resonance": 0.2, "a_filter2_keytrack": 0.5,
                          "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.09), "a_lfo6_trigmode": 0, **env(1, 1.0, 1.0, 0.9, 1.8), "polylimit": 12},
                         {"a_filter2_cutoff": [("scene lfo1", 8.0)]}),
    # A tube's bass: a sine leaned toward a saw and clipped, a triangle beside it, nothing of it over 2 kHz.
    "house bass tube": ({**sine(1, feedback=0.3), **triangle(2, level=0.5), "a_osc2_retrigger": 1,
                         "a_filter1_type": LP24, "a_filter1_subtype": 1, "a_filter1_cutoff": hz(420.0), "a_filter1_resonance": 0.12, "a_filter1_envmod": 14.0,
                         "a_filter1_keytrack": 0.4, "a_ws_type": WS_HARD, "a_ws_drive": 9.0, "a_filter2_type": LP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(1800.0),
                         **env(2, 0.001, 0.22, 0.2, 0.12), **env(1, 0.003, 0.6, 0.85, 0.09), "polylimit": 4},
                        {"a_filter1_cutoff": [("velocity", 8.0)]}),
}


def _split(data: bytes) -> tuple[bytes, str, bytes]:
    """A patch file's state: the wavetables' sizes, the XML, and what follows it (the wavetables)."""
    state = data[60:]
    if state[:4] != b"sub3":
        raise ValueError("not a Surge patch state")
    size = struct.unpack("<I", state[4:8])[0]
    return state[8:32], state[32:32 + size].decode("utf-8"), state[32 + size:]


def xml(name: str, surge: Path) -> str:
    """The design's patch as Surge's XML: the empty saw with the design's parameters and modulations set."""
    values, routes = DESIGNS[name]
    _, text, _ = _split((surge / BASE).read_bytes())
    root = ET.fromstring(text)
    meta = root.find("meta")
    if meta is not None:
        meta.set("name", name)
        meta.set("category", "FreeRock")
        meta.set("author", "FreeRock")
    params = root.find("parameters")
    for n in (1, 2, 3):
        kind = values.get("a_osc%d_type" % n, CLASSIC)
        if kind == CLASSIC:
            continue
        theirs = ET.fromstring(_split((surge / KINDS[kind]).read_bytes())[1]).find("parameters")
        if int(theirs.find("a_osc1_type").get("value")) != kind:
            raise ValueError("%s: %s's first oscillator is not of kind %d" % (name, KINDS[kind], kind))
        for k in range(7):
            node, their = params.find("a_osc%d_param%d" % (n, k)), theirs.find("a_osc1_param%d" % k)
            node.attrib.clear()
            node.attrib.update(their.attrib)
    for key, value in values.items():
        if key.startswith("table "):
            continue                                     # (a table's waves go after the XML: `state`)
        if key.startswith("sync "):
            params.find(key[5:]).set("temposync", "1")   # (an LFO that goes with the song: its rate is what it would be at 120)
            continue
        node = params.find(key)
        if node is None:
            raise KeyError("%s: Surge's patch has no parameter %r" % (name, key))
        node.set("value", ("%d" % value) if node.get("type") == "0" else ("%.6f" % value))
    for key, wanted in routes.items():
        node = params.find(key)
        if node is None:
            raise KeyError("%s: Surge's patch has no parameter %r" % (name, key))
        for source, depth in wanted:
            ET.SubElement(node, "modrouting", {"source": str(SOURCES[source]), "depth": "%.6f" % depth})
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + ET.tostring(root, encoding="unicode")


WAVES = 32            # how many of a table's waves a design keeps, spread over the whole of it (a table may have 256)


def waves(path: Path, most: int = WAVES) -> bytes:
    """A wavetable file as Surge keeps one inside a patch: its header and its waves. A `.wt` has its own header; a `.wav` says how long a wave is in a chunk of its own (Surge's, Serum's
    or Hive's). The waves are brought to one loudness with nothing under them, so that going through the table changes the colour and not the level."""
    data = path.read_bytes()
    if data[:4] == b"vawt":
        size, count, flags = struct.unpack("<IHH", data[4:12])
        kind = "<i2" if flags & 4 else "<f4"
        audio = np.frombuffer(data, kind, size * count, 12).astype(np.float64)
    elif data[:4] == b"RIFF":
        at, size, form, depth, body = 12, 2048, 1, 16, b""
        while at + 8 <= len(data):
            tag, length = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
            chunk = data[at + 8:at + 8 + length]
            if tag == b"fmt ":
                form, _, _, _, _, depth = struct.unpack("<HHIIHH", chunk[:16])
            elif tag in (b"srge", b"srgo"):
                size = struct.unpack("<I", chunk[4:8])[0]
            elif tag == b"clm ":
                size = int(chunk[3:].split()[0])
            elif tag == b"data":
                body = chunk
            at += 8 + length + (length & 1)
        kind = {(1, 16): "<i2", (3, 32): "<f4"}.get((form, depth))
        if kind is None:
            raise ValueError("%s: waves of format %d, %d bits" % (path, form, depth))
        audio = np.frombuffer(body, kind, len(body) // (depth // 8)).astype(np.float64)
        count = len(audio) // size
    else:
        raise ValueError("%s is not a wavetable" % path)
    if count < 1 or size < 2 or size > 4096 or size & (size - 1):
        raise ValueError("%s: %d waves of %d samples" % (path, count, size))
    rows = audio[:size * count].reshape(count, size)
    if count > most:
        rows = rows[np.linspace(0, count - 1, most).round().astype(int)]
    rows = rows - rows.mean(axis=1, keepdims=True)
    loud = np.sqrt((rows ** 2).mean(axis=1, keepdims=True))
    rows = rows / np.maximum(loud, 0.1 * loud.max())
    rows = 0.98 * rows / np.abs(rows).max()
    return struct.pack("<4sIHH", b"vawt", size, len(rows), 0) + rows.astype("<f4").tobytes()


def state(name: str, surge: Path) -> bytes:
    """What Surge keeps as its state for the design: its header with the XML's new size and its tables', the XML, and the waves of its tables (none in the empty saw, and none in a design that has no table)."""
    sizes, _, tail = _split((surge / BASE).read_bytes())
    body = xml(name, surge).encode("utf-8")
    values = DESIGNS[name][0]
    blocks = [waves(surge / values["table %d" % n]) if "table %d" % n in values else b"" for n in (1, 2, 3)]
    if any(blocks):
        sizes, tail = struct.pack("<6I", *[len(block) for block in blocks], 0, 0, 0), b"".join(blocks)
    return b"sub3" + struct.pack("<I", len(body)) + sizes + body + tail
