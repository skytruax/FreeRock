"""The orchestra's writer: original music for the Warcraft style, written as notes.

A track is a story in five parts. It opens (a drone, a fragment of the tune on one instrument),
states its theme, rises (the accompaniment quickens, fragments of the theme climb, the drums
roll in), comes to its moment (the theme again with everyone playing, sometimes lifted into a
higher key) and closes. How big the moment is depends on what the track is for: a village dance
comes to a merry tutti of fiddles and tambourine, a march through the mountains to horns and
timpani.

What is written first is a FAMILY: the kind of place and moment it is for (its character), its
key, tempo and metre, and its changes, the chord under every bar of the story. Then TAKES: each
take is the whole story over those changes, written afresh from its own seed, with its own tune,
its own accompaniment figure, bass line and drums, and its own choice of instruments from the
character's palette. Since every take of a family follows the same chords bar for bar, the
player can put the drums of one with the tune of another.

Nothing here is copied from anywhere. The tunes are built the way tunes are: a motif of a bar,
answered, repeated a step higher, and brought home; long notes on the notes of the chord, steps
between them; the highest note late in the phrase.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .score import Voice
from .theory import BRIGHT, Chord, Key, Line, tones, voiced

# ---------------------------------------------------------------------------------------------
# The instruments (MuseScore General: bank, program) and where each one sounds well
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Instrument:
    bank: int
    program: int
    low: int
    high: int
    home: int                  # the middle of where its tunes sit
    held: bool = True          # it sustains for as long as the note is written (a bow, a breath); a plucked one does not
    level: float = 1.0         # a taste: this one a little under the others whatever it measures
    early: float = 0.0         # seconds it is played ahead, for instruments that speak slowly
    wired: bool = False        # an electric guitar: recorded clean and played through the amplifier (studio.amp)


I = Instrument
INSTRUMENTS = {
    "flute": I(0, 73, 60, 96, 79), "piccolo": I(0, 72, 74, 103, 90, level=0.8), "oboe": I(0, 68, 58, 89, 72),
    "english horn": I(0, 69, 52, 81, 65), "clarinet": I(0, 71, 50, 89, 67), "bassoon": I(0, 70, 34, 70, 50),
    "recorder": I(0, 74, 60, 93, 77), "pan flute": I(0, 75, 60, 93, 76), "shakuhachi": I(0, 77, 55, 86, 70),
    "whistle": I(0, 78, 72, 98, 84, level=0.8), "ocarina": I(0, 79, 60, 91, 76),
    "trumpet": I(0, 56, 55, 82, 70), "trombone": I(0, 57, 40, 70, 55), "tuba": I(0, 58, 28, 55, 40),
    "horns": I(0, 60, 41, 74, 58), "brass": I(0, 61, 48, 82, 62, level=0.9),
    "violin": I(0, 40, 55, 96, 74), "viola": I(0, 41, 48, 84, 62), "cello": I(0, 42, 36, 74, 52),
    "violins": I(20, 48, 55, 96, 74, early=0.02), "violins slow": I(20, 49, 55, 96, 74, early=0.08),
    "violas": I(30, 48, 48, 84, 62, early=0.02), "celli": I(40, 48, 36, 72, 50, early=0.02),
    "celli slow": I(40, 49, 36, 72, 50, early=0.08), "basses": I(50, 48, 28, 52, 38, early=0.03),
    "basses slow": I(50, 49, 28, 52, 38, early=0.08),
    "strings": I(0, 48, 36, 96, 64, early=0.02), "strings slow": I(0, 49, 36, 96, 64, early=0.08),
    "tremolo": I(0, 44, 36, 96, 64, early=0.03), "pizzicato": I(0, 45, 36, 91, 62, held=False),
    "celli pizz": I(40, 45, 36, 72, 50, held=False), "basses pizz": I(50, 45, 28, 52, 38, held=False),
    "harp": I(0, 46, 31, 96, 64, held=False), "celesta": I(0, 8, 60, 105, 84, held=False),
    "glock": I(0, 9, 72, 105, 88, held=False, level=0.7), "music box": I(0, 10, 60, 96, 79, held=False),
    "vibes": I(0, 11, 53, 89, 70, held=False), "marimba": I(0, 12, 45, 96, 65, held=False),
    "xylophone": I(0, 13, 65, 105, 84, held=False, level=0.8), "bells": I(0, 14, 55, 84, 69, held=False),
    "church bell": I(8, 14, 48, 72, 60, held=False), "dulcimer": I(0, 15, 55, 91, 70, held=False),
    "organ": I(0, 19, 36, 91, 60, level=0.8), "harpsichord": I(0, 6, 36, 89, 65, held=False),
    "accordion": I(0, 21, 53, 89, 69, level=0.8), "guitar": I(0, 24, 40, 84, 60, held=False),
    "steel guitar": I(0, 25, 40, 84, 62, held=False), "mandolin": I(16, 25, 55, 91, 72, held=False),
    "twelve string": I(8, 25, 40, 84, 62, held=False), "sitar": I(0, 104, 48, 84, 64, held=False),
    "koto": I(0, 107, 48, 91, 67, held=False), "kalimba": I(0, 108, 60, 96, 76, held=False),
    "banjo": I(0, 105, 48, 84, 64, held=False), "bagpipe": I(0, 109, 58, 82, 70, level=0.7),
    "fiddle": I(0, 110, 55, 96, 74), "shenai": I(0, 111, 58, 86, 70, level=0.8),
    "choir": I(0, 52, 48, 81, 64, early=0.05), "oohs": I(0, 53, 48, 84, 65, early=0.05),
    "timpani": I(0, 47, 36, 57, 45, held=False), "taiko": I(0, 116, 36, 60, 45, held=False),
    "great drum": I(8, 116, 36, 60, 43, held=False), "melodic tom": I(0, 117, 36, 72, 48, held=False),
    "acoustic bass": I(0, 32, 28, 60, 40, held=False),
    # The band. The guitars are the SoundFont's clean and muted ones, driven by our own amplifier.
    "rhythm guitar": I(0, 27, 40, 76, 50, held=False, wired=True), "muted guitar": I(0, 28, 40, 72, 47, held=False, wired=True),
    "lead guitar": I(0, 27, 52, 86, 67, wired=True), "picked bass": I(0, 34, 28, 55, 38, held=False),
    "rock organ": I(0, 18, 36, 84, 60, level=0.8), "harmonica": I(0, 22, 60, 84, 72),
    "fretless": I(0, 35, 28, 60, 40),
}

# Percussion: a kit (its program on the drum channel) and its strokes by name.
_STROKES = {"shake": 82, "jingle": 83, "castanet": 85, "tick": 75, "high": 60, "low": 61, "deep": 87, "mute": 86,
            "conga": 63, "conga low": 64, "block": 76, "block low": 77, "guiro": 73, "bell": 53,
            "hat": 42, "hat open": 46, "ride": 51, "tom": 45, "tom low": 41, "tom high": 48, "cowbell": 56}
KITS = {
    "orchestra": (48, dict(_STROKES, boom=36, snare=38, crash=59, crash2=57, tamb=54, ting=81, clack=39)),
    "march": (48, dict(_STROKES, boom=36, snare=40, crash=57, crash2=59, tamb=54, ting=81, clack=37)),
    "folk": (0, dict(_STROKES, boom=36, snare=37, crash=55, crash2=49, tamb=54, ting=81, clack=39)),
    "hands": (0, dict(_STROKES, boom=64, snare=63, crash=55, crash2=49, tamb=54, ting=80, clack=62, shake=70, jingle=69)),
    "wood": (0, dict(_STROKES, boom=87, snare=77, crash=55, crash2=49, tamb=69, ting=76, clack=75)),
    "rock": (16, dict(_STROKES, boom=36, snare=38, crash=49, crash2=57, tamb=54, ting=81, clack=37)),
    "room": (8, dict(_STROKES, boom=36, snare=38, crash=49, crash2=57, tamb=54, ting=81, clack=37)),
}
# How loud each instrument's samples are, played alone at a middling strength (LUFS, measured
# 2026-11-15 with tools/stems notes): the quietest is eighteen decibels under the loudest. Every
# instrument is turned down to the level of the quietest ones, so that what is written loud is
# loud and what is written soft is soft whoever plays it.
LOUD = {
    "music box": -37.3, "dulcimer": -36.1, "harpsichord": -35.0, "xylophone": -34.2, "steel guitar": -32.4,
    "melodic tom": -31.6, "sitar": -31.3, "timpani": -31.2, "celesta": -31.0, "great drum": -30.8, "guitar": -30.6,
    "english horn": -30.5, "taiko": -30.1, "kalimba": -30.1, "basses": -30.0, "glock": -29.6, "koto": -29.5,
    "accordion": -29.4, "marimba": -29.3, "strings slow": -28.9, "vibes": -28.9, "pizzicato": -28.9, "tremolo": -28.5,
    "fiddle": -27.6, "mandolin": -27.5, "harp": -27.5, "bells": -27.3, "choir": -26.8, "banjo": -26.1, "oohs": -26.0,
    "organ": -25.6, "celli": -25.5, "strings": -25.4, "viola": -25.3, "brass": -25.0, "clarinet": -24.4, "fretless": -24.2,
    "acoustic bass": -24.2, "violin": -24.2, "shakuhachi": -23.7, "church bell": -23.6, "pan flute": -23.5, "horns": -23.5,
    "violins": -23.3, "bassoon": -22.6, "shenai": -22.2, "cello": -22.1, "tuba": -21.4, "trumpet": -21.4, "oboe": -21.3,
    "flute": -21.2, "recorder": -21.1, "whistle": -20.5, "piccolo": -20.5, "ocarina": -19.5, "trombone": -18.9,
    "bagpipe": -18.7,
    "rhythm guitar": -22.1, "muted guitar": -29.9, "lead guitar": -22.1, "picked bass": -23.5, "rock organ": -24.7,
    "harmonica": -26.0,
    # Not measured one by one: taken as their nearest relation.
    "violins slow": -26.5, "violas": -25.3, "celli slow": -28.0, "basses slow": -31.0, "celli pizz": -28.9,
    "basses pizz": -29.5, "twelve string": -32.4,
}
LEVEL = -34.0                  # every instrument is brought to this, at the same setting of the player


# ---------------------------------------------------------------------------------------------
# Characters: the kinds of track there are
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Character:
    name: str
    kinds: tuple[str, ...]             # the kinds of place it is for
    role: str = "wander"
    light: bool = False
    serves: tuple[int, ...] = (0, 1)
    modes: tuple[str, ...] = ("minor",)
    bpm: tuple[int, int] = (80, 92)
    metres: tuple[str, ...] = ("4/4",)
    busy: float = 0.5                  # how many notes its tunes have
    weight: float = 0.8                # how big its moment is: 0.5 a handful of players, 1 everyone
    leads: tuple[str, ...] = ("oboe", "flute")             # who states the theme
    strong: tuple[str, ...] = ("violins", "trumpet")       # who carries it at the moment
    under: tuple[str, ...] = ("horns",)                    # who answers underneath at the moment
    pads: tuple[str, ...] = ("strings slow",)
    pad_ways: tuple[str, ...] = ("pad",)                   # pad | tremolo | arp | drone
    plucks: tuple[str, ...] = ("pizzicato", "harp")
    figures: tuple[str, ...] = ("pulse", "arp")            # the accompaniment's figure
    basses: tuple[str, ...] = ("celli", "basses")
    kit: str = "orchestra"
    drums: tuple[str, ...] = ("timpani",)                  # pitched drums that join in
    grooves: tuple[str, ...] = ("stately",)
    hall: tuple[float, float] = (2.3, 0.24)                # how long the room rings, and how much of it
    lift: float = 0.3                                      # how likely the moment is to be in a higher key
    titles: tuple[tuple[str, ...], tuple[str, ...]] = (("Old",), ("Road",))
    style: str = "warcraft"                                # the style whose bucket its tracks are for
    band: bool = False                                     # a band, not an orchestra: riffs, a kit, the bass in eighths


C = Character
KINDS_ALL = ("pastoral", "highland", "haunted", "desert", "jungle", "infernal", "regal", "mystic")
CHARACTERS = (
    # --- pastoral ---------------------------------------------------------------------------
    C("village dance", ("pastoral",), light=True, modes=("major", "mixolydian"), bpm=(150, 168), metres=("6/8",), busy=0.75,
      weight=0.6, leads=("fiddle", "whistle", "recorder"), strong=("fiddle", "flute"), under=("clarinet",),
      pads=("accordion", "strings"), pad_ways=("drone", "pad"), plucks=("steel guitar", "mandolin", "pizzicato"),
      figures=("strum", "oompah"), basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("jig", "claps"),
      hall=(1.4, 0.16), lift=0.2,
      titles=(("Harvest", "Maypole", "Barley", "Haystack", "Market Day", "Cider", "Goose Fair", "Sheepfold"),
              ("Reel", "Jig", "Round", "Dance", "Hop", "Fling"))),
    C("morning fields", ("pastoral",), light=True, modes=("major", "lydian"), bpm=(72, 86), busy=0.45, weight=0.6,
      leads=("flute", "oboe", "clarinet"), strong=("violins", "flute"), under=("horns", "celli"),
      pads=("strings slow", "violins slow"), pad_ways=("pad", "arp"), plucks=("harp", "pizzicato"), figures=("arp", "rock"),
      basses=("celli", "basses pizz"), kit="folk", drums=(), grooves=("sparkle",), lift=0.25,
      titles=(("Morning", "Dew", "Lark", "Meadow", "Orchard", "Millpond", "First Light", "Clover"),
              ("Song", "Air", "Fields", "Lane", "Idyll", "Pastoral"))),
    C("riverside waltz", ("pastoral",), light=True, modes=("major", "mixolydian"), bpm=(104, 126), metres=("3/4",), busy=0.5,
      weight=0.65, leads=("clarinet", "violin", "oboe"), strong=("violins", "flute"), under=("celli",),
      pads=("strings", "strings slow"), pad_ways=("pad",), plucks=("pizzicato", "harp", "guitar"), figures=("oompah",),
      basses=("basses pizz", "celli pizz"), kit="folk", drums=(), grooves=("waltz",), lift=0.25,
      titles=(("Riverside", "Willow", "Ferryman's", "Mill", "Swan", "Bridge", "Lantern", "Sunday"),
              ("Waltz", "Turn", "Promenade", "Drift"))),
    C("long road home", ("pastoral",), modes=("dorian", "mixolydian"), bpm=(84, 98), busy=0.5, weight=0.85,
      leads=("english horn", "clarinet", "violin"), strong=("violins", "horns"), under=("celli", "trombone"),
      pads=("strings", "strings slow"), plucks=("pizzicato", "harp"), figures=("pulse", "arp"), basses=("celli", "basses"),
      kit="orchestra", drums=("timpani",), grooves=("stately", "march"),
      titles=(("Long", "Dusty", "Homeward", "Weathered", "Far", "Old"), ("Road", "Miles", "Hills", "Furrows", "Fences", "Way"))),
    # --- highland ---------------------------------------------------------------------------
    C("highland reel", ("highland",), light=True, modes=("mixolydian", "dorian"), bpm=(104, 118), busy=0.8, weight=0.65,
      leads=("whistle", "fiddle", "bagpipe"), strong=("fiddle", "whistle"), under=("accordion",),
      pads=("bagpipe", "strings"), pad_ways=("drone",), plucks=("steel guitar", "mandolin"), figures=("strum", "pulse"),
      basses=("acoustic bass", "celli pizz"), kit="march", drums=(), grooves=("reel", "march"), hall=(1.5, 0.17), lift=0.2,
      titles=(("Heather", "Cairn", "Tarn", "Piper's", "Snowmelt", "Shepherd's", "Windy", "Stag"),
              ("Reel", "Strathspey", "Jig", "Step", "Fling"))),
    C("snowfall", ("highland",), light=True, modes=("major", "lydian", "dorian"), bpm=(66, 80), metres=("3/4", "4/4"), busy=0.35,
      weight=0.55, leads=("flute", "celesta", "clarinet"), strong=("violins slow", "flute"), under=("horns",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "celesta", "glock"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("sleigh", "sparkle"), hall=(2.8, 0.3), lift=0.2,
      titles=(("First", "Quiet", "Falling", "White", "Still", "Lantern"), ("Snow", "Frost", "Drifts", "Pines", "Hearth", "Morning"))),
    C("mountain pass", ("highland",), modes=("dorian", "minor", "mixolydian"), bpm=(76, 92), busy=0.45, weight=1.0,
      leads=("horns", "english horn", "trumpet"), strong=("trumpet", "violins"), under=("horns", "trombone"),
      pads=("strings", "tremolo"), pad_ways=("pad", "tremolo"), plucks=("strings", "pizzicato"), figures=("pulse", "gallop"),
      basses=("celli", "basses"), kit="march", drums=("timpani",), grooves=("march", "stately"), lift=0.45,
      titles=(("High", "Iron", "Eagle", "Storm", "Granite", "Wind-Cut"), ("Pass", "Ridge", "Summit", "Watch", "Crossing", "Stair"))),
    C("moorland ride", ("highland",), modes=("dorian", "mixolydian"), bpm=(132, 150), metres=("6/8",), busy=0.65, weight=0.9,
      leads=("fiddle", "horns", "whistle"), strong=("violins", "trumpet"), under=("horns",), pads=("strings",),
      plucks=("strings", "steel guitar"), figures=("gallop", "pulse"), basses=("celli", "basses"), kit="march",
      drums=("timpani",), grooves=("ride",), lift=0.35,
      titles=(("Moorland", "Hard", "Border", "Gale", "Night", "Courier's"), ("Ride", "Gallop", "Chase", "Run", "Charge"))),
    # --- haunted ----------------------------------------------------------------------------
    C("requiem", ("haunted",), modes=("minor",), bpm=(60, 72), busy=0.3, weight=1.0,
      leads=("english horn", "cello", "oohs"), strong=("violins", "choir"), under=("horns", "trombone"),
      pads=("tremolo", "organ", "strings slow"), pad_ways=("tremolo", "pad"), plucks=("bells", "harpsichord"),
      figures=("toll", "arp"), basses=("basses slow", "celli slow"), kit="orchestra", drums=("timpani", "great drum"),
      grooves=("dirge",), hall=(3.2, 0.34), lift=0.3,
      titles=(("Grave", "Ashen", "Hollow", "Widow's", "Last", "Cold"), ("Requiem", "Vigil", "Procession", "Bell", "Lament", "Vespers"))),
    C("music box", ("haunted",), light=True, modes=("minor", "dorian"), bpm=(88, 104), metres=("3/4",), busy=0.5, weight=0.5,
      leads=("music box", "celesta", "clarinet"), strong=("celesta", "violins slow"), under=("cello",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harpsichord", "pizzicato", "harp"), figures=("oompah", "arp"),
      basses=("celli pizz", "basses pizz"), kit="folk", drums=(), grooves=("tick",), hall=(2.6, 0.3), lift=0.15,
      titles=(("Broken", "Dusty", "Forgotten", "Moth-Eaten", "Porcelain", "Attic"), ("Music Box", "Waltz", "Lullaby", "Nursery", "Doll"))),
    C("danse macabre", ("haunted",), modes=("minor",), bpm=(138, 156), metres=("6/8",), busy=0.7, weight=0.85,
      leads=("fiddle", "clarinet", "oboe"), strong=("violins", "xylophone"), under=("bassoon", "trombone"),
      pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("pizzicato", "harpsichord", "xylophone"),
      figures=("oompah", "pulse"), basses=("celli pizz", "bassoon"), kit="orchestra", drums=("timpani",), grooves=("bones",),
      hall=(2.4, 0.26), lift=0.35,
      titles=(("Midnight", "Bone", "Gallows", "Crooked", "Lantern", "Thirteenth"), ("Dance", "Jig", "Revel", "Round", "Caper"))),
    C("moonlit graves", ("haunted",), light=True, modes=("minor", "dorian"), bpm=(64, 78), busy=0.35, weight=0.55,
      leads=("oboe", "flute", "viola"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad", "arp"), plucks=("harp", "celesta"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("sparkle",), hall=(3.0, 0.32), lift=0.15,
      titles=(("Moonlit", "Pale", "Quiet", "Silver", "Sleeping", "Gentle"), ("Graves", "Yew", "Chapel", "Mist", "Epitaph", "Hour"))),
    # --- desert -----------------------------------------------------------------------------
    C("caravan", ("desert",), light=True, modes=("phrygian dominant", "mixolydian"), bpm=(96, 110), busy=0.65, weight=0.65,
      leads=("shenai", "oboe", "guitar"), strong=("shenai", "violins"), under=("english horn",),
      pads=("strings", "strings slow"), pad_ways=("drone",), plucks=("dulcimer", "guitar", "koto"), figures=("pulse", "strum"),
      basses=("fretless", "celli pizz"), kit="hands", drums=(), grooves=("caravan", "darbuka"), hall=(1.6, 0.18), lift=0.2,
      titles=(("Caravan", "Spice", "Oasis", "Camel", "Bazaar", "Date Palm"), ("Trail", "Song", "Market", "Dance", "Road", "Bells"))),
    C("mirage", ("desert",), light=True, modes=("phrygian dominant", "dorian"), bpm=(66, 80), busy=0.4, weight=0.5,
      leads=("pan flute", "english horn", "guitar"), strong=("violins slow", "pan flute"), under=("celli",),
      pads=("strings slow",), pad_ways=("drone", "pad"), plucks=("guitar", "sitar", "harp"), figures=("arp", "rock"),
      basses=("fretless", "celli slow"), kit="hands", drums=(), grooves=("heat",), hall=(2.4, 0.26), lift=0.15,
      titles=(("Mirage", "Noon", "Still", "Shimmering", "Salt", "White"), ("Dunes", "Well", "Haze", "Flats", "Shade", "Sky"))),
    C("sun anvil", ("desert",), modes=("phrygian", "phrygian dominant"), bpm=(72, 86), busy=0.45, weight=0.95,
      leads=("english horn", "shenai", "trumpet"), strong=("brass", "violins"), under=("trombone", "horns"),
      pads=("strings", "tremolo"), pad_ways=("drone", "tremolo"), plucks=("strings", "dulcimer"), figures=("pulse", "gallop"),
      basses=("basses", "celli"), kit="hands", drums=("taiko", "timpani"), grooves=("war camp",), lift=0.4,
      titles=(("Sun", "Scorpion", "Red Rock", "Vulture", "Burning", "Dust"), ("Anvil", "Throne", "Canyon", "March", "Gate", "Storm"))),
    C("sandstorm ride", ("desert",), modes=("phrygian dominant", "minor"), bpm=(120, 134), metres=("7/8", "4/4"), busy=0.7,
      weight=0.9, leads=("shenai", "fiddle", "oboe"), strong=("violins", "trumpet"), under=("horns",), pads=("strings",),
      pad_ways=("drone", "pad"), plucks=("dulcimer", "strings", "guitar"), figures=("pulse", "gallop"),
      basses=("celli", "fretless"), kit="hands", drums=("taiko",), grooves=("darbuka", "war camp"), lift=0.35,
      titles=(("Sandstorm", "Raider's", "Jackal", "Mesa", "Red Wind", "Nomad"), ("Ride", "Run", "Dance", "Chase", "Whirl"))),
    # --- jungle -----------------------------------------------------------------------------
    C("canopy", ("jungle",), light=True, modes=("major", "dorian", "mixolydian"), bpm=(100, 116), busy=0.7, weight=0.6,
      leads=("pan flute", "ocarina", "marimba"), strong=("marimba", "flute"), under=("clarinet",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("marimba", "kalimba", "xylophone"), figures=("pattern", "arp"),
      basses=("acoustic bass", "melodic tom"), kit="wood", drums=(), grooves=("canopy", "rain"), hall=(1.8, 0.2), lift=0.2,
      titles=(("Canopy", "Parrot", "Vine", "Monkey", "Orchid", "Waterfall"), ("Song", "Dance", "Trail", "Morning", "Chatter", "Swing"))),
    C("river spirits", ("jungle",), light=True, modes=("dorian", "lydian"), bpm=(70, 84), busy=0.4, weight=0.5,
      leads=("shakuhachi", "pan flute", "kalimba"), strong=("shakuhachi", "vibes"), under=("celli",),
      pads=("oohs", "strings slow"), pad_ways=("pad", "arp"), plucks=("kalimba", "harp", "vibes"), figures=("arp", "rock"),
      basses=("fretless", "celli slow"), kit="wood", drums=(), grooves=("rain",), hall=(2.6, 0.28), lift=0.15,
      titles=(("River", "Firefly", "Mist", "Lotus", "Hidden", "Green"), ("Spirits", "Pool", "Shrine", "Dream", "Shallows", "Hollow"))),
    C("prowl", ("jungle",), modes=("minor", "phrygian"), bpm=(126, 144), metres=("6/8",), busy=0.55, weight=0.9,
      leads=("bassoon", "english horn", "shakuhachi"), strong=("horns", "violins"), under=("trombone",),
      pads=("tremolo", "strings"), pad_ways=("tremolo", "drone"), plucks=("marimba", "strings", "xylophone"),
      figures=("pattern", "pulse"), basses=("basses pizz", "melodic tom"), kit="wood", drums=("taiko",), grooves=("hunt",),
      lift=0.35,
      titles=(("Panther", "Raptor", "Fang", "Shadow", "Stalker's", "Tall Grass"), ("Prowl", "Hunt", "Trail", "Drums", "Eyes"))),
    C("swamp fever", ("jungle", "haunted"), modes=("minor", "dorian"), bpm=(76, 90), busy=0.45, weight=0.8,
      leads=("clarinet", "bassoon", "fiddle"), strong=("violins", "clarinet"), under=("trombone",),
      pads=("strings slow", "tremolo"), pad_ways=("pad", "tremolo"), plucks=("banjo", "pizzicato", "marimba"),
      figures=("rock", "pulse"), basses=("acoustic bass", "basses pizz"), kit="wood", drums=(), grooves=("bog",),
      hall=(2.2, 0.24), lift=0.25,
      titles=(("Swamp", "Mire", "Croaking", "Black Water", "Witch's", "Mosquito"), ("Fever", "Blues", "Crossing", "Lantern", "Song"))),
    # --- infernal ---------------------------------------------------------------------------
    C("the forge", ("infernal",), modes=("minor", "phrygian"), bpm=(96, 112), busy=0.5, weight=1.0,
      leads=("trombone", "horns", "trumpet"), strong=("brass", "violins"), under=("trombone", "tuba"),
      pads=("tremolo", "strings"), pad_ways=("tremolo", "pad"), plucks=("strings", "bells"), figures=("hammer", "gallop"),
      basses=("basses", "tuba"), kit="orchestra", drums=("taiko", "timpani"), grooves=("anvil",), lift=0.4,
      titles=(("Great", "Black", "Molten", "Iron", "Deep", "Cinder"), ("Forge", "Hammer", "Bellows", "Furnace", "Anvil", "Foundry"))),
    C("ash march", ("infernal",), modes=("minor", "phrygian"), bpm=(84, 96), metres=("4/4", "5/4"), busy=0.4, weight=1.0,
      leads=("horns", "english horn", "trombone"), strong=("trumpet", "choir"), under=("trombone", "horns"),
      pads=("strings", "choir"), pad_ways=("pad", "tremolo"), plucks=("strings",), figures=("pulse", "hammer"),
      basses=("basses", "celli"), kit="orchestra", drums=("timpani", "great drum"), grooves=("march", "dirge"), lift=0.45,
      titles=(("Ash", "Ember", "Scorched", "Black Banner", "Smoke", "Ruin"), ("March", "Legion", "Column", "Road", "Host", "Advance"))),
    C("embers", ("infernal",), light=True, modes=("dorian", "minor"), bpm=(64, 78), busy=0.35, weight=0.5,
      leads=("cello", "english horn", "clarinet"), strong=("violins slow", "horns"), under=("celli",),
      pads=("strings slow",), pad_ways=("pad", "arp"), plucks=("harp", "guitar"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("sparkle",), hall=(2.6, 0.28), lift=0.15,
      titles=(("Banked", "Dying", "Warm", "Smith's", "Quiet", "Last"), ("Embers", "Coals", "Glow", "Rest", "Hearthstone"))),
    C("lava fields", ("infernal",), modes=("phrygian", "minor"), bpm=(120, 136), busy=0.6, weight=0.95,
      leads=("trumpet", "horns", "oboe"), strong=("brass", "violins"), under=("trombone",), pads=("tremolo",),
      pad_ways=("tremolo",), plucks=("strings", "xylophone"), figures=("gallop", "hammer"), basses=("celli", "basses"),
      kit="orchestra", drums=("taiko", "timpani"), grooves=("anvil", "ride"), lift=0.4,
      titles=(("Lava", "Firewalker's", "Obsidian", "Sulphur", "Red River", "Magma"), ("Fields", "Run", "Crossing", "Dance", "Fury"))),
    # --- regal ------------------------------------------------------------------------------
    C("court dance", ("regal",), light=True, modes=("major", "mixolydian"), bpm=(104, 118), metres=("3/4", "4/4"), busy=0.6,
      weight=0.65, leads=("oboe", "recorder", "violin"), strong=("violins", "oboe"), under=("celli", "bassoon"),
      pads=("strings",), pad_ways=("pad",), plucks=("harpsichord", "pizzicato", "guitar"), figures=("arp", "oompah"),
      basses=("celli", "bassoon"), kit="folk", drums=(), grooves=("courtly",), hall=(1.9, 0.2), lift=0.2,
      titles=(("Courtly", "Queen's", "Garland", "Chancellor's", "Ribbon", "Banquet"), ("Dance", "Minuet", "Galliard", "Pavane", "Air"))),
    C("coronation", ("regal",), modes=("major", "lydian"), bpm=(72, 84), busy=0.4, weight=1.0,
      leads=("horns", "trumpet", "oboe"), strong=("trumpet", "violins"), under=("horns", "trombone"),
      pads=("strings", "brass"), pad_ways=("pad",), plucks=("strings", "harp"), figures=("pulse", "arp"),
      basses=("celli", "basses"), kit="orchestra", drums=("timpani",), grooves=("stately", "march"), lift=0.5,
      titles=(("Coronation", "Crown", "King's", "Banner", "Golden", "Throne"), ("Hymn", "Anthem", "Processional", "Hall", "Oath", "Dawn"))),
    C("city gates", ("regal",), modes=("mixolydian", "major", "dorian"), bpm=(100, 110), busy=0.6, weight=0.9,
      leads=("trumpet", "clarinet", "fiddle"), strong=("trumpet", "violins"), under=("horns",), pads=("strings",),
      plucks=("strings", "pizzicato"), figures=("pulse", "gallop"), basses=("celli", "tuba"), kit="march", drums=("timpani",),
      grooves=("march",), lift=0.4,
      titles=(("City", "Guard's", "Market", "Herald's", "Stone", "Bell Tower"), ("Gates", "Parade", "March", "Square", "Walls", "Watch"))),
    C("cathedral", ("regal", "haunted"), light=True, modes=("dorian", "major", "minor"), bpm=(62, 74), busy=0.3, weight=0.7,
      leads=("oohs", "oboe", "organ"), strong=("choir", "violins slow"), under=("horns",), pads=("organ", "strings slow"),
      pad_ways=("pad",), plucks=("harp", "bells"), figures=("toll", "arp"), basses=("basses slow", "organ"), kit="orchestra",
      drums=(), grooves=("sparkle",), hall=(3.4, 0.36), lift=0.25,
      titles=(("Cathedral", "Vaulted", "Candle", "Stained Glass", "Morning", "Quiet"), ("Light", "Hymn", "Prayer", "Nave", "Choir", "Bells"))),
    # --- mystic -----------------------------------------------------------------------------
    C("moonwell", ("mystic",), light=True, modes=("lydian", "dorian"), bpm=(60, 76), metres=("3/4", "4/4"), busy=0.35,
      weight=0.55, leads=("flute", "ocarina", "oohs"), strong=("violins slow", "flute"), under=("celli",),
      pads=("oohs", "strings slow"), pad_ways=("pad", "arp"), plucks=("harp", "celesta", "vibes"), figures=("arp", "rock"),
      basses=("celli slow", "harp"), kit="folk", drums=(), grooves=("sparkle",), hall=(3.2, 0.34), lift=0.2,
      titles=(("Moonwell", "Starlit", "Silver", "Dreaming", "Elder", "Whispering"), ("Waters", "Glade", "Song", "Boughs", "Vigil", "Light"))),
    C("fireflies", ("mystic",), light=True, modes=("major", "lydian", "mixolydian"), bpm=(92, 108), busy=0.65, weight=0.55,
      leads=("kalimba", "celesta", "flute"), strong=("glock", "flute"), under=("clarinet",), pads=("oohs", "strings slow"),
      pad_ways=("pad",), plucks=("kalimba", "vibes", "harp"), figures=("pattern", "arp"), basses=("fretless", "celli pizz"),
      kit="folk", drums=(), grooves=("sparkle", "tick"), hall=(2.4, 0.26), lift=0.2,
      titles=(("Firefly", "Wisp", "Dewdrop", "Twilight", "Sprite", "Lantern Moth"), ("Dance", "Games", "Flight", "Chase", "Glimmer"))),
    C("ancient ruins", ("mystic",), modes=("minor", "phrygian", "dorian"), bpm=(62, 76), busy=0.35, weight=0.95,
      leads=("english horn", "cello", "oohs"), strong=("violins", "choir"), under=("horns", "trombone"),
      pads=("strings slow", "choir"), pad_ways=("pad", "tremolo"), plucks=("harp", "bells"), figures=("toll", "arp"),
      basses=("basses slow", "celli slow"), kit="orchestra", drums=("timpani", "great drum"), grooves=("dirge", "stately"),
      hall=(3.4, 0.36), lift=0.4,
      titles=(("Sunken", "Elder", "Fallen", "Titan's", "Nameless", "Drowned"), ("Ruins", "Colonnade", "Empire", "Stones", "Halls", "Crown"))),
    C("twilight forest", ("mystic",), modes=("dorian", "minor"), bpm=(84, 98), metres=("6/8", "4/4"), busy=0.5, weight=0.8,
      leads=("clarinet", "viola", "flute"), strong=("violins", "horns"), under=("celli",), pads=("strings", "oohs"),
      pad_ways=("pad", "arp"), plucks=("harp", "pizzicato", "vibes"), figures=("arp", "pulse"), basses=("celli", "basses pizz"),
      kit="folk", drums=("timpani",), grooves=("stately", "sparkle"), hall=(2.6, 0.28), lift=0.3,
      titles=(("Twilight", "Violet", "Owl", "Thornwood", "Dusk", "Antlered"), ("Forest", "Path", "Sentinels", "Hunt", "Canopy", "Song"))),
    # --- the kinds of moment that are not walking about -------------------------------------------
    C("lullaby", ("pastoral", "highland", "regal"), role="night", light=True, modes=("major", "lydian"), bpm=(58, 70),
      metres=("3/4", "4/4"), busy=0.3, weight=0.4, leads=("flute", "clarinet", "celesta"), strong=("violins slow", "flute"),
      under=("celli",), pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "celesta"), figures=("arp", "rock"),
      basses=("celli slow",), kit="folk", drums=(), grooves=("none",), hall=(3.0, 0.32), lift=0.0,
      titles=(("Night", "Sleeping", "Starry", "Shuttered", "Candle", "Crescent"), ("Lullaby", "Watch", "Fields", "Windows", "Hour", "Nocturne"))),
    C("nocturne", ("haunted", "mystic", "jungle"), role="night", modes=("minor", "dorian"), bpm=(56, 68), busy=0.3, weight=0.45,
      leads=("english horn", "viola", "oohs"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("strings slow", "tremolo"), pad_ways=("pad", "tremolo"), plucks=("celesta", "harp", "vibes"), figures=("arp", "toll"),
      basses=("basses slow",), kit="folk", drums=(), grooves=("none",), hall=(3.4, 0.36), lift=0.0,
      titles=(("Owl", "Moonless", "Black", "Whispering", "Cold", "Watchful"), ("Nocturne", "Hours", "Woods", "Vigil", "Night", "Dark"))),
    C("desert night", ("desert", "infernal"), role="night", light=True, modes=("phrygian dominant", "dorian"), bpm=(58, 70),
      busy=0.3, weight=0.4, leads=("pan flute", "guitar", "english horn"), strong=("violins slow", "pan flute"), under=("celli",),
      pads=("strings slow",), pad_ways=("drone",), plucks=("guitar", "harp"), figures=("arp", "rock"), basses=("fretless",),
      kit="hands", drums=(), grooves=("none",), hall=(2.8, 0.3), lift=0.0,
      titles=(("Cold", "Thousand", "Jackal", "Silent", "Blue"), ("Stars", "Sands", "Campfire", "Night", "Dunes"))),
    C("tavern", ("pastoral", "regal", "highland"), role="ember", light=True, modes=("major", "mixolydian", "dorian"), bpm=(112, 126),
      busy=0.75, weight=0.6, leads=("fiddle", "accordion", "recorder"), strong=("fiddle", "accordion"), under=("clarinet",),
      pads=("accordion",), pad_ways=("drone", "pad"), plucks=("steel guitar", "mandolin", "banjo"), figures=("strum", "oompah"),
      basses=("acoustic bass",), kit="folk", drums=(), grooves=("claps", "reel"), hall=(1.1, 0.12), lift=0.2,
      titles=(("Full Tankard", "Innkeeper's", "Warm Hearth", "Crooked Stool", "Last Round", "Travellers'"),
              ("Reel", "Song", "Stomp", "Rest", "Fancy"))),
    C("hearth", ("haunted", "mystic", "jungle", "infernal", "desert"), role="ember", light=True, modes=("dorian", "major"), bpm=(66, 80),
      metres=("3/4", "4/4"), busy=0.4, weight=0.4, leads=("guitar", "clarinet", "cello"), strong=("violin", "flute"), under=("cello",),
      pads=("strings slow",), pad_ways=("pad",), plucks=("guitar", "harp"), figures=("arp", "rock"), basses=("acoustic bass", "celli pizz"),
      kit="folk", drums=(), grooves=("none",), hall=(1.4, 0.15), lift=0.0,
      titles=(("Hearth", "Kettle", "Dry Boots", "Safe", "Shuttered", "Stranger's"), ("Rest", "Fire", "Corner", "Welcome", "Evening"))),
    C("cavern", KINDS_ALL, role="depths",
      modes=("minor", "phrygian"), bpm=(56, 68), busy=0.25, weight=0.6, leads=("bassoon", "english horn", "cello"),
      strong=("horns", "violins slow"), under=("trombone",), pads=("basses slow", "tremolo"), pad_ways=("drone", "tremolo"),
      plucks=("harp", "vibes", "kalimba"), figures=("toll", "rock"), basses=("basses slow",), kit="wood",
      drums=("great drum",), grooves=("drip",), hall=(4.2, 0.45), lift=0.0,
      titles=(("Deep", "Dripping", "Lightless", "Echoing", "Buried", "Cold"), ("Cavern", "Tunnels", "Dark", "Roots", "Hollow", "Stone"))),
    C("crystal cave", KINDS_ALL, role="depths", light=True, modes=("lydian", "dorian"), bpm=(60, 72), busy=0.35, weight=0.45,
      leads=("celesta", "vibes", "flute"), strong=("glock", "violins slow"), under=("celli",), pads=("oohs", "strings slow"),
      pad_ways=("pad", "arp"), plucks=("vibes", "harp", "kalimba"), figures=("arp", "toll"), basses=("celli slow",), kit="wood",
      drums=(), grooves=("drip",), hall=(4.2, 0.45), lift=0.0,
      titles=(("Crystal", "Glowing", "Glimmering", "Underground", "Blue"), ("Cave", "Lake", "Grotto", "Veins", "Pool"))),
    C("tempest", KINDS_ALL, role="storm", serves=(1, 2), modes=("minor", "phrygian"), bpm=(126, 142), busy=0.6, weight=1.0,
      leads=("horns", "trumpet", "violins"), strong=("violins", "brass"), under=("trombone", "horns"), pads=("tremolo",),
      pad_ways=("tremolo",), plucks=("strings",), figures=("gallop", "hammer"), basses=("celli", "basses"), kit="orchestra",
      drums=("timpani", "great drum"), grooves=("thunder",), lift=0.4,
      titles=(("Black", "Howling", "Breaking", "Thunder", "Lashing", "Wild"), ("Tempest", "Squall", "Gale", "Skies", "Rain", "Storm"))),
    C("skirmish", ("pastoral", "highland", "regal", "mystic"), role="battle", serves=(2,), modes=("minor", "dorian"), bpm=(138, 154),
      busy=0.65, weight=1.0, leads=("trumpet", "horns", "violins"), strong=("trumpet", "violins"), under=("horns", "trombone"),
      pads=("tremolo", "strings"), pad_ways=("tremolo", "pad"), plucks=("strings",), figures=("gallop", "hammer"),
      basses=("celli", "basses"), kit="march", drums=("timpani",), grooves=("battle",), lift=0.45,
      titles=(("Drawn", "Crossed", "Sudden", "Border", "Bandit", "Road"), ("Steel", "Swords", "Skirmish", "Ambush", "Clash", "Fray"))),
    C("warband", ("desert", "jungle", "infernal"), role="battle", serves=(2,), modes=("phrygian", "minor", "phrygian dominant"),
      bpm=(132, 148), metres=("4/4", "6/8"), busy=0.6, weight=1.0, leads=("trombone", "shenai", "horns"), strong=("brass", "violins"),
      under=("trombone", "tuba"), pads=("tremolo",), pad_ways=("tremolo", "drone"), plucks=("strings", "marimba"),
      figures=("hammer", "gallop"), basses=("basses", "tuba"), kit="hands", drums=("taiko", "timpani"), grooves=("war drums",),
      lift=0.4,
      titles=(("Blood", "War", "Spear", "Tusk", "Red", "Raider's"), ("Drums", "Band", "Charge", "Fury", "Howl", "Tide"))),
    C("unquiet dead", ("haunted",), role="battle", serves=(2,), modes=("minor",), bpm=(136, 150), metres=("6/8", "4/4"), busy=0.6,
      weight=1.0, leads=("violins", "trombone", "xylophone"), strong=("violins", "choir"), under=("trombone", "horns"),
      pads=("tremolo", "organ"), pad_ways=("tremolo",), plucks=("strings", "xylophone", "harpsichord"), figures=("gallop", "hammer"),
      basses=("celli", "basses"), kit="orchestra", drums=("timpani", "great drum"), grooves=("battle", "bones"), lift=0.4,
      titles=(("Unquiet", "Risen", "Shambling", "Grave", "Rattling", "Cursed"), ("Dead", "Host", "Swarm", "Onslaught", "Legion"))),
    C("titan", KINDS_ALL, role="boss", serves=(2,), modes=("minor", "phrygian"), bpm=(92, 106), metres=("4/4", "5/4"), busy=0.45,
      weight=1.0, leads=("trombone", "horns", "choir"), strong=("brass", "choir"), under=("trombone", "tuba"),
      pads=("choir", "organ", "tremolo"), pad_ways=("pad", "tremolo"), plucks=("strings", "bells"), figures=("hammer", "pulse"),
      basses=("basses", "tuba"), kit="orchestra", drums=("taiko", "timpani", "great drum"), grooves=("colossus",),
      hall=(3.0, 0.3), lift=0.5,
      titles=(("Titan", "World-Breaker", "Dread", "Colossus", "Final", "Ancient"), ("Wakes", "Rising", "Judgement", "Wrath", "Reckoning"))),
    # --- more colours (added after the first forty-four: new ones go at the end, so that the ---
    # --- families already written keep the numbers they were written from) ----------------------
    C("sea shanty", ("pastoral", "mystic"), light=True, modes=("major", "mixolydian", "dorian"), bpm=(132, 150), metres=("6/8",),
      busy=0.65, weight=0.6, leads=("accordion", "fiddle", "whistle"), strong=("fiddle", "accordion"), under=("clarinet",),
      pads=("accordion", "strings"), pad_ways=("drone", "pad"), plucks=("steel guitar", "banjo", "mandolin"),
      figures=("strum", "oompah"), basses=("acoustic bass",), kit="folk", drums=(), grooves=("claps", "jig"), hall=(1.3, 0.14),
      lift=0.25,
      titles=(("Harbour", "Windlass", "Fair Wind", "Gull", "Tidewater", "Deckhand's"), ("Shanty", "Roll", "Reel", "Homecoming", "Song"))),
    C("elven hymn", ("mystic",), light=True, modes=("lydian", "major"), bpm=(56, 68), busy=0.3, weight=0.6,
      leads=("oohs", "flute", "harp"), strong=("oohs", "violins slow"), under=("celli",), pads=("oohs", "strings slow"),
      pad_ways=("pad",), plucks=("harp", "glock", "celesta"), figures=("arp", "toll"), basses=("celli slow", "harp"),
      kit="folk", drums=(), grooves=("sparkle",), hall=(3.6, 0.38), lift=0.3,
      titles=(("Evensong", "Silverleaf", "Starwell", "Dawn Tree", "Moon Priestess", "Elder Grove"), ("Hymn", "Blessing", "Chant", "Canticle"))),
    C("dwarven hall", ("highland", "regal"), modes=("dorian", "mixolydian", "minor"), bpm=(92, 108), metres=("3/4", "4/4"), busy=0.5,
      weight=0.95, leads=("horns", "trombone", "bassoon"), strong=("brass", "horns"), under=("tuba", "trombone"),
      pads=("brass", "strings"), pad_ways=("pad", "drone"), plucks=("strings", "bells"), figures=("hammer", "oompah"),
      basses=("tuba", "basses"), kit="orchestra", drums=("timpani", "great drum"), grooves=("anvil", "stately"), hall=(2.8, 0.3),
      lift=0.4,
      titles=(("Thane's", "Deep Hall", "Stout", "Hammerfall", "Stone Father", "Keg"), ("Hall", "Toast", "Oath", "Stomp", "Hearth"))),
    C("plague wind", ("haunted",), modes=("phrygian", "minor"), bpm=(58, 70), metres=("4/4", "5/4"), busy=0.3, weight=0.9,
      leads=("english horn", "viola", "oohs"), strong=("choir", "violins"), under=("trombone", "bassoon"),
      pads=("tremolo", "choir"), pad_ways=("tremolo", "drone"), plucks=("harpsichord", "church bell", "bells"),
      figures=("toll", "rock"), basses=("basses slow",), kit="orchestra", drums=("great drum",), grooves=("dirge", "drip"),
      hall=(3.6, 0.38), lift=0.25,
      titles=(("Plague", "Withered", "Sorrow", "Empty", "Blight", "Carrion"), ("Wind", "Fields", "Village", "Harvest", "Bell", "Road"))),
    C("oasis dance", ("desert",), light=True, modes=("phrygian dominant", "mixolydian", "dorian"), bpm=(118, 132), metres=("7/8",),
      busy=0.7, weight=0.6, leads=("shenai", "guitar", "pan flute"), strong=("shenai", "dulcimer"), under=("english horn",),
      pads=("strings",), pad_ways=("drone",), plucks=("dulcimer", "koto", "guitar"), figures=("pattern", "pulse"),
      basses=("fretless",), kit="hands", drums=(), grooves=("darbuka", "caravan"), hall=(1.5, 0.16), lift=0.2,
      titles=(("Oasis", "Palm Wine", "Fig", "Water Seller's", "Tent", "Dancing Girl's"), ("Dance", "Feast", "Whirl", "Night", "Bells"))),
    C("troll drums", ("jungle",), modes=("minor", "dorian"), bpm=(104, 120), metres=("5/4", "7/8"), busy=0.55, weight=0.9,
      leads=("pan flute", "bassoon", "marimba"), strong=("horns", "marimba"), under=("trombone",), pads=("tremolo", "strings"),
      pad_ways=("drone", "tremolo"), plucks=("marimba", "xylophone", "kalimba"), figures=("pattern", "pulse"),
      basses=("melodic tom", "basses pizz"), kit="wood", drums=("taiko",), grooves=("hunt", "canopy"), lift=0.3,
      titles=(("Voodoo", "Bonfire", "Spirit Mask", "Tusk", "Loa", "Headhunter's"), ("Drums", "Circle", "Rite", "Chant", "Night"))),
    C("frost giant", ("highland",), modes=("minor", "phrygian"), bpm=(60, 72), busy=0.3, weight=1.0,
      leads=("trombone", "horns", "english horn"), strong=("brass", "violins"), under=("tuba", "trombone"),
      pads=("tremolo", "strings slow"), pad_ways=("tremolo", "pad"), plucks=("strings", "bells"), figures=("toll", "hammer"),
      basses=("basses slow", "tuba"), kit="orchestra", drums=("great drum", "timpani"), grooves=("dirge", "colossus"),
      hall=(3.4, 0.36), lift=0.4,
      titles=(("Frost", "Glacier", "White", "Winter King's", "Frozen", "Avalanche"), ("Giant", "Throne", "Wastes", "March", "Tomb"))),
    C("pilgrim road", ("pastoral", "regal"), light=True, modes=("major", "mixolydian"), bpm=(88, 100), busy=0.55, weight=0.6,
      leads=("clarinet", "guitar", "recorder"), strong=("violins", "clarinet"), under=("bassoon",), pads=("strings",),
      pad_ways=("pad",), plucks=("guitar", "pizzicato", "twelve string"), figures=("rock", "arp"),
      basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("claps", "courtly"), hall=(1.6, 0.17), lift=0.25,
      titles=(("Pilgrim", "Peddler's", "Easy", "Milestone", "Sunlit", "Crossroads"), ("Road", "Walk", "Ramble", "Whistle", "Miles"))),
    C("forge song", ("infernal", "regal"), light=True, modes=("dorian", "mixolydian"), bpm=(96, 110), busy=0.6, weight=0.65,
      leads=("bassoon", "clarinet", "horns"), strong=("clarinet", "horns"), under=("trombone",), pads=("strings", "accordion"),
      pad_ways=("pad", "drone"), plucks=("pizzicato", "marimba", "strings"), figures=("pulse", "pattern"),
      basses=("acoustic bass", "bassoon"), kit="orchestra", drums=(), grooves=("anvil",), hall=(1.8, 0.2), lift=0.25,
      titles=(("Smith's", "Bellows", "Apprentice", "Tongs", "Whetstone", "Quench"), ("Song", "Work", "Rhythm", "Shift", "Whistle"))),
    C("bazaar", ("desert", "regal"), light=True, modes=("phrygian dominant", "major", "mixolydian"), bpm=(120, 136), busy=0.75, weight=0.6,
      leads=("mandolin", "shenai", "oboe"), strong=("mandolin", "violins"), under=("clarinet",), pads=("strings",),
      pad_ways=("drone", "pad"), plucks=("dulcimer", "guitar", "banjo"), figures=("strum", "pattern"),
      basses=("acoustic bass", "fretless"), kit="hands", drums=(), grooves=("caravan", "claps"), hall=(1.4, 0.15), lift=0.25,
      titles=(("Bazaar", "Haggler's", "Brass Lamp", "Silk", "Coin", "Street Juggler's"), ("Bustle", "Song", "Morning", "Dance", "Trade"))),
    C("drowned bell", ("mystic", "haunted"), modes=("minor", "dorian"), bpm=(60, 72), metres=("3/4", "4/4"), busy=0.3, weight=0.85,
      leads=("oohs", "cello", "english horn"), strong=("choir", "violins slow"), under=("horns",), pads=("strings slow", "oohs"),
      pad_ways=("pad", "tremolo"), plucks=("church bell", "harp", "vibes"), figures=("toll", "arp"), basses=("basses slow",),
      kit="orchestra", drums=("great drum",), grooves=("drip", "dirge"), hall=(3.8, 0.4), lift=0.3,
      titles=(("Drowned", "Tidal", "Lost", "Sunken", "Mist", "Wrecker's"), ("Bell", "Shore", "Fleet", "Chapel", "Watch", "Lament"))),
    C("drinking song", ("highland", "regal", "pastoral"), role="ember", light=True, modes=("major", "mixolydian"), bpm=(132, 150),
      metres=("3/4",), busy=0.6, weight=0.6, leads=("accordion", "fiddle", "clarinet"), strong=("accordion", "fiddle"),
      under=("bassoon",), pads=("accordion",), pad_ways=("pad",), plucks=("steel guitar", "banjo"), figures=("oompah",),
      basses=("acoustic bass", "tuba"), kit="folk", drums=(), grooves=("waltz", "claps"), hall=(1.1, 0.12), lift=0.25,
      titles=(("One More", "Brewer's", "Raised Mug", "Barmaid's", "Foaming"), ("Round", "Waltz", "Chorus", "Toast", "Sway"))),
    C("wild hunt", ("mystic", "jungle", "highland"), role="battle", serves=(2,), modes=("dorian", "minor"), bpm=(140, 156),
      metres=("6/8",), busy=0.65, weight=1.0, leads=("horns", "violins", "oboe"), strong=("horns", "violins"),
      under=("trombone",), pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("strings", "xylophone"),
      figures=("gallop", "pulse"), basses=("celli", "basses"), kit="orchestra", drums=("timpani", "taiko"),
      grooves=("ride", "battle"), lift=0.45,
      titles=(("Wild", "Antlered", "Moonlit", "Baying", "Thorn"), ("Hunt", "Chase", "Pack", "Riders", "Horn"))),
    C("blizzard", ("highland", "mystic"), role="storm", serves=(1, 2), modes=("minor", "dorian"), bpm=(118, 132), busy=0.55,
      weight=0.95, leads=("violins", "horns", "piccolo"), strong=("violins", "horns"), under=("trombone",), pads=("tremolo",),
      pad_ways=("tremolo",), plucks=("strings", "glock"), figures=("gallop", "arp"), basses=("celli", "basses"),
      kit="orchestra", drums=("timpani", "great drum"), grooves=("thunder", "sleigh"), lift=0.35,
      titles=(("White", "Blinding", "North", "Howling", "Driving"), ("Blizzard", "Squall", "Wall", "Gale", "Whiteout"))),
    # --- Knight Rock: a band, not an orchestra ------------------------------------------------------
    # Riff guitars through the amplifier, a lead guitar (two of them in thirds at the moment), the
    # bass on the root in steady eighths, a plain hard-hitting kit, and under it a drone as of a
    # hurdy-gurdy. The light ones are the same band unplugged: strummed strings, fiddle and whistle.
    C("open road", ("pastoral", "highland"), light=True, style="knight", band=True, modes=("mixolydian", "major"), bpm=(112, 126),
      busy=0.65, weight=0.65, leads=("fiddle", "harmonica", "whistle"), strong=("fiddle", "whistle"), under=(),
      pads=("accordion", "rock organ"), pad_ways=("drone", "pad"), plucks=("steel guitar", "twelve string", "mandolin"),
      figures=("strum",), basses=("picked bass",), kit="rock", drums=(), grooves=("tavern rock", "rock"), hall=(1.2, 0.13),
      lift=0.3, titles=(("Open", "Sunny", "Wagon", "Milestone", "Free", "Homeward"), ("Road", "Miles", "Wheels", "Ramble", "Highway"))),
    C("banner ride", ("pastoral", "regal", "highland"), style="knight", band=True, modes=("mixolydian", "dorian"), bpm=(118, 132),
      busy=0.6, weight=0.95, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "bagpipe"),
      pad_ways=("drone",), plucks=("rhythm guitar",), figures=("riff",), basses=("picked bass",), kit="rock", drums=(),
      grooves=("rock", "rock ride"), hall=(1.3, 0.14), lift=0.4,
      titles=(("Banner", "Lionheart", "Steel", "Charger", "King's", "Shield"), ("Ride", "Knights", "Oath", "Thunder", "Vanguard"))),
    C("black chapel", ("haunted",), style="knight", band=True, modes=("minor", "phrygian"), bpm=(76, 88), busy=0.45, weight=1.0,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "organ"), pad_ways=("drone", "pad"),
      plucks=("rhythm guitar",), figures=("riff",), basses=("picked bass",), kit="rock", drums=("church bell",),
      grooves=("half rock",), hall=(2.2, 0.22), lift=0.3,
      titles=(("Black", "Grave", "Midnight", "Raven", "Witching", "Cursed"), ("Chapel", "Sabbath", "Bell", "Mass", "Riders", "Hour"))),
    C("lantern walk", ("haunted", "mystic"), light=True, style="knight", band=True, modes=("minor", "dorian"), bpm=(84, 96), busy=0.5,
      weight=0.55, leads=("harmonica", "fiddle", "whistle"), strong=("fiddle", "harmonica"), under=(),
      pads=("rock organ", "strings slow"), pad_ways=("pad",), plucks=("twelve string", "guitar"), figures=("arp", "rock"),
      basses=("picked bass",), kit="room", drums=(), grooves=("brushes",), hall=(1.8, 0.2), lift=0.2,
      titles=(("Lantern", "Foggy", "Crossroads", "Lonesome", "Pale Moon", "Owl"), ("Walk", "Blues", "Ballad", "Road", "Waltz"))),
    C("sand rider", ("desert", "infernal"), style="knight", band=True, modes=("phrygian dominant", "phrygian"), bpm=(120, 134),
      busy=0.6, weight=0.95, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "shenai"),
      pad_ways=("drone",), plucks=("rhythm guitar",), figures=("riff", "chug"), basses=("picked bass",), kit="rock", drums=(),
      grooves=("desert rock", "rock ride"), hall=(1.3, 0.14), lift=0.35,
      titles=(("Sand", "Scorpion", "Mirage", "Red Sun", "Dune", "Cobra"), ("Rider", "Run", "Kings", "Fever", "Strike"))),
    C("oasis shuffle", ("desert", "jungle"), light=True, style="knight", band=True, modes=("mixolydian", "dorian"), bpm=(138, 156),
      metres=("6/8",), busy=0.65, weight=0.6, leads=("mandolin", "whistle", "fiddle"), strong=("mandolin", "fiddle"), under=(),
      pads=("accordion", "rock organ"), pad_ways=("drone", "pad"), plucks=("steel guitar", "banjo"), figures=("strum", "oompah"),
      basses=("picked bass",), kit="room", drums=(), grooves=("shuffle",), hall=(1.2, 0.13), lift=0.25,
      titles=(("Oasis", "Palm", "Lazy River", "Monkey", "Coconut", "Shade Tree"), ("Shuffle", "Swing", "Jig", "Stroll", "Sway"))),
    C("jungle stomp", ("jungle",), style="knight", band=True, modes=("minor", "dorian"), bpm=(100, 112), busy=0.55, weight=0.9,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "pan flute"), pad_ways=("drone",),
      plucks=("rhythm guitar",), figures=("riff", "chug"), basses=("picked bass",), kit="rock", drums=("taiko",),
      grooves=("tom rock",), hall=(1.4, 0.15), lift=0.3,
      titles=(("Jungle", "Tiger", "Vine", "Headhunter", "Gorilla", "Thunder Lizard"), ("Stomp", "Boogie", "Drums", "Crawl", "Fever"))),
    C("forge anthem", ("infernal", "regal"), style="knight", band=True, modes=("minor", "dorian"), bpm=(96, 108), busy=0.5, weight=1.0,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "bagpipe"), pad_ways=("drone", "pad"),
      plucks=("rhythm guitar",), figures=("riff", "hammer"), basses=("picked bass",), kit="rock", drums=(),
      grooves=("anvil rock",), hall=(1.6, 0.17), lift=0.4,
      titles=(("Forge", "Anvil", "Hammer", "Molten", "Ironclad", "Blacksmith's"), ("Anthem", "Thunder", "Law", "Fire", "Hymn"))),
    C("moon glade", ("mystic",), light=True, style="knight", band=True, modes=("lydian", "dorian"), bpm=(80, 92), busy=0.45, weight=0.5,
      leads=("whistle", "ocarina", "harmonica"), strong=("whistle", "fiddle"), under=(), pads=("strings slow", "oohs"),
      pad_ways=("pad",), plucks=("guitar", "twelve string", "harp"), figures=("arp",), basses=("picked bass", "fretless"),
      kit="room", drums=(), grooves=("brushes",), hall=(2.2, 0.24), lift=0.2,
      titles=(("Moon", "Silver", "Starlight", "Willow", "Dreaming", "Fae"), ("Glade", "Ballad", "Serenade", "Waters", "Lullaby"))),
    C("mountain stomp", ("highland",), style="knight", band=True, modes=("dorian", "mixolydian"), bpm=(100, 110), busy=0.5, weight=0.95,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("bagpipe", "rock organ"), pad_ways=("drone",),
      plucks=("rhythm guitar",), figures=("riff",), basses=("picked bass",), kit="rock", drums=(), grooves=("half rock", "anvil rock"),
      hall=(1.5, 0.16), lift=0.35,
      titles=(("Mountain", "Stonefist", "Avalanche", "Iron Boot", "Highland", "Ram"), ("Stomp", "March", "Thunder", "Clan", "Pride"))),
    C("tavern rock", KINDS_ALL, role="ember", light=True, style="knight", band=True, modes=("major", "mixolydian"), bpm=(126, 140),
      busy=0.7, weight=0.6, leads=("fiddle", "harmonica", "accordion"), strong=("fiddle", "accordion"), under=(), pads=("accordion",),
      pad_ways=("drone", "pad"), plucks=("steel guitar", "banjo", "mandolin"), figures=("strum",), basses=("picked bass",),
      kit="rock", drums=(), grooves=("tavern rock",), hall=(1.0, 0.11), lift=0.25,
      titles=(("Barrel", "Rowdy", "Last Call", "Full House", "Table-Top", "Landlord's"), ("Rock", "Stomp", "Boogie", "Singalong", "Round"))),
    C("storm rider", KINDS_ALL, role="storm", serves=(1, 2), style="knight", band=True, modes=("minor", "dorian"), bpm=(138, 150),
      busy=0.6, weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",), pad_ways=("drone", "pad"),
      plucks=("rhythm guitar",), figures=("chug", "riff"), basses=("picked bass",), kit="rock", drums=(), grooves=("rock ride",),
      hall=(1.4, 0.15), lift=0.4,
      titles=(("Storm", "Lightning", "Thunder", "Rain", "Black Cloud", "Tempest"), ("Rider", "Runner", "Road", "Chaser", "Rock"))),
    C("battle cry", ("pastoral", "highland", "regal", "mystic"), role="battle", serves=(2,), style="knight", band=True,
      modes=("minor", "dorian"), bpm=(150, 164), busy=0.6, weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(),
      pads=("rock organ",), pad_ways=("drone",), plucks=("rhythm guitar",), figures=("chug", "riff"), basses=("picked bass",),
      kit="rock", drums=(), grooves=("rock ride", "rock"), hall=(1.2, 0.13), lift=0.4,
      titles=(("Battle", "Sword", "Charge", "Steel", "Fury", "Lance"), ("Cry", "Storm", "Song", "Breaker", "Dance"))),
    C("war machine", ("haunted", "desert", "jungle", "infernal"), role="battle", serves=(2,), style="knight", band=True,
      modes=("phrygian", "minor"), bpm=(140, 156), busy=0.55, weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(),
      pads=("rock organ",), pad_ways=("drone",), plucks=("rhythm guitar",), figures=("chug",), basses=("picked bass",), kit="rock",
      drums=("taiko",), grooves=("tom rock", "rock ride"), hall=(1.2, 0.13), lift=0.4,
      titles=(("War", "Siege", "Skull", "Juggernaut", "Blood", "Wrecking"), ("Machine", "Engine", "Crusher", "Hammer", "March"))),
    C("dragon", KINDS_ALL, role="boss", serves=(2,), style="knight", band=True, modes=("minor", "phrygian"), bpm=(92, 104), busy=0.45,
      weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("choir", "rock organ"), pad_ways=("pad",),
      plucks=("rhythm guitar",), figures=("riff", "hammer"), basses=("picked bass",), kit="rock", drums=("church bell", "taiko"),
      grooves=("half rock",), hall=(2.0, 0.2), lift=0.5,
      titles=(("Dragon", "Tyrant", "Doom", "Overlord", "Wyrm", "Last"), ("Fire", "Throne", "Slayer", "Awakens", "Stand"))),
    C("night watch", KINDS_ALL, role="night", light=True, style="knight", band=True, modes=("dorian", "minor"), bpm=(66, 78), busy=0.4,
      weight=0.45, leads=("harmonica", "whistle", "fiddle"), strong=("harmonica", "fiddle"), under=(), pads=("strings slow",),
      pad_ways=("pad",), plucks=("guitar", "twelve string"), figures=("arp", "rock"), basses=("picked bass",), kit="room", drums=(),
      grooves=("none", "brushes"), hall=(2.0, 0.22), lift=0.0,
      titles=(("Night", "Campfire", "Sentry's", "Starless", "Low Moon"), ("Watch", "Ballad", "Blues", "Embers", "Song"))),
    C("deep mine", KINDS_ALL, role="depths", style="knight", band=True, modes=("minor", "phrygian"), bpm=(80, 92), busy=0.4, weight=0.7,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",), pad_ways=("drone",), plucks=("rhythm guitar",),
      figures=("riff",), basses=("picked bass",), kit="rock", drums=(), grooves=("anvil rock",), hall=(3.4, 0.38), lift=0.0,
      titles=(("Deep", "Pickaxe", "Shaft", "Lamp-Lit", "Cave-In"), ("Mine", "Blues", "Echo", "Dig", "Shift"))),
)

METRES = {"4/4": (4.0, (2.0, 2.0)), "3/4": (3.0, (3.0,)), "6/8": (3.0, (1.5, 1.5)), "5/4": (5.0, (3.0, 2.0)),
          "7/8": (3.5, (1.5, 1.0, 1.0))}

# Changes for eight bars of theme, by mode: four chords are two bars each. The last two bars are
# rewritten as the mode's own way home.
THEMES = {
    "major": ("1 5 6 4", "1 4 5 1", "1 6 4 5", "6 4 1 5", "1 3 4 5", "1 4 6 5", "1 5 4 4 1 5 4 5", "1 1 4 4 6 4 5 5", "1 6 2 5"),
    "lydian": ("1 2 1 5", "1 2 6 5", "1 5 2 1", "1 2 5 1", "1 5 6 2", "1 2 1 6"),
    "mixolydian": ("1 7 4 1", "1 5 4 1", "1 7 1 4", "1 4 7 4", "1 7 4 4 1 7 4 1", "1 4 1 7"),
    "dorian": ("1 4 1 7", "1 3 4 1", "1 7 4 1", "1 4 7 1", "1 3 7 4", "1 7 3 4"),
    "minor": ("1 6 3 7", "1 4 6 5+", "1 7 6 7", "1 3 4 6", "1 5 6 4", "1 6 4 5+", "1 1 6 6 4 4 5+ 5+", "1 7 6 5+",
              "1 4 7 3 6 4 5+ 1"),
    "phrygian": ("1 2 1 7", "1 2 3 2", "1 7 6 2", "1 2 6 2", "1 4 2 1"),
    "phrygian dominant": ("1 2 1 7", "1 4 2 1", "1 2 4 2", "1 7 2 1"),
}
RISES = {
    "major": ("4 5 4 5", "6 4 2 5", "4 4 5 5", "2 3 4 5"), "lydian": ("2 2 5 5", "6 2 5 5", "6 5 2 5"),
    "mixolydian": ("4 4 7 7", "5 4 7 7", "4 7 4 7"), "dorian": ("3 4 3 7", "4 4 7 7", "3 4 7 7"),
    "minor": ("6 7 6 5+", "4 4 5+ 5+", "6 6 7 5+", "4 6 7 5+"), "phrygian": ("2 3 2 2", "6 7 2 2", "4 3 2 2"),
    "phrygian dominant": ("4 2 4 2", "7 2 2 2", "4 4 2 2"),
}
HOME = {"major": ("5", "1"), "lydian": ("2", "1"), "mixolydian": ("7", "1"), "dorian": ("4", "1"), "minor": ("5+", "1"),
        "phrygian": ("2", "1"), "phrygian dominant": ("2", "1")}
COLOUR = {"major": "4", "lydian": "2", "mixolydian": "7", "dorian": "4", "minor": "6", "phrygian": "2", "phrygian dominant": "2"}


# ---------------------------------------------------------------------------------------------
# A family: the changes every take is written over
# ---------------------------------------------------------------------------------------------
@dataclass
class Section:
    story: str
    bars: int
    chords: list[str]              # one for each bar
    level: tuple[float, float]     # how hard it is played at its start and at its end, 0 to 1
    lifted: bool = False           # in the higher key


@dataclass
class Family:
    name: str
    title: str
    character: Character
    seed: int
    key: Key
    bpm: float
    metre: str
    lift: int                      # semitones the moment is lifted by; 0 for none
    sections: list[Section] = field(default_factory=list)

    @property
    def beats(self) -> float:
        return METRES[self.metre][0]

    @property
    def group(self) -> tuple[float, ...]:
        return METRES[self.metre][1]

    @property
    def bars(self) -> int:
        return sum(section.bars for section in self.sections)

    @property
    def seconds(self) -> float:
        return self.bars * self.beats * 60.0 / self.bpm


def _spread(figures: str, bars: int) -> list[str]:
    """A run of chords laid over so many bars, each for as long as the others."""
    chords = figures.split()
    return [chords[min(index * len(chords) // bars, len(chords) - 1)] for index in range(bars)]


def family(character: Character, seed: int, name: str, title: str) -> Family:
    """Makes up the changes for one family of tracks of a character."""
    rng = random.Random(seed)
    mode = rng.choice(character.modes)
    key = Key(rng.randrange(12), mode)
    metre = rng.choice(character.metres)
    beats = METRES[metre][0]
    bpm = float(rng.randint(*character.bpm))
    bar_s = beats * 60.0 / bpm
    # Three minutes or so: the theme and the moment twice as long as the opening and the close,
    # as many bars of each as the tempo leaves room for.
    unit = min((4, 8, 12, 16, 20, 24), key=lambda bars: abs(bars * 7.5 * bar_s - 176.0))
    lengths = {"open": unit, "theme": 2 * unit, "rise": unit + unit // 2, "moment": 2 * unit, "close": unit}
    if character.role in ("battle", "boss", "storm"):
        lengths["open"], lengths["close"] = max(unit // 2, 2), max(unit // 2, 2)      # a fight does not wait
        lengths["rise"] = unit
    theme = _spread(rng.choice(THEMES[mode]), 8)
    theme[6], theme[7] = HOME[mode]
    if theme[3] == "1":
        theme[3] = HOME[mode][0]                       # the first half ends away from home, so the second can come back
    def run(bars: int, eight: list[str]) -> list[str]:
        if bars % 8 == 0:
            return eight * (bars // 8)
        # A length that is not a multiple of eight: the changes at half speed or cut short, ending at home.
        out = [eight[min(index * 8 // bars, 7)] for index in range(bars)]
        out[-2:] = HOME[mode] if bars >= 2 else out[-2:]
        return out
    colour = COLOUR[mode]
    heavy = character.weight
    opening = ["1"] * lengths["open"]
    if lengths["open"] >= 4:
        opening[lengths["open"] // 2] = colour
    closing = [colour if index % 2 == 0 else "1" for index in range(lengths["close"])]
    closing[-1] = "1"
    if lengths["close"] >= 3:
        closing[-2] = "1"
    lift = rng.choice((2, 2, 3)) if rng.random() < character.lift else 0
    made = Family(name=name, title=title, character=character, seed=seed, key=key, bpm=bpm, metre=metre, lift=lift)
    # How hard each part of the story is played, from its start to its end. A fight is hard
    # from its first bar; a night piece never gets far above a murmur.
    if character.role in ("battle", "boss", "storm"):
        levels = {"open": (0.6, 0.72), "theme": (0.7, 0.8), "rise": (0.75, 1.0), "moment": (1.0, 1.0), "close": (0.9, 0.65)}
    elif character.role in ("night", "ember", "depths"):
        top = 0.5 + 0.4 * heavy
        levels = {"open": (0.2, 0.3), "theme": (0.4, 0.5), "rise": (0.45, 0.45 + 0.3 * heavy), "moment": (top, top), "close": (0.4, 0.15)}
    else:
        top = 0.55 + 0.45 * heavy
        levels = {"open": (0.22, 0.34), "theme": (0.45, 0.58), "rise": (0.5, 0.5 + 0.45 * heavy), "moment": (top, top), "close": (0.5, 0.18)}
    changes = {"open": opening, "theme": run(lengths["theme"], theme), "rise": _spread(rng.choice(RISES[mode]), lengths["rise"]),
               "moment": run(lengths["moment"], theme), "close": closing}
    made.sections = [Section(story, lengths[story], changes[story], levels[story], bool(lift) and story in ("moment", "close"))
                     for story in ("open", "theme", "rise", "moment", "close")]
    return made


# ---------------------------------------------------------------------------------------------
# Writing a tune
# ---------------------------------------------------------------------------------------------
_SPLITS = {
    0.5: ((0.5,),),
    1.0: ((1.0,), (0.5, 0.5), (0.75, 0.25)),
    1.5: ((1.5,), (1.0, 0.5), (0.5, 1.0), (0.5, 0.5, 0.5)),
    2.0: ((2.0,), (1.0, 1.0), (1.5, 0.5), (1.0, 0.5, 0.5), (0.5, 0.5, 1.0), (0.75, 0.25, 1.0), (0.5, 0.5, 0.5, 0.5)),
    3.0: ((3.0,), (2.0, 1.0), (1.0, 2.0), (1.5, 1.5), (1.0, 1.0, 1.0), (1.5, 0.5, 1.0), (1.0, 0.5, 0.5, 1.0), (2.0, 0.5, 0.5)),
}


def _cell(rng: random.Random, group: tuple[float, ...], busy: float) -> list[float]:
    """One bar of rhythm for a tune: note lengths that fill the bar, more of them the busier."""
    out: list[float] = []
    for size in group:
        ways = _SPLITS[size]
        wanted = 1.0 + busy * 2.6 * size / 2.0
        weights = [math.exp(-1.3 * abs(len(way) - wanted)) for way in ways]
        out += rng.choices(ways, weights)[0]
    return out


def _shape(rng: random.Random, moves: int, leap: bool) -> list[int]:
    """How a motif moves from note to note, in scale steps."""
    kind = rng.choice(("rise", "fall", "arch", "dip", "turn", "leap" if leap else "wave", "wave", "thirds"))
    if kind == "rise":
        return [1] * moves
    if kind == "fall":
        return [-1] * moves
    if kind == "arch":
        return [1 if index < (moves + 1) // 2 else -1 for index in range(moves)]
    if kind == "dip":
        return [-1 if index < (moves + 1) // 2 else 1 for index in range(moves)]
    if kind == "turn":
        return [(1, -1, -1, 1)[index % 4] for index in range(moves)]
    if kind == "leap":
        return [rng.choice((2, 3, 4))] + [-1] * (moves - 1)
    if kind == "thirds":
        up = rng.choice((1, -1))
        return [(2 * up, -up)[index % 2] for index in range(moves)]
    return [(1, 1, -1)[index % 3] for index in range(moves)]                  # a wave: two steps on, one back


def _chord_steps(chord: Chord, low: int, high: int) -> list[int]:
    """The scale steps between two of them that are notes of a chord."""
    return [step for step in range(low, high + 1) if step % 7 in {note % 7 for note in chord.steps}]


def theme(rng: random.Random, fam: Family, chords: list[Chord], busy: float) -> Line:
    """An eight-bar tune over eight bars of chords. It is made the way tunes are: a motif of two
    bars; the same motif again at another height, ending away from home; the motif a third
    time, climbing to the tune's highest note; and two bars that bring it home. Each bar begins
    on a note of its chord, and those notes, heard alone, are a line of their own that rises
    over the phrase and falls back."""
    beats, group = fam.beats, fam.group
    low, high = -3, 9                                             # a tenth and a bit, around the key note
    heights = [0.4, 0.5, 0.55, 0.42, 0.6, 0.95, 0.7, 0.3]
    start = rng.choice((0, 2, 4))                                 # the tune's first note: the key note, its third or its fifth
    spine: list[int] = []
    for bar, chord in enumerate(chords):
        choices = _chord_steps(chord, low, high)
        aim = start if bar == 0 else low + heights[bar] * (high - low) + rng.uniform(-1.0, 1.0)
        if bar == 7:
            choices = [step for step in choices if step % 7 == 0] or choices          # home
            aim = min((0, 7), key=lambda step: abs(step - spine[-1]))
        elif bar == 3:
            away = [step for step in choices if step % 7 in (1, 4)]                   # the second or the fifth: a question
            choices = away or choices
        before = spine[-1] if spine else start
        spine.append(min(choices, key=lambda step: abs(step - aim) + (1.5 if abs(step - before) > 4 else 0.0)
                         + (0.8 if step == before and bar not in (0, 7) else 0.0)))
    first, second, third = _cell(rng, group, busy), _cell(rng, group, busy * 0.7), _cell(rng, group, min(busy * 1.2, 1.0))
    if len(second) > 1:
        second = second[:-2] + [second[-2] + second[-1]]           # the answer ends on a longer note
    cells = [first, second, first, second, third, first if rng.random() < 0.5 else third, second, [beats]]
    leap = rng.random() < 0.5
    shapes = {id(first): _shape(rng, len(first) - 1, leap), id(second): _shape(rng, len(second) - 1, False),
              id(third): _shape(rng, len(third) - 1, True)}
    line = Line()
    for bar, (cell, chord) in enumerate(zip(cells, chords)):
        step, at = spine[bar], bar * beats
        moves = shapes.get(id(cell), [])
        chord_notes = {note % 7 for note in chord.steps}
        for index, length in enumerate(cell):
            if index:
                step += moves[index - 1]
                last = index == len(cell) - 1
                if last and bar < 7 and len(cell) >= 3:
                    # The bar's last note leads into the next bar's first by step.
                    step = spine[bar + 1] + (1 if step >= spine[bar + 1] else -1)
                elif length >= 1.0 and step % 7 not in chord_notes:
                    step += 1 if (step + 1) % 7 in chord_notes else -1                 # a long note sits on the chord
                step = min(max(step, low - 1), high + 1)
            weight = 0.62 + 0.3 * heights[bar] + (0.08 if index == 0 else 0.0)
            line.notes.append((at, length if bar < 7 else length * 0.75, step, min(weight, 1.0)))
            at += length
    # A tune that sits on one note is no tune: where a note comes three times running, one of
    # the three (not one that begins a bar, if that can be helped) moves a step aside.
    notes = line.notes
    for index in range(len(notes) - 2):
        if notes[index][2] == notes[index + 1][2] == notes[index + 2][2]:
            on_bar = [abs(notes[which][0] / beats - round(notes[which][0] / beats)) < 1e-6 for which in (index, index + 1, index + 2)]
            which = index + (2 if not on_bar[2] and index + 2 < len(notes) - 1 else 1 if not on_bar[1] else 0 if not on_bar[0] else 1)
            start, length, step, weight = notes[which]
            after = notes[which + 1][2] if which + 1 < len(notes) else step
            notes[which] = (start, length, step + (1 if after > step or (after == step and which % 2) else -1), weight)
    # No leap wider than an octave: a note further off than that comes an octave nearer.
    for index in range(1, len(notes)):
        start, length, step, weight = notes[index]
        while abs(step - notes[index - 1][2]) > 7:
            step += 7 if step < notes[index - 1][2] else -7
        notes[index] = (start, length, step, weight)
    return line


def varied(rng: random.Random, line: Line) -> Line:
    """A tune the second time round: the leaps filled in with passing notes, here and there a
    turn on a long note."""
    out = Line()
    notes = line.notes
    for index, (start, length, step, weight) in enumerate(notes):
        after = notes[index + 1][2] if index + 1 < len(notes) else step
        if length >= 1.0 and abs(after - step) == 2 and rng.random() < 0.7:
            out.notes.append((start, length / 2, step, weight))
            out.notes.append((start + length / 2, length / 2, (step + after) // 2, weight * 0.85))
        elif length >= 2.0 and rng.random() < 0.5:
            out.notes.append((start, length - 1.0, step, weight))
            out.notes.append((start + length - 1.0, 0.5, step + 1, weight * 0.8))
            out.notes.append((start + length - 0.5, 0.5, step, weight * 0.85))
        else:
            out.notes.append((start, length, step, weight))
    return out


def answer(rng: random.Random, fam: Family, chords: list[Chord], tune: Line) -> Line:
    """A slower line under a tune: a note or two to the bar, on the chord, moving the other way
    when the tune moves, an octave or so below it."""
    beats = fam.beats
    line, before = Line(), -3
    tops = [next((step for start, _, step, _ in tune.notes if start >= bar * beats - 1e-6), 0) for bar in range(len(chords))]
    for bar, chord in enumerate(chords):
        choices = _chord_steps(chord, -8, 1)
        rising = bar > 0 and tops[bar] > tops[bar - 1]
        aim = before - 1 if rising else before + 1
        choices = [step for step in choices if step % 7 != tops[bar] % 7] or choices
        step = min(choices, key=lambda each: abs(each - aim))
        if beats >= 4.0 and rng.random() < 0.5:
            other = min(choices, key=lambda each: abs(each - (step + rng.choice((-2, 2)))))
            line.notes.append((bar * beats, beats / 2, step, 0.7))
            line.notes.append((bar * beats + beats / 2, beats / 2, other, 0.65))
            before = other
        else:
            line.notes.append((bar * beats, beats, step, 0.7))
            before = step
    return line


# ---------------------------------------------------------------------------------------------
# The drums: what each groove plays in the theme and at the moment
# ---------------------------------------------------------------------------------------------
# A layer is (sound, where in the bar, how loud) and, optionally, every how many bars. A sound is
# a stroke of the kit, or one of the pitched drums and bells, which play the chord's root.
GROOVES = {
    "none": dict(theme=[], moment=[], roll=None, hit=None),
    "sparkle": dict(theme=[("ting", "down", .35, 4)], moment=[("ting", "groups", .4), ("tamb", "offs", .3)], roll="shake", hit="ting"),
    "stately": dict(theme=[("timpani", "down", .45, 2)],
                    moment=[("timpani", "groups", .8), ("boom", "down", .8), ("snare", "back", .45), ("crash", "down", .7, 4)],
                    roll="timpani", hit="crash"),
    "march": dict(theme=[("snare", "pulses", .4), ("snare", "last", .35), ("boom", "down", .55, 2)],
                  moment=[("snare", "gallop", .6), ("boom", "groups", .8), ("crash", "down", .7, 4), ("timpani", "groups", .7)],
                  roll="snare", hit="crash"),
    "jig": dict(theme=[("tamb", "groups", .5), ("tamb", "offs", .3), ("clack", "back", .4)],
                moment=[("tamb", "pulses", .6), ("boom", "groups", .6), ("clack", "back", .6), ("jingle", "halves", .3)],
                roll="tamb", hit="crash"),
    "claps": dict(theme=[("clack", "back", .5), ("shake", "pulses", .3), ("boom", "down", .45)],
                  moment=[("clack", "back", .7), ("boom", "groups", .65), ("tamb", "halves", .45)], roll="tamb", hit="crash"),
    "waltz": dict(theme=[("ting", "down", .3, 2), ("tamb", "offs", .3)],
                  moment=[("boom", "down", .5), ("tamb", "offs", .5), ("ting", "down", .4)], roll="tamb", hit="ting"),
    "reel": dict(theme=[("snare", "halves", .3), ("boom", "down", .5), ("clack", "back", .45)],
                 moment=[("snare", "halves", .5), ("boom", "groups", .7), ("clack", "back", .6), ("tamb", "pulses", .4)],
                 roll="snare", hit="crash"),
    "sleigh": dict(theme=[("jingle", "pulses", .35), ("ting", "down", .3, 2)],
                   moment=[("jingle", "halves", .4), ("ting", "groups", .4), ("tamb", "back", .35)], roll="jingle", hit="ting"),
    "ride": dict(theme=[("snare", "gallop", .35), ("boom", "groups", .5)],
                 moment=[("snare", "gallop", .6), ("boom", "groups", .8), ("timpani", "groups", .7), ("crash", "down", .7, 4)],
                 roll="snare", hit="crash"),
    "dirge": dict(theme=[("great drum", "down", .5, 2), ("timpani", "mid", .3, 4)],
                  moment=[("great drum", "down", .9), ("timpani", "groups", .75), ("crash", "down", .75, 4), ("snare", "last", .4)],
                  roll="timpani", hit="crash"),
    "tick": dict(theme=[("tick", "pulses", .3), ("ting", "down", .25, 4)],
                 moment=[("tick", "pulses", .45), ("tamb", "offs", .3), ("ting", "down", .4, 2)], roll=None, hit="ting"),
    "bones": dict(theme=[("castanet", "offs", .45), ("block", "pulses", .3), ("timpani", "down", .4, 2)],
                  moment=[("castanet", "halves", .5), ("boom", "groups", .7), ("snare", "back", .55), ("timpani", "groups", .7),
                          ("crash", "down", .7, 4)], roll="snare", hit="crash"),
    "caravan": dict(theme=[("deep", "down", .6), ("high", "offs", .4), ("low", "mid", .5), ("jingle", "pulses", .3)],
                    moment=[("deep", "groups", .75), ("high", "halves", .45), ("low", "back", .6), ("tamb", "pulses", .45),
                            ("bell", "down", .4, 2)], roll="high", hit="crash"),
    "darbuka": dict(theme=[("deep", "three", .65), ("high", "ands", .4), ("clack", "back", .45)],
                    moment=[("deep", "three", .8), ("high", "halves", .5), ("clack", "back", .6), ("tamb", "pulses", .45),
                            ("taiko", "down", .7)], roll="high", hit="crash"),
    "heat": dict(theme=[("shake", "pulses", .25), ("deep", "down", .4, 2)],
                 moment=[("shake", "halves", .3), ("deep", "down", .5), ("high", "back", .35)], roll="shake", hit="ting"),
    "war camp": dict(theme=[("deep", "groups", .55), ("mute", "offs", .4)],
                     moment=[("taiko", "groups", .85), ("deep", "three", .75), ("mute", "halves", .5), ("crash", "down", .7, 4),
                             ("timpani", "down", .7)], roll="taiko", hit="crash"),
    "canopy": dict(theme=[("conga", "offs", .45), ("conga low", "groups", .5), ("shake", "halves", .3), ("block", "back", .35)],
                   moment=[("conga", "halves", .5), ("conga low", "groups", .65), ("shake", "halves", .4), ("block", "three", .5),
                           ("deep", "down", .6)], roll="conga", hit="crash"),
    "rain": dict(theme=[("shake", "halves", .22), ("block low", "mid", .3, 2)],
                 moment=[("shake", "halves", .3), ("conga low", "groups", .4), ("block", "back", .35)], roll="shake", hit="ting"),
    "hunt": dict(theme=[("deep", "groups", .55), ("block low", "offs", .4), ("guiro", "mid", .35, 2)],
                 moment=[("taiko", "groups", .8), ("deep", "pulses", .6), ("block", "halves", .45), ("crash", "down", .6, 4)],
                 roll="taiko", hit="crash"),
    "bog": dict(theme=[("guiro", "back", .4), ("block low", "groups", .4), ("shake", "pulses", .25)],
                moment=[("deep", "groups", .6), ("guiro", "back", .5), ("block", "offs", .45), ("shake", "halves", .3)],
                roll="shake", hit="crash"),
    "anvil": dict(theme=[("ting", "back", .7), ("boom", "down", .6), ("taiko", "mid", .5, 2)],
                  moment=[("ting", "back", .9), ("taiko", "pulses", .75), ("boom", "groups", .85), ("snare", "gallop", .5),
                          ("crash", "down", .75, 4), ("timpani", "groups", .7)], roll="taiko", hit="crash"),
    "courtly": dict(theme=[("tamb", "back", .3), ("ting", "down", .25, 4)],
                    moment=[("tamb", "pulses", .4), ("ting", "down", .4, 2), ("boom", "down", .4)], roll="tamb", hit="ting"),
    "thunder": dict(theme=[("great drum", "down", .6, 2), ("timpani", "gallop", .45), ("crash2", "down", .4, 4)],
                    moment=[("great drum", "groups", .9), ("timpani", "gallop", .7), ("snare", "halves", .5), ("crash", "down", .8, 2)],
                    roll="timpani", hit="crash"),
    "battle": dict(theme=[("snare", "gallop", .5), ("boom", "groups", .7), ("timpani", "down", .6)],
                   moment=[("snare", "halves", .6), ("boom", "pulses", .8), ("timpani", "gallop", .75), ("crash", "down", .8, 2)],
                   roll="snare", hit="crash"),
    "war drums": dict(theme=[("taiko", "gallop", .6), ("deep", "groups", .7), ("mute", "offs", .45)],
                      moment=[("taiko", "halves", .75), ("deep", "pulses", .8), ("timpani", "groups", .75), ("crash", "down", .8, 2),
                              ("clack", "back", .5)], roll="taiko", hit="crash"),
    "colossus": dict(theme=[("great drum", "groups", .8), ("taiko", "three", .6), ("church bell", "down", .5, 2)],
                     moment=[("great drum", "groups", .95), ("taiko", "halves", .7), ("timpani", "gallop", .75),
                             ("crash", "down", .85, 2), ("snare", "back", .6), ("church bell", "down", .6)],
                     roll="timpani", hit="crash"),
    # The band's kit.
    "rock": dict(theme=[("boom", "kick", .85), ("snare", "back", .8), ("hat", "halves", .45)],
                 moment=[("boom", "kick busy", .95), ("snare", "back", .95), ("hat open", "pulses", .5), ("crash", "down", .8, 4)],
                 roll="snare", hit="crash"),
    "half rock": dict(theme=[("boom", "down", .9), ("snare", "mid", .85), ("hat", "pulses", .45)],
                      moment=[("boom", "kick busy", .95), ("snare", "mid", .95), ("ride", "pulses", .5), ("crash", "down", .85, 2),
                              ("tom low", "last", .7)], roll="tom", hit="crash"),
    "rock ride": dict(theme=[("boom", "pulses", .8), ("snare", "back", .8), ("hat", "halves", .45)],
                      moment=[("boom", "pulses", .9), ("snare", "back", .95), ("ride", "halves", .5), ("crash", "down", .85, 2)],
                      roll="snare", hit="crash"),
    "tavern rock": dict(theme=[("boom", "kick", .65), ("clack", "back", .6), ("tamb", "halves", .35)],
                        moment=[("boom", "kick busy", .75), ("snare", "back", .7), ("tamb", "halves", .45), ("hat open", "pulses", .35)],
                        roll="tamb", hit="crash"),
    "tom rock": dict(theme=[("boom", "kick", .8), ("tom low", "halves", .5), ("snare", "back", .7)],
                     moment=[("boom", "kick busy", .9), ("tom", "halves", .6), ("tom low", "pulses", .6), ("snare", "back", .9),
                             ("crash", "down", .8, 4)], roll="tom low", hit="crash"),
    "anvil rock": dict(theme=[("boom", "kick", .85), ("snare", "back", .7), ("ting", "back", .8), ("hat", "pulses", .4)],
                       moment=[("boom", "kick busy", .95), ("snare", "back", .9), ("ting", "back", .95), ("hat open", "pulses", .45),
                               ("crash", "down", .8, 4)], roll="snare", hit="crash"),
    "desert rock": dict(theme=[("boom", "kick", .8), ("snare", "back", .75), ("high", "ands", .45), ("jingle", "pulses", .3)],
                        moment=[("boom", "kick busy", .9), ("snare", "back", .9), ("high", "halves", .45), ("hat open", "pulses", .45),
                                ("crash", "down", .8, 4)], roll="high", hit="crash"),
    "brushes": dict(theme=[("clack", "back", .35), ("hat", "pulses", .25)], moment=[("clack", "back", .5), ("hat", "halves", .3),
                    ("boom", "down", .5)], roll=None, hit="ting"),
    "shuffle": dict(theme=[("boom", "kick", .7), ("clack", "back", .6), ("hat", "pulses", .4)],
                    moment=[("boom", "kick busy", .8), ("snare", "back", .8), ("hat open", "groups", .45), ("hat", "pulses", .4),
                            ("crash", "down", .7, 4)], roll="snare", hit="crash"),
    "drip": dict(theme=[("block", "down", .3, 3), ("great drum", "down", .4, 4)],
                 moment=[("block", "mid", .3, 2), ("great drum", "down", .55, 2), ("tick", "back", .2)], roll=None, hit=None),
}
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")


# ---------------------------------------------------------------------------------------------
# A take: the whole story, written out for the band
# ---------------------------------------------------------------------------------------------
class Take:
    """One take of a family: every part of the story written for every channel."""

    def __init__(self, fam: Family, take: int):
        self.fam, self.take, self.ch = fam, take, fam.character
        self.rng = random.Random(fam.seed * 9973 + take * 7919 + 5)
        self.beats, self.group = fam.beats, fam.group
        # What the feet tap: a quarter note, or in six-eight and seven-eight an eighth.
        self.pulse = 0.5 if any(size % 1 for size in self.group) else 1.0
        self.voices: dict[str, dict[str, Voice]] = {channel: {} for channel in CHANNELS}
        self.spans: list[tuple[Section, float, Key, list[Chord]]] = []
        at = 0.0
        for section in fam.sections:
            key = fam.key.lifted(fam.lift) if section.lifted else fam.key
            self.spans.append((section, at, key, [key.chord(figure) for figure in section.chords]))
            at += section.bars * self.beats
        self.total = at
        self.heavy = self.ch.weight >= 0.8
        for write in (self.lead, self.texture, self.rhythm, self.bass, self.drums):
            write()

    # --- the players -----------------------------------------------------------------------
    def voice(self, channel: str, name: str, tag: str = "") -> Voice:
        have = self.voices[channel]
        if name + tag not in have:
            inst = INSTRUMENTS[name]
            volume = min(10 ** ((LEVEL - LOUD[name]) / 40.0) * inst.level, 1.0)
            have[name + tag] = Voice(inst.program, bank=inst.bank, volume=volume, shift=inst.early,
                                     pan=self.rng.uniform(-0.35, 0.35), wired=inst.wired)
        return have[name + tag]

    def kit(self) -> Voice:
        have = self.voices["drums"]
        if "kit" not in have:
            have["kit"] = Voice(KITS[self.ch.kit][0], drums=True)
        return have["kit"]

    def put(self, channel: str, name: str, start: float, length: float, pitch: int, loud: float, tag: str = "") -> None:
        inst = INSTRUMENTS[name]
        while pitch < inst.low:
            pitch += 12
        while pitch > inst.high:
            pitch -= 12
        if inst.held:
            # A bow or a breath needs a moment to speak: no note of theirs is shorter than this.
            length = max(length * 0.97, 0.11 * self.fam.bpm / 60.0)
        self.voice(channel, name, tag).add(start, length, pitch, loud)

    def level(self, section: Section, bar: float) -> float:
        low, high = section.level
        return low + (high - low) * min(max(bar / max(section.bars, 1), 0.0), 1.0)

    @staticmethod
    def hard(level: float, weight: float = 1.0) -> float:
        """How hard a note is struck for how hard the music is being played."""
        return min(max(0.26 + 0.66 * level * weight, 0.05), 1.0)

    def fit(self, line: Line, chord: Chord, aim: float = 0.0) -> Line:
        """A fragment of a tune moved bodily so that it begins on a note of a chord, as near
        to `aim` scale steps away as it can."""
        first = line.notes[0][2]
        notes = {step % 7 for step in chord.steps}
        moves = [move for move in range(-9, 10) if (first + move) % 7 in notes]
        return line.moved(steps=min(moves, key=lambda move: abs(move - aim)))

    def sing(self, channel: str, name: str, line: Line, at: float, key: Key, chords: list[Chord], first: float,
             loud: float = 1.0, octave: int = 0, tag: str = "") -> None:
        """Gives a line to an instrument, in its register. `chords` are the bars of the part of
        the story the line is in, which begins at `first`."""
        inst = INSTRUMENTS[name]
        def chord_at(beat: float) -> Chord:
            return chords[min(max(int((beat - first) / self.beats + 1e-6), 0), len(chords) - 1)]
        near = inst.home + 12 * octave
        pitches = [key.pitch(step, near, chord_at(at + start)) for start, _, step, _ in line.notes]
        shift = 0
        while max(pitches) + shift > inst.high:
            shift -= 12
        while min(pitches) + shift < inst.low:
            shift += 12
        for (start, length, _, weight), pitch in zip(line.notes, pitches):
            self.voice(channel, name, tag).add(at + start, length * (0.96 if inst.held else 1.0), pitch + shift,
                                               min(weight * loud, 1.0))

    def spots(self, where: str) -> list[tuple[float, float]]:
        """The moments in a bar a drum pattern names, each with how strongly it is struck."""
        beats, pulse = self.beats, self.pulse
        starts, at = [], 0.0
        for size in self.group:
            starts.append(at)
            at += size
        simple = pulse == 1.0
        count = int(round(beats / pulse))
        pulses = [index * pulse for index in range(count)]
        if where == "down":
            return [(0.0, 1.0)]
        if where == "groups":
            return [(start, 1.0 if start == 0 else 0.85) for start in starts]
        if where == "pulses":
            return [(each, 1.0 if each in starts else 0.7) for each in pulses]
        if where == "back":
            if simple:
                return [(each, 1.0) for each in pulses if int(each) % 2 == 1] if count != 3 else [(1.0, 0.9), (2.0, 1.0)]
            return [(start, 1.0) for start in starts[1:]]
        if where == "offs":
            return [(each, 0.8) for each in pulses if each not in starts]
        if where == "halves":
            return [(index * pulse / 2, 1.0 if index % 2 == 0 and index * pulse / 2 in starts else 0.75 if index % 2 == 0 else 0.55)
                    for index in range(count * 2)]
        if where == "ands":
            return [(each + pulse / 2, 0.8) for each in pulses]
        if where == "gallop":
            if simple:
                return [(each + off, loud) for each in pulses for off, loud in ((0.0, 1.0), (0.5, 0.6), (0.75, 0.7))]
            return [(start + off, loud) for start in starts for off, loud in ((0.0, 1.0), (1.0, 0.7))]
        if where == "last":
            return [(beats - pulse, 0.8)]
        if where == "kick":                      # a rock kick: the one and the three
            return [(0.0, 1.0), (2.0, 0.9)] if simple and count == 4 else [(start, 1.0 if start == 0 else 0.9) for start in starts]
        if where == "kick busy":                 # ...and a push before the three
            if simple and count == 4:
                return [(0.0, 1.0), (1.5, 0.7), (2.0, 0.95), (3.5, 0.6)]
            return [(start, 1.0 if start == 0 else 0.9) for start in starts] + [(beats - pulse, 0.6)]
        if where == "three":
            return [(0.0, 1.0), (1.5, 0.85), (3.0, 0.9)] if simple and count == 4 else [(start, 1.0 if start == 0 else 0.85) for start in starts]
        if where == "mid":
            return [(starts[1] if len(starts) > 1 else pulse * (count // 2), 0.9)]
        raise ValueError("No such place in the bar: %r" % where)

    # --- the tune ----------------------------------------------------------------------------
    def lead(self) -> None:
        ch, rng, beats = self.ch, self.rng, self.beats
        chords8 = next(chords for section, _, _, chords in self.spans if section.story == "theme")[:8]
        tune = theme(rng, self.fam, chords8, ch.busy)
        again = varied(rng, tune)
        other = theme(rng, self.fam, chords8, max(ch.busy - 0.15, 0.2))
        under = answer(rng, self.fam, chords8, tune)
        turn = self.take % len(ch.leads)
        order = ch.leads[turn:] + ch.leads[:turn]
        solo, second, third = order[0], order[1 % len(order)], order[2 % len(order)]
        strong = ch.strong[self.take % len(ch.strong):] + ch.strong[:self.take % len(ch.strong)]
        self.tune = tune
        for section, first, key, chords in self.spans:
            bars, story = section.bars, section.story
            if story == "open":
                motif = self.fit(tune.cut(0, min(2, bars) * beats), chords[min(1, bars - 1)])
                self.sing("lead", solo, motif, first + min(1, bars - 1) * beats, key, chords, first, loud=self.hard(section.level[0], 0.9))
                if bars >= 6:
                    echo = self.fit(tune.cut(0, 2 * beats), chords[bars // 2 + 1], aim=rng.choice((-3, 2, 4)))
                    self.sing("lead", second, echo, first + (bars // 2 + 1) * beats, key, chords, first,
                              loud=self.hard(section.level[1], 0.85))
            elif story == "theme":
                for turn in range(bars // 8):
                    at, loud = first + turn * 8 * beats, self.hard(self.level(section, turn * 8 + 4))
                    if turn == 0:
                        self.sing("lead", solo, tune, at, key, chords, first, loud=loud)
                    elif turn == 1:
                        self.sing("lead", second, again, at, key, chords, first, loud=loud)
                    elif turn % 4 == 2:
                        self.sing("lead", third, other, at, key, chords, first, loud=loud)
                    else:
                        self.sing("lead", solo, tune, at, key, chords, first, loud=loud)
                        self.sing("lead", second, again, at, key, chords, first, loud=loud * 0.9, octave=1 if second != solo else -1)
            elif story == "rise":
                motif, bar, players = tune.cut(0, beats), 0, [solo]
                while bar < bars - 1:
                    along = bar / bars
                    piece = self.fit(motif, chords[bar], aim=round(along * 6) - 2)
                    for name in players:
                        self.sing("lead", name, piece, first + bar * beats, key, chords, first, loud=self.hard(self.level(section, bar), 0.95))
                    if along >= 0.4 and second not in players:
                        players.append(second)
                    if along >= 0.7 and strong[0] not in players:
                        players.append(strong[0])
                    bar += 2 if along < 0.5 else 1
                # The last bar runs up the scale to where the moment begins.
                step = self.pulse / 2 if self.fam.bpm < 110 else self.pulse
                count = max(int(round(beats / step)), 2)
                top = tune.notes[0][2] + 7
                run = Line([(index * step, step, top - (count - index), 0.7 + 0.3 * index / count) for index in range(count)])
                for name in players:
                    self.sing("lead", name, run, first + (bars - 1) * beats, key, chords, first, loud=self.hard(section.level[1]))
            elif story == "moment":
                for turn in range(bars // 8):
                    at, use = first + turn * 8 * beats, tune if turn % 2 == 0 else again
                    loud = self.hard(section.level[0])
                    self.sing("lead", strong[0], use, at, key, chords, first, loud=loud)
                    if len(strong) > 1:
                        self.sing("lead", strong[1], use, at, key, chords, first, loud=loud * 0.95,
                                  octave=1 if INSTRUMENTS[strong[1]].home - INSTRUMENTS[strong[0]].home < 7 else 0)
                    for name in ch.under:
                        self.sing("lead", name, under, at, key, chords, first, loud=loud * 0.8, tag=" under")
                    if ch.band and INSTRUMENTS[strong[0]].wired:
                        # Twin guitars: the tune again a third above it.
                        self.sing("lead", strong[0], use.moved(steps=2), at, key, chords, first, loud=loud * 0.8, tag=" twin")
                    if turn % 2 == 1 and not ch.band:
                        top = "piccolo" if self.heavy else "glock"
                        self.sing("lead", top, use, at, key, chords, first, loud=loud * 0.6, octave=1 if self.heavy else 0)
            else:
                if bars >= 6:
                    self.sing("lead", second, self.fit(tune.cut(0, 2 * beats), chords[0]), first, key, chords, first,
                              loud=self.hard(section.level[0], 0.8))
                home = max(bars - 4, 0)
                tail = self.fit(tune.cut(6 * beats, 8 * beats), chords[home], aim=0)
                self.sing("lead", solo, tail, first + home * beats, key, chords, first, loud=self.hard(self.level(section, home), 0.85))
                if bars >= 3:
                    last = Line([(0.0, min(2, bars - home - 1) * beats + beats * 0.5, 0, 0.6)])
                    self.sing("lead", solo, last, first + (bars - 2) * beats, key, chords, first, loud=self.hard(section.level[1], 0.9))

    # --- the pad -----------------------------------------------------------------------------
    def texture(self) -> None:
        ch, rng, beats = self.ch, self.rng, self.beats
        way = ch.pad_ways[(self.take + rng.randrange(2)) % len(ch.pad_ways)]
        pad = ch.pads[self.take % len(ch.pads)]
        lift = 5 if ch.light else 0
        before: list[int] | None = None
        for section, first, key, chords in self.spans:
            story, bars = section.story, section.bars
            name = "tremolo" if way == "tremolo" and story in ("open", "rise") else pad
            count = {"open": 2, "theme": 3, "rise": 4, "moment": 4, "close": 3}[story]
            centre = {"open": 53, "theme": 58, "rise": 60, "moment": 62, "close": 56}[story] + lift
            arp = way == "arp" and story in ("open", "theme", "close")
            drone = way == "drone" and story != "moment"
            held: dict[int, tuple[float, int]] = {}                # which player: (since when, what pitch)
            swell = self.voice("texture", name)
            for bar, chord in enumerate(chords):
                at, level = first + bar * beats, self.level(section, bar)
                if drone:
                    root = key.pitch(0, centre - 7)
                    notes = [root, root + 7] + ([root + 12] if count > 2 else [])
                else:
                    notes = voiced(key, chord, before if before and len(before) == count else None, count, centre)
                    before = notes
                swell.swells.append((at, 0.3 + 0.62 * level))
                swell.swells.append((at + beats * 0.5, 0.3 + 0.62 * min(level + 0.05, 1.0)))
                if arp:
                    # Broken chords on the harp: up through the chord and down again.
                    ladder = notes + [notes[0] + 12] + notes[::-1][:-1]
                    step = self.pulse / 2 if self.pulse == 1.0 else self.pulse
                    for index in range(int(round(beats / step))):
                        self.put("texture", "harp", at + index * step, step * 2, ladder[index % len(ladder)],
                                 self.hard(level, 0.75 if index else 0.9))
                    continue
                for player, pitch in enumerate(notes):
                    if player in held and held[player][1] == pitch:
                        continue                                    # the same note again: it is held over the bar line
                    if player in held:
                        since, was = held[player]
                        self.put("texture", name, since, at - since, was, self.hard(0.55, 1.0))
                    held[player] = (at, pitch)
            end = first + bars * beats
            for since, was in held.values():
                self.put("texture", name, since, end - since, was, self.hard(0.55, 1.0))
            swell.swells.append((end - 0.01, 0.3 + 0.62 * section.level[1]))
            if story == "moment" and self.heavy and not ch.band:
                # Everyone: the violins an octave above the pad, and voices where the palette has them.
                for bar, chord in enumerate(chords):
                    at = first + bar * beats
                    top = voiced(key, chord, None, 2, centre + 14)
                    for pitch in top:
                        self.put("texture", "violins", at, beats, pitch, self.hard(0.8))
                    if "choir" in ch.pads + ch.strong:
                        for pitch in voiced(key, chord, None, 3, 62):
                            self.put("texture", "choir", at, beats, pitch, self.hard(0.75), tag=" tutti")

    # --- the accompaniment -------------------------------------------------------------------
    def rhythm(self) -> None:
        ch, rng, beats, pulse = self.ch, self.rng, self.beats, self.pulse
        name = ch.plucks[self.take % len(ch.plucks)]
        figure = ch.figures[(self.take + rng.randrange(2)) % len(ch.figures)]
        inst = INSTRUMENTS[name]
        starts, at = [], 0.0
        for size in self.group:
            starts.append(at)
            at += size
        half = pulse / 2 if pulse == 1.0 else pulse
        slots = int(round(beats / half))
        # A riff of its own for this take: where in the bar the chords fall and how long each rings.
        if beats == 4.0:
            self.riff = list(rng.choice((
                ((0.0, 1.5), (1.5, 1.0), (2.5, 1.5)), ((0.0, 0.75), (2.0, 0.75), (3.0, 0.5), (3.5, 0.5)),
                ((0.0, 2.0), (2.5, 0.5), (3.0, 1.0)), ((0.0, 0.5), (0.5, 0.5), (1.5, 1.0), (2.5, 1.5)),
                ((0.0, 1.0), (1.0, 0.5), (2.0, 1.0), (3.5, 0.5)), ((0.0, 3.0), (3.0, 0.5), (3.5, 0.5)))))
        elif beats == 3.0 and pulse == 0.5:
            self.riff = list(rng.choice((((0.0, 1.0), (1.5, 1.0)), ((0.0, 1.5), (1.5, 0.5), (2.0, 1.0)), ((0.0, 0.5), (1.0, 0.5), (1.5, 1.5)))))
        else:
            self.riff = [(start, size * 0.8) for start, size in zip(starts, self.group)]
        # A pattern of its own for this take: which note of the chord falls on which half beat.
        walk, pattern = rng.randrange(3), []
        for slot in range(slots):
            walk = (walk + rng.choice((-1, 1, 1, 2))) % 4
            pattern.append(walk if slot == 0 or rng.random() < 0.68 else None)
        before: list[int] | None = None
        for section, first, key, chords in self.spans:
            story, bars = section.story, section.bars
            for bar, chord in enumerate(chords):
                level = self.level(section, bar)
                along = bar / bars
                density = {"open": 0.15, "theme": 0.5, "rise": 0.5 + 0.5 * along, "moment": 1.0, "close": 0.4 * (1.0 - along)}[story]
                if story == "open" and not ch.band and (figure not in ("toll", "rock", "arp") or bar % 2 == 1 or bar == 0):
                    continue
                if ch.band and story == "open":
                    density = 0.3                              # a band opens on its riff alone
                if density < 0.12:
                    continue
                notes = voiced(key, chord, before, 3, inst.home - 4)
                before = notes
                ladder = notes + [notes[0] + 12]
                bar_at = first + bar * beats
                loud = self.hard(level, 0.8)
                thin = density < 0.45
                if figure == "pulse":
                    step = half if density >= 0.5 else pulse
                    if density > 0.85 and pulse == 1.0 and self.fam.bpm <= 112:
                        step = 0.25
                    for index in range(int(round(beats / step))):
                        on = index * step
                        strong = on in starts
                        for pitch in ((notes[0], notes[2]) if strong or index % 2 == 0 else (notes[1],)):
                            self.put("rhythm", name, bar_at + on, step * 0.45, pitch, loud * (1.0 if strong else 0.72))
                elif figure == "arp":
                    for index in range(slots):
                        if thin and index % 2:
                            continue
                        order = (0, 1, 2, 3, 2, 1)
                        self.put("rhythm", name, bar_at + index * half, half * 1.6, ladder[order[index % 6]],
                                 loud * (1.0 if index * half in starts else 0.75))
                elif figure == "strum":
                    for index in range(slots):
                        on = index * half
                        down = on in starts
                        if not down and (thin or index % 2 == 0 and pulse == 1.0 and density < 0.8):
                            continue
                        chord_notes = ladder if down else ladder[1:][::-1]
                        for string, pitch in enumerate(chord_notes):
                            self.put("rhythm", name, bar_at + on + string * 0.012, half * 0.9, pitch, loud * (0.95 if down else 0.6))
                elif figure == "oompah":
                    for index in range(int(round(beats / pulse))):
                        on = index * pulse
                        if on in starts:
                            continue
                        for pitch in ladder[1:]:
                            self.put("rhythm", name, bar_at + on, pulse * 0.5, pitch, loud * 0.8)
                elif figure == "rock":
                    order = (0, 2, 1, 2)
                    for index in range(int(round(beats / pulse))):
                        if thin and index % 2:
                            continue
                        self.put("rhythm", name, bar_at + index * pulse, pulse * 1.5, ladder[order[index % 4]], loud * 0.8)
                elif figure == "toll":
                    if bar % 2 == 0 or density > 0.8:
                        self.put("rhythm", name, bar_at, beats, notes[0] + 12, loud)
                        self.put("rhythm", name, bar_at + (starts[1] if len(starts) > 1 else beats / 2), beats / 2, notes[2], loud * 0.6)
                elif figure == "gallop":
                    for on, weight in self.spots("gallop" if not thin else "groups"):
                        self.put("rhythm", name, bar_at + on, 0.22, notes[0] if weight >= 1.0 else notes[1], loud * weight)
                        if weight >= 1.0:
                            self.put("rhythm", name, bar_at + on, 0.22, notes[2], loud * 0.85)
                elif figure == "hammer":
                    for on, weight in self.spots("three"):
                        for pitch in notes:
                            self.put("rhythm", name, bar_at + on, half * 0.6, pitch, loud * weight)
                    if not thin:
                        for on, weight in self.spots("halves"):
                            self.put("rhythm", name, bar_at + on, half * 0.4, notes[0] - 12, loud * 0.5 * weight)
                elif figure in ("riff", "chug"):
                    # A riff: power chords with room between them, and the muted string chugging
                    # where the chords are not. Root, fifth and octave: the third is left to the tune.
                    root = key.pitch(chord.root, 45)
                    root += 12 if root < 40 else -12 if root > 52 else 0
                    power = (root, root + 7, root + 12)
                    hits = self.riff
                    if density > 0.85 or figure == "chug":
                        hits = hits + [(on, None) for on in [index * half for index in range(slots)]
                                       if not any(abs(on - at) < 1e-6 for at, _ in hits)]
                    for on, length in sorted(hits, key=lambda hit: hit[0]):
                        if length is None:
                            if thin:
                                continue
                            self.put("rhythm", "muted guitar", bar_at + on, 0.2, root, loud * (0.75 if on in starts else 0.6))
                            self.put("rhythm", "muted guitar", bar_at + on, 0.2, root + 7, loud * 0.5)
                        else:
                            for pitch in power:
                                self.put("rhythm", "rhythm guitar", bar_at + on, length * 0.92, pitch, loud * (1.0 if on in starts else 0.9))
                elif figure == "pattern":
                    for slot, which in enumerate(pattern):
                        if which is None or (thin and slot % 2):
                            continue
                        self.put("rhythm", name, bar_at + slot * half, half * 1.2, ladder[which], loud * (1.0 if slot * half in starts else 0.75))
                else:
                    raise ValueError("No such figure: %r" % figure)
                if story == "moment" and self.heavy and not ch.band:
                    # At the moment the brass marks the chord on the strong beats.
                    for on in starts:
                        for pitch in voiced(key, chord, None, 3, 58):
                            self.put("rhythm", "brass", bar_at + on, pulse * 0.8, pitch, self.hard(level, 0.85), tag=" stabs")

    # --- the bass ----------------------------------------------------------------------------
    def bass(self) -> None:
        ch, rng, beats, pulse = self.ch, self.rng, self.beats, self.pulse
        name = ch.basses[self.take % len(ch.basses)]
        inst = INSTRUMENTS[name]
        way = rng.choice(("two", "walk", "oct") if ch.busy >= 0.5 else ("long", "two", "walk"))
        if ch.band and self.heavy:
            way = "eight"
        starts, at = [], 0.0
        for size in self.group:
            starts.append(at)
            at += size
        for section, first, key, chords in self.spans:
            story, bars = section.story, section.bars
            for bar, chord in enumerate(chords):
                level, bar_at = self.level(section, bar), first + bar * beats
                root = key.pitch(chord.root, inst.home - 5)
                loud = self.hard(level, 0.9)
                after = chords[bar + 1] if bar + 1 < bars else chord
                if story == "open":
                    if self.heavy or bar >= bars // 2:
                        self.put("bass", name, bar_at, beats, key.pitch(0, inst.home - 5), loud * 0.8)      # the key note, held
                    continue
                if story == "close" or way == "long":
                    self.put("bass", name, bar_at, beats, root, loud)
                elif way == "two":
                    for index, on in enumerate(starts):
                        length = (starts[index + 1] if index + 1 < len(starts) else beats) - on
                        self.put("bass", name, bar_at + on, length, root + (7 if index % 2 and bar % 2 else 0), loud * (1.0 if index == 0 else 0.85))
                elif way == "walk":
                    for index, on in enumerate(starts):
                        length = (starts[index + 1] if index + 1 < len(starts) else beats) - on
                        self.put("bass", name, bar_at + on, length - (pulse if index == len(starts) - 1 else 0.0), root, loud)
                    # The last note of the bar leads to the next bar's root by a step of the scale.
                    toward = key.pitch(after.root, inst.home - 5)
                    lead_in = after.root + 4 if toward == root else after.root + (1 if toward < root else -1)
                    near = key.pitch(lead_in, inst.home - 5)
                    near += 12 if near < toward - 6 else -12 if near > toward + 6 else 0
                    self.put("bass", name, bar_at + beats - pulse, pulse, near, loud * 0.8)
                elif way == "eight":
                    step = 0.5
                    for index in range(int(round(beats / step))):
                        on = index * step
                        self.put("bass", name, bar_at + on, step * 0.85, root, loud * (1.0 if on in starts else 0.8))
                else:
                    step = pulse if pulse == 1.0 else pulse * 1.0
                    for index in range(int(round(beats / step))):
                        self.put("bass", name, bar_at + index * step, step * 0.8, root + (12 if index % 2 else 0), loud * (1.0 if index % 2 == 0 else 0.75))
                if story == "moment" and self.heavy and not ch.band:
                    low = "tuba" if "tuba" in ch.basses + ch.under else "basses"
                    self.put("bass", low, bar_at, beats, root, self.hard(level, 0.8), tag=" tutti")

    # --- the drums ---------------------------------------------------------------------------
    def strike(self, sound: str, at: float, loud: float, chord: Chord, key: Key) -> None:
        if sound in INSTRUMENTS:
            inst = INSTRUMENTS[sound]
            self.put("drums", sound, at, 0.5, key.pitch(chord.root, inst.home), loud)
        else:
            self.kit().add(at, 0.25, KITS[self.ch.kit][1][sound], loud)

    def drums(self) -> None:
        ch, rng, beats = self.ch, self.rng, self.beats
        groove = GROOVES[ch.grooves[(self.take + rng.randrange(2)) % len(ch.grooves)]]
        fight = ch.role in ("battle", "boss", "storm")

        def lay(layers: list, bar: int, bar_at: float, level: float, scale: float, chord: Chord, key: Key) -> None:
            for layer in layers:
                sound, where, loud = layer[0], layer[1], layer[2]
                if len(layer) > 3 and bar % layer[3]:
                    continue
                for on, weight in self.spots(where):
                    self.strike(sound, bar_at + on, min(loud * weight * scale * (0.55 + 0.6 * level), 1.0), chord, key)

        for section, first, key, chords in self.spans:
            story, bars = section.story, section.bars
            for bar, chord in enumerate(chords):
                level, bar_at, along = self.level(section, bar), first + bar * beats, bar / bars
                if story == "open":
                    if ch.band and not fight and bar == bars - 1 and ch.kit in ("rock", "room"):
                        for on, weight in self.spots("pulses"):          # the sticks count the band in
                            self.strike("hat", bar_at + on, 0.5 * weight, chord, key)
                    if fight:
                        if bar == 0:
                            for sound in ("crash", "great drum" if "great drum" in ch.drums else "boom"):
                                self.strike(sound, bar_at, 0.85, chord, key)
                        elif bar >= 1:
                            lay(groove["theme"], bar, bar_at, level, 0.8, chord, key)
                elif story == "theme":
                    lay(groove["theme"], bar, bar_at, level, 1.0, chord, key)
                elif story == "rise":
                    lay(groove["theme"] if along < 0.5 else groove["moment"], bar, bar_at, level, 1.0 if along < 0.5 else 0.7, chord, key)
                    roll = groove["roll"]
                    length = 2 if self.heavy else 1
                    if roll and bar >= bars - length:
                        step = 0.25
                        count = int(round(beats / step))
                        for index in range(count):
                            done = ((bar - (bars - length)) * count + index) / (length * count)
                            self.strike(roll, bar_at + index * step, (0.2 + 0.7 * done) * (0.6 + 0.4 * ch.weight), chord, key)
                elif story == "moment":
                    lay(groove["moment"], bar, bar_at, level, 1.0, chord, key)
                    if bar == 0 and groove["hit"]:
                        self.strike(groove["hit"], bar_at, 0.6 + 0.35 * ch.weight, chord, key)
                        if self.heavy:
                            for sound in ch.drums[:2]:
                                self.strike(sound, bar_at, 0.9, chord, key)
                    if bar % 8 == 7 and groove["roll"] and bars - bar > 1:
                        for index in range(4):                       # a fill into the next time round
                            self.strike(groove["roll"], bar_at + beats - (4 - index) * 0.25, 0.45 + 0.12 * index, chord, key)
                else:
                    if along < 0.5 and bar % 2 == 0:
                        lay(groove["theme"], bar, bar_at, level, 0.7, chord, key)
                    if bar == bars - 2 and groove["hit"] and self.heavy:
                        self.strike("timpani" if "timpani" in ch.drums else "ting", bar_at, 0.45, chord, key)
