"""Real scores: orchestral works in the public domain, played by the studio's instruments.

The writers in this package make music up. This module does not: it takes scores that already
exist (Beethoven's symphonies, Brahms's, an overture or two), each as data that someone has
published under terms that allow it, and has the studio's sampled orchestra play them. The
orchestra is split into the five channels by family, each family is played alone, and the whole
is staged as tracks of about three minutes, cut where the music itself draws breath and laid
out as a story by how loud it is: where it is quiet, where it climbs, where it comes to its
moment, where it falls away.

Where the scores come from (each track's `credit` says which, and under what terms):

  OpenScore Orchestra   full scores as MusicXML, "Scores: CC0 1.0 Universal"
                        github.com/MarkGotham/Hauptstimme (data/<composer>/<work>/<movement>/*.mxl)
  Mutopia Project       MIDI files, each with its own licence: Public Domain, or Creative
                        Commons Attribution-ShareAlike 3.0
  pd-score-corpus       MIDI files whose uploaders declared them CC0 or public domain
  Wikimedia Commons     one MIDI file, free to use with attribution

Every work here was written by a composer who died before 1945 and was published before 1929.
Nothing is taken from a recording.

    uv run --no-sync python -I -m freerock.studio.scores fetch      fetches the scores into var/scores
    uv run --no-sync python -I -m freerock.studio.scores stage      plays and stages every work in the table
    uv run --no-sync python -I -m freerock.studio.scores stage beethoven-7-2 tell
    uv run --no-sync python -I -m freerock.studio.scores report     what is staged, counted

What is fetched is data from elsewhere: each file is kept in a folder of its own under
var/scores and is only ever read, never run.
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import analysis, forever, kinds
from . import fluid, room, score, write_track

RATE = forever.RATE
APP = Path(__file__).resolve().parents[2]
VAR = APP.parent / "var"
STYLE = "warcraft"
POST_S = 6.0                   # how long each recording rings on after the last note
AGENT = "FreeRockStudio/1.0 (music for personal listening; generic client)"
OPENSCORE = "https://raw.githubusercontent.com/MarkGotham/Hauptstimme/main/data/"
OPENSCORE_TERMS = "Score: OpenScore Orchestra, CC0 1.0 Universal (github.com/MarkGotham/Hauptstimme)"
PLAYED_BY = "Played by FluidSynth on the MuseScore General SoundFont (MIT licence)."

CHANNELS = forever.CHANNELS
# The least each channel is played at, whatever the game is doing: a real score is always whole,
# and the game only adds weight to it.
FLOOR = {"texture": 1.0, "lead": 1.0, "bass": 0.9, "rhythm": 0.8, "drums": 0.7}


# ---------------------------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------------------------
def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError("%s answered %d" % (url, response.status))
        return response.read()


def fetch_one(url: str, folder: Path, name: str) -> Path:
    """One file into a folder of its own. A file that is already there is left as it is."""
    path = folder / name
    if path.is_file() and path.stat().st_size > 0:
        return path
    folder.mkdir(parents=True, exist_ok=True)
    data = _get(url)
    scratch = folder / (name + ".part")
    scratch.write_bytes(data)
    scratch.replace(path)
    return path


# ---------------------------------------------------------------------------------------------
# What a score is, once read: who plays which notes, and when, in seconds
# ---------------------------------------------------------------------------------------------
@dataclass
class Tone:
    start: float               # seconds
    length: float              # seconds
    pitch: int                 # MIDI number, sounding
    loud: float                # 0 to 1
    way: str = ""              # "pizz" plucked, "trem" bowed tremolo; otherwise as the instrument usually sounds


@dataclass
class Player:
    """One line of the score: an instrument, and everything it plays."""
    name: str
    sound: str                 # what it is, in MusicXML's words where known: "strings.violin", "brass.trumpet"
    program: int               # General MIDI, 0 to 127
    drums: bool = False
    tones: list[Tone] = field(default_factory=list)
    swells: list[tuple[float, float]] = field(default_factory=list)      # (seconds, 0..1): the swell within held notes


@dataclass
class Reading:
    """A whole score as read."""
    players: list[Player]
    seconds: float
    tempo: float               # quarter notes a minute at the beginning
    notes: list[str] = field(default_factory=list)       # what was left out or guessed, for the record


# ---------------------------------------------------------------------------------------------
# Reading a MIDI file
# ---------------------------------------------------------------------------------------------
def _varlen(data: bytes, at: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[at]
        at += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, at


def read_midi(data: bytes) -> Reading:
    """A Standard MIDI File as players and their notes in seconds. Each track's notes on each
    channel are one player; its name is the track's, its instrument the last program set on that
    channel before its first note. Channel volume and expression scale how loud its notes are."""
    if data[:4] != b"MThd":
        raise ValueError("Not a MIDI file")
    length, kind, count, division = struct.unpack(">IHHH", data[4:14])
    if division & 0x8000:
        raise ValueError("A MIDI file timed in frames a second is not read here")
    at = 8 + length
    tempos: list[tuple[int, float]] = []                    # (tick, seconds per quarter)
    raw: list[dict[str, Any]] = []
    for _ in range(count):
        if data[at:at + 4] != b"MTrk":
            raise ValueError("The MIDI file's tracks are not where they should be")
        size = struct.unpack(">I", data[at + 4:at + 8])[0]
        body, at = data[at + 8:at + 8 + size], at + 8 + size
        tick, pos, status = 0, 0, 0
        name = ""
        events: list[tuple[int, int, int, int, int]] = []    # (tick, kind, channel, a, b)
        while pos < len(body):
            delta, pos = _varlen(body, pos)
            tick += delta
            byte = body[pos]
            if byte == 0xFF:
                meta = body[pos + 1]
                size, pos = _varlen(body, pos + 2)
                payload = body[pos:pos + size]
                pos += size
                if meta == 0x51 and size == 3:
                    tempos.append((tick, int.from_bytes(payload, "big") / 1e6))
                elif meta == 0x03 and not name:
                    name = payload.decode("utf-8", "replace").strip("\x00 \t\r\n")
                elif meta == 0x04 and not name:
                    name = payload.decode("utf-8", "replace").strip("\x00 \t\r\n")
                continue
            if byte in (0xF0, 0xF7):
                size, pos = _varlen(body, pos + 1)
                pos += size
                continue
            if byte & 0x80:
                status = byte
                pos += 1
            high, channel = status & 0xF0, status & 0x0F
            if high in (0xC0, 0xD0):
                a, b = body[pos], 0
                pos += 1
            else:
                a, b = body[pos], body[pos + 1]
                pos += 2
            events.append((tick, high, channel, a, b))
        raw.append({"name": name, "events": events})
    tempos.sort()
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, 0.5))

    # Seconds at each change of tempo, then any tick's seconds from the change before it.
    marks, total = [], 0.0
    for index, (tick, spq) in enumerate(tempos):
        if index:
            total += (tick - tempos[index - 1][0]) * tempos[index - 1][1] / division
        marks.append((tick, total, spq))

    def seconds(tick: int) -> float:
        low, high = 0, len(marks) - 1
        while low < high:
            middle = (low + high + 1) // 2
            if marks[middle][0] <= tick:
                low = middle
            else:
                high = middle - 1
        first, base, spq = marks[low]
        return base + (tick - first) * spq / division

    players: dict[tuple[int, int], Player] = {}
    end = 0.0
    for index, track in enumerate(raw):
        program: dict[int, int] = {}
        volume: dict[int, float] = {}
        swell: dict[int, float] = {}
        sounding: dict[tuple[int, int], tuple[int, int]] = {}      # (channel, pitch) -> (tick, velocity)
        for tick, high, channel, a, b in track["events"]:
            if high == 0xC0:
                program[channel] = a
            elif high == 0xB0 and a == 7:
                volume[channel] = b / 127.0
            elif high == 0xB0 and a == 11:
                swell[channel] = b / 127.0
            elif high == 0x90 and b > 0:
                if (channel, a) in sounding:
                    continue                                 # struck again while held: the first holds
                key = (index, channel)
                if key not in players:
                    players[key] = Player(name=track["name"] or "track %d" % (index + 1), sound="",
                                          program=program.get(channel, 0), drums=channel == 9)
                # How loud: the key's own velocity, turned down by where the channel's volume
                # and expression stand (most files leave both alone).
                level = b / 127.0 * (0.4 + 0.6 * volume.get(channel, 1.0)) * (0.4 + 0.6 * swell.get(channel, 1.0))
                sounding[(channel, a)] = (tick, max(int(round(level * 127)), 1))
            elif high == 0x80 or (high == 0x90 and b == 0):
                began = sounding.pop((channel, a), None)
                if began is None:
                    continue
                first, last = seconds(began[0]), seconds(tick)
                players[(index, channel)].tones.append(Tone(first, max(last - first, 0.02), a, began[1] / 127.0))
                end = max(end, last)
    found = [player for _, player in sorted(players.items()) if player.tones]
    return Reading(players=found, seconds=end, tempo=60.0 / tempos[0][1])


# ---------------------------------------------------------------------------------------------
# Reading a MusicXML score
# ---------------------------------------------------------------------------------------------
# How loud each dynamic mark is, as a key velocity out of 127 (MusicXML's own table).
MARKS = {"pppp": 10, "ppp": 16, "pp": 33, "p": 49, "mp": 64, "mf": 80, "f": 96, "ff": 112, "fff": 126, "ffff": 127}
# Marks that are about one note, not about how loud the music is from here on.
ACCENTS = ("sf", "sfz", "sffz", "fz", "rf", "rfz", "sfp", "sfpp", "fp")
FERMATA = 1.8                  # a note under a fermata is held this many times its length
STEP = 0.14                    # one degree of loudness (p to mp, f to ff), for a cresc. that names no goal
ROLL_S = 0.072                 # a drum roll is a stroke this often
TRILL_S = 0.085                # and a trill a note this often


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass
class _Written:
    """A note as written, in quarter notes from the start of what is played."""
    start: float
    length: float
    pitch: int
    way: str = ""
    short: float = 1.0         # how much of its length it sounds for, where it is marked short
    joined: bool = False       # under a slur: it runs into the next note
    accent: float = 1.0
    roll: bool = False
    trill: int = 0             # semitones to the note it trills with
    open: bool = False         # tied on to a note still to come


def _plan(part: ET.Element) -> tuple[list[int], list[str]]:
    """Which bars of a part are played, in order: every bar once, as written, except the bars of
    a first ending, which are left out for the ending that follows. Repeats are not taken and
    a da capo is not gone back for: the music is wanted once."""
    measures = part.findall("measure")
    blocks, begun = [], None
    said: list[str] = []
    for index, measure in enumerate(measures):
        for barline in measure.findall("barline"):
            ending = barline.find("ending")
            if ending is not None:
                if ending.get("type") == "start":
                    begun = index
                elif begun is not None:
                    blocks.append((begun, index))
                    begun = None
            if barline.find("repeat") is not None and "repeats are not taken" not in said:
                said.append("repeats are not taken")
        for sound in measure.iter("sound"):
            if any(sound.get(name) for name in ("dacapo", "dalsegno", "tocoda")) and "a da capo is not gone back for" not in said:
                said.append("a da capo is not gone back for")
    skip: set[int] = set()
    for (first, last), following in zip(blocks, blocks[1:]):
        if following[0] == last + 1:                      # another ending follows at once: this one is not the last
            skip.update(range(first, last + 1))
    if skip:
        said.append("first endings are left out")
    return [index for index in range(len(measures)) if index not in skip], said


def read_musicxml(data: bytes, retempo: dict[float, float] | None = None,
                  tempo_marks: list[tuple[str, float]] | None = None) -> Reading:
    """A MusicXML score (score-partwise, as MuseScore writes it) as players and their notes in
    seconds: transposing instruments at the pitch they sound, ties joined, dynamics as how
    hard each note is played, hairpins and cresc. as a climb to the next mark, pizzicato and
    tremolo as other ways of playing, fermatas held, tempo changes kept.

    A score's tempo marks are sometimes wrong by a factor of two (a half note taken for a
    quarter) or missing. `retempo` puts a marked tempo right wherever it stands ({160: 320});
    `tempo_marks` replaces every mark in the score with these: (the bar's number, quarter
    notes a minute)."""
    root = ET.fromstring(data)
    if _local(root.tag) != "score-partwise":
        raise ValueError("Only score-partwise MusicXML is read here, not %s" % _local(root.tag))
    listed = {}
    for item in root.find("part-list").iter("score-part"):
        unpitched = {}
        for instrument in item.findall("midi-instrument"):
            if instrument.findtext("midi-unpitched"):
                unpitched[instrument.get("id")] = int(instrument.findtext("midi-unpitched")) - 1
        program = item.findtext("midi-instrument/midi-program")
        listed[item.get("id")] = {
            "name": " ".join((item.findtext("part-name") or item.get("id")).split()),
            "sound": item.findtext("score-instrument/instrument-sound") or "",
            "program": int(program) - 1 if program else 0, "unpitched": unpitched}
    parts = root.findall("part")
    if not parts:
        raise ValueError("The score has no parts")
    order, said = _plan(parts[0])

    # How long each bar is, in quarter notes: as far as any part gets in it.
    lengths = [0.0] * len(parts[0].findall("measure"))
    for part in parts:
        divisions = 1
        for index, measure in enumerate(part.findall("measure")):
            at = reach = 0
            for item in measure:
                tag = item.tag
                if tag == "attributes" and item.findtext("divisions"):
                    divisions = int(item.findtext("divisions"))
                elif tag == "note":
                    if item.find("grace") is not None or item.find("chord") is not None:
                        continue
                    at += int(item.findtext("duration") or 0)
                elif tag == "backup":
                    at -= int(item.findtext("duration"))
                elif tag == "forward":
                    at += int(item.findtext("duration"))
                reach = max(reach, at)
            if index < len(lengths):
                lengths[index] = max(lengths[index], reach / divisions)
    begins, total = {}, 0.0
    numbered: dict[str, float] = {}
    for index in order:
        begins[index] = total
        numbered.setdefault(parts[0].findall("measure")[index].get("number", ""), total)
        total += lengths[index]

    tempos: list[tuple[float, float]] = []
    holds: list[tuple[float, float]] = []
    concert_key: list[tuple[float, int]] = []
    readings: list[tuple[dict, list[_Written], list[tuple[float, float]]]] = []
    for part in parts:
        about = listed.get(part.get("id"), {"name": part.get("id"), "sound": "", "program": 0, "unpitched": {}})
        strings = about["sound"].startswith("strings.")
        kettle = "timpani" in about["sound"] or "timpani" in about["name"].lower()
        divisions, transpose, way, slurs = 1, 0, "", 0
        notes: list[_Written] = []
        tied: dict[int, _Written] = {}
        marks: list[tuple[float, float]] = []             # (quarter, level 0..1): how loud from here on
        ramps: list[tuple[float, float | None, int]] = []  # (from, to or None, up or down)
        accents: list[float] = []
        wedge: dict[str, tuple[float, int]] = {}
        measures = part.findall("measure")
        last_start = 0.0
        for index in order:
            if index >= len(measures):
                break
            base, at = begins[index], 0.0
            for item in measures[index]:
                tag = item.tag
                if tag == "attributes":
                    if item.findtext("divisions"):
                        divisions = int(item.findtext("divisions"))
                    moved = item.find("transpose")
                    if moved is not None:
                        transpose = int(float(moved.findtext("chromatic") or 0)) + 12 * int(moved.findtext("octave-change") or 0)
                    if item.findtext("key/fifths") is not None and transpose % 12 == 0:
                        concert_key.append((base + at, int(item.findtext("key/fifths"))))
                elif tag == "backup":
                    at -= int(item.findtext("duration")) / divisions
                elif tag == "forward":
                    at += int(item.findtext("duration")) / divisions
                elif tag == "direction":
                    here = base + at + int(item.findtext("offset") or 0) / divisions
                    sound = item.find("sound")
                    if sound is not None and sound.get("tempo"):
                        tempos.append((max(here, 0.0), float(sound.get("tempo"))))
                    if sound is not None and sound.get("pizzicato") and strings:
                        way = "pizz" if sound.get("pizzicato") == "yes" else ""
                    for kind in item.findall("direction-type"):
                        dynamics = kind.find("dynamics")
                        if dynamics is not None and len(dynamics):
                            name = _local(dynamics[0].tag)
                            if name in ACCENTS:
                                accents.append(here)
                                if name in ("fp", "sfp", "sfpp"):
                                    marks.append((here + 0.01, MARKS["pp" if name == "sfpp" else "p"] / 127.0))
                            elif name in MARKS:
                                level = MARKS[name] / 127.0
                                if sound is not None and sound.get("dynamics"):
                                    level = min(float(sound.get("dynamics")) * 0.9 / 127.0, 1.0)
                                marks.append((here, level))
                        for words in kind.findall("words"):
                            text = (words.text or "").strip().lower()
                            if strings and text.startswith("pizz"):
                                way = "pizz"
                            elif strings and text.startswith("arco"):
                                way = ""
                            elif text.startswith("cresc"):
                                ramps.append((here, None, 1))
                            elif text.startswith(("dim", "decresc", "calando", "morendo", "smorz", "perdendo")):
                                ramps.append((here, None, -1))
                        mark = kind.find("wedge")
                        if mark is not None:
                            number = mark.get("number", "1")
                            if mark.get("type") in ("crescendo", "diminuendo"):
                                wedge[number] = (here, 1 if mark.get("type") == "crescendo" else -1)
                            elif mark.get("type") == "stop" and number in wedge:
                                began, way_up = wedge.pop(number)
                                ramps.append((began, here, way_up))
                elif tag == "note":
                    if item.find("grace") is not None or item.find("cue") is not None:
                        continue
                    length = int(item.findtext("duration") or 0) / divisions
                    if item.find("chord") is not None:
                        start = last_start
                    else:
                        start = base + at
                        last_start = start
                        at += length
                    notations = item.find("notations")
                    if notations is not None and notations.find("fermata") is not None:
                        holds.append((start, start + length))
                    if notations is not None:
                        for slur in notations.findall("slur"):
                            slurs += 1 if slur.get("type") == "start" else -1 if slur.get("type") == "stop" else 0
                        slurs = max(slurs, 0)
                    if item.find("rest") is not None or length <= 0:
                        continue
                    pitch = item.find("pitch")
                    if pitch is not None:
                        number = (12 * (int(pitch.findtext("octave")) + 1) + {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[pitch.findtext("step")]
                                  + int(round(float(pitch.findtext("alter") or 0))) + transpose)
                    else:
                        which = item.find("instrument")
                        number = about["unpitched"].get(which.get("id") if which is not None else "", -1)
                        if number < 0:
                            continue
                    stops = any(tie.get("type") == "stop" for tie in item.findall("tie"))
                    starts = any(tie.get("type") == "start" for tie in item.findall("tie"))
                    if stops and number in tied:
                        held = tied[number]
                        held.length = start + length - held.start
                        held.open = starts
                        if not starts:
                            del tied[number]
                        continue
                    if way == "pizz" and (slurs or starts or length >= 3.0):
                        # Nobody plucks a slur or a long held note: the score has gone back to
                        # the bow without saying so (some of these scores leave "arco" out).
                        way = ""
                    note = _Written(start, length, number, way=way, open=starts)
                    note.joined = slurs > 0
                    if notations is not None:
                        for group in notations.findall("articulations"):
                            names = {_local(each.tag) for each in group}
                            if "staccatissimo" in names:
                                note.short = 0.3
                            elif "staccato" in names or "spiccato" in names:
                                note.short = 0.5
                            elif "detached-legato" in names:
                                note.short = 0.75
                            elif "tenuto" in names:
                                note.joined = True
                            if "strong-accent" in names:
                                note.accent = 1.3
                            elif "accent" in names:
                                note.accent = 1.18
                        if notations.find("dynamics") is not None:
                            note.accent = max(note.accent, 1.25)
                        for group in notations.findall("ornaments"):
                            shake = group.find("tremolo")
                            if shake is not None and shake.get("type", "single") == "single":
                                strokes = int(shake.text or 3)
                                if kettle or not about["sound"].startswith(("strings.", "wind.", "brass.", "voice.")):
                                    note.roll = True
                                elif strings and strokes >= 3 and not way:
                                    note.way = "trem"
                                elif strings and not way:
                                    note.roll = True               # a measured tremolo: bowed again and again
                                    note.trill = -strokes          # (how fast is worked out from the tempo)
                            if group.find("trill-mark") is not None:
                                if kettle or pitch is None:
                                    note.roll = True
                                else:
                                    note.trill = 2
                    if starts:
                        tied[number] = note
                    notes.append(note)
        # How loud the part is at every moment: the marks, and the climbs and falls between them.
        marks.sort()
        readings.append((about, notes, _loudness_line(marks, ramps, total), accents))
    if tempo_marks is not None:
        missing = [bar for bar, _ in tempo_marks if bar not in numbered]
        if missing:
            raise ValueError("The score has no bar numbered %s to set a tempo at" % ", ".join(missing))
        tempos = [(numbered[bar], pace) for bar, pace in tempo_marks]
    elif retempo:
        tempos = [(at, next((right for wrong, right in retempo.items() if abs(pace - wrong) < 0.6), pace)) for at, pace in tempos]
    if not tempos:
        tempos = [(0.0, 96.0)]
        said.append("no tempo is marked: 96 to the minute is assumed")
    tempos.sort()
    if tempos[0][0] > 0:
        tempos.insert(0, (0.0, tempos[0][1]))
    clock = _Clock(tempos, holds)
    concert_key.sort()
    players = []
    for about, notes, line, accents in readings:
        if not notes:
            continue
        drums = bool(about["unpitched"]) and not any(note.pitch > 0 and not about["unpitched"] for note in notes)
        player = Player(name=about["name"], sound=about["sound"], program=about["program"], drums=drums)
        accents.sort()
        for note in notes:
            level = _level_at(line, note.start) * note.accent
            if any(abs(note.start - mark) < 0.26 for mark in accents[_first_at(accents, note.start - 0.26):_first_at(accents, note.start + 0.27)]):
                level = max(level * 1.25, 0.72)
            level = min(max(level, 0.06), 1.0)
            first, last = clock.seconds(note.start), clock.seconds(note.start + note.length)
            if note.short < 1.0:
                last = first + (last - first) * note.short
            elif not note.joined:
                # Not slurred: a breath, or a change of bow, before the next note. A twentieth
                # of a second, less for a note too short to spare it; never a share of the
                # note's length, which would leave a hole after every long one.
                last = max(last - 0.05, first + 0.75 * (last - first))
            if note.roll:
                # A roll, or a bowed tremolo that is counted: one stroke after another.
                each = ROLL_S
                if note.trill < 0:
                    each = max((clock.seconds(note.start + 1.0) - first) / (2 ** -note.trill), 0.05)
                count = max(int(round((clock.seconds(note.start + note.length) - first) / each)), 1)
                span = (clock.seconds(note.start + note.length) - first) / count
                for stroke in range(count):
                    player.tones.append(Tone(first + stroke * span, span * (0.95 if note.trill < 0 else 1.6), note.pitch,
                                             level * (0.93 if stroke % 2 else 1.0), note.way))
            elif note.trill > 0 and last - first > 2.5 * TRILL_S:
                upper = note.pitch + _step_above(note.pitch, concert_key, note.start)
                count = max(int((last - first) / TRILL_S), 2)
                span = (last - first) / count
                for stroke in range(count):
                    player.tones.append(Tone(first + stroke * span, span * 1.05, upper if stroke % 2 else note.pitch, level * 0.9, note.way))
            else:
                player.tones.append(Tone(first, max(last - first, 0.03), note.pitch, level, note.way))
        # The swell inside held notes: where the part's loudness moves while a note is sounding.
        player.swells = [(clock.seconds(quarter), level) for quarter, level in line]
        players.append(player)
    return Reading(players=players, seconds=clock.seconds(total), tempo=tempos[0][1], notes=said)


def _first_at(sorted_values: list[float], value: float) -> int:
    low, high = 0, len(sorted_values)
    while low < high:
        middle = (low + high) // 2
        if sorted_values[middle] < value:
            low = middle + 1
        else:
            high = middle
    return low


def _step_above(pitch: int, keys: list[tuple[float, int]], when: float) -> int:
    """How far above a note the next note of the key is: one semitone or two."""
    fifths = 0
    for at, value in keys:
        if at <= when + 1e-6:
            fifths = value
    tonic = (fifths * 7) % 12
    scale = {(tonic + step) % 12 for step in (0, 2, 4, 5, 7, 9, 11)}
    return 2 if (pitch + 2) % 12 in scale or (pitch + 1) % 12 not in scale else 1


def _loudness_line(marks: list[tuple[float, float]], ramps: list[tuple[float, float | None, int]], end: float
                   ) -> list[tuple[float, float]]:
    """A part's loudness through the piece as points to draw straight lines between: level
    between marks, a sudden change at a mark, and for a hairpin or a cresc. a climb (or a fall)
    from where it begins to the mark it leads to, or by one degree where it leads to none."""
    points: list[tuple[float, float]] = [(0.0, marks[0][1] if marks and marks[0][0] <= 0.01 else MARKS["mf"] / 127.0)]
    events = sorted([(at, 0, level, None) for at, level in marks if at > 0.01]
                    + [(at, 1, float(way), until) for at, until, way in ramps], key=lambda event: (event[0], event[1]))
    climbing: tuple[float, float, float | None, float] | None = None    # (from when, from level, until, way)

    def settle(at: float, target: float | None) -> None:
        nonlocal climbing
        began, level, until, way = climbing
        stop = min(until if until is not None else at, at)
        if target is not None and (target - level) * way > 0 and (until is None or at - until < 2.01):
            goal = target                                   # it leads to the mark that follows
        else:
            goal = min(max(level + way * STEP, 10 / 127.0), 1.0)
        if until is None and target is None:
            stop = min(began + 16.0, at)                    # a cresc. that leads nowhere is over in four bars
        if stop > began:
            points.append((began, level))
            points.append((stop, goal))
        climbing = None

    for at, kind, value, until in events:
        now = points[-1][1]
        if kind == 0:
            if climbing is not None:
                settle(at, value)
                now = points[-1][1]
            if abs(value - now) > 1e-6:
                points.append((max(at - 0.001, points[-1][0]), now))
                points.append((at, value))
        else:
            if climbing is not None:
                settle(at, None)
                now = points[-1][1]
            climbing = (at, now, until, value)
    if climbing is not None:
        settle(end, None)
    points.append((max(end, points[-1][0]) + 1.0, points[-1][1]))
    return points


def _level_at(line: list[tuple[float, float]], when: float) -> float:
    low, high = 0, len(line) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if line[middle][0] <= when:
            low = middle
        else:
            high = middle - 1
    if low + 1 >= len(line):
        return line[-1][1]
    (a, first), (b, second) = line[low], line[low + 1]
    if when <= a or b <= a:
        return first
    return first + (second - first) * (when - a) / (b - a)


class _Clock:
    """Quarter notes to seconds, through every change of tempo and every fermata."""

    def __init__(self, tempos: list[tuple[float, float]], holds: list[tuple[float, float]]):
        merged: list[list[float]] = []
        for first, last in sorted(holds):
            if merged and first <= merged[-1][1] + 1e-6:
                merged[-1][1] = max(merged[-1][1], last)
            else:
                merged.append([first, last])
        edges = sorted({at for at, _ in tempos} | {edge for hold in merged for edge in hold} | {0.0})
        self.marks: list[tuple[float, float, float]] = []       # (quarter, seconds, seconds per quarter)
        total = 0.0
        for index, edge in enumerate(edges):
            if index:
                total += (edge - edges[index - 1]) * self.marks[-1][2]
            pace = 60.0 / [tempo for at, tempo in tempos if at <= edge + 1e-9][-1]
            if any(first <= edge + 1e-9 < last for first, last in merged):
                pace *= FERMATA
            self.marks.append((edge, total, pace))

    def seconds(self, quarter: float) -> float:
        low, high = 0, len(self.marks) - 1
        while low < high:
            middle = (low + high + 1) // 2
            if self.marks[middle][0] <= quarter:
                low = middle
            else:
                high = middle - 1
        at, base, pace = self.marks[low]
        return base + (quarter - at) * pace


def off_pitch(reading: Reading) -> list[str]:
    """Players whose notes do not agree with the strings: a transposing instrument read at the
    wrong pitch, or a part entered in the wrong octave of the wrong key. Nobody can listen to
    every score, so each one is held against this: at the moment a player sounds a note, how
    often some string player is sounding that note too (in any octave), and whether the
    player would agree with the strings far better moved up or down by some interval. Returns
    a line for each player that would."""
    slot = 0.1
    count = int(reading.seconds / slot) + 2
    held = np.zeros(count, dtype=np.int32)                   # for each tenth of a second: which of the twelve notes the strings hold
    strings = [player for player in reading.players if what(player) in ("violin", "violin 2", "viola", "cello", "contrabass")]
    for player in strings:
        for tone in player.tones:
            first, last = int(tone.start / slot), min(int((tone.start + tone.length) / slot) + 1, count)
            held[first:last] |= 1 << (tone.pitch % 12)
    found = []
    for player in reading.players:
        if player in strings or player.drums or what(player) in ("timpani", "percussion") or len(player.tones) < 40:
            continue
        agree = np.zeros(12)
        heard = 0
        for tone in player.tones:
            near = held[max(int(tone.start / slot) - 1, 0):int((tone.start + min(tone.length, 0.6)) / slot) + 2]
            both = int(np.bitwise_or.reduce(near)) if len(near) else 0
            if not both:
                continue
            heard += 1
            for move in range(12):
                if both >> ((tone.pitch + move) % 12) & 1:
                    agree[move] += 1
        if heard < 40:
            continue
        agree /= heard
        best = int(np.argmax(agree))
        if best != 0 and agree[best] - agree[0] > 0.12:
            found.append("%s agrees with the strings %d%% of the time as read and %d%% moved by %d semitones" % (
                player.name, round(agree[0] * 100), round(agree[best] * 100), best if best <= 6 else best - 12))
    return found


def stretched(reading: Reading, factor: float) -> Reading:
    """The same music, `factor` times as long: for a score whose tempo is plainly not what
    anyone plays it at."""
    for player in reading.players:
        for tone in player.tones:
            tone.start *= factor
            tone.length *= factor
        player.swells = [(at * factor, level) for at, level in player.swells]
    reading.seconds *= factor
    reading.tempo /= factor
    return reading


# ---------------------------------------------------------------------------------------------
# Seating the orchestra: which channel each instrument is part of, and what plays it
# ---------------------------------------------------------------------------------------------
# kind of instrument -> (channel, General MIDI program, how loud it is set, where it sits left to right)
SEATS = {
    "violin": ("texture", 48, 0.92, -0.42), "violin 2": ("texture", 48, 0.90, -0.12), "viola": ("texture", 48, 0.88, 0.16),
    "cello": ("bass", 48, 0.95, 0.34), "contrabass": ("bass", 48, 1.0, 0.5),
    "violin solo": ("lead", 40, 0.85, -0.2), "viola solo": ("lead", 41, 0.85, 0.1), "cello solo": ("lead", 42, 0.9, 0.2),
    "flute": ("lead", 73, 0.62, -0.14), "piccolo": ("lead", 72, 0.5, -0.2), "oboe": ("lead", 68, 0.58, 0.08),
    "english horn": ("lead", 69, 0.62, 0.12), "clarinet": ("lead", 71, 0.62, -0.06), "bass clarinet": ("lead", 71, 0.66, 0.0),
    "bassoon": ("lead", 70, 0.68, 0.14), "contrabassoon": ("lead", 70, 0.72, 0.18),
    "horn": ("rhythm", 60, 0.76, -0.3), "trumpet": ("rhythm", 56, 0.62, 0.22), "trombone": ("rhythm", 57, 0.7, 0.34),
    "tuba": ("rhythm", 58, 0.76, 0.4),
    "timpani": ("drums", 47, 0.95, -0.06), "percussion": ("drums", 48, 0.9, 0.0),
    "glockenspiel": ("lead", 9, 0.6, 0.1), "celesta": ("lead", 8, 0.7, -0.1), "harp": ("lead", 46, 0.9, -0.34),
    "choir": ("lead", 52, 0.78, 0.0), "organ": ("texture", 19, 0.7, 0.0), "harpsichord": ("texture", 6, 0.75, 0.05),
    "keyboard": ("lead", 0, 0.8, 0.0),
    # A singer alone is given to an instrument: a sampled voice singing "aah" through Bach's
    # runs is no singer, and an oboe is an oboe.
    "soprano": ("lead", 68, 0.74, -0.05), "alto": ("lead", 69, 0.76, 0.05), "tenor": ("lead", 71, 0.76, -0.02),
    "bass voice": ("lead", 42, 0.85, 0.1),
}
_BY_SOUND = (
    ("strings.violin", "violin"), ("strings.viola", "viola"), ("strings.cello", "cello"), ("strings.contrabass", "contrabass"),
    ("strings.viol", "contrabass"), ("wind.flutes.flute.piccolo", "piccolo"), ("wind.flutes", "flute"),
    ("wind.reed.oboe-damore", "english horn"), ("wind.reed.oboe", "oboe"), ("wind.reed.english-horn", "english horn"),
    ("wind.reed.clarinet.bass", "bass clarinet"), ("wind.reed.clarinet", "clarinet"),
    ("wind.reed.contrabassoon", "contrabassoon"), ("wind.reed.sarrus", "contrabassoon"), ("wind.reed.bassoon", "bassoon"),
    ("brass.french-horn", "horn"), ("brass.natural-horn", "horn"), ("brass.trumpet", "trumpet"), ("brass.cornet", "trumpet"),
    ("brass.trombone", "trombone"), ("brass.tuba", "tuba"), ("drum.timpani", "timpani"), ("drum.", "percussion"),
    ("metal.", "percussion"), ("wood.", "percussion"), ("pitched-percussion.glockenspiel", "glockenspiel"),
    ("keyboard.celesta", "celesta"), ("pluck.harp", "harp"), ("keyboard.organ", "organ"),
    ("keyboard.harpsichord", "harpsichord"), ("keyboard.", "keyboard"),
)
# Words in a part's name, most particular first.
_BY_NAME = (
    (("piccolo",), "piccolo"), (("english horn", "cor anglais", "corno inglese"), "english horn"),
    (("bass clarinet", "bassclarinet"), "bass clarinet"), (("contrabassoon", "double bassoon", "doublebassoon", "contrafag"), "contrabassoon"),
    (("bassoon", "fagott"), "bassoon"), (("bass drum", "cymbal", "triangle", "tambourine", "castanet", "snare", "percussion"), "percussion"),
    (("timpani", "pauken", "kettle"), "timpani"), (("glockenspiel",), "glockenspiel"), (("celesta",), "celesta"),
    (("trombon",), "trombone"), (("tuba",), "tuba"), (("trumpet", "tromba", "trombe", "clarino"), "trumpet"),
    (("horn", "corni", "corno"), "horn"), (("flute", "flaut", "traverso"), "flute"), (("oboe", "oboi"), "oboe"),
    (("clarinet",), "clarinet"), (("harp", "arpa"), "harp"), (("violoncell", "cello", "celli"), "cello"),
    (("contrabass", "double bass", "doublebass", "violone", "bassi", "continuo"), "contrabass"),
    (("viola", "viole"), "viola"), (("violin",), "violin"), (("bass",), "contrabass"),
)
_BY_PROGRAM = {72: "piccolo", 73: "flute", 68: "oboe", 69: "english horn", 71: "clarinet", 70: "bassoon", 60: "horn",
               59: "horn", 56: "trumpet", 57: "trombone", 58: "tuba", 47: "timpani", 40: "violin", 41: "viola",
               42: "cello", 43: "contrabass", 46: "harp", 52: "choir", 53: "choir", 54: "choir", 9: "glockenspiel",
               8: "celesta", 19: "organ", 6: "harpsichord", 32: "contrabass"}


def what(player: Player) -> str:
    """What kind of instrument a player is (a key of SEATS): from what the score calls its
    sound, else from its name, else from its General MIDI program and how high it plays."""
    sound, name = player.sound.lower(), player.name.lower()
    solo = "solo" in name or "principal" in name
    if player.drums:
        return "percussion"
    if sound.startswith("voice."):
        if not solo:
            return "choir"
        return {"soprano": "soprano", "alto": "alto", "tenor": "tenor", "bass": "bass voice"}.get(sound.split(".")[1], "soprano")
    if "continuo" in name:
        return "contrabass"                # the bass line of a baroque score: cellos and a violone play it, whatever else does
    found = next((kind for prefix, kind in _BY_SOUND if sound.startswith(prefix)), None)
    if found is None or sound == "strings.group":
        found = next((kind for words, kind in _BY_NAME if any(word in name for word in words)), found)
    if found is None:
        found = _BY_PROGRAM.get(player.program)
    if found is None and player.tones and (40 <= player.program <= 51):
        # A string section with nothing to say which: by how high it plays.
        middle = float(np.median([tone.pitch for tone in player.tones]))
        found = "violin" if middle >= 62 else "viola" if middle >= 54 else "cello" if middle >= 44 else "contrabass"
    if found is None:
        found = "keyboard"
    if found == "violin" and any(mark in name for mark in ("violin 2", "violins ii", "violin ii", "violino2", "violino 2", "2nd violin", "violin2")):
        found = "violin 2"
    if solo and found in ("violin", "violin 2", "viola", "cello"):
        found = found.replace(" 2", "") + " solo"
    return found


def seat(player: Player, kind: str | None = None) -> tuple[str, int, float, float]:
    """(channel, program, volume, pan) for a player."""
    return SEATS[kind or what(player)]


# ---------------------------------------------------------------------------------------------
# Playing a score: each family alone, then the one room
# ---------------------------------------------------------------------------------------------
BEATS_A_SECOND = 2.0           # the MIDI files are written at 120 to the minute, so a beat is half a second
# A sampled instrument played as softly as a score's pianissimo asks is all but gone: forty
# decibels and more under its fortissimo, where an orchestra in a hall has thirty at most, and
# music heard under a game needs less still. Every note's loudness is raised to this power,
# which brings the quiet up towards the loud and leaves the loud where it is.
SOFTEN = 0.75
SWELL = 0.8                    # where the expression pedal rests; a swell inside a held note moves it from there
HALL_S, HALL_WET = 2.4, 0.24   # the room every family is put in


def voices_of(reading: Reading, kinds: dict[str, str] | None = None, seed: int = 0) -> dict[str, list[score.Voice]]:
    """The score as voices for the studio's instruments, by channel. `kinds` names the kind of
    instrument for players the score is wrong or silent about (player name -> a key of SEATS)."""
    rng = random.Random(seed)
    out: dict[str, list[score.Voice]] = {channel: [] for channel in CHANNELS}
    kit: dict[str, score.Voice] = {}
    for player in reading.players:
        if (kinds or {}).get(player.name) == "":
            continue                                       # a player the table says to leave out
        kind = (kinds or {}).get(player.name) or what(player)
        channel, program, volume, pan = seat(player, kind)
        strings = kind in ("violin", "violin 2", "viola", "cello", "contrabass")
        if kind == "percussion":
            # Everything struck goes on one kit: the orchestra's (bass drum, cymbals, triangle).
            voice = kit.setdefault(channel, score.Voice(48, drums=True, volume=volume))
            for tone in player.tones:
                voice.add(tone.start * BEATS_A_SECOND, max(tone.length, 0.1) * BEATS_A_SECOND, tone.pitch, tone.loud ** SOFTEN)
            continue
        ways: dict[str, score.Voice] = {}
        for tone in sorted(player.tones, key=lambda tone: tone.start):
            way = tone.way if strings or kind.endswith("solo") else ""
            if player.program in (45, 32) and (strings or kind.endswith("solo")):
                way = "pizz"                               # a file that keeps its plucked notes on a channel of their own
            elif player.program == 44 and strings:
                way = "trem"
            if way not in ways:
                ways[way] = score.Voice({"pizz": 45, "trem": 44}.get(way, program), pan=pan,
                                        volume=min(volume * (1.08 if way == "pizz" else 1.0), 1.0))
            ways[way].add(tone.start * BEATS_A_SECOND, tone.length * BEATS_A_SECOND, tone.pitch, tone.loud ** SOFTEN)
        if "" in ways and player.swells and kind != "timpani" and kind != "harp":
            ways[""].swells = _swells(player, ways[""])
        for voice in ways.values():
            score.humanise(voice, rng, timing=0.007, loud=0.03, bpm=60.0 * BEATS_A_SECOND)
            out[channel].append(voice)
    for channel, voice in kit.items():
        out[channel].append(voice)
    return out


def _swells(player: Player, voice: score.Voice) -> list[tuple[float, float]]:
    """The expression pedal for a voice: at rest, except inside a held note while the part's
    loudness is moving, where it follows it. A crescendo on a held chord is heard as one."""
    line = player.swells
    moves: list[tuple[float, float]] = [(0.0, SWELL)]
    for note in sorted(voice.notes, key=lambda note: note.start):
        first, last = note.start / BEATS_A_SECOND, (note.start + note.length) / BEATS_A_SECOND
        begins = _level_at(line, first)
        if moves[-1][1] != SWELL:
            moves.append((note.start, SWELL))
        if last - first < 0.7 or begins <= 0:
            continue
        steps = int((last - first) / 0.2)
        for step in range(1, steps + 1):
            at = first + step * 0.2
            pedal = min(max(SWELL * (_level_at(line, at) / begins) ** SOFTEN, 0.3), 1.0)
            if abs(pedal - moves[-1][1]) >= 0.025:
                moves.append((at * BEATS_A_SECOND, pedal))
    return moves if len(moves) > 1 else []


def play(reading: Reading, work: Path, kinds: dict[str, str] | None = None, seed: int = 0) -> dict[str, np.ndarray]:
    """Plays a score: each of the five channels alone, dry, then the same hall added to each.
    Returns channel -> stereo audio, every one the length of the score and POST_S more, for
    the channels that play at all. `work` is a folder for the MIDI and WAV files it makes on
    the way, which it removes."""
    frames = int(round(reading.seconds * RATE)) + int(POST_S * RATE) + int(HALL_S * RATE)
    beats = (reading.seconds + POST_S + HALL_S) * BEATS_A_SECOND
    out: dict[str, np.ndarray] = {}
    work.mkdir(parents=True, exist_ok=True)
    for channel, voices in voices_of(reading, kinds, seed).items():
        voices = [voice for voice in voices if voice.notes]
        if not voices:
            continue
        pitched = [voice for voice in voices if not voice.drums]
        kits = [voice for voice in voices if voice.drums]
        batches = [pitched[index:index + 15] for index in range(0, len(pitched), 15)] or [[]]
        batches[0] = batches[0] + kits
        total = np.zeros((frames, 2), dtype=np.float32)
        for number, batch in enumerate(batches):
            if not batch:
                continue
            midi, wav = work / ("%s-%d.mid" % (channel, number)), work / ("%s-%d.wav" % (channel, number))
            score.write_midi(midi, batch, 60.0 * BEATS_A_SECOND, beats)
            gain = 0.3
            while True:
                audio = fluid.render(midi, wav, gain=gain)
                if float(np.max(np.abs(audio))) < 0.985 or gain < 0.02:
                    break
                gain *= 0.5                                # it ran into full scale: again, quieter
            audio = audio * (0.3 / gain)
            length = min(len(audio), frames)
            total[:length] += audio[:length]
            midi.unlink()
            wav.unlink()
        out[channel] = room.add(total, seconds=HALL_S, wet=HALL_WET)[:frames - int(HALL_S * RATE)]
    return out


# ---------------------------------------------------------------------------------------------
# Cutting a movement into tracks, and a track into its story
# ---------------------------------------------------------------------------------------------
HALF = RATE // 2               # everything here is counted in half seconds
TRACK_S = 180.0                # about how long a track is
BAR_S = 2.0                    # about how long a "bar" of a real score is: see `bars_of`


def level_curve(mix: np.ndarray) -> np.ndarray:
    """How loud the music is in each half second, in dB."""
    mono = mix.mean(axis=1)
    count = len(mono) // HALF
    power = (mono[:count * HALF].reshape(count, HALF).astype(np.float64) ** 2).mean(axis=1)
    return 10.0 * np.log10(power + 1e-10)


def smooth(curve: np.ndarray, width: int) -> np.ndarray:
    """The curve with each point the mean of `width` round it."""
    if width <= 1 or len(curve) < 2:
        return curve.copy()
    padded = np.concatenate([np.full(width // 2, curve[0]), curve, np.full(width - 1 - width // 2, curve[-1])])
    return np.convolve(padded, np.ones(width) / width, mode="valid")


RIDE = 0.35                    # how much of the way a quiet passage is brought up towards the loud ones
RIDE_MOST = 26.0               # a passage more than this far under the loud ones is treated as this far under


def ride(curve: np.ndarray) -> np.ndarray:
    """How much to turn each half second up, in dB, so that the quiet stretches of a movement
    can be heard under a game: a hand on the fader, slowly. A concert piece goes from a whisper
    to the whole orchestra, thirty decibels and more; this leaves the loud passages where they
    are and brings each quieter one RIDE of the way up to them, following the music's level
    over some eight seconds so that nothing pumps. The shape of the piece is kept (what was
    quieter is still quieter), with a little over half its range."""
    sounding = curve[curve > -70.0]
    if not len(sounding):
        return np.zeros(len(curve))
    loud = float(np.percentile(sounding, 90))
    slow = smooth(np.maximum(curve, loud - 60.0), 17)
    return smooth(RIDE * np.clip(loud - slow, 0.0, RIDE_MOST), 9)


def cut_tracks(curve: np.ndarray, target: float = TRACK_S, least: float = 100.0) -> list[tuple[int, int]]:
    """Where to cut a movement into tracks of about `target` seconds: at the quietest moments
    near where even cuts would fall, so that each track ends where the music draws breath.
    In half seconds: [(first, last), ...]."""
    count = len(curve)
    if count / 2.0 < 1.45 * target:
        return [(0, count)]
    tracks = max(int(round(count / 2.0 / target)), 2)
    soft = smooth(curve, 5)
    reach = int(40 * 2)
    edges = [0]
    for index in range(1, tracks):
        ideal = int(round(index * count / tracks))
        low, high = max(edges[-1] + int(least * 2), ideal - reach), min(count - int(least * 2), ideal + reach)
        if low >= high:
            continue
        window = np.arange(low, high)
        cost = soft[window] + 4.0 * np.abs(window - ideal) / reach       # the quiet matters most, the place a little
        edges.append(int(window[int(np.argmin(cost))]) + 1)                # the quiet half second ends the track
    edges.append(count)
    return list(zip(edges, edges[1:]))


def _dip(fine: np.ndarray, at: int, reach: int, low: int, high: int) -> int:
    """The quietest moment within `reach` of `at`, kept inside [low, high]."""
    first, last = max(at - reach, low), min(at + reach + 1, high)
    if first >= last:
        return min(max(at, low), high)
    return first + int(np.argmin(fine[first:last]))


def tell(curve: np.ndarray) -> list[tuple[str, int, int]]:
    """A track's story, read off how loud it is: [(part of the story, first, last), ...] in
    half seconds, covering the whole of it in order.

    The moment is the loudest stretch: the broad curve's peak and whatever stays within a
    couple of dB of it. The rise is the climb that leads into it. What comes before the rise
    is the opening and, if there is enough of it, the theme; what comes after the moment is
    the close, with a theme before it if that is long. Every part is at least twelve seconds
    (a part too short to stand alone joins its neighbour), and its edges are moved to the
    quietest moment nearby, so that parts change where phrases do."""
    count = len(curve)
    least = 24
    if count < 3 * least:
        return [("moment", 0, count)]
    broad, fine = smooth(curve, 21), smooth(curve, 5)
    peak = int(np.argmax(broad))
    first = last = peak
    while first > 0 and broad[first - 1] > broad[peak] - 2.5 and peak - first < 60:
        first -= 1
    while last < count - 1 and broad[last + 1] > broad[peak] - 2.5 and last - peak < 60:
        last += 1
    last += 1
    while last - first < 32:                                    # sixteen seconds at least
        if first > 0:
            first -= 1
        if last < count and last - first < 32:
            last += 1
        if first == 0 and last == count:
            break
    first, last = _dip(fine, first, 8, 0, peak), _dip(fine, last, 8, peak + 1, count)
    # The rise: back from the moment for as long as the music was climbing towards it.
    start = first
    while start > 0 and broad[start - 1] <= broad[start] + 0.25 and first - start < 90:
        start -= 1
    if first - start >= 20:
        start = _dip(fine, start, 8, 0, first - 20)
    else:
        start = first
    parts: list[tuple[str, int, int]] = []
    head = start
    if head >= 80:
        split = _dip(fine, max(40, int(head * 0.42)), 16, 28, head - 28)
        parts += [("open", 0, split), ("theme", split, head)]
    elif head >= least:
        parts.append(("open", 0, head))
    else:
        start = 0                                               # too little before the climb to stand alone
    if first - start >= 20:
        parts.append(("rise", start, first))
    elif parts:
        parts[-1] = (parts[-1][0], parts[-1][1], first)
    else:
        first = 0
    tail = count - last
    if tail < least:
        last = count
    parts.append(("moment", first, last))
    if tail >= 120:
        split = _dip(fine, count - max(60, int(tail * 0.45)), 16, last + 28, count - 28)
        parts += [("theme", last, split), ("close", split, count)]
    elif tail >= least:
        parts.append(("close", last, count))
    if parts[0][0] == "rise":
        parts[0] = ("open", parts[0][1], parts[0][2])           # a track that begins by climbing still begins
    return parts


def bars_of(parts: list[tuple[str, int, int]]) -> tuple[float, list[dict[str, Any]]]:
    """The story as the staging wants it: the length of a bar in samples and each part's
    length in bars. A real score has no steady bar (its tempo comes and goes), so the track is
    ruled into bars of about two seconds, the same for the whole track and a whole number of
    them long. Two seconds, not less, because the player counts its blends in bars."""
    total = parts[-1][2] - parts[0][1]
    bars = max(int(round(total * 0.5 / BAR_S)), len(parts))
    each = total / bars                                         # half seconds to a bar
    edges = [0]
    for index, (_, _, last) in enumerate(parts):
        edge = bars if index == len(parts) - 1 else int(round((last - parts[0][1]) / each))
        edges.append(min(max(edge, edges[-1] + 1), bars - (len(parts) - 1 - index)))
    return each * HALF, [{"story": story, "bars": after - before} for (story, _, _), before, after in zip(parts, edges, edges[1:])]


# ---------------------------------------------------------------------------------------------
# The works
# ---------------------------------------------------------------------------------------------
# Where each OpenScore movement is in its repository, under data/ (as fetched 2026-11-15).
OPENSCORE_PATHS = {
    'bach-bwv-1048-1': 'Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048/1/Bach_BWV.1048_1.mxl',
    'bach-bwv-1048-2': 'Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048/2/Bach_BWV.1048_2.mxl',
    'bach-bwv-1048-3': 'Bach,_Johann_Sebastian/Brandenburg_Concerto_No.3,_BWV.1048/3/Bach_BWV.1048_3.mxl',
    'bach-bwv-1049-1': 'Bach,_Johann_Sebastian/Brandenburg_Concerto_No.4,_BWV.1049/1/Bach_BWV.1049_1.mxl',
    'bach-bwv-1049-2': 'Bach,_Johann_Sebastian/Brandenburg_Concerto_No.4,_BWV.1049/2/Bach_BWV.1049_2.mxl',
    'bach-bwv-1049-3': 'Bach,_Johann_Sebastian/Brandenburg_Concerto_No.4,_BWV.1049/3/Bach_BWV.1049_3.mxl',
    'bach-bwv-232-01': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/01/Bach_BWV.232_01.mxl',
    'bach-bwv-232-02': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/02/Bach_BWV.232_02.mxl',
    'bach-bwv-232-03': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/03/Bach_BWV.232_03.mxl',
    'bach-bwv-232-04': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/04/Bach_BWV.232_04.mxl',
    'bach-bwv-232-05': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/05/Bach_BWV.232_05.mxl',
    'bach-bwv-232-06': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/06/Bach_BWV.232_06.mxl',
    'bach-bwv-232-07a': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/07a/Bach_BWV.232_07a.mxl',
    'bach-bwv-232-07b': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/07b/Bach_BWV.232_07b.mxl',
    'bach-bwv-232-08': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/08/Bach_BWV.232_08.mxl',
    'bach-bwv-232-09a': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/09a/Bach_BWV.232_09a.mxl',
    'bach-bwv-232-09b': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/09b/Bach_BWV.232_09b.mxl',
    'bach-bwv-232-10': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/10/Bach_BWV.232_10.mxl',
    'bach-bwv-232-11': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/11/Bach_BWV.232_11.mxl',
    'bach-bwv-232-12': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/12/Bach_BWV.232_12.mxl',
    'bach-bwv-232-13': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/13/Bach_BWV.232_13.mxl',
    'bach-bwv-232-14': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/14/Bach_BWV.232_14.mxl',
    'bach-bwv-232-15': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/15/Bach_BWV.232_15.mxl',
    'bach-bwv-232-16': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/16/Bach_BWV.232_16.mxl',
    'bach-bwv-232-17': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/17/Bach_BWV.232_17.mxl',
    'bach-bwv-232-18': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/18/Bach_BWV.232_18.mxl',
    'bach-bwv-232-19-21': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/19,21/Bach_BWV.232_19,21.mxl',
    'bach-bwv-232-20': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/20/Bach_BWV.232_20.mxl',
    'bach-bwv-232-22': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/22/Bach_BWV.232_22.mxl',
    'bach-bwv-232-23': 'Bach,_Johann_Sebastian/B_Minor_Mass,_BWV.232/23/Bach_BWV.232_23.mxl',
    'beach-op-32-1': 'Beach,_Amy/Symphony_in_E_minor_(Gaelic),_Op.32/1/Beach_Op.32_1.mxl',
    'beach-op-32-2': 'Beach,_Amy/Symphony_in_E_minor_(Gaelic),_Op.32/2/Beach_Op.32_2.mxl',
    'beach-op-32-3': 'Beach,_Amy/Symphony_in_E_minor_(Gaelic),_Op.32/3/Beach_Op.32_3.mxl',
    'beach-op-32-4': 'Beach,_Amy/Symphony_in_E_minor_(Gaelic),_Op.32/4/Beach_Op.32_4.mxl',
    'beethoven-op-125-1': 'Beethoven,_Ludwig_van/Symphony_No.9,_Op.125/1/Beethoven_Op.125_1.mxl',
    'beethoven-op-125-2': 'Beethoven,_Ludwig_van/Symphony_No.9,_Op.125/2/Beethoven_Op.125_2.mxl',
    'beethoven-op-125-3': 'Beethoven,_Ludwig_van/Symphony_No.9,_Op.125/3/Beethoven_Op.125_3.mxl',
    'beethoven-op-125-4': 'Beethoven,_Ludwig_van/Symphony_No.9,_Op.125/4/Beethoven_Op.125_4.mxl',
    'beethoven-op-21-1': 'Beethoven,_Ludwig_van/Symphony_No.1,_Op.21/1/Beethoven_Op.21_1.mxl',
    'beethoven-op-21-2': 'Beethoven,_Ludwig_van/Symphony_No.1,_Op.21/2/Beethoven_Op.21_2.mxl',
    'beethoven-op-21-3': 'Beethoven,_Ludwig_van/Symphony_No.1,_Op.21/3/Beethoven_Op.21_3.mxl',
    'beethoven-op-21-4': 'Beethoven,_Ludwig_van/Symphony_No.1,_Op.21/4/Beethoven_Op.21_4.mxl',
    'beethoven-op-36-1': 'Beethoven,_Ludwig_van/Symphony_No.2,_Op.36/1/Beethoven_Op.36_1.mxl',
    'beethoven-op-36-2': 'Beethoven,_Ludwig_van/Symphony_No.2,_Op.36/2/Beethoven_Op.36_2.mxl',
    'beethoven-op-36-3': 'Beethoven,_Ludwig_van/Symphony_No.2,_Op.36/3/Beethoven_Op.36_3.mxl',
    'beethoven-op-36-4': 'Beethoven,_Ludwig_van/Symphony_No.2,_Op.36/4/Beethoven_Op.36_4.mxl',
    'beethoven-op-55-1': 'Beethoven,_Ludwig_van/Symphony_No.3,_Op.55/1/Beethoven_Op.55_1.mxl',
    'beethoven-op-55-2': 'Beethoven,_Ludwig_van/Symphony_No.3,_Op.55/2/Beethoven_Op.55_2.mxl',
    'beethoven-op-55-3': 'Beethoven,_Ludwig_van/Symphony_No.3,_Op.55/3/Beethoven_Op.55_3.mxl',
    'beethoven-op-55-4': 'Beethoven,_Ludwig_van/Symphony_No.3,_Op.55/4/Beethoven_Op.55_4.mxl',
    'beethoven-op-60-1': 'Beethoven,_Ludwig_van/Symphony_No.4,_Op.60/1/Beethoven_Op.60_1.mxl',
    'beethoven-op-60-2': 'Beethoven,_Ludwig_van/Symphony_No.4,_Op.60/2/Beethoven_Op.60_2.mxl',
    'beethoven-op-60-3': 'Beethoven,_Ludwig_van/Symphony_No.4,_Op.60/3/Beethoven_Op.60_3.mxl',
    'beethoven-op-60-4': 'Beethoven,_Ludwig_van/Symphony_No.4,_Op.60/4/Beethoven_Op.60_4.mxl',
    'beethoven-op-67-1': 'Beethoven,_Ludwig_van/Symphony_No.5,_Op.67/1/Beethoven_Op.67_1.mxl',
    'beethoven-op-67-2': 'Beethoven,_Ludwig_van/Symphony_No.5,_Op.67/2/Beethoven_Op.67_2.mxl',
    'beethoven-op-67-3': 'Beethoven,_Ludwig_van/Symphony_No.5,_Op.67/3/Beethoven_Op.67_3.mxl',
    'beethoven-op-67-4': 'Beethoven,_Ludwig_van/Symphony_No.5,_Op.67/4/Beethoven_Op.67_4.mxl',
    'beethoven-op-68-1': 'Beethoven,_Ludwig_van/Symphony_No.6,_Op.68/1/Beethoven_Op.68_1.mxl',
    'beethoven-op-68-2': 'Beethoven,_Ludwig_van/Symphony_No.6,_Op.68/2/Beethoven_Op.68_2.mxl',
    'beethoven-op-68-3': 'Beethoven,_Ludwig_van/Symphony_No.6,_Op.68/3/Beethoven_Op.68_3.mxl',
    'beethoven-op-68-4': 'Beethoven,_Ludwig_van/Symphony_No.6,_Op.68/4/Beethoven_Op.68_4.mxl',
    'beethoven-op-68-5': 'Beethoven,_Ludwig_van/Symphony_No.6,_Op.68/5/Beethoven_Op.68_5.mxl',
    'beethoven-op-92-1': 'Beethoven,_Ludwig_van/Symphony_No.7,_Op.92/1/Beethoven_Op.92_1.mxl',
    'beethoven-op-92-2': 'Beethoven,_Ludwig_van/Symphony_No.7,_Op.92/2/Beethoven_Op.92_2.mxl',
    'beethoven-op-92-3': 'Beethoven,_Ludwig_van/Symphony_No.7,_Op.92/3/Beethoven_Op.92_3.mxl',
    'beethoven-op-92-4': 'Beethoven,_Ludwig_van/Symphony_No.7,_Op.92/4/Beethoven_Op.92_4.mxl',
    'beethoven-op-93-1': 'Beethoven,_Ludwig_van/Symphony_No.8,_Op.93/1/Beethoven_Op.93_1.mxl',
    'beethoven-op-93-2': 'Beethoven,_Ludwig_van/Symphony_No.8,_Op.93/2/Beethoven_Op.93_2.mxl',
    'beethoven-op-93-3': 'Beethoven,_Ludwig_van/Symphony_No.8,_Op.93/3/Beethoven_Op.93_3.mxl',
    'beethoven-op-93-4': 'Beethoven,_Ludwig_van/Symphony_No.8,_Op.93/4/Beethoven_Op.93_4.mxl',
    'brahms-op-45-1': 'Brahms,_Johannes/Ein_Deutsches_Requiem,_Op.45/1/Brahms_Op.45_1.mxl',
    'brahms-op-68-1': 'Brahms,_Johannes/Symphony_No.1,_Op.68/1/Brahms_Op.68_1.mxl',
    'brahms-op-68-2': 'Brahms,_Johannes/Symphony_No.1,_Op.68/2/Brahms_Op.68_2.mxl',
    'brahms-op-68-3': 'Brahms,_Johannes/Symphony_No.1,_Op.68/3/Brahms_Op.68_3.mxl',
    'brahms-op-68-4': 'Brahms,_Johannes/Symphony_No.1,_Op.68/4/Brahms_Op.68_4.mxl',
    'brahms-op-73-1': 'Brahms,_Johannes/Symphony_No.2,_Op.73/1/Brahms_Op.73_1.mxl',
    'brahms-op-73-2': 'Brahms,_Johannes/Symphony_No.2,_Op.73/2/Brahms_Op.73_2.mxl',
    'brahms-op-73-3': 'Brahms,_Johannes/Symphony_No.2,_Op.73/3/Brahms_Op.73_3.mxl',
    'brahms-op-73-4': 'Brahms,_Johannes/Symphony_No.2,_Op.73/4/Brahms_Op.73_4.mxl',
    'brahms-op-90-1': 'Brahms,_Johannes/Symphony_No.3,_Op.90/1/Brahms_Op.90_1.mxl',
    'brahms-op-90-2': 'Brahms,_Johannes/Symphony_No.3,_Op.90/2/Brahms_Op.90_2.mxl',
    'brahms-op-90-3': 'Brahms,_Johannes/Symphony_No.3,_Op.90/3/Brahms_Op.90_3.mxl',
    'brahms-op-90-4': 'Brahms,_Johannes/Symphony_No.3,_Op.90/4/Brahms_Op.90_4.mxl',
    'brahms-op-98-1': 'Brahms,_Johannes/Symphony_No.4,_Op.98/1/Brahms_Op.98_1.mxl',
    'brahms-op-98-2': 'Brahms,_Johannes/Symphony_No.4,_Op.98/2/Brahms_Op.98_2.mxl',
    'brahms-op-98-3': 'Brahms,_Johannes/Symphony_No.4,_Op.98/3/Brahms_Op.98_3.mxl',
    'brahms-op-98-4': 'Brahms,_Johannes/Symphony_No.4,_Op.98/4/Brahms_Op.98_4.mxl',
    'bruckner-wab-105-1': 'Bruckner,_Anton/Symphony_No.5,_WAB.105/1/Bruckner_WAB.105_1.mxl',
    'bruckner-wab-105-2': 'Bruckner,_Anton/Symphony_No.5,_WAB.105/2/Bruckner_WAB.105_2.mxl',
    'bruckner-wab-105-3a-scherzo': 'Bruckner,_Anton/Symphony_No.5,_WAB.105/3a/Bruckner_WAB.105_3a_Scherzo.mxl',
    'bruckner-wab-105-3b-trio': 'Bruckner,_Anton/Symphony_No.5,_WAB.105/3b/Bruckner_WAB.105_3b_Trio.mxl',
    'bruckner-wab-105-4': 'Bruckner,_Anton/Symphony_No.5,_WAB.105/4/Bruckner_WAB.105_4.mxl',
    'd-un-matin-de-printemps': "Boulanger,_Lili/D'un_matin_de_printemps/D'un_matin_de_printemps.mxl",
    'haydn-104-1': 'Haydn,_Franz/Symphony_No.104/1/Haydn_104_1.mxl',
    'schubert-d-485-1': 'Schubert,_Franz/Symphony_No.5,_D.485/1/Schubert_D.485_1.mxl',
}
# The other sources: folder under var/scores -> (file name, where it is fetched from).
OTHERS = {
    "mutopia/egmont": ("Egmont.mid", "https://www.mutopiaproject.org/ftp/BeethovenLv/O84/Egmont/Egmont.mid"),
    "mutopia/coriolan": ("Coriolan-mids.zip", "https://www.mutopiaproject.org/ftp/BeethovenLv/O62/Coriolan/Coriolan-mids.zip"),
    "mutopia/dvorak9": ("Sym9-mids.zip", "https://www.mutopiaproject.org/ftp/DvorakA/O95/Sym9/Sym9-mids.zip"),
    "pdcorpus/tell": ("tell.mid", "https://raw.githubusercontent.com/GCraftsman/pd-score-corpus/main/midi/12/6/QmU7w88CbWwWirfa2fBPmK4AvtWUp7YxE4ZQdDvyME6o43.mid"),
    "pdcorpus/capriccio": ("capriccio.mid", "https://raw.githubusercontent.com/GCraftsman/pd-score-corpus/main/midi/11/30/QmTLWLYKcFNUJTNomjbNgZzD1zTaWoKr7Rg64kosD2QMet.mid"),
    "commons/jupiter": ("The_Planets-Jupiter.mid", "https://upload.wikimedia.org/wikipedia/commons/1/18/The_Planets-Jupiter.mid"),
}
MUTOPIA_PD = "Score: Mutopia Project (mutopiaproject.org), Public Domain"
MUTOPIA_SA = "Score: typeset for the Mutopia Project (mutopiaproject.org, DvorakA/O95/Sym9), Creative Commons Attribution-ShareAlike 3.0"
PDCORPUS = "Score: pd-score-corpus (github.com/GCraftsman/pd-score-corpus, from the PDMX dataset), declared CC0 or Public Domain by its uploader"
COMMONS = "Score: Wikimedia Commons, File:The_Planets-Jupiter.mid, free to use with attribution"


def fetch() -> int:
    """Fetches every score the table needs that is not here yet. Returns how many files are here."""
    count = 0
    for slug, path in OPENSCORE_PATHS.items():
        fetch_one(OPENSCORE + urllib.parse.quote(path), VAR / "scores" / "openscore" / slug, "score.mxl")
        count += 1
    for folder, (name, url) in OTHERS.items():
        fetch_one(url, VAR / "scores" / folder, name)
        count += 1
    return count


@dataclass
class Work:
    """One movement (or one overture) and what it is for."""
    id: str
    title: str
    source: tuple[str, ...]            # ("openscore", slug) | ("midi", path) | ("zip", path, member), under var/scores
    tonic: str
    moods: tuple[str, ...]             # the kinds of place it suits (kinds.KINDS)
    role: str = "wander"
    serves: tuple[int, ...] = (0, 1)
    light: bool = False
    terms: str = OPENSCORE_TERMS
    minutes: float | None = None       # how long it lasts as people play it, where the score's tempo cannot be trusted
    retempo: dict[float, float] | None = None
    tempo_marks: list[tuple[str, float]] | None = None
    fight: str = ""                    # "all": every track of it is for a fight; "loud": its loud tracks are
    fight_role: str = "battle"
    kinds: dict[str, str] | None = None        # player name -> kind of instrument, where the score is wrong or silent ("" to leave the player out)
    shift: dict[str, int] | None = None        # player name -> semitones, where a part was entered at the wrong pitch
    breaks: tuple[tuple[float, dict[str, Any]], ...] = ()    # (seconds, what changes from there): a work in several parts


def _b(number: int, movement: int, name: str, tonic: str, moods: tuple[str, ...], **more: Any) -> Work:
    opus = {1: 21, 2: 36, 3: 55, 4: 60, 5: 67, 6: 68, 7: 92, 8: 93, 9: 125}[number]
    return Work("beethoven-%d-%d" % (number, movement), "Beethoven: Symphony No. %d, %s" % (number, name),
                ("openscore", "beethoven-op-%d-%d" % (opus, movement)), tonic, moods, **more)


def _br(number: int, movement: int, name: str, tonic: str, moods: tuple[str, ...], **more: Any) -> Work:
    opus = {1: 68, 2: 73, 3: 90, 4: 98}[number]
    return Work("brahms-%d-%d" % (number, movement), "Brahms: Symphony No. %d, %s" % (number, name),
                ("openscore", "brahms-op-%d-%d" % (opus, movement)), tonic, moods, **more)


def _mass(number: str, name: str, tonic: str, moods: tuple[str, ...], **more: Any) -> Work:
    return Work("mass-%s" % number, "Bach: Mass in B minor, %s" % name, ("openscore", "bach-bwv-232-%s" % number), tonic, moods, **more)


_WORKS = [
    # Beethoven's nine. His own metronome marks are in the scores; a few were entered at half
    # or twice their value, and are put right here.
    _b(1, 1, "I. Adagio molto - Allegro con brio", "C major", ("regal", "pastoral"), light=True),
    _b(1, 2, "II. Andante cantabile con moto", "F major", ("pastoral",), light=True),
    _b(1, 3, "III. Menuetto", "C major", ("regal", "highland"), light=True),
    _b(1, 4, "IV. Adagio - Allegro molto e vivace", "C major", ("pastoral", "regal"), light=True),
    _b(2, 1, "I. Adagio molto - Allegro con brio", "D major", ("regal", "highland")),
    _b(2, 2, "II. Larghetto", "A major", ("pastoral", "mystic"), light=True, role="night"),
    _b(2, 3, "III. Scherzo", "D major", ("highland", "pastoral"), light=True),
    _b(2, 4, "IV. Allegro molto", "D major", ("regal", "pastoral"), light=True),
    _b(3, 1, "I. Allegro con brio", "Eb major", ("regal", "highland"), fight="loud"),
    _b(3, 2, "II. Marcia funebre", "C minor", ("haunted",)),
    # (Its trumpets are in E flat; the score has them as trumpets in B flat, a fourth too low.)
    _b(3, 3, "III. Scherzo", "Eb major", ("highland", "pastoral"), light=True, shift={"Bb Trumpet 1": 5, "Bb Trumpet 2": 5}),
    _b(3, 4, "IV. Finale", "Eb major", ("regal",)),
    _b(4, 1, "I. Adagio - Allegro vivace", "Bb major", ("mystic", "pastoral"), light=True, retempo={160: 320}),
    _b(4, 2, "II. Adagio", "Eb major", ("mystic", "pastoral"), light=True, role="night", retempo={84: 42}),
    _b(4, 3, "III. Allegro vivace", "Bb major", ("pastoral", "highland"), light=True),
    _b(4, 4, "IV. Allegro ma non troppo", "Bb major", ("pastoral", "jungle", "infernal"), light=True),
    _b(5, 1, "I. Allegro con brio", "C minor", ("infernal", "haunted"), role="battle", serves=(1, 2), fight="all"),
    _b(5, 2, "II. Andante con moto", "Ab major", ("regal", "highland"), tempo_marks=[("0", 46), ("205", 58), ("218", 46)]),
    _b(5, 3, "III. Allegro", "C minor", ("haunted", "infernal"), role="depths"),
    _b(5, 4, "IV. Allegro", "C major", ("regal",), retempo={224: 448}),
    _b(6, 1, "I. Awakening of cheerful feelings on arriving in the country", "F major", ("pastoral",), light=True),
    _b(6, 2, "II. Scene by the brook", "Bb major", ("pastoral", "mystic"), light=True, role="ember", serves=(0,)),
    _b(6, 3, "III. Merry gathering of country folk", "F major", ("pastoral",), light=True),
    _b(6, 4, "IV. Thunderstorm", "F minor", ("pastoral", "highland", "jungle"), role="storm", serves=(1, 2)),
    _b(6, 5, "V. Shepherd's song", "F major", ("pastoral",), light=True),
    _b(7, 1, "I. Poco sostenuto - Vivace", "A major", ("highland", "regal")),
    _b(7, 2, "II. Allegretto", "A minor", ("haunted", "desert")),
    _b(7, 3, "III. Presto", "F major", ("highland", "pastoral"), light=True),
    _b(7, 4, "IV. Allegro con brio", "A major", ("jungle", "infernal"), role="battle", serves=(1, 2), fight="all"),
    _b(8, 1, "I. Allegro vivace e con brio", "F major", ("pastoral", "regal"), light=True),
    # (Its horns are in B flat basso; the score has them as horns in F, a fifth too high.)
    _b(8, 2, "II. Allegretto scherzando", "Bb major", ("pastoral", "infernal"), light=True, shift={"F Horn 1": -7, "F Horn 2": -7}),
    _b(8, 3, "III. Tempo di menuetto", "F major", ("regal",), light=True),
    _b(8, 4, "IV. Allegro vivace", "F major", ("pastoral", "jungle"), light=True, retempo={168: 336}),
    _b(9, 1, "I. Allegro ma non troppo, un poco maestoso", "D minor", ("infernal", "haunted"), fight="loud", fight_role="boss"),
    _b(9, 2, "II. Molto vivace", "D minor", ("highland", "jungle"), fight="loud"),
    _b(9, 3, "III. Adagio molto e cantabile", "Bb major", ("mystic", "pastoral"), light=True, role="night"),
    _b(9, 4, "IV. Finale", "D major", ("regal",)),
    # Brahms left no metronome marks, and the tempos in these scores are often only whatever
    # the notation program began with. Where one is far from how the movement is played, the
    # movement is given the length it usually has (without its repeats).
    _br(1, 1, "I. Un poco sostenuto - Allegro", "C minor", ("infernal", "haunted"), fight="loud", fight_role="boss"),
    _br(1, 2, "II. Andante sostenuto", "E major", ("mystic", "pastoral"), light=True, role="night", minutes=8.8),
    _br(1, 3, "III. Un poco allegretto e grazioso", "Ab major", ("pastoral",), light=True, minutes=4.6),
    _br(1, 4, "IV. Adagio - Allegro non troppo, ma con brio", "C major", ("highland", "regal"), minutes=16.2),
    _br(2, 1, "I. Allegro non troppo", "D major", ("pastoral", "mystic"), light=True, minutes=15.0),
    _br(2, 2, "II. Adagio non troppo", "B major", ("mystic", "haunted"), minutes=9.5),
    _br(2, 3, "III. Allegretto grazioso", "G major", ("pastoral",), light=True, minutes=5.2),
    _br(2, 4, "IV. Allegro con spirito", "D major", ("regal", "pastoral"), minutes=9.5),
    _br(3, 1, "I. Allegro con brio", "F major", ("highland", "infernal"), fight="loud"),
    _br(3, 2, "II. Andante", "C major", ("pastoral", "mystic"), light=True, role="ember", serves=(0,), minutes=8.3),
    _br(3, 3, "III. Poco allegretto", "C minor", ("haunted", "mystic"), light=True, minutes=6.1),
    _br(3, 4, "IV. Allegro", "F minor", ("infernal", "highland"), fight="loud"),
    _br(4, 1, "I. Allegro non troppo", "E minor", ("haunted", "mystic")),
    _br(4, 2, "II. Andante moderato", "E phrygian", ("desert", "mystic", "haunted"), light=True, minutes=11.3),
    _br(4, 3, "III. Allegro giocoso", "C major", ("regal", "jungle")),
    _br(4, 4, "IV. Allegro energico e passionato", "E minor", ("infernal", "haunted"), role="boss", serves=(1, 2), fight="all",
        fight_role="boss", minutes=10.0),
    Work("brahms-requiem-1", "Brahms: A German Requiem, I. Selig sind, die da Leid tragen", ("openscore", "brahms-op-45-1"),
         "F major", ("mystic", "haunted"), role="ember", serves=(0,), light=True, minutes=10.0),
    Work("bruckner-5-1", "Bruckner: Symphony No. 5, I. Adagio - Allegro", ("openscore", "bruckner-wab-105-1"), "Bb major", ("regal", "mystic")),
    Work("bruckner-5-2", "Bruckner: Symphony No. 5, II. Adagio", ("openscore", "bruckner-wab-105-2"), "D minor", ("mystic", "haunted"),
         role="night", minutes=16.0),
    Work("bruckner-5-3a", "Bruckner: Symphony No. 5, III. Scherzo", ("openscore", "bruckner-wab-105-3a-scherzo"), "D minor",
         ("highland", "infernal"), fight="loud"),
    Work("bruckner-5-3b", "Bruckner: Symphony No. 5, III. Trio", ("openscore", "bruckner-wab-105-3b-trio"), "Bb major", ("pastoral",),
         light=True, minutes=2.6),
    Work("bruckner-5-4", "Bruckner: Symphony No. 5, IV. Finale", ("openscore", "bruckner-wab-105-4"), "Bb major", ("regal", "infernal")),
    Work("beach-gaelic-1", "Amy Beach: Gaelic Symphony, I. Allegro con fuoco", ("openscore", "beach-op-32-1"), "E minor",
         ("highland", "infernal"), fight="loud", fight_role="storm"),
    Work("beach-gaelic-2", "Amy Beach: Gaelic Symphony, II. Alla siciliana - Allegro vivace", ("openscore", "beach-op-32-2"), "F major",
         ("highland", "pastoral"), light=True),
    Work("beach-gaelic-3", "Amy Beach: Gaelic Symphony, III. Lento con molto espressione", ("openscore", "beach-op-32-3"), "E minor",
         ("highland", "haunted"), light=True),
    Work("beach-gaelic-4", "Amy Beach: Gaelic Symphony, IV. Allegro di molto", ("openscore", "beach-op-32-4"), "E minor", ("highland",),
         fight="loud"),
    Work("boulanger-matin", "Lili Boulanger: D'un matin de printemps", ("openscore", "d-un-matin-de-printemps"), "E minor",
         ("mystic", "pastoral"), light=True),
    Work("haydn-104-1", "Haydn: Symphony No. 104, I. Adagio - Allegro", ("openscore", "haydn-104-1"), "D major", ("regal", "pastoral"),
         light=True, tempo_marks=[("1", 38), ("18", 250)]),
    Work("schubert-5-1", "Schubert: Symphony No. 5, I. Allegro", ("openscore", "schubert-d-485-1"), "Bb major", ("pastoral",),
         light=True, minutes=5.3),
    Work("brandenburg-3-1", "Bach: Brandenburg Concerto No. 3, I.", ("openscore", "bach-bwv-1048-1"), "G major", ("regal", "pastoral"), light=True),
    Work("brandenburg-3-3", "Bach: Brandenburg Concerto No. 3, III. Allegro", ("openscore", "bach-bwv-1048-3"), "G major",
         ("pastoral", "regal"), light=True),
    Work("brandenburg-4-1", "Bach: Brandenburg Concerto No. 4, I. Allegro", ("openscore", "bach-bwv-1049-1"), "G major", ("pastoral",), light=True),
    Work("brandenburg-4-2", "Bach: Brandenburg Concerto No. 4, II. Andante", ("openscore", "bach-bwv-1049-2"), "E minor",
         ("mystic", "haunted"), light=True),
    Work("brandenburg-4-3", "Bach: Brandenburg Concerto No. 4, III. Presto", ("openscore", "bach-bwv-1049-3"), "G major",
         ("regal", "pastoral"), light=True),
    # The Mass in B minor. The choir is a sampled choir; a singer alone is given to an instrument.
    _mass("01", "Kyrie eleison", "B minor", ("haunted", "mystic")),
    _mass("02", "Christe eleison", "D major", ("pastoral", "mystic"), light=True),
    _mass("03", "Kyrie eleison (the second)", "F# minor", ("haunted",), role="depths"),
    _mass("04", "Gloria in excelsis - Et in terra pax", "D major", ("regal",), light=True),
    _mass("05", "Laudamus te", "A major", ("pastoral",), light=True),
    _mass("06", "Gratias agimus tibi", "D major", ("regal", "mystic")),
    _mass("07a", "Domine Deus", "G major", ("pastoral", "mystic"), light=True),
    _mass("07b", "Qui tollis peccata mundi", "B minor", ("haunted", "mystic"), role="night"),
    _mass("08", "Qui sedes ad dexteram Patris", "B minor", ("mystic", "haunted"), light=True),
    _mass("09a", "Quoniam tu solus sanctus", "D major", ("regal", "highland")),
    _mass("09b", "Cum Sancto Spiritu", "D major", ("regal",)),
    _mass("10", "Credo in unum Deum", "A mixolydian", ("mystic", "regal")),
    _mass("11", "Patrem omnipotentem", "D major", ("regal",)),
    _mass("12", "Et in unum Dominum", "G major", ("pastoral",), light=True),
    _mass("13", "Et incarnatus est", "B minor", ("haunted", "mystic"), role="depths", minutes=3.0),
    _mass("14", "Crucifixus", "E minor", ("haunted",), role="depths"),
    _mass("15", "Et resurrexit", "D major", ("regal",)),
    _mass("16", "Et in Spiritum Sanctum", "A major", ("pastoral",), light=True),
    _mass("17", "Confiteor - Et expecto", "F# minor", ("mystic", "regal")),
    _mass("18", "Sanctus", "D major", ("regal", "mystic")),
    _mass("19-21", "Osanna in excelsis", "D major", ("regal",)),
    _mass("20", "Benedictus", "B minor", ("mystic", "haunted"), light=True, role="night", minutes=4.0),
    _mass("22", "Agnus Dei", "G minor", ("haunted", "mystic"), light=True, role="night", minutes=5.2),
    _mass("23", "Dona nobis pacem", "D major", ("regal", "mystic")),
    # From MIDI files.
    Work("egmont", "Beethoven: Egmont, Overture", ("midi", "mutopia/egmont/Egmont.mid"), "F minor", ("infernal", "regal"),
         terms=MUTOPIA_PD, fight="loud", kinds={"six:": "horn", "seven:": "horn", "eight:": "trumpet"}),
    Work("coriolan", "Beethoven: Coriolan, Overture", ("zip", "mutopia/coriolan/Coriolan-mids.zip", "coriolan.mid"), "C minor",
         ("infernal", "haunted"), terms=MUTOPIA_PD, fight="loud"),
    Work("dvorak-9-1", "Dvorak: Symphony No. 9 \"From the New World\", I. Adagio - Allegro molto",
         ("zip", "mutopia/dvorak9/Sym9-mids.zip", "Mvt1_Adagio.mid"), "E minor", ("highland", "desert"), terms=MUTOPIA_SA, fight="loud"),
    Work("dvorak-9-2", "Dvorak: Symphony No. 9 \"From the New World\", II. Largo",
         ("zip", "mutopia/dvorak9/Sym9-mids.zip", "Mvt2_Largo.mid"), "Db major", ("pastoral", "desert"), terms=MUTOPIA_SA,
         light=True, role="ember", serves=(0,), kinds={"oboe:": "english horn"}),
    Work("dvorak-9-3", "Dvorak: Symphony No. 9 \"From the New World\", III. Scherzo",
         ("zip", "mutopia/dvorak9/Sym9-mids.zip", "Mvt3_Scherzo.mid"), "E minor", ("jungle", "highland"), terms=MUTOPIA_SA, fight="loud"),
    Work("dvorak-9-4", "Dvorak: Symphony No. 9 \"From the New World\", IV. Allegro con fuoco",
         ("zip", "mutopia/dvorak9/Sym9-mids.zip", "Mvt4_conFuoco.mid"), "E minor", ("infernal", "regal"), terms=MUTOPIA_SA, fight="loud"),
    Work("tell", "Rossini: William Tell, Overture", ("midi", "pdcorpus/tell/tell.mid"), "E major", ("mystic", "pastoral"),
         terms=PDCORPUS, light=True, kinds={"Violoncello": "cello solo", "Bass Drum": "percussion"},
         breaks=((0.0, {"name": "Dawn", "moods": ("mystic", "haunted", "pastoral")}),
                 (156.5, {"name": "The storm", "tonic": "E minor", "moods": ("highland", "pastoral"), "role": "storm", "serves": (1, 2), "light": False}),
                 (295.0, {"name": "The call to the cows", "tonic": "G major", "moods": ("pastoral",), "light": True}),
                 (430.8, {"name": "March of the Swiss soldiers", "tonic": "E major", "moods": ("regal", "highland"), "role": "battle",
                          "serves": (1, 2), "light": False}))),
    # (The solo cello's few bars do not agree with anything else in the file, at any pitch: left out.)
    Work("capriccio", "Rimsky-Korsakov: Capriccio espagnol", ("midi", "pdcorpus/capriccio/capriccio.mid"), "A major", ("desert", "jungle"),
         terms=PDCORPUS, light=True, kinds={"Violoncello Solo": ""}),
    Work("jupiter", "Holst: The Planets, Jupiter, the Bringer of Jollity", ("midi", "commons/jupiter/The_Planets-Jupiter.mid"), "C major",
         ("regal", "pastoral"), terms=COMMONS, light=True,
         shift={"English Horn": -7, "Tenor Tuba in Bb": -14, "Clarinets in Bb": -24, "BassClarinets in Bb": -24, "Piccolos": 12}),
]
WORKS = {work.id: work for work in _WORKS}


def load(work: Work) -> Reading:
    """A work's score, read, with whatever the table says must be put right."""
    folder = VAR / "scores"
    if work.source[0] == "openscore":
        with zipfile.ZipFile(folder / "openscore" / work.source[1] / "score.mxl") as packed:
            inside = [name for name in packed.namelist() if name.endswith(".xml") and not name.startswith("META-INF")]
            if len(inside) != 1:
                raise ValueError("%s holds %d scores, not one" % (work.source[1], len(inside)))
            reading = read_musicxml(packed.read(inside[0]), retempo=work.retempo, tempo_marks=work.tempo_marks)
    elif work.source[0] == "midi":
        reading = read_midi((folder / work.source[1]).read_bytes())
    elif work.source[0] == "zip":
        with zipfile.ZipFile(folder / work.source[1]) as packed:
            reading = read_midi(packed.read(work.source[2]))
    else:
        raise ValueError("No way to read a score from %r" % (work.source,))
    names = {player.name for player in reading.players}
    for name in list(work.shift or {}) + list(work.kinds or {}):
        if name not in names:
            raise ValueError("%s has no player called %r (it has %s)" % (work.id, name, ", ".join(sorted(names))))
    for player in reading.players:
        move = (work.shift or {}).get(player.name, 0)
        if move:
            for tone in player.tones:
                tone.pitch += move
    if work.minutes:
        reading.notes.append("its tempo is set so that it lasts %.1f minutes, not the %.1f its own marks give" % (
            work.minutes, reading.seconds / 60.0))
        stretched(reading, work.minutes * 60.0 / reading.seconds)
    return reading


# ---------------------------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------------------------
SILENT = 10 ** (-66 / 20)      # a family that never rises above this in a track is left out of it
LEAD_IN = 10.0                 # music for a fight begins where it comes within this many dB of its loudest
FULL = 0.89                    # the loudest moment of a movement, every family playing, is brought to this


def _seed(text: str) -> int:
    value = 0
    for letter in text:
        value = (value * 131 + ord(letter)) % 2_147_483_647
    return value


def _tags(work: Work, at: float) -> dict[str, Any]:
    """What a track that begins `at` seconds into a work is: the work's own tags, or those of
    the part of the work it falls in."""
    whole = {"name": "", "tonic": work.tonic, "moods": work.moods, "role": work.role, "serves": work.serves, "light": work.light}
    tags = whole
    for begins, changes in work.breaks:
        if at >= begins - 1.0:
            tags = {**whole, **changes}
    return tags


def stage_work(work_id: str, out: Path | None = None) -> list[dict[str, Any]]:
    """Plays one work and stages it as tracks under `out` (var/studio/warcraft). Returns what
    it staged, a row for each track: for the record and for the report."""
    work = WORKS[work_id]
    out = Path(out) if out is not None else VAR / "studio" / STYLE
    reading = load(work)
    scratch = VAR / "scores" / "work" / work.id
    parts = play(reading, scratch, work.kinds, seed=_seed(work.id))
    scratch.rmdir()
    if not parts:
        raise ValueError("Nothing plays in %s" % work.id)
    frames = int(round(reading.seconds * RATE))
    mix = sum(parts.values())
    # The quiet passages are brought up towards the loud ones, the same for every family, so
    # that the families still add up to the orchestra.
    lift = ride(level_curve(mix[:frames]))
    if len(lift):
        at = (np.arange(len(lift)) + 0.5) * HALF
        gain = (10.0 ** (np.interp(np.arange(len(mix)), at, lift) / 20.0)).astype(np.float32)
        for channel in parts:
            parts[channel] = parts[channel] * gain[:, None]
        mix = sum(parts.values())
    scale = FULL / max(float(np.max(np.abs(mix))), 1e-9)
    curve = level_curve(mix[:frames] * scale)
    # A work in several parts is cut where its parts join, whatever else.
    marks = sorted({0} | {min(int(round(begins * 2)), len(curve)) for begins, _ in work.breaks} | {len(curve)})
    spans: list[tuple[int, int]] = []
    for first, last in zip(marks, marks[1:]):
        if last - first < 2 * 30:
            continue                                             # under half a minute: not a track
        spans += [(first + a, first + b) for a, b in cut_tracks(curve[first:last])]
    sounding = curve[curve > -70.0]
    hot = float(np.percentile(sounding, 60)) if len(sounding) else 0.0
    # What was staged before for this work goes: there may be fewer tracks this time.
    prefix = "real-%s-" % work.id
    for old in sorted(out.glob(prefix + "[0-9][0-9]")):
        for inner in sorted(old.glob("*/*")):
            inner.unlink()
        for inner in sorted(old.glob("*")):
            inner.rmdir()
        old.rmdir()
    rows = []
    post = int(POST_S * RATE)
    # Of a work whose loud tracks are for a fight, the fiercest track always is, if it is fierce at all.
    heat = [float(np.mean(curve[first:last] > hot)) for first, last in spans]
    for number, (first, last) in enumerate(spans, start=1):
        tags = _tags(work, first / 2.0)
        role, serves = tags["role"], tuple(tags["serves"])
        fierce = heat[number - 1]
        if work.fight == "all" or (work.fight == "loud" and (fierce >= 0.44 or (fierce >= 0.38 and fierce == max(heat)))):
            role, serves = work.fight_role, (1, 2)
        if role in ("battle", "boss", "storm"):
            # Music that answers a fight or a storm has to be there when it is brought in: a
            # quiet lead-in is left off, and the track begins a second before the music does.
            soft = smooth(curve[first:last], 3)
            there = np.nonzero(soft > float(np.percentile(soft, 95)) - LEAD_IN)[0]
            lead = max(int(there[0]) - 2, 0) if len(there) else 0
            if lead >= 4 and last - first - lead >= 120:
                first += lead
        story = tell(curve[first:last])
        bar, sections = bars_of(story)
        a, b = first * HALF, last * HALF
        cut: dict[str, np.ndarray] = {}
        for channel, audio in parts.items():
            piece = audio[a:b + post] * scale
            if len(piece) < b - a + post:
                piece = np.concatenate([piece, np.zeros((b - a + post - len(piece), 2), dtype=np.float32)])
            if float(np.max(np.abs(piece[:b - a]))) > SILENT:
                cut[channel] = piece.astype(np.float32)
        title = work.title + (": " + tags["name"] if tags["name"] else "")
        if len(spans) > 1 and not tags["name"]:
            title += " (%d of %d)" % (number, len(spans))
        elif tags["name"]:
            same = [span for span in spans if _tags(work, span[0] / 2.0)["name"] == tags["name"]]
            if len(same) > 1:
                title += " (%d of %d)" % ([span[1] for span in same].index(last) + 1, len(same))
        family = "%s%02d" % (prefix, number)
        tonic = key_of(sum(cut.values())[:b - a], tags["tonic"])
        meta = {
            "style": STYLE, "family": family, "take": 1, "title": title, "tempo": round(reading.tempo, 2), "beats": 4,
            "bar_frames": bar, "tonic": tonic, "moods": list(tags["moods"]), "role": role, "serves": list(serves),
            "light": bool(tags["light"]), "sections": sections,
            "floor": {section["story"]: dict(FLOOR) for section in sections}, "follow": {}, "post_s": POST_S,
            "credit": "%s. %s. %s" % (work.title, work.terms, PLAYED_BY), "seed": _seed(work.id),
        }
        write_track(out / family / "1", meta, cut)
        whole = sum(cut.values())
        edges, bars = [0], 0
        for section in sections:
            bars += section["bars"]
            edges.append(int(round(bars * bar)))
        rows.append({
            "work": work.id, "family": family, "title": title, "seconds": round((b - a) / RATE, 1), "from": round(first / 2.0, 1),
            "moods": list(tags["moods"]), "role": role, "serves": list(serves), "light": bool(tags["light"]), "tonic": tonic,
            "channels": sorted(cut), "peak": round(float(np.max(np.abs(whole))), 3), "fierce": round(fierce, 2),
            "sections": [{"story": section["story"], "bars": section["bars"],
                          "lufs": round(analysis.loudness_lufs(whole[begin:end], RATE), 1)}
                         for section, begin, end in zip(sections, edges, edges[1:])],
            "notes": reading.notes, "players": len(reading.players), "minutes": round(reading.seconds / 60.0, 2)})
    record = VAR / "scores" / "staged"
    record.mkdir(parents=True, exist_ok=True)
    (record / (work.id + ".json")).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return rows


def retag() -> int:
    """Brings what every staged track says of itself up to date with the table: the kinds of
    place it is for, whether it is light, and the kind of moment it is for. Nothing is played
    again. A track that was given to fights because it turned out loud stays given to them,
    and every track keeps its key, which was heard. Returns how many tracks were changed."""
    changed = 0
    for path in sorted((VAR / "scores" / "staged").glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        work = WORKS.get(path.stem)
        if work is None:
            continue
        for row in rows:
            tags = _tags(work, row["from"])
            fresh = {"moods": list(tags["moods"]), "light": bool(tags["light"])}
            fought = bool(work.fight) and row["role"] == work.fight_role and row["serves"] == [1, 2]
            if not fought:
                fresh.update(role=tags["role"], serves=list(tags["serves"]))
            folder = VAR / "studio" / STYLE / row["family"] / "1" / "track.json"
            meta = json.loads(folder.read_text(encoding="utf-8"))
            if all(meta[name] == value for name, value in fresh.items()):
                continue
            meta.update(fresh)                             # (its key stays: that was heard when it was staged)
            row.update(fresh)
            scratch = folder.with_suffix(".json.new")
            scratch.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
            scratch.replace(folder)
            changed += 1
        path.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return changed


def report() -> dict[str, Any]:
    """What is staged, counted: tracks and minutes in all, and by kind of place, by kind of
    moment, light and heavy."""
    rows = [row for path in sorted((VAR / "scores" / "staged").glob("*.json")) for row in json.loads(path.read_text(encoding="utf-8"))]
    minutes = lambda some: round(sum(row["seconds"] for row in some) / 60.0, 1)       # noqa: E731
    by_mood: dict[str, list] = {kind: [] for kind in kinds.KINDS}
    for row in rows:
        for mood in row["moods"]:
            by_mood[mood].append(row)
    roles = sorted({row["role"] for row in rows})
    return {
        "tracks": len(rows), "minutes": minutes(rows), "works": len({row["work"] for row in rows}),
        "by kind of place": {kind: {"tracks": len(some), "minutes": minutes(some), "light": sum(row["light"] for row in some),
                                    "heavy": sum(not row["light"] for row in some)} for kind, some in by_mood.items()},
        "by kind of moment": {role: {"tracks": len([row for row in rows if row["role"] == role]),
                                     "minutes": minutes([row for row in rows if row["role"] == role])} for role in roles},
        "light": len([row for row in rows if row["light"]]), "heavy": len([row for row in rows if not row["light"]]),
        "for a fight": len([row for row in rows if 2 in row["serves"]]),
        "loudest peak": max((row["peak"] for row in rows), default=0.0),
        "shortest": min((row["seconds"] for row in rows), default=0.0), "longest": max((row["seconds"] for row in rows), default=0.0),
    }


_SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 9, 10, 11), "phrygian": (0, 1, 3, 5, 7, 8, 10),
           "mixolydian": (0, 2, 4, 5, 7, 9, 10), "dorian": (0, 2, 3, 5, 7, 9, 10)}


def in_key(chroma: np.ndarray, tonic: str) -> float:
    """How much of some music's energy is on the notes of a key: 1 for all of it."""
    note, _, mode = tonic.partition(" ")
    first = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[note[0]] + (1 if note.endswith("#") else -1 if note.endswith("b") else 0)
    return float(sum(chroma[(first + step) % 12] for step in _SCALES[mode]))


IN_KEY = 0.62                  # less of a track than this on the notes of its work's key, and it is somewhere else


def key_of(mix: np.ndarray, tonic: str) -> str:
    """The key a track says it is in: its work's, unless the track has plainly gone somewhere
    else (the hymn in the middle of Jupiter is in E flat, not C), in which case the key it is
    heard to be in. The player uses the key to tell which tracks can ring on under which."""
    heard = analysis.estimate_key(mix, RATE)
    return tonic if in_key(heard.chroma, tonic) >= IN_KEY else heard.name


def check_track(folder: Path) -> dict[str, Any]:
    """Holds one staged track against what it should be, since nobody is listening tonight:
    that its recordings are the length its story says, that nothing passes full scale, that it
    has no long hole in it, that it is in tune, and that it sounds in the key its work is in.
    Returns what it measured, and under "wrong" anything that is not as it should be."""
    from . import read_track
    meta, parts = read_track(folder)
    wrong: list[str] = []
    bars = sum(section["bars"] for section in meta["sections"])
    frames = int(round(bars * meta["bar_frames"]))
    want = frames + int(round(meta["post_s"] * RATE))
    for channel, audio in parts.items():
        if len(audio) != want:
            wrong.append("%s is %d samples, not %d" % (channel, len(audio), want))
    mix = sum(audio[:frames] for audio in parts.values())
    peak = float(np.max(np.abs(mix)))
    if peak > 0.95:
        wrong.append("the parts together reach %.2f of full scale" % peak)
    curve = level_curve(mix)
    longest = run = 0
    for level in curve:
        run = run + 1 if level < -62.0 else 0
        longest = max(longest, run)
    if longest > 16:
        wrong.append("a hole of %.0f seconds" % (longest / 2.0))
    key = analysis.estimate_key(mix, RATE)
    if abs(key.tuning_cents) > 12.0:
        wrong.append("%.0f cents out of tune" % key.tuning_cents)
    share = in_key(key.chroma, meta["tonic"])
    if share < IN_KEY:
        wrong.append("only %d%% of it is on the notes of %s" % (round(share * 100), meta["tonic"]))
    return {"family": meta["family"], "seconds": round(frames / RATE, 1), "peak": round(peak, 3), "hole_s": longest / 2.0,
            "tuning_cents": round(float(key.tuning_cents), 1), "in_key": round(share, 2), "hears": key.name, "wrong": wrong}


def check(workers: int = 6) -> list[dict[str, Any]]:
    """Checks every staged track of real music. Returns what was measured for each."""
    folders = sorted(path.parent for path in (VAR / "studio" / STYLE).glob("real-*/1/track.json"))
    with ProcessPoolExecutor(max_workers=max(1, min(workers, 6))) as pool:
        return list(pool.map(check_track, folders))


# How much each work is wanted when there is not room for all of them: the ones everybody knows
# and the ones that suit a game best come first; the choruses of the Mass (a sampled choir
# is the weakest of the studio's sounds) and Bruckner's half-hours come last.
WANTED = {
    "beethoven-5-1": 2.0, "beethoven-7-2": 2.0, "beethoven-6-1": 1.8, "beethoven-6-2": 1.6, "beethoven-6-3": 1.6,
    "beethoven-6-4": 2.0, "beethoven-6-5": 1.6, "beethoven-9-2": 1.8, "beethoven-3-2": 1.7, "beethoven-5-3": 1.6,
    "beethoven-5-4": 1.5, "beethoven-7-4": 1.7, "beethoven-7-1": 1.4, "beethoven-9-1": 1.5, "beethoven-9-3": 1.4,
    "beethoven-3-1": 1.4, "beethoven-8-2": 1.4, "beethoven-4-2": 1.3, "egmont": 1.8, "coriolan": 1.7, "tell": 2.0,
    "dvorak-9-1": 1.6, "dvorak-9-2": 1.9, "dvorak-9-3": 1.6, "dvorak-9-4": 1.8, "brahms-3-3": 1.9, "brahms-4-4": 1.7,
    "brahms-1-4": 1.6, "brahms-1-1": 1.5, "brahms-4-1": 1.5, "brahms-4-2": 1.5, "brahms-2-3": 1.4, "brahms-3-1": 1.3,
    "jupiter": 1.7, "capriccio": 1.6, "beach-gaelic-2": 1.4, "beach-gaelic-1": 1.3, "boulanger-matin": 1.4,
    "brandenburg-3-1": 1.4, "brandenburg-4-1": 1.3, "schubert-5-1": 1.3, "haydn-104-1": 1.2,
    "mass-14": 1.2, "mass-01": 1.0, "mass-13": 1.0,
}


def pick(minutes: float) -> list[str]:
    """The staged tracks to take when there is room for only `minutes` of them: the families,
    most wanted first. Every kind of moment that is scarce (a fight, a storm, a cave, the
    night, an inn) is taken first from the works most wanted; then the kinds of place take
    turns, each taking its most wanted track that is not in yet, light and heavy by turns."""
    rows = [row for path in sorted((VAR / "scores" / "staged").glob("*.json")) for row in json.loads(path.read_text(encoding="utf-8"))]

    def want(row: dict[str, Any]) -> float:
        base = WANTED.get(row["work"], 0.6 if row["work"].startswith(("mass-", "bruckner-")) else 1.0)
        return base + (0.05 if any(part["story"] == "rise" for part in row["sections"]) else 0.0)

    rows.sort(key=lambda row: (-want(row), row["family"]))
    taken: list[dict[str, Any]] = []
    total = 0.0

    def take(row: dict[str, Any]) -> None:
        nonlocal total
        taken.append(row)
        total += row["seconds"] / 60.0

    for role, most in (("battle", 12), ("boss", 5), ("storm", 5), ("depths", 5), ("night", 8), ("ember", 6)):
        for row in [row for row in rows if row["role"] == role][:most]:
            if total < minutes * 0.45:
                take(row)
    turn = 0
    while total < minutes:
        added = False
        for kind in kinds.KINDS:
            have = [row for row in taken if kind in row["moods"]]
            light = sum(row["light"] for row in have) <= len(have) / 2
            left = [row for row in rows if row not in taken and kind in row["moods"] and row["role"] == "wander"]
            choice = next((row for row in left if row["light"] == light), None) or (left[0] if left else None)
            if choice is not None and total < minutes:
                take(choice)
                added = True
        turn += 1
        if not added:
            break
    return [row["family"] for row in taken]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m freerock.studio.scores", description="Real scores, played and staged.")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("fetch", help="fetch the scores into var/scores")
    staging = actions.add_parser("stage", help="play and stage works (all of them, or those named)")
    staging.add_argument("works", nargs="*")
    staging.add_argument("--workers", type=int, default=6)
    staging.add_argument("--keep-since", type=float, default=None, metavar="TIME",
                         help="leave alone the works staged since this moment (seconds since 1970): to go on with a run that was stopped")
    actions.add_parser("report", help="count what is staged")
    actions.add_parser("check", help="hold every staged track against what it should be")
    actions.add_parser("retag", help="bring the staged tracks' tags up to date with the table, without playing anything again")
    picking = actions.add_parser("pick", help="the staged tracks to take when there is room for only so many minutes")
    picking.add_argument("minutes", type=float)
    actions.add_parser("list", help="the works in the table")
    args = parser.parse_args(argv)
    if args.action == "fetch":
        print("%d score files are in %s" % (fetch(), VAR / "scores"))
    elif args.action == "list":
        for work in WORKS.values():
            print("%-18s %-11s %-7s %-5s %s" % (work.id, ",".join(work.moods), work.role, "light" if work.light else "", work.title))
    elif args.action == "report":
        print(json.dumps(report(), indent=1))
    elif args.action == "retag":
        print("%d staged tracks were given new tags" % retag())
    elif args.action == "check":
        found = check()
        for row in found:
            if row["wrong"]:
                print("%-30s %s" % (row["family"], "; ".join(row["wrong"])))
        print("%d tracks checked, %d with something wrong; tuning within %.0f cents; least in key %d%%" % (
            len(found), sum(bool(row["wrong"]) for row in found), max((abs(row["tuning_cents"]) for row in found), default=0.0),
            round(min((row["in_key"] for row in found), default=0.0) * 100)))
        return 1 if any(row["wrong"] for row in found) else 0
    elif args.action == "pick":
        for family in pick(args.minutes):
            print(VAR / "studio" / STYLE / family / "1")
    else:
        wanted = args.works or list(WORKS)
        unknown = [name for name in wanted if name not in WORKS]
        if unknown:
            parser.error("no such work: %s" % ", ".join(unknown))
        if args.keep_since is not None:
            record = VAR / "scores" / "staged"
            wanted = [name for name in wanted if not ((record / (name + ".json")).is_file()
                                                      and (record / (name + ".json")).stat().st_mtime >= args.keep_since)]
        # The most wanted first, so that a run that is cut short has the best of it done.
        wanted.sort(key=lambda name: -WANTED.get(name, 0.6 if name.startswith(("mass-", "bruckner-")) else 1.0))
        failed = []
        with ProcessPoolExecutor(max_workers=max(1, min(args.workers, 6))) as pool:
            jobs = {pool.submit(stage_work, name): name for name in wanted}
            for job in as_completed(jobs):
                name = jobs[job]
                error = job.exception()
                if error is not None:
                    failed.append(name)
                    print("FAILED %s: %r" % (name, error), flush=True)
                    continue
                for row in job.result():
                    print("%-30s %5.0f s  %-18s %-7s %-5s %s" % (row["family"], row["seconds"], ",".join(row["moods"]), row["role"],
                                                                 "light" if row["light"] else "", " ".join(
                        "%s:%d(%.0f)" % (part["story"], part["bars"], part["lufs"]) for part in row["sections"])), flush=True)
        if failed:
            print("%d works failed: %s" % (len(failed), ", ".join(sorted(failed))))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
