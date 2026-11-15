"""The music commands: make, library, ledger."""
import pytest

from freerock import atlas, cli, musiccli
from freerock.composer import core_suite
from freerock.eleven import AllowanceExceeded, Gateway
from freerock.ingest import Made, TrackFailedChecks
from freerock.ledger import Ledger
from freerock.library import Library
from freerock.settings import Settings
from test_library import made_up_track


class StandInGateway:
    async def aclose(self):
        pass


class StandInIngest:
    def __init__(self, library, failure=None):
        self.library, self.failure, self.calls = library, failure, []

    async def core_suite(self, name, *, rock=None, reroll=False):
        self.calls.append((name, rock))
        if self.failure:
            raise self.failure
        profile = atlas.profile_for(name)
        request = core_suite(profile, seed=2, part_bars=atlas.part_bars(profile.bpm))
        mix, layers = made_up_track(request)
        asset = self.library.add(zone=profile.key, set_name="core", request=request, mix=mix, layers=layers,
                                 checks={"failed": [], "parts": {"Wander A": {
                                     "tempo_off_percent": 0.01, "start_to_beat_ms": 1.2, "heard_as": "D minor"}}})
        return Made(asset=asset, first_audio_s=5.8, total_s=11.6, split_s=77.0)


@pytest.fixture
def home(tmp_path, monkeypatch):
    settings = Settings(var_dir=tmp_path)
    monkeypatch.setattr(musiccli, "_settings", lambda: Settings.load(tmp_path))
    library = Library(settings.library_dir)
    made = {}

    def ingest(_settings, failure=None):
        made["ingest"] = StandInIngest(library, made.get("failure"))
        return made["ingest"], StandInGateway()

    monkeypatch.setattr(musiccli, "_ingest", ingest)
    return settings, library, made


def test_make_makes_music_for_a_zone_and_says_what_it_did(home, capsys):
    settings, library, made = home
    assert cli.main(["make", "Duskwood", "--rock", "0.8"]) == 0
    out = capsys.readouterr().out
    assert "Making music for Duskwood: 80 BPM, D minor" in out and "minutes of music" in out
    assert "Wander A  tempo +0.010%" in out
    assert made["ingest"].calls == [("Duskwood", 0.8)]
    assert cli.main(["make", "Westfall"]) == 0 and made["ingest"].calls[-1] == ("Westfall", None)
    library_before = len(library.assets())
    assert library_before == 2
    assert sorted(asset.zone for asset in library.assets()) == ["duskwood", "westfall"]
    # A second time it leaves the zone alone unless told otherwise.
    assert cli.main(["make", "Duskwood"]) == 0
    assert "already has music" in capsys.readouterr().out and len(library.assets()) == 2
    assert cli.main(["make", "Duskwood", "--again"]) == 0 and len(library.assets()) == 3


def test_make_says_why_when_it_cannot(home, capsys):
    settings, library, made = home
    made["failure"] = TrackFailedChecks("duskwood", {"failed": ["Battle is 2.50% off tempo"]})
    assert cli.main(["make", "Duskwood"]) == 1
    assert "not put in the library: Battle is 2.50% off tempo." in capsys.readouterr().err
    made["failure"] = AllowanceExceeded("FreeRock did not make this call (core suite): 3.20 min asked for, 1.00 left of today\'s allowance.")
    assert cli.main(["make", "Duskwood"]) == 1
    assert "today\'s allowance" in capsys.readouterr().err and library.assets() == []


def test_make_warns_about_a_place_it_has_no_profile_for(home, capsys):
    assert cli.main(["make", "The Deadmines"]) == 0
    assert "worked out from its name" in capsys.readouterr().out


def test_library_lists_what_there_is(home, capsys):
    settings, library, made = home
    assert cli.main(["library"]) == 0 and "The library is empty." in capsys.readouterr().out
    cli.main(["make", "Duskwood"])
    library.mark(library.assets()[0].id, loved=True)
    capsys.readouterr()
    assert cli.main(["library"]) == 0
    out = capsys.readouterr().out
    assert "duskwood" in out and "80 BPM" in out and "loved" in out and "1 pieces of music for 1 places" in out


def test_ledger_shows_the_spend_and_the_account(home, capsys, monkeypatch):
    settings, library, made = home
    ledger = Ledger(settings.ledger_path)
    done = ledger.start(kind="music", purpose="core suite", minutes=2.8, zone="duskwood")
    ledger.finish(done, http_status=200)

    async def subscription(self):
        return {"tier": "pro", "character_count": 5220, "character_limit": 781495}

    monkeypatch.setattr(Gateway, "subscription", subscription)
    assert cli.main(["ledger"]) == 0
    out = capsys.readouterr().out
    assert "This month: 2.80 of 300 minutes (about $0.42). Today: 2.80 of 20 minutes." in out
    assert "core suite" in out and "ElevenLabs account: pro plan, 5220 of 781495 credits used." in out


def test_settings_can_be_shown_and_changed(home, capsys):
    settings, library, made = home
    assert cli.main(["settings"]) == 0
    out = capsys.readouterr().out
    assert "monthly_minutes  300" in out and "daily_minutes    20" in out and "rock             0.5" in out
    assert cli.main(["settings", "daily_minutes", "40"]) == 0
    assert "daily_minutes    40" in capsys.readouterr().out
    assert Settings.load(settings.var_dir).daily_minutes == 40 and Settings.load(settings.var_dir).monthly_minutes == 300
    assert cli.main(["settings", "rock", "0.8"]) == 0 and Settings.load(settings.var_dir).rock == 0.8
    capsys.readouterr()
    assert cli.main(["settings", "rock", "3"]) == 1 and "between 0 and 1" in capsys.readouterr().err
    assert cli.main(["settings", "model_id", "1"]) == 1 and "is not a setting" in capsys.readouterr().err
    assert cli.main(["settings", "rock"]) == 1 and "Give a value" in capsys.readouterr().err
    assert Settings.load(settings.var_dir).rock == 0.8


def test_a_settings_file_with_something_wrong_in_it_is_an_error(tmp_path):
    (tmp_path / "settings.json").write_text('{"daily_minutes": "lots"}')
    with pytest.raises(ValueError):
        Settings.load(tmp_path)
    (tmp_path / "settings.json").write_text('{"monthly_minutes": 120, "rock": 0.2}')
    loaded = Settings.load(tmp_path)
    assert loaded.monthly_minutes == 120 and loaded.rock == 0.2 and loaded.daily_minutes == 20
