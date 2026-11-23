"""The songs of the day written to listen to first (tools/listen.py --new): the whole files alone, the newest first, beside the pass
over every staged song, which writes the mixer's channels too and takes hours. (2026-11-23: the page of what is new was five hours
old in places, "its file is being written", because the pass had reached none of the day's songs.)"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile

from freerock import studio

REPO = Path(__file__).resolve().parents[2]


def _tool(var: Path):
    spec = importlib.util.spec_from_file_location("listen_tool", REPO / "tools" / "listen.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VAR = var
    return module


def _staged(var: Path, style: str, family: str, title: str, ago: float, level: float = 0.2) -> Path:
    folder = var / "studio" / style / family / "1"
    folder.mkdir(parents=True)
    meta = {"style": style, "family": family, "take": 1, "title": title, "tempo": 100.0, "beats": 4.0, "bar_frames": 4800.0, "tonic": "A minor",
            "moods": ["pastoral"], "role": "wander", "serves": [0, 1], "light": False, "sections": [{"story": "open", "bars": 4}]}
    for channel in ("lead", "drums"):
        soundfile.write(str(folder / (channel + ".flac")), np.full((19200, 2), level, dtype=np.float32), studio.RATE, format="FLAC", subtype="PCM_24")
    (folder / "track.json").write_text(json.dumps(meta), encoding="utf-8")
    then = time.time() - ago * 3600.0
    for path in folder.iterdir():
        os.utime(path, (then, then))
    return folder


@pytest.fixture
def var(tmp_path):
    return tmp_path / "var"


def test_the_days_songs_are_written_newest_first_and_only_their_whole_files(var, capsys):
    tool = _tool(var)
    _staged(var, "knight", "old-song-1", "Old Song", ago=60.0)
    _staged(var, "warcraft", "first-1", "First of Today", ago=5.0)
    _staged(var, "house", "second-1", "Second of Today", ago=1.0)

    assert tool.main(["--new", "24"]) == 0

    said = capsys.readouterr().out
    assert said.index("Second of Today") < said.index("First of Today") and "Old Song" not in said
    assert "2 new songs written to listen to" in said
    listen = var / "listen"
    assert (listen / "house" / "Second of Today - take 1 (second-1).flac").is_file()
    assert not (listen / "knight").exists() and not (listen / "house" / "Second of Today - take 1 (second-1)").exists()     # no channels
    audio, _ = soundfile.read(str(listen / "house" / "Second of Today - take 1 (second-1).flac"))
    assert abs(float(np.abs(audio).max()) - 0.89) < 0.01                                  # the mix, brought to its ceiling
    assert not list(listen.rglob("*.part.flac"))


def test_a_song_already_written_is_left_and_one_made_again_is_written_again(var, capsys):
    tool = _tool(var)
    folder = _staged(var, "house", "song-1", "The Song", ago=1.0)
    assert tool.main(["--new", "24"]) == 0
    file = var / "listen" / "house" / "The Song - take 1 (song-1).flac"
    before = file.read_bytes()
    capsys.readouterr()
    assert tool.main(["--new", "24"]) == 0 and "0 new songs" in capsys.readouterr().out
    # (A tone that changes: two steady ones, each brought to the ceiling, come to the same file.)
    soundfile.write(str(folder / "lead.flac"), np.linspace(0.0, 0.3, 19200 * 2, dtype=np.float32).reshape(19200, 2), studio.RATE, format="FLAC", subtype="PCM_24")
    (folder / "track.json").touch()
    os.utime(file, (time.time() - 1800.0, time.time() - 1800.0))
    assert tool.main(["--new", "24"]) == 0 and "1 new songs" in capsys.readouterr().out and file.read_bytes() != before


def test_a_song_that_cannot_be_put_together_is_named_and_the_rest_are_written(var, capsys):
    tool = _tool(var)
    broken = _staged(var, "house", "broken-1", "Broken", ago=1.0)
    (broken / "lead.flac").write_bytes(b"not a recording")
    _staged(var, "house", "good-1", "Good", ago=2.0)
    assert tool.main(["--new", "24"]) == 1
    said = capsys.readouterr().out
    assert "NOT written" in said and "broken-1" in said and (var / "listen" / "house" / "Good - take 1 (good-1).flac").is_file()
