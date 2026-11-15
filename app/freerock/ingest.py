"""Making new music for a zone: ask ElevenLabs, split the layers, check the result, store it.

One call here is the whole journey of a track: the request is written from the zone's profile,
streamed from ElevenLabs through the paid-call gateway, split into bed, drums and bass on this
machine, measured against what was asked for, and put in the library. A track that fails its
checks is not stored; the caller decides whether to try again.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import analysis, atlas, composer
from .audio import PcmStream, read_audio, write_flac
from .eleven import Gateway
from .library import Asset, Library
from .stems import Layers, split

# What experiment 0 found the account allows: uncompressed 48 kHz stereo.
FORMAT, RATE, CHANNELS = "pcm_48000", 48000, 2

# The pass lines a track has to meet before it is stored.
MAX_TEMPO_OFF_PERCENT = 1.0
# The parts have to keep one beat between them: each part's start may be this far from where the
# others put the beat. Where that beat falls against the clock is not held against a track. The
# player cuts every part of a track at the same point in the beat, so a track that runs a little
# late throughout, or whose loudest hits are on the off-beat, loops and changes part as cleanly as
# any other. (Measured on 2026-11-15: one track read 297 ms from the beat in every part, which at
# 100 beats a minute is the off-beat, where its anvil strikes are.)
MAX_START_SPREAD_MS = 30.0
# Singing. The separator's "vocals" layer also catches a whistle, a flute or a fiddle playing
# alone, and half the zones ask for one of those. So a track is turned away for singing when that
# layer is plainly a large part of the whole track, or when it is noticeable and has the top end
# that sung words have. Measured on 2026-11-15: a tin whistle solo read -21 dB overall and -52 dB
# where words are; the tracks without any such solo read -36 to -60 dB overall. A wordless voice
# cannot be told from a flute this way and is let through.
MAX_VOCAL_LEAK_DB = -30.0        # below this the vocals layer is too quiet to be anything
LOUD_VOCAL_LEAK_DB = -12.0       # above this it is a large part of the track whatever it is made of
MAX_VOCAL_WORDS_DB = -45.0       # the vocals layer between 2.5 and 8 kHz, relative to the whole mix
MAX_LENGTH_OFF_S = 0.1
# Parts with little to fit a beat to: one guitar alone, a drone, a chord left to ring. They are
# measured and noted, and not held to the tempo or the beat.
SPARSE_PARTS = ("Arrival", "Intro", "Outro")


class TrackFailedChecks(RuntimeError):
    """The music came back but is not what was asked for. `checks` says what was measured, and
    `kept` is the folder the audio was put in, so it can be listened to and the checks themselves
    can be checked."""

    def __init__(self, zone: str, checks: dict[str, Any], kept: Path | None = None):
        self.zone = zone
        self.checks = checks
        self.kept = kept
        message = "New music for %s failed its checks: %s." % (zone, "; ".join(checks["failed"]))
        if kept is not None:
            message += " The audio is kept in %s." % kept
        super().__init__(message)


@dataclass
class Made:
    asset: Asset
    first_audio_s: float | None
    total_s: float | None
    split_s: float


def shared_scale(keys: list[analysis.KeyEstimate], asked: int) -> tuple[int, int]:
    """The seven-note scale that most of a track's parts fit, give or take a note, as the pitch
    class of that scale's key note (0 is the scale of C major), and how many parts fit it. Where
    several scales do equally well, the one that was asked for wins, then the nearest to it."""
    def fits(key: analysis.KeyEstimate, root: int) -> bool:
        shares = key.scale_shares()
        family = max(shares[root], shares[(root + 7) % 12], shares[(root + 5) % 12])
        return bool(family >= shares.max() - 0.03)

    counts = [sum(fits(key, root) for key in keys) for root in range(12)]

    def apart(root: int) -> int:           # steps round the circle of fifths from what was asked for
        steps = ((root - asked) * 7) % 12
        return min(steps, 12 - steps)

    best = max(range(12), key=lambda root: (counts[root], -apart(root)))
    return best, counts[best]


def beat_offset(to_beat_ms: list[float], beat_ms: float) -> tuple[float, list[float]]:
    """Where the parts of a track put the beat, as one figure (how far after the asked-for starts
    it falls, between minus and plus half a beat), and how far each part is from that. Distances
    wrap round the beat: 297 ms after one beat and 299 ms before the next are 4 ms apart at 100
    beats a minute."""
    if not to_beat_ms:
        return 0.0, []

    def wrap(value: float) -> float:
        return (value + beat_ms / 2.0) % beat_ms - beat_ms / 2.0

    first = to_beat_ms[0]
    around_first = sorted(wrap(value - first) for value in to_beat_ms)
    middle = around_first[len(around_first) // 2] if len(around_first) % 2 else \
        (around_first[len(around_first) // 2 - 1] + around_first[len(around_first) // 2]) / 2.0
    offset = wrap(first + middle)
    return offset, [wrap(value - offset) for value in to_beat_ms]


def check(request: composer.Request, mix: np.ndarray, layers: Layers, rate: int) -> dict[str, Any]:
    """Measures a track against its request. The result has `failed`, a list of what went wrong
    in words, empty when the track is good."""
    failed: list[str] = []
    asked = request.parts[-1].end_ms / 1000.0
    got = len(mix) / rate
    if abs(got - asked) > MAX_LENGTH_OFF_S:
        failed.append("asked for %.2f s, got %.2f s" % (asked, got))
    parts, starts, keys = {}, {}, []
    astray: dict[str, list[str]] = {}       # part name -> what is off about its timing
    for part in request.parts:
        start = part.start_ms * rate // 1000
        end = min(part.end_ms * rate // 1000, len(mix))
        if end - start < rate * 4:
            continue                                   # the track is far too short; already noted
        grid = analysis.fit_grid(mix[start:end], rate, request.bpm, start_s=part.start_ms / 1000.0)
        key = analysis.estimate_key(mix[start:end], rate)
        off = (grid.bpm / request.bpm - 1.0) * 100.0
        to_beat = grid.distance_to_beat_s(part.start_ms / 1000.0) * 1000.0
        # Whether the part uses the notes of the key that was asked for is noted, not held against
        # it: see below.
        keys.append(key)
        parts[part.name] = {"tempo_off_percent": round(off, 3), "start_to_beat_ms": round(to_beat, 1),
                            "heard_as": key.name, "key_agrees": key.in_family(request.tonic),
                            "tuning_cents": round(key.tuning_cents, 1)}
        if part.name not in SPARSE_PARTS:
            if abs(off) > MAX_TEMPO_OFF_PERCENT:
                astray.setdefault(part.name, []).append("%s is %.2f%% off tempo" % (part.name, off))
            starts[part.name] = to_beat
    # Half a beat apart counts as together. Whether the beat finder hears the beat or the
    # off-beat depends on which is louder in a part (the kick, or the open hi-hat and bass between
    # the kicks), and in dance music it changes from part to part; the parts themselves start
    # where they were asked to. (Measured on 2026-11-15: trance parts read 232 ms apart at 128
    # beats a minute, where half a beat is 234 ms.)
    beat_ms = 60000.0 / request.bpm
    offset, apart = beat_offset(list(starts.values()), beat_ms / 2.0)
    for (name, _), distance in zip(starts.items(), apart):
        parts[name]["off_the_shared_beat_ms"] = round(distance, 1)
        if abs(distance) > MAX_START_SPREAD_MS:
            astray.setdefault(name, []).append(
                "%s starts %.0f ms off the beat the other parts keep" % (name, distance))
    # One part in five may read off without the track being turned away. ElevenLabs has held
    # the tempo it was asked for in every track measured; a single part that reads otherwise (a
    # breakdown with no drums, a solo passage) is far more often the measurement than the music,
    # and a track thrown away costs as much as one kept.
    noted = [words for found in astray.values() for words in found]
    if len(astray) > len(starts) // 5:
        failed.extend(noted)
    # The parts have to agree with each other on a set of notes (give or take one), so that going
    # from one to another is not a lurch. Which set is the music's own business: hard rock asked
    # for in A minor comes back leaning major as often as not, and is no worse for it. (Measured
    # on 2026-11-15: three tracks on the beat and without a voice were turned away for that.)
    if keys:
        scale, agree = shared_scale(keys, analysis.parent_scale(request.tonic))
        if agree < len(keys) - 1:
            failed.append("the parts do not share a set of notes: only %d of %d fit the scale of %s major, "
                          "the one most of them fit" % (agree, len(keys), analysis.PITCH_NAMES[scale]))
    if layers.vocal_leak_db > MAX_VOCAL_LEAK_DB and (
            layers.vocal_leak_db > LOUD_VOCAL_LEAK_DB or layers.vocal_words_db > MAX_VOCAL_WORDS_DB):
        failed.append("there seems to be singing (%.1f dB, and %.1f dB where sung words are)"
                      % (layers.vocal_leak_db, layers.vocal_words_db))
    return {"failed": failed, "noted": [] if failed else noted, "parts": parts,
            "vocal_leak_db": round(layers.vocal_leak_db, 1),
            "vocal_words_db": round(layers.vocal_words_db, 1), "beat_offset_ms": round(offset, 1),
            "shared_scale": "%s major" % analysis.PITCH_NAMES[scale] if keys else None,
            "seconds": round(got, 3)}


class Ingest:
    def __init__(self, gateway: Gateway, library: Library,
                 splitter: Callable[[np.ndarray, int], Layers] = split,
                 rng: random.Random | None = None):
        self.gateway = gateway
        self.library = library
        self.splitter = splitter
        self.rng = rng or random.Random()

    @property
    def genre(self) -> str:
        """The style new music is made in right now."""
        return self.gateway.settings.genre

    def _rock(self, rock: float | None) -> float:
        """How much rock new music gets: what was asked for, else the setting."""
        return self.gateway.settings.rock if rock is None else rock

    async def _generate(self, request: composer.Request, *, purpose: str, zone: str,
                        reroll: bool) -> tuple[np.ndarray, Any]:
        decoder, pieces = PcmStream(CHANNELS), []
        async with self.gateway.stream_music(
                purpose=purpose, zone=zone, plan=request.plan, seed=request.seed, output_format=FORMAT,
                store_for_inpainting=True, reroll=reroll) as stream:
            async for chunk in stream:
                pieces.append(decoder.feed(chunk))
        if decoder.leftover_bytes:
            raise RuntimeError("The audio from ElevenLabs ended in the middle of a sample")
        return np.concatenate(pieces), stream

    async def _make(self, request: composer.Request, *, zone: str, set_name: str, purpose: str,
                    reroll: bool, subzone: str | None = None, genre: str = "knight") -> Made:
        mix, stream = await self._generate(request, purpose=purpose, zone=zone, reroll=reroll)
        # Splitting takes over a minute of processor time; it runs off to the side so the server
        # keeps answering the player and the sensor meanwhile.
        layers = await asyncio.to_thread(self.splitter, mix, RATE)
        checks = await asyncio.to_thread(check, request, mix, layers, RATE)
        if checks["failed"]:
            kept = await asyncio.to_thread(self._keep_rejected, zone, request, mix, checks, stream.song_id,
                                           set_name, subzone, genre)
            raise TrackFailedChecks(zone, checks, kept)
        asset = await asyncio.to_thread(
            self.library.add, zone=zone, set_name=set_name, request=request, mix=mix, layers=layers,
            song_id=stream.song_id, checks=checks, subzone=subzone, genre=genre)
        return Made(asset=asset, first_audio_s=stream.first_audio_s, total_s=stream.total_s,
                    split_s=layers.seconds)

    async def place_piece(self, core: Asset, zone_name: str | None, place_name: str, *,
                          rock: float | None = None, seed: int | None = None,
                          reroll: bool = False) -> Made:
        """A short piece for one named place inside a zone (the Hall of Thanes in Ironforge): the
        zone's tempo and key, the place's own colours, and told to stay close to the zone's first
        riff so it is the same band. Sixteen bars, so it is ready in well under a minute."""
        profile = atlas.place_profile(zone_name, place_name)
        reference = None
        if core.song_id:
            riff = self._signature(core)
            start_ms = riff.start * 1000 // core.rate
            reference = composer.Reference(core.song_id, start_ms, start_ms + min(30_000, int(riff.end - riff.start) * 1000 // core.rate))
        request = composer.place_piece(profile, seed=seed if seed is not None else self.rng.randrange(2 ** 31),
                                       rock=self._rock(rock), reference=reference, genre=core.genre)
        return await self._make(request, zone=core.zone, set_name="place", purpose="place piece",
                                reroll=reroll, subzone=atlas.slug(place_name), genre=core.genre)

    def _keep_rejected(self, zone: str, request: composer.Request, mix: np.ndarray,
                       checks: dict[str, Any], song_id: str | None, set_name: str = "core",
                       subzone: str | None = None, genre: str = "knight") -> Path:
        """A track that failed its checks cost the same as one that passed. It is kept, out of
        the library, with what was asked for and what was measured: either the track is at fault
        and the request wants changing, or the checks are, and only the audio can say which."""
        folder = self.library.root.parent / "rejected" / ("%s-%s" % (zone, time.strftime("%Y%m%d-%H%M%S")))
        folder.mkdir(parents=True)
        write_flac(folder / "mix.flac", mix, RATE)
        (folder / "checks.json").write_text(json.dumps({
            "zone": zone, "set": set_name, "subzone": subzone, "genre": genre,
            "bpm": request.bpm, "tonic": request.tonic, "seed": request.seed,
            "song_id": song_id, "checks": checks, "plan": request.plan,
            "parts": [{"name": part.name, "bars": part.bars, "start_ms": part.start_ms, "end_ms": part.end_ms,
                       "song": part.song} for part in request.parts]}, indent=2) + "\n", encoding="utf-8")
        return folder

    async def adopt(self, folder: Path, set_name: str | None = None) -> Made:
        """Looks again at a track that was kept after failing its checks and, if it passes them as
        they are now, puts it in the library as what it was made to be (its set, its place, its
        style). Costs nothing: the audio is already here."""
        noted = json.loads((Path(folder) / "checks.json").read_text(encoding="utf-8"))
        set_name = set_name or noted.get("set") or "core"
        mix, rate = read_audio(Path(folder) / "mix.flac")
        if rate != RATE:
            raise ValueError("The kept track is at %d Hz, not %d" % (rate, RATE))
        request = composer.Request(
            plan=noted["plan"], bpm=noted["bpm"], tonic=noted["tonic"], seed=noted["seed"],
            parts=[composer.Part(part["name"], part["bars"], part["start_ms"], part["end_ms"], part.get("song"))
                   for part in noted["parts"]])
        layers = await asyncio.to_thread(self.splitter, mix, RATE)
        checks = await asyncio.to_thread(check, request, mix, layers, RATE)
        if checks["failed"]:
            raise TrackFailedChecks(noted["zone"], checks, Path(folder))
        asset = await asyncio.to_thread(
            self.library.add, zone=noted["zone"], set_name=set_name, request=request, mix=mix,
            layers=layers, song_id=noted.get("song_id"), checks=checks, subzone=noted.get("subzone"),
            genre=noted.get("genre") or "knight")
        return Made(asset=asset, first_audio_s=None, total_s=None, split_s=layers.seconds)

    async def core_suite(self, place_name: str | None, *, rock: float | None = None,
                         seed: int | None = None, reroll: bool = False,
                         context: list[str] | None = None) -> Made:
        """A zone's first music, from the zone's name as the game gives it, in the style the
        settings name."""
        profile, genre = atlas.profile_for(place_name), self.genre
        request = composer.core_suite(profile, seed=seed if seed is not None else self.rng.randrange(2 ** 31),
                                      rock=self._rock(rock), part_bars=self._part_bars(profile, genre), genre=genre,
                                      context=context)
        return await self._make(request, zone=profile.key, set_name="core",
                                purpose="core suite", reroll=reroll, genre=genre)

    @staticmethod
    def _signature(core: Asset):
        """The stretch of a zone's first music that later music is told to stay close to: the
        chorus of its song, or for music made before there were songs its first riff."""
        for name in ("Chorus", "Wander A"):
            for section in core.sections:
                if section.name == name:
                    return section
        return core.sections[0]

    @staticmethod
    def _part_bars(profile: composer.ZoneProfile, genre: str) -> int:
        """How long a piece is, at the tempo the style plays this zone at."""
        return atlas.part_bars(composer.for_genre(profile, genre).bpm)

    async def later_set(self, core: Asset, place_name: str | None, kind: str, *,
                        rock: float | None = None, seed: int | None = None,
                        reroll: bool = False, context: list[str] | None = None) -> Made:
        """More music for a zone that already has its core suite: kind is "second" or "fresh". It
        is told to stay close to thirty seconds of the core suite's first Wander riff, so it
        sounds like the same band."""
        if kind not in ("second", "fresh"):
            raise ValueError("kind must be second or fresh, not %r" % kind)
        profile, genre = atlas.profile_for(place_name), core.genre     # more of the same style as its core
        reference = None
        if core.song_id:
            riff = self._signature(core)
            start_ms = riff.start * 1000 // core.rate
            reference = composer.Reference(core.song_id, start_ms, start_ms + min(30_000, (core.frames - riff.start) * 1000 // core.rate))
        chosen = seed if seed is not None else self.rng.randrange(2 ** 31)
        bars = self._part_bars(profile, genre)
        if kind == "second":
            request = composer.second_set(profile, seed=chosen, rock=self._rock(rock), reference=reference,
                                          part_bars=bars, genre=genre, context=context)
        else:
            # Each fresh set goes further down the lists of feels than the one before it.
            had = sum(1 for asset in self.library.assets(core.zone)
                      if asset.set == "fresh" and asset.genre == genre)
            request = composer.fresh_set(profile, seed=chosen, rock=self._rock(rock), reference=reference,
                                         part_bars=bars, turn=had, genre=genre, context=context)
        return await self._make(request, zone=profile.key, set_name=kind,
                                purpose="%s set" % kind, reroll=reroll, genre=genre)
