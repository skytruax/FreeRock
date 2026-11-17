"""The sounds: which real instruments play what the writers write.

The writers name their instruments ("violins", "horns", "harp", "kit orchestra"). Here each
name is given its PLAYERS: recorded instruments from the sample sets on the drive, played by
the sfizz sampler in REAPER; drum-kit plug-ins; and patches of synths. A written instrument
can have several: the bowed recording for its long notes and the short-bow one for its quick
notes; one section for its low notes and another for its high ones; two drum kits and a third
set of drums for the war drums; a sub underneath.

RECORDED is every recorded instrument there is (a folder of single notes, and how to play
them). STROKES and KIT_STROKES are the drums, DRUMS the big drums made of several, KIT_PLUGS
what the drum-kit plug-ins take over. SOUNDS is the writers' names. Each recorded instrument
is written out as an instrument for the sampler (studio.sfz) as what it is: a section that
was recorded as a section is played as recorded, a soloist is one player, and the brass,
which was recorded soft, medium and loud at every semitone, swells through its three
strengths and is made into small sections from neighbouring semitones. A line of single notes
is slurred. Each instrument sits on a REAPER track with the few effects its family gets
(`chain`). `levels` plays each one alone to measure how loud it is and, where the same
instrument is among the recordings that were liked (studio.ear), what its top needs; `lines`
turns one written voice into the REAPER tracks that play it.

    uv run --no-sync python -m freerock.studio.sounds        write and measure every instrument

The sample sets: VSCO 2 Community Edition and VCSL (Versilian Studios, CC0), TinySOL (IRCAM,
CC BY 4.0), Big Rusty Drums (Karoryfer, CC0); the AVL drum kits (Glen MacArthur, CC BY-SA
3.0). See tools/stems/README.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import desk, muse, reaper, samples, sfz
from .samples import SAMPLES, Patch
from .score import Note, Voice

PATCHES = desk.VAR / "reaper" / "patches"          # each recorded instrument as read (kept, since reading measures every recording)
LEVELS = desk.TEMPLATES / "levels.json"            # how many dB each template is turned by, to play at LEVEL
LEVEL = -30.0                                      # LUFS: every instrument alone, at a firm strength, is brought to this
V2, VC, SOL = "vsco2/", "vcsl/", "tinysol/"
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
    # The clarinet and the bassoon are TinySOL's: every semitone played soft, medium and loud. A clarinet has no
    # vibrato, and its tone changes more from soft to loud than any other woodwind's; one recording cannot do that.
    "clarinet long": (SOL + "Winds/Clarinet_Bb/ordinario", WIND), "clarinet short": (_WW + "Clarinet/stac", SHORT),
    "bassoon long": (SOL + "Winds/Bassoon/ordinario", WIND), "bassoon plain": (_WW + "Bassoon/sus", WIND), "bassoon short": (_WW + "Bassoon/stac", SHORT),
    "recorder high long": (_EDGE + "Baroque Soprano Recorder/Sustain", WIND), "recorder high short": (_EDGE + "Baroque Soprano Recorder/Staccato", SHORT),
    "recorder long": (_EDGE + "Baroque Alto Recorder/SusVib", WIND), "recorder short": (_EDGE + "Baroque Alto Recorder/Staccato", SHORT),
    "recorder low long": (_EDGE + "Baroque Tenor Recorder/SusVib", WIND), "recorder low short": (_EDGE + "Baroque Tenor Recorder/Staccato", SHORT),
    "recorder bass long": (_EDGE + "Baroque Bass Recorder/SusVib", WIND),
    "ocarina long": (_EDGE + "Ocarina, Small/Sustain", WIND), "ocarina short": (_EDGE + "Ocarina, Small/Staccato", SHORT),
    # A chromatic harmonica (a Hohner Super 64), with its own vibrato on the held notes and its accented notes for the short ones.
    "harmonica long": (VC + "Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/Vib", dict(WIND, attack=20.0, release=160.0)),
    "harmonica short": (VC + "Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/Accented", dict(WIND, attack=6.0, release=110.0)),
    # --- brass: TinySOL (IRCAM, CC BY 4.0), every semitone played soft, medium and loud, with no vibrato ---
    # Brass is the family that changes most with strength: a horn played loud is twenty decibels louder than one
    # played soft and has twenty-five more above 2.5 kHz. The brass there was before (VSCO 2) had one strength, a
    # mellow one, and its trumpet a wide vibrato; nothing on the desk makes that blaze. The short notes are the
    # same recordings begun at once and let go at once.
    "horn long": (SOL + "Brass/Horn/ordinario", dict(WIND, attack=40.0, release=240.0)),
    "horn short": (SOL + "Brass/Horn/ordinario", dict(WIND, attack=8.0, release=110.0)),
    "horn muted": (_BR + "F Horn/mute", WIND),
    "trumpet long": (SOL + "Brass/Trumpet_C/ordinario", dict(WIND, attack=30.0, release=200.0)),
    "trumpet short": (SOL + "Brass/Trumpet_C/ordinario", dict(WIND, attack=6.0, release=90.0)),
    "trombone long": (SOL + "Brass/Trombone/ordinario", dict(WIND, attack=40.0, release=230.0)),
    "trombone short": (SOL + "Brass/Trombone/ordinario", dict(WIND, attack=8.0, release=110.0)),
    "tuba long": (SOL + "Brass/Bass_Tuba/ordinario", dict(WIND, attack=50.0, release=240.0)),
    "tuba short": (SOL + "Brass/Bass_Tuba/ordinario", dict(WIND, attack=10.0, release=120.0)),
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


# Big drums made of several drums struck by several players (studio.sfz.layered): name -> (the
# drums, how many players). Each drum is its strokes, the written note at which it sounds as
# it was recorded, its level in dB, and the lowest and highest written note that strike it.
#
# Every drum is played at the pitch it was recorded at, or within a semitone of it. The first
# war drums had these same drums tuned five to fifteen semitones down, through a low-pass
# filter: measured, nearly all their power lay under 160 Hz and their top was twenty decibels
# short of drums that were liked. No stick, no skin: a thud (2026-11-16).
_RUSTY = "big-rusty-drums/Samples/"            # Karoryfer's Big Rusty Drums (CC0): a 24-inch kick, a 22-inch kick hung as a tom, 18- and 15-inch toms
DRUMS: dict[str, tuple[list[tuple[str, int, float, int, int]], int]] = {
    # Written 36 and 38 are the 22-inch drum, 41 and 43 the 18-inch, 45 and 47 the 15-inch: struck in the middle with
    # sticks, heard over the kit (where the skin and the stick are) with the close microphone under it for the thump.
    "war drums": ([(_RUSTY + "tom_22/center/oh/t22_vl*_rr*.flac", 38, 0.0, 36, 39), (_RUSTY + "tom_22/center/cl/t22_vl*_rr*.flac", 38, -7.0, 36, 39),
                   (_RUSTY + "tom_18/center/oh/t18_vl*_rr*.flac", 42, 0.0, 40, 43), (_RUSTY + "tom_18/center/cl/t18_vl*_rr*.flac", 42, -7.0, 40, 43),
                   (_RUSTY + "tom_15/center/oh/t15_vl*_rr*.flac", 46, -1.0, 44, 47)], 3),
    "frame drums": ([(_MEMB + "Frame Drum/HDrumL_Hit_v*.wav", 46, 0.0, 40, 49), (_MEMB + "Frame Drum/HDrumS_Hit_v*.wav", 55, -2.0, 50, 64)], 2),
    # The deep stroke on an arrival: the undamped 24-inch kick, the 22-inch drum under a mallet and a concert bass drum, as one.
    "boom": ([(_RUSTY + "kick_24_nodamp/kick/oh/k_nodamp_vl*_rr*.flac", 36, 0.0, 24, 50), (_RUSTY + "tom_22/mallet/oh/t22_m_vl*_rr*.flac", 36, -3.0, 24, 50),
              (_MEMB + "Bass Drum 1/BDrumNew_hit_*.wav", 36, -1.0, 24, 50)], 2),
}
# The kick. A recorded studio kick (Wilkinson Audio's Naked Drums, CC BY 4.0: a 22-inch drum, ten takes of each of
# five strengths, each microphone a file of its own) gives the beater's click and the punch; a designed sub from
# the Geonkick drum synthesiser sits under it. Short on purpose: a kick is a stroke, and the bass owns what rings.
# The kick there was before was a 26-inch drum whose body lay at 28 Hz and rang for seven tenths of a second:
# a long soft thud with no stroke in it.
_NAKED = "naked-drums/Wilkinson Audio/Naked Drums/Samples/"
NAKED = {"kick": [("-Bottom_Black", "D2", 0.0), ("-TopOne_Black", "D2", -1.0), ("-CloseRoom_Black", "D2", -9.0)]}      # the microphone inside, the one outside, a little room
KICK_SUB = "geonkick:SPKickPresetsVol1/kick-07"          # 50 Hz, a fifth of a second, with enough above it to be heard on small loudspeakers
_TURNS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _naked(microphone: str, stroke: str, name: str, note: int) -> Patch:
    """One Naked Drums drum from one microphone: its files are named microphone, stroke, strength (10 to 50) and take."""
    by_layer: dict[int, list[tuple[int, str, str]]] = {}
    for path in sorted((SAMPLES / _NAKED).glob("%s_%s_*.flac" % (microphone, stroke))):
        words = path.name[len(microphone) + len(stroke) + 2:].split("-")[0].split("_")
        if len(words) != 2 or not words[0].isdigit() or words[1] not in _TURNS:
            continue
        by_layer.setdefault(int(words[0]), []).append((_TURNS.index(words[1]), path.name, str(path.relative_to(SAMPLES))))
    if not by_layer:
        raise FileNotFoundError("No Naked Drums recordings of %s %s under %s" % (microphone, stroke, SAMPLES / _NAKED))
    made = Patch(name=name, attack=0.5, release=600.0, held=False, floor=-18.0)
    have = sorted(by_layer)
    for place, layer in enumerate(have):
        soft = 1 if place == 0 else int(round(127 * place / len(have))) + 1
        hard = 127 if place == len(have) - 1 else int(round(127 * (place + 1) / len(have)))
        made.zones.append(samples.Zone(files=tuple(file for _, _, file in sorted(by_layer[layer])), low=note, high=note, root=note, soft=soft, hard=hard))
    return made


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
    # For a drum kit, whose every note is a different drum: (the written note, or -1 for any; the kit's note that is
    # struck for it; how much softer it is struck, in dB). A written note may strike several of the kit's drums.
    takes: tuple[tuple[int, int, float], ...] = ()


@dataclass(frozen=True)
class Sound:
    players: tuple[Player, ...]
    short: float = 0.26        # seconds: a note shorter than this is a short note


def _bowed(name: str, seat: float, long: str = "long") -> Sound:
    players = (Player("%s %s" % (name, long), "long", seat=seat), Player(name + " short", "short", seat=seat))
    if name == "basses":
        # A recorded double bass has little of its own bottom octave. Where the basses play out, a synth's plain sub
        # sits under them at their pitch, in the middle: felt more than heard, and the only thing down there.
        players += (Player(SUB, "long", over=0.55, gain=-9.0, octave=1, seat=0.0),)
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
SUB = "surge:patches_factory/Basses/Sub 1.fxp"          # a plain sine that sounds an octave under the note it is given (measured): played an octave up, it is at the note
# Drum-kit plug-ins: the AVL drum kits (Glen MacArthur's recordings, CC BY-SA 3.0, in Robin
# Gareus's plug-in). Red Zeppelin is a 1970s rock kit with a 26-inch bass drum, Black Pearl a
# tighter modern kit with a deeper floor tom, Buskman's Holiday hand percussion; every drum was
# recorded at five strengths (the hand percussion at ten). After "#" stands what the kit is
# used as: the same kit is mixed one way as war drums and another behind a band.
#   Both kits: 36 kick, 37 side stick, 38 snare, 40 snare edge, 41 floor tom, 43 floor tom edge, 45 tom, 47 tom edge,
#   42 44 46 48 hi-hat (closed, pedal, half open, swish), 49 57 60 crashes, 51 53 59 ride, 54 tambourine, 56 cowbell, 61 maraca.
#   Buskman's: 35 stick click, 36 cajon thump, 38 40 cajon slaps, 39 claps, 41 43 big conga, 45 47 small conga, 42 shakers,
#   44 46 tambourine, 48 claves, 49 cymbal, 50 its bell, 51 cowbell, 52 foot stomp, 53 bucket.
RED, PEARL, BUSK = "avl:Red Zeppelin Drumkit", "avl:Black Pearl Drumkit", "avl:Buskman's Holiday Percussion"
# The war drums are two drummers at two kits and a third at the big rusty drums. Written 36 is
# everything low at once (the 26-inch bass drum and both floor toms), 38 the deep floor tom,
# 41 the other kit's, 43 the deep one struck at its edge, 45 and 47 the two kits' toms: so a
# roll (38, 41, 38, 41) goes from drummer to drummer, as do the eighths that drive (43, 41).
# ("think we need a little more kick drum", 2026-11-16: three decibels more of both.)
# ("more bass and kick in the intense parts", the same evening: two more.)
_KICK = (Player("kick", takes=((36, 36, 0.0),), gain=6.0, seat=0.0), Player(KICK_SUB, takes=((36, 60, 0.0),), gain=4.0, seat=0.0))
_WAR = (Player(PEARL + "#war", takes=((36, 41, 0.0), (38, 41, 0.0), (43, 43, 0.0), (45, 45, 0.0)), seat=-0.3),
        Player(RED + "#war", takes=((36, 41, -3.0), (41, 41, 0.0), (47, 45, 0.0)), seat=0.3),
        Player("war drums", gain=-3.0, seat=0.0)) + _KICK
# A kit's strokes that a kit plug-in plays (the rest stay with the recordings in the sampler):
# kit -> (the plug-in, the writer's stroke -> the plug-in's note).
_ROCK = {"boom": 36, "snare": 38, "clack": 37, "crash": 49, "crash2": 57, "tamb": 54, "hat": 42, "hat open": 46, "ride": 51, "bell": 53,
         "tom": 45, "tom low": 41, "tom high": 47, "cowbell": 56, "shake": 61}
KIT_PLUGS: dict[str, tuple[str, dict[str, int]]] = {
    "rock": (RED + "#kit", _ROCK), "room": (PEARL + "#kit", _ROCK),
    "hands": (BUSK + "#hands", {"boom": 41, "conga low": 43, "snare": 45, "conga": 47, "clack": 38, "mute": 40, "deep": 36, "shake": 42, "jingle": 44,
                                "tamb": 46, "tick": 48, "crash": 49, "ting": 50, "cowbell": 51}),
    "folk": (BUSK + "#hands", {"clack": 39, "shake": 42, "jingle": 44, "tamb": 46, "tick": 48}),
}
# The kits whose bass-drum stroke ("boom") has the kick with it, beside the kit's own drum. A band's kits have a
# bass drum that is meant to be heard (Red Zeppelin's is 26 inches across and booms): the kick goes with it at half
# the strength, for the stroke and the bottom that drum does not have.
KICKED = ("orchestra", "march", "folk", "wood", "rock", "room")
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
    "harp": Sound((Player("harp", seat=-0.45),)),
    # There is no recording of a celesta. Of what there is, a vibraphone under soft mallets is nearest: metal bars over
    # resonators, a soft stroke, a pure note. (A glockenspiel, which stood in before, is glass beside it.)
    "celesta": Sound((Player("vibes", seat=-0.3),)),
    "glock": Sound((Player("glock", seat=0.25),)), "music box": Sound((Player("kalimba", octave=1, seat=-0.1),)),
    "vibes": Sound((Player("vibes", seat=0.3),)), "marimba": Sound((Player("marimba", seat=0.3),)),
    "xylophone": Sound((Player("xylophone", seat=0.3),)),
    "bells": Sound((Player("tubular bells", seat=0.35),)),
    "church bell": Sound((Player("tubular bells", seat=0.1), Player("hand chimes", gain=-8.0, octave=1, seat=0.1))),
    "dulcimer": Sound((Player("psaltery", seat=-0.2),)),
    "organ": Sound((Player("organ quiet", under=0.62, seat=0.0), Player("organ loud", over=0.62, seat=0.0))),
    "harpsichord": Sound((Player("harpsichord", seat=-0.15),)),
    # There is no accordion that sounds like one. A harmonica is the same kind of instrument (free reeds), was asked
    # for by name ("i better hear harmonica and banjo", 2026-11-16) and is there as a real recording: it has the
    # accordion's parts. The banjo's are a strumstick's: three strings and the same twang; there is no banjo here.
    "accordion": _blown("harmonica", 0.15), "harmonica": _blown("harmonica", 0.1),
    "guitar": Sound((Player("folk harp", seat=-0.25),)), "steel guitar": Sound((Player("strumstick", seat=-0.25),)),
    "mandolin": Sound((Player("strumstick", octave=1, seat=0.2),)),
    "twelve string": Sound((Player("strumstick", seat=-0.25), Player("psaltery", octave=1, gain=-7.0, seat=-0.25))),
    "sitar": Sound((Player("zither bent", seat=-0.1),)), "koto": Sound((Player("zither", seat=-0.1),)),
    "kalimba": Sound((Player("kalimba", seat=0.2),)), "banjo": Sound((Player("strumstick", seat=0.25),)),
    "bagpipe": Sound((Player("oboe plain", seat=0.0), Player("small organ", gain=-8.0, seat=0.0))),
    "shenai": Sound((Player("oboe plain", seat=0.05),)),
    "choir": Sound((Player(CHOIR, gain=-3.0, seat=0.0),)), "oohs": Sound((Player(OOHS, gain=-3.0, seat=0.0),)),
    "timpani": Sound((Player("timpani", seat=-0.1),)),
    # A drum written at the chord's note, whatever that is: the deep floor tom and the rusty drums nearest that size.
    "taiko": Sound((Player(PEARL + "#war", takes=((-1, 41, 0.0),), seat=-0.2), Player(RED + "#war", takes=((-1, 41, -2.0),), seat=0.2),
                    Player("war drums", gain=-3.0, seat=0.0))),
    "great drum": Sound((Player("great drum", seat=0.0), Player(RED + "#war", takes=((-1, 36, -2.0),), gain=-4.0, seat=0.0))),
    "melodic tom": Sound((Player("tom mallet", seat=0.15),)),
    "war drums": Sound(_WAR),
    # The frame drums and a cajon with them: its thump under the low strokes, its slaps with the high ones.
    "frame drums": Sound((Player("frame drums", seat=0.1),
                          Player(BUSK + "#hands", takes=((45, 36, 0.0), (47, 36, -2.0), (55, 38, -3.0), (57, 40, -3.0), (50, 38, -8.0), (52, 40, -8.0)),
                                 gain=-5.0, seat=-0.15))),
    # The deep stroke on an arrival: both kits' bass drums and the deep floor tom, the big rusty kick and a concert bass
    # drum, and a synth's sub under them an octave above the bottom of hearing (it used to sit at 33 Hz, where it
    # could not be heard and every loudspeaker had to carry it).
    "boom": Sound((Player(PEARL + "#war", takes=((36, 41, 0.0),), seat=0.0), Player("boom", gain=-2.0, seat=0.0),
                   Player(SUB, gain=-6.0, octave=1, seat=0.0)) + _KICK),
    "kick": Sound(_KICK),
    # What is stacked under MuseScore's double basses where they play out: a plain sub at their pitch.
    "sub": Sound((Player(SUB, "long", over=0.4, gain=-7.0, octave=1, seat=0.0),)),
    # Layers the desk stacks on a piece (studio.build): a deep sub under the bass at the story's moments, and a wide
    # synth pad (ZynAddSubFX's full strings) far under the string pad, for depth: felt as width more than heard.
    "deep": Sound((Player(SUB, gain=-4.0, octave=1, seat=0.0),)),
    "pad": Sound((Player(SILK, gain=-13.0, seat=0.0),)),
    "gong": Sound((Player("gong", seat=0.2),)), "anvil": Sound((Player("anvil", seat=-0.2),)),
}


# ---------------------------------------------------------------------------------------------
# Each recorded instrument as an instrument for the sampler
# ---------------------------------------------------------------------------------------------
# ---- The dance floor (studio.club). What the house writer calls its sounds, played by Surge XT's own patches: a
# real synth in place of the studio's, which was turned down ("figure out how to make house music not suck",
# 2026-11-16). Chosen by what each patch is; the ones that are real instruments (piano, marimba, harp, flute,
# strings, brass) go to Muse Sounds instead (studio.club.PLAYED).
_SURGE = "surge:patches_factory/"
HOUSE = {
    "house sub": "Basses/Sub 1", "house bass pluck": "Basses/Fingered", "house bass saw": "Basses/Lord Sawtooth",
    "house bass square": "Basses/Squared", "house bass fm": "Basses/FM Bass 1", "house bass wide": "Basses/Wide Bassline",
    "house bass organ": "Keys/House Organ", "house organ": "Keys/House Organ", "house stab": "Polysynths/Smooth Stabs",
    "house pluck": "Plucks/Nice Pluck 1", "house bell": "Plucks/Bell 1", "house glass": "Plucks/Diamonds",
    "house lead saw": "Leads/Classic Lead 1", "house lead super": "Polysynths/Super Jupiter", "house lead hollow": "Leads/Smoothy Hollow",
    "house lead sine": "Leads/Sine Lead", "house pad warm": "Pads/MKS-70 Warm Pad", "house pad super": "Pads/Super",
    "house pad glass": "Pads/Sparkly", "house pad hollow": "Pads/Ooh", "house pad organ": "Keys/Organ 1",
}
# How many octaves from where it is written each patch has to be played to sound where it is written. Measured
# 2026-11-16 by playing C3, C4 and C5 on each alone and reading the pitch that came out: Surge's basses sound an
# octave under the key (its wide bassline and its house organ two), as do its Super Jupiter and its MKS-70 pad.
# (Its "Square Bass" does not follow the keys at all, and "Rubber Bass" does not die away as a plucked bass does:
# "Squared" and "Fingered" are used in their places.)
HOUSE_OCTAVE: dict[str, int] = {"house sub": 1, "house bass pluck": 1, "house bass saw": 1, "house bass square": 1, "house bass wide": 2,
                                "house bass organ": 2, "house organ": 2, "house lead super": 1, "house pad warm": 1}
SOUNDS.update({name: Sound((Player(_SURGE + patch + ".fxp", octave=HOUSE_OCTAVE.get(name, 0), seat=0.0),)) for name, patch in HOUSE.items()})


def _file(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _.-]+", " ", name).strip()


_patches: dict[str, Patch] = {}


def patch(name: str) -> Patch:
    """A recorded instrument by name, read from its folder (and kept, since reading it means
    measuring every recording)."""
    if name not in _patches:
        _patches[name] = _read_patch(name)
    return _patches[name]


def _read_patch(name: str) -> Patch:
    kept = PATCHES / (_file(name) + ".json")
    if kept.is_file():
        had = Patch.load(kept)
        if name not in RECORDED:
            return had
        # A kept reading is good only while the instrument is still read from the same folder in the same way.
        folder, how = RECORDED[name]
        if (had.zones and had.zones[0].files[0].startswith(folder + "/") and had.attack == how.get("attack", 4.0)
                and had.release == how.get("release", 180.0) and had.held == how.get("held", True)):
            return had
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


def _kit_plug(name: str) -> bool:
    """Whether a player is a drum plug-in: a drum kit ("avl:<the plug-in's name>#<what it is
    used as>") or the Geonkick drum synthesiser with one of its presets ("geonkick:<preset>")."""
    return name.startswith(("avl:", "geonkick:"))


def _role(name: str) -> str:
    return name.split("#", 1)[1] if "#" in name else ""


def family(name: str) -> str:
    """Which kind of instrument a recorded one is: it settles how it is written for the sampler
    and what effects go on its channel."""
    first = name.split(" ")[0]
    if _kit_plug(name) or name in DRUMS or name in NAKED or name in TUNED_DRUMS or name in KETTLES or name in STRUCK or name.startswith("kit "):
        return "drums"
    if first in ("violins", "violas", "celli", "basses"):
        return "strings short" if name.endswith(("short", "pizz")) else "strings"
    if first == "violin":
        return "solo strings short" if name.endswith(("short", "pizz")) else "solo strings"
    if first in ("flute", "piccolo", "oboe", "clarinet", "bassoon", "recorder", "ocarina", "harmonica"):
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


_written: dict[tuple[str, bool], Path] = {}
# How many play each note of a held instrument, where that is more than the recording itself:
# the brass, whose every semitone was recorded, so that the players beside the first are the
# neighbouring semitones bent to the note (three horns, two trumpets, two trombones, one tuba).
PLAYERS = {"horn": 3, "trombone": 2}
# A vibrato for what was recorded dead straight and is heard alone: (times a second, cents either way, dB). The
# trumpet has the tune as one player; two straight trumpets a few cents apart were heard as "a cheesy synth".
VIBRATO = {"trumpet": (5.3, 9.0, 0.6)}
# How long a slurred note takes to come in over the note before it, in seconds, by family.
SLUR = {"strings": 0.12, "solo strings": 0.09, "woodwind": 0.07, "brass": 0.08}


def _dry(name: str) -> bool:
    """Whether an instrument was recorded with no room about it (TinySOL: one microphone, close)."""
    return name in RECORDED and RECORDED[name][0].startswith(SOL)


def instrument(name: str, slurs: bool = False) -> Path:
    """The sampler instrument (an SFZ file) for a recorded instrument, a big drum or a kit
    ("kit orchestra"). It is written afresh the first time it is asked for in a run, so that a
    change to how instruments are written reaches every one of them. With `slurs`, the
    instrument for a line of single notes: a note begun while the last is held joins it."""
    if (name, slurs) in _written:
        return _written[(name, slurs)]
    kind = family(name)
    slur = SLUR.get(kind, 0.0) if slurs else 0.0
    if name.startswith("kit "):
        from .orchestra import KITS
        strokes = KITS[name[4:]][1]
        hats = {strokes[each]: 1 for each in ("hat", "hat open") if each in strokes}
        text = sfz.kit(kit_patches(name[4:], strokes), chokes=hats)
    elif name in DRUMS:
        parts, players = DRUMS[name]
        made_parts = []
        for pattern, centre, level, low, high in parts:
            files = sorted(SAMPLES.glob(pattern))
            if not files:
                raise FileNotFoundError("No recordings match %s (for %s)" % (pattern, name))
            made_parts.append((samples.struck(files, name, centre, release=1500.0), centre, level, low, high))
        text = sfz.layered(made_parts, players=players)
    elif name in NAKED:
        # One drum heard through its microphones at once, as recorded: one player, no shifting.
        text = sfz.layered([(_naked(microphone, stroke, name, 36), 36, level, 24, 60) for microphone, stroke, level in NAKED[name]],
                           players=1, track=0.0)
    else:
        read = patch(name)
        if read.held and any(zone.loop for zone in read.zones):
            first = name.split(" ")[0]
            # Every instrument is its recording as it is: a section that was recorded as a section has its players
            # in it, and a soloist is one player. (Sections used to be three recordings a few cents and a few
            # hundredths of a second apart: that is a chorus, and a chorus on strings is a keyboard's strings.)
            if kind == "strings":
                # (A section swells from its soft recording into its loud one: many players do not change all at once.)
                bite = patch(first + " short") if name.endswith(("long", "slow")) else None
                text = sfz.held(read, blend=True, range_db=14.0, drift=2.0, bite=bite, slur=slur)
            elif kind == "solo strings":
                text = sfz.held(read, range_db=14.0, drift=3.0, slur=slur)
            elif kind == "woodwind" and _dry(name):
                # Three recorded strengths: the note's own strength picks one (one player), and they differ as recorded.
                text = sfz.held(read, blend=False, dark=6000.0, opens=2400.0, range_db=5.0, drift=2.0, slur=slur)
            elif kind == "woodwind":
                text = sfz.held(read, range_db=18.0 if len({zone.soft for zone in read.zones}) == 1 else 13.0, drift=2.5, slur=slur)
            elif kind in ("brass", "brass short") and _dry(name):
                # The three recorded strengths fade into each other as the players swell: that is the whole of a brass
                # section's dynamics, and it is in the recordings. Nothing is added but a few decibels of range.
                count = PLAYERS.get(first, 1)
                text = sfz.held(read, players=count, blend=count > 1, dark=7000.0, opens=2400.0, range_db=4.0, drift=1.5, spread=26.0, slur=slur,
                                vibrato=VIBRATO.get(first) if name.endswith("long") else None)
            elif kind == "brass":
                text = sfz.held(read, dark=2400.0, opens=4000.0, range_db=14.0, drift=2.0, slur=slur)
            elif kind == "organ":
                text = sfz.held(read, dark=8000.0, opens=1800.0, range_db=8.0, drift=0.6)
            else:
                text = sfz.held(read, range_db=14.0, drift=2.5)
        elif kind == "drums":
            text = sfz.struck(read, dull=6000.0, opens=2400.0)
        else:
            text = sfz.struck(read)
    _written[(name, slurs)] = sfz.write(_file(name) + (" slurred" if slur else ""), text)
    return _written[(name, slurs)]


# ---------------------------------------------------------------------------------------------
# The effects on each instrument's channel
# ---------------------------------------------------------------------------------------------
def _db(value: float) -> float:
    return 10 ** (value / 20.0)


def equalise(*, low_cut: float = 0.0, high_cut: float = 0.0, low_shelf: tuple[float, float] | None = None,
             high_shelf: tuple[float, float] | None = None, bands: tuple[tuple[float, float, float], ...] = ()) -> str:
    """The studio's own equaliser (studio/jsfx/channel_eq: six plain filters, cheap enough for
    every channel): cuts in Hz, shelves as (Hz, dB), up to three bands as (Hz, dB, width in octaves)."""
    if len(bands) > 3:
        raise ValueError("The equaliser has three bands; %d were asked for" % len(bands))
    three = list(bands) + [(1000.0, 0.0, 1.0)] * (3 - len(bands))
    low = low_shelf or (100.0, 0.0)
    high = high_shelf or (8000.0, 0.0)
    return desk.js("freerock/channel_eq", low_cut, high_cut, low[0], low[1], *[value for band in three for value in band], high[0], high[1])


def ensemble(amount: float, *, voices: int = 6, rate: float = 0.35, depth: float = 2.5) -> str:
    """A chorus (Calf's multi chorus): for synths. Not for recorded strings."""
    return desk.lv2("Calf Multi Chorus", voices=voices, min_delay=6.0, mod_depth=depth, mod_rate=rate, stereo=180.0, vphase=300.0,
                    amount=amount, dry=1.0 - 0.35 * amount)


def wide(side: float) -> str:
    """More of what differs between left and right (Calf's stereo tools): 1 leaves it as it is."""
    return desk.lv2("Calf Stereo Tools", slev=side)


def flipped() -> str:
    """Left and right changed over (Calf's stereo tools): a second kit of the same make has its
    drums where the first has them, and two drummers do not sit on each other's lap."""
    return desk.lv2("Calf Stereo Tools", mode=6)


def warm(amount: float) -> str:
    """Tape (Calf's tape simulator with its hiss and wobble off, and its own top cut out of
    the way): rounds the peaks and thickens what is under them."""
    return desk.lv2("Calf Tape Simulator", level_in=0.33 * (1.0 + 1.6 * amount), level_out=1.0 / (1.0 + 0.9 * amount), mix=min(0.3 + 0.5 * amount, 1.0),
                    lowpass=20000.0, noise=0.0, mechanical=0.0, magnetical=1.0)


def punch(strike: float, body: float) -> str:
    """A transient shaper (Calf's): more of the stroke, more or less of what rings after it."""
    return desk.lv2("Calf Transient Designer", attack_time=20.0, attack_boost=strike, release_time=250.0, release_boost=body, lookahead=0, mix=1.0)


def squeeze(threshold: float, ratio: float, attack: float, release: float, makeup: float = 0.0) -> str:
    """A compressor (Steve Harris's SC4): threshold and make-up in dB, times in milliseconds."""
    return desk.lv2("SC4", rms_peak=0.0, attack=max(attack, 1.5), release=release, threshold=max(threshold, -30.0), ratio=ratio, knee=5.0,
                    makeup_gain=max(makeup, 0.0))


def smash(amount: float, *, threshold: float = -28.0, ratio: float = 8.0, attack: float = 6.0, release: float = 110.0, makeup: float = 10.0) -> str:
    """A compressor laid beside the sound instead of over it (Calf's compressor with its mix
    part-way: what drummers' engineers call parallel compression). The strokes stay as they
    were played; what rings between them, the skin and the room, comes up under them.
    `amount` is how much of the squeezed sound is mixed in, 0 to 1."""
    return desk.lv2("Calf Compressor", threshold=_db(threshold), ratio=ratio, attack=attack, release=release, makeup=_db(makeup), knee=_db(6.0),
                    detection=0, stereo_link=0, mix=amount)


def echo(bpm: float, amount: float, *, left: int = 3, right: int = 3, again: float = 0.35) -> str:
    """A tempo echo from side to side (Calf's vintage delay), counted in sixteenths: three is a dotted eighth."""
    return desk.lv2("Calf Vintage Delay", timing=0, bpm=min(max(bpm, 30.0), 300.0), subdiv=4, time_l=left, time_r=right, feedback=again, amount=amount,
                    dry=1.0, medium=1, mix_mode=1)


def excite(amount: float) -> str:
    """Air (Calf's exciter): new harmonics made above 7.5 kHz out of what is under them, mixed in a little."""
    return desk.lv2("Calf Exciter", amount=amount, drive=8.5, blend=0.0, freq=7500.0)


def enhance(amount: float) -> str:
    """The bass made audible where a loudspeaker has no bottom (Calf's bass enhancer): harmonics of what lies under 100 Hz."""
    return desk.lv2("Calf Bass Enhancer", amount=amount, drive=8.5, blend=0.0, freq=100.0)


def ceiling(threshold: float = -1.0, push: float = 0.0) -> str:
    """A limiter (x42's): nothing goes over `threshold` dB. With `push`, the sound is turned
    up by so many dB into it, so its peaks are held and its body comes up: denser, louder."""
    return desk.lv2("x42-dpl - Digital Peak Limiter Stereo", gain=push, threshold=threshold, release=0.05)


def row(depth: float, dry: bool = False) -> str:
    """Where on the stage a player sits, front to back (Dragonfly's early reflections): the
    further back, the more of the first echoes off the walls and the bigger they are. The
    player's own sound is left whole and its top is left alone. A recording made close, with
    no room in it (`dry`), is given more of the stage: it has none of its own."""
    more = 1.7 if dry else 1.0
    return desk.lv2("Dragonfly Early Reflections", dry_level=100.0 - 10.0 * depth * more, early_level=min((10.0 + 25.0 * depth) * more, 60.0), program=2,
                    size=14.0 + 18.0 * depth, width=110.0 - 20.0 * depth, low_cut=80.0 - 30.0 * depth, high_cut=16000.0 - 4000.0 * depth)


def drum_room() -> str:
    """A big drum room around the drums themselves (Dragonfly's room reverb)."""
    return desk.lv2("Dragonfly Room Reverb", dry_level=90.0, early_level=20.0, early_send=20.0, late_level=25.0, size=14.0, width=100.0,
                    predelay=16.0, decay=0.7, diffuse=40.0, spin=2.7, wander=10.0, in_high_cut=16000.0, early_damp=10000.0, late_damp=7000.0,
                    low_boost=30.0, boost_freq=300.0, in_low_cut=4.0)


LOW_CUT = {"harmonica": 200.0, "violins": 170.0, "violas": 115.0, "celli": 58.0, "basses": 30.0, "violin": 175.0, "flute": 230.0, "piccolo": 480.0, "oboe": 210.0,
           "clarinet": 130.0, "bassoon": 52.0, "recorder": 220.0, "ocarina": 400.0, "horn": 60.0, "trumpet": 150.0, "trombone": 55.0, "tuba": 30.0}
VOICING = desk.TEMPLATES / "voicing.json"          # what the ear worked out for each instrument's top (see `levels`)
_voicing: dict[str, dict] | None = None


def voiced(name: str) -> dict:
    """What the equaliser does to an instrument's top so that it stands where the same
    instrument stands in recordings that were liked: {"bands": ..., "high_shelf": ...} for
    `equalise`, worked out by `levels` and kept. Nothing, for an instrument there is no such
    recording of."""
    global _voicing
    if _voicing is None:
        _voicing = json.loads(VOICING.read_text(encoding="utf-8")) if VOICING.is_file() else {}
    found = _voicing.get(template_of(name))
    if not found and name.endswith(" short") and name in RECORDED and RECORDED[name][0] == RECORDED.get(name[:-6] + " long", ("",))[0]:
        found = _voicing.get(template_of(name[:-6] + " long"))          # the same recordings, begun and let go at once
    if not found:
        return {}
    return {"bands": tuple(tuple(band) for band in found["bands"]), "high_shelf": tuple(found["high_shelf"])}


def chain(name: str, bpm: float) -> list[str]:
    """The effects on a recorded instrument's channel, by its family. Less than there was: an
    equaliser that takes away what is under the instrument and sets its top by ear (`voiced`),
    and for a few families one thing more. Each further box used to be there on principle,
    and together they made the orchestra dull and wide and unlike itself."""
    kind = family(name)
    first = name.split(" ")[0]
    cut = LOW_CUT.get(first, 0.0)
    tone = voiced(name)
    if name.startswith("geonkick:"):
        return [equalise(low_cut=30.0), warm(0.25)]                 # the sub under the kick: left as it was designed
    if name in NAKED:
        # The kick: its stroke brought out and what rings after it held back, the box at 350 Hz down, the beater up.
        return [punch(0.3, -0.15), equalise(low_cut=38.0, low_shelf=(75.0, 2.0), bands=((350.0, -3.0, 1.2), (3800.0, 3.0, 1.5))), smash(0.35), warm(0.3)]
    if _kit_plug(name):
        role = _role(name)
        if role == "war":
            # The stroke brought out, the box at 260 Hz down, the stick up; then the skin and the room brought up
            # under the strokes, and tape to thicken it.
            return [punch(0.35, 0.2), equalise(low_cut=36.0, bands=((260.0, -2.0, 1.2), (3600.0, 3.0, 1.6)), high_shelf=(9000.0, 2.0)),
                    smash(0.45), warm(0.4)]
        if role == "hands":
            return [punch(0.2, 0.0), equalise(low_cut=45.0, bands=((3500.0, 2.0, 1.6),)), smash(0.3)]
        # A kit behind a band. (Measured in "Lance Cry" against the rock kits that were liked, 2026-11-16: 4.5 dB too
        # much from 320 Hz to 5 kHz, 4 dB too little at 160 to 320 Hz, and strokes that rose 9 dB in ten milliseconds
        # where the liked ones rise 16: more stroke, less of what rings, the box down, the shell up, less tape.)
        return [punch(0.5, 0.0), equalise(low_cut=32.0, low_shelf=(200.0, 2.0), bands=((480.0, -4.0, 1.4), (2200.0, -2.0, 1.6))),
                smash(0.3), warm(0.15)]
    if kind == "woodwind" and _dry(name):
        # Recorded close: the keys and the breath are nearer than they are from a seat in the hall.
        return [equalise(low_cut=cut, high_shelf=(7500.0, -3.0))]
    if kind in ("strings", "strings short", "solo strings", "solo strings short", "woodwind", "woodwind short"):
        return [equalise(low_cut=cut, **tone)]
    if kind.startswith("brass"):
        return [equalise(low_cut=cut, **tone), warm(0.3)]
    if kind == "organ":
        return [equalise(low_cut=28.0, bands=((300.0, -2.0, 1.0),))]
    if kind == "bowed metal":
        return [equalise(low_cut=150.0)]
    if kind == "bells":
        return [equalise(low_cut=250.0, **tone), echo(bpm, 0.15)]
    if kind == "mallets":
        return [equalise(low_cut=90.0, **tone)]
    if kind == "keys":
        return [equalise(low_cut=45.0, **tone)]
    if kind == "plucked":
        return [equalise(low_cut=70.0, **tone), echo(bpm, 0.1) if name in ("zither", "zither bent", "psaltery", "kalimba", "mbira") else ""]
    if name in ("war drums", "boom"):
        return [punch(0.3, 0.2), equalise(low_cut=34.0, bands=((280.0, -2.5, 1.2), (3200.0, 4.0, 1.8)), high_shelf=(8000.0, 3.0)), smash(0.5), warm(0.45)]
    if name == "frame drums":
        return [punch(0.3, 0.1), equalise(low_cut=45.0, bands=((400.0, -2.0, 1.2), (4000.0, 3.0, 1.6))), smash(0.35), warm(0.3)]
    if name in ("timpani", "great drum", "war drum", "tom mallet", "frame drum"):
        return [punch(0.25, 0.1), equalise(low_cut=32.0, bands=((450.0, -2.5, 1.4), (3500.0, 2.0, 1.6))), smash(0.3)]
    if name in ("gong", "anvil"):
        return [equalise(low_cut=60.0)]
    if name.startswith("kit "):
        # The cymbals and the tambourine were recorded close and are bright enough: the top is eased, not lifted.
        return [punch(0.25, 0.05), equalise(low_cut=30.0, bands=((400.0, -2.0, 1.0),), high_shelf=(8000.0, -4.0)), smash(0.3)]
    return [equalise(low_cut=40.0)]


def synth_chain(player: str, bpm: float) -> list[str]:
    """The effects on a synth's channel."""
    if player in (CHOIR, OOHS):
        return [equalise(low_cut=120.0, bands=((350.0, -2.0, 1.5),), high_shelf=(11000.0, 2.5)), ensemble(0.4, voices=6, rate=0.2, depth=3.0)]
    if player == SILK:
        return [equalise(low_cut=150.0, high_cut=9000.0), wide(1.5), echo(bpm, 0.12)]
    if player == SUB:
        return [equalise(low_cut=28.0, high_cut=260.0), squeeze(-18.0, 4.0, 25.0, 125.0, 2.0)]
    return []


def bus(channel: str, style: str = "") -> list[str]:
    """What is on a whole channel's folder. The drums: their room, a compressor that holds
    them together, tape, and a ceiling. The others: a gentle compressor that only takes the
    edge off the loudest notes, and a ceiling. (2026-11-16, night: "rewrite all music to be
    more dynamic". The compressors began 6 dB lower and every ceiling was pushed 3 dB, which
    flattened what the writer wrote between pianissimo and fortissimo.)"""
    # Under 28 Hz nothing is heard, and what is there uses up the room every loudspeaker and limiter has.
    if style == "house":
        # The house desk's channels, as they were before the orchestra's were held against the liked stems (house has
        # its own liked stems, and has not been held against them yet).
        if channel == "drums":
            return [equalise(low_cut=28.0), drum_room(), squeeze(-12.0, 2.5, 25.0, 180.0, 1.0), warm(0.3), ceiling(-1.5, push=1.0)]
        if channel == "bass":
            return [equalise(low_cut=28.0, low_shelf=(90.0, 2.5)), enhance(0.35), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.25),
                    ceiling(-1.5, push=1.0)]
        if channel == "texture":
            return [equalise(low_cut=28.0), wide(1.25), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.15), ceiling(-1.5, push=0.5)]
        if channel == "lead":
            return [equalise(low_cut=28.0), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), excite(0.25), warm(0.12), ceiling(-1.5, push=0.5)]
        return [equalise(low_cut=28.0), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.15), ceiling(-1.5, push=0.5)]
    if style == "knight":
        # The band's channels (2026-11-17, night, the first Knight Rock piece held against the band stems that were liked:
        # the lead guitar 10 dB short in its middle, the pads 7 dB heavy there; the liked stems have next to nothing above
        # 2.5 kHz, 30 to 60 dB under their middle, more than any guitar or organ, so their top is not followed far).
        if channel == "drums":
            return [equalise(low_cut=28.0, high_shelf=(6000.0, -2.0)), drum_room(), squeeze(-12.0, 2.5, 25.0, 180.0, 1.0), warm(0.3),
                    ceiling(-1.5, push=1.0)]
        if channel == "bass":
            return [equalise(low_cut=28.0, low_shelf=(90.0, 2.5), high_shelf=(2000.0, -4.0)), enhance(0.25), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0),
                    warm(0.3), ceiling(-1.5, push=1.0)]
        if channel == "texture":
            return [equalise(low_cut=28.0, bands=((500.0, -3.0, 1.5),), high_shelf=(3000.0, -6.0)), wide(1.25), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0),
                    warm(0.15), ceiling(-1.5, push=0.5)]
        if channel == "lead":
            return [equalise(low_cut=28.0, bands=((900.0, 5.0, 1.6),), high_shelf=(4000.0, -4.0)), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0),
                    warm(0.2), ceiling(-1.5, push=0.5)]
        return [equalise(low_cut=28.0, high_shelf=(4000.0, -2.0)), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.2), ceiling(-1.5, push=0.5)]
    # (2026-11-17, night: the first pieces of the night held against the stems that were liked, studio/ear.py: the pads
    # 5 to 9 dB too bright from 2.5 to 10 kHz, the tune 3 to 6 dB too bright and short of its middle, the drums 2 to 7 dB
    # too bright, the accompaniment 1 to 3 dB dull. Half of each is taken back here, and after the second pass (pads still 3 dB
    # bright, the tune 3 dB) half of what was left: the liked stems were separated from
    # whole mixes, and separation dulls the top a little.)
    if channel == "drums":
        return [equalise(low_cut=28.0, high_shelf=(5000.0, -2.5)), drum_room(), squeeze(-12.0, 2.5, 25.0, 180.0, 1.0), warm(0.3),
                ceiling(-1.5, push=1.0)]
    if channel == "bass":
        # More of the bottom, and harmonics of it so that it is heard on small loudspeakers too; tape to thicken it.
        return [equalise(low_cut=28.0, low_shelf=(90.0, 2.5)), enhance(0.35), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.25),
                ceiling(-1.5, push=1.0)]
    if channel == "texture":
        return [equalise(low_cut=28.0, high_shelf=(4000.0, -5.5)), wide(1.25), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.15),
                ceiling(-1.5, push=0.5)]
    if channel == "lead":
        return [equalise(low_cut=28.0, bands=((600.0, 2.0, 1.5),), high_shelf=(5000.0, -3.5)), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0),
                excite(0.1), warm(0.12), ceiling(-1.5, push=0.5)]
    return [equalise(low_cut=28.0, high_shelf=(5000.0, 1.0)), squeeze(-14.0, 2.0, 30.0, 250.0, 1.0), warm(0.15), ceiling(-1.5, push=0.5)]


def hall(seconds: float) -> str:
    """The hall at the foot of a channel's folder (Dragonfly's hall reverb, giving only what
    the room adds): a concert hall that rings `seconds`."""
    # Its "Large Bright Hall", with less ring in the bass and less wobble (its maker's advice for an orchestra).
    return desk.bare("hall", [desk.lv2("Dragonfly Hall Reverb", dry_level=0.0, early_level=0.0, late_level=100.0, size=min(24.0 + 7.5 * seconds, 58.0),
                                       width=100.0, delay=28.0, diffuse=90.0, low_cut=80.0, low_xo=400.0, low_mult=1.2, high_cut=10000.0,
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
    if player.startswith("geonkick:"):
        return _file("geonkick " + player[9:].replace("/", " "))
    if _kit_plug(player):
        return _file("avl " + player[4:].replace("#", " as "))
    return _file(player)


def wanted(names: list[str] | None = None) -> list[str]:
    """Every player the given written instruments need (all of them and the kits' plug-ins,
    if none are given)."""
    out: list[str] = []
    for name in names or list(SOUNDS):
        for player in SOUNDS[name].players:
            if player.name not in out:
                out.append(player.name)
    if not names:
        out += [plug for plug, _ in KIT_PLUGS.values() if plug not in out]
    return out


def _synth(player: str) -> bool:
    return player.startswith(("surge:", "zyn:"))


_tracks: dict[tuple[str, bool], str] = {}


def track_of(player: str, slurs: bool = False) -> str:
    """The text of a player's track: the sampler with its instrument (the one that slurs, for
    a line of single notes), a drum-kit plug-in, or a synth with its patch."""
    if (player, slurs) not in _tracks:
        if _synth(player):
            _tracks[(player, slurs)] = desk.template(template_of(player))
        elif player.startswith("geonkick:"):
            _tracks[(player, slurs)] = desk.bare(template_of(player), [desk.geonkick(player[9:])])
        elif _kit_plug(player):
            _tracks[(player, slurs)] = desk.bare(template_of(player), [desk.lv2(player[4:].split("#")[0])])
        else:
            _tracks[(player, slurs)] = desk.bare(_file(player), [desk.sfizz(instrument(player, slurs))])
    return _tracks[(player, slurs)]


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
    if name.startswith("geonkick:") or name in NAKED:
        return [Note(beat * 1.5, 0.5, 60 if name.startswith("geonkick:") else 36, 0.75) for beat in range(4)], firm
    if _kit_plug(name):
        struck = {"war": (41, 45, 36, 41), "hands": (36, 38, 41, 45)}.get(_role(name), (36, 38, 41, 38))
        return [Note(beat * 2.0, 0.5, pitch, 0.75) for beat, pitch in enumerate(struck)], firm
    if name in DRUMS:
        low, high = _range(name)
    else:
        read = patch(name)
        low, high = read.low, read.high
    return [Note(beat * 3.0, 2.6, low + int((high - low) * part), 0.75) for beat, part in enumerate((0.25, 0.5, 0.75))], firm


# What a recorded instrument is held against among the recordings that were liked (studio.ear:
# what the stem was asked for, and its strength), by the instrument's first word. Only where
# the same instrument is there at the same strength: a bassoon held against a woodwind choir,
# or a section played firmly against one played softly, is told to be something it is not.
# With each: the most its top may be lifted, and the most it may be cut, in dB.
HEARD_AS = {"violins": ("violins in", "hard", 5.0, 3.0), "violin": ("solo fiddle", "", 5.0, 3.0), "horn": ("french horns in unison", "", 5.0, 3.0),
            "trumpet": ("trumpets in unison", "", 3.0, 6.0), "harp": ("solo harp", "", 0.0, 6.0)}


def _heard_as(name: str) -> tuple[str, str, float, float] | None:
    if _synth(name) or _kit_plug(name) or name not in RECORDED or name.endswith(("short", "pizz", "trem")):
        return None
    return HEARD_AS.get(name.split(" ")[0])


def levels(names: list[str], *, display: str, bpm: float = 120.0) -> dict[str, dict[str, float]]:
    """Plays each player alone, twice, and writes down three things for it. From its bare
    sound: how many dB it has to be turned to come out at LEVEL ("before" in levels.json: this
    is done ahead of its effects, so that every compressor and tape meets the level it is set
    for), and what the equaliser has to do to its top for it to stand where the same
    instrument stands in the recordings that were liked (voicing.json, see `voiced`). Then,
    with its effects on: how many more dB ("after": this is its fader)."""
    from .. import analysis
    from . import ear
    work = desk.TEMPLATES / "levels"
    work.mkdir(parents=True, exist_ok=True)
    each_s = 6.0
    had = json.loads(LEVELS.read_text(encoding="utf-8")) if LEVELS.is_file() else {}
    had = {name: value for name, value in had.items() if isinstance(value, dict)}
    global _voicing
    tones = json.loads(VOICING.read_text(encoding="utf-8")) if VOICING.is_file() else {}
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
        if stage == "before":
            for name in names:
                against = _heard_as(name)
                if against is None:
                    tones.pop(template_of(name), None)
                    continue
                mine = ear.profile(heard[template_of(name)], desk.RATE)
                tones[template_of(name)] = ear.top(mine, ear.reference(against[0], strength=against[1]), lift=against[2], cut=against[3])
            VOICING.write_text(json.dumps(tones, indent=1, sort_keys=True), encoding="utf-8")
            _voicing = tones
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
          ("recorder", 0.4), ("ocarina", 0.4), ("harmonica", 0.3), ("flute", 0.45), ("piccolo", 0.45), ("oboe", 0.45), ("clarinet", 0.45), ("bassoon", 0.45),
          ("small organ", 0.5), ("horn", 0.6), ("balafon", 0.6), ("frame drum", 0.6), ("trumpet", 0.65), ("trombone", 0.65), ("tuba", 0.65),
          ("surge", 0.7), ("marimba", 0.7), ("vibes", 0.7), ("glock", 0.75), ("tube glock", 0.75), ("xylophone", 0.75), ("anvil", 0.75),
          ("hand chimes", 0.8), ("organ", 0.85), ("tubular bells", 0.85), ("war drum", 0.85), ("tom mallet", 0.85), ("kit", 0.85), ("avl", 0.85),
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
    send = WAR_SEND if player in ("war drums", "boom", "gong") or _role(player) == "war" else SENDS[kind]
    if player.startswith("geonkick:"):
        return 0.0, []                                   # a sub does not ring in a hall
    if player in NAKED:
        return 10 ** (-20.0 / 20.0) * room, []
    if kind == "drums":
        return 10 ** (send / 20.0) * room, []           # the drums have their own room, on their bus
    depth = depth_of("surge" if _synth(player) else name)
    if _dry(player):
        return 10 ** ((send + 2.0) / 20.0) * room, [row(max(depth, 0.3), dry=True)]
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
    for index, note in enumerate(ordered):
        begin, end = int((note.start - first) / step), min(int((note.start + note.length - first) / step) + 1, count)
        if end <= begin:
            continue
        strength = min(max((note.loud - 0.12) / 0.8, 0.05), 1.0)
        shape = np.full(end - begin, strength)
        if note.length >= long and not swells:
            # A long note leans in, is fullest past its middle and eases off; how far and where differs from note to
            # note (but is the same each time the piece is played), and the last note of a phrase falls away.
            along = np.linspace(0.0, 1.0, end - begin)
            draw = (note.start * 7.31 + note.pitch * 0.37) % 1.0
            peak, depth = 0.55 + 0.2 * draw, 0.2 + 0.12 * ((draw * 3.7) % 1.0)
            climb = np.where(along < peak, along / peak, 1.0 - 0.6 * (along - peak) / (1.0 - peak))
            after = ordered[index + 1] if index + 1 < len(ordered) else None
            ends_phrase = after is None or (after.start - note.start - note.length) * 60.0 / bpm >= 0.4
            fall = np.where(along > 0.75, 1.0 - (0.45 if ends_phrase else 0.12) * (along - 0.75) / 0.25, 1.0)
            shape = strength * (1.0 - depth + depth * np.sin(0.5 * np.pi * np.clip(climb, 0.0, 1.0))) * fall
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
    if _kit_plug(player):
        return 0, 127
    if player in NAKED:
        return 24, 60
    if player in DRUMS:
        return min(part[3] for part in DRUMS[player][0]), max(part[4] for part in DRUMS[player][0])
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


def _slurred(notes: list[Note], beat: float) -> list[Note] | None:
    """If these notes are one line (no two of them sound together), the line as a player
    plays it: each note that is followed at once by a different one is held a moment into it,
    which is what tells the instrument to slur the second to the first. None, if they are not
    one line. A note followed by a gap, or by the same note again, is left as it is: the next
    one starts afresh."""
    ordered = sorted(notes, key=lambda note: (note.start, note.pitch))
    out = []
    for this, after in zip(ordered, ordered[1:] + [None]):
        if after is None:
            out.append(this)
            break
        gap = (after.start - this.start - this.length) * beat          # seconds of silence between them
        if after.start - this.start < 1e-6 or gap < -0.05:
            return None                                                 # together, or one over the other: chords
        if gap <= 0.09 and after.pitch != this.pitch:
            out.append(Note(this.start, after.start - this.start + 0.045 / beat, this.pitch, this.loud))
        else:
            out.append(this)
    return out


MUSE_LEVEL = 6.0               # dB: MuseScore's recordings are laid in this much up (it leaves a lot of room over its sounds)
MUSE_SEND = -12.0              # dB to the hall: Muse Sounds come with a room of their own; this sets them deep in one hall with the rest
MUSE_SENDS = {"Horn in F": -9.0, "Trumpet in B♭": -10.0, "Trombone": -10.0, "Tuba": -12.0, "Women": -8.0, "Men": -8.0, "Harp": -9.0, "Celesta": -8.0,
              "Tubular Bells": -7.0, "Glockenspiel": -8.0, "Contrabasses": -16.0,
              # A band stands close: its amplifiers a little way into the hall, its bass hardly at all, the tune further in.
              "Rhythm Guitar": -19.0, "Muted Guitar": -22.0, "Electric Guitar": -11.0, "Bass Guitar": -26.0, "Hammond Organ": -14.0}
ECHOED = ("Harp", "Celesta", "Glockenspiel", "Marimba", "Vibraphone", "Classical Guitar", "Clean Guitar")       # parts that get a tempo echo from side to side
MUSE_CUT = {"Violins 1": 170.0, "Violin": 170.0, "Violas": 115.0, "Viola": 115.0, "Flute": 230.0, "Piccolo": 480.0, "Oboe": 210.0, "Trumpet in B♭": 150.0,
            "Clarinet in B♭": 130.0, "Women": 150.0, "Celesta": 200.0, "Glockenspiel": 400.0,
            "Rhythm Guitar": 85.0, "Muted Guitar": 85.0, "Electric Guitar": 110.0, "Hammond Organ": 90.0,       # under the guitars and the organ is the bass guitar's
            # A sound given to a part of another size: its own cut, not the part's (a bass flute is not a flute's 230 Hz).
            "Muse Woodwinds/Bass Flute": 90.0, "Muse Woodwinds/Bass Clarinet": 45.0, "Muse Brass/Euphonium": 40.0, "Muse Handbells/Handbells": 180.0,
            "Muse Woodwinds/Contrabassoon": 22.0, "Muse Woodwinds/Contrabass Flute": 40.0, "Muse Choir/Full Choir": 70.0,
            "Muse Handbells/Handchimes": 180.0, "Muse Keys/Dream Piano": 35.0}
MUTED_TOP = 3200.0             # Hz: a muted string has nothing above this
# Where the two rhythm guitars sit (one each side, as a record is made), and how far the second is behind the
# first: two takes are never together to the sample, and that is what makes two guitars sound like two.
MUSE_SEATS = {"Muse Guitars Vol 1/Electric LP - Heavy": -0.6, "Muse Guitars Vol 1/Electric SC - Heavy": 0.65}
MUSE_LATE = {"Muse Guitars Vol 1/Electric SC - Heavy": 0.011}
# The band's sounds one at a time against the rock stems that were liked (2026-11-16: the same riff, tune and bass
# line played by each, measured by octave). Played the same riff the Les Paul is 8 dB quieter than the Stratocaster
# (-26 against -18.5 LUFS): they are brought level, the Stratocaster a little under, since it is all middle. The Les
# Paul has 6 dB more than the liked guitars from 1.2 to 5 kHz and 24 dB more fizz over 10 kHz; the Stratocaster has
# 9 dB more at 320 to 640 Hz (a honk); the lead is 9 dB hotter at 2.5 to 5 kHz than the liked leads are; the bass is
# close, with less of the pick; the Hammond is brighter, and so wide that its two sides nearly cancel in the bass.
MUSE_TRIM = {"Muse Guitars Vol 1/Electric LP - Heavy": 4.0, "Muse Guitars Vol 1/Electric SC - Heavy": -5.0}
# (The first whole piece, "Lance Cry", measured the same evening: the two guitars together stood where the liked ones
# do from 160 Hz to 10 kHz, 6 dB short under 160 Hz; the lead still had 5 dB too much from 640 Hz to 5 kHz and 8 to
# 20 dB too little under 320 Hz: a thin, bright lead. So: more of the bottom string on the Les Paul, and the lead
# given a body and its top taken down further.)
MUSE_TONE = {"Muse Guitars Vol 1/Electric LP - Heavy": dict(low_shelf=(170.0, 3.0), bands=((1800.0, -3.0, 1.5),), high_shelf=(7500.0, -8.0)),
             "Muse Guitars Vol 1/Electric SC - Heavy": dict(bands=((450.0, -5.0, 1.4),)),
             "Muse Guitars Vol 1/Electric LP - Lead": dict(bands=((260.0, 4.0, 1.6), (3200.0, -7.0, 1.8)), high_shelf=(7500.0, -8.0)),
             "Muse Guitars Vol 1/Electric Bass": dict(bands=((800.0, 3.0, 1.2),)),
             "Muse Keys/Hammond Organ": dict(bands=((1500.0, -3.0, 2.0),))}
MUSE_NARROW = {"Muse Guitars Vol 1/Electric Bass": 0.35, "Muse Keys/Hammond Organ": 0.4}       # how much of what differs between left and right is kept


def _muse(voice: Voice, title: str, bpm: float, taste: float, room: float, seed: int) -> list[desk.Line]:
    """The tracks of a voice that MuseScore plays (studio.muse): for each part that has some
    of its notes, MuseScore's recording of that part laid on a track of its own. Which Muse
    Sound plays a part that has several is drawn from the piece's `seed`."""
    import soundfile
    out = []
    for part, way, notes, sound in muse.shared(voice.instrument, voice.notes, seed):
        made = muse.perform(part, notes, bpm=bpm, way=way, sound=sound, swells=voice.swells or None)
        effects = [equalise(low_cut=MUSE_CUT.get(sound or "", MUSE_CUT.get(part, 28.0)), high_cut=MUTED_TOP if part == "Muted Guitar" else 0.0, **MUSE_TONE.get(sound or "", {}))]
        if sound in MUSE_NARROW:
            effects.append(wide(MUSE_NARROW[sound]))
        if part in ECHOED or way == "pizz":
            effects.append(echo(bpm, 0.16))                    # plucked and struck things answer themselves, a dotted eighth later
        if part in ("Horn in F", "Trumpet in B♭", "Trombone", "Tuba"):
            effects.append(warm(0.25))                         # brass through tape: rounder at the top of a swell
        if part == "Electric Guitar":
            effects += [echo(bpm, 0.22), warm(0.2)]            # a lead guitar's echo, and tape on its top
        if part in ("Rhythm Guitar", "Muted Guitar", "Bass Guitar"):
            effects.append(warm(0.2))
        late = MUSE_LATE.get(sound or "", 0.0)
        out.append(desk.Line("%s: %s" % (title, part), desk.bare(part, []), volume=_db(MUSE_LEVEL + MUSE_TRIM.get(sound or "", 0.0)) * taste,
                             pan=MUSE_SEATS.get(sound or "", 0.0),
                             clips=[(late, soundfile.info(str(made)).duration, str(made))], send=_db(MUSE_SENDS.get(part, MUSE_SEND)) * room,
                             effects=effects))
    if voice.instrument in ("basses", "basses slow"):
        # Stacked under the basses where they play out: a synth's plain sub at their pitch, felt more than heard.
        out += lines(Voice(0, notes=list(voice.notes), instrument="sub"), title + " sub", bpm, taste=taste, room=room, seed=seed)
    return out


def lines(voice: Voice, title: str, bpm: float, *, taste: float = 1.0, room: float = 1.0, seed: int = 0) -> list[desk.Line]:
    """The REAPER tracks that play one written voice. `taste` turns it up or down as a whole;
    `room` is how much hall the piece has (1 is the usual). Where MuseScore's orchestra is
    there (studio.muse), it plays the instruments it has; the drums, and whatever it has not,
    are the studio's own."""
    if not voice.drums and voice.instrument in muse.PARTS and muse.available():
        return _muse(voice, title, bpm, taste, room, seed)
    if voice.drums:
        if not voice.instrument.startswith("kit "):
            raise ValueError("The drum voice %s does not say which kit it is" % title)
        out, left = [], list(voice.notes)
        kit = voice.instrument[4:]
        if kit in KIT_PLUGS:
            # The strokes a drum-kit plug-in has are played by it; the rest stay with the recordings in the sampler.
            from .orchestra import KITS
            plug, table = KIT_PLUGS[kit]
            strokes = KITS[kit][1]
            to = {strokes[stroke]: note for stroke, note in table.items() if stroke in strokes}
            mine = [Note(note.start, note.length, to[note.pitch], note.loud) for note in left if note.pitch in to]
            left = [note for note in left if note.pitch not in to]
            if mine:
                send, placed = _placed(plug, room)
                out.append(desk.Line("%s: %s" % (title, template_of(plug)), track_of(plug), mine, volume=_db(level(plug)["after"]) * taste, pan=0.0,
                                     send=send, effects=[turned(level(plug)["before"])] + chain(plug, bpm) + placed))
        if left:
            name = _file(voice.instrument)
            send, placed = _placed(name, room)
            out.append(desk.Line(title, track_of(name), left, volume=_db(level(name)["after"]) * taste, pan=0.0, send=send,
                                 effects=[turned(level(name)["before"])] + chain(name, bpm) + placed))
        if kit in KICKED:
            # An orchestra's bass drum is a soft, deep stroke that small loudspeakers do not carry: the kick goes with it.
            from .orchestra import KITS
            boom = KITS[kit][1]["boom"]
            struck = [Note(note.start, note.length, 36, note.loud) for note in voice.notes if note.pitch == boom]
            if struck:
                own = "boom" in KIT_PLUGS.get(kit, ("", {}))[1]          # the kit's plug-in has a bass drum of its own
                out += lines(Voice(0, notes=struck, instrument="kick"), title + " kick", bpm, taste=taste * (_db(-6.0) if own else 1.0), room=room, seed=seed)
        return out
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
        for note in voice.notes if not player.takes else ():
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
        for written, struck, softer in player.takes:
            # A kit: each written note strikes the kit's drums that are set down for it.
            notes += [Note(note.start, note.length, struck, min(max(note.loud * _db(softer), 0.03), 1.0))
                      for note in voice.notes if written in (-1, note.pitch)]
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
        slurs = False
        if held and not synth and family(player.name) in SLUR:
            joined = _slurred(notes, beat)
            if joined is not None:
                notes, slurs = joined, True                     # a line of single notes: played under one bow, in one breath
        send, placed = _placed(player.name, room)
        effects = [turned(level(player.name)["before"])] + (synth_chain(player.name, bpm) if synth else chain(player.name, bpm)) + placed
        out.append(desk.Line("%s: %s" % (title, name), track_of(player.name, slurs), notes, volume=_db(level(player.name)["after"] + player.gain) * taste,
                             pan=voice.pan if player.seat is None else player.seat,
                             controls=_dynamics(notes, voice.swells, bpm) if held else [], early=early, send=send,
                             effects=[each for each in effects if each]))
    return out


def main(argv: list[str] | None = None) -> int:
    """Sets the instruments up: writes each one for the sampler, plays each alone in REAPER,
    and keeps how loud it is and what its top needs (`levels`).

        uv run --no-sync python -m freerock.studio.sounds                  every instrument
        uv run --no-sync python -m freerock.studio.sounds --only horn      only those with "horn" in their name
    """
    import argparse
    from .orchestra import KITS
    parser = argparse.ArgumentParser(description="Write every instrument, and measure how loud and how bright each one is.")
    parser.add_argument("--only", default="", help="only the players whose name contains this")
    args = parser.parse_args(argv)
    names = [name for name in wanted() + ["kit " + kit for kit in KITS] if args.only in name]
    if not names:
        print("No instrument has %r in its name" % args.only)
        return 2
    reaper.configure()
    with reaper.Display() as display:
        had = levels(names, display=display)
    for name in names:
        each, tone = had[template_of(name)], voiced(name)
        told = "  top: %+.1f dB at 3.5 kHz, %+.1f dB from 7.5 kHz" % (tone["bands"][0][1], tone["high_shelf"][1]) if tone else ""
        print("%-48s before %+6.1f dB  after %+6.1f dB%s" % (template_of(name), each["before"], each["after"], told))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
