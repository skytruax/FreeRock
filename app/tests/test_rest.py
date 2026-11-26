"""Resting songs and bringing them back (tools/rest.py): the lines the bucket's builder reads (pieces.resting)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from freerock import pieces

REPO = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("rest", REPO / "tools" / "rest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _take(var: Path, name: str, when: str | None) -> None:
    folder = var / "studio" / "knight" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "track.json").write_text("{}", encoding="utf-8")
    if when is not None:
        (folder / "sheet.json").write_text(json.dumps({"history": [{"revision": 1, "when": when}, {"revision": 2, "when": "2026-11-26T03:00:00"}]}), encoding="utf-8")


def test_the_songs_begun_since_a_time_are_the_new_families_and_not_new_takes_of_older_ones(tmp_path):
    tool = _tool()
    _take(tmp_path, "old-road-1/1", None)                           # from before there were sheets
    _take(tmp_path, "old-road-1/2", "2026-11-25T02:00:00")          # a new take of it
    _take(tmp_path, "mill-song-1/1", "2026-11-23T21:00:00")
    _take(tmp_path, "mill-song-1/2", "2026-11-25T03:00:00")         # a new take of an older family
    _take(tmp_path, "bone-mill-1/1", "2026-11-25T01:00:00")
    _take(tmp_path, "bone-mill-1/2", "2026-11-26T01:00:00")
    assert tool.begun_since(tmp_path, "knight", "2026-11-24T08:40") == ["bone-mill-1/1", "bone-mill-1/2"]


def test_a_rested_song_is_left_out_by_the_builder_and_comes_back_by_its_tag(tmp_path):
    tool = _tool()
    path = tool.path_of(tmp_path, "knight")
    path.parent.mkdir(parents=True)
    path.write_text(tool.HEAD + "storm-09/2 2026-11-24: until it is made again\n", encoding="utf-8")
    assert tool.rest(tmp_path, "knight", ["bone-mill-1/1", "bone-mill-1/2", "storm-09/2"], "audit-1126", "came in after the last evening that was liked") \
        == ["bone-mill-1/1", "bone-mill-1/2"]
    assert tool.rest(tmp_path, "knight", ["bone-mill-1/1"], "audit-1126", "again") == []            # once only
    resting = pieces.resting(tmp_path, "knight")
    assert set(resting) == {"storm-09/2", "bone-mill-1/1", "bone-mill-1/2"}
    assert resting["bone-mill-1/1"] == "[audit-1126] came in after the last evening that was liked"
    assert tool.back(tmp_path, "knight", "audit-1126", ["bone-mill-1/2"]) == ["bone-mill-1/2"]
    assert set(pieces.resting(tmp_path, "knight")) == {"storm-09/2", "bone-mill-1/1"}
    assert tool.back(tmp_path, "knight", "audit-1126") == ["bone-mill-1/1"]
    assert pieces.resting(tmp_path, "knight") == {"storm-09/2": "2026-11-24: until it is made again"}  # what was resting before stays
    assert path.read_text(encoding="utf-8").startswith("#")


def test_a_tag_is_one_word_and_a_song_a_family_and_a_take(tmp_path):
    tool = _tool()
    with pytest.raises(ValueError):
        tool.rest(tmp_path, "knight", ["bone-mill-1/1"], "two words", "why")
    with pytest.raises(ValueError):
        tool.rest(tmp_path, "knight", ["bone-mill-1"], "audit", "why")


def _bucket(var: Path, *sources: str) -> None:
    folder = var / "buckets" / "knight" / "all"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "bucket.json").write_text(json.dumps({"pieces": {"p%d" % number: {"source": "knight/" + source} for number, source in enumerate(sources)}}), encoding="utf-8")


def test_every_staged_take_the_player_does_not_have_is_new_a_further_take_of_a_song_it_has_too(tmp_path):
    """(2026-11-26: a night's new songs were the next evening, none of them judged. A build rests what is new to the player first: a new family's
    take and a further take of an older family alike, since that too is written and mixed as the writer and the desk are that night.)"""
    tool = _tool()
    for name in ("old-road-1/1", "old-road-1/2", "bone-mill-1/1", "bone-mill-1/2", "salt-pan-1/1", "night-fair-1/1"):
        _take(tmp_path, name, "2026-11-26T01:00:00")
    with pytest.raises(ValueError):
        tool.new_songs(tmp_path, "knight")                                     # no bucket: nothing to tell a new song from
    _bucket(tmp_path, "old-road-1/1", "night-fair-1/1")
    tool.rest(tmp_path, "knight", ["bone-mill-1/1"], "audit-1126", "resting")
    # old-road-1/2 is a further take of a song the player has; bone-mill-1/2 a further take of one that rests; salt-pan is a new family's: all three are new.
    assert tool.new_songs(tmp_path, "knight") == ["bone-mill-1/2", "old-road-1/2", "salt-pan-1/1"]
    assert tool.rest(tmp_path, "knight", tool.new_songs(tmp_path, "knight"), "new-1127", "new") == ["bone-mill-1/2", "old-road-1/2", "salt-pan-1/1"]
    assert tool.new_songs(tmp_path, "knight") == []
    # What is brought back (it passed the gate) is let in, and is not rested again by the next build's look, though the bucket has not got it yet.
    assert tool.back(tmp_path, "knight", "new-1127", ["salt-pan-1/1", "old-road-1/2"]) == ["old-road-1/2", "salt-pan-1/1"]
    assert tool.new_songs(tmp_path, "knight") == []
    resting = pieces.resting(tmp_path, "knight")
    assert "salt-pan-1/1" not in resting and "old-road-1/2" not in resting and "bone-mill-1/2" in resting and "bone-mill-1/1" in resting
    assert (tmp_path / "studio" / "knight" / "admitted.txt").read_text(encoding="utf-8").splitlines()[-2:] == ["old-road-1/2 [new-1127]", "salt-pan-1/1 [new-1127]"]



def test_resting_songs_move_to_another_tag_and_are_brought_back_and_read_by_it(tmp_path):
    """(2026-11-26: the takes told another way each time rested under the same tag as every other new song, and the morning's "bring back what
    passed" went by that tag: one of them the judges passed would have come back. They rest under a word of their own until written again.)"""
    tool = _tool()
    for name, when in (("bone-mill-1/1", "2026-11-25T01:00:00"), ("bone-mill-1/2", "2026-11-25T01:30:00"), ("salt-pan-1/1", "2026-11-25T02:00:00"), ("old-road-1/1", None)):
        _take(tmp_path, name, when)
    tool.rest(tmp_path, "knight", ["bone-mill-1/1", "bone-mill-1/2", "salt-pan-1/1", "old-road-1/1"], "audit-1126", "new since the evening that was liked")
    assert tool.retag(tmp_path, "knight", "audit-1126", "retold-1126", ["bone-mill-1/1", "bone-mill-1/2", "night-fair-1/1"], why="told another way each time") == ["bone-mill-1/1", "bone-mill-1/2"]
    lines = tool.lines_of(tool.path_of(tmp_path, "knight"))
    assert "bone-mill-1/1 [retold-1126] told another way each time" in lines and "salt-pan-1/1 [audit-1126] new since the evening that was liked" in lines
    assert set(pieces.resting(tmp_path, "knight")) == {"bone-mill-1/1", "bone-mill-1/2", "salt-pan-1/1", "old-road-1/1"}  # (they all rest still)
    assert tool.back(tmp_path, "knight", "audit-1126", ["bone-mill-1/1", "salt-pan-1/1"]) == ["salt-pan-1/1"]             # not by the other tag
    # Written again since (its sheet's first draft is of this afternoon): it moves back to the tag the judges read, the reason kept where none is given.
    _take(tmp_path, "bone-mill-1/1", "2026-11-26T14:30:00")
    assert tool.retag(tmp_path, "knight", "retold-1126", "audit-1126", since="2026-11-26T14:11") == ["bone-mill-1/1"]
    lines = tool.lines_of(tool.path_of(tmp_path, "knight"))
    assert "bone-mill-1/1 [audit-1126] told another way each time" in lines and "bone-mill-1/2 [retold-1126] told another way each time" in lines
    assert tool.retag(tmp_path, "knight", "audit-1126", "kept-1126", ["old-road-1/1"], since="2026-11-26T14:11") == []     # no sheet: not written since
    assert tool.retag(tmp_path, "knight", "nothing-here", "audit-1126") == []
    with pytest.raises(ValueError, match="one word"):
        tool.retag(tmp_path, "knight", "audit-1126", "two words")
