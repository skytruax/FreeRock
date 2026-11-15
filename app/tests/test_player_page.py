"""The real player page in headless Chrome against a real server with made-up music.

This is the whole music path short of the speakers: the game's state goes onto the hub, the
conductor tells the page, the page fetches audio and starts its engine, and reports back what it
is playing. Skipped where Chrome is not installed.
"""
import asyncio
import shutil

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from freerock import conductor as music
from freerock import state as game
from freerock.composer import ZoneProfile, core_suite
from freerock.library import Library
from freerock.server import ServerConfig, create_app
from test_library import made_up_track

CHROME = next((path for path in (shutil.which(name) for name in
                                 ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"))
               if path), None)
pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed on this machine")

ZONE = ZoneProfile(key="elwynn-forest", bpm=120, tonic="G mixolydian", colours=["fiddle"])


def say(app, **fields):
    hub = app["hub"]
    if hub.link is not game.Link.LIVE:
        hub.publish(game.LinkChanged(link=game.Link.LIVE, previous=hub.link))
    state = game.GameState(**{"daytime": True, "zone_name": "Elwynn Forest", **fields})
    hub.publish(game.StateChanged(state=state, previous=hub.state, changed=frozenset(fields)))


async def until(condition, what, timeout=30.0):
    """Waits for `condition()` to give something true and returns it."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        found = condition()
        if found:
            return found
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("Gave up waiting for " + what)
        await asyncio.sleep(0.2)


async def test_the_page_connects_loads_the_music_and_plays(tmp_path):
    library = Library(tmp_path / "library")
    request = core_suite(ZONE, seed=3)
    mix, layers = made_up_track(request)
    asset = library.add(zone="elwynn-forest", set_name="core", request=request, mix=mix, layers=layers)
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    conductor = music.attach(app, library=library)
    server = TestServer(app)
    await server.start_server()
    say(app)
    chrome = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=%s" % (tmp_path / "chrome"),
        "--autoplay-policy=no-user-gesture-required", str(server.make_url("/player")),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        def playing():
            return next((s for s in conductor.statuses.values() if s.get("started") and s.get("section")), None)

        status = await until(playing, "the page to start playing")
        assert status["asset"] == asset.id and status["context"] == "running"
        assert status["section"] == "Arrival" and status["late"] == 0     # a zone opens with its Arrival
        assert not [note for note in conductor.notes if "problem" in note], conductor.notes

        # A fight against an elite: the page is told, and two seconds later it is in Battle.
        say(app, in_combat=True, target_class="elite")
        battle = await until(lambda: next((s for s in conductor.statuses.values() if s.get("section") == "Battle"), None),
                             "the page to move to Battle")
        assert battle["place"] == "battle" and battle["late"] == 0
        assert conductor.target.bass == 1.0

        # The music keeps going: a few seconds on, the audio clock has moved and nothing is late.
        before = battle["time"]
        later = await until(lambda: next((s for s in conductor.statuses.values() if s.get("time", 0) > before + 3), None),
                            "the audio clock to move on")
        assert later["late"] == 0 and later["started"]
        assert not [note for note in conductor.notes if "problem" in note], conductor.notes
    finally:
        chrome.terminate()
        await chrome.wait()
        await server.close()
