"""Making new music for a zone, against a stand-in for ElevenLabs and a stand-in for the splitter."""
import json
import random

import httpx
import numpy as np
import pytest

from freerock import analysis
from freerock.audio import float_to_pcm16
from freerock.eleven import AllowanceExceeded, Gateway
from freerock.ingest import Ingest, TrackFailedChecks
from freerock.ledger import Ledger
from freerock.library import Library
from freerock.settings import Settings
from freerock.stems import Layers

RATE = 48000


def stand_in_music(plan, tempo_factor=1.0, seconds_short=0.0, seed=8):
    """Music that fits a request: a click on every beat at the tempo it asks for, over a held
    chord on its key note. `tempo_factor` plays it faster or slower than asked."""
    rng = np.random.default_rng(seed)
    first = plan["chunks"][0]["positive_styles"]
    bpm = int(first[0].split()[0]) * tempo_factor
    tonic = analysis.parse_tonic(first[1])
    seconds = sum(chunk["duration_ms"] for chunk in plan["chunks"]) / 1000.0 - seconds_short
    frames = int(round(seconds * RATE))
    t = np.arange(frames) / RATE
    root = 220.0 * 2 ** ((tonic - 9) / 12.0)
    audio = sum(np.sin(2 * np.pi * root * ratio * t) for ratio in (1.0, 1.5, 2.0)).astype(np.float32) * 0.05
    burst = (rng.normal(0, 1, 480) * np.exp(-np.arange(480) / 80.0)).astype(np.float32) * 0.5
    beat = 0
    while True:
        start = int(round(beat * 60.0 / bpm * RATE))
        if start + len(burst) >= frames:
            break
        audio[start:start + len(burst)] += burst
        beat += 1
    return np.stack([audio, audio], axis=1)


def stand_in_splitter(leak_db=-40.0, words_db=-70.0):
    def splitter(mix, rate):
        return Layers(bed=mix * 0.5, drums=mix * 0.3, bass=mix * 0.2, rate=rate,
                      vocal_leak_db=leak_db, seconds=0.01, model="stand-in", vocal_words_db=words_db)
    return splitter


def make(tmp_path, seen, splitter=None, **music):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        audio = stand_in_music(body["composition_plan"], **music)
        return httpx.Response(200, content=float_to_pcm16(audio), headers={"song-id": "song-%d" % len(seen)})

    settings = Settings(var_dir=tmp_path)
    gateway = Gateway(settings, Ledger(settings.ledger_path),
                      client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), key="sk_test")
    library = Library(tmp_path / "library")
    return Ingest(gateway, library, splitter=splitter or stand_in_splitter(), rng=random.Random(1)), library, gateway


async def test_a_zone_gets_its_core_suite(tmp_path):
    seen = []
    ingest, library, gateway = make(tmp_path, seen)
    made = await ingest.core_suite("Elwynn Forest")
    asset = made.asset
    assert asset.zone == "elwynn-forest" and asset.set == "core" and asset.song_id == "song-1"
    assert asset.bpm == 120 and asset.tonic == "G mixolydian" and asset.minutes == pytest.approx(2.8)
    assert [s.name for s in asset.sections] == ["Arrival", "Wander A", "Wander B", "Battle", "Ember", "Depths"]
    assert library.assets("elwynn-forest")[0].id == asset.id
    assert asset.checks["failed"] == [] and asset.checks["parts"]["Battle"]["key_agrees"]
    assert abs(asset.checks["parts"]["Wander A"]["tempo_off_percent"]) < 0.1

    body = seen[0]
    assert body["model_id"] == "music_v2_5" and body["store_for_inpainting"] is True
    assert isinstance(body["seed"], int) and "fiddle" in body["composition_plan"]["chunks"][0]["positive_styles"]
    row = gateway.ledger.rows()[0]
    assert row["purpose"] == "core suite" and row["zone"] == "elwynn-forest" and row["status"] == "done"
    assert row["minutes"] == pytest.approx(2.8)
    await gateway.aclose()


async def test_a_slow_zone_gets_shorter_parts(tmp_path):
    ingest, library, gateway = make(tmp_path, [])
    asset = (await ingest.core_suite("Duskwood")).asset
    assert asset.bpm == 80 and [len(s.cells) for s in asset.sections] == [1, 3, 3, 3, 3, 3]
    assert asset.minutes == pytest.approx(3.2)
    await gateway.aclose()


async def test_music_off_tempo_is_not_stored_but_is_still_counted(tmp_path):
    ingest, library, gateway = make(tmp_path, [], tempo_factor=1.025)
    with pytest.raises(TrackFailedChecks) as failure:
        await ingest.core_suite("Elwynn Forest")
    assert "off tempo" in str(failure.value) and failure.value.zone == "elwynn-forest"
    assert library.assets() == []
    # It is kept outside the library, with what was asked for and what was measured.
    kept = failure.value.kept
    assert kept.parent == tmp_path / "rejected" and str(kept) in str(failure.value)
    assert (kept / "mix.flac").stat().st_size > 100_000
    noted = json.loads((kept / "checks.json").read_text())
    assert noted["bpm"] == 120 and noted["song_id"] == "song-1" and noted["checks"]["failed"]
    assert [part["name"] for part in noted["parts"]][:2] == ["Arrival", "Wander A"]
    assert gateway.ledger.month_minutes() == pytest.approx(2.8), "ElevenLabs made it, so it counts"
    await gateway.aclose()


async def test_singing_and_short_tracks_are_refused(tmp_path):
    sung, library, gateway = make(tmp_path / "a", [], splitter=stand_in_splitter(leak_db=-15.0, words_db=-30.0))
    with pytest.raises(TrackFailedChecks) as failure:
        await sung.core_suite("Westfall")
    assert "singing" in str(failure.value) and library.assets() == []
    assert failure.value.checks["vocal_leak_db"] == -15.0 and failure.value.checks["vocal_words_db"] == -30.0
    await gateway.aclose()

    # So loud that it is a large part of the track: turned away whatever it is made of.
    loud, library, gateway = make(tmp_path / "c", [], splitter=stand_in_splitter(leak_db=-8.0, words_db=-60.0))
    with pytest.raises(TrackFailedChecks) as failure:
        await loud.core_suite("Westfall")
    assert "singing" in str(failure.value)
    await gateway.aclose()

    short, library, gateway = make(tmp_path / "b", [], seconds_short=2.0)
    with pytest.raises(TrackFailedChecks) as failure:
        await short.core_suite("Westfall")
    assert "asked for" in str(failure.value)
    await gateway.aclose()


async def test_a_later_set_is_tied_to_the_core_suite(tmp_path):
    seen = []
    ingest, library, gateway = make(tmp_path, seen)
    core = (await ingest.core_suite("Elwynn Forest")).asset
    second = (await ingest.later_set(core, "Elwynn Forest", "second")).asset
    assert second.set == "second" and second.zone == "elwynn-forest"
    assert [s.name for s in second.sections] == ["Wander C", "Wander D", "Night", "Storm", "Battle B", "Boss"]
    for chunk in seen[1]["composition_plan"]["chunks"]:
        assert chunk["conditioning_ref"] == {"song_id": "song-1", "range": {"start_ms": 8000, "end_ms": 38000}}
    assert len(library.assets("elwynn-forest")) == 2
    fresh = (await ingest.later_set(core, "Elwynn Forest", "fresh")).asset
    assert fresh.set == "fresh" and fresh.sections[0].name == "Wander E"
    with pytest.raises(ValueError):
        await ingest.later_set(core, "Elwynn Forest", "third")
    await gateway.aclose()


async def test_nothing_is_made_past_the_allowance(tmp_path):
    seen = []
    ingest, library, gateway = make(tmp_path, seen)
    gateway.settings.daily_minutes = 3.0
    await ingest.core_suite("Elwynn Forest")
    with pytest.raises(AllowanceExceeded):
        await ingest.core_suite("Westfall")
    assert len(seen) == 1 and len(library.assets()) == 1
    await gateway.aclose()


async def test_a_whistle_solo_is_not_taken_for_singing(tmp_path):
    """The separator puts a whistle or a flute playing alone into its vocals layer. What was
    measured on the first tin whistle: -21 dB overall, but -52 dB where sung words would be."""
    whistle, library, gateway = make(tmp_path, [], splitter=stand_in_splitter(leak_db=-21.0, words_db=-52.0))
    made = await whistle.core_suite("Westfall")
    assert made.asset.checks["vocal_leak_db"] == -21.0 and made.asset.checks["vocal_words_db"] == -52.0
    assert [asset.id for asset in library.assets("westfall")] == [made.asset.id]
    await gateway.aclose()


async def test_a_kept_track_can_be_adopted_once_it_passes(tmp_path):
    # Rejected for singing by one splitter; looked at again with another, it passes and is stored.
    strict, library, gateway = make(tmp_path, [], splitter=stand_in_splitter(leak_db=-15.0, words_db=-30.0))
    with pytest.raises(TrackFailedChecks) as failure:
        await strict.core_suite("Westfall")
    kept = failure.value.kept
    with pytest.raises(TrackFailedChecks):
        await strict.adopt(kept)                               # still fails by the same measure
    lenient = Ingest(gateway, library, splitter=stand_in_splitter())
    made = await lenient.adopt(kept)
    assert made.asset.zone == "westfall" and made.asset.song_id == "song-1" and made.asset.bpm == 96
    assert [asset.id for asset in library.assets("westfall")] == [made.asset.id]
    assert gateway.ledger.month_minutes() == pytest.approx(3.5), "adopting must not cost anything more"
    await gateway.aclose()


async def test_new_music_uses_the_rock_setting_unless_told_otherwise(tmp_path):
    seen = []
    ingest, library, gateway = make(tmp_path, seen)
    gateway.settings.rock = 0.9
    await ingest.core_suite("Elwynn Forest")
    assert "crunchy rhythm guitars, the riff played with swagger" in seen[0]["composition_plan"]["chunks"][1]["positive_styles"]
    await ingest.core_suite("Westfall", rock=0.1)
    assert "clean chiming electric guitars, the riff played gently" in seen[1]["composition_plan"]["chunks"][1]["positive_styles"]
    await gateway.aclose()
