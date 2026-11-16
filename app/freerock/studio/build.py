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
from .orchestra import CHANNELS, CHARACTERS, INSTRUMENTS, Family, Take, family
from .score import humanise

VAR = Path(__file__).resolve().parents[3] / "var"
PROJECTS = VAR / "reaper" / "projects"       # every track's REAPER project is kept here, to be opened and changed by hand
MASTER = 20261115
# Where each channel sits when everyone is playing (LUFS at the moment, before the whole track
# is brought to the bucket's level): the tune on top, the pad and the accompaniment under it.
PLACE = {"lead": -17.0, "texture": -21.0, "rhythm": -21.5, "bass": -20.0, "drums": -23.0}       # an orchestra's drums are a few great strokes: by loudness they sit low
LIGHT = {"drums": -24.0, "bass": -21.5}        # a light track's drums and bass sit further back
WAR_DRUMS = -17.5                              # where the drums sit in a track that has war drums: up with the tune, the loudest strokes in the piece
BAND = {"lead": -17.0, "rhythm": -18.5, "drums": -18.0, "bass": -19.5, "texture": -24.0}       # a band: guitars and drums up front
BAND_LIGHT = {"drums": -21.0, "bass": -21.0, "rhythm": -20.0}
RIDE = 0.42                    # how far each part of the story is brought up towards the loudest part
# The least each channel is played at in each part of the story, so that the story is whole
# whatever the game is doing; the game then only adds weight to the drums and the bass.
# Under every stroke of the kick the other channels give way for a moment and come back within
# a quarter of a second: drawn into each channel's volume, the same at every stroke (how dance
# music makes room for its kick: a drawn curve, not a compressor that listens). How far each
# channel is turned down under the hardest stroke, as a part of its level.
DUCK = {"bass": 0.56, "texture": 0.8, "rhythm": 0.8, "lead": 0.9}
FLOOR = {"open": {"rhythm": 1.0, "bass": 0.85, "drums": 0.6}, "theme": {"rhythm": 1.0, "bass": 0.85, "drums": 0.55},
         "rise": {"rhythm": 1.0, "bass": 0.9, "drums": 0.75}, "moment": {"rhythm": 1.0, "bass": 1.0, "drums": 0.9},
         "close": {"rhythm": 1.0, "bass": 0.85, "drums": 0.55}}


def plan() -> list[tuple[Family, int]]:
    """Every family of the library and how many takes of it there are. A character that is
    for walking about gets a family of three takes (and the light ones a second family of
    two, since light places hear nothing else); the rarer moments get fewer."""
    out: list[tuple[Family, int]] = []
    titles: set[str] = set()
    for index, character in enumerate(CHARACTERS):
        if character.role == "wander":
            shapes = [3, 2] if character.light or character.band else [3]
        elif character.role in ("battle", "ember", "storm", "boss"):
            shapes = [2, 2]
        else:
            shapes = [2]
        for number, takes in enumerate(shapes):
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
    return out


def folder_of(fam: Family, take: int) -> Path:
    return stage_root(VAR, fam.character.style) / fam.name / str(take)


def project_of(fam: Family, take: int) -> Path:
    return PROJECTS / fam.character.style / fam.name / str(take) / "track.rpp"


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
            boom = KITS[voice.instrument[4:]][1]["boom"]
            strokes += [(note.start, note.loud) for note in voice.notes if note.pitch == boom]
        elif voice.instrument in ("war drums", "boom"):
            strokes += [(note.start, note.loud) for note in voice.notes if note.pitch == 36]
    for channel in CHANNELS:
        for name, voice in written.voices[channel].items():
            if voice.notes:
                humanise(voice, rng, timing=0.004 if channel == "drums" else 0.007, bpm=fam.bpm)
    if muse.available():
        # MuseScore performs every instrument it has, several at a time, before the project is put together.
        muse.prepare([(voice.instrument, voice.notes, fam.bpm) for channel in CHANNELS for voice in written.voices[channel].values()
                      if voice.notes and not voice.drums], seed=fam.seed * 31 + take)
    folders = []
    for channel in CHANNELS:
        under = []
        for name, voice in written.voices[channel].items():
            if not voice.notes:
                continue
            taste = INSTRUMENTS[voice.instrument].level if voice.instrument in INSTRUMENTS else 1.0
            under += sounds.lines(voice, name, fam.bpm, taste=taste, room=room, seed=fam.seed * 31 + take)
        if under:
            moves, last = [], -1.0
            for at, loud in sorted(strokes) if channel in DUCK else ():
                if loud < 0.45 or at <= last:
                    continue
                down = 1.0 - (1.0 - DUCK[channel]) * min(loud / 0.85, 1.0)
                beat_s = 60.0 / fam.bpm
                moves += [(at - 0.012 / beat_s, 1.0), (at, down), (at + 0.06 / beat_s, down), (at + 0.26 / beat_s, 1.0)]
                last = at + 0.26 / beat_s
            folders.append((desk.Line(channel, desk.bare(channel, []), effects=sounds.bus(channel), moves=moves), under))
    rpp = project_of(fam, take)
    work = rpp.parent
    work.mkdir(parents=True, exist_ok=True)
    rpp.write_text(desk.project(folders, bpm=fam.bpm, seconds=whole / RATE, out=work, tail=forever.POST_S,
                                hall=sounds.hall(character.hall[0])), encoding="utf-8")
    with reaper.Display() as display:
        desk.render(rpp, display=display, timeout=240.0 + 2.0 * whole / RATE)
    parts = desk.stems(work, [bus.name for bus, _ in folders], frames)
    for bus, _ in folders:
        (work / (bus.name + ".wav")).unlink()      # the staged track has them; the project can make them again
    # Each channel to its place in the mix, by how loud it is where everyone is playing.
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
            del parts[channel]                       # it plays nothing to speak of in this take
            continue
        gain = min(max(places[channel] - loud, -18.0), 18.0)
        parts[channel] = audio * np.float32(10 ** (gain / 20.0))
        levels[channel] = round(loud + gain, 1)
        gains[channel] = round(gain, 1)
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
    curve = (10.0 ** (ride / 20.0)).astype(np.float32)[:, None]
    parts = {channel: audio * curve for channel, audio in parts.items()}
    mix = mix * curve
    peak = max(float(np.abs(mix).max()), max(float(np.abs(audio).max()) for audio in parts.values()))
    scale = np.float32(0.6 / peak)
    parts = {channel: audio * scale for channel, audio in parts.items()}
    mix = mix * scale
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
        "serves": list(character.serves), "light": character.light, "sections": sections, "floor": FLOOR,
        "follow": {"rhythm": ["lead"], "texture": ["lead"]}, "post_s": forever.POST_S,
        "credit": "Written by FreeRock's studio (%s, %s); played in REAPER by the sfizz sampler on the VSCO 2 Community "
                  "Edition and VCSL recordings (Versilian Studios, CC0), the TinySOL recordings (Cella, Ghisi, Lostanlen, Levy, "
                  "Fineberg and Maresz, IRCAM, CC BY 4.0) and Big Rusty Drums (Karoryfer, CC0), by the AVL drum kits (Glen "
                  "MacArthur, CC BY-SA 3.0) and by the Surge XT and ZynAddSubFX synths" % (character.name, fam.metre),
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
