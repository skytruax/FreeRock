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
    _take(stage / "crow-watch-4" / "1", "Crow Watch", "baroque", "4/4", channels=("lead", "rhythm", "drums"))
    _take(stage / "mill-song-1" / "1", "Mill Song", "jug", "4/4")
    _take(tmp_path / "studio-demo" / "retold-audit-1126" / "resting" / "knight" / "bone-mill-1" / "1", "Bone Mill", "jug", "7/8", channels=("lead", "bass"))
    listen = tmp_path / "listen" / "knight"
    listen.mkdir(parents=True)
    for name in ("Bone Mill - take 1 (bone-mill-1).flac", "Night Fair - take 1 (night-fair-1).flac", "Crow Watch - take 1 (crow-watch-4).flac"):
        (listen / name).write_bytes(b"")
    made = (stage / "night-fair-1" / "1" / "track.json").stat().st_mtime
    for name in ("Night Fair - take 1 (night-fair-1).flac", "Crow Watch - take 1 (crow-watch-4).flac"):
        os.utime(listen / name, (made - 3600, made - 3600))                                          # written before the take was performed again
    rows = [_row("watch", "old-%d/1" % n, 3.0 + n / 10, "/drive/studio/knight/old-%d/1" % n) for n in range(5)]
    rows += [_row("gate-x", take, score, str(stage / take)) for take, score in (("bone-mill-1/1", 3.4), ("old-road-4/1", 3.3), ("salt-pan-1/1", 2.0), ("night-fair-1/1", 3.2), ("crow-watch-4/1", 3.1),
                                                                                ("gone-song-1/1", 3.5))]
    rows.append(_row("gate-x", "mill-song-1/1", 3.6, str(stage / "mill-song-1/1"), at="2000-01-01T00:00"))      # read before the take as it is staged was performed
    (stage / "admitted.txt").write_text("# let in\ncrow-watch-4/1 [audit-1126]\n", encoding="utf-8")       # the listener said so (tools/rest.py back)
    log = tmp_path / "judged.jsonl"
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert tool.main(["--var", str(tmp_path), "--log", str(log), "gate-x"]) == 0
    assert "5 songs read, 4 passed (1 let in; 2 a band's, a company's or an act's waiting), 1 of them with the take of before beside" in capsys.readouterr().out
    page = (tmp_path / "listen" / "gate.html").read_text(encoding="utf-8")
    waiting, own, held = page.index("Passed, and waiting for your word"), page.index("Passed, the house's own players"), page.index("<h3>Held</h3>")
    assert waiting < page.index("Bone Mill") < page.index("Night Fair") < own < page.index("Old Road") < held < page.index("Salt Pan")     # a band's by score, the house's own, the held
    assert page.index("Passed, and let into the player") < page.index("Crow Watch") < waiting and "crow-watch-4/1 · the baroque" in page      # what was let in is first, and says whose
    assert "<h4>jug</h4>" in page and "gone-song" not in page                                        # (read, and not staged: nothing to hear)
    # A band is one decision where its songs are many (57 waited at once on 2026-11-27), so each band says how ALL of its songs read, the held ones too.
    assert '<h4>jug</h4><p class="band">2 of its songs read, 2 passed; they read <b>3.30</b> on average (the bar is above). 2 are waiting for your word.</p>' in page
    # The bar a song passes at is said once, in the style's own line, and on no row: it stood on all 123 rows of the page of 2026-11-27, two lines of every one on a phone.
    assert page.count("A song of this style passes when the judges give it") == 1 and "a song passes at" not in page
    assert "the judges 3.40, memorability 3.40" in page                                              # (a row says what the judges gave it, and no more)
    assert "Mill Song" not in page                                                                   # (its reading is of a take that is no longer there)
    assert 'src="knight/Bone%20Mill%20-%20take%201%20%28bone-mill-1%29.flac"' in page
    assert "as it was before it was written again in 7/8" in page and 'src="gate/knight--bone-mill-1--1--before.flac"' in page
    assert page.count("this file is of the take before it was performed again") == 1                 # Night Fair's: it has no recordings here to write it from
    again, rate = soundfile.read(str(listen / "Crow Watch - take 1 (crow-watch-4).flac"), always_2d=True)       # a passing song's older file is written again from its channels
    assert rate == 48000 and len(again) == 2400 and abs(float(np.abs(again).max()) - 0.89) < 0.01
    assert "its file to listen to is not written yet" in page                                        # Old Road's
    before = tmp_path / "listen" / "gate" / "knight--bone-mill-1--1--before.flac"
    audio, rate = soundfile.read(str(before), always_2d=True)
    assert rate == 48000 and len(audio) == 2400 and abs(float(np.abs(audio).max()) - 0.89) < 0.01    # its two channels together, as loud as a listening file
    written = before.stat().st_mtime_ns
    assert tool.main(["--var", str(tmp_path), "--log", str(log), "gate-x"]) == 0 and before.stat().st_mtime_ns == written      # not written twice


def test_whichever_gate_writes_the_page_it_is_of_every_gate_label(tmp_path, capsys):
    """(2026-11-28: the day's gate copy and the night's each wrote the page of their own labels only, one over the other: 82 songs waiting,
    then 57, then 82 again.)"""
    tool = _tool()
    stage = tmp_path / "studio" / "knight"
    for take, title in (("bone-mill-1", "Bone Mill"), ("salt-pan-1", "Salt Pan"), ("night-fair-1", "Night Fair"), ("crow-watch-1", "Crow Watch")):
        _take(stage / take / "1", title, "jug", "4/4")
    rows = [_row("watch", "old-%d/1" % n, 3.0 + n / 10, "/drive/studio/knight/old-%d/1" % n) for n in range(5)]
    # (the readings' times are after the takes' own, which are written now: a reading older than its take is of recordings no longer there)
    rows += [_row("gate-1126", "bone-mill-1/1", 3.4, str(stage / "bone-mill-1/1"), at="2099-11-26T23:00"),
             _row("gate-1126", "night-fair-1/1", 2.0, str(stage / "night-fair-1/1"), at="2099-11-26T23:10"),
             _row("gate-1128", "salt-pan-1/1", 3.3, str(stage / "salt-pan-1/1"), at="2099-11-28T01:00"),
             _row("gate-1128", "night-fair-1/1", 3.2, str(stage / "night-fair-1/1"), at="2099-11-28T01:10"),     # read again, later: it counts
             _row("revise-1128b", "salt-pan-1/1", 1.0, str(stage / "salt-pan-1/1"), at="2099-11-28T11:00"),    # (a revision's label: not the gate's)
             # gate-1126 read something after all of gate-1128 (the day's copy goes round), so it is the label read most lately; Night Fair's
             # newer reading is still gate-1128's, and that is the one that counts.
             _row("gate-1126", "crow-watch-1/1", 3.35, str(stage / "crow-watch-1/1"), at="2099-11-29T11:30")]
    log = tmp_path / "judged.jsonl"
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert tool.every_label(tool.gate.rows_of(log), ["gate-1126"]) == ["gate-1128", "gate-1126"]
    assert tool.main(["--var", str(tmp_path), "--log", str(log), "gate-1126"]) == 0                  # the day's copy, of its own label
    assert "4 songs read, 4 passed (0 let in; 4 a band's, a company's or an act's waiting)" in capsys.readouterr().out
    page = (tmp_path / "listen" / "gate.html").read_text(encoding="utf-8")
    assert all(title in page for title in ("Bone Mill", "Salt Pan", "Night Fair", "Crow Watch"))
    assert "the judges 3.20" in page and "the judges 2.00" not in page                              # Night Fair by its newer reading
    assert tool.main(["--var", str(tmp_path), "--log", str(log), "gate-1126", "--only"]) == 0
    assert "3 songs read, 2 passed" in capsys.readouterr().out                                          # (--only: as the page was before)
