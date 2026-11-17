"""The styles FreeRock plays in, and a zone's profile as each style takes it.

A style is a kind of music with a bucket of its own (forever.Buckets): Knight Rock, Warcraft
and Progressive House. A zone's profile (atlas) gives a new bucket its tempo and key; each style
takes the profile in its own way (`for_genre`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The styles. For each: its name, a few words about it for the player page, and how it takes a
# zone's profile ("colours"): Knight Rock whole, the orchestra without the instruments of a rock
# band, and the house style with a tempo, a mode and a mood of its own, keeping only the zone's
# key note, so that it is happy and laid back wherever the player is.
KNIGHT = {
    "label": "Knight Rock",
    "about": "riff rock with lute and hurdy-gurdy",
    "colours": "all",
}

WARCRAFT = {
    "label": "Warcraft",
    "about": "an orchestral fantasy score in the old style",
    "colours": "acoustic",
}

HOUSE = {
    "label": "Progressive House",
    "about": "uplifting progressive house, happy and chill",
    "colours": "none",
    "tempo": 110,
    "mode": "major",
    "mood": ["happy and carefree", "warm and laid-back"],
}

GENRES = {"knight": KNIGHT, "warcraft": WARCRAFT, "house": HOUSE}
DEFAULT_GENRE = "knight"

# Words in a zone's colours that belong to a rock band and have no place in an orchestra.
_BAND_WORDS = ("guitar", "riff", "chord", "wah", "palm-muted", "power", "twelve-string", "strum", "slide")


@dataclass
class ZoneProfile:
    """What makes one zone's music its own."""
    key: str                      # short name used in file names, e.g. "elwynn-forest"
    bpm: int
    tonic: str                    # e.g. "G mixolydian", "A minor", "D dorian"
    colours: list[str]            # two or three instruments or textures that belong to the zone
    mood: list[str] = field(default_factory=list)  # a few words for how the zone feels


def genre_of(key: str | None) -> dict[str, Any]:
    """A style by its short name. An unknown name is an error, not Knight Rock."""
    if key not in GENRES:
        raise ValueError("No style called %r; the styles are %s" % (key, ", ".join(GENRES)))
    return GENRES[key]


def for_genre(profile: ZoneProfile, genre: str = DEFAULT_GENRE) -> ZoneProfile:
    """A zone's profile as one style uses it. Knight Rock takes it whole. The orchestra keeps the
    zone's tempo, key and mood and those of its instruments that are not a rock band's. The house
    style keeps only the zone's key note: its tempo, its mode and its mood are its own."""
    recipe = genre_of(genre)
    if recipe["colours"] == "all":
        return profile
    if recipe["colours"] == "acoustic":
        colours = [colour for colour in profile.colours if not any(word in colour for word in _BAND_WORDS)]
        return ZoneProfile(key=profile.key, bpm=profile.bpm, tonic=profile.tonic, colours=colours,
                           mood=list(profile.mood))
    return ZoneProfile(key=profile.key, bpm=recipe["tempo"],
                       tonic="%s %s" % (profile.tonic.split()[0], recipe["mode"]), colours=[],
                       mood=list(recipe["mood"]))
