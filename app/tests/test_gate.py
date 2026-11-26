"""The gate (tools/gate.py): a new song is held to the liked library's own windows, not to its round."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("gate", REPO / "tools" / "gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(label: str, style: str, take: str, which: str, score: float, memorability: float | None = None, folder: str | None = None) -> dict:
    memorability = score if memorability is None else memorability
    rest = (5 * score - memorability) / 4                 # the other four, so that the five's mean is `score`
    return {"label": label, "style": style, "take": take, "title": take.title(),
            "folder": folder or "/drive/studio-demo/windows-x/%s/%s/%s" % (which, style, take),
            "songeval": {"Coherence": rest, "Musicality": rest, "Memorability": memorability, "Clarity": rest, "Naturalness": rest}}


def test_a_window_is_told_by_its_folder_and_a_whole_song_is_not_one():
    tool = _tool()
    assert tool.window_of({"style": "knight", "folder": "/a/studio-demo/windows-round13/summit/knight/x-1/1"}) == "summit"
    assert tool.window_of({"style": "warcraft", "folder": "/a/studio-demo/windows-rev1126/before-theme/warcraft/x-1/1"}) == "theme"
    assert tool.window_of({"style": "knight", "folder": "/a/studio/knight/theme-song-1/1"}) == ""            # a whole staged song, whatever it is called
    assert tool.window_of({"style": "knight", "folder": "/a/theme/studio/knight/x-1/1"}) == ""


def test_a_song_is_held_to_the_librarys_lower_quartile_in_its_own_style():
    tool = _tool()
    rows = []
    for number, score in enumerate((3.0, 3.1, 3.2, 3.3, 3.4)):                             # the library: five songs, two windows each
        rows += [_row("library", "knight", "old-%d/1" % number, which, score) for which in ("theme", "summit")]
    rows += [_row("revold-before", "warcraft", "court-1/1", "theme", 2.8), _row("revold-before", "warcraft", "court-2/1", "theme", 2.6)]
    rows += [_row("round", "knight", "new-good/1", "theme", 3.3), _row("round", "knight", "new-good/1", "summit", 3.1),      # 3.2: over the bar
             _row("round", "knight", "new-bad/1", "theme", 2.7), _row("round", "knight", "new-bad/1", "summit", 2.9),
             _row("round", "knight", "new-forgettable/1", "theme", 3.3, memorability=2.5),                                  # good, and not remembered
             _row("round", "warcraft", "new-court/1", "theme", 2.7),
             _row("round", "knight", "new-good/1", "", 1.0, folder="/drive/studio/knight/new-good/1")]                      # a whole song: not like for like
    bar = tool.library(rows)
    assert bar["knight"]["songs"] == 5 and bar["knight"]["score"] == pytest.approx(3.1) and bar["knight"]["middle"] == pytest.approx(3.2)
    assert bar["warcraft"]["score"] == pytest.approx(2.65)
    found = {each["take"]: each for each in tool.check(rows, "round") if each["way"] == "windows"}
    assert found["new-good/1"]["passes"] and found["new-good/1"]["score"] == pytest.approx(3.2) and found["new-good/1"]["windows"] == ["summit", "theme"]
    assert not found["new-bad/1"]["passes"] and found["new-bad/1"]["under"] == ["score", "memorability"]
    assert not found["new-forgettable/1"]["passes"] and found["new-forgettable/1"]["under"] == ["memorability"]
    assert found["new-court/1"]["passes"]                                                  # 2.7 against Warcraft's 2.65, not Knight Rock's 3.1
    assert [each["take"] for each in tool.check(rows, "round", "warcraft")] == ["new-court/1"]
    # The whole take of new-good was read too (1.0), and Knight Rock has no whole takes of its library here: nothing to hold that to, so it does not pass.
    assert tool.passed(tool.check(rows, "round")) == ["new-court/1"]
    assert tool.passed([each for each in tool.check(rows, "round") if each["way"] == "windows"]) == ["new-court/1", "new-good/1"]


def test_a_window_judged_again_counts_by_its_latest_reading_and_a_style_with_no_library_passes_none(tmp_path):
    tool = _tool()
    rows = [_row("library", "knight", "old-1/1", "theme", 3.0), _row("round", "knight", "new/1", "theme", 2.0), _row("round", "knight", "new/1", "theme", 3.5)]
    assert tool.check(rows, "round")[0]["score"] == pytest.approx(3.5)
    lone = next(each for each in tool.check(rows + [_row("round", "house", "new-house/1", "theme", 3.0)], "round") if each["style"] == "house")
    assert not lone["passes"] and lone["under"][0].startswith("no library")                # nothing to hold it to: it does not pass, and it is said why
    log = tmp_path / "judged.jsonl"
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert tool.main(["--log", str(log), "check", "round"]) == 0 and tool.main(["--log", str(log), "library"]) == 0


def test_the_librarys_songs_to_read_are_the_most_played_one_take_of_each_and_none_that_rests(tmp_path):
    import sqlite3

    from freerock.playbook import PlayBook
    tool = _tool()
    PlayBook(tmp_path / "plays.sqlite3")
    heard = {"knight/old-road-1/1": 9, "knight/old-road-1/2": 12, "knight/mill-song-1/1": 7, "knight/bone-mill-1/1": 30, "knight/gone-1/1": 20, "knight/quiet-1/1": 0,
             "warcraft/court-1/1": 50}
    with sqlite3.connect(tmp_path / "plays.sqlite3") as db:
        for track, plays in heard.items():
            db.execute("insert into parts (style, track, place, channel, tier, stretch, plays) values (?, ?, 0, 'lead', 1, 0, ?)", (track.split("/")[0], track, plays))
    for track in heard:
        if "gone" not in track:                         # (played once, and no longer staged)
            folder = tmp_path / "studio" / track
            folder.mkdir(parents=True)
            (folder / "track.json").write_text("{}", encoding="utf-8")
    (tmp_path / "studio" / "knight" / "resting.txt").write_text("# resting\nbone-mill-1/1 [audit-1126] why\n", encoding="utf-8")
    assert tool.pick(tmp_path, "knight", 24) == ["old-road-1/2", "mill-song-1/1"]
    assert tool.pick(tmp_path, "knight", 1) == ["old-road-1/2"] and tool.pick(tmp_path, "warcraft") == ["court-1/1"]


def test_a_whole_take_is_held_to_the_whole_takes_of_the_library_and_not_to_its_windows():
    """(SongEval reads a whole take by its two minutes from the first theme on: the watch read the library so until 2026-11-23, and nothing has to be judged again.)"""
    tool = _tool()
    stage = "/drive/studio/knight/%s"
    rows = [_row("watch", "knight", "old-%d/1" % number, "", score, folder=stage % ("old-%d/1" % number)) for number, score in enumerate((3.0, 3.1, 3.2, 3.3, 3.4))]
    rows += [_row("library", "knight", "old-9/1", "theme", 2.0)]                                  # a window of the library: another reading, another bar
    rows += [_row("gate-1126", "knight", "new-good/1", "", 3.15, folder=stage % "new-good/1"), _row("gate-1126", "knight", "new-bad/1", "", 3.05, folder=stage % "new-bad/1"),
             _row("gate-1126", "knight", "new-bad/1", "", 2.9, folder="/drive/studio-demo/x/knight/new-bad/1")]      # judged again, somewhere else: the latest counts
    assert tool.whole(rows[0]) and not tool.whole(rows[5])
    assert tool.library(rows, "whole")["knight"]["score"] == pytest.approx(3.1) and tool.library(rows, "whole")["knight"]["songs"] == 5
    assert tool.library(rows, "windows")["knight"]["score"] == pytest.approx(2.0)
    found = {each["take"]: each for each in tool.check(rows, "gate-1126")}
    assert found["new-good/1"]["passes"] and found["new-good/1"]["way"] == "whole" and found["new-good/1"]["windows"] == ["whole"]
    assert not found["new-bad/1"]["passes"] and found["new-bad/1"]["score"] == pytest.approx(2.9)
    assert tool.passed(tool.check(rows, "gate-1126")) == ["new-good/1"]


def test_the_resting_songs_of_a_tag_still_to_be_read_are_those_with_no_whole_reading_under_the_label(tmp_path):
    tool = _tool()
    folder = tmp_path / "studio" / "knight"
    folder.mkdir(parents=True)
    (folder / "resting.txt").write_text("# resting\nbone-mill-1/1 [audit-1126] why\nsalt-pan-1/1 [audit-1126] why\nstorm-09/2 2026-11-24: another reason\nnight-fair-1/1 [new-1127] new\n", encoding="utf-8")
    rows = [_row("gate-1126", "knight", "bone-mill-1/1", "", 3.0, folder="/drive/studio/knight/bone-mill-1/1"),
            _row("gate-1126", "knight", "salt-pan-1/1", "theme", 3.0),                         # a window of it: not the whole reading
            _row("other", "knight", "salt-pan-1/1", "", 3.0, folder="/drive/studio/knight/salt-pan-1/1")]
    assert tool.to_read(tmp_path, rows, "gate-1126", "knight", "audit-1126") == ["salt-pan-1/1"]
    assert tool.to_read(tmp_path, rows, "gate-1126", "knight", "new-1127") == ["night-fair-1/1"]
    assert tool.to_read(tmp_path, rows, "gate-1126", "warcraft", "audit-1126") == []
    with pytest.raises(FileNotFoundError):
        tool.read(tmp_path, "gate-1126", "knight", ["salt-pan-1/1"])                           # no judges on this made-up drive: said, not passed over



def test_a_reading_made_before_its_take_was_performed_again_does_not_count_and_the_take_is_read_again(tmp_path):
    """(2026-11-26: the resting songs written again plainly are performed over their takes by day, and the judges read what rests by night, under
    one label: a reading of the take of before would have stood for the new one, and passed or held a song nobody had read.)"""
    import os
    import time
    tool = _tool()
    stage = tmp_path / "studio" / "knight"
    read_at = time.mktime(time.strptime("2026-11-26T12:38", "%Y-%m-%dT%H:%M"))
    for name, made in (("bone-mill-1/1", read_at - 3600), ("salt-pan-1/1", read_at + 7200), ("night-fair-1/1", read_at + 30)):
        (stage / name).mkdir(parents=True)
        (stage / name / "track.json").write_text("{}", encoding="utf-8")
        os.utime(stage / name / "track.json", (made, made))
    (stage / "resting.txt").write_text("".join("%s [audit-1126] why\n" % name for name in ("bone-mill-1/1", "salt-pan-1/1", "night-fair-1/1", "gone-song-1/1")), encoding="utf-8")
    rows = [dict(_row("watch", "knight", "old-%d/1" % n, "", 3.0 + n / 10, folder=str(stage / ("old-%d" % n) / "1")), at="2026-11-20T10:00") for n in range(5)]
    rows += [dict(_row("gate-1126", "knight", name, "", 3.4, folder=str(stage / name)), at="2026-11-26T12:38")
             for name in ("bone-mill-1/1", "salt-pan-1/1", "night-fair-1/1", "gone-song-1/1")]
    by = {row["take"]: row for row in rows if row["label"] == "gate-1126"}
    assert not tool.performed_since(by["bone-mill-1/1"])                 # staged an hour before it was read
    assert tool.performed_since(by["salt-pan-1/1"])                      # performed again two hours after
    assert not tool.performed_since(by["night-fair-1/1"])                # within the minute a reading's time is kept to: the reading stands
    assert not tool.performed_since(by["gone-song-1/1"])                 # not staged there: nothing is known against the reading
    assert not tool.performed_since({"folder": str(stage / "salt-pan-1/1")})     # a row with no time
    kept, again = tool.standing(rows, "gate-1126")
    assert again == ["knight/salt-pan-1/1"] and len(kept) == len(rows) - 1
    assert tool.to_read(tmp_path, kept, "gate-1126", "knight", "audit-1126") == ["salt-pan-1/1"]
    assert tool.passed(tool.check(kept, "gate-1126")) == ["bone-mill-1/1", "gone-song-1/1", "night-fair-1/1"]
    # Read again after the performance: that reading stands, and nothing is left to read. The library's rows are never looked at.
    rows.append(dict(_row("gate-1126", "knight", "salt-pan-1/1", "", 2.0, folder=str(stage / "salt-pan-1/1")), at="2026-11-26T15:00"))
    kept, again = tool.standing(rows, "gate-1126")
    assert again == [] and tool.to_read(tmp_path, kept, "gate-1126", "knight", "audit-1126") == []
    assert [each["passes"] for each in tool.check(kept, "gate-1126") if each["take"] == "salt-pan-1/1"] == [False]
    assert tool.standing(rows, "watch") == (rows, [])


def test_whose_a_song_is_its_sheet_says_and_the_morning_brings_back_only_the_houses_own(tmp_path, monkeypatch, capsys):
    """(2026-11-26: "the new bands a lot of time just sound random". A band's song that the judges pass waits for the listener's word; the house's own
    players' come back on the judges'. Until this the two came out of one list of names.)"""
    tool = _tool()
    stage = tmp_path / "studio" / "knight"
    for name, about in (("bone-mill-1/1", {"sounds": "jug", "band": True}), ("old-road-4/1", {"sounds": "", "band": True}), ("salt-pan-1/1", {"sounds": "saloon"}), ("mill-song-1/1", None)):
        (stage / name).mkdir(parents=True)
        if about is not None:
            (stage / name / "sheet.json").write_text(json.dumps({"about": about}), encoding="utf-8")
    assert [tool.whose(tmp_path, "knight", name) for name in ("bone-mill-1/1", "old-road-4/1", "salt-pan-1/1", "mill-song-1/1", "not-staged-1/1")] == ["jug", "", "saloon", "", ""]
    rows = [_row("watch", "knight", "old-%d/1" % n, "", 3.0 + n / 10, folder="/drive/studio/knight/old-%d/1" % n) for n in range(5)]
    rows += [_row("gate-1126", "knight", name, "", score, folder="/drive/studio/knight/%s" % name)
             for name, score in (("bone-mill-1/1", 3.4), ("old-road-4/1", 3.4), ("salt-pan-1/1", 2.0), ("mill-song-1/1", 3.3))]
    log = tmp_path / "judged.jsonl"
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(tool, "VAR", tmp_path)
    said = {}
    for flags in ((), ("--own",), ("--bands",)):
        assert tool.main(["--log", str(log), "check", "gate-1126", "--style", "knight", "--passed", *flags]) == 0
        said[flags] = capsys.readouterr().out.split()
    assert said[()] == ["bone-mill-1/1", "mill-song-1/1", "old-road-4/1"]
    assert said[("--own",)] == ["mill-song-1/1", "old-road-4/1"] and said[("--bands",)] == ["bone-mill-1/1"]
    assert tool.main(["--log", str(log), "check", "gate-1126"]) == 0
    told = capsys.readouterr().out
    assert "jug" in told and "of those that pass: 2 the house's own players' (the morning brings these back), 1 a band's, a company's or an act's" in told
    with pytest.raises(SystemExit):
        tool.main(["--log", str(log), "check", "gate-1126", "--passed", "--own", "--bands"])
    # Let in on the listener's word (tools/rest.py back writes it down): it waits for nobody, and is not put to them again.
    assert tool.let_in(tmp_path, "knight") == set()
    (stage / "admitted.txt").write_text("# Songs let into the player\nbone-mill-1/1 [audit-1126]\n", encoding="utf-8")
    assert tool.let_in(tmp_path, "knight") == {"bone-mill-1/1"}
    for flags in ((), ("--own",), ("--bands",)):
        assert tool.main(["--log", str(log), "check", "gate-1126", "--style", "knight", "--passed", *flags]) == 0
        said[flags] = capsys.readouterr().out.split()
    assert said[()] == ["bone-mill-1/1", "mill-song-1/1", "old-road-4/1"] and said[("--own",)] == ["mill-song-1/1", "old-road-4/1"] and said[("--bands",)] == []
    assert tool.main(["--log", str(log), "check", "gate-1126"]) == 0
    told = capsys.readouterr().out
    assert "of those that pass: 1 let in already; 2 the house's own players' (the morning brings these back), 0 a band's, a company's or an act's" in told
    assert [line.split()[0] for line in told.splitlines() if "bone-mill-1/1" in line] == ["in"]
