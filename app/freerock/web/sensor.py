# /// script
# requires-python = ">=3.10"
# dependencies = ["mss>=9"]
# ///
"""FreeRock sensor: copies the FreeRock strip off the game window and sends it to FreeRock.

Run it on the gaming PC:

    uv run http://<freerock-host>:8765/sensor.py                  (start reading the screen)
    uv run http://<freerock-host>:8765/sensor.py --install-addon  (put the addon in the game first)

It does one thing: about twenty times a second it copies the few rows of screen pixels where the
FreeRock addon draws its strip, and when those pixels have changed it sends them to the FreeRock
server. It does not read the strip itself, does not touch the game's memory, and sends no keys or
clicks. While the game is not the window in front it copies nothing.

Everything except the screen copy itself is plain Python with no extra packages, so the same file
is run by FreeRock's tests on Linux with a stand-in for the screen.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import io
import json
import os
import pathlib
import select
import shutil
import socket
import struct
import sys
import time
import urllib.parse
import urllib.request
import zipfile
import zlib

SENSOR_VERSION = "0.1.0"

# The server fills in its own address when it hands this file out, so that
# `uv run http://host:8765/sensor.py` needs no arguments.
DEFAULT_SERVER = "http://127.0.0.1:8765"

GAME_WINDOW_TITLE = "World of Warcraft"

# ---------------------------------------------------------------------------
# The wire format, shared with the server (which imports this file for it)
# ---------------------------------------------------------------------------
# A picture message is this header followed by the pixels: rows from the top, four bytes a pixel
# in the order blue, green, red, alpha. All numbers are little-endian.
#   magic "FRK1", flags (bit 0: the pixels are zlib-compressed), part (which piece of the window),
#   width, height of this piece, x, y of its top left corner inside the game window,
#   width, height of the game window, a count that goes up with every picture sent.
MAGIC = b"FRK1"
HEADER = struct.Struct("<4sBBHHhhHHI")
FLAG_ZLIB = 1
PART_TOP = 0      # the band along the top edge, sent while looking for the strip
PART_BOTTOM = 1   # the band along the bottom edge, likewise
PART_STRIP = 2    # just the strip, once the server has said where it is


@dataclasses.dataclass(frozen=True)
class Picture:
    part: int
    width: int
    height: int
    x: int
    y: int
    window_width: int
    window_height: int
    count: int
    pixels: bytes  # BGRA


def pack_picture(picture: Picture, compress: bool = True) -> bytes:
    if len(picture.pixels) != picture.width * picture.height * 4:
        raise ValueError(
            f"{picture.width} x {picture.height} pixels need {picture.width * picture.height * 4} bytes, "
            f"got {len(picture.pixels)}")
    body = zlib.compress(picture.pixels, 1) if compress else picture.pixels
    header = HEADER.pack(
        MAGIC, FLAG_ZLIB if compress else 0, picture.part, picture.width, picture.height,
        picture.x, picture.y, picture.window_width, picture.window_height, picture.count & 0xFFFFFFFF)
    return header + body


def unpack_picture(message: bytes) -> Picture:
    if len(message) < HEADER.size:
        raise ValueError(f"a picture message is at least {HEADER.size} bytes, got {len(message)}")
    magic, flags, part, width, height, x, y, window_width, window_height, count = HEADER.unpack_from(message)
    if magic != MAGIC:
        raise ValueError(f"not a FreeRock picture message (starts with {magic!r})")
    body = message[HEADER.size:]
    pixels = zlib.decompress(body) if flags & FLAG_ZLIB else bytes(body)
    if len(pixels) != width * height * 4:
        raise ValueError(f"{width} x {height} pixels need {width * height * 4} bytes, got {len(pixels)}")
    return Picture(part, width, height, x, y, window_width, window_height, count, pixels)


# ---------------------------------------------------------------------------
# A small WebSocket client (RFC 6455) on plain sockets, so no extra package is needed
# ---------------------------------------------------------------------------
class LinkClosed(ConnectionError):
    """The connection to FreeRock ended."""


class WebSocket:
    TEXT, BINARY, CLOSE, PING, PONG = 0x1, 0x2, 0x8, 0x9, 0xA

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("ws", "http"):
            raise ValueError(f"FreeRock is reached over plain http on the home network, not {parts.scheme}")
        host, port = parts.hostname, parts.port or 80
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._buffer = b""
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {parts.path or '/'} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self._socket.sendall(request.encode("ascii"))
        while b"\r\n\r\n" not in self._buffer:
            chunk = self._socket.recv(4096)
            if not chunk:
                raise LinkClosed("the server closed the connection during the handshake")
            self._buffer += chunk
        head, _, self._buffer = self._buffer.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0] + " ":
            raise LinkClosed(f"the server did not accept the connection: {lines[0]}")
        headers = {name.strip().lower(): value.strip() for name, _, value in (line.partition(":") for line in lines[1:])}
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise LinkClosed("the server's handshake answer does not match; is that address FreeRock?")
        self._socket.settimeout(timeout)

    def _send(self, opcode: int, payload: bytes) -> None:
        length = len(payload)
        if length < 126:
            head = bytes([0x80 | opcode, 0x80 | length])
        elif length < 65536:
            head = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", length)
        else:
            head = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", length)
        mask = os.urandom(4)
        if length:
            pad = (mask * (length // 4 + 1))[:length]
            payload = (int.from_bytes(payload, "big") ^ int.from_bytes(pad, "big")).to_bytes(length, "big")
        try:
            self._socket.sendall(head + mask + payload)
        except OSError as error:
            raise LinkClosed(f"sending failed: {error}") from error

    def send_text(self, text: str) -> None:
        self._send(self.TEXT, text.encode("utf-8"))

    def send_binary(self, data: bytes) -> None:
        self._send(self.BINARY, data)

    def _read(self, count: int) -> bytes:
        while len(self._buffer) < count:
            try:
                chunk = self._socket.recv(65536)
            except OSError as error:
                raise LinkClosed(f"receiving failed: {error}") from error
            if not chunk:
                raise LinkClosed("the server closed the connection")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data

    def receive(self, wait: float = 0.0) -> str | bytes | None:
        """The next message, or None if none arrives within `wait` seconds."""
        message, kind = b"", None
        while True:
            if not self._buffer and kind is None:
                ready, _, _ = select.select([self._socket], [], [], wait)
                if not ready:
                    return None
            first, second = self._read(2)
            opcode, final = first & 0x0F, bool(first & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if second & 0x80 else None
            payload = self._read(length)
            if mask:
                pad = (mask * (length // 4 + 1))[:length]
                payload = (int.from_bytes(payload, "big") ^ int.from_bytes(pad, "big")).to_bytes(length, "big") if length else b""
            if opcode == self.CLOSE:
                raise LinkClosed("the server closed the connection")
            if opcode == self.PING:
                self._send(self.PONG, payload)
                continue
            if opcode == self.PONG:
                continue
            if opcode in (self.TEXT, self.BINARY):
                kind = opcode
            message += payload
            if final:
                return message.decode("utf-8") if kind == self.TEXT else message

    def close(self) -> None:
        self._socket.close()


# ---------------------------------------------------------------------------
# The game window and the screen
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Window:
    """The inside of the game window, in screen pixels."""

    left: int
    top: int
    width: int
    height: int
    in_front: bool
    process_path: str | None = None
    handle: int | None = None  # Windows' own number for the window


class NoWindow(Exception):
    """Why the game window cannot be used right now, in words for the person at the screen."""


def find_game_window(title: str = GAME_WINDOW_TITLE) -> Window:
    """Finds the game's window on Windows. Raises NoWindow with the reason when it cannot."""
    if sys.platform != "win32":
        raise NoWindow("this is not Windows; use --monitor to read a whole screen instead")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(handle, _):
        if user32.IsWindowVisible(handle):
            length = user32.GetWindowTextLengthW(handle)
            if length:
                text = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(handle, text, length + 1)
                if text.value == title:
                    found.append(handle)
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        raise NoWindow(f'no window titled "{title}" is open; start the game')
    best, best_area, minimised = None, -1, False
    for handle in found:
        if user32.IsIconic(handle):
            minimised = True
            continue
        rect = wintypes.RECT()
        user32.GetClientRect(handle, ctypes.byref(rect))
        if rect.right * rect.bottom > best_area:
            best, best_area = handle, rect.right * rect.bottom
    if best is None:
        raise NoWindow("the game window is minimised" if minimised else "the game window has no size")
    rect = wintypes.RECT()
    user32.GetClientRect(best, ctypes.byref(rect))
    corner = wintypes.POINT(0, 0)
    user32.ClientToScreen(best, ctypes.byref(corner))
    if rect.right < 400 or rect.bottom < 100:
        raise NoWindow(f"the game window is only {rect.right} x {rect.bottom} pixels")
    return Window(corner.x, corner.y, rect.right, rect.bottom, user32.GetForegroundWindow() == best,
                  _process_path(best), best)


def window_in_front(window: Window) -> bool:
    """Whether the game window is the one in front right now. Cheap enough to ask before every copy."""
    if sys.platform != "win32" or window.handle is None:
        return window.in_front
    import ctypes

    return ctypes.windll.user32.GetForegroundWindow() == window.handle


def _process_path(handle) -> str | None:
    """The path of the program that owns a window, or None if Windows will not say."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    process_id = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
    process = kernel32.OpenProcess(0x1000, False, process_id.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        return None
    try:
        size = wintypes.DWORD(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)):
            return path.value
        return None
    finally:
        kernel32.CloseHandle(process)


def make_windows_see_real_pixels() -> None:
    """Without this, Windows hands a program scaled-up coordinates on a scaled display."""
    if sys.platform != "win32":
        return
    import ctypes

    result = ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per monitor
    # 0: done. 0x80070005: it was already set for this program, which is just as good.
    if result not in (0, -2147024891, 0x80070005):
        print(f"Note: Windows refused to switch off display scaling for the sensor (code {result:#x}). "
              "If the strip is never found, set the display to 100% scaling.")


class ScreenCopier:
    """Copies a rectangle of the screen with mss (a plain screen copy)."""

    def __init__(self) -> None:
        import mss  # imported here so everything else in this file works without it

        self._screen = mss.mss()

    def monitor(self, number: int) -> Window:
        monitors = self._screen.monitors  # [0] is all screens together, [1] the first screen
        if not 1 <= number < len(monitors):
            raise NoWindow(f"there is no screen number {number}; this machine has {len(monitors) - 1}")
        area = monitors[number]
        return Window(area["left"], area["top"], area["width"], area["height"], True)

    def copy(self, left: int, top: int, width: int, height: int) -> bytes:
        shot = self._screen.grab({"left": left, "top": top, "width": width, "height": height})
        return bytes(shot.raw)


# ---------------------------------------------------------------------------
# The sensor itself
# ---------------------------------------------------------------------------
BAND = 56          # rows of pixels copied along each edge while looking for the strip
SEARCH_EVERY = 0.5  # seconds between looks while the strip has not been found
TRACK_EVERY = 0.05  # seconds between copies once it has
RESEND_EVERY = 1.0  # an unchanged strip is still sent this often, so the server knows it is unchanged
STATUS_EVERY = 1.0
WINDOW_EVERY = 1.0  # how often the game window is looked up again (it can move or be resized)


class Sensor:
    """The loop: find the window, copy the pixels, send what changed, do what the server asks.

    Everything it touches is handed in, so the tests run this same loop with a pretend screen.
    """

    def __init__(self, link, find_window, copy, *, clock=time.monotonic, sleep=time.sleep,
                 say=print, even_in_background: bool = False, in_front=window_in_front) -> None:
        self.link, self.find_window, self.copy = link, find_window, copy
        self.clock, self.sleep, self.say = clock, sleep, say
        self.even_in_background = even_in_background
        self.in_front = in_front  # asked before every copy: is the game still the window in front?
        self.mode = "search"
        self.roi: tuple[int, int, int, int] | None = None
        self.window: Window | None = None
        self.sent = self.unchanged = self.count = 0
        self.last_pixels: bytes | None = None
        self.note: str | None = None      # why nothing is being copied, when nothing is
        self._window_at = self._status_at = self._sent_at = self._look_at = -1e9
        self._copy_seconds = 0.0
        self._copies = 0
        self._said: str | None = None

    def _tell(self, text: str) -> None:
        """Says something to the person at the screen, once, not on every pass of the loop."""
        if text != self._said:
            self._said = text
            self.say(text)

    def _handle(self, message: str) -> None:
        order = json.loads(message)
        if order.get("type") == "mode":
            mode = order.get("mode")
            if mode == "track":
                self.mode, self.roi = "track", tuple(int(value) for value in order["roi"])
                self.last_pixels = None
                self._tell("FreeRock found the strip and is reading it.")
            elif mode == "search":
                if self.mode != "search":
                    self._tell("FreeRock lost sight of the strip and is looking for it again.")
                self.mode, self.roi = "search", None
            else:
                raise ValueError(f"the server asked for a mode this sensor does not know: {mode!r}")
        elif order.get("type") == "note":
            self.say("FreeRock: " + str(order.get("text")))

    def _copy(self, x: int, y: int, width: int, height: int) -> bytes:
        """Copies a rectangle of the game window, and notes how long the copy took."""
        window = self.window
        started = self.clock()
        pixels = self.copy(window.left + x, window.top + y, width, height)
        self._copy_seconds += self.clock() - started
        self._copies += 1
        return pixels

    def _status(self, now: float) -> None:
        window = self.window
        self.link.send_text(json.dumps({
            "type": "status",
            "window": [window.width, window.height] if window else None,
            "in_front": bool(window and window.in_front),
            "mode": self.mode,
            "note": self.note,
            "sent": self.sent,
            "unchanged": self.unchanged,
            "copy_ms": round(1000 * self._copy_seconds / self._copies, 2) if self._copies else None,
        }))
        self._copy_seconds, self._copies = 0.0, 0
        self._status_at = now

    def step(self) -> float:
        """One pass. Returns how long to wait before the next."""
        now = self.clock()
        while True:
            message = self.link.receive(0.0)
            if message is None:
                break
            if isinstance(message, str):
                self._handle(message)

        if now - self._window_at >= WINDOW_EVERY:
            self._window_at = now
            try:
                self.window, self.note = self.find_window(), None
            except NoWindow as reason:
                self.window, self.note = None, str(reason)
                self._tell(f"Waiting: {reason}.")
            if self.window and not self.window.in_front and not self.even_in_background:
                self.note = "the game is not the window in front"
                self._tell("Waiting: the game is not the window in front.")
            elif self.window:
                self._tell(f"Game window found: {self.window.width} x {self.window.height} pixels. Looking for the strip."
                           if self.mode == "search" else "FreeRock found the strip and is reading it.")
        # The window is looked up once a second, but whether it is still in front is asked every
        # time, so that nothing of another window is copied in the second after switching away.
        if self.window and not self.note and not self.even_in_background and not self.in_front(self.window):
            self.window = dataclasses.replace(self.window, in_front=False)
            self.note = "the game is not the window in front"
            self._tell("Waiting: the game is not the window in front.")
        if now - self._status_at >= STATUS_EVERY:
            self._status(now)
        window = self.window
        if window is None or self.note:
            return 0.25

        if self.mode == "search":
            if now - self._look_at < SEARCH_EVERY:
                return 0.05
            self._look_at = now
            band = min(BAND, window.height // 2)
            for part, top in ((PART_TOP, 0), (PART_BOTTOM, window.height - band)):
                pixels = self._copy(0, top, window.width, band)
                self.count += 1
                self.link.send_binary(pack_picture(Picture(part, window.width, band, 0, top, window.width,
                                                           window.height, self.count, pixels)))
                self.sent += 1
            return 0.05

        x, y, width, height = self.roi
        # The window may have changed size since the server said where the strip is.
        if x < 0 or y < 0 or x + width > window.width or y + height > window.height:
            self.mode, self.roi = "search", None
            return 0.0
        pixels = self._copy(x, y, width, height)
        if pixels == self.last_pixels and now - self._sent_at < RESEND_EVERY:
            self.unchanged += 1
            return TRACK_EVERY
        self.last_pixels, self._sent_at = pixels, now
        self.count += 1
        self.link.send_binary(pack_picture(Picture(PART_STRIP, width, height, x, y, window.width,
                                                   window.height, self.count, pixels)))
        self.sent += 1
        return TRACK_EVERY

    def run(self) -> None:
        self.link.send_text(json.dumps({"type": "hello", "sensor": SENSOR_VERSION, "platform": sys.platform}))
        while True:
            self.sleep(self.step())


def websocket_url(server: str) -> str:
    parts = urllib.parse.urlsplit(server)
    return f"ws://{parts.netloc}/ws/sensor"


def read_the_screen(arguments) -> int:
    make_windows_see_real_pixels()
    copier = ScreenCopier()
    if arguments.monitor is not None:
        find_window = lambda: copier.monitor(arguments.monitor)
    else:
        find_window = lambda: find_game_window(arguments.title)
    print(f"FreeRock sensor {SENSOR_VERSION}. Sending to {arguments.server}. Close this window to stop.")
    wait = 1.0
    while True:
        try:
            link = WebSocket(websocket_url(arguments.server))
        except (OSError, LinkClosed) as error:
            print(f"Cannot reach FreeRock at {arguments.server}: {error}. Trying again in {wait:.0f} s.")
            time.sleep(wait)
            wait = min(wait * 2, 3.0)             # the server is a few yards away: a restart of it is over in seconds
            continue
        wait = 1.0
        print("Connected to FreeRock.")
        try:
            Sensor(link, find_window, copier.copy, even_in_background=arguments.always).run()
        except LinkClosed as error:
            print(f"The connection to FreeRock ended: {error}. Connecting again.")
            time.sleep(1.0)


# ---------------------------------------------------------------------------
# Installing the addon
# ---------------------------------------------------------------------------
ADDON_FOLDER = "FreeRock"
GAME_FOLDER = "_forever_"


def addon_folders(process_path: str | None, registry_path: str | None, roots: list[pathlib.Path]) -> list[pathlib.Path]:
    """Places the game's AddOns folder could be, most certain first. Only ones whose game folder exists."""
    candidates: list[pathlib.Path] = []
    if process_path:
        candidates.append(pathlib.Path(process_path).parent)          # ...\World of Warcraft\_forever_\<game>.exe
    if registry_path:
        candidates.append(pathlib.Path(registry_path).parent / GAME_FOLDER)  # InstallPath is one of the game's folders
        candidates.append(pathlib.Path(registry_path) / GAME_FOLDER)
    candidates += [root / GAME_FOLDER for root in roots]
    found: list[pathlib.Path] = []
    for folder in candidates:
        if folder.name.lower() == GAME_FOLDER and folder.is_dir():
            addons = folder / "Interface" / "AddOns"
            if addons not in found:
                found.append(addons)
    return found


def _registry_install_path() -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    for key_path in (r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft",
                     r"SOFTWARE\Blizzard Entertainment\World of Warcraft"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                return str(winreg.QueryValueEx(key, "InstallPath")[0])
        except FileNotFoundError:
            continue  # this machine keeps it under the other key, or not at all
    return None


def _usual_roots() -> list[pathlib.Path]:
    roots = []
    for drive in "CDEFG":
        for folder in (r"Program Files (x86)\World of Warcraft", r"Program Files\World of Warcraft",
                       "World of Warcraft", r"Games\World of Warcraft"):
            roots.append(pathlib.Path(f"{drive}:\\") / folder)
    return roots


def unpack_addon(archive: bytes, addons: pathlib.Path) -> int:
    """Replaces <addons>/FreeRock with the addon in the archive. Returns how many files were written."""
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = [name for name in bundle.namelist() if not name.endswith("/")]
        for name in names:
            parts = pathlib.PurePosixPath(name).parts
            if not parts or parts[0] != ADDON_FOLDER or ".." in parts or name.startswith("/") or "\\" in name:
                raise ValueError(f"the addon archive holds a file outside the {ADDON_FOLDER} folder: {name!r}")
        if f"{ADDON_FOLDER}/{ADDON_FOLDER}.toc" not in names:
            raise ValueError("the addon archive has no FreeRock.toc; it is not the addon")
        target = addons / ADDON_FOLDER
        if target.exists():
            shutil.rmtree(target)
        addons.mkdir(parents=True, exist_ok=True)
        bundle.extractall(addons, members=names)
    return len(names)


def install_addon(arguments) -> int:
    if arguments.addons_dir:
        folders = [pathlib.Path(arguments.addons_dir)]
    else:
        process_path = None
        try:
            process_path = find_game_window(arguments.title).process_path
        except NoWindow as reason:
            print(f"The running game could not be asked where it is installed ({reason}); looking in the usual places.")
        folders = addon_folders(process_path, _registry_install_path(), _usual_roots())
    if not folders:
        print("Could not find World of Warcraft: Forever on this PC. Start the game and run this again, or give the "
              r'folder yourself:  --addons-dir "D:\World of Warcraft\_forever_\Interface\AddOns"')
        return 1
    addons = folders[0]
    print(f"The game's AddOns folder: {addons}")
    if len(folders) > 1:
        print("(Also found: " + ", ".join(str(folder) for folder in folders[1:]) + ". Use --addons-dir to pick another.)")
    target = addons / ADDON_FOLDER
    question = (f"Replace the FreeRock addon in {target}?" if target.exists() else f"Install the FreeRock addon into {target}?")
    if not arguments.yes:
        if input(question + " [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing was changed.")
            return 1
    with urllib.request.urlopen(arguments.server.rstrip("/") + "/addon.zip", timeout=15) as response:
        archive = response.read()
    count = unpack_addon(archive, addons)
    print(f"Installed {count} files into {target}. If the game is running, type /reload in it (a full restart "
          "the first time the addon is installed).")
    return 0


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FreeRock sensor: sends the FreeRock strip from the game window to FreeRock.")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="where FreeRock is running (default: %(default)s)")
    parser.add_argument("--title", default=GAME_WINDOW_TITLE, help="title of the game window (default: %(default)s)")
    parser.add_argument("--monitor", type=int, help="read a whole screen instead of looking for the game window (1 is the first screen)")
    parser.add_argument("--always", action="store_true", help="keep copying while the game is not the window in front")
    parser.add_argument("--install-addon", action="store_true", help="put the FreeRock addon into the game's AddOns folder, then read the screen")
    parser.add_argument("--addons-dir", help="the game's Interface\\AddOns folder, if it is not found by itself")
    parser.add_argument("--yes", action="store_true", help="install without asking")
    arguments = parser.parse_args(argv)
    if arguments.install_addon:
        result = install_addon(arguments)
        if result != 0:
            return result
    return read_the_screen(arguments)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Stopped.")
        sys.exit(0)
