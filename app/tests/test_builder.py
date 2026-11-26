"""A style's bucket built again (pieces.build_beside, pieces.swap, tools/fresh_bucket.py): beside the one that plays, a song that
did not change told by the ids it had and its recordings linked, and put in its place in a moment. (2026-11-23, "fix the
builder": a build had the server down for up to two hours, and gave every part a new id, so that a page left open across it
lost the end of its song and asked for parts that were gone.)"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np
import pytest

from freerock import forever, pieces, studio
from test_studio import made_track, tone

REPO = Path(__file__).resolve().parents[2]


def _stage(var: Path, take: int, ago: float = 7200.0, **more) -> Path:
    folder = var / "studio" / "warcraft" / "test-family" / str(take)
    made_track(folder, take=take, **more)
    then = time.time() - ago
    for path in folder.iterdir():
        os.utime(path, (then, then))
    return folder


def _render_again(folder: Path, hz: float = 777.0) -> None:
    """The same take staged now with other audio."""
    meta, parts = studio.read_track(folder)
    studio.write_track(folder, meta, dict(parts, lead=tone(len(parts["lead"]), hz, 0.1)))


def _bucket(var: Path, takes: list[Path]) -> forever.Bucket:
    """The style's bucket as it stands, with these songs in it."""
    bucket = forever.Bucket(var / "buckets", "all", "warcraft", 80, "D minor")
    for folder in takes:
        studio.import_track(bucket, folder)
    return bucket


def _songs(bucket: forever.Bucket) -> dict[str, list[str]]:
    """Each song's pieces, in their order."""
    out: dict[str, dict[int, str]] = {}
    for piece_id, (track, place) in bucket.places().items():
        out.setdefault(track, {})[place] = piece_id
    return {track: [places[place] for place in sorted(places)] for track, places in out.items()}


def _everything(folder: Path) -> dict[str, tuple[int, bytes]]:
    return {str(path.relative_to(folder)): (path.stat().st_ino, path.read_bytes()) for path in sorted(folder.rglob("*")) if path.is_file()}


def test_a_song_put_in_again_unchanged_is_told_by_the_ids_it_had(tmp_path):
    one, two = _stage(tmp_path / "a", 1), _stage(tmp_path / "b", 1)
    first, second = _bucket(tmp_path / "a", [one]), _bucket(tmp_path / "b", [two])
    assert list(first.pieces) == list(second.pieces) and [clip.id for clip in first.clips] == [clip.id for clip in second.clips]
    assert len(set(first.pieces)) == 5 and len({clip.id for clip in first.clips}) == len(first.clips)
    # What it is called and what it is for have no part in it...
    meta = studio.described(two)
    stamp = studio.stamp_of(two, meta)
    assert studio.stamp_of(two, dict(meta, title="Another Name", moods=["desert"], role="town")) == stamp
    # ...and any other audio, cut or level does.
    assert studio.stamp_of(two, dict(meta, level_db=-2.0)) != stamp
    _render_again(two)
    assert studio.stamp_of(two, meta) != stamp
    other = _bucket(tmp_path / "c", [two])
    assert not set(other.pieces) & set(first.pieces) and not {clip.id for clip in other.clips} & {clip.id for clip in first.clips}


def test_a_build_takes_what_did_not_change_and_leaves_the_bucket_that_plays_alone(tmp_path, monkeypatch):
    same, changed = _stage(tmp_path, 1), _stage(tmp_path, 2)
    old = _bucket(tmp_path, [same, changed])
    was = _songs(old)
    files = _everything(old.folder)
    # One song is described anew, one made again, one is new.
    meta = studio.described(same)
    (same / "track.json").write_text(json.dumps(dict(meta, title="Renamed", moods=["frozen"])), encoding="utf-8")
    _render_again(changed)
    _stage(tmp_path, 3)
    read: list[str] = []
    saves: list[int] = []
    real = studio.read_track
    monkeypatch.setattr(studio, "read_track", lambda folder: read.append(folder.name) or real(folder))
    real_save = forever.Bucket._save
    monkeypatch.setattr(forever.Bucket, "_save", lambda self: saves.append(1) or real_save(self))

    new, done = pieces.build_beside(tmp_path, "warcraft")

    assert (done["put"], done["taken"], done["wrong"]) == (3, 1, []) and sorted(read) == ["2", "3"]
    assert len(saves) <= 3, "the index was written %d times" % len(saves)
    assert _everything(old.folder) == files, "the bucket that plays was touched"
    now = _songs(new)
    track = "warcraft/test-family/%d"
    assert now[track % 1] == was[track % 1] and now[track % 2] != was[track % 2] and len(now[track % 3]) == 5
    kept = {clip.id for clip in old.clips if clip.piece in was[track % 1]}
    assert kept and kept == {clip.id for clip in new.clips if clip.piece in now[track % 1]}
    for clip_id in kept:
        assert new._file(clip_id).stat().st_ino == old._file(clip_id).stat().st_ino, "a recording was made again"
    again = forever.Bucket(new.root, "all", "warcraft", 80, "D minor")          # as the server will read it
    first = again.pieces[now[track % 1][0]]
    assert first["title"] == "Renamed (open)" and first["moods"] == ["frozen"] and first["next"] == now[track % 1][1]
    assert [again.pieces[each]["place"] for each in now[track % 1]] == list(range(5))
    before = {(clip.channel, clip.piece): clip for clip in old.clips}
    for clip in again.clips:
        if clip.piece in now[track % 1]:
            had = before[(clip.channel, clip.piece)]
            assert (clip.frames, clip.post, clip.gain_db, clip.order) == (had.frames, had.post, had.gain_db, had.order)
            assert np.array_equal(again.audio(clip.id), old.audio(had.id))
    assert new.version > old.version


def _sheet(folder: Path, parts: dict[str, list[float]], first: int = 8, bars: int = 16) -> None:
    """A music sheet with a theme at bar `first`, and the lead channel's parts by the beats (four to a bar) their notes begin at."""
    notes = {name: {"notes": [[at, 1.0, 64, 0.8] for at in starts]} for name, starts in parts.items()}
    (folder / "sheet.json").write_text(json.dumps({"beats": 4.0, "form": [
        {"story": "open", "first": 0, "bars": first}, {"story": "theme", "first": first, "bars": bars}], "parts": {"lead": notes}}), encoding="utf-8")


def test_a_song_says_which_instrument_leads_it(tmp_path):
    """(2026-11-23, "make sure to switch up the instruments from song to song so theres variety".)"""
    folder = tmp_path / "a"
    folder.mkdir()
    assert studio.lead_of(folder) == ""                         # a song with no sheet (a Warcraft take of before the sheets)
    inside = [32.0 + beat for beat in range(8)]
    _sheet(folder, {"fiddle": inside, "lead guitar": inside[:3], "lead guitar solo": inside * 4, "horns": [4.0, 5.0, 6.0]})
    assert studio.lead_of(folder) == "fiddle"                   # the most notes in the first theme, a solo not counted
    _sheet(folder, {"violins slow": inside})
    assert studio.lead_of(folder) == "violins"                  # a section and its player are one voice
    _sheet(folder, {"fiddle": [], "whistle": [2.0, 3.0]})
    assert studio.lead_of(folder) == "whistle"                  # a theme without a tune: the song's
    _sheet(folder, {"fiddle": []})
    assert studio.lead_of(folder) == ""


def test_the_player_is_told_which_instrument_leads_a_song_and_a_bucket_of_before_says_nothing(tmp_path):
    folder = _stage(tmp_path, 1)
    old = _bucket(tmp_path, [folder])
    assert {piece["lead"] for piece in old.describe()["pieces"].values()} == {""}       # no sheet yet
    for piece in old.pieces.values():
        del piece["lead"]                                        # a bucket of before
    old._save()
    assert {piece["lead"] for piece in old.describe()["pieces"].values()} == {""}
    _sheet(folder, {"fiddle": [40.0, 41.0]})

    new, done = pieces.build_beside(tmp_path, "warcraft")

    assert (done["put"], done["taken"]) == (1, 1)                 # its sheet has come since: told anew, its recordings as they were
    assert {piece["lead"] for piece in new.describe()["pieces"].values()} == {"fiddle"}


def test_pieces_cut_before_stamps_were_kept_are_taken_only_if_nothing_was_staged_since(tmp_path, monkeypatch):
    settled, fresh = _stage(tmp_path, 1), _stage(tmp_path, 2)
    with monkeypatch.context() as patched:
        patched.setattr(studio, "stamp_of", lambda folder, meta: "")              # as builds before 2026-11-23 left it: ids drawn, no stamp
        old = _bucket(tmp_path, [settled, fresh])
    assert all(len(piece_id) == 10 and not piece["stamp"] for piece_id, piece in old.pieces.items())
    os.utime(fresh / "lead.flac")                                     # staged again about when it was cut: not to be relied on
    new, done = pieces.build_beside(tmp_path, "warcraft")
    assert (done["put"], done["taken"]) == (2, 1)
    assert new.linked == set(_songs(new)["warcraft/test-family/1"])
    assert all(piece["stamp"] for piece in new.pieces.values())
    for clip in new.clips:
        if clip.piece in new.linked:
            assert os.stat(new._file(clip.id)).st_nlink == 2
    assert not set(new.pieces) & set(old.pieces)                      # (the old ids were drawn; from here on they stay)
    pieces.swap(tmp_path, "warcraft")
    third, done = pieces.build_beside(tmp_path, "warcraft")
    assert done["taken"] == 2 and set(third.pieces) == set(new.pieces)


def test_a_song_with_a_recording_missing_is_cut_again_and_one_that_cannot_be_is_said(tmp_path):
    one, two = _stage(tmp_path, 1), _stage(tmp_path, 2)
    old = _bucket(tmp_path, [one, two])
    old._file(old.clips[0].id).unlink()
    (two / "lead.flac").write_bytes(b"not a recording")
    new, done = pieces.build_beside(tmp_path, "warcraft")
    assert (done["put"], done["taken"]) == (1, 0)
    assert [(folder.name, problem != "") for folder, problem in done["wrong"]] == [("2", True)]
    assert " (raised at " in done["wrong"][0][1] and ".py:" in done["wrong"][0][1]          # where it was raised, not its kind and words alone
    assert len(new.pieces) == 5 and all(new._file(clip.id).is_file() for clip in new.clips)


def test_a_song_that_is_resting_is_staged_and_not_put_in(tmp_path):
    # (2026-11-24: House was heard as sweet still; its sweetest songs rest, by a list, and a line taken out brings its song back.)
    one, two = _stage(tmp_path, 1), _stage(tmp_path, 2)
    _bucket(tmp_path, [one, two])
    assert pieces.resting(tmp_path, "warcraft") == {}
    rest = tmp_path / "studio" / "warcraft" / "resting.txt"
    rest.write_text("# what rests, and why\n\ntest-family/2 sweet: a major key, bells\n", encoding="utf-8")
    assert pieces.resting(tmp_path, "warcraft") == {"test-family/2": "sweet: a major key, bells"}
    new, done = pieces.build_beside(tmp_path, "warcraft")
    assert (done["put"], done["taken"], done["wrong"]) == (1, 1, []) and set(_songs(new)) == {"warcraft/test-family/1"}
    assert studio.staged(tmp_path, "warcraft") == [one, two]          # it is staged all the same
    rest.write_text("", encoding="utf-8")
    new, done = pieces.build_beside(tmp_path, "warcraft")
    assert done["put"] == 2 and set(_songs(new)) == {"warcraft/test-family/1", "warcraft/test-family/2"}
    rest.write_text("test-family 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="family and take"):
        pieces.build_beside(tmp_path, "warcraft")


def test_a_build_keeps_what_was_played_loved_and_banned_even_while_it_was_building(tmp_path):
    takes = [_stage(tmp_path, 1), _stage(tmp_path, 2)]
    _bucket(tmp_path, takes)
    server = forever.Buckets(tmp_path / "buckets").home("warcraft", None)       # as the server has it, with the play book
    server.played([server.clips[0].id])
    server.mark([server.clips[-1].id], banned=True)
    new, done = pieces.build_beside(tmp_path, "warcraft")
    assert done["carried"] >= 2
    server.played([server.clips[1].id])                               # heard between the build and the swap
    pieces.swap(tmp_path, "warcraft")
    after = forever.Buckets(tmp_path / "buckets").home("warcraft", None)
    by_id = {clip.id: clip for clip in after.clips}
    assert by_id[server.clips[0].id].plays == 1 and by_id[server.clips[1].id].plays == 1
    assert by_id[server.clips[-1].id].banned and after.pieces[server.clips[-1].piece]["banned"]


def test_a_swap_takes_the_place_of_the_bucket_and_can_be_taken_back(tmp_path):
    one = _stage(tmp_path, 1)
    old = _bucket(tmp_path, [one])
    with pytest.raises(ValueError, match="has been built beside"):
        pieces.swap(tmp_path, "warcraft")
    _stage(tmp_path, 2)
    new, _ = pieces.build_beside(tmp_path, "warcraft")
    kept = pieces.swap(tmp_path, "warcraft")
    assert len(pieces.standing(tmp_path, "warcraft").pieces) == 10 and not new.folder.exists()
    assert len(json.loads((kept / "bucket.json").read_text(encoding="utf-8"))["pieces"]) == 5
    assert pieces.swap_back(tmp_path, "warcraft") == new.folder
    assert set(pieces.standing(tmp_path, "warcraft").pieces) == set(old.pieces)
    pieces.swap(tmp_path, "warcraft")
    assert len(pieces.standing(tmp_path, "warcraft").pieces) == 10


def test_the_buckets_may_be_on_another_drive_through_a_link(tmp_path):
    # (As they are: var/buckets is a link to the assets' drive, and a recording cannot be linked from one drive to another.)
    var, drive = tmp_path / "var", tmp_path / "drive" / "assets"
    drive.mkdir(parents=True)
    var.mkdir()
    (drive / "buckets").mkdir()
    (var / "buckets").symlink_to(drive / "buckets")
    _bucket(var, [_stage(var, 1)])
    new, done = pieces.build_beside(var, "warcraft")
    assert done["taken"] == 1 and new.folder == drive / "buckets-next" / "warcraft" / "all"
    assert pieces.swap(var, "warcraft") == drive / "buckets-before" / "warcraft" / "all"
    assert (var / "buckets").is_symlink() and len(pieces.standing(var, "warcraft").pieces) == 5
    assert (var / "plays.sqlite3").is_file() and not (drive / "plays.sqlite3").exists(), "the play book was begun beside the wrong folder"


def test_a_page_playing_a_song_from_before_the_build_finds_the_rest_of_it(tmp_path):
    one = _stage(tmp_path, 1)
    old = _bucket(tmp_path, [one])
    rest = old.samples(old.clips[3].id)
    _render_again(one)                                                # its parts have other ids now
    pieces.build_beside(tmp_path, "warcraft")
    pieces.swap(tmp_path, "warcraft")
    now = forever.Buckets(tmp_path / "buckets").home("warcraft", None)
    assert old.clips[3].id not in {clip.id for clip in now.clips}
    assert now.samples(old.clips[3].id) == rest
    for unknown in ("0123456789abcdef", "../../../../secret", ""):
        with pytest.raises(KeyError):
            now.samples(unknown)


def test_a_build_that_fails_leaves_nothing_to_swap_in(tmp_path, monkeypatch):
    _bucket(tmp_path, [_stage(tmp_path, 1)])
    with monkeypatch.context() as patched:
        patched.setattr(pieces, "restore_marks", lambda *_: (_ for _ in ()).throw(RuntimeError("the disk is full")))
        patched.setattr(pieces, "add_staged", lambda *_: (_ for _ in ()).throw(RuntimeError("the disk is full")))
        with pytest.raises(RuntimeError):
            pieces.build_beside(tmp_path, "warcraft")
    with pytest.raises(ValueError, match="has been built beside"):
        pieces.swap(tmp_path, "warcraft")
    assert pieces.build_beside(tmp_path, "warcraft")[1]["put"] == 1, "what it left was in the way of the next"


def _tool(monkeypatch, var: Path, up: bool):
    spec = importlib.util.spec_from_file_location("fresh_bucket", REPO / "tools" / "fresh_bucket.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "VAR", var)
    monkeypatch.setattr(module.pieces, "server_is_up", lambda port: up)
    return module


def test_the_command_builds_with_the_server_up_and_swaps_only_with_it_stopped(tmp_path, monkeypatch, capsys):
    _bucket(tmp_path, [_stage(tmp_path, 1), _stage(tmp_path, 2)])
    up = _tool(monkeypatch, tmp_path, up=True)
    assert up.main(["warcraft", "--beside"]) == 0
    said = capsys.readouterr().out
    assert "2 tracks put in; the bucket now has 10 pieces in 2 tracks" in said and "2 of them as they were" in said
    assert up.main(["warcraft", "--swap"]) == 1 and "stop it first" in capsys.readouterr().out
    down = _tool(monkeypatch, tmp_path, up=False)
    assert down.main(["warcraft", "--swap"]) == 0 and "is in its place" in capsys.readouterr().out
    assert down.main(["warcraft", "--swap-back"]) == 0 and "is back in its place" in capsys.readouterr().out
    assert down.main(["--swap"]) == 2
    shutil.rmtree(tmp_path / "studio" / "warcraft" / "test-family" / "2")
    (tmp_path / "studio" / "warcraft" / "test-family" / "1" / "lead.flac").write_bytes(b"spoilt")
    assert up.main(["warcraft", "--beside"]) == 1 and "NOT put in" in capsys.readouterr().out


def test_a_server_that_does_not_answer_in_time_is_up(monkeypatch):
    """(2026-11-26, the audit: a timeout was read as no server, and a bucket could be swapped under one that was only slow, which has the buckets in memory.)"""
    import socket

    def slow(*_, **__):
        raise socket.timeout("timed out")

    def refused(*_, **__):
        raise ConnectionRefusedError("nobody there")

    monkeypatch.setattr(socket, "create_connection", slow)
    assert pieces.server_is_up(8765) is True
    monkeypatch.setattr(socket, "create_connection", refused)
    assert pieces.server_is_up(8765) is False
