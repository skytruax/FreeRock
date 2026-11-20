"""The boredom meter: how long each channel of a take goes on sounding the same (2026-11-18: "some of the instruments get
boring figure out how to get more especially in house", "put that in the recursive loop").

Each bar of each channel's stem gets a fingerprint: its shape across the octaves (the share of its sound in each, in
dB), its brightness and its loudness. A bar that differs from the one where its stretch began by less than a little
(`--still`, in dB on average over the octaves and twice as much in any one that is sounding, and its loudness
within as much) carries the stretch on; the longest
such stretch is what the ear hears as a part that never moves. Silence is not a stretch. A stretch at the take's
sheet (sheet.json, where there is one) is also checked for its notes: a part whose bars are the same notes all
through is marked as such, since then nothing at all is changing. Something should change in every channel at least
every 8 or 16 bars (the plan): a stretch of 16 bars or more is flagged.

    cd app && uv run --no-sync python ../tools/boredom.py house/coast-03/1 knight/infernal-forge-anthem-1/3 ...
    ... --folder <a staged take's folder>      (a take staged somewhere else, a demo's)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile

VAR = Path(__file__).resolve().parents[1] / "var"
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
EDGES = (40, 80, 160, 320, 640, 1250, 2500, 5000, 10000, 20000)
FLAG = 16          # bars: a stretch this long or longer that does not change is flagged


def fingerprints(audio: np.ndarray, rate: int, bar_frames: float, bars: int) -> list[tuple[np.ndarray, float] | None]:
    """Each bar's shape across the octaves (dB, its total taken away) and its loudness (dB); None where it is silent."""
    mono = audio.mean(axis=1)
    out: list[tuple[np.ndarray, float] | None] = []
    size = 4096
    freqs = np.fft.rfftfreq(size, 1.0 / rate)
    bands = [(freqs >= low) & (freqs < high) for low, high in zip(EDGES, EDGES[1:])]
    window = np.hanning(size)
    for bar in range(bars):
        piece = mono[int(round(bar * bar_frames)):int(round((bar + 1) * bar_frames))]
        loud = 10 * np.log10(float(np.mean(piece ** 2)) + 1e-20) if len(piece) else -200.0
        if loud < -60.0 or len(piece) < size:
            out.append(None)
            continue
        spectrum = sum(np.abs(np.fft.rfft(piece[start:start + size] * window)) ** 2 for start in range(0, len(piece) - size, size // 2))
        energy = np.array([spectrum[band].sum() for band in bands]) + 1e-20
        shape = 10 * np.log10(energy / energy.sum())
        # ...and its rhythm: where in the bar's sixteen steps its top (over 4 kHz) strikes, a groove's figure.
        step = len(piece) // 16
        top = []
        for index in range(16):
            slice_ = piece[index * step:(index + 1) * step]
            spec = np.abs(np.fft.rfft(slice_)) ** 2
            top.append(float(spec[int(4000 * len(slice_) / rate):].sum()))
        top = np.array(top) + 1e-20
        out.append((np.maximum(shape, -60.0), loud, top / top.sum()))
    return out


def timbres(audio: np.ndarray, rate: int, bar_frames: float, bars: int) -> list[tuple[np.ndarray, float] | None]:
    """Each bar's colour apart from its notes: the cepstrum of its spectrum on a mel scale (coefficients 1 to 12, the
    envelope a voice's colour makes, which hardly moves when only the pitch does), as (vector, loudness)."""
    mono = audio.mean(axis=1)
    size = 4096
    freqs = np.fft.rfftfreq(size, 1.0 / rate)
    mel = lambda hz: 2595.0 * np.log10(1.0 + hz / 700.0)          # noqa: E731
    points = np.linspace(mel(60.0), mel(12000.0), 34)
    hz = 700.0 * (10 ** (points / 2595.0) - 1.0)
    bank = np.zeros((32, len(freqs)))
    for index in range(32):
        low, mid, high = hz[index], hz[index + 1], hz[index + 2]
        bank[index] = np.clip(np.minimum((freqs - low) / (mid - low), (high - freqs) / (high - mid)), 0.0, None)
    basis = np.cos(np.pi / 32 * (np.arange(32) + 0.5)[None, :] * np.arange(13)[:, None])
    window = np.hanning(size)
    out: list[tuple[np.ndarray, float] | None] = []
    for bar in range(bars):
        piece = mono[int(round(bar * bar_frames)):int(round((bar + 1) * bar_frames))]
        loud = 10 * np.log10(float(np.mean(piece ** 2)) + 1e-20) if len(piece) else -200.0
        if loud < -60.0 or len(piece) < size:
            out.append(None)
            continue
        spectrum = sum(np.abs(np.fft.rfft(piece[start:start + size] * window)) ** 2 for start in range(0, len(piece) - size, size // 2))
        cepstrum = basis @ (10 * np.log10(bank @ spectrum + 1e-20))
        # The top's share of the bar, in dB (2026-11-19: the drummer's turn from the hat to the ride or the open hat, under a
        # kick on every beat, hardly moves the cepstrum, which follows the whole spectrum's tilt; King's Oath's and House's
        # drums read one colour 30 to 68 bars across turns the ear hears).
        top = 10 * np.log10(float(spectrum[freqs >= 4000.0].sum()) / (float(spectrum.sum()) + 1e-20) + 1e-20)
        # ...and the air in that top: its share over 16 kHz, in dB (2026-11-20: the kit's closed hat, its open hat and its
        # ride sit within 1 dB in the top's share, but a closed hat's top keeps a fifth to a hundredth of itself over 16 kHz,
        # an open hat's a thousandth, a ride's a three-thousandth: Downpour Run's turn from the hat to the ride is 13 to 15 dB
        # here, one cymbal's bars within 2 to 6 dB of each other).
        air = 10 * np.log10(float(spectrum[freqs >= 16000.0].sum()) / (float(spectrum[freqs >= 4000.0].sum()) + 1e-20) + 1e-20)
        out.append((cepstrum[1:13] / 32.0, loud, None, top, air))
    return out


def stretches(prints: list[tuple[np.ndarray, float] | None], still: float) -> list[tuple[int, int]]:
    """(first bar, bars) of each stretch in which nothing moves by more than `still` dB from where it began."""
    found = []
    start = None
    for bar, here in enumerate(prints + [None]):
        if here is None:
            if start is not None:
                found.append((start, bar - start))
            start = None
            continue
        if start is None:
            start = bar
            continue
        shape, loud = prints[start][0], prints[start][1]
        # Moved: on average over the octaves, or in any one octave that is sounding (within 30 dB of the loudest) by
        # twice as much, since a part's top may change while its bottom, far louder, stays (the hats over the kick).
        sounding = np.maximum(here[0], shape) > max(here[0].max(), shape.max()) - 30.0
        moved = float(np.sqrt(np.mean((here[0] - shape) ** 2)))
        most = float(np.max(np.abs(here[0] - shape)[sounding])) if sounding.any() else 0.0
        figure = 0.0
        if len(here) > 2 and len(prints[start]) > 2 and here[2] is not None and prints[start][2] is not None:
            a, b = here[2], prints[start][2]
            figure = 1.0 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-20))
        top = abs(here[3] - prints[start][3]) if len(here) > 3 and len(prints[start]) > 3 else 0.0
        air = abs(here[4] - prints[start][4]) if len(here) > 4 and len(prints[start]) > 4 else 0.0
        if moved > still or most > 2.0 * still or abs(here[1] - loud) > still or figure > 0.1 or top > 2.0 * still \
                or air > 4.0 * still:
            found.append((start, bar - start))
            start = bar
    return found


def same_notes(sheet: dict, channel: str, first: int, bars: int) -> bool:
    """Whether every part of a channel plays the same notes in every bar of a stretch (on the take's sheet)."""
    beats = float(sheet["beats"])
    parts = sheet["parts"].get(channel, {})
    seen = set()
    for bar in range(first, first + bars):
        a, b = bar * beats, (bar + 1) * beats
        key = []
        for name in sorted(parts):
            notes = [(round(start - a, 2), pitch) for start, _, pitch, _ in parts[name]["notes"] if a <= start < b]
            key.append((name, tuple(sorted(notes))))
        seen.add(hashlib.sha1(repr(key).encode()).hexdigest())
    return len(seen) == 1


def meter(folder: Path, still: float) -> dict:
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    bars = sum(section["bars"] for section in meta["sections"])
    story = []
    for section in meta["sections"]:
        story += [section["story"]] * section["bars"]
    sheet = json.loads((folder / "sheet.json").read_text(encoding="utf-8")) if (folder / "sheet.json").is_file() else None
    found = {}
    for channel in CHANNELS:
        path = folder / (channel + ".flac")
        if not path.is_file():
            continue
        audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
        runs = stretches(fingerprints(audio, rate, meta["bar_frames"], bars), still)
        colour = stretches(timbres(audio, rate, meta["bar_frames"], bars), still)
        same_colour = max(colour, key=lambda run: run[1]) if colour else (0, 0)
        playing = sum(count for _, count in runs)
        longest = max(runs, key=lambda run: run[1]) if runs else (0, 0)
        long_ones = [run for run in runs if run[1] >= FLAG]
        found[channel] = {
            "longest": longest, "where": story[longest[0]] if longest[1] else "",
            "long": long_ones, "share": sum(count for _, count in long_ones) / max(playing, 1),
            "same notes": bool(sheet) and longest[1] >= 4 and same_notes(sheet, channel, *longest),
            "colour": same_colour, "colour where": story[same_colour[0]] if same_colour[1] else "",
        }
    return {"title": meta.get("title", folder.name), "bars": bars, "channels": found}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="How long each channel of a take goes on sounding the same.")
    parser.add_argument("takes", nargs="*", help='staged takes: "house/coast-03/1"')
    parser.add_argument("--folder", action="append", default=[], help="a staged take's folder, anywhere")
    parser.add_argument("--still", type=float, default=1.5, help="dB: what counts as not having moved (default 1.5)")
    args = parser.parse_args(argv)
    folders = [VAR / "studio" / take for take in args.takes] + [Path(folder) for folder in args.folder]
    if not folders:
        parser.print_help()
        return 2
    for folder in folders:
        report = meter(folder, args.still)
        print("%s (%s), %d bars" % (report["title"], folder, report["bars"]))
        for channel, found in report["channels"].items():
            first, count = found["longest"]
            flag = "  <-- the same for %d bars" % count if count >= FLAG else ""
            c_first, c_count = found["colour"]
            print("   %-8s unchanged: %3d bars from bar %3d (%s)%s; its colour unchanged %3d bars from bar %3d (%s)%s%s"
                  % (channel, count, first, found["where"], ", the same notes all through" if found["same notes"] else "",
                     c_count, c_first, found["colour where"], "  <-- the same colour" if c_count >= FLAG else "", flag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
