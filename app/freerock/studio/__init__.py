"""The studio: where music is written, played by software instruments and put in the buckets.

Nothing here asks anyone outside this machine for anything. A writer (studio.orchestra for the
orchestra, studio.house for the dance floor) makes up a track as notes: a story in five parts
(it opens, states its theme, rises, comes to its moment and closes), written over a set of
changes for one kind of place and one kind of moment. Instruments play each part of the band
alone, and what comes out is staged: a folder for the track with one recording for each channel
and a small file saying what the track is. Staged tracks are then cut into pieces and put in a
style's bucket, where the player strings them together (see forever.Bucket.add_piece).

A staged track is a folder:

    var/studio/<style>/<family>/<take>/track.json
    var/studio/<style>/<family>/<take>/<channel>.flac      48 kHz stereo, one for each channel that plays

`family` names the changes: the tempo, the key, the chords bar by bar and the lengths of the five
parts of the story. Every take of a family is a whole track of its own (its own tune, its own
drums, its own bass) written over those same changes, so the player may take any channel of
one take with the other channels of another, and a family of three takes is a few hundred
different bands playing the same story.

track.json holds:

    style, family, take     where it belongs
    title                   what the track is called
    tempo, beats            beats a minute, and beats in a bar
    bar_frames              the length of a bar in samples (a fraction is fine)
    tonic                   its key, as "D minor" or "G mixolydian"
    moods                   the kinds of place it was written for (kinds.KINDS)
    role                    the kind of moment (director.PLACES): wander, night, ember, depths, storm, battle, boss
    serves                  the strengths of what the game asks for that it answers: 0 calm, 1 steady, 2 hard
    light                   whether it is of the lighter sort
    sections                the story: [{"story": "open", "bars": 8}, ...] in order; a section in another key
                            than the track's says so ("tonic")
    floor                   for each part of the story, the least each channel is played at: {"moment": {"drums": 0.7}}
    follow                  channels that are as loud as the loudest of some others: {"rhythm": ["lead"]}
    post_s                  how many seconds of ringing-on each recording has after the last bar
    level_db                (optional) how far under the usual level the whole track sits: music for an inn or
                            for the night is quieter than music for the road
    credit, seed            who or what wrote it, and the number it was written from

Each recording is the whole track (the bars of every section, in order) followed by `post_s`
seconds in which the last notes die away.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile

from .. import analysis, forever

RATE = forever.RATE
ROLES = ("wander", "night", "ember", "depths", "storm", "battle", "boss")
LIFT = 1.0                     # the loudest part of a track is this much over a bucket's usual level: it is the moment
QUIET = 10 ** (-72 / 20)       # a part that never rises above this in a piece is not playing in it


def stage_root(var: Path, style: str) -> Path:
    return Path(var) / "studio" / style


def write_track(folder: Path, meta: dict[str, Any], parts: dict[str, np.ndarray]) -> None:
    """Stages a track: its recordings and what it is. `parts` is channel -> stereo audio at
    48 kHz, each the whole track and its ringing-on."""
    bars = sum(section["bars"] for section in meta["sections"])
    frames = int(round(bars * meta["bar_frames"])) + int(round(meta["post_s"] * RATE))
    for channel, audio in parts.items():
        if channel not in forever.CHANNELS:
            raise ValueError("%r is not one of the channels" % channel)
        if audio.ndim != 2 or audio.shape[1] != 2 or len(audio) != frames:
            raise ValueError("The %s part of %s is %s, not %d stereo samples" % (channel, folder, audio.shape, frames))
    for section in meta["sections"]:
        if section["story"] not in forever.STORY:
            raise ValueError("%r is not a part of a story" % section["story"])
    if meta["role"] not in ROLES:
        raise ValueError("%r is not a kind of moment" % meta["role"])
    folder.mkdir(parents=True, exist_ok=True)
    for channel, audio in parts.items():
        scratch = folder / (channel + ".part")
        soundfile.write(str(scratch), np.clip(audio, -1.0, 1.0), RATE, format="FLAC", subtype="PCM_16")
        scratch.replace(folder / (channel + ".flac"))
    scratch = folder / "track.json.new"
    scratch.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    scratch.replace(folder / "track.json")


def read_track(folder: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    meta = json.loads((Path(folder) / "track.json").read_text(encoding="utf-8"))
    parts = {}
    for channel in forever.CHANNELS:
        path = Path(folder) / (channel + ".flac")
        if path.is_file():
            audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
            if rate != RATE:
                raise ValueError("%s is at %d Hz, not %d" % (path, rate, RATE))
            parts[channel] = audio
    return meta, parts


def staged(var: Path, style: str) -> list[Path]:
    """Every staged track of a style, in order."""
    return sorted(path.parent for path in stage_root(var, style).glob("*/*/track.json"))


def import_track(bucket: forever.Bucket, folder: Path) -> list[str]:
    """Cuts a staged track into the pieces of its story and puts them in a bucket, each going
    on into the next. Returns the ids of the pieces; none if the track is in the bucket already.

    The whole track gets one gain, which brings its loudest part (every channel playing) to a
    little over the bucket's usual level: so the story keeps its shape, quiet where it was
    written quiet. A channel that is silent in a part of the story has no part in that piece."""
    meta, parts = read_track(folder)
    source = "%s/%s/%s" % (meta["style"], meta["family"], meta["take"])
    if any(piece.get("source") == source for piece in bucket.pieces.values()):
        return []
    bar = float(meta["bar_frames"])
    edges, bars = [0], 0
    for section in meta["sections"]:
        bars += section["bars"]
        edges.append(int(round(bars * bar)))
    whole = edges[-1]
    mix = sum(audio[:whole] for audio in parts.values())
    loudest = max(analysis.loudness_lufs(mix[first:last], RATE) for first, last in zip(edges, edges[1:]))
    peak = max(analysis.peak(mix), 1e-6)
    gain = min(forever.PIECE_LEVEL + LIFT - loudest, -20.0 * float(np.log10(peak)) - 1.0) + float(meta.get("level_db", 0.0))
    ids: list[str] = []
    for index, (section, first, last) in enumerate(zip(meta["sections"], edges, edges[1:])):
        tail = min(int(forever.POST_S * RATE), min(len(audio) for audio in parts.values()) - last)
        cut = {(channel, 1): audio[first:last + tail] for channel, audio in parts.items()
               if float(np.max(np.abs(audio[first:last]))) > QUIET}
        if not cut:
            raise ValueError("Nothing plays in the %s of %s" % (section["story"], folder))
        seconds = (last - first) / RATE
        windows = max(int(np.ceil(seconds / forever.WINDOW_S)), 1)
        ids.append(bucket.add_piece(
            cut, title="%s (%s)" % (meta["title"], section["story"]), bar_frames=bar,
            bars=max(int(np.ceil(section["bars"] / windows)), 1), post=tail, tonic=section.get("tonic", meta["tonic"]),
            story=section["story"],
            moods=meta["moods"], role=meta["role"], serves=meta["serves"], follow=meta.get("follow") or {},
            floor=(meta.get("floor") or {}).get(section["story"], {}), track=source, after=ids[-1] if ids else "",
            gain_db=gain, source=source, credit=meta.get("credit", ""), family="%s/%s" % (meta["style"], meta["family"]),
            light=bool(meta.get("light"))))
    return ids
