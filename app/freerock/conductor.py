"""The music side of the server.

The conductor listens to the game's state on the hub, asks the director what should be heard,
chooses which music from the library to play for the zone, and tells every connected player page.
It also hands the player the audio it asks for.

Add it to the server with `attach(app)`. It adds the player page, the audio route and the
player's WebSocket, and starts its own loop when the server starts.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from . import atlas
from . import state as game
from .director import Director, Target
from .library import Asset, Library
from .settings import Settings

log = logging.getLogger("freerock.conductor")

PLAYER_DIR = Path(__file__).resolve().parent / "web" / "player"
PLAYER_FILES = {"player.html": "text/html", "player.js": "application/javascript",
                "engine.js": "application/javascript", "player.css": "text/css"}
STEP_S = 0.25          # how often the director is asked again while nothing changes
TICK_S = 1.0           # how often the players are nudged, so their queue never depends on a timer


def slug(name: str | None) -> str | None:
    """A zone name as the library files it: "Elwynn Forest" -> "elwynn-forest". None if there is
    no name to go on."""
    return (atlas.slug(name) or None) if name else None


class Conductor:
    def __init__(self, hub: game.Hub, library: Library, director: Director | None = None,
                 clock=time.monotonic):
        self.hub = hub
        self.library = library
        self.director = director or Director()
        self.clock = clock
        self.players: set[web.WebSocketResponse] = set()
        self.asset: Asset | None = None
        self.borrowed = False            # the zone has no music of its own yet; another zone's is playing
        self.target: Target | None = None
        self.statuses: dict[int, dict[str, Any]] = {}   # what each player page last reported
        self.notes: list[str] = []       # things worth showing on the control page
        self._task: asyncio.Task | None = None
        self._sent_asset: str | None = None

    # --- choosing the music ----------------------------------------------------------------------

    def choose_asset(self, state: game.GameState) -> tuple[Asset | None, bool]:
        """The music for where the player is: the zone's own if the library has any, otherwise the
        most recent music from anywhere. Returns (asset, borrowed)."""
        usable = [asset for asset in self.library.assets() if not asset.banned]
        if not usable:
            return None, False
        wanted = {slug(state.instance_name) if state.in_instance else slug(state.zone_name)}
        own = [asset for asset in usable if asset.zone in wanted or slug(asset.zone) in wanted
               or any(name and name.startswith(asset.zone) for name in wanted)]
        if own:
            keep = [asset for asset in own if self.asset and asset.id == self.asset.id]
            return (keep[0] if keep else own[-1]), False
        if self.asset and any(asset.id == self.asset.id for asset in usable):
            return self.asset, True
        return usable[-1], True

    # --- talking to the players ------------------------------------------------------------------

    async def _send(self, socket: web.WebSocketResponse, message: dict[str, Any]) -> None:
        try:
            await socket.send_str(json.dumps(message))
        except (ConnectionResetError, RuntimeError) as error:
            # The page went away between two messages. It is dropped here; its own handler logs
            # the disconnect.
            log.info("a player page could not be reached and is dropped: %r", error)
            self.players.discard(socket)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        for socket in list(self.players):
            await self._send(socket, message)

    def _asset_message(self) -> dict[str, Any]:
        asset = self.asset
        return {"type": "asset", "borrowed": self.borrowed,
                "asset": {**asset.to_json(), "bar_frames": asset.bar_frames}}

    def _target_message(self) -> dict[str, Any]:
        state = self.hub.state
        return {"type": "target", "target": self.target.as_dict(), "link": self.hub.link.value,
                "where": {"zone": state.zone_name if state else None,
                          "subzone": state.subzone_name if state else None,
                          "instance": state.instance_name if state else None}}

    async def step(self) -> None:
        """Looks at the game once and tells the players whatever has changed."""
        state = self.hub.state
        if state is None:
            return                      # nothing has been heard from the game yet
        if self.hub.link in (game.Link.LOST, game.Link.NEVER):
            target = Target(silent=True, fade_s=2.0, why=("the game cannot be seen",))
        else:
            target = self.director.update(state, self.clock())
        asset, borrowed = self.choose_asset(state)
        if asset is not None and (self.asset is None or asset.id != self.asset.id):
            self.asset, self.borrowed = asset, borrowed
            where = state.zone_name or "this zone"
            self.notes.append("%s has no music of its own yet; playing %s's." % (where, asset.zone)
                              if borrowed else "Playing %s's music." % asset.zone)
        if self.asset is not None and self._sent_asset != self.asset.id:
            self._sent_asset = self.asset.id
            await self._broadcast(self._asset_message())
        if target != self.target:
            self.target = target
            await self._broadcast(self._target_message())

    async def _handle(self, event: object) -> None:
        if isinstance(event, game.CommandReceived):
            if event.name == "skip":
                await self._broadcast({"type": "skip"})
            elif event.name in ("love", "ban") and self.asset is not None:
                self.library.mark(self.asset.id, loved=True if event.name == "love" else None,
                                  banned=True if event.name == "ban" else None)
                self.notes.append("%s marked as %s." % (self.asset.id, "loved" if event.name == "love" else "banned"))
                if event.name == "ban":
                    self._sent_asset = None      # choose again without it
        elif isinstance(event, game.MomentReceived):
            await self._broadcast({"type": "moment", "name": event.name})

    async def run(self) -> None:
        """Runs until cancelled: reacts to every event from the game, and looks again a few times
        a second so that rules that depend on time (a fight that lasts, a storm that stays) move."""
        subscription = self.hub.subscribe()
        last_tick = self.clock()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=STEP_S)
                except asyncio.TimeoutError:
                    event = None
                except game.Overrun as behind:
                    # The hub says how to recover: its current state is still right.
                    log.warning("the conductor fell behind: %s", behind)
                    event = None
                if event is not None:
                    await self._handle(event)
                await self.step()
                if self.clock() - last_tick >= TICK_S:
                    last_tick = self.clock()
                    await self._broadcast({"type": "tick"})
        finally:
            subscription.close()

    # --- the routes ------------------------------------------------------------------------------

    async def player_socket(self, request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse(heartbeat=20)
        await socket.prepare(request)
        self.players.add(socket)
        try:
            await self._send(socket, {"type": "hello"})
            if self.asset is not None:
                await self._send(socket, self._asset_message())
            if self.target is not None:
                await self._send(socket, self._target_message())
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    continue
                report = json.loads(message.data)
                if report.get("type") == "status":
                    self.statuses[id(socket)] = report
                elif report.get("type") == "problem":
                    note = "The player page reported a problem: %s" % report.get("message")
                    log.error(note)
                    self.notes.append(note)
        finally:
            self.players.discard(socket)
            self.statuses.pop(id(socket), None)
        return socket

    async def audio(self, request: web.Request) -> web.Response:
        try:
            asset = self.library.get(request.match_info["asset"])
            start, end = int(request.query["start"]), int(request.query["end"])
            if end - start > asset.rate * 60:
                raise ValueError("more than a minute asked for at once")
            data = self.library.samples(asset, request.match_info["layer"], start, end)
        except (KeyError, ValueError) as error:
            raise web.HTTPBadRequest(text="Cannot give that audio: %s" % error)
        return web.Response(body=data, content_type="application/octet-stream",
                            headers={"Cache-Control": "max-age=3600"})

    async def page(self, request: web.Request) -> web.FileResponse:
        name = request.match_info.get("name", "player.html")
        if name not in PLAYER_FILES:
            raise web.HTTPNotFound()
        return web.FileResponse(PLAYER_DIR / name, headers={"Content-Type": PLAYER_FILES[name],
                                                            "Cache-Control": "no-cache"})

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "asset": self.asset.id if self.asset else None,
            "zone_of_asset": self.asset.zone if self.asset else None, "borrowed": self.borrowed,
            "target": self.target.as_dict() if self.target else None,
            "players": list(self.statuses.values()), "players_connected": len(self.players),
            "notes": self.notes[-20:]})


def _ended(conductor: Conductor, task: asyncio.Task) -> None:
    """The conductor's loop is meant to run for as long as the server does. If it stops with an
    error the music would freeze without a word, so the error is logged and kept for the control
    page."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        note = "The conductor stopped with an error: %r. Restart the server." % (error,)
        log.error(note, exc_info=error)
        conductor.notes.append(note)


async def _start(app: web.Application) -> None:
    conductor: Conductor = app["conductor"]
    conductor._task = asyncio.create_task(conductor.run(), name="freerock-conductor")
    conductor._task.add_done_callback(lambda task: _ended(conductor, task))


async def _stop(app: web.Application) -> None:
    conductor: Conductor = app["conductor"]
    for socket in list(conductor.players):
        await socket.close()
    if conductor._task is not None and not conductor._task.done():
        conductor._task.cancel()
        # Being cancelled is how this loop is meant to end; any other error was already reported
        # by _ended when it happened.
        with contextlib.suppress(asyncio.CancelledError):
            await conductor._task


def attach(app: web.Application, library: Library | None = None,
           director: Director | None = None, clock=time.monotonic) -> Conductor:
    """Adds the music side to a server made by server.create_app()."""
    conductor = Conductor(app["hub"], library or Library(Settings().library_dir), director, clock)
    app["conductor"] = conductor
    app.router.add_get("/player", conductor.page)
    app.router.add_get("/player/{name}", conductor.page)
    app.router.add_get("/ws/player", conductor.player_socket)
    app.router.add_get("/audio/{asset}/{layer}", conductor.audio)
    app.router.add_get("/api/music", conductor.status)
    app.on_startup.append(_start)
    app.on_cleanup.append(_stop)
    return conductor
