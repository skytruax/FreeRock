"""Notes on paper: what a part plays, and the MIDI file that tells an instrument to play it.

A part is a list of notes and of moves of the expression pedal, in beats. Nothing here knows
anything about music; it only writes down what the writers decide.
"""
from __future__ import annotations

import random
import struct
from dataclasses import dataclass, field
from pathlib import Path

TICKS = 480                    # to a beat


@dataclass
class Note:
    start: float               # in beats from the beginning of the track
    length: float              # in beats
    pitch: int                 # MIDI: 60 is middle C
    loud: float = 0.7          # 0 to 1


@dataclass
class Voice:
    """One instrument's line: a program (General MIDI, 0 to 127), or the drum kit."""
    program: int
    notes: list[Note] = field(default_factory=list)
    drums: bool = False
    bank: int = 0
    swells: list[tuple[float, float]] = field(default_factory=list)      # (beat, 0..1): the expression pedal
    pan: float = 0.0           # -1 left to 1 right
    volume: float = 1.0        # 0 to 1: how loud the instrument is set
    shift: float = 0.0         # seconds: an instrument that speaks late is played a little early

    def add(self, start: float, length: float, pitch: int, loud: float = 0.7) -> None:
        if length > 0 and 0 <= pitch <= 127:
            self.notes.append(Note(start, length, int(pitch), min(max(loud, 0.02), 1.0)))


def humanise(voice: Voice, rng: random.Random, timing: float = 0.012, loud: float = 0.06, bpm: float = 100.0) -> None:
    """Nobody plays like a clock: each note a few milliseconds early or late and a little
    louder or softer. `timing` is in seconds."""
    beats = timing * bpm / 60.0
    for note in voice.notes:
        move = rng.gauss(0.0, beats)
        note.start = max(note.start + move, 0.0)
        note.loud = min(max(note.loud * (1.0 + rng.gauss(0.0, loud)), 0.02), 1.0)


def _varlen(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def write_midi(path: Path, voices: list[Voice], bpm: float, beats: float) -> None:
    """Writes the voices as a MIDI file `beats` long at `bpm`, each on its own channel (the
    drum kit on the tenth). At most fifteen pitched voices."""
    pitched = [voice for voice in voices if not voice.drums]
    if len(pitched) > 15:
        raise ValueError("A MIDI file has room for fifteen instruments and the drums; this has %d" % len(pitched))
    tracks = [b"\x00\xff\x51\x03" + struct.pack(">I", int(round(60_000_000 / bpm)))[1:]
              + _varlen(int(round(beats * TICKS))) + b"\xff\x2f\x00"]
    free = [channel for channel in range(16) if channel != 9]
    for voice in voices:
        channel = 9 if voice.drums else free.pop(0)
        late = voice.shift * bpm / 60.0
        events: list[tuple[int, int, bytes]] = []          # (tick, order, bytes): offs before ons at the same tick
        events.append((0, 0, bytes([0xB0 | channel, 0, voice.bank])))
        events.append((0, 1, bytes([0xC0 | channel, voice.program])))
        events.append((0, 2, bytes([0xB0 | channel, 7, int(round(voice.volume * 127))])))
        events.append((0, 2, bytes([0xB0 | channel, 10, int(round(64 + voice.pan * 63))])))
        if not voice.swells:
            events.append((0, 2, bytes([0xB0 | channel, 11, 127])))
        for beat, level in voice.swells:
            events.append((max(int(round((beat - late) * TICKS)), 0), 3, bytes([0xB0 | channel, 11, int(round(min(max(level, 0.0), 1.0) * 127))])))
        # A note that is struck again before it has ended is ended first: otherwise the end of
        # the first would silence the second.
        spans: dict[int, list[list[int]]] = {}
        for note in sorted(voice.notes, key=lambda each: each.start):
            on = max(int(round((note.start - late) * TICKS)), 0)
            off = max(int(round((note.start - late + note.length) * TICKS)), on + 1)
            same = spans.setdefault(note.pitch, [])
            if same and same[-1][1] > on - 1:
                same[-1][1] = max(on - 1, same[-1][0] + 1)
            if same and same[-1][0] >= on:
                continue                                   # the very same note twice at once: once is enough
            same.append([on, off, max(int(round(note.loud * 127)), 1)])
        for pitch, played in spans.items():
            for on, off, loud in played:
                events.append((on, 5, bytes([0x90 | channel, pitch, loud])))
                events.append((off, 4, bytes([0x80 | channel, pitch, 0])))
        events.sort(key=lambda event: (event[0], event[1]))
        data, now = bytearray(), 0
        for tick, _, message in events:
            data += _varlen(tick - now) + message
            now = tick
        data += b"\x00\xff\x2f\x00"
        tracks.append(bytes(data))
    with open(path, "wb") as out:
        out.write(b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), TICKS))
        for track in tracks:
            out.write(b"MTrk" + struct.pack(">I", len(track)) + track)
