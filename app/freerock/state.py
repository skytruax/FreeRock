"""What the game is doing, as the rest of FreeRock sees it.

beacon.py turns a picture of the strip into a Frame of raw numbers. This file turns a stream of
frames into a GameState with names put back together, notices commands and one-off moments
exactly once, and keeps the last good state when the strip cannot be read for a while (a loading
screen, a hidden interface, another window in front).

Hub is the one place inside the program where other parts listen for all of this.
"""
from __future__ import annotations

import asyncio
import dataclasses
import enum
import time
from typing import Callable

from freerock import beacon

INSTANCE_KINDS = {0: "none", 1: "party", 2: "raid", 3: "battleground", 4: "arena", 5: "scenario"}
TARGET_CLASSES = {0: "none", 1: "normal", 2: "elite", 3: "rare", 4: "rareelite", 5: "worldboss", 6: "trivial", 7: "minus"}
PVP_KINDS = {0: "unknown", 1: "sanctuary", 2: "friendly", 3: "contested", 4: "hostile", 5: "combat", 6: "arena"}
WEATHER_KINDS = {0: "clear", 1: "rain", 2: "snow", 3: "sandstorm", 4: "misc"}
COMMANDS = {1: "skip", 2: "love", 3: "ban"}
MOMENTS = {1: "level_up", 2: "boss_defeated", 3: "boss_lost", 4: "died", 5: "quest_turned_in",
           6: "achievement"}
OTHER = "other"

_TEXT_FIELDS = {
    beacon.TEXT_ZONE: "zone_name",
    beacon.TEXT_SUBZONE: "subzone_name",
    beacon.TEXT_INSTANCE: "instance_name",
    beacon.TEXT_ENCOUNTER: "encounter_name",
    beacon.TEXT_NOTE: "addon_note",
}


class Link(str, enum.Enum):
    """How well FreeRock can see the game right now."""

    NEVER = "never"   # no strip has been read since the program started
    LIVE = "live"     # the strip is being read
    STALE = "stale"   # it was being read a moment ago; the last state is being held
    LOST = "lost"     # it has not been read for a long time
    OFF = "off"       # the strip itself says FreeRock is switched off in the game


@dataclasses.dataclass(frozen=True)
class GameState:
    """Everything the strip says, in plain terms. Names are None until they have arrived whole."""

    enabled: bool = True
    map_id: int = 0                       # the game's map number for the zone; 0 when it gives none
    zone_name: str | None = None
    subzone_name: str | None = None
    has_subzone: bool = False             # the strip says there is a subzone name (it may not have arrived yet)
    position: tuple[float, float] | None = None  # across and down the zone map, 0 to 1
    speed: float | None = None            # yards a second; None: not known, or an addon that does not say
    in_instance: bool = False
    instance_kind: str = "none"
    instance_id: int = 0
    instance_name: str | None = None
    difficulty: int = 0
    indoors: bool = False
    resting: bool = False
    swimming: bool = False
    submerged: bool = False
    mounted: bool = False
    flying: bool = False
    on_taxi: bool = False
    stealthed: bool = False
    dead: bool = False
    ghost: bool = False
    in_combat: bool = False
    encounter: bool = False
    encounter_id: int = 0
    encounter_name: str | None = None
    boss_present: bool = False
    has_target: bool = False
    target_class: str = "none"
    target_hostile: bool | None = None    # the target can be fought; None: an addon that does not say
    # Enemies with a nameplate on screen, and how many of those are in a fight (14 stands for
    # "14 or more"). None: not known, or an addon that does not say.
    enemies: int | None = None
    fighting: int | None = None
    # The addon's own line about itself: its version and what its last count of nameplates came
    # across. For whoever looks after FreeRock; the music does not use it.
    addon_note: str | None = None
    in_group: bool = False
    pvp_kind: str = "unknown"
    weather: str | None = None            # None: the game does not report weather
    weather_intensity: float | None = None  # as the game gives it; its range is not documented
    daytime: bool | None = None           # None: the game does not report day or night
    game_minutes: int | None = None       # minutes since midnight, game time
    cinematic: bool = False
    loading: bool = False
    volume: int = 70

    def as_dict(self) -> dict:
        data = dataclasses.asdict(self)
        data["position"] = list(self.position) if self.position else None
        return data


# ---------------------------------------------------------------------------
# What a tracker reports
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class StateChanged:
    state: GameState
    previous: GameState | None
    changed: frozenset[str]  # names of the fields that differ


@dataclasses.dataclass(frozen=True)
class CommandReceived:
    name: str   # skip, love or ban
    count: int


@dataclasses.dataclass(frozen=True)
class MomentReceived:
    name: str   # level_up, boss_defeated, boss_lost, died, quest_turned_in, achievement
    count: int


@dataclasses.dataclass(frozen=True)
class LinkChanged:
    link: Link
    previous: Link


@dataclasses.dataclass(frozen=True)
class TestPatternSeen:
    """The addon's test pattern was read correctly (/rock test)."""


Event = StateChanged | CommandReceived | MomentReceived | LinkChanged | TestPatternSeen


class _Name:
    """One name being put together from six-byte chunks."""

    def __init__(self) -> None:
        self.revision: int | None = None
        self.length = 0
        self.chunks: dict[int, bytes] = {}
        self.text: str | None = None

    def reset(self) -> None:
        self.chunks = {}
        self.text = None

    def add(self, revision: int, length: int, chunk: int, data: bytes) -> bool:
        """Takes one chunk. Returns True when the name changed (arrived, or was dropped)."""
        had = self.text
        if revision != self.revision or length != self.length:
            self.revision, self.length = revision, length
            self.reset()
        self.chunks[chunk] = data
        if self.text is None:
            needed = -(-length // beacon.TEXT_CHUNK_BYTES)
            if all(index in self.chunks for index in range(needed)):
                raw = b"".join(self.chunks[index] for index in range(needed))[:length]
                self.text = raw.decode("utf-8")  # the caller deals with a name that is not text
        return self.text != had


def _state_from(frame: beacon.Frame, names: dict[str, str | None]) -> GameState:
    flags = frame.flags

    def has(bit: int) -> bool:
        return bool(flags & bit)

    weather_known = has(beacon.FLAG_WEATHER_KNOWN) and frame.weather_kind != beacon.UNKNOWN_KIND
    says_more = frame.version >= 2      # speed and whether the target can be fought
    return GameState(
        enabled=has(beacon.FLAG_ENABLED),
        map_id=frame.map_id,
        zone_name=names["zone_name"],
        subzone_name=names["subzone_name"] if frame.subzone_hash else None,
        has_subzone=frame.subzone_hash != 0,
        position=(frame.x / 65534.0, frame.y / 65534.0)
        if has(beacon.FLAG_POSITION_KNOWN) and frame.x != beacon.UNKNOWN_16 and frame.y != beacon.UNKNOWN_16 else None,
        speed=frame.speed / 2.0 if says_more and frame.speed != beacon.UNKNOWN_SPEED else None,
        in_instance=has(beacon.FLAG_IN_INSTANCE),
        instance_kind=INSTANCE_KINDS.get(frame.instance_kind, OTHER),
        instance_id=frame.instance_id,
        instance_name=names["instance_name"] if has(beacon.FLAG_IN_INSTANCE) else None,
        difficulty=frame.difficulty,
        indoors=has(beacon.FLAG_INDOORS),
        resting=has(beacon.FLAG_RESTING),
        swimming=has(beacon.FLAG_SWIMMING),
        submerged=has(beacon.FLAG_SUBMERGED),
        mounted=has(beacon.FLAG_MOUNTED),
        flying=has(beacon.FLAG_FLYING),
        on_taxi=has(beacon.FLAG_TAXI),
        stealthed=has(beacon.FLAG_STEALTH),
        dead=has(beacon.FLAG_DEAD),
        ghost=has(beacon.FLAG_GHOST),
        in_combat=has(beacon.FLAG_COMBAT),
        encounter=has(beacon.FLAG_ENCOUNTER),
        encounter_id=frame.encounter_id,
        encounter_name=names["encounter_name"] if has(beacon.FLAG_ENCOUNTER) else None,
        boss_present=has(beacon.FLAG_BOSS_PRESENT),
        has_target=has(beacon.FLAG_HAS_TARGET),
        target_class=TARGET_CLASSES.get(frame.target_class, OTHER),
        target_hostile=has(beacon.FLAG_TARGET_HOSTILE) if says_more else None,
        enemies=frame.enemies if frame.version >= 3 and frame.enemies != beacon.UNKNOWN_COUNT else None,
        fighting=frame.fighting if frame.version >= 3 and frame.fighting != beacon.UNKNOWN_COUNT else None,
        addon_note=names["addon_note"],
        in_group=has(beacon.FLAG_IN_GROUP),
        pvp_kind=PVP_KINDS.get(frame.pvp_kind, OTHER),
        weather=WEATHER_KINDS.get(frame.weather_kind, OTHER) if weather_known else None,
        weather_intensity=frame.weather_intensity / 1000.0
        if weather_known and frame.weather_intensity != beacon.UNKNOWN_16 else None,
        daytime=has(beacon.FLAG_DAYTIME) if has(beacon.FLAG_DAYTIME_KNOWN) else None,
        game_minutes=frame.game_minutes if frame.game_minutes != beacon.UNKNOWN_16 else None,
        cinematic=has(beacon.FLAG_CINEMATIC),
        loading=has(beacon.FLAG_LOADING),
        volume=min(frame.volume, 100),
    )


class StateTracker:
    """Turns frames, and the lack of them, into a GameState and a list of things that happened.

    feed() takes a frame that was read. tick() is called regularly so that time passing without a
    frame is noticed. Both return the events that follow, in order. The last good state is kept
    (hold-last-good) for as long as the strip is unreadable; only the link status says how fresh
    it is.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        stale_after: float = 1.5,
        lost_after: float = 120.0,
    ) -> None:
        self._clock = clock
        self.stale_after = stale_after
        self.lost_after = lost_after
        self.state: GameState | None = None
        self.link = Link.NEVER
        self.last_frame: beacon.Frame | None = None
        self.last_good_at: float | None = None
        self.last_test_at: float | None = None
        self.frames = 0          # good frames read
        self.name_rejects = 0    # names thrown away because their bytes did not make sense
        self._names = {field: _Name() for field in _TEXT_FIELDS}
        self._command_count: int | None = None
        self._moment_count: int | None = None

    # -- names ---------------------------------------------------------------
    def _take_text(self, frame: beacon.Frame) -> None:
        name = self._names.get(frame.text_field)
        if name is None:
            return  # no text in this frame, or a field a later version added
        if frame.text_length > beacon.TEXT_MAX_BYTES or frame.text_chunk * beacon.TEXT_CHUNK_BYTES >= max(frame.text_length, 1):
            self.name_rejects += 1
            name.reset()
            return
        try:
            name.add(frame.text_revision, frame.text_length, frame.text_chunk, frame.text_bytes)
        except UnicodeDecodeError:
            # Chunks of two different names were put together (the revision is only two bits).
            # Drop them; the name comes round again within a second.
            self.name_rejects += 1
            name.reset()
            return
        if frame.text_field == beacon.TEXT_SUBZONE and name.text is not None:
            if beacon.text_hash(name.text.encode("utf-8")) != frame.subzone_hash:
                self.name_rejects += 1
                name.reset()

    def _current_names(self, frame: beacon.Frame) -> dict[str, str | None]:
        names = {key: self._names[field].text for field, key in _TEXT_FIELDS.items()}
        subzone = names["subzone_name"]
        # A subzone name that no longer matches the mark in this frame is the previous subzone's.
        if subzone is not None and beacon.text_hash(subzone.encode("utf-8")) != frame.subzone_hash:
            names["subzone_name"] = None
        return names

    # -- frames ----------------------------------------------------------------
    def feed(self, frame: beacon.Frame) -> list[Event]:
        """A frame was read off the strip."""
        events: list[Event] = []
        now = self._clock()
        self.frames += 1
        self.last_good_at = now
        if frame.kind == beacon.KIND_TEST:
            # Test frames come twenty a second for ten seconds; one event per burst is enough.
            if self.last_test_at is None or now - self.last_test_at > 2.0:
                events.append(TestPatternSeen())
            self.last_test_at = now
            events.extend(self._set_link(Link.LIVE))
            return events
        # A name belongs to the place it was sent for. When the place changes, the old name is
        # dropped at once rather than shown beside the new place until the new name arrives.
        before = self.last_frame
        if before is not None:
            if frame.map_id != before.map_id:
                self._names[beacon.TEXT_ZONE].reset()
            if frame.instance_id != before.instance_id:
                self._names[beacon.TEXT_INSTANCE].reset()
            if frame.encounter_id != before.encounter_id:
                self._names[beacon.TEXT_ENCOUNTER].reset()
        self.last_frame = frame
        self._take_text(frame)
        state = _state_from(frame, self._current_names(frame))
        events.extend(self._set_link(Link.LIVE if state.enabled else Link.OFF))

        previous = self.state
        if state != previous:
            if previous is None:
                changed = frozenset(field.name for field in dataclasses.fields(GameState))
            else:
                changed = frozenset(
                    field.name for field in dataclasses.fields(GameState)
                    if getattr(state, field.name) != getattr(previous, field.name)
                )
            self.state = state
            events.append(StateChanged(state=state, previous=previous, changed=changed))

        # A command or moment is acted on when its count changes. The first frame after starting
        # only sets the baseline: whatever is in the strip then happened before we were watching.
        if self._command_count is None:
            self._command_count = frame.command_count
        elif frame.command_count != self._command_count:
            self._command_count = frame.command_count
            if frame.command in COMMANDS:
                events.append(CommandReceived(COMMANDS[frame.command], frame.command_count))
        if self._moment_count is None:
            self._moment_count = frame.moment_count
        elif frame.moment_count != self._moment_count:
            self._moment_count = frame.moment_count
            if frame.moment in MOMENTS:
                events.append(MomentReceived(MOMENTS[frame.moment], frame.moment_count))
        return events

    def tick(self) -> list[Event]:
        """Time has passed. Says so when the strip has not been read for a while."""
        if self.last_good_at is None or self.link in (Link.NEVER, Link.OFF):
            return []
        quiet = self._clock() - self.last_good_at
        if quiet >= self.lost_after:
            return self._set_link(Link.LOST)
        if quiet >= self.stale_after:
            return self._set_link(Link.STALE) if self.link == Link.LIVE else []
        return []

    def gone(self) -> list[Event]:
        """The game itself has gone (its window is closed), which is not the same as the strip
        being out of sight for a moment: there is nothing left to hold the last state for."""
        if self.link in (Link.LIVE, Link.STALE):
            return self._set_link(Link.LOST)
        return []

    def _set_link(self, link: Link) -> list[Event]:
        if link == self.link:
            return []
        previous, self.link = self.link, link
        return [LinkChanged(link=link, previous=previous)]

    def seconds_since_good(self) -> float | None:
        return None if self.last_good_at is None else self._clock() - self.last_good_at


# ---------------------------------------------------------------------------
# Listening
# ---------------------------------------------------------------------------
class Overrun(RuntimeError):
    """A listener fell so far behind that events had to be dropped. It is told so, loudly."""


class Subscription:
    """One listener's queue of events. Use it as `async for event in subscription:`."""

    def __init__(self, hub: "Hub", size: int) -> None:
        self._hub = hub
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=size)
        self._overrun = False
        self.closed = False

    def _put(self, event: object) -> None:
        if self._overrun:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self._overrun = True

    async def get(self) -> object:
        if self._overrun and self._queue.empty():
            self._overrun = False
            raise Overrun("this listener fell behind and missed events; read hub.state to catch up")
        return await self._queue.get()

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> object:
        if self.closed:
            raise StopAsyncIteration
        return await self.get()

    def close(self) -> None:
        self.closed = True
        self._hub._subscriptions.discard(self)

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class Hub:
    """The one place inside the program where the game's state is published.

    The server feeds it; anything else (the director, the music's status) reads `hub.state` and
    `hub.link` for where things stand and calls `hub.subscribe()` for what happens next.
    """

    def __init__(self) -> None:
        self.state: GameState | None = None
        self.link = Link.NEVER
        self._subscriptions: set[Subscription] = set()

    def subscribe(self, size: int = 512) -> Subscription:
        subscription = Subscription(self, size)
        self._subscriptions.add(subscription)
        return subscription

    def publish(self, event: object) -> None:
        if isinstance(event, StateChanged):
            self.state = event.state
        elif isinstance(event, LinkChanged):
            self.link = event.link
        for subscription in list(self._subscriptions):
            subscription._put(event)
