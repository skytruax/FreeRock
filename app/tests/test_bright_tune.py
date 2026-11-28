"""The first theme is sung by a lead that sings over the band (orchestra.BRIGHT_TUNE, 2026-11-28: the instrument demo, `instrument-1128`)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from freerock.studio import orchestra


def _character(style: str, **changes) -> orchestra.Character:
    base = next(each for each in orchestra.CHARACTERS if each.style == style and not each.form)      # (every Knight Rock character is a band's)
    return replace(base, **changes)


def _take(character: orchestra.Character, take: int = 1) -> orchestra.Take:
    return orchestra.Take(orchestra.family(character, 31, "f", "F"), take)


def _homes(*names: str) -> list[int]:
    return [orchestra.INSTRUMENTS[name].home for name in names]


def test_the_instruments_the_demo_moved_are_low_leads_and_the_ones_it_gave_the_tune_to_are_not():
    assert all(home < orchestra.SINGS_OVER for home in _homes("trombone", "horns", "cello", "bassoon", "euphonium", "english horn"))
    assert all(home >= orchestra.SINGS_OVER for home in _homes("violins", "fiddle", "oboe", "flute", "clarinet", "lead guitar"))


def test_a_low_lead_whose_turn_it_is_gives_the_tune_to_the_characters_high_lead_and_doubles_it():
    character = _character("warcraft", leads=("oboe", "cello", "horns"))
    take = _take(character, 1)                          # take 1's turn comes to the cello first
    assert take.solo == "oboe" and take.mate == "cello"
    assert take.other != take.solo


def test_a_warcraft_character_with_no_high_lead_has_its_tune_sung_by_a_high_strong_voice():
    character = _character("warcraft", leads=("trombone", "horns", "cello"), strong=("brass", "violins"))
    take = _take(character, 1)
    assert take.solo == "violins" and take.mate in character.leads


def test_a_light_knight_song_keeps_its_leads_and_a_heavy_one_has_its_strong_voice_sing():
    light = _character("knight", leads=("trombone", "horns", "cello"), strong=("lead guitar", "horns"), weight=0.6)
    heavy = replace(light, weight=0.9)
    assert _take(light, 1).solo == "horns"              # as it was: the turn's own lead
    assert _take(heavy, 1).solo == "lead guitar"


def test_a_character_with_no_high_singer_anywhere_is_sung_as_it_was():
    character = _character("warcraft", leads=("trombone", "horns", "bassoon"), strong=("brass", "horns"))
    assert _take(character, 1).solo == "horns"


def test_the_switch_puts_the_old_turns_back_and_the_notes_are_the_same_either_way(monkeypatch):
    character = _character("warcraft", leads=("oboe", "cello", "horns"))
    mended = _take(character, 1)
    monkeypatch.setattr(orchestra, "BRIGHT_TUNE", False)
    before = _take(character, 1)
    assert before.solo == "cello" and mended.solo == "oboe"
    assert mended.tune.notes == before.tune.notes and mended.second.notes == before.second.notes      # no draw of the take's is spent on it
