"""What every staged take still lacks: the re-render ledger (2026-11-18: "move re-rendering to the end when the drives are
full but fully detail and keep track of what needs to be rerendered eventually this is a long tail project").

Until the drive is full the nights make new music; a change to the writer or the desk reaches the takes made after it,
and every take made before it that it would change is kept here, with what it lacks, until it is rendered again. A render
keeps the code its run began with, so a take's code is dated by when its list began (the lane logs), or for a run
outside the lanes by when its first take began (its log's "in N s").

    cd app && uv run --no-sync python ../tools/rerender_ledger.py          prints the ledger's counts
    ... --write                                                            and writes var/passes/rerender-ledger.json and .md

A new change is one more entry in CHANGES: its name, when it reached the files that render, the commit, what it does and
which pieces it changes (a test on the piece's character or House family).
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import functools

from freerock.studio import build, house
from freerock.studio.orchestra import DANCE_GROOVES, DELICATE, FIGHTS, INSTRUMENTS, LONG_HOLD, held_runs

ROOT = Path(__file__).resolve().parent.parent
PASSES = ROOT / "var" / "passes"
STUDIO = ROOT / "var" / "studio"
SNOW = {"frozen cavern", "frozen lake", "ice fields", "aurora", "ice cave", "frost camp"}


@dataclass(frozen=True)
class Piece:
    style: str
    key: str            # family/take
    family: str
    character: object   # an orchestra character, or a House family
    meta: dict


@functools.lru_cache(maxsize=1)
def _families() -> dict:
    return {fam.name: fam for fam, _ in build.plan()}


def long_rise(piece: Piece) -> bool:
    """A family whose rises hold one chord LONG_HOLD bars or more (orchestra.Take.climbs)."""
    fam = _families().get(piece.family)
    return fam is not None and any(run >= LONG_HOLD for section in fam.sections if section.part in ("build", "climb")
                                   for _, run in held_runs(section.chords))


def plays(piece: Piece, instrument: str, parts: tuple[str, ...] = ("leads", "strong", "under", "pads", "plucks")) -> bool:
    return any(instrument in getattr(piece.character, part, ()) for part in parts)


def high_bass(piece: Piece) -> bool:
    """A take whose bass line was centred above A2 before orchestra.BASS_TOP: its instrument's home less 5 over 45 (the
    organ's and the harp's, 2026-11-19)."""
    basses = getattr(piece.character, "basses", ())
    if piece.style == "house" or not basses:
        return False
    name = basses[int(piece.key.rsplit("/", 1)[1]) % len(basses)]
    return INSTRUMENTS[name].home - 5 > 45


def peak_moved(piece: Piece) -> bool:
    """A band take whose solo peaks elsewhere since orchestra.SOLO_PEAK_NEAR_TOP: the take is written, and its solo's peak
    under the old rule (the chord's highest note of the five in the octave under the top) set against the new (2026-11-20,
    Sand Fever I's solo G3 to C5)."""
    if piece.style != "knight" or not getattr(piece.character, "band", False):
        return False
    fam = _families().get(piece.family)
    if fam is None:
        return False
    from freerock.studio import orchestra
    real, moved = orchestra.guitar_solo, []

    def traced(*args, **kwargs):
        def tracer(frame, event, arg):
            if frame.f_code is real.__code__:
                if event == "return":
                    loc = frame.f_locals
                    five, top, held = loc["five"], loc["top"], {each % 7 for each in loc["chord_at"](loc["at_peak"]).steps}
                    old = max((each for each in range(top - 6, top + 1) if each % 7 in held and each % 7 in five), default=top)
                    moved.append(old != loc["peak_note"])
                return tracer
            return None
        before = sys.gettrace()
        sys.settrace(tracer)
        try:
            return real(*args, **kwargs)
        finally:
            sys.settrace(before)

    orchestra.guitar_solo = traced
    try:
        orchestra.Take(fam, int(piece.key.rsplit("/", 1)[1]))
    finally:
        orchestra.guitar_solo = real
    return any(moved)


def lively_walk(piece: Piece, busy_from: float = 0.45) -> bool:
    """Walking music that has soft war drums (orchestra.Take: `lively`), by the rule of its day: busy from 0.45 until
    2026-11-18, from 0.35 since."""
    ch = piece.character
    if piece.style == "house" or getattr(ch, "role", "") != "wander":
        return False
    return (((ch.weight >= 0.6 and ch.busy >= 0.55) or (ch.weight >= 0.5 and ch.busy >= busy_from and not set(ch.grooves) <= set(DELICATE)))
            and not set(ch.grooves) & set(DANCE_GROOVES))


@dataclass(frozen=True)
class Change:
    name: str
    at: datetime.datetime           # when it reached the files the renders load
    commit: str
    what: str
    touches: Callable[[Piece], bool]


CHANGES = [
    Change("light levels and soft war drums", datetime.datetime(2026, 11, 17, 20, 40), "2ce1bdd",
           "light pieces' drums and bass nearer in all three desks; lively lighter walking music gets soft war drums",
           lambda p: bool(p.meta.get("light")) or lively_walk(p)),
    Change("a little harder, and the valley's pad", datetime.datetime(2026, 11, 17, 21, 52), "",
           "harder story levels for walking music and the desk's levels ('this is not world of fairy craft'), the valley's "
           "pad under the tune (the whine left when sitting), House's kick and bass",
           lambda p: True),
    Change("rowdy inns walk", datetime.datetime(2026, 11, 18, 1, 8), "ef907e1",
           "an inn of busy 0.6 or more takes the walking shape instead of the quiet room's",
           lambda p: p.style != "house" and p.character.role == "ember" and p.character.busy >= 0.6),
    Change("no tuba under a band", datetime.datetime(2026, 11, 18, 3, 45), "469a811",
           "the desk's low brass at the moments no longer doubles a band's bass (it read 8 to 15 dB over at 450 Hz-1.8 kHz)",
           lambda p: p.style == "knight" and bool(getattr(p.character, "band", False)) and not p.meta.get("light")),
    Change("the snow's plucks given a middle", datetime.datetime(2026, 11, 18, 4, 41), "97b2af4",
           "pizzicato for the glockenspiel, and a guitar at the frost camp (the all-bell accompaniment read 21 dB short in the middle)",
           lambda p: p.style != "house" and p.character.name in SNOW),
    Change("a real accordion", datetime.datetime(2026, 11, 18, 5, 19), "8b95ce3",
           "TinySOL's accordion for the harmonica that stood in for it (out of its range below C4, reedy)",
           lambda p: p.style != "house" and plays(p, "accordion")),
    Change("House's clap knocks", datetime.datetime(2026, 11, 18, 7, 16), "7820310",
           "the clap's and snare's knock lifted 3 dB at 900 Hz (3 to 6 dB short in every take)",
           lambda p: p.style == "house"),
    Change("the bagpipe's tunes on a real chanter", datetime.datetime(2026, 11, 18, 8, 18), "8759cca",
           "FreePats' chanter plays the bagpipe's tunes, chosen by ear; held drones stay the english horn",
           lambda p: p.style != "house" and plays(p, "bagpipe", ("leads", "strong", "under"))),
    Change("soft war drums for the slower light walks", datetime.datetime(2026, 11, 18, 8, 55), "",
           "the lighter walking music busy from 0.35 has soft war drums too (snowfall, mirage, frozen lake, desert shrine, ice fields)",
           lambda p: lively_walk(p, 0.35) and not lively_walk(p, 0.45)),
    # (A first House rework, the filters ridden by one rule for every track, reached the files at 09:39 and was replaced
    # by the one below before any House take was made with it: House's lists were held.)
    Change("a music sheet of its own", datetime.datetime(2026, 11, 18, 10, 44), "",
           "every take written down whole as its music sheet beside its recordings, the golden rule ('the music sheet should be "
           "a separate concept and asset for every track'); a take made before has none until it is performed again",
           lambda p: True),
    Change("a reed does not hold the valley's drone", datetime.datetime(2026, 11, 18, 11, 41), "",
           "in the valley a reed's drone (the english horn's pipe drone, a bagpipe, an accordion, a harmonica) goes to the other "
           "pad, an organ's or the strings'; and the pipe drone plays down to its own E3 ('sometimes when one synth stays in when "
           "youre sitting its whiny': King's Oath's valley drone stood 9 dB over the tune, now 2 under)",
           lambda p: p.style != "house" and any(pad in ("pipe drone", "bagpipe", "accordion", "harmonica") for pad in getattr(p.character, "pads", ()))),
    Change("House's lead a riff, its synths bigger", datetime.datetime(2026, 11, 18, 11, 41), "",
           "the tune written as a riff (cells of three sixteenths, every note on the chord) on a pluck and a big synth, its echo "
           "thrown at each phrase's end and a phaser and a second synth in a drop's second half; the synths' low cuts eased and "
           "spread wider ('the lead is still lame', 'it sounds hollow and generic in the synths')",
           lambda p: p.style == "house"),
    Change("House written as sheets, its effects marked by the music", datetime.datetime(2026, 11, 18, 10, 44), "",
           "each part's low-pass follows its notes' brightness (the theme darker than the drop, the breakdown shut), the sub out "
           "of each rise and the breakdown, a rise's last beats thinned from the bottom, the hats on a dry line of their own and "
           "softer, the pump deeper at a drop ('too much high hat and not enough dynamic sound', 'this is boring generic crap')",
           lambda p: p.style == "house"),
    Change("House's drops change, its lead chosen by ear and number", datetime.datetime(2026, 11, 18, 12, 50), "",
           "the groove changes every sixteen bars and a drop builds block by block (the boredom meter: the drums had sounded the "
           "same for 40 bars); the drop's lead Argitoth's Trance Lead 1, the nearest of nine to the liked house leads, its last "
           "sixteen bars answered phrase by phrase, the chords phased there; MuseScore's chords given a gentler top of their own",
           lambda p: p.style == "house"),
    Change("the band's 1970s pedals", datetime.datetime(2026, 11, 18, 14, 47), "",
           "a band's guitars marked where their own notes ask: a jet flanged by hand into an arrival, a wah rocked through a "
           "running solo, a cry across a long note, a vibe in the valley, a phaser on strummed chords where a passage comes back "
           "('guitars should have effects in the 70s bro')",
           lambda p: p.style == "knight" and any(name in getattr(p.character, part, ()) for part in ("leads", "plucks", "strong")
                                                  for name in ("lead guitar", "rhythm guitar", "guitar"))),
    Change("an orchestra's effects that move", datetime.datetime(2026, 11, 18, 14, 47), "",
           "the valley's string and choir pads further off, closing their top and opening at the climb; a harp's, a celesta's, "
           "the bells' last note of each phrase left to hang in an echo ('this might apply to other genres too')",
           lambda p: p.style == "warcraft"),
    Change("a band's rises and drums that move", datetime.datetime(2026, 11, 18, 15, 59), "",
           "a long rise opened on the rhythm guitar's wah by hand; the drummer's cymbal turned every sixteen bars of a theme (the "
           "hat, then the ride; the ride over a groove of the toms) and a heavy band's long moment ridden out on the bell (the "
           "boredom meter: a battle piece's rhythm one colour through a 36-bar rise, its drums one groove through a theme)",
           lambda p: p.style == "knight" and p.character.band),
    Change("House's bass grows harsher through a long drop", datetime.datetime(2026, 11, 18, 15, 59), "",
           "a harsher twin of the bass on its own notes through the second half of every drop of 32 bars or more, in over "
           "eight bars (deadmau5's 'Turning Point'; the boredom meter: Moonwell's bass one colour through 44 bars of a drop)",
           lambda p: p.style == "house" and p.character.role not in ("ember", "night", "camp")),
    Change("House's drawbar organ; the open top for the big synths alone", datetime.datetime(2026, 11, 18, 16, 59), "",
           "the chords' organ the LinnStrument set's Drawbar Organ 1 (Surge's House Organ, loudest two octaves over its note, had "
           "put them 23 to 34 dB over the liked at the top); the open top asked for the saw kept to the drop's saw and super, "
           "the calm melodies and the quiet pluck back to the gentler top",
           lambda p: p.style == "house"),
    Change("House's chord roll climbs to the drop", datetime.datetime(2026, 11, 18, 17, 22), "",
           "the chords' roll into a drop softer as it comes faster, no louder than the drop; none in a calm piece (Cold Stars "
           "I's bell had rung 6 dB over its drop)",
           lambda p: p.style == "house"),
    Change("a storm's rain under the full band", datetime.datetime(2026, 11, 18, 17, 36), "",
           "a storm's rain at 0.4 in the opening, rises and close and 0.25 under the themes and drops (over a bright pad it had "
           "covered the music)",
           lambda p: p.style == "house" and p.character.role == "storm"),
    Change("a light band's clean guitar shimmers", datetime.datetime(2026, 11, 18, 19, 6), "",
           "where the clean guitar is a band's whole accompaniment, the vibe from its second theme through its moments "
           "(Lantern Walk had no effect at all)",
           lambda p: p.style == "knight" and any("guitar" in getattr(p.character, part, ()) for part in ("plucks", "strong", "leads"))),
    Change("a heavy band's long opening opens on a wah", datetime.datetime(2026, 11, 18, 19, 19), "",
           "a heavy band's opening of 16 bars or more: its lone guitar dry for the first half, then the wah opened by hand "
           "until the band comes in (Cobra Fever's riff had gone 20 bars without a change)",
           lambda p: p.style == "knight" and p.character.band),
    Change("a wind player breathes", datetime.datetime(2026, 11, 18, 20, 41), "",
           "a harmonica, the English horn's drone or an accordion holds a note no longer than a breath (5, 6 and 9 seconds), "
           "played as breaths of whole bars (Moonshine Blues' harmonica had held one chord a minute)",
           lambda p: p.style != "house" and any(plays(p, name) for name in ("harmonica", "accordion", "pipe drone"))),
    Change("a band's lead guitar takes a solo", datetime.datetime(2026, 11, 18, 21, 16), "7709caa",
           "where the summit states its theme more than once, the first time round is the lead guitar's solo over the band "
           "(two-bar phrases from the tune's motif, climbing an octave, bends, runs and a repeated lick, the wah rocked), "
           "then the theme with the twin guitars",
           lambda p: p.style == "knight" and p.character.band and tuple(getattr(p.character, "strong", ()))[:1] == ("lead guitar",)),
    Change("the guitar solo is sung", datetime.datetime(2026, 11, 18, 23, 0), "",
           "the solo in two-bar sentences with breaths, held notes on the chords, one run, the peak held late, in the key's "
           "pentatonic, with an echo and no wah (the first was runs and bends under a rocking wah: 'all wammy no chill')",
           lambda p: p.style == "knight" and p.character.band and tuple(getattr(p.character, "strong", ()))[:1] == ("lead guitar",)),
    Change("a long opening's bass goes with its chords", datetime.datetime(2026, 11, 19, 0, 0), "",
           "where an opening of 16 bars or more leaves the key chord, the held key note moves to that chord's root and back "
           "(Gull's Edge: one note 27 bars)",
           lambda p: p.style != "house" and p.character.weight >= 0.8),
    Change("a House theme after a drop begins on the other figure", datetime.datetime(2026, 11, 19, 3, 30), "",
           "the theme after a drop begins with the hats turned and the other percussion (Ambush III: one groove 32 bars)",
           lambda p: p.style == "house"),
    Change("House's lead ridden, not turned down", datetime.datetime(2026, 11, 19, 3, 30), "",
           "the lead at its place at the drop, a part over that ridden down on its own envelope (Blades III's riff 15 dB under)",
           lambda p: p.style == "house"),
    Change("House's bigger lead voice plays the drops", datetime.datetime(2026, 11, 19, 3, 0), "",
           "of a lead's two voices the bigger plays the drops (Hammerfall III's drops had the hollow square, its themes the super)",
           lambda p: p.style == "house"),
    Change("House's hats thin as the close begins", datetime.datetime(2026, 11, 19, 3, 0), "",
           "at the close's first bar the hats thin to two strokes and an open hat (the drop's groove had run on 20 bars)",
           lambda p: p.style == "house"),
    Change("a heavy band's second theme rings", datetime.datetime(2026, 11, 18, 23, 0), "",
           "the rhythm guitar strikes each chord of the second theme once and holds it, no chugs (it had one distorted colour "
           "through both themes, 42 to 64 bars)",
           lambda p: p.style == "knight" and p.character.band and not p.meta.get("light")),
    Change("a heavy band's long rise climbs", datetime.datetime(2026, 11, 19, 7, 10), "b89cc3e",
           "where a rise holds one chord nine bars or more, its second half has the riff an octave up over the low chugs and "
           "the bass pumping octaves, and its last bar runs by step into the next chord (17 bars of one note and one riff "
           "in the fights' builds)",
           lambda p: p.style == "knight" and p.character.band and p.character.weight >= 0.8 and long_rise(p)),
    Change("a heavy band's second theme opens out, its long moments dig in", datetime.datetime(2026, 11, 19, 8, 33), "e1033d1",
           "the open hat under the second theme, then the ride; from bar 16 of a 24-bar-or-longer arrival or summit the crash "
           "every other bar and the bass's octaves (the drums one colour 34 to 68 bars across both themes)",
           lambda p: p.style == "knight" and p.character.band and p.character.weight >= 0.8),
    Change("a band's licks of its own; the long build one way of three", datetime.datetime(2026, 11, 19, 8, 33), "e1033d1",
           "each take answers its riff with its own fills (runs, the curl, double stops, offbeat stabs, the turn chord, a "
           "ringing chord) in place of the one walk up to the fifth every band song played 32 times; a long build climbs, "
           "drives or plays on",
           lambda p: p.style == "knight" and p.character.band and any(figure in ("riff", "chug") for figure in p.character.figures)),
    Change("the solo riffs like Angus", datetime.datetime(2026, 11, 19, 9, 29), "87dcbf6",
           "the solo's middle: two of Angus Young's figures (the repeated note, the run down in threes, the trill, double "
           "stops) with a sung sentence between, then the run to the peak",
           lambda p: p.style == "knight" and p.character.band and tuple(getattr(p.character, "strong", ()))[:1] == ("lead guitar",)),
    Change("a band's riff moves, its lead answers", datetime.datetime(2026, 11, 19, 11, 27), "50afba7",
           "each band take's riff moves its own way inside the bar (I to IV, the flat seventh, a pedal, a push), the second turn "
           "a variation of the first, the lead guitar answering every other long note with a run into its next phrase",
           lambda p: p.style == "knight" and p.character.band),
    Change("a heavy band's close ends as a rock band ends", datetime.datetime(2026, 11, 19, 12, 50), "",
           "the riff drives on through the close, then the stop, the chord ringing over a roll around the toms, and the last "
           "chord together (the close had died away: the judges' weakest part in every band song)",
           lambda p: p.style == "knight" and p.character.band and p.character.weight >= 0.8),
    Change("the bass's break, the solo's three riffs", datetime.datetime(2026, 11, 19, 12, 50), "",
           "the first bars of a heavy band's climb are the bass's, alone over light drums, into the band's entry; the solo's "
           "middle three of Angus's figures from six (the cascade and the pedal lick new)",
           lambda p: p.style == "knight" and p.character.band and p.character.weight >= 0.8),
    Change("solos in most band songs, each its own, moving", datetime.datetime(2026, 11, 19, 14, 3), "",
           "whoever leads the summit takes the solo (fiddle, mandolin, harmonica, whistle, lead guitar), sixteen bars where the "
           "theme is eight; three figures of ten, its own form and ways; a flanger sweeping under it",
           lambda p: p.style == "knight" and p.character.band),
    Change("a band's answers sing its theme, its riff listens, its cymbals open", datetime.datetime(2026, 11, 19, 14, 3), "",
           "the lead's answers are the first theme's opening played quick; the riff's move waits where it would rub against "
           "the lead; the band kits' top 3.5 dB up from 5 kHz",
           lambda p: p.style == "knight" and p.character.band),
    Change("a band's tune stands over its guitars; its guitar comps under the solo", datetime.datetime(2026, 11, 19, 16, 28), "",
           "wherever the tune sings the lead is brought up until it stands 2 dB over the rhythm guitars, at most 5 (it had sat "
           "level with them in the first theme, median -0.4 dB over 144 takes); under a solo the rhythm guitar strikes the chord "
           "on the bar's first beat with the muted string after it, no fills",
           lambda p: p.style == "knight" and p.character.band),
    Change("a band's ride groove turns to the hat", datetime.datetime(2026, 11, 19, 17, 36), "",
           "a groove that keeps time on the ride turns to the closed hat for its second sixteen bars of a theme (it had had "
           "nowhere to turn)",
           lambda p: p.style == "knight" and p.character.band),
    Change("a solo's peak is the chord's note nearest its top", datetime.datetime(2026, 11, 20, 6, 20), "",
           "the solo's peak is the chord's note nearest the solo's top, up to two steps over it (it had been looked for only in "
           "the octave under the top: six steps down over a flat-two chord, and the whole solo kept under it, Sand Fever I's "
           "G3 to C5)",
           peak_moved),
    Change("a solo that riffs more like Angus", datetime.datetime(2026, 11, 20, 0, 14), "",
           "the solo's figures only Angus's own, four of its eight sentences riffing, each lick played again a note higher "
           "before it lands (it had riffed two or three sentences, a bar each)",
           lambda p: p.style == "knight" and p.character.band),
    Change("a light band's second-figure riff goes up the neck too", datetime.datetime(2026, 11, 19, 22, 52), "",
           "in a light band's geared phrase a riff that is the arrival's second figure goes up the neck with the rest (it had "
           "stayed put: a riff moves only by its own up)",
           lambda p: p.style == "knight" and p.character.band and p.character.role not in FIGHTS and p.character.weight < 0.8),
    Change("a band's valley keeps time, its arrival goes up a gear, a fiddle's solo sings lower", datetime.datetime(2026, 11, 19, 21, 45),
           "", "a walking band's valley keeps time softly on the hat, the bass drum and the side stick (the drummer had stopped); "
           "every second phrase of a light band's arrival of sixteen bars or more an octave up the neck (it had played the same "
           "notes all through); a fiddle's solo keeps below E6 and a mandolin's below D6 (a fiddle's had reached C7)",
           lambda p: p.style == "knight" and p.character.band and p.character.role not in FIGHTS),
    Change("an organ's or a harp's bass on its pedals", datetime.datetime(2026, 11, 19, 21, 15), "",
           "no bass line is centred above A2: an organ plays its bass on the pedals and a harp on its low strings (they had "
           "played it where they sit as a pad and a pluck, the cathedral's organ around A3, the moonwell's harp around E4)",
           high_bass),
    Change("House's theme sings from its fifth bar", datetime.datetime(2026, 11, 19, 16, 28), "",
           "the tune's opening phrases every four bars from the theme's fifth bar, softly (eight bars of tune in thirty-two had "
           "left the theme a groove waiting for one)",
           lambda p: p.style == "house"),
    Change("House's riffs are cells", datetime.datetime(2026, 11, 19, 15, 17), "c22c66e",
           "a riff is a cell of three or four notes of the chord in an order of its own, the same shape on each chord (half of "
           "every riff's notes had been the note before: F F F F A A A A A)",
           lambda p: p.style == "house"),
    Change("an orchestra's long moment goes up a gear", datetime.datetime(2026, 11, 19, 10, 43), "d6baa7f",
           "every second eight-bar phrase of an arrival or summit of sixteen bars or more: the accompaniment an octave up, "
           "the lines over the pad to the horns, the drums busier, the cymbal twice as often (16 to 24 bars of one colour)",
           lambda p: p.style == "warcraft"),
]


def code_dates() -> dict[str, datetime.datetime]:
    """When the code that made each staged take was loaded: its list's beginning, by the lane logs."""
    begun: dict[str, list[str]] = {}
    for lane_log in PASSES.glob("lane-*.log"):
        for line in lane_log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\d\d:\d\d:\d\d) begun (\S+) \(", line)
            if m:
                begun.setdefault(lane_log.stem + "/" + m.group(2), []).append(m.group(1))
    out: dict[str, datetime.datetime] = {}
    for log in sorted(list(PASSES.glob("lane-*/*.log")) + list(PASSES.glob("lane-*/*.log.carried")), key=lambda p: p.stat().st_mtime):
        ended = datetime.datetime.fromtimestamp(log.stat().st_mtime)
        dones = re.findall(r"(\d\d:\d\d:\d\d)\s+done\s+(\S+)\s.*?in (\d+) s", log.read_text(encoding="utf-8", errors="replace"))
        if not dones:
            continue
        name = log.parent.name + "/" + log.name.split(".log")[0]

        def dated(clock: str, before: datetime.datetime) -> datetime.datetime:
            at = datetime.datetime.combine(before.date(), datetime.time.fromisoformat(clock))
            return at - datetime.timedelta(days=1) if at > before + datetime.timedelta(minutes=1) else at

        first_done = min(dated(clock, ended) - datetime.timedelta(seconds=int(took)) for clock, _, took in dones)
        starts = [dated(clock, ended) for clock in begun.get(name, [])]
        starts = [at for at in starts if at <= first_done + datetime.timedelta(minutes=2)]
        start = max(starts) if starts else first_done
        for clock, key, took in dones:
            out[key] = start            # the latest run that made it wins (logs are read oldest first)
    return out


def pieces() -> list[Piece]:
    families = {fam.name: fam.character for fam, _ in build.plan()}
    families.update({fam.name: fam for fam in house.PLAN})
    found = []
    for style in ("knight", "warcraft", "house"):
        for path in sorted((STUDIO / style).glob("*/*/track.json")):
            family = path.parent.parent.name
            if family in families:
                found.append(Piece(style, family + "/" + path.parent.name, family, families[family],
                                   json.loads(path.read_text(encoding="utf-8"))))
    return found


def ledger() -> list[dict]:
    dates = code_dates()
    rows = []
    for piece in pieces():
        folder = STUDIO / piece.style / piece.key / "track.json"
        made = dates.get(piece.key) or datetime.datetime.fromtimestamp(folder.stat().st_mtime) - datetime.timedelta(minutes=30)
        lacks = [change.name for change in CHANGES if made < change.at and change.touches(piece)]
        if lacks:
            rows.append({"style": piece.style, "take": piece.key, "title": piece.meta.get("title", ""), "role": piece.meta.get("role", ""),
                         "kinds": list(piece.meta.get("moods") or []), "light": bool(piece.meta.get("light")),
                         "code_from": made.strftime("%Y-%m-%d %H:%M"), "lacks": lacks})
    return rows


def main() -> int:
    rows = ledger()
    total = len(pieces())
    by_style = {style: sum(1 for row in rows if row["style"] == style) for style in ("knight", "warcraft", "house")}
    print("%d of %d staged takes lack a change: %s" % (len(rows), total, ", ".join("%s %d" % kv for kv in by_style.items())))
    for change in CHANGES:
        print("  %-42s %4d takes" % (change.name, sum(1 for row in rows if change.name in row["lacks"])))
    if "--write" in sys.argv:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        (PASSES / "rerender-ledger.json").write_text(json.dumps({"written": stamp, "changes": [
            {"name": c.name, "at": c.at.strftime("%Y-%m-%d %H:%M"), "commit": c.commit, "what": c.what} for c in CHANGES],
            "takes": rows}, indent=1), encoding="utf-8")
        lines = ["# What the staged takes still lack (written %s)" % stamp, "",
                 "Re-rendering waits for the end, when the drive is full; until then this is kept up to date (`tools/rerender_ledger.py --write`).",
                 "%d of %d staged takes lack at least one change." % (len(rows), total), "", "## The changes", ""]
        for c in CHANGES:
            lines.append("- **%s** (%s%s): %s. Takes lacking it: %d." % (c.name, c.at.strftime("%Y-%m-%d %H:%M"), ", " + c.commit if c.commit else "",
                                                                       c.what, sum(1 for row in rows if c.name in row["lacks"])))
        for style in ("knight", "warcraft", "house"):
            mine = [row for row in rows if row["style"] == style]
            lines += ["", "## %s (%d)" % ({"knight": "Knight Rock", "warcraft": "Warcraft", "house": "House"}[style], len(mine)), "",
                      "| take | title | role | code from | lacks |", "|---|---|---|---|---|"]
            for row in sorted(mine, key=lambda r: r["take"]):
                lines.append("| %s | %s | %s | %s | %s |" % (row["take"], row["title"], row["role"], row["code_from"], "; ".join(row["lacks"])))
        (PASSES / "rerender-ledger.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("written:", PASSES / "rerender-ledger.json", PASSES / "rerender-ledger.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
