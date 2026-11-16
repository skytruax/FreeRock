"""The atlas: a music profile for every zone, and a reasonable one for places it has not met.

zones.json holds a hand-written profile per zone, keyed by the name the game reports. A place
that is not in it (a dungeon, a battleground, a zone added later) gets a profile worked out from
the words in its name, so there is always something to ask ElevenLabs for.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .. import kinds
from ..composer import ZoneProfile

ZONES_FILE = Path(__file__).resolve().parent / "zones.json"

# The tempos FreeRock uses: at these a bar is a whole number of milliseconds (which ElevenLabs
# needs) and of samples at 48 kHz (which keeps the layers and the bar lines exact).
TEMPOS = (80, 96, 100, 120, 125, 128, 150, 160)

# For a place with no profile: words in its name that say what kind of place it is.
KEYWORDS = (
    (("mine", "quarry", "excavation", "dig"), {"bpm": 100, "tonic": "E minor", "colours": ["pickaxe strikes on the backbeat", "low drone", "clanking chains"], "mood": ["underground", "torchlit"]}),
    (("cave", "cavern", "grotto", "den", "burrow", "lair", "hollow", "depths"), {"bpm": 96, "tonic": "D minor", "colours": ["echoing guitar harmonics", "low drone", "dripping echoes"], "mood": ["dark", "close"]}),
    (("crypt", "tomb", "barrow", "catacomb", "graveyard", "cemetery", "necropolis"), {"bpm": 80, "tonic": "D minor", "colours": ["organ", "tolling bell", "tremolo guitar"], "mood": ["crypt", "dread"]}),
    (("keep", "castle", "fortress", "citadel", "hold", "stronghold", "garrison", "tower", "spire"), {"bpm": 120, "tonic": "E minor", "colours": ["war drums", "horn-like twin guitars", "marching snare"], "mood": ["stone walls", "under siege"]}),
    (("monastery", "abbey", "cathedral", "temple", "shrine", "sanctum"), {"bpm": 96, "tonic": "D dorian", "colours": ["church organ", "bell-like harmonics", "low bowed drone"], "mood": ["solemn", "echoing halls"]}),
    (("swamp", "marsh", "bog", "mire", "fen"), {"bpm": 80, "tonic": "G minor", "colours": ["slide guitar", "croaking guiro", "frame drum"], "mood": ["murky", "heavy air"]}),
    (("forge", "foundry", "furnace", "volcano", "molten", "fire", "blackrock"), {"bpm": 128, "tonic": "D minor", "colours": ["anvil hits", "chugging low guitar", "clanking chains"], "mood": ["heat", "forge"]}),
    (("gulch", "basin", "valley", "battleground", "arena"), {"bpm": 150, "tonic": "E minor", "colours": ["war drums", "marching snare", "horn-like twin guitars"], "mood": ["battlefield", "urgent"]}),
    (("ruins", "ruin", "city", "halls", "library"), {"bpm": 96, "tonic": "B minor", "colours": ["harp-like guitar harmonics", "low bowed drone", "bell-like harmonics"], "mood": ["faded grandeur", "watchful"]}),
)
ELSEWHERE = {"bpm": 120, "tonic": "A minor", "colours": ["twelve-string guitar", "frame drum"], "mood": ["unknown country", "wary"]}


# For a named place inside a zone (the Hall of Thanes, Goldshire, Crystal Lake): words in its name
# and what they bring to the zone's music. A place keeps the zone's tempo and key; these only
# colour its own short piece.
PLACE_WORDS = (
    (("hall", "throne", "seat", "court", "palace", "chamber", "council", "thane", "king", "royal"),
     ["stately twin guitars in harmony", "slow proud drum march", "low horn-like swells"], ["a great stone hall", "proud and echoing"]),
    (("forge", "anvil", "smith", "foundry", "smelter"),
     ["anvil hits on the backbeat", "chugging low guitar", "bellows-like swells"], ["heat and hammering", "busy"]),
    (("inn", "tavern", "pub", "alehouse", "brewery", "distillery", "pig"),
     ["fiddle reel", "hand claps and stomps", "mandolin"], ["a merry tavern", "warm"]),
    (("bank", "vault", "counting", "treasury", "auction"),
     ["clockwork-tight muted guitar", "coin-like chimes", "walking bass"], ["brisk business", "tidy"]),
    (("market", "commons", "square", "trade", "bazaar", "plaza", "exchange", "shop"),
     ["bright strummed guitars", "tambourine", "whistle tune"], ["bustling", "cheerful"]),
    (("mystic", "mage", "arcane", "wizard", "magic", "enchant", "library", "explorer", "academy", "tinker"),
     ["chiming guitar harmonics", "delay-echo arpeggios", "music-box lute"], ["curious", "sparkling"]),
    (("military", "barracks", "arms", "ward", "command", "garrison", "guard", "watch", "post", "outpost", "camp", "fort"),
     ["marching snare", "horn-like twin guitars", "steady war drums"], ["on duty", "disciplined"]),
    (("temple", "cathedral", "chapel", "abbey", "shrine", "church", "sanctum", "altar"),
     ["church organ", "bell-like harmonics", "slow solemn melody"], ["solemn", "echoing"]),
    (("mine", "quarry", "dig", "excavation", "pit"),
     ["pickaxe strikes on the backbeat", "low drone", "clanking chains"], ["underground", "torchlit"]),
    (("cave", "cavern", "grotto", "den", "burrow", "lair", "hollow", "tunnel", "deeprun", "depths"),
     ["echoing guitar harmonics", "low drone", "floor toms"], ["dark", "close"]),
    (("crypt", "tomb", "grave", "graveyard", "cemetery", "barrow", "catacomb"),
     ["organ", "tolling bell", "tremolo guitar"], ["dread", "hushed"]),
    (("lake", "pond", "river", "falls", "waterfall", "spring", "stream", "loch", "shore", "coast", "bay",
      "harbor", "harbour", "docks", "dock", "beach", "strand", "isle", "island", "sea", "cove", "reef"),
     ["cymbal swells like water", "clean rippling guitar arpeggios", "tin whistle"], ["by the water", "open air"]),
    (("farm", "farmstead", "stead", "field", "orchard", "vineyard", "ranch", "pasture", "mill", "homestead", "garden"),
     ["acoustic strum", "fiddle", "hand claps"], ["homely", "sunlit"]),
    (("forest", "wood", "woods", "grove", "glade", "thicket", "glen", "vale", "copse"),
     ["wooden flute", "twelve-string guitar", "hand drums"], ["under the trees", "dappled"]),
    (("tower", "keep", "castle", "citadel", "stronghold", "fortress", "gate", "wall", "bastion"),
     ["war drums", "horn-like twin guitars", "marching snare"], ["stone walls", "watchful"]),
    (("ruins", "ruin", "remnants", "wreck", "fallen", "lost", "forgotten", "ancient"),
     ["harp-like guitar harmonics", "low bowed drone", "bell-like harmonics"], ["faded grandeur", "watchful"]),
    (("peak", "summit", "ridge", "mountain", "cliff", "pass", "crag", "heights", "overlook", "airfield"),
     ["wide open power chords", "soaring lead guitar", "rolling toms"], ["high and windy", "far views"]),
    (("road", "bridge", "crossing", "crossroads", "way", "path", "trail", "station", "tram"),
     ["galloping palm-muted guitar", "driving snare", "fiddle"], ["on the road", "going somewhere"]),
    (("village", "town", "hamlet", "shire", "landing", "haven", "rest", "refuge", "home"),
     ["mandolin", "fiddle", "bright strummed guitars"], ["friendly", "at ease"]),
)


def place_flavour(name: str | None) -> tuple[list[str], list[str]] | None:
    """The colours and mood the words in a place's name bring, or None when they say nothing."""
    if not name:
        return None
    words = set(slug(name).split("-"))
    words |= {word[:-1] for word in words if word.endswith("s")}
    for keys, colours, mood in PLACE_WORDS:
        if any(_names(word, key) for word in words for key in keys):
            return list(colours), list(mood)
    return None


def place_profile(zone_name: str | None, place_name: str | None) -> ZoneProfile:
    """The profile for a named place inside a zone: the zone's own tempo and key, so the place's
    piece sits among the zone's other music, coloured by what the place's name says about it."""
    zone = profile_for(zone_name)
    flavour = place_flavour(place_name)
    if flavour is None:
        return ZoneProfile(key=zone.key, bpm=zone.bpm, tonic=zone.tonic, colours=list(zone.colours),
                           mood=["a new corner of the same country"] + list(zone.mood[:1]))
    colours, mood = flavour
    return ZoneProfile(key=zone.key, bpm=zone.bpm, tonic=zone.tonic,
                       colours=colours + zone.colours[:1], mood=mood)


# A named place of one of these kinds is not a light one, whatever the country round it is.
_HEAVY_KINDS = ("haunted", "infernal")


def kinds_for(zone_name: str | None, place_name: str | None = None) -> tuple[list[str], bool]:
    """The kinds of place the player is in (kinds.KINDS: the best fit first, two at most), and
    whether it is a light one, where the music is always of the lighter sort.

    Both are read from the words of the zone's profile, so a zone nobody has listed gets them
    from the words in its name. A named place inside the zone (an inn, a hall, a crypt) adds
    what its own name says: its kinds come first, and it is light if its own words say so, or
    if the zone is and the place is not a dark one of its own."""
    if not zone_name or not slug(zone_name):
        return [], False
    zone = profile_for(zone_name)
    found = kinds.kinds_of(list(zone.mood) + list(zone.colours))
    light = kinds.is_light(zone.mood)
    flavour = place_flavour(place_name) if place_name and slug(place_name) != slug(zone_name) else None
    if flavour is not None:
        colours, mood = flavour
        own = kinds.kinds_of(mood + colours)
        found = (own + [kind for kind in found if kind not in own])[:2]
        light = kinds.is_light(mood) or (light and not any(kind in _HEAVY_KINDS for kind in own))
    return found, light


def slug(name: str) -> str:
    """A place's name as the library and the ledger file it: "Un'Goro Crater" -> "un-goro-crater"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _profile(name: str, entry: dict) -> ZoneProfile:
    if entry["bpm"] not in TEMPOS:
        raise ValueError("%s: %s BPM is not one of the tempos FreeRock uses (%s)" % (name, entry["bpm"], TEMPOS))
    return ZoneProfile(key=slug(name), bpm=entry["bpm"], tonic=entry["tonic"],
                       colours=list(entry["colours"]), mood=list(entry.get("mood", [])))


@lru_cache(maxsize=1)
def zones() -> dict[str, ZoneProfile]:
    """Every hand-written profile, keyed by the slug of the zone's name."""
    data = json.loads(ZONES_FILE.read_text(encoding="utf-8"))
    return {slug(name): _profile(name, entry) for name, entry in data["zones"].items()}


@lru_cache(maxsize=1)
def names() -> list[str]:
    """The zones that have a hand-written profile, by the names the game uses, in A to Z order."""
    data = json.loads(ZONES_FILE.read_text(encoding="utf-8"))
    return sorted(data["zones"])


def is_known(name: str | None) -> bool:
    return bool(name) and slug(name) in zones()


def profile_for(name: str | None) -> ZoneProfile:
    """The profile for a place by the name the game gives it. Never fails: a place without a
    hand-written profile gets one from the words in its name, or a plain one if nothing fits."""
    if not name or not slug(name):
        return ZoneProfile(key="elsewhere", bpm=ELSEWHERE["bpm"], tonic=ELSEWHERE["tonic"],
                           colours=list(ELSEWHERE["colours"]), mood=list(ELSEWHERE["mood"]))
    known = zones().get(slug(name))
    if known is not None:
        return known
    words = set(slug(name).split("-"))
    words |= {word[:-1] for word in words if word.endswith("s")}     # "Caverns" counts as "cavern"
    for keys, entry in KEYWORDS:
        if any(_names(word, key) for word in words for key in keys):
            return _profile(name, entry)
    # Nothing says what kind of country it is; its name may still say what kind of place (a hall,
    # a forge, a harbour), which is worth more than "unknown country".
    flavour = place_flavour(name)
    if flavour is not None:
        return _profile(name, {**ELSEWHERE, "colours": flavour[0], "mood": flavour[1]})
    return _profile(name, ELSEWHERE)


def _names(word: str, key: str) -> bool:
    """Whether a word from a place's name means `key`. Names are often run together ("Deadmines",
    "Stronghold"), so a word that ends in a keyword counts, as long as the keyword is long enough
    not to turn up by chance ("garden" does not mean "den")."""
    return word == key or (len(key) >= 4 and word.endswith(key))


def part_bars(bpm: int) -> int:
    """How many bars a piece gets at this tempo. Eight for most: the player gives a piece the
    floor for eight bars at a time, and a request of ten eight-bar pieces carries ten ideas where
    one of five sixteen-bar pieces carried five. At the two fastest tempos eight bars is under
    thirteen seconds, so they use sixteen."""
    return 16 if bpm >= 150 else 8
