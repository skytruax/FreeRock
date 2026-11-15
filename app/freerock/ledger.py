"""The spend ledger: one row for every call that can cost ElevenLabs credits.

A row is written before the request goes out, with the minutes it will cost, so the allowance is
counted even if FreeRock dies in the middle of a download. The row is then closed as done or
failed. A call that ElevenLabs turned down before making any audio costs nothing and its minutes
are set back to zero.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    REAL    NOT NULL,   -- seconds since 1970
    kind          TEXT    NOT NULL,   -- music | sfx | stems
    purpose       TEXT    NOT NULL,   -- what it was for, in words
    zone          TEXT,               -- which zone it was for, if any
    model         TEXT,
    minutes       REAL    NOT NULL,   -- minutes counted against the allowance
    status        TEXT    NOT NULL,   -- started | done | failed | refused
    http_status   INTEGER,
    error         TEXT,
    song_id       TEXT,
    bytes         INTEGER,
    first_audio_s REAL,               -- seconds until the first audio arrived
    total_s       REAL,               -- seconds until the last audio arrived
    request       TEXT                -- the request as JSON; never holds the key
);
CREATE INDEX IF NOT EXISTS calls_started_at ON calls (started_at);
"""


def month_start(now: float) -> float:
    """The first instant of the calendar month `now` falls in, local time."""
    moment = datetime.fromtimestamp(now)
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()


def day_start(now: float) -> float:
    moment = datetime.fromtimestamp(now)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


class Ledger:
    def __init__(self, path: Path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    # --- what has been spent -------------------------------------------------------------------

    def minutes_since(self, since: float) -> float:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT COALESCE(SUM(minutes), 0) FROM calls WHERE started_at >= ?", (since,)
            ).fetchone()
        return float(row[0])

    def month_minutes(self) -> float:
        return self.minutes_since(month_start(self.clock()))

    def day_minutes(self) -> float:
        return self.minutes_since(day_start(self.clock()))

    # --- writing rows --------------------------------------------------------------------------

    def start(self, *, kind: str, purpose: str, minutes: float, zone: str | None = None,
              model: str | None = None, request: Any = None) -> int:
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO calls (started_at, kind, purpose, zone, model, minutes, status, request)"
                " VALUES (?, ?, ?, ?, ?, ?, 'started', ?)",
                (self.clock(), kind, purpose, zone, model, float(minutes),
                 None if request is None else json.dumps(request, sort_keys=True)),
            )
            return int(cursor.lastrowid)

    def finish(self, call_id: int, *, http_status: int | None = None, song_id: str | None = None,
               nbytes: int | None = None, first_audio_s: float | None = None,
               total_s: float | None = None) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE calls SET status = 'done', http_status = ?, song_id = ?, bytes = ?,"
                " first_audio_s = ?, total_s = ? WHERE id = ?",
                (http_status, song_id, nbytes, first_audio_s, total_s, call_id),
            )

    def fail(self, call_id: int, *, error: str, keep_minutes: bool, http_status: int | None = None,
             nbytes: int | None = None, first_audio_s: float | None = None,
             total_s: float | None = None) -> None:
        """Closes a row as failed. `keep_minutes` is False only when no audio was made at all."""
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE calls SET status = 'failed', http_status = ?, error = ?, bytes = ?,"
                " first_audio_s = ?, total_s = ?,"
                " minutes = CASE WHEN ? THEN minutes ELSE 0 END WHERE id = ?",
                (http_status, error, nbytes, first_audio_s, total_s, 1 if keep_minutes else 0, call_id),
            )

    def refused(self, *, kind: str, purpose: str, minutes: float, error: str,
                zone: str | None = None) -> int:
        """Notes a call FreeRock itself refused to make because it would pass the allowance."""
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO calls (started_at, kind, purpose, zone, minutes, status, error)"
                " VALUES (?, ?, ?, ?, 0, 'refused', ?)",
                (self.clock(), kind, purpose, zone, "%s (asked for %.2f min)" % (error, minutes)),
            )
            return int(cursor.lastrowid)

    # --- reading rows --------------------------------------------------------------------------

    def rows(self, limit: int = 200) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            found = db.execute("SELECT * FROM calls ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in found]

    def by_purpose(self, since: float) -> list[tuple[str, float, int]]:
        """(purpose, minutes, calls) for rows that cost something since `since`, largest first."""
        with closing(self._connect()) as db:
            found = db.execute(
                "SELECT purpose, SUM(minutes), COUNT(*) FROM calls WHERE started_at >= ? AND minutes > 0"
                " GROUP BY purpose ORDER BY SUM(minutes) DESC", (since,)
            ).fetchall()
        return [(row[0], float(row[1]), int(row[2])) for row in found]
