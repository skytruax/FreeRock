"""A copy of every phrase as an audio file anyone can open, with a table of what each one is.

The buckets keep their phrases as raw arrays, which is what the player wants. For listening to
them one at a time, laying them out in a music program, or studying what was asked for and what
came back, each phrase is also kept here as a FLAC file (the same samples, nothing lost) under
var/stems/, and one table, stems.csv, says what every file is: the style, the channel and how
hard it plays, the tempo and key, the length of its verse, build-up and chorus, how loud it is,
how it measured, how often it has been played, and the words it was asked for with.

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
           "source", "asked_for")
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
"""


def _name(bucket: forever.Bucket, clip: forever.Clip) -> Path:
    key = bucket.tonic.replace(" ", "-").replace("#", "sharp")
    return Path(bucket.genre) / ("%s-%s" % (clip.channel, forever.TIER_WORDS[clip.tier])) / (
        "%dbpm-%s-%s.flac" % (bucket.bpm, key, clip.id))


def _row(bucket: forever.Bucket, clip: forever.Clip) -> dict[str, object]:
    measured = clip.measured or {}
    whole = clip.bars == bucket.cycle
    verse, build, chorus = forever.form(bucket.bpm) if whole else ("", "", "")
    return {
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
        "asked_for": "; ".join(clip.words),
    }


class StemStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def keep(self, bucket: forever.Bucket, clip: forever.Clip) -> bool:
        """Writes one phrase as a FLAC file, if it is not here already. True if it was written."""
        path = self.root / _name(bucket, clip)
        if path.is_file():
            return False
        samples = np.load(bucket.folder / "clips" / (clip.id + ".npy"))
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
