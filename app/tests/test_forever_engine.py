"""The forever-song engine, rendered offline in headless Chrome and measured.

tests/web/forever_test.html runs the real forever.js with made-up phrases whose every sample is
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
ENGINE = HERE.parent / "freerock" / "web" / "player" / "forever.js"
PAGE = HERE / "web" / "forever_test.html"
CHROME = next((path for path in (shutil.which(name) for name in
                                 ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"))
               if path), None)

pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed on this machine")

ORIGIN = 0.08          # the engine starts its grid this long after its first look
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
    app.router.add_get("/forever.js", engine_js)
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
        await asyncio.wait_for(finished.wait(), timeout=400)
    except asyncio.TimeoutError:
        process.terminate()
        _, err = await process.communicate()
        raise RuntimeError("The forever-song test page gave no results in time.\nChrome said: %s"
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


async def test_the_decks_stay_locked_to_the_sample(results):
    lock = of(results, "lock")
    assert lock["beats"] >= 100
    assert lock["worstOffsetFrames"] <= 1, "a beat landed off its place"
    # A drum click and a bass click on the same sample make one click 1.5 times the drum's.
    assert 1.49 <= lock["minRatio"] <= lock["maxRatio"] <= 1.51
    assert lock["sameLeftAndRight"]
    assert lock["drumPhrases"] >= 2 and lock["bassPhrases"] >= 2, "the decks never took another phrase"
    assert lock["late"] == 0


async def test_a_phrase_runs_into_the_next_without_a_gap_or_a_click(results):
    seams = of(results, "seams")
    gaps = [later - earlier for earlier, later in zip(seams["starts"], seams["starts"][1:])]
    assert seams["starts"][0] == pytest.approx(ORIGIN, abs=0.005)
    assert all(gap == pytest.approx(8.0, abs=1e-6) for gap in gaps), "a pass did not start on its line"
    assert all(offset == 0 for offset in seams["offsets"])
    assert len(set(seams["clips"])) >= 2, "the deck never took another phrase"
    assert seams["quietestAcrossSeam"] >= 0.6 * seams["steady"], "the music dips at the join"
    assert seams["stepAtSeam"] <= seams["stepElsewhere"] * 1.3, "the join clicks"
    assert seams["late"] == 0


async def test_the_song_keeps_moving_one_deck_at_a_time(results):
    moving = of(results, "oneAtATime")
    assert moving["mostAtOneLine"] == 1, "two decks took a new phrase at the same line"
    assert moving["linesWithAChange"] >= 0.7 * moving["lines"], "the song stood still"
    assert all(count >= 2 for count in moving["perChannel"].values())
    assert moving["soonestRepeat"] >= 2, "a deck came back to a phrase it had only just left"
    assert moving["late"] == 0


async def test_a_fight_changes_gear_on_the_next_half_beat_and_in_step(results):
    gear = of(results, "gearUp")
    assert gear["at"] == pytest.approx(gear["expected"], abs=1e-6)
    assert gear["at"] - 10.3 <= 0.08 + 0.25 + 1e-6, "the hard phrases took more than a half beat to come in"
    assert gear["offset"] == pytest.approx(gear["expectedOffset"], abs=1e-6), "the new phrase came in out of step"
    assert gear["hardAfter"] == pytest.approx(gear["steadyBefore"], rel=0.05)
    assert gear["steadyAfter"] < 0.01 * gear["steadyBefore"], "the old phrase kept playing"
    assert gear["tiersAfter"] == [2, 2, 2, 2]
    assert gear["late"] == 0


async def test_easing_off_waits_for_the_bar_line(results):
    gear = of(results, "gearDown")
    assert gear["at"] == pytest.approx(gear["expected"], abs=1e-6)
    assert gear["tiersAfter"] == [0, 0, 0, 0]


async def test_a_channel_that_is_down_is_there_the_moment_it_comes_up(results):
    levels = of(results, "levels")
    assert levels["before"] < 1e-4
    assert levels["after"] == pytest.approx(levels["rhythm"], rel=0.05)


async def test_only_phrases_that_can_be_heard_are_counted_as_heard(results):
    heard = of(results, "heard")
    assert heard["first"] == ["lead", "rhythm", "texture"]
    assert heard["second"] == ["drums"]
    assert heard["playing"] == ["drums", "lead", "rhythm", "texture"]


async def test_a_rest_fades_right_out_and_the_music_comes_back_afresh(results):
    rest = of(results, "rest")
    assert rest["during"] < 1e-4
    assert rest["scheduledDuring"] == 0
    assert rest["firstAfter"] == pytest.approx(18.0 + ORIGIN, abs=0.01)
    assert rest["offsetsAfter"] and all(offset == 0 for offset in rest["offsetsAfter"])
    assert rest["after"] == pytest.approx(rest["before"], rel=0.25)


async def test_another_place_comes_in_on_its_own_tempo(results):
    place = of(results, "newPlace")
    assert place["key"] == "test/slow"
    assert place["firstNew"] == pytest.approx(13.2, abs=0.01)
    # Four bars at 96 beats a minute are ten seconds.
    assert [round(later - earlier, 6) for earlier, later in zip(place["rhythmStarts"], place["rhythmStarts"][1:])] == [10.0, 10.0]
    assert place["oldAfter"] < 1e-3, "the old place's music kept playing"
    assert place["newAfter"] > 0.05


async def test_phrases_that_arrive_are_taken_up_at_once(results):
    arrivals = of(results, "arrivals")
    # The first drum phrase arrived at 3 s: the drums come in on the next beat, in step.
    assert arrivals["first"]["at"] == pytest.approx(3.0 + ORIGIN, abs=1e-6)
    assert arrivals["first"]["offset"] == pytest.approx(3.0, abs=1e-6)
    assert arrivals["first"]["tier"] == 1          # the nearest strength there was
    assert arrivals["hard"] is not None and arrivals["hard"]["at"] == pytest.approx(arrivals["hardExpected"], abs=1e-6)
    assert arrivals["channels"] == ["drums", "texture"]


async def test_a_phrase_that_is_set_aside_is_not_chosen_again(results):
    aside = of(results, "setAside")
    assert aside["playedAfter"] == 0
    assert aside["others"] == 2


async def test_the_tune_sits_a_phrase_out_and_another_follows(results):
    tune = of(results, "layOut")
    assert tune["starts"][:2] == pytest.approx([ORIGIN, 32.0 + ORIGIN], abs=1e-6)
    assert tune["clips"][0] != tune["clips"][1]
    assert tune["sittingOut"] < 1e-4 and tune["playing"] > 0.05 and tune["back"] > 0.05


async def test_the_tune_does_not_sit_out_a_fight(results):
    fight = of(results, "noLayOutInAFight")
    assert fight["sittingOut"] < 1e-4
    assert fight["backAt"] is not None and fight["backAt"] - 20.2 <= 0.08 + 0.25 + 1e-6
    assert fight["tier"] == 2


async def test_a_death_runs_the_music_down_and_it_starts_again(results):
    down = of(results, "windDown")
    assert down["runningDown"] < down["before"]
    assert down["runDown"] < 0.1 * down["before"]
    assert down["restartedAt"] == pytest.approx(7.2, abs=0.01)
    assert down["after"] > 0.5 * down["before"]


async def test_with_a_form_the_decks_turn_over_where_it_comes_round(results):
    form = of(results, "form")
    assert form["offBoundary"] == [], "a phrase started somewhere other than where the form comes round"
    assert form["offsetsOnTheTurn"] == [0], "a phrase was not played from its beginning"
    assert form["startedTogether"] == 5 and form["startOffsets"] == [0, 0, 0, 0, 0]
    assert form["mostInOneTurn"] <= 2, "more than two decks changed in one turn of the form"
    assert form["turnsWithAChange"] >= form["turns"] - 2, "the song stood still"
    assert form["changes"] >= form["turns"]
    # The drone keeps to the form like everything else: one pass a turn, thirty-two seconds apart.
    assert form["droneStarts"] == pytest.approx([ORIGIN, 32 + ORIGIN, 64 + ORIGIN], abs=1e-6)
    assert form["late"] == 0


async def test_the_player_shapes_each_turn_of_the_form(results):
    shape = of(results, "formShape")
    # The verse is held back by the 6 dB asked for, the build-up rises, the chorus is at full.
    assert shape["verse"] == pytest.approx(0.5 * shape["chorus"], rel=0.05)
    assert shape["verse"] < shape["earlyBuild"] < shape["lateBuild"] < shape["chorus"] * 1.01
    assert shape["nextVerse"] == pytest.approx(shape["verse"], rel=0.05)
    # A fight in the verse: held back by about a third of that, at once, and the chorus still full.
    assert shape["fightVerse"] == pytest.approx(10 ** (-6 * 0.35 / 20) * shape["chorus"], rel=0.05)
    assert shape["fightChorus"] == pytest.approx(shape["chorus"], rel=0.05)


async def test_the_song_rises_and_falls_of_its_own_accord(results):
    wave = of(results, "formWave")
    # Two turns as the game asks, one that eases right off, one straight, one that leans in.
    assert wave["waves"] == [0, 0, -1, 0, 1]
    assert wave["drums"] == [1, 1, 0, 1, 2]
    assert wave["rhythm"] == [1, 1, 0, 1, 2]
    assert wave["drone"] == [0, 0, 0, 0, 0]
    # The calm phrases come in where the form comes round, from their beginnings. (The tune may
    # sit out the verse, so it is not always among them.)
    assert {entry[0] for entry in wave["easedStarts"]} >= {"rhythm", "drums", "bass"}
    assert all(tier == 0 and offset == 0 for _, tier, offset in wave["easedStarts"])
    # The drums sit back in the turn that eases off.
    assert wave["eased"] == pytest.approx(0.6 * wave["straight"], rel=0.05)
    # A fight in the middle of it: the hard phrases at once, at that place in the form.
    assert wave["fightAt"] is not None and wave["fightAt"] - 70 <= 0.08 + 0.25 + 1e-6
    assert wave["fightOffset"] == pytest.approx((wave["fightAt"] - ORIGIN) % 32, abs=1e-6)
    assert wave["late"] == 0


async def test_the_song_comes_down_to_a_moment_of_silence_and_back(results):
    silence = of(results, "formSilence")
    # The turn before the silence eased off; the music fades away over its last bars.
    assert silence["easedBefore"] == [0]
    assert silence["fading"] < 0.6 * silence["playing"]
    assert silence["silence"] < 1e-4
    assert silence["laidDownInTheSilence"] == 0
    # Twenty seconds of nothing, then a new verse from the top, fading in.
    assert 84.0 <= silence["backAt"] <= 85.0
    assert silence["backOffsets"] == [0, 0, 0, 0, 0]
    assert silence["justBack"] < 0.5 * silence["wellBack"]
    # A fight in the silence brings the music straight back.
    assert 72.0 <= silence["fightBackAt"] <= 72.7


async def test_a_sweep_thins_the_lows_before_the_chorus_and_gives_them_back(results):
    sweep = of(results, "formSweep")
    assert sweep["tone"] < 2000
    assert sweep["beforeChorus"] < 0.5 * sweep["verse"]
    assert sweep["chorus"] == pytest.approx(sweep["verse"], rel=0.1)


async def test_with_a_form_the_new_tune_sits_out_the_verse(results):
    tune = of(results, "formTune")
    # The first tune plays its turn; the next comes in eight seconds late, at its own build-up.
    assert tune["starts"][:2] == pytest.approx([ORIGIN, 40 + ORIGIN], abs=1e-6)
    assert tune["offsets"][:2] == pytest.approx([0, 8], abs=1e-6)
    assert tune["clips"][0] != tune["clips"][1]
    assert tune["verse"] < 1e-4 and tune["firstTurn"] > 0.05 and tune["build"] > 0.05 and tune["chorus"] > 0.05


async def test_with_a_form_a_fight_comes_in_at_that_place_in_the_form(results):
    gear = of(results, "formGear")
    assert gear["at"] == pytest.approx(gear["expected"], abs=1e-6)
    assert gear["offset"] == pytest.approx(gear["expectedOffset"], abs=1e-6)
    # And the hard phrase then turns over with everything else.
    assert gear["next"] == [] or gear["next"][0] == pytest.approx([64 + ORIGIN, 0], abs=1e-6)
    assert gear["late"] == 0


async def test_another_place_takes_over_whole(results):
    place = of(results, "formPlace")
    assert place["key"] == "test/there"
    assert place["firstNew"] == pytest.approx(21.2, abs=0.05)
    assert place["together"] == 5 and place["offsets"] == [0, 0, 0, 0, 0], "the new place's decks did not come in together"
    assert place["late"] == 0
    assert place["after"] > 0.05


async def test_skip_moves_every_deck_on(results):
    assert of(results, "skip")["moved"] == ["bass", "drums", "lead", "rhythm", "texture"]


async def test_the_output_never_passes_full_scale(results):
    limiter = of(results, "limiter")
    assert limiter["peak"] < 1.0
    assert limiter["loud"] > 0.2


async def test_the_song_has_no_holes_when_the_page_is_looked_in_on_rarely(results):
    unattended = of(results, "unattended")
    assert unattended["late"] == 0
    assert unattended["quietestWindow"] > 0.3 * unattended["typical"]


async def test_phrases_are_fetched_before_they_are_needed_and_only_once(results):
    ahead = of(results, "fetchedAhead")
    assert ahead["hard"] >= 4, "the hard phrases were not fetched before a fight could need them"
    assert ahead["twice"] == 0
