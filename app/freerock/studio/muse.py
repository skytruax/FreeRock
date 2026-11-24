"""The orchestra as MuseScore plays it.

The studio's own sampled instruments were heard and turned down ("still sounds like a 90s
windows demo", "we just need a good renderer", 2026-11-16). MuseScore Studio comes with Muse
Sounds: an orchestra that is given a score, not notes to trigger, and plays it as players
would: it reads the dynamics, the slurs, the dots over short notes, the tremolo strokes and
"pizz.", and chooses how to play from them. So here a written voice is written out as a
score (MusicXML), MuseScore performs it with no window, and the recording is laid on a REAPER
track, where the rest of the studio's work (the drums, the mix, the hall) goes on as before.

    MuseScore Studio      var/tools/musescore/squashfs-root (the AppImage, unpacked)
    Muse Sounds           fetched by the Muse Sounds Manager into ~/Muse Sounds (a link to the
                          assets drive); the sampler itself is under ~/.local/share/MuseSampler

`PARTS` says which written instruments MuseScore plays and as what; `available` whether the
Muse Sounds are there; `score` writes a voice as MusicXML; `perform` has MuseScore play it
(kept by what is in it, so a voice is performed once); `line` gives the REAPER track.

What MuseScore is told the part is called settles which of its instruments plays: "Violins 1"
is the section, "Violin" one player (found by trying, MuseScore 4.7.7). Pitches are written as
they sound; MuseScore plays them so for every instrument (measured: a horn's written A is A).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

import numpy as np

from . import desk
from .score import Note

HOME = desk.VAR / "tools" / "musescore" / "squashfs-root"
KEPT = desk.VAR / "reaper" / "muse"                # every performance, by what was in its score
DIVISIONS = 8                                      # to a quarter note: the shortest written note is a thirty-second
BAR = 4 * DIVISIONS                                # every score is written in four-four: bar lines are not heard
STEPS = ("C", "C", "D", "E", "E", "F", "F", "G", "A", "A", "B", "B")
ALTERS = (0, 1, 0, -1, 0, 0, 1, 0, -1, 0, -1, 0)
# Note values in divisions, longest first, with the name MusicXML has for each and whether it is dotted.
VALUES = ((32, "whole", False), (24, "half", True), (16, "half", False), (12, "quarter", True), (8, "quarter", False), (6, "eighth", True),
          (4, "eighth", False), (3, "16th", True), (2, "16th", False), (1, "32nd", False))
MARKS_PP = ((0.30, "pp"), (0.42, "p"), (0.54, "mp"), (0.66, "mf"), (0.80, "f"), (9.0, "ff"))
# (2026-11-20: a valley's held pad, written pp at the floor of those marks, stood over a soft plucked tune; Muse Sounds play
# ppp. orchestra.VALLEY_SOFT writes a valley's pad that soft.) The softest strength is ppp.
MARKS = ((0.15, "ppp"),) + MARKS_PP

# Written instrument -> the parts that play it: (MuseScore's name for the part, the lowest and highest note it takes,
# how it is played: "" as written, "trem" with tremolo strokes, "pizz" plucked). An instrument that is a whole
# string orchestra under one name is shared out by register, each section taking the notes that lie well for it.
_STRINGS = (("Contrabasses", 0, 47), ("Violoncellos", 48, 59), ("Violas", 60, 71), ("Violins 1", 72, 127))
PARTS: dict[str, tuple[tuple, ...]] = {
    "violins": (("Violins 1", 0, 127, ""),), "violins slow": (("Violins 1", 0, 127, ""),), "violas": (("Violas", 0, 127, ""),),
    "celli": (("Violoncellos", 0, 127, ""),), "celli slow": (("Violoncellos", 0, 127, ""),),
    "basses": (("Contrabasses", 0, 127, ""),), "basses slow": (("Contrabasses", 0, 127, ""),),
    "celli pizz": (("Violoncellos", 0, 127, "pizz"),), "basses pizz": (("Contrabasses", 0, 127, "pizz"),),
    "strings": tuple(each + ("",) for each in _STRINGS), "strings slow": tuple(each + ("",) for each in _STRINGS),
    "tremolo": tuple(each + ("trem",) for each in _STRINGS), "pizzicato": tuple(each + ("pizz",) for each in _STRINGS),
    "violin": (("Violin", 0, 127, ""),), "fiddle": (("Violin", 0, 127, ""),), "viola": (("Viola", 0, 127, ""),), "cello": (("Violoncello", 0, 127, ""),),
    "flute": (("Flute", 0, 127, ""),), "piccolo": (("Piccolo", 0, 127, ""),), "oboe": (("Oboe", 0, 127, ""),),
    "english horn": (("English Horn", 0, 127, ""),), "clarinet": (("Clarinet in B♭", 0, 127, ""),), "bassoon": (("Bassoon", 0, 127, ""),),
    "horns": (("Horn in F", 0, 127, ""),), "trumpet": (("Trumpet in B♭", 0, 127, ""),), "trombone": (("Trombone", 0, 127, ""),),
    "tuba": (("Tuba", 0, 127, ""),),
    "brass": (("Trombone", 0, 54, ""), ("Horn in F", 55, 66, ""), ("Trumpet in B♭", 67, 127, "")),
    "harp": (("Harp", 0, 127, ""),), "celesta": (("Celesta", 0, 127, ""),), "glock": (("Glockenspiel", 0, 127, ""),),
    "vibes": (("Vibraphone", 0, 127, ""),), "marimba": (("Marimba", 0, 127, ""),), "xylophone": (("Xylophone", 0, 127, ""),),
    "bells": (("Tubular Bells", 0, 127, ""),), "piano": (("Piano", 0, 127, ""),),
    "choir": (("Men", 0, 59, ""), ("Women", 60, 127, "")), "oohs": (("Men", 0, 59, ""), ("Women", 60, 127, "")),
    "timpani": (("Timpani", 0, 127, ""),),
    # Instruments Muse Sounds has no recording of are given the nearest it has, by name (a fifth word: the sound).
    # Better a well-played relation than a poor recording of the thing itself: every one of these was a sample
    # set of the studio's own before, and those were turned down by ear.
    "guitar": (("Classical Guitar", 0, 127, "", "Muse Guitars Vol 1/Acoustic Nylon"),),
    "steel guitar": (("Classical Guitar", 0, 127, "", "Muse Guitars Vol 1/Acoustic Steel Plucked"),),
    "twelve string": (("Classical Guitar", 0, 127, "", "Muse Guitars Vol 1/Acoustic Steel Picked"),),
    "mandolin": (("Classical Guitar", 0, 127, "", "Muse Guitars Vol 1/Acoustic Steel Picked"),),
    "sitar": (("Classical Guitar", 0, 127, "", "Muse Guitars Vol 1/Acoustic Steel Plucked"),),
    "koto": (("Harp", 0, 127, ""),), "dulcimer": (("Harp", 0, 127, ""),),
    "fretless": (("Bass Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric Bass"),),
    "acoustic bass": (("Contrabasses", 0, 127, "pizz"),),
    "harpsichord": (("Harpsichord", 0, 127, "", "Muse Keys/Harpsichord"),),
    "music box": (("Celesta", 0, 127, "", "Muse Music Box/Jewellery Music Box"),),
    "kalimba": (("Marimba", 0, 127, ""),), "church bell": (("Tubular Bells", 0, 127, ""),),
    "recorder": (("Flute", 0, 127, "", "Muse Woodwinds/Flute 2"),), "whistle": (("Piccolo", 0, 127, ""),),
    "pan flute": (("Flute", 0, 127, "", "Muse Woodwinds/Alto Flute"),), "shakuhachi": (("Flute", 0, 127, "", "Muse Woodwinds/Alto Flute"),),
    "ocarina": (("Flute", 0, 127, "", "Muse Woodwinds/Flute 1"),),
    "shenai": (("Oboe", 0, 127, ""),),
    # The bagpipe's tunes are the studio's own since 2026-11-18 (FreePats' chanter, chosen by ear: "new horn sounds
    # better"); its held drones stay MuseScore's english horn: held, the chanter's upper middle stood over its body.
    "pipe drone": (("English Horn", 0, 127, ""),),
    # Colours added for variety (2026-11-16): sounds Muse has, given to a part of the nearest kind.
    "bass flute": (("Flute", 0, 127, "", "Muse Woodwinds/Bass Flute"),),
    "bass clarinet": (("Clarinet in B♭", 0, 127, "", "Muse Woodwinds/Bass Clarinet"),),
    "handbells": (("Tubular Bells", 0, 127, "", "Muse Handbells/Handbells"),),
    "euphonium": (("Tuba", 0, 127, "", "Muse Brass/Euphonium"),),
    "contrabassoon": (("Bassoon", 0, 127, "", "Muse Woodwinds/Contrabassoon"),),
    "contrabass flute": (("Flute", 0, 127, "", "Muse Woodwinds/Contrabass Flute"),),
    "eb clarinet": (("Clarinet in B♭", 0, 127, "", "Muse Woodwinds/Clarinet in Eb"),),
    "full choir": (("Women", 0, 127, "", "Muse Choir/Full Choir"),),
    "handchimes": (("Tubular Bells", 0, 127, "", "Muse Handbells/Handchimes"),),
    "dream piano": (("Piano", 0, 127, "", "Muse Keys/Dream Piano"),),
    # For the house desk (studio/club.py): a grand that is always the grand, and the two electric pianos.
    "house piano": (("Piano", 0, 127, "", "Muse Keys/Piano"),),
    "electric piano": (("Piano", 0, 127, "", "Muse Keys/Suitcase Piano"),),
    "wurly": (("Piano", 0, 127, "", "Muse Keys/Wurly 200A"),),
    # The band. The riff is played twice, as a record is made: a Les Paul on one side and a Stratocaster on the
    # other, each through its own amplifier (two parts with the same notes; `sounds` seats them). The Les Paul has
    # the weight (its low strings are all there), the Stratocaster the bite. The tune is the Les Paul's lead tone:
    # the Stratocaster's has four times the power between 2.5 and 5 kHz that it has anywhere else (measured), which
    # is the "cheesy" lead that was turned down by ear before. A band's plain guitar is the Stratocaster played clean.
    "rhythm guitar": (("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Heavy"),
                      ("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Heavy")),
    # A riff's muted notes (the heel of the hand on the strings) are the same two guitars playing short, with the
    # top taken off at the desk: dull and percussive, as a muted string is.
    "muted guitar": (("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Heavy"),
                     ("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Heavy")),
    "lead guitar": (("Electric Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Lead"),),
    "single guitar": (("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Heavy"),),      # the Les Paul alone: a heavy band's opening riff
    "clean guitar": (("Clean Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean"),),
    "picked bass": (("Bass Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric Bass"),),
    "rock organ": (("Hammond Organ", 0, 127, "", "Muse Keys/Hammond Organ"),),
    # The bands' other sounds (2026-11-23: "too much of the same instrument sounds"). The guitars are Muse's clean ones, each through an amplifier of
    # the studio's own (sounds.AMPS); a pair of them, where a riff is played twice, one on each side.
    "soprano sax": (("Clarinet in B♭", 0, 127, "", "Muse Woodwinds/Soprano Saxophone"),),
    "alto sax": (("Clarinet in B♭", 0, 127, "", "Muse Woodwinds/Alto Saxophone"),),
    "tenor sax": (("Clarinet in B♭", 0, 127, "", "Muse Woodwinds/Tenor Saxophone"),),
    "bari sax": (("Bassoon", 0, 127, "", "Muse Woodwinds/Baritone Saxophone"),),
    "rhodes": (("Piano", 0, 127, "", "Muse Keys/Suitcase Piano"),), "upright piano": (("Piano", 0, 127, "", "Muse Keys/Upright Piano"),),
    # (a tuba that plays a band's bass line, held together as a bass is: SQUEEZE)
    "stomp tuba": (("Tuba", 0, 127, ""),),
    # (an organ and an electric piano torn by their amplifiers)
    "torn organ": (("Hammond Organ", 0, 127, "", "Muse Keys/Hammond Organ"),), "fuzz wurly": (("Piano", 0, 127, "", "Muse Keys/Wurly 200A"),),
    # (two cellos and a viola, each through an amplifier)
    "riff celli": (("Violoncello", 0, 127, ""), ("Violoncello", 0, 127, "")), "muted celli": (("Violoncello", 0, 127, "pizz"), ("Violoncello", 0, 127, "pizz")),
    "fuzz viola": (("Viola", 0, 127, ""),),
    "crunch guitar": (("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"), ("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean")),
    "crunch muted": (("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"), ("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean")),
    "fuzz guitar": (("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"), ("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean")),
    "fuzz muted": (("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"),),
    "doom guitar": (("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"), ("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean")),
    "doom muted": (("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"),),
    "chop guitar": (("Rhythm Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean"),),
    "chop muted": (("Muted Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean"),),
    "twang guitar": (("Clean Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean"),),
    "chime guitar": (("Clean Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"),),
    "sweet lead": (("Electric Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric SC - Clean"),),
    "fuzz lead": (("Electric Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric LP - Clean"),),
    "fuzz bass": (("Bass Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric Bass"),), "round bass": (("Bass Guitar", 0, 127, "", "Muse Guitars Vol 1/Electric Bass"),),
    # The orchestra's percussion that Muse Percussion plays (2026-11-17, night: "get everything out of muse"). Written
    # on a drum staff: each note's pitch is the drum it strikes (see PERCUSSION). A "trem" part is a roll.
    "taikos": (("Taiko", 0, 127, ""),), "tam-tam": (("Tam-tam", 0, 127, ""),), "mark tree": (("Mark Tree", 0, 127, ""),),
    "field drum": (("Field Drum", 0, 127, ""),), "field drum roll": (("Field Drum", 0, 127, "trem"),),
    "cymbal roll": (("Suspended Cymbal", 0, 127, "trem"),), "piatti": (("Crash Cymbals", 0, 127, ""),),
    "concert drum": (("Concert Bass Drum", 0, 127, ""),), "concert drum roll": (("Concert Bass Drum", 0, 127, "trem"),),
}
# The drum staves: for each, the sound MusicXML names it by (or nothing, where MuseScore knows it by its name alone) and
# its drums, by the pitch MuseScore files each under. Found by asking MuseScore 4.7 what it makes of each name
# (2026-11-17, night); every one was heard played by Muse Percussion, rolls and dynamics too.
PERCUSSION: dict[str, tuple[str, tuple[tuple[int, str], ...]]] = {
    "Taiko": ("drum.taiko", ((86, "Taiko Mute"), (87, "Taiko"))),
    "Tam-tam": ("", ((52, "Tam-tam"),)),
    "Mark Tree": ("", ((84, "Glissando Down"),)),
    "Field Drum": ("drum.snare-drum", ((37, "Side Stick"), (38, "Snare"))),
    "Suspended Cymbal": ("", ((57, "Suspended Cymbal"),)),
    "Crash Cymbals": ("metal.cymbal.crash", ((57, "Hand Cymbals"),)),
    "Concert Bass Drum": ("drum.bass-drum", ((36, "Concert Bass Drum"),)),
}
# What MuseScore has to be told about a part beside its name, for the part to be that instrument and not a
# nameless staff played by its plain built-in sounds: the instrument's sound in MusicXML's list, and a program.
KINDS = {
    "Violins 1": ("strings.violin", 49), "Violins 2": ("strings.violin", 49), "Violas": ("strings.viola", 49), "Violoncellos": ("strings.cello", 49),
    "Contrabasses": ("strings.contrabass", 49), "Violin": ("strings.violin", 41), "Viola": ("strings.viola", 42), "Violoncello": ("strings.cello", 43),
    "Flute": ("wind.flutes.flute", 74), "Piccolo": ("wind.flutes.flute.piccolo", 73), "Oboe": ("wind.reed.oboe", 69),
    "English Horn": ("wind.reed.english-horn", 70), "Clarinet in B♭": ("wind.reed.clarinet.bflat", 72), "Bassoon": ("wind.reed.bassoon", 71),
    "Horn in F": ("brass.french-horn", 61), "Trumpet in B♭": ("brass.trumpet.bflat", 57), "Trombone": ("brass.trombone", 58), "Tuba": ("brass.tuba", 59),
    "Harp": ("pluck.harp", 47), "Celesta": ("keyboard.celesta", 9), "Piano": ("keyboard.piano", 1), "Men": ("voice.male", 53), "Women": ("voice.female", 53),
    "Timpani": ("drum.timpani", 48), "Glockenspiel": ("pitched-percussion.glockenspiel", 10), "Vibraphone": ("pitched-percussion.vibraphone", 12),
    "Marimba": ("pitched-percussion.marimba", 13), "Xylophone": ("pitched-percussion.xylophone", 14), "Tubular Bells": ("pitched-percussion.tubular-bells", 15),
    "Classical Guitar": ("pluck.guitar.nylon-string", 25), "Bass Guitar": ("pluck.bass.electric", 34), "Harpsichord": ("keyboard.harpsichord", 7),
    "Electric Guitar": ("pluck.guitar.electric", 31), "Rhythm Guitar": ("pluck.guitar.electric", 31), "Muted Guitar": ("pluck.guitar.electric", 31),
    "Clean Guitar": ("pluck.guitar.electric", 28),
    "Hammond Organ": ("keyboard.organ.drawbar", 17),
}
# Which Muse Sound plays a part, where it is not the one MuseScore picks by itself (its first: one horn, one
# trumpet, the first violins): the sounds a part may be given, as they are filed under ~/Muse Sounds. A piece
# draws one for each part from its own seed (`voiced`), so two pieces do not have the same orchestra.
CHOICES: dict[str, tuple[str, ...]] = {
    "Violins 1": ("Muse Strings/Violins 1", "Muse Strings/Violins 2"),
    "Violin": ("Muse Strings/Violin 1 Solo", "Muse Strings/Violin 2 Solo"),
    "Horn in F": ("Muse Brass/French Horns a6", "Muse Brass/French Horns a6", "Muse Brass/French Horn"),       # six horns twice as often as one
    "Trumpet in B♭": ("Muse Brass/Trumpet", "Muse Brass/Trumpets a4"),
    "Trombone": ("Muse Brass/Trombones a3", "Muse Brass/Trombone", "Muse Brass/Bass Trombone"),
    "Tuba": ("Muse Brass/Tuba", "Muse Brass/Cimbasso"),
    "Flute": ("Muse Woodwinds/Flute 1", "Muse Woodwinds/Flute 2"),
    "Piano": ("Muse Keys/Piano", "Muse Keys/Soft Piano", "Muse Keys/Upright Piano"),
    "Harp": ("Muse Harp/Harp", "Muse Harp/Harp", "Muse Keys/Piano"),                       # in one piece out of three the harp's part is a piano's
    "Celesta": ("Muse Keys/Celesta", "Muse Music Box/Joana's Music Box"),
    "Oboe": ("Muse Woodwinds/Oboe", "Muse Woodwinds/Oboe", "Muse Woodwinds/English Horn"),
    "Women": ("Muse Choir/Women", "Muse Choir/Sopranos", "Muse Choir/Altos"),
    "Men": ("Muse Choir/Men", "Muse Choir/Tenors", "Muse Choir/Basses"),
}
STRUCK = ("Harp", "Celesta", "Glockenspiel", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Piano", "Timpani", "Classical Guitar", "Bass Guitar",
          "Harpsichord", "Rhythm Guitar", "Muted Guitar", "Clean Guitar") + tuple(PERCUSSION)      # no dots, no slurs: each note rings (a lead guitar's line is slurred: hammered on and pulled off)


def program() -> Path:
    return HOME / "AppRun"


def sounds() -> bool:
    """Whether the Muse Sounds are installed: the sampler's library is where the manager puts it."""
    return any((Path.home() / ".local" / "share" / "MuseSampler").rglob("libMuseSamplerCoreLib.so"))


def available() -> bool:
    """Whether MuseScore plays the orchestra: the program is there, and so are the Muse Sounds
    (or FREEROCK_MUSE=basic asks for its plain built-in sounds, to try the way through)."""
    return program().is_file() and (sounds() or os.environ.get("FREEROCK_MUSE") == "basic")


def _mark(loud: float) -> int:
    return next(index for index, (under, _) in enumerate(MARKS) if loud < under)


# A held note is never still. MuseScore's players follow a hairpin under a held note, smoothly (measured
# 2026-11-16: a crescendo from p to f under one note of the violins rises 18 dB over its length, a horn's 30 dB),
# and written without one they hold every long note at one level, which is what made the orchestra sound flat.
LONG_S = 2.5                   # seconds: a note held this long is leaned into and let fall away (at 1.5 nearly every
                               # note of a slow piece swelled, which read as pumping, not phrasing: 2026-11-16, night)
UNSHAPED = ("Electric Guitar",)        # held, but left as it is: a guitar's note can only die away
_DYNAMIC = '<direction placement="below"><direction-type><dynamics><%s/></dynamics></direction-type></direction>'
_WEDGE = '<direction placement="below"><direction-type><wedge type="%s" number="1"/></direction-type></direction>'


def _events(notes: list[Note]) -> list[list[list]]:
    """The notes as voices of a staff: in each voice, events that do not overlap, each
    [start, length, pitches, strength, seconds long as written], in divisions. Notes begun
    together with the same length are one chord."""
    voices: list[list[list]] = []
    for note in sorted(notes, key=lambda each: (each.start, -each.length, each.pitch)):
        start = int(round(note.start * DIVISIONS))
        length = max(int(round(note.length * DIVISIONS)), 1)
        for voice in voices:
            last = voice[-1]
            if last[0] == start and last[1] == length:
                if note.pitch not in last[2]:
                    last[2].append(note.pitch)
                break
            if last[0] + last[1] <= start:
                voice.append([start, length, [note.pitch], note.loud, note.length])
                break
            if last[0] < start < last[0] + last[1] and len(voices) >= 4:
                last[1] = start - last[0]                      # a fifth voice there is no room for: the note before it is cut short
                voice.append([start, length, [note.pitch], note.loud, note.length])
                break
        else:
            if len(voices) >= 4:
                continue                                       # begun exactly with four other lines of other lengths: left out
            voices.append([[start, length, [note.pitch], note.loud, note.length]])
    return voices


def score(part: str, notes: list[Note], *, bpm: float, way: str = "", swells: list[tuple[float, float]] | None = None) -> str:
    """One instrument's notes as a score in MusicXML, written the way a player is given it:
    dynamics where the strength changes, a dot on a short note, a slur over notes that follow
    at once on each other in a single line, an accent on a note struck harder than those
    about it; tremolo strokes or "pizz." where `way` says so.

    A long note of a bowed, blown or sung part has a hairpin under it: it begins a mark under
    its strength, is fullest past its middle and eases off, further at the end of a phrase.
    `swells` is the writer's own rise and fall for the part ((beat, 0 to 1), as a pad has
    through the story): each note is as strong as the swell is where it begins, and a long
    note goes with the swell to where it stands at the note's end."""
    voices = _events(notes)
    if not voices:
        raise ValueError("There are no notes to write for %s" % part)
    struck = part in STRUCK and not (part in PERCUSSION and way == "trem")      # a roll is shaped like a held note
    drum = part in PERCUSSION
    beat_s = 60.0 / bpm
    if swells:
        drawn = sorted(swells)
        beats, amounts = [beat for beat, _ in drawn], [max(amount, 0.0) ** 0.8 for _, amount in drawn]

        def swell(division: float) -> float:
            return max(float(np.interp(division / DIVISIONS, beats, amounts)), 0.05)
        for voice in voices:
            for event in voice:
                event[3] = min(event[3] * swell(event[0]), 1.0)
    single = len(voices) == 1 and all(len(event[2]) == 1 for event in voices[0])
    # How each event is played, voice by voice: its dynamic mark if it changes there, dot, accent, slur.
    told: dict[tuple[int, int], dict] = {}
    now, level = None, None
    first = sorted((event[0], index, at) for index, voice in enumerate(voices) for at, event in enumerate(voice))
    for _, index, at in first:
        event = voices[index][at]
        how = told.setdefault((index, at), {})
        if index == 0:
            mark = _mark(event[3])
            # A new mark only when the strength has truly moved: not for a note a shade over a line.
            edge = MARKS[mark - 1][0] if mark else 0.0
            if now is None or (mark != now and abs(event[3] - (level or 0.0)) >= 0.05 and not (mark == now + 1 and event[3] - edge < 0.03)):
                how["mark"], now, level = MARKS[mark][1], mark, event[3]
            elif event[3] - (level or 0.0) >= 0.13 and not struck:
                how["accent"] = True
            how["level"] = now
        if not struck and way == "" and event[4] * beat_s < 0.28:
            how["dot"] = True
    # The hairpins under the long notes of the first voice (a staff has one set of dynamics): what is written in
    # the middle of a note or at its end, by where in the piece it stands, in divisions.
    timed: list[tuple[int, str]] = []
    if not struck and way != "pizz" and part not in UNSHAPED:
        voice, restate, carried = voices[0], False, False
        for at, event in enumerate(voice):
            how, here = told[(0, at)], told[(0, at)]["level"]
            if restate and "mark" not in how:
                how["mark"] = MARKS[here][1]               # after a hairpin the strength is said again
            restate, arrived, carried = False, carried, False
            if event[4] * beat_s < LONG_S or event[1] < 4:
                continue
            after = voice[at + 1] if at + 1 < len(voice) else None
            end = event[0] + event[1]
            joined = after is not None and after[0] <= end
            if swells:
                goal = _mark(min(event[3] * swell(end) / swell(event[0]), 1.0))
                if goal != here:
                    # The writer's swell moves under this note: the note goes with it.
                    how["mark"], how["wedge"], restate = MARKS[here][1], "crescendo" if goal > here else "diminuendo", True
                    timed.append((end, _WEDGE % "stop" + ("" if joined else _DYNAMIC % MARKS[goal][1])))
                    continue
            # A line of long notes that run into each other is one breath: leaned into on its first note, held
            # through the ones between, let fall on its last. A long note by itself is all three.
            holds = joined and told[(0, at + 1)]["level"] >= here          # what follows at once is as strong
            peak, low = here, max(here - 1, 0)
            if low == peak:
                peak = min(peak + 1, len(MARKS) - 1)       # the softest there is: it swells up from there
            # Where it is fullest differs from note to note, and is the same each time the piece is written.
            draw = (event[0] / DIVISIONS * 7.31 + min(event[2]) * 0.37) % 1.0
            top = event[0] + min(max(int(round(event[1] * (0.5 + 0.25 * draw))), 1), event[1] - 1)
            if not arrived:
                how["mark"], how["wedge"] = MARKS[low][1], "crescendo"
                timed.append((top, _WEDGE % "stop" + _DYNAMIC % MARKS[peak][1] + ("" if holds else _WEDGE % "diminuendo")))
            elif not holds:
                timed.append((top, _WEDGE % "diminuendo"))
            if holds:
                carried = True
                restate = restate or not arrived
            else:
                ends_phrase = after is None or (after[0] - end) / DIVISIONS * beat_s >= 0.4
                timed.append((end, _WEDGE % "stop" + ("" if joined else _DYNAMIC % MARKS[max(low - 1, 0) if ends_phrase else low][1])))
                restate = True
    if single and not struck and way == "":
        voice = voices[0]
        run = False
        for at, event in enumerate(voice[:-1]):
            after = voice[at + 1]
            joined = (after[0] - event[0] - event[1] <= 1 and after[2] != event[2] and not told[(0, at)].get("dot")
                      and not told[(0, at + 1)].get("dot") and (after[0] - event[0]) / DIVISIONS * beat_s - event[4] * beat_s <= 0.09)
            if joined and not run:
                told[(0, at)]["slur"], run = "start", True
            elif not joined and run:
                told[(0, at)]["slur"], run = "stop", False
        if run:
            told[(0, len(voice) - 1)]["slur"] = "stop"
    end = max(event[0] + event[1] for voice in voices for event in voice)
    bars = -(-end // BAR)
    if drum:
        sound_name, drums = PERCUSSION[part]
        named = {pitch for voice in voices for event in voice for pitch in event[2]}
        unknown = named - {pitch for pitch, _ in drums}
        if unknown:
            raise ValueError("%s has no drum at %s: it has %s" % (part, sorted(unknown), ", ".join("%d %s" % each for each in drums)))
        heads = "".join('<score-instrument id="P1-I%d"><instrument-name>%s</instrument-name>%s</score-instrument>'
                        % (pitch, escape(name), "<instrument-sound>%s</instrument-sound>" % sound_name if sound_name else "") for pitch, name in drums)
        heads += "".join('<midi-instrument id="P1-I%d"><midi-channel>10</midi-channel><midi-unpitched>%d</midi-unpitched></midi-instrument>'
                         % (pitch, pitch + 1) for pitch, _ in drums)
        rows = ['<?xml version="1.0" encoding="UTF-8"?>', '<score-partwise version="4.0">', "<part-list>",
                '<score-part id="P1"><part-name>%s</part-name>%s</score-part>' % (escape(part), heads), "</part-list>", '<part id="P1">']
    else:
        kind, patch = KINDS[part]
        rows = ['<?xml version="1.0" encoding="UTF-8"?>', '<score-partwise version="4.0">', "<part-list>",
                '<score-part id="P1"><part-name>%s</part-name><score-instrument id="P1-I1"><instrument-name>%s</instrument-name>'
                '<instrument-sound>%s</instrument-sound></score-instrument><midi-instrument id="P1-I1"><midi-channel>1</midi-channel>'
                '<midi-program>%d</midi-program></midi-instrument></score-part>' % (escape(part), escape(part), kind, patch), "</part-list>", '<part id="P1">']

    def lengths(span: int) -> list[tuple[int, str, bool]]:
        out = []
        while span > 0:
            value = next(each for each in VALUES if each[0] <= span)
            out.append(value)
            span -= value[0]
        return out

    def rest(span: int, voice: int) -> list[str]:
        return ["<note><rest/><duration>%d</duration><voice>%d</voice><type>%s</type>%s</note>" % (size, voice + 1, kind, "<dot/>" if dotted else "")
                for size, kind, dotted in lengths(span)]

    def due(voice: int, at: int, span: int) -> list[str]:
        """What is written under the first voice between `at` and `at + span`: each said to stand so far on from here."""
        out = []
        while voice == 0 and timed and timed[0][0] < at + span:
            division, said = timed.pop(0)
            on = max(division - at, 0)
            out.append(said.replace("</direction>", "<offset>%d</offset></direction>" % on) if on else said)
        return out

    at_event = [0] * len(voices)
    held: list[list | None] = [None] * len(voices)            # an event that runs on over the bar line: [divisions left, pitches]
    for bar in range(bars):
        rows.append('<measure number="%d">' % (bar + 1))
        if bar == 0:
            if drum:
                rows.append("<attributes><divisions>%d</divisions><time><beats>4</beats><beat-type>4</beat-type></time>"
                            "<clef><sign>percussion</sign></clef></attributes>" % DIVISIONS)
            else:
                rows.append("<attributes><divisions>%d</divisions><time><beats>4</beats><beat-type>4</beat-type></time>"
                            "<clef><sign>%s</sign><line>%d</line></clef></attributes>" % ((DIVISIONS,) + (("F", 4) if min(min(event[2]) for event in voices[0]) < 52 else ("G", 2))))
            rows.append('<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>%.2f</per-minute></metronome>'
                        '</direction-type><sound tempo="%.2f"/></direction>' % (bpm, bpm))
            if way == "pizz":
                rows.append('<direction placement="above"><direction-type><words>pizz.</words></direction-type><sound pizzicato="yes"/></direction>')
        for index, voice in enumerate(voices):
            if index:
                rows.append("<backup><duration>%d</duration></backup>" % BAR)
            place, bar_at = 0, bar * BAR                       # how far into the bar this voice has been written
            if held[index]:
                left, pitches = held[index]
                span = min(left, BAR)
                rows += due(index, bar_at, span)
                rows += _sounding(pitches, span, index, lengths, tied_in=True, tied_out=left > BAR, how={}, way=way, drum=drum)
                held[index] = [left - span, pitches] if left > span else None
                place = span
            while at_event[index] < len(voice) and voice[at_event[index]][0] < bar_at + BAR:
                event = voice[at_event[index]]
                how = told.get((index, at_event[index]), {})
                if event[0] - bar_at > place:
                    rows += due(index, bar_at + place, event[0] - bar_at - place)
                    rows += rest(event[0] - bar_at - place, index)
                    place = event[0] - bar_at
                span = min(event[1], BAR - place)
                rows += due(index, bar_at + place, 1)                  # what ends where this note begins comes before its own marks
                if "mark" in how:
                    rows.append(_DYNAMIC % how["mark"])
                if "wedge" in how:
                    rows.append(_WEDGE % how["wedge"])
                rows += due(index, bar_at + place, span)
                rows += _sounding(event[2], span, index, lengths, tied_in=False, tied_out=event[1] > span, how=how, way=way, drum=drum)
                if event[1] > span:
                    held[index] = [event[1] - span, event[2]]
                place += span
                at_event[index] += 1
            if place < BAR:
                rows += due(index, bar_at + place, BAR - place)
                rows += rest(BAR - place, index)
        if bar == bars - 1:
            rows += [said for _, said in timed]                        # what ends with the last note of all
            timed.clear()
        rows.append("</measure>")
    rows += ["</part>", "</score-partwise>"]
    return "\n".join(rows) + "\n"


def _sounding(pitches: list[int], span: int, voice: int, lengths, *, tied_in: bool, tied_out: bool, how: dict, way: str,
              drum: bool = False) -> list[str]:
    """A note or a chord of `span` divisions as MusicXML: as many tied note values as it takes.
    On a drum staff (`drum`) a pitch is the drum struck, written on the staff's one line."""
    rows = []
    values = lengths(span)
    for order, (size, kind, dotted) in enumerate(values):
        begins, ends = order == 0, order == len(values) - 1
        tie_from, tie_to = tied_in or not begins, tied_out or not ends
        for which, pitch in enumerate(sorted(pitches)):
            words = ["<note>"]
            if which:
                words.append("<chord/>")
            if drum:
                words.append("<unpitched><display-step>C</display-step><display-octave>5</display-octave></unpitched><duration>%d</duration>" % size)
            else:
                alter = ALTERS[pitch % 12]
                words.append("<pitch><step>%s</step>%s<octave>%d</octave></pitch><duration>%d</duration>" % (
                    STEPS[pitch % 12], "<alter>%d</alter>" % alter if alter else "", pitch // 12 - 1, size))
            words.append('<tie type="stop"/>' if tie_from else "")
            words.append('<tie type="start"/>' if tie_to else "")
            if drum:
                words.append('<instrument id="P1-I%d"/>' % pitch)
            words.append("<voice>%d</voice><type>%s</type>%s" % (voice + 1, kind, "<dot/>" if dotted else ""))
            marks = []
            if tie_from:
                marks.append('<tied type="stop"/>')
            if tie_to:
                marks.append('<tied type="start"/>')
            if which == 0 and begins and not tied_in and how.get("slur") == "start":
                marks.append('<slur type="start" number="1"/>')
            if which == 0 and ends and not tied_out and how.get("slur") == "stop":
                marks.append('<slur type="stop" number="1"/>')
            played = []
            if begins and not tied_in and how.get("dot"):
                played.append("<staccato/>")
            if begins and not tied_in and how.get("accent"):
                played.append("<accent/>")
            if played:
                marks.append("<articulations>%s</articulations>" % "".join(played))
            if way == "trem" and size >= DIVISIONS // 2:
                marks.append('<ornaments><tremolo type="single">3</tremolo></ornaments>')
            if marks:
                words.append("<notations>%s</notations>" % "".join(marks))
            words.append("</note>")
            rows.append("".join(word for word in words if word))
    return rows


_ids: dict[str, int] | None = None
_busy: dict[str, threading.Lock] = {}
_busy_lock = threading.Lock()


def sound_id(sound: str) -> int:
    """The number the Muse sampler knows a sound by ("Muse Brass/French Horns a6"), from the
    list the Muse Sounds Manager keeps of what it has installed."""
    global _ids
    if _ids is None:
        listed = Path.home() / "Muse Sounds" / ".instruments"
        with sqlite3.connect("file:%s?mode=ro" % quote(str(listed)), uri=True) as db:
            _ids = {path: number for number, path in db.execute("select id, path from instruments where state = 1")}
    if sound not in _ids:
        raise KeyError("There is no Muse Sound %r installed; there are: %s" % (sound, ", ".join(sorted(_ids))))
    return _ids[sound]


def voiced(part: str, seed: int) -> str | None:
    """The Muse Sound a piece gives a part: one of the part's CHOICES, by the piece's seed (the
    same piece always the same), or None for a part that has only the one MuseScore picks."""
    have = CHOICES.get(part)
    if not have or not sounds():
        return None
    return have[int(hashlib.sha1(("%d/%s" % (seed, part)).encode("utf-8")).hexdigest(), 16) % len(have)]


def _given(score_file: Path, sound: str, out: Path) -> None:
    """Writes a copy of a MuseScore file whose one part is played by the named Muse Sound.
    The file is a zip; which sound plays each part is said in its audiosettings.json, by the
    sound's pack, name and number (found by trying, 2026-11-16: so written, MuseScore 4.7
    loads the sound; the format is not documented)."""
    category, name = sound.split("/", 1)
    number = sound_id(sound)
    with zipfile.ZipFile(score_file) as packed:
        files = {item.filename: packed.read(item.filename) for item in packed.infolist()}
    inner = next(text for name_, text in files.items() if name_.endswith(".mscx")).decode("utf-8")
    part_id = inner.split('<Part id="', 1)[1].split('"', 1)[0] if '<Part id="' in inner else "1"
    instrument = inner.split('<Instrument id="', 1)[1].split('"', 1)[0]
    settings = json.loads(files["audiosettings.json"])
    settings["activeSoundProfile"] = "MuseSounds"
    settings["tracks"] = [{
        "partId": part_id, "instrumentId": instrument,
        "in": {"resourceMeta": {"id": "%s\\%s\\%d" % (category, name, number), "type": "muse_sampler_sound_pack", "vendor": "MuseSounds",
                                "hasNativeEditorSupport": False,
                                "attributes": {"museCategory": category, "museName": name, "museUID": str(number), "museVendorName": "Muse",
                                               "playbackSetupData": ""}},
               "unitConfiguration": {}},
        "out": {"auxSends": [], "balance": 0, "fxChain": {}, "volumeDb": 0}, "soloMuteState": {"mute": False, "solo": False}}]
    files["audiosettings.json"] = json.dumps(settings, indent=4).encode("utf-8")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as packed:
        for name_, data in files.items():
            packed.writestr(name_, data)


def _run(arguments: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SKIP_LIBJACK="1")
    return subprocess.run([str(program())] + arguments, env=env, capture_output=True, text=True, timeout=900.0)


def perform(part: str, notes: list[Note], *, bpm: float, way: str = "", sound: str | None = None,
            swells: list[tuple[float, float]] | None = None) -> Path:
    """Has MuseScore play one instrument's notes and returns the recording (44.1 kHz, as
    MuseScore writes it; REAPER plays it at the project's rate). `sound` names the Muse Sound
    that plays it ("Muse Brass/French Horns a6") where that is not the one MuseScore picks;
    `swells` is the writer's rise and fall for the part (see `score`). A score that was
    performed before is not performed again."""
    text = score(part, notes, bpm=bpm, way=way, swells=swells)
    profile = "MuseSounds" if sounds() else "MuseScore Basic"       # as MuseScore 4.7 spells it; a name it does not know is passed over without a word
    name = hashlib.sha1((profile + "\n" + (sound or "") + "\n" + text).encode("utf-8")).hexdigest()[:20]
    # Kept as FLAC (lossless, and a part that rests most of the time costs next to nothing), or as WAV from before
    # (2026-11-16, night: the WAVs had filled the drive).
    for made in (KEPT / (name + ".flac"), KEPT / (name + ".wav")):
        if made.is_file():
            return made
    made = KEPT / (name + ".flac")
    KEPT.mkdir(parents=True, exist_ok=True)
    with _busy_lock:
        mine = _busy.setdefault(name, threading.Lock())
    with mine:                                                 # two parts with the same notes: the second waits and takes the first one's recording
        if made.is_file():
            return made
        try:
            return _performed(part, text, name, made, profile, sound)
        except RuntimeError as error:
            if "Segmentation fault" not in str(error):
                raise
            return _performed_a_bar_later(part, notes, bpm, way, sound, swells, made, profile, error)


def _performed_a_bar_later(part: str, notes: list[Note], bpm: float, way: str, sound: str | None,
                           swells: list[tuple[float, float]] | None, made: Path, profile: str, crash: RuntimeError) -> Path:
    """MuseScore 4 can crash on a note at one particular moment of a recording: on 2026-11-17 a tubular bell struck
    5:56 into frost hammer's track at 116 beats a minute brought it down every time, while the same stroke a beat
    either side, or the same score at 120, played (and nothing about the score was wrong). The part is played once
    more a bar later and that bar is cut off the front of the recording, so every note sounds where it was written.
    If that crashes too, both crashes are said."""
    import dataclasses
    import soundfile
    later = [dataclasses.replace(note, start=note.start + 4.0) for note in notes]     # the score is always in 4/4
    text = score(part, later, bpm=bpm, way=way, swells=[(beat + 4.0, amount) for beat, amount in swells] if swells else None)
    name = hashlib.sha1((profile + "\n" + (sound or "") + "\n" + text).encode("utf-8")).hexdigest()[:20]
    try:
        shifted = _performed(part, text, name, KEPT / (name + ".flac"), profile, sound)
    except RuntimeError as again:
        raise RuntimeError("MuseScore crashed on %s, and again with it a bar later:\n%s\n%s" % (part, crash, again)) from again
    audio, rate = soundfile.read(str(shifted), dtype="float32", always_2d=True)
    packed = KEPT / ("%s.%s.part.flac" % (made.stem, uuid.uuid4().hex[:10]))
    soundfile.write(str(packed), audio[int(round(4.0 * 60.0 / bpm * rate)):], rate, format="FLAC", subtype="PCM_24")
    packed.replace(made)
    return made


def _performed(part: str, text: str, name: str, made: Path, profile: str, sound: str | None) -> Path:
    once = uuid.uuid4().hex[:10]
    written = KEPT / (name + ".musicxml")
    written.write_text(text, encoding="utf-8")
    fresh = KEPT / ("%s.%s.part.wav" % (name, once))
    if sound and profile == "MuseSounds":
        # Two steps: MuseScore turns the score into its own file, the sound is written into that, and MuseScore plays it.
        plain, named = KEPT / ("%s.%s.plain.mscz" % (name, once)), KEPT / ("%s.%s.mscz" % (name, once))
        done = _run(["--sound-profile", profile, "-o", str(plain), str(written)])
        if done.returncode != 0 or not plain.is_file():
            raise RuntimeError("MuseScore could not read the score of %s (%s):\n%s" % (part, written, (done.stderr or done.stdout)[-1500:]))
        _given(plain, sound, named)
        plain.unlink()
        done = _run(["-o", str(fresh), str(named)])
        named.unlink()
    else:
        done = _run(["--sound-profile", profile, "-o", str(fresh), str(written)])
    if done.returncode != 0 or not fresh.is_file() or fresh.stat().st_size < 1000:
        # (What a crashed MuseScore had written so far is of no use, and is 120 MB a time: twelve were left in the cache.)
        fresh.unlink(missing_ok=True)
        raise RuntimeError("MuseScore did not perform %s (%s):\n%s" % (part, written, (done.stderr or done.stdout)[-1500:]))
    if profile == "MuseSounds" and _plain(fresh):
        fresh.unlink()
        raise RuntimeError("MuseScore played %s with its plain built-in sounds, not with Muse Sounds (%s): the part's name or kind "
                           "is not one it has a Muse Sound for" % (part, written))
    import soundfile
    audio, rate = soundfile.read(str(fresh), dtype="float32", always_2d=True)
    packed = KEPT / ("%s.%s.part.flac" % (name, once))
    soundfile.write(str(packed), audio, rate, format="FLAC", subtype="PCM_24")
    packed.replace(made)
    fresh.unlink()                                             # MuseScore's own WAV, now kept as FLAC
    return made


def _plain(recording: Path) -> bool:
    """Whether a recording is MuseScore's plain built-in sound set and not Muse Sounds: that
    set has nothing at all above 16 kHz (measured: 91 dB under the rest), and a recorded
    instrument always has something there, even a felted piano (82 dB under)."""
    import numpy as np
    import soundfile
    audio, rate = soundfile.read(str(recording), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    # Where it is loudest (a part may rest for minutes): half a minute about its loudest second.
    size = rate
    loud = int(np.argmax([float(np.square(mono[at:at + size]).sum()) for at in range(0, max(len(mono) - size, 1), size)])) * size
    cut = mono[max(loud - 15 * rate, 0):loud + 15 * rate]
    if len(cut) < 2048:
        return False
    power = np.abs(np.fft.rfft(cut * np.hanning(len(cut)))) ** 2
    if power.sum() <= 0.0:
        return False                                           # silence: nothing played it
    hz = np.fft.rfftfreq(len(cut), 1.0 / rate)
    return 10 * np.log10(power[hz > 16000].sum() / power.sum() + 1e-30) < -88.0


# How far an instrument played through an amplifier of the studio's own (sounds.AMPS) is held together, 0 to 1: a note's strength goes this far of the way to
# full. A guitar's amplifier does this to a soft hand; the house band's guitars are recorded distorted and fall 3 dB where Muse's clean ones fall 20
# (2026-11-23, 23:30: Sentence March's valley tune, a chime guitar's, read -48 LUFS, and Keel-Scarred Shove's opening riff -40, under its choir). Measured, the same
# phrase at 0.25, 0.5 and 0.8 of full strength (LUFS): the house's rhythm guitar -16.9, -16.3, -16.2 and its lead -20.9, -20.6, -20.6; the crunch guitar -34.2,
# -23.5, -15.7; the doom -23.8, -18.4, -15.5; the chime -46.6, -34.6, -23.2 (Muse's clean guitar as it is -39.4, -27.4, -16.2); the sweet lead -39.6, -28.6,
# -19.6; the fuzz lead -34.3, -24.7, -20.0. Held so far, a crunch falls 7 dB, a doom 4, a lead 8, a clean one 12. (What is not amplified keeps its whole range.)
SQUEEZE: dict[str, float] = {
    "crunch guitar": 0.6, "crunch muted": 0.6, "fuzz guitar": 0.5, "fuzz muted": 0.5, "doom guitar": 0.5, "doom muted": 0.5, "chop guitar": 0.5, "chop muted": 0.5,
    "twang guitar": 0.5, "chime guitar": 0.45, "sweet lead": 0.6, "fuzz lead": 0.5, "fuzz bass": 0.1, "round bass": 0.15, "riff celli": 0.5, "muted celli": 0.5,
    "fuzz viola": 0.55, "fuzz wurly": 0.5, "stomp tuba": 0.3,
}


def shared(written: str, notes: list[Note], seed: int = 0) -> list[tuple[str, str, list[Note], str | None]]:
    """A written instrument's notes shared out among the parts that play it: (part, way,
    notes, the Muse Sound that plays it: the one set down for the part, or the piece's own
    choice by its `seed`, or None for the one MuseScore picks)."""
    out = []
    squeeze = SQUEEZE.get(written, 0.0)
    if squeeze:
        notes = [replace(note, loud=min(note.loud + (1.0 - note.loud) * squeeze, 1.0)) for note in notes]
    for each in PARTS[written]:
        part, low, high, way = each[:4]
        mine = [note for note in notes if low <= note.pitch <= high]
        if mine:
            out.append((part, way, mine, (each[4] if sounds() else None) if len(each) > 4 else voiced(part, seed)))
    return out


def prepare(jobs: list[tuple[str, list[Note], float, list[tuple[float, float]]]], seed: int = 0, workers: int = 6) -> None:
    """Performs many written voices at once ((written instrument, notes, bpm, the writer's
    swells) each), so that a whole piece's instruments are ready when its project is put
    together. `seed` is the piece's: it settles which Muse Sound each part is given."""
    each = [(part, notes, bpm, way, sound, swells) for written, voice, bpm, swells in jobs if written in PARTS
            for part, way, notes, sound in shared(written, voice, seed)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for finished in [pool.submit(perform, part, notes, bpm=bpm, way=way, sound=sound, swells=swells or None)
                         for part, notes, bpm, way, sound, swells in each]:
            finished.result()                                  # anything that went wrong stops the piece and says why
