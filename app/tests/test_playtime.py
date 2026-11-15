"""Counting the hours played, for growing music where time is spent and pacing its cost."""
import json

import pytest

from freerock.playtime import Playtime


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


NOVEMBER = 1794700800.0      # 2026-11-15, give or take the time zone
DAY = 86400.0


def test_time_is_counted_for_the_month_and_for_the_place(tmp_path):
    clock = Clock(NOVEMBER)
    played = Playtime(tmp_path / "playtime.json", clock)
    played.add("elwynn-forest", 1800)
    played.add("westfall", 900)
    played.add(None, 900)                                 # in sight, but the place's name not known yet
    assert played.month_hours() == pytest.approx(1.0)
    assert played.place_seconds("elwynn-forest") == 1800 and played.place_seconds("duskwood") == 0
    assert played.since_set("westfall") == 900
    played.add("westfall", -5)                            # a clock that stepped backwards counts for nothing
    assert played.place_seconds("westfall") == 900


def test_a_new_set_starts_the_wait_again_and_counts_towards_the_months_growth(tmp_path):
    played = Playtime(tmp_path / "playtime.json", Clock(NOVEMBER))
    played.add("elwynn-forest", 8000)
    played.set_made("elwynn-forest", 3.2)
    assert played.since_set("elwynn-forest") == 0 and played.place_seconds("elwynn-forest") == 8000
    assert played.growth_minutes() == pytest.approx(3.2)


def test_it_is_kept_between_runs_and_a_new_month_starts_the_months_counts_again(tmp_path):
    clock = Clock(NOVEMBER)
    played = Playtime(tmp_path / "playtime.json", clock)
    played.add("elwynn-forest", 7200)
    played.set_made("elwynn-forest", 3.2)
    played.add("elwynn-forest", 10)                       # not yet half a minute: only save() keeps it
    played.save()
    again = Playtime(tmp_path / "playtime.json", clock)
    assert again.month_hours() == pytest.approx(7210 / 3600) and again.growth_minutes() == pytest.approx(3.2)
    assert json.loads((tmp_path / "playtime.json").read_text())["places"]["elwynn-forest"] == 7210
    clock.now += 20 * DAY                                  # into December
    assert again.month_hours() == 0 and again.growth_minutes() == 0
    assert again.place_seconds("elwynn-forest") == 7210, "time in a place is not a monthly count"
    assert Playtime(tmp_path / "playtime.json", clock).month_hours() == 0


def test_it_saves_itself_every_half_minute_of_play(tmp_path):
    played = Playtime(tmp_path / "playtime.json", Clock(NOVEMBER))
    played.add("elwynn-forest", 20)
    assert not (tmp_path / "playtime.json").exists()
    played.add("elwynn-forest", 15)
    assert json.loads((tmp_path / "playtime.json").read_text())["month_seconds"] == 35
