"""The study's count of a tune coming back (tools/study.py): held to the liked library from below, not read as a fault from above."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("study", REPO / "tools" / "study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bars(*marks: str) -> dict[int, set]:
    """A tune by its bars: each letter a bar's notes ("." a bar of rest)."""
    return {bar: {(0, ord(mark)), (6, ord(mark) + 2)} for bar, mark in enumerate("".join(marks)) if mark != "."}


def test_a_tune_that_comes_back_counts_and_one_told_another_way_each_time_does_not():
    tool = _tool()
    assert tool.returns(_bars("abcd", "abcd", "efgh", "abcd")) == pytest.approx(6 / 8)      # the theme three times, a second one once
    assert tool.returns(_bars("abcd", "abxd", "aycd", "zbcd")) == pytest.approx(5 / 8)      # told another way each time: less of it is known again
    assert tool.returns(_bars("abcd", "xbcd", "ayzd", "wvut")) == pytest.approx(2 / 8)
    assert tool.returns(_bars("abcd", "efgh", "ijkl")) == 0.0
    assert tool.returns(_bars("ab..", "..ab")) == pytest.approx(1.0)                         # rests between are no phrase
    assert tool.returns(_bars("ab")) is None and tool.returns({}) is None


def test_the_floor_is_the_liked_librarys_and_only_where_it_was_measured():
    tool = _tool()
    assert 0.4 <= tool.RETURNS_FLOOR["knight"] <= 0.5 and 0.2 <= tool.RETURNS_FLOOR["warcraft"] <= 0.35 and "house" not in tool.RETURNS_FLOOR
