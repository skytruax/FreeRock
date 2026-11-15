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
MAX_START_TO_BEAT_MS = 60.0
MAX_VOCAL_LEAK_DB = -30.0
MAX_LENGTH_OFF_S = 0.1


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


def check(request: composer.Request, mix: np.ndarray, layers: Layers, rate: int) -> dict[str, Any]:
    """Measures a track against its request. The result has `failed`, a list of what went wrong
    in words, empty when the track is good."""
    failed: list[str] = []
    asked = request.parts[-1].end_ms / 1000.0
    got = len(mix) / rate
    if abs(got - asked) > MAX_LENGTH_OFF_S:
        failed.append("asked for %.2f s, got %.2f s" % (asked, got))
    parts, agree = {}, 0
    for part in request.parts:
        start = part.start_ms * rate // 1000
        end = min(part.end_ms * rate // 1000, len(mix))
        if end - start < rate * 4:
            continue                                   # the track is far too short; already noted
        grid = analysis.fit_grid(mix[start:end], rate, request.bpm, start_s=part.start_ms / 1000.0)
        key = analysis.estimate_key(mix[start:end], rate)
        off = (grid.bpm / request.bpm - 1.0) * 100.0
        to_beat = grid.distance_to_beat_s(part.start_ms / 1000.0) * 1000.0
        # The parts are held to the notes of the key that was asked for, not to its name: see
        # KeyEstimate.in_family for why a key finder names a different key from part to part.
        fits = key.in_family(request.tonic)
        agree += fits
        parts[part.name] = {"tempo_off_percent": round(off, 3), "start_to_beat_ms": round(to_beat, 1),
                            "heard_as": key.name, "key_agrees": fits,
                            "tuning_cents": round(key.tuning_cents, 1)}
        # The opening part is a drone and one guitar, with little to fit a beat to; it is noted
        # but only the parts with a full band are held to the tempo.
        if part.name != "Arrival":
            if abs(off) > MAX_TEMPO_OFF_PERCENT:
                failed.append("%s is %.2f%% off tempo" % (part.name, off))
            if abs(to_beat) > MAX_START_TO_BEAT_MS:
                failed.append("%s starts %.0f ms from a beat" % (part.name, to_beat))
    if parts and agree < len(parts) - 1:
        failed.append("only %d of %d parts use the notes of %s" % (agree, len(parts), request.tonic))
    if layers.vocal_leak_db > MAX_VOCAL_LEAK_DB:
        failed.append("there seems to be singing (%.1f dB)" % layers.vocal_leak_db)
    return {"failed": failed, "parts": parts, "vocal_leak_db": round(layers.vocal_leak_db, 1),
            "seconds": round(got, 3)}


class Ingest:
    def __init__(self, gateway: Gateway, library: Library,
                 splitter: Callable[[np.ndarray, int], Layers] = split,
                 rng: random.Random | None = None):
        self.gateway = gateway
        self.library = library
        self.splitter = splitter
        self.rng = rng or random.Random()

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
                    reroll: bool) -> Made:
        mix, stream = await self._generate(request, purpose=purpose, zone=zone, reroll=reroll)
        # Splitting takes over a minute of processor time; it runs off to the side so the server
        # keeps answering the player and the sensor meanwhile.
        layers = await asyncio.to_thread(self.splitter, mix, RATE)
        checks = await asyncio.to_thread(check, request, mix, layers, RATE)
        if checks["failed"]:
            kept = await asyncio.to_thread(self._keep_rejected, zone, request, mix, checks, stream.song_id)
            raise TrackFailedChecks(zone, checks, kept)
        asset = await asyncio.to_thread(
            self.library.add, zone=zone, set_name=set_name, request=request, mix=mix, layers=layers,
            song_id=stream.song_id, checks=checks)
        return Made(asset=asset, first_audio_s=stream.first_audio_s, total_s=stream.total_s,
                    split_s=layers.seconds)

    def _keep_rejected(self, zone: str, request: composer.Request, mix: np.ndarray,
                       checks: dict[str, Any], song_id: str | None) -> Path:
        """A track that failed its checks cost the same as one that passed. It is kept, out of
        the library, with what was asked for and what was measured: either the track is at fault
        and the request wants changing, or the checks are, and only the audio can say which."""
        folder = self.library.root.parent / "rejected" / ("%s-%s" % (zone, time.strftime("%Y%m%d-%H%M%S")))
        folder.mkdir(parents=True)
        write_flac(folder / "mix.flac", mix, RATE)
        (folder / "checks.json").write_text(json.dumps({
            "zone": zone, "bpm": request.bpm, "tonic": request.tonic, "seed": request.seed,
            "song_id": song_id, "checks": checks, "plan": request.plan,
            "parts": [{"name": part.name, "bars": part.bars, "start_ms": part.start_ms, "end_ms": part.end_ms}
                      for part in request.parts]}, indent=2) + "\n", encoding="utf-8")
        return folder

    async def adopt(self, folder: Path, set_name: str = "core") -> Made:
        """Looks again at a track that was kept after failing its checks and, if it passes them as
        they are now, puts it in the library. Costs nothing: the audio is already here."""
        noted = json.loads((Path(folder) / "checks.json").read_text(encoding="utf-8"))
        mix, rate = read_audio(Path(folder) / "mix.flac")
        if rate != RATE:
            raise ValueError("The kept track is at %d Hz, not %d" % (rate, RATE))
        request = composer.Request(
            plan=noted["plan"], bpm=noted["bpm"], tonic=noted["tonic"], seed=noted["seed"],
            parts=[composer.Part(part["name"], part["bars"], part["start_ms"], part["end_ms"])
                   for part in noted["parts"]])
        layers = await asyncio.to_thread(self.splitter, mix, RATE)
        checks = await asyncio.to_thread(check, request, mix, layers, RATE)
        if checks["failed"]:
            raise TrackFailedChecks(noted["zone"], checks, Path(folder))
        asset = await asyncio.to_thread(
            self.library.add, zone=noted["zone"], set_name=set_name, request=request, mix=mix,
            layers=layers, song_id=noted.get("song_id"), checks=checks)
        return Made(asset=asset, first_audio_s=None, total_s=None, split_s=layers.seconds)

    async def core_suite(self, place_name: str | None, *, rock: float = 0.5, seed: int | None = None,
                         reroll: bool = False) -> Made:
        """A zone's first music, from the zone's name as the game gives it."""
        profile = atlas.profile_for(place_name)
        request = composer.core_suite(profile, seed=seed if seed is not None else self.rng.randrange(2 ** 31),
                                      rock=rock, part_bars=atlas.part_bars(profile.bpm))
        return await self._make(request, zone=profile.key, set_name="core",
                                purpose="core suite", reroll=reroll)

    async def later_set(self, core: Asset, place_name: str | None, kind: str, *, rock: float = 0.5,
                        seed: int | None = None, reroll: bool = False) -> Made:
        """More music for a zone that already has its core suite: kind is "second" or "fresh". It
        is told to stay close to thirty seconds of the core suite's first Wander riff, so it
        sounds like the same band."""
        if kind not in ("second", "fresh"):
            raise ValueError("kind must be second or fresh, not %r" % kind)
        profile = atlas.profile_for(place_name)
        reference = None
        if core.song_id:
            riff = core.section("Wander A")
            start_ms = riff.start * 1000 // core.rate
            reference = composer.Reference(core.song_id, start_ms, start_ms + 30_000)
        maker = composer.second_set if kind == "second" else composer.fresh_set
        request = maker(profile, seed=seed if seed is not None else self.rng.randrange(2 ** 31),
                        rock=rock, reference=reference, part_bars=atlas.part_bars(profile.bpm))
        return await self._make(request, zone=profile.key, set_name=kind,
                                purpose="%s set" % kind, reroll=reroll)
