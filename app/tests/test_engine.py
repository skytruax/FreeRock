"""The player's audio engine, rendered offline in headless Chrome and measured.

tests/web/engine_test.html runs the real engine.js with made-up music whose every sample is
known and reports numbers; the tests here hold those numbers against pass lines. Skipped where
Chrome is not installed.
"""
import asyncio
import shutil
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "freerock" / "web" / "player" / "engine.js"
PAGE = HERE / "web" / "engine_test.html"
CHROME = next((path for path in (shutil.which(name) for name in
                                 ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"))
               if path), None)

pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed on this machine")

_results = None


async def render_once(tmp_path_factory):
    """Runs the test page once for the whole file; every test reads from the same results."""
    global _results
    if _results is not None:
        return _results
    finished = asyncio.Event()
    received = {}

    async def engine_js(request):
        return web.FileResponse(ENGINE)

    async def page(request):
        return web.FileResponse(PAGE)

    async def done(request):
        received["results"] = await request.json()
        finished.set()
        return web.Response(text="ok")

    app = web.Application(client_max_size=16 * 1024 * 1024)
    app.router.add_get("/engine.js", engine_js)
    app.router.add_get("/test.html", page)
    app.router.add_post("/done", done)
    server = TestServer(app)
    await server.start_server()
    profile = tmp_path_factory.mktemp("chrome")
    # Chrome is left running until the page hands its results back: rendering audio offline
    # happens outside the page's own clock, so there is no "page finished loading" to wait for.
    process = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=%s" % profile,
        str(server.make_url("/test.html")),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    try:
        await asyncio.wait_for(finished.wait(), timeout=240)
    except asyncio.TimeoutError:
        process.terminate()
        _, err = await process.communicate()
        raise RuntimeError("The engine test page gave no results in four minutes.\nChrome said: %s"
                           % err.decode("utf-8", "replace")[-2000:])
    finally:
        if process.returncode is None:
            process.terminate()
            await process.wait()
        await server.close()
    _results = received["results"]
    return _results


@pytest.fixture
async def results(tmp_path_factory):
    return await render_once(tmp_path_factory)


def of(results, name):
    result = results[name]
    assert "error" not in result, result.get("error")
    return result


async def test_layers_stay_locked_to_the_sample(results):
    lock = of(results, "lock")
    assert lock["beats"] >= 50
    assert lock["worstOffsetFrames"] <= 1, "a beat landed off its place"
    # Drum and bass clicks are 0.5 and 0.25: together they must make one click 1.5 times the
    # drum's, which only happens if they fall on the same sample.
    assert 1.49 <= lock["minRatio"] <= lock["maxRatio"] <= 1.51
    assert lock["sameLeftAndRight"]


async def test_one_cell_runs_into_the_next_without_a_dip_or_a_click(results):
    joins = of(results, "joins")
    assert joins["order"][:5] == ["Arrival 0", "Wander A 0", "Wander A 1", "Wander B 0", "Wander B 1"]
    assert joins["starts"][0] == pytest.approx(0.12, abs=0.005)
    gaps = [later - earlier for earlier, later in zip(joins["starts"], joins["starts"][1:])]
    assert all(gap == pytest.approx(8.0, abs=1e-6) for gap in gaps), "a cell did not start on its bar line"
    assert 0.98 <= joins["minAcrossJoin"] and joins["maxAcrossJoin"] <= 1.02
    assert joins["stepAtJoin"] <= joins["stepElsewhere"] * 1.05
    assert joins["sectionGain"] == pytest.approx(10 ** (-6 / 20), rel=0.03)   # Wander is stored 6 dB under Arrival
    assert joins["late"] == 0


async def test_a_change_of_place_lands_on_the_bar_or_the_beat(results):
    cuts = of(results, "cuts")
    assert cuts["toBattle"] is not None and abs(cuts["toBattle"] - cuts["barLine"]) <= 0.012
    assert cuts["toDepths"] is not None and abs(cuts["toDepths"] - cuts["beatLine"]) <= 0.012
    assert cuts["wanderBefore"] > 0.05 and cuts["battleAfter"] > 0.1
    assert cuts["wanderAfter"] < cuts["wanderBefore"] * 0.02, "the old section kept playing after the cut"
    sections = [entry["section"] for entry in cuts["log"]]
    assert sections[:4] == ["Arrival", "Wander A", "Battle", "Depths"]


async def test_levels_and_tone_move_at_once(results):
    levels = of(results, "levels")
    # The bass tone is 0.3 and the section playing is stored 6 dB down, so fully in it reads 0.15.
    # It has to be there a tenth of a second after it was asked for.
    assert levels["bassBefore"] < 0.002
    assert levels["bassAfter100ms"] == pytest.approx(0.3 * 10 ** (-6 / 20), rel=0.05)
    assert levels["brightAfterMuffle"] < levels["brightBefore"] * 0.2            # muffled within 0.3 s
    assert levels["brightAfterRelease"] > levels["brightBefore"] * 0.8
    assert levels["levelBeforeSilence"] > 0.05 and levels["levelAfterSilence"] < 1e-4


async def test_the_output_never_passes_full_scale(results):
    limiter = of(results, "limiter")
    assert limiter["peakWithout"] > 2.0, "the test signal is not loud enough to prove anything"
    assert limiter["peakWithLimiter"] <= 1.0
    assert limiter["levelWithLimiter"] > 0.3, "the limiter turned the music down to nothing"


async def test_left_alone_the_music_keeps_going(results):
    unattended = of(results, "unattended")
    assert unattended["cells"] >= 7 and unattended["late"] == 0
    assert unattended["quietestWindow"] > 0.02, "the music stopped or dipped"
    assert unattended["order"][:6] == ["Arrival 0", "Wander A 0", "Wander A 1", "Wander B 0", "Wander B 1", "Wander A 0"]
