"""Keys, chords and how a chord is laid out for a group of players.

Everything a writer writes is in steps of a scale, not in notes: degree 0 is the key note, 2 the
third above it, 7 the key note an octave up, -1 the note under it. Only when a part is handed
to an instrument do the steps become pitches, in whatever key the family of tracks is in. That
is what lets one tune be played over the chords in any key, and moved up bodily when the story
lifts into another key for its moment.
"""
from __future__ import annotations

from dataclasses import dataclass, field

NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
MODES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "phrygian dominant": (0, 1, 4, 5, 7, 8, 10),
}


@dataclass(frozen=True)
class Chord:
    """A chord of a key: the scale steps of its notes, and any of them bent out of the scale
    (the raised third that makes the dominant of a minor key pull home)."""
    root: int                                  # scale step of its root, 0 to 6
    steps: tuple[int, ...]                     # scale steps of its notes, the root first
    bent: tuple[tuple[int, int], ...] = ()     # (scale step, semitones) for notes moved out of the scale

    def bend(self, step: int) -> int:
        for which, by in self.bent:
            if which % 7 == step % 7:
                return by
        return 0


@dataclass(frozen=True)
class Key:
    tonic: int                                 # 0 is C
    mode: str

    @property
    def scale(self) -> tuple[int, ...]:
        return MODES[self.mode]

    @property
    def name(self) -> str:
        return "%s %s" % (NAMES[self.tonic % 12], self.mode)

    def lifted(self, semitones: int) -> "Key":
        return Key((self.tonic + semitones) % 12, self.mode)

    def home(self, near: int) -> int:
        """The key note nearest to a pitch."""
        low = near - (near - self.tonic) % 12
        return low if near - low <= 6 else low + 12

    def pitch(self, step: int, near: int = 60, chord: Chord | None = None) -> int:
        """The pitch of a scale step, counted from the key note nearest `near`. Under a chord
        that bends a note of the scale, the tune bends it too."""
        octave, within = divmod(step, 7)
        pitch = self.home(near) + 12 * octave + self.scale[within]
        return pitch + (chord.bend(within) if chord is not None else 0)

    def chord(self, symbol: str) -> Chord:
        """A chord from its figure: "1" to "7" for the chord on that step of the scale, with
        "+" for its third raised a semitone (the dominant of a minor key is "5+"), "-" for it
        lowered, "7" after the step for a seventh on top ("57+"), "s" for a fourth in place
        of the third, and "o" for the bare fifth with no third at all."""
        root = int(symbol[0]) - 1
        steps = [root, root + 2, root + 4]
        rest = symbol[1:]
        if "7" in rest:
            steps.append(root + 6)
        if "s" in rest:
            steps[1] = root + 3
        if "o" in rest:
            del steps[1]
        bent = []
        if "+" in rest or "-" in rest:
            third = self.scale[(root + 2) % 7] - self.scale[root % 7]
            third %= 12
            want = 4 if "+" in rest else 3
            if third != want:
                bent.append(((root + 2) % 7, want - third))
        return Chord(root, tuple(steps), tuple(bent))


def tones(key: Key, chord: Chord, low: int, high: int) -> list[int]:
    """Every pitch of a chord between two pitches."""
    found = []
    for step in chord.steps:
        pitch = key.pitch(step % 7, 60, chord)
        pitch -= 12 * ((pitch - low) // 12)
        while pitch <= high:
            if pitch >= low:
                found.append(pitch)
            pitch += 12
    return sorted(set(found))


def voiced(key: Key, chord: Chord, before: list[int] | None, voices: int, centre: int) -> list[int]:
    """A chord laid out for so many players. The first time, close together about `centre`;
    after that each player moves to the nearest note of the new chord, so the parts sing
    instead of jumping about, and no note of the chord is left out while two players share
    another."""
    span = tones(key, chord, centre - 14, centre + 14)
    if not before:
        start = min(span, key=lambda pitch: abs(pitch - (centre - 5)))
        above = [pitch for pitch in span if pitch >= start][:voices]
        while len(above) < voices:
            above.append(above[-1] + 12 if len(above) < 2 else above[len(above) - 2] + 12)
        return sorted(above)
    chosen: list[int] = []
    for was in before:
        ranked = sorted(span, key=lambda pitch: (abs(pitch - was) + (3 if pitch in chosen else 0), pitch))
        chosen.append(ranked[0])
    # A note of the chord nobody took: whoever doubles another's note takes it, if it is near.
    classes = {pitch % 12 for pitch in chosen}
    for pitch in span:
        if pitch % 12 not in classes:
            doubled = [index for index, mine in enumerate(chosen) if sum(1 for other in chosen if other % 12 == mine % 12) > 1]
            if doubled:
                nearest = min(doubled, key=lambda index: abs(chosen[index] - pitch))
                if abs(chosen[nearest] - pitch) <= 5:
                    chosen[nearest] = pitch
                    classes = {mine % 12 for mine in chosen}
    return sorted(chosen)


@dataclass
class Line:
    """A tune or any single line, in scale steps: (start in beats, length in beats, step, weight).
    `weight` is how much the note matters, 0 to 1: the writer's dynamics, before any player's."""
    notes: list[tuple[float, float, int, float]] = field(default_factory=list)

    def moved(self, beats: float = 0.0, steps: int = 0) -> "Line":
        return Line([(start + beats, length, step + steps, weight) for start, length, step, weight in self.notes])

    def cut(self, first: float, last: float) -> "Line":
        """The part of the line between two moments, counted from the first."""
        return Line([(start - first, min(length, last - start), step, weight)
                     for start, length, step, weight in self.notes if first <= start < last])

    @property
    def top(self) -> int:
        return max(step for _, _, step, _ in self.notes)

    @property
    def bottom(self) -> int:
        return min(step for _, _, step, _ in self.notes)
