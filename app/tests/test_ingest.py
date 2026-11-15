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


def stand_in_splitter(leak_db=-40.0):
    def splitter(mix, rate):
        return Layers(bed=mix * 0.5, drums=mix * 0.3, bass=mix * 0.2, rate=rate,
                      vocal_leak_db=leak_db, seconds=0.01, model="stand-in")
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
    assert gateway.ledger.month_minutes() == pytest.approx(2.8), "ElevenLabs made it, so it counts"
    await gateway.aclose()


async def test_singing_and_short_tracks_are_refused(tmp_path):
    sung, library, gateway = make(tmp_path / "a", [], splitter=stand_in_splitter(leak_db=-12.0))
    with pytest.raises(TrackFailedChecks) as failure:
        await sung.core_suite("Westfall")
    assert "singing" in str(failure.value) and library.assets() == []
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
