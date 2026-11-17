"""The forever song: a bucket of music for each style, and the mixing desk for its five channels.

The music for a style is not a set of songs. It is a bucket of written pieces, played as one song
that never ends. A piece is music written as a whole by the studio (app/freerock/studio) and kept
as its parts, one recording for each channel: the texture, the tune, the rhythm part, the drums
and the bass (see Bucket.add_piece). The player plays a piece's parts together on five decks, each
as loud as the game asks for its channel, and strings the pieces into tracks that tell a story.
What the player is doing in the game decides which channels are up and how hard they play.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile

from . import analysis, atlas, composer

RATE, CHANNELS_OUT = 48000, 2

# The channels: the drone, the tune, the rhythm part, the drums and the bass.
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
TIERS = (0, 1, 2)                       # calm, steady, hard
# How far a stretch of a part may be from the beat (measure).
MAX_TEMPO_OFF = 0.2            # percent, by the fit of a beat grid
MAX_REPEAT_OFF = 0.3           # percent, by how the stretch repeats itself two bars later
MAX_BEAT_OFF_MS = 45.0         # further than this from the beat and the stretch is out of time
DENSE = 0.6                    # a stretch with something struck on this share of its beats can be timed by them
REPEATS = 0.45                 # a stretch that is this like itself two bars later can be timed by that
CHANGES = 2                    # how many decks may take a new phrase each time the form comes round
# How the player shapes each turn of the form on top of what the phrases do themselves, by
# style: how far the verse is held back (dB), and how high the lows of the drums and the bass
# are swept away over the second half of the build-up before the chorus lands (Hz; 0 for not
# at all). The sweep is the dance floor's way of building; a band and an orchestra build by
# playing louder.
ARC = {"knight": {"verse_db": -3.5, "sweep_hz": 0}, "warcraft": {"verse_db": -4.5, "sweep_hz": 0},
       "house": {"verse_db": -3.0, "sweep_hz": 250}}

# How hard each channel plays, by how much is going on (the director's intensity, 0 to 1): calm
# below the first number, hard from the second, steady between. A fight starts at 0.8: the
# drums and the riff go hard at once. A second enemy in the fight (0.85) brings the hard lead,
# and a third (0.90) the hard bass line; a fight against one enemy gets there too, slowly, as
# it goes on. An elite or a boss is everything at once.
GEARS = {"lead": (0.52, 0.83), "rhythm": (0.52, 0.74), "drums": (0.52, 0.74), "bass": (0.50, 0.88)}
# How far past a line the intensity has to be before a channel changes gear, so that one hovering
# on a line does not flicker. It has to be less than the step another enemy makes (two enemies
# are 0.85 and three 0.90, each 0.02 past its line), or that enemy would change nothing.
GEAR_SLACK = 0.015
RHYTHM_FROM = 0.30             # the rhythm part plays once the player is on the move
CALM_PLACES = ("ember", "camp")       # an inn, the moment after a fight, a death, a camp: everything plays calm

# Pieces: written music, kept as its parts. See Bucket.add_piece.
PIECE_LEVEL = -13.0            # how loud a piece is with every part playing at its middle strength (LUFS)
POST_S = 6.0                   # how much of what follows is kept after each stretch of a part, for fading out under what comes next
ENCODERS = min(16, len(os.sched_getaffinity(0)))     # how many parts of a piece are written at once (on the processors it may use)
WINDOW_S = 52.0                # a part is kept in stretches no longer than this, so that no one of them is slow to fetch
FREE_SHARE = 0.12              # how often a stretch of loose phrases comes between two tracks, where there are enough of them
STORY = ("open", "theme", "rise", "moment", "close")       # where in a story a piece belongs; "" for one that is a story in itself


def form(bpm: int) -> tuple[int, int, int]:
    """The song's form at a tempo: the lengths of the verse, the build-up and the chorus in bars.
    Twice as many bars at the faster tempos, so that a turn of the form is always somewhere
    between forty seconds and a minute, half of it chorus."""
    return (4, 4, 8) if bpm <= 110 else (8, 8, 16)


def cycle_bars(bpm: int) -> int:
    """How long one turn of the form is, in bars: the length of every phrase at that tempo."""
    return sum(form(bpm))


def mix(target: Any, before: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Which channels are up, and how hard each plays, for what the director asks for: the mixing
    desk for the five decks. `target` is the director's Target; `before` is the last mix, so that
    an intensity hovering on a line does not make a channel change gear back and forth.

    The drums and the bass take their levels straight from the director: the drums come in when
    the player moves and the bass with a fight or a long ride. The drone is always there, the
    tune nearly always, and the rhythm part whenever the player is on the move."""
    intensity = target.intensity
    calm = target.place in CALM_PLACES
    out: dict[str, dict[str, Any]] = {}
    for channel in CHANNELS:
        tier = 0
        if channel != "texture" and not calm:
            low, high = GEARS[channel]
            tier = 0 if intensity < low else 1 if intensity < high else 2
            was = before[channel]["tier"] if before else None
            if was is not None and abs(tier - was) == 1:
                edge = low if min(tier, was) == 0 else high
                if abs(intensity - edge) < GEAR_SLACK:
                    tier = was
        if channel == "drums":
            level = target.drums
        elif channel == "bass":
            level = target.bass
        elif channel == "texture":
            level = target.bed * (0.6 if intensity >= 0.8 else 1.0)      # room for the band at full tilt
        elif channel == "rhythm":
            moving = intensity >= RHYTHM_FROM - (GEAR_SLACK if before and before["rhythm"]["level"] > 0 else 0.0)
            level = target.bed if moving else 0.0
        else:
            level = target.bed
        out[channel] = {"level": round(float(level), 3), "tier": tier}
    return out


# ---------------------------------------------------------------------------------------------
# Measuring a phrase
# ---------------------------------------------------------------------------------------------
def _repeat_off(audio: np.ndarray, rate: int, bar_s: float) -> tuple[float, float]:
    """How far the phrase is from repeating itself exactly two bars later, in percent of tempo,
    and how strongly it repeats (0 to 1). A phrase that keeps the tempo comes round on the bar."""
    envelope, env_rate = analysis.onset_envelope(audio, rate)
    envelope = envelope - envelope.mean()
    centre = int(round(2 * bar_s * env_rate))
    if centre * 1.5 > len(envelope):
        centre = int(round(bar_s * env_rate))
    reach = max(int(centre * 0.03), 4)
    best = (-2.0, centre)
    for lag in range(centre - reach, centre + reach + 1):
        a, b = envelope[:-lag], envelope[lag:]
        score = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
        if score > best[0]:
            best = (score, lag)
    return (centre / best[1] - 1.0) * 100.0, best[0]


def _timing(audio: np.ndarray, rate: int, bpm: int, bars: int, room: float = 1.0) -> dict[str, Any]:
    """How a stretch of a phrase keeps time: its tempo against the one asked for, how it comes
    round on the bar, and where its beat falls against its own start. `room` widens the lines
    it is held to."""
    bar_s = 240.0 / bpm
    grid = analysis.fit_grid(audio, rate, bpm)
    off = (grid.bpm / bpm - 1.0) * 100.0
    repeat, strength = _repeat_off(audio, rate, bar_s)
    half_beat = 30000.0 / bpm
    beat = grid.distance_to_beat_s(0.0) * 1000.0
    beat = (beat + half_beat / 2.0) % half_beat - half_beat / 2.0      # from the nearest beat or off-beat
    # A stretch of long notes has too little struck on its beats for a beat to be fitted to it,
    # and what the fit then says means nothing. Such a stretch is judged only by whether it
    # comes round on the bar, and if it does not repeat either, it is taken as it is: a few long
    # notes cannot be heard to be out of time.
    dense = grid.beats_checked >= DENSE * bars * 4
    found = {"tempo_off": round(off, 3), "repeat_off": round(repeat, 3), "repeat": round(strength, 2),
             "beat_ms": round(beat, 1), "struck": grid.beats_checked, "dense": bool(dense)}
    problems = []
    if dense and abs(off) > MAX_TEMPO_OFF * room:
        problems.append("it is %.2f%% off tempo" % off)
    elif strength >= REPEATS and abs(repeat) > MAX_REPEAT_OFF * room:
        problems.append("it comes round %.2f%% off the bar" % repeat)
    if dense and abs(beat) > MAX_BEAT_OFF_MS * room:
        problems.append("it starts %.0f ms from the beat" % beat)
    found["problems"] = problems
    return found


def measure(audio: np.ndarray, rate: int, bpm: int, channel: str, bars: int) -> dict[str, Any]:
    """How a stretch of a part keeps time: its length, level and timing, and in `problems`
    everything wrong with it (empty when nothing is). It is `bars` bars long at `bpm`. A texture
    is not held to a beat. (The studio's House tracks have their drums checked with it.)"""
    asked = bars * 240.0 / bpm
    found: dict[str, Any] = {"seconds": round(len(audio) / rate, 3), "lufs": round(analysis.loudness_lufs(audio, rate), 1),
                             "peak": round(analysis.peak(audio), 3)}
    problems: list[str] = []
    if abs(found["seconds"] - asked) > 0.05:
        problems.append("it is %.2f s long, not %.2f" % (found["seconds"], asked))
    if found["lufs"] < -50.0:
        problems.append("it is all but silent (%.0f LUFS)" % found["lufs"])
    if channel != "texture" and not problems:
        timing = _timing(audio, rate, bpm, bars)
        problems += timing.pop("problems")
        found.update(timing)
    found["problems"] = problems
    return found


# ---------------------------------------------------------------------------------------------
# The bucket
# ---------------------------------------------------------------------------------------------
@dataclass
class Clip:
    """One stretch of one part of a piece: what the player fetches and lays on a deck."""
    id: str
    channel: str
    tier: int                      # the strength it was written at (0 calm, 1 steady, 2 hard)
    bars: int
    frames: int
    gain_db: float                 # the piece's gain: it keeps the balance its parts were written with
    created: float
    plays: int = 0
    banned: bool = False           # never played again (/rock ban): the whole piece is
    loved: bool = False            # marked with /rock love
    source: str = "written"        # where it came from
    piece: str = ""                # the piece it is a part of
    order: int = 0                 # which stretch of that piece it is, counting from nought
    post: int = 0                  # samples kept after its end: what the music went on to

    # What a clip kept in the days of loose phrases bought from ElevenLabs: a bucket written then may still hold these,
    # and they are passed over when it is read (and left out when it is next written).
    FORMER = ("variant", "words", "measured", "retired", "seed", "place")


class Bucket:
    """One style's music on disk: its written pieces, each kept as the stretches of its parts.
    It is named for the place it was begun in."""

    def __init__(self, root: Path, zone: str, genre: str, bpm: int, tonic: str):
        self.root, self.zone, self.genre, self.bpm, self.tonic = Path(root), zone, genre, bpm, tonic
        self.folder = self.root / genre / zone
        self.clips: list[Clip] = []
        self.pieces: dict[str, dict[str, Any]] = {}       # written music: what each piece is, by its id
        self.version = 0
        index = self.folder / "bucket.json"
        if index.is_file():
            kept = json.loads(index.read_text(encoding="utf-8"))
            self.bpm, self.tonic = kept["bpm"], kept["tonic"]      # what its phrases were made at
            self.clips = [Clip(**{name: value for name, value in clip.items() if name not in Clip.FORMER})
                          for clip in kept["clips"]]
            self.pieces = kept.get("pieces", {})
            self.version = kept.get("version", len(self.clips))

    @property
    def key(self) -> str:
        return "%s/%s" % (self.genre, self.zone)

    @property
    def bar_frames(self) -> float:
        """How long a bar is, in samples. At most tempos a whole number; at some (110) not."""
        return RATE * 240.0 / self.bpm

    @property
    def cycle(self) -> int:
        """The length of every phrase in play, in bars: one turn of the form at this tempo."""
        return cycle_bars(self.bpm)

    def _in_play(self, clip: Clip) -> bool:
        """A part of a piece is in play for as long as the piece is: a ban is on the whole piece."""
        piece = self.pieces.get(clip.piece)
        return piece is not None and not piece.get("banned") and not clip.banned

    def live(self) -> list[Clip]:
        return [clip for clip in self.clips if self._in_play(clip)]

    def _save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.version += 1
        index = {"zone": self.zone, "genre": self.genre, "bpm": self.bpm, "tonic": self.tonic,
                 "version": self.version, "pieces": self.pieces, "clips": [asdict(clip) for clip in self.clips]}
        scratch = self.folder / "bucket.json.new"
        scratch.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
        scratch.replace(self.folder / "bucket.json")

    def add_piece(self, parts: dict[tuple[str, int], np.ndarray], *, title: str, bar_frames: float, bars: int,
                  post: int = 0, tonic: str = "", story: str = "", moods: tuple[str, ...] | list[str] = (),
                  role: str = "wander", serves: tuple[int, ...] | list[int] = (0, 1),
                  follow: dict[str, list[str]] | None = None, floor: dict[str, float] | None = None,
                  track: str = "", after: str = "", gain_db: float | None = None, source: str = "",
                  credit: str = "", family: str = "", light: bool = False, settings: tuple[str, ...] | list[str] = ()) -> str:
        """Puts a piece of written music in the bucket and returns its id.

        A piece is music that was written as a whole and is kept as its parts: `parts` holds one
        recording for each channel that plays in it (and, where the writer made them, for more
        than one strength of a channel), every one the same length and in step with the others.
        The player plays the parts together, as loud as the game asks for each, so a piece keeps
        its own harmony and its own shape however the channels come and go.

        A piece keeps its own time: `bar_frames` is the length of one of its bars in samples and
        need not be the bucket's. Each recording is the piece (a whole number of samples of it)
        followed by `post` samples of whatever the music went on to, which is what is heard
        fading away under the next piece. A long part is kept in stretches of `bars` bars.

        `story` says where in a story the piece belongs (STORY), `moods` the kinds of place it
        was written for (atlas.KINDS), `role` the director's kind of moment (director.PLACES)
        and `serves` the strengths of what the game asks for that it answers (0 calm, 1 steady,
        2 hard). `follow` makes a channel as loud as the loudest of some others (a band kept
        as one part stands in for the tune and the drone), and `floor` is the least each
        channel is ever played at, so that the moment a story comes to is whole whatever the
        game is doing. `track` is the larger work it was cut from and `after` the piece of
        that work it follows: the player goes on from one to the next without a seam.
        `family` names the changes it was written over: pieces of one family that stand at
        the same place in the story are the same length, bar for bar and chord for chord, so
        the player may take any channel of one with the other channels of another. `light`
        says the piece is of the lighter kind; light and heavy take turns. `settings` are the
        sorts of ground it was written for (atlas.SETTINGS: woods, water, heights...).

        The bucket notes how many pieces of its track come before each piece (its `place`): a
        long track uses a story word more than once (a theme, a second theme, the calm between
        two rises), so the word alone does not say where in the story a piece stands.
        """
        if not parts:
            raise ValueError("A piece needs at least one part")
        lengths = {len(audio) for audio in parts.values()}
        if len(lengths) != 1:
            raise ValueError("The parts of a piece are all one length; these are %s" % sorted(lengths))
        whole = lengths.pop() - post
        if whole <= 0 or post < 0:
            raise ValueError("A piece of %d samples cannot be followed by %d of them" % (whole + post, post))
        if story and story not in STORY:
            raise ValueError("A piece's place in a story is one of %s, not %r" % (", ".join(STORY), story))
        if after and after not in self.pieces:
            raise KeyError("No piece %r for this one to follow" % after)
        for (channel, tier), audio in parts.items():
            if channel not in CHANNELS or tier not in TIERS or audio.ndim != 2 or audio.shape[1] != CHANNELS_OUT:
                raise ValueError("A part is stereo audio for one of %s at a strength of 0, 1 or 2" % (CHANNELS,))
        # One gain for the whole piece, so that its parts keep the balance they were written
        # with: it brings the piece, every channel playing at its middle strength, to the level
        # five decks of phrases come to, and never lets the hardest of it pass full scale.
        if gain_db is None:
            middle = np.zeros((whole, CHANNELS_OUT), dtype=np.float32)
            loudest = np.zeros((whole, CHANNELS_OUT), dtype=np.float32)
            for channel in CHANNELS:
                have = sorted(tier for name, tier in parts if name == channel)
                if not have:
                    continue
                middle += parts[(channel, min(have, key=lambda tier: abs(tier - 1)))][:whole]
                loudest += parts[(channel, have[-1])][:whole]
            lufs = analysis.loudness_lufs(middle, RATE)
            if lufs < -60.0:
                raise ValueError("The piece %r is all but silent (%.0f LUFS)" % (title, lufs))
            peak = max(analysis.peak(middle), analysis.peak(loudest), 1e-6)
            gain_db = min(PIECE_LEVEL - lufs, -20.0 * float(np.log10(peak)) - 1.0)
        window = bars * bar_frames
        # (A bar is not always a whole number of samples, and a part that is one sample over
        # so many bars is not given a stretch of one sample for it.)
        count = max(int(np.ceil((whole - 1.0) / window)), 1)
        edges = [min(int(round(index * window)), whole) for index in range(count)] + [whole]
        piece_id = uuid.uuid4().hex[:10]
        (self.folder / "clips").mkdir(parents=True, exist_ok=True)
        keep = int(POST_S * RATE)
        made: list[tuple[Clip, np.ndarray]] = []
        for (channel, tier), audio in sorted(parts.items()):
            for order, (first, last) in enumerate(zip(edges, edges[1:])):
                stretch = audio[first:min(last + keep, len(audio))]
                made.append((Clip(id=uuid.uuid4().hex[:10], channel=channel, tier=tier,
                                  bars=max(int(round((last - first) / bar_frames)), 1), frames=last - first,
                                  gain_db=round(float(gain_db), 2), created=time.time(), source=source or "written",
                                  piece=piece_id, order=order, post=len(stretch) - (last - first)), stretch))

        def keep_clip(job: tuple[Clip, np.ndarray]) -> None:
            # The parts of pieces are kept losslessly, as FLAC (2026-11-17, morning: "Make sure the mp3s arent losing
            # quality"): what is played is what was staged, to 16 bits (96 dB down; a third less room than 24).
            clip, stretch = job
            scratch = self.folder / "clips" / (clip.id + ".part.flac")
            soundfile.write(str(scratch), np.clip(stretch, -1.0, 1.0), RATE, format="FLAC", subtype="PCM_16")
            scratch.replace(self.folder / "clips" / (clip.id + ".flac"))

        # Many at once (2026-11-17, night: one after another, a whole style's bucket took hours to build): the encoder
        # works outside Python's lock, so threads share the cores. An encoding that fails stops the piece with its error.
        with ThreadPoolExecutor(max_workers=ENCODERS) as pool:
            list(pool.map(keep_clip, made))
        self.clips += [clip for clip, _ in made]
        self.pieces[piece_id] = {
            "title": title, "track": track, "next": "", "story": story, "moods": list(moods), "role": role,
            "serves": sorted(set(int(tier) for tier in serves)), "bar_frames": float(bar_frames), "bars": int(bars),
            "frames": int(whole), "windows": count, "tonic": tonic, "follow": follow or {}, "floor": floor or {},
            "source": source, "credit": credit, "family": family, "light": bool(light), "settings": list(settings), "created": time.time(),
            "banned": False, "loved": False,
            # (A piece put in before places were kept has none; it was the only one of its word.)
            "place": int(self.pieces[after].get("place") or 0) + 1 if after else 0}
        if after:
            self.pieces[after]["next"] = piece_id
        self._save()
        return piece_id

    def drop_piece(self, piece_id: str) -> None:
        """Takes a piece out of the bucket for good, with the recordings of its parts."""
        if piece_id not in self.pieces:
            raise KeyError("No piece %r in the bucket for %s" % (piece_id, self.key))
        for clip in [clip for clip in self.clips if clip.piece == piece_id]:
            self._file(clip.id).unlink()
            self.clips.remove(clip)
        del self.pieces[piece_id]
        for piece in self.pieces.values():
            if piece.get("next") == piece_id:
                piece["next"] = ""
        self._save()

    def live_pieces(self) -> dict[str, dict[str, Any]]:
        """The pieces in play, by id."""
        return {piece_id: piece for piece_id, piece in self.pieces.items() if not piece.get("banned")}

    def mark(self, clip_ids: list[str], *, banned: bool | None = None, loved: bool | None = None) -> list[Clip]:
        """Bans the pieces these parts belong to, or marks them as loved: a ban or a love is for a
        whole piece, and every part of it is marked and returned."""
        wanted, found = set(clip_ids), []
        pieces = {clip.piece for clip in self.clips if clip.id in wanted and clip.piece}
        for piece_id in pieces:
            for name, value in (("banned", banned), ("loved", loved)):
                if value is not None:
                    self.pieces[piece_id][name] = value
        for clip in self.clips:
            if clip.id in wanted or clip.piece in pieces:
                found.append(clip)
                for name, value in (("banned", banned), ("loved", loved)):
                    if value is not None:
                        setattr(clip, name, value)
        if found:
            self._save()
        return found

    def played(self, clip_ids: list[str]) -> None:
        """Counts one more play for each of these parts. A part the bucket does not have (the
        page is still playing another bucket's) is passed over."""
        wanted, found = set(clip_ids), False
        for clip in self.clips:
            if clip.id in wanted:
                clip.plays += 1
                found = True
        if found:
            self._save()

    def samples(self, clip_id: str) -> bytes:
        """A stretch of a part, and what the music went on to, as 16-bit little-endian stereo."""
        if not any(clip.id == clip_id for clip in self.clips):
            raise KeyError("No part %r in the bucket for %s" % (clip_id, self.key))
        return self.audio(clip_id).tobytes()

    def _file(self, clip_id: str) -> Path:
        """Where a stretch of a part is kept: a FLAC file."""
        return self.folder / "clips" / (clip_id + ".flac")

    def audio(self, clip_id: str) -> np.ndarray:
        """A stretch of a part as 16-bit stereo samples, and then what the music went on to."""
        path = self._file(clip_id)
        samples, rate = soundfile.read(str(path), dtype="int16", always_2d=True)
        if rate != RATE:
            raise ValueError("%s is at %d Hz, not %d" % (path, rate, RATE))
        return np.ascontiguousarray(samples, dtype="<i2")

    def describe(self) -> dict[str, Any]:
        """What the player needs to know to play from this bucket."""
        verse, build, chorus = form(self.bpm)
        return {"key": self.key, "zone": self.zone, "genre": self.genre, "bpm": self.bpm, "tonic": self.tonic,
                "rate": RATE, "bar_frames": self.bar_frames, "version": self.version,
                # Every phrase is one turn of this form. The decks take new phrases where it
                # comes round, `changes` of them at most, so the song moves on a verse at a time.
                "cycle_bars": self.cycle, "form": {"verse": verse, "build": build, "chorus": chorus},
                "changes": CHANGES, "arc": ARC[self.genre],
                # Written music: what each piece is. Its parts are among the clips.
                "pieces": {piece_id: dict({name: piece[name] for name in (
                    "title", "track", "next", "story", "moods", "role", "serves", "bar_frames", "bars", "frames",
                    "windows", "tonic", "follow", "floor", "family", "light")}, place=piece.get("place"),
                    settings=piece.get("settings") or [])
                    for piece_id, piece in self.live_pieces().items()},
                "free_share": FREE_SHARE,
                "clips": [self.brief(clip) for clip in self.live()]}

    @staticmethod
    def brief(clip: Clip) -> dict[str, Any]:
        """A stretch of a part as the player is told of it."""
        return {"id": clip.id, "channel": clip.channel, "tier": clip.tier, "bars": clip.bars,
                "frames": clip.frames, "gain_db": clip.gain_db, "new": clip.plays == 0,
                "piece": clip.piece, "order": clip.order, "post": clip.post, "plays": clip.plays}


class Buckets:
    """Every bucket, by place and style."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._have: dict[str, Bucket] = {}
        self._home: dict[str, Bucket] = {}       # the one bucket each style plays from

    def get(self, place_name: str | None, genre: str) -> Bucket:
        profile = composer.for_genre(atlas.profile_for(place_name), genre)
        key = "%s/%s" % (genre, profile.key)
        if key not in self._have:
            self._have[key] = Bucket(self.root, profile.key, genre, profile.bpm, profile.tonic)
        return self._have[key]

    def home(self, genre: str, place_name: str | None) -> Bucket | None:
        """The bucket a style's song is played from, wherever the player goes.

        A style has one bucket: the song does not start again at a zone's border. It is the
        bucket on disk with the most in play for that style, or a new one for `place_name` if the
        style has none yet; None if it has none and the place is not known yet."""
        if genre in self._home:
            return self._home[genre]
        best = None
        for index in sorted((self.root / genre).glob("*/bucket.json")):
            bucket = self.by_key("%s/%s" % (genre, index.parent.name))
            if bucket.live() and (best is None or len(bucket.live()) > len(best.live())):
                best = bucket
        if best is None:
            if not place_name:
                return None
            best = self.get(place_name, genre)
        self._home[genre] = best
        return best

    def by_key(self, key: str) -> Bucket:
        if key not in self._have:
            genre, _, zone = key.partition("/")
            index = self.root / genre / zone / "bucket.json"
            if not index.is_file():
                raise KeyError("No bucket %r" % key)
            kept = json.loads(index.read_text(encoding="utf-8"))
            self._have[key] = Bucket(self.root, zone, genre, kept["bpm"], kept["tonic"])
        return self._have[key]


__all__ = ["Bucket", "Buckets", "Clip", "measure", "mix", "form", "cycle_bars", "CHANNELS", "TIERS", "STORY",
           "PIECE_LEVEL"]
