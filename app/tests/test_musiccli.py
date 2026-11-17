"""The music commands: the settings, and the written pieces in a style's bucket."""
import json

import numpy as np
import pytest
import soundfile

from freerock import cli, forever, musiccli, pieces, studio
from freerock.settings import Settings

RATE = forever.RATE


@pytest.fixture
def var(tmp_path, monkeypatch):
    """A folder of FreeRock's own for the commands, and a server that is not running."""
    monkeypatch.setattr(musiccli, "_settings", lambda: Settings.load(tmp_path))
    monkeypatch.setattr(pieces, "server_is_up", lambda port: False)
    return tmp_path


# --- the settings -----------------------------------------------------------------------------------

def test_settings_can_be_shown_and_changed(var, capsys):
    assert cli.main(["settings"]) == 0
    out = capsys.readouterr().out
    for line in ("rest_every_minutes  6", "rest_seconds        60", "genre               knight"):
        assert line in out
    assert cli.main(["settings", "rest_seconds", "40"]) == 0
    assert "rest_seconds        40" in capsys.readouterr().out
    assert Settings.load(var).rest_seconds == 40 and Settings.load(var).rest_every_minutes == 6
    assert cli.main(["settings", "rest_every_minutes", "0"]) == 0          # no moments of silence
    assert cli.main(["settings", "genre", "warcraft"]) == 0
    assert cli.main(["settings", "pieces", "off"]) == 1 and "is not a setting" in capsys.readouterr().err
    again = Settings.load(var)
    assert (again.rest_every_minutes, again.rest_seconds, again.genre) == (0, 40, "warcraft")
    capsys.readouterr()
    assert cli.main(["settings", "rest_seconds", "-3"]) == 1 and "less than nothing" in capsys.readouterr().err
    assert cli.main(["settings", "genre", "polka"]) == 1 and "genre must be one of" in capsys.readouterr().err
    assert cli.main(["settings", "daily_minutes", "40"]) == 1 and "is not a setting" in capsys.readouterr().err
    assert cli.main(["settings", "rest_seconds"]) == 1 and "Give a value" in capsys.readouterr().err
    assert Settings.load(var).rest_seconds == 40


def test_a_settings_file_with_something_wrong_in_it_is_an_error(tmp_path):
    (tmp_path / "settings.json").write_text('{"rest_seconds": "lots"}')
    with pytest.raises(ValueError):
        Settings.load(tmp_path)
    (tmp_path / "settings.json").write_text('{"rest_seconds": 20, "genre": "trance"}')
    with pytest.raises(ValueError):
        Settings.load(tmp_path)


def test_a_settings_file_written_for_buying_and_for_the_songs_is_read_without_them(tmp_path):
    (tmp_path / "settings.json").write_text('{"monthly_minutes": 100000.0, "daily_minutes": 100000.0, "mode": "songs", '
                                            '"rock": 0.2, "hours_per_month": 60, "pieces": "on", "genre": "warcraft"}')
    loaded = Settings.load(tmp_path)
    assert loaded.genre == "warcraft"
    loaded.save()
    assert json.loads((tmp_path / "settings.json").read_text()) == {"genre": "warcraft"}


# --- the written pieces -----------------------------------------------------------------------------

def staged_track(var, family="haunted-01", take=1, *, bars=(2, 3), post_s=1.0, hz=220.0, quiet_drums_in=None):
    """A tiny staged track: two parts of a story at two-second bars, a tone for each channel."""
    bar = 2 * RATE
    frames = sum(bars) * bar + int(post_s * RATE)
    time = np.arange(frames) / RATE
    parts = {}
    for index, channel in enumerate(("texture", "lead", "drums")):
        tone = 0.2 * np.sin(2 * np.pi * hz * (index + 1) * time).astype(np.float32)
        if channel == "drums" and quiet_drums_in == 0:
            tone[:bars[0] * bar] = 0.0
        parts[channel] = np.stack([tone, tone], axis=1)
    meta = {"style": "warcraft", "family": family, "take": take, "title": "The Long Dark", "tempo": 120, "beats": 4,
            "bar_frames": bar, "tonic": "D minor", "moods": ["haunted"], "role": "wander", "serves": [0, 1], "light": False,
            "sections": [{"story": "open", "bars": bars[0]}, {"story": "moment", "bars": bars[1]}],
            "floor": {"moment": {"drums": 0.7}}, "follow": {}, "post_s": post_s, "credit": "written here", "seed": 5}
    studio.write_track(studio.stage_root(var, "warcraft") / family / str(take), meta, parts)
    return meta, parts


def test_staged_tracks_are_put_in_the_styles_bucket_once(var, capsys):
    staged_track(var, "haunted-01", 1, quiet_drums_in=0)
    staged_track(var, "haunted-01", 2, hz=330.0)
    # The style has no bucket yet, so one is begun in a place; after that the style has its bucket.
    assert cli.main(["pieces", "add", "warcraft"]) == 1 and "has no bucket yet" in capsys.readouterr().err
    assert cli.main(["pieces", "add", "warcraft", "--zone", "Duskwood"]) == 0
    out = capsys.readouterr().out
    assert "added     haunted-01/1" in out and "added     haunted-01/2" in out
    assert "2 staged tracks for Warcraft: 2 put in warcraft/duskwood now, 0 were there already." in out
    assert "4 written pieces in 2 tracks" in out and "haunted 4" in out and "1 families" in out
    bucket = forever.Bucket(var / "buckets", "duskwood", "warcraft", 80, "D minor")
    first = [piece for piece in bucket.pieces.values() if piece["track"] == "warcraft/haunted-01/1"]
    opening, moment = sorted(first, key=lambda piece: piece["story"] != "open")
    assert (opening["story"], moment["story"], moment["floor"], opening["floor"]) == ("open", "moment", {"drums": 0.7}, {})
    assert opening["next"] in bucket.pieces and bucket.pieces[opening["next"]] is moment
    assert opening["family"] == moment["family"] == "warcraft/haunted-01"
    # The drums are silent in the opening of the first take, so they have no part in that piece.
    channels = lambda piece: {clip.channel for clip in bucket.clips if bucket.pieces[clip.piece] is piece}
    assert channels(opening) == {"texture", "lead"} and channels(moment) == {"texture", "lead", "drums"}
    # One gain for the track, and each piece's recording is followed by what the track went on to.
    assert len({clip.gain_db for clip in bucket.clips if bucket.pieces[clip.piece] in first}) == 1
    lead = next(clip for clip in bucket.clips if bucket.pieces[clip.piece] is opening and clip.channel == "lead")
    assert (lead.frames, lead.post) == (2 * 2 * RATE, int(forever.POST_S * RATE)), "six seconds of the seven that follow"
    # A second time, nothing is added.
    assert cli.main(["pieces", "add", "warcraft"]) == 0
    assert "0 put in warcraft/duskwood now, 2 were there already" in capsys.readouterr().out
    assert len(forever.Bucket(var / "buckets", "duskwood", "warcraft", 80, "D minor").pieces) == 4
    # The list says the same, and taking a take out leaves the other.
    assert cli.main(["pieces", "list", "warcraft"]) == 0
    assert "4 written pieces in 2 tracks" in capsys.readouterr().out
    assert cli.main(["pieces", "drop", "warcraft", "warcraft/haunted-01/1"]) == 0
    assert "2 pieces whose source begins with 'warcraft/haunted-01/1' taken out" in capsys.readouterr().out


def test_a_staged_track_that_is_not_fit_is_named_and_the_rest_go_in(var, capsys):
    staged_track(var, "haunted-01", 1)
    staged_track(var, "haunted-02", 1)
    folder = studio.stage_root(var, "warcraft") / "haunted-01" / "1"
    audio, _ = soundfile.read(str(folder / "lead.flac"), dtype="float32", always_2d=True)
    soundfile.write(str(folder / "lead.flac"), audio, 44100, format="FLAC", subtype="PCM_24")      # the wrong rate
    assert cli.main(["pieces", "add", "warcraft", "--zone", "Duskwood"]) == 1
    said = capsys.readouterr()
    assert "NOT PUT IN haunted-01/1" in said.err and "44100" in said.err
    assert "1 put in warcraft/duskwood now" in said.out and "1 could not be put in" in said.out


def test_nothing_is_written_while_the_server_runs_and_a_style_needs_a_bucket(var, monkeypatch, capsys):
    assert cli.main(["pieces", "list", "house"]) == 1
    assert "has no bucket yet" in capsys.readouterr().err
    monkeypatch.setattr(pieces, "server_is_up", lambda port: True)
    assert cli.main(["pieces", "drop", "knight", "knight/", "--zone", "Duskwood"]) == 1
    assert cli.main(["pieces", "add", "knight", "--zone", "Duskwood"]) == 1
    assert capsys.readouterr().err.count("Stop it first") == 2
    assert cli.main(["pieces", "list", "knight", "--zone", "Duskwood"]) == 0, "listing writes nothing, so it may be done at any time"
    # A style with no bucket can be given one, begun in a place.
    monkeypatch.setattr(pieces, "server_is_up", lambda port: False)
    assert cli.main(["pieces", "add", "house", "--zone", "Elwynn Forest"]) == 0
    assert "0 staged tracks for Progressive House" in capsys.readouterr().out
