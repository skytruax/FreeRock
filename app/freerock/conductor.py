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
import dataclasses
import json
import logging
import time
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from . import atlas
from . import state as game
from .director import Director, Target
from .eleven import AllowanceExceeded, ElevenError
from .ingest import Ingest, TrackFailedChecks
from .library import Asset, Library
from .settings import Settings

log = logging.getLogger("freerock.conductor")

PLAYER_DIR = Path(__file__).resolve().parent / "web" / "player"
PLAYER_FILES = {"player.html": "text/html", "player.js": "application/javascript",
                "engine.js": "application/javascript", "player.css": "text/css"}
STEP_S = 0.25          # how often the director is asked again while nothing changes
TICK_S = 1.0           # how often the players are nudged, so their queue never depends on a timer
DWELL_S = 4.0          # how long the player has been in a zone before music is made for it
TRIES = 2              # how many times music is asked for when a track fails its checks
PAUSE_S = 600.0        # no new music for this long after ElevenLabs reports a problem


def slug(name: str | None) -> str | None:
    """A zone name as the library files it: "Elwynn Forest" -> "elwynn-forest". None if there is
    no name to go on."""
    return (atlas.slug(name) or None) if name else None


class Conductor:
    def __init__(self, hub: game.Hub, library: Library, director: Director | None = None,
                 clock=time.monotonic, ingest: Ingest | None = None):
        self.hub = hub
        self.library = library
        self.director = director or Director()
        self.clock = clock
        self.ingest = ingest             # None: play what the library has, make nothing new
        self.making: str | None = None   # the zone music is being made for right now
        self._making_task: asyncio.Task | None = None
        self._seen_in: tuple[str, float] | None = None   # (zone, when the player was first seen there)
        self._tries: dict[str, int] = {}
        self._paused_until = 0.0
        self.players: set[web.WebSocketResponse] = set()
        self.asset: Asset | None = None
        self.borrowed = False            # the zone has no music of its own yet; another zone's is playing
        self.target: Target | None = None
        self.statuses: dict[int, dict[str, Any]] = {}   # what each player page last reported
        self.notes: list[str] = []       # things worth showing on the control page
        self._task: asyncio.Task | None = None
        self._sent_asset: str | None = None

    # --- choosing the music ----------------------------------------------------------------------

    @staticmethod
    def place_name(state: game.GameState) -> str | None:
        """The name music is filed under for where the player is: the dungeon inside one, the
        zone otherwise. None while the name has not arrived from the game yet."""
        return state.instance_name if state.in_instance else state.zone_name

    def place_key(self, state: game.GameState) -> str | None:
        return slug(self.place_name(state))

    def choose_asset(self, state: game.GameState) -> tuple[Asset | None, bool]:
        """The music for where the player is: the zone's own if the library has any, otherwise the
        most recent music from anywhere. Returns (asset, borrowed)."""
        usable = [asset for asset in self.library.assets() if not asset.banned]
        if not usable:
            return None, False
        wanted = self.place_key(state)
        own = [asset for asset in usable if asset.zone == wanted]
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
        self._consider_making(state)

    # --- making new music --------------------------------------------------------------------

    def _consider_making(self, state: game.GameState) -> None:
        """Starts making music for the zone the player is in, if it has none of its own, the
        player has stayed a moment, and nothing else is being made."""
        if self.ingest is None or self.making is not None:
            return
        now = self.clock()
        key = self.place_key(state)
        if not key:
            self._seen_in = None
            return
        if self._seen_in is None or self._seen_in[0] != key:
            self._seen_in = (key, now)
        # A flight path crosses zones without stopping, a loading screen is not yet anywhere,
        # and with the game out of sight there is nobody to make music for.
        if (self.hub.link is not game.Link.LIVE or not state.enabled or state.on_taxi
                or state.loading or state.cinematic):
            self._seen_in = (key, now)
            return
        if now - self._seen_in[1] < DWELL_S or now < self._paused_until:
            return
        if any(asset.zone == key for asset in self.library.assets()):
            return                       # it has music (banned music is not made again by itself)
        if self._tries.get(key, 0) >= TRIES:
            return
        name = self.place_name(state)
        self.making = key
        self._tries[key] = self._tries.get(key, 0) + 1
        self.notes.append("Making music for %s." % name)
        self._making_task = asyncio.create_task(
            self.ingest.core_suite(name, reroll=self._tries[key] > 1), name="freerock-making-" + key)
        self._making_task.add_done_callback(lambda task: self._made(name, key, task))

    def _made(self, name: str, key: str, task: asyncio.Task) -> None:
        self.making = None
        if task.cancelled():
            return
        error = task.exception()
        if error is None:
            made = task.result()
            self.notes.append("New music for %s is ready (first audio after %.1f s, all of it after %.1f s, "
                              "layers split in %.0f s)." % (name, made.first_audio_s or 0.0,
                                                           made.total_s or 0.0, made.split_s))
        elif isinstance(error, TrackFailedChecks):
            again = self._tries.get(key, 0) < TRIES
            self.notes.append("%s %s" % (error, "Trying once more." if again else "Not trying again."))
        elif isinstance(error, AllowanceExceeded):
            self._tries[key] -= 1        # nothing was asked for, so it does not count as a try
            self._paused_until = self.clock() + PAUSE_S
            self.notes.append(str(error))
        elif isinstance(error, ElevenError):
            self._paused_until = self.clock() + PAUSE_S
            self.notes.append("ElevenLabs would not make music for %s: %s No new music for ten minutes." % (name, error))
        else:
            self._paused_until = self.clock() + PAUSE_S
            note = "Making music for %s failed: %r. No new music for ten minutes." % (name, error)
            log.error(note, exc_info=error)
            self.notes.append(note)

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

    async def pretend(self, request: web.Request) -> web.Response:
        """Says the game is in the state given, as if the strip had been read. For trying the
        music without the game; with the real game connected the two would talk over each other."""
        fields = await request.json()
        allowed = {field.name for field in dataclasses.fields(game.GameState)}
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise web.HTTPBadRequest(text="The game state has no %s" % ", ".join(unknown))
        if "position" in fields and fields["position"] is not None:
            fields["position"] = tuple(fields["position"])
        try:
            state = game.GameState(**fields)
        except TypeError as error:
            raise web.HTTPBadRequest(text="Cannot make a game state from that: %s" % error)
        if self.hub.link is not game.Link.LIVE:
            self.hub.publish(game.LinkChanged(link=game.Link.LIVE, previous=self.hub.link))
        previous = self.hub.state
        changed = frozenset(name for name in allowed
                            if previous is None or getattr(previous, name) != getattr(state, name))
        self.hub.publish(game.StateChanged(state=state, previous=previous, changed=changed))
        return web.json_response({"ok": True})

    async def zones(self, request: web.Request) -> web.Response:
        have = {asset.zone for asset in self.library.assets() if not asset.banned}
        return web.json_response([{"name": name, "has_music": atlas.slug(name) in have}
                                  for name in atlas.names()])

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "asset": self.asset.id if self.asset else None,
            "zone_of_asset": self.asset.zone if self.asset else None, "borrowed": self.borrowed,
            "target": self.target.as_dict() if self.target else None,
            "players": list(self.statuses.values()), "players_connected": len(self.players),
            "making": self.making, "notes": self.notes[-20:]})


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
    if conductor._making_task is not None and not conductor._making_task.done():
        conductor._making_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await conductor._making_task
    if conductor._task is not None and not conductor._task.done():
        conductor._task.cancel()
        # Being cancelled is how this loop is meant to end; any other error was already reported
        # by _ended when it happened.
        with contextlib.suppress(asyncio.CancelledError):
            await conductor._task


def attach(app: web.Application, library: Library | None = None,
           director: Director | None = None, clock=time.monotonic,
           ingest: Ingest | None = None) -> Conductor:
    """Adds the music side to a server made by server.create_app(). With an `ingest`, music is
    made for zones that have none; without one, only what is in the library is played."""
    conductor = Conductor(app["hub"], library or Library(Settings().library_dir), director, clock, ingest)
    app["conductor"] = conductor
    app.router.add_get("/player", conductor.page)
    app.router.add_get("/player/{name}", conductor.page)
    app.router.add_get("/ws/player", conductor.player_socket)
    app.router.add_get("/audio/{asset}/{layer}", conductor.audio)
    app.router.add_get("/api/music", conductor.status)
    app.router.add_get("/api/zones", conductor.zones)
    app.router.add_post("/api/pretend", conductor.pretend)
    app.on_startup.append(_start)
    app.on_cleanup.append(_stop)
    return conductor
