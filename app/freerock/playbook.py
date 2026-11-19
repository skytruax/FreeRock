"""What has been played, loved and banned, kept apart from the buckets ("make a db so nightly bucket builds dont reset
our playlist", 2026-11-18).

A style's bucket is built again often: its written pieces are taken out and put in afresh, each part with a new id and
no plays, so the player took them all for new and a love or a ban was forgotten. This book keeps, for every written
part, by where it sits (its track, its piece's place in the track, its channel, the strength it was written at, its
stretch), how often it has been played, when it was last, and whether its piece is loved or banned. A part put in
again at the same place takes it all back (`forever.Bucket.sync_book`). It lives beside the buckets, as
var/plays.sqlite3.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

Key = tuple[str, int, str, int, int]           # track, the piece's place in it, channel, tier, stretch
Marks = dict[Key, tuple[int, bool, bool]]      # -> plays, loved, banned

SCHEMA = """
create table if not exists parts (
    style   text    not null,
    track   text    not null,
    place   integer not null,
    channel text    not null,
    tier    integer not null,
    stretch integer not null,
    plays   integer not null default 0,
    last    real,
    loved   integer not null default 0,
    banned  integer not null default 0,
    primary key (style, track, place, channel, tier, stretch)
)
"""


class PlayBook:
    """The book of what has been heard, one row for each written part that has been played, loved or banned."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._open() as db:
            db.execute(SCHEMA)

    def _open(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=30.0)
        db.execute("pragma journal_mode=wal")
        return db

    def played(self, style: str, keys: list[Key]) -> None:
        """One more play for each of these parts, now."""
        if not keys:
            return
        now = time.time()
        with self._open() as db:
            db.executemany("insert or ignore into parts (style, track, place, channel, tier, stretch) values (?, ?, ?, ?, ?, ?)",
                           [(style,) + tuple(key) for key in keys])
            db.executemany("update parts set plays = plays + 1, last = ? where style = ? and track = ? and place = ? and channel = ? "
                           "and tier = ? and stretch = ?", [(now, style) + tuple(key) for key in keys])

    def mark(self, style: str, keys: list[Key], *, loved: bool | None = None, banned: bool | None = None) -> None:
        """A love or a ban for these parts (or either taken back)."""
        if not keys or (loved is None and banned is None):
            return
        with self._open() as db:
            db.executemany("insert or ignore into parts (style, track, place, channel, tier, stretch) values (?, ?, ?, ?, ?, ?)",
                           [(style,) + tuple(key) for key in keys])
            for name, value in (("loved", loved), ("banned", banned)):
                if value is not None:
                    db.executemany("update parts set %s = ? where style = ? and track = ? and place = ? and channel = ? and tier = ? "
                                   "and stretch = ?" % name, [(int(value), style) + tuple(key) for key in keys])

    def remember(self, style: str, marks: Marks) -> None:
        """Takes in what a bucket says of its parts: the most plays either has, and its love and ban."""
        if not marks:
            return
        with self._open() as db:
            db.executemany("insert or ignore into parts (style, track, place, channel, tier, stretch) values (?, ?, ?, ?, ?, ?)",
                           [(style,) + tuple(key) for key in marks])
            db.executemany("update parts set plays = max(plays, ?), loved = (loved or ?), banned = (banned or ?) where style = ? "
                           "and track = ? and place = ? and channel = ? and tier = ? and stretch = ?",
                           [(plays, int(loved), int(banned), style) + tuple(key) for key, (plays, loved, banned) in marks.items()])

    def marks(self, style: str) -> Marks:
        """Everything the book has for a style."""
        with self._open() as db:
            rows = db.execute("select track, place, channel, tier, stretch, plays, loved, banned from parts where style = ?",
                              (style,)).fetchall()
        return {(track, place, channel, tier, stretch): (plays, bool(loved), bool(banned))
                for track, place, channel, tier, stretch, plays, loved, banned in rows}
