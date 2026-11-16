"""The written pieces a style has: putting staged tracks in its bucket, and saying what is there.

A style has one bucket, and its written music lives in it beside its loose phrases (see
forever.Bucket.add_piece). Pieces come from two places: the songs on disk, cut up by songstems,
and tracks written and played in the studio, which are staged under var/studio and put in the
bucket from there. `freerock pieces` does both, and lists what a style has.

A bucket is written here while the server is stopped: the server keeps each bucket's list in
memory and writes it back as phrases are played, so two programs writing one bucket would lose
one another's work.
"""
from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import soundfile

from . import composer, forever, studio


def server_is_up(port: int, host: str = "127.0.0.1") -> bool:
    """Whether something is listening where the FreeRock server listens."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (ConnectionRefusedError, socket.timeout):
        return False


def home_bucket(var_dir: Path, style: str, zone: str | None = None) -> forever.Bucket:
    """The one bucket a style plays from: the one it has, or a new one begun in `zone` (whose
    tempo and key its loose phrases will have) if it has none yet."""
    if style not in composer.GENRES:
        raise ValueError("%r is not a style; the styles are %s" % (style, ", ".join(composer.GENRES)))
    bucket = forever.Buckets(Path(var_dir) / "buckets").home(style, zone)
    if bucket is None:
        raise ValueError("The %s style has no bucket yet. Say where to begin one: --zone \"Duskwood\""
                         % composer.GENRES[style]["label"])
    return bucket


def add_staged(bucket: forever.Bucket, var_dir: Path, style: str) -> list[tuple[Path, list[str], str]]:
    """Puts every staged track of a style in its bucket. For each track, in order: its folder,
    the ids of the pieces it became (none if it was in the bucket already), and what was wrong
    with it if it could not be put in (the others still are)."""
    done = []
    for folder in studio.staged(Path(var_dir), style):
        try:
            done.append((folder, studio.import_track(bucket, folder), ""))
        except (ValueError, KeyError, OSError, soundfile.SoundFileError) as problem:
            # A track that is not fit to be put in (a recording of the wrong length or rate, a
            # file that cannot be read, a description with something missing) is reported by
            # name and the rest go in: one bad track among hundreds is no reason to leave the
            # bucket empty. The caller says so and ends with an error.
            done.append((folder, [], "%s: %s" % (type(problem).__name__, problem)))
    return done


def summary(bucket: forever.Bucket) -> dict[str, Any]:
    """What written pieces a bucket has in play: how many, in how many tracks, how long, and
    how they divide by the kind of moment, the kind of place, and light and heavy."""
    pieces = bucket.live_pieces()
    by_role: dict[str, list[float]] = {}
    by_kind: dict[str, list[float]] = {}
    light = heavy = 0
    minutes = 0.0
    for piece in pieces.values():
        length = piece["frames"] / forever.RATE / 60.0
        minutes += length
        role = by_role.setdefault(piece["role"], [0, 0.0])
        role[0] += 1
        role[1] += length
        for mood in piece["moods"] or ["any"]:
            kind = by_kind.setdefault(mood, [0, 0.0])
            kind[0] += 1
            kind[1] += length
        if piece.get("light"):
            light += 1
        else:
            heavy += 1
    parts = [clip for clip in bucket.live() if clip.piece]
    return {"pieces": len(pieces), "tracks": len({piece["track"] or piece_id for piece_id, piece in pieces.items()}),
            "minutes": minutes, "parts": len(parts), "by_role": by_role, "by_kind": by_kind, "light": light, "heavy": heavy,
            "banned": len(bucket.pieces) - len(pieces), "loose": sum(1 for clip in bucket.live() if not clip.piece),
            "families": len({piece["family"] for piece in pieces.values() if piece.get("family")})}
