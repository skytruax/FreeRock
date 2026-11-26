"""The judges' windows (tools/windows.py): a take's first theme's last bars and its last moment's first."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile

REPO = Path(__file__).resolve().parents[2]
BAR = 100


def _tool():
    spec = importlib.util.spec_from_file_location("windows", REPO / "tools" / "windows.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _take(root: Path) -> Path:
    folder = root / "studio" / "knight" / "mill-song-1" / "2"
    folder.mkdir(parents=True)
    sections = [{"story": "open", "bars": 4}, {"story": "theme", "bars": 8}, {"story": "moment", "bars": 6}, {"story": "theme", "bars": 8},
                {"story": "moment", "bars": 6}, {"story": "close", "bars": 2}]
    (folder / "track.json").write_text(json.dumps({"style": "knight", "family": "mill-song-1", "take": 2, "bar_frames": float(BAR), "sections": sections}), encoding="utf-8")
    frames = 34 * BAR
    ramp = (np.arange(frames, dtype=np.float32) / frames)[:, None].repeat(2, axis=1)      # each frame says where it is
    for channel in ("lead", "drums"):
        soundfile.write(str(folder / (channel + ".flac")), ramp, 48000, subtype="PCM_24")
    return folder


def test_the_two_windows_are_cut_where_they_lie_and_named_for_the_gate(tmp_path):
    tool = _tool()
    take = _take(tmp_path)
    assert tool.span(json.loads((take / "track.json").read_text())["sections"], "theme", 4) == ("theme", 8, 4)        # the first theme's last four bars
    assert tool.span(json.loads((take / "track.json").read_text())["sections"], "summit", 4) == ("moment", 26, 4)     # the last moment's first four
    assert tool.main([str(take), str(tmp_path / "win"), "--bars", "4"]) == 0
    for which, first in (("theme", 8), ("summit", 26)):
        out = tmp_path / "win" / which / "knight" / "mill-song-1" / "2"
        audio, rate = soundfile.read(str(out / "lead.flac"), dtype="float32", always_2d=True)
        assert rate == 48000 and len(audio) == 4 * BAR and sorted(path.name for path in out.glob("*.flac")) == ["drums.flac", "lead.flac"]
        assert audio[0, 0] == pytest.approx(first * BAR / (34 * BAR), abs=1e-4)
        meta = json.loads((out / "track.json").read_text())
        assert [(section["story"], section["bars"]) for section in meta["sections"]] == [("open", 0), ("theme" if which == "theme" else "moment", 4)]
    # ...and the gate reads which window each is from where it stands
    spec = importlib.util.spec_from_file_location("gate", REPO / "tools" / "gate.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    assert gate.window_of({"style": "knight", "folder": str(tmp_path / "win" / "summit" / "knight" / "mill-song-1" / "2")}) == "summit"


def test_a_window_longer_than_its_part_is_the_whole_part_and_a_take_without_one_is_an_error(tmp_path):
    tool = _tool()
    take = _take(tmp_path)
    sections = json.loads((take / "track.json").read_text())["sections"]
    assert tool.span(sections, "theme", 32) == ("theme", 4, 8) and tool.span(sections, "summit", 32) == ("moment", 26, 6)
    with pytest.raises(ValueError):
        tool.span([{"story": "open", "bars": 4}], "theme", 8)
    with pytest.raises(ValueError):
        tool.span(sections, "drop", 8)
