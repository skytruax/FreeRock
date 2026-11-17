"""Our own synthesiser: the instruments of the dance floor, made of arithmetic.

Nothing here is a plug-in or a program someone else has to keep working. A note is a few
oscillators (saws that are kept free of the false tones a computer adds to sharp edges, squares,
sines), an envelope that says how it swells and dies, and a filter that opens and closes; a
bell or an electric piano is one sine bending another; a plucked string is a burst of noise going
round a short loop. Drums are recordings of the old drum machines (the TR-808, 909, 707, 606 and
727, as played by a Roland TR-8 and released into the public domain: see `Kit`), or are made
here when those recordings are not on the machine. On top come a chorus, an echo in time with
the music, the studio's one room, and the pumping of everything but the drums against the kick.

Every sound is the same every time: what is random in it (where a saw starts, the noise in a
breath) is drawn from a number the caller gives.

The loops that touch every sample are compiled by numba, which is not one of FreeRock's own
requirements: run anything that uses this file with `uv run --no-sync --with numba ...`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile
from numba import njit
from scipy.signal import butter, resample_poly, sosfilt

from . import room

RATE = 48000
SAW, SQUARE, SINE, TRIANGLE = 0, 1, 2, 3
LOW, HIGH, BAND = 0, 1, 2
DRUMS = Path(__file__).resolve().parents[3] / "var" / "tools" / "drums"
TR8 = DRUMS / "mck" / "MckSamplePacks-main" / "TR8"


def hz(pitch: float) -> float:
    """The frequency of a MIDI pitch: 69 is the A at 440."""
    return 440.0 * 2.0 ** ((pitch - 69.0) / 12.0)


# ---------------------------------------------------------------------------------------------
# The loops
# ---------------------------------------------------------------------------------------------
@njit(cache=True, fastmath=True)
def _blep(t, dt):
    """What to take off a sharp edge so that it has no false tones (a "PolyBLEP")."""
    if t < dt:
        t = t / dt
        return t + t - t * t - 1.0
    if t > 1.0 - dt:
        t = (t - 1.0) / dt
        return t * t + t + t + 1.0
    return 0.0


@njit(cache=True, fastmath=True)
def _osc(wave, t, dt):
    if wave == 0:
        return 2.0 * t - 1.0 - _blep(t, dt)
    if wave == 1:
        other = t + 0.5
        if other >= 1.0:
            other -= 1.0
        return (1.0 if t < 0.5 else -1.0) + _blep(t, dt) - _blep(other, dt)
    if wave == 2:
        return math.sin(6.283185307179586 * t)
    return 4.0 * abs(t - 0.5) - 1.0


@njit(cache=True, fastmath=True)
def _voice(out, at, hold, tail, freq, glide_from, level, pan, p, seed):
    """One note of a subtractive voice, added to `out` from sample `at`: held for `hold`
    samples and dying away over `tail` more. `p` is the patch as numbers (see Patch.numbers)."""
    wave = int(p[0])
    voices = int(p[1])
    detune, spread = p[2], p[3]
    attack, decay, sustain, release = p[4], p[5], p[6], p[7]
    cutoff, env, env_decay, res, follow = p[8], p[9], p[10], p[11], p[12]
    sub, noise, drive = p[13], p[14], p[15]
    vib_rate, vib_depth, vib_delay = p[16], p[17], p[18]
    b_level, b_ratio = p[19], p[20]
    poles = int(p[21])
    b_wave = int(p[22])
    highpass, glide, sub_ratio = p[23], p[24], p[25]
    total = out.shape[0]
    n = hold + tail
    if at < 0 or at >= total or n <= 0:
        return
    if at + n > total:
        n = total - at
    rate = 48000.0
    state = (seed * 2654435761 + 97) % 2147483648
    phases = np.empty(voices)
    ratios = np.empty(voices)
    left = np.empty(voices)
    right = np.empty(voices)
    for k in range(voices):
        state = (1103515245 * state + 12345) % 2147483648
        phases[k] = state / 2147483648.0
        x = 0.0 if voices == 1 else k / (voices - 1) * 2.0 - 1.0
        state = (1103515245 * state + 12345) % 2147483648
        ratios[k] = 2.0 ** ((x + (state / 2147483648.0 - 0.5) * 0.2) * detune * 0.5 / 1200.0)
        side = abs(x) * spread * (1.0 if k % 2 == 0 else -1.0)
        place = pan + side
        if place > 1.0:
            place = 1.0
        if place < -1.0:
            place = -1.0
        angle = (place + 1.0) * 0.7853981633974483
        left[k] = math.cos(angle)
        right[k] = math.sin(angle)
    scale = 1.0 / math.sqrt(voices)
    centre = (pan + 1.0) * 0.7853981633974483
    mid_l, mid_r = math.cos(centre), math.sin(centre)
    sub_phase, b_phase = 0.0, 0.25
    if sub_ratio == 1.0:
        # A sine on the note itself starts in step with the oscillator, so that the two add up
        # the same way on every note: out of step, one note would be all bottom and the next none.
        sub_phase = phases[0] + (0.5 if wave == 0 else 0.25 if wave == 3 else 0.0)
        if sub_phase >= 1.0:
            sub_phase -= 1.0
    base = cutoff * (freq / 261.6256) ** follow
    q = 1.0 / (0.5 + res * 9.0)
    fe = 1.0
    fe_mul = math.exp(-1.0 / (max(env_decay, 1e-4) * rate))
    a = 0.0
    a_step = 1.0 / (max(attack, 1e-4) * rate)
    d_mul = math.exp(-1.0 / (max(decay, 1e-4) * rate))
    r_mul = math.exp(-1.0 / (max(release, 1e-4) * rate))
    rising = True
    g = a1 = a2 = a3 = 0.0
    s = np.zeros((2, 2, 2))            # [side][stage][which]
    hp_l = hp_r = 0.0
    hp_c = 1.0 - math.exp(-6.283185307179586 * highpass / rate) if highpass > 0.0 else 0.0
    g_mul = math.exp(-1.0 / (max(glide, 1e-4) * rate))
    f_now = glide_from if glide_from > 0.0 else freq
    vib_on = vib_rate > 0.0 and vib_depth > 0.0
    for i in range(n):
        if i % 8 == 0:
            fc = base * 2.0 ** (env * fe)
            if fc > 19000.0:
                fc = 19000.0
            if fc < 30.0:
                fc = 30.0
            g = math.tan(3.141592653589793 * fc / rate)
            a1 = 1.0 / (1.0 + g * (g + q))
            a2 = g * a1
            a3 = g * a2
        fe *= fe_mul
        if i < hold:
            if rising:
                a += a_step
                if a >= 1.0:
                    a = 1.0
                    rising = False
            else:
                a = sustain + (a - sustain) * d_mul
        else:
            a *= r_mul
        f_now = freq + (f_now - freq) * g_mul
        f = f_now
        if vib_on:
            t = i / rate - vib_delay
            if t > 0.0:
                depth = vib_depth * (t / 0.25 if t < 0.25 else 1.0)
                f *= 2.0 ** (depth * math.sin(6.283185307179586 * vib_rate * t) / 1200.0)
        dt = f / rate
        xl = 0.0
        xr = 0.0
        for k in range(voices):
            dk = dt * ratios[k]
            ph = phases[k] + dk
            if ph >= 1.0:
                ph -= 1.0
            phases[k] = ph
            v = _osc(wave, ph, dk)
            xl += v * left[k]
            xr += v * right[k]
        xl *= scale
        xr *= scale
        if b_level > 0.0:
            db = dt * b_ratio
            b_phase += db
            if b_phase >= 1.0:
                b_phase -= 1.0
            v = _osc(b_wave, b_phase, db) * b_level
            xl += v * mid_l
            xr += v * mid_r
        if noise > 0.0:
            state = (1103515245 * state + 12345) % 2147483648
            v = (state / 1073741824.0 - 1.0) * noise
            xl += v * mid_l
            state = (1103515245 * state + 12345) % 2147483648
            v = (state / 1073741824.0 - 1.0) * noise
            xr += v * mid_r
        for stage in range(poles):
            v3 = xl - s[0, stage, 1]
            v1 = a1 * s[0, stage, 0] + a2 * v3
            v2 = s[0, stage, 1] + a2 * s[0, stage, 0] + a3 * v3
            s[0, stage, 0] = 2.0 * v1 - s[0, stage, 0]
            s[0, stage, 1] = 2.0 * v2 - s[0, stage, 1]
            xl = v2
            v3 = xr - s[1, stage, 1]
            v1 = a1 * s[1, stage, 0] + a2 * v3
            v2 = s[1, stage, 1] + a2 * s[1, stage, 0] + a3 * v3
            s[1, stage, 0] = 2.0 * v1 - s[1, stage, 0]
            s[1, stage, 1] = 2.0 * v2 - s[1, stage, 1]
            xr = v2
        if sub > 0.0:
            sub_phase += dt * sub_ratio
            if sub_phase >= 1.0:
                sub_phase -= 1.0
            v = math.sin(6.283185307179586 * sub_phase) * sub
            xl += v * mid_l
            xr += v * mid_r
        if drive > 0.0:
            xl = math.tanh(xl * (1.0 + drive))
            xr = math.tanh(xr * (1.0 + drive))
        if hp_c > 0.0:
            hp_l += hp_c * (xl - hp_l)
            hp_r += hp_c * (xr - hp_r)
            xl -= hp_l
            xr -= hp_r
        amp = a * level
        if n - i < 96:
            amp *= (n - i) / 96.0
        out[at + i, 0] += xl * amp
        out[at + i, 1] += xr * amp


@njit(cache=True, fastmath=True)
def _keys(out, at, hold, tail, freq, level, pan, p):
    """One note of a voice made of sines: one bending another (which is how an electric piano,
    a bell and a marimba are made), with two overtones of its own."""
    ratio, index, index_decay, index_sustain = p[0], p[1], p[2], p[3]
    attack, decay, sustain, release = p[4], p[5], p[6], p[7]
    second, third, detune, width = p[8], p[9], p[10], p[11]
    total = out.shape[0]
    n = hold + tail
    if at < 0 or at >= total or n <= 0:
        return
    if at + n > total:
        n = total - at
    rate = 48000.0
    two_pi = 6.283185307179586
    up = 2.0 ** (detune / 1200.0)
    angle = (pan + 1.0) * 0.7853981633974483
    gl, gr = math.cos(angle), math.sin(angle)
    # Two copies a shade apart, one a little to each side: that is the width.
    l1 = gl * (1.0 + width) * 0.5
    r1 = gr * (1.0 - width) * 0.5
    l2 = gl * (1.0 - width) * 0.5
    r2 = gr * (1.0 + width) * 0.5
    c1 = c2 = m1 = m2 = 0.0
    step1 = two_pi * freq / up / rate
    step2 = two_pi * freq * up / rate
    idx = index
    i_mul = math.exp(-1.0 / (max(index_decay, 1e-4) * rate))
    a = 0.0
    a_step = 1.0 / (max(attack, 1e-4) * rate)
    d_mul = math.exp(-1.0 / (max(decay, 1e-4) * rate))
    r_mul = math.exp(-1.0 / (max(release, 1e-4) * rate))
    rising = True
    for i in range(n):
        if i < hold:
            if rising:
                a += a_step
                if a >= 1.0:
                    a = 1.0
                    rising = False
            else:
                a = sustain + (a - sustain) * d_mul
        else:
            a *= r_mul
        idx = index_sustain + (idx - index_sustain) * i_mul
        c1 += step1
        c2 += step2
        m1 += step1 * ratio
        m2 += step2 * ratio
        if c1 > two_pi:
            c1 -= two_pi
        if c2 > two_pi:
            c2 -= two_pi
        if m1 > two_pi:
            m1 -= two_pi
        if m2 > two_pi:
            m2 -= two_pi
        v1 = math.sin(c1 + idx * math.sin(m1)) + second * math.sin(2.0 * c1) + third * math.sin(3.0 * c1)
        v2 = math.sin(c2 + idx * math.sin(m2)) + second * math.sin(2.0 * c2) + third * math.sin(3.0 * c2)
        amp = a * level
        if n - i < 96:
            amp *= (n - i) / 96.0
        out[at + i, 0] += (v1 * l1 + v2 * l2) * amp
        out[at + i, 1] += (v1 * r1 + v2 * r2) * amp


@njit(cache=True, fastmath=True)
def _string(out, at, n, freq, level, pan, sustain, bright, body, seed):
    """One plucked string: a burst of noise going round a loop as long as one turn of the note,
    losing its top a little each time round."""
    total = out.shape[0]
    if at < 0 or at >= total or n <= 0:
        return
    if at + n > total:
        n = total - at
    rate = 48000.0
    c = 0.35 + 0.6 * bright                               # how much top the loop keeps
    period = rate / freq - (1.0 - c) / c                  # the loop's own filter is a little slow: allow for it
    size = int(period) + 2
    buffer = np.zeros(size)
    state = (seed * 2654435761 + 31) % 2147483648
    low = 0.0
    mean = 0.0
    pluck = int(period)
    for i in range(pluck):
        state = (1103515245 * state + 12345) % 2147483648
        low += (0.25 + 0.7 * body) * ((state / 1073741824.0 - 1.0) - low)
        buffer[i] = low
        mean += low
    mean /= max(pluck, 1)
    for i in range(pluck):
        buffer[i] -= mean
    gain = 10.0 ** (-3.0 / (freq * max(sustain, 0.05)))   # each turn loses this much: gone in `sustain` seconds
    angle = (pan + 1.0) * 0.7853981633974483
    gl, gr = math.cos(angle) * level, math.sin(angle) * level
    write = pluck
    kept = 0.0
    for i in range(n):
        where = write - period
        while where < 0.0:
            where += size
        first = int(where)
        part = where - first
        second = first + 1
        if second >= size:
            second -= size
        if first >= size:
            first -= size
        value = buffer[first] * (1.0 - part) + buffer[second] * part
        kept += c * (value - kept)
        value = kept * gain
        buffer[write] = value
        write += 1
        if write >= size:
            write = 0
        amp = 1.0
        if n - i < 256:
            amp = (n - i) / 256.0
        if i < 24:
            amp *= i / 24.0
        out[at + i, 0] += value * gl * amp
        out[at + i, 1] += value * gr * amp


@njit(cache=True, fastmath=True)
def _place(out, at, sample, gl, gr, step):
    """A recording laid down at `at`, played `step` times as fast (which also raises it)."""
    total = out.shape[0]
    length = sample.shape[0]
    n = int((length - 1) / step)
    if at < 0 or at >= total:
        return
    if at + n > total:
        n = total - at
    for i in range(n):
        where = i * step
        first = int(where)
        part = where - first
        value = sample[first] * (1.0 - part) + sample[first + 1] * part
        out[at + i, 0] += value * gl
        out[at + i, 1] += value * gr


@njit(cache=True, fastmath=True)
def _delay(x, left, right, feedback, damp, mix, cross):
    """An echo: each side comes back after its own number of samples, again and again, darker
    each time, and (with `cross`) from the other side."""
    n = x.shape[0]
    out = x.copy()
    bl = np.zeros(left)
    br = np.zeros(right)
    il = ir = 0
    ll = lr = 0.0
    for i in range(n):
        wl = bl[il]
        wr = br[ir]
        ll += damp * (wl - ll)
        lr += damp * (wr - lr)
        bl[il] = x[i, 0] + feedback * (cross * lr + (1.0 - cross) * ll)
        br[ir] = x[i, 1] + feedback * (cross * ll + (1.0 - cross) * lr)
        il += 1
        if il >= left:
            il = 0
        ir += 1
        if ir >= right:
            ir = 0
        out[i, 0] += mix * wl
        out[i, 1] += mix * wr
    return out


@njit(cache=True, fastmath=True)
def _chorus(x, rate_hz, depth, base, mix):
    """Two copies of the sound, each a few thousandths of a second behind and drifting."""
    n = x.shape[0]
    out = x.copy()
    size = int((base + depth) * 48000.0) + 8
    buffer = np.zeros((size, 2))
    write = 0
    two_pi = 6.283185307179586
    for i in range(n):
        buffer[write, 0] = x[i, 0]
        buffer[write, 1] = x[i, 1]
        for side in range(2):
            lfo = math.sin(two_pi * rate_hz * i / 48000.0 + side * 1.9)
            lfo2 = math.sin(two_pi * rate_hz * 0.71 * i / 48000.0 + side * 2.7 + 1.0)
            wet = 0.0
            for which in range(2):
                behind = (base + depth * 0.5 * (1.0 + (lfo if which == 0 else lfo2))) * 48000.0
                where = write - behind
                if where < 0.0:
                    where += size
                first = int(where)
                part = where - first
                # (A hair under nought, brought round, can come out as the size itself.)
                if first >= size:
                    first -= size
                second = first + 1
                if second >= size:
                    second -= size
                wet += buffer[first, side] * (1.0 - part) + buffer[second, side] * part
            out[i, side] += mix * 0.5 * wet
        write += 1
        if write >= size:
            write = 0
    return out


@njit(cache=True, fastmath=True)
def _sweep(x, cutoff, res, mode):
    """A filter whose corner moves: `cutoff` gives it in Hz for every sample."""
    n = x.shape[0]
    out = np.empty_like(x)
    q = 1.0 / (0.5 + res * 9.0)
    s = np.zeros((2, 2))
    g = a1 = a2 = a3 = 0.0
    for i in range(n):
        if i % 16 == 0:
            fc = cutoff[i]
            if fc > 19000.0:
                fc = 19000.0
            if fc < 20.0:
                fc = 20.0
            g = math.tan(3.141592653589793 * fc / 48000.0)
            a1 = 1.0 / (1.0 + g * (g + q))
            a2 = g * a1
            a3 = g * a2
        for side in range(2):
            v3 = x[i, side] - s[side, 1]
            v1 = a1 * s[side, 0] + a2 * v3
            v2 = s[side, 1] + a2 * s[side, 0] + a3 * v3
            s[side, 0] = 2.0 * v1 - s[side, 0]
            s[side, 1] = 2.0 * v2 - s[side, 1]
            if mode == 0:
                out[i, side] = v2
            elif mode == 1:
                out[i, side] = x[i, side] - q * v1 - v2
            else:
                out[i, side] = v1
    return out


# ---------------------------------------------------------------------------------------------
# Patches: what an instrument is
# ---------------------------------------------------------------------------------------------
@dataclass
class Patch:
    """A subtractive voice: oscillators, an envelope, a filter with an envelope of its own."""
    wave: int = SAW
    voices: int = 1                # how many copies of the oscillator, a shade apart
    detune: float = 0.0            # how far apart, in cents from the lowest to the highest
    spread: float = 0.0            # how far to the sides the copies sit, 0 to 1
    attack: float = 0.005
    decay: float = 0.2
    sustain: float = 0.7
    release: float = 0.15
    cutoff: float = 8000.0         # the filter's corner at middle C, in Hz
    env: float = 0.0               # how far the filter opens at the start of the note, in octaves
    env_decay: float = 0.2         # ...and how fast it closes again
    res: float = 0.15              # how much the filter rings at its corner, 0 to 1
    follow: float = 0.5            # how far the corner follows the note up the keyboard
    sub: float = 0.0               # a sine under the oscillators...
    sub_ratio: float = 0.5         # ...an octave below them, or (1.0) on the note itself, which is what a bass wants
    noise: float = 0.0             # breath
    drive: float = 0.0             # grit
    vib_rate: float = 0.0
    vib_depth: float = 0.0         # cents
    vib_delay: float = 0.2
    b_level: float = 0.0           # a second oscillator in the middle
    b_ratio: float = 2.0           # ...at this many times the pitch
    poles: int = 1                 # 1: a gentle filter; 2: a steep one
    b_wave: int = SQUARE
    highpass: float = 0.0          # takes the bottom off, in Hz
    glide: float = 0.0             # seconds to slide from the note before

    def numbers(self) -> np.ndarray:
        return np.array([self.wave, self.voices, self.detune, self.spread, self.attack, self.decay, self.sustain,
                         self.release, self.cutoff, self.env, self.env_decay, self.res, self.follow, self.sub, self.noise,
                         self.drive, self.vib_rate, self.vib_depth, self.vib_delay, self.b_level, self.b_ratio, self.poles,
                         self.b_wave, self.highpass, self.glide, self.sub_ratio], dtype=np.float64)

    @property
    def tail(self) -> float:
        return min(6.0 * self.release + 0.02, 6.0)


@dataclass
class Keys:
    """A voice of sines: one bending another."""
    ratio: float = 1.0             # the bending sine's pitch, as a multiple of the note's
    index: float = 1.5             # how hard it bends at the start
    index_decay: float = 0.3
    index_sustain: float = 0.2     # ...and once the note has settled
    attack: float = 0.003
    decay: float = 0.8
    sustain: float = 0.0
    release: float = 0.2
    second: float = 0.0            # the note's own second and third overtones
    third: float = 0.0
    detune: float = 4.0            # cents between the two copies
    width: float = 0.6

    def numbers(self) -> np.ndarray:
        return np.array([self.ratio, self.index, self.index_decay, self.index_sustain, self.attack, self.decay,
                         self.sustain, self.release, self.second, self.third, self.detune, self.width], dtype=np.float64)

    @property
    def tail(self) -> float:
        return min(6.0 * self.release + 0.02, 6.0)


@dataclass
class String:
    """A plucked string."""
    sustain: float = 1.5           # seconds for it to die away
    bright: float = 0.6            # how much top it keeps as it rings
    body: float = 0.7              # how bright the pluck itself is


def frames(seconds: float) -> int:
    return int(round(seconds * RATE))


def blank(seconds: float) -> np.ndarray:
    return np.zeros((frames(seconds), 2), dtype=np.float32)


def play(out: np.ndarray, patch: Patch | Keys | String, at: float, length: float, pitch: float, level: float = 0.5,
         pan: float = 0.0, seed: int = 0, glide_from: float | None = None, bright: float = 1.0) -> None:
    """Adds one note to `out`: `at` and `length` in seconds, `pitch` as MIDI. `bright` (0 to 1)
    closes a subtractive voice's filter by up to three octaves and softens a string or a bell,
    which is how one instrument is made to play far away or close up."""
    start, hold = frames(at), max(frames(length), 1)
    if isinstance(patch, Patch):
        numbers = patch.numbers()
        numbers[8] = patch.cutoff * 2.0 ** (-3.0 * (1.0 - bright))
        _voice(out, start, hold, frames(patch.tail), hz(pitch), hz(glide_from) if glide_from is not None and patch.glide > 0 else 0.0,
               level, pan, numbers, seed)
    elif isinstance(patch, Keys):
        numbers = patch.numbers()
        numbers[1] = patch.index * (0.35 + 0.65 * bright)
        _keys(out, start, hold, frames(patch.tail), hz(pitch), level, pan, numbers)
    else:
        _string(out, start, frames(min(max(length, 0.05) + patch.sustain, patch.sustain * 1.6)), hz(pitch), level, pan,
                patch.sustain, patch.bright * (0.45 + 0.55 * bright), patch.body * (0.5 + 0.5 * bright), seed)


# ---------------------------------------------------------------------------------------------
# Drums
# ---------------------------------------------------------------------------------------------
# The drum machines' sounds, by what the writers call them: the file under TR8/ for each machine
# that has one. A machine without a sound takes it from the first machine in the row that has.
_FILES = {
    "kick": {"909": "BD/004_909_Bass_Drum_1", "808": "BD/001_808_Bass_Drum_1", "707": "BD/009_707_Bass_Drum_1", "606": "BD/015_606_Bass_Drum_1"},
    "kick2": {"909": "BD/005_909_Bass_Drum_2", "808": "BD/002_808_Bass_Drum_2", "707": "BD/010_707_Bass_Drum_2", "606": "BD/016_606_Bass_Drum_2"},
    "punch": {"909": "BD/012_909_AttackBD_1", "808": "BD/003_808_Bass_Drum_3", "707": "BD/011_707_Bass_Drum_3", "606": "BD/017_606_Bass_Drum_3"},
    "boom": {"808": "BD/007_808_Bass_Drum_Long_1"},
    "snare": {"909": "SD/005_909_Snare_Drum_1", "808": "SD/001_808_Snare_Drum_1", "707": "SD/008_707_Snare_Dum_1", "606": "SD/013_606_Snare_Drum_1"},
    "snare2": {"909": "SD/006_909_Snare_Drum_2", "808": "SD/002_808_Snare_Drum_2", "707": "SD/009_707_Snare_Dum_2", "606": "SD/014_606_Snare_Drum_2"},
    "crack": {"909": "SD/011_909_AttackSD_1", "808": "SD/004_808_Snare_Drum_4", "707": "SD/010_707_Snare_Dum_3", "606": "SD/016_606_Snare_Drum_4"},
    "clap": {"909": "PERC/019_909_Hand_Clap", "808": "PERC/017_808_Hand_Clap", "707": "PERC/021_707_Hand_Clap"},
    "clap2": {"909": "PERC/020_909_Hand_Clap_Long", "808": "PERC/022_808_Noise_Clap"},
    "snap": {"808": "PERC/024_808_Finger_Snap"},
    "hat": {"909": "HATS/008_909_Closed_HiHat", "808": "HATS/002_808_Closed_HiHat", "707": "HATS/012_707_Closed_HiHat", "606": "HATS/014_606_Closed_HiHat"},
    "hat2": {"909": "HATS/010_909_Closed_HiHat_Short", "808": "HATS/004_808_Closed_HiHat_Short", "606": "HATS/016_606_Closed_HiHat_Long"},
    "open": {"909": "HATS/007_909_Open_HiHat", "808": "HATS/001_808_Open_HiHat", "707": "HATS/011_707_Open_HiHat", "606": "HATS/013_606_Open_HiHat"},
    "open2": {"909": "HATS/009_909_Open_HiHat_Short", "808": "HATS/003_808_Open_HiHat_Short"},
    "crash": {"909": "HATS/020_909_Crash_Cymbal", "808": "HATS/017_808_Crash_Cymbal", "707": "HATS/022_707_Crash_Cymbal", "606": "HATS/024_606_Cymbal"},
    "ride": {"909": "HATS/026_909_Ride_Cymbal", "707": "HATS/028_707_Ride_Cymbal"},
    "rim": {"909": "PERC/009_909_Rim_Shot", "808": "PERC/008_808_Rim_Shot", "707": "PERC/012_707_Rim_Shot"},
    "clave": {"808": "PERC/010_808_Claves_1"},
    "cowbell": {"808": "PERC/033_808_Cowbell"},
    "maracas": {"808": "PERC/026_808_Maracas"},
    "cabasa": {"727": "PERC/028_727_Cabasa"},
    "tambourine": {"707": "PERC/036_707_Tambourine"},
    "conga_low": {"727": "PERC/001_727_Low_Conga", "808": "TOMS/019_808_Low_Conga"},
    "conga_high": {"727": "PERC/002_727_Open_High_Conga", "808": "TOMS/021_808_High_Conga"},
    "conga_mute": {"727": "PERC/003_727_Mute_High_Conga", "808": "TOMS/023_808_Mid_Conga_Short"},
    "bongo_low": {"727": "PERC/006_727_Low_Bongo"},
    "bongo_high": {"727": "PERC/007_727_High_Bongo"},
    "timbale_low": {"727": "PERC/004_727_Low_Timbale"},
    "timbale_high": {"727": "PERC/005_727_High_Timbale"},
    "agogo_low": {"727": "PERC/014_727_Agogo_Low"},
    "agogo_high": {"727": "PERC/016_727_Agogo_High"},
    "quijada": {"727": "PERC/031_727_Quijada"},
    "whistle": {"727": "PERC/029_727_Short_Whistle"},
    "chime": {"727": "PERC/035_727_Star_Chime"},
    "tom_low": {"909": "TOMS/010_909_Low_Tom", "808": "TOMS/001_808_Low_Tom", "707": "TOMS/025_707_Low_Tom", "606": "TOMS/035_606_Low_Tom"},
    "tom_mid": {"909": "TOMS/011_909_Mid_Tom", "808": "TOMS/002_808_Mid_Tom", "707": "TOMS/026_707_Mid_Tom", "606": "TOMS/036_606_High_Tom"},
    "tom_high": {"909": "TOMS/012_909_High_Tom", "808": "TOMS/003_808_High_Tom", "707": "TOMS/027_707_High_Tom"},
}
_loaded: dict[tuple[str, str], np.ndarray] = {}


def _noise(seconds: float, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(int(seconds * RATE))


def _made(name: str) -> np.ndarray:
    """A drum made here, for a machine whose recordings are not on this one."""
    t = np.arange(int(1.2 * RATE)) / RATE
    band = lambda low, high, x: sosfilt(butter(2, [low, high], "band", fs=RATE, output="sos"), x)       # noqa: E731
    over = lambda low, x: sosfilt(butter(2, low, "high", fs=RATE, output="sos"), x)                    # noqa: E731
    if name in ("kick", "kick2", "punch", "boom"):
        long = 0.5 if name == "boom" else 0.2
        phase = 2 * np.pi * np.cumsum(46.0 + 130.0 * np.exp(-t / 0.03)) / RATE
        out = np.sin(phase) * np.exp(-t / long) + 0.25 * over(2000, _noise(1.2, 1)) * np.exp(-t / 0.003)
    elif name.startswith("snare") or name == "crack":
        out = 0.6 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.07) + 0.7 * band(900, 7000, _noise(1.2, 2)) * np.exp(-t / 0.12)
    elif name.startswith("clap") or name == "snap":
        bursts = sum(np.where(t >= d, np.exp(-(t - d) / 0.008), 0.0) for d in (0.0, 0.011, 0.023)) + np.where(t >= 0.03, np.exp(-(t - 0.03) / 0.09), 0.0)
        out = band(900, 3500, _noise(1.2, 3)) * bursts
    elif name in ("hat", "hat2", "maracas", "cabasa", "tambourine"):
        out = over(7000, _noise(1.2, 4)) * np.exp(-t / (0.03 if name != "tambourine" else 0.08))
    elif name in ("open", "open2", "ride", "crash", "chime"):
        out = over(6000, _noise(1.2, 5)) * np.exp(-t / {"open": 0.2, "open2": 0.1, "ride": 0.4, "crash": 0.6, "chime": 0.7}[name])
    elif name.startswith("tom") or name.startswith("conga") or name.startswith("bongo") or name.startswith("timbale"):
        pitch = {"tom_low": 90, "tom_mid": 130, "tom_high": 180, "conga_low": 200, "conga_high": 320, "conga_mute": 330,
                 "bongo_low": 380, "bongo_high": 520, "timbale_low": 300, "timbale_high": 440}[name]
        out = np.sin(2 * np.pi * np.cumsum(pitch * (1 + 0.5 * np.exp(-t / 0.02))) / RATE) * np.exp(-t / (0.25 if name.startswith("tom") else 0.1))
    else:                                # rim, clave, cowbell, agogo, quijada, whistle: a short knock at some pitch
        pitch = {"rim": 1700, "clave": 2500, "cowbell": 560, "agogo_low": 700, "agogo_high": 1000, "quijada": 3000, "whistle": 2200}.get(name, 1500)
        out = (np.sin(2 * np.pi * pitch * t) + 0.6 * np.sin(2 * np.pi * pitch * 1.5 * t)) * np.exp(-t / 0.05)
    return (0.89 * out / np.max(np.abs(out))).astype(np.float64)


def drum(name: str, machine: str = "909") -> np.ndarray:
    """One drum sound, mono at 48 kHz, beginning on its first sample and ending when it has died
    away: the recording of `machine` if it has that sound, else of whichever machine does, else
    one made here."""
    if (name, machine) in _loaded:
        return _loaded[(name, machine)]
    if name not in _FILES:
        raise KeyError("No drum called %r" % name)
    have = _FILES[name]
    path = TR8 / ((have.get(machine) or next(iter(have.values()))) + ".wav")
    if path.is_file():
        audio, rate = soundfile.read(str(path), dtype="float64", always_2d=True)
        audio = audio.mean(axis=1)
        if rate != RATE:
            audio = resample_poly(audio, RATE, rate)
        loud = np.abs(audio)
        peak = float(loud.max())
        if peak <= 0:
            raise ValueError("The drum recording %s is silent" % path)
        first = max(int(np.argmax(loud > 0.01 * peak)) - 8, 0)
        last = len(loud) - int(np.argmax(loud[::-1] > 0.002 * peak))
        audio = audio[first:min(last + 480, len(audio))].copy()
        audio[-240:] *= np.linspace(1.0, 0.0, 240)
    else:
        audio = _made(name)
        loud = np.abs(audio)
        last = len(loud) - int(np.argmax(loud[::-1] > 0.002))
        audio = audio[:max(last, 480)].copy()
        audio[-240:] *= np.linspace(1.0, 0.0, 240)
    _loaded[(name, machine)] = np.ascontiguousarray(audio)
    return _loaded[(name, machine)]


def hit(out: np.ndarray, sound: np.ndarray, at: float, level: float = 0.8, pan: float = 0.0, speed: float = 1.0) -> None:
    """Lays a drum down at `at` seconds. `speed` plays it faster and higher, or slower and lower."""
    angle = (min(max(pan, -1.0), 1.0) + 1.0) * math.pi / 4.0
    _place(out, frames(at), sound, math.cos(angle) * level * math.sqrt(2.0), math.sin(angle) * level * math.sqrt(2.0), float(speed))


# ---------------------------------------------------------------------------------------------
# What is done to a whole part
# ---------------------------------------------------------------------------------------------
def echo(audio: np.ndarray, left: float, right: float, *, feedback: float = 0.35, damp: float = 0.35, mix: float = 0.3,
         cross: float = 1.0) -> np.ndarray:
    """An echo in time with the music: `left` and `right` are the two sides' delays in seconds."""
    return _delay(np.ascontiguousarray(audio, dtype=np.float32), max(frames(left), 1), max(frames(right), 1),
                  feedback, damp, mix, cross).astype(np.float32)


def chorus(audio: np.ndarray, *, rate: float = 0.6, depth: float = 0.004, base: float = 0.012, mix: float = 0.5) -> np.ndarray:
    return _chorus(np.ascontiguousarray(audio, dtype=np.float32), rate, depth, base, mix).astype(np.float32)


def sweep(audio: np.ndarray, cutoff: np.ndarray, *, res: float = 0.1, mode: int = LOW) -> np.ndarray:
    """A filter whose corner moves over the part: `cutoff` in Hz, one for every sample."""
    if len(cutoff) != len(audio):
        raise ValueError("A corner for every sample: %d for %d" % (len(cutoff), len(audio)))
    return _sweep(np.ascontiguousarray(audio, dtype=np.float32), np.ascontiguousarray(cutoff, dtype=np.float32), res, mode).astype(np.float32)


def hall(audio: np.ndarray, *, seconds: float = 1.3, wet: float = 0.16, bright: float = 9000.0) -> np.ndarray:
    """The studio's room, at the size of a club: shorter and brighter than the orchestra's hall."""
    return room.add(audio, seconds=seconds, wet=wet, bright=bright)


def pump(length: int, kicks: list[float], *, depth: float = 0.6, hold: float = 0.02, release: float = 0.26) -> np.ndarray:
    """How loud everything but the drums is from moment to moment as it ducks under the kick:
    down by `depth` on each of `kicks` (in seconds) and back up over `release`."""
    gain = np.ones(length, dtype=np.float32)
    held, back = frames(hold), frames(release)
    along = np.linspace(0.0, 1.0, back, dtype=np.float32)
    shape = np.concatenate([np.full(held, 1.0 - depth, dtype=np.float32), 1.0 - depth * (1.0 - along) ** 2.2])
    # It comes down over a few thousandths of a second, not at once: at once is a click.
    down = np.linspace(1.0, 1.0 - depth, 96, dtype=np.float32)
    for kick in kicks:
        at = frames(kick)
        first = max(at - 96, 0)
        gain[first:at] = np.minimum(gain[first:at], down[96 - (at - first):])
        last = min(at + len(shape), length)
        if last > at:
            gain[at:last] = np.minimum(gain[at:last], shape[:last - at])
    return gain


def noise(seconds: float, seed: int) -> np.ndarray:
    """White noise on both sides, each its own."""
    return (np.random.default_rng(seed).standard_normal((frames(seconds), 2)) * 0.25).astype(np.float32)


def level_of(audio: np.ndarray) -> float:
    """How loud a part is where it is playing: the level of its loudest tenths of a second,
    leaving out the stretches where it rests. In dB below full scale."""
    block = RATE // 10
    whole = (len(audio) // block) * block
    if not whole:
        return -120.0
    power = (audio[:whole].astype(np.float64) ** 2).reshape(-1, block, audio.shape[1]).mean(axis=(1, 2))
    loud = power[power > power.max() * 10 ** (-25 / 10)] if power.max() > 0 else power
    return 10.0 * math.log10(float(loud.mean()) + 1e-12) if len(loud) else -120.0


def tame(audio: np.ndarray, over: float = 14.0) -> np.ndarray:
    """A part with its sharpest peaks rounded off: whatever stands more than `over` dB above
    the level the part plays at is bent back towards it. The body of the sound is all but left
    alone (its own crests lose a third of a dB); the spike at the front of a plucked string,
    which is all peak and no loudness, is what goes. Without this one spike decides how loud a whole track can be."""
    level = level_of(audio)
    if level < -100.0:
        return audio
    ceiling = 10.0 ** ((level + over) / 20.0)
    return (ceiling * np.tanh(audio / ceiling)).astype(np.float32)


def warm_up() -> None:
    """Compiles the loops, so that the first note does not wait for it. Call it once before
    starting other processes: they then find the compiled loops ready."""
    out = blank(0.2)
    play(out, Patch(voices=2, detune=10, spread=0.5, sub=0.2, noise=0.01, drive=0.2, vib_rate=5, vib_depth=5, b_level=0.2,
                    poles=2, highpass=80, glide=0.02), 0.0, 0.05, 60, glide_from=58)
    play(out, Keys(), 0.0, 0.05, 60)
    play(out, String(), 0.0, 0.05, 60)
    hit(out, np.ones(64), 0.0)
    echo(out, 0.01, 0.02)
    chorus(out)
    sweep(out, np.full(len(out), 1000.0, dtype=np.float32))
