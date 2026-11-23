"""The standing cycle's picks (tools/cycle.py): where songs are few or come round most, which old songs to test, and what was found."""
from __future__ import annotations

import datetime
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
NOW = datetime.datetime(2026, 11, 23, 13, 30)


def _tool():
    spec = importlib.util.spec_from_file_location("cycle", REPO / "tools" / "cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _song(var: Path, name: str, role: str = "wander", moods=("pastoral",), light: bool = False, title: str = "A Song") -> None:
    folder = var / "studio" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "track.json").write_text(json.dumps({"title": title, "role": role, "moods": list(moods), "light": light}), encoding="utf-8")


def _heard(var: Path, **counts: int) -> None:
    """Songs heard from their openings, so many times (the play book's own table; one that was never heard has no row)."""
    with sqlite3.connect(var / "plays.sqlite3") as db:
        db.execute("create table if not exists parts (style text, track text, place integer, channel text, tier integer, stretch integer,"
                   " plays integer, last real, loved integer, banned integer)")
        for track, n in counts.items():
            for channel in ("lead", "drums"):
                db.execute("insert into parts values ('knight', ?, 0, ?, 1, 0, ?, 1.0, 0, 0)", (track.replace("__", "/"), channel, n))
                db.execute("insert into parts values ('knight', ?, 3, ?, 1, 0, 99, 1.0, 0, 0)", (track.replace("__", "/"), channel))


def test_a_place_with_no_song_comes_first_and_then_the_one_heard_most_per_song(tmp_path):
    cycle = _tool()
    for take in (1, 2, 3):
        _song(tmp_path, "knight/storm-a-1/%d" % take, role="storm")
    _song(tmp_path, "knight/town-a-1/1", role="town", light=True)
    _song(tmp_path, "knight/walk-a-1/1", moods=("desert", "jungle"))
    _heard(tmp_path, **{"knight__storm-a-1__1": 4, "knight__storm-a-1__2": 2, "knight__town-a-1__1": 5})
    rows = cycle.gaps(tmp_path, "knight", ("pastoral", "desert", "jungle"))
    assert rows[0]["need"] == cycle.EMPTY and rows[0]["songs"] == 0                       # (the pastoral walk, the night...: nothing at all)
    empty = [row["kind"] for row in rows if row["songs"] == 0]
    assert "walk pastoral" in empty and "moment ember" in empty and "moment storm" not in empty
    full = [row for row in rows if row["songs"]]
    assert [row["kind"] for row in full][0] == "moment town" and full[0]["plays"] == 5 and full[0]["dark"] == 0
    storm = next(row for row in full if row["kind"] == "moment storm")
    assert (storm["songs"], storm["plays"], storm["never"], storm["dark"]) == (3, 6, 1, 3)
    assert {row["kind"] for row in full if row["kind"].startswith("walk")} == {"walk desert", "walk jungle"}


def test_the_old_songs_to_test_are_those_tested_least_then_heard_most_then_judged_lowest(tmp_path):
    cycle = _tool()
    for name in ("a-1", "b-1", "c-1", "d-1"):
        _song(tmp_path, "knight/%s/1" % name, title=name.upper())
    _heard(tmp_path, **{"knight__a-1__1": 1, "knight__b-1__1": 6, "knight__c-1__1": 6})
    log = tmp_path / "passes" / "judged3.jsonl"
    log.parent.mkdir()
    score = {"Coherence": 1.0, "Musicality": 2.0, "Memorability": 3.0, "Clarity": 2.0, "Naturalness": 2.0}
    log.write_text("\n".join(json.dumps(row) for row in (
        {"style": "knight", "take": "b-1/1", "label": "watch", "songeval": {k: v + 1 for k, v in score.items()}},
        {"style": "knight", "take": "c-1/1", "label": "watch", "songeval": score},
        {"style": "knight", "take": "c-1/1", "label": "demo", "songeval": {k: 9.0 for k in score}})) + "\n", encoding="utf-8")
    assert [row["name"] for row in cycle.old(tmp_path, "knight", 10)] == ["knight/c-1/1", "knight/b-1/1", "knight/a-1/1", "knight/d-1/1"]
    assert cycle.old(tmp_path, "knight", 10)[0]["judged"] == pytest.approx(2.0)
    cycle.main(["--var", str(tmp_path), "mark", "knight/c-1/1", "revise", "its drums are thin"], NOW)
    assert [row["name"] for row in cycle.old(tmp_path, "knight", 2)] == ["knight/b-1/1", "knight/a-1/1"]
    kept = cycle.state(tmp_path)["tested"]["knight/c-1/1"]
    assert kept["times"] == 1 and kept["result"] == "revise" and kept["note"] == "its drums are thin" and kept["last"] == "2026-11-23T13:30"
    cycle.main(["--var", str(tmp_path), "mark", "knight/c-1/1", "revised"], NOW)
    assert cycle.state(tmp_path)["tested"]["knight/c-1/1"]["times"] == 2
    with pytest.raises(ValueError, match="comes to"):
        cycle.mark(tmp_path, "knight/c-1/1", "good", "", NOW)


def test_a_round_is_begun_and_ended_and_what_was_learnt_is_kept(tmp_path, capsys):
    cycle = _tool()
    assert cycle.main(["--var", str(tmp_path), "round", "end"], NOW) == 1
    assert cycle.main(["--var", str(tmp_path), "round", "begin", "ten of each"], NOW) == 0
    assert cycle.main(["--var", str(tmp_path), "round", "end", "the storms are gritty now"], NOW) == 0
    assert "round 1" in capsys.readouterr().out and cycle.state(tmp_path)["rounds"][0]["said"] == "ten of each | the storms are gritty now"
    assert cycle.main(["--var", str(tmp_path), "round", "begin", "again"], NOW) == 0
    assert [each["number"] for each in cycle.state(tmp_path)["rounds"]] == [1, 2]


def test_it_lists_what_it_is_asked_for_and_needs_no_plays_and_no_judges(tmp_path, capsys):
    cycle = _tool()
    _song(tmp_path, "house/ember-01/1", role="ember", title="Low Rafters")
    assert cycle.main(["--var", str(tmp_path), "gaps", "--style", "house", "--n", "40"], NOW) == 0
    assert "moment ember" in capsys.readouterr().out
    assert cycle.main(["--var", str(tmp_path), "old", "--style", "house"], NOW) == 0
    assert "Low Rafters" in capsys.readouterr().out


def test_one_take_of_each_family_is_tested_before_a_second(tmp_path):
    cycle = _tool()
    for take in (1, 2, 3):
        _song(tmp_path, "house/camp-01/%d" % take, title="Embers")
    _song(tmp_path, "house/storm-01/1", title="Rain")
    _heard(tmp_path, **{"house__camp-01__1": 9, "house__camp-01__2": 8, "house__camp-01__3": 7, "house__storm-01__1": 1})
    assert [row["name"] for row in cycle.old(tmp_path, "house", 2)] == ["house/camp-01/1", "house/storm-01/1"]
    assert len(cycle.old(tmp_path, "house", 10)) == 4
