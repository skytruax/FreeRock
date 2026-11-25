"""Writing the studio's library: which families there are, and playing every take of them.

The orchestra's families are for the Warcraft style and the band's for Knight Rock; both are
written by studio.orchestra and played in REAPER (studio.desk): every instrument line a track
of real recorded instruments or of the Surge XT synth, in a project that is kept beside the
staged track.

    uv run --no-sync python -m freerock.studio.build                 every family, every take
    uv run --no-sync python -m freerock.studio.build --list          what there would be
    uv run --no-sync python -m freerock.studio.build --only reel     only families whose name has "reel" in it
    uv run --no-sync python -m freerock.studio.build --style knight  only the band's

A take that is staged already is left alone, so the command can be stopped and run again.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

from .. import analysis, forever
from . import RATE, desk, muse, reaper, sounds, stage_root, write_track
from .orchestra import CHANNELS, CHARACTERS, INSTRUMENTS, STRUMS, Family, Take, band_of, borrow, borrowed, family, fresh, given, held, settings_of
from .score import Sheet, humanise

VAR = Path(__file__).resolve().parents[3] / "var"
PROJECTS = VAR / "reaper" / "projects"       # every track's REAPER project is kept here, to be opened and changed by hand
MASTER = 20261115
# Where each channel sits when everyone is playing (LUFS at the moment, before the whole track
# is brought to the bucket's level): the tune on top, the pad and the accompaniment under it.
# (The drums and the bass of every style a little nearer again, the light ones most: "go a little harder this is not world of fairy craft", 2026-11-17, 21:50, played. They were
# PLACE drums -21, bass -18.5; LIGHT -22, -20; SOFT_WAR_DRUMS -19.5; WAR_DRUMS -16; BAND drums -18; BAND_LIGHT -19.5, -20, -19.)
PLACE = {"lead": -17.0, "texture": -21.0, "rhythm": -21.5, "bass": -18.0, "drums": -20.0}       # an orchestra's drums are a few great strokes: by loudness they sit low
# A light track's drums and bass sit a little further back (2026-11-17, evening, played: "just a bit light and wimpy in
# general", "in all genres", then "go a little harder": 3.5 and 2.5 dB nearer than they were at first, -24 and -21.5).
LIGHT = {"drums": -20.5, "bass": -19.0}
SOFT_WAR_DRUMS = -18.0                         # where a lighter track's softer war drums sit (`orchestra.Take.soft_war`)
WAR_DRUMS = -15.5                              # where the drums sit in a track that has war drums: up with the tune, the loudest strokes in the piece
BAND = {"lead": -17.0, "rhythm": -18.5, "drums": -17.5, "bass": -19.5, "texture": -24.0}       # a band: guitars and drums up front
BAND_LIGHT = {"drums": -18.5, "bass": -19.5, "rhythm": -18.5}      # (2 to 2.5 dB nearer since "light and wimpy" and "a little harder")
# Each band's record is balanced its own way (orchestra.BANDS; 2026-11-23, "all the knight rock songs sound like the same song": the same five places in every
# one): dB over or under the places above. The doom band is its guitars and its bass, the chop its drums, the lounge and the twang their singers, the
# cathedral its organ and its choir, the saloon its piano.
BAND_BALANCE = {"doom": {"rhythm": 1.0, "bass": 1.0, "drums": -1.0, "lead": -0.5}, "stoner": {"rhythm": 0.5, "bass": 1.0, "drums": -0.5},
                "tweed": {"rhythm": -0.5, "lead": 0.5}, "chop": {"drums": 1.0, "rhythm": -1.5, "bass": 0.5},
                "shanty": {"rhythm": -1.0, "lead": 0.5, "texture": 0.5}, "twang": {"rhythm": -1.0, "drums": -0.5, "lead": 0.5, "texture": 1.0},
                "lounge": {"rhythm": -1.5, "drums": -1.0, "bass": 0.5, "lead": 0.5}, "cellos": {"rhythm": 0.5, "drums": -1.0},
                "cathedral": {"rhythm": 0.5, "texture": 1.0, "drums": -0.5}, "saloon": {"rhythm": 0.5, "drums": -1.0, "bass": -0.5},
                "hammond": {"rhythm": 0.5, "drums": 0.5, "bass": -1.5}, "grit": {"rhythm": -0.5, "bass": 0.5}, "baroque": {"rhythm": -0.5, "texture": 0.5, "drums": -1.0},
                "bones": {"rhythm": 1.0, "drums": -0.5}, "garage": {"rhythm": 0.5, "lead": 0.5}, "skald": {"rhythm": 1.0, "texture": 0.5, "drums": -0.5},
                "brawl": {"rhythm": 0.5, "bass": -1.0, "drums": 0.5}, "noir": {"rhythm": -1.0, "bass": 0.5, "drums": -0.5}, "jug": {"rhythm": 0.5, "lead": 0.5, "drums": -1.0},
                "drumline": {"rhythm": 0.5, "bass": -0.5, "drums": 1.0}}
RIDE = 0.15                    # how far each part of the story is brought up towards the loudest part (it was 0.42, which
                               # took most of the written dynamics away: "rewrite all music to be more dynamic", 2026-11-16)
# The least each channel is played at in each part of the story, so that the story is whole
# whatever the game is doing; the game then only adds weight to the drums and the bass.
# Under every stroke of the kick the other channels give way for a moment and come back within
# a quarter of a second: drawn into each channel's volume, the same at every stroke (how dance
# music makes room for its kick: a drawn curve, not a compressor that listens). How far each
# channel is turned down under the hardest stroke, as a part of its level.
DUCK = {"bass": 0.56, "texture": 0.8, "rhythm": 0.8, "lead": 0.9}
DRUMS_UP = 6.0                 # dB: the most the drums are ever turned up to reach their place
# A song is heard from its first bar (2026-11-24, the day's seven Warcraft songs studied: every one opened at -37 to -41 LUFS; then counted: 169 of the 521 songs of Warcraft's
# library under -36, which a game's own sounds cover: the first minute of them is not heard at all. The characters that `opens` are written louder there, and they are the
# newest alone). An opening stands no further than this under its song's loudest part, and is brought up no more than this for it. (16 and 9 dB at first, the same evening: the
# thirty songs of the day stand at -17 to -21 at their loudest, so that an opening of -43 came up to -36 and was not heard still; three or four under the first theme is an opening.)
OPEN_UNDER, OPEN_MOST = 13.0, 12.0
# ...nor is its first theme under hearing (2026-11-25: a slow burn's opening and first theme stood at -36 and -37 in Basalt Walk, at -35 and -35 in Spur-Lit Halter, and an opening goes no higher than what it leads
# to): no further than this under the loudest part, brought up no more than this, and never over the part after it.
FIRST_UNDER, FIRST_MOST = 11.0, 8.0
# ...and what comes between them and a song's first arrival (its first part within ARRIVES of the loudest) is brought half way to this under it: five of nine parts of Forlorn Hope, a slow burn's four minutes, stood
# at -37 to -31 under a moment of -22 and a summit of -19 (2026-11-25). A song that arrives with its first theme or its second has nothing between.
EARLY_UNDER, EARLY_SHARE, ARRIVES = 10.0, 0.5, 8.0
# ...and a valley may be quiet and not gone: what stands further than this under the loudest after that (its close left as it is) is brought half way back to it (2026-11-25: Bluebell Fold's at -41 under a summit of
# -20, Wakeful Relief's, Winter-Dead Wind's and Siren-Grey Cloister's at -37 and -38: of the library's valleys 188 of 453 in Knight Rock and 190 of 593 in Warcraft stand 16 dB or more under, a minute of a tune
# sung alone under a game's own sounds).
LOW_UNDER, LOW_SHARE = 15.0, 0.5
MUSE_WORKERS = 5               # how many parts of a piece MuseScore performs at once
# (2026-11-16, twice. In the afternoon: "theres not much difference between quet and full, we want more ...
# drasticness", and a calm game was given no drums and a third of the bass. Played that evening: "the abruptness
# between fighting and not, its way too much now, it should only be a subtle difference like before". So these are
# as they were before: the drums and the bass stand at 55 to 100% whatever the game does, and a fight adds the rest.)
FLOOR = {"open": {"rhythm": 1.0, "bass": 0.85, "drums": 0.6}, "theme": {"rhythm": 1.0, "bass": 0.85, "drums": 0.55},
         "rise": {"rhythm": 1.0, "bass": 0.9, "drums": 0.75}, "moment": {"rhythm": 1.0, "bass": 1.0, "drums": 0.9},
         "close": {"rhythm": 1.0, "bass": 0.85, "drums": 0.55}}


# Characters written after the camps were named, kept to the end of the plan so that no family made before is given
# another title: the dungeon bosses of 2026-11-17's afternoon.
LAST_ADDED = ("deep tide", "fallen crusade",
              # (the same evening, for the new kinds of place: the marsh, the coast, the snowfields)
              "bog lights", "grey fen", "sea breeze", "salt road", "lighthouse", "ice fields", "white waste",
              # (and their own music for every moment: "it only matters if those new categories have different families of songs")
              "frog chorus", "bog inn", "drowned grotto", "reed fire", "bog beast", "sailors rest", "tide cave", "driftwood fire",
              "sea king", "sea storm", "aurora", "mead hall", "ice cave", "frost camp", "frost wyrm", "whiteout",
              # (Knight Rock's for the new kinds)
              "bayou boogie", "sea dog", "frost hammer",
              # (and more of its walking music for the hills and fields: "feel like i hear the same knight rock one over and over")
              "hill country", "harvest boogie", "iron vow", "free company",
              # (the next night: more music for Knight Rock's moments, and Warcraft's storms for the places that had none)
              "barroom blues", "dwarf hall", "road camp", "glow cave", "low tunnel", "midnight ride", "downpour run",
              "field storm", "monsoon", "witch storm",
              # (2026-11-18: Knight Rock's towns, a second boss and a battleground)
              "market square", "royal march", "warlord", "banner war")


def _shapes_last(character) -> list[int]:
    """The takes of each family of a character named last: as the others of its sort have them, all at once."""
    if character.role == "wander":
        return [3, 2]
    if character.role in ("town", "battleground"):
        return [3, 3]
    return [2, 2]


# (2026-11-22: "tonight we need new music following everything we learned"; "lets work on filling that drive with more music
# for every scenario, following everything weve learned".) How many families each character of Knight Rock and of Warcraft has
# beyond the plan's own (`plan`), by style: each one more song for its kind of place. 0 (or no entry): the plan's own, as
# before. (That night Knight Rock, the music they play, was given a second round: Warcraft had 210 first takes still to make.)
MORE_FAMILIES = {"knight": 2, "warcraft": 2}
# The families that had a take before 2026-11-25: their themes come back as they were first told. In every other a theme is told another way each time (`Character.grows`): of 430 Knight Rock songs the middle one had 46% of
# its tune's bars heard before, and seventeen of one night's new ones 50 to 66, the fourth families of characters that were written before it was.
TOLD_ONCE = frozenset((Path(__file__).parent / "told_once.txt").read_text(encoding="utf-8").split())


# House's titles (house.PLAN's, the test keeps them the same), written out here so that the plan, which the study and the lanes
# read without the House synthesiser's numba, need not import house (2026-11-22: it did for an afternoon, and every study of a
# Knight or Warcraft take stopped on "No module named 'numba'").
HOUSE_TITLES = (
    'Ambush', 'Ash Bucket', 'Ash Wind', 'Back Room', 'Backwater', 'Bad Debt', 'Banners', 'Barbed Wire', 'Basement Bar',
    'Bedroll Sky', 'Bellows and Sparks', 'Bells under the Hill', 'Bilge Pump', 'Black Frost', 'Black Market',
    'Black Rain', 'Black Water', 'Blackout', 'Blades', 'Blast Furnace', 'Boiler Room', 'Bone Procession', 'Bone Saw',
    'Breakers', 'Breakwater', 'Brownout', 'Bullfrog Bass', 'Buried Machine', 'Burn Barrel', 'By the Fire',
    'Cairn Wind', 'Cannonade', 'Canopy', 'Capture the Flag', 'Caravan at Noon', 'Cellar Door', 'Chain Gang', 'Charge',
    'Cinder Bloom', 'Closing Time', 'Cold Ashes', 'Cold Iron', 'Cold Stars', 'Cold Storage', 'Cool of the Evening',
    'Crawlspace', 'Curfew Bell', 'Customs Wall', 'Dead Hours', 'Dead Pixel', 'Dead Radio', 'Dead Reckoning',
    'Desert Nocturne', 'Dewfall', 'Dim Lamp Alley', 'Driftwood Hearth', 'Dripstone', 'Drop Shaft', 'Drowned Halls',
    'Drowned King', 'Dry Dock', 'Dunes at Dawn', 'Eclipse Gate', 'Embers under Stars', 'Empty Throne', 'Fireflies',
    'Fishmarket', 'Flat Beer', 'Frostbite', 'Frozen Echoes', 'Furnace Psalm', 'Gallows Meadow', 'Gaslight',
    'Ghostfire', 'Gilded Halls', 'Glade at Dusk', 'Glowworm Hollow', 'Grain Silo', 'Gravel Pit', 'Graveyard Shift',
    'Guard Dog', 'Guildhall Steps', "Gull's Morning", 'Hammerfall', 'Hanging Tree', 'Harbour Lights',
    'Hay Bale Sunset', 'Heat Haze', 'Hoarfrost', 'Hold the Line', 'Hollow Road', 'Hushed Parlour', 'Ice Bridge',
    'Ice Drill', 'Ice Fang', 'Ice Fishing', 'Insomnia', 'Iron Lung', 'Keelhaul', 'Knife Bazaar', 'Knuckle Duster',
    'Lanterns in the Fog', 'Lanterns on the Square', 'Larks over the Ridge', 'Last Bus', 'Last Candle', 'Last Stand',
    'Loading Bay', 'Lock-Up', 'Lodestone', 'Long Road Home', 'Low Ceiling', 'Low Rafters', 'Market Day', 'Meat Locker',
    'Mended Nets', 'Mill Stream', 'Mint Tea', 'Mirage', 'Monsoon Drums', 'Moonless', 'Moonlit Ebb', 'Moonwell',
    'Morning on the Hill', 'Moth Wings', 'Night Prowl', 'Night Shift', 'Night Watchman', 'No Fire Tonight',
    'Nomad Fire', 'Northern Lights', 'Oasis', 'Oil Drum', 'Ossuary', 'Owl Light', 'Parrots', 'Pawn Shop', 'Peat Smoke',
    'Power Cut', 'Rail Yard', 'Rain on the Roofs', 'Red Moon', 'Red Rock', 'Reedlight', 'Riot Line', 'River Drums',
    'Rock Crusher', 'Rockfall', 'Rust Water', 'Salt Caravan', 'Sandblast', 'Sandstone Hollow', 'Scarecrow Road',
    'Scrap Yard', 'Seaspray', 'Short Circuit', 'Siege Bells', 'Signal Box', 'Slag Heap', 'Sleepless Shift',
    'Slot Machine', 'Smog Quarter', 'Smoke Break', 'Snowglobe', 'Snowmelt', 'Speakeasy', 'Squall', 'Stand Fast',
    'Standing Dead', 'Starfall', 'Stone and Sky', 'Strangler Fig', 'Stray Dogs', 'Strip Mine', 'Sump', 'Sunken Grotto',
    'Sunlit Fields', 'The Dark Hall', 'The Deep Road', 'The Forge at Rest', "The Headsman's Walk", 'The High Moor',
    'The Kind Ghost', "The King's Road", 'The Leviathan', 'The Long Wait', 'The Long Watch', 'The Old Swamp',
    'The Usurper', 'Third Rail', 'Throne of Ash', 'Thunderhead', 'Tide Camp', 'Tidepools', 'Toll Booth', 'Trench Line',
    'Under the Mountain', "Undertaker's Table", 'Voltage', 'Vulture Sky', 'Weigh Station', 'Wet Powder',
    'Whispering Boughs', 'White Grave', "Will-o'-the-Wisp", 'Willow Lanterns', 'Wind over the Pass',
    "Wreckers' Lantern", 'Wrecking Ball',
)


def plan() -> list[tuple[Family, int]]:
    """Every family of the library and how many takes of it there are. A character that is
    for walking about gets a family of three takes (and the light ones a second family of
    two, since light places hear nothing else); the rarer moments get fewer."""
    out: list[tuple[Family, int]] = []
    titles: set[str] = set()

    numbers: dict[int, set[int]] = {}

    def add(index: int, character, number: int, takes: int) -> None:
        if number >= 10:      # (its seed would be the next character's family's: MORE_FAMILIES has outgrown the seeds)
            raise ValueError("%s: a family numbered %d would have another character's seed" % (character.name, number + 1))
        numbers.setdefault(index, set()).add(number)
        seed = MASTER * 100 + index * 10 + number
        rng = random.Random(seed)
        first, second = character.titles
        title = None
        for _ in range(50):
            title = "%s %s" % (rng.choice(first), rng.choice(second))
            if title not in titles:
                break
        titles.add(title)
        place = character.kinds[0] if len(character.kinds) < 5 else "anywhere"
        name = "%s-%s-%d" % (place, character.name.replace(" ", "-"), number + 1)
        # (A house band's character's families past its third are another band's songs: orchestra.fresh.)
        made = fresh(character, number)
        out.append((family(made if made.grows or name in TOLD_ONCE else replace(made, grows=True), seed, name, title), takes))

    later, camps, last = [], [], []
    for index, character in enumerate(CHARACTERS):
        if character.name in LAST_ADDED:
            last.append((index, character))           # (see below)
            continue
        if character.role == "camp":
            camps.append((index, character))          # (see below)
            continue
        if character.role == "wander":
            shapes = [3, 2] if character.light or character.band else [3]
            if not (character.light or character.band):
                later.append((index, character))
        elif character.role in ("town", "battleground"):
            shapes = [3, 3]                 # a family of songs for a town or a battleground: two families of three
        elif character.role in ("battle", "ember", "storm", "boss"):
            shapes = [2, 2]
        else:
            shapes = [2]
            if character.role in ("depths", "night"):
                later.append((index, character))
        for number, takes in enumerate(shapes):
            add(index, character, number, takes)
    # (2026-11-16, played: "need more variety in warcraft".) The heavy music for walking about has a second family too:
    # its own key, pace, changes and tunes; and so has the music for caves ("been hearing the same thing over and
    # over": a cave had two pieces). These are named after all the others, so that no family made before is given
    # another title.
    for index, character in later:
        add(index, character, 1, 2)
    # Camping (2026-11-17: "camping should get its own tunes"): two families of two for each, named after every family
    # made before them, so that none of those is given another title.
    for index, character in camps:
        for number in (0, 1):
            add(index, character, number, 2)
    # Dungeon bosses for the kinds of place that had only the titan's (2026-11-17, afternoon: "we want lots of options of
    # inns camping, caves dungeons"): two families of two for each, named after every family made before them.
    for index, character in last:
        for number, takes in enumerate(_shapes_last(character)):
            add(index, character, number, takes)
    # (2026-11-22: "The drive is still at 11 percent tonight we need new music following everything we learned", "lets work
    # on filling that drive with more music for every scenario".) Each character has MORE_FAMILIES more families, each its
    # own key, pace, changes and tunes, two takes: Knight Rock's first (the music they play), then Warcraft's; each set named
    # after every family made before it, so that none of those is given another title, and numbered on from the
    # character's own. Each family's first take is made and studied before its second (handbook 8.7). Their titles keep clear
    # of House's too (HOUSE_TITLES; a new marsh camp had drawn Peat Smoke, a House family's): House's are written by hand unlike
    # every title here (the test), so keeping clear of them changes no title drawn before.
    # A style given more rounds than another has them after the other's last: each round is planned after every round before
    # it, Knight Rock's before Warcraft's within it, so a round added changes nothing planned before it.
    titles.update(HOUSE_TITLES)
    for round_ in range(max(MORE_FAMILIES.values(), default=0)):
        for style in ("knight", "warcraft"):
            if round_ >= MORE_FAMILIES.get(style, 0):
                continue
            for index, character in enumerate(CHARACTERS):
                if character.style == style:
                    add(index, character, max(numbers.get(index, {-1})) + 1, 2)
    return out


# What crowns a heavy piece's moments, by the kind of place it is for: who sings the pad's chords with the strings, and
# whether a bell is struck on the moment's first beat. (2026-11-16, played: "need more variety in warcraft". Every heavy
# piece had a choir and a bell at its moments, so every moment sounded alike.) Music for every kind of place, the
# fights and the storms keep the choir and the bell.
CROWNS = {"haunted": ("choir", True), "mystic": ("choir", True), "regal": ("choir", True), "infernal": ("choir", False),
          "highland": ("horns", True), "pastoral": ("horns", False), "desert": ("", False), "jungle": ("", False),
          "marsh": ("oohs", False), "coast": ("horns", False), "frozen": ("choir", True)}


CROWNS_LIGHT = {"pastoral": "horns", "highland": "horns", "regal": "horns", "mystic": "oohs", "haunted": "oohs", "jungle": "oohs",
                "desert": "", "infernal": "", "marsh": "oohs", "coast": "horns", "frozen": "oohs"}


def crown_of(character) -> tuple[str, bool]:
    if character.role in ("boss", "battleground") and not character.band:
        return "full choir", True                    # the whole choir, every voice, where the fight is greatest
    if character.light:
        return (CROWNS_LIGHT[character.kinds[0]] if len(character.kinds) < 5 else "oohs"), False
    if len(character.kinds) >= 5:
        return "choir", True
    return CROWNS[character.kinds[0]]


def folder_of(fam: Family, take: int) -> Path:
    return folder_at(fam.character.style, fam.name, take)


def folder_at(style: str, family: str, take: int) -> Path:
    return stage_root(VAR, style) / family / str(take)


def project_of(fam: Family, take: int) -> Path:
    return project_at(fam.character.style, fam.name, take)


def project_at(style: str, family: str, take: int) -> Path:
    return PROJECTS / style / family / str(take) / "track.rpp"


# (2026-11-22, night: the light bands' bass thin in its middle, 3.7 to 13 dB under the liked stems at 450 to 900 Hz in the
# studies of the day's new Knight families, the inns', camps' and nights' most.) dB more at 800 Hz on a light band's bass, over
# the sound's own 3 (sounds.MUSE_TONE), as an equaliser of its own after it. Judged (bass1, the whole sound +4 at 800 Hz, on two
# light songs, a heavy band and a Warcraft fretless): the octave at 894 Hz 3 dB nearer the liked stems in all four, the mix's
# loudness unmoved; the judges near level, SongEval up in sixteen of the light songs' twenty scores, TuneJury with the brief up
# in three of their four windows and with none down in three, while the heavy band's last drop came out down (TuneJury with no
# brief -0.18) and the fretless level. So the light band's alone: the heavy band's and the orchestra's as they were. 0: as it was.
LIGHT_BAND_BASS = 4.0


# (2026-11-23, night: the blues harp, wherever it leads a band's tune or solo, 4 to 11 dB thin in its middle and 12 to 16 over
# the liked stems at its top in the studies of the night's 71 harp takes, where a fiddle's or a guitar's solo reads 7 to 11
# over: in the lantern walk's four takes, the same song, the harp's solos +12.7 and +15.2, the fiddle's +9.3 and +10.8. A
# harp through a small amp's speaker is darker than that.) A band's harmonica lead: (where its top is closed, Hz; where its
# top is shelved down from, Hz; by how much, dB; its body at 700 Hz, dB), in place of the band lead's own tone. None: the band
# lead's tone, as the fiddle's and the guitar's. (Left off, 2026-11-23, the demo harplead1 on three harp songs, at 4500, 2500, -6 and 3:
# the lead's top 1 to 6 dB nearer the liked stems at 7 and 14 kHz, its middle as thin as it was; SongEval 0.02 to 0.09 down in the
# three windows judged, TuneJury with the brief down in two and level in one, with none up in two of three, enjoyment level: a
# darker harp is no better a harp, and the liked stems have no harp in them.)
HARP_LEAD: tuple[float, float, float, float] | None = None


def tamed_tone(name: str, instrument: str, band: bool = False, channel: str = "", light: bool = False) -> str | None:
    """The top of a voice that comes out bright against the liked stems, taken down (2026-11-17, midday, the morning's
    storms, inns, bosses and battles: the brass stabs and the tubular bells at the moments had the accompaniment 12 to
    16 dB over from 3.5 kHz up, and the harmonica that plays the accordion had the inns' texture 20 to 24 dB over)."""
    if name.endswith(" stabs") or name == "bell at the moments":
        return sounds.equalise(high_shelf=(3000.0, -9.0))
    if instrument == "accordion":
        # (Taken down further the same afternoon: where it is the whole of an inn's texture it was still 14 to 16 dB over.)
        return sounds.equalise(high_cut=5500.0, high_shelf=(2000.0, -14.0))
    if instrument in ("xylophone", "glock", "harpsichord"):
        # (The afternoon's storms, hunts and battles: with the stabs and bells taken down, the struck and plucked
        # ostinati still had the accompaniment 10 to 14 dB over from 3.5 kHz up.)
        return sounds.equalise(high_shelf=(4000.0, -7.0))
    if band and instrument in ("organ", "rock organ"):
        # (Knight Rock's first piece of the evening, 2026-11-17: in the black chapel the church organ and the rock organ
        # that hold its texture had it 24 to 28 dB over the liked band stems from 7 kHz up, and 12 to 14 under the lead.
        # The orchestra's organ sits about 5 dB over its own and is left alone.)
        return sounds.equalise(high_cut=6000.0, high_shelf=(3000.0, -10.0))
    if instrument in ("banjo", "mandolin"):
        # (The places' study the same afternoon: a tavern's banjo and mandolin had the accompaniment 10 to 13 dB over
        # from 7 kHz up. Their twang, under 4 kHz, stays; the jangle of the picks over it is taken down.)
        return sounds.equalise(high_shelf=(4000.0, -6.0))
    if name == "trombone tutti":
        # (...and a trombone doubling a battle's bass line had the bass 9 to 13 dB over at the top.)
        return sounds.equalise(high_shelf=(1500.0, -6.0))
    if band and channel == "texture":
        # (Knight Rock's second families that evening, with its organs taken down: the rest of the band's texture, the reeds
        # and pipes and the choir at the moments, 12 to 46 dB over the liked band stems from 7 kHz up. Those stems are dark:
        # their texture falls away from 900 Hz, 35 to 41 dB down at the top, as an organ through a turning speaker does. Closed
        # at 7.5 kHz it came only 4 to 5 dB nearer, so it is closed lower.)
        return sounds.equalise(high_cut=5000.0, high_shelf=(2500.0, -8.0))
    if band and channel == "lead" and instrument == "harmonica" and HARP_LEAD is not None:
        top, shelf, down, body = HARP_LEAD
        return sounds.equalise(high_cut=top, high_shelf=(shelf, down), bands=((700.0, body, 1.0),))
    if band and channel == "lead":
        # (The band's lead guitar, fiddle and whistles, 10 to 20 dB over: the liked band's lead is a guitar through a cabinet,
        # falling away above 5 kHz, where ours fizzed. Its bite at 1 to 3 kHz is kept.)
        return sounds.equalise(high_cut=6000.0, high_shelf=(3500.0, -6.0))
    if band and channel == "bass" and instrument.endswith("tuba"):
        # (2026-11-25: three bands' bass is a tuba, whose fourth to eighth overtones are nearly all of it: the octave from 320 Hz at -4 to -7 dB of the whole where the liked stems have it at -26, the basses of Deep
        # Mine, Charge Song and the press gang's songs 11 to 13 over in their middle, where the riff and the tune are. Its note is left.)
        return sounds.equalise(bands=((450.0, -8.0, 0.8),), high_shelf=(1400.0, -4.0))
    if band and light and instrument in ("picked bass", "fretless") and LIGHT_BAND_BASS:
        # (2026-11-22, night: the light bands' bass, MuseScore's electric bass played softly in the walks, inns, camps and
        # nights, 3.7 to 13 dB thin in its middle in the day's studies of the new families, where the heavy band's sits within
        # 5. See LIGHT_BAND_BASS.)
        return sounds.equalise(bands=((800.0, LIGHT_BAND_BASS, 1.2),))
    return None


def opened(heard: list[float], lifts: list[float]) -> list[float]:
    """How far each part of a song is brought up (`lifts`, dB), its opening and its first theme so far that they are heard (OPEN_UNDER, FIRST_UNDER), and never over what comes after them."""
    if len(heard) < 2 or heard[0] <= -70.0:
        return lifts
    stands = [loud + lift for loud, lift in zip(heard, lifts)]
    top, out = max(stands), list(lifts)
    arrives = next(at for at, stood in enumerate(stands) if stood >= top - ARRIVES)
    for at in range(2, arrives):
        if heard[at] > -70.0:
            out[at] += max(top - EARLY_UNDER - stands[at], 0.0) * EARLY_SHARE
    for at in range(max(arrives, 2), len(heard) - 1):
        if heard[at] > -70.0:
            out[at] += max(top - LOW_UNDER - stands[at], 0.0) * LOW_SHARE
    if len(heard) > 2 and heard[1] > -70.0:
        out[1] += min(max(min(top - FIRST_UNDER, heard[2] + out[2] - 1.0) - stands[1], 0.0), FIRST_MOST)
    out[0] += min(max(min(top - OPEN_UNDER, heard[1] + out[1] - 2.0) - stands[0], 0.0), OPEN_MOST)
    return out


def stage(fam: Family, take: int) -> dict:
    """Writes one take of a family as its sheet and performs it (`write`, `perform`). Returns what it measured. The
    REAPER project is kept (see `project_of`), and the sheet beside the staged track. A take whose sheet a musician has
    revised is performed from its sheet (`sheet.revised_of`)."""
    from .sheet import revised_of
    return perform(revised_of(fam.character.style, fam.name, take) or write(fam, take))


def write(fam: Family, take: int) -> Sheet:
    """A take's music sheet, its first draft (2026-11-18: "the music sheet should be a separate concept and asset for
    every track, and updating it should be the golden rule"): the family's take as the writer writes it (orchestra.Take,
    its effect marks with it), what the desk stacks on it where the story calls for more, every part played as a player
    plays it (a few milliseconds early or late), and the strokes the other channels give way under."""
    character = fam.character
    written = Take(fam, take)
    rng = random.Random(fam.seed * 31 + take)
    bar_frames = fam.beats * 60.0 / fam.bpm * RATE
    edges, bars = [0], 0
    for section in fam.sections:
        bars += section.bars
        edges.append(int(round(bars * bar_frames)))
    # Where the kick strikes: the kit's bass drum (where the kick goes with it), the biggest war drum, the deep stroke.
    from .orchestra import KITS
    strokes: list[tuple[float, float]] = []
    for name, voice in written.voices["drums"].items():
        if voice.drums and voice.instrument[4:] in sounds.KICKED:
            boom = KITS[voice.instrument[4:]]["boom"]
            strokes += [(note.start, note.loud) for note in voice.notes if note.pitch == boom]
        elif voice.instrument in ("war drums", "boom", "kick"):
            strokes += [(note.start, note.loud) for note in voice.notes if note.pitch == 36]
    for channel in CHANNELS:
        for name, voice in written.voices[channel].items():
            if voice.notes:
                humanise(voice, rng, timing=0.004 if channel == "drums" else 0.007, bpm=fam.bpm)
    from . import orchestra
    harp = written.voices["lead"].get("harmonica solo")
    if harp is not None and harp.notes and orchestra.HARP_BENDS and written.solo_key is not None:
        # A harmonica's solo bent as a harp player bends it (orchestra.HARP_BENDS), on the notes as they are played.
        bends = orchestra.harp_bends(harp.notes, written.solo_key, fam.bpm, fam.seed * 31 + take * 7 + 11)
        if bends:
            harp.mark("bend", bends)
    # ----- What the desk stacks on what the writer wrote (2026-11-16: "stack on top of this for interesting layers",
    # "better get the kickdrum in those moments", "more depth more instruments .... more bass and kick in the intense parts").
    from .score import Note, Voice
    beat_of = fam.bpm / 60.0 / RATE
    told = [(section.story, edges[index] * beat_of, edges[index + 1] * beat_of, section.bars) for index, section in enumerate(fam.sections)]
    spans = [(first, last) for story, first, last, _ in told if story == "moment"]
    pads = [voice for voice in written.voices["texture"].values() if voice.instrument in ("tremolo", "strings", "strings slow") and voice.notes]
    if pads:
        # Depth: a wide synth pad far under the string pad, all the way through.
        written.voices["texture"]["pad under"] = Voice(notes=[Note(note.start, note.length, note.pitch, 0.5) for voice in pads for note in voice.notes
                                                                  if 48 <= note.pitch <= 84], instrument="pad")
    low = sorted((note for voice in written.voices["bass"].values() if not voice.drums for note in voice.notes), key=lambda note: note.start)
    if character.role != "night":
        # A kick on the bar all through each moment (and on the half bar, in heavy music), and on the last bars of each
        # rise; where the writer has a stroke there already, that one stands.
        had = sorted(note.start for voice in written.voices["drums"].values() for note in voice.notes
                     if (voice.drums and note.pitch == 36) or (voice.instrument in ("war drums", "boom", "kick") and note.pitch == 36))
        kicks = []
        for story, first, last, bars in told:
            if story not in ("moment", "rise"):
                continue
            for bar in range(bars):
                if story == "rise" and bar < bars * 0.6:
                    continue
                ons = [0.0] if character.light or story == "rise" or fam.beats < 4 else [0.0, fam.beats / 2.0]
                for on in ons:
                    at = first + bar * fam.beats + on
                    if at < last - 0.01 and not any(abs(at - each) < 0.12 for each in had):
                        strength = (0.6 if character.light else 0.9 if on == 0.0 else 0.75) * (0.8 if story == "rise" else 1.0)
                        kicks.append(Note(at, 0.5, 36, strength))
        if kicks:
            written.voices["drums"]["kick at the moments"] = Voice(notes=kicks, instrument="kick")
            strokes += [(note.start, note.loud) for note in kicks]         # the other channels give way under these as well
    if low and spans and not character.light:
        # More bass where it is intense: a deep sub and low brass double the bass line through each moment, and a bell
        # is struck on the moment's first beat, on the note the bass has there.
        deep = [note for note in low if any(first <= note.start < last for first, last in spans)]
        written.voices["bass"]["sub at the moments"] = Voice(notes=[Note(note.start, note.length, note.pitch, 0.8) for note in deep], instrument="deep")
        # (Not a band's: a tuba doubled the rock band's bass at its moments, and a band's bass read 8 to 15 dB over the liked
        # stems from 450 Hz to 1.8 kHz, 2026-11-18.)
        if not character.band and not any(voice.instrument in ("tuba", "trombone") and voice.notes for voice in written.voices["bass"].values()):
            written.voices["bass"]["low brass at the moments"] = Voice(notes=[Note(note.start, note.length, note.pitch if note.pitch >= 29 else note.pitch + 12, 0.75) for note in deep if note.length >= 0.45],
                instrument="tuba")
        rung = []
        for first, last in spans:
            under = [note for note in low if note.start <= first + 0.05 < note.start + note.length + 0.5] or [note for note in low if note.start >= first][:1]
            if under:
                rung.append(Note(first, 4.0, 60 + under[0].pitch % 12, 0.8))
        if rung and crown_of(character)[1] and not any(voice.instrument in ("bells", "church bell") for voice in written.voices["rhythm"].values()):
            written.voices["rhythm"]["bell at the moments"] = Voice(notes=rung, instrument="bells")
    crown = crown_of(character)[0]
    if muse.available() and crown and not (character.band and not character.light):
        # A layer on top, where the story comes to its moments: a choir sings the pad's chords with the strings (the
        # horns, in the open country and the hills). Light music has it too, softly (2026-11-16, played: "not enough
        # instruments in each track").
        low, high = (43, 79) if crown in ("choir", "oohs", "full choir") else (41, 74)
        sung = [note for voice in written.voices["texture"].values() if voice.instrument in ("tremolo", "strings", "strings slow")
                for note in voice.notes if any(first <= note.start < last for first, last in spans) and low <= note.pitch <= high]
        if sung and crown not in {voice.instrument for voice in written.voices["texture"].values()}:
            soft = 0.55 if character.light else 0.72
            written.voices["texture"]["%s at the moments" % crown] = Voice(notes=[type(note)(note.start, note.length, note.pitch, soft) for note in sung],
                                                                           instrument=crown)
    if muse.available() and character.band:
        # A band's plain guitar is an electric one played clean (its steel-strung ones stay acoustic).
        for channel in CHANNELS:
            for voice in written.voices[channel].values():
                if voice.instrument == "guitar":
                    voice.instrument = "clean guitar"
    band = band_of(fam, take)
    if band:
        # The band's own instruments play what the writer names (orchestra.BANDS): the notes are the writer's, the sound the band's.
        lent = band in STRUMS and borrowed(fam)
        for channel in CHANNELS:
            for voice in written.voices[channel].values():
                if lent:
                    borrow(band, channel, voice, fam.seed + take)
                given(band, voice)
                if channel in ("lead", "rhythm"):
                    held(voice)
    form, first_bar = [], 0
    for section in fam.sections:
        written_as = {"story": section.story, "part": section.part, "first": first_bar, "bars": section.bars,
                      "key": (fam.key.lifted(fam.lift) if section.lifted else fam.key).name, "chords": list(section.chords),
                      "level": list(section.level)}
        if section.lifted:
            written_as["lifted"] = True
        form.append(written_as)
        first_bar += section.bars
    about = {"character": character.name, "role": character.role, "kinds": list(character.kinds), "serves": list(character.serves),
             "light": character.light, "weight": character.weight, "band": character.band, "hall": list(character.hall),
             "metre": fam.metre, "seed": fam.seed, "tonic": fam.key.name, "settings": list(settings_of(character)),
             "sounds": band, "shape": character.form, "soft war": written.soft_war, "ducks under": [list(stroke) for stroke in strokes]}
    sheet = Sheet(style=character.style, family=fam.name, take=take, title=fam.title, tempo=fam.bpm, beats=fam.beats, form=form,
                  parts=written.voices, about=about)
    sheet.revised("the first draft", "written by the studio's writer as %s (%s), and stacked on by its desk" % (character.name, fam.metre),
                  by="the writer")
    return sheet


SOLO_OVER = 1.5          # dB a guitar solo stands over the rhythm guitars where it plays, measured (`solo_lift`)
SOLO_MOST = 8.0          # ...and the most it is brought up
# (2026-11-19: across 144 Knight takes a band's tune sat level with its rhythm guitars in the first theme, median -0.4 dB:
# the lead's place is set at the summit, where the twin guitars play the theme together, and one guitar or a fiddle singing
# it alone in a theme was left there. The tune is the band's singer.)
TUNE_LIFT = True         # a band's tune stands TUNE_OVER dB over its rhythm guitars wherever it sings (`tune_lift`)
TUNE_OVER = 2.0
TUNE_MOST = 5.0
# ...and in a band of other sounds (orchestra.BANDS) up to this much (2026-11-23, 23:30, the first of them, Casket Roll: a tenor saxophone, the choir's oohs and
# a sweet lead played softly read 10 to 12 dB under what they are at the summit, where the house's distorted lead reads 3; in its head, its bridge and its
# close the lift stood at its 5 and the tune was still 4 dB under the piano).
TUNE_MOST_BANDS = 13.0
TUNE_UNDER_BASS = 1.0    # dB the bass may stand over where the tune is measured against it, in those bands (Deposed Interdict's valley: no guitars, the bass at -29)
# ...and where a tune lifted as far as it goes still stands under that, the riff gives way, this far at the most (2026-11-25, Sleet-Blind Salvo's valley: cellos through amplifiers, which play as loud softly as hard, at -25 over a
# solo cello at -39; Choked Level's themes 2 and 3 dB under their riff): in a band of other sounds, as a guitarist turns down for the singer.
RIFF_GIVES = 9.0


def solo_lift(parts: dict[str, np.ndarray], span: tuple[int, int], ramp: int) -> tuple[float, np.ndarray | None]:
    """How far the lead channel is brought up where a guitar solo plays, so that it stands SOLO_OVER dB over the rhythm
    guitars there (2026-11-19: Barnyard Jamboree's solo came out 3.4 dB under them, its channel set by the theme after it,
    where a fiddle and the twin guitars play it): the gain in dB and the gain for each sample, eased in and out over
    `ramp` samples; nothing where it already stands over them."""
    if "lead" not in parts or "rhythm" not in parts:
        return 0.0, None
    first, last = span
    lead = analysis.loudness_lufs(parts["lead"][first:last], RATE)
    band = analysis.loudness_lufs(parts["rhythm"][first:last], RATE)
    if lead < -70.0 or band < -70.0:
        return 0.0, None
    lift = min(band + SOLO_OVER - lead, SOLO_MOST)
    if lift <= 0.1:
        return 0.0, None
    gain = np.float32(10 ** (lift / 20.0))
    curve = np.ones(len(parts["lead"]), dtype=np.float32)
    curve[first:last] = gain
    up = max(first - ramp, 0)
    curve[up:first] = np.linspace(1.0, gain, first - up, dtype=np.float32)
    down = min(last + ramp, len(curve))
    curve[last:down] = np.linspace(gain, 1.0, down - last, dtype=np.float32)
    return round(float(lift), 2), curve


def solos_of(notes: list[tuple[float, float]], bar: float, beat_frames: float) -> list[tuple[int, int]]:
    """Where a song's solos are, in samples, from their notes (the beat each begins on and its length in beats): one solo to the next, a rest of more than
    two bars between them."""
    spans: list[list[float]] = []
    for start, length in sorted(notes):
        if spans and start - spans[-1][1] <= 2 * bar:
            spans[-1][1] = max(spans[-1][1], start + length)
        else:
            spans.append([start, start + length])
    return [(int(first * beat_frames), int(last * beat_frames)) for first, last in spans]


def sung_spans(form: list[dict], edges: list[int], solo_spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Where a band's tune sings, in samples: every part of the story but the open, where the riff is alone, and the solos, which are lifted by
    their own measure: what a part has before its solo and after it. (2026-11-24, Keel-Scarred Shove: a solo picked up in the climb's last bar had its climb taken
    for the solo, and left unlifted.)"""
    sung = []
    for section, first, last in zip(form, edges, edges[1:]):
        if section.get("story") == "open":
            continue
        left = [(first, last)]
        for span in solo_spans:
            left = [each for a, b in left for each in ((a, min(b, span[0])), (max(a, span[1]), b)) if each[1] > each[0]] \
                if first < span[1] and last > span[0] else left
        sung += [(a, b) for a, b in left if b - a > int(2 * RATE)]
    return sung


def tune_caps(sounds: str, lead: dict[str, list[float]], spans: list[tuple[int, int]], beat_frames: float) -> list[float]:
    """The most the tune is lifted in each part it sings in (`tune_lift`): TUNE_MOST where a distorted guitar has most of it, which is as loud struck softly as hard, and
    TUNE_MOST_BANDS where anyone else does, or in a band of other sounds. `lead` is the lead channel's notes by instrument, the beat each begins on. (2026-11-24,
    00:15: of 414 Knight Rock songs the first theme's tune stood at the 5 dB in 9 of 259 led by the lead guitar, and in 30 of 60 led by a fiddle, 13 of 17 by a steel
    guitar, 10 of 20 by a harmonica, 5 of 5 by an accordion; Regicide Banquet's trombone read -44 LUFS over guitars at -26.)"""
    out = []
    for first, last in spans:
        counted: dict[str, int] = {}
        for instrument, ats in lead.items():
            counted[instrument] = counted.get(instrument, 0) + sum(1 for at in ats if first <= at * beat_frames < last)
        leader = max(sorted(counted), key=counted.__getitem__) if any(counted.values()) else ""
        wired = not leader or (leader in INSTRUMENTS and INSTRUMENTS[leader].wired)
        out.append(TUNE_MOST if wired and not sounds else TUNE_MOST_BANDS)
    return out


def tune_lift(parts: dict[str, np.ndarray], spans: list[tuple[int, int]], ramp: int, most: float | list[float] | None = None,
              bass: bool = False) -> tuple[list[float], np.ndarray | None]:
    """How far the lead channel is brought up in each part of a band's story where its tune sings (TUNE_LIFT), so that it
    stands TUNE_OVER dB over the rhythm guitars there, and at most `most` (TUNE_MOST, or one for each span: `tune_caps`); nothing where it stands over them already, or
    where the lead or the guitars play little. The gain for each sample, eased from part to part over `ramp` samples. With `bass`, against the bass as
    well (TUNE_UNDER_BASS): in a valley with no guitars it is what the tune sings over."""
    caps = [TUNE_MOST if most is None else most] * len(spans) if not isinstance(most, list) else most
    least = -58.0 if bass else -50.0
    if "lead" not in parts or "rhythm" not in parts:
        return [], None
    frames = len(parts["lead"])
    db = np.zeros(frames, dtype=np.float32)
    lifts = []
    for (first, last), cap in zip(spans, caps):
        lead = analysis.loudness_lufs(parts["lead"][first:last], RATE)
        # (Further than the house band's most only against what the rhythm plays in the part, not what rings into it: Sentence March's valley has no guitars
        # and read -31 of the chord before it.)
        since = first + min(int(4.0 * RATE), (last - first) // 4)
        band, lift = analysis.loudness_lufs(parts["rhythm"][first:last], RATE), 0.0
        if lead > -50.0 and band > -50.0:
            lift = max(min(band + TUNE_OVER - lead, min(cap, TUNE_MOST)), 0.0)
        if cap > TUNE_MOST or bass:
            band = analysis.loudness_lufs(parts["rhythm"][since:last], RATE)
            if bass and "bass" in parts:
                band = max(band, analysis.loudness_lufs(parts["bass"][since:last], RATE) - TUNE_UNDER_BASS - TUNE_OVER)
            if lead > least and band > -50.0:
                lift = max(lift, min(band + TUNE_OVER - lead, cap))
        db[first:last] = lift
        lifts.append(round(float(lift), 2))
    if max(lifts, default=0.0) <= 0.1:
        return lifts, None
    edges = sorted({edge for span in spans for edge in span})
    for edge in edges:
        low, high = max(edge - ramp, 0), min(edge + ramp, frames)
        if high - low > 1:
            db[low:high] = np.linspace(db[low], db[high - 1], high - low, dtype=np.float32)
    return lifts, (10.0 ** (db / 20.0)).astype(np.float32)


def riff_gives(parts: dict[str, np.ndarray], spans: list[tuple[int, int]], ramp: int) -> tuple[list[float], np.ndarray | None]:
    """How far the rhythm channel is taken down in each part where the tune, lifted as it is by now, stands under TUNE_OVER dB over it (RIFF_GIVES at the most): the dB for each, and the gain for each sample,
    eased over `ramp` samples at the joins; nothing where the tune stands over it, or where either plays next to nothing."""
    if "lead" not in parts or "rhythm" not in parts:
        return [], None
    frames = len(parts["rhythm"])
    db, downs = np.zeros(frames, dtype=np.float32), []
    for first, last in spans:
        since = first + min(int(4.0 * RATE), (last - first) // 4)
        lead, band = analysis.loudness_lufs(parts["lead"][first:last], RATE), analysis.loudness_lufs(parts["rhythm"][since:last], RATE)
        lack = band + TUNE_OVER - lead
        down = -min(lack, RIFF_GIVES) if lead > -62.0 and band > -50.0 and lack > 0.5 else 0.0
        db[first:last] = down
        downs.append(round(float(down), 2))
    if min(downs, default=0.0) >= -0.5:
        return [0.0] * len(downs), None
    for edge in sorted({edge for span in spans for edge in span}):
        low, high = max(edge - ramp, 0), min(edge + ramp, frames)
        if high - low > 1:
            db[low:high] = np.linspace(db[low], db[high - 1], high - low, dtype=np.float32)
    return downs, (10.0 ** (db / 20.0)).astype(np.float32)


def perform(sheet: Sheet) -> dict:
    """Plays a sheet and stages what it makes: MuseScore performs the instruments it has, REAPER plays the rest, each
    channel is brought to its place and the story's levels ridden, and the track is staged with its sheet beside it.
    Nothing here writes music: what is played is what the sheet says."""
    about, voices, bpm, take = sheet.about, sheet.parts, sheet.tempo, sheet.take
    bar_frames = sheet.beats * 60.0 / bpm * RATE
    whole = int(round(sheet.bars * bar_frames))
    frames = whole + int(round(forever.POST_S * RATE))
    edges, bars = [0], 0
    for section in sheet.form:
        bars += section["bars"]
        edges.append(int(round(bars * bar_frames)))
    # Where everyone is playing: the last and biggest of the story's moments.
    moment = max(index for index, section in enumerate(sheet.form) if section["story"] == "moment")
    # A guitar solo at the summit stands over the band by its own `gain db` (orchestra.SOLO_LIFT). The lead's place is
    # measured where the summit has no solo, so that the lift is not taken back (2026-11-18: measured over the solo, the
    # whole lead channel was turned down by the lift, and the solo came out level with the rhythm guitars).
    soloed = [note for name, voice in voices.get("lead", {}).items() if name.endswith(" solo") for note in voice.notes]
    solo_span, solo_spans = None, []                     # the summit's, and every one (a jam has one before it: orchestra.FORMS)
    if soloed:
        beat_frames = 60.0 / bpm * RATE
        solo_spans = solos_of([(note.start, note.length) for note in soloed], sheet.beats, beat_frames)
        solo_span = next((span for span in solo_spans if edges[moment] <= (span[0] + span[1]) // 2 < edges[moment + 1]), None)
    room = about["hall"][1] / 0.24
    strokes = [(float(at), float(loud)) for at, loud in about["ducks under"]]
    seed = about["seed"] * 31 + take
    if muse.available():
        # MuseScore performs every instrument it has, several at a time, before the project is put together.
        muse.prepare([(voice.instrument, voice.notes, bpm, voice.swells) for channel in CHANNELS for voice in voices[channel].values()
                      if voice.notes and not voice.drums], seed=seed, workers=MUSE_WORKERS)
    folders = []
    for channel in CHANNELS:
        under = []
        for name, voice in voices[channel].items():
            if not voice.notes:
                continue
            taste = INSTRUMENTS[voice.instrument].level if voice.instrument in INSTRUMENTS else 1.0
            made = sounds.lines(voice, name, bpm, taste=taste, room=room, seed=seed)
            tamed = tamed_tone(name, voice.instrument, band=about["band"], channel=channel, light=about["light"])
            if tamed:
                for line in made:
                    line.effects = list(line.effects) + [tamed]
            under += made
        if under:
            moves, last = [], -1.0
            for at, loud in sorted(strokes) if channel in DUCK else ():
                if loud < 0.45 or at <= last:
                    continue
                down = 1.0 - (1.0 - DUCK[channel]) * min(loud / 0.85, 1.0)
                beat_s = 60.0 / bpm
                moves += [(at - 0.012 / beat_s, 1.0), (at, down), (at + 0.06 / beat_s, down), (at + 0.26 / beat_s, 1.0)]
                last = at + 0.26 / beat_s
            folders.append((desk.Line(channel, desk.bare(channel, []), effects=sounds.bus(channel, style=sheet.style), moves=moves), under))
    rpp = project_at(sheet.style, sheet.family, take)
    work = rpp.parent
    work.mkdir(parents=True, exist_ok=True)
    rpp.write_text(desk.project(folders, bpm=bpm, seconds=whole / RATE, out=work, tail=forever.POST_S,
                                hall=sounds.hall(min(about["hall"][0] * 1.3, 3.8))), encoding="utf-8")
    with reaper.Display() as display:
        # (A heavy piece on a machine that is doing other things renders at less than half speed: "lava fields" was
        # stopped twice, half a minute from its end, by a limit of twice its length. On the night of 2026-11-17, with
        # every core busy, two night pieces at the lowest priority rendered at an eighth of their speed and were stopped
        # by a limit of five times their length, minutes from the end. Twelve times: the limit is only there for a
        # REAPER that waits on a message nobody will answer.)
        desk.render(rpp, display=display, timeout=300.0 + 12.0 * whole / RATE)
    parts = desk.stems(work, [bus.name for bus, _ in folders], frames)
    # Each channel to its place in the mix, by how loud it is where everyone is playing. (What follows is measured here
    # and done in REAPER, as a mixer would: see the end.)
    if about["band"]:
        places = dict(BAND, **(BAND_LIGHT if about["weight"] < 0.7 else {}))
        for channel, more in BAND_BALANCE.get(about.get("sounds") or "", {}).items():
            places[channel] += more
    else:
        places = dict(PLACE, **(LIGHT if about["weight"] < 0.7 else {}))
        if any(voice.notes for name, voice in voices["drums"].items() if name.startswith("war drums")):
            places["drums"] = SOFT_WAR_DRUMS if about["soft war"] else WAR_DRUMS     # war drums are meant to be heard, not only felt
    levels, gains = {}, {}
    for channel in list(parts):
        audio = parts[channel]
        where = (edges[moment], edges[moment + 1])
        if channel == "lead" and solo_span and solo_span[1] < edges[moment + 1] - 4 * int(bar_frames):
            where = (max(solo_span[1], edges[moment]), edges[moment + 1])          # the summit after its solo
        loud = analysis.loudness_lufs(audio[where[0]:where[1]], RATE)
        if loud < -60.0:
            loud = analysis.loudness_lufs(audio[:whole], RATE)
        if loud < -65.0:
            written_notes = sum(len(voice.notes) for voice in voices[channel].values() if not voice.drums)
            if written_notes >= 24:
                # Written and not heard: something between the writer and the recording failed (2026-11-17, night: the
                # Muse performances were laid into REAPER as the wrong kind of file, and three channels came out silent).
                raise RuntimeError("The %s channel of %s %d has %d notes written and came out silent (%.1f LUFS)"
                                   % (channel, sheet.family, take, written_notes, loud))
            del parts[channel]                       # it plays nothing to speak of in this take
            continue
        # ...but never so far up that another part of the story goes more than 3 dB over the channel's place (2026-11-17,
        # night: a frost night's tune was a glockenspiel and slow violins at its moments, and a flute and handbells,
        # which carry far more when played as softly, in its rises; brought up by its moments, the rises blared).
        spans = list(zip(edges, edges[1:]))
        if channel == "lead" and solo_span:
            spans[moment] = where                                                  # (the solo is meant to stand over)
        if channel == "lead" and len(solo_spans) > (1 if solo_span else 0):
            # (...and so is a jam's first solo: what its part has after it, if anything, stands for the part.)
            kept = []
            for index, (first, last) in enumerate(spans):
                early = next((span for span in solo_spans if span is not solo_span and first < span[1] and last > span[0]), None)
                if early is None or index == moment:
                    kept.append((first, last))
                elif last - early[1] > 4 * int(bar_frames):
                    kept.append((early[1], last))
            spans = kept
        parts_of = [analysis.loudness_lufs(audio[first:last], RATE) for first, last in spans]
        loud = max(loud, max(parts_of) - 3.0)
        gain = min(max(places[channel] - loud, -18.0), 18.0)
        if channel == "drums":
            # A light piece's percussion is a few taps of a triangle or a shaker: measured by loudness they are next to
            # nothing, and brought up to the drums' place they became the loudest thing in the track (16 dB up, 2026-11-16).
            gain = min(gain, DRUMS_UP)
        parts[channel] = audio * np.float32(10 ** (gain / 20.0))
        levels[channel] = round(loud + gain, 1)
        gains[channel] = gain
    # A guitar solo stands over the band, measured where it plays (`solo_lift`): its own move on the lead's stem.
    alone: dict[str, list[tuple[float, float]]] = {}
    solo_db = 0.0
    lead_curve = None
    for span in solo_spans:
        solo_db, lift_curve = solo_lift(parts, span, int(beat_frames))
        if lift_curve is not None:
            parts["lead"] = parts["lead"] * lift_curve[:, None]
            lead_curve = lift_curve if lead_curve is None else lead_curve * lift_curve
    tune_dbs: list[float] = []
    if about["band"] and TUNE_LIFT and "lead" in parts:
        # A band's tune stands over its rhythm guitars wherever it sings: every part of the story but the open, where the
        # riff is alone, and the solo, which is lifted by its own measure.
        sung = sung_spans(sheet.form, edges, solo_spans)
        sings: dict[str, list[float]] = {}
        for voice in voices["lead"].values():
            sings.setdefault(voice.instrument, []).extend(note.start for note in voice.notes)
        tune_dbs, tune_curve = tune_lift(parts, sung, int(60.0 / bpm * RATE), bass=bool(about.get("sounds")),
                                         most=tune_caps(about.get("sounds") or "", sings, sung, 60.0 / bpm * RATE))
        if tune_curve is not None:
            parts["lead"] = parts["lead"] * tune_curve[:, None]
            lead_curve = tune_curve if lead_curve is None else lead_curve * tune_curve
    riff_dbs: list[float] = []
    if tune_dbs and about.get("sounds"):
        riff_dbs, riff_curve = riff_gives(parts, sung, int(60.0 / bpm * RATE))
        if riff_curve is not None:
            parts["rhythm"] = parts["rhythm"] * riff_curve[:, None]
            alone["rhythm"] = desk.ride_points(riff_curve)
    if lead_curve is not None:
        alone["lead"] = desk.ride_points(lead_curve)
    # The story keeps its shape but not its extremes: music behind a game cannot drop to a
    # whisper. Every part of the story is brought some of the way up to the loudest, the whole
    # band together, easing from one level to the next over three seconds at each join.
    mix = sum(parts.values())
    heard = [analysis.loudness_lufs(mix[first:last], RATE) for first, last in zip(edges, edges[1:])]
    lifts = opened(heard, [min((max(heard) - loud) * RIDE, 12.0) if loud > -70.0 else 0.0 for loud in heard])
    ride = np.empty(frames, dtype=np.float32)
    for index, (first, last) in enumerate(zip(edges, edges[1:])):
        ride[first:last] = lifts[index]
    ride[edges[-1]:] = lifts[-1]
    ease = int(1.5 * RATE)
    for index, edge in enumerate(edges[1:-1]):
        low, high = max(edge - ease, 0), min(edge + ease, frames)
        ride[low:high] = np.linspace(lifts[index], lifts[index + 1], high - low, dtype=np.float32)
    curve = (10.0 ** (ride / 20.0)).astype(np.float32)
    peak = max(float(np.abs(mix * curve[:, None]).max()), max(float(np.abs(audio * curve[:, None]).max()) for audio in parts.values()))
    scale = 0.6 / peak
    # The mix itself is REAPER's (2026-11-17, night: "remember to use reaper and plugins for effects and mixing"): each
    # channel's stem on a track of its own with its fader where it was measured to go, the ride of the story as the
    # volume envelope, rendered again; the project is kept as mix.rpp beside the track's own.
    recorded = {channel: work / (channel + ".wav") for channel in parts}
    with reaper.Display() as display:
        parts = desk.mixdown(work, recorded, faders={channel: 10 ** (gains[channel] / 20.0) * scale for channel in parts},
                             ride=desk.ride_points(curve), bpm=bpm, seconds=whole / RATE, tail=forever.POST_S, frames=frames,
                             display=display, timeout=300.0 + whole / RATE, alone=alone)
    for bus, _ in folders:
        (work / (bus.name + ".wav")).unlink()      # the staged track has them; the project can make them again
    gains = {channel: round(gain, 1) for channel, gain in gains.items()}
    mix = sum(parts.values())
    loudness = [round(analysis.loudness_lufs(mix[first:last], RATE), 1) for first, last in zip(edges, edges[1:])]
    sections = []
    for section in sheet.form:
        told = {"story": section["story"], "bars": section["bars"]}
        if section.get("lifted"):
            told["tonic"] = section["key"]
        sections.append(told)
    meta = {
        "style": sheet.style, "family": sheet.family, "take": take, "title": sheet.title, "tempo": bpm, "beats": sheet.beats,
        "bar_frames": bar_frames, "tonic": about["tonic"], "moods": list(about["kinds"]), "role": about["role"],
        "serves": list(about["serves"]), "light": about["light"], "settings": list(about["settings"]),
        "sections": sections, "floor": FLOOR,
        "follow": {"rhythm": ["lead"], "texture": ["lead"]}, "post_s": forever.POST_S,
        "credit": "Written by FreeRock's studio (%s, %s); %sput together in REAPER, with the sfizz sampler on the VSCO 2 Community "
                  "Edition and VCSL recordings (Versilian Studios, CC0), the TinySOL recordings (Cella, Ghisi, Lostanlen, Levy, "
                  "Fineberg and Maresz, IRCAM, CC BY 4.0), Naked Drums (Wilkinson Audio, CC BY 4.0) and Big Rusty Drums (Karoryfer, "
                  "CC0), more of Karoryfer's, Bragi's Workshop's, Brian Wood's and itsclipping's recordings (CC0), the MuldjordKit (Lars "
                  "Muldjord, DrumGizmo, CC BY 4.0), the FreePats bagpipe (Gilles Sadowski, CC0), the AVL drum kits (Glen MacArthur, CC BY-SA 3.0) and the Surge XT, "
                  "ZynAddSubFX and Geonkick synths"
                  % (about["character"], about["metre"], "its instruments performed by MuseScore Studio with Muse Sounds (Muse Group) and " if muse.available() else ""),
        "seed": about["seed"], "measured": {"sections": loudness, "channels": levels, "gains": gains},
    }
    if solo_db:
        meta["measured"]["solo lift"] = solo_db            # dB the lead was brought up where its solo plays
    if any(tune_dbs):
        meta["measured"]["tune lift"] = tune_dbs           # dB the lead was brought up in each part where its tune sings
    if any(riff_dbs):
        meta["measured"]["riff gives"] = riff_dbs          # dB the rhythm was taken down in each of those parts, where the tune was under it still
    folder = folder_at(sheet.style, sheet.family, take)
    write_track(folder, meta, parts)
    sheet.save(folder / "sheet.json")
    return {"family": sheet.family, "take": take, "title": sheet.title, "seconds": round(whole / RATE), "sections": loudness,
            "channels": levels, "gains": gains}


def _job(index: int, take: int) -> dict:
    fam, _ = plan()[index]
    return stage(fam, take)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write and play the orchestra's library.")
    parser.add_argument("--list", action="store_true", help="say what there would be, and write nothing")
    parser.add_argument("--only", default="", help="only families whose name contains this")
    parser.add_argument("--style", default="", help="only families of this style (warcraft, knight)")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    families = plan()
    def wanted(fam: Family) -> bool:
        return args.only in fam.name and args.style in ("", fam.character.style)

    jobs = [(index, take) for index, (fam, takes) in enumerate(families) for take in range(1, takes + 1) if wanted(fam)]
    if args.list:
        seconds = 0.0
        for fam, takes in families:
            if wanted(fam):
                seconds += fam.seconds * takes
                print("%-8s %-34s %-24s %-20s %5.0f %s  %3.0f s x %d  %s%s" % (
                    fam.character.style, fam.name, fam.title, fam.key.name, fam.bpm, fam.metre, fam.seconds, takes,
                    fam.character.role, " light" if fam.character.light else ""))
        print("%d families, %d tracks, %.0f minutes" % (len({index for index, _ in jobs}), len(jobs), seconds / 60.0))
        return 0
    todo = [(index, take) for index, take in jobs if not (folder_of(families[index][0], take) / "track.json").is_file()]
    print("%d tracks to write, %d already staged" % (len(todo), len(jobs) - len(todo)), flush=True)
    began, done = time.time(), 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        waiting = [pool.submit(_job, index, take) for index, take in todo]
        for finished in as_completed(waiting):
            made = finished.result()               # anything that went wrong stops the run and says why
            done += 1
            print("%4d/%d  %-34s take %d  %3d s  story %s" % (done, len(todo), made["family"], made["take"], made["seconds"],
                                                           " ".join("%.0f" % loud for loud in made["sections"])), flush=True)
    print("done in %.0f s" % (time.time() - began), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
