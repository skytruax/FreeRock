"""The study's count of a tune coming back (tools/study.py): held to the liked library from below, not read as a fault from above."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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
    assert 0.6 <= tool.HEARD_FLOOR["knight"] <= 0.75 and 0.75 <= tool.HEARD_FLOOR["warcraft"] <= 0.9 and "house" not in tool.HEARD_FLOOR


def _voice(*phrases: tuple[int, tuple[int, ...]]) -> SimpleNamespace:
    """A lead voice from (two-bar span, pitches): the pitches a beat apart from the span's first beat, in 4/4."""
    return SimpleNamespace(notes=[SimpleNamespace(start=span * 8.0 + at, pitch=pitch) for span, pitches in phrases for at, pitch in enumerate(pitches)])


def test_a_tune_told_again_on_another_voice_or_at_another_pitch_is_heard_again():
    """(2026-11-27: Drowned Ruins read 10% by the count of phrases every lead voice plays again note for note, while its choir sang the
    English horn's theme at the arrival and its summit was all of it a minor third up; the judges gave it memorability 3.01.)"""
    tool = _tool()
    theme, other = (60, 62, 64, 65), (67, 60, 70, 59)
    horn, choir = _voice((0, theme), (1, other)), _voice((3, tuple(p + 3 for p in theme)))      # the choir has it, lifted a minor third
    assert tool.heard([horn, choir], 4.0) == pytest.approx(2 / 3)
    assert tool.heard([horn, _voice((5, tuple(p + 12 for p in theme)))], 4.0) == pytest.approx(2 / 3)      # an octave up, later: the same tune
    with_it = _voice((0, theme), (1, other)), _voice((0, tuple(p - 12 for p in theme)))
    assert tool.heard(list(with_it), 4.0) == 0.0                                                   # two voices at once: not a return
    assert tool.heard([_voice((0, theme), (1, tuple(2 * theme[0] - p for p in theme)))], 4.0) == 0.0     # told upside down: not known again
    assert tool.heard([_voice((0, (60, 62)), (1, (60, 62)))], 4.0) is None                          # two notes have no shape to know
    assert tool.heard([_voice((0, theme))], 4.0) is None and tool.heard([], 4.0) is None


def test_a_measurement_that_does_not_apply_says_so_and_does_not_print_a_nought(monkeypatch, capsys):
    """(2026-11-27: House's ten old songs of round fifteen read "tune bars heard before 0% on average". written() gives House no notes at all, so
    that nought was the mean of nothing — a number a reader would act on, standing where "not measured" belonged.)"""
    tool = _tool()
    monkeypatch.setattr(tool, "stems", lambda style, name, take: ({"title": name}, {"lead": None}, 48000))
    monkeypatch.setattr(tool, "story_loudness", lambda meta, parts, rate: [("theme", -20.0), ("moment", -12.0)])
    monkeypatch.setattr(tool.ear, "profile", lambda audio, rate: None)
    def no_stems(*_, **__):                 # (2026-11-27: main's suite passed this and a worktree's did not — reference() reads the liked
        raise KeyError("no liked stems")    # stems off the drive, so the test went to var/ for them. A test asks the drive for nothing.)
    monkeypatch.setattr(tool.ear, "reference", no_stems)
    monkeypatch.setattr(tool, "written", lambda style, name, take: {})                       # as House is
    assert tool.main(["house", "camp-03/2", "coast-01/2"]) == 0
    said = capsys.readouterr().out
    assert "study.py reads no notes for house): the tune is not measured here" in said and "0% on average" not in said
    monkeypatch.setattr(tool, "written", lambda style, name, take: {"at_once": [], "spread": [], "tune_repeats": 0.5})
    assert tool.main(["knight", "bone-mill-1/1", "old-road-4/1"]) == 0
    assert "tune bars heard before 50% on average, over 2 of the 2" in capsys.readouterr().out


def test_under_is_said_of_the_tune_heard_again_and_not_of_the_note_for_note_count(monkeypatch, capsys):
    tool = _tool()
    monkeypatch.setattr(tool, "stems", lambda style, name, take: ({"title": name}, {"lead": None}, 48000))
    monkeypatch.setattr(tool, "story_loudness", lambda meta, parts, rate: [("theme", -20.0), ("moment", -12.0)])
    monkeypatch.setattr(tool.ear, "profile", lambda audio, rate: None)
    def no_stems(*_, **__):
        raise KeyError("no liked stems")
    monkeypatch.setattr(tool.ear, "reference", no_stems)
    monkeypatch.setattr(tool, "written", lambda style, name, take: {"at_once": [], "spread": [], "tune_repeats": 0.2, "tune_returns": 0.10, "tune_heard": 0.76})
    assert tool.main(["warcraft", "mystic-ancient-ruins-1/3"]) == 0
    said = capsys.readouterr().out.splitlines()
    heard = [line for line in said if "the tune heard again" in line]
    note_for_note = [line for line in said if "note for note" in line]
    assert len(heard) == 1 and "76%" in heard[0] and "UNDER the liked library's lower quartile (83%)" in heard[0]
    assert len(note_for_note) == 1 and "10%" in note_for_note[0] and "UNDER" not in note_for_note[0] and "lower quartile 27%" in note_for_note[0]
    monkeypatch.setattr(tool, "written", lambda style, name, take: {"at_once": [], "spread": [], "tune_repeats": 0.2, "tune_returns": 0.10, "tune_heard": 0.88})
    assert tool.main(["warcraft", "mystic-ancient-ruins-1/3"]) == 0
    assert "UNDER" not in capsys.readouterr().out
