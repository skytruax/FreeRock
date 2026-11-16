"""The strip: the thin line of black and white squares the addon draws, and how to read it.

The format is defined in protocol/beacon.md. This file is the Python half of it: packing and
unpacking the 40-byte payload, laying it out as squares, drawing it (for the tests and the fake
sensor), and finding and reading it in a picture of the screen.

Reading never trusts a fixed position or a fixed brightness. A row is found by its sync pattern,
its square size is measured from its own edges, and every bit is two squares side by side, read by
asking which of the two is brighter. A checksum over the payload decides whether a reading counts.
"""
from __future__ import annotations

import dataclasses
import struct
from collections import Counter

import numpy as np
from scipy import ndimage

# Version 2 gave two things a meaning that version 1 left empty: byte 29 is the player's speed,
# and bit 23 of the flags says the target can be fought. Version 3 put two small numbers in the
# upper halves of the command and moment bytes: how many enemies have a nameplate on screen, and
# how many of those are in a fight. Everything else is the same, so all three are read; an older
# addon simply does not say the things a later version added.
PROTOCOL_VERSION = 3
KNOWN_VERSIONS = (1, 2, 3)
PAYLOAD_BYTES = 40
ROWS = 2
BITS_PER_ROW = PAYLOAD_BYTES * 8 // ROWS  # 160

# One row of squares, left to right: quiet, finder, clock, row number, data, end mark, quiet.
# 1 is a white square, 0 a black one.
QUIET = 2
FINDER = (1, 1, 1, 1, 0, 0)
CLOCK = (1, 0, 1, 0)
END = (0, 0, 1, 1, 1, 1)
ROW_ID_BITS = 2
ROW_CELLS = len(FINDER) + len(CLOCK) + 2 * ROW_ID_BITS + 2 * BITS_PER_ROW + len(END)  # 340
ROW_CELLS_WITH_QUIET = ROW_CELLS + 2 * QUIET  # 344
_DATA_START = len(FINDER) + len(CLOCK)  # the row number's first square

KIND_STATE = 0
KIND_TEST = 1

# Bits of Frame.flags (bit 0 is the least significant bit of the 24-bit number).
FLAG_ENABLED = 1 << 0
FLAG_INDOORS = 1 << 1
FLAG_RESTING = 1 << 2
FLAG_SWIMMING = 1 << 3
FLAG_SUBMERGED = 1 << 4
FLAG_MOUNTED = 1 << 5
FLAG_FLYING = 1 << 6
FLAG_TAXI = 1 << 7
FLAG_STEALTH = 1 << 8
FLAG_DEAD = 1 << 9
FLAG_COMBAT = 1 << 10
FLAG_ENCOUNTER = 1 << 11
FLAG_CINEMATIC = 1 << 12
FLAG_LOADING = 1 << 13
FLAG_DAYTIME = 1 << 14
FLAG_DAYTIME_KNOWN = 1 << 15
FLAG_WEATHER_KNOWN = 1 << 16
FLAG_POSITION_KNOWN = 1 << 17
FLAG_IN_INSTANCE = 1 << 18
FLAG_HAS_TARGET = 1 << 19
FLAG_BOSS_PRESENT = 1 << 20
FLAG_IN_GROUP = 1 << 21
FLAG_GHOST = 1 << 22
FLAG_TARGET_HOSTILE = 1 << 23   # version 2: the target is something the player can fight

UNKNOWN_16 = 0xFFFF
UNKNOWN_KIND = 15
UNKNOWN_SPEED = 255             # version 2: the speed byte when the game does not give a speed
UNKNOWN_COUNT = 15              # version 3: a count of enemies the game did not give
MANY = 14                       # version 3: a count of enemies this large means "this many or more"

TEXT_NONE = 0
TEXT_ZONE = 1
TEXT_SUBZONE = 2
TEXT_INSTANCE = 3
TEXT_ENCOUNTER = 4
TEXT_NOTE = 5                   # the addon's own line about itself: its version and what it counted
TEXT_CHUNK_BYTES = 6
TEXT_MAX_BYTES = 48  # eight chunks

_BODY = struct.Struct(">BB3sBB7H6BHBBB6s")  # everything before the checksum: 38 bytes
assert _BODY.size == PAYLOAD_BYTES - 2


class BeaconError(ValueError):
    """A payload that cannot be a strip frame: wrong length, version or checksum."""


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: polynomial 0x1021, start 0xFFFF, no reflection, no final XOR."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def text_hash(text: bytes) -> int:
    """The 16-bit mark of a name, sent in every frame so a change shows before the name arrives.

    Zero means "no name". A name whose checksum happens to be zero is sent as 0xFFFF instead.
    """
    if not text:
        return 0
    return crc16(text) or 0xFFFF


def truncate_utf8(text: str, limit: int = TEXT_MAX_BYTES) -> bytes:
    """The UTF-8 bytes of a name, cut to the limit without splitting a character."""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return data
    cut = limit
    while cut > 0 and (data[cut] & 0xC0) == 0x80:
        cut -= 1
    return data[:cut]


@dataclasses.dataclass(frozen=True)
class Frame:
    """One strip frame exactly as it is sent: whole numbers, nothing interpreted yet."""

    kind: int = KIND_STATE
    version: int = PROTOCOL_VERSION
    beat: int = 0
    flags: int = 0
    instance_kind: int = 0
    target_class: int = 0
    pvp_kind: int = 0
    weather_kind: int = UNKNOWN_KIND
    weather_intensity: int = UNKNOWN_16
    map_id: int = 0
    x: int = UNKNOWN_16
    y: int = UNKNOWN_16
    instance_id: int = 0
    encounter_id: int = 0
    game_minutes: int = UNKNOWN_16
    command: int = 0
    command_count: int = 0
    moment: int = 0
    moment_count: int = 0
    volume: int = 0
    difficulty: int = 0
    subzone_hash: int = 0
    speed: int = UNKNOWN_SPEED     # half yards a second; in a version 1 frame the byte is empty (0)
    # Version 3: enemies with a nameplate on screen, and how many of them are in a fight. 0 to 13,
    # 14 for that many or more, 15 not known. Earlier versions do not say (the Frame holds 15).
    enemies: int = UNKNOWN_COUNT
    fighting: int = UNKNOWN_COUNT
    text_field: int = TEXT_NONE
    text_revision: int = 0
    text_chunk: int = 0
    text_length: int = 0
    text_bytes: bytes = b"\x00" * TEXT_CHUNK_BYTES


def test_pattern_body() -> bytes:
    """Bytes 1 to 37 of a test frame: a fixed sequence that exercises every bit position."""
    return bytes((17 * index + 3) % 256 for index in range(1, PAYLOAD_BYTES - 2))


def pack(frame: Frame) -> bytes:
    """The 40 bytes of a frame, checksum included."""
    if frame.version not in KNOWN_VERSIONS:
        raise BeaconError(f"version = {frame.version} is not a strip version this program writes")
    if frame.kind == KIND_TEST:
        body = bytes([(frame.version << 4) | KIND_TEST]) + test_pattern_body()
    else:
        if len(frame.text_bytes) != TEXT_CHUNK_BYTES:
            raise BeaconError(f"a text chunk is {TEXT_CHUNK_BYTES} bytes, got {len(frame.text_bytes)}")
        for name, limit in (
            ("kind", 15), ("beat", 255), ("flags", 0xFFFFFF), ("instance_kind", 15),
            ("target_class", 15), ("pvp_kind", 15), ("weather_kind", 15),
            ("weather_intensity", 0xFFFF), ("map_id", 0xFFFF), ("x", 0xFFFF), ("y", 0xFFFF),
            ("instance_id", 0xFFFF), ("encounter_id", 0xFFFF), ("game_minutes", 0xFFFF),
            ("command", 255 if frame.version < 3 else 15), ("command_count", 255),
            ("moment", 255 if frame.version < 3 else 15), ("moment_count", 255),
            ("volume", 255), ("difficulty", 255), ("subzone_hash", 0xFFFF), ("speed", 255),
            ("enemies", 15), ("fighting", 15),
            ("text_field", 7), ("text_revision", 3), ("text_chunk", 7), ("text_length", 255),
        ):
            value = getattr(frame, name)
            if not 0 <= value <= limit:
                raise BeaconError(f"{name} = {value} does not fit (0 to {limit})")
        # From version 3 the command and the moment share their bytes with the two counts.
        shared = frame.version >= 3
        body = _BODY.pack(
            (frame.version << 4) | frame.kind,
            frame.beat,
            frame.flags.to_bytes(3, "big"),
            (frame.instance_kind << 4) | frame.target_class,
            (frame.pvp_kind << 4) | frame.weather_kind,
            frame.weather_intensity, frame.map_id, frame.x, frame.y,
            frame.instance_id, frame.encounter_id, frame.game_minutes,
            (frame.enemies << 4) | frame.command if shared else frame.command, frame.command_count,
            (frame.fighting << 4) | frame.moment if shared else frame.moment, frame.moment_count,
            frame.volume, frame.difficulty,
            frame.subzone_hash,
            frame.speed,
            (frame.text_field << 5) | (frame.text_revision << 3) | frame.text_chunk,
            frame.text_length,
            frame.text_bytes,
        )
    return body + crc16(body).to_bytes(2, "big")


def unpack(payload: bytes) -> Frame:
    """The frame in 40 bytes. Raises BeaconError when the bytes are not a frame of this version."""
    if len(payload) != PAYLOAD_BYTES:
        raise BeaconError(f"a payload is {PAYLOAD_BYTES} bytes, got {len(payload)}")
    body, checksum = payload[:-2], int.from_bytes(payload[-2:], "big")
    if crc16(body) != checksum:
        raise BeaconError("checksum does not match")
    version, kind = body[0] >> 4, body[0] & 0x0F
    if version not in KNOWN_VERSIONS:
        raise BeaconError(f"strip version {version}; this reader knows versions "
                          + " and ".join(str(known) for known in KNOWN_VERSIONS))
    if kind == KIND_TEST:
        if body[1:] != test_pattern_body():
            raise BeaconError("a test frame with the wrong test pattern")
        return Frame(kind=KIND_TEST, version=version)
    (
        _, beat, flags, kinds_a, kinds_b,
        weather_intensity, map_id, x, y, instance_id, encounter_id, game_minutes,
        command, command_count, moment, moment_count, volume, difficulty,
        subzone_hash, speed, text_header, text_length, text_bytes,
    ) = _BODY.unpack(body)
    enemies = fighting = UNKNOWN_COUNT
    if version >= 3:
        enemies, command = command >> 4, command & 0x0F
        fighting, moment = moment >> 4, moment & 0x0F
    return Frame(
        kind=kind, version=version, beat=beat, flags=int.from_bytes(flags, "big"),
        instance_kind=kinds_a >> 4, target_class=kinds_a & 0x0F,
        pvp_kind=kinds_b >> 4, weather_kind=kinds_b & 0x0F,
        weather_intensity=weather_intensity, map_id=map_id, x=x, y=y,
        instance_id=instance_id, encounter_id=encounter_id, game_minutes=game_minutes,
        command=command, command_count=command_count, moment=moment, moment_count=moment_count,
        volume=volume, difficulty=difficulty, subzone_hash=subzone_hash, speed=speed,
        enemies=enemies, fighting=fighting,
        text_field=text_header >> 5, text_revision=(text_header >> 3) & 0x03,
        text_chunk=text_header & 0x07, text_length=text_length, text_bytes=text_bytes,
    )


# ---------------------------------------------------------------------------
# Squares
# ---------------------------------------------------------------------------
def _bits(data: bytes) -> list[int]:
    return [(byte >> shift) & 1 for byte in data for shift in range(7, -1, -1)]


def _manchester(bits: list[int]) -> list[int]:
    """Each bit as two squares: 1 is white then black, 0 is black then white."""
    cells: list[int] = []
    for bit in bits:
        cells += (1, 0) if bit else (0, 1)
    return cells


def row_cells(payload: bytes, row: int) -> list[int]:
    """The squares of one row, quiet squares included (344 values, 1 white and 0 black)."""
    if len(payload) != PAYLOAD_BYTES:
        raise BeaconError(f"a payload is {PAYLOAD_BYTES} bytes, got {len(payload)}")
    if not 0 <= row < ROWS:
        raise BeaconError(f"row {row} of {ROWS}")
    bits = _bits(payload)[row * BITS_PER_ROW:(row + 1) * BITS_PER_ROW]
    row_id = [(row >> shift) & 1 for shift in range(ROW_ID_BITS - 1, -1, -1)]
    cells = list(FINDER) + list(CLOCK) + _manchester(row_id) + _manchester(bits) + list(END)
    return [0] * QUIET + cells + [0] * QUIET


def cells_text(payload: bytes) -> list[str]:
    """Each row as a string of # (white) and . (black), for the test vectors."""
    return ["".join("#" if cell else "." for cell in row_cells(payload, row)) for row in range(ROWS)]


def render(payload: bytes, cell: int = 3, margin: int = 2, white: int = 255, black: int = 0) -> np.ndarray:
    """A grey picture of the strip, the way the addon draws it: black backing, white squares."""
    if cell < 1:
        raise ValueError("a square is at least one pixel")
    height = ROWS * cell + 2 * margin
    width = ROW_CELLS_WITH_QUIET * cell + 2 * margin
    image = np.full((height, width), black, dtype=np.uint8)
    for row in range(ROWS):
        cells = np.array(row_cells(payload, row), dtype=bool)
        line = np.repeat(np.where(cells, white, black).astype(np.uint8), cell)
        top = margin + row * cell
        image[top:top + cell, margin:margin + line.size] = line
    return image


# ---------------------------------------------------------------------------
# Reading a picture
# ---------------------------------------------------------------------------
MIN_PITCH = 0.9   # smallest square, in pixels, the reader will lock on to: one pixel, drawn pixel for pixel
MAX_PITCH = 9.5   # largest
_WINDOW = 81      # pixels over which "white" and "black" are judged; wider than any run of squares
# The squares may be drawn faint (dark grey on the black backing) so the strip is hard to see on
# screen. Judged against a bright sky next to it, a faint strip would count as all black. So when
# a picture gives no frame as it is, it is looked at again with everything brighter than a ceiling
# flattened to that ceiling, lower each time. Each look: (the ceiling or None, the white-minus-black
# difference, out of 255, below which a stretch counts as featureless). A strip whose squares are
# brighter than half a ceiling is readable in that look, so the ceilings step down by less than
# half each time and squares from white down to about 16 of 255 are covered.
_LOOKS = ((None, 28.0), (150.0, 24.0), (88.0, 18.0), (52.0, 14.0), (30.0, 9.0))
_WORSE = {"no strip": 0, "half a strip": 1, "checksum": 2}   # which failure says most about a picture


@dataclasses.dataclass(frozen=True)
class RowRead:
    """One row of squares read off one line of pixels."""

    row: int            # the row number the squares themselves carry
    bits: bytes         # the row's 160 data bits, packed into 20 bytes
    y: int              # the line of pixels it was read from
    x: float            # where the finder starts, in pixels
    pitch: float        # the size of a square, in pixels
    margin: float       # the weakest white-against-black difference, as a share of the typical one


@dataclasses.dataclass(frozen=True)
class Reading:
    """What was found in a picture."""

    payload: bytes | None = None
    frame: Frame | None = None
    box: tuple[int, int, int, int] | None = None  # x, y, width, height of the strip in the picture
    pitch: float | None = None
    rows_seen: tuple[int, ...] = ()
    problem: str | None = None  # why there is no frame: "no strip", "half a strip", "checksum", ...
    look: int | None = None     # which look found the frame: 0 as the picture is, higher for a fainter strip

    @property
    def ok(self) -> bool:
        return self.frame is not None


def to_luma(image: np.ndarray) -> np.ndarray:
    """Brightness of each pixel as float32. Accepts grey, RGB, RGBA or BGRA pictures."""
    array = np.asarray(image)
    if array.ndim == 2:
        return array.astype(np.float32)
    if array.ndim == 3 and array.shape[2] in (3, 4):
        # The plain average of the three colours: the strip is grey, so the order of the colour
        # channels does not matter and neither does a tint.
        return array[:, :, :3].astype(np.float32).mean(axis=2)
    raise ValueError(f"cannot read a picture of shape {array.shape}")


def _edge(line: np.ndarray, threshold: np.ndarray, index: int) -> float:
    """Where, between pixel index-1 and pixel index, the brightness crosses the threshold."""
    before, after = float(line[index - 1]), float(line[index])
    level = (float(threshold[index - 1]) + float(threshold[index])) / 2
    if after == before:
        return float(index)
    share = min(1.0, max(0.0, (level - before) / (after - before)))
    return index - 0.5 + share


def _sample(line: np.ndarray, centres: np.ndarray, pitch: float) -> np.ndarray:
    """Brightness of each square: the middle of it, averaged over a little width."""
    pixels = np.arange(line.size, dtype=np.float32) + 0.5
    spread = 0.22 * pitch
    total = np.interp(centres, pixels, line)
    total += np.interp(centres - spread, pixels, line)
    total += np.interp(centres + spread, pixels, line)
    return total / 3.0


def _read_row(line: np.ndarray, threshold: np.ndarray, starts: np.ndarray, first: int, y: int) -> RowRead | None:
    """Follow a row of squares from a finder candidate. None when it is not a row after all.

    starts[first] is the pixel where the finder's white run begins. Every later change between
    white and black must fall on a square boundary; the boundaries are used to measure the square
    size ever more exactly as the row is followed to its end mark.
    """
    if first + 5 >= starts.size:
        return None
    origin = _edge(line, threshold, int(starts[first]))
    # The finder and clock put edges at squares 0, 4, 6, 7, 8 and 9.
    pitch = (_edge(line, threshold, int(starts[first + 5])) - origin) / 9.0
    if not MIN_PITCH <= pitch <= MAX_PITCH:
        return None
    # Least squares fit of edge position against square number, updated as edges come in.
    count, sum_k, sum_e, sum_kk, sum_ke = 1.0, 0.0, origin, 0.0, 0.0
    last_k = 0
    for index in range(first + 1, starts.size):
        position = _edge(line, threshold, int(starts[index]))
        k = round((position - origin) / pitch)
        if k <= last_k or k - last_k > 5:
            return None  # two edges in one square, or a run longer than any the strip has
        if abs(position - (origin + k * pitch)) > 0.42 * pitch:
            return None
        if k > ROW_CELLS:
            return None
        count += 1.0
        sum_k += k
        sum_e += position
        sum_kk += k * k
        sum_ke += k * position
        spread = count * sum_kk - sum_k * sum_k
        if count >= 4 and spread > 0:
            pitch = (count * sum_ke - sum_k * sum_e) / spread
            origin = (sum_e - pitch * sum_k) / count
        last_k = k
        if k == ROW_CELLS:
            break
    if last_k != ROW_CELLS:
        return None
    if not MIN_PITCH <= pitch <= MAX_PITCH:
        return None

    centres = origin + (np.arange(ROW_CELLS, dtype=np.float32) + 0.5) * pitch
    if centres[0] < 0 or centres[-1] > line.size:
        return None
    values = _sample(line, centres, pitch)
    # The fixed squares must read as drawn, each judged against its opposite-coloured neighbours.
    fixed = list(FINDER) + list(CLOCK)
    head = values[:len(fixed)]
    white = head[[i for i, cell in enumerate(fixed) if cell]].min()
    black = head[[i for i, cell in enumerate(fixed) if not cell]].max()
    tail = values[ROW_CELLS - len(END):]
    if white <= black or tail[2:].min() <= tail[:2].max():
        return None

    pairs = values[_DATA_START:ROW_CELLS - len(END)].reshape(-1, 2)
    difference = pairs[:, 0] - pairs[:, 1]
    typical = float(np.median(np.abs(difference)))
    if typical <= 0:
        return None
    bits = (difference > 0).astype(np.uint8)
    row = int(bits[0]) << 1 | int(bits[1])
    if row >= ROWS:
        return None
    return RowRead(
        row=row,
        bits=np.packbits(bits[ROW_ID_BITS:]).tobytes(),
        y=y,
        x=origin,
        pitch=pitch,
        margin=float(np.abs(difference).min()) / typical,
    )


def _scan_line(line: np.ndarray, white: np.ndarray, threshold: np.ndarray, y: int) -> list[RowRead]:
    """Every row of squares that starts somewhere on this line of pixels."""
    change = np.flatnonzero(white[1:] != white[:-1]) + 1
    if change.size < 12:
        return []
    starts = np.concatenate(([0], change))
    lengths = np.diff(np.concatenate((starts, [line.size]))).astype(np.float32)
    colours = white[starts]
    index = np.arange(1, starts.size - 5)
    unit = lengths[index] / 4.0
    loose = np.maximum(0.6 * unit, 1.25)
    candidate = (
        colours[index]
        & (unit >= MIN_PITCH * 0.75) & (unit <= MAX_PITCH * 1.25)
        & (lengths[index - 1] >= np.maximum(unit, 1.0))                      # quiet squares before
        & (np.abs(lengths[index + 1] - 2 * unit) <= np.maximum(0.75 * unit, 1.25))
        & (np.abs(lengths[index + 2] - unit) <= loose)
        & (np.abs(lengths[index + 3] - unit) <= loose)
        & (np.abs(lengths[index + 4] - unit) <= loose)
    )
    reads = []
    for first in index[candidate]:
        read = _read_row(line, threshold, starts, int(first), y)
        if read is not None:
            reads.append(read)
    return reads


def read_rows(image: np.ndarray, look: int = 0) -> list[RowRead]:
    """Every row of squares readable anywhere in the picture, one entry per line of pixels.

    `look` picks one of _LOOKS: 0 judges the picture as it is, higher ones flatten its bright
    parts first so that a faint strip stands out from what is around it.
    """
    luma = to_luma(image)
    if luma.shape[1] < ROW_CELLS * MIN_PITCH:
        return []
    ceiling, least = _LOOKS[look]
    if ceiling is not None:
        luma = np.minimum(luma, np.float32(ceiling))
    high = ndimage.maximum_filter1d(luma, size=_WINDOW, axis=1, mode="nearest")
    low = ndimage.minimum_filter1d(luma, size=_WINDOW, axis=1, mode="nearest")
    threshold = (high + low) / 2.0
    white = (luma > threshold) & ((high - low) >= least)
    reads: list[RowRead] = []
    for y in range(luma.shape[0]):
        reads.extend(_scan_line(luma[y], white[y], threshold[y], y))
    return reads


def read(image: np.ndarray, look_first: int | None = None, every_look: bool = True) -> Reading:
    """Find the strip in a picture and read its frame.

    The result always says what happened: a frame, or the reason there is none. `look_first` is
    the look that found the last frame (Reading.look); starting there saves the looks that a
    faint strip is known to fail. With `every_look` false only that one look is taken, which is
    a fifth of the work on a large picture that may hold no strip at all.
    """
    luma = to_luma(image)
    order = list(range(len(_LOOKS)))
    if look_first is not None and look_first in order:
        order.remove(look_first)
        order.insert(0, look_first)
    if not every_look:
        order = order[:1]
    best = Reading(problem="no strip")
    for look in order:
        reading = _read_look(luma, look)
        if reading.ok:
            return reading
        if _WORSE[reading.problem] > _WORSE[best.problem]:
            best = reading
    return best


def _read_look(luma: np.ndarray, look: int) -> Reading:
    """One look at a picture: a frame, or the reason this look found none."""
    reads = read_rows(luma, look)
    if not reads:
        return Reading(problem="no strip")
    by_row: dict[int, list[RowRead]] = {}
    for item in reads:
        by_row.setdefault(item.row, []).append(item)
    rows_seen = tuple(sorted(by_row))
    if len(by_row) < ROWS:
        return Reading(rows_seen=rows_seen, problem="half a strip")

    # Several lines of pixels cross each row of squares. The reading most of them agree on is
    # tried first; the checksum has the last word.
    choices = []
    for row in range(ROWS):
        counted = Counter(item.bits for item in by_row[row])
        choices.append([bits for bits, _ in counted.most_common(3)])
    for top in choices[0]:
        for bottom in choices[1]:
            payload = top + bottom
            try:
                frame = unpack(payload)
            except BeaconError:
                continue
            used = [item for item in reads if item.bits in (top, bottom)]
            pitch = float(np.median([item.pitch for item in used]))
            left = float(np.median([item.x for item in used])) - QUIET * pitch
            first_y = min(item.y for item in used)
            last_y = max(item.y for item in used)
            box = (
                max(0, int(np.floor(left))),
                first_y,
                int(np.ceil(ROW_CELLS_WITH_QUIET * pitch)),
                last_y - first_y + 1,
            )
            return Reading(payload=payload, frame=frame, box=box, pitch=pitch, rows_seen=rows_seen, look=look)
    return Reading(rows_seen=rows_seen, problem="checksum")
