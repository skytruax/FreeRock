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

import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import analysis, forever
from . import RATE, desk, house, muse, reaper, sfz, sounds, stage_root, write_track
from .score import Note, Sheet, Voice

VAR = Path(__file__).resolve().parents[3] / "var"
PROJECTS = VAR / "reaper" / "projects"
BEAT = house.BEAT
# What plays each of the writer's sounds: (the writer's table, its name for the sound) -> a written instrument the
# desk knows (sounds.SOUNDS for the synths, muse.PARTS for the real ones).
PLAYED = {
    ("bass", "sub"): "house sub", ("bass", "pluck"): "house bass pluck", ("bass", "saw"): "house bass saw", ("bass", "square"): "house bass square",
    ("bass", "fm"): "house bass fm", ("bass", "reese"): "house bass wide", ("bass", "organ"): "house bass organ",
    ("bass", "harsh"): "house bass wide", ("bass", "harsh saw"): "house bass saw",      # the twin that comes in late in a drop
    ("keys", "piano"): "house piano", ("keys", "keys"): "electric piano", ("keys", "organ"): "house organ", ("keys", "stab"): "house stab",
    ("keys", "pluck"): "house pluck", ("keys", "bell"): "house bell", ("keys", "glass"): "house glass", ("keys", "harp"): "harp",
    ("keys", "marimba"): "marimba", ("keys", "oud"): "guitar", ("keys", "string"): "guitar", ("keys", "brass"): "brass",
    # (The tunes the pan flute, the flute and the marimba sang were heard as cheesy, 2026-11-17: synths sing them now.)
    ("lead", "saw"): "house lead saw", ("lead", "super"): "house lead super", ("lead", "hollow"): "house lead hollow", ("lead", "pipe"): "house lead hollow",
    ("lead", "whistle"): "house lead sine", ("lead", "flute"): "house lead sine", ("lead", "bell"): "house bell", ("lead", "glass"): "house glass",
    ("lead", "keys"): "wurly", ("lead", "pluck"): "house pluck", ("lead", "marimba"): "house pluck", ("lead", "harp"): "harp", ("lead", "oud"): "guitar",
    ("lead", "string"): "harp", ("lead", "brass"): "trumpet",
    ("pad", "warm"): "house pad warm", ("pad", "strings"): "strings slow", ("pad", "super"): "house pad super", ("pad", "glass"): "house pad glass",
    ("pad", "hollow"): "house pad hollow", ("pad", "organ"): "house pad organ",
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


@dataclass
class Heard:
    """What the writer asked to be played."""
    notes: dict[tuple[str, str, str], list[tuple[float, float, float, float, float, float]]] = field(default_factory=lambda: defaultdict(list))
    hits: list[tuple[str, str, float, float, float]] = field(default_factory=list)      # drum, machine, seconds, level, pan
    airs: list = field(default_factory=list)       # what the texture is besides its notes: risers, wind, drips (house.Air)
    # Each part's effect marks and their settings, from its sheet (score.EFFECTS): (channel, table, sound) -> (marks, settings).
    marks: dict[tuple[str, str, str], tuple[dict, dict]] = field(default_factory=dict)


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
SUBBED = ("house bass pluck", "house bass saw")      # the basses that are heard more than felt: a sine goes under them
HARSH = 0.55        # how far under the bass its harsh twin plays, once it is all the way in (`harsher`)
# The drop's big synths, whose edge is the hook: their top is left open and their filter opens further than the band's
# ("i wish i could hear more of that saw synths top end"). The other leads, a calm piece's sung melody and the riff's
# pluck in the quiet, keep the gentler top (2026-11-18: the open top had reached them too, and an inn's tune stood
# 20 dB over the liked leads there).
OPEN_TOP = ("house lead saw", "house lead super")
SUB_UNDER = 0.8     # ...this far under the bass it holds up (0.7 until the third pass: the liked basses have 3 to 7 dB more at 28 to 57 Hz)


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
    most: dict[str, float] = defaultdict(float)
    for (channel, _, _), levels in spans.items():
        most[channel] = max(most[channel], max(levels.values()))
    out = []
    for (channel, table, name), notes in sorted(heard.notes.items()):
        written = PLAYED[(table, name)]
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
            ride = _ride(levels)
            share = [level / levels[_span_of(at)] for at, _, _, level, _, _ in notes]
            tune = [(note, part) for note, part in zip(notes, share) if part >= UNDER]
            under = [(note, part) for note, part in zip(notes, share) if part < UNDER]
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
        if written in ("house sub", "house bass fm"):
            # (2026-11-17, night: against the liked house stems the bass was 30 dB short in its middle and 44 at its top: a
            # sine under 100 Hz, which a small loudspeaker does not play at all. The FM bass the same the next morning: 17 to
            # 30 dB short from 450 Hz up.) A sawtooth on the same notes, closed
            # above 900 Hz and well under the sub, is the part of the bass that is heard; the sub is the part that is felt.
            out.append((channel, table, name + " growl", "house bass saw", 900.0, sorted(every, key=lambda note: note.start),
                        taste * 0.45, ride))
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
            out["drums"].append(desk.Line("house %s" % which, template, notes, volume=volume, send=send, effects=effects))
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
            effects, settings = heard.marks.get((channel, table, name.split(" ")[0]), ({}, {}))
            for line in sounds.lines(Voice(notes=mine, instrument=written, effects=dict(effects), settings=dict(settings)), title, house.BPM,
                                     taste=taste, room=1.0, seed=seed, muse_level=sounds.LEVEL):
                if ride:
                    line.moves = list(ride)
                if cut:
                    line.effects = list(line.effects) + [sounds.equalise(high_cut=cut)]
                if channel == "bass":
                    # (Against the liked house stems the sawtooth and wide basses were 13 to 34 dB bright above 2.5 kHz,
                    # 2026-11-17, night: a house bass is closed well down. The growl beside the sub has its own cut.)
                    # (Third pass, 2026-11-17, midday, twenty tracks: still 7 to 13 dB heavy from 450 Hz to 1.8 kHz: closed
                    # from 1.8 kHz, the shelf down from 800 Hz.)
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=30.0, high_cut=1800.0, high_shelf=(800.0, -6.0)),
                                                         sounds.wide(0.25)]
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
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=80.0, bands=tone, **top)] \
                        + moved + [sounds.warm(0.3), sounds.wide(1.3), sounds.echo(house.BPM, 0.26, left=3, right=4, again=0.36)]
                    line.send = max(line.send, 0.24)
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
                    if synth_played and written in OPEN_TOP:
                        toned = sounds.equalise(low_cut=85.0, high_shelf=(7000.0, -2.0))
                    elif synth_played:
                        toned = sounds.equalise(low_cut=85.0, bands=((2500.0, -5.0, 1.0),), high_shelf=(3500.0, -8.0))
                    else:
                        toned = sounds.equalise(low_cut=85.0, bands=((1200.0, 3.0, 1.5),), high_shelf=(4000.0, 6.0))
                    # (...and the lead: tape, a chorus on a synth's, a longer echo from side to side, more room.)
                    widened = ([sounds.excite(0.15)] if written in OPEN_TOP else []) + [sounds.ensemble(0.35), sounds.wide(1.3)] if synth_played else []
                    line.effects = list(line.effects) + [toned, sounds.warm(0.35)] + widened + [sounds.echo(house.BPM, 0.3, left=3, right=4, again=0.42)]
                    line.send = max(line.send, 0.3)
                elif channel == "texture":
                    # (...and the pad 15 to 35 dB too much there: its glass is kept, its glare taken away; 16 dB bright still on
                    # 2026-11-17, night, with the risers tamed: 4 dB more off, and closed from 5 kHz.)
                    # (Third pass, midday: the pads alone, in the open and the themes, still 7 to 20 dB over at 3.5 to 7 kHz.)
                    # (2026-11-18, "hollow": the pads from 110 Hz, not 200, their top a little more open, the moving low-pass
                    # doing the rest; and wider.)
                    closed = sounds.equalise(low_cut=110.0, high_cut=4200.0, high_shelf=(2500.0, -10.0)) if synth_played \
                        else sounds.equalise(low_cut=110.0, high_cut=6000.0, high_shelf=(3000.0, -9.0))
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
    """A House take's music sheet, its first draft: what the writer (studio.house) asks to be played, taken down as it
    writes (`listen`), every part with its effect marks. Each part's low-pass follows its notes' brightness as the
    track opens and closes (`cutoff`), and its high-pass where the form takes the bottom away (`thinning`)."""
    track = house.Take(house.family(name), take)
    fam = track.family
    heard = listen(track)
    calm = fam.role in house.CALM_ROLES
    form = [dict({"story": story, "first": first, "bars": count}, **({"breakdown": True} if track.broken(story, first) else {}))
            for story, first, count in track.sections]
    parts: dict[str, dict[str, Voice]] = {channel: {} for channel in forever.CHANNELS}
    for (channel, table, sound), notes in sorted(heard.notes.items()):
        part = Voice(instrument=PLAYED[(table, sound)],
                     notes=[Note(at / BEAT, length / BEAT, int(round(pitch)), level) for at, length, pitch, level, _, _ in notes])
        lane: list[tuple[float, float]] = []
        for at, _, _, _, _, bright in sorted(notes):
            # The drop's big synths open further than the band: the hook, whose edge is what is heard (a theme's lead
            # about 6 kHz, not 3; "i wish i could hear more of that saw synths top end"). The other leads follow the band.
            beat, hz = at / BEAT, cutoff(0.35 + 0.65 * bright if channel == "lead" and PLAYED[(table, sound)] in OPEN_TOP else bright)
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
    if not calm:
        harsher(parts, form)
    machine = heard.hits[0][1] if heard.hits else ""
    for drum, _, at, level, _ in heard.hits:
        parts["drums"].setdefault(drum, Voice(drums=True, instrument="house kit " + machine)).notes.append(Note(at / BEAT, 0.25, 36, level))
    meta = track.meta()
    about = {"meta": meta, "frames": track.frames, "kick": bool(track.kick), "role": fam.role, "calm": calm, "seed": track.seed,
             "machine": machine, "hard": fam.hard}
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
            notes.append(Note(note.start, note.length, note.pitch, note.loud * HARSH * step))
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
            if part.effects:
                heard.marks[(channel, table, sound)] = (part.effects, part.settings)
    heard.hits = sorted(((drum, sheet.about["machine"], n.start * BEAT, n.loud, 0.0) for drum, part in sheet.parts.get("drums", {}).items()
                         for n in part.notes), key=lambda hit: hit[2])
    heard.airs = [house.Air(**air) for air in sheet.airs]
    return heard


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


def stage(name: str, take: int) -> dict:
    """Writes one take of a house family as its sheet and performs it (`write`, `perform`)."""
    return perform(write(name, take))


def perform(sheet: Sheet) -> dict:
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
        folders.append((desk.Line(channel, desk.bare(channel, []), effects=bus, moves=moves), under[channel]))
    seconds = sheet.bars * house.BAR
    rpp = work / "track.rpp"
    rpp.write_text(desk.project(folders, bpm=float(house.BPM), seconds=seconds, out=work, tail=forever.POST_S, hall=sounds.hall(1.5, top=6000.0)), encoding="utf-8")       # a darker room than the orchestra's
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
    faders = {}
    alone: dict[str, list[tuple[float, float]]] = {}
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
        if channel == "lead":
            # The hook stands at its place at the drop, and a part of the story that would stand more than 3 dB over it is
            # ridden down to that on the lead's own volume envelope, as a mixer rides a fader (2026-11-19: Blades III's
            # riff was 15 dB under its rises at the drops, the whole channel turned down by its rises).
            faders[channel] = 10.0 ** ((want[channel] - have) / 20.0)
            parts[channel] = (parts[channel] * faders[channel]).astype(np.float32)
            ride = ridden(parts[channel], list(zip(edges, edges[1:])), want[channel] + 3.0, int(house.BAR_FRAMES))
            if ride is not None:
                parts[channel] = (parts[channel] * ride[:, None]).astype(np.float32)
                alone[channel] = desk.ride_points(ride)
            continue
        have = max(have, max(analysis.loudness_lufs(parts[channel][low:high], RATE) for low, high in zip(edges, edges[1:])) - 3.0)
        faders[channel] = 10.0 ** ((want[channel] - have) / 20.0)
        parts[channel] = (parts[channel] * faders[channel]).astype(np.float32)
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
    meta["credit"] = ("Written by FreeRock's studio (studio.house); played in REAPER by the Surge XT synth (with Argitoth's Trance Lead 1 "
                      "and the LinnStrument set's Drawbar Organ 1, patches that ship with it), MuseScore Studio's Muse Sounds (Muse Group) "
                      "and MckAudio's TR-8 drum-machine recordings (CC0), put together by studio.club.")
    found = house.measure(meta, parts)
    folder = stage_root(VAR, "house") / name / str(take)
    write_track(folder, meta, parts)
    sheet.save(folder / "sheet.json")
    found.update(family=name, take=take, title=meta["title"], seconds=round(seconds, 1), took=round(time.time() - began, 1),
                 voices=sorted("%s: %s %s -> %s" % (channel, table, sound, PLAYED[(table, sound)]) for channel, table, sound in heard.notes))
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
