"""The music side of the server.

The conductor listens to the game's state on the hub, asks the director what should be heard,
and tells every connected player page: the bucket to play from (a style has one, its song, which
goes wherever the player goes), how the five channels are mixed, and what kind of place the
player is in. It also hands the player the phrases and the parts of pieces it asks for.

Add it to the server with `attach(app)`. It adds the player page, the phrase route and the
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

from . import atlas, composer, forever, stemstore
from . import state as game
from .director import Director, Target
from .eleven import AllowanceExceeded, ElevenError
from .server import close_sockets
from .settings import Settings

log = logging.getLogger("freerock.conductor")

PLAYER_DIR = Path(__file__).resolve().parent / "web" / "player"
PLAYER_FILES = {"player.html": "text/html", "player.js": "application/javascript",
                "forever.js": "application/javascript", "player.css": "text/css"}
STEP_S = 0.25          # how often the director is asked again while nothing changes
TICK_S = 1.0           # how often the players are nudged, so their queue never depends on a timer
PAUSE_S = 600.0        # no new phrases for this long after ElevenLabs reports a problem
# Phrases for the bucket of the place the player is in.
FILL_AT_ONCE = 2         # ElevenLabs makes two things at a time for this account
POOL_REST_S = 90.0       # a pool whose phrase failed its checks three times running is left alone this long
BUSY_S = 20.0            # how long to hold off when ElevenLabs is busy or stumbles
SPENT_S = 3600.0         # how long to hold off when the account has nothing left to make music with
SETTLE_S = 20.0          # how long the player has been in a new place before phrases are asked for in its colours
RESTART_GRACE_S = 30.0   # after a start, how long a page that was playing is left to play while the game's sensor finds its way back
ARRIVAL_EVERY_S = 600.0  # and how long before the same place is greeted that way again


def page_version() -> str:
    """Changes whenever a file of the player page changes."""
    return str(max(int((PLAYER_DIR / name).stat().st_mtime) for name in PLAYER_FILES))


def slug(name: str | None) -> str | None:
    """A place's name as FreeRock files it: "Elwynn Forest" -> "elwynn-forest". None if there is
    no name to go on."""
    return (atlas.slug(name) or None) if name else None


class Conductor:
    def __init__(self, hub: game.Hub, director: Director | None = None, clock=time.monotonic,
                 settings: Settings | None = None, filler: forever.Filler | None = None):
        self.hub = hub
        self.director = director or Director()
        self.clock = clock
        self.settings = settings or Settings()
        self._began = clock()
        self._zone_of_map: dict[int, str] = {}           # the zone each of the game's maps belongs to
        self._paused_until = 0.0
        self.players: set[web.WebSocketResponse] = set()
        self.target: Target | None = None
        self.statuses: dict[int, dict[str, Any]] = {}   # what each player page last reported
        self.notes: list[str] = []       # things worth showing on the control page
        self._task: asyncio.Task | None = None
        self._volume: int | None = None  # the volume last passed on from the game
        self._pretend_state: game.GameState | None = None   # the last state the pretend game set
        self._told: tuple | None = None      # what the players were last told
        self._pretend_may_make = False
        self.filler = filler             # None: play what the buckets hold, ask for nothing new
        self.buckets = forever.Buckets(self.settings.var_dir / "buckets")
        self.bucket: forever.Bucket | None = None    # the bucket the players are playing from
        self.mix: dict[str, dict[str, Any]] | None = None    # which channels are up and how hard
        self._sent_bucket: str | None = None
        self._here: tuple[str, float] | None = None  # (the place the player is in, since when)
        self._filling: dict[asyncio.Task, tuple[str, tuple[str, int]]] = {}   # phrases on their way
        self._pool_rested: dict[tuple[str, tuple[str, int]], float] = {}      # pools left alone, until when
        self._last_ask = -1e9
        self.phrases_made = 0
        # Every phrase is also kept as an audio file anyone can open, with a table of what it is.
        self.stems = stemstore.StemStore(self.settings.var_dir / "stems")
        self._arrivals: list[tuple[str, int]] = []   # pools to add to at once: the player is somewhere new
        self._greeted: dict[str, float] = {}         # when each place was last greeted with new phrases
        # The forever song has its own moments of silence, which begin where its form comes
        # round: the player is told about how much music there is between two and about how long
        # one lasts (the settings say), and the director's own rests, which cut in wherever they
        # fall, are off.
        self._silences = {"every_s": self.settings.rest_every_minutes * 60.0, "for_s": self.settings.rest_seconds}
        self.director.rules.rest_every_s = 0.0

    # --- where the player is --------------------------------------------------------------------

    def place_name(self, state: game.GameState) -> str | None:
        """The name music is filed under for where the player is: the dungeon inside one, the
        zone otherwise. None while the name has not arrived from the game yet.

        Inside some buildings the game gives the building's name as the zone's (the Scarlet
        Raven Tavern in Duskwood) while the map stays the zone's. The zone is then the one that
        map was last known to be, and the building is a named place inside it."""
        if state.in_instance:
            return state.instance_name
        name = state.zone_name
        if name and state.map_id:
            if atlas.is_known(name) or state.map_id not in self._zone_of_map:
                self._zone_of_map[state.map_id] = name
            else:
                return self._zone_of_map[state.map_id]
        return name

    def spot_name(self, state: game.GameState) -> str | None:
        """The named place inside the zone the player is in: the subzone, or a building whose
        name the game gave as the zone's."""
        if state.subzone_name:
            return state.subzone_name
        if not state.in_instance and state.zone_name and state.zone_name != self.place_name(state):
            return state.zone_name
        return None

    def kinds_here(self, state: game.GameState | None) -> tuple[list[str], bool]:
        """The kinds of place the player is in (haunted woods, farmland, a desert: kinds.KINDS)
        and whether it is a light one. Nothing while the game has not said where the player is."""
        if state is None:
            return [], False
        return atlas.kinds_for(self.place_name(state), self.spot_name(state))

    def setting_here(self, state: game.GameState | None) -> str:
        """What sort of ground the player is on (atlas.SETTINGS: woods, water, heights, fields...), or ""."""
        if state is None:
            return ""
        return atlas.setting_for(self.place_name(state), self.spot_name(state))

    def shade_here(self, state: game.GameState | None) -> float:
        """How dark or bright it is where the player is (-3 grim to 3 radiant), to the half
        step: the place itself, darker by night, in the rain and under a roof of rock."""
        if state is None:
            return 0.0
        shade = atlas.shade_for(self.place_name(state), self.spot_name(state))
        if state.daytime is False:
            shade -= 1.5                                  # night is darker than a cloud ("night should feel like night")
        if state.weather == "rain" and (state.weather_intensity or 0.0) > 0.0 and not state.indoors:
            shade -= 0.5 if (state.weather_intensity or 0.0) < 0.6 else 1.0
        if state.indoors and not state.resting and not state.in_instance:
            shade -= 1.0                                  # a cave, a mine, a crypt: not an inn
        return round(min(max(shade, -3.0), 3.0) * 2.0) / 2.0

    @property
    def genre(self) -> str:
        """The style in force: whose bucket is played."""
        return self.settings.genre

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

    def _target_message(self) -> dict[str, Any]:
        state = self.hub.state
        target = self.target.as_dict()
        # The mixing desk for the five decks: which channels are up, and how hard each plays.
        target["channels"] = self.mix or forever.mix(self.target)
        # The kind of place the player is in, and whether it is a light one: what written pieces
        # are chosen by.
        target["kinds"], target["light"] = self.kinds_here(state)
        # ...and how dark or bright it is there: among pieces for the same kind of place, the nearest in shade.
        target["shade"] = self.shade_here(state)
        # ...and what sort of ground it is (by a lake, in the woods, on the heights): among those, the piece written for it.
        target["setting"] = self.setting_here(state)
        return {"type": "target", "target": target, "link": self.hub.link.value,
                # The volume set in the game with /rock volume, 0 to 100; the page's own volume
                # control follows it whenever it changes.
                "game_volume": state.volume if state else None,
                "where": {"zone": self.place_name(state) if state and not state.in_instance else None,
                          "subzone": self.spot_name(state) if state else None,
                          "instance": state.instance_name if state else None}}

    async def step(self) -> None:
        """Looks at the game once and tells the players whatever has changed."""
        state = self.hub.state
        if state is None:
            # Nothing has been heard from the game since the program started. For the first half
            # minute that is a restart: the game's sensor needs some seconds to find the new
            # server, and a page that was playing goes on with what it has (on 2026-11-16 a
            # restart was forty seconds of silence in the middle of an evening). After that, a
            # page that is playing is told to be quiet, not left playing to itself.
            if self.clock() - self._began < RESTART_GRACE_S:
                return
            waiting = Target(silent=True, fade_s=2.0, why=("the game has not been seen yet",))
            if self.target != waiting:
                self.target = waiting
                await self._broadcast(self._target_message())
            return
        now = self.clock()
        if self.hub.link in (game.Link.LOST, game.Link.NEVER):
            target = Target(silent=True, fade_s=2.0, why=("the game cannot be seen",))
        else:
            target = self.director.update(state, now)
        await self._forever_step(state, target, now)

    # --- the forever song --------------------------------------------------------------------

    def _bucket_message(self) -> dict[str, Any]:
        told = self.bucket.describe()
        if self.settings.pieces == "off":
            # Written pieces are switched off: the player is told of the loose phrases only.
            told = {**told, "pieces": {}, "clips": [clip for clip in told["clips"] if "piece" not in clip]}
        return {"type": "bucket", "bucket": {**told, "rest": self._silences,
                                             "style": composer.GENRES[self.bucket.genre]["label"]}}

    async def _forever_step(self, state: game.GameState, target: Target, now: float) -> None:
        """One look at the game with the forever song playing: which place's bucket the players
        play from, how the five channels are mixed, and whether another phrase should be asked for."""
        name = self.place_name(state)
        # A style has one bucket, which goes on growing wherever the player goes: the song does
        # not start again at a zone's border. Another style's bucket takes over as soon as it
        # has anything to play, since the style was asked for.
        here = self.buckets.home(self.genre, name)
        if here is not None and here is not self.bucket and here.live():
            self.bucket = here
            loose = sum(1 for clip in here.live() if not clip.piece)
            self.notes.append("Playing the %s song: %d written pieces and %d loose phrases in its bucket so far "
                              "(%d BPM, %s)." % (composer.GENRES[here.genre]["label"], len(here.live_pieces()),
                                                 loose, here.bpm, here.tonic))
        if self.bucket is not None and self._sent_bucket != self.bucket.key:
            self._sent_bucket = self.bucket.key
            await self._broadcast(self._bucket_message())
        mixed = forever.mix(target, self.mix)
        found, light = self.kinds_here(state)
        told = (target, state.volume, self._sent_bucket, json.dumps(mixed, sort_keys=True), tuple(found), light, self.shade_here(state),
                self.setting_here(state))
        if told != self._told:
            self.target, self.mix, self._volume, self._told = target, mixed, state.volume, told
            await self._broadcast(self._target_message())
        # Somewhere new: once the player has stayed a moment, a phrase is asked for at once for
        # every channel that is up, in the new place's colours, so that the song takes the
        # place on within a turn or two of its form.
        place = slug(name)
        if place:
            if self._here is None or self._here[0] != place:
                first = self._here is None
                self._here = (place, now)
                if first:
                    self._greeted[place] = now       # where the music began needs no greeting
            elif (now - self._here[1] >= SETTLE_S and now - self._greeted.get(place, -1e9) >= ARRIVAL_EVERY_S
                  and here is not None and here.started()):
                self._greeted[place] = now
                self._arrivals = list(forever.in_use(self.mix))
                self.notes.append("Now in %s: asking for phrases in its colours." % name)
        self._consider_filling(state, name, now)

    def phrase_words(self, state: game.GameState) -> list[str]:
        """What is true in the game as a phrase is about to be asked for, in a word or two for the
        tune and the drone: the hour and the weather. A phrase is made for the moment it is asked
        for in."""
        words = []
        if state.daytime is False:
            words.append("nocturnal")
        strength = state.weather_intensity or 0.0
        if state.weather == "rain" and strength >= 0.3:
            words.append("rain-soaked")
        elif state.weather == "snow" and strength >= 0.3:
            words.append("hushed and wintry")
        elif state.weather == "sandstorm" and strength >= 0.3:
            words.append("dry desert wind")
        return words

    def _consider_filling(self, state: game.GameState, name: str | None, now: float) -> None:
        """Asks for the next phrase for the bucket of the place the player is in, if one is wanted.

        A place gets phrases as fast as they can be made, two at a time, until every channel has
        some depth at every strength: the hard phrases a fight will want as much as the calm
        ones playing now. After that it goes on being fed one at a time for as long as the game
        is played: first wherever the music is about to run out of phrases nobody has heard, so
        that every change is to something new, then wherever the bucket is shallowest. See
        forever.Bucket.wanted.

        It goes on while the game is out of sight for a moment (the player has looked away from
        it) and through the music's own silences. It stops when the game is gone, on a flight
        path, and when no player page is open."""
        if self.filler is None or not name:
            return
        if state is self._pretend_state and not self._pretend_may_make:
            return                       # a pretend game that has not asked for new music
        if (self.hub.link not in (game.Link.LIVE, game.Link.STALE) or not state.enabled or state.on_taxi
                or state.loading or state.cinematic or not self.players or now < self._paused_until):
            return
        bucket = self.buckets.home(self.genre, name)
        if bucket is None:
            return
        spot = self.spot_name(state)
        profile = atlas.place_profile(name, spot) if spot and slug(spot) != slug(name) else atlas.profile_for(name)
        while len(self._filling) < FILL_AT_ONCE:
            coming: dict[tuple[str, int], int] = {}
            for key, pool in self._filling.values():
                if key == bucket.key:
                    coming[pool] = coming.get(pool, 0) + 1
            resting = {pool for (key, pool), until in self._pool_rested.items() if key == bucket.key and until > now}
            self._arrivals = [pool for pool in self._arrivals if pool not in resting]
            if self._arrivals:
                pool, hurry = self._arrivals.pop(0), True          # the player is somewhere new
            else:
                choice = bucket.wanted(forever.in_use(self.mix), coming, resting)
                if choice is None:
                    return
                pool, hurry = choice
            if not hurry and self._filling:
                return                   # one at a time once every pool has some depth
            self._last_ask = now
            task = asyncio.create_task(self._fill(bucket, profile, pool, self.phrase_words(state)),
                                       name="freerock-phrase-%s-%s-%d" % (bucket.key, pool[0], pool[1]))
            self._filling[task] = (bucket.key, pool)
            task.add_done_callback(self._fill_ended)

    async def _fill(self, bucket: forever.Bucket, profile: composer.ZoneProfile, pool: tuple[str, int],
                    words: list[str]) -> None:
        """Asks for one phrase and, when it has passed its checks, tells the players about it."""
        channel, tier = pool
        what = "%s (%s) for %s" % (channel, forever.TIER_WORDS[tier], bucket.zone)
        try:
            clip = await self.filler.phrase(bucket, profile, channel, tier, context=words)
        except forever.PhraseFailed as failed:
            self._pool_rested[(bucket.key, pool)] = self.clock() + POOL_REST_S
            self.notes.append("%s Leaving that one for a minute and a half." % failed)
            return
        except AllowanceExceeded as over:
            self._paused_until = self.clock() + PAUSE_S
            self.notes.append(str(over))
            return
        except ElevenError as error:
            if error.status == "quota_exceeded":
                # Nothing left to make music with. The song goes on from what the buckets hold,
                # and the phrases that had been set aside as worn come back into play.
                self._paused_until = self.clock() + SPENT_S
                self.notes.append("ElevenLabs has no credits left for new phrases: %s The song carries on from "
                                  "the bucket, with every phrase made so far back in play." % error)
                await self._play_everything()
            elif error.http_status == 429 or error.http_status >= 500:
                self._paused_until = self.clock() + BUSY_S
                self.notes.append("ElevenLabs is busy (%s); asking again in a few seconds." % error)
            else:
                self._pool_rested[(bucket.key, pool)] = self.clock() + POOL_REST_S
                self.notes.append("ElevenLabs would not make a phrase of %s: %s" % (what, error))
            return
        self.phrases_made += 1
        try:
            await asyncio.to_thread(self.stems.add, bucket, clip)
        except OSError as error:
            # The phrase is in the bucket and plays; only its copy for study could not be
            # written (a full disk, say). Said once on the control page each time, and logged.
            note = "The copy of a phrase for the stems folder could not be written: %s" % error
            log.error(note)
            self.notes.append(note)
        gone = bucket.make_room(channel, tier)
        await self._broadcast({"type": "phrase", "key": bucket.key, "clip": bucket.brief(clip)})
        if gone:
            await self._broadcast({"type": "retired", "key": bucket.key, "ids": [worn.id for worn in gone]})

    def _fill_ended(self, task: asyncio.Task) -> None:
        """A phrase has arrived or been turned away. Anything `_fill` did not expect is logged
        and shown on the control page, and nothing more is asked for for a minute."""
        self._filling.pop(task, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            self._paused_until = self.clock() + 60.0
            note = "Making a phrase failed: %r. No new phrases for a minute." % (error,)
            log.error(note, exc_info=error)
            self.notes.append(note)
            return
        # The next one is asked for at once, not at the conductor's next look at the game.
        state = self.hub.state
        if state is not None and self._task is not None and not self._task.done():
            self._consider_filling(state, self.place_name(state), self.clock())

    async def _play_everything(self) -> None:
        """Brings the phrases that were set aside as worn back into play, in every bucket in use."""
        for bucket in {self.bucket, *(self.buckets.by_key(key) for key, _ in self._filling.values())}:
            if bucket is not None and not bucket.everything:
                bucket.everything = True
                if bucket is self.bucket:
                    await self._broadcast(self._bucket_message())

    def _count_phrases(self, report: dict[str, Any]) -> None:
        """Notes the phrases a player says have come in since it last said."""
        heard, key = report.get("heard"), report.get("bucket")
        if not heard or not key:
            return
        try:
            self.buckets.by_key(key).played(heard)
        except KeyError:
            # The page is playing from a bucket this server does not have. Nothing to count.
            log.warning("a player is playing from the bucket %s, which is not here", key)

    def _playing_phrases(self) -> tuple[forever.Bucket, list[str]] | None:
        """The bucket and the phrases a player is playing right now: what love and ban apply to."""
        for status in self.statuses.values():
            playing, key = status.get("playing"), status.get("bucket")
            if playing and key:
                try:
                    return self.buckets.by_key(key), [entry["id"] for entry in playing.values()]
                except KeyError:
                    log.warning("a player is playing from the bucket %s, which is not here", key)
        return None

    async def _handle(self, event: object) -> None:
        if isinstance(event, game.CommandReceived):
            if event.name == "skip":
                await self._broadcast({"type": "skip"})
            elif event.name in ("love", "ban"):
                # Love and ban are about the phrases playing at this moment. Loved ones are never
                # set aside as worn; banned ones are not played again, and the decks playing them
                # move on. A piece of written music is loved or banned whole, every part of it.
                found = self._playing_phrases()
                if found:
                    bucket, ids = found
                    marked = bucket.mark(ids, loved=True) if event.name == "love" else bucket.mark(ids, banned=True)
                    titles = sorted({bucket.pieces[clip.piece]["title"] for clip in marked if clip.piece})
                    what = ("The piece %s is" % " and ".join(titles)) if titles \
                        else "The %d phrases playing are" % len(marked)
                    if event.name == "love":
                        self.notes.append("%s marked as loved." % what)
                    else:
                        self.notes.append("%s banned." % what)
                        await self._broadcast({"type": "retired", "key": bucket.key,
                                               "ids": [clip.id for clip in marked]})
        elif isinstance(event, game.MomentReceived):
            # A level gained, a quest handed in, a boss beaten: the director brings the whole
            # band in for a few seconds, and the next step tells the players.
            if self.director.moment(event.name, self.clock()):
                self.notes.append("A moment in the game: %s." % event.name.replace("_", " "))
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

    def heard(self) -> dict[str, int]:
        """How many player pages are open, and how many of them say they are making sound."""
        playing = sum(1 for status in self.statuses.values()
                      if status.get("started") and status.get("context") == "running")
        return {"connected": len(self.players), "playing": playing}

    async def player_socket(self, request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse(heartbeat=20)
        await socket.prepare(request)
        self.players.add(socket)
        link = request.app.get("link")
        if link is not None:
            link.note("A player page was opened from %s." % (request.remote or "an unknown address"), "player")
        try:
            # The page keeps the version it was loaded with; a different one after a reconnect
            # means the server was updated under it, and it says so.
            await self._send(socket, {"type": "hello", "version": page_version()})
            # What the game asks for goes first, so that the page knows where the player is and
            # what is happening there before it chooses the first music to play.
            if self.target is not None:
                await self._send(socket, self._target_message())
            if self.bucket is not None:
                await self._send(socket, self._bucket_message())
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    continue
                report = json.loads(message.data)
                if report.get("type") == "status":
                    self.statuses[id(socket)] = report
                    self._count_phrases(report)
                elif report.get("type") == "problem":
                    note = "The player page reported a problem: %s" % report.get("message")
                    log.error(note)
                    self.notes.append(note)
        finally:
            self.players.discard(socket)
            self.statuses.pop(id(socket), None)
            if link is not None:
                link.note("The player page at %s was closed." % (request.remote or "an unknown address"), "player")
        return socket

    async def phrase(self, request: web.Request) -> web.Response:
        """One whole phrase from a bucket, as 16-bit stereo."""
        key = "%s/%s" % (request.match_info["genre"], request.match_info["zone"])
        try:
            # Read to one side: a part of a piece is unpacked from FLAC, which takes a moment
            # the game should not have to wait for.
            data = await asyncio.to_thread(self.buckets.by_key(key).samples, request.match_info["clip"])
        except KeyError as error:
            raise web.HTTPNotFound(text="Cannot give that phrase: %s" % error)
        # A phrase never changes once it is made, so the browser may keep it for good.
        return web.Response(body=data, content_type="application/octet-stream",
                            headers={"Cache-Control": "max-age=31536000, immutable"})

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
        # The server has no login, so a page must not be able to spend money by accident: new
        # phrases are asked for a pretend game only when the request says so outright.
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

    def _styles(self) -> dict[str, Any]:
        return {"genre": self.genre, "pieces": self.settings.pieces,
                "genres": [{"key": key, "label": recipe["label"], "about": recipe["about"]}
                           for key, recipe in composer.GENRES.items()]}

    async def style(self, request: web.Request) -> web.Response:
        """Which style is in force and which there are, and whether the written pieces are
        played; a POST changes either. The change is kept (var/settings.json) and takes effect at
        once: the new style's bucket is played as soon as it has anything in it."""
        if request.method == "POST":
            asked = await request.json()
            try:
                for name in ("genre", "pieces"):
                    if name in asked:
                        self.settings.change(name, asked[name])
            except ValueError as error:
                raise web.HTTPBadRequest(text=str(error))
            self.settings.save()
            if "genre" in asked:
                self._arrivals = []
                self.notes.append("The style is now %s." % composer.GENRES[self.genre]["label"])
            if "pieces" in asked:
                # The players are told at once what there now is to play from.
                self.notes.append("Written pieces are switched %s." % self.settings.pieces)
                if self.bucket is not None:
                    await self._broadcast(self._bucket_message())
        return web.json_response(self._styles())

    async def zones(self, request: web.Request) -> web.Response:
        """The zones the pretend game offers: every one with a profile of its own, A to Z."""
        return web.json_response(atlas.names())

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "target": self.target.as_dict() if self.target else None,
            "players": list(self.statuses.values()), "players_connected": len(self.players),
            "genre": self.genre, "forever": self._forever_status(), "notes": self.notes[-20:]})

    def _forever_status(self) -> dict[str, Any]:
        """The forever song for the control page: the bucket in play, what each pool holds, what
        is on its way, and how many phrases have been made since the server started."""
        bucket = self.bucket
        live = bucket.live() if bucket else []
        # The written piece a player is in the middle of, as that player's page last said.
        piece = next((status["piece"] for status in self.statuses.values() if status.get("piece")), None)
        found, light = self.kinds_here(self.hub.state)
        return {"bucket": bucket.key if bucket else None,
                "bpm": bucket.bpm if bucket else None, "tonic": bucket.tonic if bucket else None,
                # Loose phrases (each one instrument alone, any with any) and written pieces
                # (each kept as its parts, which are counted apart from the phrases).
                "phrases": sum(1 for clip in live if not clip.piece),
                "pieces": len(bucket.live_pieces()) if bucket else 0,
                "parts": sum(1 for clip in live if clip.piece),
                "playing_piece": piece,
                "kinds": found, "light": light, "shade": self.shade_here(self.hub.state), "setting": self.setting_here(self.hub.state),
                "kept": len(bucket.clips) if bucket else 0,
                "pools": bucket.counts() if bucket else {},
                "mix": self.mix,
                "coming": ["%s %s" % (pool[0], forever.TIER_WORDS[pool[1]]) for _, pool in self._filling.values()],
                "made": self.phrases_made,
                "turned_away": self.filler.turned_away if self.filler else 0,
                "new_phrases": self.filler is not None}


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
    if conductor._filling:
        # A phrase that is on its way has been paid for; it takes a few seconds to arrive.
        log.warning("%d phrases are on their way; waiting for them before stopping", len(conductor._filling))
        _, late = await asyncio.wait(list(conductor._filling), timeout=30.0)
        for task in late:
            log.error("a phrase was not finished in half a minute and is given up")
            task.cancel()
    if conductor._task is not None and not conductor._task.done():
        conductor._task.cancel()
        # Being cancelled is how this loop is meant to end; any other error was already reported
        # by _ended when it happened.
        with contextlib.suppress(asyncio.CancelledError):
            await conductor._task


def attach(app: web.Application, director: Director | None = None, clock=time.monotonic,
           settings: Settings | None = None, filler: forever.Filler | None = None) -> Conductor:
    """Adds the music side to a server made by server.create_app(). With a `filler`, phrases are
    bought for the bucket while the game is played; without one, what the buckets hold is played."""
    settings = settings or Settings()
    conductor = Conductor(app["hub"], director, clock, settings=settings, filler=filler)
    app["conductor"] = conductor
    if "link" in app:
        app["link"].music = conductor.heard   # so the game link can say when nothing can be heard
    app.router.add_get("/player", conductor.page)
    app.router.add_get("/player/{name}", conductor.page)
    app.router.add_get("/ws/player", conductor.player_socket)
    app.router.add_get("/phrase/{genre}/{zone}/{clip}", conductor.phrase)
    app.router.add_get("/api/music", conductor.status)
    app.router.add_get("/api/zones", conductor.zones)
    app.router.add_get("/api/style", conductor.style)
    app.router.add_post("/api/style", conductor.style)
    app.router.add_post("/api/pretend", conductor.pretend)
    # Whole tracks to listen to without the game (tools/listen.py writes them, with a page for
    # each style): http://<this machine>:8765/listen/warcraft/index.html
    listen = Path(settings.var_dir) / "listen"
    listen.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/listen", listen, show_index=True)
    app.on_startup.append(_start)

    async def _stopping(app: web.Application) -> None:
        await close_sockets(conductor.players)       # the player pages are told at once, and find the next server

    app.on_shutdown.append(_stopping)
    app.on_cleanup.append(_stop)
    return conductor
