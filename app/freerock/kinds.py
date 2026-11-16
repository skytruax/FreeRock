"""Kinds of place: what a written piece says it is for, and what the game's places are.

Music is not written for Duskwood. It is written for a kind of place (haunted woods, open
farmland, a desert), and Duskwood is one of that kind, as is any place the game adds later. A
place's kinds are read from the words of its music profile (atlas), so a place nobody has
listed still gets music of the right kind from the words in its name.

A place can also be a light one: somewhere sunny and at peace, where the music is always of the
lighter sort. Everywhere else light and heavy music take turns.
"""
from __future__ import annotations

KINDS = ("pastoral", "highland", "haunted", "desert", "jungle", "infernal", "regal", "mystic")

# What each kind sounds like to someone writing for it, in a line.
ABOUT = {
    "pastoral": "farmland and gentle woods: sunny, easy, a village dance",
    "highland": "mountains, snow and open moor: wide, sturdy, wind and distance",
    "haunted": "graveyards, plague and cursed woods: slow, minor, bells and organ",
    "desert": "sand, red rock and dry wind: sparse, sun-struck, a bazaar far off",
    "jungle": "rainforest and swamp: humid, prowling, drums and wood",
    "infernal": "forge, ash and fire: heavy, hammering, low brass",
    "regal": "cities, keeps and great halls: proud, bustling, fanfares",
    "mystic": "ancient forest, moonlight and ruins by the sea: twilight, harp and chimes",
}

# Words in a place's profile (its moods and its instruments) that say which kinds it is.
_WORDS = {
    "pastoral": ("pastoral", "sunny", "hopeful", "farmland", "golden fields", "lakeside", "cheerful", "rolling plains",
                 "peaceful", "meadow", "easy-going", "breezy", "bright", "fiddle", "tin whistle", "mandolin", "village",
                 "merry", "tavern", "river"),
    "highland": ("mountain", "snow", "highland", "peaks", "heights", "windy", "crisp", "sleigh", "drone pipes",
                 "stout", "riding hard", "slopes", "sturdy", "soaring", "cold"),
    "haunted": ("gothic", "haunted", "moonlit", "blighted", "sorrowful", "ruin", "dread", "mournful", "misty", "fog",
                "menace", "cursed", "desolate", "crypt", "sinister", "corrupted", "sickly", "grey wasteland", "tolling",
                "organ", "dark pines", "plague", "ash on the wind", "witchy"),
    "desert": ("scorched", "dry wind", "desert", "red rock", "harsh sun", "savanna", "heat haze", "canyon", "mesas",
               "bazaar", "sand on", "like an oud", "rattles", "long roads"),
    "jungle": ("jungle", "humid", "prowling", "rainforest", "swamp", "murky", "marsh", "primeval", "beasts", "log drums",
               "hand drums and shakers", "damp", "lush"),
    "infernal": ("volcanic", "forge", "heat", "ash and fire", "anvil", "fire", "molten", "red sky", "war drums",
                 "clanking chains", "insect hives", "under siege", "battlefield"),
    "regal": ("proud", "regal", "bustling", "great forge", "stone halls", "fortress city", "majestic", "fanfare",
              "calm pride", "stone walls", "a great stone hall", "stately", "royal", "solemn", "disciplined", "on duty"),
    "mystic": ("ancient forest", "twilight", "gentle", "misty shore", "violet dusk", "lost empire", "sacred",
               "moonlight", "serene", "temple", "chimes", "harp-like", "faded grandeur", "ancient ruins", "sparkling",
               "curious", "melancholy", "autumn"),
}

# Words that make a place a light one.
_LIGHT = ("sunny", "hopeful", "peaceful", "cheerful", "easy-going", "bright", "serene", "gentle", "peace",
          "merry", "breezy", "calm pride", "crisp, quiet", "pastoral", "warm")


def kinds_of(words: list[str] | tuple[str, ...]) -> list[str]:
    """The kinds of place a set of profile words describes: the best fit first, two at most.
    None for words that say nothing about it."""
    text = " ; ".join(words).lower()
    scores = {kind: sum(1 for word in found if word in text) for kind, found in _WORDS.items()}
    ranked = sorted((kind for kind in KINDS if scores[kind] > 0), key=lambda kind: (-scores[kind], KINDS.index(kind)))
    return ranked[:2]


def is_light(words: list[str] | tuple[str, ...]) -> bool:
    """Whether the words describe a light place."""
    text = " ; ".join(words).lower()
    return any(word in text for word in _LIGHT)
