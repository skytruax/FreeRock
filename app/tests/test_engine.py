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


async def test_a_new_zone_at_another_tempo_cuts_in_on_the_old_bar_line(results):
    change = of(results, "zoneChange")
    assert change["handover"] is not None and abs(change["handover"] - change["barLine"]) <= 0.012
    sections = [(entry["section"], round(entry["at"], 2)) for entry in change["log"]]
    # The new zone opens with its Arrival on the old music's bar line, and its own cells are then
    # ten seconds long (four bars at 96 beats a minute).
    assert sections[0] == ("Arrival", round(change["barLine"], 2))
    assert sections[1] == ("Wander A", round(change["barLine"] + 10, 2))
    assert sections[2] == ("Wander A", round(change["barLine"] + 20, 2))
    assert change["arrivalTone"] > 0.15 and change["wanderTone"] > 0.15
    assert change["oldAfter"] < 0.005, "the old zone's music kept playing"


async def test_a_rest_fades_the_music_away_and_it_comes_back_with_a_fresh_opening(results):
    rest = of(results, "rest")
    assert rest["before"] > 0.05
    assert rest["fading"] < rest["before"] * 0.75                     # on its way down
    assert rest["resting"] < 1e-4, "something played during the rest"
    assert rest["startsDuringRest"] == 0, "cells were still being queued during the rest"
    first = rest["firstAfter"]
    assert first["section"] == "Arrival" and first["at"] == pytest.approx(16.12, abs=0.02)
    assert rest["back"] > 0.1 and rest["toneAfter"] > 0.1             # Arrival's own tone, at full level
    assert rest["late"] == 0


async def test_a_later_set_joins_the_rotation_from_its_own_request(results):
    sets = of(results, "sets")
    assert sets["order"][:8] == ["Arrival 0", "Wander A 0", "Wander A 1", "Wander B 0", "Wander B 1",
                                 "Wander C 0", "Wander C 1", "Wander A 0"]
    assert sets["from"][:8] == ["test"] * 5 + ["extra"] * 2 + ["test"]
    assert sets["toneOfThird"] > 0.08 and sets["otherToneThen"] < 0.005
    assert sets["late"] == 0


async def test_more_music_for_the_zone_that_is_playing_does_not_interrupt_it(results):
    more = of(results, "moreMusic")
    gaps = [later - earlier for earlier, later in zip(more["starts"], more["starts"][1:])]
    assert all(gap == pytest.approx(8.0, abs=1e-6) for gap in gaps), "a cell was cut when the new set arrived"
    assert more["order"][:7] == ["Arrival 0", "Wander A 0", "Wander A 1", "Wander B 0", "Wander B 1",
                                 "Wander C 0", "Wander C 1"]
    assert more["steadyAcross"] == pytest.approx(1.0, abs=0.02) and more["late"] == 0


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


def test_kinds_of_section_take_turns(results):
    """In a cave the Depths part and the zone's riffs come round one after the other: the part
    made for the place is heard first, and nothing is left to loop."""
    turns = of(results, "takingTurns")
    assert turns["sections"][:7] == ["Depths", "Wander A", "Wander B", "Depths", "Wander A", "Wander B", "Depths"]
    assert turns["late"] == 0


def test_crossing_into_another_area_changes_the_riff_on_the_next_bar(results):
    scene = of(results, "newScene")
    # Arrival, then Wander A; the crossing at 10 s is answered on the next bar line, at 10.12 s
    # (bars are two seconds long and Wander A began at 8.12). When A's turn comes round again it
    # goes on from its second cell.
    assert scene["order"][:5] == ["Arrival 0", "Wander A 0", "Wander B 0", "Wander B 1", "Wander A 1"]
    assert scene["starts"][2] == pytest.approx(0.12 + 10, abs=0.001)
    assert scene["toneAfter"] > 10 * scene["toneOfTheOld"]
    assert scene["late"] == 0


def test_what_has_left_the_rotation_gives_way_on_the_next_bar(results):
    left = of(results, "leavingTheRotation")
    assert left["sections"][:4] == ["Arrival", "Wander A", "Wander B", "Ember"]
    assert left["emberAt"] == pytest.approx(0.12 + 40, abs=0.001)
    # Asked at 43.3 s: the next bar line is at 44 s, and a riff is playing from there.
    assert left["nextAt"] == pytest.approx(0.12 + 44, abs=0.001) and left["next"].startswith("Wander")
    assert left["late"] == 0


def test_after_a_rest_the_riff_that_has_gone_longest_unheard_comes_first(results):
    rest = of(results, "afterARest")
    # Before the rest: Arrival, then Wander A. After it: the opening again, then Wander B, which
    # has not been heard yet. (It used to be Wander A after every rest.)
    assert rest["sections"][:4] == ["Arrival", "Wander A", "Arrival", "Wander B"]
    assert rest["late"] == 0


def test_a_riff_has_eight_bars_then_another_has_a_turn_and_each_goes_on_where_it_left_off(results):
    turns = of(results, "turns")
    assert turns["order"][:11] == ["Arrival 0", "Wander A 0", "Wander A 1", "Wander B 0", "Wander B 1",
                                   "Wander A 2", "Wander A 3", "Wander B 2", "Wander B 3",
                                   "Wander A 0", "Wander A 1"]
    assert turns["late"] == 0


def test_a_fight_carries_on_through_its_one_section_and_the_riff_goes_on_after(results):
    fight = of(results, "oneSectionCarriesOn")
    order = fight["order"]
    # Arrival, Wander A; the fight at 12 s cuts in on the next beat (12.12 s) and Battle runs its
    # four cells and round again; back to the riffs at 56 s, with Wander B, the one not yet heard.
    assert order[:3] == ["Arrival 0", "Wander A 0", "Battle 0"]
    assert fight["starts"][2] == pytest.approx(0.12 + 12, abs=0.001)
    assert order[3:8] == ["Battle 1", "Battle 2", "Battle 3", "Battle 0", "Battle 1"]
    after = [name for name in order[8:] if not name.startswith("Battle")]
    assert after[0] == "Wander B 0", "after the fight comes the riff that has gone longest unheard"
    assert "Wander A 1" in after, "and the riff the fight interrupted goes on from where it had got to"
    assert fight["late"] == 0


def test_every_section_is_fetched_before_it_is_needed(results):
    ahead = of(results, "fetchedAhead")
    assert set(ahead["sectionStarts"]) <= set(ahead["beforeTheFight"]), "a section's first cell was not fetched ahead"
    assert ahead["beforeTheFight"].index(ahead["battleStart"]) <= 1, "the Battle part is fetched first of all"
    assert ahead["battleStart"] not in ahead["afterIt"], "going to Battle asked the server for it again"
    # Asked for at 12.3 s: the next beat line is 12.62 s, and nothing waited for the network.
    assert ahead["battleAt"] == pytest.approx(0.12 + 12.5, abs=0.001)
    assert ahead["late"] == 0


def test_a_death_runs_the_music_down_like_a_record_stopping(results):
    down = of(results, "windDown")
    assert down["runningDown"] < 0.7 * down["before"] and down["runningDown"] > 0.2 * down["before"]
    assert down["gone"] < 0.08 * down["before"]
    # The pitch falls with it: the note that was playing is no longer at its own pitch.
    assert down["toneWhileRunningDown"] < 0.3 * down["toneBefore"]
    assert down["nextAt"] == pytest.approx(10.0 + 1.2, abs=0.01), "the next music starts when the old has run down"
    assert down["late"] == 0
