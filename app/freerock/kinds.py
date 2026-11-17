"""Kinds of place: what a written piece says it is for, and what the game's places are.

Music is not written for Duskwood. It is written for a kind of place (haunted woods, open
farmland, a desert), and Duskwood is one of that kind, as is any place the game adds later. A
place's kinds are read from the words of its music profile (atlas), so a place nobody has
listed still gets music of the right kind from the words in its name.

A place can also be a light one: somewhere sunny and at peace, where the music is always of the
lighter sort. Everywhere else light and heavy music take turns.
"""
from __future__ import annotations

KINDS = ("pastoral", "highland", "haunted", "desert", "jungle", "infernal", "regal", "mystic", "marsh", "coast", "frozen")
# (The last three, 2026-11-17, evening: "tonight make more types or categories of places and thus the tracks that match
# them and how they're categorized". The Wetlands, a grey and damp marsh, had been heard as a jungle; the snowfields as
# the mountains round them; the sea coasts and islands as plain country by the water.)

# Words in a place's profile (its moods and its instruments) that say which kinds it is.
_WORDS = {
    "pastoral": ("pastoral", "sunny", "hopeful", "farmland", "golden fields", "lakeside", "cheerful", "rolling plains",
                 "peaceful", "meadow", "easy-going", "breezy", "bright", "fiddle", "tin whistle", "mandolin", "village",
                 "merry", "tavern", "river"),
    "highland": ("mountain", "highland", "peaks", "heights", "windy", "crisp", "drone pipes",
                 "stout", "riding hard", "slopes", "sturdy", "soaring"),
    "haunted": ("gothic", "haunted", "moonlit", "blighted", "sorrowful", "ruin", "dread", "mournful", "misty", "fog",
                "menace", "cursed", "desolate", "crypt", "sinister", "corrupted", "sickly", "grey wasteland", "tolling",
                "organ", "dark pines", "plague", "ash on the wind", "witchy"),
    "desert": ("scorched", "dry wind", "desert", "red rock", "harsh sun", "savanna", "heat haze", "canyon", "mesas",
               "bazaar", "sand on", "like an oud", "rattles", "long roads"),
    "jungle": ("jungle", "humid", "prowling", "rainforest", "primeval", "beasts", "log drums",
               "hand drums and shakers", "lush"),
    "infernal": ("volcanic", "forge", "heat", "ash and fire", "anvil", "fire", "molten", "red sky", "war drums",
                 "clanking chains", "insect hives", "under siege", "battlefield"),
    "regal": ("proud", "regal", "bustling", "great forge", "stone halls", "fortress city", "majestic", "fanfare",
              "calm pride", "stone walls", "a great stone hall", "stately", "royal", "solemn", "disciplined", "on duty"),
    "mystic": ("ancient forest", "twilight", "gentle", "misty shore", "violet dusk", "lost empire", "sacred",
               "moonlight", "serene", "temple", "chimes", "harp-like", "faded grandeur", "ancient ruins", "sparkling",
               "curious", "melancholy", "autumn"),
    "marsh": ("swamp", "marsh", "bog", "fen ", "mire", "murky", "damp", "wetland", "croaking", "heavy air", "reeds"),
    "coast": ("surf", "shore", "seaside", "by the sea", "sea air", "sea breeze", "salt air", "coast", "harbour", "harbor",
              "island", "beach", "concertina", "shanty", "gulls", "waves"),
    "frozen": ("snow", "frozen", "icy", "glacier", "winter", "frost", "sleigh", "cold", "blizzard"),
}

# Words that make a place a light one.
_LIGHT = ("sunny", "hopeful", "peaceful", "cheerful", "easy-going", "bright", "serene", "gentle", "peace",
          "merry", "breezy", "calm pride", "crisp, quiet", "pastoral", "warm")


# What a place's own name says ("Shadowgale Forest", "Blightwood", "Emberfall"): the kind of place the beginning
# of each of its words points to. A zone's profile speaks for the whole zone; its corners are told apart by their
# names, and a dark wood on a sunny island is a dark wood ("in a dark misty place and music is too light",
# 2026-11-16). Only the beginning of a word is read: inside a word the same letters turn up by chance (an orchard
# has "char" in it, a grotto "rot", a pilgrim "grim"). The words that darken count double.
_IN_NAMES = {
    "haunted": ("shadow", "dark", "gloom", "dread", "grave", "crypt", "tomb", "ghost", "wraith", "haunt", "raven", "blight", "plague",
                "wither", "dead", "death", "bone", "skull", "curse", "dusk", "web", "widow", "sorrow", "wail", "bleak", "murk", "gallow",
                "coffin", "corpse", "nightmare", "doom", "terror", "scourge", "lich", "fel", "black", "grim"),
    "mystic": ("mist", "fog", "moon", "star", "elder", "shrine", "temple", "spirit", "dream", "whisper", "veil", "twilight", "crystal",
               "rune", "arcane", "fae", "enchant", "glimmer", "oracle", "eternal", "night", "ancient"),
    "infernal": ("fire", "flame", "ember", "cinder", "lava", "magma", "scorch", "burn", "forge", "furnace", "brimstone", "blaze", "molten",
                 "smolder", "slag", "searing"),
    "jungle": ("tangle", "jungle", "serpent", "raptor", "moss", "venom"),
    "marsh": ("swamp", "marsh", "bog", "mire", "mud", "reed", "quag", "slough", "bayou"),
    "coast": ("harbor", "harbour", "bay", "beach", "coast", "shore", "isle", "island", "cove", "dock", "pier", "wharf", "reef", "tide",
              "gull", "lighthouse", "strand", "seaside", "seashore", "seaspray", "seabreeze"),   # not "sea": a seat, a season
    "frozen": ("frost", "snow", "ice", "icy", "frozen", "winter", "chill", "glacier", "rime", "blizzard", "hoar"),
    # (2026-11-16, played: "Shen'dar Highlands" was heard as the plain country round it. The words for high ground itself.)
    "highland": ("crag", "eagle", "gryphon", "highland", "mountain", "peak", "ridge", "summit", "cliff", "height", "crest", "pinnacle",
                 "moor"),
    "desert": ("sand", "dune", "dust", "dry", "salt", "mesa", "canyon", "gulch", "barren", "waste", "bleach", "parch", "scorpid"),
    "pastoral": ("gold", "sunny", "meadow", "bloom", "blossom", "honey", "apple", "berry", "willow", "brook", "clover", "barley", "wheat"),
    "regal": ("king", "queen", "crown", "throne", "royal", "lion", "noble", "court", "cathedral", "garrison", "bastion", "valor", "honor"),
}
_DARKENING = ("haunted", "infernal")


def named(name: str | None) -> list[str]:
    """The kinds of place a place's own name points to, the strongest first: none for a name
    that says nothing ("Goldshire" says pastoral; "The Crossroads" says nothing)."""
    words = "".join(letter if letter.isalpha() else " " for letter in (name or "").lower()).split()
    scores = {kind: sum((2 if kind in _DARKENING else 1) for part in parts if any(word.startswith(part) for word in words))
              for kind, parts in _IN_NAMES.items()}
    return sorted((kind for kind in KINDS if scores[kind] > 0), key=lambda kind: (-scores[kind], KINDS.index(kind)))


# How dark or bright a place is, from -3 (grim) through 0 to 3 (radiant): a finer thing than its kind, and finer
# than light or heavy ("we need lots of different granularity", 2026-11-16). A haunted wood and a haunted chapel
# garden are both haunted; a meadow at noon and the same meadow in the rain at night are both pastoral. The words
# of a profile that brighten a place and the ones that darken it, each worth three quarters of a step:
_BRIGHT = ("sunny", "hopeful", "peaceful", "cheerful", "easy-going", "bright", "serene", "gentle", "merry", "breezy", "warm", "golden",
           "calm pride", "friendly", "sunlit", "homely", "sparkling", "far views", "open air")
_DARK = ("gothic", "haunted", "blighted", "sorrowful", "dread", "mournful", "misty", "fog", "menace", "cursed", "desolate", "crypt",
         "sinister", "corrupted", "sickly", "grey wasteland", "tolling", "dark", "plague", "murky", "prowling", "scorched", "harsh",
         "volcanic", "under siege", "battlefield", "melancholy", "hushed", "close", "faded grandeur", "under the trees")
# ...and the beginnings of words in a place's own name: these darken it outright, these dim it, these brighten it.
_NAME_DARK = _IN_NAMES["haunted"] + _IN_NAMES["infernal"]
_NAME_DIM = ("mist", "fog", "moon", "twilight", "night", "swamp", "marsh", "bog", "mire", "whisper", "veil", "frozen", "winter")
_NAME_BRIGHT = _IN_NAMES["pastoral"] + ("sun", "dawn", "bright", "crown", "royal", "star", "glimmer")


def shade_of(words: list[str] | tuple[str, ...], name: str | None = None) -> float:
    """How dark or bright a place is (-3 to 3), from the words of its profile and, for a named
    place inside a zone, from its own name: a name that darkens outweighs a bright country."""
    text = " ; ".join(words).lower()
    shade = 0.75 * sum(1 for word in _BRIGHT if word in text) - 0.75 * sum(1 for word in _DARK if word in text)
    shade = min(max(shade, -2.5), 2.5)
    parts = "".join(letter if letter.isalpha() else " " for letter in (name or "").lower()).split()
    begins = lambda found: any(word.startswith(part) for word in parts for part in found)       # noqa: E731
    if begins(_NAME_DARK):
        shade = min(shade, 0.0) - 1.5
    elif begins(_NAME_DIM):
        shade = min(shade, 1.0) - 1.0
    elif begins(_NAME_BRIGHT):
        shade += 1.0
    return min(max(shade, -3.0), 3.0)


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
