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

from . import atlas, composer
from . import state as game
from .director import Director, Target
from .eleven import AllowanceExceeded, ElevenError
from .ingest import Ingest, TrackFailedChecks
from .library import Asset, Library, merged
from .playtime import Playtime
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
SECOND_AFTER_S = 600.0   # time in a place before its music gets a second set
FRESH_EVERY_S = 7200.0   # time in a place between fresh sets after that
MAX_FRESH = 3            # fresh sets a place keeps in rotation; an older one is retired for a newer
GROWTH_SHARE = 0.6       # the part of the monthly allowance that goes on growing places' music
GROWTH_FLOAT = 6.0       # minutes of growth allowed before any hours have been played


def slug(name: str | None) -> str | None:
    """A zone name as the library files it: "Elwynn Forest" -> "elwynn-forest". None if there is
    no name to go on."""
    return (atlas.slug(name) or None) if name else None


class Conductor:
    def __init__(self, hub: game.Hub, library: Library, director: Director | None = None,
                 clock=time.monotonic, ingest: Ingest | None = None,
                 settings: Settings | None = None, playtime: Playtime | None = None):
        self.hub = hub
        self.library = library
        self.director = director or Director()
        self.clock = clock
        self.ingest = ingest             # None: play what the library has, make nothing new
        self.settings = settings or Settings()
        self.playtime = playtime or Playtime(self.settings.var_dir / "playtime.json")
        self._last_step: float | None = None
        self.making: str | None = None   # the zone music is being made for right now
        self._making_task: asyncio.Task | None = None
        self._seen_in: tuple[str, float] | None = None   # (zone, when the player was first seen there)
        self._tries: dict[str, int] = {}
        self._paused_until = 0.0
        self.players: set[web.WebSocketResponse] = set()
        self.assets: list[Asset] = []    # the music that is playing: a core suite and any later sets
        self.borrowed = False            # the zone has no music of its own yet; another zone's is playing
        self.target: Target | None = None
        self.statuses: dict[int, dict[str, Any]] = {}   # what each player page last reported
        self.notes: list[str] = []       # things worth showing on the control page
        self._task: asyncio.Task | None = None
        self._sent_asset: str | None = None
        self._volume: int | None = None  # the volume last passed on from the game
        self._pretend_state: game.GameState | None = None   # the last state the pretend game set
        self._noted: tuple | None = None     # the place and music last written to the notes
        self._told: tuple | None = None      # what the players were last told
        self._pretend_may_make = False

    # --- choosing the music ----------------------------------------------------------------------

    @staticmethod
    def place_name(state: game.GameState) -> str | None:
        """The name music is filed under for where the player is: the dungeon inside one, the
        zone otherwise. None while the name has not arrived from the game yet."""
        return state.instance_name if state.in_instance else state.zone_name

    def place_key(self, state: game.GameState) -> str | None:
        return slug(self.place_name(state))

    @property
    def asset(self) -> Asset | None:
        """The first piece of the music that is playing (a place's core suite, as a rule)."""
        return self.assets[0] if self.assets else None

    @property
    def view_id(self) -> str | None:
        """Names exactly the music that is playing, sets and all; it changes when a set is added."""
        return "+".join(asset.id for asset in self.assets) if self.assets else None

    def choose(self, state: game.GameState) -> tuple[list[Asset], bool]:
        """The music for where the player is: everything the place has of its own, otherwise the
        music that was already playing, otherwise the newest place's. Returns (music, borrowed)."""
        usable = self.library.usable()
        if not usable:
            return [], False
        wanted = self.place_key(state)
        own = [asset for asset in usable if asset.zone == wanted]
        if own:
            return own, False
        playing = self.assets[0].zone if self.assets else None
        if playing is None or not any(asset.zone == playing for asset in usable):
            playing = max(usable, key=lambda asset: asset.created).zone
        return [asset for asset in usable if asset.zone == playing], True

    def playing_asset_id(self) -> str | None:
        """Which request the section a player is playing right now came from: what love and ban
        apply to. The first piece of the music if no player has said."""
        ours = {asset.id for asset in self.assets}
        for status in self.statuses.values():
            if status.get("asset_id") in ours:
                return status["asset_id"]
        return self.assets[0].id if self.assets else None

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
        return {"type": "asset", "borrowed": self.borrowed, "asset": merged(self.assets)}

    def _target_message(self) -> dict[str, Any]:
        state = self.hub.state
        return {"type": "target", "target": self.target.as_dict(), "link": self.hub.link.value,
                # The volume set in the game with /rock volume, 0 to 100; the page's own volume
                # control follows it whenever it changes.
                "game_volume": state.volume if state else None,
                "music": {"zone": self.asset.zone if self.asset else None, "borrowed": self.borrowed},
                "where": {"zone": state.zone_name if state else None,
                          "subzone": state.subzone_name if state else None,
                          "instance": state.instance_name if state else None}}

    async def step(self) -> None:
        """Looks at the game once and tells the players whatever has changed."""
        state = self.hub.state
        if state is None:
            return                      # nothing has been heard from the game yet
        now = self.clock()
        live = self.hub.link is game.Link.LIVE and state.enabled
        if self._last_step is not None and live:
            # Time counts as played while the game is in sight and FreeRock is on. A gap of more
            # than a couple of seconds (the server was busy, the machine slept) is not counted.
            self.playtime.add(self.place_key(state), min(now - self._last_step, 2.0))
        self._last_step = now
        if self.hub.link in (game.Link.LOST, game.Link.NEVER):
            target = Target(silent=True, fade_s=2.0, why=("the game cannot be seen",))
        else:
            target = self.director.update(state, now)
        music, borrowed = self.choose(state)
        if music:
            # Said once for each place, and again if the music under it changes: whose music is
            # playing, and whether the place is borrowing it.
            place = (self.place_key(state), music[0].zone, borrowed)
            if place[0] and place != self._noted:
                self._noted = place
                self.notes.append("%s has no music of its own yet; playing %s's."
                                  % (self.place_name(state), music[0].zone)
                                  if borrowed else "Playing %s's music." % music[0].zone)
            self.assets, self.borrowed = music, borrowed
        if self.assets and self._sent_asset != self.view_id:
            self._sent_asset = self.view_id
            await self._broadcast(self._asset_message())
        told = (target, state.volume, self.view_id, self.borrowed)
        if told != self._told:
            self.target, self._volume, self._told = target, state.volume, told
            await self._broadcast(self._target_message())
        self._consider_making(state)

    # --- making new music --------------------------------------------------------------------

    def _consider_making(self, state: game.GameState) -> None:
        """Starts making music for the zone the player is in, if it has none of its own, the
        player has stayed a moment, and nothing else is being made."""
        if self.ingest is None or self.making is not None:
            return
        if state is self._pretend_state and not self._pretend_may_make:
            return                       # a pretend game that has not asked for new music
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
        name = self.place_name(state)
        if not any(asset.zone == key for asset in self.library.assets()):
            kind = "core"                # the place has no music at all (banned music is not remade)
        else:
            kind = self._growth_due(name, key)
            if kind is None:
                return
        tried = key + ":" + kind
        if self._tries.get(tried, 0) >= TRIES:
            return
        self.making = key
        self._tries[tried] = self._tries.get(tried, 0) + 1
        again = self._tries[tried] > 1
        if kind == "core":
            self.notes.append("Making music for %s." % name)
            job = self.ingest.core_suite(name, reroll=again)
        else:
            self.notes.append("Making more music for %s (a %s set)." % (name, kind))
            core = next(asset for asset in self.library.usable(key) if asset.set == "core")
            job = self.ingest.later_set(core, name, kind, reroll=again)
        self._making_task = asyncio.create_task(job, name="freerock-making-" + tried)
        self._making_task.add_done_callback(lambda task: self._made(name, key, kind, task))

    def _growth_due(self, name: str | None, key: str) -> str | None:
        """Whether the place the player is in has earned more music, and which kind: a second set
        once some time has been spent there, a fresh set every couple of hours after that. None
        if it has not, or if the month's growth has run ahead of the hours played."""
        own = self.library.usable(key)
        if not any(asset.set == "core" for asset in own):
            return None                  # its core suite was banned; nothing to grow from
        if not any(asset.set == "second" for asset in self.library.assets(key)):
            if self.playtime.place_seconds(key) < SECOND_AFTER_S:
                return None
            kind = "second"
        else:
            if self.playtime.since_set(key) < FRESH_EVERY_S:
                return None
            kind = "fresh"
        profile = atlas.profile_for(name)
        maker = composer.second_set if kind == "second" else composer.fresh_set
        minutes = maker(profile, part_bars=atlas.part_bars(profile.bpm)).minutes
        return kind if self.growth_left() >= minutes else None

    def growth_left(self) -> float:
        """Minutes that may still go on growing places' music right now. A share of the monthly
        allowance is kept for this and released as the month's hours are played, so a month
        planned for a hundred hours still has new music coming in its last week."""
        budget = self.settings.monthly_minutes * GROWTH_SHARE
        played = min(self.playtime.month_hours() / self.settings.hours_per_month, 1.0)
        earned = min(GROWTH_FLOAT + budget * played, budget)
        return earned - self.playtime.growth_minutes()

    def _retire_old_sets(self, key: str) -> None:
        """A place keeps a few fresh sets in rotation. When a newer one arrives the oldest that has
        not been marked as loved is set aside (kept on disk, no longer played)."""
        fresh = [asset for asset in self.library.usable(key) if asset.set == "fresh"]
        spare = [asset for asset in fresh if not asset.loved]
        while len(fresh) > MAX_FRESH and spare:
            oldest = spare.pop(0)
            self.library.mark(oldest.id, retired=True)
            fresh.remove(oldest)
            self.notes.append("Set aside an older set (%s) to make room for the new one." % oldest.id)

    def _made(self, name: str, key: str, kind: str, task: asyncio.Task) -> None:
        self.making = None
        tried = key + ":" + kind
        if task.cancelled():
            return
        error = task.exception()
        if error is None:
            made = task.result()
            if kind != "core":
                self.playtime.set_made(key, made.asset.minutes)
                self._retire_old_sets(key)
            self.notes.append("%s for %s is ready (first audio after %.1f s, all of it after %.1f s, "
                              "layers split in %.0f s)." % (
                                  "New music" if kind == "core" else "More music (a %s set)" % kind, name,
                                  made.first_audio_s or 0.0, made.total_s or 0.0, made.split_s))
        elif isinstance(error, TrackFailedChecks):
            again = self._tries.get(tried, 0) < TRIES
            self.notes.append("%s %s" % (error, "Trying once more." if again else "Not trying again."))
        elif isinstance(error, AllowanceExceeded):
            self._tries[tried] -= 1      # nothing was asked for, so it does not count as a try
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
            elif event.name in ("love", "ban") and self.assets:
                # Love and ban are about what is playing at this moment: the set the section came
                # from, not the whole of a place's music.
                which = self.playing_asset_id()
                self.library.mark(which, loved=True if event.name == "love" else None,
                                  banned=True if event.name == "ban" else None)
                self.notes.append("%s marked as %s." % (which, "loved" if event.name == "love" else "banned"))
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
            if self.assets:
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
        # The server has no login, so a page must not be able to spend the allowance by accident:
        # a pretend zone with no music only has some made when the request says so outright.
        self._pretend_may_make = bool(fields.pop("make_new_music", False))
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
        self._pretend_state = state
        self.hub.publish(game.StateChanged(state=state, previous=previous, changed=changed))
        return web.json_response({"ok": True})

    async def zones(self, request: web.Request) -> web.Response:
        have = {asset.zone for asset in self.library.assets() if not asset.banned}
        return web.json_response([{"name": name, "has_music": atlas.slug(name) in have}
                                  for name in atlas.names()])

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "asset": self.view_id,
            "zone_of_asset": self.asset.zone if self.asset else None, "borrowed": self.borrowed,
            "hours_this_month": round(self.playtime.month_hours(), 2),
            "growth_minutes_left": round(self.growth_left(), 2),
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
    conductor.playtime.save()
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
           ingest: Ingest | None = None, settings: Settings | None = None,
           playtime: Playtime | None = None) -> Conductor:
    """Adds the music side to a server made by server.create_app(). With an `ingest`, music is
    made for zones that have none and grown where time is spent; without one, only what is in the
    library is played."""
    settings = settings or Settings()
    conductor = Conductor(app["hub"], library or Library(settings.library_dir), director, clock, ingest,
                          settings=settings, playtime=playtime)
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
