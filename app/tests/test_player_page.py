"""The real player page in headless Chrome against a real server with made-up music.

This is the whole music path short of the speakers: the game's state goes onto the hub, the
conductor tells the page, the page fetches the phrases and starts its engine, and reports back
what it is playing. Skipped where Chrome is not installed.
"""
import asyncio
import shutil

import pytest
from aiohttp.test_utils import TestServer

from freerock import conductor as music
from freerock import state as game
from freerock.server import ServerConfig, create_app
from freerock.settings import Settings
from test_conductor import STARTING
from test_forever import fill

CHROME = next((path for path in (shutil.which(name) for name in
                                 ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"))
               if path), None)
pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed on this machine")


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


async def test_the_page_plays_the_forever_song_from_a_bucket(tmp_path):
    """The page is sent a bucket of phrases, fetches the ones its five decks start with, plays
    them, changes gear in a fight, and says what it has heard."""
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    conductor = music.attach(app, settings=Settings(var_dir=tmp_path / "var"))
    bucket = conductor.buckets.get("Duskwood", "knight")
    hard = [("drums", 2), ("bass", 2), ("rhythm", 2), ("lead", 2)]
    fill(bucket, STARTING + hard)
    server = TestServer(app)
    await server.start_server()
    say(app, zone_name="Duskwood", speed=7.0)
    chrome = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=%s" % (tmp_path / "chrome"),
        "--autoplay-policy=no-user-gesture-required", str(server.make_url("/player")),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        def playing():
            return next((s for s in conductor.statuses.values() if s.get("forever") and s.get("playing")), None)

        status = await until(playing, "the page to start the forever song")
        assert status["bucket"] == "knight/duskwood" and status["context"] == "running" and status["started"]
        assert {"texture", "lead"} <= set(status["playing"])
        assert not [note for note in conductor.notes if "problem" in note], conductor.notes

        # A fight against an elite: every deck that plays changes to its hard phrase.
        say(app, zone_name="Duskwood", speed=7.0, in_combat=True, has_target=True, target_class="elite")

        def fighting():
            return next((s for s in conductor.statuses.values() if s.get("forever") and all(
                s["playing"].get(channel, {}).get("tier") == 2 for channel in ("drums", "bass", "rhythm", "lead"))), None)

        fight = await until(fighting, "the decks to change to their hard phrases")
        assert fight["late"] == 0
        # What it has played has been counted, for choosing what comes next.
        await until(lambda: sum(clip.plays for clip in bucket.clips) >= 5, "the phrases heard to be counted")
        before = fight["time"]
        later = await until(lambda: next((s for s in conductor.statuses.values() if s.get("time", 0) > before + 3), None),
                            "the audio clock to move on")
        assert later["late"] == 0 and not later["resting"]
        assert not [note for note in conductor.notes if "problem" in note], conductor.notes
    finally:
        chrome.terminate()
        await chrome.wait()
        await server.close()
