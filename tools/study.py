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


# How much of a liked song's tune comes back: the share of its lead's two-bar phrases that are played more than once, the lower quartile
# of the library as it stood on the evening of 2026-11-24, the last one that was liked (Knight Rock's middle 49%, Warcraft's 35). A song
# under it has a tune that hardly returns. (2026-11-26, after "the new bands a lot of time just sound random": the one number the study had
# of a tune, its bars heard before, was read one way only, a high one as a fault, 55% and over; a rule was written to bring it down, and
# three in four of the songs that rule made lie under 38% here, where nine in ten of the liked ones lie over 40.) House's leads are hooks,
# nearly all of them heard again (92% in the middle of its own songs): no floor is set for it yet.
RETURNS_FLOOR = {"knight": 0.44, "warcraft": 0.27}


def returns(by_bar: dict[int, set]) -> float | None:
    """The share of a tune's two-bar phrases that are played more than once (bars 0-1, 2-3, ...; a phrase with nothing in it is none):
    how much of it comes back, note for note. None for a tune of fewer than two phrases."""
    if not by_bar:
        return None
    mark = lambda bar: tuple(sorted(by_bar.get(bar, ())))      # noqa: E731
    phrases = [(mark(bar), mark(bar + 1)) for bar in range(0, max(by_bar) + 1, 2)]
    phrases = [phrase for phrase in phrases if any(phrase)]
    if len(phrases) < 2:
        return None
    counts = collections.Counter(phrases)
    return sum(1 for phrase in phrases if counts[phrase] > 1) / len(phrases)


# How much of the tune a listener knows again (2026-11-27, round sixteen's old songs). The count above was blind: Drowned Ruins read 10%,
# "stated, then abandoned", while its choir sings the English horn's theme note for note at the arrival, its cello plays its answer again in
# the valley and its summit is all of it lifted a minor third — told again on other voices, together with others, in another key, and so
# never the same phrases of every lead voice at the same pitch; the judges give it memorability 3.01 where Warcraft's bar is 2.65. Counted by
# each voice's phrase shape instead, over the gate's library (the whole takes the judges' watch read, 121 Knight Rock songs and 63 Warcraft),
# and over the songs the retelling rule of 11-24 made before it was turned down (66 and 91, studio-demo/retold-audit-1126): with a quarter of
# the liked under the floor either way, the old count caught 56 of the 66 retold Knight Rock songs and 35 of the 91 Warcraft, this one 63 and
# all 91. So it hears a tune told another way each time at least as well as the old one did, and does not take a tune told again on other
# voices for one that never came back. The lower quartiles of the liked: 68% for Knight Rock (the middle 72), 83 for Warcraft (the middle 88).
# (The same night, later: over every take the judges have read whose sheet is staged, 231 Knight Rock and 268 Warcraft, this goes with SongEval's
# memorability by r = +0.07 and +0.04, and the middle memorability under the floor and over it is 3.06 against 3.10, and 2.92 against 2.94. It
# tells the fault it was made against, a tune told another way each time, and nothing more: it is no reason on its own to revise a song.
# Split by the characters' `light`, the liked library's quartiles are alike (Knight Rock 70 light and 67 full, Warcraft 82 and 84): one floor.)
HEARD_FLOOR = {"knight": 0.68, "warcraft": 0.83}
SHAPE_NOTES = 3            # a phrase of fewer notes than this has no shape to be known again by


def heard(lead: list, beats: float) -> float | None:
    """The share of the tune's two-bar spans in which some lead voice plays a phrase whose shape — where its notes fall in the two bars
    and how far each lies from its first — is played in another span too, by any lead voice at any pitch: the tune told again as a
    listener knows it, on another instrument, an octave or a lift away, or under a second line. The same phrase in two voices at once
    is not a return. A phrase of fewer than SHAPE_NOTES notes is left out of both sides of the share, and a span where no voice has one
    is not counted. None for a tune of fewer than two such spans."""
    where: dict[tuple, set] = collections.defaultdict(set)
    spans_shapes: dict[int, list] = collections.defaultdict(list)
    for voice in lead:
        spans: dict[int, set] = collections.defaultdict(set)
        for note in voice.notes:
            at = round(note.start * 12.0) / 12.0
            span = int((at + 1e-6) // (2 * beats))
            spans[span].add((round((at - span * 2 * beats) * 12), note.pitch))
        for span, notes in spans.items():
            if len(notes) < SHAPE_NOTES:
                continue
            notes = sorted(notes)
            shape = tuple((onset, pitch - notes[0][1]) for onset, pitch in notes)
            where[shape].add(span)
            spans_shapes[span].append(shape)
    if len(spans_shapes) < 2:
        return None
    return sum(1 for span, shapes in spans_shapes.items() if any(where[shape] - {span} for shape in shapes)) / len(spans_shapes)


def written(style: str, name: str, take: int) -> dict:
    """From the take's music sheet: instruments at once in each part, the tune's repeated bars, the spread of registers.

    The staged sheet is read, not the writer asked again (2026-11-25: Keg Clamour, retold the night before to 51% of its
    tune's bars heard before, was still read at the first draft's 69 and marked for a revision it had had: a revised sheet
    is what the song is). A take with no sheet (staged before the sheets were) is written again, as it was."""
    if style == "house":
        return {}
    from freerock.studio import sheet as sheets
    from freerock.studio.score import Sheet
    path = sheets.path_of("%s/%s/%d" % (style, name, take))
    if path.is_file():
        sheet = Sheet.load(path)
        beats = float(sheet.beats)
        spans = [(part["part"], part["first"] * beats, (part["first"] + part["bars"]) * beats) for part in sheet.form]
        # (What the desk stacks on a moment, a kick under the kit's, a sub under the bass, a bell, doubles what is there: it is not one more playing.)
        voices = {channel: [(voice, channel == "drums" or voice.drums) for tag, voice in sheet.parts.get(channel, {}).items() if not tag.endswith(" at the moments")]
                  for channel in CHANNELS}
    else:
        from freerock.studio import build, orchestra
        fam = next(fam for fam, _ in build.plan() if fam.name == name)
        w = orchestra.Take(fam, take)
        beats = fam.beats
        spans, at = [], 0.0
        for section in fam.sections:
            spans.append((section.part, at, at + section.bars * beats))
            at += section.bars * beats
        voices = {channel: [(voice, voice.drums) for voice in w.voices[channel].values()] for channel in orchestra.CHANNELS}
    out = {"at_once": [], "spread": []}
    lead_bars: list[bool] = []
    for part, first, last in spans:
        playing = collections.Counter()
        low, high = 127, 0
        for channel, each in voices.items():
            for voice, drums in each:
                inside = [note for note in voice.notes if first <= note.start < last]
                if not inside:
                    continue
                playing[channel] += 1
                if not drums:
                    low, high = min(low, min(n.pitch for n in inside)), max(high, max(n.pitch for n in inside))
        out["at_once"].append((part, sum(playing.values())))
        out["spread"].append((part, (high - low) if high >= low else 0))
    # How much of the tune is a bar heard before: through time, each bar of the lead channel (all its voices together)
    # against every bar before it. (Until 2026-11-17 every voice's bars were pooled, so a tune doubled by a second
    # instrument counted as half heard before: 58 to 80% where through time it is 28 to 54%.)
    # (A staged sheet's notes are where the player put them, a little off the line: each is heard at the nearest twelfth of a beat,
    # as a revision's own count is, tools' recipes.)
    by_bar = collections.defaultdict(set)
    for voice, _ in voices.get("lead", []):
        for note in voice.notes:
            at = round(note.start * 12.0) / 12.0
            by_bar[int((at + 1e-6) // beats)].add((round((at % beats) * 12), note.pitch))
    seen: set = set()
    for bar in sorted(by_bar):
        signature = tuple(sorted(by_bar[bar]))
        lead_bars.append(signature in seen)
        seen.add(signature)
    out["tune_repeats"] = sum(lead_bars) / max(len(lead_bars), 1)
    out["tune_returns"] = returns(by_bar)
    out["tune_heard"] = heard([voice for voice, _ in voices.get("lead", [])], beats)
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
        off, unheld = {}, []
        for channel, audio in parts.items():
            mine = ear.profile(audio, rate)
            try:
                wanted = ear.reference("", style=style, channel=channel)
            except KeyError:
                unheld.append(channel)          # no liked stems of this style and channel: said below, not passed over
                continue
            if mine is not None:
                gaps = [mine.bands[at] - wanted.bands[at] for at in range(len(ear.CENTRES))]
                off[channel] = (round(float(np.mean(gaps[3:6])), 1), round(float(np.mean(gaps[7:9])), 1))     # mids, top
        rows.append((track, meta["title"], swing, story, notes, off))
        print("%-34s %-26s story %s | swing %4.1f dB" % (track, meta["title"][:26], " ".join("%s %.0f" % (s[:4], v) for s, v in story), swing))
        if notes:
            print("%-34s at once: %s | spread: %s | tune bars heard before: %.0f%%" % (
                "", " ".join("%s %d" % (p[:4], n) for p, n in notes["at_once"]), " ".join("%d" % s for _, s in notes["spread"]), 100 * notes["tune_repeats"]))
            # (2026-11-27: UNDER is said of the tune heard again, by shape; the count of phrases played again note for note, every lead voice
            # together, is still printed beside it with its own quartile, and marks nothing: it was blind to a tune told again on other voices.)
            known, floor = notes.get("tune_heard"), HEARD_FLOOR.get(style)
            if known is not None:
                print("%-34s the tune heard again (any voice, any pitch): %.0f%%%s" % ("", 100 * known, "" if floor is None else (
                    "  UNDER the liked library's lower quartile (%.0f%%): a tune told another way each time, or one told once; it predicts nothing of the"
                    " judges' memorability, so look by ear and at their reading before any revision" % (100 * floor)
                    if known < floor else "  (the liked library's lower quartile %.0f%%)" % (100 * floor))))
            back, floor = notes.get("tune_returns"), RETURNS_FLOOR.get(style)
            if back is not None:
                print("%-34s the tune's phrases played again note for note, every lead voice together: %.0f%%%s" % ("", 100 * back, "" if floor is None else
                    "  (the liked library's lower quartile %.0f%%)" % (100 * floor)))
        if off:
            print("%-34s against the liked stems (mids dB, top dB): %s" % ("", "  ".join("%s %+.1f %+.1f" % (c, m, t) for c, (m, t) in off.items())))
        if unheld:
            print("%-34s NOT held against the liked stems (there are none of %s's): %s" % ("", style, ", ".join(unheld)))
    if rows:
        # (2026-11-27: House's ten old songs read "tune bars heard before 0% on average", which was the mean of nothing — written() gives House no
        # notes at all. A measurement that does not apply says so; it does not print a nought that a reader would act on.)
        told = [r[4]["tune_repeats"] for r in rows if r[4] and "tune_repeats" in r[4]]
        print("\nacross the set: story swing %.1f dB on average (least %.1f); %s" % (
            float(np.mean([r[2] for r in rows])), min(r[2] for r in rows),
            ("tune bars heard before %.0f%% on average, over %d of the %d" % (100 * float(np.mean(told)), len(told), len(rows))) if told
            else "what is written was not read for any of them (study.py reads no notes for %s): the tune is not measured here" % style))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
