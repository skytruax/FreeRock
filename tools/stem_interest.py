"""How interesting each channel of a written take is on its own, since the game brings channels
in and out (the bass with a fight, the drums on a horse or in the rain, the bed down when one
stands still): for each channel, how many notes it plays to the bar, how many of its bars are
silent, how many different bars it has (the same notes in the same places counted once), how
many instruments take part, and for the bass how far its line moves from note to note and how
often it is on something other than the chord's root.

    cd app && uv run --no-sync python ../tools/stem_interest.py warcraft pastoral-morning-fields-1/1 ...
"""
from __future__ import annotations

import collections
import statistics
import sys

CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")


def interest(name: str, take: int) -> dict:
    from freerock.studio import build, orchestra
    fam = next(fam for fam, _ in build.plan() if fam.name == name)
    w = orchestra.Take(fam, take)
    beats = fam.beats
    total_bars = sum(section.bars for section in fam.sections)
    out = {}
    roots = {}
    at = 0.0
    for section, first, key, chords in w.spans:
        for bar, chord in enumerate(chords):
            roots[int(round((first + bar * beats) / beats))] = key.pitch(chord.root, 0) % 12
    for channel in CHANNELS:
        bars = collections.defaultdict(list)
        players = set()
        for tag, voice in w.voices[channel].items():
            if not voice.notes:
                continue
            players.add(voice.instrument)
            for note in voice.notes:
                bars[int(note.start // beats)].append((voice.instrument, round(note.start % beats, 2), note.pitch))
        heard = [b for b in range(total_bars) if bars.get(b)]
        patterns = collections.Counter(tuple(sorted(bars[b])) for b in heard)
        rhythms = collections.Counter(tuple(sorted({on for _, on, _ in bars[b]})) for b in heard)
        row = {"per_bar": sum(len(bars[b]) for b in heard) / max(len(heard), 1), "silent": 1 - len(heard) / total_bars,
               "different_bars": len(patterns) / max(len(heard), 1), "rhythms": len(rhythms), "players": len(players)}
        if channel == "bass":
            main = max(w.voices["bass"].values(), key=lambda v: len(v.notes))
            notes = sorted(main.notes, key=lambda n: n.start)
            moves = [abs(b.pitch - a.pitch) for a, b in zip(notes, notes[1:])]
            row["moves"] = statistics.mean(moves) if moves else 0.0
            row["still"] = sum(1 for m in moves if m == 0) / max(len(moves), 1)
            row["off_root"] = sum(1 for n in notes if roots.get(int(n.start // beats)) is not None and n.pitch % 12 != roots[int(n.start // beats)]) / max(len(notes), 1)
        out[channel] = row
    return out


def main(argv: list[str]) -> int:
    style, tracks = argv[0], argv[1:]
    sums = collections.defaultdict(list)
    for track in tracks:
        name, take = track.rsplit("/", 1)
        found = interest(name, int(take))
        print(track)
        for channel, row in found.items():
            extra = ""
            if "moves" in row:
                extra = " | moves %.1f st, repeated %.0f%%, off the root %.0f%%" % (row["moves"], 100 * row["still"], 100 * row["off_root"])
            print("   %-8s %5.1f notes/bar  silent %3.0f%%  different bars %3.0f%%  rhythms %3d  players %2d%s" % (
                channel, row["per_bar"], 100 * row["silent"], 100 * row["different_bars"], row["rhythms"], row["players"], extra))
            for key, value in row.items():
                sums[(channel, key)].append(value)
    print("\nacross the set:")
    for channel in CHANNELS:
        print("   %-8s %s" % (channel, "  ".join("%s %.2f" % (key, statistics.mean(values)) for (c, key), values in sums.items() if c == channel)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
