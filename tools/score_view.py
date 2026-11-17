"""Lays a track's written parts out as a full score, the way a conductor reads one, and has
MuseScore engrave it as pictures: every instrument the track gives a line to, in the orchestra's
order, for some bars of one part of its story (by default the first eight bars of its first
arrival). For studying what was written, part against part: where the tune is, what doubles it,
how the chords are spaced, what the accompaniment and the bass do under it.

    cd app && uv run --no-sync python ../tools/score_view.py warcraft pastoral-morning-fields-1/1 [--part arrival] [--bars 8]
    cd app && uv run --no-sync --with numba python ../tools/score_view.py house pastoral-01/1 [--part moment]

Writes var/passes/scores/<style>-<family>-<take>-<part>.musicxml and MuseScore's pages beside it
(...-1.png, ...-2.png). Every part is written in four-four, as the studio writes them for
MuseScore (bar lines are not heard); a piece in six-eight or three-four reads across them.
The drums are left out: a score of unpitched strokes says little that the stems do not.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from freerock.studio import muse
from freerock.studio.score import Note

VAR = Path(__file__).resolve().parents[1] / "var"
OUT = VAR / "passes" / "scores"
# The orchestra's order, top of the page to the bottom. A part not named here goes after the strings.
ORDER = ("Piccolo", "Flute", "Oboe", "English Horn", "Clarinet in B♭", "Bassoon", "Horn in F", "Trumpet in B♭", "Trombone", "Tuba",
         "Timpani", "Glockenspiel", "Xylophone", "Vibraphone", "Marimba", "Tubular Bells", "Celesta", "Harp", "Piano", "Harpsichord",
         "Classical Guitar", "Clean Guitar", "Electric Guitar", "Rhythm Guitar", "Muted Guitar", "Bass Guitar", "Hammond Organ",
         "Women", "Men", "Violin", "Violins 1", "Viola", "Violas", "Violoncello", "Violoncellos", "Contrabasses")


def window(notes: list[Note], first: float, last: float) -> list[Note]:
    """The notes that begin within [first, last) beats, moved to begin from 0 and cut at the end."""
    out = []
    for note in notes:
        if first <= note.start < last:
            out.append(Note(note.start - first, min(note.length, last - note.start), note.pitch, note.loud))
    return out


def orchestra_lines(style: str, name: str, take: int, part: str, bars: int) -> tuple[list[tuple[str, str, list[Note], str | None, str]], float, str]:
    """Every written line of a Warcraft or Knight Rock take within the bars asked for:
    (MuseScore part, how it is played, notes, Muse Sound, the line's own name), the tempo, and a caption."""
    from freerock.studio import build, orchestra
    fam = next(fam for fam, _ in build.plan() if fam.name == name)
    written = orchestra.Take(fam, take)
    at = 0.0
    for section in fam.sections:
        if section.part == part:
            break
        at += section.bars * fam.beats
    else:
        raise SystemExit("%s has no part called %r: it has %s" % (name, part, ", ".join(section.part for section in fam.sections)))
    span = (at, at + bars * fam.beats)
    lines = []
    for channel in orchestra.CHANNELS:
        for tag, voice in written.voices[channel].items():
            if voice.drums or voice.instrument not in muse.PARTS or any(part in muse.PERCUSSION for part, *_ in muse.PARTS[voice.instrument]):
                continue                                       # the drums, and the drum staves of Muse Percussion, are left out
            notes = window(voice.notes, *span)
            if not notes:
                continue
            for each_part, way, mine, sound in muse.shared(voice.instrument, notes, fam.seed * 31 + take):
                lines.append((each_part, way, mine, sound, "%s (%s)" % (tag, channel)))
    caption = "%s %d: %s, %s, %d BPM, %s, bars %d-%d" % (
        fam.title, take, part, fam.key.name, fam.bpm, fam.metre, int(at // fam.beats) + 1, int(at // fam.beats) + bars)
    return lines, fam.bpm, caption


def house_lines(name: str, take: int, part: str, bars: int) -> tuple[list[tuple[str, str, list[Note], str | None, str]], float, str]:
    """The same for a house take: its synths written on a piano staff each, under their own names."""
    from freerock.studio import club, house
    track = house.Take(house.family(name), take)
    heard = club.listen(track)
    story = {"open": "open", "theme": "theme", "rise": "rise", "moment": "moment", "close": "close"}.get(part, part)
    first = next((start for kind, start, count in track.sections if kind == story), None)
    if first is None:
        raise SystemExit("%s has no part called %r" % (name, part))
    span = (first * 4.0, (first + bars) * 4.0)
    lines = []
    for channel, table, sound, written, cut, notes, taste in club.voices(heard):
        mine = window(notes, *span)
        if not mine:
            continue
        label = "%s %s (%s)" % (table, sound, channel)
        if written in muse.PARTS:
            for each_part, way, part_notes, chosen in muse.shared(written, mine, track.seed):
                lines.append((each_part, way, part_notes, chosen, label))
        else:
            lines.append(("Piano", "", mine, None, label))           # a synth: written out on a staff of its own
    caption = "%s %d: %s, house, %d BPM, bars %d-%d" % (track.family.title, take, part, house.BPM, first + 1, first + bars)
    return lines, float(house.BPM), caption


def joined(lines: list[tuple[str, str, list[Note], str | None, str]], bpm: float, caption: str) -> str:
    """The lines written as one MusicXML score: each line's own score, numbered and put together."""
    rank = {name: index for index, name in enumerate(ORDER)}
    lines = sorted(lines, key=lambda line: (rank.get(line[0], len(ORDER)), line[4]))
    heads, bodies = [], []
    for number, (part, way, notes, _, label) in enumerate(lines, start=1):
        text = muse.score(part, notes, bpm=bpm, way=way)
        # Every id of the part made its own (a drum staff has an instrument for each of its drums: "P1-I52" and so on).
        text = text.replace('"P1-I', '"P%d-I' % number).replace('id="P1"', 'id="P%d"' % number)
        text = text.replace("<midi-channel>1</midi-channel>", "<midi-channel>%d</midi-channel>" % min(number, 16))
        head = re.search(r"<score-part .*?</score-part>", text, re.S).group(0)
        head = re.sub(r"<part-name>.*?</part-name>", "<part-name>%s</part-name>" % _escape(label), head, count=1)
        heads.append(head)
        bodies.append(re.search(r"<part id=.*?</part>", text, re.S).group(0))
    # Small staves (4 mm), so that a whole orchestra fits on one page and can be read at once.
    return "\n".join(['<?xml version="1.0" encoding="UTF-8"?>', '<score-partwise version="4.0">',
                      "<work><work-title>%s</work-title></work>" % _escape(caption),
                      "<defaults><scaling><millimeters>4</millimeters><tenths>40</tenths></scaling></defaults>",
                      "<part-list>"] + heads + ["</part-list>"] + bodies + ["</score-partwise>"]) + "\n"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def engrave(xml: str, stem: str) -> list[Path]:
    """Has MuseScore engrave a score as PNG pages; returns them in order."""
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT / (stem + ".musicxml")
    source.write_text(xml, encoding="utf-8")
    for old in sorted(OUT.glob(stem + "-*.png")):
        old.unlink()                                       # the pages of this score's last engraving
    done = muse._run(["-r", "150", "-o", str(OUT / (stem + ".png")), str(source)])      # 150 dpi: enough to read every note
    pages = sorted(OUT.glob(stem + "-*.png"), key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    if done.returncode != 0 or not pages:
        raise RuntimeError("MuseScore did not engrave %s:\n%s" % (source, (done.stderr or done.stdout)[-1500:]))
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A track's written parts as a full score, engraved by MuseScore.")
    parser.add_argument("style", choices=("warcraft", "knight", "house"))
    parser.add_argument("track", help="family/take")
    parser.add_argument("--part", default="", help="the part of the story (orchestra: open, first, second, build, arrival, valley, "
                                                   "climb, summit, close; house: open, theme, rise, moment, close)")
    parser.add_argument("--bars", type=int, default=8)
    args = parser.parse_args(argv)
    name, take = args.track.rsplit("/", 1)
    part = args.part or ("moment" if args.style == "house" else "arrival")
    lines, bpm, caption = (house_lines(name, int(take), part, args.bars) if args.style == "house"
                           else orchestra_lines(args.style, name, int(take), part, args.bars))
    if not lines:
        raise SystemExit("Nothing is written there")
    pages = engrave(joined(lines, bpm, caption), "%s-%s-%s-%s" % (args.style, name, take, part))
    print(caption)
    print("%d lines: %s" % (len(lines), ", ".join(sorted({line[0] for line in lines}))))
    for page in pages:
        print(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
