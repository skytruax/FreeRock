"""Instruments for the sfizz sampler, written from the recordings.

An SFZ file tells a sampler which recording answers to which notes, and how to play it. A
bare mapping (one recording to a note, the same every time) is what makes sampled instruments
sound like a keyboard. What is written here is how sample libraries make a few recordings
sound played:

  a held note swells and fades   the soft and the hard recordings of a bowed or blown note
                                 play together, and controller 1 (which the desk draws under
                                 every line) fades from one to the other. Only at its softest
                                 is a note also a little duller than it was recorded
  a soloist can be several       a note can be played by its own recording and the neighbouring
                                 ones bent to the same pitch, a few cents apart, a little late,
                                 to the left and to the right. A recording of a whole section
                                 is left as it is: it has its players in it already
  no two notes are the same      each note starts a few milliseconds off, a few cents off, a
                                 shade louder or softer; recordings that were made more than
                                 once take turns
  a struck note's strength       fades between the soft and hard recordings instead of
                                 switching, and a soft stroke is duller as well as quieter
  a held note has no end         it goes round the steady middle of the recording, and drifts
                                 slowly in pitch as players do
  a slur is not two notes        in a line of single notes, a note begun while the last is
                                 still held joins it: it comes in without its own start, as
                                 the next note under one bow or in one breath does

`held`, `struck` and `kit` return the text of an SFZ file for a patch (studio.samples). The
files are kept in var/reaper/sfz, and can be loaded into sfizz by hand as well.

The filters here are gentle on purpose. They used to follow the note (so a cello's or a
bass's top was cut two octaves lower than a violin's) and stand half shut at a middling
strength, and the whole orchestra came out dull: measured against recordings that were liked,
ten to eighteen decibels short above 2.5 kHz (2026-11-16). The breath, the rosin and the
stick are up there, and they do not go away when a player plays softly.
"""
from __future__ import annotations

from pathlib import Path

import os

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


def held(patch: Patch, *, players: int = 1, blend: bool | None = None, dark: float = 3200.0, opens: float = 3600.0, range_db: float = 16.0,
         drift: float = 3.0, spread: float = 45.0, bite: Patch | None = None, slur: float = 0.0,
         vibrato: tuple[float, float, float] | None = None) -> str:
    """A bowed or blown instrument. `players` is how many play each note (1 the recording as
    it is: a soloist, or a section that was recorded as one; 2 or 3 add the neighbouring
    recordings as further players, which only sounds like more players where the neighbours
    are a semitone away). `blend` says what the soft and the hard recordings of a note do:
    fade into each other as controller 1 moves (several players swelling together; the usual
    for more than one player), or the note's own strength picks one of them for the whole note
    (one player: two recordings of him at once are two players). `dark` is the filter's cutoff
    in Hz at the softest and `opens` how many cents it opens by the loudest (it is past 9 kHz
    by the middle); `range_db` how much louder the loudest is than the softest on top of what
    the recordings themselves differ by; `bite` a patch of short strokes that is heard at the
    start of a note struck hard (the bow digging in).

    `vibrato` (how many times a second, how many cents either way, how many dB) is for a
    recording played dead straight: a held note begins straight and the vibrato comes in
    after a third of a second, as a player's does. A loud brass note held with none at all
    is very nearly a sawtooth wave, and sounds like one.

    With `slur` (seconds), a note begun while another is still held is slurred to it: it
    leaves out that much of the start of its recording and comes in over the same time, so
    the bow or the breath carries on instead of starting again. This is for a line of single
    notes, which the desk writes with each slurred note reaching a little into the next."""
    if blend is None:
        blend = players > 1
    rows = _head()
    attack = patch.attack / 1000.0
    rows += ["<global>", "loop_mode=loop_sustain loop_crossfade=0.25",
             "ampeg_release=%.3f" % (patch.release / 1000.0), "amp_veltrack=18",
             # One draw of the dice for every recording of a note, so that layers fading into each other stay in tune together.
             "pitch_oncc136=5 amp_random=0.8",
             "fil_type=lpf_1p cutoff=%.0f cutoff_cc%d=%.0f resonance=0" % (dark, DYNAMICS, opens),
             "volume=%.1f gain_cc%d=%.1f" % (-range_db, DYNAMICS, range_db), "xf_cccurve=power",
             "lfo01_freq=0.19 lfo01_pitch=%.1f lfo01_phase_oncc135=1" % drift]
    if vibrato:
        rows.append("lfo02_freq=%.2f lfo02_pitch=%.1f lfo02_volume=%.2f lfo02_delay=0.33 lfo02_fade=0.45" % vibrato)
    layers = _layers(patch.zones)
    roots = list(layers)
    voices = [(0, 0.0, 0.0, 0.0, 0.0)]
    if players >= 2:
        voices.append((1, 8.0, -spread, 0.017, -5.0))
    if players >= 3:
        voices.append((-1, -7.0, spread, 0.029, -5.0))
    # A note begun softly speaks slowly, one begun hard at once. The swell is on the controller.
    spoken = "ampeg_attack=%.3f ampeg_vel2attack=%.3f" % (attack * 1.7, -attack * 1.45)
    ways = [("", spoken, 0.0)] if slur <= 0.0 else [("trigger=first", spoken, 0.0), ("trigger=legato", "ampeg_attack=%.3f ampeg_vel2attack=0" % slur, slur)]
    for trigger, speaks, skipped in ways:
        rows.append(" ".join(word for word in ("<group>", trigger, speaks) if word))
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
                    which = _fades(len(own), place, "cc%d" % DYNAMICS) if blend else "lovel=%d hivel=%d" % (zone.soft, zone.hard)
                    for turn, file in enumerate(source.files):
                        words = ["<region>", "sample=%s" % file, "lokey=%d hikey=%d pitch_keycenter=%d" % (zone.low, zone.high, source.root),
                                 "tune=%d" % round(source.tune + tune), _loop(source, file), which]
                        if skipped:
                            words.append("offset=%d" % round(skipped * soundfile.info(str(SAMPLES / file)).samplerate))
                        if step:
                            words.append("pan=%.0f delay=%.3f volume=%.1f" % (pan, late, level - range_db))
                        if len(source.files) > 1:
                            words.append("seq_length=%d seq_position=%d" % (len(source.files), turn + 1))
                        rows.append(" ".join(word for word in words if word))
    if bite is not None:
        # The start of a hard note: a short stroke under it, heard only when the note is struck hard.
        rows.append("<group> trigger=first" if slur > 0.0 else "<group>")
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


def struck(patch: Patch, *, dull: float = 3500.0, opens: float = 3600.0, players: int = 1, spread: float = 0.0) -> str:
    """A plucked or struck instrument, or one short bow stroke. Left to ring unless the patch
    is held (a piano, a harpsichord: stopped when the key is let go)."""
    rows = _head()
    rows += ["<global>", "loop_mode=%s" % ("no_loop" if patch.held else "one_shot"),
             "ampeg_attack=%.4f ampeg_release=%.3f" % (patch.attack / 1000.0, patch.release / 1000.0),
             "amp_veltrack=72", "pitch_oncc136=4 amp_random=0.7",
             "fil_type=lpf_1p cutoff=%.0f fil_veltrack=%.0f resonance=0" % (dull, opens), "xf_velcurve=power"]
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


# One sweep of a brush, cut from a recording of it going round and round: in over six hundredths of a second, away over half a second.
SWEEP = "ampeg_attack=0.06 ampeg_hold=0.04 ampeg_decay=0.55 ampeg_sustain=0"
SWEPT_RATE = 44100             # the rate those recordings were made at (a place in them is counted in frames)


def kit(strokes: list[tuple[int, Patch]], *, chokes: dict[int, int] | None = None, cuts: dict[int, tuple[float, ...]] | None = None) -> str:
    """A drum kit: each stroke's patch on its own note. `chokes` puts notes into groups that
    silence each other (an open hi-hat is stopped by a closed one): note -> group number.
    `cuts` are the notes whose recordings go on (a brush stirred round a snare) and where in
    them, in seconds, a stroke is cut from: it comes in, swells and dies away (SWEEP), each
    time from another place in another of them."""
    rows = _head()
    rows += ["<global>", "loop_mode=one_shot", "amp_veltrack=85", "pitch_random=9 amp_random=1.0 delay_random=0.004",
             "fil_type=lpf_1p cutoff=5000 fil_veltrack=3000 resonance=0", "ampeg_release=0.6"]
    for note, patch in strokes:
        own = sorted(patch.zones, key=lambda zone: zone.soft)
        for zone in own:
            starts = (cuts or {}).get(note, ())
            strokes_of = [(start, file) for start in starts or (0.0,) for file in zone.files]
            for turn, (start, file) in enumerate(strokes_of):
                words = ["<region>", "sample=%s" % file, "key=%d pitch_keytrack=0" % note, "lovel=%d hivel=%d" % (zone.soft, zone.hard)]
                if len(strokes_of) > 1:
                    words.append("seq_length=%d seq_position=%d" % (len(strokes_of), turn + 1))
                if zone.gain:
                    words.append("volume=%.1f" % zone.gain)
                if starts:
                    words.append("offset=%d %s" % (round(start * SWEPT_RATE), SWEEP))
                if chokes and note in chokes:
                    words.append("group=%d off_by=%d off_mode=fast" % (chokes[note], chokes[note]))
                rows.append(" ".join(words))
    return "\n".join(rows) + "\n"


def layered(parts: list[tuple[Patch, int, float, int, int]], *, players: int = 3, spread: float = 55.0, track: float = 35.0) -> str:
    """Several drums struck by several players: a war-drum ensemble. Each part is one drum: a
    patch of its strokes, the written note at which it sounds as it was recorded, its level in
    dB, and the lowest and highest written note that strike it (so the low notes are the big
    drums and the high ones the small, and a note between two drums strikes both). A drum
    moves only `track` cents for each written note away from its own: a drum tuned far from
    where it was recorded is all boom and no skin. Each player strikes a different recording
    of the stroke, a little apart in time and place: three drummers, not one drum in a chorus."""
    rows = _head()
    rows += ["<global>", "loop_mode=one_shot", "amp_veltrack=85", "amp_random=1.0", "pitch_keytrack=%.0f" % track, "ampeg_release=1.5"]
    seats = [(0.0, 0.0, 0.0, 0.0), (-9.0, -spread, 0.012, -2.5), (7.0, spread, 0.021, -2.5), (-14.0, -spread * 0.5, 0.03, -4.0)][:max(players, 1)]
    for patch, centre, level, low, high in parts:
        own = sorted(patch.zones, key=lambda zone: zone.soft)
        for seat, (tune, pan, late, down) in enumerate(seats):
            for zone in own:
                count = len(zone.files)
                for turn in range(count):
                    words = ["<region>", "sample=%s" % zone.files[(turn + seat) % count], "lokey=%d hikey=%d pitch_keycenter=%d" % (low, high, centre),
                             "lovel=%d hivel=%d" % (zone.soft, zone.hard), "tune=%d" % round(tune), "volume=%.1f" % (level + down),
                             "pan=%.0f delay=%.3f delay_random=0.008 pitch_random=6" % (pan, late)]
                    if count > 1:
                        words.append("seq_length=%d seq_position=%d" % (count, turn + 1))
                    rows.append(" ".join(words))
    return "\n".join(rows) + "\n"


def write(name: str, text: str) -> Path:
    """Keeps an instrument's text under its name. A file that says the same already is not
    touched: the sampler watches its instrument's file and loads it again when it changes,
    and a render in which that happens stops dead (found 2026-11-16: one instrument played
    alone for the listening page while a whole piece was rendering). A file that does change
    is put in place whole."""
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / (name + ".sfz")
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return path
    fresh = FOLDER / ("%s.%d.part" % (name, os.getpid()))
    fresh.write_text(text, encoding="utf-8")
    os.replace(fresh, path)
    return path
