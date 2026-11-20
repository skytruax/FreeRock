"""The real player page in headless Chrome playing written pieces from a real server.

The whole path short of the speakers: the bucket and its pieces go to the page, the page fetches
the parts, plays them together, says which piece it is in, changes to a fight's own piece when a
dungeon's boss is fought and picks the first one up again afterwards. Skipped where Chrome is not
installed.
"""
import asyncio
import shutil

import numpy as np
import pytest
from aiohttp.test_utils import TestServer

from freerock import conductor as music
from freerock import forever
from freerock.server import ServerConfig, create_app
from freerock.settings import Settings
from test_player_page import say, until

CHROME = next((path for path in (shutil.which(name) for name in
                                 ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"))
               if path), None)
pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed on this machine")

RATE = forever.RATE
BAR = 2 * RATE


def tone(hz, bars, post_s=4.0):
    frames = bars * BAR + int(post_s * RATE)
    wave = 0.2 * np.sin(2 * np.pi * hz * np.arange(frames) / RATE).astype(np.float32)
    return np.stack([wave, wave], axis=1)


async def test_the_page_plays_a_piece_a_boss_cuts_in_and_the_piece_is_picked_up_again(tmp_path):
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    conductor = music.attach(app, settings=Settings(var_dir=tmp_path / "var"))
    bucket = conductor.buckets.get("Duskwood", "knight")
    # A long walk of five stretches, and a fight of one; the band stands in for the tune and the drone.
    walk = bucket.add_piece({("rhythm", 1): tone(220.0, 40), ("drums", 1): tone(110.0, 40), ("bass", 1): tone(55.0, 40)},
                            title="Duskwood 1: Verse", bar_frames=BAR, bars=8, post=4 * RATE, tonic="D minor", story="theme",
                            moods=["haunted"], follow={"rhythm": ["texture", "lead"]}, floor={"drums": 0.3})
    brawl = bucket.add_piece({("rhythm", 1): tone(330.0, 8), ("drums", 1): tone(165.0, 8), ("bass", 1): tone(82.0, 8)},
                             title="Duskwood 1: Fight", bar_frames=BAR, bars=8, post=4 * RATE, tonic="D minor",
                             moods=["haunted"], role="battle", serves=[2], floor={"drums": 1.0, "bass": 1.0})
    server = TestServer(app)
    await server.start_server()
    say(app, zone_name="Duskwood", speed=7.0)
    chrome = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--mute-audio", "--disable-gpu", "--no-first-run", "--user-data-dir=%s" % (tmp_path / "chrome"),
        "--autoplay-policy=no-user-gesture-required", str(server.make_url("/player")),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        def in_piece(piece_id):
            return lambda: next((s for s in conductor.statuses.values()
                                 if s.get("forever") and (s.get("piece") or {}).get("id") == piece_id and s.get("playing")), None)

        status = await until(in_piece(walk), "the page to start the piece")
        assert status["bucket"] == "knight/all" and status["context"] == "running" and status["pieces"] == 2
        assert status["piece"]["title"] == "Duskwood 1: Verse" and status["piece"]["of"] == pytest.approx(80.0)
        assert set(status["playing"]) >= {"rhythm", "drums"}, "the band plays though only the tune and the drums are asked for"
        assert not [note for note in conductor.notes if "problem" in note], conductor.notes
        # What it plays is counted, part by part.
        await until(lambda: sum(clip.plays for clip in bucket.clips if clip.piece == walk) >= 2, "the parts heard to be counted")

        # A dungeon's boss: the fight's own piece takes over (an ordinary fight goes on with the song that is playing).
        left_at = max(s["piece"]["at"] for s in conductor.statuses.values() if (s.get("piece") or {}).get("id") == walk)
        say(app, zone_name="Duskwood", speed=7.0, in_combat=True, encounter=True)
        fight = await until(in_piece(brawl), "the fight's piece to cut in")
        assert fight["late"] == 0 and set(fight["playing"]) == {"rhythm", "drums", "bass"}
        assert (await (await _get(server, "/api/music")).json())["forever"]["playing_piece"]["title"] == "Duskwood 1: Fight"

        # The fight is over: the piece that was playing is picked up where it was left, not begun again.
        say(app, zone_name="Duskwood", speed=7.0)
        back = await until(in_piece(walk), "the piece to be picked up after the fight", timeout=40.0)
        assert back["piece"]["at"] >= left_at - 2.0, "it began again instead of being picked up"
        before = back["time"]
        later = await until(lambda: next((s for s in conductor.statuses.values() if s.get("time", 0) > before + 3), None),
                            "the audio clock to move on")
        assert later["late"] == 0 and not later["resting"]
        assert not [note for note in conductor.notes if "problem" in note], conductor.notes
    finally:
        chrome.terminate()
        await chrome.wait()
        await server.close()


async def _get(server, path):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        response = await session.get(server.make_url(path))
        await response.read()
        return response
