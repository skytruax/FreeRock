"""The music library: every generated track, cut into sections and cells, ready for the player.

A track (an "asset") is one request's worth of music for one zone. It is stored as three layers
(bed, drums, bass) that add up to the original, each as plain 16-bit samples so any stretch can be
handed to the player without decoding, plus a small description file saying where each section
and cell starts and how loud it should be played.

    var/library/<zone>/<asset id>/asset.json, bed.npy, drums.npy, bass.npy, mix.flac
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import analysis
from .audio import write_flac
from .composer import BEATS_PER_BAR, Request
from .stems import Layers

LAYERS = ("bed", "drums", "bass")
BARS_PER_CELL = 4

# How loud each kind of section is played, in LUFS. The suites come back from ElevenLabs at much
# the same loudness whatever the part (about -10), so the difference between calm and battle is
# set here. The whole scale sits a little under that, which leaves the limiter with nothing to do
# in ordinary play while keeping the music loud; the volume control goes down from here.
TARGET_LUFS = {"arrival": -16.0, "wander": -16.0, "ember": -19.0, "night": -18.0, "depths": -17.0,
               "storm": -15.0, "battle": -14.0, "boss": -13.0}


def role_of(part_name: str) -> str:
    """What a part is for: "Wander B" and "Wander C" are both wander, "Battle B" is battle."""
    words = part_name.lower().split()
    if len(words) > 1 and len(words[-1]) == 1:
        words = words[:-1]
    role = " ".join(words)
    if role == "theme":
        role = "wander"            # a place's own piece is played where the zone's riffs are
    if role not in TARGET_LUFS:
        raise ValueError("Unknown kind of part: %r" % part_name)
    return role


@dataclass
class Cell:
    start: int   # frames from the start of the asset
    end: int


@dataclass
class Section:
    name: str
    role: str
    start: int
    end: int
    gain_db: float              # applied to all three layers alike, so they still add up
    measured_lufs: float
    cells: list[Cell]


@dataclass
class Asset:
    id: str
    zone: str
    set: str                    # core | second | fresh
    bpm: int
    tonic: str
    rate: int
    frames: int
    minutes: float
    created: float
    sections: list[Section]
    seed: int | None = None
    song_id: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)
    loved: bool = False
    banned: bool = False
    retired: bool = False       # set aside to make room for a newer set; kept on disk, not played
    subzone: str | None = None  # the named place inside the zone this piece was made for, if any
    genre: str = "knight"       # the style it is in: knight | warcraft | trance (composer.GENRES)

    @property
    def usable(self) -> bool:
        return not self.banned and not self.retired

    @property
    def bar_frames(self) -> int:
        return self.rate * 60 * BEATS_PER_BAR // self.bpm

    def section(self, name: str) -> Section:
        for section in self.sections:
            if section.name == name:
                return section
        raise KeyError(name)

    def sections_for(self, role: str) -> list[Section]:
        return [section for section in self.sections if section.role == role]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Asset":
        sections = [Section(**{**section, "cells": [Cell(**cell) for cell in section["cells"]]})
                    for section in data["sections"]]
        return cls(**{**data, "sections": sections})


def _to_int16(audio: np.ndarray) -> np.ndarray:
    return np.round(np.clip(audio, -1.0, 32767.0 / 32768.0) * 32768.0).astype(np.int16)


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._open: dict[tuple[str, str], np.ndarray] = {}

    def _folder(self, asset: Asset) -> Path:
        return self.root / asset.zone / asset.id

    # --- adding ----------------------------------------------------------------------------------

    def add(self, *, zone: str, set_name: str, request: Request, mix: np.ndarray, layers: Layers,
            song_id: str | None = None, checks: dict[str, Any] | None = None,
            subzone: str | None = None, genre: str = "knight") -> Asset:
        """Stores a finished track. `mix` is what ElevenLabs sent; `layers` is its split."""
        rate = layers.rate
        if len(mix) != len(layers.bed):
            raise ValueError("The mix and its layers are different lengths")
        bar = rate * 60 * BEATS_PER_BAR // request.bpm
        if bar * request.bpm != rate * 60 * BEATS_PER_BAR:
            raise ValueError("A bar at %d BPM is not a whole number of frames at %d Hz" % (request.bpm, rate))
        expected = request.parts[-1].end_ms * rate // 1000
        if abs(len(mix) - expected) > rate // 10:
            raise ValueError("Asked for %.2f s of music, got %.2f s" % (expected / rate, len(mix) / rate))

        sections = []
        for part in request.parts:
            start, end = part.start_ms * rate // 1000, min(part.end_ms * rate // 1000, len(mix))
            role = role_of(part.name)
            measured = analysis.loudness_lufs(mix[start:end], rate)
            cells = [Cell(start + index * BARS_PER_CELL * bar, start + (index + 1) * BARS_PER_CELL * bar)
                     for index in range(part.bars // BARS_PER_CELL)]
            if not cells:
                raise ValueError("%s has fewer than %d bars, too short to play from" % (part.name, BARS_PER_CELL))
            sections.append(Section(name=part.name, role=role, start=start, end=end,
                                    gain_db=round(TARGET_LUFS[role] - measured, 2),
                                    measured_lufs=round(measured, 2), cells=cells))

        asset = Asset(id=uuid.uuid4().hex[:12], zone=zone, set=set_name, bpm=request.bpm,
                      tonic=request.tonic, rate=rate, frames=len(mix), minutes=round(request.minutes, 3),
                      created=time.time(), sections=sections, seed=request.seed, song_id=song_id,
                      checks=checks or {}, subzone=subzone, genre=genre)
        folder = self._folder(asset)
        folder.mkdir(parents=True)
        # Whole samples, with the bed as what is left of the mix after drums and bass, so the three
        # stored layers add back up to the stored mix exactly.
        whole = _to_int16(mix).astype(np.int32)
        drums, bass = _to_int16(layers.drums), _to_int16(layers.bass)
        bed = np.clip(whole - drums - bass, -32768, 32767).astype(np.int16)
        for name, layer in (("bed", bed), ("drums", drums), ("bass", bass)):
            np.save(folder / (name + ".npy"), layer)
        write_flac(folder / "mix.flac", mix, rate)
        self._write(asset)
        return asset

    def _write(self, asset: Asset) -> None:
        (self._folder(asset) / "asset.json").write_text(
            json.dumps(asset.to_json(), indent=2) + "\n", encoding="utf-8")

    # --- finding ---------------------------------------------------------------------------------

    def assets(self, zone: str | None = None) -> list[Asset]:
        found = []
        for path in sorted(self.root.glob("*/*/asset.json")):
            asset = Asset.from_json(json.loads(path.read_text(encoding="utf-8")))
            if zone is None or asset.zone == zone:
                found.append(asset)
        return sorted(found, key=lambda asset: asset.created)

    def get(self, asset_id: str) -> Asset:
        for asset in self.assets():
            if asset.id == asset_id:
                return asset
        raise KeyError("No asset %r in the library" % asset_id)

    def usable(self, zone: str | None = None) -> list[Asset]:
        """The music that may be played: not banned and not retired. Core suite first, then the
        second set, then fresh sets, oldest first."""
        order = {"core": 0, "second": 1}
        return sorted((asset for asset in self.assets(zone) if asset.usable),
                      key=lambda asset: (asset.zone, order.get(asset.set, 2), asset.created))

    def mark(self, asset_id: str, *, loved: bool | None = None, banned: bool | None = None,
             retired: bool | None = None) -> Asset:
        asset = self.get(asset_id)
        if loved is not None:
            asset.loved = loved
        if banned is not None:
            asset.banned = banned
        if retired is not None:
            asset.retired = retired
        self._write(asset)
        return asset

    # --- audio for the player ----------------------------------------------------------------

    def _layer(self, asset: Asset, layer: str) -> np.ndarray:
        if layer not in LAYERS:
            raise KeyError("No layer %r; the layers are %s" % (layer, ", ".join(LAYERS)))
        key = (asset.id, layer)
        if key not in self._open:
            self._open[key] = np.load(self._folder(asset) / (layer + ".npy"), mmap_mode="r")
        return self._open[key]

    def samples(self, asset: Asset, layer: str, start: int, end: int) -> bytes:
        """Frames `start` to `end` of one layer as 16-bit little-endian stereo. Frames before the
        start or past the end of the asset come back as silence, so a cell can be asked for with a
        little extra either side without the caller having to know where the asset ends."""
        if end <= start:
            raise ValueError("Empty stretch asked for: %d to %d" % (start, end))
        data = self._layer(asset, layer)
        out = np.zeros((end - start, data.shape[1]), dtype="<i2")
        low, high = max(start, 0), min(end, len(data))
        if high > low:
            out[low - start:high - start] = data[low:high]
        return out.tobytes()


def merged(assets: list[Asset]) -> dict[str, Any]:
    """One description, for the player, of all the music a place has.

    A place's music may come from several requests: its core suite and the sets added later. The
    player treats them as one body of music; each section says which request its audio is in. Only
    sets on the same tempo as the first are included, since they have to share bar lines.
    """
    if not assets:
        raise ValueError("No music to describe")
    first = assets[0]
    same = [asset for asset in assets if asset.bpm == first.bpm and asset.rate == first.rate]
    # A section made for one named place says so ("tag"); the player plays it there and nowhere else.
    sections = [{**asdict(section), "asset_id": asset.id, "tag": asset.subzone}
                for asset in same for section in asset.sections]
    return {"id": "+".join(asset.id for asset in same), "zone": first.zone, "genre": first.genre,
            "set": " + ".join(asset.set for asset in same), "bpm": first.bpm, "tonic": first.tonic,
            "rate": first.rate, "bar_frames": first.bar_frames,
            "minutes": round(sum(asset.minutes for asset in same), 2), "sections": sections}
