#!/usr/bin/env python3
"""Writes protocol/vectors.json: frames, the 40 bytes they pack to, and the squares they draw as.

    cd app && uv run --no-sync python ../tools/tests/make_vectors.py

The cases are listed here by hand. The bytes and squares come from app/freerock/beacon.py; the Lua
side (FreeRock/Beacon.lua) must produce exactly the same for the same frame, which tools/tests and
app/tests both check. The checksum routine itself is pinned to the published check value for
CRC-16/CCITT-FALSE, so the two sides cannot agree on a wrong one.
"""
import dataclasses
import json
import pathlib

from freerock import beacon

ROOT = pathlib.Path(__file__).resolve().parents[2]

FRAMES = {
    "nothing known": beacon.Frame(),
    "elwynn, walking past goldshire": beacon.Frame(
        beat=7,
        flags=beacon.FLAG_ENABLED | beacon.FLAG_DAYTIME | beacon.FLAG_DAYTIME_KNOWN
        | beacon.FLAG_WEATHER_KNOWN | beacon.FLAG_POSITION_KNOWN,
        pvp_kind=2, weather_kind=0, weather_intensity=0,
        map_id=1429, x=27500, y=42800, game_minutes=875,
        volume=70, subzone_hash=beacon.text_hash(b"Goldshire"),
        text_field=beacon.TEXT_SUBZONE, text_revision=1, text_chunk=0, text_length=9, text_bytes=b"Goldsh",
    ),
    "in a mine, fighting an elite, in the rain": beacon.Frame(
        beat=200,
        flags=beacon.FLAG_ENABLED | beacon.FLAG_INDOORS | beacon.FLAG_COMBAT | beacon.FLAG_HAS_TARGET
        | beacon.FLAG_DAYTIME_KNOWN | beacon.FLAG_WEATHER_KNOWN | beacon.FLAG_POSITION_KNOWN,
        target_class=2, pvp_kind=3, weather_kind=1, weather_intensity=450,
        map_id=1429, x=40100, y=53300, game_minutes=1310,
        command=1, command_count=12, moment=1, moment_count=3,
        volume=85, subzone_hash=beacon.text_hash(b"Fargodeep Mine"),
        text_field=beacon.TEXT_SUBZONE, text_revision=2, text_chunk=2, text_length=14, text_bytes=b"ne\x00\x00\x00\x00",
    ),
    "running up to a boar, sizing it up": beacon.Frame(
        beat=31,
        flags=beacon.FLAG_ENABLED | beacon.FLAG_DAYTIME | beacon.FLAG_DAYTIME_KNOWN | beacon.FLAG_WEATHER_KNOWN
        | beacon.FLAG_POSITION_KNOWN | beacon.FLAG_HAS_TARGET | beacon.FLAG_TARGET_HOSTILE,
        target_class=1, pvp_kind=3, weather_kind=0, weather_intensity=0,
        map_id=1429, x=30111, y=44002, game_minutes=880, volume=70, speed=14,
        subzone_hash=beacon.text_hash(b"Goldshire"),
        text_field=beacon.TEXT_ZONE, text_revision=1, text_chunk=1, text_length=13, text_bytes=b" Fores",
    ),
    "dungeon boss": beacon.Frame(
        beat=255,
        flags=beacon.FLAG_ENABLED | beacon.FLAG_INDOORS | beacon.FLAG_COMBAT | beacon.FLAG_ENCOUNTER
        | beacon.FLAG_IN_INSTANCE | beacon.FLAG_HAS_TARGET | beacon.FLAG_BOSS_PRESENT | beacon.FLAG_IN_GROUP,
        instance_kind=1, target_class=5, pvp_kind=0,
        map_id=0, instance_id=36, encounter_id=1144, game_minutes=65,
        moment=4, moment_count=255, volume=100, difficulty=1,
        text_field=beacon.TEXT_ENCOUNTER, text_revision=3, text_chunk=1, text_length=16, text_bytes=b"n Clee",
    ),
    "every field at its largest": beacon.Frame(
        beat=255, flags=0xFFFFFF, instance_kind=15, target_class=15, pvp_kind=15, weather_kind=15,
        weather_intensity=0xFFFF, map_id=0xFFFF, x=0xFFFF, y=0xFFFF, instance_id=0xFFFF,
        encounter_id=0xFFFF, game_minutes=0xFFFF, command=255, command_count=255, moment=255,
        moment_count=255, volume=255, difficulty=255, subzone_hash=0xFFFF, speed=255,
        text_field=7, text_revision=3, text_chunk=7, text_length=255, text_bytes=b"\xff" * 6,
    ),
    "test frame": beacon.Frame(kind=beacon.KIND_TEST),
}

# Names as the game gives them, and what is sent for them.
NAMES = [
    "",
    "Goldshire",
    "Fargodeep Mine",
    "Zul'Gurub",
    "The Temple of Atal'Hakkar, where the old gods sleep under green water",  # longer than 48 bytes
    "a" * 47 + "\u00e9" + "tail",   # the cut would split a two-byte character: 47 bytes are sent
    "b" * 46 + "\u2014" + "tail",   # the cut would split a three-byte character: 46 bytes are sent
    "Caf\u00e9 \u00e0 l'\u00eele",   # short, with two-byte characters
]


def frame_fields(frame: beacon.Frame) -> dict:
    fields = dataclasses.asdict(frame)
    fields["text_bytes"] = frame.text_bytes.hex()
    return fields


def main() -> None:
    vectors = {
        "version": beacon.PROTOCOL_VERSION,
        "payload_bytes": beacon.PAYLOAD_BYTES,
        "rows": beacon.ROWS,
        "row_squares": beacon.ROW_CELLS_WITH_QUIET,
        "crc_check": {"text": "123456789", "crc16": beacon.crc16(b"123456789")},
        "frames": [],
        "names": [],
    }
    for name, frame in FRAMES.items():
        payload = beacon.pack(frame)
        assert beacon.unpack(payload) == frame, name
        vectors["frames"].append({
            "name": name,
            "frame": frame_fields(frame),
            "payload": payload.hex(),
            "squares": beacon.cells_text(payload),
        })
    for text in NAMES:
        sent = beacon.truncate_utf8(text)
        sent.decode("utf-8")  # a cut that split a character would fail here
        vectors["names"].append({"text": text, "sent": sent.hex(), "mark": beacon.text_hash(sent)})
    path = ROOT / "protocol" / "vectors.json"
    path.write_text(json.dumps(vectors, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(vectors['frames'])} frames, {len(vectors['names'])} names)")


if __name__ == "__main__":
    main()
