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

BASE = "patches_factory/Templates/Init Saw.fxp"

# Surge XT 1.3's numbers (src/common/SurgeStorage.h, ModulationSource.h; sst-filters' FilterConfiguration.h).
CLASSIC = 0                                         # the classic oscillator: Shape -1 triangle, 0 saw, +1 pulse
LP12, LP24, LADDER, HP12, OBXD4 = 1, 2, 3, 4, 12    # filters; the legacy ladder's subtype 3 is 24 dB
WS_SOFT = 1                                         # the waveshaper's soft saturation (after the first filter); its drive in dB
SOURCES = {"velocity": 1, "keytrack": 2, "amp env": 15, "filter env": 16, "lfo1": 17, "lfo2": 18, "scene lfo1": 23,
           "scene lfo2": 24, "random": 31}


def seconds(value: float) -> float:
    return math.log2(value)


def hz(value: float) -> float:
    """A cutoff in Surge's units: semitones from A440."""
    return 12.0 * math.log2(value / 440.0)


def rate(value: float) -> float:
    return math.log2(value)


def osc(n: int, *, shape: float = 0.0, octave: int = 0, pitch: float = 0.0, voices: int = 1, detune: float = 0.1,
        level: float = 1.0, width: float = 0.5) -> dict:
    p = "a_osc%d_" % n
    return {p + "type": CLASSIC, p + "octave": octave, p + "pitch": pitch, p + "param0": shape, p + "param1": width,
            p + "param5": detune, p + "param6": voices, "a_level_o%d" % n: level, "a_mute_o%d" % n: 0}


def env(which: int, attack: float, decay: float, sustain: float, release: float) -> dict:
    p = "a_env%d_" % which
    return {p + "attack": seconds(attack), p + "decay": seconds(decay), p + "sustain": sustain, p + "release": seconds(release)}


# Each design: its parameters (on the empty saw) and its modulations, {parameter: [(source, depth), ...]}.
DESIGNS: dict[str, tuple[dict, dict]] = {
    # The rolling bass's body (the sub plays under it on its own track): a saw and a square a few cents apart, through a
    # 24 dB ladder low-pass that opens on each note and closes within a sixteenth or two, so a line of eighths or sixteenths
    # rolls rather than drones, its notes ending clean so the kick's duck can breathe between them.
    # (2026-11-21, the first demo: its middle 10 dB under the factory saw's at 320 to 640 Hz, where a bass is heard on small
    # loudspeakers, and weighed by loudness it took 2.6 dB more of the lows: the ladder a little more open, the envelope
    # leaving more of itself, and a soft waveshaper after the filter for the harmonics that carry it.)
    "house bass": ({**osc(1), **osc(2, shape=1.0, pitch=0.07, level=0.55),
                    "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(450.0), "a_filter1_resonance": 0.25,
                    "a_filter1_envmod": 30.0, "a_filter1_keytrack": 0.5, "a_ws_type": WS_SOFT, "a_ws_drive": 6.0,
                    **env(2, 0.004, 0.16, 0.22, 0.08), **env(1, 0.002, 0.5, 0.8, 0.07), "polylimit": 4},
                   {}),
    # The harsh twin (club.harsher): what comes in under a long drop's second half on the bass's own notes, heard as the
    # bass turning harsher. Three detuned saws and a square driven hard through a soft waveshaper, opened to 2.4 kHz, and a
    # 12 dB high-pass at 180 Hz after it, so that it adds the grit and leaves the low end to the bass and the sub.
    "house bass harsh": ({**osc(1, voices=3, detune=0.15), **osc(2, shape=1.0, level=0.5),
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
                   **osc(3, shape=-1.0, octave=1, level=0.2),
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
    "house lead": ({**osc(1, voices=9, detune=0.18), **osc(2, shape=1.0, octave=-1, level=0.3),
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
                          **osc(3, shape=1.0, octave=-1, level=0.25),
                          "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(2200.0), "a_filter1_resonance": 0.15,
                          "a_filter1_envmod": 16.0, "a_filter1_keytrack": 0.5,
                          **env(2, 0.004, 0.6, 0.5, 0.4), **env(1, 0.006, 0.8, 0.9, 0.4), "a_portamento": seconds(0.02),
                          "polylimit": 8},
                         {}),
    # The glass pluck (arpeggios and bells over the chords): a narrow pulse and a triangle an octave up, through a 24 dB
    # low-pass thrown open and shut in a sixth of a second: hollow and bright, a bell's ring without a bell's clang.
    "house glass": ({**osc(1, shape=1.0, width=0.3), **osc(2, shape=-1.0, octave=1, level=0.5),
                     "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1800.0), "a_filter1_resonance": 0.2,
                     "a_filter1_envmod": 36.0, "a_filter1_keytrack": 0.7,
                     **env(2, 0.002, 0.15, 0.0, 0.2), **env(1, 0.002, 0.5, 0.0, 0.4), "polylimit": 16},
                    {"a_filter1_cutoff": [("velocity", 10.0)]}),
    # The warm pad: five saws over a triangle an octave down through a soft low-pass well under a kilohertz, opening and
    # closing half an octave each way in about seventeen seconds: the pad of the calm places, a bed rather than a shine.
    "house pad warm": ({**osc(1, voices=5, detune=0.15), **osc(2, shape=-1.0, octave=-1, level=0.6),
                        "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(900.0), "a_filter1_resonance": 0.1,
                        "a_filter1_keytrack": 0.3, "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.06), "a_lfo6_trigmode": 0,
                        **env(1, 1.2, 1.0, 0.9, 2.5), "polylimit": 16},
                       {"a_filter1_cutoff": [("scene lfo1", 8.0)]}),
    # The hollow pad: squares, three a little apart and one an octave down, through a resonant 24 dB low-pass; a slow
    # triangle moves the squares' width (the hollowness itself breathing) and a slower sine the filter.
    "house pad hollow": ({**osc(1, shape=1.0, width=0.5, voices=3, detune=0.12), **osc(2, shape=1.0, width=0.5, octave=-1, level=0.5),
                         "a_filter1_type": LP24, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(1200.0), "a_filter1_resonance": 0.35,
                         "a_filter1_keytrack": 0.4, "a_lfo6_shape": 1, "a_lfo6_rate": rate(0.1), "a_lfo6_trigmode": 0,
                         "a_lfo7_shape": 0, "a_lfo7_rate": rate(0.05), "a_lfo7_trigmode": 0,
                         **env(1, 0.8, 1.0, 0.85, 2.0), "polylimit": 16},
                        {"a_osc1_param1": [("scene lfo1", 0.3)], "a_filter1_cutoff": [("scene lfo2", 6.0)]}),
    # The glass pad: triangles a little apart and narrow pulses an octave up, high-passed at 250 Hz and open on top, its
    # filter turning slowly: air and shimmer over the chords, nothing under them.
    "house pad glass": ({**osc(1, shape=-1.0, voices=3, detune=0.08), **osc(2, shape=1.0, width=0.25, octave=1, voices=3, detune=0.15, level=0.35),
                        "a_filter1_type": LP12, "a_filter1_subtype": 0, "a_filter1_cutoff": hz(3000.0), "a_filter1_resonance": 0.1,
                        "a_filter2_type": HP12, "a_filter2_subtype": 0, "a_filter2_cutoff": hz(200.0),
                        "a_lfo6_shape": 0, "a_lfo6_rate": rate(0.12), "a_lfo6_trigmode": 0,
                        **env(1, 1.0, 1.0, 0.9, 3.0), "polylimit": 16},
                       {"a_filter1_cutoff": [("scene lfo1", 7.0)]}),     # (14 to 16 dB brighter than the factory pad at 5-10 kHz, open to 5 kHz: shut lower)
    # The chord stab: three saws and a square through a 24 dB ladder, a quick envelope snapping it open and the note gone
    # in under half a second, so the chords are struck and leave room: a deep house stab, not a held organ.
    "house stab": ({**osc(1, voices=3, detune=0.1), **osc(2, shape=1.0, pitch=0.05, level=0.5),
                    "a_filter1_type": LADDER, "a_filter1_subtype": 3, "a_filter1_cutoff": hz(500.0), "a_filter1_resonance": 0.2,
                    "a_filter1_envmod": 36.0, "a_filter1_keytrack": 0.4,
                    **env(2, 0.003, 0.18, 0.1, 0.15), **env(1, 0.002, 0.4, 0.0, 0.2), "polylimit": 16},
                   {}),
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
    for key, value in values.items():
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


def state(name: str, surge: Path) -> bytes:
    """What Surge keeps as its state for the design: its header with the XML's new size, the XML, and the base's
    wavetables (none in the empty saw)."""
    sizes, _, tail = _split((surge / BASE).read_bytes())
    body = xml(name, surge).encode("utf-8")
    return b"sub3" + struct.pack("<I", len(body)) + sizes + body + tail
