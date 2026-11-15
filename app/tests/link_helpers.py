"""Shared by the game-link tests: frames to test with, ways to spoil a picture, and the real
addon running under the stand-in client so its strip can be photographed.
"""
from __future__ import annotations

import io
import pathlib

import numpy as np
from hypothesis import strategies as st
from lupa import lua51
from PIL import Image
from scipy import ndimage

from freerock import beacon

REPO = pathlib.Path(__file__).resolve().parents[2]
CLIENT_LISTS = REPO.parent / "FreeControl" / "tools" / "sim" / "lab" / "dl-wowless-wowf-data"


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------
def frames() -> st.SearchStrategy[beacon.Frame]:
    """Any state frame the format can carry."""
    return st.builds(
        beacon.Frame,
        kind=st.just(beacon.KIND_STATE),
        beat=st.integers(0, 255),
        flags=st.integers(0, 0xFFFFFF),
        instance_kind=st.integers(0, 15),
        target_class=st.integers(0, 15),
        pvp_kind=st.integers(0, 15),
        weather_kind=st.integers(0, 15),
        weather_intensity=st.integers(0, 0xFFFF),
        map_id=st.integers(0, 0xFFFF),
        x=st.integers(0, 0xFFFF),
        y=st.integers(0, 0xFFFF),
        instance_id=st.integers(0, 0xFFFF),
        encounter_id=st.integers(0, 0xFFFF),
        game_minutes=st.integers(0, 0xFFFF),
        command=st.integers(0, 255),
        command_count=st.integers(0, 255),
        moment=st.integers(0, 255),
        moment_count=st.integers(0, 255),
        volume=st.integers(0, 255),
        difficulty=st.integers(0, 255),
        subzone_hash=st.integers(0, 0xFFFF),
        speed=st.integers(0, 255),
        text_field=st.integers(0, 7),
        text_revision=st.integers(0, 3),
        text_chunk=st.integers(0, 7),
        text_length=st.integers(0, 255),
        text_bytes=st.binary(min_size=6, max_size=6),
    )


SAMPLE = beacon.Frame(
    beat=200, flags=0x2A5A5B, instance_kind=2, target_class=5, pvp_kind=4, weather_kind=2,
    weather_intensity=999, map_id=1453, x=1, y=65534, instance_id=409, encounter_id=663,
    game_minutes=1439, command=3, command_count=255, moment=2, moment_count=9, volume=100,
    difficulty=9, subzone_hash=0xBEEF, text_field=4, text_revision=3, text_chunk=7, text_length=48,
    text_bytes=b"\xc3\xa9abcd",
)


# ---------------------------------------------------------------------------
# Pictures
# ---------------------------------------------------------------------------
def screen_band(strip: np.ndarray, *, at=(0, 16), height=40, extra=240, seed=0, busy=True) -> np.ndarray:
    """The top of a game screen with the strip on it: a busy picture (or flat grey) around it."""
    rng = np.random.default_rng(seed)
    rows, columns = strip.shape[:2]
    shape = (max(height, at[0] + rows + 4), at[1] + columns + extra)
    if busy:
        band = rng.integers(0, 256, shape).astype(np.float32)
        band = ndimage.uniform_filter(band, size=(1, 5)) * 0.5 + rng.integers(0, 256, shape) * 0.5
    else:
        band = np.full(shape, 128.0, dtype=np.float32)
    band[at[0]:at[0] + rows, at[1]:at[1] + columns] = strip
    return band


def as_picture(values: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def gamma(values: np.ndarray, power: float) -> np.ndarray:
    return 255.0 * (np.clip(values, 0, 255) / 255.0) ** power


def levels(values: np.ndarray, black: float, white: float) -> np.ndarray:
    """Black and white moved to other brightnesses (contrast, brightness, a dimmed screen)."""
    return black + values * ((white - black) / 255.0)


def dim_across(values: np.ndarray, left: float, right: float, lift: float = 0.0) -> np.ndarray:
    """Uneven dimming: brightness falls (or rises) across the picture, with an optional grey veil."""
    ramp = np.linspace(left, right, values.shape[1], dtype=np.float32)[None, :]
    veil = np.linspace(0.0, lift, values.shape[1], dtype=np.float32)[None, :]
    return values * ramp + veil


def tint(values: np.ndarray, gains=(1.0, 0.85, 0.6), lifts=(20.0, 0.0, 0.0)) -> np.ndarray:
    """A colour cast: each colour channel gets its own gain and offset. Returns an RGB picture."""
    return np.stack([values * gain + lift for gain, lift in zip(gains, lifts)], axis=2)


def blur(values: np.ndarray, sigma: float) -> np.ndarray:
    return ndimage.gaussian_filter(values, sigma)


def rescale(values: np.ndarray, factor: float) -> np.ndarray:
    """The picture resampled, as when the game is not drawn pixel for pixel."""
    image = Image.fromarray(as_picture(values))
    size = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    return np.asarray(image.resize(size, Image.BILINEAR)).astype(np.float32)


def noise(values: np.ndarray, sigma: float, seed: int = 0) -> np.ndarray:
    return values + np.random.default_rng(seed).normal(0.0, sigma, values.shape)


def jpeg(values: np.ndarray, quality: int) -> np.ndarray:
    buffer = io.BytesIO()
    Image.fromarray(as_picture(values)).save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    return np.asarray(Image.open(buffer)).astype(np.float32)


# ---------------------------------------------------------------------------
# The real addon under the stand-in client
# ---------------------------------------------------------------------------
def _read(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


_LOADER = """
function LoadAddon(saved)
	FreeRockDB = saved
	local ns = {}
	for line in ReadFile("FreeRock/FreeRock.toc"):gmatch("[^\\r\\n]+") do
		if line ~= "" and not line:match("^#") then
			local chunk = assert(loadstring(ReadFile("FreeRock/" .. line), "@FreeRock/" .. line))
			chunk("FreeRock", ns)
		end
	end
	Mock.Fire("ADDON_LOADED", "FreeRock")
	Mock.Fire("PLAYER_LOGIN")
	Mock.Fire("PLAYER_ENTERING_WORLD", true, false)
	return ns
end
"""


class GameClient:
    """FreeRock's Lua, loaded as the game loads it, in a stand-in client a test can steer."""

    def __init__(self, *, screen=(2560, 1440), ui_scale=0.71, saved: dict | None = None, game: dict | None = None):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        g = self.lua.globals()
        g.ReadFile = _read
        self.lua.execute(_read("tools/tests/wowmock.lua"))
        self.lua.execute(_LOADER)
        self.mock = g.Mock
        self.mock.screen[1], self.mock.screen[2] = screen
        g.UIParent.scale = ui_scale
        for key, value in (game or {}).items():
            self.mock.game[key] = value
        self.screen = screen
        self.ns = g.LoadAddon(self.lua.table_from(saved) if saved else None)

    # -- steering ----------------------------------------------------------------
    def set(self, **values) -> None:
        """Change what the game would answer. None clears an answer."""
        for key, value in values.items():
            if isinstance(value, dict):
                value = self.lua.table_from(value)
            self.mock.game[key] = value

    def fire(self, event: str, *arguments) -> None:
        self.mock.Fire(event, *arguments)

    def advance(self, seconds: float) -> None:
        self.mock.Advance(seconds)

    def slash(self, text: str) -> None:
        self.mock.Slash(text)

    def errors(self) -> list[str]:
        problems = [problem.text for problem in self.ns.GetProblems().values()]
        return list(self.mock.luaErrors.values()) + problems

    def printed(self) -> list[str]:
        return list(self.mock.printed.values())

    # -- looking -----------------------------------------------------------------
    def addon_frame(self) -> dict:
        """The frame the addon says it is showing, as plain numbers."""
        table = self.ns.Beacon.BuildFrame()
        fields = {key: value for key, value in table.items() if key != "text_bytes"}
        fields = {key: int(value) for key, value in fields.items()}
        if "text_bytes" in table and table.text_bytes is not None:
            data = [int(table.text_bytes[index] or 0) for index in range(1, 7)]
            fields["text_bytes"] = bytes(data)
        return fields

    def photograph(self, *, band: int = 48, seed: int = 0, busy: bool = True) -> np.ndarray | None:
        """A picture of the edge of the screen the strip is on, drawn from what the addon drew.

        Rectangles are painted with their true, unrounded edges: a strip laid out off the pixel
        grid comes out blurred here as it would on a real screen. None when no strip is showing.
        """
        rects = self.mock.StripRects()
        if rects is None:
            return None
        width, height = self.screen
        rects = [tuple(float(rect[index]) for index in range(1, 6)) for rect in rects.values()]
        top = min(rect[1] for rect in rects)
        band_top = 0 if top < height / 2 else height - band
        rng = np.random.default_rng(seed)
        if busy:
            picture = rng.integers(0, 256, (band, width)).astype(np.float32)
        else:
            picture = np.full((band, width), 128.0, dtype=np.float32)
        for x, y, w, h, grey in rects:
            y -= band_top
            x0, x1 = max(0.0, x), min(float(width), x + w)
            y0, y1 = max(0.0, y), min(float(band), y + h)
            if x1 <= x0 or y1 <= y0:
                continue
            columns = np.arange(int(np.floor(x0)), int(np.ceil(x1)))
            lines = np.arange(int(np.floor(y0)), int(np.ceil(y1)))
            cover_x = np.clip(np.minimum(columns + 1, x1) - np.maximum(columns, x0), 0, 1)
            cover_y = np.clip(np.minimum(lines + 1, y1) - np.maximum(lines, y0), 0, 1)
            cover = np.outer(cover_y, cover_x).astype(np.float32)
            area = picture[lines[0]:lines[-1] + 1, columns[0]:columns[-1] + 1]
            area *= 1.0 - cover
            area += cover * (grey * 255.0)
        return as_picture(picture)
