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
import datetime
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
from .ingest import Ingest, TrackFailedChecks
from .library import Asset, Library, merged
from .playtime import Playtime
from .server import close_sockets
from .settings import Settings

log = logging.getLogger("freerock.conductor")

PLAYER_DIR = Path(__file__).resolve().parent / "web" / "player"
PLAYER_FILES = {"player.html": "text/html", "player.js": "application/javascript",
                "engine.js": "application/javascript", "forever.js": "application/javascript",
                "player.css": "text/css"}
STEP_S = 0.25          # how often the director is asked again while nothing changes
TICK_S = 1.0           # how often the players are nudged, so their queue never depends on a timer
DWELL_S = 4.0          # how long the player has been in a zone before music is made for it
TRIES = 3              # how many times music is asked for when a track fails its checks
PAUSE_S = 600.0        # no new music for this long after ElevenLabs reports a problem
AHEAD = 1                # songs a place keeps ready that have not been heard yet: when the last
                         # unheard one starts playing, the next is begun, so every song is a new one
BETWEEN_S = 45.0         # at least this long between two sets for one place, whatever the count says
FRESH_EVERY_S = 480.0    # and a new song is begun this often in any case, wherever the player is
RETRY_AFTER_S = 1800.0   # after TRIES failures in a row for one thing, it is left alone this long
MAX_FRESH = 12           # fresh sets a place keeps in rotation; an older one is retired for a newer
GROWTH_SHARE = 0.6       # the part of the monthly allowance that goes on growing places' music
GROWTH_FLOAT = 6.0       # minutes of growth allowed before any hours have been played
MIN_PLAY_S = 150.0       # however little music a place has, at least this much between rests
PLACE_DWELL_S = 2.0      # how long in a named place inside a zone before it gets a piece of its own
STOP_WAIT_S = 180.0      # how long a stopping server waits for music that is being made
# The forever song (settings.mode "forever"): phrases for the bucket of the place the player is in.
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
    """A zone name as the library files it: "Elwynn Forest" -> "elwynn-forest". None if there is
    no name to go on."""
    return (atlas.slug(name) or None) if name else None


class Conductor:
    def __init__(self, hub: game.Hub, library: Library, director: Director | None = None,
                 clock=time.monotonic, ingest: Ingest | None = None,
                 settings: Settings | None = None, playtime: Playtime | None = None,
                 filler: forever.Filler | None = None):
        self.hub = hub
        self.library = library
        self.director = director or Director()
        self._rest_every_s = self.director.rules.rest_every_s   # the longest the music goes without a rest
        self.clock = clock
        self.ingest = ingest             # None: play what the library has, make nothing new
        self.settings = settings or Settings()
        self.playtime = playtime or Playtime(self.settings.var_dir / "playtime.json")
        self._last_step: float | None = None
        self._began = clock()
        self.making: str | None = None   # the zone music is being made for right now
        self._making_task: asyncio.Task | None = None
        self._seen_in: tuple[str, float] | None = None   # (zone, when the player was first seen there)
        self._seen_at: tuple[str, float] | None = None   # (named place inside the zone, since when)
        self._zone_of_map: dict[int, str] = {}           # the zone each of the game's maps belongs to
        # How many times each piece of music has been asked for today. Kept in a file, so that a
        # restart does not ask again for music that has just been turned away twice.
        self._tries_file = self.settings.var_dir / "tries.json"
        self._tries: dict[str, int] = self._load_tries()
        self._paused_until = 0.0
        self._last_made = clock()        # when new music last arrived, for any place
        self._asked_at: dict[str, float] = {}   # when a set was last asked for, by place
        self._song_heard: str | None = None     # the music whose song a player was last heard playing
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
        # The forever song.
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
        # one lasts, and the director's own rests, which cut in wherever they fall, are off.
        self._silences = {"every_s": self.director.rules.rest_every_s, "for_s": self.director.rules.rest_for_s}
        if self.forever:
            self.director.rules.rest_every_s = 0.0

    # --- choosing the music ----------------------------------------------------------------------

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

    def place_key(self, state: game.GameState) -> str | None:
        return slug(self.place_name(state))

    def kinds_here(self, state: game.GameState | None) -> tuple[list[str], bool]:
        """The kinds of place the player is in (haunted woods, farmland, a desert: kinds.KINDS)
        and whether it is a light one. Nothing while the game has not said where the player is."""
        if state is None:
            return [], False
        return atlas.kinds_for(self.place_name(state), self.spot_name(state))

    def shade_here(self, state: game.GameState | None) -> float:
        """How dark or bright it is where the player is (-3 grim to 3 radiant), to the half
        step: the place itself, darker by night, in the rain and under a roof of rock."""
        if state is None:
            return 0.0
        shade = atlas.shade_for(self.place_name(state), self.spot_name(state))
        if state.daytime is False:
            shade -= 1.0
        if state.weather == "rain" and (state.weather_intensity or 0.0) > 0.0 and not state.indoors:
            shade -= 0.5 if (state.weather_intensity or 0.0) < 0.6 else 1.0
        if state.indoors and not state.resting and not state.in_instance:
            shade -= 1.0                                  # a cave, a mine, a crypt: not an inn
        return round(min(max(shade, -3.0), 3.0) * 2.0) / 2.0

    @property
    def asset(self) -> Asset | None:
        """The first piece of the music that is playing (a place's core suite, as a rule)."""
        return self.assets[0] if self.assets else None

    @property
    def view_id(self) -> str | None:
        """Names exactly the music that is playing, sets and all; it changes when a set is added."""
        return "+".join(asset.id for asset in self.assets) if self.assets else None

    @property
    def genre(self) -> str:
        """The style in force: what is played, and what new music is made in."""
        return self.settings.genre

    @property
    def forever(self) -> bool:
        """Whether the music is one song that never ends, built from a bucket of phrases."""
        return self.settings.mode == "forever"

    def _in_style(self, zone: str | None = None, usable_only: bool = True) -> list[Asset]:
        """The library's music in the style in force, for one zone or for all."""
        found = self.library.usable(zone) if usable_only else self.library.assets(zone)
        return [asset for asset in found if asset.genre == self.genre]

    def choose(self, state: game.GameState) -> tuple[list[Asset], bool]:
        """The music for where the player is, in the style in force: everything the place has of
        its own, otherwise the music that was already playing, otherwise the newest place's. If
        there is nothing at all in that style yet, the place's music in another style, so that
        there is sound while the first of the new style is made. Returns (music, borrowed)."""
        usable = self._in_style()
        wanted = self.place_key(state)
        if not usable:
            others = self.library.usable()
            if not others:
                return [], False
            here = [asset for asset in others if asset.zone == wanted] or \
                [asset for asset in others if asset.zone == max(others, key=lambda a: a.created).zone]
            style = here[0].genre
            return [asset for asset in here if asset.genre == style], True
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

    def scene_tag(self, state: game.GameState | None) -> str | None:
        """The named place inside the zone the player is in, as its music is filed: the pieces
        made for that place are played there and nowhere else."""
        return slug(self.spot_name(state)) if state is not None else None

    def _target_message(self) -> dict[str, Any]:
        state = self.hub.state
        target = self.target.as_dict()
        target["scene_tag"] = self.scene_tag(state)
        if self.forever:
            # The mixing desk for the five decks: which channels are up, and how hard each plays.
            target["channels"] = self.mix or forever.mix(self.target)
            # The kind of place the player is in, and whether it is a light one: what written
            # pieces are chosen by.
            target["kinds"], target["light"] = self.kinds_here(state) if state is not None else ([], False)
            # ...and how dark or bright it is there: among pieces for the same kind of place, the nearest in shade.
            target["shade"] = self.shade_here(state)
            zone = self.bucket.zone if self.bucket else None
        else:
            zone = self.asset.zone if self.asset else None
        return {"type": "target", "target": target, "link": self.hub.link.value,
                # The volume set in the game with /rock volume, 0 to 100; the page's own volume
                # control follows it whenever it changes.
                "game_volume": state.volume if state else None,
                "music": {"zone": zone, "borrowed": self.borrowed},
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
        if self.forever:
            await self._forever_step(state, target, now)
            return
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
            self._pace_the_rests()
            await self._broadcast(self._asset_message())
        told = (target, state.volume, self.view_id, self.borrowed, self.scene_tag(state))
        if told != self._told:
            self.target, self._volume, self._told = target, state.volume, told
            await self._broadcast(self._target_message())
        self._consider_making(state)

    def _pace_the_rests(self) -> None:
        """Where a place has little music, hearing it a third and fourth time is worse than a
        pause. The music rests after about twice round what the place has for exploring, and
        never later than the setting says."""
        if self._rest_every_s <= 0:
            return
        # Music made as songs brings its own silences: each song is played to its end and
        # followed by one. Cutting across a song on a timer as well would spoil it.
        if any(section.song for asset in self.assets for section in asset.sections if not asset.subzone):
            self.director.rules.rest_every_s = 0.0
            return
        exploring = sum((section.end - section.start) / asset.rate for asset in self.assets
                        for section in asset.sections if section.role in ("wander", "ember"))
        self.director.rules.rest_every_s = min(self._rest_every_s, max(MIN_PLAY_S, 2.0 * exploring))

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
        told = (target, state.volume, self._sent_bucket, json.dumps(mixed, sort_keys=True), tuple(found), light, self.shade_here(state))
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

    # --- making new music --------------------------------------------------------------------

    @staticmethod
    def _today() -> str:
        return datetime.date.today().isoformat()

    def _load_tries(self) -> dict[str, int]:
        """How many times in a row each piece of music has been asked for without success, and
        when it was last asked for. Kept in a file, so that a restart does not ask again at once
        for music that has just been turned away three times."""
        self._tried_at: dict[str, float] = {}
        if not self._tries_file.exists():
            return {}
        kept = json.loads(self._tries_file.read_text(encoding="utf-8"))
        self._tried_at = {key: float(when) for key, when in kept.get("at", {}).items()}
        return dict(kept.get("tries", {}))

    def _save_tries(self) -> None:
        self._tries_file.parent.mkdir(parents=True, exist_ok=True)
        self._tries_file.write_text(json.dumps({"tries": self._tries, "at": self._tried_at}, indent=1) + "\n",
                                    encoding="utf-8")

    def _may_try(self, tried: str) -> bool:
        """Whether a piece of music may be asked for now. Three failures in a row and it is
        left alone for half an hour; then it may be tried again. It is never given up for good:
        a place is not left without new music for a day because its checks failed."""
        if self._tries.get(tried, 0) < TRIES:
            return True
        if time.time() - self._tried_at.get(tried, 0.0) >= RETRY_AFTER_S:
            self._tries[tried] = 0
            return True
        return False

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
        # and with the game out of sight or no player page open there is nobody to make music for.
        if (self.hub.link is not game.Link.LIVE or not state.enabled or state.on_taxi
                or state.loading or state.cinematic or not self.players):
            self._seen_in = (key, now)
            return
        if now - self._seen_in[1] < DWELL_S or now < self._paused_until:
            return
        name = self.place_name(state)
        spot = None
        if not self._in_style(key, usable_only=False):
            kind = "core"                # the place has no music in this style (banned music is not remade)
        else:
            # A named place inside the zone that has no piece of its own comes first: it is
            # where the player is standing, and its piece is short and quick to make.
            spot = self._place_due(state, key, now)
            kind = "place" if spot else self._growth_due(name, key)
            if kind is None:
                return
        tried = self.genre + ":" + key + ("/" + slug(spot) if spot else "") + ":" + kind
        if not self._may_try(tried):
            if kind != "second":
                return
            # A second set that keeps failing does not hold up the songs that would follow it.
            kind = "fresh"
            tried = self.genre + ":" + key + ":" + kind
            if not self._may_try(tried):
                return
        self.making = key
        self._tries[tried] = self._tries.get(tried, 0) + 1
        self._tried_at[tried] = time.time()
        self._save_tries()
        again = self._tries[tried] > 1
        self._asked_at[key] = now
        moment = self.moment_words(state)
        if kind == "core":
            self.notes.append("Making music for %s (%s)." % (name, composer.GENRES[self.genre]["label"]))
            job = self.ingest.core_suite(name, reroll=again, context=moment)
        elif kind == "place":
            self.notes.append("Making a piece for %s." % spot)
            core = next(asset for asset in self._in_style(key) if asset.set == "core")
            job = self.ingest.place_piece(core, name, spot, reroll=again)
            name = spot
        else:
            self.notes.append("Writing a new song for %s%s." % (name, ": " + "; ".join(moment) if moment else ""))
            core = next(asset for asset in self._in_style(key) if asset.set == "core")
            job = self.ingest.later_set(core, name, kind, reroll=again, context=moment)
        self._making_task = asyncio.create_task(job, name="freerock-making-" + tried)
        self._making_task.add_done_callback(lambda task: self._made(name, key, kind, task, tried))

    def moment_words(self, state: game.GameState) -> list[str]:
        """What is true in the game as a song is about to be written, in words for the request:
        the hour, the weather, how much fighting and riding there has been. A song is written
        for the moment it is asked for in, which is one more thing that keeps two songs apart."""
        words = []
        if state.daytime is False:
            words.append("a song for the night: cooler, with more space in it")
        strength = state.weather_intensity or 0.0
        if state.weather == "rain" and strength >= 0.3:
            words.append("rain on the road: a driving wet-weather song")
        elif state.weather == "snow" and strength >= 0.3:
            words.append("falling snow: hushed verses and a warm chorus")
        elif state.weather == "sandstorm" and strength >= 0.3:
            words.append("a dry wind blowing: a gritty, swaying song")
        if self.director.heat >= 0.6:
            words.append("after a run of fights: restless and hard-driving")
        elif state.resting:
            words.append("in town and at ease: an easy-going song")
        elif state.mounted:
            words.append("a riding song with a galloping feel in the verses")
        return words

    def _count_play(self, report: dict[str, Any]) -> None:
        """Notes that a player has started a song, once for each start. A song that a fight cut
        into and that then went on is still the same start."""
        asset_id = report.get("asset_id")
        if not report.get("song") or not asset_id or asset_id == self._song_heard:
            return
        self._song_heard = asset_id
        try:
            self.library.played(asset_id)
        except KeyError:
            # The page is still playing music the library no longer has. Nothing to count.
            log.warning("a player is playing %s, which is not in the library", asset_id)

    def _place_due(self, state: game.GameState, key: str, now: float) -> str | None:
        """The named place inside the zone the player is in, if it should get a piece of its own
        now: it has a name of its own, the player has been in it a moment, nothing has been made
        for it before, and the zone has a core suite for the piece to belong to."""
        spot = self.spot_name(state)
        tag = slug(spot)
        if not tag or tag == key:
            self._seen_at = None
            return None
        if self._seen_at is None or self._seen_at[0] != tag:
            self._seen_at = (tag, now)
        if now - self._seen_at[1] < PLACE_DWELL_S:
            return None
        if any(asset.subzone == tag for asset in self._in_style(key, usable_only=False)):
            return None
        if not any(asset.set == "core" for asset in self._in_style(key)):
            return None
        return spot

    def _growth_due(self, name: str | None, key: str) -> str | None:
        """Whether the place the player is in has earned more music, and which kind: a second set
        once some time has been spent there, a fresh set every couple of hours after that. None
        if it has not, or if the month's growth has run ahead of the hours played."""
        own = self._in_style(key)
        if not any(asset.set == "core" for asset in own):
            return None                  # its core suite was banned; nothing to grow from
        # A place keeps one song ready that nobody has heard. The moment that song starts
        # playing, the next is begun, so that the music is a run of new songs and not a round of
        # the same ones. And in any case a new one is begun every eight minutes, wherever the
        # player is and whether or not they have changed zone.
        now = self.clock()
        if now - self._asked_at.get(key, -1e9) < BETWEEN_S:
            return None
        unheard = [asset for asset in own if asset.has_song and not asset.subzone and asset.plays == 0]
        overdue = (self.playtime.since_set(key) >= FRESH_EVERY_S or now - self._last_made >= FRESH_EVERY_S)
        if len(unheard) >= AHEAD and not overdue:
            return None
        kind = "fresh" if any(asset.set == "second" for asset in self._in_style(key, usable_only=False)) else "second"
        profile = atlas.profile_for(name)
        maker = composer.second_set if kind == "second" else composer.fresh_set
        bars = atlas.part_bars(composer.for_genre(profile, self.genre).bpm)
        minutes = maker(profile, part_bars=bars, genre=self.genre).minutes
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
        fresh = [asset for asset in self._in_style(key) if asset.set == "fresh"]
        spare = [asset for asset in fresh if not asset.loved]
        while len(fresh) > MAX_FRESH and spare:
            oldest = spare.pop(0)
            self.library.mark(oldest.id, retired=True)
            fresh.remove(oldest)
            self.notes.append("Set aside an older set (%s) to make room for the new one." % oldest.id)

    def _made(self, name: str, key: str, kind: str, task: asyncio.Task, tried: str | None = None) -> None:
        self.making = None
        tried = tried or key + ":" + kind
        if task.cancelled():
            return
        error = task.exception()
        if error is None:
            made = task.result()
            if kind != "place":
                self._last_made = self.clock()
            if kind in ("second", "fresh"):
                self.playtime.set_made(key, made.asset.minutes)
                self._retire_old_sets(key)
            self._tries[tried] = 0           # it worked: the count of failures in a row starts again
            self._save_tries()
            what = {"core": "New music", "place": "A piece of its own"}.get(kind, "More music (a %s set)" % kind)
            self.notes.append("%s for %s is ready (first audio after %.1f s, all of it after %.1f s, "
                              "layers split in %.0f s)." % (
                                  what, name, made.first_audio_s or 0.0, made.total_s or 0.0, made.split_s))
        elif isinstance(error, TrackFailedChecks):
            again = self._tries.get(tried, 0) < TRIES
            self.notes.append("%s %s" % (error, "Trying once more." if again
                                         else "Leaving it for half an hour before trying again."))
        elif isinstance(error, AllowanceExceeded):
            self._tries[tried] -= 1      # nothing was asked for, so it does not count as a try
            self._save_tries()
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
            elif event.name in ("love", "ban") and self.forever:
                # In the forever song, love and ban are about the phrases playing at this moment.
                # Loved ones are never set aside as worn; banned ones are not played again, and
                # the decks playing them move on.
                # A piece of written music is loved or banned whole, every part of it.
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
            elif event.name in ("love", "ban") and self.assets:
                # Love and ban are about what is playing at this moment: the set the section came
                # from, not the whole of a place's music.
                which = self.playing_asset_id()
                self.library.mark(which, loved=True if event.name == "love" else None,
                                  banned=True if event.name == "ban" else None)
                self.notes.append("%s marked as %s." % (which, "loved" if event.name == "love" else "banned"))
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
            if self.forever:
                if self.bucket is not None:
                    await self._send(socket, self._bucket_message())
            elif self.assets:
                await self._send(socket, self._asset_message())
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    continue
                report = json.loads(message.data)
                if report.get("type") == "status":
                    self.statuses[id(socket)] = report
                    if report.get("forever"):
                        self._count_phrases(report)
                    else:
                        self._count_play(report)
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

    def _styles(self) -> dict[str, Any]:
        have = {}
        for asset in self.library.usable():
            have.setdefault(asset.genre, set()).add(asset.zone)
        return {"genre": self.genre, "pieces": self.settings.pieces,
                "genres": [{"key": key, "label": recipe["label"], "about": recipe["about"],
                            "places": len(have.get(key, ()))} for key, recipe in composer.GENRES.items()]}

    async def style(self, request: web.Request) -> web.Response:
        """Which style is in force and which there are; a POST changes it. The change is kept
        (var/settings.json) and takes effect at once: what the library has in the new style is
        played, and the place the player is in gets music in it if it has none."""
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
                self._seen_in = self._seen_at = None      # the wait before making music starts again
                self._arrivals = []
                self.notes.append("The style is now %s." % composer.GENRES[self.genre]["label"])
            if "pieces" in asked:
                # The players are told at once what there now is to play from.
                self.notes.append("Written pieces are switched %s." % self.settings.pieces)
                if self.bucket is not None:
                    await self._broadcast(self._bucket_message())
        return web.json_response(self._styles())

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
            "making": self.making, "genre": self.genre, "mode": self.settings.mode,
            "forever": self._forever_status() if self.forever else None, "notes": self.notes[-20:]})

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
                "kinds": found, "light": light, "shade": self.shade_here(self.hub.state),
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
    conductor.playtime.save()
    if conductor._filling:
        # A phrase that is on its way has been paid for; it takes a few seconds to arrive.
        log.warning("%d phrases are on their way; waiting for them before stopping", len(conductor._filling))
        _, late = await asyncio.wait(list(conductor._filling), timeout=30.0)
        for task in late:
            log.error("a phrase was not finished in half a minute and is given up")
            task.cancel()
    if conductor._making_task is not None and not conductor._making_task.done():
        # Music that is being made has been paid for by the time the request is out. Stopping
        # in the middle would throw it away, so the server waits for it to be finished and stored.
        log.warning("music is being made for %s; waiting for it before stopping", conductor.making)
        try:
            await asyncio.wait_for(asyncio.shield(conductor._making_task), timeout=STOP_WAIT_S)
        except asyncio.TimeoutError:
            log.error("the music for %s was not finished in %.0f s and is given up", conductor.making, STOP_WAIT_S)
            conductor._making_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await conductor._making_task
        except Exception as error:   # what went wrong with the track itself was reported when it happened
            log.warning("the music being made ended with %r", error)
    if conductor._task is not None and not conductor._task.done():
        conductor._task.cancel()
        # Being cancelled is how this loop is meant to end; any other error was already reported
        # by _ended when it happened.
        with contextlib.suppress(asyncio.CancelledError):
            await conductor._task


def attach(app: web.Application, library: Library | None = None,
           director: Director | None = None, clock=time.monotonic,
           ingest: Ingest | None = None, settings: Settings | None = None,
           playtime: Playtime | None = None, filler: forever.Filler | None = None) -> Conductor:
    """Adds the music side to a server made by server.create_app(). With an `ingest`, music is
    made for zones that have none and grown where time is spent; without one, only what is in the
    library is played."""
    settings = settings or Settings()
    conductor = Conductor(app["hub"], library or Library(settings.library_dir), director, clock, ingest,
                          settings=settings, playtime=playtime, filler=filler)
    app["conductor"] = conductor
    if "link" in app:
        app["link"].music = conductor.heard   # so the game link can say when nothing can be heard
    app.router.add_get("/player", conductor.page)
    app.router.add_get("/player/{name}", conductor.page)
    app.router.add_get("/ws/player", conductor.player_socket)
    app.router.add_get("/audio/{asset}/{layer}", conductor.audio)
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
