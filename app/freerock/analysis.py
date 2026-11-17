"""Measuring a track without ears: tempo and beat grid, key and tuning, loudness, band energy.

Everything FreeRock measures was made at a stated tempo and key, so nothing here has to guess a
tempo from nothing. Each function checks how well the audio matches what it was meant to be, and
reports numbers that tests and the studio can hold against a pass line.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pyloudnorm
from scipy.signal import butter, sosfiltfilt

from .audio import db, rms, to_mono

PITCH_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# How strongly each scale degree is heard as belonging to a major or minor key
# (Krumhansl and Kessler's probe-tone ratings, the usual reference for finding a key).
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


# --- onsets ------------------------------------------------------------------------------------

ONSET_WINDOW_S = 0.020


def onset_envelope(audio: np.ndarray, rate: int, hop_s: float = 0.005,
                   window_s: float = ONSET_WINDOW_S) -> tuple[np.ndarray, float]:
    """How much new sound starts at each moment. Returns (envelope, envelope samples per second).

    It is the rise in the spectrum from one short window to the next, summed over frequency, so a
    drum hit or a picked note shows as a peak whatever its pitch. Entry i describes the window
    that starts at sample i * hop; `_envelope_offset` says where in that window an onset sits when
    the envelope peaks.
    """
    mono = to_mono(audio).astype(np.float32)
    hop = max(1, int(round(hop_s * rate)))
    size = int(2 ** np.ceil(np.log2(window_s * rate)))
    if len(mono) < size + hop:
        return np.zeros(0, dtype=np.float32), rate / hop
    window = np.hanning(size).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(mono, size)[::hop]
    envelope = np.empty(len(frames), dtype=np.float32)
    previous = None
    block = 4096  # frames transformed at a time, to keep memory flat on long tracks
    for start in range(0, len(frames), block):
        spectrum = np.log1p(100.0 * np.abs(np.fft.rfft(frames[start:start + block] * window, axis=1)))
        if previous is None:
            previous = spectrum[0]
        stacked = np.vstack([previous[None, :], spectrum])
        rise = np.maximum(stacked[1:] - stacked[:-1], 0.0).sum(axis=1)
        envelope[start:start + len(rise)] = rise
        previous = spectrum[-1]
    envelope = envelope / (np.median(envelope) + 1e-9)
    return envelope, rate / hop


def _envelope_offset(rate: int, window_s: float = ONSET_WINDOW_S) -> float:
    """Seconds from the start of a window to the onset that makes the envelope peak there.

    The window fades in and out, so a sound's weight grows fastest while it crosses the window's
    later half: a click peaks the envelope three quarters of the way through, a sustained note at
    the middle. Five eighths splits the difference; with a 20 ms window the two cases are then
    within 3 ms of it, which is finer than any pass line FreeRock uses.
    """
    size = int(2 ** np.ceil(np.log2(window_s * rate)))
    return 0.625 * size / rate


# --- tempo and beat grid -------------------------------------------------------------------------

@dataclass
class Grid:
    """A steady beat fitted to a stretch of audio."""
    bpm: float
    first_beat_s: float        # time of the first beat at or after the start of the stretch
    contrast: float            # how much stronger the fit is at its best phase than on average
    jitter_ms: float           # typical distance between a beat and the nearest onset
    outliers: int              # beats whose nearest onset is more than 40 ms from the grid
    beats_checked: int
    drift_ms_per_100_beats: float

    @property
    def period_s(self) -> float:
        return 60.0 / self.bpm

    def beat_times(self, until_s: float) -> np.ndarray:
        count = int(np.floor((until_s - self.first_beat_s) / self.period_s)) + 1
        return self.first_beat_s + np.arange(max(count, 0)) * self.period_s

    def distance_to_beat_s(self, moment_s: float) -> float:
        """How far `moment_s` is from the nearest beat of this grid, signed (positive = beat is later)."""
        phase = (self.first_beat_s - moment_s) % self.period_s
        return phase if phase <= self.period_s / 2 else phase - self.period_s


def _comb_scores(envelope: np.ndarray, env_rate: float, period_s: float,
                 phases_s: np.ndarray) -> np.ndarray:
    """For each phase, the mean envelope height at the beats of a grid with this period."""
    duration = len(envelope) / env_rate
    count = int(np.floor((duration - phases_s.max()) / period_s))
    if count < 4:
        return np.zeros_like(phases_s)
    beat_index = np.arange(count)
    positions = (phases_s[:, None] + beat_index[None, :] * period_s) * env_rate
    low = np.floor(positions).astype(np.int64)
    frac = positions - low
    low = np.clip(low, 0, len(envelope) - 2)
    heights = envelope[low] * (1.0 - frac) + envelope[low + 1] * frac
    return heights.mean(axis=1)


def fit_grid(audio: np.ndarray, rate: int, nominal_bpm: float, search: float = 0.03,
             start_s: float = 0.0) -> Grid:
    """Fits a steady beat near `nominal_bpm` to `audio`. Times in the result are measured from
    the start of `audio` plus `start_s`, so a part cut out of a longer track keeps track times."""
    envelope, env_rate = onset_envelope(audio, rate)
    offset = _envelope_offset(rate)
    duration = len(envelope) / env_rate
    if duration < 4 * 60.0 / nominal_bpm:
        raise ValueError("%.2f s is too short to fit a beat at %.1f BPM" % (duration, nominal_bpm))

    def best_for(bpm_values: np.ndarray) -> tuple[float, float, float]:
        top = (-1.0, 0.0, 0.0, 0.0)  # score, bpm, phase, mean score
        for bpm in bpm_values:
            period = 60.0 / bpm
            phases = np.arange(0.0, period, 0.004)
            scores = _comb_scores(envelope, env_rate, period, phases)
            best = int(np.argmax(scores))
            if scores[best] > top[0]:
                top = (float(scores[best]), float(bpm), float(phases[best]), float(scores.mean()))
        return top[1], top[2], top[0] / (top[3] + 1e-9)

    # A tempo error of e BPM moves the last beat by duration * e / bpm seconds. Step finely enough
    # that the coarse pass lands within about 10 ms at the end, then refine around the winner.
    coarse_step = max(0.010 * nominal_bpm / duration, 0.002)
    low, high = nominal_bpm * (1.0 - search), nominal_bpm * (1.0 + search)
    bpm, phase, contrast = best_for(np.arange(low, high + coarse_step, coarse_step))
    fine = np.arange(bpm - coarse_step, bpm + coarse_step, coarse_step / 20.0)
    bpm, phase, contrast = best_for(fine)
    period = 60.0 / bpm

    # Compare each beat with the strongest onset near it to see how tightly the audio keeps the
    # grid. "Near" is just under a quarter of a beat either side: wide enough to catch a hit that
    # is plainly late, narrow enough that the notes halfway between beats are not mistaken for it.
    reach = int(round(0.24 * period * env_rate))
    floor = float(np.percentile(envelope, 75))
    deviations, positions = [], []
    for index, moment in enumerate(phase + np.arange(int((duration - phase) / period)) * period):
        centre = int(round(moment * env_rate))
        left, right = max(centre - reach, 0), min(centre + reach + 1, len(envelope))
        if right - left < 3:
            continue
        peak = left + int(np.argmax(envelope[left:right]))
        if envelope[peak] <= floor:
            continue  # nothing was struck near this beat; it says nothing about timing
        deviations.append(peak / env_rate - moment)
        positions.append(index)
    if deviations:
        found = np.array(deviations)
        centred = found - np.median(found)
        jitter_ms = float(np.median(np.abs(centred)) * 1000.0)
        outliers = int(np.sum(np.abs(centred) > 0.040))
        drift = float(np.polyfit(positions, found, 1)[0] * 100.0 * 1000.0) if len(found) >= 8 else 0.0
    else:
        jitter_ms, outliers, drift = float("nan"), 0, 0.0

    first = (phase + offset) % period
    return Grid(bpm=bpm, first_beat_s=first + start_s, contrast=contrast, jitter_ms=jitter_ms,
                outliers=outliers, beats_checked=len(deviations), drift_ms_per_100_beats=drift)


# --- key and tuning ------------------------------------------------------------------------------

@dataclass
class KeyEstimate:
    tonic: int                 # 0 = C ... 11 = B
    mode: str                  # "major" or "minor"
    correlation: float         # how well the best key fits, -1 to 1
    tuning_cents: float        # how far the track sits from concert pitch (A = 440 Hz)
    chroma: np.ndarray = field(repr=False)  # energy in each of the twelve pitch classes

    @property
    def name(self) -> str:
        return "%s %s" % (PITCH_NAMES[self.tonic], self.mode)

    def rank_of(self, pitch_class: int) -> int:
        """1 if `pitch_class` is the strongest pitch class in the track, 2 if second, and so on."""
        order = np.argsort(-self.chroma)
        return int(np.where(order == pitch_class % 12)[0][0]) + 1

    def scale_shares(self) -> np.ndarray:
        """For each of the twelve major scales, the share of the track's energy that falls on
        its seven notes. Entry 0 is the scale of C major (the white keys), entry 7 that of G."""
        return np.array([sum(self.chroma[(root + step) % 12] for step in MAJOR_SCALE) for root in range(12)])

    def in_family(self, key_name: str) -> bool:
        """Whether the track uses the notes of `key_name`, give or take one.

        Riff rock and folk tunes move their weight around inside one set of seven notes: a piece
        asked for in D minor may sit on A for a section, or lean on the major sixth and so sound
        Dorian. A key finder then names a different key each time, though nothing has gone wrong
        and the parts still join and layer. So this asks which seven-note scale the audio fits
        best, and accepts the scale `key_name` belongs to or a neighbour that differs from it by
        a single note.
        """
        wanted = parent_scale(key_name)
        shares = self.scale_shares()
        family = max(shares[wanted], shares[(wanted + 7) % 12], shares[(wanted + 5) % 12])
        # "As well as any scale could, within three points": a sparse part (a drone, power chords
        # of root and fifth) fits several scales equally, and must not fail for which one a tie
        # happens to name.
        return bool(family >= shares.max() - 0.03)

    def agrees_with(self, tonic: int) -> bool:
        """True when `tonic` is this estimate's tonic, or the tonic of its relative key, or one of
        the two strongest pitch classes. Modal music (Dorian, Mixolydian) is often heard by a
        key finder as the relative major or minor, so an exact match would be too strict."""
        relative = (self.tonic + 3) % 12 if self.mode == "minor" else (self.tonic - 3) % 12
        return tonic % 12 in (self.tonic, relative) or self.rank_of(tonic) <= 2


def estimate_key(audio: np.ndarray, rate: int) -> KeyEstimate:
    mono = to_mono(audio).astype(np.float32)
    size = int(2 ** np.ceil(np.log2(rate * 0.17)))  # about 6 Hz between bins: enough to tell semitones apart down to low E
    if len(mono) < size:
        raise ValueError("Too short to estimate a key")
    hop = size // 2
    window = np.hanning(size).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(mono, size)[::hop]
    spectrum = np.zeros(size // 2 + 1, dtype=np.float64)
    for start in range(0, len(frames), 256):
        spectrum += (np.abs(np.fft.rfft(frames[start:start + 256] * window, axis=1)) ** 2).sum(axis=0)
    freqs = np.fft.rfftfreq(size, 1.0 / rate)
    keep = (freqs >= 60.0) & (freqs <= 2000.0)
    freqs, power = freqs[keep], spectrum[keep]

    # Only the peaks of the spectrum are used, each placed by fitting a curve through it and its
    # two neighbours. Taking every bin instead smears a low note into the semitones either side
    # of it (the bins are about 6 Hz apart, and at 80 Hz a semitone is under 5 Hz wide), which is
    # enough to make a drone on E look as if it had F in it.
    is_peak = np.zeros(len(power), dtype=bool)
    is_peak[1:-1] = (power[1:-1] > power[:-2]) & (power[1:-1] >= power[2:])
    is_peak &= power > power.max() * 1e-4
    at = np.flatnonzero(is_peak)
    left, mid, right = (np.log(power[at + shift] + 1e-30) for shift in (-1, 0, 1))
    curve = left - 2.0 * mid + right
    shift = np.where(curve < 0, 0.5 * (left - right) / np.where(curve < 0, curve, -1.0), 0.0)
    peak_freqs = freqs[at] + np.clip(shift, -0.5, 0.5) * (freqs[1] - freqs[0])
    weight = np.sqrt(power[at])

    # Tuning: where the peaks sit between two semitones, as an average around the circle.
    semitones = 12.0 * np.log2(peak_freqs / 440.0)
    fraction = semitones - np.round(semitones)
    strong = power[at] > np.percentile(power, 90)
    angle = np.angle(np.sum(power[at][strong] * np.exp(2j * np.pi * fraction[strong])))
    tuning_cents = float(angle / (2 * np.pi) * 100.0)

    pitch_class = (np.round(semitones - tuning_cents / 100.0).astype(int) + 9) % 12  # A is pitch class 9
    chroma = np.bincount(pitch_class, weights=weight, minlength=12)
    chroma = chroma / (chroma.sum() + 1e-12)

    best = (-2.0, 0, "major")
    for tonic in range(12):
        rotated = np.roll(chroma, -tonic)
        for mode, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            correlation = float(np.corrcoef(rotated, profile)[0, 1])
            if correlation > best[0]:
                best = (correlation, tonic, mode)
    return KeyEstimate(tonic=best[1], mode=best[2], correlation=best[0],
                       tuning_cents=tuning_cents, chroma=chroma)


MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
# How far above its parent major scale's key note each mode starts, in semitones: D Dorian uses
# the notes of C major, two semitones below D.
MODE_STEPS = {"major": 0, "ionian": 0, "dorian": 2, "phrygian": 4, "lydian": 5, "mixolydian": 7,
              "minor": 9, "aeolian": 9, "locrian": 11}


def parent_scale(key_name: str) -> int:
    """The major scale whose seven notes a key uses, as the pitch class of that scale's key
    note: "A minor", "D dorian" and "G mixolydian" all give 0, the scale of C major."""
    words = key_name.strip().lower().split()
    mode = words[1] if len(words) > 1 else "major"
    if mode not in MODE_STEPS:
        raise ValueError("Unknown mode %r in %r" % (mode, key_name))
    return (parse_tonic(key_name) - MODE_STEPS[mode]) % 12


def parse_tonic(name: str) -> int:
    """The pitch class of a key name such as "A minor", "D dorian" or "F# mixolydian"."""
    note = name.strip().split()[0].replace("b", "♭")
    flat = note.endswith("♭")
    base = note.rstrip("♭")
    index = PITCH_NAMES.index(base.upper() if len(base) == 1 else base[0].upper() + base[1:])
    return (index - 1) % 12 if flat else index


# --- loudness and bands ----------------------------------------------------------------------------

def loudness_lufs(audio: np.ndarray, rate: int) -> float:
    """Programme loudness as broadcasters measure it (ITU-R BS.1770)."""
    if len(audio) < int(0.4 * rate):
        raise ValueError("Loudness needs at least 0.4 s of audio")
    return float(pyloudnorm.Meter(rate).integrated_loudness(np.asarray(audio, dtype=np.float64)))


def band_level_db(audio: np.ndarray, rate: int, low_hz: float, high_hz: float) -> float:
    """The level of the part of `audio` between two frequencies, in dB relative to full scale."""
    nyquist = rate / 2.0
    sos = butter(4, [low_hz / nyquist, min(high_hz / nyquist, 0.999)], btype="bandpass", output="sos")
    return db(rms(sosfiltfilt(sos, to_mono(audio).astype(np.float64))))


def peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio))) if audio.size else 0.0


# --- comparing the sound of two recordings ---------------------------------------------------

def band_profile(audio: np.ndarray, rate: int, low_hz: float = 50.0, high_hz: float = 12_800.0,
                 per_octave: int = 3) -> np.ndarray:
    """The average level in each third of an octave from `low_hz` to `high_hz`, in dB.

    It is a rough picture of a recording's tone: how much low end, how bright, where the guitars
    sit. Two recordings by the same band in the same room have similar pictures.
    """
    mono = to_mono(audio).astype(np.float32)
    size = 8192
    if len(mono) < size:
        raise ValueError("Too short to take a band profile")
    window = np.hanning(size).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(mono, size)[::size // 2]
    power = np.zeros(size // 2 + 1, dtype=np.float64)
    for start in range(0, len(frames), 256):
        power += (np.abs(np.fft.rfft(frames[start:start + 256] * window, axis=1)) ** 2).sum(axis=0)
    power /= len(frames)
    freqs = np.fft.rfftfreq(size, 1.0 / rate)
    count = int(round(np.log2(high_hz / low_hz) * per_octave))
    edges = low_hz * 2.0 ** (np.arange(count + 1) / per_octave)
    levels = np.empty(count)
    for index in range(count):
        inside = (freqs >= edges[index]) & (freqs < edges[index + 1])
        levels[index] = 10.0 * np.log10(power[inside].sum() + 1e-20)
    return levels


def profile_difference_db(first: np.ndarray, second: np.ndarray) -> float:
    """How different two band profiles are, in dB, ignoring that one may simply be louder.
    Around 1 to 2 dB is the same sound; 4 dB and up is a clearly different mix."""
    gap = (first - first.mean()) - (second - second.mean())
    return float(np.sqrt(np.mean(gap ** 2)))
