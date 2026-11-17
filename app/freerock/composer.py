"""The styles FreeRock plays in, and a zone's profile as each style takes it.

A style is a kind of music with a bucket of its own (forever.Buckets): Knight Rock, Warcraft
and Progressive House. A zone's profile (atlas) gives a new bucket its tempo and key; each style
takes the profile in its own way (`for_genre`).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

# The styles. For each: its name and a few words about it for the player page; the house style
# also has a tempo and a mode of its own, keeping only a zone's key note.
KNIGHT = {
    "label": "Knight Rock",
    "about": "riff rock with lute and hurdy-gurdy",
}

WARCRAFT = {
    "label": "Warcraft",
    "about": "an orchestral fantasy score in the old style",
}

HOUSE = {
    "label": "Progressive House",
    "about": "uplifting progressive house, happy and chill",
    "tempo": 110,
    "mode": "major",
}

GENRES = {"knight": KNIGHT, "warcraft": WARCRAFT, "house": HOUSE}


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


def for_genre(profile: ZoneProfile, genre: str) -> ZoneProfile:
    """A zone's profile as one style's bucket takes it (its tempo and key are the bucket's): Knight
    Rock and the orchestra take it as it is, the house style keeps only the zone's key note, at a
    tempo and in a mode of its own."""
    recipe = genre_of(genre)
    if "tempo" not in recipe:
        return profile
    return dataclasses.replace(profile, bpm=recipe["tempo"], tonic="%s %s" % (profile.tonic.split()[0], recipe["mode"]))
