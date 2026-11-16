"""Recorded instruments: turning a folder of recordings into something a sampler can play.

A sampled instrument is a set of recordings of single notes: a few pitches across its range,
each at a few strengths, sometimes each several times over (so that a note struck twice is not
the same recording twice). To play any note, the sampler takes the nearest recording and shifts
it a little. This module reads such a set and says which recording answers to which notes at
which strengths: a list of ZONES, which the desk (studio.desk) hands to REAPER's own sampler,
one zone to each sampler.

Nothing is taken on trust from a file's name except which of the twelve notes it is. Which
octave it sounds in, and how far out of tune it is, is measured from the recording: the sets
do not agree on what to call an octave, and a zone that is an octave out is a wrong note.

The sets are on the drive under var/samples. tools/stems/README.md says where each came from
and under what licence.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import soundfile

SAMPLES = Path(__file__).resolve().parents[3] / "var" / "samples"
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE = re.compile(r"(?<![A-Za-z])([A-G])([#b]?)(-?\d)(?![0-9A-Za-z])")
_LAYER = re.compile(r"(?<![A-Za-z0-9])vl?(\d+)(?![0-9A-Za-z])", re.IGNORECASE)
_TURN = re.compile(r"(?:rr|RR)(\d+)|_(\d+)(?=\.[A-Za-z0-9]+$)")
# Strengths that are written as words or as the marks in a score, softest first.
MARKS = {"ppp": 1, "pp": 2, "p": 3, "soft": 3, "mp": 4, "mf": 5, "medium": 5, "f": 6, "loud": 7, "ff": 7, "fff": 8}
REACH = 4                      # how many semitones past its outermost recordings an instrument may be stretched


@dataclass(frozen=True)
class Zone:
    files: tuple[str, ...]     # the recordings that take turns here, as paths under var/samples
    low: int                   # the notes it answers to
    high: int
    root: int                  # the note the recordings are of
    soft: int = 1              # the strengths (MIDI, 1 to 127) it answers to
    hard: int = 127
    tune: float = 0.0          # cents to add, to bring the recordings into tune
    gain: float = 0.0          # dB
    loop: float = 0.0          # milliseconds into the recording where a held note goes round from; 0 if it does not
    until: float = 1.0         # how far through the recording it goes before going round (a part of the whole)


@dataclass
class Patch:
    """One way of playing one instrument: bowed, plucked, short; or one drum."""
    name: str
    zones: list[Zone] = field(default_factory=list)
    attack: float = 4.0        # milliseconds
    release: float = 180.0     # milliseconds a note rings on after it is let go
    held: bool = True          # a note lasts as long as it is written; if not, every recording plays to its end
    floor: float = -14.0       # dB: how much quieter the softest strike is than the hardest, within one zone
    seconds: float = 0.0       # how long the shortest of its recordings lasts
    credit: str = ""
    calls: int = 0             # what its set calls an octave: semitones its file names are from the usual (middle C is C4)

    @property
    def low(self) -> int:
        return min(zone.low for zone in self.zones)

    @property
    def high(self) -> int:
        return max(zone.high for zone in self.zones)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Patch":
        data = json.loads(path.read_text(encoding="utf-8"))
        zones = [Zone(**dict(zone, files=tuple(zone["files"]))) for zone in data.pop("zones")]
        return cls(zones=zones, **data)


# ---------------------------------------------------------------------------------------------
# Hearing what a recording is
# ---------------------------------------------------------------------------------------------
def _steady(audio: np.ndarray, rate: int, long: bool) -> np.ndarray:
    """The stretch of a recording to measure: for a held note a third of a second from where it
    has settled, for a short one what follows the strike."""
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    size = int(rate * (0.35 if long else 0.12))
    hop = max(size // 4, 1)
    if len(mono) <= size:
        return mono
    energy = np.array([float(np.square(mono[at:at + size]).sum()) for at in range(0, len(mono) - size, hop)])
    if not len(energy) or energy.max() <= 0.0:
        return mono[:size]
    loud = np.nonzero(energy >= energy.max() * 0.5)[0]
    # A held note is measured in the middle of its loud part; a short one at its loudest.
    at = int(loud[len(loud) // 2] if long else energy.argmax()) * hop
    return mono[at:at + size]


def pitch_of(audio: np.ndarray, rate: int, note: int | None = None) -> tuple[int, float, float]:
    """The note a recording sounds (MIDI), how many cents sharp of it, and how sure that is
    (0 to 1: how well the sound repeats at that pitch). With `note`, which of the twelve notes
    it is (0 is C) is taken as known and only the octave is looked for."""
    long = len(audio) / rate > 1.2
    cut = _steady(audio, rate, long).astype(np.float64)
    cut = cut - cut.mean()
    if not np.any(cut):
        return 60, 0.0, 0.0
    size = 1 << int(np.ceil(np.log2(len(cut) * 2)))
    spectrum = np.fft.rfft(cut * np.hanning(len(cut)), size)
    repeat = np.fft.irfft(np.abs(spectrum) ** 2)
    repeat = repeat / max(repeat[0], 1e-20)

    def best(lag: float) -> tuple[float, float]:
        low, high = max(int(lag * 0.955), 2), min(int(np.ceil(lag * 1.047)) + 1, len(repeat) // 2 - 2)
        if high <= low:
            return 0.0, lag
        at = low + int(repeat[low:high + 1].argmax())
        a, b, c = repeat[at - 1], repeat[at], repeat[at + 1]
        bend = a - 2 * b + c
        fine = at + (0.5 * (a - c) / bend if abs(bend) > 1e-12 else 0.0)
        return float(b), fine

    if note is None:
        candidates = range(24, 109)
    else:
        candidates = [midi for midi in range(12 + note % 12, 121, 12)]
    # Any smooth sound is like itself a moment later. A pitch is a likeness that comes back
    # after the sound has first stopped being like itself, so nothing nearer than that counts.
    under = np.nonzero(repeat[:len(repeat) // 2] < 0.25)[0]
    nearest = int(under[0]) if len(under) else 8
    scored = []
    for midi in candidates:
        lag = rate / (440.0 * 2 ** ((midi - 69) / 12.0))
        if lag >= len(repeat) // 2 - 2 or lag * 0.955 <= nearest:
            continue
        score, fine = best(lag)
        if fine > 0:
            scored.append((score, midi, fine))
    if not scored:
        return 60, 0.0, 0.0
    top = max(score for score, _, _ in scored)
    # A sound that repeats every so often repeats every twice so often as well: of the octaves
    # that fit about equally, the highest is the note.
    score, midi, fine = max((each for each in scored if each[0] >= top - 0.1 * abs(top)), key=lambda each: each[1])
    hz = rate / fine
    cents = 1200.0 * np.log2(hz / (440.0 * 2 ** ((midi - 69) / 12.0)))
    return midi, float(cents), float(score)


def loudness(audio: np.ndarray) -> float:
    """dB of the loudest tenth of a second of a recording (full scale is 0)."""
    mono = np.abs(audio).max(axis=1) if audio.ndim == 2 else np.abs(audio)
    size = 4410
    if len(mono) < size:
        return float(20 * np.log10(max(np.sqrt(np.square(mono).mean()), 1e-9)))
    frames = np.sqrt(np.square(mono[:len(mono) // size * size]).reshape(-1, size).mean(axis=1))
    return float(20 * np.log10(max(frames.max(), 1e-9)))


# ---------------------------------------------------------------------------------------------
# A folder of recordings named by note, strength and turn
# ---------------------------------------------------------------------------------------------
def _named(name: str) -> tuple[int | None, int, int]:
    """Which of the twelve notes a file says it is (None if it does not say), which strength
    (1 is the softest) and which turn."""
    stem = name.rsplit(".", 1)[0]
    found = _NOTE.findall(stem)
    note = None
    if found:
        letter, sign, _ = found[-1]
        note = (NAMES[letter] + (1 if sign == "#" else -1 if sign == "b" else 0)) % 12
    else:
        small = re.match(r"([a-g])([#b]?)(-?\d)(?=[_\-\s]|$)", stem)       # "b2_mf_1": the note in small letters, first
        if small:
            note = (NAMES[small.group(1).upper()] + (1 if small.group(2) == "#" else -1 if small.group(2) == "b" else 0)) % 12
    layer = _LAYER.search(stem)
    turn = _TURN.search(name)
    strength = int(layer.group(1)) if layer else 1
    again = int(next(part for part in turn.groups() if part)) if turn else 1
    if not layer:
        for word in re.split(r"[_\-\s]+", stem):
            mark = re.fullmatch(r"(ppp|pp|p|mp|mf|f|ff|fff|soft|medium|loud)(\d*)", word, re.IGNORECASE)
            if mark:
                strength = MARKS[mark.group(1).lower()]
                if mark.group(2) and not turn:
                    again = int(mark.group(2))
    return note, strength, again


def pitched(folder: Path, name: str, *, held: bool = True, attack: float = 4.0, release: float = 180.0,
            floor: float = -14.0, layers: tuple[float, ...] | None = None, credit: str = "",
            only: str = "", calls: int | None = None) -> Patch:
    """Reads a folder of single notes into a patch. `layers` is how many dB under the hardest
    strength each softer one is played (softest first), for sets whose recordings were all
    brought to the same loudness; left out, the recordings' own loudness is kept. `only` keeps
    the files with that in their names. `calls` says what the set calls an octave (how many
    semitones its names are from the usual, where middle C is C4), for a folder whose
    recordings have too little pitch to settle it: a tremolo, a rattle."""
    heard: dict[tuple[int, int], list[tuple[int, str, float]]] = {}       # (root, layer) -> [(turn, file, cents)]
    lengths: dict[str, float] = {}
    shortest = 1e9
    read = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in (".wav", ".flac", ".aif", ".aiff") or (only and only not in path.name):
            continue
        note, layer, turn = _named(path.name)
        stem = path.name.rsplit(".", 1)[0]
        octave = _NOTE.findall(stem) or re.findall(r"^([a-g])([#b]?)(-?\d)(?=[_\-\s]|$)", stem)
        written = None if note is None or not octave else note + 12 * (int(octave[-1][2]) + 1)     # as if middle C were C4
        audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
        root, cents, sure = pitch_of(audio, rate, note)
        read.append((path, layer, turn, written, root, cents, sure))
        lengths[str(path.relative_to(SAMPLES))] = len(audio) / rate
        shortest = min(shortest, len(audio) / rate)
    if not read:
        raise FileNotFoundError("No recordings in %s" % folder)
    # What the set calls an octave: the recordings that can be heard clearly settle it for the
    # ones that cannot (a plucked or a very short note has too little pitch to measure).
    clear = [root - written for _, _, _, written, root, cents, sure in read if written is not None and sure >= 0.5 and abs(cents) <= 30.0]
    if calls is None:
        if not clear:
            raise ValueError("None of the recordings in %s has a pitch that can be measured" % folder)
        calls = max(set(clear), key=clear.count)
        if clear.count(calls) < 0.6 * len(clear):
            raise ValueError("The recordings in %s do not agree on what an octave is called: %s" % (folder, sorted(set(clear))))
    for path, layer, turn, written, root, cents, sure in read:
        if written is not None:
            sharp = cents if root == written + calls and sure >= 0.5 and abs(cents) <= 30.0 else 0.0
            root = written + calls
        elif sure < 0.5 or abs(cents) > 30.0:
            raise ValueError("%s does not say what note it is, and it cannot be measured" % path)
        else:
            sharp = cents
        heard.setdefault((root, layer), []).append((turn, str(path.relative_to(SAMPLES)), sharp))
    roots = sorted({root for root, _ in heard})
    patch = Patch(name=name, attack=attack, release=release, held=held, floor=floor, seconds=shortest, credit=credit, calls=calls)
    for index, root in enumerate(roots):
        # Each recording answers to the notes nearer to it than to its neighbours.
        low = roots[0] - REACH if index == 0 else (roots[index - 1] + root) // 2 + 1
        high = roots[-1] + REACH if index == len(roots) - 1 else (root + roots[index + 1]) // 2
        have = sorted(layer for each, layer in heard if each == root)
        for place, layer in enumerate(have):
            soft = 1 if place == 0 else int(round(127 * place / len(have))) + 1
            hard = 127 if place == len(have) - 1 else int(round(127 * (place + 1) / len(have)))
            takes = sorted(heard[(root, layer)])
            gain = 0.0
            if layers is not None:
                # Counted from the hardest: a note that has only two strengths has the two hardest.
                under = list(layers)[-len(have):] if len(have) <= len(layers) else [layers[0]] * (len(have) - len(layers)) + list(layers)
                gain = under[place]
            loop, until = 0.0, 1.0
            if held:
                # A held note goes round a stretch of the recording's steady middle for as long
                # as it is held: from a little way in, to before the player lets go.
                least = min(lengths[file] for _, file, _ in takes)
                if least >= 2.5:
                    loop = min(1500.0, 350.0 * least)
                    until = (least - max(0.6, 0.12 * least)) / least
            patch.zones.append(Zone(files=tuple(file for _, file, _ in takes), low=max(low, 0), high=min(high, 127), root=root,
                                    soft=soft, hard=hard, tune=-float(np.median([cents for _, _, cents in takes])), gain=gain,
                                    loop=loop, until=until))
    return patch


def struck(files: list[Path], name: str, note: int, *, floor: float = -18.0, release: float = 400.0, credit: str = "") -> Patch:
    """One drum, bell or other thing that is hit: its recordings by strength and turn, all
    answering to one note."""
    by_layer: dict[int, list[tuple[int, str]]] = {}
    for path in files:
        _, layer, turn = _named(path.name)
        by_layer.setdefault(layer, []).append((turn, str(path.relative_to(SAMPLES))))
    if not by_layer:
        raise FileNotFoundError("No recordings for %s" % name)
    patch = Patch(name=name, attack=0.5, release=release, held=False, floor=floor, credit=credit)
    have = sorted(by_layer)
    for place, layer in enumerate(have):
        soft = 1 if place == 0 else int(round(127 * place / len(have))) + 1
        hard = 127 if place == len(have) - 1 else int(round(127 * (place + 1) / len(have)))
        patch.zones.append(Zone(files=tuple(file for _, file in sorted(by_layer[layer])), low=note, high=note, root=note,
                                soft=soft, hard=hard))
    return patch


def tone_of(audio: np.ndarray, rate: int, low: float = 55.0, high: float = 420.0) -> float | None:
    """The note a kettledrum is tuned to, as a MIDI number with a fraction: its lowest strong
    partial. (How often its sound repeats is no guide: a drum's partials are not a harmonic
    series, and that measure lands an octave low or a fifth high as often as not.)"""
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    start = int(np.abs(mono).argmax())
    cut = mono[start + int(0.03 * rate): start + int(1.6 * rate)]
    if len(cut) < rate // 4:
        return None
    size = 1 << 17
    spectrum = np.abs(np.fft.rfft(cut * np.hanning(len(cut)), size))
    hz = np.fft.rfftfreq(size, 1.0 / rate)
    band = np.nonzero((hz >= low) & (hz <= high))[0]
    top = spectrum[band].max()
    for at in band:
        if spectrum[at] >= 0.3 * top and spectrum[at] >= spectrum[at - 1] and spectrum[at] >= spectrum[at + 1]:
            a, b, c = np.log(spectrum[at - 1:at + 2] + 1e-12)
            bend = a - 2 * b + c
            fine = at + (0.5 * (a - c) / bend if abs(bend) > 1e-12 else 0.0)
            return float(69 + 12 * np.log2(fine * rate / size / 440.0))
    return None


def kettles(folder: Path, name: str, *, drum: str = r"^(.+?)_[Hh]it", only: str = "", low: int = 36, high: int = 60,
            floor: float = -14.0, release: float = 900.0, credit: str = "") -> Patch:
    """Reads a folder of kettledrum strokes that are named by drum and tuning, not by note.
    The strokes of one drum at one tuning are measured together; a tuning whose strokes do not
    agree on a note (the wanted partial is too weak in some of them) is left out."""
    groups: dict[str, list[tuple[Path, float | None]]] = {}
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() != ".wav" or (only and only not in path.name):
            continue
        found = re.match(drum, path.name)
        if not found:
            continue
        audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
        groups.setdefault(found.group(1), []).append((path, tone_of(audio, rate)))
    by_root: dict[int, list[tuple[Path, float]]] = {}
    for strokes in groups.values():
        tones = [tone for _, tone in strokes if tone is not None]
        if len(tones) < 3:
            continue
        middle = float(np.median(tones))
        agree = [(path, tone) for path, tone in strokes if tone is not None and abs(tone - middle) <= 0.5]
        if len(agree) < max(4, len(strokes) - 1) or not low <= round(middle) <= high:
            continue
        by_root.setdefault(int(round(middle)), []).extend(agree)
    if len(by_root) < 4:
        raise ValueError("Too few of the drums in %s could be told a note: %s" % (folder, sorted(by_root)))
    roots = sorted(by_root)
    patch = Patch(name=name, attack=0.5, release=release, held=False, floor=floor, credit=credit)
    for index, root in enumerate(roots):
        bottom = roots[0] - REACH if index == 0 else (roots[index - 1] + root) // 2 + 1
        top = roots[-1] + REACH if index == len(roots) - 1 else (root + roots[index + 1]) // 2
        tune = -100.0 * (float(np.median([tone for _, tone in by_root[root]])) - root)
        by_layer: dict[int, list[str]] = {}
        for path, _ in by_root[root]:
            by_layer.setdefault(_named(path.name)[1], []).append(str(path.relative_to(SAMPLES)))
        have = sorted(by_layer)
        for place, layer in enumerate(have):
            soft = 1 if place == 0 else int(round(127 * place / len(have))) + 1
            hard = 127 if place == len(have) - 1 else int(round(127 * (place + 1) / len(have)))
            patch.zones.append(Zone(files=tuple(sorted(by_layer[layer])), low=max(bottom, 0), high=min(top, 127), root=root,
                                    soft=soft, hard=hard, tune=tune))
    return patch
