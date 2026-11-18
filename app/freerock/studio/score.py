"""Notes on paper: what a part plays, and a track's whole music sheet.

A part is a list of notes, of moves of the expression pedal and of effect marks, in beats.
Nothing here knows anything about music; it only writes down what the writers decide. The
studio's desk finds each voice's real sound by the name of its instrument (sounds.py).

A track's sheet (`Sheet`) is its music written down whole: its form, every part and its
history (2026-11-18: "the music sheet should be a separate concept and asset for every track,
and updating it should be the golden rule, you are a musician were working on music.... the rest
is plumbing"). The writers make a sheet's first draft; the studio performs a sheet; a track is
made better by revising its sheet, with what was changed and why written into its history.
"""
from __future__ import annotations

import datetime
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SHEET = 1                      # how a sheet is written down (`Sheet.save`); a sheet of another is read by `Sheet.load` or refused


@dataclass
class Note:
    start: float               # in beats from the beginning of the track
    length: float              # in beats
    pitch: int                 # MIDI: 60 is middle C
    loud: float = 0.7          # 0 to 1


# What an effect mark moves (Voice.effects), and what its values are. The desk plays them on the part's own track
# (studio/jsfx/pedals and studio/jsfx/sweep), the marks drawn as the effect's envelope, so they move with the music
# (2026-11-18: "the music itself should denote the effects it shouldnt be standard").
EFFECTS = {
    "wah": "the wah pedal: 0 out, 1 all the way in",
    "wah depth": "how far the wah is rocked: 0 holds it where it stands, 1 rocks it from heel to toe",
    "wah position": "where a held wah stands: 0 the heel, 1 the toe",
    "phaser": "the phaser: 0 out, 1 all the way in",
    "flanger": "the flanger: 0 out, 1 all the way in",
    "flanger depth": "how far the flanger sweeps itself: 1 in time with the song, 0 only where it is swept by hand",
    "flanger position": "where a flanger swept by hand stands: 0 its shortest delay, 1 its longest",
    "echo": "the tape echo's send: 0 none, 1 thrown all the way up (a phrase's last note)",
    "lowpass": "the low-pass filter, in Hz (20000 is open)",
    "highpass": "the high-pass filter, in Hz (20 is open)",
}
# ...and how each is set where it does not move (Voice.settings).
SETTINGS = {
    "wah beats": "beats from one rock of the wah to the next, toe down on the beat",
    "phaser bars": "bars one sweep of the phaser takes",
    "phaser feedback": "0 to 0.9",
    "flanger bars": "bars one sweep of the flanger takes, down and back",
    "flanger feedback": "0 to 0.95",
    "echo beats": "beats the echo's left repeat comes after (the right one a beat after)",
    "echo feedback": "how much of each repeat comes round again, 0 to 0.9",
    "lowpass resonance": "0 to 1",
    "highpass resonance": "0 to 1",
}


@dataclass
class Voice:
    """One instrument's line, or a drum kit's (each of its strokes written on a note of its own)."""
    notes: list[Note] = field(default_factory=list)
    drums: bool = False
    swells: list[tuple[float, float]] = field(default_factory=list)      # (beat, 0..1): the expression pedal
    pan: float = 0.0           # -1 left to 1 right
    shift: float = 0.0         # seconds: an instrument that speaks late is played a little early
    instrument: str = ""       # what it is called ("celli", "kit rock"): the studio's desk finds its real sound by this
    effects: dict[str, list[tuple[float, float]]] = field(default_factory=dict)     # what moves (EFFECTS): (beat, value)
    settings: dict[str, float] = field(default_factory=dict)                        # ...and what is set and stays (SETTINGS)

    def add(self, start: float, length: float, pitch: int, loud: float = 0.7) -> None:
        if length > 0 and 0 <= pitch <= 127:
            self.notes.append(Note(start, length, int(pitch), min(max(loud, 0.02), 1.0)))

    def mark(self, effect: str, points: list[tuple[float, float]]) -> None:
        """Effect marks for this part: `points` ((beat, value)) joined to what is marked for that effect already."""
        if effect not in EFFECTS:
            raise ValueError("No such effect mark: %r (there are %s)" % (effect, ", ".join(EFFECTS)))
        self.effects[effect] = sorted(self.effects.get(effect, []) + [(float(at), float(value)) for at, value in points])

    def set(self, setting: str, value: float) -> None:
        if setting not in SETTINGS:
            raise ValueError("No such effect setting: %r (there are %s)" % (setting, ", ".join(SETTINGS)))
        self.settings[setting] = float(value)


def humanise(voice: Voice, rng: random.Random, timing: float = 0.012, loud: float = 0.06, bpm: float = 100.0) -> None:
    """Nobody plays like a clock: each note a few milliseconds early or late and a little
    louder or softer. `timing` is in seconds."""
    beats = timing * bpm / 60.0
    for note in voice.notes:
        move = rng.gauss(0.0, beats)
        note.start = max(note.start + move, 0.0)
        note.loud = min(max(note.loud * (1.0 + rng.gauss(0.0, loud)), 0.02), 1.0)


# ---------------------------------------------------------------------------------------------
# The sheet
# ---------------------------------------------------------------------------------------------
@dataclass
class Sheet:
    """A track's music written down whole.

    `form` is the story section by section, in order: what it is ("story": open, theme, rise, moment, close; "part":
    which of them, as the writer names it), its first bar and how many bars, its key and its chords, and how loud it is
    to be from its first bar to its last. `parts` is every part by channel and name. `about` is what the desk needs to
    perform it and the player to choose it (the character, the room, whether it is a band, the kinds of place). `history`
    is every revision, oldest first: what was changed, why, by whom, when."""
    style: str
    family: str
    take: int
    title: str
    tempo: float
    beats: float                                  # beats in a bar
    form: list[dict[str, Any]]
    parts: dict[str, dict[str, Voice]]
    about: dict[str, Any] = field(default_factory=dict)
    airs: list[dict[str, Any]] = field(default_factory=list)       # sounds made of noise and weather (House's risers, wind, rain)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def bars(self) -> int:
        return sum(int(section["bars"]) for section in self.form)

    def revised(self, what: str, why: str, by: str) -> dict[str, Any]:
        """Writes a revision into the history (whoever calls this has changed the sheet): what was changed and why."""
        entry = {"revision": len(self.history) + 1, "when": datetime.datetime.now().isoformat(timespec="seconds"), "by": by,
                 "what": what, "why": why}
        self.history.append(entry)
        return entry

    @property
    def revision(self) -> int:
        return len(self.history)

    # --- on paper -------------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        def voice(part: Voice) -> dict[str, Any]:
            out: dict[str, Any] = {"instrument": part.instrument}
            if part.drums:
                out["drums"] = True
            # Every number exactly as written (a note a hundred-thousandth of a beat off is a MIDI tick off, and another
            # performance by MuseScore): a sheet read back plays as it was written.
            if part.pan:
                out["pan"] = part.pan
            if part.shift:
                out["shift"] = part.shift
            out["notes"] = [[n.start, n.length, n.pitch, n.loud] for n in part.notes]
            if part.swells:
                out["swells"] = [[at, value] for at, value in part.swells]
            if part.effects:
                out["effects"] = {name: [[at, value] for at, value in points] for name, points in part.effects.items()}
            if part.settings:
                out["settings"] = dict(part.settings)
            return out
        return {"sheet": SHEET, "style": self.style, "family": self.family, "take": self.take, "title": self.title,
                "tempo": self.tempo, "beats": self.beats, "form": self.form, "about": self.about,
                "parts": {channel: {name: voice(part) for name, part in parts.items()} for channel, parts in self.parts.items()},
                "airs": self.airs, "history": self.history}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sheet":
        if data.get("sheet") != SHEET:
            raise ValueError("A sheet written down as %r, not %r" % (data.get("sheet"), SHEET))

        def voice(made: dict[str, Any]) -> Voice:
            return Voice(notes=[Note(float(a), float(b), int(c), float(d)) for a, b, c, d in made["notes"]], drums=bool(made.get("drums")),
                         swells=[(float(a), float(b)) for a, b in made.get("swells", [])], pan=float(made.get("pan", 0.0)),
                         shift=float(made.get("shift", 0.0)), instrument=made["instrument"],
                         effects={name: [(float(a), float(b)) for a, b in points] for name, points in made.get("effects", {}).items()},
                         settings={name: float(value) for name, value in made.get("settings", {}).items()})
        return cls(style=data["style"], family=data["family"], take=int(data["take"]), title=data["title"], tempo=float(data["tempo"]),
                   beats=float(data["beats"]), form=list(data["form"]), about=dict(data["about"]),
                   parts={channel: {name: voice(made) for name, made in parts.items()} for channel, parts in data["parts"].items()},
                   airs=list(data.get("airs", [])), history=list(data.get("history", [])))

    def save(self, path: Path) -> None:
        """Writes the sheet down (one line for each part's notes, so a revision reads as a change to a few lines), and
        keeps the revision it replaces beside it (`sheet.r<N>.json`)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            before = json.loads(path.read_text(encoding="utf-8"))
            kept = path.with_name("%s.r%d.json" % (path.stem, len(before.get("history", []))))
            if not kept.exists():
                path.replace(kept)
        data = self.to_dict()
        rows = ["{"]
        heads = [key for key in data if key not in ("parts", "history")]
        for key in heads:
            rows.append(" %s: %s," % (json.dumps(key), json.dumps(data[key], ensure_ascii=False)))
        rows.append(' "parts": {')
        channels = list(data["parts"].items())
        for index, (channel, parts) in enumerate(channels):
            rows.append("  %s: {" % json.dumps(channel))
            named = list(parts.items())
            for inner, (name, made) in enumerate(named):
                rows.append("   %s: %s%s" % (json.dumps(name, ensure_ascii=False), json.dumps(made, ensure_ascii=False),
                                             "," if inner < len(named) - 1 else ""))
            rows.append("  }%s" % ("," if index < len(channels) - 1 else ""))
        rows.append(" },")
        rows.append(' "history": %s' % json.dumps(data["history"], indent=2, ensure_ascii=False).replace("\n", "\n "))
        rows.append("}")
        scratch = path.with_name(path.name + ".new")
        scratch.write_text("\n".join(rows) + "\n", encoding="utf-8")
        scratch.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Sheet":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
