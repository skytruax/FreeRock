"""The strip format in numbers: packing, the checksum, the squares, and the shared vectors."""
import dataclasses
import json

import pytest
from hypothesis import given, settings

from freerock import beacon
from link_helpers import REPO, SAMPLE, frames

VECTORS = json.loads((REPO / "protocol" / "vectors.json").read_text(encoding="utf-8"))


def test_checksum_is_crc16_ccitt_false():
    assert beacon.crc16(b"123456789") == 0x29B1 == VECTORS["crc_check"]["crc16"]
    assert beacon.crc16(b"") == 0xFFFF


def test_layout_numbers_match_the_vectors_file():
    assert VECTORS["version"] == beacon.PROTOCOL_VERSION
    assert VECTORS["payload_bytes"] == beacon.PAYLOAD_BYTES == 40
    assert VECTORS["rows"] == beacon.ROWS == 2
    assert VECTORS["row_squares"] == beacon.ROW_CELLS_WITH_QUIET == 344


@pytest.mark.parametrize("case", VECTORS["frames"], ids=[case["name"] for case in VECTORS["frames"]])
def test_vector_frames(case):
    fields = dict(case["frame"])
    fields["text_bytes"] = bytes.fromhex(fields["text_bytes"])
    frame = beacon.Frame(**fields)
    payload = beacon.pack(frame)
    assert payload.hex() == case["payload"]
    assert beacon.unpack(payload) == frame
    assert beacon.cells_text(payload) == case["squares"]


@pytest.mark.parametrize("case", VECTORS["names"], ids=[repr(case["text"][:16]) for case in VECTORS["names"]])
def test_vector_names(case):
    sent = beacon.truncate_utf8(case["text"])
    assert sent.hex() == case["sent"]
    assert len(sent) <= beacon.TEXT_MAX_BYTES
    assert sent.decode("utf-8") == case["text"][:len(sent.decode("utf-8"))]
    assert beacon.text_hash(sent) == case["mark"]


def test_the_vectors_file_is_what_the_script_writes():
    """protocol/vectors.json is generated; a hand edit, or a format change without regenerating,
    would let the Lua and Python sides drift apart unnoticed."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_vectors", REPO / "tools" / "tests" / "make_vectors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, frame in module.FRAMES.items():
        case = next(case for case in VECTORS["frames"] if case["name"] == name)
        assert beacon.pack(frame).hex() == case["payload"], name
    assert len(module.FRAMES) == len(VECTORS["frames"])
    assert [case["text"] for case in VECTORS["names"]] == module.NAMES


@given(frames())
@settings(max_examples=300, deadline=None)
def test_any_frame_survives_packing(frame):
    payload = beacon.pack(frame)
    assert len(payload) == 40
    assert beacon.unpack(payload) == frame


def test_a_frame_that_does_not_fit_is_refused():
    with pytest.raises(beacon.BeaconError):
        beacon.pack(dataclasses.replace(SAMPLE, map_id=70000))
    with pytest.raises(beacon.BeaconError):
        beacon.pack(dataclasses.replace(SAMPLE, text_bytes=b"abc"))
    with pytest.raises(beacon.BeaconError):
        beacon.pack(dataclasses.replace(SAMPLE, text_chunk=8))


def test_unpack_refuses_what_is_not_a_frame():
    payload = beacon.pack(SAMPLE)
    with pytest.raises(beacon.BeaconError, match="40 bytes"):
        beacon.unpack(payload[:-1])
    for position in range(len(payload)):
        for bit in (0, 3, 7):
            spoiled = bytearray(payload)
            spoiled[position] ^= 1 << bit
            with pytest.raises(beacon.BeaconError):
                beacon.unpack(bytes(spoiled))
    # A later version of the format, correctly summed, is refused by name rather than misread.
    body = bytes([0x40]) + payload[1:-2]
    with pytest.raises(beacon.BeaconError, match="version 4"):
        beacon.unpack(body + beacon.crc16(body).to_bytes(2, "big"))


def test_older_addons_are_still_read_and_do_not_say_what_was_added_later():
    """The addon in the game may be older than the program. Versions 1 and 2 use the whole of
    the command and moment bytes for the command and the moment; version 3 shares them with the
    two counts of enemies."""
    new = dataclasses.replace(SAMPLE, command=2, moment=5, enemies=3, fighting=2)
    payload = beacon.pack(new)
    assert payload[21] == (3 << 4) | 2 and payload[23] == (2 << 4) | 5
    assert beacon.unpack(payload) == new
    for version in (1, 2):
        old = dataclasses.replace(SAMPLE, version=version, command=2, moment=5)
        payload = beacon.pack(old)
        assert payload[21] == 2 and payload[23] == 5
        read = beacon.unpack(payload)
        assert read == old
        assert (read.enemies, read.fighting) == (beacon.UNKNOWN_COUNT, beacon.UNKNOWN_COUNT)
    # A count that does not fit its four bits is refused, as is a command that no longer has eight.
    with pytest.raises(beacon.BeaconError):
        beacon.pack(dataclasses.replace(SAMPLE, enemies=16))
    with pytest.raises(beacon.BeaconError):
        beacon.pack(dataclasses.replace(SAMPLE, command=16))


def test_test_frames():
    payload = beacon.pack(beacon.Frame(kind=beacon.KIND_TEST))
    assert payload[0] == 0x31
    assert beacon.pack(beacon.Frame(kind=beacon.KIND_TEST, version=2))[0] == 0x21
    assert beacon.pack(beacon.Frame(kind=beacon.KIND_TEST, version=1))[0] == 0x11
    assert list(payload[1:4]) == [(17 * i + 3) % 256 for i in (1, 2, 3)]
    assert beacon.unpack(payload).kind == beacon.KIND_TEST
    body = bytearray(payload[:-2])
    body[5] ^= 0xFF
    with pytest.raises(beacon.BeaconError, match="test pattern"):
        beacon.unpack(bytes(body) + beacon.crc16(bytes(body)).to_bytes(2, "big"))


@given(frames())
@settings(max_examples=100, deadline=None)
def test_rows_of_squares_have_the_documented_shape(frame):
    payload = beacon.pack(frame)
    for row in range(beacon.ROWS):
        cells = beacon.row_cells(payload, row)
        assert len(cells) == 344
        assert cells[:2] == [0, 0] and cells[-2:] == [0, 0]
        assert cells[2:12] == [1, 1, 1, 1, 0, 0, 1, 0, 1, 0]
        assert cells[-8:-2] == [0, 0, 1, 1, 1, 1]
        data = cells[12:-8]
        assert len(data) == 4 + 320
        # Every bit is a pair of unlike squares, so no run inside the data is longer than two.
        assert all(data[index] != data[index + 1] for index in range(0, len(data), 2))
        row_id = [data[0], data[2]]
        assert row_id == [(row >> 1) & 1, row & 1]
        longest, run = 1, 1
        for before, after in zip(data, data[1:]):
            run = run + 1 if before == after else 1
            longest = max(longest, run)
        assert longest <= 2


def test_name_marks():
    assert beacon.text_hash(b"") == 0
    assert beacon.text_hash(b"Goldshire") == beacon.crc16(b"Goldshire") != 0
    assert beacon.truncate_utf8("x" * 60) == b"x" * 48
    assert beacon.truncate_utf8("x" * 47 + "é") == b"x" * 47
    assert beacon.truncate_utf8("x" * 46 + "é") == b"x" * 46 + "é".encode()
