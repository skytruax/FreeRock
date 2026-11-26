"""The page of what the judges passed (tools/gate_page.py): a band's song that passed is there to be heard and waits for the listener's word."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile

REPO = Path(__file__).resolve().parents[2]


def _tool():
    sys.modules.pop("gate", None)                      # (the page's tool imports the gate's by name from its own folder)
    spec = importlib.util.spec_from_file_location("gate_page", REPO / "tools" / "gate_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(label: str, take: str, score: float, folder: str, at: str = "2099-01-01T00:00") -> dict:
    return {"label": label, "style": "knight", "take": take, "title": take, "folder": folder, "at": at,
            "songeval": {"Coherence": score, "Musicality": score, "Memorability": score, "Clarity": score, "Naturalness": score}}


def _take(folder: Path, title: str, sounds: str, metre: str, channels: tuple[str, ...] = ()) -> None:
    folder.mkdir(parents=True)
    family, take = folder.parent.name, int(folder.name)
    (folder / "track.json").write_text(json.dumps({"title": title, "take": take, "family": family, "tempo": 120.0}), encoding="utf-8")
    (folder / "sheet.json").write_text(json.dumps({"about": {"sounds": sounds, "metre": metre}}), encoding="utf-8")
    tone = np.sin(np.arange(2400) / 20.0).astype("float32")
    for at, channel in enumerate(channels):
        soundfile.write(str(folder / (channel + ".flac")), np.stack([tone, tone], axis=1)[:2400 - 600 * at] * 0.2, 48000, format="FLAC", subtype="PCM_24")


def test_the_page_has_a_bands_passes_to_hear_the_houses_own_and_the_held_and_the_take_of_before(tmp_path, capsys):
    tool = _tool()
    stage = tmp_path / "studio" / "knight"
    _take(stage / "bone-mill-1" / "1", "Bone Mill", "jug", "4/4")
    _take(stage / "old-road-4" / "1", "Old Road", "", "4/4")
    _take(stage / "salt-pan-1" / "1", "Salt Pan", "saloon", "4/4")
    _take(stage / "night-fair-1" / "1", "Night Fair", "jug", "4/4")
    _take(stage / "mill-song-1" / "1", "Mill Song", "jug", "4/4")
    _take(tmp_path / "studio-demo" / "retold-audit-1126" / "resting" / "knight" / "bone-mill-1" / "1", "Bone Mill", "jug", "7/8", channels=("lead", "bass"))
    listen = tmp_path / "listen" / "knight"
    listen.mkdir(parents=True)
    for name in ("Bone Mill - take 1 (bone-mill-1).flac", "Night Fair - take 1 (night-fair-1).flac"):
        (listen / name).write_bytes(b"")
    made = (stage / "night-fair-1" / "1" / "track.json").stat().st_mtime
    os.utime(listen / "Night Fair - take 1 (night-fair-1).flac", (made - 3600, made - 3600))          # written before the take was performed again
    rows = [_row("watch", "old-%d/1" % n, 3.0 + n / 10, "/drive/studio/knight/old-%d/1" % n) for n in range(5)]
    rows += [_row("gate-x", take, score, str(stage / take)) for take, score in (("bone-mill-1/1", 3.4), ("old-road-4/1", 3.3), ("salt-pan-1/1", 2.0), ("night-fair-1/1", 3.2),
                                                                                ("gone-song-1/1", 3.5))]
    rows.append(_row("gate-x", "mill-song-1/1", 3.6, str(stage / "mill-song-1/1"), at="2000-01-01T00:00"))      # read before the take as it is staged was performed
    log = tmp_path / "judged.jsonl"
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert tool.main(["--var", str(tmp_path), "--log", str(log), "gate-x"]) == 0
    assert "4 songs read, 3 passed (2 a band's, a company's or an act's), 1 of them with the take of before beside" in capsys.readouterr().out
    page = (tmp_path / "listen" / "gate.html").read_text(encoding="utf-8")
    waiting, own, held = page.index("Passed, and waiting for your word"), page.index("Passed, the house's own players"), page.index("<h3>Held</h3>")
    assert waiting < page.index("Bone Mill") < page.index("Night Fair") < own < page.index("Old Road") < held < page.index("Salt Pan")     # a band's by score, the house's own, the held
    assert "<h4>jug</h4>" in page and "gone-song" not in page                                        # (read, and not staged: nothing to hear)
    assert "Mill Song" not in page                                                                   # (its reading is of a take that is no longer there)
    assert 'src="knight/Bone%20Mill%20-%20take%201%20%28bone-mill-1%29.flac"' in page
    assert "as it was before it was written again in 7/8" in page and 'src="gate/knight--bone-mill-1--1--before.flac"' in page
    assert "this file is of the take before it was performed again" in page                          # Night Fair's
    assert "its file to listen to is not written yet" in page                                        # Old Road's
    before = tmp_path / "listen" / "gate" / "knight--bone-mill-1--1--before.flac"
    audio, rate = soundfile.read(str(before), always_2d=True)
    assert rate == 48000 and len(audio) == 2400 and abs(float(np.abs(audio).max()) - 0.89) < 0.01    # its two channels together, as loud as a listening file
    written = before.stat().st_mtime_ns
    assert tool.main(["--var", str(tmp_path), "--log", str(log), "gate-x"]) == 0 and before.stat().st_mtime_ns == written      # not written twice
