"""Instruments that came with a program of their own (2026-11-24: "find more instruments!").

Most of the studio's recorded instruments are a folder of single notes, and the program that plays
them is written here (studio.sfz). A few libraries are more than that: a saxophone with five ways of
playing, a lyre whose strings ring until they are damped, a voice that slides from note to note, each
with a program (an SFZ file) by the people who recorded it, which says how all of it is played. Those
are played by their own programs, in the same sampler (sfizz). What is set down here for each is only
what the studio has to know to write for it: where its keys sound, what its controllers start at, which
of its ways of playing is meant, and how it stands on the desk. Every octave and cent was measured by
playing each key alone (tools/programs.py).

The libraries are under var/samples/found, each in its own folder with its licence; every one of them
is CC0 unless its `credit` says otherwise (tools/stems/README.md has the list). A program is read and
written out again beside itself with the few lines the studio adds (`wrapper`): its own files are never
changed.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .samples import SAMPLES

FOUND = SAMPLES / "found"


@dataclass(frozen=True)
class Program:
    """An instrument played by its own program. Its notes are written as they sound."""
    file: str                                       # its program, under var/samples/found
    kind: str                                       # the family it is on the desk with (sounds.family): its effects, its hall, whether it slurs
    low: int                                        # the lowest note it has, as it sounds
    high: int
    key: int = 0                                    # from the note it sounds to the key that plays it, in semitones
    tune: float = 0.0                               # cents to add, to bring it to the band's A
    held: bool = False                              # whether its held notes swell (controller 1)
    cc: tuple[tuple[int, float], ...] = ()          # what its controllers start at, where not as it comes
    switch: int | None = None                       # its way of playing, by the key that chooses it
    line: str = ""                                  # the program that plays a line of single notes, where that is another
    slurred: tuple[tuple[int, float], ...] = ()     # ...and what its controllers start at then
    early: float = 0.0                              # seconds it is played ahead: it speaks slowly
    cut: float = 0.0                                # Hz: there is nothing of it under this
    depth: float = 0.35                             # how far back it sits (sounds.DEPTHS)
    credit: str = ""                                # whom a licence that asks for it names


_KARO = "karoryfer."
_ERHU, _LYRE = "aliexpress-erhu/Programs/", "cithara-barbarica/Programs/"
_BEAR, _TUBA, _HEART = _KARO + "bear-sax/Programs/", _KARO + "war-tuba/Programs/", _KARO + "string-cyborgs/Programs/Blackheart.sfz"
PROGRAMS: dict[str, Program] = {
    # An erhu, the two-stringed fiddle of China (close, in stereo): D4 to A5, its long notes swelling by controller 1, a line of them slid from note to note.
    "erhu long": Program(_ERHU + "02-erhu_long.sfz", "solo strings", 62, 81, key=-12, tune=6.0, held=True, cc=((21, 20.0),), slurred=((21, 20.0), (105, 127.0)),
                         early=0.05, cut=220.0, depth=0.2),
    "erhu short": Program(_ERHU + "03-erhu_short.sfz", "solo strings short", 62, 81, key=-12, tune=9.0, early=0.03, cut=220.0, depth=0.2),
    # A Germanic lyre of ten metal strings, under the fingers and under the nails: E4 to C6, ringing until the key is let go.
    "lyre finger": Program(_LYRE + "02-cithara_barbarica_finger.sfz", "plucked", 64, 84, key=-12, tune=-3.5, early=0.02, cut=180.0, depth=0.25),
    "lyre nail": Program(_LYRE + "03-cithara_barbarica_nail.sfz", "plucked", 64, 84, key=-12, tune=-3.5, early=0.02, cut=180.0, depth=0.25),
    # A 1926 Conn baritone saxophone: its growl, its plain notes and its subtone (a whisper round a low note). (Its short notes were tried for the quick ones: 20 cents sharp in the
    # middle and up to 36, where the growl itself, as quick, is within 4. A tuba's likewise, from 42 under to 10 over: the held note let go is the short one.)
    "bear sax growl": Program(_BEAR + "2-solo-poly.sfz", "woodwind", 37, 68, held=True, switch=27, line=_BEAR + "1-solo-mono.sfz", early=0.015, cut=50.0, depth=0.35),
    "bear sax sub": Program(_BEAR + "2-solo-poly.sfz", "woodwind", 37, 68, held=True, switch=28, line=_BEAR + "1-solo-mono.sfz", early=0.02, cut=50.0, depth=0.3),
    "bear sax duo": Program(_BEAR + "4-duo-poly.sfz", "woodwind", 37, 66, held=True, switch=24, line=_BEAR + "3-duo-mono.sfz", early=0.015, cut=50.0, depth=0.35),
    "bear sax plain": Program(_BEAR + "2-solo-poly.sfz", "woodwind", 37, 68, held=True, switch=24, line=_BEAR + "1-solo-mono.sfz", early=0.015, cut=50.0, depth=0.35),
    # Saxophones as an accordion's reeds: chords of them, A3 to C7.
    "saxcordion": Program(_KARO + "weresax/Programs/saxcordion.sfz", "woodwind", 57, 96, key=-12, early=0.05, cut=160.0, depth=0.35),
    # The tuba of a street band, blown to be heard outdoors.
    "war tuba": Program(_TUBA + "2-solo-poly.sfz", "brass", 27, 60, tune=-4.5, held=True, switch=26, line=_TUBA + "1-solo-legato.sfz", early=0.01, cut=34.0, depth=0.4),
    # A bass voice's one vowel, sliding from note to note where it is one line: D#2 to A#3.
    "bass voice": Program("legato_vocal_tutorial/Programs/09-complete_original_legato_a.sfz", "voice", 38, 58, key=12, tune=-3.0, held=True,
                          cc=((21, 20.0), (100, 0.0), (105, 0.0), (107, 30.0)), slurred=((21, 30.0), (100, 0.0), (105, 127.0), (107, 30.0)), early=0.02, cut=60.0, depth=0.6),
    # A jazz bass with new roundwound strings, both pickups up: as it came from its jack.
    "growly bass": Program(_KARO + "growlybass/growlybass_clean.sfz", "bass", 25, 64, key=12, tune=-3.0, cut=28.0, depth=0.1),
    # A cello's and a double bass's bowed notes as the oscillators of a synthesiser (its filter, its envelopes, its bow's screech), five ways. (Its controllers: 94 how
    # many voices, five from 64 to 95 and none over it; 102 its low-pass, 120 Hz and seven octaves of the rest; 104 how far each note throws it open, 106 for how long, of two
    # seconds; 80, 82, 83 and 84 its attack of half a second, its decay of ten, its sustain and its release of five.)
    "blackheart": Program(_HEART, "synth strings", 28, 91, cc=((84, 8.0), (85, 25.0), (93, 22.0), (94, 79.0), (95, 110.0), (102, 76.0), (103, 30.0), (104, 40.0), (106, 25.0)), depth=0.3),
    "blackheart pluck": Program(_HEART, "synth strings", 28, 91, cc=((82, 6.0), (83, 20.0), (84, 8.0), (93, 18.0), (94, 79.0), (95, 110.0), (102, 36.0), (103, 28.0), (104, 70.0), (106, 14.0)), depth=0.3),
    "blackheart stab": Program(_HEART, "synth strings", 28, 91, cc=((82, 3.0), (83, 0.0), (84, 3.0), (85, 20.0), (93, 30.0), (94, 79.0), (95, 127.0), (102, 44.0), (103, 24.0), (104, 70.0), (106, 8.0)), depth=0.3),
    "blackheart pad": Program(_HEART, "synth strings", 28, 91, cc=((80, 90.0), (84, 40.0), (93, 34.0), (94, 79.0), (95, 127.0), (102, 48.0), (103, 10.0), (107, 18.0), (108, 4.0)), depth=0.45),
    "ironface": Program(_KARO + "string-cyborgs/Programs/Ironface.sfz", "bass", 24, 47, key=12, cc=((82, 60.0), (83, 100.0), (84, 8.0), (85, 80.0), (102, 70.0), (103, 20.0), (104, 60.0), (106, 30.0), (94, 10.0)),
                        cut=28.0, depth=0.1),
}


def there(name: str) -> bool:
    """Whether an instrument's program is on this machine."""
    return (FOUND / PROGRAMS[name].file).is_file()


def text_of(name: str, slurs: bool = False) -> tuple[Path, str]:
    """An instrument's program with the studio's lines in it, and the program it was made from."""
    mine = PROGRAMS[name]
    path = FOUND / (mine.line if slurs and mine.line else mine.file)
    text = path.read_bytes().decode("latin-1")                  # (byte for byte: what its names are written in is their own affair)
    if mine.switch is not None:
        text, changed = re.subn(r"sw_default\s*=\s*\d+", "sw_default=%d" % mine.switch, text)
        if not changed:
            raise ValueError("%s has no keyswitch to choose %d by" % (path, mine.switch))
    starts = dict(mine.cc)
    starts.update(dict(mine.slurred) if slurs else {})
    # Read whole when it is loaded, so that a render faster than the music never waits for the disk; then what its controllers start at, after the
    # program's own, at the end of its first block of controls, and before anything it includes (after which another block stands).
    added = "\nhint_ram_based=1\n" + "".join("set_cc%d=%g\n" % each for each in sorted(starts.items()))
    found = re.search(r"<control>", text)
    if found is None:
        text = "<control>%s%s" % (added, text)
    else:
        after = re.compile(r"^[ \t]*(?:<|#include)", re.MULTILINE).search(text, found.end())
        at = after.start() if after else len(text)
        text = text[:at] + added + text[at:]
    if mine.tune:
        text, changed = re.subn(r"<global>", "<global>\ntune=%g\n" % mine.tune, text, count=1)
        if not changed:
            first = re.search(r"<(?:master|group|region)>", text)
            if first is None:
                raise ValueError("%s has nothing in it to tune" % path)
            text = text[:first.start()] + "<global>\ntune=%g\n" % mine.tune + text[first.start():]
    return path, "// A program as it came, with the studio's lines (studio/programs.py).\n" + text


def wrapper(name: str, slurs: bool = False) -> Path:
    """The file the sampler plays an instrument from, beside the program it is made from (whose own files are beside it). Written only where it is not there as it
    should be: a sampler whose file changes while it renders stops dead."""
    path, text = text_of(name, slurs)
    out = path.with_name("freerock %s%s.sfz" % (name, " line" if slurs else ""))
    data = text.encode("latin-1")
    if not out.is_file() or out.read_bytes() != data:
        fresh = out.with_name("%s.%d.part" % (out.name, os.getpid()))
        fresh.write_bytes(data)
        os.replace(fresh, out)
    return out
