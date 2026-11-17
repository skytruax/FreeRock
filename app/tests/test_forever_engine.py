"""The forever-song engine, rendered offline in headless Chrome and measured.

tests/web/forever_test.html runs the real forever.js with made-up phrases whose every sample is
known and reports numbers; the tests here hold those numbers against pass lines. Skipped where
Chrome is not installed.
"""
import asyncio
import os
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
        # (A machine that is busy rendering music needs longer: FREEROCK_ENGINE_TEST_S says how long.)
        await asyncio.wait_for(finished.wait(), timeout=float(os.environ.get("FREEROCK_ENGINE_TEST_S", "400")))
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


async def test_a_channel_that_comes_up_is_playing_at_once_and_is_faded_in_slowly(results):
    """("you gotta fade in and out of everything, new songs, but even channel changes", 2026-11-16.)"""
    levels = of(results, "levels")
    assert levels["before"] < 1e-4
    # It is there half a second on (nothing has to be fetched first), and comes up over four seconds: a slow hand on a fader.
    assert 0.03 * levels["rhythm"] < levels["soon"] < 0.25 * levels["rhythm"]
    assert 0.35 * levels["rhythm"] < levels["halfway"] < 0.65 * levels["rhythm"]
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
    assert place["firstNew"] == pytest.approx(13.5, abs=0.01)
    # Four bars at 96 beats a minute are ten seconds.
    assert [round(later - earlier, 6) for earlier, later in zip(place["rhythmStarts"], place["rhythmStarts"][1:])] == [10.0, 10.0]
    assert place["oldDuring"] > 0.01, "the old music was cut off, not faded"
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


async def test_every_change_is_a_blend(results):
    blend = of(results, "formBlend")
    assert not blend["sameClip"] and blend["changedAt"] == pytest.approx(blend["turn"], abs=1e-6)
    full = blend["oldBefore"]
    assert blend["newBefore"] < 0.01 * full
    # Two bars (four seconds here): the old phrase falls as the new one rises...
    assert blend["oldEarly"] > 0.9 * full and blend["newEarly"] < 0.3 * full
    assert blend["oldLate"] < 0.3 * full and blend["newLate"] > 0.9 * full
    assert blend["oldGone"] < 0.01 * full and blend["newFull"] == pytest.approx(full, rel=0.05)
    # ...and halfway the two together are as loud as either alone.
    together = (blend["oldMiddle"] ** 2 + blend["newMiddle"] ** 2) ** 0.5
    assert together == pytest.approx(full, rel=0.08)
    # A fight in the middle of a turn: a bar (two seconds here), a blend like the rest.
    assert blend["fightAt"] is not None and blend["fightAt"] - 10.3 <= 0.08 + 0.25 + 1e-6
    assert 0.2 * full < blend["fightOldSoon"] < 0.8 * full and 0.2 * full < blend["fightNewSoon"] < 0.9 * full
    assert blend["fightOldGone"] < 0.01 * full and blend["fightNewFull"] == pytest.approx(full, rel=0.05)


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
    assert place["firstNew"] == pytest.approx(21.5, abs=0.05)
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


# --- written pieces ------------------------------------------------------------------------------

async def test_the_parts_of_a_piece_play_together_and_join_without_a_seam(results):
    parts = of(results, "pieceParts")
    for channel in ("rhythm", "drums", "bass"):
        assert parts[channel] == pytest.approx(0.1, rel=0.08), "the %s part is not there at its level" % channel
    assert parts["later"] == pytest.approx(0.1, rel=0.08)
    assert parts["decks"] == 3, "a deck with no part in the piece played something"
    assert len(parts["secondAt"]) == 3
    assert all(at == pytest.approx(ORIGIN + 8.0, abs=1e-6) for at in parts["secondAt"]), "a stretch did not follow on its line"
    assert all(offset == 0 for offset in parts["offsets"])
    assert parts["acrossSeam"] >= 0.97 * parts["steady"], "the music dips where two stretches of a part join"
    assert parts["stepAtSeam"] <= parts["stepElsewhere"] * 1.2, "the join clicks"
    assert parts["piece"]["title"] == "song"
    assert parts["late"] == 0


async def test_a_track_runs_from_one_piece_into_the_next_without_a_seam(results):
    track = of(results, "pieceTrack")
    assert track["seen"] == ["one", "two"]
    assert track["twoAt"] == pytest.approx(ORIGIN + 8.0, abs=1e-6)
    assert track["acrossSeam"] >= 0.97 * track["steady"], "the music dips where the track goes from one piece to the next"
    assert track["stepAtSeam"] <= track["stepElsewhere"] * 1.2
    assert track["late"] == 0


async def test_a_boss_brings_its_own_piece_in_and_the_track_is_picked_up_after_and_no_other_fight_does(results):
    """("in normal fights dont play a separate battle piece dungeon bosses ONLY", 2026-11-16.)"""
    fight = of(results, "pieceFight")
    assert fight["ordinary"] == ["walk"], "an ordinary fight brought another piece in: %s" % fight["ordinary"]
    assert fight["ordinaryWalk"] == pytest.approx(0.1, rel=0.08), "the song that was playing did not go on through the fight"
    assert fight["brawlAt"] == pytest.approx(ORIGIN + 10.5, abs=1e-6), "the boss's piece did not begin to come in on the next beat"
    assert fight["brawlOffset"] == 0
    # A second into its bar of blending in: both are heard, neither whole.
    assert 0.02 < fight["brawlBlend"] < 0.08 and 0.02 < fight["walkBlend"] < 0.08, "the boss's piece cut in: %s" % fight
    assert fight["walkBefore"] == pytest.approx(0.1, rel=0.08)
    assert fight["walkDuring"] < 0.005, "the piece that was playing went on under the fight"
    assert fight["brawlDuring"] == pytest.approx(0.1, rel=0.08)
    assert fight["backAt"] == pytest.approx(ORIGIN + 10.5 + 10.0, abs=1e-6), "the calm did not come in on the bar line"
    assert fight["backClip"].endswith("-w1") and fight["backOffset"] == pytest.approx(2.0, abs=1e-6), \
        "the track was not picked up at the bar it had reached"
    assert fight["walkAfter"] == pytest.approx(0.1, rel=0.08)
    assert fight["brawlAfter"] < 0.005
    assert fight["piece"]["title"] == "walk"
    assert fight["late"] == 0


async def test_the_next_fight_goes_on_with_the_last_fights_track(results):
    again = of(results, "pieceFightAgain")
    assert again["second"] == again["first"], "the second fight began another track: %s" % again
    # The first fight's piece came in at 10.5 s and was left on its bar line ten seconds in:
    # the second fight picks it up there, two seconds into its second stretch.
    assert again["secondClip"].endswith("-w1") and again["secondOffset"] == pytest.approx(2.0, abs=1e-6)
    assert again["secondAt"] == pytest.approx(ORIGIN + 30.5, abs=1e-6), "it did not come in on the next beat"
    assert again["late"] == 0


async def test_a_fight_in_the_last_bars_of_a_piece_and_the_track_goes_on_from_the_next(results):
    late = of(results, "pieceFightAtTheEnd")
    assert late["brawlAt"] == pytest.approx(ORIGIN + 13.5, abs=1e-6)
    assert late["after"] == "two" and late["afterOffset"] == 0, "the track did not go on from its next piece: %s" % late
    assert late["afterAt"] == pytest.approx(ORIGIN + 13.5 + 8.0, abs=1e-6)


async def test_the_piece_is_chosen_for_the_kind_of_place(results):
    place = of(results, "piecePlace")
    assert place["haunted"] == ["crypt"]
    assert place["pastoral"] == ["meadow"]
    assert place["order"][:2] == ["crypt", "meadow"], "the next track was not the new place's"
    assert "crypt" not in place["order"][1:], "a light place was not kept light"


async def test_the_music_follows_the_player_into_another_kind_of_place_within_a_few_bars(results):
    follows = of(results, "pieceFollows")
    # A step over the border at 5 s and back at 7 moved nothing; in for good at 8.5 s: four seconds to be
    # sure of it, then the next bar line (a bar is two seconds), long before the piece ends at 48 s.
    assert follows["cryptAt"] == pytest.approx(ORIGIN + 14.0, abs=1e-6), "the new place's track did not come on the bar line after the player had stayed: %s" % follows
    assert follows["meadowBefore"] > 0.05 and follows["cryptBefore"] < 0.005, "the music moved before the player had stayed: %s" % follows
    assert follows["cryptThere"] > 0.05 and follows["meadowThere"] < 0.005, "the old place's track had not given way: %s" % follows
    # Back at 20 s: the music does not move twice within twenty seconds; then the old track, from the bar it had reached.
    assert follows["backAt"] == pytest.approx(ORIGIN + 34.0, abs=1e-6), follows
    assert follows["backClip"].endswith("-w1") and follows["backOffset"] == pytest.approx(6.0, abs=1e-6), "the old track was not picked up where it was left: %s" % follows
    assert follows["meadowBack"] > 0.05 and follows["cryptBack"] < 0.005, follows
    # A border crossed at 4.5 s in a fight that is over at 12: the look at 8.5 s is put off, the one four seconds on moves the music.
    assert follows["afterFightAt"] == pytest.approx(ORIGIN + 14.0, abs=1e-6), "the music did not follow once the fight was over: %s" % follows


async def test_a_cave_brings_its_own_music_at_once_and_the_calm_after_a_fight_does_not(results):
    cave = of(results, "pieceIntoCave")
    assert cave["deepAt"] == pytest.approx(ORIGIN + 10.0, abs=1e-6), "the cave's music did not come on the bar line after the player had stayed: %s" % cave
    assert cave["backAt"] == pytest.approx(ORIGIN + 46.0, abs=1e-6), "the walking music did not come back outside: %s" % cave
    assert cave["backOffset"] == pytest.approx(2.0, abs=1e-6), "the walking track was not picked up where it was left: %s" % cave
    assert cave["calm"] == ["walk"], "the calm after a fight took the walking track away: %s" % cave
    assert cave["afterFight"] == ["deep"], "the calm after a fight in the cave took the cave's track away: %s" % cave


async def test_a_track_carries_on_through_a_calm_moment(results):
    order = of(results, "pieceCarriesOn")["order"]
    assert order[:3] == ["one", "two", "calm"], "the track was dropped for the calm piece: %s" % order
    assert order[3] == "one", "the calm track went on after the calm moment was over: %s" % order


async def test_a_border_crossed_in_the_last_seconds_of_a_piece_still_changes_the_music(results):
    border = of(results, "pieceBorderLate")
    assert border["meadow"] == pytest.approx(0.1, rel=0.1), "the new place's music did not come: %s" % border
    assert border["vault"] < 0.005, "the old track went on into its next piece"


async def test_tracks_heard_lately_give_way_to_others_and_a_neighbouring_kind_of_place_comes_before_a_third_hearing(results):
    """("feels like its playing the same songs over and over", 2026-11-16.)"""
    order = of(results, "pieceVariety")["order"]
    assert len(order) >= 8, order
    assert set(order[:2]) == {"a1", "a2"}, "the two tracks written for the place did not come first: %s" % order
    assert all(now != before for now, before in zip(order[1:], order)), "a track was played twice running: %s" % order
    assert "near" in order[:5], "both tracks were heard a third time before the neighbouring kind's got a turn: %s" % order
    assert "far" in order and order.index("near") < order.index("far"), "the track for somewhere else came before the neighbour's: %s" % order


async def test_the_takes_of_one_family_count_as_one_song_and_its_sister_families_as_half_of_one(results):
    """("i feel like im hearing alot the same shit again", 2026-11-16: the takes of one family were counted as songs of
    their own, so a take could follow another take of the same song.)"""
    order = of(results, "pieceFamilies")["order"]
    # A track plays each channel from one take of its family or another (they share a key and a pace), so what is
    # heard is counted by family.
    family = {"a1": "fields-1", "a2": "fields-1", "b1": "dance-1", "b2": "dance-2", "d1": "river-1"}
    heard = []
    for each in order:
        if not heard or heard[-1] != family[each]:
            heard.append(family[each])
    assert len(heard) >= 4, order
    kinds = [name.rsplit("-", 1)[0] for name in heard]
    assert len(set(kinds[:3])) == 3, "a family or its sister came round again before the others: %s" % heard
    assert heard[3] == "dance-2", "the sister family did not come before a second hearing of the others: %s" % heard


async def test_with_six_loudspeakers_the_music_is_laid_over_all_of_them_and_each_can_be_sounded_alone(results):
    six = of(results, "sixSpeakers")
    assert six["speakers"] == 6 and six["status"] == 6
    assert six["names"] == ["front left", "front right", "centre", "sub", "rear left", "rear right"]
    left, right, centre, sub, rear_left, rear_right = six["music"]
    assert left > 0.02 and right > 0.02, "nothing in the front pair: %s" % six["music"]
    assert 0.1 * left < centre < 0.6 * left, "the centre is not a little of the front: %s" % six["music"]
    assert 0.2 * left < rear_left < 0.8 * left and 0.2 * right < rear_right < 0.8 * right, "the rear pair is not the front, softer: %s" % six["music"]
    assert sub > 0.0, "nothing reaches the sub: %s" % six["music"]
    for name, slot in zip(six["names"], six["slots"]):
        assert slot["own"] > 0.05, "the %s loudspeaker did not sound in its turn: %s" % (name, slot)
        assert slot["others"] < 0.2 * slot["own"], "another loudspeaker sounded with the %s: %s" % (name, slot)


async def test_among_pieces_for_one_kind_of_place_the_nearest_in_shade_is_chosen_and_the_music_follows_the_light(results):
    """("in a dark misty place and music is too light we need lots of different granularity", 2026-11-16.)"""
    shade = of(results, "pieceShade2")
    assert shade["shades"] == [3, -2.5, 0], "a bright major piece, a dark minor one, a wistful light one: %s" % shade["shades"]
    assert shade["bright"] == ["sunny"] and shade["dark"] == ["dusky"], shade
    # The light goes at 8.5 s (a passing cloud at 5.5 moved nothing): four seconds to be sure, then the next bar line.
    assert shade["first"] == "sunny" and shade["movedAt"] == pytest.approx(ORIGIN + 14.0, abs=1e-6), shade


async def test_among_pieces_for_one_kind_of_place_the_one_written_for_its_ground_comes_first_and_the_music_follows_it(results):
    """("make sure by tomorroow morning we have granularity in locations on all the kinds", 2026-11-16.)"""
    ground = of(results, "pieceSetting")
    assert ground["water"] == ["lake"] and ground["fields"] == ["farm"], ground
    # The ground changes at 8.5 s: four seconds to be sure, then the next bar line.
    assert ground["first"] == "lake" and ground["movedAt"] == pytest.approx(ORIGIN + 14.0, abs=1e-6), ground


async def test_at_night_the_night_music_comes_first_and_the_walking_music_still_comes(results):
    """("night should feel like night", 2026-11-16.)"""
    order = of(results, "pieceNight")["order"]
    assert order[0] == "owl", "the night's own music did not come first: %s" % order
    assert "walk" in order, "the walking music never came, however often the night's was heard: %s" % order
    assert order.count("owl") > order.count("walk"), order


async def test_light_and_heavy_take_turns(results):
    shade = of(results, "pieceShade")
    assert len(shade["order"]) >= 12
    assert shade["heavyPairs"] == 0, "two heavy tracks in a row: %s" % shade["order"]
    assert shade["kinds"] == 5, "a piece was never played: %s" % shade["order"]


async def test_a_piece_says_which_channels_stand_in_for_which_and_how_little_it_can_do_with(results):
    levels = of(results, "pieceLevels")
    assert levels["rhythm"] == pytest.approx(0.1, rel=0.08), "the band did not stand in for the tune"
    assert levels["drums"] == pytest.approx(0.05, rel=0.08), "the drums were not kept at their least"
    assert levels["bass"] < 0.002


async def test_pieces_over_the_same_changes_lend_each_other_their_parts(results):
    kin = of(results, "pieceKin")
    assert kin["mixed"] >= 3, "the parts were never taken from more than one piece"
    assert kin["casts"] >= 4
    assert kin["late"] == 0


@pytest.mark.parametrize("name", ["pieceLong", "pieceLongPlaced"])
async def test_a_long_track_is_played_in_its_order_and_kin_keep_to_their_place(results, name):
    """Nine pieces whose story words come round more than once: a theme, a second theme, the
    calm between two rises. Whether the bucket tells each piece's place or the player has to
    count the pieces before it, a part is lent only to the piece at the same place."""
    long = of(results, name)
    assert long["order"] == list(range(9)), "the track was not played right through"
    assert long["words"] == ["open", "theme", "theme", "rise", "moment", "theme", "rise", "moment", "close"]
    assert all(parts == 3 for parts in long["parts"]), "a piece came without all its parts: %s" % long["parts"]
    assert long["astray"] == 0, "a part was played under a piece from another place in the story"
    assert long["mixed"] >= 1, "the two takes never lent each other a part"
    assert long["late"] == 0


async def test_one_track_is_crossfaded_into_the_next_under_its_last_bar(results):
    hand = of(results, "pieceHandover")
    assert len(hand["order"]) >= 2 and hand["order"][0] != hand["order"][1]
    # The first track ends at 16 s; a bar is two seconds: the next comes in from 14 s, from its own first beat.
    assert hand["at"] == pytest.approx(ORIGIN + 14.0, abs=1e-6)
    assert hand["offset"] == 0
    assert hand["newBefore"] < 0.003, "the next track was heard before the blend began"
    assert 0.3 * hand["before"] < hand["oldMiddle"] < 0.7 * hand["before"], "the track that is ending did not fade away under the next: %s" % hand
    assert 0.03 < hand["newMiddle"] < 0.07, "the next track did not fade in: %s" % hand
    assert hand["arrived"] == pytest.approx(0.1, rel=0.1), "the next track was not whole when the first had ended"
    assert hand["gone"] < 0.003
    assert hand["acrossBlend"] >= 0.6 * hand["steady"], "a hole in the music where one track gives way to the next"
    assert hand["late"] == 0


async def test_a_banned_piece_is_left_at_once(results):
    ban = of(results, "pieceBan")
    assert ban["movedAt"] is not None and ban["movedAt"] <= 9.2 + 2.2, "the banned piece went on playing"
    assert ban["later"] == ["good" if ban["banned"] == "bad" else "bad"]
    assert ban["quietest"] >= 0.5 * ban["typical"], "the music stopped when the piece was banned"


async def test_pieces_can_be_switched_off_in_the_middle_of_one(results):
    off = of(results, "pieceOff")
    assert off["looseAt"] is not None and off["looseAt"] <= 9.2 + 2.2, "the piece went on after pieces were switched off"
    assert off["later"] == ["loose"]
    assert off["quietest"] >= 0.3 * off["typical"], "the music stopped when pieces were switched off"
    assert off["late"] == 0


async def test_loose_phrases_and_silences_come_between_tracks(results):
    free = of(results, "pieceFree")
    assert free["kinds"][:3] in (["piece", "loose", "piece"], ["loose", "piece", "loose"]), free["kinds"]
    assert free["quietest"] >= 0.3 * free["typical"], "there is a hole where a track hands over to loose phrases"
    assert free["late"] == 0
    rest = of(results, "pieceRest")
    assert rest["longestSeconds"] >= 3.0, "no moment of silence came between tracks"
    assert rest["silentSeconds"] <= 45.0, "the music stayed away"


async def test_a_track_has_no_holes_when_the_page_is_looked_in_on_rarely(results):
    alone = of(results, "pieceUnattended")
    assert alone["quietest"] >= 0.5 * alone["typical"], "a hole in the music"
    assert alone["late"] == 0
    assert set(alone["pieces"]) >= {"one", "two", "three"}
