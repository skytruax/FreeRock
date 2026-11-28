"""A Knight Rock theme is not sung by a mandolin or a whistle where another can sing it over the band (orchestra.WEAK_TUNE, 2026-11-28: the
day's swaps `revise-1128b`, Bitter Dirge's whistle and Soot Toll's mandolin given to the fiddle, +0.30 and +0.19 on SongEval's mean)."""
from __future__ import annotations

from dataclasses import replace

from freerock.studio import orchestra


def _character(style: str, **changes) -> orchestra.Character:
    base = next(each for each in orchestra.CHARACTERS if each.style == style and not each.form)      # (every Knight Rock character is a band's)
    return replace(base, **changes)


def _take(character: orchestra.Character, take: int = 1) -> orchestra.Take:
    return orchestra.Take(orchestra.family(character, 31, "f", "F"), take)


WEAK = orchestra.WEAK_SINGERS["knight"]


def test_the_weak_voices_sing_high_so_the_first_mend_never_moved_them():
    assert all(orchestra.INSTRUMENTS[name].home >= orchestra.SINGS_OVER for name in WEAK)
    assert "whistle" not in orchestra.WEAK_SINGERS.get("warcraft", ())


def test_a_character_whose_only_lead_is_a_mandolin_has_its_first_theme_sung_by_its_fiddle():
    character = _character("knight", leads=("mandolin",), strong=("fiddle",))          # gallows row: Soot Toll
    for number in (1, 2, 3):
        take = _take(character, number)
        assert take.solo == take.mate == "fiddle" and take.other not in WEAK and take.other != take.solo


def test_where_nobody_else_can_sing_the_second_theme_the_weak_voice_still_does():
    # last drink, Bitter Dirge's: a whistle and a fiddle and nobody else to sing. The swap gave the fiddle both themes; the writer keeps
    # two singers (test_studio: the two themes can be told apart), and the fiddle has the first, the one heard most.
    character = _character("knight", leads=("whistle",), strong=("fiddle",), under=(), pads=("strings slow",))
    for number in (1, 2):
        take = _take(character, number)
        assert take.solo == "fiddle" and take.other == "whistle"


def test_a_whistle_whose_turn_it_is_sings_neither_theme_where_the_fiddle_can():
    character = _character("knight", leads=("fiddle", "whistle"), strong=("fiddle",))  # cutpurse alley
    for number in (1, 2):
        take = _take(character, number)
        assert take.solo == "fiddle" and take.mate not in WEAK and take.third not in WEAK


def test_the_valleys_voice_is_not_a_weak_one_where_another_can_sing_it():
    character = _character("knight", leads=("whistle",), strong=("fiddle",), under=("whistle", "cello", "viola"))
    for number in (1, 2, 3, 4, 5):                      # (with the whistle left in the valley's pool, take 5 draws it)
        take = _take(character, number)
        assert take.solo == "fiddle" and take.other not in WEAK and take.hush not in WEAK


def test_a_character_with_no_other_singer_that_high_is_sung_as_it_was():
    character = _character("knight", leads=("mandolin",), strong=("viola", "mandolin"))    # outriders fire: the viola sits under G4
    assert _take(character, 1).solo == "mandolin"


def test_warcraft_keeps_its_whistle():
    character = _character("warcraft", leads=("whistle", "cello"), strong=("violins",))
    assert {_take(character, number).solo for number in (1, 2)} == {"whistle"}


def test_the_switch_puts_the_weak_voices_back_and_the_notes_are_the_same_either_way(monkeypatch):
    character = _character("knight", leads=("mandolin",), strong=("fiddle",))
    mended = _take(character, 1)
    monkeypatch.setattr(orchestra, "WEAK_TUNE", False)
    before = _take(character, 1)
    assert before.solo == "mandolin" and mended.solo == "fiddle"
    assert mended.tune.notes == before.tune.notes and mended.second.notes == before.second.notes      # no draw of the take's is spent on it
