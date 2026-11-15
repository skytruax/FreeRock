"""Playing a scripted session through the real player, faster than real time.

A session is a list of moments at which the game's state changes. The director turns it into the
targets the player would be sent, and the player's own engine (the same engine.js the live page
uses) renders the result in headless Chrome with the real music from the library. What comes back
is the audio the gaming PC would have played, as numbers that can be measured and as a clip that
can be listened to.
"""
from __future__ import annotations

import asyncio
import dataclasses
import random
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from aiohttp import web

from .audio import pcm16_to_float
from .director import Director, Rules, playable
from .library import Asset, Library, merged
from .state import GameState

PLAYER_DIR = Path(__file__).resolve().parent / "web" / "player"
STEP_S = 0.25


class RenderFailed(RuntimeError):
    """The page could not render the session; the message is what it reported."""


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


def timeline(session: list[tuple[float, dict[str, Any]]], seconds: float, music: list[Asset],
             start: GameState | None = None, rules: Rules | None = None,
             seed: int = 1) -> list[tuple[float, dict]]:
    """The targets the player would be sent over a session: (time, target) each time it changes.

    `session` is a list of (time, {field: value}) changes to the game's state, and `music` is
    everything the place has (its core suite and any later sets). The place in each target is
    already narrowed to a kind of section that music has.
    """
    director = Director(rules, rng=random.Random(seed))
    state = start or GameState(daytime=True)
    changes = sorted(session, key=lambda item: item[0])
    roles = {section.role for asset in music for section in asset.sections}
    out: list[tuple[float, dict]] = []
    last = None
    for tick in range(int(round(seconds / STEP_S)) + 1):
        now = tick * STEP_S
        while changes and changes[0][0] <= now + 1e-9:
            state = dataclasses.replace(state, **changes.pop(0)[1])
        target = director.update(state, now)
        if target != last:
            last = target
            sent = target.as_dict()
            sent["place"] = playable(target.place, roles)
            out.append((now, sent))
    return out


async def render(library: Library, music: list[Asset], script: list[tuple[float, dict]], seconds: float,
                 chrome: str | None = None, timeout: float = 300.0) -> tuple[np.ndarray, dict[str, Any]]:
    """Renders `script` (from `timeline`) with the real engine and a place's whole music. Returns
    (audio, what the engine scheduled). Raises RenderFailed with the page's own words if it
    could not."""
    chrome = chrome or find_chrome()
    if chrome is None:
        raise RenderFailed("Chrome is not installed, and the player's engine needs a browser to run in")
    finished = asyncio.Event()
    got: dict[str, Any] = {}

    async def page(request: web.Request) -> web.FileResponse:
        return web.FileResponse(PLAYER_DIR / "render.html")

    async def engine(request: web.Request) -> web.FileResponse:
        return web.FileResponse(PLAYER_DIR / "engine.js")

    async def job(request: web.Request) -> web.Response:
        return web.json_response({"asset": merged(music), "seconds": seconds, "script": script})

    by_id = {asset.id: asset for asset in music}

    async def audio(request: web.Request) -> web.Response:
        try:
            data = library.samples(by_id[request.match_info["asset"]], request.match_info["layer"],
                                   int(request.query["start"]), int(request.query["end"]))
        except (KeyError, ValueError) as error:
            raise web.HTTPBadRequest(text=str(error))
        return web.Response(body=data, content_type="application/octet-stream")

    async def log(request: web.Request) -> web.Response:
        got["log"] = await request.json()
        return web.Response(text="ok")

    async def done(request: web.Request) -> web.Response:
        got["audio"] = await request.read()
        finished.set()
        return web.Response(text="ok")

    async def failed(request: web.Request) -> web.Response:
        got["error"] = await request.text()
        finished.set()
        return web.Response(text="ok")

    app = web.Application(client_max_size=512 * 1024 * 1024)
    app.router.add_get("/render", page)
    app.router.add_get("/player/engine.js", engine)
    app.router.add_get("/render/job", job)
    app.router.add_get("/audio/{asset}/{layer}", audio)
    app.router.add_post("/render/log", log)
    app.router.add_post("/render/done", done)
    app.router.add_post("/render/failed", failed)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="freerock-chrome-") as profile:
        process = await asyncio.create_subprocess_exec(
            chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + profile,
            "http://127.0.0.1:%d/render" % port,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            await asyncio.wait_for(finished.wait(), timeout)
        except asyncio.TimeoutError:
            process.terminate()
            _, err = await process.communicate()
            raise RenderFailed("The render gave nothing back in %.0f s. Chrome said: %s"
                               % (timeout, err.decode("utf-8", "replace")[-1500:]))
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()
            await runner.cleanup()
    if "error" in got:
        raise RenderFailed(got["error"])
    return pcm16_to_float(got["audio"], 2), got.get("log", {})
