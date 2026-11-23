"""The real player page, left open in headless Chrome while the server goes away and comes back, its bucket built again.

The page stands in a frame of one the test serves, so that the test can look at its address and speak to it. Skipped where
Chrome is not installed.
"""
import asyncio
import os
import time

import numpy as np
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from freerock import conductor as music
from freerock import forever, pieces, studio
from freerock.server import ServerConfig, create_app
from freerock.settings import Settings
from test_player_page import CHROME, say, until

pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed on this machine")
RATE = forever.RATE
BARS = 8                        # to a part of a song, a bar a second

FRAME = """<!doctype html><html><body><iframe id="page" src="%s" allow="autoplay" style="width:900px;height:700px"></iframe><script>
const page = document.getElementById("page");
let away = false;
setInterval(() => {
  const inside = page.contentWindow;
  if (!inside || !inside.document || !inside.document.getElementById("banner")) return;
  if (!away && inside.document.getElementById("banner").textContent.includes("cannot be reached")) {
    away = true;
    inside.dispatchEvent(new inside.ErrorEvent("error", { message: "made up while the server was away", filename: "a-test", lineno: 1 }));
  }
  fetch("/seen", { method: "POST", body: JSON.stringify({ search: inside.location.search, away }) }).catch(() => {});  // (the server is away at times)
}, 200);
</script></body></html>"""


def _app(var, seen, address="/player"):
    app = create_app(ServerConfig(var_dir=var, keep_log=False))
    conductor = music.attach(app, settings=Settings(var_dir=var))

    async def frame(request):
        return web.Response(text=FRAME % address, content_type="text/html")

    async def told(request):
        seen.update(await request.json())
        return web.Response(text="ok")

    app.router.add_get("/frame", frame)
    app.router.add_post("/seen", told)
    return app, conductor


async def _chrome(server, tmp_path):
    return await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--mute-audio", "--disable-gpu", "--no-first-run", "--user-data-dir=%s" % (tmp_path / "chrome"),
        "--autoplay-policy=no-user-gesture-required", str(server.make_url("/frame")),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)


def _song(var, family, title, hz, ago=7200.0):
    """A staged song of five parts; staged a while ago, or now (`ago` 0) with other audio: the same take made again."""
    folder = var / "studio" / "knight" / family / "1"
    frames = 5 * BARS * RATE + 2 * RATE
    wave = np.sin(2 * np.pi * hz * np.arange(frames) / RATE).astype(np.float32)
    parts = {channel: np.stack([level * wave] * 2, axis=1) for channel, level in (("lead", 0.1), ("rhythm", 0.1), ("drums", 0.2), ("bass", 0.2))}
    meta = {"style": "knight", "family": family, "take": 1, "title": title, "tempo": 240.0, "beats": 4, "bar_frames": float(RATE),
            "tonic": "D minor", "moods": ["haunted"], "role": "wander", "serves": [0, 1, 2], "light": False,
            "sections": [{"story": story, "bars": BARS} for story in forever.STORY], "floor": {}, "follow": {}, "post_s": 2.0,
            "credit": "a test", "seed": 1}
    studio.write_track(folder, meta, parts)
    for path in folder.iterdir():
        os.utime(path, (time.time() - ago, time.time() - ago))
    return folder


def _playing(conductor):
    return next((s for s in conductor.statuses.values() if s.get("forever") and s.get("playing") and s.get("piece")), None)


async def test_a_page_left_open_plays_its_song_to_the_end_across_a_rebuild(tmp_path):
    """("songs without ends that abruptly cut off and some others the player was looking for that no longer existed", "i think
    the player has an old manifest", 2026-11-23.) While a song plays, the server stops, a bucket in which that song was made
    again is put in its place, and the server starts: the song goes on through its parts to its close, and nothing is asked
    for that is not there."""
    var, seen = tmp_path / "var", {}
    for family, title, hz in (("first-family", "First Song", 220.0), ("second-family", "Second Song", 330.0)):
        _song(var, family, title, hz)
    bucket = forever.Buckets(var / "buckets").get("Duskwood", "knight")
    with bucket.saved_once():
        pieces.add_staged(bucket, var, "knight")
    app, conductor = _app(var, seen)
    server = TestServer(app)
    await server.start_server()
    port = server.port
    say(app, zone_name="Duskwood", speed=7.0)
    chrome = await _chrome(server, tmp_path)
    second = None
    try:
        status = await until(lambda: _playing(conductor), "the page to start a song")
        song = status["piece"]["title"].split(" (")[0]
        family = "first-family" if song == "First Song" else "second-family"
        _song(var, family, song, 247.0, ago=0.0)                             # that very song is made again
        built, done = await asyncio.to_thread(pieces.build_beside, var, "knight")
        assert (done["put"], done["taken"], done["wrong"]) == (2, 1, [])
        heard = [_playing(conductor)["piece"]["title"]]
        await server.close()
        await asyncio.to_thread(pieces.swap, var, "knight")
        app, conductor = _app(var, seen)
        second = TestServer(app, port=port)
        await second.start_server()
        say(app, zone_name="Duskwood", speed=7.0)
        await until(lambda: _playing(conductor), "the page to come back")
        assert len(conductor.bucket.pieces) == 10

        def watched():
            now = _playing(conductor)
            if now and now["piece"]["title"] != heard[-1]:
                heard.append(now["piece"]["title"])
            return heard[-1].endswith("(close)") or not heard[-1].startswith(song)

        await until(watched, "the song to come to its end", 90.0)
        words = [title.split("(")[1].rstrip(")") for title in heard]
        assert all(title.startswith(song) for title in heard), heard
        assert words == list(forever.STORY)[forever.STORY.index(words[0]):], heard
        assert _playing(conductor)["late"] == 0
        assert not [note for note in conductor.notes if "problem" in note and "made up" not in note], conductor.notes
    finally:
        chrome.terminate()
        await chrome.wait()
        await (second or server).close()


async def test_a_song_asked_for_in_the_address_is_asked_for_once(tmp_path):
    """A reload must not ask for it again: it leaves the page's address as it is played, or not found; the rest of the address stays."""
    var, seen = tmp_path / "var", {}
    _song(var, "first-family", "First Song", 220.0)
    bucket = forever.Buckets(var / "buckets").get("Duskwood", "knight")
    pieces.add_staged(bucket, var, "knight")
    app, conductor = _app(var, seen, "/player?keep=1&cue=knight/nowhere-family/1&at=climb")
    server = TestServer(app)
    await server.start_server()
    say(app, zone_name="Duskwood", speed=7.0)
    chrome = await _chrome(server, tmp_path)
    try:
        await until(lambda: _playing(conductor), "the page to start a song")
        await until(lambda: seen.get("search") == "?keep=1", "the song asked for to leave the address: %s" % seen)
        assert len([note for note in conductor.notes if "knight/nowhere-family/1" in note]) == 1, conductor.notes
    finally:
        chrome.terminate()
        await chrome.wait()
        await server.close()


async def test_what_goes_wrong_while_the_server_is_away_is_told_when_it_is_back(tmp_path):
    var, seen = tmp_path / "var", {}
    _song(var, "first-family", "First Song", 220.0)
    bucket = forever.Buckets(var / "buckets").get("Duskwood", "knight")
    pieces.add_staged(bucket, var, "knight")
    app, conductor = _app(var, seen)
    server = TestServer(app)
    await server.start_server()
    port = server.port
    say(app, zone_name="Duskwood", speed=7.0)
    chrome = await _chrome(server, tmp_path)
    second = None
    try:
        await until(lambda: _playing(conductor), "the page to start a song")
        await server.close()
        await asyncio.sleep(2.0)                                             # (the page sees that it is gone, and the test's own error happens there)
        app, conductor = _app(var, seen)
        second = TestServer(app, port=port)
        await second.start_server()
        say(app, zone_name="Duskwood", speed=7.0)
        await until(lambda: [note for note in conductor.notes if "made up while the server was away" in note], "what went wrong to be told")
        told = [note for note in conductor.notes if "made up" in note]
        assert len(told) == 1 and "with the server out of reach" in told[0], told
        assert [entry for entry in app["link"].log if entry["kind"] == "problem" and "made up" in entry["text"]], "not in the log with its time"
    finally:
        chrome.terminate()
        await chrome.wait()
        await (second or server).close()
