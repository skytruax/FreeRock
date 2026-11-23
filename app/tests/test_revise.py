"""A song's music sheet revised (tools/revise.py), and a revised sheet kept: what a musician has changed in a song's sheet is what the song is
("remember your music sheets are your core principal and most important asset", 2026-11-18; the standing cycle's old songs,
2026-11-23), so a list that comes to the song again performs the sheet, not a new first draft."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from freerock.studio import build, orchestra, sheet as sheets
from freerock.studio.score import Note, Sheet, Voice

REPO = Path(__file__).resolve().parents[2]
TRACK = "knight/test-song-1/2"


def _tool():
    spec = importlib.util.spec_from_file_location("revise", REPO / "tools" / "revise.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sheet() -> Sheet:
    return Sheet(style="knight", family="test-song-1", take=2, title="Test Song", tempo=100.0, beats=4.0,
                 form=[{"story": "open", "first": 0, "bars": 4, "part": "open"}],
                 parts={"texture": {"harmonica": Voice(notes=[Note(0.0, 4.0, 72, 0.6), Note(4.0, 4.0, 79, 0.6)], instrument="harmonica")},
                        "lead": {"fiddle": Voice(notes=[Note(1.0, 1.0, 69, 0.5)], instrument="fiddle")}},
                 history=[{"revision": 1, "when": "2026-11-20T10:00:00", "by": "the writer", "what": "the first draft", "why": "written"}])


def _staged(var: Path) -> Path:
    folder = var / "studio" / "knight" / "test-song-1" / "2"
    folder.mkdir(parents=True)
    _sheet().save(folder / "sheet.json")
    (folder / "track.json").write_text(json.dumps({"title": "Test Song"}), encoding="utf-8")
    for channel in ("lead", "texture"):
        (folder / (channel + ".flac")).write_bytes(b"as it was: " + channel.encode())
    return folder


RECIPE = """def revise(sheet):
    for note in sheet.parts["texture"]["harmonica"].notes:
        note.loud = 0.4
    return "the pad softer", "the harmonica held it all through"
"""


@pytest.fixture
def var(tmp_path, monkeypatch):
    monkeypatch.setattr(sheets, "VAR", tmp_path)
    return tmp_path


def test_a_first_draft_is_written_again_and_a_revised_sheet_is_what_the_song_is(var):
    assert sheets.revised_of("knight", "test-song-1", 2) is None                  # no sheet
    folder = _staged(var)
    assert sheets.revised_of("knight", "test-song-1", 2) is None                  # a first draft
    sheet = Sheet.load(folder / "sheet.json")
    sheet.revised("a change", "a reason", by="the musician")
    sheet.save(folder / "sheet.json")
    kept = sheets.revised_of("knight", "test-song-1", 2)
    assert kept is not None and kept.revision == 2 and kept.history[-1]["by"] == "the musician"


def test_a_sheet_is_laid_out_as_a_part_chart_whatever_is_marked_on_it():
    """(2026-11-23: the harmonica's bends had been made an effect mark on the 22nd, and the sheet tool, which has a letter for each mark,
    could not be loaded from then on.)"""
    from freerock.studio import score
    sheet = _sheet()
    sheet.parts["texture"]["harmonica"].mark("bend", [(0.0, 0.0), (0.5, -1.0), (1.0, 0.0)])
    shown = sheets.show(sheet)
    assert "Test Song" in shown and "harmonica" in shown and "r1" in shown
    assert set(sheets.SHORT) == set(score.EFFECTS)


def test_a_list_that_comes_to_a_revised_song_performs_its_sheet(var, monkeypatch):
    folder = _staged(var)
    performed = []
    monkeypatch.setattr(build, "perform", lambda sheet: performed.append(sheet) or {"title": sheet.title})
    draft = _sheet()
    written = []
    monkeypatch.setattr(build, "write", lambda fam, take: written.append((fam.name, take)) or draft)
    fam = type("Family", (), {"name": "test-song-1", "character": type("Character", (), {"style": "knight"})})()
    build.stage(fam, 2)
    assert performed == [draft] and written == [("test-song-1", 2)]               # a first draft: written again, as ever
    sheet = Sheet.load(folder / "sheet.json")
    sheet.revised("a change", "a reason", by="the musician")
    sheet.save(folder / "sheet.json")
    build.stage(fam, 2)
    assert written == [("test-song-1", 2)] and performed[1].revision == 2        # the revised sheet, and no new draft written


def test_a_revision_is_said_before_it_is_made_and_dry_changes_nothing(var, tmp_path, monkeypatch, capsys):
    folder, tool = _staged(var), _tool()
    recipe = tmp_path / "softer.py"
    recipe.write_text(RECIPE, encoding="utf-8")
    monkeypatch.setattr(tool.sheets, "perform", lambda sheet: pytest.fail("performed on a dry run"))
    before = (folder / "sheet.json").read_text(encoding="utf-8")
    assert tool.main([TRACK, "--recipe", str(recipe), "--dry"]) == 0
    said = capsys.readouterr().out
    assert "revision 2: the pad softer (the harmonica held it all through)" in said
    assert "texture: harmonica" in said and "2 notes at 0.60 -> 2 notes at 0.40" in said and "fiddle" not in said
    assert (folder / "sheet.json").read_text(encoding="utf-8") == before and not (var / "studio-demo").exists()
    unmoved = tmp_path / "nothing.py"
    unmoved.write_text("def revise(sheet):\n    return 'a', 'b'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed nothing"):
        tool.main([TRACK, "--recipe", str(unmoved), "--dry"])


def test_a_performed_revision_keeps_the_take_of_before_and_can_be_put_back(var, tmp_path, monkeypatch, capsys):
    folder, tool = _staged(var), _tool()
    recipe = tmp_path / "softer.py"
    recipe.write_text(RECIPE, encoding="utf-8")

    def perform(sheet):
        (folder / "lead.flac").write_bytes(b"performed again")          # as the desk does: over the files it has
        sheet.save(folder / "sheet.json")
        return {"title": sheet.title, "seconds": 400, "problems": []}

    monkeypatch.setattr(tool.sheets, "perform", perform)
    monkeypatch.setattr("freerock.studio.reaper.configure", lambda: None)
    assert tool.main([TRACK, "--recipe", str(recipe)]) == 0
    assert "performed:" in capsys.readouterr().out
    kept = var / "studio-demo" / "before-revise" / TRACK
    assert (kept / "lead.flac").read_bytes() == b"as it was: lead" and (folder / "lead.flac").read_bytes() == b"performed again"
    now = Sheet.load(folder / "sheet.json")
    assert now.revision == 2 and {note.loud for note in now.parts["texture"]["harmonica"].notes} == {0.4}
    assert json.loads((kept / "sheet.json").read_text(encoding="utf-8"))["history"][-1]["by"] == "the writer"

    assert tool.main([TRACK, "--back"]) == 0
    back = Sheet.load(folder / "sheet.json")
    assert (folder / "lead.flac").read_bytes() == b"as it was: lead" and back.revision == 1
    assert not list(folder.glob("*.back"))
    with pytest.raises(FileNotFoundError):
        tool.main(["knight/no-such-song-1/1", "--back"])
