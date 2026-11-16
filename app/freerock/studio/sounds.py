"""The sounds: which real instruments play what the writers write.

The writers name their instruments ("violins", "horns", "harp", "kit orchestra"). Here each
name is given its PLAYERS: recorded instruments from the sample sets on the drive, played by
REAPER's sampler, and patches of the Surge XT synth. A written instrument can have several: the
bowed recording for its long notes and the short-bow one for its quick notes; one section for
its low notes and another for its high ones; a synth underneath.

RECORDED is every recorded instrument there is (a folder of single notes, and how to play
them). STROKES and KITS are the drums. SOUNDS is the writers' names. `build` has REAPER make a
track template of each, `levels` measures how loud each one is so that they can all be set to
the same level, and `lines` turns one written voice into the REAPER tracks that play it.

The sample sets: VSCO 2 Community Edition and VCSL (Versilian Studios, CC0). See
tools/stems/README.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import desk, reaper, samples
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


@dataclass(frozen=True)
class Player:
    """One of the real instruments that play a written one, and which of its notes it takes."""
    name: str                  # a recorded instrument, a tuned drum, or "surge:<patch file under Surge's patch folders>"
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
    return Sound((Player("%s %s" % (name, long), "long", seat=seat), Player(name + " short", "short", seat=seat)))


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


CHOIR = "surge:patches_factory/Pads/Retro Choir.fxp"
OOHS = "surge:patches_factory/Pads/Ooh.fxp"
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
    "choir": Sound((Player(CHOIR, gain=-4.0, seat=0.0),)), "oohs": Sound((Player(OOHS, gain=-4.0, seat=0.0),)),
    "timpani": Sound((Player("timpani", seat=-0.1),)),
    "taiko": Sound((Player("war drum", seat=0.0), Player("great drum", gain=-6.0, seat=0.0))),
    "great drum": Sound((Player("great drum", seat=0.0),)), "melodic tom": Sound((Player("tom mallet", seat=0.15),)),
}


# ---------------------------------------------------------------------------------------------
# Reading and building
# ---------------------------------------------------------------------------------------------
def _file(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _.-]+", " ", name).strip()


def patch(name: str) -> Patch:
    """A recorded instrument or tuned drum by name, read from its folder (and kept, since
    reading it means measuring every recording)."""
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
    else:
        raise KeyError("There is no recorded instrument called %r" % name)
    made.save(kept)
    return made


def kit(name: str, strokes: dict[str, int]) -> list[dict]:
    """A whole kit as one track: every stroke the writers know, each on its note."""
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
        out += desk.sampler(samples.struck(files, "%s %s" % (name, stroke), note, release=1500.0))
    return out


def template_of(player: str) -> str:
    """What a player's track template is called."""
    return _file("surge " + Path(player[6:]).stem) if player.startswith("surge:") else _file(player)


def wanted(names: list[str] | None = None) -> list[str]:
    """Every player the given written instruments need (all of them, if none are given)."""
    out: list[str] = []
    for name in names or list(SOUNDS):
        for player in SOUNDS[name].players:
            if player.name not in out:
                out.append(player.name)
    return out


def build(players: list[str], kits: dict[str, dict[str, int]], *, display: str) -> str:
    """Has REAPER make a track template for each of these players and kits."""
    tracks = []
    for player in players:
        fx = [desk.surge(player[6:])] if player.startswith("surge:") else desk.sampler(patch(player))
        tracks.append({"name": template_of(player), "fx": fx})
    desk.TEMPLATES.mkdir(parents=True, exist_ok=True)
    for name, strokes in kits.items():
        made = kit(name, strokes)
        tracks.append({"name": _file("kit " + name), "fx": made})
        # Which notes and strengths each of the kit's samplers answers to, in order: `lines`
        # leaves out the ones a part never strikes.
        (desk.TEMPLATES / (_file("kit " + name) + ".zones.json")).write_text(
            json.dumps([[each["low"], each["high"], each["soft"], each["hard"]] for each in made]), encoding="utf-8")
    return desk.make_tracks(tracks, display=display)


_kit_zones: dict[str, list[list[int]]] = {}


def _needed(zones: list[tuple[int, int, int, int]], notes: list[Note]) -> set[int]:
    """Which samplers a line's notes strike: the numbers of the zones (low, high, soft, hard)
    that some note falls in."""
    struck = {(note.pitch, min(max(int(round(note.loud * 127)), 1), 127)) for note in notes}
    return {index for index, (low, high, soft, hard) in enumerate(zones)
            if any(low <= pitch <= high and soft <= strength <= hard for pitch, strength in struck)}


def levels(names: list[str], *, display: str) -> dict[str, float]:
    """Plays each template alone (three firm notes across its range, or its loudest stroke) and
    writes down how many dB it has to be turned to come out at LEVEL. Kept in levels.json."""
    from .. import analysis
    work = desk.TEMPLATES / "levels"
    work.mkdir(parents=True, exist_ok=True)
    bpm, each_s = 120.0, 6.0
    folders = []
    for name in names:
        text = desk.template(name)
        if name.startswith("kit "):
            from .orchestra import KITS
            strokes = KITS[name[4:]][1]                     # its own drum and its own snare, whatever notes they are on
            notes = [Note(beat, 0.5, strokes[stroke], 0.75) for beat, stroke in ((0, "boom"), (2, "snare"), (4, "boom"), (6, "snare"))]
        elif name.startswith("surge "):
            notes = [Note(beat * 3.0, 2.6, pitch, 0.75) for beat, pitch in enumerate((48, 60, 72))]
        else:
            read = patch(next(player for player in list(RECORDED) + list(TUNED_DRUMS) + list(KETTLES) if _file(player) == name))
            span = read.high - read.low
            notes = [Note(beat * 3.0, 2.6, read.low + int(span * part), 0.75) for beat, part in enumerate((0.25, 0.5, 0.75))]
        folders.append((desk.Line(name, text, notes), []))
    rows = desk.project_flat(folders, bpm=bpm, seconds=each_s, out=work, tail=1.0)
    rpp = work / "levels.rpp"
    rpp.write_text(rows, encoding="utf-8")
    desk.render(rpp, display=display)
    had = json.loads(LEVELS.read_text(encoding="utf-8")) if LEVELS.is_file() else {}
    heard = desk.stems(work, names, int((each_s + 1.0) * desk.RATE))
    for name, audio in heard.items():
        loud = analysis.loudness_lufs(audio, desk.RATE)
        if loud < -70.0:
            raise RuntimeError("The instrument %s made no sound when it was played alone" % name)
        had[name] = round(LEVEL - loud, 2)
    LEVELS.write_text(json.dumps(had, indent=1, sort_keys=True), encoding="utf-8")
    return had


_levels: dict[str, float] | None = None


def level(name: str) -> float:
    global _levels
    if _levels is None:
        if not LEVELS.is_file():
            raise FileNotFoundError("The instruments' levels have not been measured yet (%s)" % LEVELS)
        _levels = json.loads(LEVELS.read_text(encoding="utf-8"))
    if name not in _levels:
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
          ("surge", 0.7), ("marimba", 0.7), ("vibes", 0.7), ("glock", 0.75), ("tube glock", 0.75), ("xylophone", 0.75),
          ("hand chimes", 0.8), ("organ", 0.85), ("tubular bells", 0.85), ("war drum", 0.85), ("tom mallet", 0.85), ("kit", 0.85),
          ("timpani", 0.9), ("great drum", 0.9))
SEND_FRONT, SEND_BACK = -16.0, -6.5            # dB of a player sent to the hall, at the front of the stage and at the back


def depth_of(template: str) -> float:
    found = [(len(name), depth) for name, depth in DEPTHS if template.startswith(name)]
    if not found:
        raise KeyError("Nothing says how far back %r sits" % template)
    return max(found)[1]


def _placed(template: str, room: float) -> tuple[float, list[str]]:
    """How much of a player goes to the hall, and the effects that set it back from the front."""
    depth = depth_of(template)
    send = 10 ** ((SEND_FRONT + (SEND_BACK - SEND_FRONT) * depth) / 20.0) * room
    effects = [desk.js("sstillwell/hpflpf", 0, 18000 - 9000 * depth, 0)] if depth >= 0.3 else []
    return send, effects


def _breathe(notes: list[Note], bpm: float) -> list[tuple[float, float]]:
    """A held note is never still: it swells a little after it starts and falls away towards
    its end. For a line of one note at a time; where notes pile up, nothing is done."""
    long = 1.2 * bpm / 60.0
    ordered = sorted(notes, key=lambda note: note.start)
    for first, second in zip(ordered, ordered[1:]):
        if second.start < first.start + first.length * 0.8:
            return []
    moves: list[tuple[float, float]] = []
    for note in ordered:
        if note.length < long:
            continue
        if moves and note.start <= moves[-1][0]:
            continue
        moves += [(note.start, 0.84), (note.start + note.length * 0.4, 1.0), (note.start + note.length * 0.97, 0.8)]
    return moves


def _range(player: str) -> tuple[int, int]:
    if player.startswith("surge:"):
        return 24, 108
    read = patch(player)
    return read.low, read.high


def lines(voice: Voice, title: str, bpm: float, *, taste: float = 1.0, room: float = 1.0) -> list[desk.Line]:
    """The REAPER tracks that play one written voice. `taste` turns it up or down as a whole;
    `room` is how much hall the piece has (1 is the usual)."""
    if voice.drums:
        if not voice.instrument.startswith("kit "):
            raise ValueError("The drum voice %s does not say which kit it is" % title)
        name = _file(voice.instrument)
        gain = 10 ** (level(name) / 20.0) * taste
        send, effects = _placed(name, room)
        if name not in _kit_zones:
            _kit_zones[name] = json.loads((desk.TEMPLATES / (name + ".zones.json")).read_text(encoding="utf-8"))
        text = desk.pruned(desk.template(name), _needed([tuple(zone) for zone in _kit_zones[name]], voice.notes))
        return [desk.Line(title, text, list(voice.notes), volume=gain, pan=0.0, send=send, effects=effects)]
    if voice.instrument not in SOUNDS:
        raise KeyError("Nothing is set down to play the written instrument %r (voice %s)" % (voice.instrument, title))
    sound = SOUNDS[voice.instrument]
    beat = 60.0 / bpm
    # The writers' swells are from 0 to 1. A real player's swell is told mostly by which
    # recording answers (soft bow or hard), so the fader moves less than the swell does.
    moves = [(at, max(amount, 0.0) ** 1.3) for at, amount in voice.swells]
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
        gain = 10 ** ((level(name) + player.gain) / 20.0) * taste
        early, held = voice.shift, False
        text = desk.template(name)
        if not player.name.startswith("surge:"):
            read = patch(player.name)
            text = desk.pruned(text, _needed([(zone.low, zone.high, zone.soft, zone.hard) for zone in read.zones], notes))
            if player.name in RECORDED:
                held = read.held
                early = max(early, read.attack / 2000.0)        # an instrument that speaks softly is played that much ahead
        send, effects = _placed(name, room)
        out.append(desk.Line("%s: %s" % (title, name), text, notes, volume=gain,
                             pan=voice.pan if player.seat is None else player.seat,
                             moves=moves or (_breathe(notes, bpm) if held else []), early=early, send=send, effects=effects))
    return out
