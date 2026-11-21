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
breath (a band's fight breaks down in it: the riff stops, the clean guitar sings, and the band
comes back in before the climb); a night piece keeps the whole arc under its breath.

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
import statistics
from dataclasses import dataclass, field

from .score import Note, Voice
from .theory import MODES, Chord, Key, Line, tones, voiced

# ---------------------------------------------------------------------------------------------
# The instruments the writers name, and where each one sounds well (what plays each: sounds.py)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Instrument:
    low: int
    high: int
    home: int                  # the middle of where its tunes sit
    held: bool = True          # it sustains for as long as the note is written (a bow, a breath); a plucked one does not
    level: float = 1.0         # a taste: this one a little under (or over) the others whatever it measures (the desk's taste)
    early: float = 0.0         # seconds it is played ahead, for instruments that speak slowly
    wired: bool = False        # an electric guitar: a twin tune a third above is written for it in a band


I = Instrument
INSTRUMENTS = {
    "flute": I(60, 96, 79), "piccolo": I(74, 103, 90, level=0.8), "oboe": I(58, 89, 72),
    "english horn": I(52, 81, 65), "clarinet": I(50, 89, 67), "bassoon": I(34, 70, 50),
    "recorder": I(60, 93, 77), "pan flute": I(60, 93, 76), "shakuhachi": I(55, 86, 70),
    "whistle": I(72, 98, 84, level=0.8), "ocarina": I(60, 91, 76),
    "trumpet": I(55, 82, 70), "trombone": I(40, 70, 55), "tuba": I(28, 55, 40),
    "horns": I(41, 74, 58), "brass": I(48, 82, 62, level=0.9),
    "violin": I(55, 96, 74), "viola": I(48, 84, 62), "cello": I(36, 74, 52),
    "violins": I(55, 96, 74, early=0.02), "violins slow": I(55, 96, 74, early=0.08),
    "violas": I(48, 84, 62, early=0.02), "celli": I(36, 72, 50, early=0.02),
    "celli slow": I(36, 72, 50, early=0.08), "basses": I(28, 52, 38, early=0.03),
    "basses slow": I(28, 52, 38, early=0.08),
    "strings": I(36, 96, 64, early=0.02), "strings slow": I(36, 96, 64, early=0.08),
    "tremolo": I(36, 96, 64, early=0.03), "pizzicato": I(36, 91, 62, held=False),
    "celli pizz": I(36, 72, 50, held=False), "basses pizz": I(28, 52, 38, held=False),
    "harp": I(31, 96, 64, held=False), "celesta": I(60, 105, 84, held=False),
    "glock": I(72, 105, 88, held=False, level=0.7), "music box": I(60, 96, 79, held=False),
    "vibes": I(53, 89, 70, held=False), "marimba": I(45, 96, 65, held=False),
    "xylophone": I(65, 105, 84, held=False, level=0.8), "bells": I(55, 84, 69, held=False),
    "church bell": I(48, 72, 60, held=False), "dulcimer": I(55, 91, 70, held=False),
    "organ": I(36, 91, 60, level=0.8), "harpsichord": I(36, 89, 65, held=False),
    "accordion": I(53, 89, 69, level=0.8), "guitar": I(40, 84, 60, held=False),
    "steel guitar": I(40, 84, 62, held=False), "mandolin": I(55, 91, 72, held=False),
    "twelve string": I(40, 84, 62, held=False), "sitar": I(48, 84, 64, held=False),
    "koto": I(48, 91, 67, held=False), "kalimba": I(60, 96, 76, held=False),
    # (The pipe drone, the english horn that holds a pad's drone, down to its own lowest E3, 2026-11-18: from B-flat 3, the
    # old bagpipe's range, a valley's drone written on A2 and E3 was pushed up to A4 and E4 and held there twenty-four bars,
    # a reed whining over a soft guitar at -35 against the tune's -44, "sometimes when one synth stays in when youre
    # sitting its whiny". Its home note, which casts who sings what, is as it was.)
    "banjo": I(48, 84, 64, held=False), "bagpipe": I(61, 83, 72, level=0.7), "pipe drone": I(52, 82, 70, level=0.7),
    "fiddle": I(55, 96, 74), "shenai": I(58, 86, 70, level=0.8),
    "choir": I(48, 81, 64, early=0.05), "oohs": I(48, 84, 65, early=0.05),
    "timpani": I(36, 57, 45, held=False), "taiko": I(36, 60, 45, held=False),
    "great drum": I(36, 60, 43, held=False), "melodic tom": I(36, 72, 48, held=False),
    "acoustic bass": I(28, 60, 40, held=False),
    # The band: Muse Guitars' electric guitars (heavy, lead and clean), its bass, an organ.
    "rhythm guitar": I(40, 76, 50, held=False, wired=True), "muted guitar": I(40, 72, 47, held=False, wired=True),
    "single guitar": I(40, 76, 50, held=False, wired=True),     # one of the two riff guitars, alone: a heavy band's opening riff
    "lead guitar": I(52, 86, 67, wired=True), "picked bass": I(28, 55, 38, held=False),
    "rock organ": I(36, 84, 60, level=0.8), "harmonica": I(60, 84, 72),
    "fretless": I(28, 60, 40),
    # Colours added for variety (2026-11-16, played: "need more variety in warcraft"). Muse Sounds plays all of these.
    "piano": I(33, 100, 64, held=False), "bass flute": I(48, 84, 62), "bass clarinet": I(38, 77, 55),
    # (Handbells carry far more than the glockenspiel at the same written strength: at 0.85 a frost night's rise, its
    # tune on handbells, came out louder than its moment on the glockenspiel, 2026-11-17, night.)
    "handbells": I(60, 93, 74, held=False, level=0.6),
    # (Muse's euphonium under C3 was found to sound an octave up and 18 dB soft, played alone: it is kept above it.)
    "euphonium": I(48, 72, 58),
    # The rest of what Muse Sounds has (2026-11-17, night: "revisit it see if you left good ones out"), each heard played
    # alone first: the two low winds at the written pitch, every note.
    "contrabassoon": I(22, 50, 34, level=1.6), "contrabass flute": I(36, 62, 48, level=1.6),
    "eb clarinet": I(62, 91, 76), "full choir": I(43, 81, 62, early=0.05),
    "handchimes": I(60, 96, 74, held=False), "dream piano": I(36, 96, 64, held=False),
    # The big drums and what marks an arrival, found by name alone. A war drum's or a frame
    # drum's pitch is its size: 36 is the
    # biggest war drum, 45 the lowest frame drum. The others have one note each.
    "war drums": I(36, 47, 41, held=False), "frame drums": I(45, 57, 50, held=False),
    "boom": I(36, 36, 36, held=False), "gong": I(48, 48, 48, held=False),
    "swell": I(49, 49, 49, held=False), "anvil": I(60, 60, 60, held=False),
    # Played by Muse Percussion on drum staves (studio.muse.PERCUSSION): the pitch is the drum. The level is what each
    # needed beside the rest, measured played alone at one strength (2026-11-17, night): the taikos are by far the loudest.
    "taikos": I(86, 87, 87, held=False, level=0.4), "tam-tam": I(52, 52, 52, held=False, level=1.2),
    # (The mark tree was at 2.0 at first: a night piece's drums, nearly all mark tree, came out 14 dB bright.)
    "mark tree": I(84, 84, 84, held=False, level=1.0), "field drum": I(37, 38, 38, held=False),
    "field drum roll": I(38, 38, 38, held=False, level=1.3), "cymbal roll": I(57, 57, 57, held=False, level=1.5),
    "piatti": I(57, 57, 57, held=False, level=0.5), "concert drum roll": I(36, 36, 36, held=False, level=1.3),
}

# Percussion: a kit's strokes by name, as the note each is written on.
_STROKES = {"shake": 82, "jingle": 83, "castanet": 85, "tick": 75, "high": 60, "low": 61, "deep": 87, "mute": 86,
            "conga": 63, "conga low": 64, "block": 76, "block low": 77, "guiro": 73, "bell": 53,
            "hat": 42, "hat open": 46, "ride": 51, "tom": 45, "tom low": 41, "tom high": 48, "cowbell": 56}
KITS = {
    "orchestra": dict(_STROKES, boom=36, snare=38, crash=59, crash2=57, tamb=54, ting=81, clack=39),
    "march": dict(_STROKES, boom=36, snare=40, crash=57, crash2=59, tamb=54, ting=81, clack=37),
    "folk": dict(_STROKES, boom=36, snare=37, crash=55, crash2=49, tamb=54, ting=81, clack=39),
    "hands": dict(_STROKES, boom=64, snare=63, crash=55, crash2=49, tamb=54, ting=80, clack=62, shake=70, jingle=69),
    "wood": dict(_STROKES, boom=87, snare=77, crash=55, crash2=49, tamb=69, ting=76, clack=75),
    "rock": dict(_STROKES, boom=36, snare=38, crash=49, crash2=57, tamb=54, ting=81, clack=37),
    "room": dict(_STROKES, boom=36, snare=38, crash=49, crash2=57, tamb=54, ting=81, clack=37),
}


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
KINDS_ALL = ("pastoral", "highland", "haunted", "desert", "jungle", "infernal", "regal", "mystic", "marsh", "coast", "frozen")
CHARACTERS = (
    # --- pastoral ---------------------------------------------------------------------------
    C("village dance", ("pastoral",), light=True, modes=("major", "mixolydian"), bpm=(150, 168), metres=("6/8",), busy=0.75,
      weight=0.6, leads=("fiddle", "whistle", "eb clarinet"), strong=("fiddle", "flute"), under=("clarinet",),
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
      pads=("pipe drone", "strings"), pad_ways=("drone",), plucks=("steel guitar", "mandolin"), figures=("strum", "pulse"),
      basses=("acoustic bass", "celli pizz"), kit="march", drums=(), grooves=("reel", "march"), hall=(1.5, 0.17), lift=0.2,
      titles=(("Heather", "Cairn", "Tarn", "Piper's", "Snowmelt", "Shepherd's", "Windy", "Stag"),
              ("Reel", "Strathspey", "Jig", "Step", "Fling"))),
    C("snowfall", ("highland", "frozen"), light=True, modes=("major", "lydian", "dorian"), bpm=(66, 80), metres=("3/4", "4/4"), busy=0.35,
      weight=0.55, leads=("flute", "celesta", "clarinet"), strong=("violins slow", "flute"), under=("horns",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "celesta", "glock"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("sleigh", "sparkle"), hall=(2.8, 0.3), lift=0.2,
      titles=(("First", "Quiet", "Falling", "White", "Still", "Lantern"), ("Snow", "Frost", "Drifts", "Pines", "Hearth", "Morning"))),
    C("mountain pass", ("highland", "frozen"), modes=("dorian", "minor", "mixolydian"), bpm=(76, 92), busy=0.45, weight=1.0,
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
    C("river spirits", ("jungle", "marsh"), light=True, modes=("dorian", "lydian"), bpm=(70, 84), busy=0.4, weight=0.5,
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
    C("swamp fever", ("jungle", "haunted", "marsh"), modes=("minor", "dorian"), bpm=(76, 90), busy=0.45, weight=0.8,
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
      under=("celli",), pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "dream piano", "celesta"), figures=("arp", "rock"),
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
    C("hearth", ("haunted", "mystic", "jungle", "infernal", "desert", "marsh", "frozen"), role="ember", light=True, modes=("dorian", "major"), bpm=(66, 80),
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
      pad_ways=("pad", "arp"), plucks=("vibes", "harp", "kalimba"), figures=("arp", "toll"), basses=("celli slow", "contrabass flute"), kit="wood",
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
    C("warband", ("desert", "jungle", "infernal", "coast"), role="battle", serves=(2,), modes=("phrygian", "minor", "phrygian dominant"),
      bpm=(132, 148), metres=("4/4", "6/8"), busy=0.6, weight=1.0, leads=("trombone", "shenai", "horns"), strong=("brass", "violins"),
      under=("trombone", "tuba"), pads=("tremolo",), pad_ways=("tremolo", "drone"), plucks=("strings", "marimba"),
      figures=("hammer", "gallop"), basses=("basses", "tuba"), kit="hands", drums=("taiko", "timpani"), grooves=("war drums",),
      lift=0.4,
      titles=(("Blood", "War", "Spear", "Tusk", "Red", "Raider's"), ("Drums", "Band", "Charge", "Fury", "Howl", "Tide"))),
    C("unquiet dead", ("haunted", "frozen"), role="battle", serves=(2,), modes=("minor",), bpm=(136, 150), metres=("6/8", "4/4"), busy=0.6,
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
    C("sea shanty", ("pastoral", "mystic", "coast"), light=True, modes=("major", "mixolydian", "dorian"), bpm=(132, 150), metres=("6/8",),
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
    C("dwarven hall", ("highland", "regal", "frozen"), modes=("dorian", "mixolydian", "minor"), bpm=(92, 108), metres=("3/4", "4/4"), busy=0.5,
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
    C("frost giant", ("highland", "frozen"), modes=("minor", "phrygian"), bpm=(60, 72), busy=0.3, weight=1.0,
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
    C("drowned bell", ("mystic", "haunted", "marsh", "coast"), modes=("minor", "dorian"), bpm=(60, 72), metres=("3/4", "4/4"), busy=0.3, weight=0.85,
      leads=("oohs", "cello", "english horn"), strong=("choir", "violins slow"), under=("horns",), pads=("strings slow", "oohs"),
      pad_ways=("pad", "tremolo"), plucks=("church bell", "harp", "vibes"), figures=("toll", "arp"), basses=("basses slow",),
      kit="orchestra", drums=("great drum",), grooves=("drip", "dirge"), hall=(3.8, 0.4), lift=0.3,
      titles=(("Drowned", "Tidal", "Lost", "Sunken", "Mist", "Wrecker's"), ("Bell", "Shore", "Fleet", "Chapel", "Watch", "Lament"))),
    C("drinking song", ("highland", "regal", "pastoral", "frozen"), role="ember", light=True, modes=("major", "mixolydian"), bpm=(132, 150),
      metres=("3/4",), busy=0.6, weight=0.6, leads=("accordion", "fiddle", "clarinet"), strong=("accordion", "fiddle"),
      under=("bassoon",), pads=("accordion",), pad_ways=("pad",), plucks=("steel guitar", "banjo"), figures=("oompah",),
      basses=("acoustic bass", "tuba"), kit="folk", drums=(), grooves=("waltz", "claps"), hall=(1.1, 0.12), lift=0.25,
      titles=(("One More", "Brewer's", "Raised Mug", "Barmaid's", "Foaming"), ("Round", "Waltz", "Chorus", "Toast", "Sway"))),
    C("wild hunt", ("mystic", "jungle", "highland", "marsh"), role="battle", serves=(2,), modes=("dorian", "minor"), bpm=(140, 156),
      metres=("6/8",), busy=0.65, weight=1.0, leads=("horns", "violins", "oboe"), strong=("horns", "violins"),
      under=("trombone",), pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("strings", "xylophone"),
      figures=("gallop", "pulse"), basses=("celli", "basses"), kit="orchestra", drums=("timpani", "taiko"),
      grooves=("ride", "battle"), lift=0.45,
      titles=(("Wild", "Antlered", "Moonlit", "Baying", "Thorn"), ("Hunt", "Chase", "Pack", "Riders", "Horn"))),
    C("blizzard", ("highland", "mystic", "frozen"), role="storm", serves=(1, 2), modes=("minor", "dorian"), bpm=(118, 132), busy=0.55,
      weight=0.95, leads=("violins", "horns", "piccolo"), strong=("violins", "horns"), under=("trombone",), pads=("tremolo",),
      pad_ways=("tremolo",), plucks=("strings", "glock"), figures=("gallop", "arp"), basses=("celli", "basses"),
      kit="orchestra", drums=("timpani", "great drum"), grooves=("thunder", "sleigh"), lift=0.35,
      titles=(("White", "Blinding", "North", "Howling", "Driving"), ("Blizzard", "Squall", "Wall", "Gale", "Whiteout"))),
    # --- Knight Rock: a band, not an orchestra ------------------------------------------------------
    # Heavy riff guitars, a lead guitar (two of them in thirds at the moment), the
    # bass on the root in steady eighths, a plain hard-hitting kit, and under it a drone as of a
    # hurdy-gurdy. The light ones are the same band unplugged: strummed strings, fiddle and whistle.
    C("open road", ("pastoral", "highland", "coast"), light=True, style="knight", band=True, modes=("mixolydian", "major"), bpm=(112, 126),
      busy=0.65, weight=0.65, leads=("fiddle", "harmonica", "whistle"), strong=("fiddle", "whistle"), under=(),
      pads=("accordion", "rock organ"), pad_ways=("drone", "pad"), plucks=("steel guitar", "twelve string", "mandolin"),
      figures=("strum",), basses=("picked bass",), kit="rock", drums=(), grooves=("tavern rock", "rock"), hall=(1.2, 0.13),
      lift=0.3, titles=(("Open", "Sunny", "Wagon", "Milestone", "Free", "Homeward"), ("Road", "Miles", "Wheels", "Ramble", "Highway"))),
    C("banner ride", ("pastoral", "regal", "highland"), style="knight", band=True, modes=("mixolydian", "dorian"), bpm=(118, 132),
      busy=0.6, weight=0.95, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "pipe drone"),
      pad_ways=("drone",), plucks=("rhythm guitar",), figures=("riff",), basses=("picked bass",), kit="rock", drums=(),
      grooves=("rock", "rock ride"), hall=(1.3, 0.14), lift=0.4,
      titles=(("Banner", "Lionheart", "Steel", "Charger", "King's", "Shield"), ("Ride", "Knights", "Oath", "Thunder", "Vanguard"))),
    C("black chapel", ("haunted",), style="knight", band=True, modes=("minor", "phrygian"), bpm=(76, 88), busy=0.45, weight=1.0,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "organ"), pad_ways=("drone", "pad"),
      plucks=("rhythm guitar",), figures=("riff",), basses=("picked bass",), kit="rock", drums=("church bell",),
      grooves=("half rock",), hall=(2.2, 0.22), lift=0.3,
      titles=(("Black", "Grave", "Midnight", "Raven", "Witching", "Cursed"), ("Chapel", "Sabbath", "Bell", "Mass", "Riders", "Hour"))),
    C("lantern walk", ("haunted", "mystic", "marsh"), light=True, style="knight", band=True, modes=("minor", "dorian"), bpm=(84, 96), busy=0.5,
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
    C("jungle stomp", ("jungle", "marsh"), style="knight", band=True, modes=("minor", "dorian"), bpm=(100, 112), busy=0.55, weight=0.9,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "pan flute"), pad_ways=("drone",),
      plucks=("rhythm guitar",), figures=("riff", "chug"), basses=("picked bass",), kit="rock", drums=("taiko",),
      grooves=("tom rock",), hall=(1.4, 0.15), lift=0.3,
      titles=(("Jungle", "Tiger", "Vine", "Headhunter", "Gorilla", "Thunder Lizard"), ("Stomp", "Boogie", "Drums", "Crawl", "Fever"))),
    C("forge anthem", ("infernal", "regal"), style="knight", band=True, modes=("minor", "dorian"), bpm=(96, 108), busy=0.5, weight=1.0,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "pipe drone"), pad_ways=("drone", "pad"),
      plucks=("rhythm guitar",), figures=("riff", "hammer"), basses=("picked bass",), kit="rock", drums=(),
      grooves=("anvil rock",), hall=(1.6, 0.17), lift=0.4,
      titles=(("Forge", "Anvil", "Hammer", "Molten", "Ironclad", "Blacksmith's"), ("Anthem", "Thunder", "Law", "Fire", "Hymn"))),
    C("moon glade", ("mystic",), light=True, style="knight", band=True, modes=("lydian", "dorian"), bpm=(80, 92), busy=0.45, weight=0.5,
      leads=("whistle", "ocarina", "harmonica"), strong=("whistle", "fiddle"), under=(), pads=("strings slow", "oohs"),
      pad_ways=("pad",), plucks=("guitar", "twelve string", "harp"), figures=("arp",), basses=("picked bass", "fretless"),
      kit="room", drums=(), grooves=("brushes",), hall=(2.2, 0.24), lift=0.2,
      titles=(("Moon", "Silver", "Starlight", "Willow", "Dreaming", "Fae"), ("Glade", "Ballad", "Serenade", "Waters", "Lullaby"))),
    C("mountain stomp", ("highland", "frozen"), style="knight", band=True, modes=("dorian", "mixolydian"), bpm=(100, 110), busy=0.5, weight=0.95,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("pipe drone", "rock organ"), pad_ways=("drone",),
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
    C("witch hollow", ("haunted", "jungle", "marsh"), modes=("phrygian", "minor"), bpm=(96, 110), metres=("5/4", "7/8", "6/8"), busy=0.55, weight=0.8,
      leads=("bass clarinet", "oboe", "fiddle"), strong=("violins", "clarinet"), under=("bassoon",), pads=("tremolo", "oohs"),
      pad_ways=("tremolo", "drone"), plucks=("harpsichord", "pizzicato", "marimba"), figures=("pattern", "oompah"),
      basses=("basses pizz", "bassoon"), kit="wood", drums=(), grooves=("bones", "bog"), hall=(2.2, 0.24), lift=0.3,
      titles=(("Witch", "Hag's", "Toadstool", "Cauldron", "Black Cat", "Hex"), ("Hollow", "Brew", "Hut", "Circle", "Charm", "Ring"))),
    C("spirit grove", ("mystic", "pastoral"), light=True, modes=("lydian", "major"), bpm=(76, 88), metres=("3/4", "6/8"), busy=0.4, weight=0.5,
      leads=("pan flute", "handbells", "flute"), strong=("handbells", "violins slow"), under=("celli", "clarinet"), pads=("oohs", "strings slow"),
      pad_ways=("pad",), plucks=("handbells", "celesta", "harp"), figures=("arp", "pattern"), basses=("celli slow", "celli pizz"),
      kit="folk", drums=(), grooves=("sparkle", "waltz"), hall=(3.0, 0.32), lift=0.2,
      titles=(("Spirit", "Dawnpetal", "Feather", "Wishing", "Sunlit", "Bright"), ("Grove", "Bells", "Spring", "Clearing", "Ring", "Glade"))),
    C("barrow kings", ("highland", "haunted", "frozen"), modes=("minor", "dorian", "phrygian"), bpm=(60, 72), busy=0.3, weight=1.0,
      leads=("euphonium", "cello", "english horn"), strong=("brass", "choir"), under=("tuba", "trombone"), pads=("strings slow", "choir"),
      pad_ways=("drone", "pad"), plucks=("harp", "church bell"), figures=("toll", "arp"), basses=("basses slow", "tuba"), kit="orchestra",
      drums=("great drum", "timpani"), grooves=("dirge", "stately"), hall=(3.2, 0.34), lift=0.35,
      titles=(("Barrow", "Cairn", "Old King's", "Stone Crown", "Long Sleep", "Howe"), ("Kings", "Mound", "Tomb", "Vigil", "Rest", "Lords"))),
    C("cliffside wind", ("highland", "pastoral", "coast"), modes=("dorian", "mixolydian", "minor"), bpm=(108, 122), metres=("6/8",), busy=0.5, weight=0.9,
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
      pads=("strings slow", "strings"), pad_ways=("pad", "drone"), plucks=("harp", "steel guitar", "mandolin"), figures=("arp", "strum"),
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
      kit="folk", drums=(), grooves=("waltz",), hall=(2.6, 0.28), lift=0.35,
      titles=(("Sunset", "Amber", "Evening", "Long Shadow", "Homeward", "Golden"), ("Hills", "Vale", "Rise", "Glow", "Light", "Slope"))),
    C("lakeside reverie", ("pastoral", "mystic"), light=True, modes=("lydian", "major", "dorian"), bpm=(60, 72), metres=("4/4", "3/4"),
      busy=0.3, weight=0.5, leads=("piano", "flute", "cello"), strong=("violins slow", "flute"), under=("celli", "clarinet"),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "piano", "guitar"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("sparkle", "rain"), hall=(3.0, 0.32), lift=0.2,
      titles=(("Lakeside", "Still Water", "Reed", "Heron", "Mirror", "Lily Pad"), ("Reverie", "Dream", "Hour", "Mere", "Ripples", "Shallows"))),
    C("harvest home", ("pastoral",), light=True, modes=("major", "mixolydian"), bpm=(100, 112), metres=("3/4", "6/8"), busy=0.6, weight=0.65,
      leads=("violin", "eb clarinet", "whistle"), strong=("violins", "horns"), under=("celli", "bassoon"), pads=("strings",), pad_ways=("pad",),
      plucks=("harp", "guitar", "pizzicato"), figures=("arp", "oompah"), basses=("celli pizz", "basses pizz"), kit="folk", drums=("timpani",),
      grooves=("waltz", "jig"), hall=(2.0, 0.22), lift=0.45,
      titles=(("Harvest", "Sheaf", "Hayrick", "Lammas", "Gleaner's", "Bonfire"), ("Home", "Feast", "Supper", "Round", "Thanks", "Ring"))),
    # --- caves and inns: a cave had two pieces, one light and one heavy, so every light cave played the same one ----
    C("glowworm grotto", ("mystic", "jungle", "pastoral", "marsh"), role="depths", light=True, modes=("lydian", "dorian"), bpm=(60, 72),
      metres=("3/4", "4/4"), busy=0.3, weight=0.45, leads=("celesta", "bass flute", "vibes"), strong=("vibes", "oohs"), under=("celli",),
      pads=("oohs", "strings slow"), pad_ways=("pad",), plucks=("harp", "vibes", "celesta"), figures=("arp", "toll"),
      basses=("celli slow", "contrabass flute", "basses pizz"), kit="wood", drums=(), grooves=("drip",), hall=(4.0, 0.42), lift=0.0,
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
    C("fireside", ("pastoral", "highland", "regal", "frozen"), role="ember", light=True, modes=("major", "dorian", "mixolydian"), bpm=(76, 88),
      metres=("3/4", "6/8"), busy=0.45, weight=0.45, leads=("piano", "fiddle", "clarinet"), strong=("fiddle", "piano"), under=("cello",),
      pads=("strings slow", "accordion"), pad_ways=("pad",), plucks=("guitar", "harp"), figures=("arp", "rock"),
      basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("waltz", "tick"), hall=(1.2, 0.13), lift=0.0,
      titles=(("Fireside", "Crackling", "Snug", "Mulled", "Pipe Smoke", "Chimney"), ("Tune", "Corner", "Waltz", "Rest", "Evening", "Glow"))),
    # --- more caves, inns and bosses (2026-11-16, played: "more different cave and special encounter pieces like inns ---
    # --- and caves"): a cave of each kind of place, an inn of each, and bosses other than the titan. -------------------
    C("frozen cavern", ("highland", "mystic", "frozen"), role="depths", light=True, modes=("lydian", "dorian"), bpm=(56, 68), metres=("3/4", "4/4"),
      busy=0.3, weight=0.45, leads=("celesta", "flute", "handbells"), strong=("glock", "violins slow"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("celesta", "harp", "pizzicato"), figures=("arp", "toll"),
      basses=("celli slow", "basses pizz"), kit="wood", drums=(), grooves=("drip",), hall=(4.4, 0.46), lift=0.0,
      titles=(("Frozen", "Icebound", "Rime", "Glittering", "Blue Ice", "Hoarfrost"), ("Cavern", "Grotto", "Halls", "Vault", "Deep", "Hollow"))),
    C("spider den", ("haunted", "jungle", "marsh"), role="depths", modes=("phrygian", "minor"), bpm=(64, 76), metres=("4/4", "5/4"), busy=0.35,
      weight=0.7, leads=("bass clarinet", "viola", "bassoon"), strong=("violins", "horns"), under=("bassoon",), pads=("tremolo", "basses slow"),
      pad_ways=("tremolo", "drone"), plucks=("pizzicato", "harpsichord", "marimba"), figures=("pattern", "toll"),
      basses=("basses pizz", "bassoon"), kit="wood", drums=("great drum",), grooves=("drip", "bog"), hall=(3.6, 0.38), lift=0.0,
      titles=(("Silken", "Webbed", "Venom", "Brood", "Eight-Eyed", "Skittering"), ("Den", "Nest", "Lair", "Tunnels", "Burrow", "Hollow"))),
    C("lava tube", ("infernal", "desert"), role="depths", modes=("phrygian", "minor"), bpm=(66, 78), busy=0.3, weight=0.8,
      leads=("trombone", "bass clarinet", "english horn"), strong=("brass", "choir"), under=("tuba",), pads=("tremolo", "basses slow"),
      pad_ways=("drone", "tremolo"), plucks=("strings", "bells"), figures=("toll", "hammer"), basses=("basses slow", "tuba"),
      kit="orchestra", drums=("taiko", "great drum"), grooves=("drip", "anvil"), hall=(3.8, 0.4), lift=0.0,
      titles=(("Lava", "Smouldering", "Molten", "Sulphur", "Glowing", "Scorched"), ("Tube", "Vent", "Chasm", "Flow", "Throat", "Deep"))),
    C("sea grotto", ("pastoral", "mystic", "jungle", "coast"), role="depths", light=True, modes=("dorian", "lydian", "mixolydian"), bpm=(60, 72),
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
    C("lamplit inn", ("haunted", "regal", "marsh"), role="ember", light=True, modes=("minor", "dorian"), bpm=(66, 78), metres=("3/4", "4/4"),
      busy=0.4, weight=0.45, leads=("cello", "clarinet", "piano"), strong=("violin", "piano"), under=("cello",), pads=("strings slow", "organ"),
      pad_ways=("pad",), plucks=("piano", "harp", "celesta"), figures=("arp", "rock"), basses=("acoustic bass", "celli pizz"), kit="folk",
      drums=(), grooves=("tick", "waltz"), hall=(1.4, 0.15), lift=0.0,
      titles=(("Shuttered", "Raven's", "Candlewick", "Last Lamp", "Bolted Door", "Lamplit"), ("Inn", "Room", "Parlour", "Rest", "Waltz", "Vigil"))),
    C("harbour saloon", ("pastoral", "desert", "jungle", "coast"), role="ember", light=True, modes=("major", "mixolydian"), bpm=(104, 118),
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
    # --- the gaps in every kind of place, by setting and by light (2026-11-16, the night's loop: "make sure by tomorroow ---
    # --- morning we have granularity in locations on all the kinds"). Each fills a cell of kind x setting x light that ---
    # --- had nothing, or darkens a kind that had only bright music. ------------------------------------------------------
    C("frozen lake", ("highland", "mystic", "frozen"), light=True, modes=("lydian", "major", "dorian"), bpm=(66, 78), metres=("3/4",), busy=0.4,
      weight=0.5, leads=("celesta", "flute", "violin"), strong=("violins slow", "glock"), under=("celli",), pads=("strings slow", "oohs"),
      pad_ways=("pad",), plucks=("harp", "celesta", "pizzicato"), figures=("arp", "rock"), basses=("celli slow", "basses pizz"), kit="folk",
      drums=(), grooves=("sleigh", "sparkle"), hall=(3.0, 0.32), lift=0.25,
      titles=(("Frozen", "Moonlit", "Glass", "Still", "Skater's", "Silver"), ("Lake", "Mere", "Ice", "Waltz", "Shallows", "Tarn"))),
    C("snowbound pines", ("highland", "haunted", "frozen"), modes=("minor", "dorian"), bpm=(84, 96), metres=("6/8", "4/4"), busy=0.45, weight=0.85,
      leads=("horns", "english horn", "cello"), strong=("violins", "horns"), under=("trombone", "celli"), pads=("tremolo", "strings slow"),
      pad_ways=("tremolo", "pad"), plucks=("harp", "pizzicato"), figures=("arp", "gallop"), basses=("celli", "basses"), kit="march",
      drums=("timpani",), grooves=("ride", "dirge"), hall=(3.0, 0.32), lift=0.35,
      titles=(("Snowbound", "Wolf", "Black", "Deep", "Howling", "Hunter's"), ("Pines", "Forest", "Timber", "Woods", "Night", "Trail"))),
    C("misty lake", ("haunted", "mystic", "marsh"), light=True, modes=("dorian", "minor"), bpm=(60, 72), metres=("3/4", "4/4"), busy=0.3, weight=0.45,
      leads=("bass flute", "harp", "oohs"), strong=("oohs", "violins slow"), under=("celli",), pads=("strings slow", "oohs"), pad_ways=("pad",),
      plucks=("harp", "celesta", "vibes"), figures=("arp", "rock"), basses=("celli slow", "basses pizz"), kit="folk", drums=(),
      grooves=("drip", "sparkle"), hall=(3.4, 0.36), lift=0.15,
      titles=(("Misty", "Grey", "Veiled", "Drifting", "Pale", "Hushed"), ("Lake", "Water", "Shore", "Reeds", "Mere", "Fog"))),
    C("wisp wood", ("haunted", "pastoral"), light=True, modes=("dorian", "minor"), bpm=(80, 92), metres=("3/4", "6/8"), busy=0.45, weight=0.5,
      leads=("celesta", "clarinet", "viola"), strong=("violins slow", "celesta"), under=("bassoon",), pads=("strings slow", "oohs"),
      pad_ways=("pad",), plucks=("pizzicato", "harpsichord", "harp"), figures=("arp", "oompah"), basses=("celli pizz", "basses pizz"),
      kit="folk", drums=(), grooves=("tick", "sparkle"), hall=(2.8, 0.3), lift=0.2,
      titles=(("Wisp", "Lantern", "Glimmer", "Will-o'", "Faerie", "Twinkling"), ("Wood", "Path", "Lights", "Dance", "Thicket", "Ring"))),
    C("dark road", ("haunted", "pastoral"), modes=("minor", "phrygian"), bpm=(72, 84), busy=0.35, weight=0.85,
      leads=("bass clarinet", "english horn", "cello"), strong=("violins", "horns"), under=("trombone",), pads=("tremolo", "strings slow"),
      pad_ways=("tremolo", "drone"), plucks=("pizzicato", "church bell"), figures=("pulse", "toll"), basses=("basses", "celli"),
      kit="orchestra", drums=("timpani", "great drum"), grooves=("dirge", "march"), hall=(2.8, 0.3), lift=0.3,
      titles=(("Dark", "Gallows", "Crow's", "Old Corpse", "Lonely", "Wagon-Rut"), ("Road", "Way", "Mile", "Track", "Lane", "Crossing"))),
    C("buried tomb", ("desert", "haunted"), modes=("phrygian dominant", "phrygian"), bpm=(60, 72), busy=0.3, weight=0.9,
      leads=("shenai", "choir", "english horn"), strong=("choir", "brass"), under=("trombone", "tuba"), pads=("tremolo", "choir"),
      pad_ways=("drone", "tremolo"), plucks=("dulcimer", "harp", "bells"), figures=("toll", "pulse"), basses=("basses slow", "tuba"),
      kit="hands", drums=("great drum", "taiko"), grooves=("heat", "war camp"), hall=(3.6, 0.38), lift=0.3,
      titles=(("Buried", "Sand-Choked", "Pharaoh's", "Sealed", "Scarab", "Sunken"), ("Tomb", "Kings", "Necropolis", "Dynasty", "Vault", "Sphinx"))),
    C("desert shrine", ("desert", "mystic"), light=True, modes=("dorian", "phrygian dominant", "lydian"), bpm=(66, 78), busy=0.35, weight=0.5,
      leads=("pan flute", "guitar", "handbells"), strong=("pan flute", "violins slow"), under=("cello",), pads=("strings slow", "oohs"),
      pad_ways=("drone", "pad"), plucks=("guitar", "dulcimer", "handbells"), figures=("arp", "pattern"), basses=("fretless", "celli pizz"),
      kit="hands", drums=(), grooves=("heat", "sparkle"), hall=(3.0, 0.32), lift=0.2,
      titles=(("Sun", "Moon", "Pilgrim's", "Lamp", "Wind", "Star"), ("Shrine", "Altar", "Prayer", "Pillar", "Well", "Stone"))),
    C("jungle cliffs", ("jungle", "highland"), modes=("dorian", "minor"), bpm=(96, 108), metres=("6/8", "4/4"), busy=0.5, weight=0.9,
      leads=("horns", "pan flute", "violin"), strong=("violins", "horns"), under=("trombone",), pads=("strings", "tremolo"), pad_ways=("pad", "tremolo"),
      plucks=("marimba", "harp", "strings"), figures=("pattern", "gallop"), basses=("celli", "basses"), kit="wood", drums=("taiko", "timpani"),
      grooves=("hunt", "canopy"), hall=(2.6, 0.28), lift=0.45,
      titles=(("Vine", "Mist", "Eagle", "Waterfall", "Sky", "Jaguar"), ("Cliffs", "Heights", "Crag", "Ledge", "Ridge", "Falls"))),
    C("jungle camp", ("jungle", "pastoral"), light=True, modes=("mixolydian", "major", "dorian"), bpm=(100, 112), metres=("4/4", "6/8"), busy=0.65,
      weight=0.55, leads=("kalimba", "flute", "marimba"), strong=("marimba", "flute"), under=("clarinet",), pads=("strings", "oohs"), pad_ways=("pad",),
      plucks=("kalimba", "guitar", "marimba"), figures=("pattern", "strum"), basses=("acoustic bass", "fretless"), kit="wood", drums=(),
      grooves=("canopy", "claps"), hall=(1.8, 0.2), lift=0.2,
      titles=(("Expedition", "Explorer's", "Bamboo", "Hammock", "Riverboat", "Base"), ("Camp", "Outpost", "Landing", "Stockade", "Post", "Clearing"))),
    C("jungle temple", ("jungle", "mystic"), modes=("phrygian", "dorian", "minor"), bpm=(80, 92), metres=("4/4", "5/4"), busy=0.4, weight=0.95,
      leads=("choir", "shakuhachi", "trombone"), strong=("choir", "brass"), under=("trombone", "tuba"), pads=("choir", "tremolo"),
      pad_ways=("drone", "pad"), plucks=("marimba", "bells", "harp"), figures=("toll", "pattern"), basses=("basses slow", "melodic tom"),
      kit="wood", drums=("taiko", "great drum"), grooves=("hunt", "dirge"), hall=(3.4, 0.36), lift=0.4,
      titles=(("Serpent", "Sunken", "Idol", "Moss-Grown", "Jaguar", "Feathered"), ("Temple", "Ziggurat", "Altar", "Steps", "Pyramid", "Sanctum"))),
    C("volcano peak", ("infernal", "highland"), modes=("phrygian", "minor"), bpm=(88, 100), busy=0.45, weight=1.0,
      leads=("trombone", "horns", "choir"), strong=("brass", "choir"), under=("tuba", "trombone"), pads=("tremolo", "choir"), pad_ways=("tremolo", "drone"),
      plucks=("strings", "bells"), figures=("hammer", "gallop"), basses=("basses", "tuba"), kit="orchestra", drums=("taiko", "timpani", "great drum"),
      grooves=("anvil", "colossus"), hall=(3.0, 0.32), lift=0.45,
      titles=(("Smoking", "Fire", "Cinder", "Ashfall", "Burning", "Black"), ("Peak", "Summit", "Crater", "Mountain", "Caldera", "Crown"))),
    C("harbour town", ("regal", "pastoral", "coast"), light=True, modes=("major", "mixolydian", "lydian"), bpm=(104, 116), metres=("6/8", "4/4"), busy=0.6,
      weight=0.65, leads=("flute", "violin", "trumpet"), strong=("violins", "flute"), under=("horns", "celli"), pads=("strings",), pad_ways=("pad",),
      plucks=("harp", "pizzicato", "guitar"), figures=("arp", "oompah"), basses=("celli pizz", "basses pizz"), kit="march", drums=("timpani",),
      grooves=("courtly", "jig"), hall=(2.2, 0.24), lift=0.35,
      titles=(("Harbour", "Lighthouse", "Seagate", "Admiral's", "Mariner's", "Pier"), ("Town", "Watch", "Promenade", "Quay", "Morning", "Sails"))),
    C("royal gardens", ("regal", "pastoral"), light=True, modes=("major", "lydian"), bpm=(80, 92), metres=("3/4",), busy=0.5, weight=0.5,
      leads=("flute", "oboe", "harpsichord"), strong=("violins slow", "flute"), under=("celli",), pads=("strings slow",), pad_ways=("pad",),
      plucks=("harpsichord", "harp", "pizzicato"), figures=("arp", "oompah"), basses=("celli pizz", "basses pizz"), kit="folk", drums=(),
      grooves=("courtly", "sparkle"), hall=(2.0, 0.22), lift=0.2,
      titles=(("Royal", "Rose", "Fountain", "Topiary", "Queen's", "Summer"), ("Gardens", "Walk", "Arbour", "Terrace", "Parterre", "Hedge"))),
    C("shadow glade", ("mystic", "haunted"), modes=("phrygian", "minor"), bpm=(64, 76), metres=("4/4", "3/4"), busy=0.3, weight=0.85,
      leads=("bass flute", "oohs", "cello"), strong=("choir", "violins slow"), under=("bass clarinet",), pads=("tremolo", "oohs"),
      pad_ways=("tremolo", "drone"), plucks=("harp", "celesta", "vibes"), figures=("toll", "arp"), basses=("basses slow", "celli slow"),
      kit="folk", drums=("great drum",), grooves=("drip", "dirge"), hall=(3.6, 0.38), lift=0.25,
      titles=(("Shadow", "Withered", "Blighted", "Moonless", "Thorned", "Hollow"), ("Glade", "Grove", "Boughs", "Circle", "Clearing", "Wood"))),
    C("moon peak", ("mystic", "highland", "frozen"), light=True, modes=("lydian", "dorian"), bpm=(64, 76), metres=("4/4", "3/4"), busy=0.35, weight=0.55,
      leads=("handbells", "flute", "oohs"), strong=("violins slow", "handbells"), under=("horns",), pads=("oohs", "strings slow"), pad_ways=("pad",),
      plucks=("harp", "handbells", "celesta"), figures=("arp", "toll"), basses=("celli slow", "basses pizz"), kit="folk", drums=(),
      grooves=("sparkle",), hall=(3.4, 0.36), lift=0.3,
      titles=(("Moon", "Star", "Silver", "Owl", "Cloud", "Wind"), ("Peak", "Summit", "Spire", "Heights", "Overlook", "Crest"))),
    C("flooded mill", ("pastoral", "haunted", "marsh"), modes=("minor", "dorian"), bpm=(72, 84), metres=("3/4", "4/4"), busy=0.4, weight=0.8,
      leads=("cello", "english horn", "piano"), strong=("violins", "piano"), under=("celli",), pads=("strings slow", "tremolo"),
      pad_ways=("pad", "tremolo"), plucks=("harp", "piano", "pizzicato"), figures=("arp", "rock"), basses=("celli", "basses pizz"),
      kit="folk", drums=("timpani",), grooves=("rain", "waltz"), hall=(2.6, 0.28), lift=0.3,
      titles=(("Flooded", "Drowned", "Silted", "Broken", "Weir", "Rain-Swollen"), ("Mill", "Wheel", "Sluice", "Millrace", "Pond", "Dam"))),
    C("stone circle", ("highland", "pastoral"), modes=("dorian", "mixolydian", "minor"), bpm=(76, 88), metres=("4/4", "6/8"), busy=0.4, weight=0.75,
      leads=("english horn", "bagpipe", "viola"), strong=("violins", "horns"), under=("celli",), pads=("strings slow", "oohs"), pad_ways=("drone", "pad"),
      plucks=("harp", "pizzicato"), figures=("arp", "toll"), basses=("celli slow", "basses"), kit="march", drums=("great drum",),
      grooves=("dirge", "stately"), hall=(3.2, 0.34), lift=0.3,
      titles=(("Standing", "Old", "Ring", "Sentinel", "Weathered", "Solstice"), ("Stones", "Circle", "Henge", "Menhirs", "Watchers", "Dolmen"))),
    # --- the night (2026-11-16, played: "night should feel like night"): night out of doors is a place of its own now, --
    # --- and had three pieces. One for each kind of place and its ground, quiet, slow and far off. -----------------------
    C("starlit meadow", ("pastoral", "highland"), role="night", light=True, modes=("lydian", "major"), bpm=(56, 68), metres=("3/4", "4/4"),
      busy=0.3, weight=0.4, leads=("flute", "celesta", "clarinet"), strong=("violins slow", "flute"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("harp", "dream piano", "celesta"), figures=("arp", "rock"), basses=("celli slow",),
      kit="folk", drums=(), grooves=("none", "sparkle"), hall=(3.2, 0.34), lift=0.0,
      titles=(("Starlit", "Dew-Wet", "Sleeping", "Moonbright", "Silver", "Hushed"), ("Meadow", "Fields", "Furrows", "Hay", "Pasture", "Grass"))),
    C("owl wood", ("pastoral", "haunted", "mystic", "marsh"), role="night", light=True, modes=("dorian", "minor"), bpm=(58, 70), metres=("3/4", "4/4"),
      busy=0.3, weight=0.4, leads=("clarinet", "bass flute", "viola"), strong=("violins slow", "clarinet"), under=("celli",),
      pads=("oohs", "strings slow"), pad_ways=("pad",), plucks=("harp", "pizzicato"), figures=("arp", "toll"), basses=("celli slow", "basses pizz"),
      kit="folk", drums=(), grooves=("none", "tick"), hall=(3.4, 0.36), lift=0.0,
      titles=(("Owl", "Moth", "Badger's", "Hollow Oak", "Night", "Bramble"), ("Wood", "Hollow", "Thicket", "Copse", "Boughs", "Path"))),
    C("moonlit shore", ("pastoral", "mystic", "jungle", "coast"), role="night", light=True, modes=("lydian", "dorian"), bpm=(56, 68), metres=("6/8", "3/4"),
      busy=0.3, weight=0.4, leads=("harp", "flute", "oohs"), strong=("oohs", "violins slow"), under=("celli",), pads=("strings slow", "oohs"),
      pad_ways=("pad",), plucks=("harp", "handchimes", "vibes"), figures=("arp", "rock"), basses=("celli slow",), kit="folk", drums=(),
      grooves=("none", "sparkle"), hall=(3.6, 0.38), lift=0.0,
      titles=(("Moonlit", "Low Tide", "Silver", "Sleeping", "Night", "Gentle"), ("Shore", "Sands", "Tide", "Harbour", "Waves", "Cove"))),
    C("village asleep", ("pastoral", "regal", "highland"), role="night", light=True, modes=("major", "dorian"), bpm=(60, 72), metres=("3/4",),
      busy=0.35, weight=0.4, leads=("music box", "celesta", "cello"), strong=("violins slow", "celesta"), under=("cello",),
      pads=("strings slow",), pad_ways=("pad",), plucks=("harp", "dream piano", "celesta"), figures=("oompah", "arp"), basses=("celli pizz",),
      kit="folk", drums=(), grooves=("tick", "none"), hall=(2.6, 0.28), lift=0.0,
      titles=(("Shuttered", "Lamp-Out", "Chimney", "Cradle", "Sleeping", "Curfew"), ("Village", "Rooftops", "Lane", "Bells", "Windows", "Square"))),
    C("frost night", ("highland", "mystic", "frozen"), role="night", light=True, modes=("lydian", "dorian"), bpm=(54, 66), metres=("4/4", "3/4"),
      busy=0.3, weight=0.4, leads=("celesta", "flute", "handbells"), strong=("violins slow", "glock"), under=("celli",),
      pads=("strings slow", "oohs"), pad_ways=("pad",), plucks=("celesta", "handchimes", "harp"), figures=("arp", "toll"), basses=("celli slow",),
      kit="folk", drums=(), grooves=("none", "sparkle"), hall=(3.8, 0.4), lift=0.0,
      titles=(("Frost", "Star", "Northern", "Crystal", "Snow-Lit", "Aurora"), ("Night", "Sky", "Peaks", "Hush", "Lights", "Silence"))),
    C("jungle night", ("jungle", "mystic", "marsh"), role="night", modes=("dorian", "minor"), bpm=(64, 76), busy=0.35, weight=0.5,
      leads=("pan flute", "bass flute", "marimba"), strong=("marimba", "oohs"), under=("celli",), pads=("oohs", "strings slow"),
      pad_ways=("pad", "drone"), plucks=("marimba", "kalimba", "vibes"), figures=("pattern", "arp"), basses=("celli slow", "basses pizz"),
      kit="wood", drums=(), grooves=("rain", "none"), hall=(3.0, 0.32), lift=0.0,
      titles=(("Firefly", "Frog", "Cricket", "Black Water", "Glowing", "Humid"), ("Night", "Chorus", "Dark", "Hours", "Swamp", "Canopy"))),
    C("grave watch", ("haunted", "regal"), role="night", modes=("minor", "phrygian"), bpm=(54, 64), busy=0.25, weight=0.5,
      leads=("cello", "oohs", "english horn"), strong=("violins slow", "oohs"), under=("celli",), pads=("strings slow", "organ"),
      pad_ways=("pad", "drone"), plucks=("church bell", "harp"), figures=("toll", "arp"), basses=("basses slow",), kit="orchestra",
      drums=(), grooves=("none", "drip"), hall=(4.0, 0.42), lift=0.0,
      titles=(("Grave", "Sexton's", "Lych-Gate", "Yew", "Midnight", "Mourner's"), ("Watch", "Vigil", "Hour", "Bell", "Lantern", "Candle"))),
    C("ember night", ("infernal", "desert"), role="night", modes=("phrygian", "minor"), bpm=(56, 68), busy=0.25, weight=0.5,
      leads=("bass clarinet", "euphonium", "english horn"), strong=("horns", "violins slow"), under=("trombone",), pads=("strings slow", "tremolo"),
      pad_ways=("drone", "pad"), plucks=("harp", "bells"), figures=("toll", "arp"), basses=("basses slow", "tuba"), kit="orchestra",
      drums=(), grooves=("none", "drip"), hall=(3.4, 0.36), lift=0.0,
      titles=(("Cooling", "Ember", "Ashen", "Smouldering", "Banked", "Red"), ("Night", "Forge", "Glow", "Embers", "Hours", "Coals"))),
    C("moon choir", ("mystic", "regal"), role="night", light=True, modes=("lydian", "dorian"), bpm=(54, 64), busy=0.3, weight=0.45,
      leads=("handbells", "oohs", "flute"), strong=("oohs", "violins slow"), under=("celli",), pads=("oohs", "strings slow"), pad_ways=("pad",),
      plucks=("handbells", "handchimes", "harp"), figures=("arp", "toll"), basses=("celli slow",), kit="folk", drums=(),
      grooves=("sparkle", "none"), hall=(4.0, 0.42), lift=0.0,
      titles=(("Moon", "Elune's", "Silver", "Starlight", "Veiled", "Dreaming"), ("Choir", "Vespers", "Chant", "Song", "Canticle", "Prayer"))),
    # --- camping (2026-11-17: "camping should get its own tunes"): a long wait in one spot out of doors, for a spawn, a --
    # --- rare or a friend. Patient music: a single line over a drone, a slow tick under it, never a climb to a crash. ---
    C("watchfire", ("pastoral", "highland", "regal", "coast"), role="camp", light=True, modes=("dorian", "mixolydian", "major"), bpm=(60, 72),
      metres=("3/4", "6/8", "4/4"), busy=0.3, weight=0.4, leads=("flute", "guitar", "english horn"), strong=("violins slow", "horns"),
      under=("celli",), pads=("strings slow", "oohs"), pad_ways=("drone", "pad"), plucks=("guitar", "harp"), figures=("arp", "rock"),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("tick", "none"), hall=(2.2, 0.26), lift=0.0,
      titles=(("Watchfire", "Patient", "Lantern", "Long", "Quiet", "Woodsmoke"), ("Watch", "Vigil", "Wait", "Camp", "Hours", "Fire"))),
    C("still hunt", ("jungle", "desert", "mystic"), role="camp", modes=("dorian", "phrygian dominant", "minor"), bpm=(64, 76),
      metres=("4/4", "5/4"), busy=0.35, weight=0.55, leads=("bass flute", "shenai", "marimba"), strong=("violins slow", "oohs"),
      under=("bassoon",), pads=("strings slow", "basses slow"), pad_ways=("drone",), plucks=("marimba", "dulcimer", "harp"),
      figures=("pattern", "pulse"), basses=("basses pizz", "fretless"), kit="hands", drums=(), grooves=("heat", "canopy"), hall=(2.6, 0.3),
      lift=0.0, titles=(("Still", "Patient", "Hidden", "Crouching", "Watchful", "Silent"), ("Hunt", "Blind", "Wait", "Watch", "Lair", "Ambush"))),
    C("uneasy vigil", ("haunted", "infernal"), role="camp", modes=("minor", "phrygian"), bpm=(56, 66), metres=("4/4", "3/4"), busy=0.25,
      weight=0.6, leads=("cello", "bass clarinet", "oohs"), strong=("choir", "violins slow"), under=("celli",), pads=("tremolo", "organ"),
      pad_ways=("drone", "tremolo"), plucks=("harp", "celesta", "church bell"), figures=("toll", "arp"), basses=("basses slow",),
      kit="orchestra", drums=(), grooves=("dirge", "drip"), hall=(3.2, 0.34), lift=0.0,
      titles=(("Uneasy", "Sleepless", "Wary", "Cold", "Ashen", "Hollow"), ("Vigil", "Watch", "Wait", "Hours", "Camp", "Night"))),
    C("campfire", KINDS_ALL, role="camp", light=True, style="knight", band=True, modes=("mixolydian", "dorian", "major"), bpm=(84, 100),
      busy=0.45, weight=0.4, leads=("harmonica", "steel guitar", "fiddle"), strong=("harmonica", "fiddle"), under=(), pads=("accordion",),
      pad_ways=("drone", "pad"), plucks=("guitar", "mandolin", "banjo"), figures=("strum",), basses=("picked bass",), kit="rock", drums=(),
      grooves=("brushes",), hall=(1.4, 0.15), lift=0.0,
      titles=(("Campfire", "Starlit", "Bedroll", "Woodsmoke", "Coffee Pot", "Saddle"), ("Blues", "Strum", "Jam", "Song", "Ballad", "Ramble"))),
    # --- more camps (2026-11-17, afternoon: "we want lots of options of inns camping, caves dungeons and just a not -------
    # --- repetative experienxe"; a camp is heard at every sit-down to eat and drink): a second camp for each sort of -----
    # --- country, with winds, plucks and a ground of its own. Named after every other family, so none is given another title.
    # (The marsh's demo, written with a pad as well as a drone, had 13 to 17 players at once where the other camps have 9 to
    # 13: a four-part string pad. A camp is a line over a drone, so these hold a drone only, of one voice: a hum, a cello,
    # the basses or an organ.)
    C("shepherds rest", ("pastoral", "highland", "regal"), role="camp", light=True, modes=("major", "lydian", "mixolydian"),
      bpm=(58, 70), metres=("3/4", "6/8"), busy=0.3, weight=0.35, leads=("whistle", "recorder", "clarinet"),
      strong=("violins slow", "oohs"), under=("violas",), pads=("oohs", "celli slow"), pad_ways=("drone",),
      plucks=("dulcimer", "harp", "twelve string"), figures=("arp",), basses=("celli slow", "basses pizz"), kit="folk", drums=(),
      grooves=("none", "tick"), hall=(2.4, 0.26), lift=0.0,
      titles=(("Shepherd's", "Hillside", "Folded", "Evening", "Dusk", "Lamb's"), ("Rest", "Star", "Pipe", "Fold", "Hour", "Hush"))),
    C("fen fire", ("jungle", "mystic", "haunted", "marsh"), role="camp", modes=("dorian", "lydian"), bpm=(60, 72), metres=("6/8", "4/4"),
      busy=0.3, weight=0.4, leads=("ocarina", "shakuhachi", "pan flute"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("oohs", "basses slow"), pad_ways=("drone",), plucks=("kalimba", "harp", "celesta"), figures=("arp", "pattern"),
      basses=("fretless", "celli slow"), kit="wood", drums=(), grooves=("drip", "bog"), hall=(2.8, 0.32), lift=0.0,
      titles=(("Fen", "Marsh", "Reed", "Mire", "Wisp", "Heron"), ("Fire", "Lights", "Rest", "Hush", "Glow", "Dusk"))),
    C("oasis embers", ("desert", "infernal"), role="camp", light=True, modes=("phrygian dominant", "dorian"), bpm=(62, 74),
      metres=("4/4", "6/8"), busy=0.3, weight=0.45, leads=("english horn", "clarinet", "sitar"), strong=("violins slow", "oohs"),
      under=("bassoon",), pads=("celli slow", "oohs"), pad_ways=("drone",), plucks=("dulcimer", "harp", "twelve string"),
      figures=("pattern", "arp"), basses=("basses pizz", "fretless"), kit="hands", drums=(), grooves=("heat", "none"),
      hall=(2.2, 0.24), lift=0.0,
      titles=(("Oasis", "Ember", "Dune", "Starlit", "Coal", "Palm"), ("Embers", "Rest", "Coals", "Night", "Hours", "Shade"))),
    C("crows rest", ("haunted", "highland", "frozen"), role="camp", modes=("minor", "dorian"), bpm=(54, 66), metres=("3/4", "4/4"),
      busy=0.25, weight=0.45, leads=("violin", "clarinet", "english horn"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("organ", "basses slow"), pad_ways=("drone",), plucks=("music box", "harp", "celesta"),
      figures=("toll", "arp"), basses=("basses slow", "celli slow"), kit="orchestra", drums=(), grooves=("drip", "none"),
      hall=(3.0, 0.32), lift=0.0,
      titles=(("Crow's", "Lantern", "Grey", "Lonely", "Mist", "Tolling"), ("Rest", "Watch", "Hour", "Light", "Wait", "Heath"))),
    # --- more dungeon bosses (the same afternoon): the kinds of place whose dungeons had only the titan's music. A drowned ---
    # --- horror for the water and the old forests (Blackfathom), a fallen crusader for the halls and the cloisters. ------
    C("deep tide", ("mystic", "jungle", "marsh", "coast"), role="boss", serves=(2,), modes=("dorian", "phrygian"), bpm=(88, 100), metres=("6/8", "4/4"),
      busy=0.45, weight=1.0, leads=("horns", "full choir", "trombone"), strong=("brass", "full choir"), under=("trombone", "tuba"),
      pads=("choir", "tremolo"), pad_ways=("tremolo", "pad"), plucks=("strings", "harp"), figures=("gallop", "hammer"),
      basses=("basses", "contrabassoon"), kit="orchestra", drums=("taiko", "great drum"), grooves=("colossus", "thunder"),
      hall=(3.4, 0.34), lift=0.5,
      titles=(("Abyssal", "Drowned", "Tidal", "Leviathan", "Sunken", "Brine"), ("Tide", "Maw", "Herald", "Horror", "Queen", "Deep"))),
    C("fallen crusade", ("regal", "haunted"), role="boss", serves=(2,), modes=("minor", "phrygian"), bpm=(100, 112), metres=("4/4",),
      busy=0.5, weight=1.0, leads=("trumpet", "choir", "horns"), strong=("brass", "choir"), under=("trombone", "tuba"),
      pads=("organ", "choir"), pad_ways=("pad", "tremolo"), plucks=("strings", "church bell"), figures=("hammer", "gallop"),
      basses=("basses", "tuba"), kit="march", drums=("timpani", "church bell"), grooves=("march", "battle"),
      hall=(3.0, 0.3), lift=0.5,
      titles=(("Crimson", "Fallen", "Zealot", "Scarlet", "Iron", "Penitent"), ("Crusade", "Inquisitor", "Commander", "Paladin", "Warden", "Judge"))),
    # --- the new kinds of place (2026-11-17, evening: "tonight make more types or categories of places and thus the tracks --
    # --- that match them"): music to walk about the marshes, the sea coasts and the snowfields, light and heavy, and a night
    # --- by the sea. Each kind's own colours: the marsh's low reeds, dulcimer and croaking guiro in a slow sway; the coast's
    # --- whistle, fiddle and concertina in a rolling six-eight; the snow's celesta, harp and sleigh bells, and its bare brass.
    C("bog lights", ("marsh", "jungle"), light=True, modes=("dorian", "lydian", "mixolydian"), bpm=(72, 86), metres=("6/8", "4/4"),
      busy=0.45, weight=0.5, leads=("clarinet", "bass flute", "ocarina"), strong=("violins slow", "oohs"), under=("bassoon",),
      # (A pad of one voice, 17:55 the same evening: the first take, with a four-part string pad, opened with nine players and
      # swung only 11 dB, where the light jungle's river spirits open with six and swing 16. A marsh opens on a mist and a reed.)
      pads=("oohs", "celli slow"), pad_ways=("drone", "pad"), plucks=("dulcimer", "kalimba", "harp"), figures=("arp", "pattern"),
      basses=("fretless", "celli pizz"), kit="wood", drums=(), grooves=("bog", "drip"), hall=(2.6, 0.3), lift=0.2,
      titles=(("Bog", "Peat", "Reed", "Heron's", "Frog", "Lantern"), ("Lights", "Glimmer", "Wander", "Song", "Dance", "Lanterns"))),
    C("grey fen", ("marsh", "haunted"), modes=("dorian", "minor", "phrygian"), bpm=(70, 84), metres=("6/8", "4/4"), busy=0.4, weight=0.85,
      leads=("bass clarinet", "english horn", "cello"), strong=("violins", "horns"), under=("celli",), pads=("tremolo", "strings slow"),
      pad_ways=("tremolo", "drone"), plucks=("harp", "dulcimer"), figures=("pulse", "arp"), basses=("basses", "celli slow"), kit="wood",
      drums=("great drum",), grooves=("bog", "drip"), hall=(2.8, 0.3), lift=0.25,
      titles=(("Grey", "Sunken", "Weeping", "Sodden", "Mire", "Bitter"), ("Fen", "Causeway", "Reach", "Mere", "Fenland", "Water"))),
    C("sea breeze", ("coast", "pastoral"), light=True, modes=("mixolydian", "major", "dorian"), bpm=(104, 120), metres=("6/8",),
      busy=0.6, weight=0.6, leads=("whistle", "fiddle", "flute"), strong=("violins", "horns"), under=("celli",),
      pads=("accordion", "strings slow"), pad_ways=("pad", "drone"), plucks=("harp", "guitar", "mandolin"), figures=("arp", "strum"),
      basses=("celli pizz", "basses pizz"), kit="folk", drums=(), grooves=("jig", "sparkle"), hall=(2.0, 0.22), lift=0.3,
      titles=(("Salt", "Gull's", "Spray", "Morning", "Bright", "Sailor's"), ("Breeze", "Jig", "Wind", "Air", "Hornpipe", "Tide"))),
    C("salt road", ("coast", "highland"), modes=("dorian", "minor", "mixolydian"), bpm=(84, 98), metres=("6/8", "4/4"), busy=0.5,
      weight=0.9, leads=("horns", "english horn", "violins"), strong=("brass", "violins"), under=("trombone", "celli"),
      pads=("strings slow", "tremolo"), pad_ways=("pad", "tremolo"), plucks=("harp", "pizzicato"), figures=("pulse", "gallop"),
      basses=("celli", "basses"), kit="orchestra", drums=("timpani",), grooves=("stately", "tick"), hall=(2.6, 0.28), lift=0.4,
      titles=(("Storm", "Cliff", "Wrecker's", "Grey", "Seawall", "Headland"), ("Road", "Watch", "Crossing", "Reach", "Coast", "Light"))),
    C("lighthouse", ("coast", "mystic"), role="night", light=True, modes=("lydian", "dorian"), bpm=(56, 68), metres=("3/4", "6/8"),
      busy=0.3, weight=0.4, leads=("flute", "english horn", "violin"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("oohs", "celli slow"), pad_ways=("drone",), plucks=("harp", "celesta"), figures=("arp",), basses=("celli slow", "basses slow"),
      kit="folk", drums=(), grooves=("none", "tick"), hall=(2.6, 0.3), lift=0.0,
      titles=(("Lighthouse", "Beacon", "Keeper's", "Tideless", "Lamp", "Harbour"), ("Night", "Lullaby", "Vigil", "Hours", "Glow", "Dream"))),
    C("ice fields", ("frozen", "highland"), light=True, modes=("lydian", "major", "dorian"), bpm=(66, 80), metres=("3/4", "4/4"),
      busy=0.4, weight=0.5, leads=("flute", "clarinet", "oboe"), strong=("violins slow", "horns"), under=("violas",),
      pads=("strings slow", "oohs"), pad_ways=("pad", "drone"), plucks=("celesta", "harp", "pizzicato"), figures=("arp",),
      basses=("celli pizz", "basses slow"), kit="folk", drums=(), grooves=("sleigh", "none"), hall=(3.0, 0.32), lift=0.2,
      titles=(("Hoarfrost", "Glittering", "Snowlit", "Starry", "Crystal", "White"), ("Fields", "Waltz", "Drift", "Hush", "Morning", "Glitter"))),
    C("white waste", ("frozen", "haunted"), modes=("minor", "phrygian", "dorian"), bpm=(60, 74), metres=("4/4", "3/4"), busy=0.35,
      weight=0.95, leads=("horns", "cello", "english horn"), strong=("brass", "choir"), under=("trombone", "tuba"), pads=("tremolo", "choir"),
      pad_ways=("tremolo", "drone"), plucks=("harp", "strings"), figures=("pulse", "toll"), basses=("basses", "contrabassoon"),
      kit="orchestra", drums=("timpani", "great drum"), grooves=("dirge", "stately"), hall=(3.4, 0.34), lift=0.3,
      titles=(("Howling", "Bitter", "Endless", "Pale", "Frozen", "Silent"), ("Waste", "Expanse", "Silence", "Wind", "March", "Tundra"))),
    # --- and music of their own for every moment there ("it only matters if those new categories have different families of
    # --- songs", the same evening): the marsh's night, inn, cave, camp and boss; the coast's inn, cave, camp, boss and storm;
    # --- the snow's night, inn, cave, camp, boss and storm.
    C("frog chorus", ("marsh", "jungle"), role="night", light=True, modes=("dorian", "lydian"), bpm=(56, 68), metres=("6/8", "4/4"),
      busy=0.3, weight=0.4, leads=("bass flute", "clarinet", "ocarina"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("oohs", "basses slow"), pad_ways=("drone",), plucks=("kalimba", "harp"), figures=("arp", "pattern"),
      basses=("fretless", "celli slow"), kit="wood", drums=(), grooves=("bog", "none"), hall=(2.8, 0.32), lift=0.0,
      titles=(("Frog", "Firefly", "Bullfrog", "Moonlit", "Cattail", "Croaking"), ("Chorus", "Night", "Serenade", "Hours", "Hush", "Song"))),
    C("bog inn", ("marsh", "haunted"), role="ember", light=True, modes=("dorian", "mixolydian", "minor"), bpm=(86, 100),
      metres=("6/8", "3/4"), busy=0.5, weight=0.45, leads=("accordion", "fiddle", "clarinet"), strong=("fiddle", "accordion"),
      under=("celli",), pads=("accordion", "celli slow"), pad_ways=("pad", "drone"), plucks=("banjo", "guitar", "dulcimer"),
      figures=("strum", "arp"), basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("waltz", "tick"),
      hall=(1.5, 0.18), lift=0.15,
      titles=(("Mudlark", "Peatsmoke", "Sodden", "Lamplit", "Reedcutter", "Stilt"), ("Inn", "Taproom", "Supper", "Hearth", "Table", "Evening"))),
    C("drowned grotto", ("marsh", "mystic"), role="depths", modes=("dorian", "phrygian", "minor"), bpm=(60, 72), metres=("4/4", "6/8"),
      busy=0.3, weight=0.6, leads=("bass clarinet", "shakuhachi", "oohs"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("oohs", "basses slow"), pad_ways=("drone",), plucks=("harp", "kalimba"), figures=("arp", "pattern"),
      basses=("basses slow", "fretless"), kit="wood", drums=(), grooves=("drip", "none"), hall=(4.0, 0.42), lift=0.0,
      titles=(("Drowned", "Sunken", "Weed-Choked", "Dripping", "Mossy", "Silted"), ("Grotto", "Hollow", "Cellar", "Burrow", "Vault", "Depths"))),
    C("reed fire", ("marsh", "pastoral"), role="camp", light=True, modes=("mixolydian", "dorian"), bpm=(62, 74), metres=("6/8", "3/4"),
      busy=0.3, weight=0.35, leads=("pan flute", "clarinet", "whistle"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("oohs", "celli slow"), pad_ways=("drone",), plucks=("dulcimer", "harp"), figures=("arp",), basses=("celli slow", "basses pizz"),
      kit="wood", drums=(), grooves=("drip", "none"), hall=(2.4, 0.26), lift=0.0,
      titles=(("Reed", "Rushlight", "Punt", "Willow", "Marsh", "Peat"), ("Fire", "Camp", "Glow", "Rest", "Embers", "Smoke"))),
    C("bog beast", ("marsh", "jungle"), role="boss", serves=(2,), modes=("phrygian", "minor", "dorian"), bpm=(84, 96), metres=("6/8", "4/4"),
      busy=0.45, weight=1.0, leads=("trombone", "full choir", "horns"), strong=("brass", "full choir"), under=("trombone", "tuba"),
      pads=("tremolo", "choir"), pad_ways=("tremolo", "pad"), plucks=("strings", "harp"), figures=("gallop", "hammer"),
      basses=("basses", "contrabassoon"), kit="orchestra", drums=("taiko", "great drum"), grooves=("colossus", "battle"),
      hall=(3.0, 0.3), lift=0.5,
      titles=(("Bog", "Mire", "Swamp", "Rotting", "Sunken", "Fen"), ("Beast", "Hydra", "Horror", "King", "Wyrm", "Maw"))),
    C("sailors rest", ("coast", "pastoral"), role="ember", light=True, modes=("major", "mixolydian", "dorian"), bpm=(110, 126),
      metres=("6/8",), busy=0.6, weight=0.45, leads=("fiddle", "whistle", "accordion"), strong=("fiddle", "accordion"), under=("celli",),
      pads=("accordion", "celli slow"), pad_ways=("pad", "drone"), plucks=("guitar", "mandolin", "harp"), figures=("strum", "arp"),
      basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("jig", "reel"), hall=(1.5, 0.16), lift=0.2,
      titles=(("Sailors", "Bosun's", "Mariner's", "Anchor", "Salty", "Quayside"), ("Rest", "Hornpipe", "Taproom", "Shanty", "Round", "Reel"))),
    C("tide cave", ("coast", "mystic"), role="depths", modes=("dorian", "lydian", "minor"), bpm=(58, 70), metres=("6/8", "4/4"),
      busy=0.3, weight=0.55, leads=("english horn", "flute", "oohs"), strong=("violins slow", "oohs"), under=("celli",),
      pads=("oohs", "basses slow"), pad_ways=("drone",), plucks=("harp", "celesta"), figures=("arp",), basses=("basses slow", "celli slow"),
      kit="folk", drums=(), grooves=("drip", "none"), hall=(3.8, 0.4), lift=0.0,
      titles=(("Tide", "Echoing", "Barnacle", "Wreck", "Low-Tide", "Seaglass"), ("Cave", "Cove", "Hollow", "Cellar", "Grotto", "Run"))),
    C("driftwood fire", ("coast", "pastoral"), role="camp", light=True, modes=("mixolydian", "major", "dorian"), bpm=(64, 76),
      metres=("6/8", "4/4"), busy=0.3, weight=0.35, leads=("whistle", "guitar", "english horn"), strong=("violins slow", "oohs"),
      under=("celli",), pads=("oohs", "celli slow"), pad_ways=("drone",), plucks=("guitar", "harp"), figures=("arp",),
      basses=("celli slow", "basses pizz"), kit="folk", drums=(), grooves=("none", "tick"), hall=(2.2, 0.24), lift=0.0,
      titles=(("Driftwood", "Beach", "Shell", "Dune-Grass", "Tidewrack", "Starlit"), ("Fire", "Camp", "Embers", "Watch", "Rest", "Glow"))),
    C("sea king", ("coast", "haunted"), role="boss", serves=(2,), modes=("minor", "phrygian", "dorian"), bpm=(100, 112), metres=("6/8", "4/4"),
      busy=0.5, weight=1.0, leads=("horns", "trombone", "full choir"), strong=("brass", "full choir"), under=("trombone", "tuba"),
      pads=("tremolo", "organ"), pad_ways=("tremolo", "pad"), plucks=("strings", "harp"), figures=("gallop", "hammer"),
      basses=("basses", "tuba"), kit="orchestra", drums=("timpani", "taiko"), grooves=("battle", "colossus"), hall=(2.8, 0.28), lift=0.5,
      titles=(("Pirate", "Drowned", "Corsair", "Kraken", "Black-Sail", "Reef"), ("King", "Captain", "Admiral", "Queen", "Reaver", "Lord"))),
    C("sea storm", ("coast", "highland"), role="storm", serves=(1, 2), modes=("minor", "dorian"), bpm=(126, 140), metres=("6/8", "4/4"),
      busy=0.6, weight=1.0, leads=("horns", "violins", "trumpet"), strong=("brass", "violins"), under=("trombone", "celli"),
      pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("strings", "harp"), figures=("gallop", "hammer"), basses=("celli", "basses"),
      kit="orchestra", drums=("timpani", "great drum"), grooves=("thunder",), hall=(2.6, 0.3), lift=0.4,
      titles=(("Gale", "Squall", "Breaker", "Rogue", "Thundering", "Spindrift"), ("Swell", "Surge", "Breakers", "Seas", "Gale", "Waves"))),
    C("aurora", ("frozen", "mystic"), role="night", light=True, modes=("lydian", "major"), bpm=(52, 64), metres=("3/4", "4/4"), busy=0.3,
      weight=0.4, leads=("flute", "violin", "oohs"), strong=("violins slow", "oohs"), under=("celli",), pads=("oohs", "celli slow"),
      pad_ways=("drone",), plucks=("celesta", "harp", "pizzicato"), figures=("arp",), basses=("celli slow", "basses slow"), kit="folk", drums=(),
      grooves=("none", "tick"), hall=(3.4, 0.36), lift=0.0,
      titles=(("Aurora", "Northern", "Shimmering", "Polar", "Starfall", "Arctic"), ("Lights", "Veil", "Night", "Ribbon", "Glow", "Dream"))),
    C("mead hall", ("frozen", "highland"), role="ember", light=True, modes=("mixolydian", "dorian", "major"), bpm=(100, 116),
      metres=("3/4", "6/8"), busy=0.55, weight=0.5, leads=("fiddle", "accordion", "whistle"), strong=("fiddle", "horns"), under=("celli",),
      pads=("accordion", "celli slow"), pad_ways=("pad", "drone"), plucks=("guitar", "harp", "mandolin"), figures=("strum", "arp"),
      basses=("acoustic bass", "celli pizz"), kit="folk", drums=(), grooves=("waltz", "reel"), hall=(1.8, 0.2), lift=0.2,
      titles=(("Mead", "Snowed-In", "Thane's", "Frostbeard", "Honeyed", "Longhouse"), ("Hall", "Toast", "Feast", "Waltz", "Round", "Cup"))),
    C("ice cave", ("frozen", "mystic"), role="depths", light=True, modes=("lydian", "dorian"), bpm=(54, 66), metres=("3/4", "4/4"),
      busy=0.3, weight=0.45, leads=("flute", "oboe", "oohs"), strong=("violins slow", "oohs"), under=("violas",), pads=("oohs", "basses slow"),
      pad_ways=("drone",), plucks=("celesta", "harp", "pizzicato"), figures=("arp",), basses=("celli slow", "basses slow"), kit="folk", drums=(),
      grooves=("drip", "none"), hall=(4.4, 0.45), lift=0.0,
      titles=(("Glass", "Blue", "Icicle", "Hoarfrost", "Rimed", "Sapphire"), ("Cave", "Hollow", "Halls", "Vault", "Chamber", "Grotto"))),
    C("frost camp", ("frozen", "highland"), role="camp", modes=("dorian", "minor", "lydian"), bpm=(58, 70), metres=("3/4", "4/4"), busy=0.25,
      weight=0.4, leads=("english horn", "flute", "clarinet"), strong=("violins slow", "oohs"), under=("celli",), pads=("celli slow", "oohs"),
      pad_ways=("drone",), plucks=("harp", "guitar", "celesta"), figures=("arp",), basses=("celli slow", "basses slow"), kit="folk", drums=(),
      grooves=("none", "tick"), hall=(2.8, 0.3), lift=0.0,
      titles=(("Snowbound", "Frostbitten", "Windbreak", "Huddled", "Long", "Lee-Side"), ("Camp", "Night", "Watch", "Wait", "Fire", "Shelter"))),
    C("frost wyrm", ("frozen", "haunted"), role="boss", serves=(2,), modes=("minor", "phrygian"), bpm=(88, 100), metres=("4/4", "3/4"),
      busy=0.45, weight=1.0, leads=("horns", "full choir", "trombone"), strong=("brass", "full choir"), under=("trombone", "tuba"),
      pads=("choir", "tremolo"), pad_ways=("tremolo", "pad"), plucks=("strings", "bells"), figures=("hammer", "gallop"),
      basses=("basses", "contrabassoon"), kit="orchestra", drums=("timpani", "great drum"), grooves=("colossus", "battle"),
      hall=(3.6, 0.36), lift=0.5,
      titles=(("Frost", "Rime", "Glacial", "Winter", "Ice-Bound", "Bone-White"), ("Wyrm", "Tyrant", "Lich", "Giant", "Queen", "Fang"))),
    C("whiteout", ("frozen", "highland"), role="storm", serves=(1, 2), modes=("minor", "dorian"), bpm=(118, 132), metres=("4/4", "6/8"),
      busy=0.55, weight=1.0, leads=("horns", "violins", "flute"), strong=("brass", "violins"), under=("trombone", "celli"),
      pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("strings", "glock"), figures=("gallop", "pulse"), basses=("celli", "basses"),
      kit="orchestra", drums=("timpani",), grooves=("thunder", "sleigh"), hall=(3.0, 0.32), lift=0.3,
      titles=(("Howling", "Blinding", "Driving", "Bitter", "Whirling", "Northern"), ("Gale", "Storm", "Drift", "Squall", "Wind", "Whiteout"))),
    # --- Knight Rock's own music to walk the new kinds of place to ("make sure all genres got the updates around new place --
    # --- categories", the same evening): a swamp boogie of slide and harmonica, a rocking shanty, a riff hammered on a drone.
    C("bayou boogie", ("marsh", "jungle"), light=True, style="knight", band=True, modes=("mixolydian", "dorian", "minor"), bpm=(96, 110),
      # (The lead guitar alone has the tune, as in every band piece: shared with a harmonica it was carried out of its range
      # at the moments. The harmonica holds the chords instead, as a blues harp does.)
      busy=0.55, weight=0.7, leads=("lead guitar",), strong=("lead guitar",), under=(),
      pads=("harmonica", "rock organ"), pad_ways=("drone", "pad"), plucks=("rhythm guitar", "steel guitar"), figures=("riff", "chug"),
      basses=("picked bass",), kit="rock", drums=(), grooves=("half rock", "tom rock"), hall=(1.4, 0.15), lift=0.0,
      # (No key change at its moment: a swamp blues stays home, and lifted, its lead's licks went over the guitar's top.)
      titles=(("Bayou", "Gator", "Muddy", "Catfish", "Moonshine", "Cottonmouth"), ("Boogie", "Shuffle", "Crawl", "Blues", "Strut", "Swagger"))),
    C("sea dog", ("coast", "pastoral"), light=True, style="knight", band=True, modes=("mixolydian", "dorian", "major"), bpm=(120, 136),
      metres=("6/8", "4/4"), busy=0.6, weight=0.7, leads=("lead guitar", "fiddle", "whistle"), strong=("lead guitar", "fiddle"), under=(),
      pads=("accordion", "rock organ"), pad_ways=("drone", "pad"), plucks=("rhythm guitar", "twelve string", "mandolin"),
      figures=("strum", "riff"), basses=("picked bass",), kit="rock", drums=(), grooves=("rock", "tavern rock"), hall=(1.3, 0.14), lift=0.3,
      titles=(("Sea", "Bilge", "Rum", "Anchor", "Scurvy", "Barnacle"), ("Dog", "Rocker", "Runner", "Riot", "Rollers", "Raiders"))),
    C("frost hammer", ("frozen", "highland"), style="knight", band=True, modes=("minor", "dorian", "phrygian"), bpm=(108, 120), busy=0.5,
      weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "oohs"), pad_ways=("drone",),
      plucks=("rhythm guitar",), figures=("riff", "chug"), basses=("picked bass",), kit="rock", drums=("taiko",),
      grooves=("half rock", "tom rock"), hall=(1.8, 0.2), lift=0.35,
      titles=(("Frost", "Ice", "Winter", "Rime", "Glacier", "Northern"), ("Hammer", "Giant", "Riders", "Anthem", "Wall", "Fist"))),
    # --- More of Knight Rock's walking music for the hills and the fields ("feel like i hear the same knight rock one over and --
    # --- over", 2026-11-17, played in Loch Modan: the band had two light tracks there, of one character). Pads, not drones:
    # --- a drone held through a quiet stretch was the whine of the same evening.
    C("hill country", ("highland", "pastoral", "frozen"), light=True, style="knight", band=True, modes=("mixolydian", "major", "dorian"),
      bpm=(108, 122), busy=0.6, weight=0.6, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",),
      pad_ways=("pad",), plucks=("twelve string", "mandolin", "rhythm guitar"), figures=("strum", "riff"), basses=("picked bass",),
      kit="rock", drums=(), grooves=("rock", "half rock"), hall=(1.3, 0.14), lift=0.3,
      titles=(("Hill", "Granite", "Kinsman's", "Ridge", "Stonecutter's", "Thane's"), ("Country", "Stride", "Ballad", "Lane", "Rover", "Homestead"))),
    C("harvest boogie", ("pastoral", "coast", "regal"), light=True, style="knight", band=True, modes=("major", "mixolydian"),
      bpm=(126, 140), busy=0.65, weight=0.6, leads=("fiddle", "lead guitar"), strong=("lead guitar", "fiddle"), under=(),
      pads=("rock organ", "accordion"), pad_ways=("pad",), plucks=("banjo", "steel guitar", "twelve string"), figures=("strum",),
      basses=("picked bass",), kit="rock", drums=(), grooves=("tavern rock", "rock"), hall=(1.2, 0.13), lift=0.3,
      titles=(("Harvest", "Haystack", "Barnyard", "Market", "Millpond", "Hayride"), ("Boogie", "Shuffle", "Jamboree", "Stomp", "Day", "Run"))),
    C("iron vow", ("highland", "pastoral", "regal"), style="knight", band=True, modes=("dorian", "minor", "mixolydian"), bpm=(96, 110),
      busy=0.5, weight=0.9, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",), pad_ways=("pad",),
      plucks=("rhythm guitar",), figures=("riff", "chug"), basses=("picked bass",), kit="rock", drums=("taiko",),
      grooves=("half rock", "rock ride"), hall=(1.6, 0.18), lift=0.35,
      titles=(("Iron", "Oathsworn", "Thunderhead", "Anvil", "Clansman's", "Bastion"), ("Vow", "March", "Gate", "Drum", "Hold", "Creed"))),
    C("free company", ("pastoral", "regal", "highland"), style="knight", band=True, modes=("mixolydian", "dorian"), bpm=(124, 138),
      busy=0.6, weight=0.85, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",), pad_ways=("pad", "drone"),
      plucks=("rhythm guitar", "twelve string"), figures=("riff", "strum"), basses=("picked bass",), kit="rock", drums=(),
      grooves=("rock", "rock ride"), hall=(1.3, 0.14), lift=0.4,
      titles=(("Free", "Sellsword", "Roving", "Hired", "Wandering", "Mercenary"), ("Company", "Blades", "Riders", "Band", "Lances", "Banners"))),
    # --- Knight Rock's moments, each of which had one character for every kind of place (2026-11-18, night: an inn, a camp, a --
    # --- cave, the night or a storm now changes the song, and the round of what has been heard would go round two tunes). --
    # --- Pads, not drones, in the quiet parts; the tune to one instrument where a second would carry it out of range. --
    C("barroom blues", KINDS_ALL, role="ember", light=True, style="knight", band=True, modes=("mixolydian", "dorian"), bpm=(92, 104),
      busy=0.5, weight=0.55, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("harmonica", "rock organ"), pad_ways=("pad",),
      plucks=("rhythm guitar", "steel guitar"), figures=("riff", "strum"), basses=("picked bass",), kit="rock", drums=(),
      grooves=("half rock", "tavern rock"), hall=(1.1, 0.12), lift=0.0,
      titles=(("Barroom", "Whiskey", "Sawdust", "Lantern", "Last Round", "Back Room"), ("Blues", "Shuffle", "Boogie", "Swing", "Groove", "Slow-Down"))),
    C("dwarf hall", ("highland", "frozen", "regal"), role="ember", style="knight", band=True, modes=("dorian", "mixolydian"), bpm=(112, 124),
      busy=0.6, weight=0.7, leads=("fiddle",), strong=("fiddle",), under=(), pads=("accordion", "rock organ"), pad_ways=("pad",),
      plucks=("rhythm guitar", "mandolin"), figures=("strum", "riff"), basses=("picked bass",), kit="rock", drums=(),
      grooves=("tavern rock", "anvil rock"), hall=(1.6, 0.18), lift=0.25,
      titles=(("Alehouse", "Stonehall", "Tankard", "Hearthfire", "Mead-Bench", "Keg"), ("Stomp", "Roar", "Chorus", "Rumble", "Clamour", "Brawl"))),
    C("road camp", KINDS_ALL, role="camp", light=True, style="knight", band=True, modes=("major", "mixolydian", "dorian"), bpm=(76, 90),
      busy=0.4, weight=0.4, leads=("steel guitar", "fiddle"), strong=("fiddle",), under=(), pads=("strings slow",), pad_ways=("pad",),
      plucks=("twelve string", "guitar"), figures=("strum", "arp"), basses=("picked bass",), kit="room", drums=(),
      grooves=("brushes", "none"), hall=(1.8, 0.2), lift=0.0,
      titles=(("Wayside", "Riverbank", "Moonrise", "Long Night", "Hillside", "Drover's"), ("Camp", "Rest", "Waltz", "Lullaby", "Halt", "Hearth"))),
    C("glow cave", KINDS_ALL, role="depths", light=True, style="knight", band=True, modes=("dorian", "lydian"), bpm=(72, 84), busy=0.35,
      weight=0.5, leads=("steel guitar", "fiddle"), strong=("fiddle",), under=(), pads=("strings slow", "rock organ"), pad_ways=("pad",),
      plucks=("twelve string", "guitar"), figures=("arp",), basses=("picked bass",), kit="room", drums=(), grooves=("brushes",),
      hall=(3.8, 0.42), lift=0.0,
      titles=(("Glimmer", "Crystal", "Dripstone", "Echo", "Glowworm", "Silver"), ("Cave", "Grotto", "Hollow", "Vein", "Chamber", "Seam"))),
    C("low tunnel", KINDS_ALL, role="depths", style="knight", band=True, modes=("phrygian", "minor"), bpm=(70, 82), busy=0.4, weight=0.85,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",), pad_ways=("pad",), plucks=("rhythm guitar",),
      figures=("chug", "riff"), basses=("picked bass",), kit="rock", drums=("taiko",), grooves=("half rock", "tom rock"),
      hall=(3.6, 0.4), lift=0.0,
      titles=(("Low", "Black", "Bedrock", "Lightless", "Hollow", "Rockfall"), ("Tunnel", "Crawl", "Delve", "Rumble", "Below", "Deeps"))),
    C("midnight ride", KINDS_ALL, role="night", style="knight", band=True, modes=("minor", "dorian"), bpm=(84, 96), busy=0.45, weight=0.6,
      leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "strings slow"), pad_ways=("pad",),
      plucks=("twelve string", "rhythm guitar"), figures=("arp", "riff"), basses=("picked bass",), kit="room", drums=(),
      grooves=("brushes", "half rock"), hall=(2.2, 0.24), lift=0.0,
      titles=(("Midnight", "Moonless", "Owl-Light", "Shadow", "Silver Moon", "Dark Lane"), ("Ride", "Rider", "Prowl", "Run", "Patrol", "Vigil"))),
    C("downpour run", KINDS_ALL, role="storm", serves=(1, 2), style="knight", band=True, modes=("minor", "mixolydian"), bpm=(128, 142),
      busy=0.65, weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",), pad_ways=("pad",),
      plucks=("rhythm guitar",), figures=("chug", "riff"), basses=("picked bass",), kit="rock", drums=("taiko",),
      grooves=("rock", "tom rock"), hall=(1.6, 0.17), lift=0.4,
      titles=(("Thunder", "Downpour", "Gale", "Hailstone", "Iron Sky", "Flood"), ("Run", "March", "Riot", "Charge", "Gallop", "Surge"))),
    # --- Warcraft's storms, which had music of their own only in the hills, the snow, the coast and the mystic places (the
    # --- same night: a storm setting in now changes the song, and fields, jungles, haunted woods heard only "anywhere"'s).
    C("field storm", ("pastoral", "regal", "coast"), role="storm", serves=(1, 2), modes=("minor", "dorian"), bpm=(120, 136),
      metres=("4/4", "6/8"), busy=0.6, weight=1.0, leads=("horns", "violins", "trumpet"), strong=("brass", "violins"),
      under=("trombone", "celli"), pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("strings",), figures=("gallop", "pulse"),
      basses=("celli", "basses"), kit="orchestra", drums=("timpani",), grooves=("thunder",), hall=(2.8, 0.3), lift=0.3,
      titles=(("Rolling", "Darkening", "Sudden", "Windblown", "Iron-Grey", "Harvest"), ("Storm", "Thunder", "Squall", "Downpour", "Rain", "Gale"))),
    C("monsoon", ("jungle", "marsh", "desert"), role="storm", serves=(1, 2), modes=("phrygian", "minor"), bpm=(112, 128),
      busy=0.6, weight=1.0, leads=("horns", "violins", "trombone"), strong=("brass", "violins"), under=("trombone", "celli"),
      pads=("tremolo", "strings"), pad_ways=("tremolo",), plucks=("strings", "marimba"), figures=("hammer", "gallop"),
      basses=("celli", "basses"), kit="orchestra", drums=("timpani", "great drum"), grooves=("thunder",), hall=(3.0, 0.32), lift=0.35,
      titles=(("Monsoon", "Drowning", "Warm", "Torrent", "Steaming", "Green"), ("Rains", "Deluge", "Thunder", "Flood", "Squall", "Season"))),
    C("witch storm", ("haunted", "infernal", "mystic"), role="storm", serves=(1, 2), modes=("minor", "phrygian"), bpm=(104, 120),
      busy=0.55, weight=1.0, leads=("horns", "trombone", "violins"), strong=("brass", "violins"), under=("trombone", "tuba"),
      pads=("choir", "tremolo"), pad_ways=("tremolo", "pad"), plucks=("strings",), figures=("hammer", "gallop"),
      basses=("basses", "contrabassoon"), kit="orchestra", drums=("timpani", "great drum"), grooves=("thunder",), hall=(3.4, 0.36), lift=0.4,
      titles=(("Witch", "Grave", "Howling", "Raven", "Bone", "Shrieking"), ("Storm", "Gale", "Tempest", "Squall", "Night", "Thunder"))),
    # --- Knight Rock's towns, a second boss and a battleground (2026-11-18: "then focus on some knight rock for the rest of --
    # --- the day"; the band had none for a town, Stormwind and Ironforge among them, one boss and no battleground). -------
    C("market square", KINDS_ALL, role="town", light=True, serves=(0, 1), style="knight", band=True, modes=("mixolydian", "major"),
      bpm=(104, 116), busy=0.6, weight=0.55, leads=("fiddle", "lead guitar"), strong=("fiddle",), under=(), pads=("accordion", "rock organ"),
      pad_ways=("pad",), plucks=("rhythm guitar", "mandolin", "twelve string"), figures=("strum", "riff"), basses=("picked bass",),
      kit="rock", drums=(), grooves=("shuffle", "tavern rock"), hall=(1.4, 0.15), lift=0.25,
      titles=(("Market", "Cobblestone", "Guildhall", "Fountain", "Merchant's", "Bell Tower"), ("Square", "Shuffle", "Strut", "Day", "Row", "Crossing"))),
    C("royal march", ("regal", "pastoral", "highland", "infernal"), role="town", serves=(0, 1), style="knight", band=True,
      modes=("major", "mixolydian", "dorian"), bpm=(92, 104), busy=0.5, weight=0.85, leads=("lead guitar",), strong=("lead guitar",),
      under=(), pads=("rock organ", "choir"), pad_ways=("pad",), plucks=("rhythm guitar", "twelve string"), figures=("riff", "hammer"),
      basses=("picked bass",), kit="rock", drums=("church bell",), grooves=("half rock", "anvil rock"), hall=(1.9, 0.2), lift=0.35,
      titles=(("King's", "Throne", "Lion's", "Iron", "High", "Banner"), ("March", "Hall", "Gate", "Anthem", "Parade", "Crown"))),
    C("warlord", ("desert", "jungle", "infernal", "haunted"), role="boss", serves=(2,), style="knight", band=True, modes=("phrygian", "minor"),
      bpm=(132, 144), busy=0.55, weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ",),
      pad_ways=("drone",), plucks=("rhythm guitar",), figures=("chug", "riff"), basses=("picked bass",), kit="rock", drums=("taiko",),
      grooves=("tom rock", "rock ride"), hall=(1.4, 0.15), lift=0.5,
      titles=(("Warlord", "Bloodfang", "Skullcrusher", "Chieftain", "Ironjaw", "Ravager"), ("Throne", "Reckoning", "Fury", "Last Stand", "Den", "Pit"))),
    C("banner war", KINDS_ALL, role="battleground", serves=(0, 1, 2), style="knight", band=True, modes=("minor", "dorian"), bpm=(136, 150),
      busy=0.6, weight=1.0, leads=("lead guitar",), strong=("lead guitar",), under=(), pads=("rock organ", "choir"), pad_ways=("drone", "pad"),
      plucks=("rhythm guitar",), figures=("riff", "chug"), basses=("picked bass",), kit="rock", drums=("taiko",), grooves=("rock ride", "tom rock"),
      hall=(1.6, 0.17), lift=0.45,
      titles=(("Warsong", "Banner", "Flag", "Front Line", "Blood", "Bridge"), ("War", "Charge", "Rally", "Run", "Raid", "Clash"))),
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
# The styles whose open walks the first theme's changes, slowly, from a bar or two on its key chord to the chord before home;
# the others hold the key chord and stir every fourth bar of the second half (2026-11-20, the judges: Warcraft's opens the
# weakest of its nine parts on TuneJury and on enjoyment, -38 to -40 dB, its pads "one colour" 16 to 18 bars on the meter).
# Tried on five Warcraft takes and left off (2026-11-20, the judges, the open before and after, TuneJury with the brief / with
# none / Audiobox's enjoyment): Heather Fling +0.21 / -0.02 / +0.14, Old Corpse Road +0.06 / +0.22 / +0.93, Fair Wind Shanty
# +0.11 / -0.26 / +0.01, Crooked Round -0.08 / -0.13 / -0.97 (its 32 bars eight a chord, i VII VI V); on average a little up on
# the brief, a little down with none, enjoyment level. The meter heard the pads move. Kept for the ear to decide.
OPEN_WALKS: tuple[str, ...] = ()
FIGHTS = ("battle", "boss", "storm", "battleground")
DANCE_GROOVES = ("jig", "reel", "waltz", "courtly")      # the grooves of dances: no war drums under them
VALLEY_PAD = 0.55      # how far the pad's swell goes under in the valley, where the tune is a single soft player
# (2026-11-20, the study: Midnight Mass II's valley at -29, its church organ 13 dB over the guitar's soft tune; Thunder Lizard
# Stomp II's rock organ 3 to 10 dB over, Throne Parade IV's organ and choir 5 to 9. A held pad written pp, the floor of the
# marks, still stood over a single plucked tune, and a pad's notes at 0.6 put the church organ on its loud stops, which split
# at 0.62.) In a band's valley a pad's swell goes further under (VALLEY_PAD_SOFT), so that MuseScore plays it ppp (muse.MARKS),
# and its notes are struck softer, the organ on its soft stops. The judges: the three Knight takes' valleys up on TuneJury and on
# Audiobox's enjoyment (Midnight Mass II's 0.27 to 1.01, enjoyment 7.08 to 7.54; Throne Parade IV's 0.33 to 0.48, 6.88 to 7.32;
# Thunder Lizard Stomp II's level); Warcraft's Bone Rite I's TuneJury up there (0.19 to 0.54) but its enjoyment down a whole
# point (5.58 to 4.57): an orchestra's valley, whose tune is a single soft player too, keeps its pad as it was.
VALLEY_SOFT = True
VALLEY_PAD_SOFT = 0.35
# The reeds: held alone under a soft tune they whine, and MuseScore's english horn hardly follows its dynamics there (2026-11-18:
# King's Oath's valley drone stood 12.7 dB over the clean guitar's tune at pianissimo as at piano). In the valley the drone goes to
# the other pad, an organ's or the strings', which go down 20 dB there as written.
REEDS = ("pipe drone", "bagpipe", "accordion", "harmonica")
# How long a player of each holds one note before a breath (an accordion's bellows turning), in seconds: a held note
# longer is played as breaths of whole bars (`Take.breathe`). A bagpipe's bag holds its drone on; the organ, the strings
# and the choir's voices take turns, and are not here.
BREATH = {"harmonica": 5.0, "pipe drone": 6.0, "accordion": 9.0}
DELICATE = ("sparkle", "tick", "rain", "drip", "bog", "brushes", "none")      # grooves too fine for war drums under them
LONG = 480.0                   # seconds: about how long a track is
# A band's guitars' effect marks (Take.effects) and an orchestra's (Take._orchestra_marks): new sounds, heard as demos
# before they were used (var/listen/now.html), then "k keep going" (2026-11-18, 14:25).
BAND_PEDALS = True
SOLOS = True             # a band's lead guitar takes a solo at the summit (guitar_solo); False takes it away
# (2026-11-19, 13:15: "most songs should have solos", "and they should be original each time", "i think you need the solos to
# do some flange shit like move a little".)
MOST_SOLOS = True        # whoever leads the band's summit takes the solo, and a summit of a theme and a half has one; False: the
                         # lead guitar alone, where the theme comes round twice
ORIGINAL_SOLOS = True    # each solo draws its own form, its own way through each figure and from ten figures; False: those of 12:05
SOLO_FLANGER = True      # a flanger sweeps slowly under the solo, a little (Take._solo_marks); False: the echo alone
# (2026-11-19, 16:15, the boredom meter on the day's new heavy takes: the rhythm guitar one colour 34 to 50 bars from the
# summit through the close in three of four, the riff played on under the solo as everywhere else.)
SOLO_COMP = True         # under a solo the rhythm guitar comps: the chord on the bar's first beat, muted eighths after, no fills
TURNS_TO_HAT = True      # a band's groove on the ride turns to the hat for its second sixteen bars (Take.cymbal); False: it stays
# Who may take a band's solo, and whether they can sound two notes at once (double stops, octaves, a held note doubled):
SOLOISTS = {"lead guitar": True, "fiddle": True, "mandolin": True, "harmonica": True, "whistle": False}
# (2026-11-19, the study: Lazy River Swing V's fiddle solo sat F5 to C7, Sea Raiders V's C5 to Bb6: a solo climbs an octave and a
# note over where the tune begins, and a fiddle's tune begins high; its reach was the fiddle's whole written range.) The highest
# note a solo sings on, where the written range runs far above it: a fiddle's E6, a mandolin's D6. The lead guitar's D6 and the
# harmonica's C6 are their written tops already. Empty: the written range, as before. (2026-11-21, the study: the whistle's
# solos sang up to its very top, all in its shrill second octave: Silver Glade II A5 to D7, Dreaming Ballad II C#6 to C#7,
# Sunny Wheels I and III E5 to C#7, eight takes.) A whistle's A6: a player keeps the top of a whistle for a note or two.
SOLO_TOP = {"fiddle": 88, "mandolin": 86, "whistle": 93}
# The figures a solo's middle is made of, three drawn for each solo: Angus Young's and Chuck Berry's (the repeated note, the
# run in threes or fours, the trill, the double stops, the cascade, the pedal lick), the octaves Wes Montgomery and Hendrix
# play a tune in, a figure echoed a step lower each beat, one note picked in threes against the beat, and notes slid into.
SOLO_FIGURES = ("repeat", "sequence", "trill", "stops", "cascade", "pedal", "octaves", "echo", "stutter", "slide")
RIFFY = ("repeat", "sequence", "trill", "cascade")      # (each solo has one of these at least: a riff of quick notes)
RING_SECOND = True       # a heavy band's second theme rings: its rhythm guitar holds each chord (Take.rhythm); False chugs on
SOLO_LIFT = 5.0          # dB the solo stands over the lead's usual level (Take._solo_marks)
CLIMBS = True            # a heavy band's rise climbs where one chord is held long (Take.rhythm, Take.bass); False plays on as it was
LONG_HOLD = 9            # bars of one chord in a rise that make it a long one
OPENS_OUT = True         # a heavy band's drummer opens the hat for the second theme, as its guitars ring (Take.drums)
DIGS_IN = True           # a heavy band's long moment digs in at its half: the bass's octaves, the crash every other bar
# (2026-11-20, the study: Lightning Runner II's rhythm one colour all 32 bars of its arrival, the drums and the bass digging in
# at its half and the guitars playing on as they were.) Each take its own way, as a rise's (`rise_way`): not every song's turn
# the same ("hearing that same guitar riff climb in too many knight songs", 2026-11-19).
HEAVY_DIG_TURNS = True   # ...and its guitars turn for the first half of the dig-in, each take its own way (Take.dig_way)
# (2026-11-21, the judges on Lightning Runner II, its dig-in ringing: level, TuneJury 0.389 to 0.394, enjoyment 7.08 both; the
# meter's run of the rhythm's colour at the arrival 32 bars to 16, the bass's 8 to 3.) The riff up the neck an octave was
# judged on 20 November and left off: a take drawn to go up plays on as written.
DIG_UP = False           # the dig-in's riff goes up the neck an octave over the muted string; False: such a take plays as written
GEARS = True            # an orchestra's long moment goes up a gear every second phrase (Take.geared); False plays it one way
GEAR_BARS = 8            # the phrase a long moment changes on
# (2026-11-19, the study: Sea Raiders V's mandolin, rhythm guitar and muted guitar played the same 160, 78 and 32 notes in every
# eight bars of its 40-bar arrival, the meter's colour unchanged all 40: a heavy band digs in at its half and an orchestra goes
# up a gear, a light band had nothing.)
LIGHT_GEARS = True       # a light band's long arrival goes up a gear every second phrase: its rhythm an octave up (Take.band_geared)
# (2026-11-20, the study: Anchor Dog V's mandolin, rhythm guitar, muted guitar, kit and bass the same 32 bars through its
# summit's fiddle solo and the twin theme after it; Lazy River Sway I's drums one colour 27 bars of its summit.)
# Tried and left off (2026-11-20, the judges, the summit before and after): Anchor Dog V level (TuneJury -0.06 with the brief,
# +0.06 with none, enjoyment +0.06); Lazy River Sway I down (-0.16, -0.46), and with its octave bass kept (LAST_CHORUS no longer
# making a light band's octaves a walk) still down (-0.11, -0.31): its banjo an octave up or the ride is the rest. The meter heard
# the turn (Anchor Dog V's rhythm one colour 38 bars before, 22 after). The light band's summit is still owed its turn.
LIGHT_SUMMIT_TURNS = False  # after a light band's solo its summit comes back harder: the rhythm up a gear, the ride, the bass moving more
# (2026-11-20, the study: Lazy River Sway I's banjo, geared after its solo, back at its own register within twelve bars, and
# from a chord spread over 21 semitones: a geared voicing was led apart from the bars before it, about a centre an octave up,
# and each voice moves to the nearest note of the next chord anywhere within 14 semitones of it, so it walked back down.)
# (Off until it is heard on its own, before and after: every demo of 20 November had it in both halves, and Lazy River Sway's
# banjo strumming at the top of its neck, as this makes it in a geared phrase, may be part of what the judges liked less.)
GEARED_SHAPE = False     # a geared bar plays the bar's own chord shape an octave up; False leads the raised voicing on its own
# (2026-11-19, the judges: Knight's valleys scored TuneJury 0.36 with no brief, against 0.9 for its first theme and arrival,
# and Audiobox's enjoyment its lowest there, 6.34: a walking band's drummer stopped for the whole valley, under a single
# player, a pad and held roots.)
VALLEY_KEEPS_TIME = True  # a band's walking valley keeps time softly: the hat on the beat, the bass drum on the bar, the side stick
# A drum pattern one step busier, for a long moment's geared phrases.
BUSIER_STROKES = {"down": "groups", "groups": "pulses", "back": "pulses", "mid": "groups", "offs": "ands", "pulses": "halves",
                  "last": "back", "three": "pulses"}
CYMBALS = ("crash", "crash2", "ting")
OWN_LICKS = True         # each band take answers its riff with fills of its own (Take.fills); False: the one run and walk-up of 11-17
ANGUS = True             # the solo's middle riffs the way Angus Young plays them (guitar_solo); False: the sung solo of 11-18 alone
# (2026-11-19, 23:00: "gimme a better angus", "lets go".) The solo riffs more and longer, as Angus does: its figures only his
# own (the repeated note, the trill, the pedal lick, the cascade, the run in threes, Chuck Berry's double stops; no octaves,
# echo, stutter or slide), four of a sixteen-bar solo's eight sentences, and each riff carried through its second bar a note
# higher, the lick and the lick again before it lands, where it had played one bar and held the second. The tune's call,
# the run, the peak and the way home are still sung. False: the solos of 14:03.
ANGUS_MORE = True
ANGUS_FIGURES = ("repeat", "trill", "pedal", "cascade", "sequence", "stops")
# (2026-11-20, the study: Sand Fever I's solo sat G3 to C5, its peak C5 where it could have been C6. The peak is a note of the
# chord under it, and it was looked for only in the octave under the solo's top: over Sand Fever's flat-two chord the one note
# of the five in that octave was six steps under the top, and everything before the peak is kept under it. 32 of 165 band
# solos peaked lower than they could.)
SOLO_PEAK_NEAR_TOP = True  # the peak is the chord's note nearest the top, up to two steps over it where the guitar reaches
RIFF_MOVES = True        # a band take's riff moves inside the bar, its own way (Take.riff_move); False: one chord struck in rhythm
LEAD_ANSWERS = True      # a band's lead guitar answers its own long notes with a run into its next (Take.sing); False: it holds them
# (2026-11-19, 13:20, the judges on King's Oath: neither the riff's moves nor the lead's answers had taken SongEval down,
# within its noise either way; the answers sung from the theme scored the same or a little over the scale runs. Kept for
# what they are: the song's own idea in its answers, and no chord struck against the note the lead holds.)
ANSWERS_SING_THE_THEME = True    # the lead's answers are the first theme's opening played quick (Take._answered); False: a scale run
MOVES_LISTEN = True      # a riff's move to another chord waits where the lead holds a note a semitone or a tritone from it (Take._rubs)
ROCK_ENDING = True       # a heavy band's close ends as a rock band ends (Take.ending); False: it dies away as an orchestra's does
BASS_SOLO = True         # a heavy band's bass leads it back in after the valley, alone (Take.bass_break); False: the band climbs together
# The bass's riffs for its break, a bar each over the chord's root in semitones, as (beat, beats, interval) in a bar of four.
BASS_RIFFS = (
    ((0.0, 1.0, 0), (1.0, 0.5, 3), (1.5, 0.5, 5), (2.0, 0.5, 6), (2.5, 0.5, 7), (3.0, 1.0, 10)),               # the blues climb
    ((0.0, 0.5, 0), (0.5, 0.5, 12), (1.0, 0.5, 10), (1.5, 0.5, 7), (2.0, 0.5, 0), (2.5, 0.5, 3), (3.0, 1.0, 5)),   # up the octave and down
    ((0.0, 0.75, 0), (0.75, 0.25, 0), (1.0, 0.5, 3), (1.5, 0.5, 0), (2.0, 0.75, 5), (2.75, 0.25, 5), (3.0, 1.0, 7)),   # the shuffle
    ((0.0, 0.5, 0), (0.5, 0.5, 0), (1.0, 0.5, 7), (1.5, 0.5, 0), (2.0, 0.5, 10), (2.5, 0.5, 0), (3.0, 0.5, 12), (3.5, 0.5, 10)),   # the pedal
)
PENTATONIC = (-12, -9, -7, -5, -2, 0, 3, 5, 7, 10, 12, 15, 17, 19, 22, 24)   # the minor pentatonic over the riff's root, in semitones
# A riff band's fills (2026-11-19: "hearing that same guitar riff climb in too many knight songs", "cant you study acdc and do
# different licks"). Every band song had answered its riff with the same two runs: the walk up to the fifth (b3, 4, b5, 5) at
# the end of every fourth bar and the blues run down at the end of every second, about 32 times a song, in every song. From
# the lessons on Malcolm's and Angus's playing: fills in the minor pentatonic with the blues note, the major pentatonic mixed
# in where the key is major; double stops; the minor third hammered to the major; chords struck on the offbeat; space, a
# chord left to ring rather than filled; the flat seventh's chord as a turn back to the root. Semitones over the riff's root.
FILL_RUNS = ((10, 7, 5, 3), (12, 10, 7, 5), (7, 5, 3, 0), (15, 12, 10, 7), (5, 3, 0, -2), (12, 7, 10, 5), (7, 6, 5, 3),
             (10, 7, 6, 5), (7, 10, 7, 5), (12, 10, 12, 7), (3, 0, -2, -5), (5, 7, 10, 12))     # mostly falling into the chord
BRIGHT_RUNS = ((9, 7, 4, 2), (12, 9, 7, 4), (4, 2, 0, -3), (7, 9, 7, 4), (9, 12, 9, 7), (2, 4, 7, 9))   # the major pentatonic
CURLS = ((3, 4, 0), (3, 4, 7), (10, 3, 4, 0))                                    # the minor third hammered to the major
DOUBLE_STOPS = (((7, 12), (5, 10)), ((3, 7), (5, 9)), ((5, 9), (3, 7)), ((10, 15), (7, 12)), ((7, 12), (7, 12)), ((5, 10), (3, 7)))
MAJORISH = ("major", "mixolydian", "lydian")


def held_runs(symbols: list[str]) -> list[tuple[int, int]]:
    """For each bar of a part, how far it is into the stretch of bars on one chord, and how long that stretch is."""
    out: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(symbols) + 1):
        if index == len(symbols) or symbols[index] != symbols[start]:
            out += [(into, index - start) for into in range(index - start)]
            start = index
    return out
VIBE_QUIET = 0.55        # a passage this soft or softer is the quiet one, where a clean guitar's broken chords take the vibe
ORCHESTRA_MARKS = True
STRUCK = ("harp", "celesta", "glockenspiel", "bells", "marimba", "music box", "dulcimer", "xylophone", "handbells", "harpsichord",
          "pizzicato")         # what a plucked or struck line is played on: its phrase's last note can hang in an echo
DISTANT = ("strings", "strings slow", "tremolo", "choir", "oohs")      # the pads that go further off in the valley
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


def _levels(role: str, heavy: float, busy: float = 0.5) -> dict[str, tuple[float, float]]:
    """How hard each part of the story is played, from its start to its end. The first arrival
    is clearly under the summit, and the valley between them is the quietest the story gets
    once it has begun. A fight is hard from its first bar, and its valley is only a breath; a
    night piece never gets far above a murmur."""
    if role in FIGHTS:
        return {"open": (0.6, 0.72), "first": (0.7, 0.8), "second": (0.66, 0.78), "build": (0.75, 0.95), "arrival": (0.9, 0.9),
                "valley": (0.58, 0.66), "climb": (0.68, 1.0), "summit": (1.0, 1.0), "close": (0.9, 0.65)}
    # (2026-11-16, night: "rewrite all music to be more dynamic". The quiet parts are quieter and the top is as high: an
    # opening and a valley at pianissimo to piano, the summit at fortissimo, a close that dies away.)
    # (A rowdy tavern is not a quiet room: an inn's music busy 0.6 or more is shaped as walking music is, its opening and
    # its middle present and not whispered; the player turns every inn down 4 dB anyway. Found 2026-11-18: a dwarven
    # drinking hall's demo opened at -38 dB and its middle fell to -41.)
    if role in ("night", "ember", "depths", "camp") and not (role == "ember" and busy >= 0.6):
        top, under = 0.45 + 0.4 * heavy, 0.4 + 0.26 * heavy
        return {"open": (0.14, 0.26), "first": (0.34, 0.44), "second": (0.3, 0.42), "build": (0.36, 0.38 + 0.2 * heavy),
                "arrival": (under, under), "valley": (0.18, 0.16), "climb": (0.26, 0.42 + 0.3 * heavy), "summit": (top, top),
                "close": (0.36, 0.1)}
    # (Walking music a little harder, its quiet parts less faint and a light piece's top higher, the valley still the
    # quietest and the summit the loudest: "go a little harder this is not world of fairy craft", 2026-11-17. It was top
    # 0.6 + 0.4 heavy, under 0.5 + 0.28 heavy, open 0.14 to 0.3, first 0.38 to 0.55, second 0.34 to 0.52, build 0.42 to
    # 0.45 + 0.4 heavy, valley 0.2 to 0.16, climb 0.28 to 0.5 + 0.45 heavy, close 0.45 to 0.1.)
    top, under = 0.68 + 0.32 * heavy, 0.56 + 0.26 * heavy
    return {"open": (0.18, 0.34), "first": (0.42, 0.6), "second": (0.38, 0.56), "build": (0.46, 0.5 + 0.38 * heavy),
            "arrival": (under, under), "valley": (0.24, 0.2), "climb": (0.32, 0.55 + 0.42 * heavy), "summit": (top, top),
            "close": (0.48, 0.12)}


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
        # and "6 4 1" come to the same eight bars). It is drawn again; the families that never met this are unchanged.
        # (The player plays a family's takes channel by channel together, so a family's takes must all be made with
        # one set of changes.)
        if other != eight:
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
    if character.style in OPEN_WALKS and lengths["open"] >= 8:
        # The open walks the first theme's changes, slowed to fill it (each bar of the theme one bar of the open, two,
        # three or four, as the open is eight bars long or sixteen, twenty-four or thirty-two), after the key chord for
        # whatever bars are over; it sets out from the key chord whatever the theme's first, and ends on the chord before
        # home, so the first theme comes in at home.
        hold = min(lengths["open"] // 8, 4)
        walk = [chord for chord in ["1"] + eight[1:7] for _ in range(hold)] + [away] * hold
        opening = ["1"] * (lengths["open"] - len(walk)) + walk
    else:
        if lengths["open"] >= 4:
            opening[lengths["open"] // 2] = colour
        for bar in range(lengths["open"] // 2 + 4, lengths["open"] - 1, 4):
            opening[bar] = colour                      # a long opening stirs every fourth bar of its second half
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
    levels = _levels(character.role, character.weight, character.busy)
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
        if len(answer_notes) >= 2 and notes and notes[-1][2] == answer_notes[0][2] == answer_notes[1][2]:
            # The question's held note is the note the answer begins on twice: three of a kind, and the tidying would move
            # one inside the answer, which is to begin as the question did. The held note moves instead, to the nearest
            # other note of its chord that is not the key note (a question does not end at home). (Found 2026-11-16.)
            at, length, step, weight = notes[-1]
            chord = chords[7]
            others = [tone for tone in _chord_steps(chord, step - 5, step + 5) if tone != step and tone % 7 != 0]
            if others:
                notes[-1] = (at, length, min(others, key=lambda tone: (abs(tone - step), tone)), weight)
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


def decorated(rng: random.Random, line: Line) -> Line:
    """A tune the third time round (2026-11-17, night: at the moments the theme and its first variation took turns, so
    that the third time round was the first again, note for note): its notes on the strong beats where they were, and
    between them what a player adds who knows it well: the next note anticipated in the last eighth of a long one, a
    turn round the longest note at its end, and here and there a passing note in a leap of a third."""
    out = Line()
    notes = line.notes
    longest = max(range(len(notes)), key=lambda index: notes[index][1]) if notes else -1
    for index, (start, length, step, weight) in enumerate(notes):
        after = notes[index + 1][2] if index + 1 < len(notes) else None
        if index == longest and length >= 1.5:
            body = length - 1.0
            out.notes.append((start, body, step, weight))
            for number, (off, turn) in enumerate(((0.0, step + 1), (0.25, step), (0.5, step - 1), (0.75, step))):
                out.notes.append((start + body + off, 0.25, turn, weight * (0.85 if number == 0 else 0.8)))
        elif after is not None and after != step and length >= 1.0 and rng.random() < 0.6:
            out.notes.append((start, length - 0.5, step, weight))
            out.notes.append((start + length - 0.5, 0.5, after, weight * 0.8))
        elif after is not None and abs(after - step) == 2 and length >= 0.5 and rng.random() < 0.5:
            out.notes.append((start, length / 2, step, weight))
            out.notes.append((start + length / 2, length / 2, (step + after) // 2, weight * 0.85))
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
                             ("crash", "down", .8, 4)], roll="tom low", hit="crash", fill="snare"),
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
SINGERS = ("rock organ", "organ", "accordion", "choir", "oohs", "harmonica", "bagpipe", "pipe drone", "shenai", "pan flute")
# A section of an orchestra plays one note at a time. A chord for the strings is therefore a
# line for each section, not a block: who takes which note, from the bottom up, by how many
# notes the chord has. (The second violins are the violins again, on a part of their own.)
DESKS = {
    "strings": {2: (("celli", ""), ("violas", "")), 3: (("celli", ""), ("violas", ""), ("violins", "")),
                4: (("celli", ""), ("violas", ""), ("violins", " seconds"), ("violins", ""))},
    "strings slow": {2: (("celli slow", ""), ("violas", "")), 3: (("celli slow", ""), ("violas", ""), ("violins slow", "")),
                     4: (("celli slow", ""), ("violas", ""), ("violins slow", " seconds"), ("violins slow", ""))},
}
# The sorts of ground each character's music was written for (atlas.SETTINGS), finer than its kinds of place (2026-11-16,
# played: "make sure by tomorroow morning we have granularity in locations on all the kinds"). The player prefers, among
# pieces for the same kind of place, those written for the ground the player stands on. Music for a moment (a cave, an
# inn, the night, a storm, a fight, a town) is for the moment, not the ground: it has none.
SETTINGS_OF: dict[str, tuple[str, ...]] = {
    "barroom blues": ("settlement",), "dwarf hall": ("settlement", "heights"), "road camp": ("road", "woods"),
    "midnight ride": ("road",), "downpour run": ("road",), "field storm": ("fields",), "monsoon": ("woods", "water"),
    "witch storm": ("graves", "woods"),
    "hill country": ("heights", "road"), "harvest boogie": ("fields", "settlement"), "iron vow": ("heights",),
    "free company": ("road", "fields"),
    # The rest of Knight Rock's (2026-11-18: "make sure all our new location, song switch, signal stuff, persists across
    # all genres": 23 of its characters had no ground, so the player's preference for the piece written for the ground
    # underfoot never reached them).
    "open road": ("road", "fields"), "banner ride": ("road", "fields"), "black chapel": ("graves", "sacred"),
    "lantern walk": ("woods", "road"), "sand rider": ("wastes", "road"), "oasis shuffle": ("water", "wastes"),
    "jungle stomp": ("woods",), "forge anthem": ("works", "heights"), "moon glade": ("woods", "sacred"),
    "mountain stomp": ("heights",), "tavern rock": ("settlement",), "storm rider": ("road", "heights"),
    "battle cry": ("fields", "fort"), "war machine": ("works", "fort"), "dragon": ("heights", "ruins"),
    "night watch": ("fort", "settlement"), "deep mine": ("works",), "campfire": ("road", "woods"),
    "bayou boogie": ("water", "woods"), "sea dog": ("water",), "frost hammer": ("heights", "works"),
    "glow cave": ("water",), "low tunnel": ("works", "ruins"),
    # ...and the Warcraft characters that had none (the same day): the inns, caves, storms, fights, bosses and towns.
    "tavern": ("settlement",), "hearth": ("settlement",), "cavern": ("heights", "works"), "crystal cave": ("water", "sacred"),
    "tempest": ("fields", "heights"), "skirmish": ("fields", "road"), "warband": ("wastes", "fort"),
    "unquiet dead": ("graves", "ruins"), "titan": ("ruins", "heights"), "wild hunt": ("woods",), "blizzard": ("heights",),
    "dread lord": ("ruins", "graves"), "wild king": ("woods", "ruins"), "alliance town": ("settlement", "fort"),
    "town square": ("settlement",), "battleground": ("fields", "fort"), "siege line": ("fort", "fields"),
    "market square": ("settlement",), "royal march": ("settlement", "fort"), "warlord": ("fort", "ruins"), "banner war": ("fields", "fort"),
    "deep tide": ("water",), "fallen crusade": ("ruins", "sacred"), "bog beast": ("water",), "sea king": ("water",),
    "sea storm": ("water",), "frost wyrm": ("heights", "ruins"), "whiteout": ("heights",),
    "village dance": ("settlement", "fields"), "morning fields": ("fields",), "riverside waltz": ("water", "fields"),
    "long road home": ("road", "fields"), "highland reel": ("heights", "settlement"), "snowfall": ("heights", "woods"),
    "mountain pass": ("heights", "road"), "moorland ride": ("heights", "road"), "requiem": ("graves", "sacred"),
    "music box": ("ruins", "settlement"), "danse macabre": ("graves", "woods"), "moonlit graves": ("graves",),
    "caravan": ("road", "settlement"), "mirage": ("wastes",), "sun anvil": ("wastes", "heights"), "sandstorm ride": ("wastes", "road"),
    "canopy": ("woods",), "river spirits": ("water", "woods"), "prowl": ("woods",), "swamp fever": ("water", "woods"),
    "the forge": ("works",), "ash march": ("wastes", "road"), "embers": ("works", "settlement"), "lava fields": ("wastes",),
    "court dance": ("settlement", "fort"), "coronation": ("fort", "sacred"), "city gates": ("settlement", "fort"),
    "cathedral": ("sacred",), "moonwell": ("sacred", "water", "woods"), "fireflies": ("woods", "water"), "ancient ruins": ("ruins",),
    "twilight forest": ("woods",), "sea shanty": ("water", "settlement"), "elven hymn": ("sacred", "woods"),
    "dwarven hall": ("fort", "works", "heights"), "plague wind": ("fields", "ruins", "graves"), "oasis dance": ("water", "settlement"),
    "troll drums": ("woods", "ruins"), "frost giant": ("heights", "ruins"), "pilgrim road": ("road",), "forge song": ("works", "settlement"),
    "bazaar": ("settlement",), "drowned bell": ("water", "ruins"),
    "shadowed wood": ("woods",), "fallen farmstead": ("fields", "ruins"), "border keep": ("fort", "road"),
    "rain on the roof": ("settlement", "fields"), "forsaken parlour": ("ruins", "settlement"), "witch hollow": ("woods", "water"),
    "spirit grove": ("woods", "sacred"), "barrow kings": ("graves", "heights"), "cliffside wind": ("heights", "water"),
    "dark ritual": ("sacred",), "savanna": ("wastes", "fields"), "temple steps": ("sacred",), "night market": ("settlement",),
    "high pasture": ("heights", "fields"), "orchard morning": ("fields",), "sunset hills": ("heights", "fields"),
    "lakeside reverie": ("water",), "harvest home": ("fields", "settlement"),
    "frozen lake": ("water", "heights"), "snowbound pines": ("woods", "heights"), "misty lake": ("water",), "wisp wood": ("woods",),
    "dark road": ("road",), "buried tomb": ("ruins", "graves", "wastes"), "desert shrine": ("sacred", "wastes"),
    "jungle cliffs": ("heights", "woods", "water"), "jungle camp": ("settlement", "woods"), "jungle temple": ("sacred", "ruins"),
    "volcano peak": ("heights", "wastes"), "harbour town": ("water", "settlement"), "royal gardens": ("fields", "sacred"),
    "shadow glade": ("woods", "sacred"), "moon peak": ("heights", "sacred"), "flooded mill": ("water", "fields", "ruins"),
    "stone circle": ("sacred", "heights", "fields"),
    # The night is a place now ("night should feel like night"), and its music has its ground too.
    "lullaby": ("fields", "settlement"), "nocturne": ("woods", "graves"), "desert night": ("wastes",),
    "starlit meadow": ("fields", "heights"), "owl wood": ("woods",), "moonlit shore": ("water",), "village asleep": ("settlement",),
    "frost night": ("heights", "water"), "jungle night": ("woods", "water"), "grave watch": ("graves", "sacred"),
    "ember night": ("works", "wastes"), "moon choir": ("sacred", "woods"),
    # Caves and inns have their ground too ("Dont forget caves inns pvp ect"): a mine's music in a mine, a crypt's in a crypt.
    "old mine": ("works", "heights"), "kobold tunnels": ("works",), "crypt": ("graves", "sacred"), "sea grotto": ("water",),
    "lava tube": ("wastes", "works"), "bandit hideout": ("ruins", "road"), "frozen cavern": ("heights", "water"),
    "spider den": ("woods", "ruins"), "glowworm grotto": ("water", "woods"),
    "harbour saloon": ("water", "settlement"), "caravanserai": ("road", "wastes"), "lamplit inn": ("settlement", "graves"),
    "elven rest": ("woods", "sacred"), "drinking song": ("heights", "settlement"), "fireside": ("fields", "settlement"),
    # A camp is out of doors, so its ground counts as a walk's does (2026-11-17, with the second camps).
    "watchfire": ("fields", "road"), "still hunt": ("woods", "wastes"), "uneasy vigil": ("graves", "ruins"),
    "shepherds rest": ("fields", "heights"), "fen fire": ("water", "woods"), "oasis embers": ("wastes", "water", "road"),
    "crows rest": ("heights", "graves", "fields"),
    "bog lights": ("water", "woods"), "grey fen": ("water", "ruins"), "sea breeze": ("water", "settlement"), "salt road": ("water", "road", "heights"),
    "lighthouse": ("water",), "ice fields": ("heights", "fields"), "white waste": ("heights", "wastes"),
    "frog chorus": ("water", "woods"), "bog inn": ("water", "settlement"), "drowned grotto": ("water",), "reed fire": ("water", "fields"),
    "sailors rest": ("water", "settlement"), "tide cave": ("water",), "driftwood fire": ("water",), "aurora": ("heights", "fields"),
    "mead hall": ("heights", "settlement"), "ice cave": ("heights", "water"), "frost camp": ("heights",),
}


def settings_of(character: Character) -> tuple[str, ...]:
    return SETTINGS_OF.get(character.name, ())


# A rock band's lead plays the blues: the minor pentatonic of the key over its major chords, as the riff bands of the
# late seventies did (2026-11-16, night: "acdc for knight rock"). A note off it goes to the nearest note on it.
BLUES = (0, 3, 5, 7, 10)


def guitar_solo(rng: random.Random, tune: Line, bars: int, beats: float, pulse: float, bpm: float, chords: list[Chord],
                mode: str, low: int, high: int, two: bool = True) -> Line:
    """A guitar solo over `bars` bars, in scale steps of the key: sung, not shredded. ("i want fucking guitar solos in my
    knight rock, study eddie vedder and pearl jam"; of the first one, all runs and bends under a wah rocked from end to
    end: "all wammy no chill", "thats not a guitar solo thats a solo effect track", "do better", 2026-11-18.)

    The way Mike McCready plays a slow Pearl Jam song ("Yellow Ledbetter", after Hendrix's "Little Wing") and the way a
    singer phrases: sentences of two bars, each ending on a note held over its chord and a breath before the next. Its
    first words are the tune's own opening; they are answered, then carried higher; a held note is now and then doubled a
    third below; the figures grow shorter as it builds, one quick run near the top, the highest note held long, and the
    tune's opening again to come home on the key note. A note on a strong beat is a note of the chord under it. In the
    key's own five notes: the major pentatonic in a major key, the minor in a minor one. `low` and `high` are the lowest
    and highest steps the guitar should go to.

    Whoever leads the band takes it (MOST_SOLOS: a fiddle, a mandolin, a harmonica, a whistle as well as the lead guitar);
    `two` is whether that player can sound two notes at once (a whistle cannot: no double stops, octaves or doubled
    notes). Each solo is its own (ORIGINAL_SOLOS, 2026-11-19: "and they should be original each time"): its figures drawn
    from ten, where they fall among its sentences, and its own way through each figure."""
    bright = MODES[mode][2] == 4 and MODES[mode][1] == 2
    five = (0, 1, 2, 4, 5) if bright else (0, 2, 3, 4, 6)
    span = 2 * beats
    fast = 0.25 if bpm <= (150 if pulse == 1.0 else 120) else 0.5
    out: list[tuple[float, float, int, float]] = []

    def snap(step: int) -> int:
        for move in (0, -1, 1, -2, 2):
            if (step + move) % 7 in five:
                return step + move
        return step

    def up(step: int, count: int = 1) -> int:
        """The note of the five `count` notes above."""
        for _ in range(count):
            step += 1
            while step % 7 not in five:
                step += 1
        return step

    def down(step: int, count: int = 1) -> int:
        for _ in range(count):
            step -= 1
            while step % 7 not in five:
                step -= 1
        return step

    def chord_at(at: float) -> Chord:
        return chords[min(max(int(at // beats + 1e-6), 0), len(chords) - 1)]

    def tone(step: int, at: float, under: int | None = None) -> int:
        """The note of the chord sounding at `at` nearest to `step`, one of the five where one is (and none over `under`)."""
        held = {each % 7 for each in chord_at(at).steps}
        roof = min(high, under if under is not None else high)
        found = [each for each in range(step - 7, step + 5) if each % 7 in held and low <= each <= roof]
        found = [each for each in found if each % 7 in five] or found
        if not found:
            return snap(min(step, roof))
        return min(found, key=lambda each: (abs(each - step), each))

    def keep(step: int) -> int:
        while step > high:
            step -= 7
        while step < low:
            step += 7
        return step

    def fit(rhythm: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """A rhythm written for two bars of four, laid over two bars of this metre on its eighths."""
        scale = span / 8.0
        laid: list[tuple[float, float]] = []
        for at, length in rhythm:
            on = round(at * scale / 0.5) * 0.5
            if laid and on <= laid[-1][0]:
                continue
            laid.append((on, max(round(length * scale / 0.5) * 0.5, 0.5)))
        for index in range(len(laid) - 1):
            laid[index] = (laid[index][0], min(laid[index][1], laid[index + 1][0] - laid[index][0]))
        return laid

    def put(at: float, rhythm: list[tuple[float, float]], steps: list[int], weight: float, double: bool = False,
            breath: bool = True) -> None:
        """A sentence: its notes legato, its last held to leave a breath before the next. Before the peak nothing goes
        as high as it: a note that would is turned back under it."""
        before = None
        for index, ((on, length), step) in enumerate(zip(rhythm, steps)):
            last = index == len(rhythm) - 1
            if at + on < at_peak - 1e-6 and step > ceiling:
                if last:
                    step = tone(ceiling, at + on, ceiling)       # a held note stays a note of the chord
                else:
                    step = ceiling if before != ceiling else down(ceiling)
            before = step
            if last and breath:
                length = max(span - on - max(beats / 4, 0.5), 0.5)
            accent = 0.06 if (on % beats) < 1e-6 else 0.0
            out.append((at + on, length * (0.98 if last else 0.94), keep(step), min(weight + accent, 1.0)))
            if last and double:
                out.append((at + on, length * 0.98, keep(step) - 2, min(weight, 1.0) * 0.8))

    ordered = sorted(tune.notes)
    motif = [snap(step) for _, _, step, _ in ordered[:4]] or [0, 1, 2]
    while len(motif) < 4:
        motif.append(up(motif[-1]))
    # Where it sits: the octave of the tune's opening from which the solo's top (an octave and a note above it) comes
    # nearest the top of the guitar's neck, where a solo sings; never so high that it begins up there.
    def top_from(start: int) -> int:
        found = up(start, 6)
        while found > high:
            found = down(found)
        return found
    starts = [motif[0] + 7 * octave for octave in range(-3, 4) if low + 1 <= motif[0] + 7 * octave <= high - 6]
    start = max(starts, key=lambda each: (top_from(each), -each)) if starts else keep(motif[0])
    motif = [step + start - motif[0] for step in motif]
    base = motif[0]
    phrases = max(bars // 2, 2)
    middle = ["carry", "double", "build", "run"]
    while len(middle) < phrases - 4:
        middle.insert(2, "carry")
    kinds = (["call", "answer"] + middle[:max(phrases - 4, 0)] + ["peak", "home"]) if phrases >= 4 else ["call", "home"]
    ways = {"repeat": "under", "sequence": "down 3", "trill": 1, "cascade": "down", "pedal": "top", "stops": "up", "echo": 1,
            "stutter": (3, 3, 2), "call": 0}
    if ANGUS and phrases >= 4 and ORIGINAL_SOLOS:
        # (2026-11-19, 13:15: "most songs should have solos", "and they should be original each time".) Three figures drawn
        # from ten, one of them at least a riff of quick notes (the repeated note, the run, the trill, the cascade); where they
        # fall among the sung sentences: after the call and its answer, first of all, between the call and its answer, or
        # with the call carried higher between them; and each figure's own way: the run in threes or in fours, down the five
        # or up it; the trill a step wide or a third; the pedal over its line or under it; the cascade falling or climbing;
        # the double stops climbing or falling; the repeated note against the note under it or over it; the echo a step
        # lower each beat or two; the push 3+3+2 or 3+2+3; and the call's own rhythm.
        if ANGUS_MORE:
            riffs = [kind for kind in ANGUS_FIGURES if two or kind != "stops"]
            rng.shuffle(riffs)
            form = rng.choice(("riff first", "answered"))
        else:
            riffs = [kind for kind in SOLO_FIGURES if two or kind not in ("stops", "octaves")]
            rng.shuffle(riffs)
            if not any(kind in RIFFY for kind in riffs[:3]):
                found = next(index for index, kind in enumerate(riffs) if kind in RIFFY)
                riffs[2], riffs[found] = riffs[found], riffs[2]
            form = rng.choice(("sung", "riff first", "answered", "climbing"))
        ways = {"repeat": rng.choice(("under", "over")), "sequence": rng.choice(("down 3", "down 4", "up 3", "up 4")),
                "trill": rng.choice((1, 2)), "cascade": rng.choice(("down", "up")), "pedal": rng.choice(("top", "bottom")),
                "stops": rng.choice(("up", "down")), "echo": rng.choice((1, 2)), "stutter": rng.choice(((3, 3, 2), (3, 2, 3))),
                "call": rng.randrange(3)}
        if phrases >= 8:
            if ANGUS_MORE:
                # Four of his riffs among the eight sentences, the call before them or between the first two.
                middle = {"riff first": [riffs[0], "call", riffs[1], riffs[2], riffs[3], "run"],
                          "answered": ["call", riffs[0], riffs[1], riffs[2], riffs[3], "run"]}[form]
            else:
                middle = {"sung": ["call", "answer", riffs[0], riffs[1], riffs[2], "run"],
                          "riff first": [riffs[0], "call", riffs[1], "answer", riffs[2], "run"],
                          "answered": ["call", riffs[0], "answer", riffs[1], riffs[2], "run"],
                          "climbing": ["call", riffs[0], "carry", riffs[1], riffs[2], "run"]}[form]
            extra = 4 if ANGUS_MORE else 3
            while len(middle) < phrases - 2:
                middle.insert(len(middle) - 1, riffs[extra % len(riffs)])        # a longer solo draws more of them
                extra += 1
            kinds = middle[:phrases - 2] + ["peak", "home"]
        elif phrases >= 6:
            middle = {"sung": ["call", "answer", riffs[0]], "riff first": [riffs[0], "call", riffs[1]],
                      "answered": ["call", riffs[0], "answer"], "climbing": ["call", riffs[0], "carry"]}[form]
            kinds = middle + ["carry"] * (phrases - 6) + ["run", "peak", "home"]
        else:
            # An eight-bar solo: one figure or two before its peak.
            kinds = {"sung": ["call", riffs[0]], "riff first": [riffs[0], "call"], "answered": [riffs[0], riffs[1]],
                     "climbing": [riffs[0], "carry"]}[form] + ["peak", "home"]
    elif ANGUS and phrases >= 4:
        # (2026-11-19: "couldnt you do more complex riffs in the solo part like angus".) The middle of the solo riffs: two of
        # Angus Young's figures, drawn for this solo (the repeated note, the run down in threes, the trill, Chuck Berry's
        # double stops), a sung sentence between them, and the quick run up to the peak; the call, the peak and the way
        # home are still sung. A short solo trades its answer for one riff.
        riffs = [kind for kind in ("repeat", "sequence", "trill", "stops", "cascade", "pedal") if two or kind != "stops"]
        rng.shuffle(riffs)
        if phrases >= 8:
            # (2026-11-19, 12:05: "angus solo sounds pretty good iterate on those".) Three of his figures in a row, then the
            # run to the peak: the call, the answer, the peak and the way home are still sung.
            middle = [riffs[0], riffs[1], riffs[2], "run"]
            while len(middle) < phrases - 4:
                middle.insert(2, riffs[2 + len(middle) % 2])
            kinds = ["call", "answer"] + middle[:phrases - 4] + ["peak", "home"]
        elif phrases >= 6:
            kinds = ["call", "answer", riffs[0]] + ["carry"] * (phrases - 6) + ["run", "peak", "home"]
        else:
            kinds = ["call", riffs[0], "peak", "home"]
    # The top of the solo: an octave and a note over where it began, as high as the guitar should go.
    top = up(base, 6)
    while top > high:
        top = down(top)
    # The peak is the highest note of the chord under it, and nothing before it goes as high.
    at_peak = kinds.index("peak") * span if "peak" in kinds else 0.0
    held_there = {each % 7 for each in chord_at(at_peak).steps}
    peak_note = max((each for each in range(top - 6, top + 1) if each % 7 in held_there and each % 7 in five), default=top)
    if SOLO_PEAK_NEAR_TOP:
        near = [each for each in range(top - 6, min(top + 2, high) + 1) if each % 7 in held_there and each % 7 in five]
        peak_note = min(near, key=lambda each: (abs(each - top), -each)) if near else top
    ceiling = down(peak_note)
    for index, kind in enumerate(kinds):
        at = index * span
        along = index / max(len(kinds) - 1, 1)
        weight = 0.72 + 0.26 * along
        second = at + beats                                  # the second bar's downbeat
        begun = len(out)                                     # where this sentence's notes begin (ANGUS_MORE, below)
        if kind == "call":
            # The tune's own opening, sung, from the band's stop chord on: its last note held over the chord. (Each solo its
            # own rhythm for it: as the tune has it, from a pickup, or pushed.)
            rhythm = fit(([(0.0, 1.5), (1.5, 0.5), (2.0, 0.5), (2.5, 1.5), (4.0, 3.0)],
                          [(0.5, 0.5), (1.0, 1.0), (2.0, 0.5), (2.5, 1.5), (4.0, 3.0)],
                          [(0.0, 1.0), (1.0, 0.5), (1.5, 1.0), (2.5, 1.5), (4.0, 3.0)])[ways["call"]])
            steps = motif[:len(rhythm) - 1] + [tone(motif[min(3, len(motif) - 1)], second, ceiling)]
            put(at, rhythm, steps, weight)
        elif kind == "answer":
            # The same words again, then turned upwards to another note of the chord.
            rhythm = fit([(0.0, 0.5), (0.5, 0.5), (1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (4.0, 3.0)])
            turn = up(motif[2])
            steps = [motif[0], motif[1], motif[2], turn, motif[2]][:len(rhythm) - 1]
            steps.append(tone(up(turn), second, ceiling))
            put(at, rhythm, steps, weight)
        elif kind == "carry":
            # Carried higher: up the five in eighths, over the top by a note, and down onto the chord.
            start = min(up(base, 1 + index % 2), down(ceiling, 4))
            rhythm = fit([(0.0, 0.5), (0.5, 0.5), (1.0, 0.5), (1.5, 0.5), (2.0, 1.0), (3.0, 1.0), (4.0, 3.0)])
            steps = [start, up(start), up(start, 2), up(start, 3), up(start, 4), up(start, 3)][:len(rhythm) - 1]
            steps.append(tone(up(start, 2), second))
            put(at, rhythm, steps, weight)
        elif kind == "double":
            # A turn about a note, and the held note doubled a third below.
            start = min(up(base, 3), down(ceiling, 1))
            rhythm = fit([(0.5, 0.5), (1.0, 0.5), (1.5, 1.0), (2.5, 0.5), (3.0, 1.0), (4.0, 3.0)])
            steps = [start, up(start), start, down(start), start][:len(rhythm) - 1]
            steps.append(tone(up(start), second))
            put(at, rhythm, steps, weight, double=two)
        elif kind == "build":
            # Two bars of one short figure, the second a note higher each time: da-da-DUM, and on.
            for half in range(2):
                bar_at = at + half * beats
                figure = fit([(0.0, 0.5), (0.5, 0.5), (1.0, 1.5), (2.5, 0.5), (3.0, 0.5), (3.5, 0.5)])
                figure = [(on, length) for on, length in figure if on < beats - 1e-6]
                rise = min(up(base, 3 + half), down(ceiling, 3 - half))
                dum = tone(up(rise, 2), bar_at)
                if dum <= up(rise):
                    dum = up(rise, 2)                            # the long note always a step on, not struck again
                notes = [rise, up(rise), dum, up(rise), up(rise, 2), up(rise, 3)]
                notes = [min(step, ceiling) for step in notes]
                for place in range(1, len(notes)):
                    if notes[place] == notes[place - 1] == ceiling:
                        notes[place] = down(ceiling)          # turned back at the ceiling, not struck again
                for (on, length), step in zip(figure, notes):
                    out.append((bar_at + on, length * 0.94, keep(step), min(weight + (0.06 if on == 0 else 0.0), 1.0)))
        elif kind == "repeat":
            # Angus's repeated note: a high note of the chord picked against the note under it, fast, then held; the second
            # bar a note higher, half as long, and a note of the chord held into the breath.
            over = ways["repeat"] == "over"                     # (against the note over it: from a note further down)

            def other(step: int) -> int:
                # Against the note over it or under it; at the ceiling, under it: never the same note twice over.
                found = min(up(step), ceiling) if over else down(step)
                return found if found != step else down(step)
            high_note = tone(down(ceiling, 2 if over else 1), at, ceiling)
            count = max(int(round((beats - 1.0) / fast)), 2)
            rhythm = [(each * fast, fast) for each in range(count)] + [(count * fast, beats - count * fast)]
            steps = [high_note if each % 2 == 0 else other(high_note) for each in range(count)] + [high_note]
            upper = min(tone(up(high_note), second, ceiling), ceiling)
            if upper == high_note:
                upper = min(up(high_note), ceiling) if up(high_note) <= ceiling else down(high_note)   # it moves, a note on
            again = max(int(round(beats / 2 / fast)), 2)
            rhythm += [(beats + each * fast, fast) for each in range(again)] + [(beats + again * fast, 1.0)]
            steps += [upper if each % 2 == 0 else other(upper) for each in range(again)] + [tone(upper, second + again * fast, ceiling)]
            put(at, rhythm, steps, weight)
        elif kind == "sequence":
            # A run down the five in threes (a note and the two under it, then the same from the note under it), fast for a
            # bar, onto a note of the chord held through the second.
            # (Each solo its own: in threes or in fours, down the five or up it from lower down.)
            group = int(ways["sequence"][-1])
            move = up if ways["sequence"].startswith("up") else down
            head = tone(down(ceiling, 2 * group) if move is up else down(ceiling), at, ceiling)
            count = max(int(round(beats / fast)), group)
            steps = []
            while len(steps) < count:
                steps += [move(head, each) for each in range(group)]
                head = move(head)
            steps = steps[:count]
            rhythm = [(each * fast, fast) for each in range(count)] + [(beats, beats)]
            steps.append(tone(move(steps[-1]), second, ceiling))
            put(at, rhythm, steps, weight)
        elif kind == "trill":
            # A trill, hammered on and pulled off between a note of the chord and the note over it for a bar, then a fall by
            # step onto the chord.
            width = ways["trill"]                               # (a step wide, or a third)
            note = tone(down(ceiling, 1 + width), at, ceiling)
            count = max(int(round(beats / fast)), 2)
            rhythm = [(each * fast, fast) for each in range(count)] + [(beats, 0.5), (beats + 0.5, 0.5), (beats + 1.0, 1.0)]
            steps = [note if each % 2 == 0 else min(up(note, width), ceiling) for each in range(count)]
            steps += [down(note), down(note, 2), tone(down(note, 3), second + 1.0, ceiling)]
            put(at, rhythm, steps, weight)
        elif kind == "stops":
            # Double stops, as Chuck Berry played them and Angus plays them: two notes struck together on each beat and
            # off-beat, a note higher every two, then the top pair held with its third under it.
            falling = ways["stops"] == "down"                   # (or from high, falling a note every two)
            under = tone(down(ceiling, 1 if falling else 4), at, ceiling)
            hits = max(int(round(beats / 0.5)), 2)
            for each in range(hits):
                note = down(under, each // 2) if falling else min(up(under, each // 2), ceiling)
                for pair, step in enumerate((note, down(note))):
                    if not (at + each * 0.5 < at_peak and step > ceiling):
                        out.append((at + each * 0.5, 0.42, keep(step), min(weight + (0.06 if each % 2 == 0 else 0.0), 1.0) * (1.0 if pair == 0 else 0.85)))
            last_pair = down(under, hits // 2) if falling else min(up(under, hits // 2), ceiling)
            put(at, [(beats, beats)], [tone(last_pair, second, ceiling)], weight, double=True)
        elif kind == "cascade":
            # Angus's run down from the top in triplets: a note of the chord and the two under it, then the same from the note
            # under it, three to the beat (two in a fast or compound bar) for a bar, onto a note of the chord held.
            step = 1.0 / 3.0 if pulse == 1.0 and bpm <= 150 else 2.0 / 3.0 if pulse == 1.0 else pulse / 2.0
            move = up if ways["cascade"] == "up" else down        # (or climbing to the top from under it)
            head = tone(down(ceiling, 7) if move is up else down(ceiling), at, ceiling)
            count = max(int(round(beats / step)), 3)
            steps = []
            while len(steps) < count:
                steps += [head, move(head), move(head, 2)]
                head = move(head)
            steps = steps[:count]
            rhythm = [(each * step, step) for each in range(count)] + [(beats, beats)]
            steps.append(tone(move(steps[-1]), second, ceiling))
            put(at, rhythm, steps, weight)
        elif kind == "pedal":
            # The pedal lick (Chuck Berry's, and Angus's): a high note of the chord picked again and again, a line falling under
            # it between the picks, fast, for a bar; then the line's last note held.
            count = max(int(round(beats / fast)) // 2 * 2, 2)
            if ways["pedal"] == "top":
                top_note = tone(down(ceiling), at, ceiling)
                steps = [top_note if each % 2 == 0 else down(top_note, 1 + each // 2) for each in range(count)]
                steps.append(tone(down(top_note, 1 + count // 2), second, ceiling))
            else:
                # Under it: a low note of the chord picked again and again, a line climbing over it between the picks.
                bottom = tone(down(ceiling, 7), at, ceiling)
                steps = [bottom if each % 2 == 0 else min(up(bottom, 1 + each // 2), ceiling) for each in range(count)]
                steps.append(tone(min(up(bottom, 1 + count // 2), ceiling), second, ceiling))
            rhythm = [(each * fast, fast) for each in range(count)] + [(beats, beats)]
            put(at, rhythm, steps, weight)
        elif kind == "octaves":
            # The tune's opening in octaves, as Wes Montgomery and Hendrix play a line: each note with the one an octave
            # under it, its last held.
            rhythm = fit([(0.0, 1.0), (1.0, 1.0), (2.0, 0.5), (2.5, 1.5), (4.0, 3.0)])
            line = [min(step, ceiling) for step in motif[:len(rhythm) - 1]] + [tone(motif[1], second, ceiling)]
            begun = len(out)
            put(at, rhythm, line, weight)
            for start_at, length, step, loud in out[begun:]:
                if step - 7 >= low:
                    out.append((start_at, length, step - 7, loud * 0.85))
        elif kind == "echo":
            # A figure of a beat, echoed: quick notes about a note of the chord (on it, under it, on it, over it), the same a
            # step lower each beat (or two), and the last held through the second bar.
            shape = (0, -1, 0, 1) if fast <= 0.25 else (0, -1)
            head = tone(down(ceiling), at, ceiling)
            rhythm, steps = [], []
            count = max(int(beats + 1e-6), 1)
            for beat in range(count):
                centre = down(head, beat * ways["echo"])
                for index, near in enumerate(shape):
                    rhythm.append((beat + index * fast, fast))
                    steps.append(up(centre, near) if near > 0 else down(centre, -near))
            rhythm.append((beats, beats))
            steps.append(tone(down(head, count * ways["echo"]), second, ceiling))
            put(at, rhythm, steps, weight)
        elif kind == "stutter":
            # One note picked in threes against the beat (3+3+2 sixteenths, or 3+2+3: the push rock drives on), every other
            # stroke a note higher, across a bar; then a note of the chord held.
            note = tone(down(ceiling, 2), at, ceiling)
            rhythm, steps, on, stroke = [], [], 0.0, 0
            while on < beats - 1e-6:
                for size in ways["stutter"]:
                    if on >= beats - 1e-6:
                        break
                    rhythm.append((on, min(size * fast, beats - on)))
                    steps.append(note if stroke % 2 == 0 else min(up(note), ceiling))
                    on += size * fast
                    stroke += 1
            rhythm.append((beats, beats))
            steps.append(tone(up(note), second, ceiling))
            put(at, rhythm, steps, weight)
        elif kind == "slide":
            # Two long notes, each slid onto from three notes under it, quick, as a fiddler or a slide guitar comes onto a
            # note: the first a note of the chord, the second higher.
            grace = max(fast / 2, 0.125)
            rhythm, steps = [], []
            for half in range(2):
                goal = tone(down(ceiling, 3 - 2 * half), at + half * beats, ceiling)
                for each in range(3):
                    rhythm.append((half * beats + each * grace, grace))
                    steps.append(down(goal, 3 - each))
                rhythm.append((half * beats + 3 * grace, beats - 3 * grace))
                steps.append(goal)
            put(at, rhythm, steps, weight)
        elif kind == "run":
            # The one quick run, up to a note under the top, held; then down by step onto the chord.
            peak = ceiling
            count = min(int(round(beats / 2 / fast)), 6)
            notes = [down(peak, count - each) for each in range(count)]
            for each, step in enumerate(notes):
                out.append((at + each * fast, fast * 0.95, keep(step), min(weight + 0.04 * each / max(count, 1), 1.0)))
            hold = count * fast
            rhythm = [(hold, beats - hold), (beats, 1.0), (beats + 1.0, 0.5), (beats + 1.5, 0.5)]
            steps = [peak, down(peak), down(peak, 2), tone(down(peak, 3), second + 1.5)]
            put(at, rhythm, steps, weight)
        elif kind == "peak":
            # The top: the highest note of the chord held long, then down by step to the chord.
            peak = peak_note
            rhythm = fit([(0.0, 3.0), (3.0, 0.5), (3.5, 0.5), (4.0, 0.5), (4.5, 0.5), (5.0, 2.0)])
            steps = [peak] + [down(peak, each) for each in range(1, len(rhythm) - 1)]
            steps.append(tone(down(steps[-1]), second + 1.0))
            put(at, rhythm, steps, 1.0)
        else:
            # Home: the tune's opening once more, slower, to the key note held.
            rhythm = fit([(0.0, 1.0), (1.0, 1.0), (2.0, 2.0), (4.0, 3.0)])
            steps = motif[:len(rhythm) - 1]
            home = keep(0) if abs(keep(0) - steps[-1]) <= abs(keep(7) - steps[-1]) else keep(7)
            steps.append(home)
            put(at, rhythm, steps, 0.85)
        if ANGUS_MORE and kind in ANGUS_FIGURES:
            # The lick again, a note higher (ANGUS_MORE): the riff's first bar laid over the first half of its second a note
            # up, no higher than the ceiling before the peak, landing on a note of the chord held a beat, and a breath of a
            # beat before the next sentence (a sentence breathes, as the sung solo of 11-18 does).
            lick = [note for note in out[begun:] if note[0] < second - 1e-6]
            if lick:
                del out[begun:]
                out.extend(lick)
                land = at + span - min(2.0, beats / 2)
                last = None
                for start_at, length, step, loud in lick:
                    on = start_at + beats
                    if on >= land - 1e-6:
                        continue
                    moved = up(step)
                    if on < at_peak - 1e-6 and moved > ceiling:
                        moved = ceiling
                    out.append((on, min(length, land - on), keep(moved), loud))
                    last = moved
                if last is not None:
                    out.append((land, min(2.0, beats / 2) * 0.5, keep(tone(last, land, ceiling)), min(weight + 0.06, 1.0)))
    out.sort()
    return Line(out)


def blues(pitch: int, tonic: int) -> int:
    for move in (0, -1, 1, -2, 2):
        if (pitch + move - tonic) % 12 in BLUES:
            return pitch + move
    return pitch


# The small percussion: what may join a theme the second time round without crowding it.
SMALL = ("tamb", "shake", "jingle", "ting", "tick", "high", "clack", "conga", "conga low", "block", "block low", "guiro", "hat", "castanet", "bell")
# Who doubles the bass line an octave away, by who has it: the neighbour in the orchestra, played the same way.
PARTNERS = {"basses": "celli", "basses slow": "celli slow", "basses pizz": "celli pizz", "celli": "basses", "celli slow": "basses slow",
            "celli pizz": "basses pizz", "acoustic bass": "celli pizz", "fretless": "celli pizz", "tuba": "basses", "bassoon": "basses pizz"}
# (2026-11-19, the study: Stained Glass Choir's organ played its bass line from A2 to F#4, median A3, a tenor's line, and the
# desk raised it 8.9 dB to its place: 7 dB over the liked stems in the mids and 16 at the top, with nothing under it. A bass
# line is centred on its instrument's home less 5, and the organ's home is middle C and the harp's E4, where they play as a
# pad and a pluck.) No bass line is centred above A2: an organ plays its bass on the pedals, a harp on its low strings.
# None: the instrument's home less 5, as before.
BASS_TOP: int | None = 45


# (2026-11-20, the study: Blood Machine I's bass, in Eb phrygian, played its key note on Eb2 and every other root under it,
# the bII on the low E, E1, a major seventh down where the phrygian half step should be: the key note nearest the bass's
# centre, Eb1, is under the bass's lowest string, and it alone was lifted. And in 18 of Knight's 71 parts that go up a key,
# most of them the climb to the summit, the bass went down about a seventh, its key note again the one nearest the centre:
# Frost Hammer's climb, C# phrygian to E, C#2 to E1.)
BASS_FOLLOWS_KEY = True  # each part's key note for the bass is the one nearest the part before's, in the instrument's range


def bass_tonics(spans: list, inst: "Instrument", centre: int) -> list[int]:
    """The bass's key note in each part of a take's story (`Take.spans`): the first nearest the bass's centre, each other the
    one nearest the part before's, so that a key a step up is a step up; moved by octaves into the instrument's range,
    with room for the scale over it (BASS_FOLLOWS_KEY). Off, each is the key note nearest the centre, as it was."""
    out: list[int] = []
    for _, _, key, _ in spans:
        if not BASS_FOLLOWS_KEY:
            out.append(key.home(centre))
            continue
        tonic = key.home(centre if not out else out[-1])
        while tonic < inst.low:
            tonic += 12
        while tonic + 11 > inst.high and tonic - 12 >= inst.low:
            tonic -= 12
        out.append(tonic)
    return out


def bass_centre(inst: Instrument) -> int:
    """Where a bass line is centred: its instrument's home less 5, never above BASS_TOP."""
    home = inst.home - 5
    return home if BASS_TOP is None else min(home, BASS_TOP)


# How the bass plays the second time round a theme, by how it played the first.
BUSIER = {"long": "two", "two": "walk", "walk": "two"}
# A light band's bass after its solo, in the last chorus: one step more drive (Take.after_solo); the octaves stay, the most a
# light band's bass drives (2026-11-20, the judges: Lazy River Sway I's shuffle, its octave bass made a walk for the last
# chorus, fell 0.46 on TuneJury with no brief there, where Anchor Dog V's walk made octaves held level).
LAST_CHORUS = {"long": "two", "two": "walk", "walk": "oct"}
# Who doubles a tune an octave above it rather than where the tune is: high woodwinds and bells.
HIGH = ("flute", "piccolo", "whistle", "recorder", "ocarina", "pan flute", "glock", "celesta", "xylophone")
# The orchestra's own low drums: what the war drums stand in for while they play.
LOW = ("boom", "great drum", "taiko", "deep")
# A drummer fills with what is not keeping time (2026-11-20, the study: Downpour Surge II's summit the same 19 bars, its groove
# "tom rock", the mid tom on the eighths and the low tom on the beat, and its fill every eight bars four sixteenths of the low
# tom, the drum already playing the beat; the fill vanished into the groove and the summit's phrases went unmarked). On a
# groove of the toms the pickups and fills go on the snare; the long roll up to the summit stays on the low tom, the thunder.
TOM_FILLS_ON_SNARE = True


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
        self.rng = random.Random(fam.seed * 9973 + take * 7919 + 5)    # the cast and the lead's: the tunes are drawn first from it
        self._streams: dict[str, random.Random] = {}
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
        self.soloed = False             # whether the lead guitar takes a solo at the summit (see lead)
        self.solo_bars = 0              # how many of the summit's first bars the solo takes
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
        for write in (self.lead, self.answer, self.make_room, self.texture, self.rhythm, self.bass, self.drums, self.war_drums, self.marks,
                      self.breathe, self.effects):
            write()

    def own(self, what: str) -> random.Random:
        """A writer's own generator (2026-11-19, the judges: the rhythm guitar, the bass and the drums drew from the lead's,
        after it, and each instrument's place too as it was first played, so that a change to the close or a part brought in
        anywhere drew every later riff and groove of the take anew, and a change's before and after were two takes). The cast
        and the lead keep the take's; each other writer that draws has its own, the same one however often it is asked for."""
        if what not in self._streams:
            self._streams[what] = random.Random("%s/%d/%d" % (what, self.fam.seed, self.take))
        return self._streams[what]

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
        # (2026-11-17, evening, played: "just a bit light and wimpy in general", "dont hear much war drums", "in all genres".
        # Lively walking music of some weight has them too, softer (`soft_war`): not a dance, nor a hymn or a morning.)
        # (And from 21:50 the rhythmic lighter music a little lighter and calmer than that too, so long as its grooves are not
        # all the delicate ones (a music box, fireflies, rain on the roof keep none): "go a little harder this is not world
        # of fairy craft".)
        # (2026-11-18, "i hope you have been working on those war drums", "its okay if some light pieces dont": of the
        # lighter walking music only one take in thirty-five had them; the slower of it, busy from 0.35 (a snowfall, a
        # mirage, a frozen lake, a desert shrine, the ice fields), has them too now. Dances and the most delicate still
        # go without.)
        lively = walk and ((ch.weight >= 0.6 and ch.busy >= 0.55) or (ch.weight >= 0.5 and ch.busy >= 0.35 and not set(ch.grooves) <= set(DELICATE))) \
            and not set(ch.grooves) & set(DANCE_GROOVES)
        self.has_war = self.fight or (walk and self.heavy) or lively
        self.soft_war = self.has_war and not self.fight and not self.heavy
        self.has_frames = not ch.band and (self.has_war or (walk and ch.weight >= 0.6 and hand))
        self.hand = hand                                         # hand drums go under its second theme
        self.forge = (walk or self.fight) and any("anvil" in name for name in ch.grooves)   # the "ting" of its groove is an anvil
        self.embers = self.has_war and not ch.band and not self.forge and len(ch.kinds) < len(KINDS_ALL) and "infernal" in ch.kinds
        self.has_swell = self.fight or (walk and ch.weight >= 0.6)
        self.has_gong = self.has_war and not ch.band and ch.weight >= 0.9
        # The colours of Muse Percussion (2026-11-17, night: "Use more instruments get everything out of muse"): what an
        # orchestra's percussion section adds where the music is grim, light, regal, fiery or a storm.
        kinds = set(ch.kinds) if len(ch.kinds) < len(KINDS_ALL) else set()
        self.tam_tam = not ch.band and ((self.heavy and (bool(kinds & {"haunted", "infernal"}) or ch.role == "boss"))
                                        or (ch.role == "depths" and not ch.light))
        self.tree = not ch.band and (ch.light or "mystic" in kinds) and ch.role not in FIGHTS
        self.soft_roll = not ch.band and not self.has_swell and ch.role in ("wander", "night", "town", "ember", "camp") and ch.weight >= 0.4
        self.field = not ch.band and ch.role in ("wander", "town", "battleground", "battle", "boss") and \
            ("regal" in kinds or ch.role == "battleground" or "march" in ch.grooves)
        self.taikos = not ch.band and self.heavy and (bool(kinds & {"jungle", "infernal", "desert"}) or ch.role in ("battle", "boss", "battleground"))
        self.rumble = not ch.band and ch.role == "storm"
        self.grim = not ch.band and not ch.light and (bool(kinds & {"haunted", "infernal"}) or ch.role in ("boss", "depths"))

    def voice(self, channel: str, name: str, tag: str = "") -> Voice:
        have = self.voices[channel]
        if name + tag not in have:
            # Where it sits is drawn from its own name, so that a part brought in anywhere moves no one else's draws.
            place = random.Random("pan/%d/%d/%s" % (self.fam.seed, self.take, name + tag))
            have[name + tag] = Voice(shift=INSTRUMENTS[name].early, pan=place.uniform(-0.35, 0.35), instrument=name)
        return have[name + tag]

    def kit(self) -> Voice:
        have = self.voices["drums"]
        if "kit" not in have:
            have["kit"] = Voice(drums=True, instrument="kit " + self.ch.kit)
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
        return min(max(0.16 + 0.8 * level * weight, 0.05), 1.0)          # pianissimo to fortissimo ("more dynamic")

    def fit(self, line: Line, chord: Chord, aim: float = 0.0) -> Line:
        """A fragment of a tune moved bodily so that it begins on a note of a chord, as near
        to `aim` scale steps away as it can."""
        first = line.notes[0][2]
        notes = {step % 7 for step in chord.steps}
        moves = [move for move in range(-9, 10) if (first + move) % 7 in notes]
        return line.moved(steps=min(moves, key=lambda move: abs(move - aim)))

    def sing(self, channel: str, name: str, line: Line, at: float, key: Key, chords: list[Chord], first: float,
             loud: float = 1.0, octave: int = 0, tag: str = "", even: float = 0.0) -> None:
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
        placed = []
        for (start, length, _, weight), pitch in zip(line.notes, pitches):
            pitch += shift
            # A line wider than the instrument: the notes it cannot reach come an octave in.
            while pitch > inst.high:
                pitch -= 12
            while pitch < inst.low:
                pitch += 12
            # `even`: how far the line keeps its strength from note to note (at the big moments the tune does not dip
            # to mezzo-forte between its accents).
            weight = weight + (1.0 - weight) * even
            if self.ch.band and name == "lead guitar" and tag != " solo":
                pitch = blues(pitch, key.tonic)
            placed.append([at + start, length * (0.96 if inst.held else 1.0), pitch, min(weight * loud, 1.0)])
        for start, length, pitch, weight in placed:
            self.voice(channel, name, tag).add(start, length, pitch, weight)

    def answer(self) -> None:
        """A band's lead guitar answers its own long notes (LEAD_ANSWERS, `_answered`), over its whole part once it is written,
        so that a phrase's held last note can run into the next phrase."""
        if not (LEAD_ANSWERS and self.ch.band):
            return
        voice = self.voices["lead"].get("lead guitar")
        if voice is None or not voice.notes:
            return
        from .score import Note
        ordered = sorted(voice.notes, key=lambda note: (note.start, note.pitch))
        def key_at(at: float) -> Key:
            found = self.spans[0][2]
            for section, first, key, _ in self.spans:
                if first <= at + 1e-6:
                    found = key
            return found
        head = self._theme_head(ordered) if ANSWERS_SING_THE_THEME else None
        placed = self._answered([[note.start, note.length, note.pitch, note.loud] for note in ordered], key_at, INSTRUMENTS["lead guitar"],
                                head)
        voice.notes = [Note(start, length, pitch, loud) for start, length, pitch, loud in placed]

    def _theme_head(self, ordered: list) -> list[int] | None:
        """The first theme's opening on the lead guitar: the pitches of its first four notes (one to an onset), or None where
        the song has no first theme or its lead plays fewer than four notes there."""
        for section, first, _, _ in self.spans:
            if section.part == "first":
                end = first + section.bars * self.beats
                onsets: dict[float, int] = {}
                for note in ordered:
                    if first - 1e-6 <= note.start < end:
                        onsets.setdefault(round(note.start, 4), note.pitch)
                head = [onsets[at] for at in sorted(onsets)][:4]
                return head if len(head) == 4 and len(set(head)) > 1 else None
        return None

    def _answered(self, placed: list, key_at, inst, head: list[int] | None = None) -> list:
        """A band's lead guitar answers its own long notes (2026-11-19: "still need more complex leads and riffs"): where the
        tune holds a note two and a half beats or more and its next phrase begins within two and a half beats of the hold's
        end, the breath between them takes a run into the next phrase's first note, four quick notes of the blues scale
        (the minor pentatonic) climbing or falling to it, ending as that note begins; the held note keeps a beat and a half
        at least. Every other long note, so the tune still sings.

        With the first theme's opening (`head`, ANSWERS_SING_THE_THEME; 2026-11-19, the judges: SongEval's coherence and
        musicality fell with the answers' scale runs, figures that are no part of the song): the run is that opening's shape
        on the same ladder of the blues scale, quick, set so that its last note is the step beside the next phrase's first,
        approached the way the opening's own last move goes. Where it would leap more than a sixth from the held note or
        leave the guitar's range, the scale run is played."""
        fast = 0.25 if self.fam.bpm <= 150 else 0.5
        count = int(round(1.0 / fast))
        out, answered = [], 0
        for index, (start, length, pitch, weight) in enumerate(placed):
            following = placed[index + 1] if index + 1 < len(placed) else None
            if following is None or length < 2.5 or following[0] - (start + length) > 2.5 or following[0] <= start:
                out.append([start, length, pitch, weight])
                continue
            answered += 1
            begin = following[0] - count * fast
            if answered % 2 == 0 or begin < start + 1.5:
                out.append([start, length, pitch, weight])
                continue
            goal = following[2]
            scale = sorted({key_at(start).tonic + 12 * octave + step for octave in range(1, 9) for step in BLUES})
            sung = self._head_run(head, scale, pitch, goal, count) if head else None
            if sung and all(inst.low <= note <= inst.high for note in sung):
                out.append([start, min(length, begin - start - 0.04), pitch, weight])
                for each, note in enumerate(sung):
                    out.append([begin + each * fast, fast * 0.92, note, min(weight * (0.82 + 0.04 * each), 1.0)])
                continue
            if goal >= pitch:
                run = [note for note in scale if pitch < note < goal][-count:]
                while len(run) < count:
                    run.insert(0, max([note for note in scale if note < (run[0] if run else goal)], default=goal - 3))
            else:
                run = [note for note in scale if goal < note < pitch][::-1][-count:]
                while len(run) < count:
                    run.insert(0, min([note for note in scale if note > (run[0] if run else goal)], default=goal + 3))
            if any(note < inst.low or note > inst.high for note in run):
                out.append([start, length, pitch, weight])
                continue
            out.append([start, min(length, begin - start - 0.04), pitch, weight])
            for each, note in enumerate(run):
                out.append([begin + each * fast, fast * 0.92, note, min(weight * (0.82 + 0.04 * each), 1.0)])
        return out

    def _rubs(self, at: float, length: float, shape: tuple) -> bool:
        """Whether the lead guitar sounds a note, across a chord struck at `at` for `length` beats, a semitone or a tritone from
        one of the chord's (MOVES_LISTEN; 2026-11-19, the judges: SongEval's musicality fell with the riff's moves). The rhythm
        guitar is written after the lead, so it can listen: where the tune holds the major third of the I, the IV's chord
        would rub a semitone against it, and the riff stays on the I there."""
        voice = self.voices["lead"].get("lead guitar")
        if voice is None or not voice.notes:
            return False
        if getattr(self, "_lead_index", None) is None or self._lead_index[0] is not voice.notes:
            ordered = sorted(voice.notes, key=lambda note: note.start)
            self._lead_index = (voice.notes, ordered, [note.start for note in ordered],
                                max((note.length for note in ordered), default=0.0))
        _, ordered, starts, longest = self._lead_index
        import bisect
        for note in ordered[bisect.bisect_left(starts, at - longest):bisect.bisect_left(starts, at + length)]:
            if note.start < at + length and note.start + note.length > at + 0.05:
                if any((note.pitch - pitch) % 12 in (1, 6, 11) for pitch in shape):
                    return True
        return False

    @staticmethod
    def _head_run(head: list[int], scale: list[int], held: int, goal: int, count: int) -> list[int] | None:
        """The first theme's opening as an answer's run (see `_answered`): its last `count` notes' shape in steps of the
        ladder `scale`, set to end on the step beside `goal`, or None where it does not fit. Where the opening climbs and the
        next phrase begins below the held note (or the other way round), the shape is turned upside down: the same figure
        falling into the phrase."""
        place = lambda pitch: min(range(len(scale)), key=lambda index: abs(scale[index] - pitch))
        steps = [place(each) for each in head[-count:]]
        shape = [each - steps[0] for each in steps]
        if len(set(shape)) < 2:
            return None
        if shape[-1] * (goal - held) < 0:
            shape = [-each for each in shape]
        rising = shape[-1] > shape[-2] if shape[-1] != shape[-2] else goal >= held
        last = place(goal) + (-1 if rising else 1)
        indices = [last - shape[-1] + each for each in shape]
        if min(indices) < 0 or max(indices) >= len(scale):
            return None
        run = [scale[index] for index in indices]
        if abs(run[0] - held) > 9 or run[-1] == goal:
            return None
        return run

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
        adorned = decorated(random.Random(fam.seed * 17 + self.take * 3 + 1), tune)    # its own draw: the rest of the take's are as they were
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
                even = 0.55 if part in ("arrival", "summit") and tag != " under" else 0.0
                self.sing("lead", name, line, first + bar * beats, key, chords, first, loud=loud, octave=octave, tag=tag, even=even)

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
                        # A conversation: the question from one player, the answer from another (2026-11-17, night: in the
                        # orchestral scores studied, who is playing changes every two bars or so; here it changed only
                        # from one statement of a theme to the next).
                        answering = solo if solo != third else mate
                        sing(third, tune.cut(0, half), bar, loud)
                        sing(answering, tune.cut(half, whole), bar + period // 2, loud)
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
                    use = (tune, again, adorned)[index % 3] if full else tune.cut(half, whole)
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
                # (A band's valley is quiet only if its tune is: a distorted guitar is as loud played softly. In a heavy
                # band's the clean guitar has it and answers itself; in a lighter band's it stands in for the distorted
                # lead only. Measured on the night of 2026-11-17: the heavy band's pieces went from 8 dB between their
                # quietest and loudest parts to 17 to 20.)
                if ch.band and self.heavy:
                    hush = echo = "guitar"
                elif ch.band:
                    hush, echo = ("guitar" if name == "lead guitar" else name for name in (hush, echo))
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
                whole_turns = sum(1 for _, full in stated if full)
                several = whole_turns > 1
                below = ch.under or ((other,) if other not in strong else ())
                soloist = ch.band and strong[0] == "lead guitar" and several and SOLOS
                solo_turns = 1
                if MOST_SOLOS:
                    # (2026-11-19, 13:15: "most songs should have solos".) Whoever leads the band's summit takes it, the fiddle,
                    # the mandolin, the harmonica or the whistle as well as the lead guitar; and a summit of the theme and half
                    # of it again has room for one, the half after it. Where the theme is eight bars and the summit states it
                    # three times or more, the solo takes two of them: sixteen bars, as a solo wants.
                    soloist = ch.band and strong[0] in SOLOISTS and whole_turns >= 1 and len(stated) > 1 and SOLOS
                    if period <= 8 and whole_turns >= 3 and stated[1][1]:
                        solo_turns = 2
                for index, (bar, full) in enumerate(stated):
                    use = (tune, again, adorned)[index % 3] if full else tune.cut(half, whole)
                    loud = self.hard(section.level[0])
                    if soloist and 0 < index < solo_turns:
                        continue                                  # (the solo's second eight bars)
                    if soloist and index == 0 and full:
                        # The guitar solo: the summit's first time round is the lead's alone over the band, and the theme
                        # comes back after it, the twin guitars with it. On a voice of its own, so that it has its own
                        # colour (an echo, no pedal) and keeps the five notes of the key it is written in.
                        own = random.Random(fam.seed * 31 + self.take * 7 + 5)          # its own draws: the take's are as they were
                        player = INSTRUMENTS[strong[0]]
                        solo_top = min(player.high, SOLO_TOP.get(strong[0], player.high))     # where a solo sings (SOLO_TOP)
                        reach = [step for step in range(-14, 22) if player.low + 2 <= key.pitch(step, player.home) <= solo_top]
                        length = period * solo_turns
                        mine = [chords[min(bar + each, len(chords) - 1)] for each in range(length)]
                        sing(strong[0], guitar_solo(own, tune, length, beats, self.pulse, fam.bpm, mine, key.mode, min(reach), max(reach),
                                                    two=SOLOISTS.get(strong[0], True)),
                             bar, loud, tag=" solo")
                        self.soloed = True
                        self.solo_bars = bar + length
                        continue
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
        # (A light piece's pad sits three semitones up, warmer than the five it had: "go a little harder this is not world
        # of fairy craft", 2026-11-17, played: light pads high and airy were half of the fairy sound.)
        lift = 3 if ch.light else 0
        # Under a second theme that is sung high the pad sits low, and the other way about.
        second_centre = 55 if INSTRUMENTS[self.other].home >= 64 else 62
        before: list[int] | None = None
        for section, first, key, chords in self.spans:
            part, bars = section.part, section.bars
            pad, way = (self.pad_b, self.way_b) if part in ("second", "valley") else (self.pad, self.way)
            if part == "valley" and pad in REEDS and self.pad not in REEDS:
                pad = self.pad                         # a reed does not hold the valley's drone (REEDS)
            if part == "valley" and (not self.fight or ch.band):
                way = self.valley_way                  # (a band's fight breaks down in its valley too: see `drums`)
            name = "tremolo" if way == "tremolo" and part in ("open", "build", "climb") else pad
            count = {"open": 2, "first": 3, "second": 3, "build": 4, "arrival": 4, "valley": 2, "climb": 4, "summit": 4, "close": 3}[part]
            centre = {"open": 53, "first": 58, "second": second_centre, "build": 60, "arrival": 62, "valley": 56, "climb": 61,
                      "summit": 62, "close": 56}[part] + lift
            arp = way == "arp" and part in ("open", "first", "second", "valley", "close")
            drone = way == "drone" and part not in ("arrival", "summit")
            held: dict[int, tuple[float, int]] = {}                # which player: (since when, what pitch)
            inner = random.Random(self.fam.seed * 11 + self.take * 101 + PARTS.index(part) * 7)
            moving = {"open": 0.5, "first": 0.6, "second": 0.6, "build": 0.4, "arrival": 0.3, "valley": 0.7, "climb": 0.4,
                      "summit": 0.25, "close": 0.7}[part]
            hold_over = self.starts[1] if len(self.starts) > 1 else beats / 2
            fill = beats - self.starts[-1] if len(self.starts) > 1 else beats / 2
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
                # (In the valley the pad is under the tune. Its swell never went below 0.3 while the tune went down to the
                # valley's pianissimo, so a band's drone stood 9 to 11 dB over everything else there, a bagpipe and an
                # organ held all but alone: "sometimes when one synth stays in when youre sitting its whiny and annoying
                # mix better", 2026-11-17, played.)
                soft = VALLEY_SOFT and part == "valley" and self.ch.band        # (a band's valley: VALLEY_SOFT)
                under = (VALLEY_PAD_SOFT if soft else VALLEY_PAD) if part == "valley" else 1.0
                held_hard = 0.4 if soft else 0.55                               # (struck softer in a band's valley)
                for swell in swells:
                    swell.swells.append((at, (0.3 + 0.62 * level) * under))
                    swell.swells.append((at + beats * 0.5, (0.3 + 0.62 * min(level + 0.05, 1.0)) * under))
                if arp:
                    # Broken chords on the harp: up through the chord and down again.
                    ladder = notes + [notes[0] + 12] + notes[::-1][:-1]
                    step = (self.pulse / 2 if self.pulse == 1.0 else self.pulse) * (2 if part == "valley" else 1)
                    for index in range(int(round(beats / step))):
                        self.put("texture", "harp", at + index * step, step * 2, ladder[index % len(ladder)],
                                 self.hard(level, 0.75 if index else 0.9))
                    continue
                # (2026-11-17, night: in the scores studied an inner voice holds one note through a bar one time in
                # fourteen; this pad held every note until the chord took it away.) One of the players that has to move
                # does it as an orchestra's inner voice does: a step down is held over into the bar and let fall (a
                # suspension), a third is filled with the note between at the end of the bar (a passing note).
                movers = [player for player, pitch in enumerate(notes) if player in held and held[player][1] != pitch
                          and (1 <= held[player][1] - pitch <= 2 or 3 <= abs(held[player][1] - pitch) <= 4)]
                mover = movers[int(inner.random() * len(movers))] if movers and inner.random() < moving else None
                if not drone and len(notes) > 2 and all(player in held and held[player][1] == pitch for player, pitch in enumerate(notes)) \
                        and inner.random() < moving * 0.6:
                    # The same chord again: one of the upper players goes over to another of its notes halfway through the bar.
                    player = 1 + int(inner.random() * (len(notes) - 1))
                    others = [p for p in tones(key, chord, notes[player] - 5, notes[player] + 5) if p != notes[player] and p not in notes]
                    if others:
                        since, was = held[player]
                        moved = min(others, key=lambda p: abs(p - was))
                        self.put("texture", who[player][0], since, at + hold_over - since, was, self.hard(held_hard, 1.0), tag=who[player][1], tied=True)
                        held[player] = (at + hold_over, moved)
                        notes = notes[:player] + [moved] + notes[player + 1:]
                        before = notes
                for player, pitch in enumerate(notes):
                    if player in held and held[player][1] == pitch:
                        continue                                    # the same note again: it is held over the bar line
                    begins = at
                    if player in held:
                        since, was = held[player]
                        ends = at
                        if player == mover and 1 <= was - pitch <= 2:
                            ends = begins = at + hold_over          # held into the new chord, then down a step
                        elif player == mover:
                            passing = [p for p in sorted({key.pitch(step, was, chord) + octave for step in range(7) for octave in (-12, 0, 12)})
                                       if min(was, pitch) < p < max(was, pitch)]
                            if passing:
                                ends = at - fill
                                self.put("texture", who[player][0], ends, fill, passing[len(passing) // 2], self.hard(0.5, 1.0),
                                         tag=who[player][1], tied=True)
                        self.put("texture", who[player][0], since, ends - since, was, self.hard(held_hard, 1.0), tag=who[player][1], tied=True)
                    held[player] = (begins, pitch)
            end = first + bars * beats
            for player, (since, was) in held.items():
                self.put("texture", who[player][0], since, end - since, was, self.hard(held_hard, 1.0), tag=who[player][1], tied=True)
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
                    # In a long moment's geared phrase (`geared`) the horns take the two lines, an octave lower: a warm call
                    # the second time round, a colour of its own. (Raised instead, an octave or a fifth, the violins put 8 to
                    # 13 dB on the texture's top from 5 to 10 kHz in those bars, Withered Circle's: too bright for the room.)
                    horns = GEARS and self.geared(part, bars, bar)
                    players = (("horns", ""), ("horns", " seconds")) if horns else above
                    for (player, tag), pitch in zip(players, voiced(key, chord, None, 2, centre + (2 if horns else 14))):
                        self.put("texture", player, at, beats, pitch, self.hard(0.8 if part == "summit" else 0.65), tag=tag)
                    if part == "summit" and "choir" in ch.pads + ch.strong:
                        for pitch in voiced(key, chord, None, 3, 62):
                            self.put("texture", "choir", at, beats, pitch, self.hard(0.75), tag=" tutti")

    # --- the accompaniment -------------------------------------------------------------------
    def rhythm(self) -> None:
        ch, rng, beats, pulse, starts = self.ch, self.own("rhythm"), self.beats, self.pulse, self.starts
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

        # Where a heavy band comes in behind its opening guitar: at the end of the opening.
        self.band_in = next(first + section.bars * beats for section, first, _, _ in self.spans if section.part == "open")
        # One riff and one pattern for the first theme and what is made of it, and another for
        # the second: a take that has only one figure to its name still plays two things.
        self.riff, riff_b = riff(), riff()
        if ch.band:
            self.fills = self._fills()
            # (2026-11-19: "still need more complex leads and riffs".) How this take's riff moves inside the bar, the way a
            # riff band's rhythm guitar does, on a generator of its own: it rocks up to the fourth's chord over the root, it
            # drops to the flat seventh's at the bar's end, it pedals the low root between its chords, or it pushes a stab
            # on the last off-beat. One move for the whole take, so the riff is the song's own.
            self.riff_move = random.Random(self.fam.seed * 7919 + self.take * 104729 + 41).choice(("rock", "drop", "pedal", "push"))
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
                  level: float, density: float, rings: bool = False, up: int = 0, ending: bool = False, comp: bool = False) -> None:
            """One bar of an accompaniment's figure on one instrument. `rings`: the riff's chord is struck once and held
            through the bar, without the chugs. `up`: the riff's power chords and licks so many semitones higher on the neck
            (the muted string chugs on where it was)."""
            inst = INSTRUMENTS[name]
            if GEARED_SHAPE and raised >= 12:
                # A geared bar is the chord shape the bar would have had, an octave up the neck (`geared`, `band_geared`): led
                # from the last bar that was not geared, which it leaves where it was; a note past the instrument's top stays.
                base = raised % 12
                notes = voiced(key, chord, leading.get((name, base)), 3, inst.home - 4 + base)
                notes = sorted(pitch + raised - base if pitch + raised - base <= inst.high else pitch for pitch in notes)
            else:
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
                chug = root                                    # the muted string, where the riff was
                root += up
                power = (root, root + 7, root + 12)
                hits: list[tuple[float, float | None]] = [(0.0, beats)] if rings else list(riff_b if second else self.riff)
                if comp:
                    # Under a solo the rhythm guitar comps (SOLO_COMP): the chord struck on the bar's first beat and left to
                    # ring half the bar, the muted string chugging the eighths after it, no fills: the solo has the room.
                    hits = [(0.0, beats / 2)] + [(index * half, None) for index in range(slots) if index * half >= beats / 2 - 1e-6]
                elif not rings and (density > 0.85 or figure == "chug"):
                    hits = hits + [(on, None) for on in [index * half for index in range(slots)]
                                   if not any(abs(on - at) < 1e-6 for at, _ in hits)]
                if ch.band and bar % 2 == 1 and not thin and not ending and not comp:
                    # The riff answers its chords (2026-11-17, night: "acdc for knight rock"; the band's guitars struck the
                    # same chords in every bar): at the end of the second bar of each four, and with a turn at the end of the
                    # fourth, the take's own fills (`fills`, OWN_LICKS), two turns taking it in turns.
                    if OWN_LICKS:
                        fill = self.fills[0] if bar % 4 == 1 else self.fills[1 + (bar // 4) % 2]
                    else:
                        fill = ("run", (10, 7, 5, 3)) if bar % 4 == 1 else ("run", (3, 5, 6, 7))
                    lick_guitar = "single guitar" if ch.band and self.heavy and bar_at < self.band_in else "rhythm guitar"
                    hits = self._fill(fill, hits, bar_at, root, loud, lick_guitar, half)
                # (2026-11-17, night: the heavy band's pieces swung 8 dB from their quietest to their loudest, the orchestra's
                # 18; distorted guitars hardly grow softer when played softly. A riff band opens on one guitar alone, and the
                # second guitar, the chugs and the band come in together with the first theme.)
                alone = ch.band and self.heavy and bar_at < self.band_in
                guitar = "single guitar" if alone else "rhythm guitar"
                move = getattr(self, "riff_move", None) if RIFF_MOVES and ch.band and not rings and not thin else None
                chords_struck = [hit for hit in hits if hit[1] is not None]
                if move == "push" and chords_struck and beats >= 3.0:
                    # A stab on the last off-beat, the muted string out of its way: the riff leans into the next bar.
                    late = beats - half
                    if not any(abs(on - late) < 1e-6 and length is not None for on, length in hits) and late > max(on for on, _ in chords_struck):
                        hits = [hit for hit in hits if abs(hit[0] - late) > 1e-6] + [(late, half)]
                shaped = []
                for on, length in hits:
                    shape = power
                    if length is not None and move == "rock" and len(chords_struck) >= 2 and beats - 2.0 <= on < beats - 0.5 \
                            and (on, length) != chords_struck[0]:
                        shape = (root + 5, root + 12, root + 17)       # the fourth's chord over the root (I to IV and back)
                    elif length is not None and move == "drop" and on >= beats - 1.0 and (on, length) != chords_struck[0] \
                            and root - 2 >= INSTRUMENTS["rhythm guitar"].low:
                        shape = (root - 2, root + 5, root + 10)        # the flat seventh's chord into the next bar
                    if shape is not power and MOVES_LISTEN and self._rubs(bar_at + on, length * 0.92, shape):
                        shape = power                                  # the singer holds a note the move would rub against
                    shaped.append((on, length, shape))
                for on, length, shape in sorted(shaped, key=lambda hit: hit[0]):
                    if self.breathing(bar_at + on):
                        continue
                    if length is None:
                        if thin or alone:
                            continue
                        if move == "pedal":
                            # The low root alone, palm-muted, on every eighth between the chords: the pedal under the riff.
                            self.put("rhythm", "muted guitar", bar_at + on, 0.22, chug, loud * (0.8 if on in starts else 0.68))
                            continue
                        self.put("rhythm", "muted guitar", bar_at + on, 0.2, chug, loud * (0.75 if on in starts else 0.6))
                        self.put("rhythm", "muted guitar", bar_at + on, 0.2, chug + 7, loud * 0.5)
                    else:
                        for pitch in shape:
                            self.put("rhythm", guitar, bar_at + on, length * 0.92, pitch, loud * (1.0 if on in starts else 0.9))
                if move == "pedal" and not alone and not any(length is None for _, length in hits):
                    # Where the riff had no chugs (a thin or a light theme), the pedal fills the gaps between its chords.
                    struck = sorted(on for on, length in hits if length is not None)
                    for slot in range(slots):
                        on = slot * half
                        if any(abs(on - at) < 1e-6 for at in struck) or any(at < on < at + 0.9 * half for at in struck):
                            continue
                        if not self.breathing(bar_at + on):
                            self.put("rhythm", "muted guitar", bar_at + on, 0.22, chug, loud * 0.62)
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

        soloed = [note for name, voice in self.voices["lead"].items() if name.endswith(" solo") for note in voice.notes]
        solo_from = min((note.start for note in soloed), default=None)
        solo_to = max((note.start + note.length for note in soloed), default=None)
        for section, first, key, chords in self.spans:
            part, bars = section.part, section.bars
            runs = held_runs(section.chords)
            for bar, chord in enumerate(chords):
                level, along = self.level(section, bar), bar / bars
                second = part in ("second", "valley") or (part == "climb" and along < 0.5)
                name, figure = (self.pluck_b, self.figure_b) if second else (self.pluck, self.figure)
                density = {"open": 0.15, "first": 0.5, "second": 0.45, "build": 0.5 + 0.5 * along, "arrival": 0.9,
                           "valley": 0.5 if self.fight else 0.2, "climb": 0.35 + 0.65 * along, "summit": 1.0,
                           "close": 0.4 * (1.0 - along)}[part]
                if self.bass_break(part, bars, bar):
                    continue                                     # the guitars rest while the bass leads the band back in
                end = self.ending(part, bars, bar)
                if end == "drive":
                    density, level = 0.8, max(level, 0.6)        # the riff goes on through a band's close
                elif end is not None:
                    density, level = 0.9, max(level, 0.8)        # the ending's chords, struck hard
                # (A band's fight rests its riff through the first half of its valley: see `drums`.)
                bare = part == "open" or (part == "valley" and (not self.fight or (ch.band and along < 0.5)))
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
                if self.geared(part, bars, bar) or self.band_geared(part, bars, bar):
                    raised += 12                               # a long moment's geared phrase: the figure an octave up (`geared`)
                bar_at = first + bar * beats
                if ch.band and self.heavy and part in ("arrival", "summit") and bar == 0:
                    # The band's arrival: one chord struck together on the downbeat and left to ring through the bar,
                    # then the riff (a rock band's stop: the room it leaves is what makes the next bar hit).
                    root = key.pitch(chord.root, 45)
                    root += 12 if root < 40 else -12 if root > 52 else 0
                    for pitch in (root, root + 7, root + 12):
                        self.put("rhythm", "rhythm guitar", bar_at, beats * 0.95, pitch, self.hard(level, 0.9))
                    continue
                # A heavy band's second theme rings (2026-11-18, the boredom meter: a heavy band's rhythm guitar had one colour
                # through both its themes, 42 to 64 bars, a riff and then a strum or a chug, all one distorted sound): its
                # chords are struck once and held under the second theme's singer, the way a '70s band opens out for its
                # other tune, and the riff comes back with the rise.
                rings = (RING_SECOND and ch.band and self.heavy and part == "second") or end in ("stop", "ring", "last")
                # A heavy band's long rise climbs (2026-11-19, the boredom meter: in a fight's 36-bar build the rhythm guitar
                # played one riff 17 bars over one chord, Lightning Runner's): where a chord is held nine bars or more, its second
                # half has the riff an octave up the neck, over the muted string still chugging low, and the next chord
                # brings it down again; the arrival comes in on the low riff, the way a riff band climbs and lands.
                into, run = runs[bar]
                climbing = self.climbs(part, run, into)
                # (A light band's geared phrase takes its riff up the neck the same way, the muted string chugging where it was:
                # a riff's register is its own, so the raise above does not reach it. `band_geared`.)
                geared_band = self.band_geared(part, bars, bar)
                played = "riff" if rings else "chug" if climbing and self.rise_way == "drive" and figure == "riff" else figure
                comping = SOLO_COMP and ch.band and solo_from is not None and played in ("riff", "chug") and not rings \
                    and solo_from - 1e-6 <= bar_at < solo_to - beats / 2
                # (A heavy band's long moment turns its guitars at its dig-in, out of the solo's way: `dig_turn`.)
                turn = None if comping else self.dig_turn(part, bars, bar)
                if turn == "ring" and played in ("riff", "chug"):
                    rings, played = True, "riff"
                layer(name, played, second, raised, 0.85 if comping else 1.0, key, chord, bar, bar_at, level, density, rings=rings,
                      up=12 if ((climbing and self.rise_way == "climb") or geared_band or turn == "up") and figure in ("riff", "chug")
                      and not rings else 0,
                      ending=end in ("stop", "ring", "last"), comp=comping)
                # (A band's riff guitars are the band's whole accompaniment; the unplugged band takes the second figure too.)
                if not (ch.band and self.heavy) and fuller(part, bar, along):
                    # The other figure, on its own instrument (another of the palette's, where both themes have the
                    # same one), an octave up where the two would sit on each other, a little under the first.
                    with_name, with_figure = (self.pluck, self.figure) if second else (self.pluck_b, self.figure_b)
                    if with_name == name:
                        with_name = ch.plucks[(self.take + 2) % len(ch.plucks)]
                    if with_name != name or with_figure != figure:
                        apart = abs(INSTRUMENTS[with_name].home - INSTRUMENTS[name].home)
                        up = 12 if (with_name == name or apart < 7 or geared_band) else 0
                        # (A riff keeps its own register and goes up the neck only by `up`: in a geared phrase a riff that
                        # is the second figure goes up too, 2026-11-19, Kinsman's Ballad VI's rhythm guitar 53 all through.)
                        layer(with_name, with_figure, not second, up, 0.72, key, chord, bar, bar_at, level, max(density, 0.5),
                              up=12 if geared_band and with_figure in ("riff", "chug") else 0)
                if part in ("arrival", "summit") and self.heavy and not ch.band:
                    # The brass marks the chord: on the bar at the first arrival, on every strong beat
                    # at the summit. A line each for the trombones, the horns and the trumpets;
                    # until then the heavy brass has rested, so that it means something.
                    for on in (starts if part == "summit" else starts[:1]):
                        for player, pitch in zip(("trombone", "horns", "trumpet"), voiced(key, chord, None, 3, 58)):
                            self.put("rhythm", player, bar_at + on, pulse * 0.8, pitch, self.hard(level, 0.85), tag=" stabs")

    # --- the bass ----------------------------------------------------------------------------
    def line(self, part: str, key: Key, chords: list[Chord], home: int) -> list[int]:
        """The bass's note for each bar of a part of the story: the chord's root or, between the
        bars that open and close a phrase, its third (and now and then its fifth), whichever
        makes the line move by step. (2026-11-17, night: measured against 72 movements of
        Beethoven, Brahms, Bruckner, Schubert, Haydn and Bach, a real bass repeats its note one
        time in four and moves by step two times in five; this bass repeated its note one time
        in two and sat on the root nine times in ten.) At the big moments of heavy music the
        root, where the whole low end is together."""
        period = self.fam.period
        rng = random.Random(self.fam.seed * 7 + self.take * 131 + PARTS.index(part) * 17 + len(chords))
        rooted = part in ("open",) or (self.heavy and part in ("arrival", "summit"))
        out: list[int] = []
        for bar, chord in enumerate(chords):
            root = key.pitch(chord.root, home)
            if rooted or not out or bar % period in (0, period - 1) or bar == len(chords) - 1:
                pitch = root if not out else min((root - 12, root, root + 12), key=lambda p: abs(p - out[-1]) + (0.5 if p < home - 9 or p > home + 8 else 0))
                out.append(pitch)
                continue
            candidates = [(chord.root, 0.0), (chord.steps[1] if len(chord.steps) > 1 else chord.root, 0.8)]
            if len(chord.steps) > 2:
                candidates.append((chord.steps[2], 2.2))
            best, cost = None, 1e9
            for step, penalty in candidates:
                tone = key.pitch(step % 7, home, chord)
                for pitch in (tone - 12, tone, tone + 12):
                    if pitch < home - 9 or pitch > home + 8:
                        continue
                    move = abs(pitch - out[-1])
                    mine = penalty + {0: 1.6, 1: 0.0, 2: 0.0, 3: 0.7, 4: 0.7, 5: 1.0, 6: 3.0, 7: 1.5}.get(move, 2.5) + 0.3 * rng.random()
                    if mine < cost:
                        best, cost = pitch, mine
            out.append(best if best is not None else root)
        return out

    def between(self, key: Key, chord: Chord, here: int, there: int) -> int:
        """A note to go from one bass note to the next on the way: the note of the scale between
        them if they are a third apart; the chord's other note a third or a fourth off if they
        are a step apart or the same; a note of the chord between them if they are further."""
        scale = sorted({key.pitch(step, here, chord) + octave for step in range(7) for octave in (-12, 0, 12)})
        gap = there - here
        if 3 <= abs(gap) <= 4:
            inside = [p for p in scale if min(here, there) < p < max(here, there)]
            if inside:
                return inside[len(inside) // 2]
        if abs(gap) >= 5:
            inside = [p for p in tones(key, chord, min(here, there) + 1, max(here, there) - 1)]
            if inside:
                return inside[len(inside) // 2]
        # A step or the same note: away by a third, on the side the line is not going, then back by step.
        away = [p for p in tones(key, chord, here - 5, here + 5) if 3 <= abs(p - here) <= 5 and (gap == 0 or (p - here) * gap < 0)]
        return away[0] if away else here

    def bass(self) -> None:
        ch, beats, pulse, starts = self.ch, self.beats, self.pulse, self.starts
        name = ch.basses[self.take % len(ch.basses)]
        inst = INSTRUMENTS[name]
        centre = bass_centre(inst)
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
        tonics, middle = bass_tonics(self.spans, inst, centre), centre
        for index_of, (section, first, key, chords) in enumerate(self.spans):
            part, bars = section.part, section.bars
            runs = held_runs(section.chords)
            ahead = self.spans[index_of + 1] if index_of + 1 < len(self.spans) else None
            # Each part's line centred an octave over where its key note would have put it, or under, as `bass_tonics` moved
            # that key note: whole octaves, so the line keeps its shape around it (most parts are not moved at all).
            centre = middle + tonics[index_of] - key.home(middle)
            ahead_centre = middle + tonics[index_of + 1] - ahead[2].home(middle) if ahead is not None else centre
            # A band's bass keeps to the root, as the riff bands do; an orchestra's moves through the chords.
            line = [key.pitch(chord.root, centre) for chord in chords] if ch.band else self.line(part, key, chords, centre)
            for bar, chord in enumerate(chords):
                level, bar_at, along = self.level(section, bar), first + bar * beats, bar / bars
                doubled = (part in ("first", "second") and bar >= self.fam.period) or (part in ("build", "climb") and along >= 0.5) \
                    or (part in ("arrival", "summit") and not self.heavy)
                root = key.pitch(chord.root, centre)
                here = line[bar]
                loud = self.hard(level, 0.9)
                after = chords[bar + 1] if bar + 1 < bars else chord
                there = line[bar + 1] if bar + 1 < bars else key.pitch(after.root, centre)
                if ch.band and self.heavy and part in ("arrival", "summit") and bar == 0:
                    low(bar_at, beats * 0.95, root, loud)                 # the stop: one note with the chord, left to ring
                    continue
                if part == "open":
                    if self.heavy or bar >= bars // 2:
                        # The key note, held; but in a long opening it goes with the chord where the harmony leaves home and
                        # comes back with it (2026-11-18, the boredom meter: Gull's Edge's basses held one note 27 bars of
                        # a 28-bar opening, under its flat-seventh chords as well).
                        held = key.pitch(0, centre)
                        if (bars >= 16 or ch.style in OPEN_WALKS) and chord.root % 7 != 0:
                            held = root                    # (and in an open that walks the first theme's changes: OPEN_WALKS)
                        self.put("bass", name, bar_at, beats, held, loud * 0.8)
                    continue
                # One way of playing for the first theme and what is made of it, another for the
                # second; long notes where the story is quiet; and at the top of the climb the
                # root over and over, driving at the summit.
                fight_valley = "long" if ch.band and along < 0.5 else two          # a band's fight: held roots under its breakdown
                way = {"first": one, "second": two, "build": one, "arrival": one, "valley": fight_valley if self.fight else "long",
                       "climb": two if along < 0.5 else drive, "summit": one, "close": "long"}[part]
                if self.after_solo(part, bar):
                    way = LAST_CHORUS.get(way, way)          # a light band's last chorus: its bass moves more (LIGHT_SUMMIT_TURNS)
                if self.bass_break(part, bars, bar):
                    self._bass_solo_bar(key, chord, chords, bar, bars, bar_at, root, inst, low, level)
                    continue
                end = self.ending(part, bars, bar)
                if end == "drive":
                    way, loud = drive, self.hard(max(level, 0.6), 0.9)      # a band's close keeps driving
                elif end is not None:
                    low(bar_at, beats * 0.95, root, self.hard(max(level, 0.8), 0.9))      # the root under the ending's chord
                    continue
                if part in ("first", "second") and bar >= self.fam.period and not ch.band:
                    way = BUSIER.get(way, way)          # the second time round a theme the bass moves more, as it does in the scores
                if way == "long":
                    low(bar_at, beats, here, loud)
                    if self.grim and part == "valley":
                        self.put("bass", "contrabassoon", bar_at, beats, here - 12, loud * 0.85)     # an octave under, the deepest wind there is
                elif way == "two":
                    # The bar's note, and on the way to the next: a passing note, or the chord's other note.
                    for index, on in enumerate(starts):
                        length = (starts[index + 1] if index + 1 < len(starts) else beats) - on
                        pitch = here if index == 0 else self.between(key, chord, here, there) if index == len(starts) - 1 else self.between(key, chord, here, here)
                        low(bar_at + on, length, pitch, loud * (1.0 if index == 0 else 0.85))
                elif way == "walk":
                    # The bar's note, then notes of the chord or the scale on the way, and the last
                    # note of the bar a step of the scale from the next bar's note.
                    toward = there
                    scale = sorted({key.pitch(step, toward, chord) + octave for step in range(7) for octave in (-12, 0, 12)})
                    side = [p for p in scale if 1 <= abs(p - toward) <= 2]
                    near = min(side, key=lambda p: (abs(p - here) if p != here else 99)) if side else toward
                    walked = here
                    for index, on in enumerate(starts):
                        length = (starts[index + 1] if index + 1 < len(starts) else beats) - on
                        if index:
                            walked = self.between(key, chord, walked, near)
                        low(bar_at + on, length - (pulse if index == len(starts) - 1 else 0.0), walked, loud if index == 0 else loud * 0.9)
                    low(bar_at + beats - pulse, pulse, near, loud * 0.8)
                elif way == "eight":
                    step = 0.5
                    count = int(round(beats / step))
                    toward = key.pitch(after.root, centre)
                    toward += 12 if toward < root - 6 else -12 if toward > root + 6 else 0
                    # A heavy band's long rise climbs (2026-11-19, the boredom meter: Warlord Fury's bass played one note 17
                    # bars through its build): through the second half of a chord held nine bars or more the bass pumps its
                    # octaves, and in its last bar it runs by step, two eighths a note, into the next bar's note (the
                    # arrival's, at the end of the rise): up from under it where the music goes up, down from over it where
                    # the chords step down (or where there is no room under it).
                    into, run = runs[bar]
                    climbs = self.climbs(part, run, into)
                    # (And through the second half of a heavy band's long moment the octaves are pumped too: `digs_in`.)
                    pumps = climbs or self.digs_in(part, bars, bar)
                    stair: list[int] = []
                    if climbs and self.rise_way == "climb" and into == run - 1:
                        goal = key.pitch(after.root, centre) if bar + 1 < bars else \
                            ahead[2].pitch(ahead[3][0].root, ahead_centre) if ahead is not None else root
                        scale = sorted({key.pitch(degree, goal, chord) + octave for degree in range(7) for octave in (-12, 0, 12)})
                        pairs = count // 2
                        under = [p for p in scale if p < goal][-pairs:]
                        over = [p for p in scale if p > goal][:pairs][::-1]
                        rising = goal >= root and under and under[0] >= inst.low
                        falling = over and over[0] <= inst.high
                        run_in = under if rising else over if falling else (under if under and under[0] >= inst.low else [])
                        stair = [p for p in run_in for _ in (0, 1)]
                        stair = [root] * (count - len(stair)) + stair if stair else []
                    # (The octave pumped: the root and the octave over it, or where that is past the bass's top, the octave
                    # under it and the root.)
                    pumped = root if root + 12 <= inst.high else root - 12 if root - 12 >= inst.low else None
                    for index in range(count):
                        on = index * step
                        pitch = root
                        if stair:
                            pitch = stair[index]
                        elif pumps and pumped is not None:
                            pitch = pumped + (12 if index % 2 == 1 else 0)
                        elif index == count - 1 and toward != root and bar + 1 < bars:
                            # Into a new chord the last eighth is a step away from its root (2026-11-17, night: the band's bass
                            # played one note 85% of the time; the riff bands' bass players lead into each change like this).
                            pitch = toward + (1 if toward < root else -1) * (1 if abs(toward - root) <= 2 else 2)
                        low(bar_at + on, step * 0.85, pitch, loud * (1.0 if on in starts else 0.8))
                elif way == "pulse":
                    for index in range(int(round(beats / pulse))):
                        on = index * pulse
                        low(bar_at + on, pulse * 0.85, root, loud * (1.0 if on in starts else 0.8))
                else:
                    step = pulse
                    for index in range(int(round(beats / step))):
                        low(bar_at + index * step, step * 0.8, here + (12 if index % 2 else 0), loud * (1.0 if index % 2 == 0 else 0.75))
                if part in ("arrival", "summit") and self.heavy and not ch.band:
                    # The low end at the big moments: the celli and the basses an octave apart,
                    # whichever of them has the bass line; and at the summit the low brass with
                    # them, where the palette has it: the tuba on the bass's note, the trombones
                    # an octave above. Nothing is left open between the bass and the chords.
                    weight = self.hard(level, 0.8)
                    upper = key.pitch(chord.root, INSTRUMENTS["celli"].home - 5)        # where the celli have the bass
                    lower = upper - 12                                                  # and the basses under them
                    # (Bowed, whatever plays the bass line: a summit with only plucked basses under it has no floor.)
                    if name not in ("celli", "celli slow"):
                        self.put("bass", "celli", bar_at, beats, upper, weight, tag=" tutti")
                    if name not in ("basses", "basses slow"):
                        self.put("bass", "basses", bar_at, beats, lower, weight, tag=" tutti")
                    if self.grim and part == "summit":
                        self.put("bass", "contrabassoon", bar_at, beats, lower, weight * 0.9, tag=" tutti")
                    if part == "summit":
                        if "tuba" in ch.basses + ch.under and name != "tuba":
                            self.put("bass", "tuba", bar_at, beats, lower, weight, tag=" tutti")
                        if "trombone" in ch.under + ch.leads:
                            self.put("bass", "trombone", bar_at, beats, upper, weight * 0.9, tag=" tutti")

    # --- the drums ---------------------------------------------------------------------------
    def strike(self, sound: str, at: float, loud: float, chord: Chord, key: Key) -> None:
        if sound == "ting" and self.forge:
            self.put("drums", "anvil", at, 0.5, 60, loud)        # in a forge the bright stroke is an anvil
        elif sound in KITS[self.ch.kit]:
            # A stroke of the kit. (The kit's "boom" is its bass drum; the deep stroke that marks
            # an arrival is an instrument of the same name, and is written by `marks`.)
            self.kit().add(at, 0.25, KITS[self.ch.kit][sound], loud)
        elif sound == "timpani":
            # A pair of kettledrums is tuned to the key note and the fourth below it. They play
            # whichever of the two is in the chord, and the chord's own root only where neither is.
            notes = {step % 7 for step in chord.steps}
            step = 0 if 0 in notes else -3 if 4 in notes else chord.root
            self.put("drums", sound, at, 0.5, key.pitch(step, INSTRUMENTS[sound].home), loud)
        else:
            inst = INSTRUMENTS[sound]
            self.put("drums", sound, at, 0.5, key.pitch(chord.root, inst.home), loud)

    def _fills(self) -> tuple:
        """A band take's own fills (OWN_LICKS): what answers the riff at the end of the second bar of each four, and two turns
        for the end of the fourth, used in turn. Drawn on a generator of its own, so the writing's other draws do not move."""
        own = random.Random(self.fam.seed * 7919 + self.take * 104729 + 31)
        bright = self.fam.key.mode in MAJORISH

        def one(kinds: dict[str, float]) -> tuple:
            kind = own.choices(list(kinds), weights=list(kinds.values()))[0]
            if kind == "run":
                return kind, own.choice(FILL_RUNS)
            if kind == "bright":
                return "run", own.choice(BRIGHT_RUNS)
            if kind == "curl":
                return kind, own.choice(CURLS)
            if kind == "stops":
                return kind, own.choice(DOUBLE_STOPS)
            return kind, None
        answer = one({"run": 0.3, "stops": 0.2, "stabs": 0.2, "ring": 0.3})
        turns = {"run": 0.3 if bright else 0.4, "turn chord": 0.2, "stops": 0.15, "curl": 0.15, "stabs": 0.1}
        if bright:
            turns["bright"] = 0.1
        first = one(turns)
        # The second turn is a variation of the first (2026-11-19, the judges: SongEval's coherence fell 0.08 and 0.11 on both
        # songs given their own fills, when their two turns were drawn apart): the same run a step of the scale away, the
        # other curl, the double stops the other way round, the turn chord answered by stabs.
        return answer, first, self._varied(first)

    @staticmethod
    def _varied(fill: tuple) -> tuple:
        kind, what = fill
        if kind == "run":
            def shift(semitones: int, steps: int) -> int:
                nearest = min(range(len(PENTATONIC)), key=lambda index: abs(PENTATONIC[index] - semitones))
                return PENTATONIC[min(max(nearest + steps, 0), len(PENTATONIC) - 1)]
            for steps in (-1, 1):
                moved = tuple(shift(each, steps) for each in what)
                if moved != what and min(moved) >= -12 and max(moved) <= 22:
                    return ("run", moved)
            return ("run", tuple(reversed(what)))
        if kind == "curl":
            return ("curl", next(each for each in CURLS if each != what))
        if kind == "stops":
            return ("stops", tuple(reversed(what)))
        if kind == "turn chord":
            return ("stabs", None)
        return ("turn chord", None)

    def _fill(self, fill: tuple, hits: list, bar_at: float, root: int, loud: float, guitar: str, half: float) -> list:
        """One fill at the end of a bar of the riff (see `_fills`); returns the riff's chords that are left before it.

        - a run or a curl: single notes picked to the bar line, sixteenths (eighths when it is fast);
        - double stops, or the riff's chord, struck on the last two offbeats;
        - the turn chord: the flat seventh's power chord on the last beat, back to the root on the next bar;
        - ring: no fill; the last chord struck before the last beat rings to the bar line."""
        beats = self.beats
        kind, what = fill
        cut = lambda begin: [(on, None if length is None else min(length, begin - on)) for on, length in hits if on < begin - 1e-6]

        def play(at: float, length: float, pitches, strength: float) -> None:
            if not self.breathing(bar_at + at):
                for pitch in pitches:
                    self.put("rhythm", guitar, bar_at + at, length, root + pitch, loud * strength)
        if kind in ("run", "curl"):
            span = 1.0 if beats >= 4.0 else self.group[-1]
            step = 0.25 if self.fam.bpm <= 150 else 0.5
            count = int(round(span / step))
            notes = list(what)[-count:] if count < len(what) else list(what)
            begin = beats - len(notes) * step
            for index, above in enumerate(notes):
                play(begin + index * step, step * 0.9, (above,), 0.95 if index == 0 else 0.85)
            return cut(begin)
        if kind in ("stops", "stabs"):
            offs = [beats - 3 * half, beats - half]
            shapes = what if kind == "stops" else ((0, 7, 12), (0, 7, 12))
            for at, shape in zip(offs, shapes):
                play(at, half * 0.75, shape, 0.9)
            return cut(offs[0])
        if kind == "turn chord":
            begin = beats - min(1.0, beats / 3)
            low = -2 if root - 2 >= INSTRUMENTS["rhythm guitar"].low else 10
            play(begin, (beats - begin) * 0.92, (low, low + 7, low + 12), 0.95)
            return cut(begin)
        # ring: the chords struck before the last beat are kept, the last of them held to the bar line, the chugs after it gone
        until = beats - 1.0
        kept = [(on, length) for on, length in hits if on < until - 1e-6]
        struck = [index for index, (on, length) in enumerate(kept) if length is not None]
        if struck:
            on, _ = kept[struck[-1]]
            kept = kept[:struck[-1]] + [(on, beats - on)]
        return kept

    @property
    def rise_way(self) -> str:
        """How this take plays a long hold in a heavy band's rise (see `climbs`): it climbs (the riff an octave up the neck, the
        bass's octaves and a run into the next chord), it drives (the muted string on every eighth under the riff, the bass's
        octaves), or it plays on as written. Drawn on a generator of its own (2026-11-19: "hearing that same guitar riff climb in
        too many knight songs": the climb is one way among three, not every song's)."""
        if not hasattr(self, "_rise_way"):
            self._rise_way = random.Random(self.fam.seed * 7919 + self.take * 104729 + 37).choice(("climb", "drive", "plain"))
        return self._rise_way

    def bass_break(self, part: str, bars: int, bar: int) -> bool:
        """Whether a bar is in a heavy band's bass break (BASS_SOLO, 2026-11-19: "do bass solos too"): the first four bars of the
        climb (eight in a climb of twenty-four bars or more), where after the valley the bass leads the band back in alone,
        the drummer keeping time lightly, the guitars and the lead resting; then the band comes in."""
        if not (BASS_SOLO and self.ch.band and self.heavy and part == "climb"):
            return False
        return bar < (8 if bars >= 24 else 4)

    def _bass_solo_bar(self, key: Key, chord: Chord, chords: list, bar: int, bars: int, bar_at: float, root: int, inst, low, level: float) -> None:
        """A bar of the bass's break (`bass_break`): the take's riff over the chord's root (BASS_RIFFS, drawn for the take), its
        second time an octave's leap at its end, the octave pumped with passing notes in the third of each four, and in the
        break's last bar a run up the blues scale into the band's entry. It sits up the neck, to be heard alone."""
        own = random.Random(self.fam.seed * 7919 + self.take * 104729 + 43)
        riff = BASS_RIFFS[own.randrange(len(BASS_RIFFS))]
        scale = self.beats / 4.0
        loud = self.hard(max(level, 0.75), 1.0)
        length = 8 if bars >= 24 else 4
        base = root + (12 if root + 12 <= inst.home + 6 else 0)          # up the neck, as a soloist plays
        if bar == length - 1:
            nxt = chords[min(bar + 1, len(chords) - 1)]
            goal = key.pitch(nxt.root, base + 7)
            steps = sorted({key.tonic + 12 * octave + interval for octave in range(1, 6) for interval in BLUES})
            run = [note for note in steps if base <= note < goal][-8:] or [base]
            fast = self.beats / max(len(run), 1)
            for each, note in enumerate(run):
                low(bar_at + each * fast, fast * 0.85, note, loud * (0.85 + 0.15 * each / max(len(run) - 1, 1)))
            return
        if bar % 4 == 2:
            for each, interval in enumerate((0, 12, 0, 10, 0, 7, 0, 3)):
                low(bar_at + each * 0.5 * scale, 0.45 * scale, base + interval, loud * (1.0 if each % 2 == 0 else 0.85))
            return
        for index, (on, beats_long, interval) in enumerate(riff):
            if bar % 4 == 1 and index == len(riff) - 1:
                interval = 12                                            # the second time: the leap to the octave
            low(bar_at + on * scale, beats_long * scale * 0.9, base + interval, loud * (1.0 if on == 0 else 0.88))

    def make_room(self) -> None:
        """The lead rests through the bass's break (`bass_break`): its notes there are taken out, every voice of the lead."""
        if not (BASS_SOLO and self.ch.band and self.heavy):
            return
        for section, first, _, _ in self.spans:
            if section.part != "climb":
                continue
            until = first + (8 if section.bars >= 24 else 4) * self.beats
            for voice in self.voices["lead"].values():
                voice.notes = [note for note in voice.notes if not (first - 1e-6 <= note.start < until - 1e-6)]

    def ending(self, part: str, bars: int, bar: int) -> str | None:
        """Where a bar of a heavy band's close stands in its rock ending (ROCK_ENDING, 2026-11-19, the judges: in every band song
        the close scored lowest of the nine parts, TuneJury 0.20 against 0.67 for the second theme, enjoyment 6.6 against 7.4;
        it died away as an orchestra's does): "drive" while the band keeps its riff going, then the last four bars (two in a
        short close): "stop", one chord struck with the crash and left to ring; "ring", the chord struck again and held while
        the drummer rolls around the toms; "last", the final chord with the crash, together, held. None outside it."""
        if not (ROCK_ENDING and self.ch.band and self.heavy and part == "close"):
            return None
        tail = 4 if bars >= 8 else 2
        if bar < bars - tail:
            return "drive"
        return "stop" if bar == bars - tail else "last" if bar == bars - 1 else "ring"

    def digs_in(self, part: str, bars: int, bar: int) -> bool:
        """Whether a bar of a heavy band's long moment (an arrival or a summit of 24 bars or more) is in its second half, from
        the first eight-bar line at or after its middle (see `drums` and `bass`)."""
        if not (DIGS_IN and self.ch.band and self.heavy and part in ("arrival", "summit") and bars >= 24):
            return self.after_solo(part, bar)
        return bar >= max(16, ((bars // 2 + 7) // 8) * 8)

    @property
    def dig_way(self) -> str:
        """How this take's guitars turn as a heavy band's long moment digs in (HEAVY_DIG_TURNS): the riff goes up the neck an
        octave over the muted string ("up"), its chords are struck and left to ring over the drums ("ring"), or it plays on
        as written ("plain"). Drawn on a generator of its own, as `rise_way` is, so that not every song turns the same way.
        The way up is left off (DIG_UP): such a take plays on as written."""
        if not hasattr(self, "_dig_way"):
            self._dig_way = random.Random(self.fam.seed * 7919 + self.take * 104729 + 41).choice(("up", "ring", "plain"))
        return self._dig_way

    def dig_turn(self, part: str, bars: int, bar: int) -> str | None:
        """The turn of a bar of a heavy band's long moment (`dig_way`), in the first half of its dig-in (`digs_in`): then the
        second half brings the riff back as it was, so that the moment ends on it (bars 16 to 23 of a 32-bar arrival, 24 to 31
        of a 40-bar summit)."""
        if not (HEAVY_DIG_TURNS and DIGS_IN and self.ch.band and self.heavy and part in ("arrival", "summit") and bars >= 24):
            return None
        start = max(16, ((bars // 2 + 7) // 8) * 8)
        if not start <= bar < start + (bars - start) // 2 or self.dig_way == "plain" or (self.dig_way == "up" and not DIG_UP):
            return None
        return self.dig_way

    def after_solo(self, part: str, bar: int) -> bool:
        """Whether a bar of a light band's summit comes after its solo, where the band comes back in harder, as it plays its
        last chorus (LIGHT_SUMMIT_TURNS): the rhythm up a gear (`band_geared`), the drummer over to the ride with the crash
        twice as often and the bass pumping its octaves (`digs_in`)."""
        return LIGHT_SUMMIT_TURNS and self.ch.band and not self.heavy and not self.fight and part == "summit" \
            and self.soloed and bar >= self.solo_bars

    def geared(self, part: str, bars: int, bar: int) -> bool:
        """Whether a bar of an orchestra's arrival or summit is in one of its geared phrases: where the moment is two phrases
        long or more, every second phrase of it (see `rhythm` and `drums`)."""
        return GEARS and not self.ch.band and part in ("arrival", "summit") and bars >= 2 * GEAR_BARS \
            and (bar // GEAR_BARS) % 2 == 1

    def band_geared(self, part: str, bars: int, bar: int) -> bool:
        """Whether a bar of a light band's arrival of two phrases or more is in one of its geared phrases: every second
        phrase, the rhythm's figure an octave up, as a guitarist goes up the neck the second time round (LIGHT_GEARS). The
        summit is the solo's and its comp's; a heavy band digs in instead (`digs_in`); a fight keeps its own."""
        return LIGHT_GEARS and self.ch.band and not self.heavy and not self.fight and part == "arrival" \
            and bars >= 2 * GEAR_BARS and (bar // GEAR_BARS) % 2 == 1 or self.after_solo(part, bar)

    def climbs(self, part: str, run: int, into: int) -> bool:
        """Whether a bar of a heavy band's rise is in the climbing half of a chord held long (see `rhythm` and `bass`)."""
        return CLIMBS and self.ch.band and self.heavy and part in ("build", "climb") and run >= LONG_HOLD and into >= run // 2 \
            and self.rise_way != "plain"

    def fill_of(self, groove: dict) -> str | None:
        """What a short fill is played on (a phrase's pickup, the fill every eight bars of a moment, the fill into a stop):
        the groove's roll, or, on a groove whose roll is a drum keeping its time, what it names to fill with
        (TOM_FILLS_ON_SNARE). The long roll up a rise stays the roll."""
        return groove.get("fill", groove["roll"]) if TOM_FILLS_ON_SNARE else groove["roll"]

    def cymbal(self, layers: list, bar: int, moment: bool = False) -> list:
        """A band's drummer keeps time on the hat for sixteen bars of a theme and on the ride for the next sixteen, the
        same figure a little softer; on a groove of the toms, with no cymbal keeping time, the ride joins it softly for
        those sixteen bars and leaves again (2026-11-18, the boredom meter: a battle piece's drums had sounded the same
        through a whole theme and into the next, 44 bars; "some of the instruments get boring"). Any other groove (a
        tavern's tambourine and side stick) is left as it is.

        At a heavy band's moment the drummer rides it out the same way: the cymbal keeping time goes over to the ride's
        bell for the second sixteen bars, or the bell joins a groove of the toms (the meter: 18 bars of a battle piece's
        40-bar last moment without a change)."""
        if not self.ch.band or not layers or (bar // 16) % 2 == 0:
            return layers                                   # (a theme the drums sit out stays without them)
        if moment:
            if not self.heavy:
                return layers
            keeper = ("hat open", "ride", "hat")
            if any(layer[0] in keeper for layer in layers):
                return [("bell", layer[1], 0.85 * layer[2]) + tuple(layer[3:]) if layer[0] in keeper else layer for layer in layers]
            if any(layer[0] in ("tom", "tom low") for layer in layers):
                return list(layers) + [("bell", "pulses", 0.4)]
            return layers
        if any(layer[0] in ("hat", "hat open") for layer in layers):
            return [("ride", layer[1], 0.9 * layer[2]) + tuple(layer[3:]) if layer[0] in ("hat", "hat open") else layer for layer in layers]
        if any(layer[0] in ("tom", "tom low") for layer in layers) and not any(layer[0] in ("hat open", "ride") for layer in layers):
            return list(layers) + [("ride", "halves", 0.35)]
        if TURNS_TO_HAT and any(layer[0] == "ride" for layer in layers) and not any(layer[0] in ("hat", "hat open") for layer in layers):
            # A groove that keeps time on the ride turns to the closed hat for its second sixteen bars, the same figure a
            # little softer: tighter after the wash (2026-11-19, the boredom meter: the fights' drums one colour 40 and 41
            # bars, Blood Machine and Lance Cry, their groove on the ride with nowhere to turn).
            return [("hat", layer[1], 0.85 * layer[2]) + tuple(layer[3:]) if layer[0] == "ride" else layer for layer in layers]
        return layers

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
                    lay(self.cymbal(main["theme"], bar), bar, bar_at, level, 1.0, chord, key)
                    if bar >= self.fam.period and not (ch.band and self.heavy):
                        # The second time round a theme, the moment's small percussion joins softly (2026-11-16,
                        # played: "not enough instruments in each track").
                        lay([each for each in main["moment"] if each[0] in SMALL and each not in main["theme"]], bar, bar_at, level, 0.55, chord, key)
                elif part == "second":
                    keeping = second
                    if OPENS_OUT and ch.band and self.heavy:
                        # The band opens out for its other tune (2026-11-19, the boredom meter: a heavy band's drums one colour
                        # 34 to 68 bars across both its themes, King's Oath's and Banner Oath's; the turn from the hat to the
                        # ride sits too far under the kick and the snare to be heard): as the guitars ring, the drummer keeps
                        # time on the open hat, and goes over to the ride for the theme's second sixteen bars.
                        keeping = [("hat open", layer[1], 0.9 * layer[2]) + tuple(layer[3:]) if layer[0] == "hat" else layer
                                   for layer in second]
                    lay(self.cymbal(keeping, bar), bar, bar_at, level, 1.0 if other is not main else 0.85, chord, key)
                    if bar >= self.fam.period and not (ch.band and self.heavy):
                        lay([each for each in other["moment"] if each[0] in SMALL and each not in second], bar, bar_at, level, 0.55, chord, key)
                if part in ("first", "second"):
                    # Phrasing (2026-11-17, night: "make sure the individual stem tracks are interesting enough"; the drums
                    # played the same bar through a whole theme). The last bar of each phrase ends on a pickup of the
                    # groove's roll into the next, getting louder; the next phrase opens with its light stroke. A heavy
                    # band's drummer keeps time and fills only every other phrase.
                    period = self.fam.period * (2 if ch.band and self.heavy else 1)
                    groove = main if part == "first" else other
                    fill = self.fill_of(groove)
                    if bar % period == period - 1 and bar < bars - 1 and fill and not (crowded and fill in LOW):
                        count = 3 if self.pulse == 1.0 else 2
                        step = 0.25 if self.pulse == 1.0 else 0.5
                        for index in range(count):
                            self.strike(fill, bar_at + beats - (count - index) * step, (0.3 + 0.12 * index) * (0.6 + 0.6 * level), chord, key)
                    if bar % period == 0 and bar > 0 and groove["hit"]:
                        light = "ting" if groove["hit"] == "crash" and not self.heavy else groove["hit"]
                        self.strike(light, bar_at, 0.35 + 0.25 * level, chord, key)
                elif self.bass_break(part, bars, bar):
                    # Under the bass's break the drummer keeps time lightly: the hat on the eighths, the kick on the bar, the
                    # snare on the backbeat, and a fill into the band's entry.
                    lay([("hat", "halves", 0.42), ("boom", "down", 0.7), ("snare", "back", 0.5)], bar, bar_at, level, 0.8, chord, key)
                    if not self.bass_break(part, bars, bar + 1) and self.fill_of(main):
                        for index in range(4):
                            self.strike(self.fill_of(main), bar_at + beats - (4 - index) * 0.25, 0.5 + 0.12 * index, chord, key)
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
                    groove = self.cymbal(main["moment"], bar, moment=True)
                    if self.after_solo(part, bar):
                        # After a light band's solo the drummer goes over to the ride for the last chorus (2026-11-20, the
                        # study: Lazy River Sway I's drums one colour 27 bars of its summit, on the hats all through).
                        groove = [("ride", layer[1], 0.9 * layer[2]) + tuple(layer[3:]) if layer[0] in ("hat", "hat open") else layer
                                  for layer in groove]
                    if self.digs_in(part, bars, bar):
                        # A heavy band's long moment digs in at its half (2026-11-19, the meter: the bass and the drums of a
                        # 32-bar arrival or summit one colour all through): the crash every other bar, over the ride's bell.
                        groove = [layer[:3] + (max(layer[3] // 2, 1),) + tuple(layer[4:]) if layer[0] == "crash" and len(layer) > 3
                                  else layer for layer in groove]
                    if self.geared(part, bars, bar):
                        # An orchestra's long moment goes up a gear every second phrase (2026-11-19, the boredom meter: the
                        # drums of Warcraft's summits one colour 19 to 23 bars, Withered Circle's, Quiet Nave's, Spirit
                        # Bells'): each drum one step busier and the cymbal twice as often, then back for the next phrase.
                        groove = [(sound, where if sound in CYMBALS else BUSIER_STROKES.get(where, where), loud,
                                   *([max(rest[0] // 2, 1)] if rest and sound in CYMBALS else rest))
                                  for sound, where, loud, *rest in groove]
                    if not (ch.band and self.heavy and bar == 0):          # a band's moment begins with a stop: the hit alone
                        lay(groove, bar, bar_at, level, 1.0 if big else 0.85, chord, key)
                    if bar == 0 and main["hit"]:
                        self.strike(main["hit"], bar_at, (0.6 + 0.35 * ch.weight) * (1.0 if big else 0.85), chord, key)
                        if self.heavy:
                            for sound in ch.drums[:2 if big else 1]:
                                if not (crowded and sound in LOW):
                                    self.strike(sound, bar_at, 0.9 if big else 0.75, chord, key)
                    fill = self.fill_of(main)
                    if bar % 8 == 7 and fill and bars - bar > 1 and not (crowded and fill in LOW):
                        for index in range(4):                       # a fill into the next time round
                            self.strike(fill, bar_at + beats - (4 - index) * 0.25, 0.45 + 0.12 * index, chord, key)
                elif part == "valley":
                    if fight and ch.band and along < 0.5:
                        # A band's fight breaks down in its valley (2026-11-17, morning: its fight pieces went only 4 to
                        # 5 dB between their quietest part and their loudest, the whole band playing on through the
                        # valley): the riff stops under the clean guitar's theme, the bass holds its roots, and the
                        # drummer keeps time on the cymbal with the bass drum on the bar.
                        keeping = [layer for layer in main["theme"] if layer[0] in ("hat", "hat open", "ride")] or [("hat", "halves", 0.45)]
                        lay(keeping + [("boom", "down", 0.7)], bar, bar_at, level, 0.6, chord, key)
                    elif fight and ch.band:
                        # ...then the groove is back, and a fill takes it into the climb.
                        lay(main["theme"], bar, bar_at, level, 0.65, chord, key)
                        if bar == bars - 1 and self.fill_of(main):
                            for index in range(4):
                                self.strike(self.fill_of(main), bar_at + beats - (4 - index) * 0.25, 0.4 + 0.12 * index, chord, key)
                    elif ch.band and VALLEY_KEEPS_TIME:
                        # A band's walking valley keeps time softly (VALLEY_KEEPS_TIME): the closed hat on the beat and the
                        # bass drum on the bar under the single player, and from the valley's second half the side stick on
                        # the backbeat, the band gathering itself before the climb.
                        keeping = [("hat", "pulses", 0.4), ("boom", "down", 0.5)]
                        if along >= 0.5:
                            keeping.append(("clack", "back", 0.45))
                        lay(keeping, bar, bar_at, level, 0.6, chord, key)
                else:
                    end = self.ending(part, bars, bar)
                    if end == "drive":
                        lay(self.cymbal(main["theme"], bar), bar, bar_at, max(level, 0.6), 0.9, chord, key)
                        if self.ending(part, bars, bar + 1) == "stop" and self.fill_of(main):
                            for index in range(4):                   # a fill into the stop
                                self.strike(self.fill_of(main), bar_at + beats - (4 - index) * 0.25, 0.5 + 0.12 * index, chord, key)
                    elif end in ("stop", "last"):
                        self.strike("crash", bar_at, 0.95 if end == "stop" else 1.0, chord, key)
                        self.strike("boom", bar_at, 0.95 if end == "stop" else 1.0, chord, key)
                    elif end == "ring":
                        # Around the toms, high to low, in sixteenths (eighths when it is fast), growing to the last hit.
                        step = 0.25 if self.fam.bpm <= 150 else 0.5
                        count = int(round(beats / step))
                        around = ("tom high", "tom high", "tom", "tom", "tom low", "tom low", "snare", "snare")
                        rolled = bars - 2 - (bars - (4 if bars >= 8 else 2))          # which of the ringing bars this is
                        for index in range(count):
                            grow = (rolled + index / count) / max(bars - 2 - (bars - (4 if bars >= 8 else 2)) + 1, 1)
                            self.strike(around[index * len(around) // count], bar_at + index * step, 0.5 + 0.45 * grow, chord, key)
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
                if self.soft_war:
                    enter, whole = enter + 0.1, whole + 0.08            # lighter music: a little later up the rise, and softer
            if along < enter:
                return None, 0.0
            return ("low" if along < whole else "full"), (0.55 + 0.45 * along) * (0.9 if self.soft_war else 1.0)
        if ch.band:
            return {"open": ("low", 0.6), "valley": ("single", 0.5)}.get(part, (None, 0.0)) if fight else (None, 0.0)
        if part == "arrival":
            return ("full", 0.8) if self.soft_war else ("top", 0.9 if fight else 0.85)
        if part == "summit":
            return "top", 0.92 if self.soft_war else 1.0
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
        rng, beats, pulse, starts = self.own("drum cycle"), self.beats, self.pulse, self.starts
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
        rng, beats, pulse, starts = self.own("frame cycle"), self.beats, self.pulse, self.starts
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
            if self.has_war and (summit or not self.soft_war):          # lighter music: the boom at its summit only
                for bar in rounds:
                    self.put("drums", "boom", first + bar * beats, 1.0, 36, (1.0 if summit else 0.85) if bar == 0 else (0.75 if summit else 0.65))
            if self.has_gong and summit and not self.tam_tam:          # grim music has the tam-tam there (`colours`)
                self.put("drums", "gong", first, 2.0, 48, 0.85)
                if ch.weight >= 1.0 and len(rounds) > 1:
                    self.put("drums", "gong", first + rounds[-1] * beats, 2.0, 48, 0.7)
            if self.embers:
                on = self.starts[1] if len(self.starts) > 1 else beats / 2
                for bar in range(0, bars, 2 if summit else 4):
                    self.put("drums", "anvil", first + bar * beats + on, 0.5, 60, 0.75 if summit else 0.6)
        self.colours()

    # --- effect marks --------------------------------------------------------------------------
    def breathe(self) -> None:
        """A wind player breathes (2026-11-18, Moonshine Blues: its harmonica held one chord a minute, notes 16 and 24
        bars long, as an organ would, and the boredom meter heard its opening unchanged 25 bars). A note held longer than
        a breath (BREATH) is played as breaths of whole bars, each let go half a beat before the next bar line it reaches
        and taken up again on it; an accordion's bellows turn the same way, less often."""
        bar_s = self.beats * 60.0 / self.fam.bpm
        for parts in self.voices.values():
            for voice in parts.values():
                breath = BREATH.get(voice.instrument)
                if not breath or voice.drums or not voice.notes:
                    continue
                span = max(1, int(breath / bar_s)) * self.beats
                out: list[Note] = []
                for note in voice.notes:
                    end = note.start + note.length
                    if note.length <= span + 0.01:
                        out.append(note)
                        continue
                    at = note.start
                    while end - at > 0.01:
                        upto = min((math.floor(at / span + 1e-6) + 1) * span, end)
                        last = end - upto <= 0.01
                        length = upto - at if last else max(upto - at - 0.5, 0.5)
                        out.append(Note(at, length, note.pitch, note.loud))
                        at = upto
                voice.notes = sorted(out, key=lambda note: (note.start, note.pitch))

    def effects(self) -> None:
        """Effect marks where the music asks for them, on the part that plays it (2026-11-18: "guitars should have
        effects in the 70s bro", "the music itself should denote the effects it shouldnt be standard"). A band's
        guitars, as a player of the time works his pedals:

        - a rhythm guitar whose chords ring is coloured where a passage comes back, the first time it is heard dry:
          by a phaser that sweeps once for each chord it holds, or in some takes by a slow flanger;
        - a chord held into an arrival is flanged by hand across exactly that chord, and is dry when the arrival lands;
        - a long rise opens on the rhythm guitar's wah, held at the heel as it begins and brought by hand to the toe, and so
          does a long opening, on the guitar that carries its riff, across its second half;
        - the lead's busy runs at a moment go through a wah rocked at the pace of its own notes, and a long note held
          at a moment is opened slowly from heel to toe (the cry);
        - a clean guitar's broken chords that ring in the quiet go through a vibe, and where the clean guitar is the band's
          whole accompaniment, wherever a passage comes back.

        Chugs, stabs and short notes stay dry, and so does everything where the music does not ask. The marks follow
        this take's own notes, so no two takes have them in the same places. (`BAND_PEDALS`, on since the demos were
        heard, var/listen/now.html.)"""
        if not self.ch.band:
            if ORCHESTRA_MARKS:
                self._orchestra_marks()
            return
        if not BAND_PEDALS:
            return
        rng = random.Random(self.fam.seed * 7919 + self.take * 104729 + 17)      # its own: the writing's draws are not moved
        depth = 0.6 if self.ch.light else 1.0
        colour = rng.choice(("phaser", "phaser", "flanger"))                      # how this take colours a passage come back
        heard: set[tuple[str, ...]] = set()
        returns = []
        for section, first, _, _ in self.spans:
            harmony = tuple(section.chords)
            returns.append(harmony in heard or section.part in ("valley", "summit"))
            heard.add(harmony)
        riffs = any(voice.instrument == "rhythm guitar" and voice.notes for parts in self.voices.values() for voice in parts.values())
        for channel, parts in self.voices.items():
            for name, voice in parts.items():
                if not voice.notes or voice.drums:
                    continue
                if voice.instrument == "rhythm guitar":
                    self._ringing_marks(voice, returns, colour, depth)
                    self._opening_marks(voice, depth)
                elif name.endswith(" solo"):
                    self._solo_marks(voice, depth)
                elif voice.instrument == "lead guitar" and "twin" not in name:
                    self._lead_marks(voice, depth)          # (a second guitar in harmony stays dry: the harmony is its colour)
                elif voice.instrument == "guitar":
                    self._vibe_marks(voice, depth)
                    if not riffs:
                        self._shimmer_marks(voice, depth)
                elif voice.instrument == "single guitar":
                    self._opening_marks(voice, depth)

    def _orchestra_marks(self) -> None:
        """An orchestra's effects, where its music asks (2026-11-18: "this might apply to other genres too"): the valley
        further off, its pads' top closing as it begins and opening again at the climb, as the far end of a hall sounds;
        and a plucked or struck line's last note of each phrase left to hang in an echo (a harp's, a celesta's), not one
        echo on every note. A light piece has them less far."""
        beats = self.beats
        depth = 0.6 if self.ch.light else 0.8
        valley = next(((first, first + section.bars * beats) for section, first, _, _ in self.spans if section.part == "valley"), None)
        for channel, parts in self.voices.items():
            for voice in parts.values():
                if not voice.notes or voice.drums:
                    continue
                if valley and channel == "texture" and voice.instrument in DISTANT and self._notes_in(voice, *valley):
                    a, b = valley
                    turn = min(2 * beats, (b - a) / 4)
                    voice.mark("lowpass", [(a - 0.05, 20000.0), (a + turn, 3500.0), (b - turn, 3500.0), (b, 20000.0)])
                    voice.set("lowpass resonance", 0.05)
                if voice.instrument in STRUCK and channel in ("lead", "rhythm", "texture"):
                    phrases: dict[int, list[Note]] = {}
                    for note in voice.notes:
                        phrases.setdefault(int(note.start // (4 * beats)), []).append(note)
                    points: list[tuple[float, float]] = []
                    for _, mine in sorted(phrases.items()):
                        last = max(mine, key=lambda note: note.start)
                        end = last.start + last.length
                        points += [(last.start - 0.05, 0.0), (last.start, depth), (end + 0.25, depth), (end + 0.75, 0.0)]
                    if points:
                        voice.mark("echo", points)
                        voice.set("echo beats", 0.75)
                        voice.set("echo feedback", 0.4)

    def _notes_in(self, voice: Voice, first: float, last: float) -> list[Note]:
        return [note for note in voice.notes if first - 1e-6 <= note.start < last - 1e-6]

    @staticmethod
    def _sounding(notes: list[Note], first: float, last: float) -> float:
        """How much of a stretch a part sounds in, 0 to 1: strummed chords that run into each other near 1, palm-muted
        chugs with air between them well under."""
        spans = sorted((max(note.start, first), min(note.start + note.length, last)) for note in notes)
        total, reach = 0.0, first
        for start, end in spans:
            if end > reach:
                total += end - max(start, reach)
                reach = end
        return total / max(last - first, 1e-6)

    def _ringing_marks(self, voice: Voice, returns: list[bool], colour: str, depth: float) -> None:
        """A rhythm guitar's colour where a passage comes back and its chords ring, and its jet into an arrival."""
        beats = self.beats
        bars_a_chord: list[float] = []
        for (section, first, _, _), back in zip(self.spans, returns):
            last = first + section.bars * beats
            notes = self._notes_in(voice, first, last)
            if not notes:
                continue
            if section.story == "rise":
                # The jet: a chord held two beats or more that rings into the arrival, flanged by hand from its first beat
                # to the arrival, the delay drawn from short to long and back to the middle as the chord dies into it.
                held = [note for note in notes if note.length >= 2.0 and note.start + note.length >= last - beats - self.breath]
                jet = min(note.start for note in held) if held else None
                if section.bars >= 16:
                    # A long rise opens (2026-11-18, the boredom meter: a battle piece's rhythm guitar kept one colour
                    # through a 36-bar rise): the wah rocked back to the heel as the rise begins, dark, and brought forward
                    # by hand to the toe by its last bars, slowly at first; let go where the jet begins or the arrival
                    # lands, so the moment comes in open and dry. Half in, the guitar keeps its body.
                    end = jet - 0.25 if jet is not None else last
                    if end - first >= 8 * beats:
                        voice.mark("wah", [(first, 0.0), (first + beats, 0.55 * depth), (end - 0.25, 0.55 * depth), (end, 0.0)])
                        voice.mark("wah depth", [(first, 0.0), (end, 0.0)])
                        voice.mark("wah position", [(first, 0.05), (first + 0.6 * (end - first), 0.4), (end - 0.25, 0.95)])
                if held:
                    start = jet
                    voice.mark("flanger", [(start - 0.25, 0.0), (start, depth), (last - 0.05, depth), (last, 0.0)])
                    # By hand while it is in; sweeping in time again once it is out (a colour of this take may use it).
                    voice.mark("flanger depth", [(start - 0.3, 1.0), (start - 0.25, 0.0), (last, 0.0), (last + 0.05, 1.0)])
                    voice.mark("flanger position", [(start, 0.0), (start + 0.7 * (last - start), 1.0), (last, 0.55)])
                continue
            if not back or section.story == "moment" or self._sounding(notes, first, last) < 0.6:
                continue                                    # heard for the first time, the moment itself, or a chug: dry
            # One sweep for each chord as it is held: the bars from one change of chord to the next, as the section has them.
            changes = 1 + sum(1 for before, after in zip(section.chords, section.chords[1:]) if after != before)
            bars_a_chord.append(section.bars / changes)
            fade = min(beats, 0.25 * section.bars * beats)
            voice.mark(colour, [(first, 0.0), (first + fade, depth), (last - fade, depth), (last, 0.0)])
        if bars_a_chord:
            sweep = min(max(statistics.median(bars_a_chord), 0.5), 4.0)
            voice.set("phaser bars" if colour == "phaser" else "flanger bars", sweep if colour == "phaser" else 2.0 * sweep)
            voice.set("phaser feedback" if colour == "phaser" else "flanger feedback", 0.5 if colour == "phaser" else 0.4)
        if "flanger" in voice.effects:
            voice.set("flanger feedback", voice.settings.get("flanger feedback", 0.7))

    def _lead_marks(self, voice: Voice, depth: float) -> None:
        """The lead's wah at the moments: rocked at the pace of its own notes through a busy run (at the first moment
        only where it runs hard, at the summit wherever it is busy), and opened by hand across a long held note."""
        beats = self.beats
        paces = []
        for section, first, _, _ in self.spans:
            if section.story != "moment" or (section.part == "summit" and self.soloed):
                continue                            # (a summit with a solo has no pedal: see _solo_marks)
            last = first + section.bars * beats
            notes = self._notes_in(voice, first, last)
            if not notes:
                continue
            onsets = sorted({round(note.start, 3) for note in notes})
            gaps = [after - before for before, after in zip(onsets, onsets[1:]) if after - before > 0.05]
            busy = len(onsets) / (last - first)
            long_notes = [note for note in notes if note.length >= 2.0]
            rocked = busy >= (1.0 if section.part == "summit" else 1.5) and bool(gaps)
            if rocked:
                paces.append(statistics.median(gaps))
                voice.mark("wah", [(first, 0.0), (first + 0.5, depth), (last - 0.5, depth), (last, 0.0)])
                voice.mark("wah depth", [(first, 0.9), (last, 0.9)])
            for note in long_notes:
                # The cry: rocking stops, the pedal goes back to the heel and is pushed down across the note.
                begin, end = note.start, note.start + note.length
                if not rocked:
                    voice.mark("wah", [(begin - 0.1, 0.0), (begin, depth), (end - 0.1, depth), (end, 0.0)])
                voice.mark("wah depth", [(begin - 0.05, 0.9), (begin, 0.0), (end - 0.05, 0.0), (end, 0.9)])
                voice.mark("wah position", [(begin, 0.1), (begin + 0.75 * (end - begin), 0.95), (end, 0.95)])
        if paces:
            pace = statistics.median(paces)
            voice.set("wah beats", 0.5 if pace <= 0.3 else 1.0)       # rocked in eighths over sixteenths, else on every beat

    def _solo_marks(self, voice: Voice, depth: float) -> None:
        """The solo's colour: no pedal at all, and a tape echo a dotted eighth behind it, so that its held notes sing on
        into the room. (The first solo was rocked on the wah from end to end and its every long note made to cry: "all
        wammy no chill", "thats not a guitar solo thats a solo effect track", 2026-11-18.)"""
        first = min(note.start for note in voice.notes)
        last = max(note.start + note.length for note in voice.notes)
        send = 0.35 if depth >= 1.0 else 0.28
        voice.mark("echo", [(first - 0.1, 0.0), (first, send), (last, send), (last + 1.5, 0.0)])
        voice.set("echo beats", 0.75)
        voice.set("echo feedback", 0.3)
        if SOLO_FLANGER:
            # (2026-11-19, 13:15: "i think you need the solos to do some flange shit like move a little".) A flanger sweeping
            # in time under it, a little: in from its first bar, opening a little more toward its peak, its highest note, and
            # out as it ends. Each solo its own sweep (one bar, two or four) and its own bite (the feedback). Never rocked by
            # hand, never on every note: it moves, it does not cry.
            mine = random.Random("solo flanger/%d/%d/%s" % (self.fam.seed, self.take, voice.instrument))
            amount = 0.3 if depth >= 1.0 else 0.24
            peak = max(voice.notes, key=lambda note: (note.pitch, -note.start)).start
            ease = min(self.beats, max(peak - first, 0.5) / 2)
            voice.mark("flanger", [(first - 0.1, 0.0), (first + ease, amount), (max(peak, first + ease + 0.05), amount * 1.5),
                                   (max(last - self.beats, peak + 0.1), amount * 1.2), (last + 0.5, 0.0)])
            voice.set("flanger bars", mine.choice((1.0, 2.0, 2.0, 4.0)))
            voice.set("flanger feedback", mine.choice((0.3, 0.45, 0.6)))
        # Over the band, as a solo stands: played at the lead's level it was 2 dB under the rhythm guitars and 4 under the
        # twin guitars' theme after it (Free Blades' demo, 22:25).
        voice.set("gain db", SOLO_LIFT)

    def _opening_marks(self, voice: Voice, depth: float) -> None:
        """The guitar that carries a long opening's riff (16 bars or more: Cobra Fever's lone guitar went 20 bars without
        a change, 2026-11-18; in Hammer Thunder's fifth take the band opens together and the rhythm guitar carried the
        16): dry for the first half, then the wah held at the heel and opened by hand to the toe by its last bar, slowly
        at first, and let go as the band comes in with the first theme, as a long rise opens. A guitar that only counts
        the band in at the opening's end is left dry."""
        beats = self.beats
        for section, first, _, _ in self.spans:
            if section.story != "open" or section.bars < 16:
                continue
            last = first + section.bars * beats
            begin, end = first + (section.bars // 2) * beats, last - 0.25
            halves = section.bars - section.bars // 2
            playing = sum(1 for bar in range(halves) if self._notes_in(voice, begin + bar * beats, begin + (bar + 1) * beats))
            if playing < 0.75 * halves:
                continue                                    # (a riff of short strokes plays in every bar: that is carrying it)
            voice.mark("wah", [(begin - 0.25, 0.0), (begin + beats, 0.55 * depth), (end - 0.25, 0.55 * depth), (end, 0.0)])
            voice.mark("wah depth", [(begin - 0.3, 0.0), (end, 0.0)])
            voice.mark("wah position", [(begin, 0.05), (begin + 0.6 * (end - begin), 0.4), (end - 0.25, 0.95)])

    def _shimmer_marks(self, voice: Voice, depth: float) -> None:
        """A clean guitar that is the band's whole accompaniment (a light band's broken chords, with no rhythm guitar:
        Lantern Walk, 2026-11-18, had no mark at all, its guitar playing only where the music is above the quiet): dry
        through the first theme, the vibe coming in with the second and staying through the moments, where a light band's
        arpeggios want the shimmer that a heavy band's arrival, struck dry, does not. The rises are left as they are."""
        beats = self.beats
        for section, first, _, _ in self.spans:
            if section.part not in ("second", "arrival", "summit") or max(section.level) <= VIBE_QUIET:
                continue                                    # (the quiet passages are the vibe's own: `_vibe_marks`)
            last = first + section.bars * beats
            notes = self._notes_in(voice, first, last)
            if not notes or self._sounding(notes, first, last) < 0.5:
                continue
            fade = min(2.0, 0.25 * section.bars * beats)
            voice.mark("phaser", [(first, 0.0), (first + fade, 0.85 * depth), (last - fade, 0.85 * depth), (last, 0.0)])

    def _vibe_marks(self, voice: Voice, depth: float) -> None:
        """A clean guitar's vibe where its broken chords ring in the quiet."""
        beats = self.beats
        for section, first, _, _ in self.spans:
            last = first + section.bars * beats
            notes = self._notes_in(voice, first, last)
            if not notes or max(section.level) > VIBE_QUIET or self._sounding(notes, first, last) < 0.5:
                continue
            fade = min(2.0, 0.25 * section.bars * beats)
            voice.mark("phaser", [(first, 0.0), (first + fade, 0.85 * depth), (last - fade, 0.85 * depth), (last, 0.0)])
            voice.set("phaser bars", 0.5)
            voice.set("phaser feedback", 0.35)

    def colours(self) -> None:
        """What Muse Percussion adds (see `cast`). The tam-tam: struck at the summit of grim
        heavy music (in place of the gong) and at the arrival of a boss, and touched softly as a
        dark cave's music opens. The mark tree: brushed into each moment of light and mystic
        music, and into the second time round its first theme. A soft roll on the suspended
        cymbal into the moments of light music, which has no swell of its own. The field drum:
        a roll into each moment of regal music and of the battlegrounds, and at the summit its
        march on the off-beats. The taikos: with the big drums at the summits of jungle, fire
        and desert music and of the fights, and their pickup into each moment. The bass drum's
        rumble under a storm's rise."""
        ch, beats, period = self.ch, self.beats, self.fam.period
        beat_s = 60.0 / self.fam.bpm

        def roll(name: str, end: float, seconds: float, low: float, high: float, pitch: int, before: float) -> None:
            length = min(max(seconds / beat_s, 1.0), before)
            voice = self.voice("drums", name)
            voice.add(end - length, length, pitch, high)
            voice.swells += [(end - length, low), (end - 0.01, high), (end + 0.01, low)]

        for index, (section, first, _, _) in enumerate(self.spans):
            part, bars = section.part, section.bars
            before = self.spans[index - 1][0].bars * beats if index else 0.0
            moment = part in ("arrival", "summit")
            summit = part == "summit"
            if self.tam_tam:
                if summit:
                    self.put("drums", "tam-tam", first, 4.0, 52, 0.85)
                elif part == "arrival" and ch.role == "boss":
                    self.put("drums", "tam-tam", first, 4.0, 52, 0.7)
                elif part == "open" and ch.role == "depths":
                    self.put("drums", "tam-tam", first, 4.0, 52, 0.3)
            if self.tree and before:
                if moment:
                    self.put("drums", "mark tree", first - min(1.0, before), 2.0, 84, 0.55 if summit else 0.45)
                elif part == "first" and bars > period and "mystic" in ch.kinds:
                    self.put("drums", "mark tree", first + period * beats - 1.0, 2.0, 84, 0.35)
            if self.soft_roll and moment and before:
                roll("cymbal roll", first, 3.0 if summit else 2.0, 0.08, 0.5 if summit else 0.4, 57, before)
            if self.field and before:
                if moment:
                    roll("field drum roll", first, 2.0 if summit else 1.5, 0.2, 0.75 if summit else 0.6, 38, before)
                if summit:
                    offs = [start + self.pulse / 2 for start in self.starts] if self.pulse == 1.0 else self.starts[1:]
                    for bar in range(0, bars, 2):
                        for on in offs:
                            self.put("drums", "field drum", first + bar * beats + on, 0.25, 38, 0.45)
            if self.taikos and moment:
                if before:
                    for count in range(4):                         # the pickup: four strokes, rising, into the moment
                        self.put("drums", "taikos", first - (4 - count) * self.pulse / 2, 0.25, 86, 0.4 + 0.12 * count)
                if summit:
                    for bar in range(bars):
                        for number, on in enumerate(self.starts):
                            self.put("drums", "taikos", first + bar * beats + on, 0.5, 87, 0.85 if number == 0 else 0.65)
            if self.rumble and part in ("build", "climb"):
                end = first + bars * beats
                roll("concert drum roll", end, 4.0 if part == "climb" else 3.0, 0.1, 0.8, 36, bars * beats)
