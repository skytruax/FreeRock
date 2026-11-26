"""What was heard on an evening (tools/heard.py): how much of it was new, and heard for the first time."""
from __future__ import annotations

import datetime
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from freerock.playbook import PlayBook

REPO = Path(__file__).resolve().parents[2]
EVENING = datetime.datetime(2026, 11, 25, 15, 0)


def _tool():
    spec = importlib.util.spec_from_file_location("heard", REPO / "tools" / "heard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _song(var: Path, name: str, title: str, when: str | None, sounds: str = "") -> None:
    folder = var / "studio" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "track.json").write_text(json.dumps({"title": title}), encoding="utf-8")
    if when:
        (folder / "sheet.json").write_text(json.dumps({"about": {"sounds": sounds}, "history": [{"revision": 1, "when": when}]}), encoding="utf-8")


def _played(var: Path, track: str, *times: datetime.datetime) -> None:
    PlayBook(var / "plays.sqlite3")                       # the book's own table
    with sqlite3.connect(var / "plays.sqlite3") as db:
        for place, at in enumerate(times):
            db.execute("insert into parts (style, track, place, channel, tier, stretch, plays, last) values (?, ?, ?, 'lead', 1, 0, 1, ?)",
                       (track.split("/")[0], track, place, at.timestamp()))


def test_an_evening_is_read_by_songs_and_says_how_much_was_new_and_heard_for_the_first_time(tmp_path):
    tool = _tool()
    at = lambda hour, minute: datetime.datetime(2026, 11, 25, hour, minute)      # noqa: E731
    _song(tmp_path, "knight/old-road-1/1", "Old Road", None)
    _song(tmp_path, "knight/old-road-1/2", "Old Road", "2026-11-25T02:00:00")                 # a new take of an old song: the song is not new
    _song(tmp_path, "knight/bone-mill-1/1", "Bone Mill", "2026-11-25T01:00:00", "bones")
    _song(tmp_path, "warcraft/court-1/1", "Court", "2026-11-21T01:00:00")
    _played(tmp_path, "knight/old-road-1/1", datetime.datetime(2026, 11, 22, 20, 0), at(19, 0), at(19, 4))     # heard before, and again tonight
    _played(tmp_path, "knight/old-road-1/2", at(19, 2))
    _played(tmp_path, "knight/bone-mill-1/1", at(20, 0), at(20, 5), at(22, 0))                 # twice tonight, two hours apart
    _played(tmp_path, "warcraft/court-1/1", datetime.datetime(2026, 11, 24, 21, 0))            # not tonight
    found = tool.evening(tmp_path, EVENING, 15.0)
    assert found["songs"] == 2 and [each["song"] for each in found["hearings"]] == ["knight/old-road-1", "knight/bone-mill-1", "knight/bone-mill-1"]
    road, mill, again = found["hearings"]
    assert road["seconds"] == pytest.approx(240 + tool.TAIL) and not road["first time"] and not road["new"] and road["title"] == "Old Road"
    assert mill["seconds"] == pytest.approx(300 + tool.TAIL) and mill["first time"] and mill["new"] and mill["sounds"] == "bones"
    assert again["seconds"] == pytest.approx(tool.TAIL)
    assert found["first time"] == 1 and found["new"] == 1
    assert found["new share"] == pytest.approx((300 + 2 * tool.TAIL) / (540 + 3 * tool.TAIL))
    assert tool.evening(tmp_path, datetime.datetime(2026, 11, 20, 15, 0), 15.0)["hearings"] == []
