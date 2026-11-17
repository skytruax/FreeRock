"""Studies a set of staged tracks the way the night's passes need: for each, how far its story
travels in loudness (quiet parts against loud ones), how its channels sit against the stems
that were liked (studio/ear.py), and from what was written how many instruments play at once in
each part of the story, how much of the tune is a bar heard before, and how wide the music
spreads from the bass to the top. One line per track, then what stands out across the set.

    cd app && uv run --no-sync python ../tools/study.py warcraft pastoral-morning-fields-1/1 haunted-shadowed-wood-1/1 ...
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np
import soundfile

from freerock import analysis
from freerock.studio import ear

VAR = Path(__file__).resolve().parents[1] / "var"
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")


def stems(style: str, name: str, take: str) -> tuple[dict, dict[str, np.ndarray], int]:
    folder = VAR / "studio" / style / name / take
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    parts, rate = {}, 48000
    for channel in CHANNELS:
        for suffix in (".flac", ".mp3"):
            if (folder / (channel + suffix)).is_file():
                parts[channel], rate = soundfile.read(str(folder / (channel + suffix)), dtype="float32", always_2d=True)
                break
    return meta, parts, rate


def story_loudness(meta: dict, parts: dict[str, np.ndarray], rate: int) -> list[tuple[str, float]]:
    mix = sum(parts.values())
    out, at = [], 0
    for section in meta["sections"]:
        frames = int(round(section["bars"] * meta["bar_frames"]))
        out.append((section["story"], analysis.loudness_lufs(mix[at:at + frames], rate)))
        at += frames
    return out


def written(style: str, name: str, take: int) -> dict:
    """From the writer: instruments at once in each part, the tune's repeated bars, the spread of registers."""
    if style == "house":
        return {}
    from freerock.studio import build, orchestra
    fam = next(fam for fam, _ in build.plan() if fam.name == name)
    w = orchestra.Take(fam, take)
    beats = fam.beats
    at, out = 0.0, {"at_once": [], "spread": []}
    lead_bars: list[tuple] = []
    for section in fam.sections:
        span = (at, at + section.bars * beats)
        playing = collections.Counter()
        low, high = 127, 0
        for channel in orchestra.CHANNELS:
            for tag, voice in w.voices[channel].items():
                inside = [note for note in voice.notes if span[0] <= note.start < span[1]]
                if not inside:
                    continue
                playing[channel] += 1
                if not voice.drums:
                    low, high = min(low, min(n.pitch for n in inside)), max(high, max(n.pitch for n in inside))
        out["at_once"].append((section.part, sum(playing.values())))
        out["spread"].append((section.part, (high - low) if high >= low else 0))
        at = span[1]
    # How much of the tune is a bar heard before (the same notes in the same places, wherever it stands).
    for tag, voice in w.voices["lead"].items():
        bars = collections.defaultdict(list)
        for note in voice.notes:
            bars[int(note.start // beats)].append((round(note.start % beats, 3), note.pitch))
        lead_bars += [tuple(sorted(notes)) for notes in bars.values()]
    counts = collections.Counter(lead_bars)
    out["tune_repeats"] = 1.0 - len(counts) / max(len(lead_bars), 1)
    return out


def main(argv: list[str]) -> int:
    style, tracks = argv[0], argv[1:]
    rows = []
    for track in tracks:
        name, take = track.rsplit("/", 1)
        try:
            meta, parts, rate = stems(style, name, take)
        except FileNotFoundError:
            print("%-34s not staged" % track)
            continue
        story = story_loudness(meta, parts, rate)
        loud = [value for _, value in story if value > -70]
        swing = max(loud) - min(loud) if loud else 0.0
        notes = written(style, name, int(take))
        off = {}
        for channel, audio in parts.items():
            mine = ear.profile(audio, rate)
            try:
                wanted = ear.reference("", style=style, channel=channel)
            except KeyError:
                continue
            if mine is not None:
                gaps = [mine.bands[at] - wanted.bands[at] for at in range(len(ear.CENTRES))]
                off[channel] = (round(float(np.mean(gaps[3:6])), 1), round(float(np.mean(gaps[7:9])), 1))     # mids, top
        rows.append((track, meta["title"], swing, story, notes, off))
        print("%-34s %-26s story %s | swing %4.1f dB" % (track, meta["title"][:26], " ".join("%s %.0f" % (s[:4], v) for s, v in story), swing))
        if notes:
            print("%-34s at once: %s | spread: %s | tune bars heard before: %.0f%%" % (
                "", " ".join("%s %d" % (p[:4], n) for p, n in notes["at_once"]), " ".join("%d" % s for _, s in notes["spread"]), 100 * notes["tune_repeats"]))
        if off:
            print("%-34s against the liked stems (mids dB, top dB): %s" % ("", "  ".join("%s %+.1f %+.1f" % (c, m, t) for c, (m, t) in off.items())))
    if rows:
        print("\nacross the set: story swing %.1f dB on average (least %.1f); tune bars heard before %.0f%% on average" % (
            float(np.mean([r[2] for r in rows])), min(r[2] for r in rows),
            100 * float(np.mean([r[4].get("tune_repeats", 0) for r in rows if r[4]] or [0]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
