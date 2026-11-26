"""The written pieces a style has: putting staged tracks in its bucket, and saying what is there.

A style has one bucket, and its written music lives in it (see forever.Bucket.add_piece).
Pieces are tracks written and played in the studio, which are staged under var/studio and put in
the bucket from there. `freerock pieces` puts them in, lists what a
style has, and takes pieces out again.

A bucket is written here while the server is stopped: the server keeps each bucket's list in
memory and writes it back as pieces are played, so two programs writing one bucket would lose
one another's work. A whole bucket is built again beside the one that plays, with the server
running, and put in its place in the seconds the server is stopped for (`build_beside`, `swap`).
"""
from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path
from typing import Any

import soundfile

from . import composer, forever, studio
from .playbook import PlayBook


def server_is_up(port: int, host: str = "127.0.0.1") -> bool:
    """Whether something is listening where the FreeRock server listens."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except ConnectionRefusedError:
        return False
    except socket.timeout:
        # (2026-11-26, the audit: a server that does not answer in half a second was read as no server, and a bucket could be swapped under one that
        # was only slow or hung, which has the buckets in memory.) Something holds the port or is too busy to say: it is up.
        return True


def home_bucket(var_dir: Path, style: str, zone: str | None = None) -> forever.Bucket:
    """The one bucket a style plays from: the one it has, or a new one (named "all", at the tempo
    and key of `zone`) if it has none yet."""
    if style not in composer.GENRES:
        raise ValueError("%r is not a style; the styles are %s" % (style, ", ".join(composer.GENRES)))
    bucket = forever.Buckets(Path(var_dir) / "buckets").home(style, zone)
    if bucket is None:
        raise ValueError("The %s style has no bucket yet. Say which place's tempo and key to begin one at: --zone \"Duskwood\""
                         % composer.GENRES[style]["label"])
    return bucket


def standing(var_dir: Path, style: str) -> forever.Bucket:
    """The bucket a style plays from as it is on disk (the one `Buckets.home` would choose), to be read and not written: the
    server, if it runs, has it in memory and writes it."""
    root, best = Path(var_dir) / "buckets", None
    for index in sorted((root / style).glob("*/bucket.json")):
        kept = json.loads(index.read_text(encoding="utf-8"))
        bucket = forever.Bucket(root, index.parent.name, style, kept["bpm"], kept["tonic"])
        if bucket.live() and (best is None or len(bucket.live()) > len(best.live())):
            best = bucket
    if best is None:
        raise ValueError("The %s style has no bucket to build again" % style)
    return best


def build_beside(var_dir: Path, style: str) -> tuple[forever.Bucket, dict[str, Any]]:
    """Builds a style's bucket again from what is staged, beside the one that plays (`swap` puts it in its place), so that the
    server runs on meanwhile. Returns it, and what was done: how many songs are in (`put`), how many of those were taken
    from the bucket as it stands (`taken`) and which could not be put in (`wrong`), how many parts kept their plays, loves
    and bans (`carried`), and how many had any (`marks`).

    (2026-11-23, "fix the builder": a build had the server down from its beginning to its end, half an hour to two hours
    for a band's or the orchestra's bucket, and a player that cannot reach the server for a minute fades out.)"""
    old = standing(var_dir, style)
    root = forever.beside(old.root, forever.NEXT)
    for left in (root / style, forever.beside(old.root, forever.BEFORE) / style):      # a build that did not end, and the bucket before last
        if left.exists():
            shutil.rmtree(left)
    bucket = forever.Bucket(root, old.zone, style, old.bpm, old.tonic, book=PlayBook(Path(var_dir) / "plays.sqlite3"))
    bucket.version = old.version
    before, put, taken, wrong = studio.Before(old), 0, 0, []
    with bucket.saved_once():
        for folder, made, problem in add_staged(bucket, var_dir, style, before):
            if problem:
                wrong.append((folder, problem))
            elif made:
                put += 1
                taken += made[0] in bucket.linked
        marks = marks_of(old)
    carried = restore_marks(bucket, marks)
    carried += bucket.sync_book()                 # and what the play book has kept: what is played while this is built is there
    return bucket, {"put": put, "taken": taken, "wrong": wrong, "carried": carried, "marks": len(marks)}


def swap(var_dir: Path, style: str) -> Path:
    """Puts the bucket `build_beside` made in the place of the one that plays, which is kept (`forever.BEFORE`) until the next
    build: what is left of a song begun before is found there, and `swap_back` puts it back. The server must be stopped.
    Returns where the old one is kept."""
    here = standing(var_dir, style).folder.resolve()
    ready = forever.beside(Path(var_dir) / "buckets", forever.NEXT) / style / here.name
    if not (ready / "bucket.json").is_file() or not json.loads((ready / "bucket.json").read_text(encoding="utf-8"))["pieces"]:
        raise ValueError("No bucket for %s has been built beside the one that plays (%s)" % (style, ready))
    kept = forever.beside(Path(var_dir) / "buckets", forever.BEFORE) / style / here.name
    if kept.exists():
        shutil.rmtree(kept)
    kept.parent.mkdir(parents=True, exist_ok=True)
    here.rename(kept)
    try:
        ready.rename(here)
    except OSError:
        kept.rename(here)
        raise
    return kept


def swap_back(var_dir: Path, style: str) -> Path:
    """Puts the bucket as it was before the last `swap` back in its place, and the one that was swapped in back beside it
    (`forever.NEXT`). The server must be stopped. Returns where that one is now."""
    here = standing(var_dir, style).folder.resolve()
    kept = forever.beside(Path(var_dir) / "buckets", forever.BEFORE) / style / here.name
    ready = forever.beside(Path(var_dir) / "buckets", forever.NEXT) / style / here.name
    if not (kept / "bucket.json").is_file():
        raise ValueError("No bucket for %s is kept from before (%s)" % (style, kept))
    ready.parent.mkdir(parents=True, exist_ok=True)
    here.rename(ready)
    kept.rename(here)
    return ready


def resting(var_dir: Path, style: str) -> dict[str, str]:
    """The staged songs of a style that are kept out of its bucket for now, each ("family/take") with why: a line each in
    var/studio/<style>/resting.txt. They stay staged, and on the listening pages; a line taken out of the list brings its song
    back at the next build. (2026-11-24: House was heard as sweet still, with 41 dark songs among 102 light ones.)"""
    path = studio.stage_root(Path(var_dir), style) / "resting.txt"
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else ():
        if not line.strip() or line.startswith("#"):
            continue
        name, _, why = line.strip().partition(" ")
        if name.count("/") != 1:
            raise ValueError("%s: a song is said as its family and take (meadow-01/2), not %r" % (path, name))
        out[name] = why.strip()
    return out


def add_staged(bucket: forever.Bucket, var_dir: Path, style: str, before: studio.Before | None = None) -> list[tuple[Path, list[str], str]]:
    """Puts every staged track of a style in its bucket, but for those that are resting (`resting`). For each track, in order:
    its folder, the ids of the pieces it became (none if it was in the bucket already), and what was wrong with it if it could
    not be put in (the others still are)."""
    done = []
    rest = resting(var_dir, style)
    for folder in studio.staged(Path(var_dir), style):
        if "%s/%s" % (folder.parent.name, folder.name) in rest:
            continue
        try:
            done.append((folder, studio.import_track(bucket, folder, before), ""))
        except (ValueError, KeyError, OSError, soundfile.SoundFileError) as problem:
            # A track that is not fit to be put in (a recording of the wrong length or rate, a
            # file that cannot be read, a description with something missing) is reported by
            # name and the rest go in: one bad track among hundreds is no reason to leave the
            # bucket empty. The caller says so and ends with an error.
            done.append((folder, [], "%s: %s" % (type(problem).__name__, problem)))
    return done


def drop_from(bucket: forever.Bucket, source: str) -> int:
    """Takes out of a bucket, for good, every piece whose source begins with `source` (the
    studio's tracks are "<style>/<family>/<take>"). The staged tracks are left where they are,
    so the pieces can be put back. Returns how many pieces went."""
    if not source:
        raise ValueError("Say which pieces: an empty source would take every one")
    mine = [piece_id for piece_id, piece in bucket.pieces.items() if str(piece.get("source", "")).startswith(source)]
    for piece_id in mine:
        bucket.drop_piece(piece_id)
    return len(mine)


def _places(bucket: forever.Bucket) -> dict[str, tuple[str, int]]:
    """Each written piece's track and its place in it (`forever.Bucket.places`)."""
    return bucket.places()


def marks_of(bucket: forever.Bucket) -> dict[tuple, tuple[int, bool, bool]]:
    """What has been done with each written part, by where it sits: (its track, its piece's place in the track, its
    channel, the strength it was written at, its stretch) -> (plays, loved, banned). A track put into a bucket again is
    cut the same way, so its parts can take back what was theirs (`restore_marks`). (2026-11-18: "make sure whats played
    is marked as played": a whole build had begun every part again at no plays, so the player took them all for new, and
    it would have forgotten a love or a ban.)"""
    places = _places(bucket)
    out: dict[tuple, tuple[int, bool, bool]] = {}
    for clip in bucket.clips:
        place = places.get(clip.piece)
        if place and (clip.plays or clip.loved or clip.banned):
            out[place + (clip.channel, clip.tier, clip.order)] = (clip.plays, clip.loved, clip.banned)
    return out


def restore_marks(bucket: forever.Bucket, marks: dict[tuple, tuple[int, bool, bool]]) -> int:
    """Gives the parts at the same places what `marks_of` kept; returns how many took something back."""
    places = _places(bucket)
    found = 0
    for clip in bucket.clips:
        place = places.get(clip.piece)
        kept = marks.get(place + (clip.channel, clip.tier, clip.order)) if place else None
        if kept:
            clip.plays, clip.loved, clip.banned = kept
            found += 1
    if found:
        bucket._save()
    return found


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
    parts = bucket.live()
    return {"pieces": len(pieces), "tracks": len({piece["track"] or piece_id for piece_id, piece in pieces.items()}),
            "minutes": minutes, "parts": len(parts), "by_role": by_role, "by_kind": by_kind, "light": light, "heavy": heavy,
            "banned": len(bucket.pieces) - len(pieces),
            "families": len({piece["family"] for piece in pieces.values() if piece.get("family")})}
