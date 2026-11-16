"""Every instrument on its own, on one page to listen to.

    cd app && uv run --no-sync python ../tools/audition.py                 every instrument
    cd app && uv run --no-sync python ../tools/audition.py --only drums    only the rows with "drums" in their name
    cd app && uv run --no-sync python ../tools/audition.py --keep          call what is there now "before", then render

Nobody can judge an instrument inside a full piece, and the studio cannot hear at all. So each
instrument plays a short phrase alone, and the page has it up to three ways:

    the recording   the bare recording: one track, no effects, no room (where there is one)
    before          how the instrument sounded the last time the page was kept (--keep)
    now             what the pieces use now: its players, its effects, its seat, the hall

Beside listening, each "now" is measured against the same instrument among the recordings
that were liked (studio.ear), and the difference is printed: plus is more than there, by octave
from 20 Hz to 20 kHz. The page is var/listen/instruments/index.html
(http://<this machine>:8765/listen/instruments/index.html).
"""
from __future__ import annotations

import argparse
import html
import json
import sys

import numpy as np
import soundfile

from freerock.studio import desk, ear, reaper, sfz, sounds
from freerock.studio.score import Note, Voice

OUT = desk.VAR / "listen" / "instruments"
WORK = desk.VAR / "reaper" / "audition"
BPM = 80.0
HALL = 2.1
TUNE = [(0, 2, 0, 0.45), (2, 1, 3, 0.5), (3, 1, 2, 0.55), (4, 3, 7, 0.75), (7, 1, 5, 0.7), (8, 1, 3, 0.65), (9, 1, 2, 0.6), (10, 1, 0, 0.55),
        (11, 1, -2, 0.5), (12, 4, 0, 0.4)]             # (beat, beats, semitones above the first note, strength): a phrase that rises and falls
QUICK = [(16 + step * 0.5, 0.22, (0, 3, 7, 12, 7, 3, 0, -5)[step % 8], 0.55 + 0.1 * (step % 4 == 0)) for step in range(16)]
CHORDS = ((0, 7, 12, 15), (-4, 3, 8, 12), (-9, -2, 3, 7), (-2, 5, 10, 14))


def phrase(first: int, quick: bool = True) -> list[Note]:
    notes = [Note(beat, long * 0.98, first + step, loud) for beat, long, step, loud in TUNE]
    if quick:
        notes += [Note(beat, long, first + step, loud) for beat, long, step, loud in QUICK]
    return notes


def chords(low: int, loud: float = 0.45) -> list[Note]:
    return [Note(bar * 4, 3.9, low + step, loud + 0.1 * bar) for bar, steps in enumerate(CHORDS) for step in steps]


def stabs(low: int) -> list[Note]:
    """Short chords, hard: what brass and strings do at a moment."""
    out = []
    for bar, steps in enumerate(CHORDS):
        for beat in (0, 1.5, 2.5, 3):
            out += [Note(bar * 4 + beat, 0.3, low + step, 0.8 + 0.05 * bar) for step in steps]
    return out


def plucked(low: int) -> list[Note]:
    return [Note(bar * 4 + index * 0.5, 0.4, low + steps[index % 4] + (12 if index >= 4 else 0), 0.5 + 0.05 * (index % 4 == 0))
            for bar, steps in enumerate(CHORDS) for index in range(8)]


def strokes() -> list[Note]:
    """War drums as the writer writes them: the biggest on the bar, the next on the strong
    beat, pickups and a quiet drive between, then a run down the drums and a roll that grows."""
    out = []
    for bar in range(4):
        hits = [(0, 36, 1.0), (2, 38, 0.85), (1.5, 41, 0.6), (3.5, 41, 0.6), (3.75, 41, 0.7)]
        hits += [(on, 43 if on % 1 == 0 else 41, 0.4) for on in (0.5, 1.0, 2.5, 3.0)]
        if bar == 3:
            hits = [(0, 36, 1.0), (2, 47, 0.65), (2.5, 45, 0.7), (3, 43, 0.75), (3.5, 41, 0.8)]
        out += [Note(bar * 4 + on, 0.25, pitch, min(loud * (0.8 + 0.07 * bar), 1.0)) for on, pitch, loud in hits]
    out += [Note(16 + step * 0.25, 0.25, (38, 41)[step % 2], 0.3 + 0.045 * step) for step in range(16)]        # a roll that grows
    out += [Note(20, 1.0, pitch, loud) for pitch, loud in ((36, 1.0), (43, 0.8), (47, 0.7))]                    # every drum together
    return out


def frames() -> list[Note]:
    out = []
    for bar in range(6):
        for on, pitch, loud in ((0, 45, 0.9), (0.5, 52, 0.38), (1, 55, 0.55), (1.5, 50, 0.38), (2, 47, 0.75), (2.5, 55, 0.55), (3, 57, 0.55), (3.5, 52, 0.4)):
            out.append(Note(bar * 4 + on, 0.25, pitch, min(loud * (0.8 + 0.05 * bar), 1.0)))
    return out


def roll(pitches: tuple[int, int]) -> list[Note]:
    out = [Note(step * 0.125, 0.125, pitches[0], 0.2 + 0.02 * step) for step in range(32)]
    out += [Note(4 + beat, 0.9, pitch, 0.9) for beat, pitch in ((0, pitches[0]), (1, pitches[1]), (2, pitches[0]), (2.5, pitches[0]), (3, pitches[1]), (4, pitches[0]))]
    return out


def ripple(low: int) -> list[Note]:
    out = []
    for bar, steps in enumerate(((0, 7, 12, 15, 19, 24), (-4, 3, 8, 12, 15, 20), (-9, -2, 3, 7, 10, 15), (-2, 5, 10, 14, 17, 22))):
        out += [Note(bar * 4 + index * 0.5, 2.0, low + step, 0.5 + 0.04 * index) for index, step in enumerate(steps)]
        out += [Note(bar * 4 + 3 + index * 0.5, 1.0, low + steps[4 - index * 2], 0.5) for index in range(2)]
    return out


def march(kit: dict[str, int]) -> list[Note]:
    """An orchestra's percussion at a moment: the bass drum on the bar, the snare's gallop, a cymbal."""
    out = []
    for bar in range(6):
        out.append(Note(bar * 4, 0.5, kit["boom"], 0.8))
        out += [Note(bar * 4 + on, 0.25, kit["snare"], loud) for on, loud in ((1, 0.6), (1.5, 0.4), (1.75, 0.45), (2, 0.65), (3, 0.6), (3.5, 0.4), (3.75, 0.5))]
        if bar % 2 == 0:
            out.append(Note(bar * 4, 2.0, kit["crash"], 0.7))
        out += [Note(bar * 4 + on, 0.25, kit["tamb"], 0.4) for on in (0.5, 2.5)]
    return out


def alone(player: str) -> str:
    """A recorded player's recordings with nothing done to them: one player, the filter open."""
    read = sounds.patch(player)
    if read.held and any(zone.loop for zone in read.zones):
        text = sfz.held(read, players=1, dark=12000.0, opens=1200.0, range_db=10.0, drift=1.5)
    else:
        text = sfz.struck(read, dull=9000.0, opens=1800.0)
    return desk.bare(player, [desk.sfizz(sfz.write("audition %s" % player, text))])


def recording(players: dict[str, list[Note]]) -> list[desk.Line]:
    out = []
    for player, notes in players.items():
        if not notes:
            continue
        read = sounds.patch(player)
        held = read.held and any(zone.loop for zone in read.zones)
        level = sounds.level(player)
        out.append(desk.Line(player, alone(player), notes, volume=10 ** (level["before"] / 20.0),
                             controls=sounds._dynamics(notes, [], BPM) if held else []))
    return out


def split(long: str, short: str, notes: list[Note]) -> dict[str, list[Note]]:
    return {long: [note for note in notes if note.length * 60.0 / BPM >= 0.26], short: [note for note in notes if note.length * 60.0 / BPM < 0.26]}


def now(instrument: str, notes: list[Note], drums: bool = False) -> list[desk.Line]:
    return sounds.lines(Voice(0, notes=list(notes), drums=drums, instrument=instrument), instrument, BPM)


def rows() -> list[tuple[str, str, list[desk.Line] | None, list[desk.Line], str | None]]:
    """What is auditioned: (its name on the page, which channel's bus it goes through, the
    bare recording's tracks or None, the tracks that play it now, and what it is held against
    among the recordings that were liked)."""
    from freerock.studio.orchestra import KITS

    def bowed(name: str, written: str, section: str, first: int, against: str | None) -> tuple:
        notes = phrase(first)
        return name, "lead", recording(split(section + " long", section + " short", notes)), now(written, notes), against

    def blown(name: str, written: str, player: str, first: int, against: str | None) -> tuple:
        notes = phrase(first)
        return name, "lead", recording(split(player + " long", player + " short", notes)), now(written, notes), against

    pad = chords(57)
    spread = {"violins long": [note for note in pad if note.pitch >= 67], "violas long": [note for note in pad if 60 <= note.pitch < 67],
              "celli long": [note for note in pad if note.pitch < 60]}
    kit = KITS["orchestra"][1]
    return [
        bowed("violins", "violins", "violins", 69, "violins in"), bowed("violas", "violas", "violas", 62, "violas and second violins"),
        bowed("celli", "celli", "celli", 45, "solo cello"), bowed("basses", "basses", "basses", 33, "double basses"),
        bowed("violin (one player)", "violin", "violin", 69, "solo fiddle"),
        ("strings: held chords", "texture", recording(spread), now("strings slow", pad), "a soft sustained string chord"),
        ("strings: short chords, hard", "rhythm", None, now("strings", stabs(52)), "full strings"),
        ("strings: plucked", "rhythm", None, now("pizzicato", plucked(48)), "pizzicato strings"),
        ("strings: tremolo", "texture", None, now("tremolo", chords(64, 0.4)), "a high shimmering violin tremolo"),
        blown("flute", "flute", "flute", 76, None), blown("oboe", "oboe", "oboe", 69, "solo oboe"),
        blown("clarinet", "clarinet", "clarinet", 64, "solo clarinet"), blown("bassoon", "bassoon", "bassoon", 45, None),
        blown("horns", "horns", "horn", 57, "french horns in unison"), blown("trumpet", "trumpet", "trumpet", 64, "trumpets in unison"),
        blown("trombone", "trombone", "trombone", 50, None), blown("tuba", "tuba", "tuba", 33, None),
        ("brass: short chords, hard", "rhythm", None, now("brass", stabs(50)), "brass"),
        ("harp", "rhythm", recording({"harp": ripple(45)}), now("harp", ripple(45)), "solo harp"),
        ("celesta", "rhythm", None, now("celesta", ripple(69)), "solo celesta"),
        ("organ", "texture", recording({"organ loud": chords(45, 0.8)}), now("organ", chords(45, 0.8)), None),
        ("choir (a synth: there is no recorded one)", "texture", None, now("choir", chords(57)), None),
        ("timpani", "drums", recording({"timpani": roll((45, 40))}), now("timpani", roll((45, 40))), "orchestral percussion"),
        ("war drums", "drums", None, now("war drums", strokes()), "orchestral percussion"),
        ("the deep stroke on an arrival", "drums", None, now("boom", [Note(beat, 1.0, 36, loud) for beat, loud in ((0, 1.0), (4, 0.75), (8, 1.0))]),
         None),
        ("frame drums", "drums", None, now("frame drums", frames()), None),
        ("the orchestra's percussion", "drums", None, now("kit orchestra", march(kit), drums=True), "orchestral percussion"),
        ("gong", "drums", None, now("gong", [Note(0, 6.0, 48, 0.85)]), None),
    ]


def clean(text: str) -> str:
    return "".join(letter if letter.isalnum() or letter in " -" else "" for letter in text).strip()


def play(clip: str, bus: str | None, lines: list[desk.Line], hall: bool, display: str) -> np.ndarray:
    """Renders these tracks as one file (through a channel's bus, if one is named) and returns it."""
    last = max((note.start + note.length for line in lines for note in line.notes), default=8.0)
    seconds = last * 60.0 / BPM + 0.5
    folder = desk.Line(clip, desk.bare(clip, []), effects=sounds.bus(bus) if bus else [])
    rpp = WORK / (clip + ".rpp")
    rpp.write_text(desk.project([(folder, lines)], bpm=BPM, seconds=seconds, out=WORK, tail=4.0,
                                hall=sounds.hall(HALL) if hall else None), encoding="utf-8")
    desk.render(rpp, display=display, timeout=180.0)
    audio = desk.heard(WORK / (clip + ".wav"))
    (WORK / (clip + ".wav")).unlink()
    return audio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render each instrument alone for the listening page.")
    parser.add_argument("--only", default="", help="only the rows whose name contains this")
    parser.add_argument("--keep", action="store_true", help='first rename what is there as "now" to "before"')
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if args.keep:
        for old in sorted(OUT.glob("* - now.flac")):
            old.replace(old.with_name(old.name.replace(" - now.flac", " - before.flac")))
    reaper.configure()
    told = OUT / "measured.json"
    measured = json.loads(told.read_text(encoding="utf-8")) if told.is_file() else {}
    wanted = [row for row in rows() if args.only in row[0]]
    with reaper.Display() as display:
        for name, bus, bare, lines, against in wanted:
            for label, tracks, through, hall in (("the recording", bare, None, False), ("now", lines, bus, True)):
                if not tracks:
                    continue
                clip = "%s - %s" % (clean(name), label)
                audio = play(clip, through, tracks, hall, display)
                peak = float(np.abs(audio).max())
                if peak <= 0.0:
                    raise RuntimeError("%s (%s) rendered silent" % (name, label))
                soundfile.write(str(OUT / (clip + ".flac")), audio * (0.7 / peak), desk.RATE, format="FLAC", subtype="PCM_24")
                found = ear.profile(audio, desk.RATE)
                line = "%-44s %-13s %5.1f s  %s" % (name, label, len(audio) / desk.RATE, found)
                if against and label == "now":
                    wanted_sound = ear.reference(against)
                    line += "\n%-44s %-13s          %s" % ("", "against: " + against[:28], ear.differs(found, wanted_sound))
                    measured[name] = {"against": against, "octaves": [round(found.bands[at] - wanted_sound.bands[at], 1) for at in range(len(found.bands))],
                                      "crest": [found.crest, wanted_sound.crest]}
                print(line, flush=True)
    told.write_text(json.dumps(measured, indent=1), encoding="utf-8")
    labels = ["the recording", "before", "now"]
    page = ["<!doctype html><html><head><meta charset='utf-8'><title>FreeRock: the instruments one by one</title>",
            "<style>body{font:15px sans-serif;margin:24px;background:#16181c;color:#e8e8e8}table{border-collapse:collapse}"
            "td,th{padding:6px 12px;text-align:left;border-bottom:1px solid #333;vertical-align:middle}audio{height:28px;width:250px}"
            "small{color:#aaa}</style></head><body>",
            "<h1>The instruments, one by one</h1>",
            "<p>Each instrument plays a short phrase alone. <b>the recording</b> is the bare recording with nothing done to it; "
            "<b>before</b> is how the instrument sounded this morning; <b>now</b> is what the pieces use now (its effects, its seat on the "
            "stage, the hall).</p>"
            "<p>What helps most: for each row, say whether <b>now</b> is right, better but not there, or wrong. If <b>the recording</b> "
            "itself already sounds bad, the recording is the problem and a better one has to be found.</p>",
            "<table><tr><th>Instrument</th>" + "".join("<th>%s</th>" % label for label in labels) + "</tr>"]
    for name, _, _, _, _ in rows():
        cells = []
        for label in labels:
            file = "%s - %s.flac" % (clean(name), label)
            cells.append("<td>%s</td>" % ("<audio controls preload='none' src='%s'></audio>" % html.escape(file, quote=True)
                                          if (OUT / file).is_file() else ""))
        page.append("<tr><td>%s</td>%s</tr>" % (html.escape(name), "".join(cells)))
    page.append("</table></body></html>")
    (OUT / "index.html").write_text("\n".join(page) + "\n", encoding="utf-8")
    print("page written: %s" % (OUT / "index.html"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
