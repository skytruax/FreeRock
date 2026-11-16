"""Writing a voice out as a score for MuseScore: what a player would be given."""
from __future__ import annotations

import re

import pytest

from freerock.studio import muse
from freerock.studio.score import Note


def notes_of(text: str) -> list[str]:
    return re.findall(r"<note>.*?</note>", text)


def test_a_line_is_written_with_its_dynamics_a_slur_and_dots_on_its_short_notes():
    line = [Note(0.0, 1.96, 69, 0.45), Note(2.0, 0.98, 72, 0.5), Note(3.0, 0.98, 71, 0.55), Note(4.0, 3.9, 76, 0.75),
            Note(8.0, 0.22, 69, 0.75), Note(8.5, 0.22, 72, 0.75)]
    text = muse.score("Violins 1", line, bpm=80.0)
    assert "<part-name>Violins 1</part-name>" in text and "<instrument-sound>strings.violin</instrument-sound>" in text     # or MuseScore plays it with its plain sounds
    assert text.index("<mp/>") < text.index("<f/>") and "<pp/>" not in text                 # soft at first, loud where the line is loud
    assert text.count('<slur type="start"') == 1 and text.count('<slur type="stop"') == 1   # the four long notes under one bow
    assert text.count("<staccato/>") == 2                                                   # the two short ones
    assert 'tempo="80.00"' in text and text.count("<measure ") == 3


def test_a_note_over_a_bar_line_is_tied_and_every_bar_is_full():
    text = muse.score("Horn in F", [Note(2.0, 4.0, 60, 0.6)], bpm=60.0)       # from the third beat of one bar to the third of the next
    sounding = [note for note in notes_of(text) if "<pitch>" in note]
    assert len(sounding) == 2 and '<tie type="start"/>' in sounding[0] and '<tie type="stop"/>' in sounding[1]
    for bar in re.findall(r"<measure .*?</measure>", text, re.S):
        assert sum(int(length) for length in re.findall(r"<duration>(\d+)</duration>", bar)) == muse.BAR


def test_notes_begun_together_are_a_chord_and_a_held_note_under_a_moving_one_is_a_second_voice():
    chord = muse.score("Violoncellos", [Note(0.0, 4.0, 48, 0.5), Note(0.0, 4.0, 55, 0.5), Note(0.0, 4.0, 60, 0.5)], bpm=80.0)
    assert chord.count("<chord/>") == 2 and "<voice>2</voice>" not in chord
    two = muse.score("Violoncellos", [Note(0.0, 4.0, 48, 0.5), Note(1.0, 1.0, 55, 0.5), Note(2.0, 1.0, 57, 0.5)], bpm=80.0)
    assert "<voice>2</voice>" in two and "<backup><duration>%d</duration></backup>" % muse.BAR in two
    assert 'slur type="start"' not in two                                                    # slurs are for a single line


def test_tremolo_and_plucked_strings_are_marked_and_struck_instruments_get_no_dots():
    held = [Note(0.0, 2.0, 60, 0.5), Note(2.0, 2.0, 64, 0.5)]
    assert muse.score("Violas", held, bpm=80.0, way="trem").count('<tremolo type="single">3</tremolo>') == 2
    plucked = muse.score("Contrabasses", held, bpm=80.0, way="pizz")
    assert "<words>pizz.</words>" in plucked and 'pizzicato="yes"' in plucked
    assert "<staccato/>" not in muse.score("Harp", [Note(0.0, 0.1, 60, 0.5), Note(0.5, 0.1, 64, 0.5)], bpm=120.0)


def directions(text: str) -> list[str]:
    """What is written under the staff, in order: marks, hairpins and where in a note they stand."""
    out = []
    for found in re.findall(r'<direction placement="below"><direction-type>(.*?)</direction-type>(?:<offset>(\d+)</offset>)?</direction>', text):
        what = re.sub(r'<dynamics><(\w+)/></dynamics>', r"\1", found[0])
        what = re.sub(r'<wedge type="(\w+)" number="1"/>', r"\1", what)
        out.append(what + ("+" + found[1] if found[1] else ""))
    return out


def test_a_line_of_long_notes_is_one_breath_leaned_into_held_and_let_fall():
    # Three long notes that run into each other, a rest, a long note by itself, two short ones.
    line = [Note(0.0, 4.0, 69, 0.6), Note(4.0, 4.0, 72, 0.6), Note(8.0, 4.0, 71, 0.6), Note(14.0, 6.0, 67, 0.75), Note(20.0, 0.5, 69, 0.6),
            Note(20.5, 0.5, 71, 0.6)]
    said = directions(muse.score("Violins 1", line, bpm=80.0))
    # The first begins a mark under and grows; the second is held; the third falls away, further since a rest follows.
    assert said[:3] == ["mp", "crescendo", "stop+20"] and said[3] == "mf+20"
    assert said[4:8] == ["mf", "diminuendo+22", "stop", "p"]
    # The note by itself does all three, and the short notes after it are told their strength again.
    assert said[8:10] == ["mf", "crescendo"] and said[10:13] == ["stop+10", "f+10", "diminuendo+10"] and said[13:] == ["stop", "mf"]
    # Every hairpin that is begun is ended, and only one is open at a time.
    opened = 0
    for each in said:
        if each.split("+")[0] in ("crescendo", "diminuendo"):
            assert opened == 0
            opened = 1
        elif each.split("+")[0] == "stop":
            assert opened == 1
            opened = 0
    assert opened == 0
    for bar in re.findall(r"<measure .*?</measure>", muse.score("Violins 1", line, bpm=80.0), re.S):
        assert sum(int(length) for length in re.findall(r"<duration>(\d+)</duration>", bar)) == muse.BAR, "a hairpin took up time in the bar"


def test_a_pad_goes_with_the_writers_swell_and_plucked_struck_and_guitar_notes_are_left_alone():
    pad = [Note(0.0, 8.0, 60, 0.62), Note(8.0, 8.0, 62, 0.62), Note(16.0, 8.0, 60, 0.62)]
    said = directions(muse.score("Violas", pad, bpm=80.0, swells=[(0.0, 0.42), (8.0, 0.6), (16.0, 0.9), (24.0, 0.45)]))
    marks = [each for each in said if each.split("+")[0] in ("pp", "p", "mp", "mf", "f", "ff")]
    order = ["pp", "p", "mp", "mf", "f", "ff"]
    assert marks[0] == "pp" and max(order.index(mark.split("+")[0]) for mark in marks) == order.index("mf"), "one strength all through, as written without the swell: %s" % said
    assert "crescendo" in said and "diminuendo" in said and said[-2:] == ["stop", "p"], said
    assert directions(muse.score("Violas", pad, bpm=80.0)).count("mf") >= 1 and "pp" not in directions(muse.score("Violas", pad, bpm=80.0))
    long = [Note(0.0, 8.0, 60, 0.6), Note(8.0, 8.0, 64, 0.6)]
    for part, way in (("Harp", ""), ("Contrabasses", "pizz"), ("Electric Guitar", ""), ("Rhythm Guitar", "")):
        assert not any("crescendo" in each or "diminuendo" in each for each in directions(muse.score(part, long, bpm=80.0, way=way))), part


def test_the_band_is_two_rhythm_guitars_a_lead_a_bass_and_a_hammond(monkeypatch):
    monkeypatch.setattr(muse, "sounds", lambda: True)
    riff = [Note(0.0, 0.5, 40, 0.8), Note(0.0, 0.5, 47, 0.8)]
    two = muse.shared("rhythm guitar", riff)
    assert [(part, sound) for part, _, _, sound in two] == [("Rhythm Guitar", "Muse Guitars Vol 1/Electric LP - Heavy"),
                                                           ("Rhythm Guitar", "Muse Guitars Vol 1/Electric SC - Heavy")]
    assert [sound for _, _, _, sound in muse.shared("muted guitar", riff)] == [sound for _, _, _, sound in two]
    assert muse.shared("lead guitar", riff)[0][3] == "Muse Guitars Vol 1/Electric LP - Lead"
    assert muse.shared("picked bass", riff)[0][::3] == ("Bass Guitar", "Muse Guitars Vol 1/Electric Bass")
    assert muse.shared("rock organ", riff)[0][::3] == ("Hammond Organ", "Muse Keys/Hammond Organ")
    assert "<staccato/>" not in muse.score("Rhythm Guitar", [Note(0.0, 0.1, 40, 0.8), Note(0.5, 0.1, 40, 0.8)], bpm=150.0)


def test_a_whole_string_orchestra_is_shared_out_by_register_and_a_piece_keeps_its_choice_of_sounds(monkeypatch):
    shared = muse.shared("strings", [Note(0.0, 1.0, pitch, 0.5) for pitch in (36, 50, 62, 80)])
    assert [(part, [note.pitch for note in notes]) for part, _, notes, _ in shared] == [
        ("Contrabasses", [36]), ("Violoncellos", [50]), ("Violas", [62]), ("Violins 1", [80])]
    assert muse.shared("tremolo", [Note(0.0, 1.0, 62, 0.5)])[0][1] == "trem"
    monkeypatch.setattr(muse, "sounds", lambda: True)
    first = {part: muse.voiced(part, 7) for part in muse.CHOICES}
    assert first == {part: muse.voiced(part, 7) for part in muse.CHOICES}                    # the same piece, the same orchestra
    assert all(first[part] in muse.CHOICES[part] for part in first)
    assert any({muse.voiced(part, seed) for seed in range(12)} == set(muse.CHOICES[part]) for part in muse.CHOICES)      # other pieces, other choices
    assert muse.voiced("Timpani", 7) is None                                                 # there is one set of kettledrums
    with pytest.raises(ValueError):
        muse.score("Harp", [], bpm=80.0)
