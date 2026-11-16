"""The sounds: which real instruments play what the writers write.

The writers name their instruments ("violins", "horns", "harp", "kit orchestra"). Here each
name is given its PLAYERS: recorded instruments from the sample sets on the drive, played by
REAPER's sampler, and patches of the Surge XT synth. A written instrument can have several: the
bowed recording for its long notes and the short-bow one for its quick notes; one section for
its low notes and another for its high ones; a synth underneath.

RECORDED is every recorded instrument there is (a folder of single notes, and how to play
them). STROKES and KITS are the drums, DRUMS the big drums made of several. SOUNDS is the
writers' names. Each recorded instrument is written out as an instrument for the sfizz sampler
(studio.sfz: sections of several players, swells that change the tone, no two notes alike) and
sits on a REAPER track with the effects its family gets (`chain`). `build` writes them all,
`levels` measures how loud each one is so that they can be set level with each other, and
`lines` turns one written voice into the REAPER tracks that play it.

The sample sets: VSCO 2 Community Edition and VCSL (Versilian Studios, CC0). See
tools/stems/README.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import desk, reaper, samples, sfz
from .samples import SAMPLES, Patch
from .score import Note, Voice

PATCHES = desk.VAR / "reaper" / "patches"          # each recorded instrument as read (kept, since reading measures every recording)
LEVELS = desk.TEMPLATES / "levels.json"            # how many dB each template is turned by, to play at LEVEL
LEVEL = -30.0                                      # LUFS: every instrument alone, at a firm strength, is brought to this
V2, VC = "vsco2/", "vcsl/"
_STR, _WW, _BR = V2 + "Strings/", V2 + "Woodwinds/", V2 + "Brass/"
_EDGE = VC + "Aerophones/Edge-blown Aerophones/"
_ZITH = VC + "Chordophones/Zithers/"
_COMP = VC + "Chordophones/Composite Chordophones/"
_IDIO = VC + "Idiophones/Struck Idiophones/"
_PLUCK = VC + "Idiophones/Plucked Idiophones/"
_MEMB = VC + "Membranophones/Struck Membranophones/"

LONG = dict(attack=70.0, release=330.0, floor=-8.0)            # a bow or a breath: speaks softly, rings on a little
SLOW = dict(attack=260.0, release=560.0, floor=-8.0)           # the same, swelling in
WIND = dict(attack=35.0, release=220.0, floor=-8.0)
SHORT = dict(held=False, release=350.0, floor=-10.0)           # one stroke: the recording plays to its end
RINGS = dict(held=False, release=600.0, floor=-12.0)           # plucked or struck and left to ring
DAMPED = dict(held=True, release=160.0, floor=-12.0, loops=False)      # struck, and stopped when the key is let go

# name -> (folder of recordings under var/samples, how they are played)
RECORDED: dict[str, tuple[str, dict]] = {
    # --- strings (sections of VSCO 2; its double bass and one violin are solo players) ---
    "violins long": (_STR + "Violin Section/susVib", LONG), "violins slow": (_STR + "Violin Section/susVib", SLOW),
    "violins short": (_STR + "Violin Section/Spic", SHORT), "violins pizz": (_STR + "Violin Section/Pizz", RINGS),
    "violins trem": (_STR + "Violin Section/Trem", LONG),
    "violas long": (_STR + "Viola Section/susvib", LONG), "violas slow": (_STR + "Viola Section/susvib", SLOW),
    "violas short": (_STR + "Viola Section/spic", SHORT), "violas pizz": (_STR + "Viola Section/pizz", RINGS),
    "violas trem": (_STR + "Viola Section/trem", LONG),
    "celli long": (_STR + "Cello Section/susvib", LONG), "celli slow": (_STR + "Cello Section/susvib", SLOW),
    "celli short": (_STR + "Cello Section/spic", SHORT), "celli pizz": (_STR + "Cello Section/pizzT", RINGS),
    "celli trem": (_STR + "Cello Section/trem", dict(LONG, like="celli long")),
    "basses long": (_STR + "Solo Contrabass/SusVib", LONG), "basses slow": (_STR + "Solo Contrabass/SusVib", SLOW),
    "basses short": (_STR + "Solo Contrabass/Spic", SHORT), "basses pizz": (_STR + "Solo Contrabass/Pizz", RINGS),
    "basses trem": (_STR + "Solo Contrabass/Trem", LONG),
    "violin long": (_STR + "Solo Violin/Arco Vib", dict(LONG, attack=45.0)), "violin short": (_STR + "Solo Violin/spic", SHORT),
    "violin pizz": (_STR + "Solo Violin/Pizz", RINGS),
    # --- woodwinds ---
    "flute long": (_WW + "Flute/susvib", WIND), "flute plain": (_WW + "Flute/susNV", WIND), "flute warm": (_WW + "Flute/expvib", WIND),
    "flute short": (_WW + "Flute/stac", SHORT),
    "piccolo long": (_WW + "Piccolo/Sus", WIND), "piccolo short": (_WW + "Piccolo/Stac", SHORT),
    "oboe long": (_WW + "Oboe/Vib", WIND), "oboe plain": (_WW + "Oboe/Sus", WIND), "oboe short": (_WW + "Oboe/Stacc", SHORT),
    "clarinet long": (_WW + "Clarinet/susLong", WIND), "clarinet short": (_WW + "Clarinet/stac", SHORT),
    "bassoon long": (_WW + "Bassoon/vib", WIND), "bassoon plain": (_WW + "Bassoon/sus", WIND), "bassoon short": (_WW + "Bassoon/stac", SHORT),
    "recorder high long": (_EDGE + "Baroque Soprano Recorder/Sustain", WIND), "recorder high short": (_EDGE + "Baroque Soprano Recorder/Staccato", SHORT),
    "recorder long": (_EDGE + "Baroque Alto Recorder/SusVib", WIND), "recorder short": (_EDGE + "Baroque Alto Recorder/Staccato", SHORT),
    "recorder low long": (_EDGE + "Baroque Tenor Recorder/SusVib", WIND), "recorder low short": (_EDGE + "Baroque Tenor Recorder/Staccato", SHORT),
    "recorder bass long": (_EDGE + "Baroque Bass Recorder/SusVib", WIND),
    "ocarina long": (_EDGE + "Ocarina, Small/Sustain", WIND), "ocarina short": (_EDGE + "Ocarina, Small/Staccato", SHORT),
    # --- brass ---
    "horn long": (_BR + "F Horn/sus", dict(WIND, attack=45.0, release=260.0)), "horn short": (_BR + "F Horn/stac", SHORT),
    "horn muted": (_BR + "F Horn/mute", WIND),
    "trumpet long": (_BR + "Trumpet/susvib", WIND), "trumpet plain": (_BR + "Trumpet/sus", WIND), "trumpet short": (_BR + "Trumpet/stac", SHORT),
    "trombone long": (_BR + "Tenor Trombone/sus", dict(WIND, attack=45.0)), "trombone short": (_BR + "Tenor Trombone/stac", SHORT),
    "tuba long": (_BR + "Tuba/sus", dict(WIND, attack=50.0)), "tuba short": (_BR + "Tuba/stac", SHORT),
    # --- keys and things plucked ---
    "organ loud": (_EDGE + "Pipe Organ/Loud", dict(attack=25.0, release=260.0, floor=-3.0)),
    "organ quiet": (_EDGE + "Pipe Organ/Quiet", dict(attack=25.0, release=260.0, floor=-3.0)),
    "small organ": (_EDGE + "Renaissance Organ/8'", dict(attack=15.0, release=140.0, floor=-3.0)),
    "small organ high": (_EDGE + "Renaissance Organ/4'", dict(attack=15.0, release=140.0, floor=-3.0)),
    "harp": (_COMP + "Concert Harp", RINGS), "folk harp": (_COMP + "Folk Harp", RINGS),
    "strumstick": (_COMP + "Strumstick/Finger", RINGS),
    "psaltery": (_ZITH + "Psaltery, Bowed and Plucked/Pluck", RINGS), "psaltery bowed": (_ZITH + "Psaltery, Bowed and Plucked/LongBow", LONG),
    "zither": (_ZITH + "Dan Tranh/Normal", RINGS), "zither bent": (_ZITH + "Dan Tranh/Vibrato", RINGS),
    "harpsichord": (_ZITH + "Harpsichord, French/Sustains", DAMPED),
    "piano": (_ZITH + "Grand Piano, Steinway B/NoSus", dict(DAMPED, release=220.0)),
    "kalimba": (_PLUCK + "Kalimba, Tanzania", RINGS), "mbira": (_PLUCK + "Mbira dzaVadzimu Nyamaropa, Zimbabwe, Low B", RINGS),
    # --- tuned things that are struck ---
    "glock": (_IDIO + "Glockenspiel", RINGS), "tube glock": (_IDIO + "Tubular Glockenspiel", RINGS),
    "xylophone": (_IDIO + "Xylophone/Medium Mallets", RINGS), "marimba": (_IDIO + "Marimba", RINGS),
    "balafon": (_IDIO + "Balafon/Soft Mallet", RINGS),
    "vibes": (_IDIO + "Vibraphone/Soft Mallets", RINGS), "vibes bowed": (_IDIO + "Vibraphone/Bowed", dict(LONG, attack=200.0, release=900.0)),
    "tubular bells": (_IDIO + "Tubular Bells 1", RINGS), "hand chimes": (_IDIO + "Hand Chimes", RINGS),
}
KETTLES = {"timpani": _MEMB + "Timpani 2/Hit"}

# A drum that is played at several pitches (the writers' taiko, great drum, toms): one hit,
# shifted. name -> (the hits, the note the hit is taken to be, lowest and highest note it plays).
TUNED_DRUMS: dict[str, tuple[str, int, int, int]] = {
    "great drum": (_MEMB + "Bass Drum 1/BDrumNew_hit_*.wav", 40, 28, 60),
    "war drum": (_MEMB + "Tom 2/Mallet/TomL_HitM_*.wav", 45, 31, 62),
    "tom mallet": (_MEMB + "Tom 1/Mallet/TomH_HitM_*.wav", 52, 40, 74),
    "frame drum": (_MEMB + "Frame Drum/HDrumL_Hit_v*.wav", 45, 33, 62),
}

# What is hit for each stroke a writer can ask of a kit.
STROKES: dict[str, str] = {
    "boom": _MEMB + "Bass Drum 1/BDrumNew_hit_*.wav",
    "snare": _MEMB + "Snare Drum, Modern 1/Snare2_HitSN_*.wav",
    "crash": _IDIO + "Clash Cymbals 1/cymbal_crash1_[pmf]*.wav",
    "crash2": _IDIO + "Suspended Cymbal 1/susCymb1_hit_[pmf]*.wav",
    "tamb": _IDIO + "Tambourine 1/Tamb1_Hit_*.wav",
    "ting": _IDIO + "Triangles/Triangle1_Hit_v*.wav",
    "clack": _IDIO + "Claps/Clap_rr*.wav",
    "shake": _IDIO + "Shaker, Small/Mid_ShakerDouble_Down_*.wav",
    "jingle": _IDIO + "Sleigh Bells/Sleighbells_Hit_*.wav",
    "castanet": _IDIO + "Woodblock/wood_click3_vl*.wav",
    "tick": _IDIO + "Claves/Claves1_Hit_*.wav",
    "high": _MEMB + "Bongos/BongoH_Hit1_*.wav",
    "low": _MEMB + "Bongos/BongoL_Hit1_*.wav",
    "deep": _MEMB + "Frame Drum/HDrumL_Hit_v*.wav",
    "mute": _MEMB + "Frame Drum/HDrumL_HitMuted_*.wav",
    "conga": _MEMB + "Conga/Conga_HitN_*.wav",
    "conga low": _MEMB + "Conga/Tumba_HitN_*.wav",
    "block": _IDIO + "Woodblock/wood_click_[pmf]*.wav",
    "block low": _IDIO + "Slit Drum/LogDrumLo_*.wav",
    "guiro": _IDIO + "Guiro/Guiro_Hit_*.wav",
    "bell": _IDIO + "Agogo Bells/Agogo_High_*.wav",
    "hat": _IDIO + "Hi-Hat Cymbal/HiHat_HitC_*.wav",
    "hat open": _IDIO + "Hi-Hat Cymbal/HiHat_HitO_rr*.wav",
    "ride": _IDIO + "Suspended Cymbal 1/susCymb1_hit_stick_*.wav",
    "tom": _MEMB + "Tom 1/Stick/TomH_HitS_*.wav",
    "tom low": _MEMB + "Tom 2/Stick/TomL_HitS_*.wav",
    "tom high": _MEMB + "Tom 1/Mallet/TomH_HitM_*.wav",
    "cowbell": _IDIO + "Cowbells/Cowbell1_Hit_*.wav",
}
# Where a kit's stroke is something else than the usual.
KIT_STROKES: dict[str, dict[str, str]] = {
    "march": {"snare": _MEMB + "Snare Drum, Rope Tension/Low/RopeSnare_low_sn_Main_*.wav",
              "clack": _MEMB + "Legacy Snares/drum3_marching/snare3_click_*.wav"},
    "folk": {"boom": _MEMB + "Frame Drum/HDrumL_Hit_v*.wav", "snare": _MEMB + "Frame Drum/HDrumS_Hit_v*.wav",
             "crash": _IDIO + "Suspended Cymbal 1/susCymb1_hit_[pmf]*.wav", "clack": _IDIO + "Claps/Clap_rr*.wav"},
    "hands": {"boom": _MEMB + "Conga/Tumba_HitN_*.wav", "snare": _MEMB + "Conga/Conga_HitN_*.wav",
              "clack": _MEMB + "Conga/Conga_HitFM_*.wav", "ting": _IDIO + "Agogo Bells/Agogo_High_*.wav",
              "shake": _IDIO + "Cabasa/*.wav", "jingle": _IDIO + "Shaker, Small/Mid_ShakerHighFaster_Down_*.wav",
              "crash": _IDIO + "Suspended Cymbal 1/susCymb1_hit_[pmf]*.wav"},
    "wood": {"boom": _IDIO + "Slit Drum/LogDrumLo_*.wav", "snare": _IDIO + "Slit Drum/LogDrumHi_*.wav",
             "tamb": _IDIO + "Cabasa/*.wav", "ting": _IDIO + "Woodblock/wood_click_[pmf]*.wav",
             "clack": _IDIO + "Claves/Claves1_Hit_*.wav", "crash": _IDIO + "Suspended Cymbal 1/susCymb1_hit_[pmf]*.wav"},
}


# Big drums made of several drums struck as one by several players (studio.sfz.layered):
# name -> (the drums: the strokes, the written note at which they sound as recorded, level in
# dB), the lowest and highest written note, how many players.
_RUSTY = "big-rusty-drums/Samples/"            # Karoryfer's Big Rusty Drums (CC0): a 24-inch kick, a 22-inch kick hung as a tom, an 18-inch floor tom
DRUMS: dict[str, tuple[list[tuple[str, int, float]], int, int, int]] = {
    # The war drums: the 22-inch drum struck with mallets (the room's microphones and the close one), the undamped
    # 24-inch kick under it for the depth, and the 18-inch floor tom. Written note 36 is the biggest.
    "war drums": ([(_RUSTY + "tom_22/mallet/oh/t22_m_vl*_rr*.flac", 43, 0.0), (_RUSTY + "tom_22/mallet/cl/t22_m_vl*_rr*.flac", 43, -4.0),
                   (_RUSTY + "kick_24_nodamp/kick/oh/k_nodamp_vl*_rr*.flac", 41, -2.0), (_RUSTY + "tom_18/mallet/oh/t18_m_vl*_rr*.flac", 47, -4.0)],
                  28, 54, 3),
    "frame drums": ([(_MEMB + "Frame Drum/HDrumL_Hit_v*.wav", 48, 0.0), (_MEMB + "Frame Drum/HDrumS_Hit_v*.wav", 53, -2.0),
                     (_RUSTY + "tom_15/mallet/oh/t15_m_vl*_rr*.flac", 55, -6.0)], 40, 64, 3),
    "boom": ([(_RUSTY + "kick_24_nodamp/kick/oh/k_nodamp_vl*_rr*.flac", 46, 0.0), (_RUSTY + "tom_22/mallet/oh/t22_m_vl*_rr*.flac", 50, -3.0),
              (_MEMB + "Bass Drum 1/BDrumNew_hit_*.wav", 46, -3.0)], 24, 50, 2),
}
# Single things that are struck, each on one written note: name -> (the strokes, the note).
STRUCK: dict[str, tuple[str, int]] = {
    "gong": (_IDIO + "Gong 1/gong_[pmf]*.wav", 48),
    "anvil": (_IDIO + "Anvil/Anvil_Hit1_*.wav", 60),
}
# A cymbal swelling up to a moment: the recordings, by how long each takes to get there.
SWELLS = {1.5: _IDIO + "Suspended Cymbal 1/susCymb1_cresc_1.5s.wav", 2.0: _IDIO + "Suspended Cymbal 1/susCymb1_cresc_2s.wav",
          4.0: _IDIO + "Suspended Cymbal 1/susCymb1_cresc_4s.wav", 7.5: _IDIO + "Suspended Cymbal 1/susCymb1_cresc_7.5s.wav"}


@dataclass(frozen=True)
class Player:
    """One of the real instruments that play a written one, and which of its notes it takes."""
    name: str                  # a recorded instrument, a big drum, or "surge:<patch file under Surge's patch folders>"
    notes: str = "all"         # all | long | short
    low: int = 0               # only the written notes from here
    high: int = 127            # to here
    over: float = 0.0          # only the notes struck at least this hard (0 to 1)
    under: float = 1.01        # and less hard than this
    gain: float = 0.0          # dB
    octave: int = 0            # played this many octaves away from where it is written
    seat: float | None = None  # where it sits, -1 left to 1 right; None leaves it to the writer


@dataclass(frozen=True)
class Sound:
    players: tuple[Player, ...]
    short: float = 0.26        # seconds: a note shorter than this is a short note


def _bowed(name: str, seat: float, long: str = "long") -> Sound:
    players = (Player("%s %s" % (name, long), "long", seat=seat), Player(name + " short", "short", seat=seat))
    if name in ("violins", "violas", "celli"):
        players += (Player(SILK, "long", gain=-13.0, seat=seat * 0.5),)        # silk under the section: felt more than heard
    return Sound(players)


def _blown(name: str, seat: float, long: str = "long") -> Sound:
    return Sound((Player("%s %s" % (name, long), "long", seat=seat), Player(name + " short", "short", seat=seat)), short=0.2)


def _all_strings(way: str) -> Sound:
    """The whole string orchestra under one name: each note goes to the sections it lies well
    for, so the middle of the range is two sections together."""
    return Sound((Player("basses " + way, high=50, gain=-2.0, seat=0.45), Player("celli " + way, low=36, high=64, gain=-2.0, seat=0.3),
                  Player("violas " + way, low=53, high=76, gain=-2.0, seat=0.12), Player("violins " + way, low=62, gain=-2.0, seat=-0.4)))


def _strings(long: str) -> Sound:
    longs, shorts = _all_strings(long).players, _all_strings("short").players
    return Sound(tuple(Player(each.name, "long", each.low, each.high, gain=each.gain, seat=each.seat) for each in longs)
                 + tuple(Player(each.name, "short", each.low, each.high, gain=each.gain, seat=each.seat) for each in shorts))


# Synths. "zyn:<preset>" is a ZynAddSubFX patch by the name REAPER lists it under; "surge:<file>" a Surge XT patch file.
CHOIR = "zyn:Fantasy: 0011-Space Choir1.xiz"            # a wide, diffuse choir (PADsynth)
OOHS = "zyn:Collection: 0121-Breathy Ahh.xiz"
SILK = "zyn:Collection: 0024-Full Strings.xiz"         # a string pad that goes under the recorded sections
SUB = "surge:patches_factory/Basses/Sub 1.fxp"
SOUNDS: dict[str, Sound] = {
    "violins": _bowed("violins", -0.4), "violins slow": _bowed("violins", -0.4, "slow"),
    "violas": _bowed("violas", 0.12), "celli": _bowed("celli", 0.3), "celli slow": _bowed("celli", 0.3, "slow"),
    "basses": _bowed("basses", 0.45), "basses slow": _bowed("basses", 0.45, "slow"),
    "strings": _strings("long"), "strings slow": _strings("slow"),
    "tremolo": _all_strings("trem"), "pizzicato": _all_strings("pizz"),
    "celli pizz": Sound((Player("celli pizz", seat=0.3),)), "basses pizz": Sound((Player("basses pizz", seat=0.45),)),
    "acoustic bass": Sound((Player("basses pizz", seat=0.1),)),
    "violin": _bowed("violin", -0.25), "fiddle": _bowed("violin", -0.15),
    "viola": Sound((Player("violas long", "long", gain=-2.0, seat=0.1), Player("violas short", "short", gain=-2.0, seat=0.1))),
    "cello": Sound((Player("celli long", "long", gain=-2.0, seat=0.25), Player("celli short", "short", gain=-2.0, seat=0.25))),
    "flute": _blown("flute", -0.15), "piccolo": _blown("piccolo", -0.2), "oboe": _blown("oboe", 0.12),
    "english horn": Sound((Player("oboe plain", "long", low=56, seat=0.15), Player("oboe short", "short", low=56, seat=0.15),
                           Player("bassoon plain", "long", high=55, seat=0.15), Player("bassoon short", "short", high=55, seat=0.15)), short=0.2),
    "clarinet": _blown("clarinet", -0.1), "bassoon": _blown("bassoon", 0.2),
    "recorder": Sound((Player("recorder long", "long", high=83, seat=-0.1), Player("recorder short", "short", high=83, seat=-0.1),
                       Player("recorder high long", "long", low=84, seat=-0.1), Player("recorder high short", "short", low=84, seat=-0.1)), short=0.2),
    "whistle": _blown("recorder high", -0.05),
    "pan flute": Sound((Player("flute plain", "long", seat=-0.1), Player("flute short", "short", seat=-0.1), Player("ocarina long", "long", gain=-9.0, seat=0.1)), short=0.2),
    "shakuhachi": Sound((Player("flute warm", "long", seat=-0.1), Player("flute short", "short", seat=-0.1)), short=0.2),
    "ocarina": _blown("ocarina", 0.05),
    "trumpet": _blown("trumpet", 0.2), "trombone": _blown("trombone", 0.32), "tuba": _blown("tuba", 0.38),
    "horns": _blown("horn", -0.28),
    "brass": Sound((Player("trumpet long", "long", low=58, gain=-2.0, seat=0.2), Player("trumpet short", "short", low=58, gain=-2.0, seat=0.2),
                    Player("trombone long", "long", high=66, gain=-2.0, seat=0.32), Player("trombone short", "short", high=66, gain=-2.0, seat=0.32),
                    Player("horn long", "long", low=41, high=74, gain=-5.0, seat=-0.28)), short=0.2),
    "harp": Sound((Player("harp", seat=-0.45),)), "celesta": Sound((Player("tube glock", seat=-0.3),)),
    "glock": Sound((Player("glock", seat=0.25),)), "music box": Sound((Player("kalimba", octave=1, seat=-0.1),)),
    "vibes": Sound((Player("vibes", seat=0.3),)), "marimba": Sound((Player("marimba", seat=0.3),)),
    "xylophone": Sound((Player("xylophone", seat=0.3),)),
    "bells": Sound((Player("tubular bells", seat=0.35),)),
    "church bell": Sound((Player("tubular bells", seat=0.1), Player("hand chimes", gain=-8.0, octave=1, seat=0.1))),
    "dulcimer": Sound((Player("psaltery", seat=-0.2),)),
    "organ": Sound((Player("organ quiet", under=0.62, seat=0.0), Player("organ loud", over=0.62, seat=0.0))),
    "harpsichord": Sound((Player("harpsichord", seat=-0.15),)),
    "accordion": Sound((Player("small organ", seat=0.15), Player("small organ high", gain=-9.0, seat=0.15))),
    "guitar": Sound((Player("folk harp", seat=-0.25),)), "steel guitar": Sound((Player("strumstick", seat=-0.25),)),
    "mandolin": Sound((Player("strumstick", octave=1, seat=0.2),)),
    "twelve string": Sound((Player("strumstick", seat=-0.25), Player("psaltery", octave=1, gain=-7.0, seat=-0.25))),
    "sitar": Sound((Player("zither bent", seat=-0.1),)), "koto": Sound((Player("zither", seat=-0.1),)),
    "kalimba": Sound((Player("kalimba", seat=0.2),)), "banjo": Sound((Player("strumstick", seat=0.25),)),
    "bagpipe": Sound((Player("oboe plain", seat=0.0), Player("small organ", gain=-8.0, seat=0.0))),
    "shenai": Sound((Player("oboe plain", seat=0.05),)),
    "choir": Sound((Player(CHOIR, gain=-3.0, seat=0.0),)), "oohs": Sound((Player(OOHS, gain=-3.0, seat=0.0),)),
    "timpani": Sound((Player("timpani", seat=-0.1),)),
    "taiko": Sound((Player("war drums", seat=0.0),)),
    "great drum": Sound((Player("great drum", seat=0.0),)), "melodic tom": Sound((Player("tom mallet", seat=0.15),)),
    "war drums": Sound((Player("war drums", seat=0.0),)), "frame drums": Sound((Player("frame drums", seat=0.1),)),
    "boom": Sound((Player("boom", seat=0.0), Player(SUB, gain=-3.0, octave=-1, seat=0.0))),
    "gong": Sound((Player("gong", seat=0.2),)), "anvil": Sound((Player("anvil", seat=-0.2),)),
}


# ---------------------------------------------------------------------------------------------
# Each recorded instrument as an instrument for the sampler
# ---------------------------------------------------------------------------------------------
def _file(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _.-]+", " ", name).strip()


def patch(name: str) -> Patch:
    """A recorded instrument by name, read from its folder (and kept, since reading it means
    measuring every recording)."""
    kept = PATCHES / (_file(name) + ".json")
    if kept.is_file():
        return Patch.load(kept)
    if name in KETTLES:
        made = samples.kettles(SAMPLES / KETTLES[name], name, only="main")
    elif name in RECORDED:
        folder, how = RECORDED[name]
        how = dict(how)
        loops = how.pop("loops", True)
        like = how.pop("like", None)
        if like:
            how["calls"] = patch(like).calls          # it names its octaves as its sister does
        made = samples.pitched(SAMPLES / folder, name, **how)
        if not loops:
            made.zones = [samples.Zone(**dict(zone.__dict__, loop=0.0, until=1.0)) for zone in made.zones]
    elif name in TUNED_DRUMS:
        pattern, root, low, high = TUNED_DRUMS[name]
        made = samples.struck(sorted(SAMPLES.glob(pattern)), name, root, release=900.0)
        made.zones = [samples.Zone(**dict(zone.__dict__, low=low, high=high, root=root)) for zone in made.zones]
    elif name in STRUCK:
        pattern, note = STRUCK[name]
        made = samples.struck(sorted(SAMPLES.glob(pattern)), name, note, release=4000.0)
    else:
        raise KeyError("There is no recorded instrument called %r" % name)
    made.save(kept)
    return made


def family(name: str) -> str:
    """Which kind of instrument a recorded one is: it settles how it is written for the sampler
    and what effects go on its channel."""
    first = name.split(" ")[0]
    if name in DRUMS or name in TUNED_DRUMS or name in KETTLES or name in STRUCK or name.startswith("kit "):
        return "drums"
    if first in ("violins", "violas", "celli", "basses"):
        return "strings short" if name.endswith(("short", "pizz")) else "strings"
    if first == "violin":
        return "solo strings short" if name.endswith(("short", "pizz")) else "solo strings"
    if first in ("flute", "piccolo", "oboe", "clarinet", "bassoon", "recorder", "ocarina"):
        return "woodwind short" if name.endswith("short") else "woodwind"
    if first in ("horn", "trumpet", "trombone", "tuba"):
        return "brass short" if name.endswith("short") else "brass"
    if name.startswith(("organ", "small organ")):
        return "organ"
    if name in ("psaltery bowed", "vibes bowed"):
        return "bowed metal"
    if name in ("glock", "tube glock", "vibes", "tubular bells", "hand chimes", "kalimba", "mbira"):
        return "bells"
    if name in ("xylophone", "marimba", "balafon"):
        return "mallets"
    if name in ("harpsichord", "piano"):
        return "keys"
    return "plucked"


def kit_patches(name: str, strokes: dict[str, int]) -> list[tuple[int, Patch]]:
    """A kit's strokes, each as a patch on its note."""
    out, taken = [], set()
    special = KIT_STROKES.get(name, {})
    for stroke, note in strokes.items():
        if note in taken:
            continue
        taken.add(note)
        pattern = special.get(stroke, STROKES.get(stroke))
        if pattern is None:
            raise KeyError("Nothing is set down to be hit for the stroke %r" % stroke)
        files = sorted(SAMPLES.glob(pattern))
        if not files:
            raise FileNotFoundError("No recordings match %s (for %s of the %s kit)" % (pattern, stroke, name))
        out.append((note, samples.struck(files, "%s %s" % (name, stroke), note, release=1500.0)))
    return out


def instrument(name: str) -> Path:
    """The sampler instrument (an SFZ file) for a recorded instrument, a big drum or a kit
    ("kit orchestra"), written if it is not there yet."""
    made = sfz.FOLDER / (_file(name) + ".sfz")
    if made.is_file():
        return made
    kind = family(name)
    if name.startswith("kit "):
        from .orchestra import KITS
        strokes = KITS[name[4:]][1]
        hats = {strokes[each]: 1 for each in ("hat", "hat open") if each in strokes}
        text = sfz.kit(kit_patches(name[4:], strokes), chokes=hats)
    elif name in DRUMS:
        parts, low, high, players = DRUMS[name]
        made_parts = []
        for pattern, centre, level in parts:
            files = sorted(SAMPLES.glob(pattern))
            if not files:
                raise FileNotFoundError("No recordings match %s (for %s)" % (pattern, name))
            made_parts.append((samples.struck(files, name, centre, release=1500.0), 0.0, level))
        text = sfz.layered(made_parts, low, high, players=players)
    else:
        read = patch(name)
        if read.held and any(zone.loop for zone in read.zones):
            first = name.split(" ")[0]
            if kind == "strings":
                bite = patch(first + " short") if name.endswith(("long", "slow")) else None
                text = sfz.held(read, players=3, dark=1400.0, opens=4200.0, range_db=16.0, drift=3.5, bite=bite)
            elif kind == "solo strings":
                text = sfz.held(read, players=1, dark=1500.0, opens=4000.0, range_db=16.0, drift=3.0)
            elif kind == "woodwind":
                text = sfz.held(read, players=1, dark=1900.0, opens=3600.0, range_db=20.0 if len({zone.soft for zone in read.zones}) == 1 else 15.0, drift=2.5)
            elif kind == "brass":
                text = sfz.held(read, players=2 if name.startswith("horn") else 1, dark=850.0, opens=5200.0, range_db=14.0, drift=2.0, spread=30.0)
            elif kind == "organ":
                text = sfz.held(read, players=1, dark=6000.0, opens=1500.0, range_db=8.0, drift=0.6)
            else:
                text = sfz.held(read, players=2, dark=1800.0, opens=3900.0, range_db=16.0, drift=2.5)
        elif kind == "strings short":
            text = sfz.struck(read, dull=1500.0, opens=4800.0, players=3, spread=42.0)
        elif kind == "drums":
            text = sfz.struck(read, dull=700.0, opens=6200.0)
        elif kind in ("bells", "mallets"):
            text = sfz.struck(read, dull=2000.0, opens=4600.0)
        else:
            text = sfz.struck(read, dull=1200.0, opens=5200.0)
    return sfz.write(_file(name), text)


# ---------------------------------------------------------------------------------------------
# The effects on each instrument's channel
# ---------------------------------------------------------------------------------------------
def _db(value: float) -> float:
    return 10 ** (value / 20.0)


def equalise(*, low_cut: float = 0.0, high_cut: float = 0.0, low_shelf: tuple[float, float] | None = None,
             high_shelf: tuple[float, float] | None = None, bands: tuple[tuple[float, float, float], ...] = ()) -> str:
    """An equaliser (x42's parametric): cuts in Hz, shelves as (Hz, dB), up to four bands as
    (Hz, dB, width in octaves), given from low to high."""
    put: dict[str, float] = {}
    if low_cut:
        put.update(HighPass=1, HPfreq=max(low_cut, 5.0))
    if high_cut:
        put.update(LowPass=1, LPfreq=high_cut)
    if low_shelf:
        put.update(LSfreq=min(max(low_shelf[0], 25.0), 400.0), LSgain=low_shelf[1])
    if high_shelf:
        put.update(HSfreq=min(max(high_shelf[0], 1000.0), 16000.0), HSgain=high_shelf[1])
    # Its four sections each cover a part of the range: a band goes to the lowest free section that reaches it.
    reach = {1: (20.0, 2000.0), 2: (40.0, 4000.0), 3: (100.0, 10000.0), 4: (200.0, 20000.0)}
    free = [1, 2, 3, 4]
    for hz, gain, width in sorted(bands):
        section = next((each for each in free if reach[each][0] <= hz <= reach[each][1]), None)
        if section is None:
            raise ValueError("The equaliser has no section left for a band at %.0f Hz" % hz)
        free.remove(section)
        put.update({"freq%d" % section: hz, "gain%d" % section: gain, "q%d" % section: width})
    return desk.lv2("x42-eq - Parametric Equalizer Stereo", **put)


def ensemble(amount: float, *, voices: int = 6, rate: float = 0.35, depth: float = 2.5) -> str:
    """A chorus (Calf's multi chorus): a few players made to sound like more."""
    return desk.lv2("Calf Multi Chorus", voices=voices, min_delay=6.0, mod_depth=depth, mod_rate=rate, stereo=180.0, vphase=300.0,
                    amount=amount, dry=1.0 - 0.35 * amount)


def wide(side: float) -> str:
    """More of what differs between left and right (Calf's stereo tools): 1 leaves it as it is."""
    return desk.lv2("Calf Stereo Tools", slev=side)


def warm(amount: float) -> str:
    """Tape (Calf's tape simulator with its hiss and wobble off): rounds the peaks, thickens."""
    return desk.lv2("Calf Tape Simulator", level_in=0.33 * (1.0 + 1.6 * amount), level_out=1.0 / (1.0 + 0.9 * amount), mix=min(0.3 + 0.5 * amount, 1.0),
                    lowpass=12000.0, noise=0.0, mechanical=0.0, magnetical=1.0)


def punch(strike: float, body: float) -> str:
    """A transient shaper (Calf's): more of the stroke, more or less of what rings after it."""
    return desk.lv2("Calf Transient Designer", attack_time=20.0, attack_boost=strike, release_time=250.0, release_boost=body, lookahead=0, mix=1.0)


def squeeze(threshold: float, ratio: float, attack: float, release: float, makeup: float = 0.0) -> str:
    """A compressor (Steve Harris's SC4): threshold and make-up in dB, times in milliseconds."""
    return desk.lv2("SC4", rms_peak=0.0, attack=max(attack, 1.5), release=release, threshold=max(threshold, -30.0), ratio=ratio, knee=5.0,
                    makeup_gain=max(makeup, 0.0))


def echo(bpm: float, amount: float, *, left: int = 3, right: int = 3, again: float = 0.35) -> str:
    """A tempo echo from side to side (Calf's vintage delay), counted in sixteenths: three is a dotted eighth."""
    return desk.lv2("Calf Vintage Delay", timing=0, bpm=min(max(bpm, 30.0), 300.0), subdiv=4, time_l=left, time_r=right, feedback=again, amount=amount,
                    dry=1.0, medium=1, mix_mode=1)


def ceiling(threshold: float = -1.0) -> str:
    return desk.lv2("x42-dpl - Digital Peak Limiter Stereo", threshold=threshold, release=0.05)


def row(depth: float) -> str:
    """Where on the stage a player sits, front to back (Dragonfly's early reflections): the
    further back, the more of the first echoes off the walls, the bigger they are, and the
    less of the top."""
    return desk.lv2("Dragonfly Early Reflections", dry_level=100.0 - 25.0 * depth, early_level=15.0 + 30.0 * depth, program=2,
                    size=14.0 + 18.0 * depth, width=110.0 - 20.0 * depth, low_cut=80.0 - 30.0 * depth, high_cut=13000.0 - 6500.0 * depth)


def drum_room() -> str:
    """A big drum room around the drums themselves (Dragonfly's room reverb)."""
    return desk.lv2("Dragonfly Room Reverb", dry_level=90.0, early_level=20.0, early_send=20.0, late_level=25.0, size=14.0, width=100.0,
                    predelay=16.0, decay=0.7, diffuse=40.0, spin=2.7, wander=10.0, in_high_cut=16000.0, early_damp=8000.0, late_damp=5000.0,
                    low_boost=60.0, boost_freq=300.0, in_low_cut=4.0)


LOW_CUT = {"violins": 170.0, "violas": 115.0, "celli": 58.0, "basses": 30.0, "violin": 175.0, "flute": 230.0, "piccolo": 480.0, "oboe": 210.0,
           "clarinet": 130.0, "bassoon": 52.0, "recorder": 220.0, "ocarina": 400.0, "horn": 60.0, "trumpet": 150.0, "trombone": 55.0, "tuba": 30.0}


def chain(name: str, bpm: float) -> list[str]:
    """The effects on a recorded instrument's channel, by its family."""
    kind = family(name)
    first = name.split(" ")[0]
    cut = LOW_CUT.get(first, 0.0)
    if kind == "strings":
        return [equalise(low_cut=cut, bands=((300.0, -1.5, 1.5), (3200.0, -2.5, 1.0)), high_shelf=(10000.0, 2.5)), ensemble(0.3), wide(1.3), warm(0.15)]
    if kind == "strings short":
        return [equalise(low_cut=cut, bands=((3200.0, -1.5, 1.0),), high_shelf=(10000.0, 1.5)), wide(1.2)]
    if kind.startswith("solo strings"):
        return [equalise(low_cut=cut, bands=((3000.0, -1.5, 1.0),), high_shelf=(10000.0, 1.5))]
    if kind.startswith("woodwind"):
        return [equalise(low_cut=cut, bands=((3000.0, -1.5, 1.0),), high_shelf=(10000.0, 1.5 if first in ("flute", "piccolo", "recorder") else 0.0))]
    if kind.startswith("brass"):
        return [equalise(low_cut=cut, low_shelf=(200.0, 1.5), bands=((3000.0, -2.5, 1.2),), high_shelf=(7000.0, -3.0)), warm(0.35)]
    if kind == "organ":
        return [equalise(low_cut=28.0, bands=((300.0, -2.0, 1.0),)), wide(1.25)]
    if kind == "bowed metal":
        return [equalise(low_cut=150.0), ensemble(0.4, voices=4, rate=0.2)]
    if kind == "bells":
        return [equalise(low_cut=250.0, high_shelf=(10000.0, 2.0)), ensemble(0.3, voices=3, rate=0.8, depth=1.2), echo(bpm, 0.2)]
    if kind == "mallets":
        return [equalise(low_cut=90.0), echo(bpm, 0.1)]
    if kind == "keys":
        return [equalise(low_cut=45.0, bands=((2500.0, -1.0, 1.0),))]
    if kind == "plucked":
        return [equalise(low_cut=70.0, high_shelf=(10000.0, 2.0)), ensemble(0.2, voices=3, rate=0.6, depth=1.2),
                echo(bpm, 0.1) if name in ("zither", "zither bent", "psaltery", "kalimba", "mbira") else ""]
    if name in ("war drums", "boom"):
        # Weight at 80 Hz, the box at 300 out, the crack of the stick up top; squeezed hard so the ring comes up; a big room.
        return [punch(0.4, 0.25), warm(0.6), equalise(low_cut=26.0, low_shelf=(85.0, 4.0), bands=((300.0, -3.5, 1.2), (4700.0, 5.0, 1.5))),
                squeeze(-22.0, 4.0, 14.0, 130.0, 4.0), drum_room(), wide(1.3)]
    if name == "frame drums":
        return [punch(0.3, 0.1), warm(0.3), equalise(low_cut=45.0, low_shelf=(110.0, 2.5), bands=((400.0, -2.5, 1.2), (4500.0, 3.0, 1.5))),
                squeeze(-20.0, 3.0, 14.0, 130.0, 2.0), drum_room()]
    if name in ("timpani", "great drum", "war drum", "tom mallet", "frame drum"):
        return [punch(0.25, 0.1), equalise(low_cut=30.0, low_shelf=(90.0, 3.0), bands=((300.0, -2.5, 1.2), (3500.0, 2.0, 1.5))),
                squeeze(-14.0, 3.0, 30.0, 150.0, 2.0), drum_room()]
    if name in ("gong", "anvil"):
        return [equalise(low_cut=60.0)]
    if name.startswith("kit "):
        return [punch(0.25, 0.05), equalise(low_cut=30.0, low_shelf=(80.0, 2.0), bands=((400.0, -2.0, 1.0), (5000.0, 1.5, 1.5))),
                squeeze(-18.0, 2.5, 12.0, 140.0, 1.5), drum_room()]
    return [equalise(low_cut=40.0)]


def synth_chain(player: str, bpm: float) -> list[str]:
    """The effects on a synth's channel."""
    if player in (CHOIR, OOHS):
        return [equalise(low_cut=120.0, bands=((350.0, -2.0, 1.5), (3000.0, -2.0, 1.0)), high_shelf=(11000.0, 2.5)), ensemble(0.5, voices=8, rate=0.2, depth=3.5),
                wide(1.4)]
    if player == SILK:
        return [equalise(low_cut=150.0, high_cut=9000.0, bands=((2500.0, -2.0, 1.0),)), wide(1.3)]
    if player == SUB:
        return [equalise(high_cut=260.0), squeeze(-18.0, 4.0, 25.0, 125.0, 2.0)]
    return []


def bus(channel: str) -> list[str]:
    """What is on a whole channel's folder: a little glue and tape, and a ceiling over the drums."""
    if channel == "drums":
        return [squeeze(-12.0, 2.0, 30.0, 200.0, 1.0), warm(0.3), ceiling(-2.0)]
    return [squeeze(-16.0, 2.0, 40.0, 300.0, 1.0), warm(0.12)]


def hall(seconds: float) -> str:
    """The hall at the foot of a channel's folder (Dragonfly's hall reverb, giving only what
    the room adds): a concert hall that rings `seconds`."""
    # Its "Large Bright Hall", with less ring in the bass and less wobble (its maker's advice for an orchestra).
    return desk.bare("hall", [desk.lv2("Dragonfly Hall Reverb", dry_level=0.0, early_level=0.0, late_level=100.0, size=min(24.0 + 7.5 * seconds, 58.0),
                                       width=100.0, delay=20.0, diffuse=90.0, low_cut=80.0, low_xo=400.0, low_mult=1.2, high_cut=8200.0,
                                       high_xo=5800.0, high_mult=0.5, spin=1.0, wander=15.0, decay=seconds, early_send=20.0, modulation=10.0)])


# ---------------------------------------------------------------------------------------------
# Building and measuring
# ---------------------------------------------------------------------------------------------
def template_of(player: str) -> str:
    """What a player's track template is called."""
    if player.startswith("surge:"):
        return _file("surge " + Path(player[6:]).stem)
    if player.startswith("zyn:"):
        return _file("zyn " + player[4:].replace(".xiz", "").replace(": ", " "))
    return _file(player)


def wanted(names: list[str] | None = None) -> list[str]:
    """Every player the given written instruments need (all of them, if none are given)."""
    out: list[str] = []
    for name in names or list(SOUNDS):
        for player in SOUNDS[name].players:
            if player.name not in out:
                out.append(player.name)
    return out


def _synth(player: str) -> bool:
    return player.startswith(("surge:", "zyn:"))


def track_of(player: str) -> str:
    """The text of a player's track: the sampler with its instrument, or the synth with its patch."""
    if _synth(player):
        return desk.template(template_of(player))
    return desk.bare(_file(player), [desk.sfizz(instrument(player))])


def build(players: list[str], kits: list[str], *, display: str) -> None:
    """Writes the sampler instrument and the track template of each of these players and kits
    (the templates can be put into a project by hand in REAPER: Insert track from template)."""
    desk.TEMPLATES.mkdir(parents=True, exist_ok=True)
    synths = []
    for player in players:
        if player.startswith("surge:"):
            synths.append({"name": template_of(player), "fx": [desk.surge(player[6:])]})
        elif player.startswith("zyn:"):
            synths.append({"name": template_of(player), "fx": [{"kind": "fx", "name": "LV2i: ZynAddSubFX", "preset": player[4:]}]})
        else:
            (desk.TEMPLATES / (_file(player) + ".RTrackTemplate")).write_text(track_of(player), encoding="utf-8")
    for name in kits:
        (desk.TEMPLATES / (_file("kit " + name) + ".RTrackTemplate")).write_text(track_of("kit " + name), encoding="utf-8")
    if synths:
        desk.make_tracks(synths, display=display)


def _trial(name: str) -> tuple[list[Note], list[tuple[float, int, int]]]:
    """A few firm notes for hearing one instrument alone."""
    firm = [(0.0, sfz.DYNAMICS, 100)]
    if name.startswith("kit "):
        from .orchestra import KITS
        strokes = KITS[name[4:]][1]
        return [Note(beat, 0.5, strokes[stroke], 0.75) for beat, stroke in ((0, "boom"), (2, "snare"), (4, "boom"), (6, "snare"))], firm
    if _synth(name):
        return [Note(beat * 3.0, 2.6, pitch, 0.75) for beat, pitch in enumerate((48, 60, 72))], firm
    if name in DRUMS:
        low, high = DRUMS[name][1], DRUMS[name][2]
    else:
        read = patch(name)
        low, high = read.low, read.high
    return [Note(beat * 3.0, 2.6, low + int((high - low) * part), 0.75) for beat, part in enumerate((0.25, 0.5, 0.75))], firm


def levels(names: list[str], *, display: str, bpm: float = 120.0) -> dict[str, dict[str, float]]:
    """Plays each player alone and writes down two things for it (levels.json): how many dB
    its bare sound has to be turned to come out at LEVEL ("before": this is done ahead of its
    effects, so that every compressor and tape meets the level it is set for), and how many
    more dB after its effects ("after": this is its fader)."""
    from .. import analysis
    work = desk.TEMPLATES / "levels"
    work.mkdir(parents=True, exist_ok=True)
    each_s = 6.0
    had = json.loads(LEVELS.read_text(encoding="utf-8")) if LEVELS.is_file() else {}
    had = {name: value for name, value in had.items() if isinstance(value, dict)}
    for stage in ("before", "after"):
        folders, stems = [], []
        for name in names:
            notes, firm = _trial(name)
            effects = []
            if stage == "after":
                effects = [turned(had[template_of(name)]["before"])] + (synth_chain(name, bpm) if _synth(name) else chain(name, bpm))
            stems.append(template_of(name))
            folders.append((desk.Line(template_of(name), track_of(name), notes, controls=firm, effects=[each for each in effects if each]), []))
        rpp = work / ("levels-%s.rpp" % stage)
        rpp.write_text(desk.project_flat(folders, bpm=bpm, seconds=each_s, out=work, tail=1.0), encoding="utf-8")
        desk.render(rpp, display=display, timeout=240.0)
        heard = desk.stems(work, stems, int((each_s + 1.0) * desk.RATE))
        for name, audio in heard.items():
            loud = analysis.loudness_lufs(audio, desk.RATE)
            if loud < -70.0:
                raise RuntimeError("The instrument %s made no sound when it was played alone (%s its effects)" % (name, stage))
            had.setdefault(name, {})[stage] = round(LEVEL - loud, 2)
    LEVELS.write_text(json.dumps(had, indent=1, sort_keys=True), encoding="utf-8")
    global _levels
    _levels = had
    return had


def turned(amount: float) -> str:
    """A plain turn of the volume by so many dB (REAPER's own), with no ceiling in the way."""
    return desk.js("utility/volume", amount, 60)


_levels: dict[str, dict[str, float]] | None = None


def level(name: str) -> dict[str, float]:
    global _levels
    if _levels is None:
        if not LEVELS.is_file():
            raise FileNotFoundError("The instruments' levels have not been measured yet (%s)" % LEVELS)
        _levels = json.loads(LEVELS.read_text(encoding="utf-8"))
    name = template_of(name)
    if name not in _levels or "after" not in _levels[name]:
        raise KeyError("The level of %s has not been measured" % name)
    return _levels[name]


# ---------------------------------------------------------------------------------------------
# From a written voice to REAPER tracks
# ---------------------------------------------------------------------------------------------
# How far back each player sits, 0 at the front of the stage to 1 at the back wall: the strings
# in front, the woodwind behind them, then the brass, the percussion and the organ at the back.
# The further back, the more of the hall is heard with it and the less of its top.
DEPTHS = (("violin", 0.0), ("viola", 0.0), ("celli", 0.0), ("basses", 0.05), ("strumstick", 0.25), ("harp", 0.3), ("folk harp", 0.3),
          ("psaltery", 0.3), ("zither", 0.3), ("harpsichord", 0.35), ("piano", 0.35), ("kalimba", 0.4), ("mbira", 0.4),
          ("recorder", 0.4), ("ocarina", 0.4), ("flute", 0.45), ("piccolo", 0.45), ("oboe", 0.45), ("clarinet", 0.45), ("bassoon", 0.45),
          ("small organ", 0.5), ("horn", 0.6), ("balafon", 0.6), ("frame drum", 0.6), ("trumpet", 0.65), ("trombone", 0.65), ("tuba", 0.65),
          ("surge", 0.7), ("marimba", 0.7), ("vibes", 0.7), ("glock", 0.75), ("tube glock", 0.75), ("xylophone", 0.75), ("anvil", 0.75),
          ("hand chimes", 0.8), ("organ", 0.85), ("tubular bells", 0.85), ("war drum", 0.85), ("tom mallet", 0.85), ("kit", 0.85),
          ("timpani", 0.9), ("great drum", 0.9), ("boom", 0.9), ("gong", 0.95), ("swell", 0.95))
# How much of each kind of player goes to the hall, in dB (the hall gives back as much as it is sent).
SENDS = {"strings": -10.0, "strings short": -11.0, "solo strings": -11.0, "solo strings short": -12.0, "woodwind": -13.0, "woodwind short": -13.0,
         "brass": -9.0, "brass short": -10.0, "organ": -7.0, "bowed metal": -8.0, "bells": -8.0, "mallets": -10.0, "keys": -12.0, "plucked": -9.0,
         "drums": -13.0, "synth": -7.0}
WAR_SEND = -8.0                # the war drums are in the hall as well as in their room


def depth_of(template: str) -> float:
    found = [(len(name), depth) for name, depth in DEPTHS if template.startswith(name)]
    if not found:
        raise KeyError("Nothing says how far back %r sits" % template)
    return max(found)[1]


def _placed(player: str, room: float) -> tuple[float, list[str]]:
    """How much of a player goes to the hall, and the effect that seats it on the stage."""
    name = template_of(player)
    kind = "synth" if _synth(player) else family(player)
    send = WAR_SEND if player in ("war drums", "boom", "gong") else SENDS[kind]
    depth = depth_of("surge" if _synth(player) else name)
    return 10 ** (send / 20.0) * room, [row(depth)] if depth >= 0.25 else []


def _dynamics(notes: list[Note], swells: list[tuple[float, float]], bpm: float) -> list[tuple[float, int, int]]:
    """Controller 1 under a held line: how hard it is being played from moment to moment. It
    sits at each note's strength, leans into a long note and falls away at its end (a held
    note is never still), and follows the writer's swells where there are any."""
    if not notes:
        return []
    ordered = sorted(notes, key=lambda note: note.start)
    step = 0.125
    first, last = ordered[0].start, max(note.start + note.length for note in ordered)
    count = int((last - first) / step) + 2
    curve = np.zeros(count)
    long = 1.0 * bpm / 60.0
    for note in ordered:
        begin, end = int((note.start - first) / step), min(int((note.start + note.length - first) / step) + 1, count)
        if end <= begin:
            continue
        strength = min(max((note.loud - 0.12) / 0.8, 0.05), 1.0)
        shape = np.full(end - begin, strength)
        if note.length >= long and not swells:
            along = np.linspace(0.0, 1.0, end - begin)
            shape = strength * (0.86 + 0.14 * np.sin(np.pi * np.minimum(along / 0.8, 1.0) ** 0.8)) * np.where(along > 0.8, 1.0 - 0.5 * (along - 0.8), 1.0)
        curve[begin:end] = np.maximum(curve[begin:end], shape)
    # Between notes it stays where the last note left it, so a note's ringing-on does not jump.
    for index in range(1, count):
        if curve[index] == 0.0:
            curve[index] = curve[index - 1]
    if swells:
        beats = first + np.arange(count) * step
        marks = sorted(swells)
        curve *= np.interp(beats, [beat for beat, _ in marks], [max(amount, 0.0) ** 0.8 for _, amount in marks])
    if count > 4:
        curve = np.convolve(np.pad(curve, 2, mode="edge"), np.ones(5) / 5.0, mode="valid")
    return [(first + index * step, sfz.DYNAMICS, int(round(8 + 119 * min(max(value, 0.0), 1.0)))) for index, value in enumerate(curve)]


def _range(player: str) -> tuple[int, int]:
    if _synth(player):
        return 24, 108
    if player in DRUMS:
        return DRUMS[player][1], DRUMS[player][2]
    read = patch(player)
    return read.low, read.high


def _swell(voice: Voice, title: str, bpm: float, taste: float, room: float) -> list[desk.Line]:
    """A cymbal swelling into a moment: for each written note, the recording that takes about
    as long as the note, laid so that it reaches its height where the note ends."""
    import soundfile
    clips = []
    for note in voice.notes:
        ends = (note.start + note.length) * 60.0 / bpm
        long = note.length * 60.0 / bpm
        took = min(SWELLS, key=lambda each: abs(each - long))
        file = SAMPLES / SWELLS[took]
        info = soundfile.info(str(file))
        # The recording rings on after its height: its height is where it is `took` seconds in.
        clips.append((max(ends - took, 0.0), info.duration, str(file)))
    send = 10 ** (-6.0 / 20.0) * room
    return [desk.Line(title, desk.bare("swell", []), volume=_db(-9.0) * taste, clips=clips, send=send,
                      effects=[equalise(low_cut=300.0), row(0.9)])]


def lines(voice: Voice, title: str, bpm: float, *, taste: float = 1.0, room: float = 1.0) -> list[desk.Line]:
    """The REAPER tracks that play one written voice. `taste` turns it up or down as a whole;
    `room` is how much hall the piece has (1 is the usual)."""
    if voice.drums:
        if not voice.instrument.startswith("kit "):
            raise ValueError("The drum voice %s does not say which kit it is" % title)
        name = _file(voice.instrument)
        send, placed = _placed(name, room)
        return [desk.Line(title, track_of(name), list(voice.notes), volume=_db(level(name)["after"]) * taste, pan=0.0, send=send,
                          effects=[turned(level(name)["before"])] + chain(name, bpm) + placed)]
    if voice.instrument == "swell":
        return _swell(voice, title, bpm, taste, room)
    if voice.instrument not in SOUNDS:
        raise KeyError("Nothing is set down to play the written instrument %r (voice %s)" % (voice.instrument, title))
    sound = SOUNDS[voice.instrument]
    beat = 60.0 / bpm
    out = []
    for player in sound.players:
        low, high = _range(player.name)
        notes = []
        for note in voice.notes:
            long = note.length * beat >= sound.short
            if (player.notes == "long" and not long) or (player.notes == "short" and long):
                continue
            if not (player.low <= note.pitch <= player.high and player.over <= note.loud < player.under):
                continue
            pitch = note.pitch + 12 * player.octave
            while pitch < low:
                pitch += 12
            while pitch > high:
                pitch -= 12
            if pitch < low:
                raise ValueError("%s cannot play the note %d that %s asks of it" % (player.name, note.pitch, title))
            notes.append(Note(note.start, note.length, pitch, note.loud))
        if not notes:
            continue
        name = template_of(player.name)
        synth = _synth(player.name)
        early, held = voice.shift, synth
        if player.name in RECORDED:
            read = patch(player.name)
            held = read.held and any(zone.loop for zone in read.zones)
            if held:
                early = max(early, read.attack / 2000.0)        # an instrument that speaks softly is played that much ahead
        send, placed = _placed(player.name, room)
        effects = [turned(level(player.name)["before"])] + (synth_chain(player.name, bpm) if synth else chain(player.name, bpm)) + placed
        out.append(desk.Line("%s: %s" % (title, name), track_of(player.name), notes, volume=_db(level(player.name)["after"] + player.gain) * taste,
                             pan=voice.pan if player.seat is None else player.seat,
                             controls=_dynamics(notes, voice.swells, bpm) if held else [], early=early, send=send,
                             effects=[each for each in effects if each]))
    return out
