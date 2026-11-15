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
    return _profile(name, ELSEWHERE)


def _names(word: str, key: str) -> bool:
    """Whether a word from a place's name means `key`. Names are often run together ("Deadmines",
    "Stronghold"), so a word that ends in a keyword counts, as long as the keyword is long enough
    not to turn up by chance ("garden" does not mean "den")."""
    return word == key or (len(key) >= 4 and word.endswith(key))


def part_bars(bpm: int) -> int:
    """How many bars a full-length part gets at this tempo. Sixteen for most. At the slowest
    tempo a request of sixteen-bar parts would run close to five minutes, so it uses twelve; at
    the two fastest it would be short, so they use twenty-four."""
    if bpm <= 80:
        return 12
    if bpm >= 150:
        return 24
    return 16
