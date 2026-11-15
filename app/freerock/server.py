"""FreeRock's server: takes in what the sensor sees, keeps the game's state, and serves the pages.

This file is the game link. The sensor on the gaming PC connects to /ws/sensor and sends pictures
of the edge of the game window; they are read here (beacon.py), turned into game state (state.py)
and published on the hub, which is where the rest of FreeRock listens. The page at / shows what
FreeRock sees, live.

To add to the server from another module: call create_app(), then add routes to the application
it returns, and read `app["hub"]` for the game's state and events.
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import dataclasses
import datetime
import io
import json
import logging
import math
import time
import zipfile
from pathlib import Path

import numpy as np
from aiohttp import WSMsgType, web
from PIL import Image

from freerock import beacon, state
from freerock.settings import REPO_ROOT, VAR_DIR
from freerock.web import sensor as wire

log = logging.getLogger("freerock.server")

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC_FILES = {"link.js": "application/javascript", "link.css": "text/css"}


@dataclasses.dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    var_dir: Path = VAR_DIR                      # where logs and captured strips are written
    addon_dir: Path = REPO_ROOT / "FreeRock"     # the addon folder handed out as /addon.zip
    front_page: str = "/"                        # the page the launcher opens on the gaming PC
    lost_after: float = 1.0                      # seconds without a good read before looking for the strip again
    keep_log: bool = True                        # write the log of changes to var/log as well as keeping it in memory


# Fields left out of the log of changes: two that change all the time and would drown it, and two
# that only say whether another field has a value.
_QUIET_FIELDS = {"position", "game_minutes", "has_subzone", "has_target"}

# How each field is named in the log, for a person reading it against what they did in the game.
_LABELS = {
    "enabled": "FreeRock in the game", "map_id": "Map", "zone_name": "Zone", "subzone_name": "Subzone",
    "in_instance": "In an instance", "instance_kind": "Instance kind", "instance_id": "Instance number",
    "instance_name": "Instance", "difficulty": "Difficulty", "indoors": "Indoors", "resting": "Resting",
    "swimming": "Swimming", "submerged": "Under water", "mounted": "Mounted", "flying": "Flying",
    "on_taxi": "Flight path", "stealthed": "Stealth", "dead": "Dead", "ghost": "Ghost", "in_combat": "In combat",
    "encounter": "Boss fight", "encounter_id": "Boss fight number", "encounter_name": "Boss",
    "boss_present": "Boss present", "target_class": "Target", "in_group": "In a group", "pvp_kind": "Territory",
    "weather": "Weather", "weather_intensity": "Weather intensity", "daytime": "Daylight",
    "cinematic": "Cinematic", "loading": "Loading screen", "volume": "Volume",
}

_LINK_WORDS = {
    state.Link.LIVE: "The strip is being read.",
    state.Link.STALE: "The strip cannot be read; the last state is being held.",
    state.Link.LOST: "The strip has not been read for a long time.",
    state.Link.OFF: "FreeRock was switched off in the game.",
}


def _words(value, name: str = "") -> str:
    if name == "daytime" and value is not None:
        return "day" if value else "night"
    if name == "enabled":
        return "on" if value else "off"
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if value is None:
        return "not known"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


class SensorConnection:
    """One connected sensor: what it last said about itself, and what it has been asked to do."""

    def __init__(self, address: str, now: float) -> None:
        self.address = address
        self.connected_at = now
        self.mode = "search"
        self.roi: list[int] | None = None
        self.last_good = now
        self.status: dict = {}
        self.hello: dict = {}
        self.copy_rate: float | None = None      # screen copies a second, from the sensor's own counts
        self._copies_at: tuple[float, int] | None = None


class LinkService:
    """Everything between a picture arriving and the hub hearing about it."""

    def __init__(self, config: ServerConfig, hub: state.Hub, clock=time.monotonic) -> None:
        self.config = config
        self.hub = hub
        self.clock = clock
        self.started = clock()
        self.tracker = state.StateTracker(clock=clock)
        self.sensors: list[SensorConnection] = []
        self.log: collections.deque = collections.deque(maxlen=500)
        self.counts = {"pictures": 0, "read": 0, "checksum": 0, "half": 0, "no_strip": 0}
        self._good_times: collections.deque = collections.deque()
        self.strip: dict = {"found": False, "box": None, "pitch": None, "roi": None}
        self._strip_pixels: np.ndarray | None = None   # the strip as last captured, for the page
        self._strip_read = False
        self._ui: set[web.WebSocketResponse] = set()
        self._dirty = True
        self._log_file = None

    # -- the log of changes --------------------------------------------------
    def note(self, text: str, kind: str = "note") -> None:
        entry = {
            "at": datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "since_start": round(self.clock() - self.started, 3),
            "kind": kind,
            "text": text,
        }
        self.log.append(entry)
        self._dirty = True
        if self.config.keep_log:
            if self._log_file is None:
                folder = self.config.var_dir / "log"
                folder.mkdir(parents=True, exist_ok=True)
                self._log_file = open(folder / f"link-{datetime.date.today().isoformat()}.jsonl", "a", encoding="utf-8")
            self._log_file.write(json.dumps(entry) + "\n")
            self._log_file.flush()

    def close(self) -> None:
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

    def publish(self, events: list) -> None:
        for event in events:
            if isinstance(event, state.StateChanged):
                if event.previous is None:
                    self.note("First state read from the strip.", "state")
                for name in sorted(event.changed - _QUIET_FIELDS):
                    before = getattr(event.previous, name) if event.previous else None
                    after = getattr(event.state, name)
                    if event.previous is None and after in (False, None, 0, "none", "unknown"):
                        continue
                    self.note(f"{_LABELS.get(name, name)}: {_words(before, name)} -> {_words(after, name)}", "state")
            elif isinstance(event, state.CommandReceived):
                self.note(f"Command from the game: {event.name} (number {event.count}).", "command")
            elif isinstance(event, state.MomentReceived):
                self.note(f"Moment in the game: {event.name} (number {event.count}).", "moment")
            elif isinstance(event, state.LinkChanged):
                self.note(_LINK_WORDS[event.link], "link")
            elif isinstance(event, state.TestPatternSeen):
                self.note("The addon's test pattern was read: every square is in the right place.", "test")
            self.hub.publish(event)
        if events:
            self._dirty = True

    # -- sensors -----------------------------------------------------------------
    def sensor_connected(self, address: str) -> SensorConnection:
        connection = SensorConnection(address, self.clock())
        self.sensors.append(connection)
        self.note(f"Sensor connected from {address}.", "sensor")
        return connection

    def sensor_disconnected(self, connection: SensorConnection) -> None:
        self.sensors.remove(connection)
        self.note(f"Sensor at {connection.address} disconnected.", "sensor")

    def take_status(self, message: dict, connection: SensorConnection) -> None:
        if message.get("type") == "hello":
            connection.hello = message
            self.note(f"Sensor {message.get('sensor')} on {message.get('platform')}.", "sensor")
        elif message.get("type") == "status":
            before = connection.status.get("note")
            connection.status = message
            copies, now = int(message.get("sent") or 0) + int(message.get("unchanged") or 0), self.clock()
            if connection._copies_at is not None and now > connection._copies_at[0]:
                connection.copy_rate = round((copies - connection._copies_at[1]) / (now - connection._copies_at[0]), 1)
            connection._copies_at = (now, copies)
            if message.get("note") != before:
                self.note(f"Sensor: {message['note']}." if message.get("note") else "Sensor: copying the screen.", "sensor")
        self._dirty = True

    def take_picture(self, picture: wire.Picture, connection: SensorConnection) -> dict | None:
        """Reads one picture from the sensor. Returns what to tell the sensor, if anything."""
        now = self.clock()
        pixels = np.frombuffer(picture.pixels, dtype=np.uint8).reshape(picture.height, picture.width, 4)
        reading = beacon.read(pixels)
        self.counts["pictures"] += 1
        self._dirty = True
        if not reading.ok:
            self.counts[{"checksum": "checksum", "half a strip": "half"}.get(reading.problem, "no_strip")] += 1
            if picture.part == wire.PART_STRIP:
                self._strip_pixels, self._strip_read = pixels, False
                if now - connection.last_good >= self.config.lost_after:
                    connection.mode, connection.roi = "search", None
                    self.strip = {"found": False, "box": None, "pitch": None, "roi": None}
                    self.note(f"The strip can no longer be read ({reading.problem}); looking for it again.", "strip")
                    return {"type": "mode", "mode": "search"}
            return None

        self.counts["read"] += 1
        self._good_times.append(now)
        connection.last_good = now
        x, y, width, height = reading.box
        self._strip_pixels = pixels[y:y + height, x:x + width]
        self._strip_read = True
        box = [picture.x + x, picture.y + y, width, height]
        order = None
        side, above = 6, max(3, math.ceil(reading.pitch))
        roi = [
            max(0, box[0] - side),
            max(0, box[1] - above),
            min(picture.window_width, box[0] + width + side) - max(0, box[0] - side),
            min(picture.window_height, box[1] + height + above) - max(0, box[1] - above),
        ]
        # Ask the sensor for just the strip, the first time and again whenever the strip has moved
        # within what it sends.
        if connection.mode != "track" or abs(roi[0] - connection.roi[0]) > 2 or abs(roi[1] - connection.roi[1]) > 2 \
                or abs(roi[2] - connection.roi[2]) > 4 or abs(roi[3] - connection.roi[3]) > 4:
            if connection.mode != "track":
                self.note(f"Strip found at {box[0]}, {box[1]}: {width} x {height} px, squares of {reading.pitch:.2f} px.", "strip")
            connection.mode, connection.roi = "track", roi
            order = {"type": "mode", "mode": "track", "roi": roi}
        self.strip = {"found": True, "box": box, "pitch": round(reading.pitch, 3), "roi": connection.roi}
        self.publish(self.tracker.feed(reading.frame))
        return order

    # -- time passing ---------------------------------------------------------
    def tick(self) -> None:
        self.publish(self.tracker.tick())
        horizon = self.clock() - 5.0
        while self._good_times and self._good_times[0] < horizon:
            self._good_times.popleft()

    def read_rate(self) -> float:
        """Good reads a second over the last five seconds."""
        horizon = self.clock() - 5.0
        recent = [moment for moment in self._good_times if moment >= horizon]
        return round(len(recent) / 5.0, 1)

    # -- what the page shows ----------------------------------------------------
    def snapshot(self, log_lines: int = 100) -> dict:
        tracker = self.tracker
        sensor = self.sensors[-1] if self.sensors else None
        since_good = tracker.seconds_since_good()
        since_test = None if tracker.last_test_at is None else round(self.clock() - tracker.last_test_at, 1)
        return {
            "link": tracker.link.value,
            "seconds_since_read": None if since_good is None else round(since_good, 2),
            "state": tracker.state.as_dict() if tracker.state else None,
            "sensor": None if sensor is None else {
                "address": sensor.address,
                "version": sensor.hello.get("sensor"),
                "platform": sensor.hello.get("platform"),
                "mode": sensor.mode,
                "copy_rate": sensor.copy_rate,
                **{key: sensor.status.get(key) for key in ("window", "in_front", "note", "copy_ms", "sent", "unchanged")},
            },
            "strip": self.strip,
            "counts": {**self.counts, "names_rejected": tracker.name_rejects},
            "read_rate": self.read_rate(),
            "test_pattern_seconds_ago": since_test,
            "log": list(self.log)[-log_lines:],
        }

    def strip_png(self, zoom: int = 3) -> bytes | None:
        """The strip as the gaming PC last captured it, enlarged so the squares can be seen."""
        if self._strip_pixels is None:
            return None
        picture = Image.fromarray(np.ascontiguousarray(self._strip_pixels[:, :, 2::-1]), "RGB")  # BGRA -> RGB
        picture = picture.resize((picture.width * zoom, picture.height * zoom), Image.NEAREST)
        output = io.BytesIO()
        picture.save(output, "PNG")
        return output.getvalue()

    async def push(self, force: bool = False) -> None:
        """Sends the current picture of things to every open page, if anything changed."""
        if not (self._dirty or force) or not self._ui:
            return
        self._dirty = False
        message = json.dumps(self.snapshot())
        for socket in list(self._ui):
            if socket.closed:
                self._ui.discard(socket)
                continue
            try:
                await socket.send_str(message)
            except ConnectionError as error:
                # The page was closed while this was being sent. The other pages still get theirs.
                self._ui.discard(socket)
                log.info("a page went away while being updated: %s", error)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def _sensor_socket(request: web.Request) -> web.WebSocketResponse:
    socket = web.WebSocketResponse(max_msg_size=64 * 1024 * 1024)
    await socket.prepare(request)
    link: LinkService = request.app["link"]
    connection = link.sensor_connected(request.remote or "unknown")
    try:
        async for message in socket:
            if message.type == WSMsgType.BINARY:
                try:
                    picture = wire.unpack_picture(message.data)
                except ValueError as error:
                    link.note(f"The sensor sent something that is not a picture: {error}", "problem")
                    raise
                order = link.take_picture(picture, connection)
                if order is not None:
                    await socket.send_str(json.dumps(order))
            elif message.type == WSMsgType.TEXT:
                link.take_status(json.loads(message.data), connection)
            elif message.type == WSMsgType.ERROR:
                raise socket.exception()
    finally:
        link.sensor_disconnected(connection)
    return socket


async def _ui_socket(request: web.Request) -> web.WebSocketResponse:
    socket = web.WebSocketResponse()
    await socket.prepare(request)
    link: LinkService = request.app["link"]
    link._ui.add(socket)
    try:
        await socket.send_str(json.dumps(link.snapshot()))
        async for message in socket:
            if message.type == WSMsgType.ERROR:
                raise socket.exception()
    finally:
        link._ui.discard(socket)
    return socket


async def _front_page(request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_DIR / "link.html")


async def _static(request: web.Request) -> web.FileResponse:
    name = request.match_info["name"]
    if name not in STATIC_FILES:
        raise web.HTTPNotFound()
    return web.FileResponse(WEB_DIR / name, headers={"Content-Type": STATIC_FILES[name], "Cache-Control": "no-cache"})


async def _snapshot(request: web.Request) -> web.Response:
    return web.json_response(request.app["link"].snapshot())


async def _state(request: web.Request) -> web.Response:
    link: LinkService = request.app["link"]
    return web.json_response({
        "link": link.tracker.link.value,
        "state": link.tracker.state.as_dict() if link.tracker.state else None,
    })


async def _log(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", "500"))
    return web.json_response(list(request.app["link"].log)[-limit:])


async def _strip_png(request: web.Request) -> web.Response:
    data = request.app["link"].strip_png()
    if data is None:
        raise web.HTTPNotFound(text="No strip has been captured yet.")
    return web.Response(body=data, content_type="image/png", headers={"Cache-Control": "no-store"})


def _address(request: web.Request) -> str:
    """How the machine asking reached this server; the files handed out point back to it."""
    return f"http://{request.host}"


async def _sensor_script(request: web.Request) -> web.Response:
    source = (WEB_DIR / "sensor.py").read_text(encoding="utf-8")
    marker = f'DEFAULT_SERVER = "{wire.DEFAULT_SERVER}"'
    if source.count(marker) != 1:
        raise web.HTTPInternalServerError(text="sensor.py no longer has the line the server fills in.")
    source = source.replace(marker, f'DEFAULT_SERVER = "{_address(request)}"')
    return web.Response(text=source, content_type="text/x-python", headers={"Cache-Control": "no-store"})


def addon_archive(addon_dir: Path) -> bytes:
    """The addon folder as a zip, laid out the way the game's AddOns folder wants it."""
    if not (addon_dir / "FreeRock.toc").is_file():
        raise FileNotFoundError(f"no FreeRock.toc in {addon_dir}")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(addon_dir.rglob("*")):
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(addon_dir).parts):
                bundle.write(path, f"FreeRock/{path.relative_to(addon_dir).as_posix()}")
    return output.getvalue()


async def _addon_zip(request: web.Request) -> web.Response:
    data = addon_archive(request.app["config"].addon_dir)
    return web.Response(body=data, content_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="FreeRock-addon.zip"', "Cache-Control": "no-store"})


LAUNCHER = """@echo off
rem FreeRock launcher. Opens FreeRock's page in its own browser window, with sound allowed to
rem start without a click, then starts the sensor in this window. Close this window to stop.
rem Needs uv (https://docs.astral.sh/uv/): in PowerShell,
rem   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
title FreeRock
start "" msedge --app={address}{page} --user-data-dir="%LOCALAPPDATA%\\FreeRock\\browser" --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows
uv run {address}/sensor.py
pause
"""


async def _launcher(request: web.Request) -> web.Response:
    text = LAUNCHER.format(address=_address(request), page=request.app["config"].front_page)
    return web.Response(text=text.replace("\n", "\r\n"), content_type="text/plain",
                        headers={"Content-Disposition": 'attachment; filename="FreeRock.cmd"', "Cache-Control": "no-store"})


async def _keep_time(app: web.Application) -> None:
    """Four times a second: notice time passing without a read, and refresh the open pages."""
    link: LinkService = app["link"]
    last_push = 0.0
    while True:
        await asyncio.sleep(0.25)
        link.tick()
        now = link.clock()
        await link.push(force=now - last_push >= 1.0)
        last_push = now if now - last_push >= 1.0 else last_push


def _timekeeper_ended(app: web.Application, task: asyncio.Task) -> None:
    """Without the timekeeper a silent strip would never be noticed, so its failure is said loudly."""
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        log.error("the server's timekeeper stopped: %r", error, exc_info=error)
        app["link"].note(f"FreeRock's timekeeper stopped with an error: {error!r}. Restart the server.", "problem")


async def _start(app: web.Application) -> None:
    task = asyncio.create_task(_keep_time(app))
    task.add_done_callback(lambda finished: _timekeeper_ended(app, finished))
    app["timekeeper"] = task


async def _stop(app: web.Application) -> None:
    task = app["timekeeper"]
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):  # how a cancelled task ends; any other error still raises
        await task
    for socket in list(app["link"]._ui):
        await socket.close()
    app["link"].close()


def create_app(config: ServerConfig | None = None, *, hub: state.Hub | None = None, clock=time.monotonic) -> web.Application:
    """The server as an aiohttp application, ready to have more routes added before it is run."""
    config = config or ServerConfig()
    app = web.Application()
    app["config"] = config
    app["hub"] = hub or state.Hub()
    app["link"] = LinkService(config, app["hub"], clock=clock)
    app.router.add_get("/", _front_page)
    app.router.add_get("/static/{name}", _static)
    app.router.add_get("/ws/sensor", _sensor_socket)
    app.router.add_get("/ws/ui", _ui_socket)
    app.router.add_get("/api/snapshot", _snapshot)
    app.router.add_get("/api/state", _state)
    app.router.add_get("/api/log", _log)
    app.router.add_get("/api/strip.png", _strip_png)
    app.router.add_get("/sensor.py", _sensor_script)
    app.router.add_get("/addon.zip", _addon_zip)
    app.router.add_get("/FreeRock.cmd", _launcher)
    app.on_startup.append(_start)
    app.on_cleanup.append(_stop)
    return app


def serve(config: ServerConfig | None = None) -> None:
    """Runs the server until it is stopped."""
    config = config or ServerConfig()
    print(f"FreeRock is listening on port {config.port}. On the gaming PC open http://<this machine>:{config.port}/")
    web.run_app(create_app(config), host=config.host, port=config.port, print=None)
