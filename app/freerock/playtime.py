"""How long the game has been played with FreeRock on: this month, and in each place.

Two things lean on this. New music for a place is added as time is spent there (a second set
after a while, fresh sets every couple of hours), and the minutes that go on such music are paced
by the hours played, so a month's allowance lasts the month.

It is one small file, var/playtime.json, written every half minute of play and when the server
stops.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SAVE_EVERY_S = 30.0


def month_of(moment: float) -> str:
    return time.strftime("%Y-%m", time.localtime(moment))


class Playtime:
    def __init__(self, path: Path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self._unsaved = 0.0
        self.data: dict[str, Any] = {"month": month_of(clock()), "month_seconds": 0.0,
                                     "growth_minutes": 0.0, "places": {}, "since_set": {}}
        if self.path.is_file():
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.update({name: stored[name] for name in self.data if name in stored})
        self._roll_over()

    def _roll_over(self) -> None:
        """A new calendar month starts the month's own counts again. Time spent in each place is
        not reset: it is what says where the music should grow."""
        now = month_of(self.clock())
        if self.data["month"] != now:
            self.data.update(month=now, month_seconds=0.0, growth_minutes=0.0)

    # --- counting ----------------------------------------------------------------------------------

    def add(self, place: str | None, seconds: float) -> None:
        """Counts `seconds` of play, in `place` if it is known."""
        if seconds <= 0:
            return
        self._roll_over()
        self.data["month_seconds"] += seconds
        if place:
            self.data["places"][place] = self.data["places"].get(place, 0.0) + seconds
            self.data["since_set"][place] = self.data["since_set"].get(place, 0.0) + seconds
        self._unsaved += seconds
        if self._unsaved >= SAVE_EVERY_S:
            self.save()

    def set_made(self, place: str, minutes: float) -> None:
        """A set was added to a place's music: the wait for its next one starts again, and the
        minutes count towards the month's growth."""
        self._roll_over()
        self.data["since_set"][place] = 0.0
        self.data["growth_minutes"] += minutes
        self.save()

    # --- reading -----------------------------------------------------------------------------------

    def month_hours(self) -> float:
        self._roll_over()
        return self.data["month_seconds"] / 3600.0

    def growth_minutes(self) -> float:
        self._roll_over()
        return float(self.data["growth_minutes"])

    def place_seconds(self, place: str) -> float:
        return float(self.data["places"].get(place, 0.0))

    def since_set(self, place: str) -> float:
        return float(self.data["since_set"].get(place, 0.0))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        self._unsaved = 0.0
