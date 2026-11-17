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

A sound in the writer has a brightness for every note (how far its filter is open: it opens as
a track builds). A voice is therefore laid over up to four tracks of the same instrument, each
with its top closed a little less, and every note goes to the one its brightness calls for.

Under each stroke of the kick the bass, the pad and the chords give way and come back (the
drawn volume curve of studio.build, deeper here: this is the music that curve comes from).

    cd app && uv run --no-sync --with numba python -m freerock.studio.club pastoral-01/1 [...]

(numba is asked for because studio.house still brings the old synthesiser in with it.)
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import analysis, forever
from . import RATE, desk, house, muse, reaper, sfz, sounds, stage_root, write_track
from .score import Note, Voice

VAR = Path(__file__).resolve().parents[3] / "var"
PROJECTS = VAR / "reaper" / "projects"
BEAT = house.BEAT
# What plays each of the writer's sounds: (the writer's table, its name for the sound) -> a written instrument the
# desk knows (sounds.SOUNDS for the synths, muse.PARTS for the real ones).
PLAYED = {
    ("bass", "sub"): "house sub", ("bass", "pluck"): "house bass pluck", ("bass", "saw"): "house bass saw", ("bass", "square"): "house bass square",
    ("bass", "fm"): "house bass fm", ("bass", "reese"): "house bass wide", ("bass", "organ"): "house bass organ",
    ("keys", "piano"): "house piano", ("keys", "keys"): "electric piano", ("keys", "organ"): "house organ", ("keys", "stab"): "house stab",
    ("keys", "pluck"): "house pluck", ("keys", "bell"): "house bell", ("keys", "glass"): "house glass", ("keys", "harp"): "harp",
    ("keys", "marimba"): "marimba", ("keys", "oud"): "guitar", ("keys", "string"): "guitar", ("keys", "brass"): "brass",
    ("lead", "saw"): "house lead saw", ("lead", "super"): "house lead super", ("lead", "hollow"): "house lead hollow", ("lead", "pipe"): "pan flute",
    ("lead", "whistle"): "house lead sine", ("lead", "flute"): "flute", ("lead", "bell"): "house bell", ("lead", "glass"): "house glass",
    ("lead", "keys"): "wurly", ("lead", "pluck"): "house pluck", ("lead", "marimba"): "marimba", ("lead", "harp"): "harp", ("lead", "oud"): "guitar",
    ("lead", "string"): "harp", ("lead", "brass"): "trumpet",
    ("pad", "warm"): "house pad warm", ("pad", "strings"): "strings slow", ("pad", "super"): "house pad super", ("pad", "glass"): "house pad glass",
    ("pad", "hollow"): "house pad hollow", ("pad", "organ"): "house pad organ",
}
# How far a note's top is closed, by how bright the writer asks for it (under this much brightness: this cut, in Hz; 0 is open).
BRIGHT = ((0.55, 900.0), (0.7, 2200.0), (0.85, 5000.0), (9.0, 0.0))
KICKS = ("kick", "kick2", "punch", "boom")
# How far each channel is turned down under a stroke of the kick, as a part of its level (studio.build.DUCK is the
# orchestra's: 0.56 for its bass). The writer's own pump took 55 to 75% of the bass away and half of the pad.
DUCK = {"bass": 0.5, "texture": 0.55, "rhythm": 0.72, "lead": 0.9}
# ...and how long each takes to come back, in beats. The bass is back in a third of a beat (about 150 ms at 110 BPM,
# where the records studied put it), so the low end is clear for the kick and full again before the off-beat; the
# pad takes three quarters of one, which is the pump that is heard.
RECOVER = {"bass": 0.33, "texture": 0.75, "rhythm": 0.6, "lead": 0.5}
# Where each channel sits where the track is fullest (LUFS), as the writer's own mix had them.
PLACE = {"drums": -14.0, "bass": -16.5, "rhythm": -20.0, "lead": -19.0, "texture": -22.0}
CALM = {"drums": -18.0, "bass": -18.0, "lead": -18.0, "texture": -20.0}        # an inn, the night


@dataclass
class Heard:
    """What the writer asked to be played."""
    notes: dict[tuple[str, str, str], list[tuple[float, float, float, float, float, float]]] = field(default_factory=lambda: defaultdict(list))
    hits: list[tuple[str, str, float, float, float, bool]] = field(default_factory=list)      # drum, machine, seconds, level, pan, in the room
    airs: list = field(default_factory=list)       # what the texture is besides its notes: risers, wind, drips (house.Air)


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
        heard.hits.append((sound.name, sound.machine, float(at), float(level), float(pan), sound.name not in KICKS))

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


def _bar_of(at: float) -> int:
    """The bar a note is struck in (one struck a hair early, as a player does, belongs to the bar it is early for)."""
    return int((at + 0.02) // house.BAR)


def _bars(notes: list[tuple[float, float, float, float, float, float]]) -> dict[int, float]:
    """How loud the writer has a voice in each bar it plays in: the mean of the notes struck there."""
    struck: dict[int, list[float]] = defaultdict(list)
    for at, _, _, level, _, _ in notes:
        struck[_bar_of(at)].append(level)
    return {bar: float(np.mean(levels)) for bar, levels in struck.items()}


def _ride(bars: dict[int, float]) -> list[tuple[float, float]]:
    """A voice's levels from bar to bar as its track's volume moves ((beat, gain)), its loudest bar
    at full. (2026-11-17, morning: the house tracks came out all but level from their first bar to
    their last, 2 to 9 dB between their quietest part and their loudest. Surge XT's patches play a
    note alike however hard it is struck, so what the writer wrote softer was not: a breakdown's
    pad written 5 dB under the drop's came out 5 dB over it. Muse Sounds' instruments do play
    softer, and keep their velocities.)"""
    top = max(bars.values())
    moves: list[tuple[float, float]] = []
    before = None
    for bar in sorted(bars):
        gain = bars[bar] / top
        if before is not None and abs(gain - before) < 0.01:
            continue
        at = bar * 4.0
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
    bars = {key: _bars(notes) for key, notes in heard.notes.items()}
    most: dict[str, float] = defaultdict(float)
    for (channel, _, _), levels in bars.items():
        most[channel] = max(most[channel], max(levels.values()))
    out = []
    for (channel, table, name), notes in sorted(heard.notes.items()):
        written = PLAYED[(table, name)]
        levels = bars[(channel, table, name)]
        # Each voice of a channel to the others as the writer has them where each is loudest (its quieter bars are the
        # volume moves' business, or its velocities').
        taste = min(max(max(levels.values()) / most[channel], 0.35), 1.0)
        if written in muse.PARTS and muse.available():
            hard, ride = _loud([level for _, _, _, level, _, _ in notes]), []
        else:
            # The bars ride the track's volume; how hard a note is struck says only how it stands out in its bar.
            hard, ride = _loud([level / levels[_bar_of(at)] for at, _, _, level, _, _ in notes]), _ride(levels)
        bands: dict[float, list[Note]] = defaultdict(list)
        for (at, length, pitch, _, _, bright), loud in zip(notes, hard):
            cut = next(cut for under, cut in BRIGHT if bright < under)
            bands[cut].append(Note(at / BEAT, max(length / BEAT, 0.05), int(round(pitch)), loud))
        for cut, mine in sorted(bands.items()):
            out.append((channel, table, name, written, cut, mine, taste, ride))
        if written == "house sub":
            # (2026-11-17, night: against the liked house stems the bass was 30 dB short in its middle and 44 at its top: a
            # sine under 100 Hz, which a small loudspeaker does not play at all.) A sawtooth on the same notes, closed
            # above 900 Hz and well under the sub, is the part of the bass that is heard; the sub is the part that is felt.
            every = [note for _, mine in sorted(bands.items()) for note in mine]
            out.append((channel, table, name + " growl", "house bass saw", 900.0, every, taste * 0.45, ride))
    return out


def lines(heard: Heard, track: house.Take, work: Path) -> tuple[dict[str, list[desk.Line]], list[tuple[float, float]]]:
    """The REAPER tracks of a take, by channel, and where its kick strikes ((beat, how hard))."""
    seed = track.seed
    out: dict[str, list[desk.Line]] = defaultdict(list)
    # ----- drums: the kick by itself, the rest of the machine, and what is struck in the room
    used = sorted({name for name, *_ in heard.hits})
    strokes: list[tuple[float, float]] = []
    if used:
        machine = heard.hits[0][1]
        file, keys = kit_file(machine, used)
        hard = _loud([level for _, _, _, level, _, _ in heard.hits])
        sets: dict[str, list[Note]] = defaultdict(list)
        for (name, _, at, level, pan, wet), loud in zip(heard.hits, hard):
            which = "kick" if name in KICKS else "room" if wet else "kit"
            sets[which].append(Note(at / BEAT, 0.25, keys[name], loud))
            if name in KICKS:
                strokes.append((at / BEAT, loud))
        template = desk.bare("house kit", [desk.sfizz(file)])
        chains = {
            # The kick: its stroke brought out, what is under 30 Hz taken away, held together; nothing of it in the hall.
            "kick": ([sounds.punch(0.35, -0.1), sounds.equalise(low_cut=30.0, bands=((320.0, -2.5, 1.2), (3500.0, 2.0, 1.6))), sounds.smash(0.3)], 0.0, 1.0),
            "kit": ([sounds.equalise(low_cut=120.0, high_shelf=(9000.0, 1.5)), sounds.smash(0.25)], 0.06, 0.7),
            "room": ([sounds.equalise(low_cut=180.0)], 0.22, 0.6),
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
            for line in sounds.lines(Voice(0, notes=mine, instrument=written), title, house.BPM, taste=taste, room=1.0, seed=seed,
                                     muse_level=sounds.LEVEL):
                if ride:
                    line.moves = list(ride)
                if cut:
                    line.effects = list(line.effects) + [sounds.equalise(high_cut=cut)]
                if channel == "bass":
                    # (Against the liked house stems the sawtooth and wide basses were 13 to 34 dB bright above 2.5 kHz,
                    # 2026-11-17, night: a house bass is closed well down. The growl beside the sub has its own cut.)
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=30.0, high_cut=2500.0, high_shelf=(1200.0, -6.0)),
                                                         sounds.wide(0.25)]
                    line.send = 0.0
                elif channel == "rhythm":
                    # (Measured against the house stems that were liked: the plucks had 11 to 24 dB too much above 3 kHz.)
                    # (Still 13 dB bright there on 2026-11-17, night: 4 dB more; then still 11: 4 more and closed from 7 kHz.)
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=140.0, high_cut=7000.0, high_shelf=(4500.0, -16.0)),
                                                         sounds.echo(house.BPM, 0.2, left=3, right=4, again=0.32)]
                    line.send = max(line.send, 0.16)
                elif channel == "lead":
                    # (6 dB dull at its top and 3 in its middle against the liked house stems, 2026-11-17, night; 5 dB dull after the first lift.)
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=180.0, bands=((1200.0, 3.0, 1.5),), high_shelf=(4000.0, 6.0)),
                                                         sounds.echo(house.BPM, 0.24, left=3, right=4, again=0.34)]
                    line.send = max(line.send, 0.2)
                elif channel == "texture":
                    # (...and the pad 15 to 35 dB too much there: its glass is kept, its glare taken away; 16 dB bright still on
                    # 2026-11-17, night, with the risers tamed: 4 dB more off, and closed from 5 kHz.)
                    line.effects = list(line.effects) + [sounds.equalise(low_cut=200.0, high_cut=5000.0, high_shelf=(3500.0, -10.0)),
                                                         sounds.ensemble(0.35)]
                    line.send = max(line.send, 0.28)
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
                               effects=[sounds.equalise(low_cut=150.0, high_cut=7000.0, high_shelf=(2500.0, -9.0))]))
    return lines


def stage(name: str, take: int) -> dict:
    """Writes one take of a house family, has REAPER play it, balances it and stages it."""
    began = time.time()
    track = house.Take(house.family(name), take)
    fam = track.family
    work = PROJECTS / "house" / name / str(take)
    work.mkdir(parents=True, exist_ok=True)
    heard = listen(track)
    if muse.available():
        # MuseScore performs its instruments' lines several at a time before the project is put together.
        muse.prepare([(written, mine, float(house.BPM), []) for _, _, _, written, _, mine, _, _ in voices(heard) if written in muse.PARTS],
                     seed=track.seed, workers=4)
    under, strokes = lines(heard, track, work)
    folders = []
    for channel in forever.CHANNELS:
        if not under.get(channel):
            continue
        moves, last = [], -1.0
        for at, loud in sorted(strokes) if channel in DUCK else ():
            if at <= last:
                continue
            down = 1.0 - (1.0 - DUCK[channel]) * min(loud / 0.8, 1.0)
            # Down just before the stroke, held for a moment, back over the channel's own time.
            back = RECOVER[channel]
            moves += [(at - 0.02, 1.0), (at, down), (at + 0.08, down), (at + back, 1.0)]
            last = at + back
        bus = sounds.bus(channel, style="house")
        if channel == "drums":
            # A drum machine on a dance floor is not a kit in a hall: no room around it and no tape on it, only the box
            # at 250 Hz taken down and a compressor slow enough to let every stroke through (measured against the liked
            # house stems: the strokes rose a third as fast as theirs through the orchestra's drum bus).
            bus = [sounds.equalise(low_cut=28.0, bands=((250.0, -3.0, 1.2),)), sounds.squeeze(-16.0, 2.5, 12.0, 120.0, 1.5),
                   sounds.ceiling(-1.0, push=1.5)]
        folders.append((desk.Line(channel, desk.bare(channel, []), effects=bus, moves=moves), under[channel]))
    seconds = track.bars * house.BAR
    rpp = work / "track.rpp"
    rpp.write_text(desk.project(folders, bpm=float(house.BPM), seconds=seconds, out=work, tail=forever.POST_S, hall=sounds.hall(1.5)), encoding="utf-8")
    with reaper.Display() as display:
        desk.render(rpp, display=display, timeout=300.0 + 12.0 * seconds)       # (see build.stage)
    parts = desk.stems(work, [bus.name for bus, _ in folders], track.frames)
    # Each channel to its place by how loud it is where the track is fullest, as the writer's own mix did it. (Measured
    # here and done in REAPER, as a mixer would: see below.)
    story, first, count = next(section for section in reversed(track.sections) if section[0] == "moment")     # the last drop
    a, b = int(round(first * house.BAR_FRAMES)), int(round((first + count) * house.BAR_FRAMES))
    want = dict(PLACE, **(CALM if fam.role in ("ember", "night") else {}))
    if not track.kick:
        want["drums"] = -27.0
    faders = {}
    for channel in list(parts):
        have = analysis.loudness_lufs(parts[channel][a:b], RATE)
        if have < -70.0:
            have = analysis.loudness_lufs(parts[channel], RATE)
        if have < -70.0:
            del parts[channel]                       # it plays nothing to speak of in this take
            continue
        # ...but never so far up that another part of the story goes more than 3 dB over the channel's place (as the
        # orchestra's desk does since 2026-11-17, night: a house tune soft at its drop and full in its theme blared there).
        edges = [0] + [int(round((first + count) * house.BAR_FRAMES)) for _, first, count in track.sections]
        have = max(have, max(analysis.loudness_lufs(parts[channel][low:high], RATE) for low, high in zip(edges, edges[1:])) - 3.0)
        faders[channel] = 10.0 ** ((want[channel] - have) / 20.0)
        parts[channel] = (parts[channel] * faders[channel]).astype(np.float32)
    # What is still ringing two seconds before the recording ends is eased away to nothing (as the writer's own render does).
    last = int(2.0 * RATE)
    ease = np.ones(track.frames, dtype=np.float32)
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
                             frames=track.frames, display=display, timeout=300.0 + seconds)
    for bus, _ in folders:
        (work / (bus.name + ".wav")).unlink()
    meta = track.meta()
    meta["credit"] = ("Written by FreeRock's studio (studio.house); played in REAPER by the Surge XT synth, MuseScore Studio's Muse Sounds "
                      "(Muse Group) and MckAudio's TR-8 drum-machine recordings (CC0), put together by studio.club.")
    found = house.measure(meta, parts)
    folder = stage_root(VAR, "house") / name / str(take)
    write_track(folder, meta, parts)
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
