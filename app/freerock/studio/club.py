"""The dance floor's desk: what the house writer writes, played by real instruments in REAPER.

studio.house writes a track as calls to the studio's own synthesiser: this sound plays this
note here, this drum is struck there. That synthesiser is what was turned down by ear ("figure
out how to make house music not suck", 2026-11-16); the notes are not. So here the writer is
listened to instead of played: every note and every stroke it asks for is taken down, and then
played by instruments that are instruments.

    the synth sounds      Surge XT's own patches (sounds.HOUSE), each at the octave it was measured to need
    the real instruments  Muse Sounds: a grand piano, electric pianos, marimba, harp, flute, strings, brass
    the drums             the drum-machine recordings the writer already used (MckAudio's TR-8 set, CC0), in the sampler
    the risers and air    what the writer makes out of noise, laid in as a recording

What the writer asks for is taken down as the take's music sheet (`write`, score.Sheet), and
the desk plays the sheet (`perform`): a sheet can be revised and played again. A sound in the
writer has a brightness for every note (how far its filter is open: it opens as a track builds);
on the sheet that is the part's low-pass, an effect mark that moves with the music, and where
the form takes the bottom away (a rise, the breakdown) the part's high-pass is marked too.

Under each stroke of the kick the bass, the pad and the chords give way and come back (the
drawn volume curve of studio.build, deeper here: this is the music that curve comes from).

    cd app && uv run --no-sync --with numba python -m freerock.studio.club pastoral-01/1 [...]
    cd app && uv run --no-sync --with numba python -m freerock.studio.club --list        what the plan holds

(numba is asked for because studio.house still brings the old synthesiser in with it.)
"""
from __future__ import annotations

import bisect
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import analysis, forever
from . import RATE, desk, house, kicks, muse, reaper, sfz, sounds, stage_root, write_track
from .score import Note, Sheet, Voice

VAR = Path(__file__).resolve().parents[3] / "var"
PROJECTS = VAR / "reaper" / "projects"
BEAT = house.BEAT
# What plays each of the writer's sounds: (the writer's table, its name for the sound) -> a written instrument the
# desk knows (sounds.SOUNDS for the synths, muse.PARTS for the real ones).
PLAYED = {
    ("bass", "sub"): "house sub", ("bass", "pluck"): "house bass pluck", ("bass", "saw"): "house bass saw", ("bass", "square"): "house bass square",
    ("bass", "fm"): "house bass fm", ("bass", "reese"): "house bass wide",
    ("bass", "harsh"): "house bass wide", ("bass", "harsh saw"): "house bass saw",      # the twin that comes in late in a drop
    ("keys", "piano"): "house piano", ("keys", "keys"): "electric piano", ("keys", "stab"): "house stab",
    ("keys", "pluck"): "house pluck", ("keys", "bell"): "house bell", ("keys", "glass"): "house glass", ("keys", "harp"): "harp",
    ("keys", "marimba"): "marimba", ("keys", "oud"): "guitar", ("keys", "string"): "guitar", ("keys", "brass"): "brass",
    # (The tunes the pan flute, the flute and the marimba sang were heard as cheesy, 2026-11-17: synths sing them now.)
    ("lead", "saw"): "house lead saw", ("lead", "super"): "house lead super", ("lead", "hollow"): "house lead hollow", ("lead", "pipe"): "house lead hollow",
    ("lead", "whistle"): "house lead sine", ("lead", "flute"): "house lead sine", ("lead", "bell"): "house bell", ("lead", "glass"): "house glass",
    ("lead", "keys"): "wurly", ("lead", "pluck"): "house pluck", ("lead", "marimba"): "house pluck", ("lead", "harp"): "harp", ("lead", "oud"): "guitar",
    ("lead", "string"): "harp", ("lead", "brass"): "trumpet",
    ("pad", "warm"): "house pad warm", ("pad", "strings"): "strings slow", ("pad", "super"): "house pad super", ("pad", "glass"): "house pad glass",
    ("pad", "hollow"): "house pad hollow",
}
RESONANCE = {"rhythm": 0.35, "texture": 0.15, "lead": 0.1, "bass": 0.0}       # how far each channel's low-pass sings as it moves


def cutoff(bright: float) -> float:
    """Where a part's low-pass stands for a note of this brightness (the writer's 0 to 1, as it opens over a track), in
    Hz, set by the records studied (the house study's filter timeline): 350 Hz as a track begins (0.12), 1.6 kHz as its
    open ends (0.45), 2 to 5 kHz across a theme (0.5 to 0.7), 550 Hz to 1.3 kHz through the breakdown (0.22 to 0.4), wide
    open at a drop (1). (2026-11-18: the brightness was four fixed cuts, so a part's tone moved in steps and a drop was
    the colour of its theme; "too much high hat and not enough dynamic sound".)"""
    return min(max(350.0 * math.exp(4.594 * (bright - 0.12)), 200.0), 20000.0)
KICKS = ("kick", "kick2", "punch", "boom")
HATS_SOUNDS = ("hat", "open", "maracas", "cabasa", "tambourine", "ride")      # the drums on the hats' own line
# How far each channel is turned down under a stroke of the kick, as a part of its level (studio.build.DUCK is the
# orchestra's: 0.56 for its bass). The writer's own pump took 55 to 75% of the bass away and half of the pad.
DUCK = {"bass": 0.2, "texture": 0.35, "rhythm": 0.45, "lead": 0.85}
# How deep that goes in each part of the story, as a share of it (2026-11-18: "not enough dynamic sound", "study top dj
# techniques like deadmau5 and daft punk": the pump is the drop's, all the way there, less in a theme, least where the
# groove is only arriving). At a drop the sub goes down 14 dB and the chords and pads 7 and 9, back in time for the
# off-beat (the study of the records: the sub -12 to -18 dB, the chords and pads -6 to -12, swelling back).
PUMP = {"open": 0.4, "theme": 0.7, "rise": 0.5, "moment": 1.0, "close": 0.7}
# ...and how long each takes to come back, in beats. The bass is back in a third of a beat (about 150 ms at 110 BPM,
# where the records studied put it), so the low end is clear for the kick and full again before the off-beat; the
# pad takes three quarters of one, which is the pump that is heard.
RECOVER = {"bass": 0.33, "texture": 0.85, "rhythm": 0.7, "lead": 0.5}
# Where each channel sits where the track is fullest (LUFS), as the writer's own mix had them.
# (The kick and the bass 1 dB up, 2026-11-17, evening, played: "just a bit light and wimpy in general", "in all genres";
# then half a dB more: "go a little harder this is not world of fairy craft".)
PLACE = {"drums": -12.5, "bass": -15.0, "rhythm": -20.0, "lead": -19.0, "texture": -22.0}
CALM = {"drums": -18.0, "bass": -18.0, "lead": -18.0, "texture": -20.0}        # an inn, the night


# (Which lead is whose, 2026-11-24, 17:50: thirteen of House's own leads in one drop, its other channels the same, measured hard against sweet (tools/hardness.py): sync -5, anthem -6, acid -7, the throat -7,
# ladder -9, stack -9, the driven pluck -11, the growl -12, the factory's saw -12.5, the turning pulses -16.5, struck metal -18. Metal and the pulses lead no act now; the growl is a dark song's soft voice.)
# Whose instruments a House song has (2026-11-24: "house still needs to work on that main synth lead sound", "and also should use differrent bands"; of 196
# songs 84 were led by the saw and 51 by the supersaw, one sound within 1 dB in every octave). What the writer names is played by what the act has: its big
# lead at the drops, the second synth that joins it, the soft lead of its themes, its chords, its bass, its pad, and its drum machine. "" is House's own act,
# the sound of every song until now, its two big leads made anew (MAIN_LEADS).
@dataclass(frozen=True)
class Act:
    big: str                           # the lead of the drops
    late: str                          # the second synth, half way through a drop
    soft: str                          # the lead of the themes and the rises
    keys: tuple[str, ...]              # the chords and the figures, by turns
    bass: tuple[str, ...] = ()         # the bass that is heard, by turns (a song whose bass is the sub alone keeps it)
    pad: tuple[str, ...] = ()
    machine: str = ""
    drive: float = 0.0                 # how hard its drums and its bass are driven at the desk (0 to 1)
    cut: tuple[str, ...] = ()          # the two voices a drop's riff is dealt to, stroke by stroke, beside the big one (`cut_up`)


ACTS: dict[str, Act] = {
    "warehouse": Act("house lead acid", "house lead ladder", "house lead growl", ("house stab rave",), ("house bass saw", "house bass acid"), ("house pad hollow",), "909", drive=0.8),
    "undercroft": Act("house lead ladder", "house lead fifth", "house lead growl", ("house stab dub",), ("house bass wide",), ("house pad hollow",), "808", drive=0.7),
    "foundry": Act("house lead razor", "house lead squelch", "house lead reed", ("house stab clang",), ("house bass fm", "house bass grind"), ("house pad hollow",), "606", drive=0.8),
    "signal": Act("house lead sync", "house lead fifth", "house lead vox", ("house stab rave",), ("house bass square",), ("house pad drone",), "909", drive=0.6),
    "monolith": Act("house lead hoover", "house lead fifth", "house lead vox", ("house stab slab",), ("house bass grind",), ("house pad drone",), "909", drive=0.7),
    "vesper": Act("house lead vox", "house lead reed", "bass clarinet", ("electric piano",), ("house bass fm",), ("choir",), "707"),
    "velvet": Act("house lead reed", "house lead vox", "wurly", ("rhodes", "electric piano"), ("house bass pluck",), ("house pad warm",), "707"),
    "strobe": Act("house lead pluck", "house lead stack", "house pluck", ("house pluck",), ("house bass fm",), ("house pad super",), "606"),
    "chamber": Act("cello", "viola", "bass flute", ("dream piano",), ("house bass pluck",), ("strings slow",), "808"),
    "brass": Act("trumpet", "trombone", "clarinet", ("rhodes", "wurly"), ("house bass pluck",), ("house pad warm",), "707"),
    "bazaar": Act("sitar", "shenai", "koto", ("dulcimer",), ("house bass fm",), ("house pad hollow",), "808"),
    # (of the instruments found on 2026-11-24: a cello's and a double bass's bows as a synthesiser's oscillators, all of it; a saxophone torn by an amplifier and a jazz bass, driven)
    "cyborg": Act("heart lead", "house lead squelch", "heart pluck", ("heart stab",), ("iron bass",), ("heart pad",), "909", drive=0.7),
    # (The junkyard's lead was a baritone saxophone torn by an amplifier, over a jazz bass: 2026-11-24, 21:20, read stroke by stroke: its long notes are in tune and its short ones, from G sharp 3 up, scoop from
    # 90 to 185 cents under and are over before they arrive: three songs. It has the squelch now; the saxophone is kept for long notes.)
    "junkyard": Act("house lead squelch", "house lead hoover", "house lead reed", ("house stab clang",), ("house bass grind",), ("house pad drone",), "808", drive=0.7),
    # (2026-11-24, 22:00: the soft acts measured -13 to -21, as sweet as the sweetest old songs; what is left of a night when the hard ones have gone home: a smoking reed, a contrabass flute and driven tines
    # over a tube; a foghorn, a baritone saxophone's long notes and plucked celli over a fretless bass and a machine's hum.)
    "cellar": Act("house lead smoke", "house lead reed", "contrabass flute", ("house keys ash",), ("house bass tube",), ("house pad breath",), "606", drive=0.3),
    "gallows": Act("house lead horn", "house lead vox", "bari sax", ("celli pizz",), ("fretless",), ("house pad drone",), "808", drive=0.35),
    # (...a bow near the bridge, a saxophone's growl, a dry knock over a double bass; a worn tape, a saxophone played under its breath, dub chords. On Dead Hours, hard against sweet, theme and drop: switchyard -7
    # and -6, gallows -8 and -7 (the darkest of all, +6.5 on that axis), cellar -9 and -12, beside vesper's -13 and -4 and velvet's -14 and -13; the mortuary's first writing, a bassoon and a parlour's piano, -16.)
    "mortuary": Act("house lead bow", "house lead growl", "growl sax", ("house keys bone",), ("acoustic bass",), ("house pad breath", "house pad hollow"), "606", drive=0.35),
    "switchyard": Act("house lead tape", "house lead smoke", "subtone sax", ("house stab dub",), ("house bass wide",), ("house pad hollow",), "808", drive=0.3),
    # (2026-11-25: five whose riffs are cut up, or are led by a machine of another kind: a throat, an eight-bit wave, a filter screaming on the note's own overtone, a folded sine, saws that beat.)
    "chopshop": Act("house lead talk", "house lead fifth", "house lead growl", ("house stab slab",), ("house bass grind",), ("house pad drone",), "909", drive=0.7,
                    cut=("house lead razor", "house lead squelch")),
    "arcade": Act("house lead chip", "house lead hoover", "house lead reed", ("house stab rave",), ("house bass square",), ("house pad hollow",), "606", drive=0.7,
                  cut=("house lead acid", "house lead sync")),
    "kennel": Act("house lead scream", "house lead fifth", "house lead vox", ("house stab clang",), ("house bass acid",), ("house pad drone",), "808", drive=0.75,
                  cut=("house lead talk", "house lead razor")),
    "quarry": Act("house lead fold", "house lead ladder", "house lead growl", ("house stab slab",), ("house bass wide",), ("house pad drone",), "808", drive=0.75),
    "tunnel": Act("house lead reese", "house lead sync", "house lead reed", ("house stab dub",), ("house bass wide",), ("house pad drone",), "606", drive=0.7),
}
# The acts a moment may have, in the order they are given out (a calm one's lead is soft).
# (2026-11-24, 19:35: every act measured on one song, hard against sweet: the hard ones +9 to -2, warehouse's acid line far the hardest, and the soft ones -13 to -21, as sweet as the sweetest old songs, on a dark
# song as on a light one: brass -21, velvet -21, bazaar -17, vesper and chamber -16, strobe -13. The soft ones play inns, camps and nights, and light songs; a dark walk, a town and a cave are the hard ones'.)
ACTS_FOR = {"calm": ("velvet", "vesper", "strobe", "chamber", "bazaar"), "fight": ("foundry", "warehouse", "undercroft", "monolith", "signal", "cyborg", "junkyard"),
            "town": ("warehouse", "signal", "junkyard", "undercroft", "cyborg"), "depths": ("undercroft", "foundry", "cyborg", "monolith"),
            "light": ("strobe", "velvet", "bazaar", "vesper", "chamber", "brass"),
            "heavy": ("warehouse", "undercroft", "monolith", "foundry", "signal", "cyborg", "junkyard"),
            "after": ("cellar", "gallows", "switchyard", "mortuary"), "cut": ("chopshop", "arcade", "kennel", "quarry", "tunnel")}
# A family's first take is House's own act; its other takes, every take of the families planned after ACTS_AFTER, and of those that had no take yet when the acts
# came in (ACTS_ALSO), another's.
ACTS_AFTER = "depths-09"
ACTS_ALSO = frozenset(("ember-05", "ember-06", "ember-07", "ember-08", "camp-05", "camp-06", "camp-07", "camp-08", "depths-05", "depths-06", "depths-07", "depths-08",
                       "boss-04", "boss-05", "boss-06", "night-05", "night-06", "night-07", "night-08", "town-04", "desert-05", "jungle-02", "jungle-04", "jungle-05",
                       "boss-02", "battleground-02"))
# (...and of the dark calm ones that had no take when the acts that are not sweet came in, every take one of those.)
ACTS_AFTER_HOURS = frozenset(("camp-07", "camp-11", "camp-12", "ember-11", "ember-12", "night-07", "night-11", "night-12"))
# House's own two big leads made anew: what is played where a sheet names the first.
MAIN_LEADS: dict[str, str] = {}


def act_of(fam: house.Family, take: int) -> str:
    """Whose instruments a take of a family has (ACTS)."""
    if fam.act and take <= 1:
        return fam.act
    names = [each.name for each in house.PLAN]
    at = names.index(fam.name) if fam.name in names else 0
    if fam.act:                        # a hard song's other takes are other hard acts'
        kin = ACTS_FOR[next(each for each in ("fight", "after", "calm", "cut") if fam.act in ACTS_FOR[each])]
        return kin[(kin.index(fam.act) + take - 1) % len(kin)]
    if fam.name in ACTS_AFTER_HOURS:
        return ACTS_FOR["after"][(at + take) % len(ACTS_FOR["after"])]
    if take <= 1 and fam.name not in ACTS_ALSO and at <= names.index(ACTS_AFTER):
        return ""
    kind = ("calm" if fam.role in house.CALM_ROLES else "fight" if fam.role in ("battle", "boss", "storm", "battleground") else fam.role if fam.role in ACTS_FOR
            else "light" if fam.light else "heavy")
    return ACTS_FOR[kind][(at + take) % len(ACTS_FOR[kind])]


def parts_of_the_lead(heard: "Heard", sections: list[tuple[str, int, int]]) -> dict[tuple[str, str], str]:
    """Which of a song's lead voices is the big one (the most of the drops is its), which joins it there ("late") and which sings the rest ("soft")."""
    drops = [(first * house.BAR, (first + count) * house.BAR) for story, first, count in sections if story == "moment"]
    counts = {(table, sound): (sum(1 for note in notes if any(a <= note[0] < b for a, b in drops)), len(notes))
              for (channel, table, sound), notes in heard.notes.items() if channel == "lead"}
    if not counts:
        return {}
    big = max(counts, key=lambda each: (counts[each][0], counts[each][1], each))
    return {each: "big" if each == big else "late" if inside > 0.6 * whole else "soft" for each, (inside, whole) in counts.items()}


def played(table: str, sound: str, act: str = "", seed: int = 0, part: str = "") -> str:
    """What plays a sound of the writer's in an act (`part`, for a lead: `parts_of_the_lead`)."""
    first = PLAYED[(table, sound)]
    if not act or (table, sound) in (("bass", "sub"), ("bass", "harsh"), ("bass", "harsh saw")):
        return first
    has = ACTS[act]
    if table == "lead":
        return {"big": has.big, "late": has.late}.get(part, has.soft)
    turns = {"keys": has.keys, "bass": has.bass, "pad": has.pad}[table] or (first,)
    return turns[(seed + sorted(name for kind, name in PLAYED if kind == table).index(sound)) % len(turns)]


def reached(instrument: str, pitch: int) -> int:
    """A note within an instrument's reach, an octave or more away where it has to be (a saxophone does not sing at the top of a synth)."""
    from .orchestra import INSTRUMENTS
    inst = INSTRUMENTS.get(instrument)
    if inst is None:
        return pitch
    while pitch > inst.high:
        pitch -= 12
    while pitch < inst.low:
        pitch += 12
    return pitch


# How hard a stroke of a lead of House's own is on the beat, the eighth and the sixteenth, before it is squared; a hard song's riff is hammered nearly even (2026-11-24, 17:00: at
# 1, 0.82 and 0.66 the recorded riffs of Riot Line, Blast Furnace and Bone Saw had every stroke off the beat 4 to 7 dB under the beat's: a pulse on the kick and ghosts
# between, where the two led by a saxophone's and a cello's recordings, which had no accents, were even).
ACCENTS, HAMMERED = (1.0, 0.9, 0.8), (1.0, 0.97, 0.95)


# The chords that are played with their third: a dub's, a dark minor chord behind a band-pass (2026-11-24, Sump: with a root, a fifth and an octave the peak of its filter rang the fifth's third overtone and the
# root's fifth, 13 in 100 of it a major second and 7 a major third over the root: a song in phrygian whose chords were neither, 63% in its key).
THIRDS = ("house stab dub",)


def with_thirds(notes: list[Note], scale: set[int]) -> list[Note]:
    """Each chord's top note moved to its third, as the key has it, over its other notes; a chord of fewer than three notes is left as it is."""
    struck: dict[int, list[Note]] = defaultdict(list)
    for note in notes:
        struck[round(note.start * 16)].append(note)
    for chord in struck.values():
        chord.sort(key=lambda note: note.pitch)
        if len(chord) < 3:
            continue
        # (Its root is the note that has its fifth in the chord, and that may be under it: 2026-11-25, Third Rail's B, E and B were given the third of B, and a D over E's own fifth rang an F sharp in E phrygian, 64% in the key.)
        has = {note.pitch % 12 for note in chord}
        root = next((note.pitch for note in chord if (note.pitch + 7) % 12 in has), chord[0].pitch)
        third = next((step for step in (3, 4) if (root + step) % 12 in scale), None)
        if third is None or any((note.pitch - root) % 12 in (3, 4) for note in chord):
            continue
        chord[-1].pitch = root + 12 + third
    return notes


def accented(notes: list[Note], form: list[dict], hammered: bool = False) -> None:
    """A lead of House's own played as a hand plays it: the beat's note harder than the eighth's and that than the sixteenth's, the whole harder as a drop goes
    on, so that its filter, which follows how hard it is struck, opens; and every fourth note tied to the next where they are near, so that it slides."""
    beat, eighth, sixteenth = HAMMERED if hammered else ACCENTS
    for index, note in enumerate(notes):
        near = lambda step: abs(note.start / step - round(note.start / step)) < 0.02      # noqa: E731
        accent = beat if near(1.0) else eighth if near(0.5) else sixteenth
        section = next((each for each in form if each["first"] * 4.0 - 1e-6 <= note.start < (each["first"] + each["bars"]) * 4.0), None)
        along = (note.start - section["first"] * 4.0) / max(section["bars"] * 4.0, 1.0) if section and section["story"] == "moment" else 0.4
        note.loud = min(max(note.loud * ((0.68 + 0.32 * along) * accent) ** 2, 1e-4), 1.0)
        after = notes[index + 1] if index + 1 < len(notes) else None
        if after is not None and index % 4 == 3 and after.pitch != note.pitch and 0.0 <= after.start - note.start - note.length < 0.2:
            note.length = after.start - note.start + 0.06


# A riff cut up (2026-11-25: "house is a little better keep iterating"; the study of the records Sky names: a riff whose every stroke is another machine's). Who hammers it, who has its
# turns and the second of two strokes that run together, and who answers in the last half bar of two, by eights of bars through a song's drops: the same riff, and another voice of it each time.
CUT_ROLES = ((0, 1, 0), (0, 1, 2), (1, 2, 0), (0, 2, 1), (2, 1, 0), (0, 1, 2))
CUT_FILLS = ("x.xxx.xx", "xx.xx.xx", "x.x.xxxx", "xxx.xxx.")          # what is said in the half bar a riff leaves out, every second eight bars (sixteenths)
CUT_NAMES, CUT_SEATS = ("", "-two", "-three"), (0.0, -0.3, 0.3)


def cut_up(notes: list[Note], form: list[dict], seed: int) -> list[list[Note]]:
    """A lead's notes dealt to three voices. What is outside the drops is the first's. In a drop, two bars at a time: the note that is hammered is one voice's, the strokes that leave it and the
    second of two that run together are another's, and the last half bar is answered by a third; who is which changes every eight bars (CUT_ROLES), and the half bar the riff leaves out at the
    end of each sixteen is filled by whoever answers, an octave under. A stroke ends before the next one of any voice begins."""
    out: list[list[Note]] = [[], [], []]
    drops = [(section["first"] * 4.0, (section["first"] + section["bars"]) * 4.0) for section in form if section["story"] == "moment"]
    done = 0                                             # the eights of bars gone by that had a riff in them
    for a, b in drops:
        for block in range(int((b - a) // 32.0)):
            first = a + 32.0 * block
            mine = sorted((note for note in notes if first - 0.05 <= note.start < first + 31.95), key=lambda note: note.start)
            if not mine:
                continue
            hammer, turn, answer = CUT_ROLES[done % len(CUT_ROLES)]
            done += 1
            pitches: list[int] = []
            for phrase in range(4):
                said = [note for note in mine if phrase * 8.0 <= note.start - first + 0.05 < (phrase + 1) * 8.0]
                if not said:
                    continue
                struck = [note.pitch for note in said]
                pitches.append(max(sorted(set(struck)), key=struck.count))
                before = None
                for note in said:
                    at = note.start - first - phrase * 8.0
                    runs = before is not None and note.start - before <= 0.3
                    out[answer if at >= 5.95 else turn if note.pitch != pitches[-1] or runs else hammer].append(note)
                    before = note.start
            if block % 2 == 1 and first + 32.0 < b and not any(note.start >= first + 29.95 for note in mine) and any(note.start >= first + 24.0 for note in mine):
                text = CUT_FILLS[(seed + done) % len(CUT_FILLS)]
                pitch, loud = pitches[-1] - 12 if pitches[-1] - 12 >= 40 else pitches[-1], max(note.loud for note in mine)
                out[answer if answer != hammer else turn] += [Note(first + 30.0 + 0.25 * at, 0.2, pitch, loud * (0.8 + 0.2 * at / 7.0)) for at, what in enumerate(text) if what == "x"]
    dealt = {id(note) for voice in out for note in voice}
    out[0] += [note for note in notes if id(note) not in dealt]
    every = sorted(((note.start, index, note) for index, voice in enumerate(out) for note in voice), key=lambda each: each[0])
    for (start, voice, note), (after, other, _) in zip(every, every[1:]):
        if other != voice and note.start + note.length > after - 0.02 and after - start > 0.1:
            note.length = max(after - 0.02 - start, 0.08)                  # (not through another voice's stroke)
    return [sorted(voice, key=lambda note: note.start) for voice in out]


def with_the_first(notes: list[Note], dealt: list[list[Note]], form: list[dict]) -> list[Note]:
    """A second synth's notes, where the riff is cut up: with the strokes of the voice that is the riff's own, and no other."""
    drops = [(section["first"] * 4.0, (section["first"] + section["bars"]) * 4.0) for section in form if section["story"] == "moment"]
    starts = sorted(note.start for note in dealt[0])
    inside = lambda beat: any(a - 0.05 <= beat < b for a, b in drops)                  # noqa: E731
    near = lambda beat: any(abs(starts[k] - beat) < 0.06 for k in (bisect.bisect_left(starts, beat) - 1, bisect.bisect_left(starts, beat)) if 0 <= k < len(starts))      # noqa: E731
    return [note for note in notes if not inside(note.start) or near(note.start)]


@dataclass
class Heard:
    """What the writer asked to be played."""
    notes: dict[tuple[str, str, str], list[tuple[float, float, float, float, float, float]]] = field(default_factory=lambda: defaultdict(list))
    hits: list[tuple[str, str, float, float, float]] = field(default_factory=list)      # drum, machine, seconds, level, pan
    airs: list = field(default_factory=list)       # what the texture is besides its notes: risers, wind, drips (house.Air)
    # What each part is played by, where its sheet says: (channel, table, sound) -> the written instrument (else PLAYED).
    played: dict[tuple[str, str, str], str] = field(default_factory=dict)
    # Each part's effect marks and their settings, from its sheet (score.EFFECTS): (channel, table, sound) -> (marks, settings).
    marks: dict[tuple[str, str, str], tuple[dict, dict]] = field(default_factory=dict)
    drive: float = 0.0             # how hard its act's drums are driven (Act.drive)
    rest: float = 49.0             # where a hard act's kick comes to rest, in Hz (kicks.rest)


class _Drum:
    def __init__(self, name: str, machine: str):
        self.name, self.machine = name, machine


def listen(track: house.Take) -> Heard:
    """Has a take written, taking down every note and stroke instead of playing it. The
    writer's own synthesiser is stood in for while it writes, and put back."""
    heard = Heard()
    # The writer's tables share some sounds (the same plucked string is a key and a lead), so a sound is looked up in
    # the table of the channel playing it first.
    tables = {"bass": house.BASS, "keys": house.KEYS, "lead": house.LEADS, "pad": house.PADS}
    own = {"bass": "bass", "rhythm": "keys", "lead": "lead", "texture": "pad"}
    names: dict[int, tuple[str, str]] = {}
    for table, sound_names in tables.items():
        for name, made in sound_names.items():
            names.setdefault(id(made), (table, name))

    def named(patch) -> tuple[str, str]:
        table = own.get(channel[0], "")
        for name, made in tables.get(table, {}).items():
            if made is patch:
                return table, name
        return names[id(patch)]
    channel = [""]
    synth = house.synth
    kept = {name: getattr(synth, name) for name in ("play", "hit", "drum", "hall", "chorus", "echo")}

    def play(out, patch, at, length, pitch, level=0.5, pan=0.0, seed=0, glide_from=None, bright=1.0):
        if id(patch) not in names:
            # A sound of the weather's own (the drips in a cave): it stays in the recording of the air.
            return kept["play"](out, patch, at, length, pitch, level, pan, seed, glide_from, bright)
        table, name = named(patch)
        heard.notes[(channel[0], table, name)].append((float(at), float(length), float(pitch), float(level), float(pan), float(bright)))

    def drum(name, machine="909"):
        return _Drum(name, machine)

    def hit(out, sound, at, level=0.8, pan=0.0, speed=1.0):
        if not isinstance(sound, _Drum):
            return kept["hit"](out, sound, at, level, pan, speed)          # the crackle of a fire: part of the air
        # The writer strikes its kick dry and everything else into a small room.
        heard.hits.append((sound.name, sound.machine, float(at), float(level), float(pan)))

    same = lambda audio, *told, **more: audio      # noqa: E731  (the echo, the chorus and the hall are the desk's now)
    kept_trim = house.trim
    synth.play, synth.hit, synth.drum, synth.hall, synth.chorus, synth.echo = play, hit, drum, same, same, same
    house.trim = lambda sound, pitch: 1.0          # every instrument is brought to one level at the desk
    try:
        for part in ("drums", "bass", "rhythm", "lead"):
            channel[0] = part
            getattr(track, part)()
        channel[0] = "texture"
        track.texture(air=False)                   # the pad's notes; its air is played by the desk (`air_lines`)
        heard.airs = track.airs()
    finally:
        for name, real in kept.items():
            setattr(synth, name, real)
        house.trim = kept_trim
    return heard


def kit_file(machine: str, drums: list[str]) -> tuple[Path, dict[str, int]]:
    """The sampler's instrument for a drum machine: one key for each drum the take uses."""
    keys = {name: 36 + index for index, name in enumerate(sorted(drums))}
    rows = ["// Written by FreeRock's studio (studio/club.py): MckAudio's TR-8 recordings (CC0), one drum to a key.",
            "<control>", "default_path=%s/" % house.synth.TR8.resolve(), "<global>", "loop_mode=one_shot ampeg_release=0.08 pitch_keytrack=0"]
    for name, key in keys.items():
        have = house.synth._FILES[name]
        rows.append("<region> key=%d sample=%s.wav" % (key, have.get(machine) or next(iter(have.values()))))
    return sfz.write("house kit %s %s" % (machine, "-".join(sorted(drums))[:60]), "\n".join(rows) + "\n"), keys


def _loud(levels: list[float]) -> list[float]:
    """The writer's levels (a part of full strength) as how hard a note is struck: the hardest of a voice is 0.9."""
    top = max(max(levels), 1e-9)
    return [min(max(0.9 * math.sqrt(level / top), 0.08), 1.0) for level in levels]


SPAN = 4            # bars: a voice's level is read four at a time (a house phrase is eight, every part a whole number of them)
UNDER = 0.6         # a note written under this part of the loudest in its four bars is a line under the tune: a doubling, an echo
SUBBED = ("house bass pluck", "house bass saw", "iron bass", "driven bass", "house bass grind")      # the basses that are heard more than felt: a sine goes under them
# The basses with a sawtooth growl under them, closed above 900 Hz (`voices`): the sub, and the factory FM bass, which had no
# middle of its own. House's own FM bass has one, and the growl under it is not heard: taken away in three songs, the bass moved
# 1 dB or less in every octave and the judges stayed level (2026-11-22; Sunlit Fields II's bass, 7 dB over the liked stems at
# 450 to 900 Hz, is the FM bass's own middle, not the growl's). FM_GROWL False: the growl under the sub alone where the FM bass
# is House's own, one track fewer.
FM_GROWL = False
GROWLED = ("house sub", "house bass fm")
# (2026-11-22, midday, every House take studied that day: the sub playing the bass alone, in the three camps that drew it, 6.8
# to 7.5 dB thin in its middle against the liked stems and 34 to 52 under at its top; the sub with only the harsh twin over it
# in walking music 1.0 to 5.9 thin, ten takes, 3.4 on average; with a pluck over it, or any other bass, level to 8 dB heavy. A
# sine is felt, not heard, and its growl at 0.45 is not enough on its own.) Where the sub is the bass with nothing over it but
# its harsh twin, its growl is SUB_ALONE_GROWL of the bass's level, not 0.45. None: 0.45. (The demo sub1, three camps: the
# bass 4.1 to 4.4 dB fuller from 226 Hz to 1.8 kHz, its lowest octaves unmoved; the judges level in all six windows, SongEval
# a shade up in four: in for its musical reason, a bass heard as well as felt.)
SUB_ALONE_GROWL: float | None = 0.8
TWINS = ("harsh", "harsh saw")       # the writer's names of the bass's harsh twin (`harsher`), which come in late in a drop
# (2026-11-22, the day's House studies: the own FM bass 3 to 8 dB heavy in its middle against the liked stems in every take that
# drew it, eleven, at 450 to 900 Hz: its own sidebands, not the growl, which is off under it.) The own FM bass is cut FM_MIDDLE dB
# an octave wide at 600 Hz at the desk. None: as it was. (The demo fm1, three takes: the middle eased 1.5 to 2.4 dB at 450 to
# 900 Hz; TuneJury with the House brief up in all six windows, +0.07 to +0.20, the rest level: in. The bass is still 4.6 to 7.9
# over there, its weight spread from 226 Hz to 3.5 kHz: a broader easing, or the patch's own index, is owed.)
FM_MIDDLE: float | None = -4.0
# (2026-11-22, the day's House studies: the own bell, the chords in the snowfields' and the haunted palettes, 36.6 to 37.8 dB over
# the liked stems at its top and 5.5 to 8.4 thin in its middle in all four takes that drew it, ten dB beyond any other House
# sound: its FM partials at three and a half times the note ring over nothing.) BELL_BODY: the own bell given a body at 450 Hz
# and its top eased from 4 kHz at the desk, (body dB, top dB). None: its top kept open as the own chords' are. LEFT OFF
# (2026-11-22, the demo bell1 at (4, -6), three songs: its body 3 to 4 dB up at 226 to 453 Hz, its top 4 dB down from 7 kHz;
# SongEval up in five windows of six, to +0.14, but TuneJury down in four, to -0.20 with the House brief and -0.28 with none:
# the judges did not agree, and the bell's bright clang may be some of what makes it House to the one that knows House.)
BELL_BODY: tuple[float, float] | None = None
HARSH = 0.55        # how far under the bass its harsh twin plays, once it is all the way in (`harsher`)
OWN_KICK = True     # House's own kick (studio/kicks.py) for every machine's; False: the machine's recorded kick
# dB: the own kick turned up to the 909's loudness: 3.6 by a trial's four strokes at one strength, and 1.5 more by Night Prowl I's
# last drop, where the drums came out 1.1 dB under the 909's, the kick 1.9 dB lighter under 60 Hz (2026-11-21)
KICK_TRIM = 5.1
# (2026-11-22, night: the own kick was the 909's for every machine.) Each machine its own kick (studio/kicks.py: the 808's, the
# 707's and the 606's drawn after the TR-8's), turned up as far again as each stands under its machine's at one strength, past
# the 909's trim (by the first 150 ms of one stroke: the 808's 1.0 dB more, the 707's 2.0, the 606's 0.6 less). False: the
# 909's kick for every machine, as it was.
MACHINE_KICKS = False
MACHINE_KICK = {"909": ("house kick", KICK_TRIM), "808": ("house kick 808", KICK_TRIM + 1.0), "707": ("house kick 707", KICK_TRIM + 2.0),
                "606": ("house kick 606", KICK_TRIM - 0.6)}
# A hard act's kick (2026-11-24; studio/kicks.py): which, by its machine, how many dB it is driven into its ceiling and how soft that is; and how far it stands under where it was made (it is 2.4 dB louder at
# the same height than the kick before it, and is to be a decibel over it).
HARD_KICK = {"909": ("house kick hard", 20.0, 0.35), "606": ("house kick hard 606", 26.0, 0.2), "808": ("house kick hard 808", 14.0, 0.5)}
HARD_KICK_AT = 0.85
# ...and its claps, snares and toms, and its hats, up against that kick (the channel is brought to its place by the whole of it, and the kick is most of that). (1.15 at first: in eight of one night's songs the
# middle of the drums stood 4 to 8 dB under the liked stems', and what is struck on two and four no higher between 350 Hz and 2.5 kHz than the kick's own click on one and three; up 2.9 dB, on two songs, the
# measure of hard against sweet moved 0.4 either way: 1.7.)
HARD_TOPS = {"room": 1.4, "hats": 1.35}
HARD_CLAPS = {"808": 1.9}        # (the 808's claps and snares further: its songs' drums 3.5 to 8.7 dB thin in their middle against the liked stems, Dead Reckoning, Sump, Knuckle Duster and Boiler
                                 # Room; at 1.45 three of the next thirteen's 5 to 7, 2026-11-25)
# A hard act plays close (2026-11-24: what softened its songs, the measure of it says, was the lead, and what it went through was a dream's: an echo in dotted eighths from side to side and a hall): how much of
# the echo its stabs and its lead have, and how far its stabs and its lead are sent to the hall.
CLOSE = (0.35, 0.1, 0.12)
# (2026-11-21: the wide twin added 0.0 to 0.4 dB to the bass in five long drops of six, unheard, and louder at 0.95 only 0.6.)
# With House's own instruments the twin is a sound of its own, driven saws with the low end left to the bass
# (studio/patches.py, "house bass harsh"), whatever the bass is.
# It is high-passed, adding no low end, so it can come nearer the bass: at 0.55 it lifted the bass's 300 Hz to 3 kHz by 1.0 dB
# once all the way in (Night Prowl I), the grit there but faint; at 0.85 by about 2.5.
HARSH_OWN = 0.85
# (2026-11-21, the demos: the drop's big lead of House's own sat 5 to 5.6 dB under the factory one in the mix (Mirage I,
# Hollow Road III), where Audiobox's enjoyment fell. The factory patch had measured quiet on the level's three short notes
# and been turned up 5.5 dB, playing that much over the studio's level in a drop; the own lead is measured true.) The drop's
# hook is lifted to the balance the drops had: dB at the desk, by written instrument.
OWN_LIFT = {"house lead super": 4.0}
if sounds.OWN_HOUSE:
    PLAYED[("bass", "harsh")] = "house bass harsh"
# The drop's big synths, whose edge is the hook: their top is left open and their filter opens further than the band's
# ("i wish i could hear more of that saw synths top end"). The other leads, a calm piece's sung melody and the riff's
# pluck in the quiet, keep the gentler top (2026-11-18: the open top had reached them too, and an inn's tune stood
# 20 dB over the liked leads there).
OPEN_TOP = ("house lead saw", "house lead super") + tuple(sounds.HOUSE_LEADS)
# How a lead of House's own is held at the desk: (how deep its three bands are held, dB on the highest, chorus, how wide, how much echo).
LEAD_CHAIN: dict[str, tuple[float, float, float, float, float]] = {
    "": (0.4, 1.5, 0.0, 1.15, 0.24), "house lead stack": (0.45, 2.0, 0.0, 1.25, 0.24), "house lead anthem": (0.45, 2.0, 0.0, 1.35, 0.24),
    "house lead pwm": (0.35, 1.0, 0.35, 1.3, 0.24), "house lead vox": (0.45, 2.5, 0.0, 1.15, 0.24), "house lead metal": (0.4, 1.0, 0.0, 1.15, 0.24),
    "house lead acid": (0.35, 1.0, 0.0, 1.1, 0.24), "house lead growl": (0.45, 2.0, 0.0, 1.15, 0.24), "house lead pluck": (0.4, 1.5, 0.0, 1.2, 0.34)}
SUB_UNDER = 0.8     # ...this far under the bass it holds up (0.7 until the third pass: the liked basses have 3 to 7 dB more at 28 to 57 Hz)
# House's room, at the foot of every channel's folder (sounds.hall): how long it rings (s), nothing in it over (Hz) or under
# (Hz), and how long its lows ring against the rest. A darker room than the orchestra's, as it was set the first night
# (2026-11-16). (A longer, cleaner one, 2.8 s from 300 Hz to 8 kHz with its lows at 0.8, was tried on 2026-11-21 and left
# off: TuneJury down in four of six windows with the House brief, five of six without; handbook 5.7, Effects.)
ROOM = (1.5, 6000.0, 80.0, 1.2)


def _span_of(at: float) -> int:
    """The four bars a note is struck in (one struck a hair early, as a player does, belongs to the bar it is early for)."""
    return int((at + 0.02) // house.BAR) // SPAN


def _spans(notes: list[tuple[float, float, float, float, float, float]]) -> dict[int, float]:
    """How loud the writer has a voice in each four bars it plays in: the loudest note struck there.
    (Not their mean: the drop's second time round has a quieter line over the tune, and with it a
    mean took the whole drop 5 dB down where it should have grown, 2026-11-17, morning.)"""
    loudest: dict[int, float] = defaultdict(float)
    for at, _, _, level, _, _ in notes:
        span = _span_of(at)
        loudest[span] = max(loudest[span], level)
    return dict(loudest)


def _ride(spans: dict[int, float]) -> list[tuple[float, float]]:
    """A voice's levels, four bars at a time, as its track's volume moves ((beat, gain)), its
    loudest four bars at full. (2026-11-17, morning: the house tracks came out all but level from
    their first bar to their last, 2 to 9 dB between their quietest part and their loudest. Surge
    XT's patches play a note alike however hard it is struck, so what the writer wrote softer was
    not: a breakdown's pad written 5 dB under the drop's came out 5 dB over it. Muse Sounds'
    instruments do play softer, and keep their velocities.)"""
    top = max(spans.values())
    moves: list[tuple[float, float]] = []
    before = None
    for span in sorted(spans):
        gain = spans[span] / top
        if before is not None and abs(gain - before) < 0.01:
            continue
        at = span * SPAN * 4.0
        if before is not None:
            moves.append((at - 0.1, before))           # a tenth of a beat to get there: nothing held over the bar line clicks
        moves.append((at, gain))
        before = gain
    return moves


def voices(heard: Heard) -> list[tuple[str, str, str, str, float, list[Note], float, list[tuple[float, float]]]]:
    """Every line the desk plays, worked out once (so that what MuseScore is asked to perform ahead
    is what the desk then lays down): (channel, the writer's table, its sound, the instrument that
    plays it, the cut at its top in Hz or 0, the notes in beats, how far it is turned down, and the
    volume moves that play its bars as loud as they were written, if its instrument does not)."""
    spans = {key: _spans(notes) for key, notes in heard.notes.items()}
    alone = {name for channel, _, name in heard.notes if channel == "bass" and name not in TWINS} == {"sub"}
    most: dict[str, float] = defaultdict(float)
    for (channel, _, _), levels in spans.items():
        most[channel] = max(most[channel], max(levels.values()))
    out = []
    for (channel, table, name), notes in sorted(heard.notes.items()):
        written = heard.played.get((channel, table, name)) or PLAYED[(table, name)]
        written = MAIN_LEADS.get(written, written)
        levels = spans[(channel, table, name)]
        # Each voice of a channel to the others as the writer has them where each is loudest (its quieter bars are the
        # volume moves' business, or its velocities').
        taste = min(max(max(levels.values()) / most[channel], 0.35), 1.0)
        if written in muse.PARTS and muse.available():
            ride: list[tuple[float, float]] = []
            parts = [("", notes, _loud([level for _, _, _, level, _, _ in notes]), taste)]
        else:
            # The four bars ride the track's volume; how hard a note is struck says only how it stands out in them. What is
            # written well under the tune there (the drop's line over it the second time round) is a track of its own, as
            # far under as it was written: an instrument that plays every note alike would play it as loud as the tune.
            # (A lead of House's own plays its soft strokes itself: they are its accents, and on a track of their own it could not slide to them. Only what sounds with a louder
            # note is a line under it: 2026-11-24, three quarters of Riot Line's riff on the track under.)
            ride = _ride(levels)
            share = [level / levels[_span_of(at)] for at, _, _, level, _, _ in notes]
            loudest: dict[int, float] = defaultdict(float)
            for at, _, _, level, _, _ in notes:
                loudest[round(at / 0.03)] = max(loudest[round(at / 0.03)], level)
            alone_at = lambda at, level: level >= max(loudest.get(round(at / 0.03) + k, 0.0) for k in (-1, 0, 1)) * 0.999      # noqa: E731
            own = channel == "lead" and written in sounds.HOUSE_LEADS
            over = [part >= UNDER if not own else alone_at(note[0], note[3]) for note, part in zip(notes, share)]
            tune = [(note, part) for note, part, top in zip(notes, share, over) if top]
            under = [(note, part) for note, part, top in zip(notes, share, over) if not top]
            parts = []
            if tune:
                parts.append(("", [note for note, _ in tune], _loud([part for _, part in tune]), taste))
            if under:
                parts.append((" under", [note for note, _ in under], _loud([part for _, part in under]),
                              taste * float(np.median([part for _, part in under]))))
        every: list[Note] = []
        for suffix, mine_notes, hard, level in parts:
            # (Its brightness is the part's moving low-pass, one of its effect marks: see `write` and `cutoff`.)
            bands: dict[float, list[Note]] = defaultdict(list)
            for (at, length, pitch, _, _, _), loud in zip(mine_notes, hard):
                bands[0.0].append(Note(at / BEAT, max(length / BEAT, 0.05), int(round(pitch)), loud))
            for cut, mine in sorted(bands.items()):
                out.append((channel, table, name + suffix, written, cut, mine, level, ride))
                every += mine
        if written in GROWLED and (written != "house bass fm" or FM_GROWL or not sounds.house_own(written)):
            # (2026-11-17, night: against the liked house stems the bass was 30 dB short in its middle and 44 at its top: a
            # sine under 100 Hz, which a small loudspeaker does not play at all. The FM bass the same the next morning: 17 to
            # 30 dB short from 450 Hz up.) A sawtooth on the same notes, closed
            # above 900 Hz and well under the sub, is the part of the bass that is heard; the sub is the part that is felt.
            growl = SUB_ALONE_GROWL if SUB_ALONE_GROWL is not None and written == "house sub" and alone else 0.45
            out.append((channel, table, name + " growl", "house bass saw", 900.0, sorted(every, key=lambda note: note.start),
                        taste * growl, ride))
        if written in SUBBED:
            # (2026-11-17, morning: against the liked house stems the plucked and the sawtooth basses had 6 to 8 dB too much
            # in their middle and too little under 200 Hz.) The other way about: the sub on the same notes under the bass
            # that is heard, the weight a house bass has from a sine under it.
            # On the same notes: the bass line is written from G1 to F#2, so its own notes are where the liked house basses
            # have their weight (40 to 80 Hz), and that is where these patches are weak. (An octave under, tried the same
            # morning, put the sub at 25 to 45 Hz: 12 dB over the liked there, and nothing more where it was wanted.)
            out.append((channel, table, name + " sub", "house sub", 0.0, sorted(every, key=lambda note: note.start), taste * SUB_UNDER, ride))
    return out


def lines(heard: Heard, seed: int, work: Path) -> tuple[dict[str, list[desk.Line]], list[tuple[float, float]]]:
    """The REAPER tracks of a take, by channel, and where its kick strikes ((beat, how hard)). Each part's effect marks
    (`Heard.marks`) go on its tracks."""
    out: dict[str, list[desk.Line]] = defaultdict(list)
    # ----- drums: the kick by itself, and everything else the machine strikes, in a small room
    used = sorted({name for name, *_ in heard.hits})
    strokes: list[tuple[float, float]] = []
    if used:
        machine = heard.hits[0][1]
        file, keys = kit_file(machine, used)
        hard = _loud([level for _, _, _, level, _ in heard.hits])
        sets: dict[str, list[Note]] = defaultdict(list)
        for (name, _, at, level, pan), loud in zip(heard.hits, hard):
            # The writer strikes its kick dry and everything else into a room; the hats and shakers have a line of their own.
            which = "kick" if name in KICKS else "hats" if name in HATS_SOUNDS else "room"
            sets[which].append(Note(at / BEAT, 0.25, keys[name], loud))
            if name in KICKS:
                strokes.append((at / BEAT, loud))
        template = desk.bare("house kit", [desk.sfizz(file)])
        # (2026-11-21, "and design yourself": House's own kick, studio/kicks.py, in the place of the machine's sample; it is
        # 3.6 dB quieter than the 909's at the same strength, so it is turned up that much, before the kick's chain.)
        kick_name, kick_trim = MACHINE_KICK.get(machine, MACHINE_KICK["909"]) if MACHINE_KICKS else MACHINE_KICK["909"]
        kick_template = desk.bare("house own kick", [desk.geonkick("own/" + kick_name)]) if OWN_KICK else template
        chains = {
            # The kick: its stroke brought out, what is under 30 Hz taken away, held together; nothing of it in the hall.
            "kick": ([sounds.punch(0.35, -0.1), sounds.equalise(low_cut=30.0, bands=((320.0, -2.5, 1.2), (3500.0, 2.0, 1.6))), sounds.smash(0.3)], 0.0, 1.0),
            # (The clap, the snare and the hats 4 to 10 dB short from 900 Hz to 3.5 kHz against the liked stems, 2026-11-17;
            # with that lifted, the clap's and the snare's knock at 900 Hz was still 3 to 6 dB short in every take, 2026-11-18.)
            "room": ([sounds.equalise(low_cut=180.0, bands=((900.0, 3.0, 1.2), (2000.0, 3.0, 0.8))), sounds.warm(0.35)], 0.22, 0.6),
            # (2026-11-18: "too much high hat". They shared the clap's chain: lifted 3 dB at 900 Hz and 2 kHz, through tape and
            # into the hall. A hat in a good house record is high-passed, dry, its top eased, and well under the kick and clap.)
            "hats": ([sounds.equalise(low_cut=500.0, high_shelf=(11000.0, -3.0))], 0.0, 0.42),
        }
        for which, notes in sets.items():
            effects, send, volume = chains[which]
            if which == "kick" and OWN_KICK:
                effects = [sounds.turned(kick_trim)] + effects
            if which == "kick" and heard.drive:
                # A hard act's kick: its own, tuned to the song, its knock and its edge brought up into a ceiling, and again after it.
                hard_kick, pushed, soft = HARD_KICK.get(machine, HARD_KICK["909"])
                kick_template = desk.bare("house hard kick", [desk.geonkick("own/%s@%.1f" % (hard_kick, heard.rest))])
                effects = [sounds.turned(KICK_TRIM), sounds.equalise(low_cut=32.0, bands=((190.0, 4.0, 1.0), (1200.0, 6.0, 0.8))), sounds.clip(pushed, ceiling=-4.0, soft=soft),
                           sounds.equalise(low_cut=30.0, bands=((170.0, 2.5, 0.9), (1100.0, 3.0, 0.8), (4000.0, 4.0, 1.2)))]
                volume = HARD_KICK_AT
            elif heard.drive:
                volume *= HARD_TOPS[which] * (HARD_CLAPS.get(machine, 1.0) if which == "room" else 1.0)                     # (what is over the kick, up with it)
            out["drums"].append(desk.Line("house %s" % which, kick_template if which == "kick" else template, notes, volume=volume,
                                          send=send, effects=effects))
    # ----- the voices: each sound of each channel, its notes shared out by how bright they are asked for
    for channel, table, name, written, cut, mine, taste, ride in voices(heard):
            title = "%s %s%s" % (table, name, " (to %d Hz)" % cut if cut else "")
            # (MuseScore's players measured to the level the studio's own are, 2026-11-17, morning: they were laid in
            # 6 dB up as the orchestra has them, and a channel that had one of each had no level between them, a
            # haunted piece's theme sung by the Wurlitzer 7 dB over its drops sung by Surge's sine.)
            # (2026-11-17, morning, against the liked house stems octave by octave: the Surge patches were the bright ones,
            # 6 to 19 dB too much from 900 Hz to 3.5 kHz in the leads and keys, the pads 16 dB over at 3.5 kHz; MuseScore's
            # instruments had measured dull the night before. So each line is toned by what plays it.)
            synth_played = not (written in muse.PARTS and muse.available())
            # (2026-11-21, "i think mainly your instruments suck for house": House's own patches, sounds.OWN_HOUSE.) A sound of
            # the studio's own is shaped in its synth, its filter opening with each note: the cuts below, made to tame the
            # factory patches' tops against the liked stems (separated from whole mixes, so dull at the top), would only muffle
            # it. It keeps its top, the lows its part does not need taken away.
            own = sounds.house_own(written)
            effects, settings = heard.marks.get((channel, table, name.split(" ")[0]), ({}, {}))
            for line in sounds.lines(Voice(notes=mine, instrument=written, effects=dict(effects), settings=dict(settings)), title, house.BPM,
                                     taste=taste, room=1.0, seed=seed, muse_level=sounds.LEVEL):
                if ride:
                    line.moves = list(ride)
                if channel == "lead" and name.split(" ")[0].endswith(CUT_NAMES[1:]):
                    line.pan = CUT_SEATS[2] if name.split(" ")[0].endswith(CUT_NAMES[2]) else CUT_SEATS[1]        # (a riff that is cut up: who hammers it in the middle, the others either side)
                if cut:
                    line.effects = list(line.effects) + [sounds.equalise(high_cut=cut)]
                if channel == "bass":
                    # (Against the liked house stems the sawtooth and wide basses were 13 to 34 dB bright above 2.5 kHz,
                    # 2026-11-17, night: a house bass is closed well down. The growl beside the sub has its own cut.)
                    # (Third pass, 2026-11-17, midday, twenty tracks: still 7 to 13 dB heavy from 450 Hz to 1.8 kHz: closed
                    # from 1.8 kHz, the shelf down from 800 Hz.)
                    shut = dict(high_cut=2400.0, high_shelf=(900.0, -3.0)) if own else dict(high_cut=1800.0, high_shelf=(800.0, -6.0))
                    middle = ((600.0, FM_MIDDLE, 1.0),) if own and written == "house bass fm" and FM_MIDDLE is not None else ()
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=30.0, bands=middle, **shut), sounds.wide(0.25)]
                    line.send = 0.0
                elif channel == "rhythm":
                    # (Measured against the house stems that were liked: the plucks had 11 to 24 dB too much above 3 kHz.)
                    # (Still 13 dB bright there on 2026-11-17, night: 4 dB more; then still 11: 4 more and closed from 7 kHz.)
                    # (Third pass, midday, twenty tracks: still 11 dB over at 1.8 kHz, 19 to 23 at 3.5 kHz: the shelf from
                    # 2.5 kHz, closed from 6 kHz.)
                    tone = ((1800.0, -4.0, 1.0),) if synth_played else ()
                    # (2026-11-17, early afternoon, by ear: "your house sounds cheesy bro more effects or something", the synths
                    # heard as presets: the chords turn slowly under a phaser, through tape, with more echo and more room.)
                    moved = [sounds.phase(0.35)] if synth_played else []
                    # (2026-11-18: a moving low-pass is marked on each part now, shut in the themes and the breakdown and open at
                    # a drop; with this top fixed at 6 kHz and 16 dB down from 2.5, a drop was as dark as its theme.)
                    # (2026-11-18, by ear: "the sounds just need to be bigger somehow it sounds hollow and generic in the
                    # synths". Cut from 110 Hz, the chords had lost their body: from 80 now, and spread wider.)
                    # (...but MuseScore's brass and keys, open to 20 kHz at a drop, were 12 to 21 dB over the liked stems from 2.5
                    # to 10 kHz: they keep a gentler top of their own, closed from 8 kHz; the moving low-pass shuts the rest.)
                    top = dict(high_shelf=(2500.0, -10.0)) if synth_played else dict(high_cut=8000.0, high_shelf=(2500.0, -13.0))
                    if own:
                        tone, top = (), dict(high_shelf=(9000.0, -2.0))
                        if written == "house bell" and BELL_BODY is not None:
                            tone, top = ((450.0, BELL_BODY[0], 1.5),), dict(high_shelf=(4000.0, BELL_BODY[1]))
                    close = heard.drive > 0.0 and written != "house stab dub"           # (a hard act's stabs are close: CLOSE)
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=150.0 if own else 80.0, bands=tone, **top)] \
                        + moved + [sounds.warm(0.3), sounds.wide(1.3), sounds.echo(house.BPM, 0.26 * (CLOSE[0] if close else 1.0), left=3, right=4, again=0.36)]
                    line.send = CLOSE[1] if close else max(line.send, 0.24)
                elif channel == "lead":
                    # (The night's leads, MuseScore's, were 6 dB dull at their top and 3 in their middle against the liked house
                    # stems: lifted. The Surge leads are the other way about: taken down from 2.5 kHz. Open from 120 Hz, since
                    # the tunes sit a fifth lower.)
                    # (Third pass, midday: Surge's leads still 8 to 20 dB over from 1.8 to 7 kHz: taken down further, which
                    # brought them 4 to 5 dB nearer. MuseScore's keep their lift: given back, a pastoral lead went 3 dB further
                    # under the liked ones at the top.)
                    # (2026-11-18, "it sounds hollow": open from 85 Hz, not 120, so the lead has its body, and a synth's
                    # wider: more chorus, spread.)
                    # (2026-11-18, by ear, Rain on the Roofs: "i wish i could hear more of that saw synths top end". The cuts
                    # measured against the liked stems' average, 5 dB at 2.5 kHz and 8 dB from 3.5, hid the saw's edge: now
                    # only its very top eased, and a little air.)
                    if own:
                        # (a little presence where a lead sings, the top eased from 6 kHz: the demos' leads short at 1.25-2.5 kHz)
                        toned = sounds.equalise(low_cut=120.0, bands=((1200.0, 2.0, 1.0),), high_shelf=(6000.0, -4.0))
                        if written in OWN_LIFT:
                            line.effects = [sounds.turned(OWN_LIFT[written])] + list(line.effects)
                    elif synth_played and written in OPEN_TOP:
                        toned = sounds.equalise(low_cut=85.0, high_shelf=(7000.0, -2.0))
                    elif synth_played:
                        toned = sounds.equalise(low_cut=85.0, bands=((2500.0, -5.0, 1.0),), high_shelf=(3500.0, -8.0))
                    else:
                        toned = sounds.equalise(low_cut=85.0, bands=((1200.0, 3.0, 1.5),), high_shelf=(4000.0, 6.0))
                    # (...and the lead: tape, a chorus on a synth's, a longer echo from side to side, more room.)
                    widened = ([sounds.excite(0.15)] if written in OPEN_TOP else []) + [sounds.ensemble(0.35), sounds.wide(1.3)] if synth_played else []
                    echoed = CLOSE[0] if heard.drive else 1.0
                    added = [toned, sounds.warm(0.35)] + widened + [sounds.echo(house.BPM, 0.3 * echoed, left=3, right=4, again=0.42)]
                    if written in sounds.HOUSE_LEADS or written in sounds.HEARTS:
                        # (2026-11-24) A lead of House's own: held in three bands (jsfx/lift), so that the edge and the tail of each note are heard with
                        # its body, presence at 2.6 kHz, its top open, and little chorus: its movement is its own.
                        depth, high, chorus, spread, again = LEAD_CHAIN.get(written, LEAD_CHAIN[""])
                        added = [sounds.equalise(low_cut=140.0, bands=((350.0, -1.5, 1.2), (2600.0, 2.0, 0.9)), high_shelf=(9000.0, 1.0)), sounds.lift(depth, high),
                                 sounds.warm(0.3)] + ([sounds.ensemble(chorus)] if chorus else []) + [sounds.wide(spread),
                                                                                                    sounds.echo(house.BPM, again * echoed, left=3, right=4, again=0.4)]
                    line.effects = list(line.effects) + added
                    line.send = CLOSE[2] if heard.drive else max(line.send, 0.3)
                elif channel == "texture":
                    # (...and the pad 15 to 35 dB too much there: its glass is kept, its glare taken away; 16 dB bright still on
                    # 2026-11-17, night, with the risers tamed: 4 dB more off, and closed from 5 kHz.)
                    # (Third pass, midday: the pads alone, in the open and the themes, still 7 to 20 dB over at 3.5 to 7 kHz.)
                    # (2026-11-18, "hollow": the pads from 110 Hz, not 200, their top a little more open, the moving low-pass
                    # doing the rest; and wider.)
                    closed = sounds.equalise(low_cut=110.0, high_cut=4200.0, high_shelf=(2500.0, -10.0)) if synth_played \
                        else sounds.equalise(low_cut=110.0, high_cut=6000.0, high_shelf=(3000.0, -9.0))
                    if own:
                        closed = sounds.equalise(low_cut=180.0, high_shelf=(6000.0, -4.0))
                    # (...and the pads wider, turning more slowly than the chords, further into the room.)
                    line.effects = list(line.effects) + [closed, sounds.ensemble(0.55), sounds.phase(0.25, rate=0.04), sounds.wide(1.4)]
                    line.send = max(line.send, 0.36)
                out[channel].append(line)
    # ----- the risers and the air: played in REAPER by the studio's own instrument (studio/jsfx/air)
    out["texture"] += air_lines(heard.airs)
    return out, strokes


# The air instrument's kinds (studio/jsfx/air), and its resonance for each.
AIR_KINDS = {"sweep": (0, 0.35), "climb": (1, 0.2), "thud": (2, 0.0), "wind": (3, 0.3), "sea": (4, 0.05), "rain": (5, 0.05),
             "fire": (6, 0.0), "drips": (7, 0.0), "crickets": (8, 0.0)}
AIR_STEP = 0.125              # beats between two moves of its controllers


def air_lines(airs: list) -> list[desk.Line]:
    """A track's air as REAPER tracks (2026-11-17, night: "remember to use reaper and plugins for effects and mixing";
    the writer made it in Python and it was laid in as a recording): one track for each kind of sound and each pair of
    corners, the studio's air instrument on it, each sound a note (its velocity how loud it is asked to be) with
    controller 1 drawing its sweep and controller 11 its swell, as the writer's own making draws them. Weather that
    runs on into more weather of the same kind is one long sound. The hall and the tamed top are the texture's."""
    groups: dict[tuple, list] = defaultdict(list)
    for air in airs:
        groups[(air.kind, air.low, air.high)].append(air)
    beat = house.BPM / 60.0
    lines = []
    for (kind, low, high), mine in sorted(groups.items()):
        number, resonance = AIR_KINDS[kind]
        if kind not in ("sweep", "climb", "thud"):
            joined: list = []
            for air in sorted(mine, key=lambda each: each.at):
                if joined and air.at <= joined[-1].at + joined[-1].seconds:
                    last = joined[-1]
                    last.seconds = max(last.seconds, air.at + air.seconds - last.at)
                    last.level = max(last.level, air.level)
                else:
                    joined.append(house.Air(air.kind, air.at, air.seconds, air.level, air.low, air.high, air.rising, air.pitch, air.fade, air.seed))
            mine = joined
        notes, controls = [], []
        for index, air in enumerate(sorted(mine, key=lambda each: each.at)):
            first, length = max(air.at, 0.0) * beat, air.seconds * beat
            # Every other sound on its own key, so that one's end never stops the next begun before it.
            key = air.pitch if kind == "climb" else 60 + 2 * (index % 2)
            notes.append(Note(first, max(length - 0.02, 0.05), key, min(max(air.level / 1.2, 0.02), 1.0)))
            steps = max(int(length / AIR_STEP), 1)
            for step in range(steps + 1):
                along = step / steps
                if kind == "sweep":
                    sweep = along ** 1.3 if air.rising else (1.0 - along) ** 1.3
                    swell = along ** 2.2 if air.rising else (1.0 - along) ** 1.6
                elif kind == "climb":
                    sweep, swell = along, along ** 2
                elif kind == "thud":
                    sweep, swell = 0.0, 1.0
                else:
                    seconds = along * air.seconds
                    sweep, swell = 0.0, min(1.0, seconds / max(air.fade, 0.01), (air.seconds - seconds) / max(air.fade, 0.01))
                at = first + along * length
                controls += [(at, 1, int(round(127 * min(max(sweep, 0.0), 1.0)))), (at, 11, int(round(127 * min(max(swell, 0.0), 1.0))))]
        name = "air %s%s" % (kind, " %d-%d Hz" % (low, high) if kind == "sweep" else "")
        effect = desk.js("freerock/air", number, low or 20.0, high or 20000.0, resonance, 24, 0.6, 0.0)
        lines.append(desk.Line(name, desk.bare(name, [effect]), notes, volume=0.3, controls=controls, send=0.25,
                               effects=[sounds.equalise(low_cut=150.0, high_cut=5000.0, high_shelf=(2000.0, -12.0))]))
    return lines


def _curve(start: float, end: float, low: float, high: float, shape: float = 1.0, steps: int = 32) -> list[tuple[float, float]]:
    """(time, Hz) from `low` to `high` evenly in pitch; a `shape` over 1 holds back and then goes, as a rise does. Its
    ends are exactly `low` and `high`."""
    def at(index: int) -> float:
        if index in (0, steps):
            return low if index == 0 else high
        return math.exp(math.log(low) + (math.log(high) - math.log(low)) * (index / steps) ** shape)
    return [(start + (end - start) * index / steps, at(index)) for index in range(steps + 1)]


def thinning(form: list[dict], channel: str, calm: bool) -> list[tuple[float, float]]:
    """Where a part's bottom is taken away, as (beat, Hz) of its high-pass (2026-11-18, the study of the records): the
    sub goes for the whole of each rise and comes back with everything on the drop's first beat; over a rise's last
    seven beats the bass is thinned from 100 Hz to 250, the chords and pads from 60 Hz to 400; and at the breakdown the
    bass is lifted out over its first four bars (30 Hz to 150), so that the drop has the whole bottom to bring back. A
    calm piece (an inn, a camp, the night) keeps its bottom, and the tune has none of this."""
    if calm or channel not in ("bass", "rhythm", "texture"):
        return []
    points = [(0.0, 20.0)]
    for section in form:
        a, b = section["first"] * 4.0, (section["first"] + section["bars"]) * 4.0
        if channel == "bass" and section.get("breakdown"):
            points += [(a - 0.05, 20.0)] + _curve(a, a + min(16.0, b - a), 30.0, 150.0, steps=12) + [(b - 0.05, 150.0)]
        elif section["story"] == "rise":
            low, high = (100.0, 250.0) if channel == "bass" else (60.0, 400.0)
            go = max(b - 7.0, a)
            if channel == "bass":
                points += [(a - 0.05, points[-1][1]), (a, low), (go, low)]
            else:
                points += [(go - 0.05, 20.0), (go, low)]
            points += _curve(go, b - 0.05, low, high, shape=1.6, steps=12)[1:] + [(b, 20.0)]
    return points


def throws(part: Voice, form: list[dict], calm: bool) -> None:
    """The tune's own treatment, marked from its phrases (2026-11-18: "the lead is still lame"): its echo thrown up on
    the last note of each four bars it plays and taken down after it (the house study: the delay send up 6 dB for a
    phrase's last note), and through the second half of each drop a phaser turning over two bars, so that the hook
    stays and what is done to it changes."""
    phrases: dict[int, list[Note]] = defaultdict(list)
    for note in part.notes:
        phrases[int(note.start // 16.0)].append(note)
    if not phrases:
        return
    up = 0.55 if calm else 0.8
    points: list[tuple[float, float]] = []
    for _, mine in sorted(phrases.items()):
        last = max(mine, key=lambda note: note.start)
        end = last.start + last.length
        points += [(last.start - 0.05, 0.0), (last.start, up), (end + 0.25, up), (end + 0.75, 0.0)]
    part.mark("echo", points)
    part.set("echo beats", 0.75)
    part.set("echo feedback", 0.5)
    for section in form:
        if section["story"] == "moment" and not calm:
            a, b = section["first"] * 4.0, (section["first"] + section["bars"]) * 4.0
            middle = a + (b - a) / 2.0
            if any(middle <= note.start < b for note in part.notes):
                part.mark("phaser", [(middle - 0.05, 0.0), (middle + 1.0, 0.6), (b - 1.0, 0.6), (b, 0.0)])
    if "phaser" in part.effects:
        part.set("phaser bars", 2.0)
        part.set("phaser feedback", 0.45)


def story_at(sections: list[tuple[str, int, int]], beat: float) -> str:
    """Which part of the story a beat is in ((story, first bar, bars) of each section)."""
    bar = beat / 4.0
    for story, first, count in sections:
        if first <= bar < first + count:
            return story
    return sections[-1][0]


def write(name: str, take: int) -> Sheet:
    """A House take's music sheet, its first draft, at its family's tempo (house.at)."""
    with house.at(house.family(name).bpm):
        return _write(name, take)


def _write(name: str, take: int) -> Sheet:
    """A House take's music sheet, its first draft: what the writer (studio.house) asks to be played, taken down as it
    writes (`listen`), every part with its effect marks. Each part's low-pass follows its notes' brightness as the
    track opens and closes (`cutoff`), and its high-pass where the form takes the bottom away (`thinning`)."""
    track = house.Take(house.family(name), take)
    fam = track.family
    heard = listen(track)
    calm = fam.role in house.CALM_ROLES
    act = act_of(fam, take)
    form = [dict({"story": story, "first": first, "bars": count}, **({"breakdown": True} if track.broken(story, first) else {}))
            for story, first, count in track.sections]
    parts: dict[str, dict[str, Voice]] = {channel: {} for channel in forever.CHANNELS}
    roles = parts_of_the_lead(heard, track.sections)
    cut = ACTS[act].cut if act else ()
    dealt: list[list[Note]] = []                         # a riff that is cut up: its three voices' notes
    if cut:
        dealt = cut_up([Note(at / BEAT, length / BEAT, int(round(pitch)), level) for (channel, table, sound), notes in sorted(heard.notes.items())
                        if channel == "lead" and roles.get((table, sound)) == "big" for at, length, pitch, level, _, _ in notes], form, track.seed)
    for (channel, table, sound), notes in sorted(heard.notes.items()):
        role = roles.get((table, sound), "") if channel == "lead" else ""
        instrument = played(table, sound, act, track.seed, role)
        part = Voice(instrument=instrument,
                     notes=[Note(at / BEAT, length / BEAT, reached(instrument, int(round(pitch))) if act else int(round(pitch)), level)
                            for at, length, pitch, level, _, _ in notes])
        if cut and role == "big":
            part.notes = dealt[0]
        elif cut and role == "late":
            part.notes = with_the_first(part.notes, dealt, form)
        if channel == "lead" and MAIN_LEADS.get(instrument, instrument) in sounds.HOUSE_LEADS:
            accented(part.notes, form, hammered=track.scene is not None)
        if instrument in THIRDS:
            part.notes = with_thirds(part.notes, {track.changes.pitch(degree) % 12 for degree in range(7)})
        lane: list[tuple[float, float]] = []
        for at, _, _, _, _, bright in sorted(notes):
            # The drop's big synths open further than the band: the hook, whose edge is what is heard (a theme's lead
            # about 6 kHz, not 3; "i wish i could hear more of that saw synths top end"). The other leads follow the band.
            beat, hz = at / BEAT, cutoff(0.35 + 0.65 * bright if channel == "lead" and instrument in OPEN_TOP else bright)
            if lane and beat - lane[-1][0] < 1e-3:
                lane[-1] = (lane[-1][0], max(lane[-1][1], hz))
            else:
                lane.append((beat, hz))
        if any(hz < 19999.0 for _, hz in lane):
            part.mark("lowpass", lane)
            part.set("lowpass resonance", RESONANCE.get(channel, 0.1))
        thin = thinning(form, channel, calm)
        if thin:
            part.mark("highpass", thin)
            part.set("highpass resonance", 0.25 if channel == "bass" else 0.15)
        if channel == "lead":
            throws(part, form, calm)
        if channel == "rhythm" and not calm:
            # The chords' treatment changes in the last sixteen bars of a long drop: a phaser comes in (the house study: a
            # phaser on the chord loop; the boredom meter: the chords' colour held all 48 bars of a last drop).
            for section in form:
                if section["story"] == "moment" and section["bars"] >= 32:
                    a, b = (section["first"] + section["bars"] - 16) * 4.0, (section["first"] + section["bars"]) * 4.0
                    part.mark("phaser", [(a - 0.05, 0.0), (a + 2.0, 0.55), (b - 1.0, 0.55), (b, 0.0)])
            if "phaser" in part.effects:
                part.set("phaser bars", 4.0)
                part.set("phaser feedback", 0.4)
        parts[channel]["%s %s" % (table, sound)] = part
        for suffix, voice, mine in zip(CUT_NAMES[1:], cut, dealt[1:]) if cut and role == "big" else ():
            other = Voice(instrument=voice, notes=[Note(note.start, note.length, reached(voice, note.pitch), note.loud) for note in mine],
                          effects={kind: list(points) for kind, points in part.effects.items() if kind != "echo"}, settings=dict(part.settings))
            if voice in sounds.HOUSE_LEADS:
                accented(other.notes, form, hammered=track.scene is not None)
            parts[channel]["%s %s%s" % (table, sound, suffix)] = other
    if not calm:
        harsher(parts, form)
    machine = (ACTS[act].machine if act else "") or (heard.hits[0][1] if heard.hits else "")
    for drum, _, at, level, _ in heard.hits:
        parts["drums"].setdefault(drum, Voice(drums=True, instrument="house kit " + machine)).notes.append(Note(at / BEAT, 0.25, 36, level))
    meta = track.meta()
    about = {"meta": meta, "frames": track.frames, "kick": bool(track.kick), "role": fam.role, "calm": calm, "seed": track.seed,
             "machine": machine, "hard": fam.hard, "sounds": act}
    sheet = Sheet(style="house", family=name, take=take, title=meta["title"], tempo=float(house.BPM), beats=4.0, form=form, parts=parts,
                  about=about, airs=[asdict(air) for air in heard.airs])
    sheet.revised("the first draft", "written by the studio's house writer (%s, %s)" % (fam.palette, fam.groove), by="the writer")
    return sheet


def harsher(parts: dict[str, dict[str, Voice]], form: list[dict]) -> None:
    """The bass grows harsher through a long drop: a second bass on the same notes comes in over eight bars halfway
    through every drop of 32 bars or more and leaves with it (the house study: deadmau5's "Turning Point", where a harsher
    bass fades in under the same notes, an illusion of the timbre changing, and "Phantoms Can't Hang", whose bass turns
    harsher before a core's midpoint; the boredom meter, 2026-11-18: the bass's colour held 44 bars of a last drop). The
    twin is the detuned saws of the wide bass, or a sawtooth where the bass is already the wide one."""
    notes: list[Note] = []
    played = ""
    for section in form:
        if section["story"] != "moment" or section["bars"] < 32:
            continue
        a, b = (section["first"] + section["bars"] // 2) * 4.0, (section["first"] + section["bars"]) * 4.0
        here = {name: [note for note in part.notes if a <= note.start < b] for name, part in parts["bass"].items()}
        name = max(here, key=lambda each: len(here[each]), default=None)
        if not name or not here[name]:
            continue
        played = parts["bass"][name].instrument
        for note in here[name]:
            # In over eight bars, a step for each of the desk's four-bar volume steps: under half way, most of the way, in.
            step = (0.45, 0.73, 1.0)[min(int((note.start - a) // 16.0), 2)]
            notes.append(Note(note.start, note.length, note.pitch, note.loud * (HARSH_OWN if sounds.OWN_HOUSE else HARSH) * step))
    if notes:
        twin = "harsh saw" if played == PLAYED[("bass", "harsh")] else "harsh"
        parts["bass"]["bass " + twin] = Voice(instrument=PLAYED[("bass", twin)], notes=notes)


def heard_from(sheet: Sheet) -> Heard:
    """What a House sheet asks to be played, as the desk takes it (`Heard`)."""
    heard = Heard()
    for channel, parts in sheet.parts.items():
        if channel == "drums":
            continue
        for part_name, part in parts.items():
            table, sound = part_name.split(" ", 1)
            heard.notes[(channel, table, sound)] = [(n.start * BEAT, n.length * BEAT, float(n.pitch), n.loud, 0.0, 1.0) for n in part.notes]
            heard.played[(channel, table, sound)] = part.instrument
            if part.effects:
                heard.marks[(channel, table, sound)] = (part.effects, part.settings)
    heard.hits = sorted(((drum, sheet.about["machine"], n.start * BEAT, n.loud, 0.0) for drum, part in sheet.parts.get("drums", {}).items()
                         for n in part.notes), key=lambda hit: hit[2])
    heard.airs = [house.Air(**air) for air in sheet.airs]
    return heard


RIDDEN = ("lead", "rhythm")      # the channels stood at their place at the drop and ridden down elsewhere (see perform)


def ridden(audio: np.ndarray, spans: list[tuple[int, int]], ceiling: float, ease: int) -> np.ndarray | None:
    """A channel ridden down where a part of the story would stand over `ceiling` (LUFS): the gain for each sample,
    each such part brought down to it and eased from one part's gain to the next over `ease` samples at the joins; None
    where every part is under it already."""
    gains = []
    for low, high in spans:
        loud = analysis.loudness_lufs(audio[low:high], RATE) if high > low else -100.0
        gains.append(10.0 ** ((ceiling - loud) / 20.0) if loud > ceiling else 1.0)
    if all(gain == 1.0 for gain in gains):
        return None
    curve = np.ones(len(audio), dtype=np.float32)
    for (low, high), gain in zip(spans, gains):
        curve[low:min(high, len(curve))] = gain
    if spans:
        curve[spans[-1][1]:] = gains[-1]
    for index, (low, _) in enumerate(spans[1:], start=1):
        start, end = max(low - ease // 2, 0), min(low + ease // 2, len(curve))
        if end > start:
            curve[start:end] = np.linspace(gains[index - 1], gains[index], end - start, dtype=np.float32)
    return curve


# How far a song's themes are held under its drops, by channel, in dB: a hard act's, and any other's that is not calm (2026-11-24: Riot Line's theme was 0.8 dB under
# its drop, its drums and its lead at one level in both: there was nothing left for the drop to bring. Then counted: of the 164 House songs staged that are not calm the
# drop stood 0.4 to 1.4 dB over the theme in every one, under a decibel in 125).
HELD_BACK = {"drums": -1.2, "bass": -1.2, "rhythm": -1.5, "lead": -2.5}
HELD_BACK_SOFTER = {"drums": -1.0, "bass": -1.0, "rhythm": -1.0, "lead": -1.5, "texture": -0.5}


def held_back(sections: list[tuple[str, int, int]], channel: str, frames: int, over: "np.ndarray | float" = 1.0, held: dict[str, float] | None = None) -> np.ndarray:
    """A channel's volume through a song (HELD_BACK, or `held`): its themes held under its drops, each eased over a bar into what comes after it."""
    curve = np.ones(frames, dtype=np.float32)
    down, bar = 10.0 ** ((HELD_BACK if held is None else held).get(channel, 0.0) / 20.0), int(house.BAR_FRAMES)
    for story, first, count in sections:
        if story == "theme":
            curve[int(round(first * house.BAR_FRAMES)):min(int(round((first + count) * house.BAR_FRAMES)), frames)] = down
    # (Eased by the mean over a bar: what is after a theme, a rise without its drums or a drop, is at its full by the second beat of it.)
    half = max(bar // 2, 1)
    total = np.cumsum(np.concatenate([np.full(half, curve[0]), curve, np.full(half, curve[-1])]), dtype=np.float64)
    eased = (total[2 * half:] - total[:-2 * half]) / (2.0 * half)
    return (np.resize(eased, frames) * over).astype(np.float32)


STROKE_OFF = 45.0           # cents: a lead whose strokes on one note stand this far from it is out of tune there


def strokes_off(notes: list[Note], audio: np.ndarray, beat_frames: float, span: tuple[float, float], most: int = 120) -> dict[int, float]:
    """How far a lead's strokes sound from what is written, in cents, for each pitch struck eight times or more in a span of beats: each stroke by the harmonic sum of its own first quarter of a beat, three
    half-steps either way, and the median of them. (2026-11-24: three songs' leads, a saxophone's short strokes, sounded 90 to 185 cents flat; the channel heard as a whole read 12 in one of them and passed the
    others, and the instrument's long notes, by which it was tuned, are in tune.)"""
    mono, found = audio.mean(axis=1), defaultdict(list)
    cents, size = np.arange(-300.0, 301.0, 5.0), 1 << 17
    for note in sorted((each for each in notes if span[0] <= each.start < span[1]), key=lambda each: each.start)[:most]:
        piece = mono[int((note.start + 0.02) * beat_frames):int((note.start + 0.95 * min(note.length, 0.24)) * beat_frames)]
        if len(piece) < 2000 or float(np.sqrt(np.mean(piece ** 2))) < 1e-4:
            continue
        power = np.concatenate([[0.0], np.cumsum(np.abs(np.fft.rfft(piece * np.hanning(len(piece)), size)) ** 2)])
        written = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0) * size / RATE
        at = np.round(written * np.arange(1, 9)[:, None] * 2.0 ** (cents[None, :] / 1200.0)).astype(int)
        at = np.clip(at, 4, size // 2 - 4)
        found[note.pitch].append(float(cents[int(np.argmax(np.sqrt(power[at + 4] - power[at - 3]).sum(axis=0)))]))
    return {pitch: float(np.median(each)) for pitch, each in sorted(found.items()) if len(each) >= 8}


def stage(name: str, take: int) -> dict:
    """Writes one take of a house family as its sheet and performs it (`write`, `perform`). A take whose sheet a musician has
    revised is performed from its sheet (`sheet.revised_of`)."""
    from .sheet import revised_of
    return perform(revised_of("house", name, take) or write(name, take))


def perform(sheet: Sheet) -> dict:
    """Plays a House sheet and stages it, at the tempo it says (house.at)."""
    with house.at(sheet.tempo):
        return _perform(sheet)


def _perform(sheet: Sheet) -> dict:
    """Plays a House sheet and stages it: MuseScore and Surge XT play its parts in REAPER with their marks, the drums from
    the drum machine's recordings, each channel giving way under the kick as deep as its part of the story asks; then
    each channel to its place, the mix rendered again in REAPER, and the track staged with its sheet beside it."""
    began = time.time()
    about = sheet.about
    name, take = sheet.family, sheet.take
    work = PROJECTS / "house" / name / str(take)
    work.mkdir(parents=True, exist_ok=True)
    heard = heard_from(sheet)
    sections = [(section["story"], section["first"], section["bars"]) for section in sheet.form]
    frames = about["frames"]
    if muse.available():
        # MuseScore performs its instruments' lines several at a time before the project is put together.
        muse.prepare([(written, mine, float(house.BPM), []) for _, _, _, written, _, mine, _, _ in voices(heard) if written in muse.PARTS],
                     seed=about["seed"], workers=4)
    heard.drive = ACTS[about["sounds"]].drive if about.get("sounds") in ACTS and not about["calm"] else 0.0
    heard.rest = kicks.rest(house.family(name).tonic)
    under, strokes = lines(heard, about["seed"], work)
    folders = []
    for channel in forever.CHANNELS:
        if not under.get(channel):
            continue
        moves, last = [], -1.0
        for at, loud in sorted(strokes) if channel in DUCK else ():
            if at <= last:
                continue
            down = 1.0 - (1.0 - DUCK[channel]) * PUMP.get(story_at(sections, at), 0.7) * min(loud / 0.8, 1.0)
            # Down just before the stroke, held for a moment, and back over the channel's own time, slowly at first so
            # that it swells into the off-beat.
            back = RECOVER[channel]
            moves += [(at - 0.02, 1.0), (at, down), (at + 0.08, down), (at + 0.6 * back, down + 0.35 * (1.0 - down)), (at + back, 1.0)]
            last = at + back
        bus = sounds.bus(channel, style="house")
        if channel == "drums":
            # A drum machine on a dance floor is not a kit in a hall: no room around it and no tape on it, only the box
            # at 250 Hz taken down and a compressor slow enough to let every stroke through (measured against the liked
            # house stems: the strokes rose a third as fast as theirs through the orchestra's drum bus).
            bus = [sounds.equalise(low_cut=28.0, bands=((250.0, -3.0, 1.2),)), sounds.squeeze(-16.0, 2.5, 12.0, 120.0, 1.5),
                   sounds.ceiling(-1.0, push=1.5)]
        drive = ACTS[about["sounds"]].drive if about.get("sounds") in ACTS else 0.0
        if drive and channel == "drums":
            # A hard act's drums (2026-11-24): what rings between the strokes brought up under them, and the whole through hot tape.
            bus = bus[:-1] + [sounds.smash(0.55 * drive, makeup=8.0), sounds.warm(drive), sounds.equalise(high_shelf=(3000.0, 2.0 * drive))] + bus[-1:]
        elif drive and channel == "bass":
            bus = bus[:-1] + [sounds.burn(0.4 * drive), sounds.warm(drive), sounds.enhance(0.5 * drive)] + bus[-1:]
        elif drive and channel == "rhythm":
            # ...its stabs (the whole of Riot Line's and Blast Furnace's mixes stood 3 dB short from 1.2 to 5 kHz of what such a record has there).
            bus = bus[:-1] + [sounds.equalise(low_cut=90.0, bands=((2500.0, 2.5, 0.9),)), sounds.warm(0.4 * drive)] + bus[-1:]
        elif drive and channel == "lead":
            # ...and its lead: a riff at the bottom of a synth's range is dull (Blast Furnace's 21 dB down from 5 kHz): its edge up, hot tape, a little air made out of it.
            bus = bus[:-1] + [sounds.equalise(low_cut=110.0, bands=((1800.0, 1.5, 0.9),), high_shelf=(3200.0, 3.0)), sounds.warm(0.6 * drive), sounds.excite(0.3 * drive)] + bus[-1:]
        folders.append((desk.Line(channel, desk.bare(channel, []), effects=bus, moves=moves), under[channel]))
    seconds = sheet.bars * house.BAR
    rpp = work / "track.rpp"
    rpp.write_text(desk.project(folders, bpm=float(house.BPM), seconds=seconds, out=work, tail=forever.POST_S,
                                 hall=sounds.hall(ROOM[0], top=ROOM[1], low=ROOM[2], low_ring=ROOM[3])), encoding="utf-8")
    with reaper.Display() as display:
        desk.render(rpp, display=display, timeout=300.0 + 12.0 * seconds)       # (see build.stage)
    parts = desk.stems(work, [bus.name for bus, _ in folders], frames)
    # Each channel to its place by how loud it is where the track is fullest, as the writer's own mix did it. (Measured
    # here and done in REAPER, as a mixer would: see below.)
    story, first, count = next(section for section in reversed(sections) if section[0] == "moment")     # the last drop
    a, b = int(round(first * house.BAR_FRAMES)), int(round((first + count) * house.BAR_FRAMES))
    want = dict(PLACE, **(CALM if about["calm"] else {}))
    if not about["kick"]:
        want["drums"] = -27.0
    if about.get("sounds") in ACTS and ACTS[about["sounds"]].drive and not about["calm"]:
        # (A hard act stands on its drums and its bass, and its lead is heard: 2026-11-24, 17:40, each channel of three songs left out in turn, the bass was what their hardness was, 4 to 5 of it by its
        # measure, and the lead what softened them: the bass a decibel up and the lead, which had been 3 dB nearer, 2.)
        want = {**want, "drums": want["drums"] + 0.7, "bass": want["bass"] + 1.0, "lead": want["lead"] + 2.0, "rhythm": want["rhythm"] + 1.5, "texture": want["texture"] - 3.0}
    faders = {}
    alone: dict[str, list[tuple[float, float]]] = {}
    hard = about.get("sounds") in ACTS and ACTS[about["sounds"]].drive > 0.0 and not about["calm"]
    held = {} if about["calm"] else HELD_BACK if hard else HELD_BACK_SOFTER
    for channel in list(parts):
        have = analysis.loudness_lufs(parts[channel][a:b], RATE)
        if have < -70.0:
            have = analysis.loudness_lufs(parts[channel], RATE)
        if have < -70.0:
            del parts[channel]                       # it plays nothing to speak of in this take
            continue
        # ...but never so far up that another part of the story goes more than 3 dB over the channel's place (as the
        # orchestra's desk does since 2026-11-17, night: a house tune soft at its drop and full in its theme blared there).
        edges = [0] + [int(round((first + count) * house.BAR_FRAMES)) for _, first, count in sections]
        if channel in RIDDEN:
            # The hook stands at its place at the drop, and a part of the story that would stand more than 3 dB over it is
            # ridden down to that on the channel's own volume envelope, as a mixer rides a fader (2026-11-19: Blades III's
            # riff was 15 dB under its rises at the drops, the whole channel turned down by its rises; then its chords 5).
            faders[channel] = 10.0 ** ((want[channel] - have) / 20.0)
            parts[channel] = (parts[channel] * faders[channel]).astype(np.float32)
            # (A hard song's lead is nowhere louder than at its drop: Riot Line's stood 3 dB over it in its rises and as it left.)
            ride = ridden(parts[channel], list(zip(edges, edges[1:])), want[channel] + (0.0 if hard else 3.0), int(house.BAR_FRAMES))
            if held.get(channel):
                ride = held_back(sections, channel, frames, 1.0 if ride is None else ride, held)
            if ride is not None:
                parts[channel] = (parts[channel] * ride[:, None]).astype(np.float32)
                alone[channel] = desk.ride_points(ride)
            continue
        have = max(have, max(analysis.loudness_lufs(parts[channel][low:high], RATE) for low, high in zip(edges, edges[1:])) - 3.0)
        faders[channel] = 10.0 ** ((want[channel] - have) / 20.0)
        parts[channel] = (parts[channel] * faders[channel]).astype(np.float32)
        if held.get(channel):
            ride = held_back(sections, channel, frames, held=held)
            parts[channel] = (parts[channel] * ride[:, None]).astype(np.float32)
            alone[channel] = desk.ride_points(ride)
    # What is still ringing two seconds before the recording ends is eased away to nothing (as the writer's own render does).
    last = int(2.0 * RATE)
    ease = np.ones(frames, dtype=np.float32)
    ease[-last:] = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, last)))
    eased = {channel: audio * ease[:, None] for channel, audio in parts.items()}
    # The track to its level and its peaks under the ceiling (house.master), and if one channel alone would still be
    # over the top, the others pulling the other way in the mix, all come down together.
    up, need = house.master_gains(eased, a, b)
    curve = ease * need.astype(np.float32)
    peak = max(float(np.max(np.abs(audio * (up * need)[:, None]))) for audio in eased.values())
    extra = 0.97 / peak if peak > 0.97 else 1.0
    # The mix itself is REAPER's (2026-11-17, night: "remember to use reaper and plugins for effects and mixing"): each
    # channel's stem on a track of its own, its fader where it was measured to go, the peaks held and the end faded by
    # the volume envelope, rendered again; the project is kept as mix.rpp beside the track's own.
    recorded = {channel: work / (channel + ".wav") for channel in parts}
    with reaper.Display() as display:
        parts = desk.mixdown(work, recorded, faders={channel: faders[channel] * up * extra for channel in parts},
                             ride=desk.ride_points(curve), bpm=float(house.BPM), seconds=seconds, tail=forever.POST_S,
                             frames=frames, display=display, timeout=300.0 + seconds, alone=alone)
    for bus, _ in folders:
        (work / (bus.name + ".wav")).unlink()
    meta = dict(about["meta"])
    meta["credit"] = ("Written by FreeRock's studio (studio.house); played in REAPER by the Surge XT synth (with Argitoth's Trance Lead 1, "
                      "a patch that ships with it), MuseScore Studio's Muse Sounds (Muse Group) "
                      "MckAudio's TR-8 drum-machine recordings (CC0) and, in some songs, Karoryfer's and others' recordings (CC0) in the sfizz "
                      "sampler, put together by studio.club.")
    found = house.measure(meta, parts)
    if "lead" in parts and sheet.parts.get("lead") and not about["calm"]:
        # The riff, stroke by stroke (strokes_off): of the voice that has the most of the drops, in the first of them.
        drops = [(first * 4.0, (first + count) * 4.0) for story, first, count in sections if story == "moment"]
        big = max(sheet.parts["lead"], key=lambda each: sum(any(a <= note.start < b for a, b in drops) for note in sheet.parts["lead"][each].notes))
        for each in [big] + [name for name in sorted(sheet.parts["lead"]) if name != big and name.endswith(CUT_NAMES[1:])]:
            part = sheet.parts["lead"][each]
            off = strokes_off(part.notes, parts["lead"], house.BAR_FRAMES / 4.0, drops[0] if each == big else (drops[0][0], drops[-1][1]))
            found.setdefault("strokes", {}).update(off if each == big else {"%s %d" % (part.instrument, pitch): cents for pitch, cents in off.items()})
            wrong = {pitch: cents for pitch, cents in off.items() if abs(cents) > STROKE_OFF}
            if wrong:
                found["problems"] = list(found.get("problems") or []) + ["the lead's strokes are out of tune (%s): %s" % (
                    part.instrument, ", ".join("%d by %+.0f cents" % each for each in wrong.items()))]
    folder = stage_root(VAR, "house") / name / str(take)
    write_track(folder, meta, parts)
    sheet.save(folder / "sheet.json")
    found.update(family=name, take=take, title=meta["title"], seconds=round(seconds, 1), took=round(time.time() - began, 1),
                 voices=sorted("%s: %s %s -> %s" % (channel, table, sound, heard.played.get((channel, table, sound)) or PLAYED[(table, sound)])
                              for channel, table, sound in heard.notes))
    scratch = folder / "measured.json.new"
    scratch.write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
    scratch.replace(folder / "measured.json")
    return found


def main(argv: list[str] | None = None) -> int:
    names = argv if argv is not None else sys.argv[1:]
    if not names:
        print(__doc__)
        return 2
    if names == ["--list"]:
        for each in house.PLAN:
            print("%-13s %-22s %-10s %-7s %-14s %s  %s bars  %s  swing %.2f  %s" % (
                each.name, each.title, each.key, each.role, ",".join(each.moods), "light" if each.light else "heavy",
                each.bars, each.groove, each.swing, each.palette))
        print("%d families, takes %s of each" % (len(house.PLAN), ", ".join(str(take) for take in house.TAKES)))
        return 0
    reaper.configure()
    for each in names:
        name, take = each.rsplit("/", 1)
        found = stage(name, int(take))
        print("%s/%s  %s: %d s of music in %.0f s; problems: %s" % (name, take, found["title"], found["seconds"], found["took"], found.get("problems") or "none"))
        for voice in found["voices"]:
            print("    " + voice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
