"""Notes on paper: what a part plays.

A part is a list of notes and of moves of the expression pedal, in beats. Nothing here knows
anything about music; it only writes down what the writers decide. The studio's desk finds each
voice's real sound by the name of its instrument (sounds.py).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

@dataclass
class Note:
    start: float               # in beats from the beginning of the track
    length: float              # in beats
    pitch: int                 # MIDI: 60 is middle C
    loud: float = 0.7          # 0 to 1


@dataclass
class Voice:
    """One instrument's line, or a drum kit's (each of its strokes written on a note of its own)."""
    notes: list[Note] = field(default_factory=list)
    drums: bool = False
    swells: list[tuple[float, float]] = field(default_factory=list)      # (beat, 0..1): the expression pedal
    pan: float = 0.0           # -1 left to 1 right
    shift: float = 0.0         # seconds: an instrument that speaks late is played a little early
    instrument: str = ""       # what it is called ("celli", "kit rock"): the studio's desk finds its real sound by this

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
