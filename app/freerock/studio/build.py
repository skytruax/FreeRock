"""Writing the studio's library: which families there are, and playing every take of them.

The orchestra's families are for the Warcraft style and the band's for Knight Rock; both are
written by studio.orchestra and played in REAPER (studio.desk): every instrument line a track
of real recorded instruments or of the Surge XT synth, in a project that is kept beside the
staged track.

    uv run --no-sync python -m freerock.studio.build                 every family, every take
    uv run --no-sync python -m freerock.studio.build --list          what there would be
    uv run --no-sync python -m freerock.studio.build --only reel     only families whose name has "reel" in it
    uv run --no-sync python -m freerock.studio.build --style knight  only the band's

A take that is staged already is left alone, so the command can be stopped and run again.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from .. import analysis, forever
from . import RATE, desk, muse, reaper, sounds, stage_root, write_track
from .orchestra import CHANNELS, CHARACTERS, INSTRUMENTS, Family, Take, family, settings_of
from .score import humanise

VAR = Path(__file__).resolve().parents[3] / "var"
PROJECTS = VAR / "reaper" / "projects"       # every track's REAPER project is kept here, to be opened and changed by hand
MASTER = 20261115
# Where each channel sits when everyone is playing (LUFS at the moment, before the whole track
# is brought to the bucket's level): the tune on top, the pad and the accompaniment under it.
PLACE = {"lead": -17.0, "texture": -21.0, "rhythm": -21.5, "bass": -18.5, "drums": -21.0}       # an orchestra's drums are a few great strokes: by loudness they sit low
LIGHT = {"drums": -24.0, "bass": -21.5}        # a light track's drums and bass sit further back
WAR_DRUMS = -16.0                              # where the drums sit in a track that has war drums: up with the tune, the loudest strokes in the piece
BAND = {"lead": -17.0, "rhythm": -18.5, "drums": -18.0, "bass": -19.5, "texture": -24.0}       # a band: guitars and drums up front
BAND_LIGHT = {"drums": -21.0, "bass": -21.0, "rhythm": -20.0}
RIDE = 0.15                    # how far each part of the story is brought up towards the loudest part (it was 0.42, which
                               # took most of the written dynamics away: "rewrite all music to be more dynamic", 2026-11-16)
# The least each channel is played at in each part of the story, so that the story is whole
# whatever the game is doing; the game then only adds weight to the drums and the bass.
# Under every stroke of the kick the other channels give way for a moment and come back within
# a quarter of a second: drawn into each channel's volume, the same at every stroke (how dance
# music makes room for its kick: a drawn curve, not a compressor that listens). How far each
# channel is turned down under the hardest stroke, as a part of its level.
DUCK = {"bass": 0.56, "texture": 0.8, "rhythm": 0.8, "lead": 0.9}
DRUMS_UP = 6.0                 # dB: the most the drums are ever turned up to reach their place
MUSE_WORKERS = 5               # how many parts of a piece MuseScore performs at once
# (2026-11-16, twice. In the afternoon: "theres not much difference between quet and full, we want more ...
# drasticness", and a calm game was given no drums and a third of the bass. Played that evening: "the abruptness
# between fighting and not, its way too much now, it should only be a subtle difference like before". So these are
# as they were before: the drums and the bass stand at 55 to 100% whatever the game does, and a fight adds the rest.)
FLOOR = {"open": {"rhythm": 1.0, "bass": 0.85, "drums": 0.6}, "theme": {"rhythm": 1.0, "bass": 0.85, "drums": 0.55},
         "rise": {"rhythm": 1.0, "bass": 0.9, "drums": 0.75}, "moment": {"rhythm": 1.0, "bass": 1.0, "drums": 0.9},
         "close": {"rhythm": 1.0, "bass": 0.85, "drums": 0.55}}


def plan() -> list[tuple[Family, int]]:
    """Every family of the library and how many takes of it there are. A character that is
    for walking about gets a family of three takes (and the light ones a second family of
    two, since light places hear nothing else); the rarer moments get fewer."""
    out: list[tuple[Family, int]] = []
    titles: set[str] = set()

    def add(index: int, character, number: int, takes: int) -> None:
        seed = MASTER * 100 + index * 10 + number
        rng = random.Random(seed)
        first, second = character.titles
        title = None
        for _ in range(50):
            title = "%s %s" % (rng.choice(first), rng.choice(second))
            if title not in titles:
                break
        titles.add(title)
        place = character.kinds[0] if len(character.kinds) < 5 else "anywhere"
        name = "%s-%s-%d" % (place, character.name.replace(" ", "-"), number + 1)
        out.append((family(character, seed, name, title), takes))

    later, camps = [], []
    for index, character in enumerate(CHARACTERS):
        if character.role == "camp":
            camps.append((index, character))          # (see below)
            continue
        if character.role == "wander":
            shapes = [3, 2] if character.light or character.band else [3]
            if not (character.light or character.band):
                later.append((index, character))
        elif character.role in ("town", "battleground"):
            shapes = [3, 3]                 # a family of songs for a town or a battleground: two families of three
        elif character.role in ("battle", "ember", "storm", "boss"):
            shapes = [2, 2]
        else:
            shapes = [2]
            if character.role in ("depths", "night"):
                later.append((index, character))
        for number, takes in enumerate(shapes):
            add(index, character, number, takes)
    # (2026-11-16, played: "need more variety in warcraft".) The heavy music for walking about has a second family too:
    # its own key, pace, changes and tunes; and so has the music for caves ("been hearing the same thing over and
    # over": a cave had two pieces). These are named after all the others, so that no family made before is given
    # another title.
    for index, character in later:
        add(index, character, 1, 2)
    # Camping (2026-11-17: "camping should get its own tunes"): two families of two for each, named after every family
    # made before them, so that none of those is given another title.
    for index, character in camps:
        for number in (0, 1):
            add(index, character, number, 2)
    return out


# What crowns a heavy piece's moments, by the kind of place it is for: who sings the pad's chords with the strings, and
# whether a bell is struck on the moment's first beat. (2026-11-16, played: "need more variety in warcraft". Every heavy
# piece had a choir and a bell at its moments, so every moment sounded alike.) Music for every kind of place, the
# fights and the storms keep the choir and the bell.
CROWNS = {"haunted": ("choir", True), "mystic": ("choir", True), "regal": ("choir", True), "infernal": ("choir", False),
          "highland": ("horns", True), "pastoral": ("horns", False), "desert": ("", False), "jungle": ("", False)}


CROWNS_LIGHT = {"pastoral": "horns", "highland": "horns", "regal": "horns", "mystic": "oohs", "haunted": "oohs", "jungle": "oohs",
                "desert": "", "infernal": ""}


def crown_of(character) -> tuple[str, bool]:
    if character.role in ("boss", "battleground") and not character.band:
        return "full choir", True                    # the whole choir, every voice, where the fight is greatest
    if character.light:
        return (CROWNS_LIGHT[character.kinds[0]] if len(character.kinds) < 5 else "oohs"), False
    if len(character.kinds) >= 5:
        return "choir", True
    return CROWNS[character.kinds[0]]


def folder_of(fam: Family, take: int) -> Path:
    return stage_root(VAR, fam.character.style) / fam.name / str(take)


def project_of(fam: Family, take: int) -> Path:
    return PROJECTS / fam.character.style / fam.name / str(take) / "track.rpp"


def tamed_tone(name: str, instrument: str) -> str | None:
    """The top of a voice that comes out bright against the liked stems, taken down (2026-11-17, midday, the morning's
    storms, inns, bosses and battles: the brass stabs and the tubular bells at the moments had the accompaniment 12 to
    16 dB over from 3.5 kHz up, and the harmonica that plays the accordion had the inns' texture 20 to 24 dB over)."""
    if name.endswith(" stabs") or name == "bell at the moments":
        return sounds.equalise(high_shelf=(3000.0, -9.0))
    if instrument == "accordion":
        return sounds.equalise(high_cut=7000.0, high_shelf=(2500.0, -10.0))
    return None


def stage(fam: Family, take: int) -> dict:
    """Writes one take of a family, has REAPER play it, balances the channels and stages the
    track. Returns what it measured. The REAPER project is kept (see `project_of`)."""
    character = fam.character
    written = Take(fam, take)
    rng = random.Random(fam.seed * 31 + take)
    bar_frames = fam.beats * 60.0 / fam.bpm * RATE
    whole = int(round(fam.bars * bar_frames))
    frames = whole + int(round(forever.POST_S * RATE))
    edges, bars = [0], 0
    for section in fam.sections:
        bars += section.bars
        edges.append(int(round(bars * bar_frames)))
    # Where everyone is playing: the last and biggest of the story's moments.
    moment = max(index for index, section in enumerate(fam.sections) if section.story == "moment")
    room = character.hall[1] / 0.24
    # Where the kick strikes: the kit's bass drum (where the kick goes with it), the biggest war drum, the deep stroke.
    from .orchestra import KITS
    strokes: list[tuple[float, float]] = []
    for name, voice in written.voices["drums"].items():
        if voice.drums and voice.instrument[4:] in sounds.KICKED:
            boom = KITS[voice.instrument[4:]]["boom"]
            strokes += [(note.start, note.loud) for note in voice.notes if note.pitch == boom]
        elif voice.instrument in ("war drums", "boom", "kick"):
            strokes += [(note.start, note.loud) for note in voice.notes if note.pitch == 36]
    for channel in CHANNELS:
        for name, voice in written.voices[channel].items():
            if voice.notes:
                humanise(voice, rng, timing=0.004 if channel == "drums" else 0.007, bpm=fam.bpm)
    # ----- What the desk stacks on what the writer wrote (2026-11-16: "stack on top of this for interesting layers",
    # "better get the kickdrum in those moments", "more depth more instruments .... more bass and kick in the intense parts").
    from .score import Note, Voice
    beat_of = fam.bpm / 60.0 / RATE
    told = [(section.story, edges[index] * beat_of, edges[index + 1] * beat_of, section.bars) for index, section in enumerate(fam.sections)]
    spans = [(first, last) for story, first, last, _ in told if story == "moment"]
    pads = [voice for voice in written.voices["texture"].values() if voice.instrument in ("tremolo", "strings", "strings slow") and voice.notes]
    if pads:
        # Depth: a wide synth pad far under the string pad, all the way through.
        written.voices["texture"]["pad under"] = Voice(notes=[Note(note.start, note.length, note.pitch, 0.5) for voice in pads for note in voice.notes
                                                                  if 48 <= note.pitch <= 84], instrument="pad")
    low = sorted((note for voice in written.voices["bass"].values() if not voice.drums for note in voice.notes), key=lambda note: note.start)
    if character.role != "night":
        # A kick on the bar all through each moment (and on the half bar, in heavy music), and on the last bars of each
        # rise; where the writer has a stroke there already, that one stands.
        had = sorted(note.start for voice in written.voices["drums"].values() for note in voice.notes
                     if (voice.drums and note.pitch == 36) or (voice.instrument in ("war drums", "boom", "kick") and note.pitch == 36))
        kicks = []
        for story, first, last, bars in told:
            if story not in ("moment", "rise"):
                continue
            for bar in range(bars):
                if story == "rise" and bar < bars * 0.6:
                    continue
                ons = [0.0] if character.light or story == "rise" or fam.beats < 4 else [0.0, fam.beats / 2.0]
                for on in ons:
                    at = first + bar * fam.beats + on
                    if at < last - 0.01 and not any(abs(at - each) < 0.12 for each in had):
                        strength = (0.6 if character.light else 0.9 if on == 0.0 else 0.75) * (0.8 if story == "rise" else 1.0)
                        kicks.append(Note(at, 0.5, 36, strength))
        if kicks:
            written.voices["drums"]["kick at the moments"] = Voice(notes=kicks, instrument="kick")
            strokes += [(note.start, note.loud) for note in kicks]         # the other channels give way under these as well
    if low and spans and not character.light:
        # More bass where it is intense: a deep sub and low brass double the bass line through each moment, and a bell
        # is struck on the moment's first beat, on the note the bass has there.
        deep = [note for note in low if any(first <= note.start < last for first, last in spans)]
        written.voices["bass"]["sub at the moments"] = Voice(notes=[Note(note.start, note.length, note.pitch, 0.8) for note in deep], instrument="deep")
        if not any(voice.instrument in ("tuba", "trombone") and voice.notes for voice in written.voices["bass"].values()):
            written.voices["bass"]["low brass at the moments"] = Voice(notes=[Note(note.start, note.length, note.pitch if note.pitch >= 29 else note.pitch + 12, 0.75) for note in deep if note.length >= 0.45],
                instrument="tuba")
        rung = []
        for first, last in spans:
            under = [note for note in low if note.start <= first + 0.05 < note.start + note.length + 0.5] or [note for note in low if note.start >= first][:1]
            if under:
                rung.append(Note(first, 4.0, 60 + under[0].pitch % 12, 0.8))
        if rung and crown_of(character)[1] and not any(voice.instrument in ("bells", "church bell") for voice in written.voices["rhythm"].values()):
            written.voices["rhythm"]["bell at the moments"] = Voice(notes=rung, instrument="bells")
    crown = crown_of(character)[0]
    if muse.available() and crown and not (character.band and not character.light):
        # A layer on top, where the story comes to its moments: a choir sings the pad's chords with the strings (the
        # horns, in the open country and the hills). Light music has it too, softly (2026-11-16, played: "not enough
        # instruments in each track").
        low, high = (43, 79) if crown in ("choir", "oohs", "full choir") else (41, 74)
        sung = [note for voice in written.voices["texture"].values() if voice.instrument in ("tremolo", "strings", "strings slow")
                for note in voice.notes if any(first <= note.start < last for first, last in spans) and low <= note.pitch <= high]
        if sung and crown not in {voice.instrument for voice in written.voices["texture"].values()}:
            soft = 0.55 if character.light else 0.72
            written.voices["texture"]["%s at the moments" % crown] = Voice(notes=[type(note)(note.start, note.length, note.pitch, soft) for note in sung],
                                                                           instrument=crown)
    if muse.available() and character.band:
        # A band's plain guitar is an electric one played clean (its steel-strung ones stay acoustic).
        for channel in CHANNELS:
            for voice in written.voices[channel].values():
                if voice.instrument == "guitar":
                    voice.instrument = "clean guitar"
    if muse.available():
        # MuseScore performs every instrument it has, several at a time, before the project is put together.
        muse.prepare([(voice.instrument, voice.notes, fam.bpm, voice.swells) for channel in CHANNELS for voice in written.voices[channel].values()
                      if voice.notes and not voice.drums], seed=fam.seed * 31 + take, workers=MUSE_WORKERS)
    folders = []
    for channel in CHANNELS:
        under = []
        for name, voice in written.voices[channel].items():
            if not voice.notes:
                continue
            taste = INSTRUMENTS[voice.instrument].level if voice.instrument in INSTRUMENTS else 1.0
            made = sounds.lines(voice, name, fam.bpm, taste=taste, room=room, seed=fam.seed * 31 + take)
            tamed = tamed_tone(name, voice.instrument)
            if tamed:
                for line in made:
                    line.effects = list(line.effects) + [tamed]
            under += made
        if under:
            moves, last = [], -1.0
            for at, loud in sorted(strokes) if channel in DUCK else ():
                if loud < 0.45 or at <= last:
                    continue
                down = 1.0 - (1.0 - DUCK[channel]) * min(loud / 0.85, 1.0)
                beat_s = 60.0 / fam.bpm
                moves += [(at - 0.012 / beat_s, 1.0), (at, down), (at + 0.06 / beat_s, down), (at + 0.26 / beat_s, 1.0)]
                last = at + 0.26 / beat_s
            folders.append((desk.Line(channel, desk.bare(channel, []), effects=sounds.bus(channel, style=character.style), moves=moves), under))
    rpp = project_of(fam, take)
    work = rpp.parent
    work.mkdir(parents=True, exist_ok=True)
    rpp.write_text(desk.project(folders, bpm=fam.bpm, seconds=whole / RATE, out=work, tail=forever.POST_S,
                                hall=sounds.hall(min(character.hall[0] * 1.3, 3.8))), encoding="utf-8")
    with reaper.Display() as display:
        # (A heavy piece on a machine that is doing other things renders at less than half speed: "lava fields" was
        # stopped twice, half a minute from its end, by a limit of twice its length. On the night of 2026-11-17, with
        # every core busy, two night pieces at the lowest priority rendered at an eighth of their speed and were stopped
        # by a limit of five times their length, minutes from the end. Twelve times: the limit is only there for a
        # REAPER that waits on a message nobody will answer.)
        desk.render(rpp, display=display, timeout=300.0 + 12.0 * whole / RATE)
    parts = desk.stems(work, [bus.name for bus, _ in folders], frames)
    # Each channel to its place in the mix, by how loud it is where everyone is playing. (What follows is measured here
    # and done in REAPER, as a mixer would: see the end.)
    if character.band:
        places = dict(BAND, **(BAND_LIGHT if character.weight < 0.7 else {}))
    else:
        places = dict(PLACE, **(LIGHT if character.weight < 0.7 else {}))
        if any(voice.notes for name, voice in written.voices["drums"].items() if name.startswith("war drums")):
            places["drums"] = WAR_DRUMS                 # war drums are meant to be heard, not only felt
    levels, gains = {}, {}
    for channel in list(parts):
        audio = parts[channel]
        loud = analysis.loudness_lufs(audio[edges[moment]:edges[moment + 1]], RATE)
        if loud < -60.0:
            loud = analysis.loudness_lufs(audio[:whole], RATE)
        if loud < -65.0:
            written_notes = sum(len(voice.notes) for voice in written.voices[channel].values() if not voice.drums)
            if written_notes >= 24:
                # Written and not heard: something between the writer and the recording failed (2026-11-17, night: the
                # Muse performances were laid into REAPER as the wrong kind of file, and three channels came out silent).
                raise RuntimeError("The %s channel of %s %d has %d notes written and came out silent (%.1f LUFS)"
                                   % (channel, fam.name, take, written_notes, loud))
            del parts[channel]                       # it plays nothing to speak of in this take
            continue
        # ...but never so far up that another part of the story goes more than 3 dB over the channel's place (2026-11-17,
        # night: a frost night's tune was a glockenspiel and slow violins at its moments, and a flute and handbells,
        # which carry far more when played as softly, in its rises; brought up by its moments, the rises blared).
        parts_of = [analysis.loudness_lufs(audio[first:last], RATE) for first, last in zip(edges, edges[1:])]
        loud = max(loud, max(parts_of) - 3.0)
        gain = min(max(places[channel] - loud, -18.0), 18.0)
        if channel == "drums":
            # A light piece's percussion is a few taps of a triangle or a shaker: measured by loudness they are next to
            # nothing, and brought up to the drums' place they became the loudest thing in the track (16 dB up, 2026-11-16).
            gain = min(gain, DRUMS_UP)
        parts[channel] = audio * np.float32(10 ** (gain / 20.0))
        levels[channel] = round(loud + gain, 1)
        gains[channel] = gain
    # The story keeps its shape but not its extremes: music behind a game cannot drop to a
    # whisper. Every part of the story is brought some of the way up to the loudest, the whole
    # band together, easing from one level to the next over three seconds at each join.
    mix = sum(parts.values())
    heard = [analysis.loudness_lufs(mix[first:last], RATE) for first, last in zip(edges, edges[1:])]
    lifts = [min((max(heard) - loud) * RIDE, 12.0) if loud > -70.0 else 0.0 for loud in heard]
    ride = np.empty(frames, dtype=np.float32)
    for index, (first, last) in enumerate(zip(edges, edges[1:])):
        ride[first:last] = lifts[index]
    ride[edges[-1]:] = lifts[-1]
    ease = int(1.5 * RATE)
    for index, edge in enumerate(edges[1:-1]):
        low, high = max(edge - ease, 0), min(edge + ease, frames)
        ride[low:high] = np.linspace(lifts[index], lifts[index + 1], high - low, dtype=np.float32)
    curve = (10.0 ** (ride / 20.0)).astype(np.float32)
    peak = max(float(np.abs(mix * curve[:, None]).max()), max(float(np.abs(audio * curve[:, None]).max()) for audio in parts.values()))
    scale = 0.6 / peak
    # The mix itself is REAPER's (2026-11-17, night: "remember to use reaper and plugins for effects and mixing"): each
    # channel's stem on a track of its own with its fader where it was measured to go, the ride of the story as the
    # volume envelope, rendered again; the project is kept as mix.rpp beside the track's own.
    recorded = {channel: work / (channel + ".wav") for channel in parts}
    with reaper.Display() as display:
        parts = desk.mixdown(work, recorded, faders={channel: 10 ** (gains[channel] / 20.0) * scale for channel in parts},
                             ride=desk.ride_points(curve), bpm=fam.bpm, seconds=whole / RATE, tail=forever.POST_S, frames=frames,
                             display=display, timeout=300.0 + whole / RATE)
    for bus, _ in folders:
        (work / (bus.name + ".wav")).unlink()      # the staged track has them; the project can make them again
    gains = {channel: round(gain, 1) for channel, gain in gains.items()}
    mix = sum(parts.values())
    loudness = [round(analysis.loudness_lufs(mix[first:last], RATE), 1) for first, last in zip(edges, edges[1:])]
    sections = []
    for section in fam.sections:
        told = {"story": section.story, "bars": section.bars}
        if section.lifted:
            told["tonic"] = fam.key.lifted(fam.lift).name
        sections.append(told)
    meta = {
        "style": character.style, "family": fam.name, "take": take, "title": fam.title, "tempo": fam.bpm, "beats": fam.beats,
        "bar_frames": bar_frames, "tonic": fam.key.name, "moods": list(character.kinds), "role": character.role,
        "serves": list(character.serves), "light": character.light, "settings": list(settings_of(character)),
        "sections": sections, "floor": FLOOR,
        "follow": {"rhythm": ["lead"], "texture": ["lead"]}, "post_s": forever.POST_S,
        "credit": "Written by FreeRock's studio (%s, %s); %sput together in REAPER, with the sfizz sampler on the VSCO 2 Community "
                  "Edition and VCSL recordings (Versilian Studios, CC0), the TinySOL recordings (Cella, Ghisi, Lostanlen, Levy, "
                  "Fineberg and Maresz, IRCAM, CC BY 4.0), Naked Drums (Wilkinson Audio, CC BY 4.0) and Big Rusty Drums (Karoryfer, "
                  "CC0), the AVL drum kits (Glen MacArthur, CC BY-SA 3.0) and the Surge XT, ZynAddSubFX and Geonkick synths"
                  % (character.name, fam.metre, "its instruments performed by MuseScore Studio with Muse Sounds (Muse Group) and " if muse.available() else ""),
        "seed": fam.seed, "measured": {"sections": loudness, "channels": levels, "gains": gains},
    }
    write_track(folder_of(fam, take), meta, parts)
    return {"family": fam.name, "take": take, "title": fam.title, "seconds": round(whole / RATE), "sections": loudness,
            "channels": levels, "gains": gains}


def _job(index: int, take: int) -> dict:
    fam, _ = plan()[index]
    return stage(fam, take)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write and play the orchestra's library.")
    parser.add_argument("--list", action="store_true", help="say what there would be, and write nothing")
    parser.add_argument("--only", default="", help="only families whose name contains this")
    parser.add_argument("--style", default="", help="only families of this style (warcraft, knight)")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    families = plan()
    def wanted(fam: Family) -> bool:
        return args.only in fam.name and args.style in ("", fam.character.style)

    jobs = [(index, take) for index, (fam, takes) in enumerate(families) for take in range(1, takes + 1) if wanted(fam)]
    if args.list:
        seconds = 0.0
        for fam, takes in families:
            if wanted(fam):
                seconds += fam.seconds * takes
                print("%-8s %-34s %-24s %-20s %5.0f %s  %3.0f s x %d  %s%s" % (
                    fam.character.style, fam.name, fam.title, fam.key.name, fam.bpm, fam.metre, fam.seconds, takes,
                    fam.character.role, " light" if fam.character.light else ""))
        print("%d families, %d tracks, %.0f minutes" % (len({index for index, _ in jobs}), len(jobs), seconds / 60.0))
        return 0
    todo = [(index, take) for index, take in jobs if not (folder_of(families[index][0], take) / "track.json").is_file()]
    print("%d tracks to write, %d already staged" % (len(todo), len(jobs) - len(todo)), flush=True)
    began, done = time.time(), 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        waiting = [pool.submit(_job, index, take) for index, take in todo]
        for finished in as_completed(waiting):
            made = finished.result()               # anything that went wrong stops the run and says why
            done += 1
            print("%4d/%d  %-34s take %d  %3d s  story %s" % (done, len(todo), made["family"], made["take"], made["seconds"],
                                                           " ".join("%.0f" % loud for loud in made["sections"])), flush=True)
    print("done in %.0f s" % (time.time() - began), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
