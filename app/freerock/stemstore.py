"""A copy of every phrase as an audio file anyone can open, with a table of what each one is.

The buckets keep their phrases as raw arrays, which is what the player wants. For listening to
them one at a time, laying them out in a music program, or studying what was asked for and what
came back, each phrase is also kept here as a FLAC file (the same samples, nothing lost) under
var/stems/, and one table, stems.csv, says what every file is: the style, the channel and how
hard it plays, the tempo and key, the length of its verse, build-up and chorus, how loud it is,
how it measured, how often it has been played, and the words it was asked for with.

A bucket also holds written pieces, each kept as its parts: one recording for each channel,
in stretches of under a minute. Every stretch of every part is here as well, in a folder for
its piece, with the piece's name and which stretch it is in the table.

The server adds each new phrase as it is made. `freerock stems` brings the whole folder up to
date from the buckets at any time, and can write it somewhere else.
"""
from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

import numpy as np
import soundfile

from . import forever

COLUMNS = ("file", "id", "style", "bucket", "channel", "strength", "bpm", "key", "bars", "verse_bars", "build_bars",
           "chorus_bars", "seconds", "loudness_lufs", "gain_db", "tuning_cents", "verse_tempo_off_percent",
           "chorus_tempo_off_percent", "times_played", "in_play", "loved", "banned", "made", "made_for", "seed",
           "source", "asked_for", "piece", "order", "title")
ABOUT = """FreeRock stems

Every file here is one phrase for one instrument: a verse, a build-up and a chorus, made to be
played with any other phrase of the same style (same tempo, same key, same lengths).

  <style>/<channel>-<strength>/<tempo>bpm-<key>-<id>.flac     16 bits, 48 kHz, stereo
  stems.csv                                                    one row for each file

Channels: texture (a drone), lead (a tune), rhythm, drums, bass. Strengths: calm, steady, hard.
The columns verse_bars, build_bars and chorus_bars say where the parts begin; a bar is
240 / bpm seconds. gain_db is what the player adds to bring the phrase to its channel's level.
asked_for is the words the phrase was asked for with, apart from the tempo, the key and the
words every phrase of its channel has in common. made_for is the place whose colours it has.

Phrases older than the form (shorter ones, 4 or 8 bars) are here too, marked by their bars.

Written pieces are here as their parts:

  <style>/pieces/<piece>/<channel>-<stretch>.flac

A piece is music written as a whole. Each channel that plays in it has a part, kept in
stretches of under a minute, numbered from 0 in the order they are played; the parts of a piece
are in step with each other, stretch for stretch. A piece keeps its own tempo and key, which
are the ones in its rows. A file holds its stretch and then up to six seconds of what the
music went on to (seconds is the stretch alone), which the player lets ring under whatever it
plays next. The columns piece, order and title say which piece a file belongs to, which
stretch it is and what the piece is called; made_for is the kinds of place the piece was
written for, and asked_for its place in a story, the kind of moment it is for and the track
it was cut from. All the parts of a piece share one gain_db, so they keep the balance they
were written with.
"""


def _name(bucket: forever.Bucket, clip: forever.Clip) -> Path:
    if clip.piece:
        # A stretch of a part of a written piece, in the piece's own folder. A part written at
        # the usual strength is named by its channel alone; the others say which they are.
        part = clip.channel if clip.tier == 1 else "%s-%s" % (clip.channel, forever.TIER_WORDS[clip.tier])
        return Path(bucket.genre) / "pieces" / clip.piece / ("%s-%d.flac" % (part, clip.order))
    key = bucket.tonic.replace(" ", "-").replace("#", "sharp")
    return Path(bucket.genre) / ("%s-%s" % (clip.channel, forever.TIER_WORDS[clip.tier])) / (
        "%dbpm-%s-%s.flac" % (bucket.bpm, key, clip.id))


def _tempo(bar_frames: float) -> int | float:
    """A piece's tempo in beats a minute, taking four beats to its bar: a whole number where it is one."""
    bpm = round(240.0 * forever.RATE / bar_frames, 2)
    return int(bpm) if bpm == int(bpm) else bpm


def _row(bucket: forever.Bucket, clip: forever.Clip) -> dict[str, object]:
    measured = clip.measured or {}
    piece = bucket.pieces.get(clip.piece) if clip.piece else None
    if clip.piece and piece is None:
        raise KeyError("The phrase %s says it is part of the piece %s, which the bucket %s does not have"
                       % (clip.id, clip.piece, bucket.key))
    whole = clip.bars == bucket.cycle and piece is None
    verse, build, chorus = forever.form(bucket.bpm) if whole else ("", "", "")
    row = {
        "file": _name(bucket, clip).as_posix(), "id": clip.id, "style": bucket.genre, "bucket": bucket.key,
        "channel": clip.channel, "strength": forever.TIER_WORDS[clip.tier], "bpm": bucket.bpm, "key": bucket.tonic,
        "bars": clip.bars, "verse_bars": verse, "build_bars": build, "chorus_bars": chorus,
        "seconds": round(clip.frames / forever.RATE, 3), "loudness_lufs": measured.get("lufs", ""),
        "gain_db": clip.gain_db, "tuning_cents": measured.get("tuning_cents", ""),
        "verse_tempo_off_percent": (measured.get("verse") or {}).get("tempo_off", measured.get("tempo_off", "")),
        "chorus_tempo_off_percent": (measured.get("chorus") or {}).get("tempo_off", ""),
        "times_played": clip.plays, "in_play": "yes" if whole and not clip.banned else "no",
        "loved": "yes" if clip.loved else "", "banned": "yes" if clip.banned else "",
        "made": datetime.datetime.fromtimestamp(clip.created).isoformat(timespec="seconds"),
        "made_for": clip.place, "seed": "" if clip.seed is None else clip.seed, "source": clip.source,
        "asked_for": "; ".join(clip.words), "piece": "", "order": "", "title": "",
    }
    if piece is not None:
        # A part of a written piece: the piece's own tempo and key, and what the piece is.
        about = [word for word in (piece.get("story"), "for " + piece["role"] if piece.get("role") else "",
                                   "track " + piece["track"] if piece.get("track") else "") if word]
        row.update({
            "bpm": _tempo(piece["bar_frames"]), "key": piece.get("tonic") or bucket.tonic,
            "in_play": "no" if piece.get("banned") or clip.banned else "yes",
            "loved": "yes" if piece.get("loved") or clip.loved else "",
            "banned": "yes" if piece.get("banned") or clip.banned else "",
            "made_for": ", ".join(piece.get("moods", [])), "asked_for": "; ".join(about),
            "piece": clip.piece, "order": clip.order, "title": piece["title"],
        })
    return row


class StemStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def keep(self, bucket: forever.Bucket, clip: forever.Clip) -> bool:
        """Writes one phrase as a FLAC file, if it is not here already. True if it was written."""
        path = self.root / _name(bucket, clip)
        if path.is_file():
            return False
        samples = bucket.audio(clip.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch = path.with_suffix(".part")
        soundfile.write(str(scratch), samples, forever.RATE, format="FLAC", subtype="PCM_16")
        scratch.replace(path)
        return True

    def add(self, bucket: forever.Bucket, clip: forever.Clip) -> None:
        """A phrase that has just been made: its file, and its row at the end of the table."""
        self.keep(bucket, clip)
        table = self.root / "stems.csv"
        fresh = not table.is_file()
        with table.open("a", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=COLUMNS)
            if fresh:
                writer.writeheader()
            writer.writerow(_row(bucket, clip))
        if fresh:
            (self.root / "README.txt").write_text(ABOUT, encoding="utf-8")

    def sync(self, buckets_root: Path) -> tuple[int, int]:
        """Brings the folder up to date with every bucket on disk: a file for every phrase that
        has none, and the table written afresh (how often each has been played changes).
        Returns (files written, phrases in all)."""
        buckets_root = Path(buckets_root)
        written, rows = 0, []
        for index in sorted(buckets_root.glob("*/*/bucket.json")):
            kept = json.loads(index.read_text(encoding="utf-8"))
            bucket = forever.Bucket(buckets_root, kept["zone"], kept["genre"], kept["bpm"], kept["tonic"])
            for clip in bucket.clips:
                written += self.keep(bucket, clip)
                rows.append(_row(bucket, clip))
        self.root.mkdir(parents=True, exist_ok=True)
        scratch = self.root / "stems.csv.new"
        with scratch.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        scratch.replace(self.root / "stems.csv")
        (self.root / "README.txt").write_text(ABOUT, encoding="utf-8")
        return written, len(rows)
