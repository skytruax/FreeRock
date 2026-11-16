"""Instruments for the sfizz sampler, written from the recordings.

An SFZ file tells a sampler which recording answers to which notes, and how to play it. A
bare mapping (one recording to a note, the same every time) is what makes sampled instruments
sound like a keyboard. What is written here is how sample libraries make a few recordings
sound played:

  a held note swells and fades   the soft and the hard recordings of a bowed or blown note
                                 play together, and controller 1 (which the desk draws under
                                 every line) fades from one to the other, opening a filter as
                                 it rises: louder is brighter, as it is on the instrument
  a section is several players   every note of a string section is three recordings: its own,
                                 and the neighbouring ones bent to the same pitch, a few cents
                                 apart, a little late, to the left and to the right
  no two notes are the same      each note starts a few milliseconds off, a few cents off, a
                                 shade louder or softer; recordings that were made more than
                                 once take turns
  a struck note's strength       fades between the soft and hard recordings instead of
                                 switching, and a soft stroke is duller as well as quieter
  a held note has no end         it goes round the steady middle of the recording, and drifts
                                 slowly in pitch as players do

`held`, `struck` and `kit` return the text of an SFZ file for a patch (studio.samples). The
files are kept in var/reaper/sfz, and can be loaded into sfizz by hand as well.
"""
from __future__ import annotations

from pathlib import Path

import soundfile

from .samples import SAMPLES, Patch, Zone

FOLDER = Path(__file__).resolve().parents[3] / "var" / "reaper" / "sfz"
DYNAMICS = 1                   # the controller that swells and fades held notes


def _head(extra: list[str] | None = None) -> list[str]:
    # hint_ram_based: every recording is read whole when the instrument is loaded, so a render
    # that runs faster than the music never waits for the disk.
    return ["// Written by FreeRock's studio (studio/sfz.py). The recordings are under default_path.",
            "<control>", "default_path=%s/" % SAMPLES, "hint_ram_based=1", "set_cc%d=90" % DYNAMICS,
            "label_cc%d=Dynamics" % DYNAMICS] + (extra or [])


def _layers(zones: list[Zone]) -> dict[int, list[Zone]]:
    """The zones of each recorded note, softest first."""
    by_root: dict[int, list[Zone]] = {}
    for zone in zones:
        by_root.setdefault(zone.root, []).append(zone)
    return {root: sorted(each, key=lambda zone: zone.soft) for root, each in sorted(by_root.items())}


def _fades(count: int, place: int, what: str) -> str:
    """How layer `place` of `count` fades in and out along `what` ("cc1" or "vel")."""
    if count < 2:
        return ""
    width = 127.0 / (count * 2.6)
    out = []
    names = ("xfin_lo%s", "xfin_hi%s", "xfout_lo%s", "xfout_hi%s")
    if place > 0:
        middle = 127.0 * place / count
        out += [names[0] % what + "=%d" % max(round(middle - width), 0), names[1] % what + "=%d" % min(round(middle + width), 127)]
    if place < count - 1:
        middle = 127.0 * (place + 1) / count
        out += [names[2] % what + "=%d" % max(round(middle - width), 0), names[3] % what + "=%d" % min(round(middle + width), 127)]
    return " ".join(out)


def _loop(zone: Zone, file: str) -> str:
    if not zone.loop:
        return ""
    info = soundfile.info(str(SAMPLES / file))
    return "loop_start=%d loop_end=%d" % (int(round(zone.loop / 1000.0 * info.samplerate)), int(zone.until * info.frames) - 1)


def held(patch: Patch, *, players: int = 1, dark: float = 1400.0, opens: float = 4200.0, range_db: float = 16.0,
         drift: float = 3.0, spread: float = 45.0, bite: Patch | None = None) -> str:
    """A bowed or blown instrument. `players` is how many play each note (1 a soloist, 3 a
    section: the others are the neighbouring recordings); `dark` the filter's cutoff in Hz at
    the softest (for the A above middle C: it follows the note) and `opens` how many cents it
    opens by the loudest; `range_db` how much louder the loudest is than the softest on top of
    what the recordings themselves differ by; `bite` a patch of short strokes that is heard at
    the start of a note struck hard (the bow digging in)."""
    rows = _head()
    attack = patch.attack / 1000.0
    rows += ["<global>", "loop_mode=loop_sustain loop_crossfade=0.25",
             # A note begun softly speaks slowly, one begun hard at once. The swell is on the controller.
             "ampeg_attack=%.3f ampeg_vel2attack=%.3f ampeg_release=%.3f" % (attack * 1.7, -attack * 1.45, patch.release / 1000.0),
             "amp_veltrack=18",
             # One draw of the dice for every recording of a note, so that layers fading into each other stay in tune together.
             "pitch_oncc136=5 amp_random=0.8",
             "fil_type=lpf_1p cutoff=%.0f cutoff_cc%d=%.0f fil_keytrack=100 fil_keycenter=69 resonance=0" % (dark, DYNAMICS, opens),
             "volume=%.1f gain_cc%d=%.1f" % (-range_db, DYNAMICS, range_db), "xf_cccurve=power",
             "lfo01_freq=0.19 lfo01_pitch=%.1f lfo01_phase_oncc135=1" % drift]
    layers = _layers(patch.zones)
    roots = list(layers)
    voices = [(0, 0.0, 0.0, 0.0, 0.0)]
    if players >= 2:
        voices.append((1, 8.0, -spread, 0.017, -5.0))
    if players >= 3:
        voices.append((-1, -7.0, spread, 0.029, -5.0))
    for step, tune, pan, late, level in voices:
        for index, root in enumerate(roots):
            # Another player is the neighbouring recording, bent to these notes.
            other = index + step
            if not 0 <= other < len(roots):
                other = index - step
            if not 0 <= other < len(roots):
                other = index
            own, lent = layers[root], layers[roots[other]]
            for place, zone in enumerate(own):
                source = lent[min(place, len(lent) - 1)]
                fade = _fades(len(own), place, "cc%d" % DYNAMICS)
                for turn, file in enumerate(source.files):
                    words = ["<region>", "sample=%s" % file, "lokey=%d hikey=%d pitch_keycenter=%d" % (zone.low, zone.high, source.root),
                             "tune=%d" % round(source.tune + tune), _loop(source, file), fade]
                    if step:
                        words.append("pan=%.0f delay=%.3f volume=%.1f" % (pan, late, level - range_db))
                    if len(source.files) > 1:
                        words.append("seq_length=%d seq_position=%d" % (len(source.files), turn + 1))
                    rows.append(" ".join(word for word in words if word))
    if bite is not None:
        # The start of a hard note: a short stroke under it, heard only when the note is struck hard.
        for zone in bite.zones:
            if zone.hard < 100:
                continue                       # only the hardest strokes
            for turn, file in enumerate(zone.files):
                words = ["<region>", "sample=%s" % file, "lokey=%d hikey=%d pitch_keycenter=%d" % (zone.low, zone.high, zone.root),
                         "tune=%d" % round(zone.tune), "loop_mode=one_shot ampeg_attack=0 ampeg_vel2attack=0 ampeg_release=0.3",
                         "amp_veltrack=100 xfin_lovel=72 xfin_hivel=118 volume=-9 gain_cc%d=0 cutoff=20000 cutoff_cc%d=0" % (DYNAMICS, DYNAMICS)]
                if len(zone.files) > 1:
                    words.append("seq_length=%d seq_position=%d" % (len(zone.files), turn + 1))
                rows.append(" ".join(words))
    return "\n".join(rows) + "\n"


def struck(patch: Patch, *, dull: float = 1500.0, opens: float = 5400.0, players: int = 1, spread: float = 0.0) -> str:
    """A plucked or struck instrument, or one short bow stroke. Left to ring unless the patch
    is held (a piano, a harpsichord: stopped when the key is let go)."""
    rows = _head()
    rows += ["<global>", "loop_mode=%s" % ("no_loop" if patch.held else "one_shot"),
             "ampeg_attack=%.4f ampeg_release=%.3f" % (patch.attack / 1000.0, patch.release / 1000.0),
             "amp_veltrack=72", "pitch_oncc136=4 amp_random=0.7",
             "fil_type=lpf_1p cutoff=%.0f fil_veltrack=%.0f fil_keytrack=100 fil_keycenter=69 resonance=0" % (dull, opens), "xf_velcurve=power"]
    layers = _layers(patch.zones)
    voices = [(0.0, 0.0, 0.0, 0.0)]
    if players >= 2:
        voices += [(11.0, -spread, 0.013, -4.0), (-9.0, spread, 0.024, -4.0)][:players - 1]
    for tune, pan, late, level in voices:
        for root, own in layers.items():
            for place, zone in enumerate(own):
                width = 127.0 / (len(own) * 2.6) if len(own) > 1 else 0.0
                low = 1 if place == 0 else max(round(127.0 * place / len(own) - width), 1)
                high = 127 if place == len(own) - 1 else min(round(127.0 * (place + 1) / len(own) + width), 127)
                fade = _fades(len(own), place, "vel")
                for turn, file in enumerate(zone.files):
                    words = ["<region>", "sample=%s" % file, "lokey=%d hikey=%d pitch_keycenter=%d" % (zone.low, zone.high, zone.root),
                             "lovel=%d hivel=%d" % (low, high), "tune=%d" % round(zone.tune + tune), fade]
                    if zone.gain:
                        words.append("volume=%.1f" % (zone.gain + level))
                    elif level:
                        words.append("volume=%.1f" % level)
                    if tune:
                        words.append("pan=%.0f delay=%.3f" % (pan, late))
                    if len(zone.files) > 1:
                        words.append("seq_length=%d seq_position=%d" % (len(zone.files), turn + 1))
                    rows.append(" ".join(word for word in words if word))
    return "\n".join(rows) + "\n"


def kit(strokes: list[tuple[int, Patch]], *, chokes: dict[int, int] | None = None) -> str:
    """A drum kit: each stroke's patch on its own note. `chokes` puts notes into groups that
    silence each other (an open hi-hat is stopped by a closed one): note -> group number."""
    rows = _head()
    rows += ["<global>", "loop_mode=one_shot", "amp_veltrack=85", "pitch_random=9 amp_random=1.0 delay_random=0.004",
             "fil_type=lpf_2p cutoff=3000 fil_veltrack=3800 resonance=0", "ampeg_release=0.6"]
    for note, patch in strokes:
        own = sorted(patch.zones, key=lambda zone: zone.soft)
        for zone in own:
            for turn, file in enumerate(zone.files):
                words = ["<region>", "sample=%s" % file, "key=%d pitch_keytrack=0" % note, "lovel=%d hivel=%d" % (zone.soft, zone.hard)]
                if len(zone.files) > 1:
                    words.append("seq_length=%d seq_position=%d" % (len(zone.files), turn + 1))
                if chokes and note in chokes:
                    words.append("group=%d off_by=%d off_mode=fast" % (chokes[note], chokes[note]))
                rows.append(" ".join(words))
    return "\n".join(rows) + "\n"


def layered(parts: list[tuple[Patch, float, float]], low: int, high: int, *, players: int = 3, spread: float = 55.0) -> str:
    """Several drums struck as one, by several players: a war-drum ensemble. Each part is a
    patch of one drum's strokes (answering to one note), how many semitones lower it is played
    than recorded, and its level in dB. Every written note from `low` to `high` strikes all of
    them, shifted with the note (so a lower note is a bigger drum), each player a little apart
    in time, pitch and place."""
    rows = _head()
    rows += ["<global>", "loop_mode=one_shot", "amp_veltrack=80", "amp_random=1.2", "fil_type=lpf_2p cutoff=1600 fil_veltrack=5200 resonance=0",
             "ampeg_release=1.2"]
    seats = [(0.0, 0.0, 0.0, 0.0), (-28.0, -spread, 0.014, -3.5), (22.0, spread, 0.026, -3.5), (-45.0, -spread * 0.5, 0.037, -5.0)][:max(players, 1)]
    for patch, lower, level in parts:
        own = sorted(patch.zones, key=lambda zone: zone.soft)
        for tune, pan, late, down in seats:
            for zone in own:
                for turn, file in enumerate(zone.files):
                    words = ["<region>", "sample=%s" % file, "lokey=%d hikey=%d pitch_keycenter=%d" % (low, high, zone.root + round(lower)),
                             "lovel=%d hivel=%d" % (zone.soft, zone.hard), "tune=%d" % round(tune), "volume=%.1f" % (level + down),
                             "pan=%.0f delay=%.3f delay_random=0.012 pitch_random=18" % (pan, late)]
                    if len(zone.files) > 1:
                        words.append("seq_length=%d seq_position=%d" % (len(zone.files), turn + 1))
                    rows.append(" ".join(words))
    return "\n".join(rows) + "\n"


def write(name: str, text: str) -> Path:
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / (name + ".sfz")
    path.write_text(text, encoding="utf-8")
    return path
