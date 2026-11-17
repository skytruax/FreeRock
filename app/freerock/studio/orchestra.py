"""The orchestra's writer: original music for the Warcraft style, written as notes.

A track is a story of about eight minutes, told in two waves and nine parts. It opens (a drone,
a fragment of the first theme on one instrument); states its first theme; states a second
theme, which begins away from home, has another singer and another figure under it; builds
(the accompaniment quickens, fragments of the first theme climb, the drums roll in); and
arrives: the first theme with most of the band. Then the valley, one of the themes on a single
instrument over very little. From there the climb, longer than the build, made of both
themes; the summit, the first theme with everyone playing and the second sung underneath it,
sometimes lifted into a higher key; and the close. How big the summit is depends on what the
track is for: a village dance comes to a merry tutti of fiddles and tambourine, a march through
the mountains to horns and timpani. A fight does not wait to begin and its valley is only a
breath; a night piece keeps the whole arc under its breath.

The drums. A fight has war drums nearly all the way (an ensemble of big drums, with an
ostinato of the take's own), and heavy music for walking has them from each rise to the moment
it comes to; frame drums have the quieter drive, and in lighter music of the desert, the
jungle and the highlands they are all there is. An arrival is marked: for the last beat or two
before it the tune rests and the accompaniment stops striking, while the drums roll and a
cymbal swells; then a deep stroke lands on its first beat, and at the summit of the heaviest
pieces a gong. Music for the night, the inn and the depths has none of this.

The player knows five words for where a piece stands in a story (open, theme, rise, moment,
close). A long story uses three of them more than once: both themes and the valley are
"theme", the build and the climb "rise", the arrival and the summit "moment".

What is written first is a FAMILY: the kind of place and moment it is for (its character), its
key, tempo and metre, and its changes, the chord under every bar of the story. Then TAKES: each
take is the whole story over those changes, written afresh from its own seed, with its own two
themes, its own accompaniment figures, bass line and drums, and its own choice of instruments
from the character's palette. Since every take of a family follows the same chords bar for
bar, the player can put the drums of one with the tune of another.

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
    # Colours added for variety (2026-11-16, played: "need more variety in warcraft"). Muse Sounds plays all of these.
    "piano": I(0, 0, 33, 100, 64, held=False), "bass flute": I(0, 73, 48, 84, 62), "bass clarinet": I(0, 71, 38, 77, 55),
    "handbells": I(0, 14, 60, 93, 74, held=False, level=0.85),
    # (Muse's euphonium under C3 was found to sound an octave up and 18 dB soft, played alone: it is kept above it.)
    "euphonium": I(0, 58, 48, 72, 58),
    # The big drums and what marks an arrival. These are found by name alone (their bank and
    # program stand for nothing). A war drum's or a frame drum's pitch is its size: 36 is the
    # biggest war drum, 45 the lowest frame drum. The others have one note each.
    "war drums": I(0, 116, 36, 47, 41, held=False), "frame drums": I(0, 117, 45, 57, 50, held=False),
    "boom": I(0, 116, 36, 36, 36, held=False), "gong": I(0, 14, 48, 48, 48, held=False),
    "swell": I(0, 119, 49, 49, 49, held=False), "anvil": I(0, 113, 60, 60, 60, held=False),
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
    "piano": -28.0, "bass flute": -26.0, "bass clarinet": -24.4, "handbells": -27.0, "euphonium": -21.4,
    "war drums": -30.0, "frame drums": -30.0, "boom": -30.0, "gong": -30.0, "swell": -30.0, "anvil": -30.0,
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
    # --- more Warcraft colours (2026-11-16, played: "need more variety in warcraft"). The heavy music for walking ------
    # --- about was the thinnest: a dark wood had three pieces of its own. New voices: a piano, a bass flute, a bass ------
    # --- clarinet, handbells and a euphonium. ------------------------------------------------------------------------
    C("shadowed wood", ("haunted", "pastoral"), modes=("dorian", "minor"), bpm=(72, 84), metres=("4/4", "6/8"), busy=0.4, weight=0.85,
      leads=("bass flute", "clarinet", "viola"), strong=("violins", "horns"), under=("bass clarinet",),
      pads=("strings slow", "oohs"), pad_ways=("pad", "drone"), plucks=("harp", "celesta", "pizzicato"), figures=("arp", "toll"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=("great drum",), grooves=("rain", "dirge"), hall=(2.8, 0.3), lift=0.25,
      titles=(("Shadowed", "Gloomwood", "Thornbriar", "Ravenhollow", "Bleak", "Grey Bark"), ("Wood", "Thicket", "Path", "Boughs", "Glen", "Deeps"))),
    C("fallen farmstead", ("pastoral", "haunted"), modes=("minor", "dorian"), bpm=(84, 96), metres=("3/4", "4/4"), busy=0.45, weight=0.8,
      leads=("english horn", "cello", "fiddle"), strong=("violins", "horns"), under=("celli",), pads=("strings", "strings slow"),
      pad_ways=("pad", "tremolo"), plucks=("guitar", "harp", "pizzicato"), figures=("rock", "arp"), basses=("celli", "basses pizz"),
      kit="folk", drums=("timpani",), grooves=("waltz", "stately"), hall=(2.2, 0.24), lift=0.3,
      titles=(("Burned", "Empty", "Fallow", "Abandoned", "Last", "Weedgrown"), ("Farmstead", "Furrows", "Barn", "Homestead", "Acre", "Fields"))),
    C("border keep", ("pastoral", "regal", "highland"), modes=("mixolydian", "dorian", "major"), bpm=(100, 112), busy=0.55, weight=0.9,
      leads=("horns", "fiddle", "trumpet"), strong=("trumpet", "violins"), under=("euphonium", "trombone"), pads=("strings", "brass"),
      pad_ways=("pad",), plucks=("strings", "pizzicato", "harp"), figures=("pulse", "gallop"), basses=("celli", "basses"), kit="march",
      drums=("timpani",), grooves=("march", "reel"), hall=(2.0, 0.22), lift=0.45,
      titles=(("Border", "Watchtower", "Westbrook", "Sentinel", "Stonewall", "Bridgeguard"), ("Keep", "Patrol", "Garrison", "Muster", "Post", "Rampart"))),
    C("rain on the roof", ("pastoral", "highland"), light=True, modes=("major", "lydian", "dorian"), bpm=(70, 84), metres=("4/4", "3/4"),
      busy=0.45, weight=0.5, leads=("piano", "oboe", "clarinet"), strong=("violins slow", "piano"), under=("cello",), pads=("strings slow",),
      pad_ways=("pad",), plucks=("piano", "harp"), figures=("arp", "rock"), basses=("celli slow", "basses pizz"), kit="folk", drums=(),
      grooves=("rain", "tick"), hall=(2.4, 0.26), lift=0.2,
      titles=(("Rainy", "Window", "Puddle", "Drizzle", "Grey Morning", "Thatch"), ("Lane", "Song", "Hours", "Roof", "Afternoon", "Pane"))),
    C("forsaken parlour", ("haunted", "regal"), modes=("minor",), bpm=(66, 78), metres=("3/4", "4/4"), busy=0.4, weight=0.8,
      leads=("piano", "cello", "violin"), strong=("violins", "piano"), under=("celli",), pads=("tremolo", "strings slow"),
      pad_ways=("tremolo", "pad"), plucks=("piano", "harpsichord", "celesta"), figures=("arp", "toll"), basses=("celli", "basses slow"),
      kit="orchestra", drums=("timpani",), grooves=("tick", "dirge"), hall=(2.8, 0.3), lift=0.25,
      titles=(("Forsaken", "Dust-Sheet", "Candlelit", "Cracked", "Shuttered", "Widow's"), ("Parlour", "Manor", "Ballroom", "Portrait", "Nocturne", "Stair"))),
    C("witch hollow", ("haunted", "jungle"), modes=("phrygian", "minor"), bpm=(96, 110), metres=("5/4", "7/8", "6/8"), busy=0.55, weight=0.8,
      leads=("bass clarinet", "oboe", "fiddle"), strong=("violins", "clarinet"), under=("bassoon",), pads=("tremolo", "oohs"),
      pad_ways=("tremolo", "drone"), plucks=("harpsichord", "pizzicato", "marimba"), figures=("pattern", "oompah"),
      basses=("basses pizz", "bassoon"), kit="wood", drums=(), grooves=("bones", "bog"), hall=(2.2, 0.24), lift=0.3,
      titles=(("Witch", "Hag's", "Toadstool", "Cauldron", "Black Cat", "Hex"), ("Hollow", "Brew", "Hut", "Circle", "Charm", "Ring"))),
    C("spirit grove", ("mystic", "pastoral"), light=True, modes=("lydian", "major"), bpm=(76, 88), metres=("3/4", "6/8"), busy=0.4, weight=0.5,
      leads=("pan flute", "handbells", "flute"), strong=("handbells", "violins slow"), under=("celli", "clarinet"), pads=("oohs", "strings slow"),
      pad_ways=("pad",), plucks=("handbells", "celesta", "harp"), figures=("arp", "pattern"), basses=("celli slow", "celli pizz"),
      kit="folk", drums=(), grooves=("sparkle", "waltz"), hall=(3.0, 0.32), lift=0.2,
      titles=(("Spirit", "Dawnpetal", "Feather", "Wishing", "Sunlit", "Bright"), ("Grove", "Bells", "Spring", "Clearing", "Ring", "Glade"))),
    C("barrow kings", ("highland", "haunted"), modes=("minor", "dorian", "phrygian"), bpm=(60, 72), busy=0.3, weight=1.0,
      leads=("euphonium", "cello", "english horn"), strong=("brass", "choir"), under=("tuba", "trombone"), pads=("strings slow", "choir"),
      pad_ways=("drone", "pad"), plucks=("harp", "church bell"), figures=("toll", "arp"), basses=("basses slow", "tuba"), kit="orchestra",
      drums=("great drum", "timpani"), grooves=("dirge", "stately"), hall=(3.2, 0.34), lift=0.35,
      titles=(("Barrow", "Cairn", "Old King's", "Stone Crown", "Long Sleep", "Howe"), ("Kings", "Mound", "Tomb", "Vigil", "Rest", "Lords"))),
    C("cliffside wind", ("highland", "pastoral"), modes=("dorian", "mixolydian", "minor"), bpm=(108, 122), metres=("6/8",), busy=0.5, weight=0.9,
      leads=("horns", "english horn", "violin"), strong=("violins", "horns"), under=("celli", "trombone"), pads=("strings", "tremolo"),
      pad_ways=("pad", "tremolo"), plucks=("harp", "strings"), figures=("arp", "gallop"), basses=("celli", "basses"), kit="march",
      drums=("timpani",), grooves=("ride", "stately"), hall=(2.6, 0.28), lift=0.45,
      titles=(("Cliffside", "Windswept", "Seawall", "Gull's", "Salt", "Highcliff"), ("Wind", "Heights", "Reach", "Edge", "Bluff", "Lookout"))),
    C("dark ritual", ("infernal", "haunted"), modes=("phrygian", "minor"), bpm=(88, 100), metres=("4/4", "5/4"), busy=0.4, weight=1.0,
      leads=("choir", "trombone", "bass clarinet"), strong=("choir", "brass"), under=("trombone", "tuba"), pads=("organ", "choir"),
      pad_ways=("drone", "pad"), plucks=("strings", "bells"), figures=("hammer", "toll"), basses=("basses", "tuba"), kit="orchestra",
      drums=("taiko", "great drum"), grooves=("war camp", "dirge"), hall=(3.0, 0.32), lift=0.4,
      titles=(("Dark", "Blood", "Shadow", "Cinder", "Black Candle", "Bone"), ("Ritual", "Rite", "Summoning", "Altar", "Pact", "Covenant"))),
    C("savanna", ("desert", "jungle"), light=True, modes=("major", "mixolydian", "dorian"), bpm=(96, 110), metres=("6/8", "4/4"), busy=0.6,
      weight=0.55, leads=("flute", "kalimba", "marimba"), strong=("marimba", "flute"), under=("clarinet",), pads=("strings", "oohs"),
      pad_ways=("pad", "drone"), plucks=("kalimba", "marimba", "guitar"), figures=("pattern", "arp"), basses=("acoustic bass", "fretless"),
      kit="hands", drums=(), grooves=("canopy", "caravan"), hall=(1.8, 0.2), lift=0.2,
      titles=(("Savanna", "Golden", "Acacia", "Grassland", "Zebra", "Long Grass"), ("Morning", "Plains", "Run", "Horizon", "Herd", "Waterhole"))),
    C("temple steps", ("regal", "mystic"), modes=("lydian", "major", "dorian"), bpm=(66, 78), busy=0.35, weight=0.95,
      leads=("choir", "horns", "oboe"), strong=("choir", "trumpet"), under=("horns", "trombone"), pads=("organ", "strings slow"),
      pad_ways=("pad",), plucks=("harp", "handbells"), figures=("toll", "arp"), basses=("basses slow", "organ"), kit="orchestra",
      drums=("timpani",), grooves=("stately", "sparkle"), hall=(3.4, 0.36), lift=0.4,
      titles=(("Temple", "Sunlit", "Marble", "High Altar", "Golden", "Dawnward"), ("Steps", "Light", "Procession", "Spire", "Dawn", "Sanctum"))),
    C("night market", ("regal", "desert"), light=True, modes=("dorian", "mixolydian", "phrygian dominant"), bpm=(100, 114),
      metres=("6/8", "4/4"), busy=0.65, weight=0.55, leads=("clarinet", "mandolin", "violin"), strong=("violin", "clarinet"),
      under=("bassoon",), pads=("strings", "accordion"), pad_ways=("pad", "drone"), plucks=("guitar", "mandolin", "pizzicato"),
      figures=("strum", "oompah"), basses=("acoustic bass", "celli pizz"), kit="hands", drums=(), grooves=("claps", "caravan"),
      hall=(1.6, 0.17), lift=0.25,
      titles=(("Lamplit", "Moonlit", "Back Alley", "Spice", "Lantern", "Late"), ("Market", "Stalls", "Square", "Street", "Crowd", "Lanes"))),
    C("high pasture", ("highland", "pastoral"), light=True, modes=("mixolydian", "major", "dorian"), bpm=(88, 100), metres=("6/8", "3/4"),
      busy=0.55, weight=0.6, leads=("whistle", "oboe", "fiddle"), strong=("violins", "whistle"), under=("horns", "celli"),
      pads=("strings slow", "strings"), pad_ways=("pad", "drone"), plucks=("harp", "steel guitar", "celesta"), figures=("arp", "strum"),
      basses=("celli pizz", "acoustic bass"), kit="folk", drums=(), grooves=("jig", "sleigh"), hall=(2.0, 0.22), lift=0.3,
      titles=(("High", "Shepherd's", "Cloudy", "Bluebell", "Thistle", "Lark's"), ("Pasture", "Downs", "Slopes", "Fold", "Air", "Hills"))),
    # --- the open country, where most of an evening is spent (2026-11-16: "been hearing the same thing over and ---
    # --- over"): each with a lead the country's other light music does not have. ------------------------------------
    C("orchard morning", ("pastoral",), light=True, modes=("major", "mixolydian"), bpm=(96, 108), metres=("4/4", "6/8"), busy=0.65,
      weight=0.55, leads=("oboe", "bassoon", "flute"), strong=("violins", "oboe"), under=("bassoon", "celli"), pads=("strings", "strings slow"),
      pad_ways=("pad",), plucks=("pizzicato", "marimba", "harp"), figures=("pattern", "oompah"), basses=("basses pizz", "bassoon"),
      kit="folk", drums=(), grooves=("tick", "claps"), hall=(1.8, 0.2), lift=0.25,
      titles=(("Orchard", "Apple", "Cherry", "Hedgerow", "Bumblebee", "Picnic"), ("Morning", "Scherzo", "Caper", "Errand", "Romp", "Trot"))),
    C("sunset hills", ("pastoral", "highland"), light=True, modes=("major", "lydian", "mixolydian"), bpm=(66, 78), metres=("3/4", "4/4"),
      busy=0.35, weight=0.6, leads=("horns", "english horn", "violin"), strong=("violins slow", "horns"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "guitar"), figures=("arp", "rock"), basses=("celli slow", "basses pizz"),
      kit="folk", drums=(), grooves=("sparkle", "waltz"), hall=(2.6, 0.28), lift=0.35,
      titles=(("Sunset", "Amber", "Evening", "Long Shadow", "Homeward", "Golden"), ("Hills", "Vale", "Rise", "Glow", "Light", "Slope"))),
    C("lakeside reverie", ("pastoral", "mystic"), light=True, modes=("lydian", "major", "dorian"), bpm=(60, 72), metres=("4/4", "3/4"),
      busy=0.3, weight=0.5, leads=("piano", "flute", "cello"), strong=("violins slow", "flute"), under=("celli", "clarinet"),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "piano", "vibes"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("sparkle", "rain"), hall=(3.0, 0.32), lift=0.2,
      titles=(("Lakeside", "Still Water", "Reed", "Heron", "Mirror", "Lily Pad"), ("Reverie", "Dream", "Hour", "Mere", "Ripples", "Shallows"))),
    C("harvest home", ("pastoral",), light=True, modes=("major", "mixolydian"), bpm=(100, 112), metres=("3/4", "6/8"), busy=0.6, weight=0.65,
      leads=("violin", "clarinet", "whistle"), strong=("violins", "horns"), under=("celli", "bassoon"), pads=("strings",), pad_ways=("pad",),
      plucks=("harp", "glock", "pizzicato"), figures=("arp", "oompah"), basses=("celli pizz", "basses pizz"), kit="folk", drums=("timpani",),
      grooves=("waltz", "jig"), hall=(2.0, 0.22), lift=0.45,
      titles=(("Harvest", "Sheaf", "Hayrick", "Lammas", "Gleaner's", "Bonfire"), ("Home", "Feast", "Supper", "Round", "Thanks", "Ring"))),
    # --- caves and inns: a cave had two pieces, one light and one heavy, so every light cave played the same one ----
    C("glowworm grotto", ("mystic", "jungle", "pastoral"), role="depths", light=True, modes=("lydian", "dorian"), bpm=(60, 72),
      metres=("3/4", "4/4"), busy=0.3, weight=0.45, leads=("celesta", "bass flute", "vibes"), strong=("vibes", "oohs"), under=("celli",),
      pads=("oohs", "strings slow"), pad_ways=("pad",), plucks=("harp", "vibes", "celesta"), figures=("arp", "toll"),
      basses=("celli slow", "basses pizz"), kit="wood", drums=(), grooves=("drip",), hall=(4.0, 0.42), lift=0.0,
      titles=(("Glowworm", "Lantern", "Starry", "Hidden", "Firefly"), ("Grotto", "Hollow", "Cave", "Chamber", "Den"))),
    C("old mine", ("highland", "infernal", "regal"), role="depths", modes=("minor", "dorian", "phrygian"), bpm=(72, 84), busy=0.35, weight=0.7,
      leads=("bass clarinet", "euphonium", "english horn"), strong=("horns", "violins slow"), under=("trombone",),
      pads=("basses slow", "strings slow"), pad_ways=("drone", "pad"), plucks=("pizzicato", "marimba"), figures=("toll", "pulse"),
      basses=("basses pizz", "tuba"), kit="wood", drums=("great drum",), grooves=("drip", "anvil"), hall=(3.6, 0.38), lift=0.0,
      titles=(("Old", "Lamplit", "Collapsed", "Silver", "Copper", "Abandoned"), ("Mine", "Seam", "Shaft", "Gallery", "Lode", "Workings"))),
    C("crypt", ("haunted", "regal"), role="depths", modes=("minor", "phrygian"), bpm=(56, 66), busy=0.25, weight=0.65,
      leads=("oohs", "cello", "bass flute"), strong=("choir", "violins slow"), under=("celli",), pads=("organ", "tremolo"),
      pad_ways=("drone", "tremolo"), plucks=("church bell", "harp", "celesta"), figures=("toll", "arp"), basses=("basses slow",),
      kit="orchestra", drums=("great drum",), grooves=("drip", "dirge"), hall=(4.2, 0.45), lift=0.0,
      titles=(("Silent", "Sealed", "Dust", "Bone", "Candle", "Forgotten"), ("Crypt", "Ossuary", "Vault", "Tomb", "Catacomb", "Undercroft"))),
    C("fireside", ("pastoral", "highland", "regal"), role="ember", light=True, modes=("major", "dorian", "mixolydian"), bpm=(76, 88),
      metres=("3/4", "6/8"), busy=0.45, weight=0.45, leads=("piano", "fiddle", "clarinet"), strong=("fiddle", "piano"), under=("cello",),
      pads=("strings slow", "accordion"), pad_ways=("pad",), plucks=("guitar", "harp"), figures=("arp", "rock"),
      basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("waltz", "tick"), hall=(1.2, 0.13), lift=0.0,
      titles=(("Fireside", "Crackling", "Snug", "Mulled", "Pipe Smoke", "Chimney"), ("Tune", "Corner", "Waltz", "Rest", "Evening", "Glow"))),
    # --- more caves, inns and bosses (2026-11-16, played: "more different cave and special encounter pieces like inns ---
    # --- and caves"): a cave of each kind of place, an inn of each, and bosses other than the titan. -------------------
    C("frozen cavern", ("highland", "mystic"), role="depths", light=True, modes=("lydian", "dorian"), bpm=(56, 68), metres=("3/4", "4/4"),
      busy=0.3, weight=0.45, leads=("celesta", "flute", "handbells"), strong=("glock", "violins slow"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("celesta", "harp", "glock"), figures=("arp", "toll"),
      basses=("celli slow", "basses pizz"), kit="wood", drums=(), grooves=("drip",), hall=(4.4, 0.46), lift=0.0,
      titles=(("Frozen", "Icebound", "Rime", "Glittering", "Blue Ice", "Hoarfrost"), ("Cavern", "Grotto", "Halls", "Vault", "Deep", "Hollow"))),
    C("spider den", ("haunted", "jungle"), role="depths", modes=("phrygian", "minor"), bpm=(64, 76), metres=("4/4", "5/4"), busy=0.35,
      weight=0.7, leads=("bass clarinet", "viola", "bassoon"), strong=("violins", "horns"), under=("bassoon",), pads=("tremolo", "basses slow"),
      pad_ways=("tremolo", "drone"), plucks=("pizzicato", "harpsichord", "marimba"), figures=("pattern", "toll"),
      basses=("basses pizz", "bassoon"), kit="wood", drums=("great drum",), grooves=("drip", "bog"), hall=(3.6, 0.38), lift=0.0,
      titles=(("Silken", "Webbed", "Venom", "Brood", "Eight-Eyed", "Skittering"), ("Den", "Nest", "Lair", "Tunnels", "Burrow", "Hollow"))),
    C("lava tube", ("infernal", "desert"), role="depths", modes=("phrygian", "minor"), bpm=(66, 78), busy=0.3, weight=0.8,
      leads=("trombone", "bass clarinet", "english horn"), strong=("brass", "choir"), under=("tuba",), pads=("tremolo", "basses slow"),
      pad_ways=("drone", "tremolo"), plucks=("strings", "bells"), figures=("toll", "hammer"), basses=("basses slow", "tuba"),
      kit="orchestra", drums=("taiko", "great drum"), grooves=("drip", "anvil"), hall=(3.8, 0.4), lift=0.0,
      titles=(("Lava", "Smouldering", "Molten", "Sulphur", "Glowing", "Scorched"), ("Tube", "Vent", "Chasm", "Flow", "Throat", "Deep"))),
    C("sea grotto", ("pastoral", "mystic", "jungle"), role="depths", light=True, modes=("dorian", "lydian", "mixolydian"), bpm=(60, 72),
      metres=("6/8", "3/4"), busy=0.35, weight=0.45, leads=("flute", "harp", "oohs"), strong=("oohs", "violins slow"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "vibes", "guitar"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="wood", drums=(), grooves=("drip", "rain"), hall=(4.0, 0.42), lift=0.0,
      titles=(("Sea", "Tidal", "Shell", "Pearl", "Smuggler's", "Echoing"), ("Grotto", "Cave", "Cove", "Arch", "Pool", "Hollow"))),
    C("kobold tunnels", ("pastoral", "highland"), role="depths", light=True, modes=("mixolydian", "dorian"), bpm=(92, 104),
      metres=("4/4", "5/4"), busy=0.55, weight=0.5, leads=("bassoon", "clarinet", "oboe"), strong=("bassoon", "marimba"), under=("tuba",),
      pads=("strings",), pad_ways=("pad",), plucks=("marimba", "pizzicato", "xylophone"), figures=("pattern", "oompah"),
      basses=("basses pizz", "tuba"), kit="wood", drums=(), grooves=("tick", "drip"), hall=(3.0, 0.32), lift=0.0,
      titles=(("Candlelit", "Kobold", "Rickety", "Tallow", "Muddy", "Crooked"), ("Tunnels", "Diggings", "Warren", "Burrow", "Holes", "Mine"))),
    C("bandit hideout", ("desert", "jungle", "pastoral"), role="depths", modes=("phrygian dominant", "dorian", "minor"), bpm=(84, 96),
      busy=0.45, weight=0.65, leads=("shenai", "bass clarinet", "guitar"), strong=("violins", "shenai"), under=("bassoon",),
      pads=("strings", "basses slow"), pad_ways=("drone",), plucks=("dulcimer", "guitar", "pizzicato"), figures=("pulse", "pattern"),
      basses=("fretless", "basses pizz"), kit="hands", drums=(), grooves=("darbuka", "heat"), hall=(3.2, 0.34), lift=0.0,
      titles=(("Bandit", "Outlaw", "Thieves'", "Smuggler", "Hidden", "Masked"), ("Hideout", "Cache", "Lair", "Den", "Stash", "Hole"))),
    C("elven rest", ("mystic", "pastoral"), role="ember", light=True, modes=("lydian", "dorian"), bpm=(60, 72), metres=("3/4", "4/4"),
      busy=0.35, weight=0.4, leads=("harp", "flute", "oohs"), strong=("flute", "violins slow"), under=("celli",), pads=("strings slow", "oohs"),
      pad_ways=("pad",), plucks=("harp", "celesta"), figures=("arp", "rock"), basses=("celli slow", "celli pizz"), kit="folk", drums=(),
      grooves=("sparkle",), hall=(2.4, 0.26), lift=0.0,
      titles=(("Moonlit", "Starleaf", "Silvered", "Quiet", "Willow", "Dreaming"), ("Rest", "Bower", "Haven", "Lodge", "Respite", "Hearth"))),
    C("caravanserai", ("desert", "jungle", "infernal"), role="ember", light=True, modes=("phrygian dominant", "dorian", "mixolydian"),
      bpm=(72, 86), metres=("4/4", "7/8"), busy=0.45, weight=0.45, leads=("shenai", "guitar", "pan flute"), strong=("dulcimer", "violin"),
      under=("cello",), pads=("strings slow",), pad_ways=("drone",), plucks=("dulcimer", "guitar", "harp"), figures=("arp", "pattern"),
      basses=("fretless", "celli pizz"), kit="hands", drums=(), grooves=("heat", "caravan"), hall=(1.6, 0.17), lift=0.0,
      titles=(("Caravanserai", "Lamp-Lit", "Cool", "Courtyard", "Fountain", "Spice Merchant's"), ("Rest", "Evening", "Rug", "Tea", "Shade", "Welcome"))),
    C("lamplit inn", ("haunted", "regal"), role="ember", light=True, modes=("minor", "dorian"), bpm=(66, 78), metres=("3/4", "4/4"),
      busy=0.4, weight=0.45, leads=("cello", "clarinet", "piano"), strong=("violin", "piano"), under=("cello",), pads=("strings slow", "organ"),
      pad_ways=("pad",), plucks=("piano", "harp", "celesta"), figures=("arp", "rock"), basses=("acoustic bass", "celli pizz"), kit="folk",
      drums=(), grooves=("tick", "waltz"), hall=(1.4, 0.15), lift=0.0,
      titles=(("Shuttered", "Raven's", "Candlewick", "Last Lamp", "Bolted Door", "Lamplit"), ("Inn", "Room", "Parlour", "Rest", "Waltz", "Vigil"))),
    C("harbour saloon", ("pastoral", "desert", "jungle"), role="ember", light=True, modes=("major", "mixolydian"), bpm=(104, 118),
      busy=0.7, weight=0.55, leads=("piano", "clarinet", "trumpet"), strong=("piano", "clarinet"), under=("tuba",), pads=("accordion", "strings"),
      pad_ways=("pad",), plucks=("piano", "guitar", "pizzicato"), figures=("oompah", "strum"), basses=("tuba", "acoustic bass"), kit="folk",
      drums=(), grooves=("claps", "tick"), hall=(1.2, 0.13), lift=0.25,
      titles=(("Harbour", "Dockside", "Rum Barrel", "Bilge Rat", "Card Sharp's", "Saltwater"), ("Saloon", "Rag", "Stomp", "Shuffle", "Jig", "Two-Step"))),
    C("dread lord", ("haunted", "infernal"), role="boss", serves=(2,), modes=("phrygian", "minor"), bpm=(84, 96), metres=("4/4", "5/4"),
      busy=0.45, weight=1.0, leads=("choir", "trombone", "violins"), strong=("choir", "brass"), under=("trombone", "tuba"),
      pads=("organ", "tremolo"), pad_ways=("pad", "tremolo"), plucks=("strings", "church bell"), figures=("hammer", "gallop"),
      basses=("basses", "tuba"), kit="orchestra", drums=("great drum", "timpani", "taiko"), grooves=("colossus", "battle"),
      hall=(3.2, 0.32), lift=0.5,
      titles=(("Dread", "Shadow", "Bone", "Black", "Undying", "Plague"), ("Lord", "Throne", "Sovereign", "Master", "Tyrant", "Crown"))),
    C("wild king", ("jungle", "desert", "highland", "pastoral"), role="boss", serves=(2,), modes=("minor", "dorian", "phrygian dominant"),
      bpm=(96, 110), metres=("4/4", "6/8"), busy=0.5, weight=1.0, leads=("horns", "trombone", "shenai"), strong=("brass", "violins"),
      under=("trombone", "tuba"), pads=("tremolo", "strings"), pad_ways=("tremolo", "drone"), plucks=("strings", "marimba"),
      figures=("gallop", "hammer"), basses=("basses", "tuba"), kit="hands", drums=("taiko", "timpani"), grooves=("war drums", "hunt"),
      hall=(2.6, 0.28), lift=0.5,
      titles=(("Wild", "Beast", "Savage", "Primal", "Fang", "Thunder"), ("King", "Chieftain", "Brute", "Alpha", "Warlord", "Lord"))),
    # --- a town's streets and a battleground (2026-11-16, played: "like whenever in an alliance base should be a ------
    # --- family of songs", "or in a battleground, a family"). The town's songs are one family of heraldry: brass and ---
    # --- strings over a courtly march, in every kind of country; the battleground's, war drums from end to end. --------
    C("alliance town", KINDS_ALL, role="town", light=True, modes=("major", "mixolydian", "lydian"), bpm=(96, 108), metres=("4/4", "3/4"),
      busy=0.55, weight=0.7, leads=("trumpet", "horns", "violin"), strong=("trumpet", "violins"), under=("horns", "celli"),
      pads=("strings", "brass"), pad_ways=("pad",), plucks=("harp", "pizzicato", "glock"), figures=("arp", "pulse"),
      basses=("celli pizz", "basses pizz"), kit="march", drums=("timpani",), grooves=("courtly", "march"), hall=(2.2, 0.24), lift=0.35,
      titles=(("Lion's", "Banner", "Bell Tower", "Gatehouse", "Herald's", "Crown"), ("Square", "Gate", "Town", "Welcome", "Muster", "Hall"))),
    C("town square", KINDS_ALL, role="town", light=True, modes=("major", "mixolydian"), bpm=(100, 112), metres=("6/8", "4/4"), busy=0.65,
      weight=0.55, leads=("fiddle", "flute", "clarinet"), strong=("fiddle", "flute"), under=("bassoon",), pads=("accordion", "strings"),
      pad_ways=("pad",), plucks=("guitar", "mandolin", "harp"), figures=("strum", "oompah"), basses=("acoustic bass", "celli pizz"),
      kit="folk", drums=(), grooves=("claps", "jig"), hall=(1.6, 0.17), lift=0.25,
      titles=(("Fountain", "Cobbled", "Lantern Post", "Well", "Baker's", "Cooper's"), ("Square", "Lane", "Morning", "Bustle", "Errand", "Corner"))),
    C("battleground", KINDS_ALL, role="battleground", serves=(0, 1, 2), modes=("minor", "dorian"), bpm=(132, 148), metres=("4/4", "6/8"),
      busy=0.6, weight=1.0, leads=("horns", "trumpet", "violins"), strong=("brass", "violins"), under=("trombone", "horns"),
      pads=("tremolo", "strings"), pad_ways=("tremolo", "pad"), plucks=("strings", "pizzicato"), figures=("gallop", "hammer"),
      basses=("celli", "basses"), kit="march", drums=("timpani", "taiko"), grooves=("battle", "ride"), hall=(2.0, 0.22), lift=0.45,
      titles=(("Rallying", "Banner", "Flag", "Contested", "Front Line", "Standard"), ("Charge", "Clash", "Struggle", "Rally", "Field", "Line"))),
    C("siege line", KINDS_ALL, role="battleground", serves=(0, 1, 2), modes=("phrygian", "minor"), bpm=(120, 132), busy=0.5, weight=1.0,
      leads=("trombone", "choir", "horns"), strong=("brass", "choir"), under=("tuba", "trombone"), pads=("choir", "tremolo"),
      pad_ways=("pad", "tremolo"), plucks=("strings", "bells"), figures=("hammer", "pulse"), basses=("basses", "tuba"), kit="orchestra",
      drums=("taiko", "great drum", "timpani"), grooves=("war drums", "colossus"), hall=(2.4, 0.26), lift=0.5,
      titles=(("Iron", "Siege", "Burning", "Last", "Broken", "Thundering"), ("Line", "Wall", "Bridge", "Ramparts", "Stand", "Breach"))),
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
# Changes for a second theme: three chords of two bars each, and then the mode's way home. A
# second theme begins away from home, on the mode's other side (the relative key of a minor
# one, the fourth or the sixth of a major one), and uses only chords that are whole in the mode.
SECONDS = {
    "major": ("4 1 2", "6 4 1", "4 6 2", "6 3 4", "2 6 4", "4 1 6", "3 6 4"),
    "lydian": ("5 6 1", "6 5 1", "6 1 5", "5 1 6", "3 6 5"),
    "mixolydian": ("4 1 5", "5 4 1", "4 6 1", "6 4 1", "2 4 1"),
    "dorian": ("3 7 1", "7 3 1", "3 1 7", "5 3 7", "7 1 3"),
    "minor": ("3 7 6", "6 3 7", "6 7 1", "3 6 4", "4 7 3", "7 3 6"),
    "phrygian": ("6 7 1", "3 6 7", "6 3 4", "4 3 6", "7 6 3"),
    "phrygian dominant": ("4 7 1", "7 4 1", "4 1 7", "7 1 4"),
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
# The long story: nine parts in two waves
# ---------------------------------------------------------------------------------------------
# The parts of the story, in order, and the word the player knows each by. The player has five
# words; a long story uses three of them more than once.
PARTS = ("open", "first", "second", "build", "arrival", "valley", "climb", "summit", "close")
WORD = {"open": "open", "first": "theme", "second": "theme", "build": "rise", "arrival": "moment", "valley": "theme",
        "climb": "rise", "summit": "moment", "close": "close"}
THEMATIC = ("first", "second", "arrival", "valley", "summit")      # the parts in which a theme is sung whole
FIGHTS = ("battle", "boss", "storm", "battleground")
LONG = 480.0                   # seconds: about how long a track is
SHORTEST, LONGEST = 455.0, 505.0
# How the time is shared out. The summit is the longest part and the opening and the close the
# shortest; a fight hardly opens at all.
SHARES = {"open": 0.085, "first": 0.125, "second": 0.12, "build": 0.10, "arrival": 0.115, "valley": 0.10, "climb": 0.125,
          "summit": 0.135, "close": 0.095}
FIGHT_SHARES = {"open": 0.045, "first": 0.135, "second": 0.13, "build": 0.12, "arrival": 0.135, "valley": 0.10, "climb": 0.135,
                "summit": 0.14, "close": 0.06}
MINUTE = 66.0                  # a part in which a theme is sung is kept under this many seconds where it can be


@dataclass
class Section:
    story: str                     # the player's word for it: open, theme, rise, moment or close
    bars: int
    chords: list[str]              # one for each bar
    level: tuple[float, float]     # how hard it is played at its start and at its end, 0 to 1
    lifted: bool = False           # in the higher key
    part: str = ""                 # which part of the long story it is (PARTS)


@dataclass
class Family:
    name: str
    title: str
    character: Character
    seed: int
    key: Key
    bpm: float
    metre: str
    lift: int                      # semitones the second wave is lifted by; 0 for none
    sections: list[Section] = field(default_factory=list)
    period: int = 8                # bars in one statement of a theme: eight, or sixteen where eight would be over too soon
    valley: str = "second"         # which theme is sung in the valley: the broader of the two

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

    def section(self, part: str) -> Section:
        return next(section for section in self.sections if section.part == part)


def _spread(figures: str, bars: int) -> list[str]:
    """A run of chords laid over so many bars, each for as long as the others."""
    chords = figures.split()
    return [chords[min(index * len(chords) // bars, len(chords) - 1)] for index in range(bars)]


def _lengths(bar_s: float, period: int, fight: bool) -> dict[str, int]:
    """How many bars each part of the story has, for a track of about eight minutes. A part in
    which a theme is sung is so many statements of it, with room at the end, if need be, for
    its second half once more; the other parts go in fours (in twos where a bar is long)."""
    shares = FIGHT_SHARES if fight else SHARES
    loose = 2 if bar_s >= 3.0 else 4
    grid = {part: period // 2 if part in THEMATIC else loose for part in PARTS}
    least = {part: period if part in THEMATIC else loose for part in PARTS}
    bars = {}
    for part in PARTS:
        count = max(int(shares[part] * LONG / bar_s / grid[part] + 0.5) * grid[part], least[part])
        if count * bar_s > MINUTE and count - grid[part] >= least[part]:
            count -= grid[part]
        bars[part] = count
    # Then a step at a time until the whole is the right length: whatever is furthest over its
    # share gives a step up, or whatever is furthest under takes one. A part that a step more
    # would carry past the minute is passed over while there is another, and a fight's opening
    # and close are the last to be made longer.
    for _ in range(60):
        whole = sum(bars.values()) * bar_s
        if SHORTEST <= whole <= LONGEST:
            break
        over = {part: bars[part] * bar_s - shares[part] * LONG for part in PARTS}
        if whole > LONGEST:
            able = [part for part in PARTS if bars[part] - grid[part] >= least[part]]
            part = max(able, key=lambda each: over[each])
            bars[part] -= grid[part]
        else:
            inner = [part for part in PARTS if not (fight and part in ("open", "close"))]
            able = [part for part in inner if (bars[part] + grid[part]) * bar_s <= MINUTE] \
                or [part for part in inner if (bars[part] + grid[part]) * bar_s <= MINUTE + 4.0] or list(PARTS)
            part = min(able, key=lambda each: over[each])
            bars[part] += grid[part]
    return bars


def _levels(role: str, heavy: float) -> dict[str, tuple[float, float]]:
    """How hard each part of the story is played, from its start to its end. The first arrival
    is clearly under the summit, and the valley between them is the quietest the story gets
    once it has begun. A fight is hard from its first bar, and its valley is only a breath; a
    night piece never gets far above a murmur."""
    if role in FIGHTS:
        return {"open": (0.6, 0.72), "first": (0.7, 0.8), "second": (0.66, 0.78), "build": (0.75, 0.95), "arrival": (0.9, 0.9),
                "valley": (0.58, 0.66), "climb": (0.68, 1.0), "summit": (1.0, 1.0), "close": (0.9, 0.65)}
    if role in ("night", "ember", "depths"):
        top, under = 0.5 + 0.4 * heavy, 0.46 + 0.26 * heavy
        return {"open": (0.2, 0.3), "first": (0.4, 0.48), "second": (0.36, 0.46), "build": (0.42, 0.42 + 0.2 * heavy),
                "arrival": (under, under), "valley": (0.24, 0.22), "climb": (0.3, 0.45 + 0.3 * heavy), "summit": (top, top),
                "close": (0.4, 0.15)}
    top, under = 0.55 + 0.45 * heavy, 0.52 + 0.3 * heavy
    return {"open": (0.22, 0.34), "first": (0.45, 0.58), "second": (0.42, 0.56), "build": (0.5, 0.5 + 0.34 * heavy),
            "arrival": (under, under), "valley": (0.26, 0.24), "climb": (0.34, 0.5 + 0.45 * heavy), "summit": (top, top),
            "close": (0.5, 0.18)}


def family(character: Character, seed: int, name: str, title: str) -> Family:
    """Makes up the changes for one family of tracks of a character: the chord under every bar
    of a story of about eight minutes, in two waves.

    It opens; states its first theme; states a second theme that begins away from home; builds
    on the first; arrives (the first theme with most of the band). Then the valley: one of the
    themes on a single instrument over very little. From there the climb, longer than the
    build, ending on a held chord that wants to go home; the summit, the first theme with
    everyone and the second sung underneath it; and the close. Where the family has a lift,
    the second wave (the climb, the summit and the close) is in a higher key."""
    rng = random.Random(seed)
    mode = rng.choice(character.modes)
    key = Key(rng.randrange(12), mode)
    metre = rng.choice(character.metres)
    beats = METRES[metre][0]
    bpm = float(rng.randint(*character.bpm))
    bar_s = beats * 60.0 / bpm
    fight = character.role in FIGHTS
    # A theme is eight bars; where eight bars are over in a quarter of a minute it is sixteen:
    # eight that end on a question and eight that answer it.
    period = 8 if 8 * bar_s >= 17.0 else 16
    lengths = _lengths(bar_s, period, fight)
    away, home = HOME[mode]
    eight = _spread(rng.choice(THEMES[mode]), 8)
    eight[6], eight[7] = away, home
    if eight[3] == "1":
        eight[3] = away                                # the first half ends away from home, so the second can come back
    lift = rng.choice((2, 2, 3)) if rng.random() < character.lift else 0
    one, two, three = rng.choice(SECONDS[mode]).split()
    other = [one, one, two, two, three, three, away, home]
    for _ in range(8):
        # A second theme over the very changes of the first is no second theme (found 2026-11-16: in major, "6 4 1 5"
        # and "6 4 1" come to the same eight bars). It is drawn again; the families that never met this are unchanged,
        # and so is the one that met it and had a take made already (the player plays a family's takes channel by
        # channel together, so its takes must keep one set of changes).
        if other != eight or name in SAME_THEMES_KEPT:
            break
        one, two, three = rng.choice(SECONDS[mode]).split()
        other = [one, one, two, two, three, three, away, home]
    rises = list(RISES[mode])
    rng.shuffle(rises)
    # In the valley the broader of the two themes is sung: the second where the first is busy
    # (a second theme is broad where the first is busy, and busy where it is broad).
    valley = "second" if character.busy >= 0.5 else "first"

    def whole(changes: list[str]) -> list[str]:
        """One statement of a theme: its eight bars, or eight that stop on the chord before
        home and then the eight."""
        return list(changes) if period == 8 else changes[:6] + [away, away] + changes

    first, second = whole(eight), whole(other)

    def run(bars: int, changes: list[str]) -> list[str]:
        """A theme's changes as often as they go into so many bars, and then, where there is
        room for half a statement more, its second half again."""
        out: list[str] = []
        while bars - len(out) >= period:
            out += changes
        if bars - len(out) >= period // 2:
            out += changes[period // 2:]
        if len(out) != bars:
            raise ValueError("%d bars is not so many statements of a theme of %d" % (bars, period))
        return out

    colour = COLOUR[mode]
    swing = colour if colour != away else "1"
    opening = ["1"] * lengths["open"]
    if lengths["open"] >= 4:
        opening[lengths["open"] // 2] = colour
    for bar in range(lengths["open"] // 2 + 4, lengths["open"] - 1, 4):
        opening[bar] = colour                          # a long opening stirs every fourth bar of its second half
    turn = 1 if bar_s >= 2.4 else 2 if bar_s >= 1.3 else 4
    closing = [colour if (index // turn) % 2 == 0 else "1" for index in range(lengths["close"])]
    for bar in range(max(lengths["close"] - max(turn, 2), 0), lengths["close"]):
        closing[bar] = "1"
    # The climb: a rise of its own for its first half, then two chords swinging to and fro, and
    # at the last the chord before home, held.
    early = lengths["climb"] // 2
    late = lengths["climb"] - early
    hold = min(4 if late >= 8 else 2, late)
    step = 1 if bar_s >= 2.2 else 2
    climbing = _spread(rises[1 % len(rises)], early) + [swing if (index // step) % 2 == 0 else away for index in range(late - hold)] \
        + [away] * hold
    changes = {"open": opening, "first": run(lengths["first"], first), "second": run(lengths["second"], second),
               "build": _spread(rises[0], lengths["build"]), "arrival": run(lengths["arrival"], first),
               "valley": run(lengths["valley"], second if valley == "second" else first), "climb": climbing,
               "summit": run(lengths["summit"], first), "close": closing}
    levels = _levels(character.role, character.weight)
    made = Family(name=name, title=title, character=character, seed=seed, key=key, bpm=bpm, metre=metre, lift=lift,
                  period=period, valley=valley)
    made.sections = [Section(WORD[part], lengths[part], changes[part], levels[part], bool(lift) and part in ("climb", "summit", "close"),
                             part) for part in PARTS]
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
# Where each bar's first note lies between the bottom and the top of a tune: for eight bars
# that come home, and for eight that end on a question. The highest note comes late. A second
# theme begins high and comes down before it climbs, where a first begins in the middle.
_HEIGHTS = {
    "first": ((0.4, 0.5, 0.55, 0.42, 0.6, 0.95, 0.7, 0.3), (0.4, 0.5, 0.55, 0.42, 0.55, 0.72, 0.62, 0.48)),
    "second": ((0.78, 0.64, 0.7, 0.5, 0.56, 0.92, 0.62, 0.3), (0.78, 0.64, 0.7, 0.5, 0.46, 0.6, 0.66, 0.5)),
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


def theme(rng: random.Random, fam: Family, chords: list[Chord], busy: float, way: str = "first", broad: bool = False,
          unlike: Line | None = None) -> Line:
    """A tune over eight bars of chords, or over sixteen. It is made the way tunes are: a motif
    of two bars; the same motif again at another height, ending away from home; the motif a
    third time, climbing to the tune's highest note; and two bars that bring it home. Each bar
    begins on a note of its chord, and those notes, heard alone, are a line of their own that
    rises over the phrase and falls back.

    Over sixteen bars it is a question and its answer: eight bars that end on a held note away
    from home, then the same four bars again and four new ones that climb higher and come home.

    `way` is "first" for a first theme, which begins in the middle of its range on a note of
    the home chord, or "second" for a second theme, which begins high, comes down before it
    climbs, sits a little lower and leans on the first note of its motif. A `broad` tune has
    the first two notes of its motif, and of the bars that climb, drawn into one long one.
    `unlike` is a tune this one is to be told from: its motif does not have that one's rhythm."""
    beats, group = fam.beats, fam.group
    if len(chords) not in (8, 16):
        raise ValueError("A tune is eight bars or sixteen, not %d" % len(chords))
    low, high = (-3, 9) if way == "first" else (-4, 8)                # a tenth and a bit, around the key note
    homeward, asking = _HEIGHTS[way]
    start = rng.choice((0, 2, 4))                                 # a first theme's first note: the key note, its third or its fifth
    first, second, third = _cell(rng, group, busy), _cell(rng, group, busy * 0.7), _cell(rng, group, min(busy * 1.2, 1.0))
    if len(second) > 1:
        second = second[:-2] + [second[-2] + second[-1]]           # the answer ends on a longer note
    if broad and len(third) > 2:
        third = [third[0] + third[1]] + third[2:]

    def motif(cell: list[float]) -> list[float]:
        """A bar of rhythm made into a motif: two notes at the least; a second theme's with
        its longest note first; a broad one's first two notes drawn into one."""
        for _ in range(6):
            if len(cell) > 1:
                break
            cell = _cell(rng, group, min(busy + 0.3, 1.0))
        if way == "second":
            cell = sorted(cell, reverse=True)
        if broad and len(cell) > 2:
            cell = [cell[0] + cell[1]] + cell[2:]
        return cell

    first = motif(first)
    told = [length for at, length, _, _ in unlike.notes if at < beats - 1e-6] if unlike is not None else None
    for _ in range(6):
        if first != told:
            break
        first = motif(_cell(rng, group, busy))
    sixth = "first" if rng.random() < 0.5 else "third"
    leap = rng.random() < 0.5
    cells = {"first": (first, _shape(rng, len(first) - 1, leap)), "second": (second, _shape(rng, len(second) - 1, False)),
             "third": (third, _shape(rng, len(third) - 1, True)), "end": ([beats], [])}
    order = ("first", "second", "first", "second", "third", sixth, "second", "end")

    def phrase(eight: list[Chord], heights: tuple[float, ...], home: bool, given: list[int] | None = None
               ) -> tuple[list[int], list[tuple[float, float, int, float]]]:
        """Eight bars: the note each bar begins on, and the notes. `given` is the notes the
        first four bars begin on, where they are to be the same as another phrase's."""
        spine: list[int] = list(given or [])
        for bar in range(len(spine), 8):
            choices = _chord_steps(eight[bar], low, high)
            # Three bars do not begin on one note (unless that is the only way home).
            thrice = spine[-1] if len(spine) >= 2 and spine[-1] == spine[-2] else None
            free = [step for step in choices if step != thrice] or choices
            if bar == 0:
                aim = float(start) if way == "first" else low + heights[0] * (high - low)
            else:
                aim = low + heights[bar] * (high - low) + rng.uniform(-1.0, 1.0)
            if bar == 7 and home:
                choices = [step for step in choices if step % 7 == 0] or choices          # home
                aim = min((0, 7), key=lambda step: abs(step - spine[-1]))
            elif bar == 7:
                # A question: the second or the fifth of the scale, or at least not the key note.
                choices = [step for step in free if step % 7 in (1, 4)] or [step for step in free if step % 7] or free
            elif bar == 3:
                choices = [step for step in free if step % 7 in (1, 4)] or free            # the second or the fifth: a question
            else:
                choices = free
            before = spine[-1] if spine else aim
            spine.append(min(choices, key=lambda step: abs(step - aim) + (1.5 if abs(step - before) > 4 else 0.0)
                             + (0.8 if step == before and bar not in (0, 7) else 0.0)))
        notes: list[tuple[float, float, int, float]] = []
        for bar, chord in enumerate(eight):
            cell, moves = cells[order[bar]]
            step, at = spine[bar], bar * beats
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
                notes.append((at, length if bar < 7 else length * 0.75, step, min(weight, 1.0)))
                at += length
        return spine, notes

    if len(chords) == 8:
        _, notes = phrase(chords, homeward, True)
    else:
        spine, notes = phrase(chords[:8], asking, False)
        _, answer_notes = phrase(chords[8:], homeward, True, given=spine[:4])
        notes += [(at + 8 * beats, length, step, weight) for at, length, step, weight in answer_notes]
    return Line(_singable(notes, beats, chords))


def _singable(notes: list[tuple[float, float, int, float]], beats: float, chords: list[Chord],
              widest: int | None = 14) -> list[tuple[float, float, int, float]]:
    """A line put right where it is awkward to sing, and a tune never wider than two octaves:
    what is further out than that comes a step back in, and the line is looked over again.
    (A line that goes under a tune may be as wide as it likes: `widest` is None.)"""
    for _ in range(4):
        notes = _smoothed(notes, beats, chords)
        steps = [step for _, _, step, _ in notes]
        if widest is None or max(steps) - min(steps) <= widest:
            break
        top = max(steps)
        notes = [(at, length, step - 1 if step == top else step, weight) for at, length, step, weight in notes]
    return notes


def _smoothed(notes: list[tuple[float, float, int, float]], beats: float, chords: list[Chord]) -> list[tuple[float, float, int, float]]:
    """A tune that sits on one note is no tune: where a note comes three times running, one of
    the three (not one that begins a bar, if that can be helped) moves a step aside; one that
    does begin a bar moves to another note of its chord. And no leap is wider than an octave:
    a note further off than that comes an octave nearer."""
    def threes(steps: list[int], around: int) -> bool:
        """Whether a note stands in a run of three of the same."""
        return any(steps[at] == steps[at + 1] == steps[at + 2] for at in range(max(around - 2, 0), min(around, len(steps) - 3) + 1))

    for _ in range(4):
        moved = False
        for index in range(len(notes) - 2):
            if not notes[index][2] == notes[index + 1][2] == notes[index + 2][2]:
                continue
            steps = [note[2] for note in notes]
            on_bar = {which: abs(notes[which][0] / beats - round(notes[which][0] / beats)) < 1e-6 for which in (index, index + 1, index + 2)}
            # Which of the three moves: not the tune's last note, not one that begins a bar, and
            # the later the better; and it moves the way that does not make another three.
            order = sorted((index, index + 1, index + 2), key=lambda which: (which == len(notes) - 1, on_bar[which], -which))
            ways = []
            for which in order:
                after = steps[which + 1] if which + 1 < len(steps) else steps[which]
                way = 1 if after > steps[which] or (after == steps[which] and which % 2) else -1
                moves = [way, -way]
                if on_bar[which]:
                    chord = chords[min(int(round(notes[which][0] / beats)), len(chords) - 1)]
                    moves = sorted((tone - steps[which] for tone in _chord_steps(chord, steps[which] - 4, steps[which] + 4)
                                    if tone != steps[which]), key=lambda move: (abs(move), -move * way))
                for by in moves:
                    trial = list(steps)
                    trial[which] += by
                    if not threes(trial, which):
                        ways.append((which, by))
            # ...and, where it can, without making the tune any wider than it is.
            inside = [(which, by) for which, by in ways if min(steps) <= steps[which] + by <= max(steps)]
            which, by = (inside or ways or [(order[0], 1)])[0]
            at, length, step, weight = notes[which]
            notes[which] = (at, length, step + by, weight)
            moved = True
        for index in range(1, len(notes)):
            at, length, step, weight = notes[index]
            while abs(step - notes[index - 1][2]) > 7:
                step += 7 if step < notes[index - 1][2] else -7
            notes[index] = (at, length, step, weight)
        if not moved:
            break
    return notes


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


def recast(line: Line, chords: list[Chord], beats: float) -> Line:
    """A tune made to fit other chords than the ones it was written over. Bar by bar it is
    moved the least it can be for the bar's first note to be a note of the new chord (never
    more than a step), and a long note left off the chord moves on to it. What comes out has
    the tune's rhythm and its shape, which is what lets a second theme be sung under the
    first when the story comes to its summit."""
    out = Line()
    firsts: list[int] = []                      # the note each bar begins on: not the same one three bars running
    for bar, chord in enumerate(chords):
        notes = line.cut(bar * beats, (bar + 1) * beats).notes
        if not notes:
            continue
        on_chord = {step % 7 for step in chord.steps}
        moves = [move for move in (0, -1, 1, -2, 2, -3, 3) if (notes[0][2] + move) % 7 in on_chord]
        move = next((each for each in moves if not (len(firsts) >= 2 and notes[0][2] + each == firsts[-1] == firsts[-2])), moves[0])
        firsts.append(notes[0][2] + move)
        for start, length, step, weight in notes:
            step += move
            if length >= 1.0 and step % 7 not in on_chord:
                step += 1 if (step + 1) % 7 in on_chord else -1
            out.notes.append((bar * beats + start, length, step, weight))
    out.notes = _singable(out.notes, beats, chords, widest=None)
    return out


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
# Instruments that are there to hold chords and can carry a tune as well: who a second theme
# may be given to when the leads are all of a kind.
SINGERS = ("rock organ", "organ", "accordion", "choir", "oohs", "harmonica", "bagpipe", "shenai", "pan flute")
# A section of an orchestra plays one note at a time. A chord for the strings is therefore a
# line for each section, not a block: who takes which note, from the bottom up, by how many
# notes the chord has. (The second violins are the violins again, on a part of their own.)
DESKS = {
    "strings": {2: (("celli", ""), ("violas", "")), 3: (("celli", ""), ("violas", ""), ("violins", "")),
                4: (("celli", ""), ("violas", ""), ("violins", " seconds"), ("violins", ""))},
    "strings slow": {2: (("celli slow", ""), ("violas", "")), 3: (("celli slow", ""), ("violas", ""), ("violins slow", "")),
                     4: (("celli slow", ""), ("violas", ""), ("violins slow", " seconds"), ("violins slow", ""))},
}
# Families whose two themes came to the same changes and had a take made before that was mended (see `family`).
SAME_THEMES_KEPT = ("mystic-fireflies-1",)
# The small percussion: what may join a theme the second time round without crowding it.
SMALL = ("tamb", "shake", "jingle", "ting", "tick", "high", "clack", "conga", "conga low", "block", "block low", "guiro", "hat", "castanet", "bell")
# Who doubles the bass line an octave away, by who has it: the neighbour in the orchestra, played the same way.
PARTNERS = {"basses": "celli", "basses slow": "celli slow", "basses pizz": "celli pizz", "celli": "basses", "celli slow": "basses slow",
            "celli pizz": "basses pizz", "acoustic bass": "celli pizz", "fretless": "celli pizz", "tuba": "basses", "bassoon": "basses pizz"}
# Who doubles a tune an octave above it rather than where the tune is: high woodwinds and bells.
HIGH = ("flute", "piccolo", "whistle", "recorder", "ocarina", "pan flute", "glock", "celesta", "xylophone")
# The orchestra's own low drums: what the war drums stand in for while they play.
LOW = ("boom", "great drum", "taiko", "deep")


# ---------------------------------------------------------------------------------------------
# A take: the whole story, written out for the band
# ---------------------------------------------------------------------------------------------
class Take:
    """One take of a family: every part of the story written for every channel.

    A take has two themes of its own over the family's changes. Who sings them, what the
    accompaniment plays under each, how the bass walks and what the drums do are settled once
    (`cast`) and differ from one part of the story to the next, so that eight minutes are
    not one minute eight times: the second theme has another singer, another figure under it,
    another pad and another groove than the first."""

    def __init__(self, fam: Family, take: int):
        self.fam, self.take, self.ch = fam, take, fam.character
        self.rng = random.Random(fam.seed * 9973 + take * 7919 + 5)
        self.beats, self.group = fam.beats, fam.group
        # What the feet tap: a quarter note, or in six-eight and seven-eight an eighth.
        self.pulse = 0.5 if any(size % 1 for size in self.group) else 1.0
        self.starts, at = [], 0.0
        for size in self.group:
            self.starts.append(at)
            at += size
        self.voices: dict[str, dict[str, Voice]] = {channel: {} for channel in CHANNELS}
        self.spans: list[tuple[Section, float, Key, list[Chord]]] = []
        at = 0.0
        for section in fam.sections:
            key = fam.key.lifted(fam.lift) if section.lifted else fam.key
            self.spans.append((section, at, key, [key.chord(figure) for figure in section.chords]))
            at += section.bars * self.beats
        self.total = at
        self.heavy = self.ch.weight >= 0.8
        self.fight = self.ch.role in FIGHTS
        # The breath before an arrival: for the last beat or two of each rise the tune rests and
        # the accompaniment stops striking, so that the downbeat lands the harder. It is the
        # last beat, or where that would be over too soon to hear, the last two (in six-eight
        # and the odd metres, the last group of the bar).
        beat_s = 60.0 / fam.bpm
        sizes = (1.0, 2.0) if self.pulse == 1.0 else (self.group[-1], self.group[-1] + self.group[-2 if len(self.group) > 1 else -1])
        self.breath = min(next((size for size in sizes if size * beat_s >= 0.45), sizes[-1]), self.beats / 2)
        self.gaps = [(first + section.bars * self.beats - self.breath, first + section.bars * self.beats)
                     for section, first, _, _ in self.spans if section.part in ("build", "climb")]
        self.cast()
        for write in (self.lead, self.texture, self.rhythm, self.bass, self.drums, self.war_drums, self.marks):
            write()

    def breathing(self, at: float) -> bool:
        """Whether a moment is in the breath before an arrival."""
        return any(first - 1e-6 <= at < last - 1e-6 for first, last in self.gaps)

    # --- the players -----------------------------------------------------------------------
    def cast(self) -> None:
        """Who does what in this take. The leads take turns from take to take; the second theme
        goes to someone who sits well away from the first theme's singer; and each of the pad,
        the accompaniment, the bass and the drums has a way of playing under the first theme
        and another under the second."""
        ch, rng, take = self.ch, self.rng, self.take
        turn = take % len(ch.leads)
        order = ch.leads[turn:] + ch.leads[:turn]
        self.solo, self.mate, self.third = order[0], order[1 % len(order)], order[2 % len(order)]
        self.strong = ch.strong[take % len(ch.strong):] + ch.strong[:take % len(ch.strong)]
        home = INSTRUMENTS[self.solo].home
        pool = [name for name in dict.fromkeys(order[1:] + ch.under + self.strong + tuple(pad for pad in ch.pads if pad in SINGERS))
                if name != self.solo]
        far = [name for name in pool if abs(INSTRUMENTS[name].home - home) >= 5] or pool
        self.other = far[take % len(far)] if far else self.solo
        # In the valley a theme is sung by someone who has not stated it.
        stated = self.solo if self.fam.valley == "first" else self.other
        self.hush = next((name for name in order + (self.other,) if name != stated), stated)
        self.pad, self.pad_b = ch.pads[take % len(ch.pads)], ch.pads[(take + 1) % len(ch.pads)]
        # In the valley there is as little as there can be: broken chords on the harp, slowly, or two notes held.
        self.valley_way = "arp" if "arp" in ch.pad_ways else "drone" if "drone" in ch.pad_ways else "pad"
        spin = rng.randrange(2)
        self.way, self.way_b = ch.pad_ways[(take + spin) % len(ch.pad_ways)], ch.pad_ways[(take + spin + 1) % len(ch.pad_ways)]
        self.pluck, self.pluck_b = ch.plucks[take % len(ch.plucks)], ch.plucks[(take + 1) % len(ch.plucks)]
        spin = rng.randrange(2)
        self.figure, self.figure_b = ch.figures[(take + spin) % len(ch.figures)], ch.figures[(take + spin + 1) % len(ch.figures)]
        ways = ("two", "walk", "oct") if ch.busy >= 0.5 else ("long", "two", "walk")
        self.bass_way = rng.choice(ways)
        if ch.band and self.heavy:
            self.bass_way = "eight"
        self.bass_way_b = rng.choice([way for way in ways if way != self.bass_way])
        spin = rng.randrange(2)
        self.groove = GROOVES[ch.grooves[(take + spin) % len(ch.grooves)]]
        self.groove_b = GROOVES[ch.grooves[(take + spin + 1) % len(ch.grooves)]]
        # Music for wandering is often left unresolved, so that its mood carries into the quiet
        # after it: half the takes end on the fifth of the key, not on the key note. A fight
        # and the music of a great city come home.
        homeward = self.fight or "regal" in ch.kinds or rng.random() < 0.5
        self.rest = 0 if homeward else 4
        # The big drums and what marks an arrival (`war_drums` and `marks`). A fight has war
        # drums nearly all the way, and so has the heavy music for walking from each rise to the
        # moment it comes to. A lighter piece of the desert, the jungle or the highlands has
        # hand drums instead. Music for the night, the inn and the depths has none of this.
        walk = ch.role == "wander"
        hand = len(ch.kinds) < len(KINDS_ALL) and bool(set(ch.kinds) & {"desert", "jungle", "highland"})
        self.has_war = self.fight or (walk and self.heavy)
        self.has_frames = not ch.band and (self.has_war or (walk and ch.weight >= 0.6 and hand))
        self.hand = hand                                         # hand drums go under its second theme
        self.forge = (walk or self.fight) and any("anvil" in name for name in ch.grooves)   # the "ting" of its groove is an anvil
        self.embers = self.has_war and not ch.band and not self.forge and len(ch.kinds) < len(KINDS_ALL) and "infernal" in ch.kinds
        self.has_swell = self.fight or (walk and ch.weight >= 0.6)
        self.has_gong = self.has_war and not ch.band and ch.weight >= 0.9

    def voice(self, channel: str, name: str, tag: str = "") -> Voice:
        have = self.voices[channel]
        if name + tag not in have:
            inst = INSTRUMENTS[name]
            volume = min(10 ** ((LEVEL - LOUD[name]) / 40.0) * inst.level, 1.0)
            have[name + tag] = Voice(inst.program, bank=inst.bank, volume=volume, shift=inst.early,
                                     pan=self.rng.uniform(-0.35, 0.35), wired=inst.wired, instrument=name)
        return have[name + tag]

    def kit(self) -> Voice:
        have = self.voices["drums"]
        if "kit" not in have:
            have["kit"] = Voice(KITS[self.ch.kit][0], drums=True, instrument="kit " + self.ch.kit)
        return have["kit"]

    def put(self, channel: str, name: str, start: float, length: float, pitch: int, loud: float, tag: str = "",
            tied: bool = False) -> None:
        inst = INSTRUMENTS[name]
        while pitch < inst.low:
            pitch += 12
        while pitch > inst.high:
            pitch -= 12
        if inst.held:
            # A bow or a breath needs a moment to speak: no note of theirs is shorter than this.
            # A note ends a little before the next is due; one that is `tied` on (a held chord
            # that goes straight into the next) only a twentieth of a second before.
            length = max(length - 0.05 * self.fam.bpm / 60.0 if tied else length * 0.97, 0.11 * self.fam.bpm / 60.0)
        self.voice(channel, name, tag).add(start, length, pitch, loud)

    def desk(self, name: str, rank: int, count: int) -> tuple[str, str]:
        """Who plays one note of a chord, and on which part: for the strings, the section whose
        line it is (`rank` counts the chord's notes from the bottom, `count` is how many it
        has); for anyone else, the instrument itself."""
        if name not in DESKS:
            return name, ""
        desks = DESKS[name][min(max(count, 2), 4)]
        return desks[min(max(rank, 0), len(desks) - 1)]

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
            pitch += shift
            # A line wider than the instrument: the notes it cannot reach come an octave in.
            while pitch > inst.high:
                pitch -= 12
            while pitch < inst.low:
                pitch += 12
            self.voice(channel, name, tag).add(at + start, length * (0.96 if inst.held else 1.0), pitch, min(weight * loud, 1.0))

    def spots(self, where: str) -> list[tuple[float, float]]:
        """The moments in a bar a drum pattern names, each with how strongly it is struck."""
        beats, pulse = self.beats, self.pulse
        starts = self.starts
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

    # --- the tunes ---------------------------------------------------------------------------
    def lead(self) -> None:
        ch, rng, beats, fam = self.ch, self.rng, self.beats, self.fam
        period = fam.period
        solo, mate, third, other, hush, strong = self.solo, self.mate, self.third, self.other, self.hush, self.strong
        first_chords = next(chords for section, _, _, chords in self.spans if section.part == "first")[:period]
        second_chords = next(chords for section, _, _, chords in self.spans if section.part == "second")[:period]
        # The first theme, and the same again with its leaps filled in; a second theme, which is
        # broad where the first is busy and busy where the first is broad; a slower line to go
        # under each; and the second theme made to fit the first one's chords, for the summit.
        tune = theme(rng, fam, first_chords, ch.busy)
        again = varied(rng, tune)
        broad = ch.busy >= 0.5
        tune_b = theme(rng, fam, second_chords, ch.busy * 0.45 if broad else min(ch.busy + 0.55, 1.0), way="second", broad=broad,
                       unlike=tune)
        again_b = varied(rng, tune_b)
        under = answer(rng, fam, first_chords, tune)
        under_b = answer(rng, fam, second_chords, tune_b)
        counter = recast(tune_b, first_chords, beats)
        self.tune, self.second, self.counter = tune, tune_b, counter
        whole, half = period * beats, period // 2 * beats

        def turns(bars: int) -> list[tuple[int, bool]]:
            """The statements of a theme that a part of the story has room for: the bar each
            begins at, and whether it is the whole theme or only its second half."""
            out, at = [], 0
            while bars - at >= period:
                out.append((at, True))
                at += period
            if bars - at >= period // 2:
                out.append((at, False))
            return out

        def octave_of(second: str, first: str) -> int:
            """Where a second player doubles a tune. In its own register: that is an octave
            off where the two sit far apart (horns under the violins) and the same notes where
            they sit close (a trumpet with the violins). A high woodwind or a bell that sits
            close goes an octave above."""
            return 1 if second in HIGH and INSTRUMENTS[second].home - INSTRUMENTS[first].home < 7 else 0

        for section, first, key, chords in self.spans:
            bars, part = section.bars, section.part

            def sing(name: str, line: Line, bar: float, loud: float, octave: int = 0, tag: str = "") -> None:
                self.sing("lead", name, line, first + bar * beats, key, chords, first, loud=loud, octave=octave, tag=tag)

            def run_up(players: list[str]) -> None:
                """The last bar of a rise runs up the scale to where the tune will begin, and
                stops short of the bar line: a breath before the arrival."""
                room = beats - self.breath
                step = min(self.pulse / 2 if fam.bpm < 110 else self.pulse, room / 2)
                count = max(int(round(room / step)), 2)
                top = tune.notes[0][2] + 7
                run = Line([(index * step, step, top - (count - index), 0.7 + 0.3 * index / count) for index in range(count)])
                for name in players:
                    sing(name, run, bars - 1, self.hard(section.level[1]))

            if part == "open":
                # A hint of the first theme: its first two bars, alone, and again from someone else.
                at = min(1, bars - 1)
                sing(solo, self.fit(tune.cut(0, min(2, bars) * beats), chords[at]), at, self.hard(section.level[0], 0.9))
                if bars >= 6:
                    at = bars // 2 + 1
                    sing(mate, self.fit(tune.cut(0, 2 * beats), chords[at], aim=rng.choice((-3, 2, 4))), at,
                         self.hard(self.level(section, at), 0.85))
                if bars >= 14:
                    at = bars * 3 // 4 + 1
                    sing(third, self.fit(tune.cut(0, 2 * beats), chords[at], aim=rng.choice((-2, 3))), at,
                         self.hard(section.level[1], 0.85))
            elif part == "first":
                # The first theme: stated, then again by another with its leaps filled in, then
                # by a third, then by two together. What room is left is its second half once more.
                for index, (bar, full) in enumerate(turns(bars)):
                    loud = self.hard(self.level(section, bar + period // 2))
                    if not full:
                        sing(third if third != solo else mate, again.cut(half, whole), bar, loud * 0.9)
                    elif index % 4 == 0:
                        sing(solo, tune, bar, loud)
                    elif index % 4 == 1:
                        sing(mate, again, bar, loud)
                    elif index % 4 == 2:
                        sing(third, tune, bar, loud)
                    else:
                        sing(solo, tune, bar, loud)
                        sing(mate, again, bar, loud * 0.9, octave=1 if mate != solo else -1)
                    if full and index >= 1 and not ch.band and ch.under:
                        # From its second statement the theme has a slower line under it (2026-11-16, played: "not
                        # enough instruments in each track"): it is stated alone once, then the band fills in.
                        below = ch.under[index % len(ch.under)]
                        if below not in (solo, mate, third):
                            sing(below, under, bar, loud * 0.7, tag=" under")
            elif part == "second":
                # The second theme, from someone who sits well away from the first one's singer;
                # the second time another has it and the first singer goes underneath.
                partner = next((name for name in (mate, third, solo) if name != other), other)
                for index, (bar, full) in enumerate(turns(bars)):
                    loud = self.hard(self.level(section, bar + period // 2), 0.95)
                    if not full:
                        sing(other, tune_b.cut(half, whole), bar, loud * 0.9)
                    elif index % 3 == 0:
                        sing(other, tune_b, bar, loud)
                    elif index % 3 == 1:
                        sing(partner, again_b, bar, loud)
                        if INSTRUMENTS[other].held and other != partner:
                            sing(other, under_b, bar, loud * 0.7, tag=" under")
                    else:
                        sing(other, tune_b, bar, loud)
                        sing(partner, again_b, bar, loud * 0.9, octave=1 if partner != other else -1)
                    already = index % 3 == 1 and INSTRUMENTS[other].held and other != partner
                    if full and index >= 1 and not already and not ch.band and ch.under:
                        below = ch.under[(index + 1) % len(ch.under)]
                        if below not in (other, partner):
                            sing(below, under_b, bar, loud * 0.7, tag=" under")
            elif part == "build":
                # The first theme's first bar and its second, turn about, each time a little
                # higher; more players as it goes, and closer together.
                motifs, bar, count, players = [tune.cut(0, beats), tune.cut(beats, 2 * beats)], 0, 0, [solo]
                while bar < bars - 1:
                    along = bar / bars
                    piece = self.fit(motifs[count % 2 if along < 0.6 else 0], chords[bar], aim=round(along * 6) - 2)
                    for name in players:
                        sing(name, piece, bar, self.hard(self.level(section, bar), 0.95))
                    if along >= 0.4 and mate not in players:
                        players.append(mate)
                    if along >= 0.7 and strong[0] not in players:
                        players.append(strong[0])
                    bar += 2 if along < 0.5 else 1
                    count += 1
                run_up(players)
            elif part == "arrival":
                # The first arrival: the first theme from whoever is strongest, a second strong
                # player joining for the second time round, and a slower line underneath.
                for index, (bar, full) in enumerate(turns(bars)):
                    use = (tune if index % 2 == 0 else again) if full else tune.cut(half, whole)
                    loud = self.hard(section.level[0])
                    sing(strong[0], use, bar, loud)
                    if len(strong) > 1 and full and (index >= 1 or ch.weight >= 0.9 or not ch.band):
                        # (In light music the second player has the tune a third above, not the same notes.)
                        sing(strong[1], use.moved(steps=2) if ch.light and not ch.band else use, bar, loud * 0.92,
                             octave=octave_of(strong[1], strong[0]))
                    if ch.under and full:
                        sing(ch.under[0], under, bar, loud * 0.75, tag=" under")
            elif part == "valley":
                # The valley: one of the themes from a single player who has not stated it, and
                # where there is time, again from another.
                sung, sung_again = (tune, again) if fam.valley == "first" else (tune_b, again_b)
                echo = next((name for name in (mate, third, other, solo) if name != hush), hush)
                for index, (bar, full) in enumerate(turns(bars)):
                    loud = self.hard(self.level(section, bar + period // 2), 0.9)
                    if not full:
                        sing(hush, sung.cut(half, whole), bar, loud * 0.9)
                    elif index % 2 == 0:
                        sing(hush, sung, bar, loud)
                    else:
                        sing(echo, sung_again, bar, loud * 0.95)
            elif part == "climb":
                # The climb. First the second theme's opening, handed from one player to another
                # and back; then the first theme's first bar, higher each time and closer
                # together, the strong players coming in one by one.
                opening, motifs = tune_b.cut(0, 2 * beats), [tune.cut(0, beats), tune.cut(beats, 2 * beats)]
                pair = [other, next((name for name in (mate, solo, third) if name != other), other)]
                turn, bar, count = bars // 3, 0, 0
                while bar + 2 <= turn:
                    piece = self.fit(opening, chords[bar], aim=round(4 * bar / max(turn, 1)) - 3)
                    sing(pair[count % 2], piece, bar, self.hard(self.level(section, bar), 0.9))
                    bar += 2
                    count += 1
                bar, count, players = turn, 0, [solo]
                while bar < bars - 1:
                    along = bar / bars
                    piece = self.fit(motifs[count % 2 if along < 0.75 else 0], chords[bar], aim=round((along - 0.33) * 9) - 2)
                    for name in players:
                        sing(name, piece, bar, self.hard(self.level(section, bar), 0.95))
                    if along >= 0.5 and mate not in players:
                        players.append(mate)
                    if along >= 0.66 and strong[0] not in players:
                        players.append(strong[0])
                    if along >= 0.85 and strong[-1] not in players:
                        players.append(strong[-1])
                    bar += 2 if along < 0.66 else 1
                    count += 1
                run_up(players)
            elif part == "summit":
                # The summit: the first theme from everyone strong, and underneath it the
                # second theme, made to fit these chords. Where the theme comes round more
                # than once, the first time has only the slower line under it, so that the
                # two themes together are the last thing to arrive.
                stated = turns(bars)
                several = sum(1 for _, full in stated if full) > 1
                below = ch.under or ((other,) if other not in strong else ())
                for index, (bar, full) in enumerate(stated):
                    use = (tune if index % 2 == 0 else again) if full else tune.cut(half, whole)
                    loud = self.hard(section.level[0])
                    sing(strong[0], use, bar, loud)
                    if len(strong) > 1:
                        sing(strong[1], use, bar, loud * 0.95, octave=octave_of(strong[1], strong[0]))
                    if full:
                        both = index >= 1 or not several
                        for name in below:
                            sing(name, counter if both else under, bar, loud * (0.85 if both else 0.8), tag=" under")
                    if ch.band and INSTRUMENTS[strong[0]].wired:
                        # Twin guitars: the tune again a third above it.
                        sing(strong[0], use.moved(steps=2), bar, loud * 0.8, tag=" twin")
                    if not ch.band and full and (index % 2 == 1 or not several):
                        top = "piccolo" if self.heavy else "glock"
                        sing(top, use, bar, loud * 0.6, octave=1 if self.heavy else 0)
            else:
                # The close: the first theme's opening once more, a memory of the second, the
                # first theme's last two bars, and the key note held.
                if bars >= 6:
                    sing(mate, self.fit(tune.cut(0, 2 * beats), chords[0]), 0, self.hard(section.level[0], 0.8))
                if bars >= 12:
                    at = bars // 2 - 1
                    sing(other, self.fit(tune_b.cut(0, 2 * beats), chords[at], aim=-2), at, self.hard(self.level(section, at), 0.8))
                home = max(bars - 4, 0)
                sing(solo, self.fit(tune.cut(whole - 2 * beats, whole), chords[home], aim=0), home,
                     self.hard(self.level(section, home), 0.85))
                if bars >= 3:
                    # The last note, held: the key note, or where the take leaves the story open, its fifth.
                    last = Line([(0.0, min(2, bars - home - 1) * beats + beats * 0.5, self.rest, 0.6)])
                    sing(solo, last, bars - 2, self.hard(section.level[1], 0.9))

    # --- the pad -----------------------------------------------------------------------------
    def texture(self) -> None:
        ch, beats = self.ch, self.beats
        lift = 5 if ch.light else 0
        # Under a second theme that is sung high the pad sits low, and the other way about.
        second_centre = 55 if INSTRUMENTS[self.other].home >= 64 else 62
        before: list[int] | None = None
        for section, first, key, chords in self.spans:
            part, bars = section.part, section.bars
            pad, way = (self.pad_b, self.way_b) if part in ("second", "valley") else (self.pad, self.way)
            if part == "valley" and not self.fight:
                way = self.valley_way
            name = "tremolo" if way == "tremolo" and part in ("open", "build", "climb") else pad
            count = {"open": 2, "first": 3, "second": 3, "build": 4, "arrival": 4, "valley": 2, "climb": 4, "summit": 4, "close": 3}[part]
            centre = {"open": 53, "first": 58, "second": second_centre, "build": 60, "arrival": 62, "valley": 56, "climb": 61,
                      "summit": 62, "close": 56}[part] + lift
            arp = way == "arp" and part in ("open", "first", "second", "valley", "close")
            drone = way == "drone" and part not in ("arrival", "summit")
            held: dict[int, tuple[float, int]] = {}                # which player: (since when, what pitch)
            # (For the strings a player is a section: each of them has one line of the chord.)
            who = [self.desk(name, player, count) for player in range(count)]
            swells = [self.voice("texture", player, tag) for player, tag in dict.fromkeys(who)]
            for bar, chord in enumerate(chords):
                at, level = first + bar * beats, self.level(section, bar)
                if drone:
                    root = key.pitch(0, centre - 7)
                    notes = [root, root + 7] + ([root + 12] if count > 2 else [])
                else:
                    notes = voiced(key, chord, before if before and len(before) == count else None, count, centre)
                    before = notes
                for swell in swells:
                    swell.swells.append((at, 0.3 + 0.62 * level))
                    swell.swells.append((at + beats * 0.5, 0.3 + 0.62 * min(level + 0.05, 1.0)))
                if arp:
                    # Broken chords on the harp: up through the chord and down again.
                    ladder = notes + [notes[0] + 12] + notes[::-1][:-1]
                    step = (self.pulse / 2 if self.pulse == 1.0 else self.pulse) * (2 if part == "valley" else 1)
                    for index in range(int(round(beats / step))):
                        self.put("texture", "harp", at + index * step, step * 2, ladder[index % len(ladder)],
                                 self.hard(level, 0.75 if index else 0.9))
                    continue
                for player, pitch in enumerate(notes):
                    if player in held and held[player][1] == pitch:
                        continue                                    # the same note again: it is held over the bar line
                    if player in held:
                        since, was = held[player]
                        self.put("texture", who[player][0], since, at - since, was, self.hard(0.55, 1.0), tag=who[player][1], tied=True)
                    held[player] = (at, pitch)
            end = first + bars * beats
            for player, (since, was) in held.items():
                self.put("texture", who[player][0], since, end - since, was, self.hard(0.55, 1.0), tag=who[player][1], tied=True)
            for swell in swells:
                swell.swells.append((end - 0.01, 0.3 + 0.62 * section.level[1]))
            if part in ("arrival", "summit") and self.heavy and not ch.band:
                # Most of the band at the first arrival: two lines an octave above the pad.
                # Everyone at the summit: voices too, where the palette has them. The two lines
                # are the first and second violins, unless the violins are busy (they have the
                # tune, or the pad is theirs already): then a flute and an oboe hold them.
                busy = "violins" in self.strong or name in DESKS
                above = (("oboe", ""), ("flute", "")) if busy else (("violins", " seconds"), ("violins", ""))
                for bar, chord in enumerate(chords):
                    at = first + bar * beats
                    for (player, tag), pitch in zip(above, voiced(key, chord, None, 2, centre + 14)):
                        self.put("texture", player, at, beats, pitch, self.hard(0.8 if part == "summit" else 0.65), tag=tag)
                    if part == "summit" and "choir" in ch.pads + ch.strong:
                        for pitch in voiced(key, chord, None, 3, 62):
                            self.put("texture", "choir", at, beats, pitch, self.hard(0.75), tag=" tutti")

    # --- the accompaniment -------------------------------------------------------------------
    def rhythm(self) -> None:
        ch, rng, beats, pulse, starts = self.ch, self.rng, self.beats, self.pulse, self.starts
        half = pulse / 2 if pulse == 1.0 else pulse
        slots = int(round(beats / half))

        def riff() -> list[tuple[float, float]]:
            """A riff of its own: where in the bar the chords fall and how long each rings."""
            if beats == 4.0:
                return list(rng.choice((
                    ((0.0, 1.5), (1.5, 1.0), (2.5, 1.5)), ((0.0, 0.75), (2.0, 0.75), (3.0, 0.5), (3.5, 0.5)),
                    ((0.0, 2.0), (2.5, 0.5), (3.0, 1.0)), ((0.0, 0.5), (0.5, 0.5), (1.5, 1.0), (2.5, 1.5)),
                    ((0.0, 1.0), (1.0, 0.5), (2.0, 1.0), (3.5, 0.5)), ((0.0, 3.0), (3.0, 0.5), (3.5, 0.5)))))
            if beats == 3.0 and pulse == 0.5:
                return list(rng.choice((((0.0, 1.0), (1.5, 1.0)), ((0.0, 1.5), (1.5, 0.5), (2.0, 1.0)), ((0.0, 0.5), (1.0, 0.5), (1.5, 1.5)))))
            return [(start, size * 0.8) for start, size in zip(starts, self.group)]

        def pattern() -> list[int | None]:
            """A pattern of its own: which note of the chord falls on which half beat."""
            walk, out = rng.randrange(3), []
            for slot in range(slots):
                walk = (walk + rng.choice((-1, 1, 1, 2))) % 4
                out.append(walk if slot == 0 or rng.random() < 0.68 else None)
            return out

        # One riff and one pattern for the first theme and what is made of it, and another for
        # the second: a take that has only one figure to its name still plays two things.
        self.riff, riff_b = riff(), riff()
        for _ in range(8):
            if riff_b != self.riff:
                break
            riff_b = riff()
        pattern_a, pattern_b = pattern(), pattern()

        def pluck(name: str, rank: int, at: float, length: float, pitch: int, loud: float, short: bool = False) -> None:
            """One note of the figure: `rank` is which note of the chord it is, from the bottom.
            Where the strings play the figure each section has its own note of the chord; and a
            `short` note from a bow is kept short enough to be a short stroke of it, not a long
            one cut off."""
            if self.breathing(at):
                return                                          # the breath before an arrival
            who, tag = self.desk(name, rank, 3)
            if short and INSTRUMENTS[who].held:
                length = min(length, 0.2 * self.fam.bpm / 60.0)
            self.put("rhythm", who, at, length, pitch, loud, tag=tag)

        # Each layer's last chord (by its instrument and how far it is raised), so that it moves to the next smoothly.
        leading: dict[tuple[str, int], list[int]] = {}

        def layer(name: str, figure: str, second: bool, raised: int, gain: float, key: Key, chord: Chord, bar: int, bar_at: float,
                  level: float, density: float) -> None:
            """One bar of an accompaniment's figure on one instrument."""
            inst = INSTRUMENTS[name]
            notes = voiced(key, chord, leading.get((name, raised)), 3, inst.home - 4 + raised)
            leading[(name, raised)] = notes
            ladder = notes + [notes[0] + 12]
            loud = self.hard(level, 0.8) * gain
            thin = density < 0.45
            if figure == "pulse":
                step = half if density >= 0.5 else pulse
                if density > 0.85 and pulse == 1.0 and self.fam.bpm <= 112:
                    step = 0.25
                for index in range(int(round(beats / step))):
                    on = index * step
                    strong = on in starts
                    for rank in ((0, 2) if strong or index % 2 == 0 else (1,)):
                        pluck(name, rank, bar_at + on, step * 0.45, notes[rank], loud * (1.0 if strong else 0.72), short=True)
            elif figure == "arp":
                for index in range(slots):
                    if thin and index % 2:
                        continue
                    order = (0, 1, 2, 3, 2, 1) if not second else (0, 2, 1, 3, 1, 2)
                    pluck(name, order[index % 6], bar_at + index * half, half * 1.6, ladder[order[index % 6]],
                          loud * (1.0 if index * half in starts else 0.75))
            elif figure == "strum":
                for index in range(slots):
                    on = index * half
                    down = on in starts
                    if not down and (thin or index % 2 == 0 and pulse == 1.0 and density < 0.8):
                        continue
                    for string, rank in enumerate((0, 1, 2, 3) if down else (3, 2, 1)):
                        pluck(name, rank, bar_at + on + string * 0.012, half * 0.9, ladder[rank], loud * (0.95 if down else 0.6))
            elif figure == "oompah":
                for index in range(int(round(beats / pulse))):
                    on = index * pulse
                    if on in starts:
                        continue
                    for rank in (1, 2, 3):
                        pluck(name, rank, bar_at + on, pulse * 0.5, ladder[rank], loud * 0.8, short=True)
            elif figure == "rock":
                order = (0, 2, 1, 2) if not second else (0, 1, 2, 1)
                for index in range(int(round(beats / pulse))):
                    if thin and index % 2:
                        continue
                    pluck(name, order[index % 4], bar_at + index * pulse, pulse * 1.5, ladder[order[index % 4]], loud * 0.8)
            elif figure == "toll":
                if bar % 2 == 0 or density > 0.8:
                    pluck(name, 3, bar_at, beats, notes[0] + 12, loud)
                    pluck(name, 2, bar_at + (starts[1] if len(starts) > 1 else beats / 2), beats / 2, notes[2], loud * 0.6)
            elif figure == "gallop":
                for on, weight in self.spots("gallop" if not thin else "groups"):
                    pluck(name, 0 if weight >= 1.0 else 1, bar_at + on, 0.22, notes[0] if weight >= 1.0 else notes[1], loud * weight,
                          short=True)
                    if weight >= 1.0:
                        pluck(name, 2, bar_at + on, 0.22, notes[2], loud * 0.85, short=True)
            elif figure == "hammer":
                for on, weight in self.spots("three"):
                    for rank, pitch in enumerate(notes):
                        pluck(name, rank, bar_at + on, half * 0.6, pitch, loud * weight, short=True)
                if not thin:
                    # Underneath, the lowest note an octave down: from the basses where the strings are hammering.
                    low = "basses" if name in DESKS else name
                    for on, weight in self.spots("halves"):
                        pluck(low, 0, bar_at + on, half * 0.4, notes[0] - 12, loud * 0.5 * weight, short=True)
            elif figure in ("riff", "chug"):
                # A riff: power chords with room between them, and the muted string chugging
                # where the chords are not. Root, fifth and octave: the third is left to the tune.
                root = key.pitch(chord.root, 45)
                root += 12 if root < 40 else -12 if root > 52 else 0
                power = (root, root + 7, root + 12)
                hits: list[tuple[float, float | None]] = list(riff_b if second else self.riff)
                if density > 0.85 or figure == "chug":
                    hits = hits + [(on, None) for on in [index * half for index in range(slots)]
                                   if not any(abs(on - at) < 1e-6 for at, _ in hits)]
                for on, length in sorted(hits, key=lambda hit: hit[0]):
                    if self.breathing(bar_at + on):
                        continue
                    if length is None:
                        if thin:
                            continue
                        self.put("rhythm", "muted guitar", bar_at + on, 0.2, root, loud * (0.75 if on in starts else 0.6))
                        self.put("rhythm", "muted guitar", bar_at + on, 0.2, root + 7, loud * 0.5)
                    else:
                        for pitch in power:
                            self.put("rhythm", "rhythm guitar", bar_at + on, length * 0.92, pitch, loud * (1.0 if on in starts else 0.9))
            elif figure == "pattern":
                for slot, which in enumerate(pattern_b if second else pattern_a):
                    if which is None or (thin and slot % 2):
                        continue
                    pluck(name, which, bar_at + slot * half, half * 1.2, ladder[which], loud * (1.0 if slot * half in starts else 0.75))
            else:
                raise ValueError("No such figure: %r" % figure)

        def fuller(part: str, bar: int, along: float) -> bool:
            """Where the other theme's figure plays as well: at the moments, from the second statement of
            each theme, and through the second half of each rise. (2026-11-16, played: "not enough
            instruments in each track".)"""
            return part in ("arrival", "summit") or (part in ("first", "second") and bar >= self.fam.period) \
                or (part in ("build", "climb") and along >= 0.5)

        for section, first, key, chords in self.spans:
            part, bars = section.part, section.bars
            for bar, chord in enumerate(chords):
                level, along = self.level(section, bar), bar / bars
                second = part in ("second", "valley") or (part == "climb" and along < 0.5)
                name, figure = (self.pluck_b, self.figure_b) if second else (self.pluck, self.figure)
                inst = INSTRUMENTS[name]
                density = {"open": 0.15, "first": 0.5, "second": 0.45, "build": 0.5 + 0.5 * along, "arrival": 0.9,
                           "valley": 0.5 if self.fight else 0.2, "climb": 0.35 + 0.65 * along, "summit": 1.0,
                           "close": 0.4 * (1.0 - along)}[part]
                bare = part == "open" or (part == "valley" and not self.fight)
                if bare and not ch.band and (figure not in ("toll", "rock", "arp") or bar % 2 == 1 or bar == 0):
                    continue
                if ch.band and part == "open":
                    density = 0.3                              # a band opens on its riff alone
                if bare and part == "valley" and (ch.band or self.valley_way == "arp"):
                    continue                                   # ...and in the valley its guitars rest; so does whoever would play against the harp
                if density < 0.12:
                    continue
                # Where the second theme has the same figure on the same instrument as the first,
                # it is at least played a fourth higher.
                raised = 5 if second and (self.pluck_b, self.figure_b) == (self.pluck, self.figure) else 0
                bar_at = first + bar * beats
                layer(name, figure, second, raised, 1.0, key, chord, bar, bar_at, level, density)
                # (A band's riff guitars are the band's whole accompaniment; the unplugged band takes the second figure too.)
                if not (ch.band and self.heavy) and fuller(part, bar, along):
                    # The other figure, on its own instrument (another of the palette's, where both themes have the
                    # same one), an octave up where the two would sit on each other, a little under the first.
                    with_name, with_figure = (self.pluck, self.figure) if second else (self.pluck_b, self.figure_b)
                    if with_name == name:
                        with_name = ch.plucks[(self.take + 2) % len(ch.plucks)]
                    if with_name != name or with_figure != figure:
                        apart = abs(INSTRUMENTS[with_name].home - INSTRUMENTS[name].home)
                        up = 12 if (with_name == name or apart < 7) else 0
                        layer(with_name, with_figure, not second, up, 0.72, key, chord, bar, bar_at, level, max(density, 0.5))
                if part in ("arrival", "summit") and self.heavy and not ch.band:
                    # The brass marks the chord: on the bar at the first arrival, on every strong beat
                    # at the summit. A line each for the trombones, the horns and the trumpets;
                    # until then the heavy brass has rested, so that it means something.
                    for on in (starts if part == "summit" else starts[:1]):
                        for player, pitch in zip(("trombone", "horns", "trumpet"), voiced(key, chord, None, 3, 58)):
                            self.put("rhythm", player, bar_at + on, pulse * 0.8, pitch, self.hard(level, 0.85), tag=" stabs")

    # --- the bass ----------------------------------------------------------------------------
    def bass(self) -> None:
        ch, beats, pulse, starts = self.ch, self.beats, self.pulse, self.starts
        name = ch.basses[self.take % len(ch.basses)]
        inst = INSTRUMENTS[name]
        one, two = self.bass_way, self.bass_way_b
        drive = "eight" if ch.band and self.heavy else "pulse"
        # (2026-11-16, played: "not enough instruments in each track".) Where the music grows, the bass line is
        # doubled an octave away by its neighbour in the orchestra: from each theme's second statement, through the
        # second half of each rise, and at the moments (where a heavy piece's tutti has the low end, that is enough).
        partner = None if ch.band else PARTNERS.get(name)
        doubled = False

        def low(at: float, length: float, pitch: int, loud: float) -> None:
            if not self.breathing(at):                          # no new note in the breath before an arrival
                self.put("bass", name, at, length, pitch, loud)
                if doubled and partner:
                    self.put("bass", partner, at, length, pitch + (12 if INSTRUMENTS[partner].home > inst.home else -12), loud * 0.8,
                             tag=" doubled")
        for section, first, key, chords in self.spans:
            part, bars = section.part, section.bars
            for bar, chord in enumerate(chords):
                level, bar_at, along = self.level(section, bar), first + bar * beats, bar / bars
                doubled = (part in ("first", "second") and bar >= self.fam.period) or (part in ("build", "climb") and along >= 0.5) \
                    or (part in ("arrival", "summit") and not self.heavy)
                root = key.pitch(chord.root, inst.home - 5)
                loud = self.hard(level, 0.9)
                after = chords[bar + 1] if bar + 1 < bars else chord
                if part == "open":
                    if self.heavy or bar >= bars // 2:
                        self.put("bass", name, bar_at, beats, key.pitch(0, inst.home - 5), loud * 0.8)      # the key note, held
                    continue
                # One way of playing for the first theme and what is made of it, another for the
                # second; long notes where the story is quiet; and at the top of the climb the
                # root over and over, driving at the summit.
                way = {"first": one, "second": two, "build": one, "arrival": one, "valley": two if self.fight else "long",
                       "climb": two if along < 0.5 else drive, "summit": one, "close": "long"}[part]
                if way == "long":
                    low(bar_at, beats, root, loud)
                elif way == "two":
                    for index, on in enumerate(starts):
                        length = (starts[index + 1] if index + 1 < len(starts) else beats) - on
                        low(bar_at + on, length, root + (7 if index % 2 and bar % 2 else 0), loud * (1.0 if index == 0 else 0.85))
                elif way == "walk":
                    for index, on in enumerate(starts):
                        length = (starts[index + 1] if index + 1 < len(starts) else beats) - on
                        low(bar_at + on, length - (pulse if index == len(starts) - 1 else 0.0), root, loud)
                    # The last note of the bar leads to the next bar's root by a step of the scale.
                    toward = key.pitch(after.root, inst.home - 5)
                    lead_in = after.root + 4 if toward == root else after.root + (1 if toward < root else -1)
                    near = key.pitch(lead_in, inst.home - 5)
                    near += 12 if near < toward - 6 else -12 if near > toward + 6 else 0
                    low(bar_at + beats - pulse, pulse, near, loud * 0.8)
                elif way == "eight":
                    step = 0.5
                    for index in range(int(round(beats / step))):
                        on = index * step
                        low(bar_at + on, step * 0.85, root, loud * (1.0 if on in starts else 0.8))
                elif way == "pulse":
                    for index in range(int(round(beats / pulse))):
                        on = index * pulse
                        low(bar_at + on, pulse * 0.85, root, loud * (1.0 if on in starts else 0.8))
                else:
                    step = pulse if pulse == 1.0 else pulse * 1.0
                    for index in range(int(round(beats / step))):
                        low(bar_at + index * step, step * 0.8, root + (12 if index % 2 else 0), loud * (1.0 if index % 2 == 0 else 0.75))
                if part in ("arrival", "summit") and self.heavy and not ch.band:
                    # The low end at the big moments: the celli and the basses an octave apart,
                    # whichever of them has the bass line; and at the summit the low brass with
                    # them, where the palette has it: the tuba on the bass's note, the trombones
                    # an octave above. Nothing is left open between the bass and the chords.
                    weight = self.hard(level, 0.8)
                    upper = key.pitch(chord.root, INSTRUMENTS["celli"].home - 5)        # where the celli have the bass
                    lower = upper - 12                                                  # and the basses under them
                    if not name.startswith("celli"):
                        self.put("bass", "celli", bar_at, beats, upper, weight, tag=" tutti")
                    if not name.startswith("basses"):
                        self.put("bass", "basses", bar_at, beats, lower, weight, tag=" tutti")
                    if part == "summit":
                        if "tuba" in ch.basses + ch.under and name != "tuba":
                            self.put("bass", "tuba", bar_at, beats, lower, weight, tag=" tutti")
                        if "trombone" in ch.under + ch.leads:
                            self.put("bass", "trombone", bar_at, beats, upper, weight * 0.9, tag=" tutti")

    # --- the drums ---------------------------------------------------------------------------
    def strike(self, sound: str, at: float, loud: float, chord: Chord, key: Key) -> None:
        if sound == "ting" and self.forge:
            self.put("drums", "anvil", at, 0.5, 60, loud)        # in a forge the bright stroke is an anvil
        elif sound in KITS[self.ch.kit][1]:
            # A stroke of the kit. (The kit's "boom" is its bass drum; the deep stroke that marks
            # an arrival is an instrument of the same name, and is written by `marks`.)
            self.kit().add(at, 0.25, KITS[self.ch.kit][1][sound], loud)
        elif sound == "timpani":
            # A pair of kettledrums is tuned to the key note and the fourth below it. They play
            # whichever of the two is in the chord, and the chord's own root only where neither is.
            notes = {step % 7 for step in chord.steps}
            step = 0 if 0 in notes else -3 if 4 in notes else chord.root
            self.put("drums", sound, at, 0.5, key.pitch(step, INSTRUMENTS[sound].home), loud)
        else:
            inst = INSTRUMENTS[sound]
            self.put("drums", sound, at, 0.5, key.pitch(chord.root, inst.home), loud)

    def drums(self) -> None:
        ch, beats, fight = self.ch, self.beats, self.fight
        main, other = self.groove, self.groove_b
        # A second groove for the second theme; where the character has only one, the same
        # with its last layer left out.
        second = other["theme"] if other is not main else main["theme"][:max(len(main["theme"]) - 1, 1)]

        def lay(layers: list, bar: int, bar_at: float, level: float, scale: float, chord: Chord, key: Key) -> None:
            for layer in layers:
                sound, where, loud = layer[0], layer[1], layer[2]
                if len(layer) > 3 and bar % layer[3]:
                    continue
                if crowded and sound in LOW:
                    continue                                    # the big drums have the low end
                if crowded and sound == "timpani":
                    where, loud = "down", loud * 0.8            # ...and the kettledrums only mark the bar
                for on, weight in self.spots(where):
                    if self.breathing(bar_at + on):
                        continue                                # the breath before an arrival
                    self.strike(sound, bar_at + on, min(loud * weight * scale * (0.55 + 0.6 * level), 1.0), chord, key)

        for section, first, key, chords in self.spans:
            part, bars = section.part, section.bars
            for bar, chord in enumerate(chords):
                level, bar_at, along = self.level(section, bar), first + bar * beats, bar / bars
                # Where the big drums play, the orchestra's own low drums leave the low end to
                # them and the kettledrums are played down. (A band keeps its kit as it is.)
                crowded = not ch.band and self.big(part, along)[0] is not None
                if part == "open":
                    if ch.band and not fight and bar == bars - 1 and ch.kit in ("rock", "room"):
                        for on, weight in self.spots("pulses"):          # the sticks count the band in
                            self.strike("hat", bar_at + on, 0.5 * weight, chord, key)
                    if fight:
                        if bar == 0:
                            for sound in ("crash", "great drum" if "great drum" in ch.drums else "boom"):
                                if not (crowded and sound in LOW):
                                    self.strike(sound, bar_at, 0.85, chord, key)
                        elif bar >= 1:
                            lay(main["theme"], bar, bar_at, level, 0.8, chord, key)
                elif part == "first":
                    lay(main["theme"], bar, bar_at, level, 1.0, chord, key)
                    if bar >= self.fam.period and not (ch.band and self.heavy):
                        # The second time round a theme, the moment's small percussion joins softly (2026-11-16,
                        # played: "not enough instruments in each track").
                        lay([each for each in main["moment"] if each[0] in SMALL and each not in main["theme"]], bar, bar_at, level, 0.55, chord, key)
                elif part == "second":
                    lay(second, bar, bar_at, level, 1.0 if other is not main else 0.85, chord, key)
                    if bar >= self.fam.period and not (ch.band and self.heavy):
                        lay([each for each in other["moment"] if each[0] in SMALL and each not in second], bar, bar_at, level, 0.55, chord, key)
                elif part in ("build", "climb"):
                    # A rise begins on a theme's groove (the climb on the second theme's) and
                    # goes over to the moment's; its last bars are a roll, longer before the summit.
                    turn = 0.5 if part == "build" else 0.6
                    early = second if part == "climb" else main["theme"]
                    lay(early if along < turn else main["moment"], bar, bar_at, level, 1.0 if along < turn else 0.7, chord, key)
                    roll = main["roll"]
                    length = min((2 if self.heavy else 1) * (2 if part == "climb" else 1), bars)
                    if self.has_war and not ch.band and roll in LOW + ("timpani",):
                        roll = None                              # the big drums roll into the arrival themselves
                    if roll and bar >= bars - length:
                        step = 0.25
                        count = int(round(beats / step))
                        for index in range(count):
                            done = ((bar - (bars - length)) * count + index) / (length * count)
                            self.strike(roll, bar_at + index * step, (0.2 + 0.7 * done) * (0.6 + 0.4 * ch.weight), chord, key)
                elif part in ("arrival", "summit"):
                    big = part == "summit"
                    lay(main["moment"], bar, bar_at, level, 1.0 if big else 0.85, chord, key)
                    if bar == 0 and main["hit"]:
                        self.strike(main["hit"], bar_at, (0.6 + 0.35 * ch.weight) * (1.0 if big else 0.85), chord, key)
                        if self.heavy:
                            for sound in ch.drums[:2 if big else 1]:
                                if not (crowded and sound in LOW):
                                    self.strike(sound, bar_at, 0.9 if big else 0.75, chord, key)
                    if bar % 8 == 7 and main["roll"] and bars - bar > 1 and not (crowded and main["roll"] in LOW):
                        for index in range(4):                       # a fill into the next time round
                            self.strike(main["roll"], bar_at + beats - (4 - index) * 0.25, 0.45 + 0.12 * index, chord, key)
                elif part == "valley":
                    if fight and ch.band:
                        lay(main["theme"], bar, bar_at, level, 0.65, chord, key)       # a band's fight keeps its pulse through the valley
                else:
                    if along < 0.5 and bar % 2 == 0:
                        lay(main["theme"], bar, bar_at, level, 0.7, chord, key)
                    if bar == bars - 2 and main["hit"] and self.heavy:
                        self.strike("timpani" if "timpani" in ch.drums else "ting", bar_at, 0.45, chord, key)

    # --- the big drums -----------------------------------------------------------------------
    def big(self, part: str, along: float) -> tuple[str | None, float]:
        """What the war drums play in a bar, and how strongly, by the part of the story and how
        far through it the bar is. "low" is the low drum on the strong beats and its pickup
        into the bar line; "full" the whole ostinato; "top" the ostinato with every drum
        together on the bar; "single" one low stroke to the bar; None, nothing.

        A fight has them nearly all the way: low as it opens and under the second theme, the
        whole ostinato under the first, one stroke to the bar in the valley. Heavy music for
        walking has them from part of the way up each rise to the moment it comes to. In a
        rise they come in low, go over to the whole ostinato, and are struck harder as it
        goes. In the close they fall away. A band, which has a kit, has them only in its rises
        (and, in a fight, as it opens and in the valley)."""
        ch, fight = self.ch, self.fight
        if not self.has_war:
            return None, 0.0
        if part in ("build", "climb"):
            if ch.band:
                enter, whole = (0.2, 0.6) if fight else (0.4, 0.7)
            elif fight:
                enter, whole = (0.0, 0.35) if part == "build" else (0.15, 0.5)
            else:
                enter, whole = (0.3, 0.65) if part == "build" else (0.3, 0.6)
            if along < enter:
                return None, 0.0
            return ("low" if along < whole else "full"), 0.55 + 0.45 * along
        if ch.band:
            return {"open": ("low", 0.6), "valley": ("single", 0.5)}.get(part, (None, 0.0)) if fight else (None, 0.0)
        if part == "arrival":
            return "top", 0.9 if fight else 0.85
        if part == "summit":
            return "top", 1.0
        if part == "close":
            end = 0.75 if fight else 0.5
            return ("low", 0.7 * (1.0 - along / end)) if along < end else (None, 0.0)
        if not fight:
            return None, 0.0
        return {"open": ("low", 0.7), "first": ("full", 0.75), "second": ("low", 0.6), "valley": ("single", 0.5)}[part]

    def hands(self, part: str, along: float, bar: int) -> tuple[str | None, float]:
        """What the frame drums play in a bar, and how strongly: "all" (their whole pattern),
        "answer" (only its high strokes, in every second bar, between the war drums'), or
        nothing. Where the war drums play, the frame drums have the quieter drive: under the
        second theme (in a fight, or in a piece of the desert, the jungle or the highlands),
        as each rise begins, in a fight's valley, and answering at the first arrival. A lighter
        piece of those places has them instead of war drums, from its second theme on."""
        if not self.has_frames:
            return None, 0.0
        if not self.has_war:
            return {"second": ("all", 0.5), "build": ("all", 0.5 + 0.3 * along), "arrival": ("all", 0.8),
                    "climb": ("all", 0.5 + 0.35 * along), "summit": ("all", 0.9)}.get(part, (None, 0.0))
        if part in ("build", "climb"):
            return ("all", 0.5 + 0.3 * along) if along < 0.45 else (None, 0.0)
        if part == "arrival":
            return ("answer", 0.6) if bar % 2 else (None, 0.0)
        if part == "second":
            return ("all", 0.55) if self.fight or self.hand else (None, 0.0)
        if part == "valley":
            return ("all", 0.45) if self.fight else (None, 0.0)
        return None, 0.0

    def war_cycle(self) -> tuple[list[list[tuple[float, int, float]]], list[tuple[float, int, float]]]:
        """An ostinato for the war drums, of this take's own: two bars or four, and for each
        bar its strokes (where in the bar, which drum, how strong). The biggest drum is on
        the bar and the next biggest on the bar's other strong beats; a smaller drum has the
        pickup into each strong beat (always into the bar line). Between them runs what
        drives it, softly, on the smaller drums: every eighth, or two quick strokes before
        each beat, or (in slower, sparer music) only a stroke off the beat here and there. The
        metre's own groups are the strong beats.

        With the cycle comes its last bar once more, ending in a run down the drums from the
        smallest into the first beat of the bar after: that is played in every fourth bar."""
        rng, beats, pulse, starts = self.rng, self.beats, self.pulse, self.starts
        busy = self.ch.busy
        pickup = rng.choice((((-0.5, 0.6),), ((-0.5, 0.5), (-0.25, 0.7)), ((-0.25, 0.65),)))
        length = rng.choice((2, 2, 4))
        drive = rng.choice(("eighths", "gallop", "gallop") if self.fight else ("sparse", "eighths", "gallop") if busy >= 0.5
                           else ("sparse", "sparse", "eighths"))
        if pulse != 1.0 and drive == "gallop":
            drive = "eighths"                                   # in six-eight and the odd metres the eighths are the gallop
        pulses = [index * pulse for index in range(int(round(beats / pulse)))]
        cycle = []
        for bar in range(length):
            strokes = []
            for index, start in enumerate(starts):
                if index and bar % 2 == 0 and rng.random() < 0.2:
                    continue                                    # a strong beat left open now and then: air
                strokes.append((start, 36 if index == 0 else 38, 1.0 if index == 0 else 0.85))
            for edge in starts[1:] + [beats]:
                if edge == beats or rng.random() < 0.6:
                    strokes += [(edge + off, 41, loud) for off, loud in pickup]

            def free(on: float) -> bool:
                return not any(abs(on - at) < 1e-6 for at, _, _ in strokes)

            if drive == "eighths":
                strokes += [(on, 43 if on in pulses else 41, 0.4) for on in (index * 0.5 for index in range(int(round(beats / 0.5)))) if free(on)]
            elif drive == "gallop":
                for beat in pulses[1:] + [beats]:
                    strokes += [(beat + off, 41, loud) for off, loud in ((-0.5, 0.38), (-0.25, 0.48)) if free(beat + off)]
            else:
                strokes += [(on, 43, 0.5) for on in pulses if on not in starts and rng.random() < 0.2 + 0.4 * busy and free(on)]
            cycle.append(sorted(strokes))
        # The run down: eighths over the bar's last group (the last two beats of a bar that has one group).
        first = starts[-1] if len(starts) > 1 else beats - 2.0
        count = int(round((beats - first) / 0.5))
        run = [stroke for stroke in cycle[-1] if stroke[0] <= first + 1e-6] \
            + [(first + index * 0.5, (47, 45, 43, 41)[(index - 1) % 4], 0.55 + 0.25 * index / count) for index in range(1, count)]
        return cycle, sorted(run)

    def frame_cycle(self) -> list[list[tuple[float, int, float]]]:
        """Two bars for the frame drums, of this take's own: the low stroke on the strong
        beats, the high one on some of the beats between, and quiet strokes in the gaps."""
        rng, beats, pulse, starts = self.rng, self.beats, self.pulse, self.starts
        busy = self.ch.busy
        cycle = []
        for _ in range(2):
            strokes = []
            for index in range(int(round(beats / pulse))):
                on = index * pulse
                if on in starts:
                    strokes.append((on, 45 if on == 0 else 47, 0.9 if on == 0 else 0.75))
                elif rng.random() < 0.45 + 0.4 * busy:
                    strokes.append((on, 55 if rng.random() < 0.7 else 57, 0.55))
                if rng.random() < 0.15 + 0.35 * busy:
                    strokes.append((on + pulse / 2, 52 if rng.random() < 0.6 else 50, 0.38))
            cycle.append(sorted(strokes))
        return cycle

    def war_drums(self) -> None:
        """The war drums and the frame drums (see `big` and `hands` for where each plays)."""
        ch, beats = self.ch, self.beats
        if not (self.has_war or self.has_frames):
            return
        war, run = self.war_cycle() if self.has_war else ([], [])
        frames = self.frame_cycle() if self.has_frames else []
        bar_s = beats * 60.0 / self.fam.bpm
        for section, first, _, chords in self.spans:
            part, bars = section.part, section.bars
            # A rise ends in a roll: quick strokes on two drums, struck harder and harder, over
            # the last bar or two and through the breath, right up to the arrival. Sixteenths
            # where the music moves fast enough for those to be a roll; where it is slower,
            # six or eight to the beat, so that a roll is never under seven strokes a second.
            rolled = min(2 if part == "climb" or bar_s < 2.0 else 1, bars) if self.has_war and part in ("build", "climb") else 0
            quick = next((step for step in (0.25, 1.0 / 6.0) if step * 60.0 / self.fam.bpm <= 1.0 / 7.0 + 1e-9), 0.125)
            for bar in range(bars):
                level, bar_at, along = self.level(section, bar), first + bar * beats, bar / bars
                way, strength = self.hands(part, along, bar)
                if way and bar < bars - rolled:
                    for on, drum, weight in frames[bar % len(frames)]:
                        if (way == "all" or drum >= 50) and not self.breathing(bar_at + on):
                            self.put("drums", "frame drums", bar_at + on, 0.25, drum, min(weight * strength * (0.6 + 0.5 * level), 1.0))
                mode, strength = self.big(part, along)
                if bar >= bars - rolled:
                    count = int(round(beats / quick))
                    for index in range(count):
                        done = ((bar - (bars - rolled)) * count + index) / (rolled * count)
                        self.put("drums", "war drums", bar_at + index * quick, quick, 38 if index % 2 == 0 else 41,
                                 min((0.3 + 0.7 * done) * (0.7 + 0.3 * ch.weight), 1.0))
                    continue
                if mode is None:
                    continue
                if self.fight and not ch.band and part == "open" and bar == 0:
                    strokes = [(0.0, 36, 1.0), (0.0, 41, 0.9), (0.0, 45, 0.8)]            # a fight begins with every drum at once
                elif mode == "single":
                    strokes = [(0.0, 36, 0.9)]
                else:
                    strokes = run if bar % 4 == 3 else war[bar % len(war)]
                    if mode == "low":
                        strokes = [stroke for stroke in strokes if stroke[1] <= 38 or (stroke[1] == 41 and stroke[0] >= beats - 0.5 - 1e-6)]
                    elif mode == "top" and (part == "summit" or bar % 2 == 0):
                        strokes = strokes + [(0.0, 43, 0.8), (0.0, 47, 0.7)]             # every drum together on the bar, with the orchestra
                for on, drum, weight in strokes:
                    self.put("drums", "war drums", bar_at + on, 0.25, drum, min(weight * strength * (0.62 + 0.45 * level), 1.0))

    def marks(self) -> None:
        """What marks an arrival. A cymbal swells into it: one note that ends on the arrival's
        first beat and begins some seconds before, longer and louder before the summit than
        before the first arrival, and in the biggest pieces a short one into the second theme
        as well. A deep stroke lands on the first beat of the arrival and of the summit, and
        again, less hard, each time the theme comes round in them. The heaviest orchestral
        pieces have a gong at the summit (and the very heaviest a second, where the theme
        comes round for the last time). And music of the fire that has no forge of its own
        has an anvil struck on the second strong beat, every fourth bar of the arrival and
        every second bar of the summit."""
        ch, beats, period = self.ch, self.beats, self.fam.period
        beat_s = 60.0 / self.fam.bpm
        for index, (section, first, _, _) in enumerate(self.spans):
            part, bars = section.part, section.bars
            if self.has_swell and (part in ("arrival", "summit") or (part == "second" and ch.weight >= 0.95 and not ch.band)):
                seconds = {"arrival": 2.5 + 2.0 * ch.weight, "summit": 4.0 + 3.0 * ch.weight, "second": 2.5}[part]
                length = min(min(max(seconds, 2.0), 8.0) / beat_s, self.spans[index - 1][0].bars * beats)
                loud = {"arrival": 0.5 + 0.3 * ch.weight, "summit": 0.65 + 0.35 * ch.weight, "second": 0.45}[part]
                self.voice("drums", "swell").add(first - length, length, 49, loud)
            if part not in ("arrival", "summit"):
                continue
            summit = part == "summit"
            rounds = [bar for bar in range(0, bars, period) if bars - bar >= period]          # where the theme comes round
            if self.has_war:
                for bar in rounds:
                    self.put("drums", "boom", first + bar * beats, 1.0, 36, (1.0 if summit else 0.85) if bar == 0 else (0.75 if summit else 0.65))
            if self.has_gong and summit:
                self.put("drums", "gong", first, 2.0, 48, 0.85)
                if ch.weight >= 1.0 and len(rounds) > 1:
                    self.put("drums", "gong", first + rounds[-1] * beats, 2.0, 48, 0.7)
            if self.embers:
                on = self.starts[1] if len(self.starts) > 1 else beats / 2
                for bar in range(0, bars, 2 if summit else 4):
                    self.put("drums", "anvil", first + bar * beats + on, 0.5, 60, 0.75 if summit else 0.6)
