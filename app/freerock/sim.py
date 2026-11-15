"""A pretend game, so the whole link runs without World of Warcraft.

A scenario is a scripted session: where the player is, and what happens when. The pretend game
draws the strip for it the way the addon does, on a pretend screen, and FreeRock's real sensor
loop (web/sensor.py) copies that screen and sends it to the real server over a real connection.
Only two things are pretend: the game, and the screen copy.

    freerock sim elwynn-walk            (the server must be running: freerock serve)

Scenario files live in app/freerock/scenarios. Each is JSON:

    "screen": [width, height]      the pretend game window, in pixels
    "cell", "edge", "inset"        how the strip is drawn (square size, top or bottom, [x, y])
    "start": {...}                 the game at time 0 (see SimGame for the names)
    "steps": [{"at": seconds, "say": "...", "set": {...}, "walk": {"x":, "y":, "seconds":},
               "command": "skip|love|ban", "moment": "level_up|...", "test": seconds,
               "hidden": true|false, "in_front": true|false, "strip": {"cell":, "edge":, "inset":}}]

The frames here are built by Python that follows protocol/beacon.md; the addon's own Lua is
checked against the same protocol by the tests, not by this file.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import time

import numpy as np

from freerock import beacon, state
from freerock.web import sensor

SCENARIOS = pathlib.Path(__file__).resolve().parent / "scenarios"

_INSTANCE_NUMBERS = {name: number for number, name in state.INSTANCE_KINDS.items()}
_TARGET_NUMBERS = {name: number for number, name in state.TARGET_CLASSES.items()}
_PVP_NUMBERS = {name: number for number, name in state.PVP_KINDS.items()}
_WEATHER_NUMBERS = {name: number for number, name in state.WEATHER_KINDS.items()}
_COMMAND_NUMBERS = {name: number for number, name in state.COMMANDS.items()}
_MOMENT_NUMBERS = {name: number for number, name in state.MOMENTS.items()}


@dataclasses.dataclass
class SimGame:
    """What the pretend game would tell the addon."""

    enabled: bool = True
    zone: str = "Elwynn Forest"
    subzone: str = "Goldshire"
    map_id: int = 1429
    x: float | None = 0.42
    y: float | None = 0.65
    in_instance: bool = False
    instance_kind: str = "none"
    instance_id: int = 0
    instance_name: str = ""
    difficulty: int = 0
    indoors: bool = False
    resting: bool = False
    swimming: bool = False
    submerged: bool = False
    mounted: bool = False
    flying: bool = False
    taxi: bool = False
    stealth: bool = False
    dead: bool = False
    ghost: bool = False
    combat: bool = False
    encounter: bool = False
    encounter_id: int = 0
    encounter_name: str = ""
    boss: bool = False
    group: bool = False
    target: str | None = None        # None, or normal / elite / rare / rareelite / worldboss / trivial / minus
    pvp: str = "friendly"
    weather: str | None = "clear"    # None: the game does not report weather
    weather_intensity: float | None = 0.0
    day: bool | None = True          # None: the game does not report day or night
    clock: str | None = "14:35"      # game time, "HH:MM"; it does not run by itself in a scenario
    cinematic: bool = False
    loading: bool = False
    volume: int = 70

    def change(self, values: dict) -> None:
        for name, value in values.items():
            if name not in self.__dataclass_fields__:
                raise ValueError(f"a scenario sets {name!r}, which the pretend game does not have")
            setattr(self, name, value)


class SimAddon:
    """Builds the frames the addon would: the beat, the names taking turns, the counts."""

    def __init__(self, game: SimGame) -> None:
        self.game = game
        self.beat = 0
        self.command = self.command_count = self.moment = self.moment_count = 0
        self.test_until: float | None = None
        self.now = 0.0
        self._beat_time = self._text_time = 0.0
        self._texts = {field: {"text": "", "bytes": b"", "revision": 0} for field in (1, 2, 3, 4)}
        self._turn = [0, 0]  # which name, which chunk

    def _names(self) -> dict[int, str]:
        game = self.game
        return {1: game.zone, 2: game.subzone, 3: game.instance_name if game.in_instance else "",
                4: game.encounter_name if game.encounter else ""}

    def _next_text(self) -> None:
        field, chunk = self._turn
        if field and (chunk + 1) * beacon.TEXT_CHUNK_BYTES < len(self._texts[field]["bytes"]):
            self._turn = [field, chunk + 1]
            return
        self._turn = [0, 0]
        for step in range(1, 5):
            candidate = (field + step - 1) % 4 + 1
            if self._texts[candidate]["bytes"]:
                self._turn = [candidate, 0]
                return

    def _sync_texts(self) -> None:
        for field, text in self._names().items():
            entry = self._texts[field]
            if entry["text"] != text:
                entry["text"], entry["bytes"] = text, beacon.truncate_utf8(text)
                entry["revision"] = (entry["revision"] + 1) % 4
                if entry["bytes"]:
                    self._turn = [field, 0]
        if not self._turn[0] or not self._texts[self._turn[0]]["bytes"]:
            self._next_text()

    def advance(self, seconds: float) -> None:
        self.now += seconds
        self._beat_time += seconds
        self._text_time += seconds
        while self._beat_time >= 0.5:
            self._beat_time -= 0.5
            self.beat = (self.beat + 1) % 256
        while self._text_time >= 0.2:
            self._text_time -= 0.2
            self._next_text()
        if self.test_until is not None and self.now >= self.test_until:
            self.test_until = None

    def send_command(self, name: str) -> None:
        self.command, self.command_count = _COMMAND_NUMBERS[name], (self.command_count + 1) % 256

    def send_moment(self, name: str) -> None:
        self.moment, self.moment_count = _MOMENT_NUMBERS[name], (self.moment_count + 1) % 256

    def frame(self) -> beacon.Frame:
        if self.test_until is not None:
            return beacon.Frame(kind=beacon.KIND_TEST)
        self._sync_texts()
        game = self.game
        flags = 0
        for on, bit in (
            (game.enabled, beacon.FLAG_ENABLED), (game.indoors, beacon.FLAG_INDOORS), (game.resting, beacon.FLAG_RESTING),
            (game.swimming, beacon.FLAG_SWIMMING), (game.submerged, beacon.FLAG_SUBMERGED), (game.mounted, beacon.FLAG_MOUNTED),
            (game.flying, beacon.FLAG_FLYING), (game.taxi, beacon.FLAG_TAXI), (game.stealth, beacon.FLAG_STEALTH),
            (game.dead or game.ghost, beacon.FLAG_DEAD), (game.combat, beacon.FLAG_COMBAT), (game.encounter, beacon.FLAG_ENCOUNTER),
            (game.cinematic, beacon.FLAG_CINEMATIC), (game.loading, beacon.FLAG_LOADING),
            (bool(game.day), beacon.FLAG_DAYTIME), (game.day is not None, beacon.FLAG_DAYTIME_KNOWN),
            (game.weather is not None, beacon.FLAG_WEATHER_KNOWN), (game.x is not None and game.y is not None, beacon.FLAG_POSITION_KNOWN),
            (game.in_instance, beacon.FLAG_IN_INSTANCE), (game.target is not None, beacon.FLAG_HAS_TARGET),
            (game.boss, beacon.FLAG_BOSS_PRESENT), (game.group, beacon.FLAG_IN_GROUP), (game.ghost, beacon.FLAG_GHOST),
        ):
            if on:
                flags |= bit

        def scaled(value: float | None, factor: float) -> int:
            if value is None:
                return beacon.UNKNOWN_16
            return max(0, min(beacon.UNKNOWN_16 - 1, int(value * factor + 0.5)))

        minutes = beacon.UNKNOWN_16
        if game.clock:
            hour, minute = game.clock.split(":")
            minutes = int(hour) * 60 + int(minute)
        field, chunk = self._turn
        entry = self._texts.get(field)
        piece = entry["bytes"][chunk * 6:chunk * 6 + 6].ljust(6, b"\0") if entry else b"\0" * 6
        position_known = game.x is not None and game.y is not None
        return beacon.Frame(
            beat=self.beat, flags=flags,
            instance_kind=_INSTANCE_NUMBERS.get(game.instance_kind, 15) if game.in_instance else 0,
            target_class=_TARGET_NUMBERS.get(game.target, 15) if game.target else 0,
            pvp_kind=_PVP_NUMBERS.get(game.pvp, 15) if game.pvp else 0,
            weather_kind=_WEATHER_NUMBERS[game.weather] if game.weather is not None else beacon.UNKNOWN_KIND,
            weather_intensity=scaled(game.weather_intensity, 1000) if game.weather is not None else beacon.UNKNOWN_16,
            map_id=game.map_id,
            x=scaled(game.x, 65534) if position_known else beacon.UNKNOWN_16,
            y=scaled(game.y, 65534) if position_known else beacon.UNKNOWN_16,
            instance_id=game.instance_id if game.in_instance else 0,
            encounter_id=game.encounter_id if game.encounter else 0,
            game_minutes=minutes,
            command=self.command, command_count=self.command_count,
            moment=self.moment, moment_count=self.moment_count,
            volume=game.volume, difficulty=game.difficulty if game.in_instance else 0,
            subzone_hash=beacon.text_hash(self._texts[2]["bytes"]),
            text_field=field, text_revision=entry["revision"] if entry else 0, text_chunk=chunk,
            text_length=len(entry["bytes"]) if entry else 0, text_bytes=piece,
        )


def load_scenario(name_or_path: str) -> dict:
    path = pathlib.Path(name_or_path)
    if not path.is_file():
        path = SCENARIOS / f"{name_or_path}.json"
    if not path.is_file():
        known = ", ".join(sorted(item.stem for item in SCENARIOS.glob("*.json")))
        raise FileNotFoundError(f"no scenario {name_or_path!r}; the ones that come with FreeRock are: {known}")
    return json.loads(path.read_text(encoding="utf-8"))


class SimSession:
    """A scenario being played: the pretend game, its strip on a pretend screen, and the clock.

    find_window, copy, clock and sleep are what sensor.Sensor needs, so the real sensor loop runs
    against this.
    """

    def __init__(self, scenario: dict, *, speed: float = 1.0, say=print, real_sleep=time.sleep) -> None:
        self.width, self.height = scenario.get("screen", [2560, 1440])
        self.cell = int(scenario.get("cell", 3))
        self.edge = scenario.get("edge", "top")
        self.inset_x, self.inset_y = scenario.get("inset", [16, 0])
        self.game = SimGame()
        self.game.change(scenario.get("start", {}))
        self.addon = SimAddon(self.game)
        self.steps = sorted(scenario.get("steps", []), key=lambda step: step["at"])
        self.speed, self.say, self._real_sleep = speed, say, real_sleep
        self.now = 0.0
        self.in_front = True
        self.hidden = False            # the strip is not on screen (a hidden interface, a loading screen)
        self._walk: dict | None = None
        self._next = 0
        self._band = min(sensor.BAND, self.height // 2)
        rng = np.random.default_rng(7)
        # What the game shows along its top and bottom edges: a busy picture that does not change.
        self._edges = {
            0: rng.integers(0, 256, (self._band, self.width, 3), dtype=np.uint8),
            self.height - self._band: rng.integers(0, 256, (self._band, self.width, 3), dtype=np.uint8),
        }
        self._drawn: tuple[bytes, np.ndarray] | None = None
        self._apply_due()  # steps at time 0 are how a scenario starts

    def still_in_front(self, window: sensor.Window) -> bool:
        return self.in_front

    @property
    def finished(self) -> bool:
        return self._next >= len(self.steps) and self._walk is None

    # -- the clock -----------------------------------------------------------
    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        seconds = max(seconds, 0.01)
        self._real_sleep(seconds / self.speed)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        """Lets time pass, a twentieth of a second at a time so that steps happen when they are due."""
        while seconds > 1e-9:
            piece = min(seconds, 0.05)
            seconds -= piece
            self._advance(piece)

    def _advance(self, seconds: float) -> None:
        self.now += seconds
        self.addon.advance(seconds)
        if self._walk:
            walk = self._walk
            share = min(1.0, (self.now - walk["from_time"]) / walk["seconds"])
            self.game.x = walk["from"][0] + (walk["to"][0] - walk["from"][0]) * share
            self.game.y = walk["from"][1] + (walk["to"][1] - walk["from"][1]) * share
            if share >= 1.0:
                self._walk = None
        self._apply_due()

    def _apply_due(self) -> None:
        while self._next < len(self.steps) and self.steps[self._next]["at"] <= self.now:
            self._apply(self.steps[self._next])
            self._next += 1

    def _apply(self, step: dict) -> None:
        known = {"at", "say", "set", "walk", "command", "moment", "test", "in_front", "hidden", "strip"}
        if set(step) - known:
            raise ValueError(f"a scenario step has parts this version does not know: {sorted(set(step) - known)}")
        if "say" in step:
            self.say(f"[{self.now:6.1f} s] {step['say']}")
        if "set" in step:
            self.game.change(step["set"])
        if "walk" in step:
            walk = step["walk"]
            self._walk = {"from": (self.game.x, self.game.y), "to": (walk["x"], walk["y"]),
                          "from_time": self.now, "seconds": float(walk["seconds"])}
        if "command" in step:
            self.addon.send_command(step["command"])
        if "moment" in step:
            self.addon.send_moment(step["moment"])
        if "test" in step:
            self.addon.test_until = self.now + float(step["test"])
        if "in_front" in step:
            self.in_front = bool(step["in_front"])
        if "hidden" in step:
            self.hidden = bool(step["hidden"])
        if "strip" in step:  # the player moves or resizes the strip (/rock strip ...)
            strip = step["strip"]
            unknown = set(strip) - {"cell", "edge", "inset"}
            if unknown:
                raise ValueError(f"a scenario changes parts of the strip this version does not know: {sorted(unknown)}")
            self.cell = int(strip.get("cell", self.cell))
            self.edge = strip.get("edge", self.edge)
            self.inset_x, self.inset_y = strip.get("inset", [self.inset_x, self.inset_y])
            self._drawn = None

    # -- the screen ------------------------------------------------------------
    def find_window(self) -> sensor.Window:
        return sensor.Window(0, 0, self.width, self.height, self.in_front)

    def _strip(self) -> np.ndarray:
        payload = beacon.pack(self.addon.frame())
        if self._drawn is None or self._drawn[0] != payload:
            self._drawn = (payload, beacon.render(payload, cell=self.cell))
        return self._drawn[1]

    def copy(self, left: int, top: int, width: int, height: int) -> bytes:
        """The pixels of a rectangle of the pretend screen, as a screen copy gives them (BGRA)."""
        if left < 0 or top < 0 or left + width > self.width or top + height > self.height:
            raise ValueError(f"the sensor asked for pixels outside the pretend screen: {left},{top} {width}x{height}")
        picture = np.zeros((height, width, 4), dtype=np.uint8)
        picture[:, :, 3] = 255
        for edge_top, edge in self._edges.items():
            first, last = max(top, edge_top), min(top + height, edge_top + edge.shape[0])
            if first < last:
                picture[first - top:last - top, :, :3] = edge[first - edge_top:last - edge_top, left:left + width]
        if not self.hidden and self.game.enabled:
            strip = self._strip()
            strip_top = self.inset_y if self.edge == "top" else self.height - self.inset_y - strip.shape[0]
            first, last = max(top, strip_top), min(top + height, strip_top + strip.shape[0])
            start, end = max(left, self.inset_x), min(left + width, self.inset_x + strip.shape[1])
            if first < last and start < end:
                piece = strip[first - strip_top:last - strip_top, start - self.inset_x:end - self.inset_x]
                picture[first - top:last - top, start - left:end - left, :3] = piece[:, :, None]
        return picture.tobytes()


def play(scenario: dict, server: str, *, speed: float = 1.0, say=print) -> None:
    """Plays a scenario against a running FreeRock server, at `speed` times real time."""
    session = SimSession(scenario, speed=speed, say=say)
    link = sensor.WebSocket(sensor.websocket_url(server))
    try:
        loop = sensor.Sensor(link, session.find_window, session.copy, clock=session.clock, sleep=session.sleep,
                             say=lambda text: say(f"[{session.now:6.1f} s] sensor: {text}"),
                             in_front=session.still_in_front)
        link.send_text(json.dumps({"type": "hello", "sensor": sensor.SENSOR_VERSION + "-sim", "platform": "pretend"}))
        while not session.finished:
            session.sleep(loop.step())
        # Let the last change be seen and sent before hanging up.
        for _ in range(10):
            session.sleep(loop.step())
    finally:
        link.close()
    say(f"[{session.now:6.1f} s] The scenario is over.")
