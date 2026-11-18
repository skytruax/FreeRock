"""The studio's ear: what a recording sounds like, in numbers.

The studio cannot hear. What it can do is what a mixing engineer does with a record they
trust: lay the two side by side and compare. `profile` measures a recording: how its power is
spread over the octaves (dull, boomy, thin, harsh), how hard its notes start, how far its peaks
stand above its body, how even its level is, how wide it is, how long it rings. `reference`
gives the same numbers for recordings that were listened to and liked, each labelled with its
instrument, measured once and kept in var/reaper/ear.json (the recordings themselves are gone), so an instrument of the studio's can be held against the same
instrument there. `differs` says where two profiles part, and `top` turns
the difference in their tops into settings for the channel equaliser.

    uv run --no-sync python -m freerock.studio.ear "violins in" path/to/mine.flac
    uv run --no-sync python -m freerock.studio.ear --list            the instruments there are references for

The numbers are no judge of whether an instrument sounds real. They do catch the faults that
make a mix sound cheap whatever is in it: no top, a boom nobody can hear but every loudspeaker
has to carry, peaks with no body under them, a bass that is not there.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile
from scipy import signal

VAR = Path(__file__).resolve().parents[3] / "var"
KEPT = VAR / "reaper" / "ear.json"            # the references' profiles: all there is of them now
EDGES = (20, 40, 80, 160, 320, 640, 1250, 2500, 5000, 10000, 20000)      # the octaves, in Hz
CENTRES = tuple(float(np.sqrt(low * high)) for low, high in zip(EDGES, EDGES[1:]))


@dataclass
class Profile:
    """A recording in numbers. `bands` is each octave's share of the power in dB (EDGES);
    `side` how much of each octave differs between left and right, in dB against what is the
    same (0 is as much, -20 nearly mono); `crest` how far the highest peak stands above the
    average level, in dB (a dense, produced sound has 12 to 18, a bare recording of single
    strokes 25); `rise` how fast the loud starts are, in dB per 10 ms; `spread` how far the
    level wanders between its loud and its quiet stretches, in dB; `rings` how many seconds a
    sound left alone takes to fall away by 60 dB; `centre` where the weight of the spectrum
    lies, in Hz; `count` how many recordings it is the average of."""
    bands: list[float]
    side: list[float]
    crest: float
    rise: float
    spread: float
    rings: float
    centre: float
    count: int = 1

    def __str__(self) -> str:
        return ("bands " + " ".join("%6.1f" % each for each in self.bands) + "   crest %4.1f  rise %4.1f  spread %4.1f  rings %4.1f s  centre %5.0f Hz"
                % (self.crest, self.rise, self.spread, self.rings, self.centre))


def _rings(level: np.ndarray, hop: float) -> float:
    """How long a sound left alone takes to fall 60 dB, from the stretches where the level
    falls steadily: the middle one of the falls from 5 dB down to 25 dB down, times three."""
    falls = []
    top = level.max()
    at = 0
    while at < len(level) - 4:
        if level[at] < top - 25.0 or level[at + 1] >= level[at]:
            at += 1
            continue
        start, peak = at, level[at]
        five = twenty_five = None
        while at < len(level) - 1 and level[at + 1] <= level[at] + 1.5:        # falling, give or take a wobble
            at += 1
            if five is None and level[at] <= peak - 5.0:
                five = at
            if level[at] <= peak - 25.0:
                twenty_five = at
                break
        if five is not None and twenty_five is not None and twenty_five > five:
            falls.append((twenty_five - five) * hop * 3.0)
        at = max(at, start + 1)
    return float(np.median(falls)) if falls else 0.0


def profile(audio: np.ndarray, rate: int) -> Profile | None:
    """The numbers for one recording (frames by channels), or None if it is silent."""
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    audio = audio.astype(np.float64)
    mid, side = (audio[:, 0] + audio[:, 1]) / 2.0, (audio[:, 0] - audio[:, 1]) / 2.0
    frame = int(rate * 0.4)
    count = len(mid) // frame
    if not count:
        return None
    power = np.array([np.mean(mid[at * frame:(at + 1) * frame] ** 2) + np.mean(side[at * frame:(at + 1) * frame] ** 2) for at in range(count)])
    if power.max() <= 1e-12:
        return None
    live = power > power.max() * 1e-4                   # only where something is playing
    keep = np.concatenate([np.arange(at * frame, (at + 1) * frame) for at in range(count) if live[at]])
    played_mid, played_side = mid[keep], side[keep]
    piece = min(8192, len(played_mid))
    hz, in_mid = signal.welch(played_mid, rate, nperseg=piece)
    _, in_side = signal.welch(played_side, rate, nperseg=piece)
    whole = np.trapezoid(in_mid + in_side, hz)
    bands, wide = [], []
    for low, high in zip(EDGES, EDGES[1:]):
        pick = (hz >= low) & (hz < high)
        bands.append(10 * np.log10(np.trapezoid(in_mid[pick] + in_side[pick], hz[pick]) / whole + 1e-12))
        wide.append(10 * np.log10((np.trapezoid(in_side[pick], hz[pick]) + 1e-15) / (np.trapezoid(in_mid[pick], hz[pick]) + 1e-15)))
    body = np.sqrt(np.mean(played_mid ** 2 + played_side ** 2))
    hop = int(rate * 0.005)
    level = 10 * np.log10(np.convolve(mid ** 2 + side ** 2, np.ones(hop) / hop, mode="same")[::hop] + 1e-12)
    rise = level[2:] - level[:-2]
    loud = level[2:] > level.max() - 30.0
    short = 10 * np.log10(power[live] + 1e-12)
    return Profile(
        bands=[round(float(each), 2) for each in bands], side=[round(float(each), 2) for each in wide],
        crest=round(float(20 * np.log10(np.abs(audio).max() / body)), 2),
        rise=round(float(np.percentile(rise[loud], 95)) if loud.any() else 0.0, 2),
        spread=round(float(np.percentile(short, 95) - np.percentile(short, 10)), 2),
        rings=round(_rings(level, hop / rate), 2),
        centre=round(float(np.sum(hz * (in_mid + in_side)) / np.sum(in_mid + in_side)), 1))


def of(path: Path | str) -> Profile:
    audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    found = profile(audio, rate)
    if found is None:
        raise ValueError("%s is silent" % path)
    return found


def mean(profiles: list[Profile]) -> Profile:
    if not profiles:
        raise ValueError("There is nothing to take the average of")
    def middle(pick) -> float:
        return round(float(np.mean([pick(each) for each in profiles])), 2)
    return Profile(bands=[middle(lambda each, at=at: each.bands[at]) for at in range(len(CENTRES))],
                   side=[middle(lambda each, at=at: each.side[at]) for at in range(len(CENTRES))],
                   crest=middle(lambda each: each.crest), rise=middle(lambda each: each.rise), spread=middle(lambda each: each.spread),
                   rings=middle(lambda each: each.rings), centre=middle(lambda each: each.centre), count=len(profiles))


_kept: dict[str, dict] | None = None


def _references() -> dict[str, dict]:
    """Every reference stem's profile with what it was asked for: file -> {style, channel,
    strength, asked, profile}. The stems were measured once and are gone (the drive was cleared on
    2026-11-16, night), so this table is the whole of them: nothing is ever added to it, and the
    studio's own recordings must never be."""
    global _kept
    if _kept is None:
        if not KEPT.is_file():
            raise FileNotFoundError("The liked stems' profiles (%s) are missing, and the stems they were measured from are "
                                    "gone: put the file back from a copy" % KEPT)
        _kept = json.loads(KEPT.read_text(encoding="utf-8"))
    return _kept


def reference(asked: str, *, style: str = "warcraft", channel: str = "", strength: str = "") -> Profile:
    """The average of the reference stems of a style whose instrument (what they were asked
    for) begins with `asked`, of one channel and strength if those are given."""
    found = [Profile(**each["profile"]) for each in _references().values()
             if each["style"] == style and each["asked"].startswith(asked) and channel in ("", each["channel"]) and strength in ("", each["strength"])]
    if not found:
        raise KeyError("No reference stem of the %s style was asked for %r" % (style, asked))
    return mean(found)


def asked_for(style: str = "warcraft") -> dict[str, int]:
    """What the reference stems of a style were asked for, and how many of each there are."""
    out: dict[str, int] = {}
    for each in _references().values():
        if each["style"] == style:
            key = "%s: %s" % (each["channel"], each["asked"])
            out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def differs(mine: Profile, wanted: Profile) -> str:
    """Where a recording parts from what is wanted, to read: each octave's difference in dB
    (plus is more than wanted) and the other numbers side by side."""
    gaps = [mine.bands[at] - wanted.bands[at] for at in range(len(CENTRES))]
    return ("octaves " + " ".join("%+6.1f" % gap for gap in gaps)
            + "   crest %4.1f (%4.1f)  rise %3.1f (%3.1f)  spread %4.1f (%4.1f)  rings %3.1f (%3.1f)  centre %4.0f (%4.0f)"
            % (mine.crest, wanted.crest, mine.rise, wanted.rise, mine.spread, wanted.spread, mine.rings, wanted.rings, mine.centre, wanted.centre))


def _body(found: Profile) -> float:
    """The power between 320 Hz and 2.5 kHz, where the body of nearly every instrument lies, in dB."""
    return float(10 * np.log10(sum(10 ** (each / 10.0) for each in found.bands[4:7])))


def top(mine: Profile, wanted: Profile, *, lift: float = 8.0, cut: float = 6.0) -> dict:
    """What the channel equaliser should do to the top of `mine` so that it stands as far
    above or below its body as the top of `wanted` does: a bell at 3.5 kHz (the presence: the
    bow on the string, the edge of brass) and a shelf from 7.5 kHz up (the air). Only the top
    is touched: below 2.5 kHz two recordings differ by what notes they play, not by how they
    sound. Returns {"bands": [[Hz, dB, octaves]], "high_shelf": [Hz, dB]} for sounds.equalise,
    with no more than `lift` dB added or `cut` taken away."""
    need = np.array([(wanted.bands[at] - _body(wanted)) - (mine.bands[at] - _body(mine)) for at in (7, 8, 9)])      # 2.5 to 5, 5 to 10, 10 to 20 kHz
    # How much of each filter's lift reaches each of those three octaves: the bell, the shelf.
    reach = np.array([[1.0, 0.25], [0.35, 0.75], [0.03, 1.0]])
    trust = np.array([1.0, 1.0, 0.5])[:, None]          # the very top is the least to be trusted
    amounts, *_ = np.linalg.lstsq(reach * trust, need * trust[:, 0], rcond=None)
    bell, shelf = (round(float(min(max(each, -cut), lift)), 1) for each in amounts)
    return {"bands": [[3500.0, bell, 1.6]], "high_shelf": [7500.0, shelf]}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--list":
        for key, count in asked_for(args[1] if len(args) > 1 else "warcraft").items():
            print("%3d  %s" % (count, key))
        return 0
    if len(args) < 2:
        print(__doc__)
        return 2
    wanted = reference(args[0])
    print("%-40s %s" % ("reference: %s (%d)" % (args[0], wanted.count), wanted))
    for path in args[1:]:
        mine = of(path)
        print("%-40s %s" % (Path(path).stem[:40], mine))
        print("%-40s %s" % ("", differs(mine, wanted)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
