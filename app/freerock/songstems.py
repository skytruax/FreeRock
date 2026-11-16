"""Written pieces from the songs that are already on disk.

Before the forever song, whole songs were made for each place and split on this machine into
drums, bass and everything else (the band). They are music written as a whole, with verses
that run into choruses, a bridge, a solo and an ending, which is exactly what a bucket's pieces
are (forever.Bucket.add_piece). So every song in the library is cut into pieces and put in its
style's bucket, where the player strings them together with everything else the style has.

Nothing is done to the sound. A piece keeps its own time, so a song at 120 beats a minute goes
into a bucket whose loose phrases are at 80 as it is: each section is cut from the three layers
where the song's own bar lines fall, and the band, the drums and the bass of a section become
the three parts of a piece (the channels rhythm, drums and bass). The band stands in for the
tune and the drone, which are inside it.

How a song becomes tracks: the song proper, from its Intro to its Outro, is one track, a piece
for each section, each going straight into the next the way the song did. An Arrival and the
Wander parts after it are one track, as are the riffs of a later set, the two halves of a
place's own theme, and two fights in a row. A Fight, a Boss, a Storm, a Night, an Ember and a
Depths part are each a short track of their own, for the moment in the game they were made for.

What a piece is for comes from where it was made: its kinds of place are those of the zone
(and of the named place inside it) the song was made for, so a song made for Duskwood is
music for haunted places, wherever they are.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import analysis, atlas, forever
from .library import LAYERS, SONG_PARTS, Asset, Library, Section

# Which channel each layer of a song plays on.
CHANNEL = {"bed": "rhythm", "drums": "drums", "bass": "bass"}
# The band is the tune and the drone as well: it is as loud as the loudest of them is asked to be.
FOLLOW = {"rhythm": ["texture", "lead"]}
LIFT = 1.0                     # a song's loudest section is this much over a bucket's usual level
QUIET = 10 ** (-72 / 20)       # a layer that never rises above this in a section has no part in the piece
CREDIT = "made by ElevenLabs for FreeRock, and split into band, drums and bass on this machine"
# Where each kind of section stands in a story.
STORY = {"intro": "open", "arrival": "open", "verse": "theme", "wander": "theme", "theme": "theme",
         "chorus": "moment", "solo": "moment", "bridge": "rise", "outro": "close"}
# The strengths of what the game asks for that each kind of moment answers.
SERVES = {"battle": (2,), "boss": (2,), "storm": (1, 2)}


def kind_of(name: str) -> str:
    """What a section is, whichever of its kind: "Verse B" is a verse, "Wander K" a wander."""
    words = name.lower().split()
    if len(words) > 1 and len(words[-1]) == 1:
        words = words[:-1]
    return " ".join(words)


def _run(section: Section) -> str:
    """Sections that follow each other and are of one run belong to one track."""
    kind = kind_of(section.name)
    if kind in SONG_PARTS:
        return "song"
    if kind in ("arrival", "wander"):
        return "wander"
    return "theme" if kind == "theme" else section.role


def tracks(asset: Asset) -> list[list[Section]]:
    """The asset's sections as tracks: each a run of sections that go on from one another."""
    runs: list[tuple[str, list[Section]]] = []
    for section in sorted(asset.sections, key=lambda each: each.start):
        run = _run(section)
        if runs and runs[-1][0] == run and runs[-1][1][-1].end == section.start:
            runs[-1][1].append(section)
        else:
            runs.append((run, [section]))
    return [sections for _, sections in runs]


def role_of(section: Section) -> str:
    """The kind of moment a section is for, as the director names them."""
    return "wander" if section.role == "arrival" else section.role


def story_of(section: Section, first: bool) -> str:
    """Where a section stands in its track's story. A riff that begins a track without an
    opening of its own is a story in itself, so that the track can be begun with it; so is a
    section made for one kind of moment (a fight, a night)."""
    kind = kind_of(section.name)
    if role_of(section) != "wander":
        return ""
    if first and kind in ("wander", "theme"):
        return ""
    return STORY.get(kind, "")


def floor_of(role: str, story: str) -> dict[str, float]:
    """The least each channel is played at, whatever the game is doing: a fight is the whole
    band, the moment a song comes to (and a storm) has its drums and bass, and a verse or a
    riff keeps a little of its drums. Calm music is left to the game."""
    if role in ("battle", "boss"):
        return {"drums": 1.0, "bass": 1.0}
    if role == "storm" or story == "moment":
        return {"drums": 0.6, "bass": 0.5}
    if role == "wander" and story in ("theme", ""):
        return {"drums": 0.3}
    return {}


_SMALL = ("of", "the", "and", "in", "on", "at", "to", "a")


def place_name(key: str) -> str:
    """A place's name from the key its music is filed under: "the-hall-of-thanes" is The Hall
    of Thanes, "anvilmar-s-rest" Anvilmar's Rest. A zone the atlas knows has its own spelling."""
    for name in atlas.names():
        if atlas.slug(name) == key:
            return name
    words: list[str] = []
    for word in key.split("-"):
        if word == "s" and words:
            words[-1] += "'s"                      # the apostrophe the key lost
        elif word in _SMALL and words:
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words)


@dataclass
class Made:
    """One track that was cut from a song."""
    asset: str
    track: str                     # "song/<asset>/<its first bar>"
    title: str
    role: str
    moods: list[str]
    light: bool
    pieces: int                    # how many pieces it is now in the bucket as
    added: int                     # how many of those this run put there
    seconds: float


def from_songs(library: Library, bucket: forever.Bucket) -> list[Made]:
    """Cuts every song in the bucket's style into pieces and puts them in the bucket. A song
    that is banned is left out; one whose pieces are in the bucket already is not put there
    again. Returns the tracks, in the order the songs were made.

    Another program must not be writing the bucket meanwhile: the server keeps the bucket's
    list in memory, so this is for while the server is stopped."""
    have = {piece["source"]: piece_id for piece_id, piece in bucket.pieces.items() if piece.get("source")}
    assets = [asset for asset in library.assets() if asset.genre == bucket.genre and not asset.banned]
    numbers: dict[tuple[str, str | None], int] = {}
    made: list[Made] = []
    for asset in assets:
        if asset.rate != forever.RATE:
            raise ValueError("The song %s is at %d Hz; a bucket's music is at %d" % (asset.id, asset.rate, forever.RATE))
        where = (asset.zone, asset.subzone)
        numbers[where] = numbers.get(where, 0) + 1
        name = "%s %d" % (place_name(asset.subzone or asset.zone), numbers[where])
        moods, light_place = atlas.kinds_for(asset.zone, asset.subzone)
        bar = asset.bar_frames
        sources = {section.start: "song/%s/%d" % (asset.id, round(section.start / bar)) for section in asset.sections}
        layers: dict[str, np.ndarray] | None = None
        gain = 0.0
        if any(source not in have for source in sources.values()):
            # The song as it is on disk. One gain for the whole of it: its loudest section, all
            # three layers together, is brought to a little over the bucket's usual level, and
            # never past full scale. So the song keeps its own shape, quiet where it was quiet.
            layers = {layer: np.frombuffer(library.samples(asset, layer, 0, asset.frames), dtype="<i2")
                      .reshape(-1, 2).astype(np.float32) / 32768.0 for layer in LAYERS}
            mix = layers["bed"] + layers["drums"] + layers["bass"]
            loudest = max(analysis.loudness_lufs(mix[section.start:section.end], asset.rate) for section in asset.sections)
            peak = max(analysis.peak(mix), 1e-6)
            gain = min(forever.PIECE_LEVEL + LIFT - loudest, -20.0 * float(np.log10(peak)) - 1.0)
        for sections in tracks(asset):
            track = sources[sections[0].start]
            role = role_of(sections[0])
            light = light_place or role == "ember"
            after, added = "", 0
            for index, section in enumerate(sections):
                source = sources[section.start]
                if source in have:
                    after = have[source]
                    continue
                story = story_of(section, index == 0)
                tail = min(int(forever.POST_S * forever.RATE), asset.frames - section.end)
                parts = {(CHANNEL[layer], 1): audio[section.start:section.end + tail] for layer, audio in layers.items()
                         if float(np.max(np.abs(audio[section.start:section.end]))) > QUIET}
                if not parts:
                    raise ValueError("Nothing plays in %s of the song %s" % (section.name, asset.id))
                after = have[source] = bucket.add_piece(
                    parts, title="%s: %s" % (name, section.name), bar_frames=float(bar),
                    bars=max(int(forever.WINDOW_S * forever.RATE // bar), 1), post=tail, tonic=asset.tonic,
                    story=story, moods=moods, role=role, serves=SERVES.get(role, (0, 1)), follow=FOLLOW,
                    floor=floor_of(role, story), track=track, after=after, gain_db=gain, source=source,
                    credit=CREDIT, light=light)
                added += 1
            made.append(Made(asset=asset.id, track=track, title="%s: %s" % (name, " to ".join(
                dict.fromkeys((sections[0].name, sections[-1].name)))), role=role, moods=moods, light=light,
                pieces=len(sections), added=added, seconds=(sections[-1].end - sections[0].start) / asset.rate))
    return made
