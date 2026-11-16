"""Real scores: reading them, seating the orchestra, cutting tracks and telling their story."""
import numpy as np
import pytest

from freerock import forever, studio
from freerock.studio import fluid, score, scores


# --- reading a MIDI file -------------------------------------------------------------------------

def test_a_midi_file_is_read_as_players_and_seconds(tmp_path):
    flute, strings = score.Voice(73), score.Voice(48)
    flute.add(0.0, 1.0, 72, 0.5)
    flute.add(3.0, 1.5, 74, 0.9)
    strings.add(1.5, 3.0, 55, 0.7)
    score.write_midi(tmp_path / "two.mid", [flute, strings], 90.0, 8.0)
    reading = scores.read_midi((tmp_path / "two.mid").read_bytes())
    assert [player.program for player in reading.players] == [73, 48]
    assert reading.tempo == pytest.approx(90.0, abs=0.01)
    first, second = reading.players[0].tones
    assert (first.pitch, second.pitch) == (72, 74)
    assert first.start == pytest.approx(0.0, abs=0.002) and first.length == pytest.approx(60.0 / 90.0, abs=0.003)
    assert second.start == pytest.approx(3.0 * 60.0 / 90.0, abs=0.003)
    assert second.loud > first.loud
    assert reading.players[1].tones[0].start == pytest.approx(1.0, abs=0.003)
    assert reading.seconds == pytest.approx(3.0, abs=0.01)


def test_a_file_that_is_not_midi_is_refused():
    with pytest.raises(ValueError):
        scores.read_midi(b"RIFF....WAVE")


# --- reading MusicXML ----------------------------------------------------------------------------

def _note(step, octave, duration, extra="", chord=False, alter=None):
    return "<note>%s<pitch><step>%s</step>%s<octave>%d</octave></pitch><duration>%d</duration>%s</note>" % (
        "<chord/>" if chord else "", step, "<alter>%d</alter>" % alter if alter is not None else "", octave, duration, extra)


SCORE = """<?xml version="1.0"?>
<score-partwise version="4.0">
 <part-list>
  <score-part id="P1"><part-name>Bb Clarinet</part-name>
   <score-instrument id="P1-I1"><instrument-name>Clarinet</instrument-name><instrument-sound>wind.reed.clarinet.bflat</instrument-sound></score-instrument>
   <midi-instrument id="P1-I1"><midi-program>72</midi-program></midi-instrument></score-part>
  <score-part id="P2"><part-name>Violin 1</part-name>
   <score-instrument id="P2-I1"><instrument-name>Violin</instrument-name><instrument-sound>strings.violin</instrument-sound></score-instrument>
   <midi-instrument id="P2-I1"><midi-program>41</midi-program></midi-instrument></score-part>
 </part-list>
 <part id="P1">
  <measure number="1">
   <attributes><divisions>2</divisions><transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose></attributes>
   <direction><direction-type><dynamics><p/></dynamics></direction-type><sound dynamics="54.44"/></direction>
   %(tied_first)s%(tied_second)s
  </measure>
  <measure number="2">
   <direction><direction-type><wedge type="crescendo" number="1"/></direction-type></direction>
   %(climb)s
   <direction><direction-type><wedge type="stop" number="1"/></direction-type></direction>
  </measure>
  <measure number="3">
   <direction><direction-type><dynamics><f/></dynamics></direction-type><sound dynamics="106.67"/></direction>
   %(short)s
   <note><rest/><duration>6</duration></note>
  </measure>
 </part>
 <part id="P2">
  <measure number="1">
   <attributes><divisions>2</divisions></attributes>
   <direction><direction-type><words>Allegro</words></direction-type><sound tempo="120"/></direction>
   %(violin_one)s
  </measure>
  <measure number="2">
   <direction><direction-type><words>pizz.</words></direction-type><sound pizzicato="yes"/></direction>
   %(plucked)s
   %(bowed)s
  </measure>
  <measure number="3">
   %(held)s
  </measure>
 </part>
</score-partwise>
""" % {
    "tied_first": _note("C", 5, 4, '<tie type="start"/>'),
    "tied_second": _note("C", 5, 4, '<tie type="stop"/>'),
    "climb": "".join(_note("D", 5, 2) for _ in range(4)),
    "short": _note("E", 5, 2, "<notations><articulations><staccato/></articulations></notations>"),
    "violin_one": _note("G", 4, 2) + _note("G", 4, 2) + _note("G", 4, 4) + _note("B", 4, 4, chord=True),
    "plucked": _note("A", 4, 2) + _note("A", 4, 2),
    "bowed": _note("B", 4, 4, '<notations><slur type="start" number="1"/></notations>'),
    "held": _note("C", 5, 8, '<notations><fermata/><slur type="stop" number="1"/></notations>'),
}


def test_a_score_is_read_at_the_pitch_it_sounds_with_its_ties_joined():
    reading = scores.read_musicxml(SCORE.encode())
    clarinet = reading.players[0]
    assert clarinet.sound == "wind.reed.clarinet.bflat" and clarinet.program == 71
    first = clarinet.tones[0]
    assert first.pitch == 70, "a clarinet in B flat sounds a tone below what is written"
    # Two tied half notes at 120 to the minute are one note of two seconds, let go a breath early.
    assert first.start == pytest.approx(0.0) and first.length == pytest.approx(2.0 - 0.05, abs=0.001)
    assert len(clarinet.tones) == 1 + 4 + 1


def test_dynamics_hairpins_and_staccato_shape_how_each_note_is_played():
    clarinet = scores.read_musicxml(SCORE.encode()).players[0]
    climb = [tone.loud for tone in clarinet.tones[1:5]]
    assert clarinet.tones[0].loud == pytest.approx(54.44 * 0.9 / 127.0, abs=0.01)
    assert climb == sorted(climb) and climb[-1] > climb[0] + 0.15, "the hairpin does not climb to the forte"
    last = clarinet.tones[5]
    assert last.loud == pytest.approx(106.67 * 0.9 / 127.0, abs=0.01)
    # (The violin holds a fermata over that whole bar, and everybody waits with it.)
    assert last.length == pytest.approx(0.25 * scores.FERMATA, abs=0.01), "a staccato quarter is half its length"


def test_plucked_notes_a_chord_a_fermata_and_the_return_of_the_bow():
    reading = scores.read_musicxml(SCORE.encode())
    violin = reading.players[1]
    assert [tone.way for tone in violin.tones] == ["", "", "", "", "pizz", "pizz", "", ""]
    chord = violin.tones[2:4]
    assert chord[0].start == chord[1].start == pytest.approx(1.0) and {tone.pitch for tone in chord} == {67, 71}
    held = violin.tones[-1]
    assert held.start == pytest.approx(4.0)
    assert held.length == pytest.approx(2.0 * scores.FERMATA - 0.05, abs=0.01), "the fermata is not held"
    slurred = violin.tones[-2]
    assert slurred.start + slurred.length == pytest.approx(held.start), "a slurred note does not run into the next"
    plucked = violin.tones[4]
    assert plucked.length == pytest.approx(0.5 * 0.75 + 0.0, abs=0.08), "a short note keeps most of its length"
    assert reading.seconds == pytest.approx(4.0 + 2.0 * scores.FERMATA, abs=0.01)
    assert reading.tempo == 120.0


def test_a_wrong_tempo_mark_can_be_put_right():
    half = scores.read_musicxml(SCORE.encode(), retempo={120: 60})
    assert half.players[1].tones[1].start == pytest.approx(1.0)
    marked = scores.read_musicxml(SCORE.encode(), tempo_marks=[("1", 120), ("2", 60)])
    assert marked.players[1].tones[4].start == pytest.approx(2.0)
    assert marked.players[1].tones[5].start == pytest.approx(3.0)
    with pytest.raises(ValueError):
        scores.read_musicxml(SCORE.encode(), tempo_marks=[("99", 60)])


def test_first_endings_are_left_out_and_repeats_are_not_taken():
    import xml.etree.ElementTree as ET
    part = ET.fromstring("""<part id="P1">
      <measure number="1"/>
      <measure number="2"><barline location="left"><ending number="1" type="start"/></barline>
        <barline location="right"><ending number="1" type="stop"/><repeat direction="backward"/></barline></measure>
      <measure number="3"><barline location="left"><ending number="2" type="start"/></barline>
        <barline location="right"><ending number="2" type="discontinue"/></barline></measure>
      <measure number="4"/></part>""")
    order, said = scores._plan(part)
    assert order == [0, 2, 3]
    assert "repeats are not taken" in said and "first endings are left out" in said


def test_a_cresc_with_no_goal_climbs_one_degree_and_one_with_a_goal_reaches_it():
    quiet, loud = scores.MARKS["p"] / 127.0, scores.MARKS["f"] / 127.0
    line = scores._loudness_line([(0.0, quiet), (8.0, loud)], [(4.0, 8.0, 1)], 16.0)
    assert scores._level_at(line, 2.0) == pytest.approx(quiet)
    assert quiet < scores._level_at(line, 6.0) < loud
    assert scores._level_at(line, 9.0) == pytest.approx(loud)
    alone = scores._loudness_line([(0.0, quiet)], [(4.0, 8.0, 1)], 16.0)
    assert scores._level_at(alone, 12.0) == pytest.approx(quiet + scores.STEP)


# --- seating -------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, sound, program, drums, kind, channel", [
    ("Violin 1", "strings.violin", 40, False, "violin", "texture"),
    ("Violins II", "", 48, False, "violin 2", "texture"),
    ("Viola", "strings.viola", 41, False, "viola", "texture"),
    ("violoncelloStaff:", "", 42, False, "cello", "bass"),
    ("Contrabass", "strings.contrabass", 43, False, "contrabass", "bass"),
    ("bass:", "", 48, False, "contrabass", "bass"),
    ("bassoon", "", 0, False, "bassoon", "lead"),
    ("Oboe d'amore 1", "wind.reed.oboe-damore", 68, False, "english horn", "lead"),
    ("E Horn 1", "brass.natural-horn", 60, False, "horn", "rhythm"),
    ("trombe:", "", 56, False, "trumpet", "rhythm"),
    ("Bass Trombone", "", 57, False, "trombone", "rhythm"),
    ("Pauken", "drum.timpani", 47, False, "timpani", "drums"),
    ("Triangle", "", 0, True, "percussion", "drums"),
    ("Soprano", "voice.soprano", 52, False, "choir", "lead"),
    ("Alto solo", "voice.alto", 52, False, "alto", "lead"),
    ("Violin Solo", "", 40, False, "violin solo", "lead"),
    ("Continuo", "keyboard.harpsichord", 6, False, "contrabass", "bass"),
    ("Harpsichord", "keyboard.harpsichord", 6, False, "harpsichord", "texture"),
])
def test_every_instrument_is_seated_in_its_family(name, sound, program, drums, kind, channel):
    player = scores.Player(name=name, sound=sound, program=program, drums=drums)
    assert scores.what(player) == kind
    assert scores.seat(player)[0] == channel


def test_a_string_section_nobody_names_is_seated_by_how_high_it_plays():
    high = scores.Player("ten:", "", 48, tones=[scores.Tone(0, 1, pitch, 0.5) for pitch in (67, 72, 76)])
    low = scores.Player("fourteen:", "", 48, tones=[scores.Tone(0, 1, pitch, 0.5) for pitch in (36, 40, 43)])
    assert scores.what(high) == "violin" and scores.what(low) == "contrabass"


def test_the_score_becomes_voices_for_each_channel():
    reading = scores.read_musicxml(SCORE.encode())
    voices = scores.voices_of(reading)
    assert len(voices["lead"]) == 1 and voices["lead"][0].program == 71
    assert sorted(voice.program for voice in voices["texture"]) == [45, 48], "bowed and plucked are two ways of playing"
    assert not voices["drums"] and not voices["bass"] and not voices["rhythm"]
    # A note's place is in beats of half a second; how loud it is has been brought up.
    clarinet = voices["lead"][0]
    assert min(note.start for note in clarinet.notes) == pytest.approx(0.0, abs=0.05)
    assert all(note.loud > 0.45 for note in clarinet.notes), "the quiet playing was not brought up"


def test_a_swell_inside_a_held_note_moves_the_expression_pedal():
    flute = scores.Player("Flute", "wind.flutes.flute", 73, tones=[scores.Tone(0.0, 4.0, 72, 0.4), scores.Tone(5.0, 0.3, 74, 0.8)],
                          swells=[(0.0, 0.4), (4.0, 0.8), (9.0, 0.8)])
    voice = scores.voices_of(scores.Reading([flute], 6.0, 120.0))["lead"][0]
    pedal = [level for beat, level in voice.swells if 0.0 < beat <= 8.0]
    assert len(pedal) >= 5 and pedal == sorted(pedal), "the pedal does not follow the crescendo"
    assert voice.swells[0] == (0.0, scores.SWELL)
    assert pedal[-1] == 1.0 or pedal[-1] > scores.SWELL * 1.5
    assert voice.swells[-1][1] == scores.SWELL, "the pedal does not come back to rest for the next note"


# --- cutting -------------------------------------------------------------------------------------

def test_a_movement_is_cut_where_it_is_quiet():
    curve = np.full(1200, -20.0)                 # ten minutes, in half seconds
    curve[376:384] = -55.0                       # a breath at 188 to 192 s
    curve[820:826] = -50.0                       # and another at 410 to 413 s
    tracks = scores.cut_tracks(curve)
    assert [first for first, _ in tracks] == [0, tracks[0][1], tracks[1][1]] and tracks[-1][1] == 1200
    assert 376 <= tracks[0][1] <= 385 and 820 <= tracks[1][1] <= 827
    assert scores.cut_tracks(np.full(400, -20.0)) == [(0, 400)], "a short movement is one track"


def test_a_track_is_told_as_a_story_by_how_loud_it_is():
    curve = np.concatenate([np.full(80, -40.0), np.full(80, -35.0), np.linspace(-35.0, -15.0, 60),
                            np.full(60, -15.0), np.full(80, -38.0)])
    parts = scores.tell(curve)
    assert [story for story, _, _ in parts] == ["open", "theme", "rise", "moment", "close"]
    assert parts[0][1] == 0 and parts[-1][2] == len(curve)
    assert all(before[2] == after[1] for before, after in zip(parts, parts[1:])), "the parts do not join up"
    assert all(last - first >= 24 for _, first, last in parts), "a part is under twelve seconds"
    moment = next(part for part in parts if part[0] == "moment")
    assert 200 <= moment[1] <= 232 and 270 <= moment[2] <= 292
    assert scores.tell(np.full(40, -20.0)) == [("moment", 0, 40)]


def test_a_story_is_ruled_into_bars_of_about_two_seconds():
    parts = [("open", 0, 61), ("rise", 61, 130), ("moment", 130, 203)]
    bar, sections = scores.bars_of(parts)
    assert [section["story"] for section in sections] == ["open", "rise", "moment"]
    assert sum(section["bars"] for section in sections) * bar == pytest.approx(203 * scores.HALF)
    assert 1.8 * scores.RATE <= bar <= 2.2 * scores.RATE
    assert all(section["bars"] >= 1 for section in sections)


def test_quiet_passages_are_brought_up_towards_the_loud_ones_and_keep_their_order():
    curve = np.concatenate([np.full(120, -45.0), np.full(120, -30.0), np.full(120, -18.0)])
    lift = scores.ride(curve)
    assert lift[300] == pytest.approx(0.0, abs=0.05), "the loud passage was moved"
    assert lift[60] > lift[180] > 1.0
    assert lift.max() <= scores.RIDE * scores.RIDE_MOST + 1e-6
    after = curve + lift
    assert after[60] < after[180] < after[300], "what was quieter is no longer quieter"
    assert np.max(np.abs(np.diff(lift))) < 0.6, "the fader jumps"
    assert not scores.ride(np.full(50, -100.0)).any(), "silence was turned up"


def test_how_loud_each_half_second_is():
    loud = np.full((scores.RATE, 2), 0.5, dtype=np.float32)
    quiet = np.full((scores.RATE, 2), 0.05, dtype=np.float32)
    curve = scores.level_curve(np.concatenate([loud, quiet]))
    assert len(curve) == 4
    assert curve[0] - curve[3] == pytest.approx(20.0, abs=0.01)


# --- the table -----------------------------------------------------------------------------------

def test_every_work_in_the_table_is_tagged_with_words_the_player_knows():
    from freerock import kinds
    assert len(scores.WORKS) >= 100
    for work in scores.WORKS.values():
        assert work.moods and set(work.moods) <= set(kinds.KINDS), work.id
        assert work.role in studio.ROLES and work.fight_role in studio.ROLES, work.id
        assert set(work.serves) <= {0, 1, 2}, work.id
        assert work.fight in ("", "all", "loud"), work.id
        if work.source[0] == "openscore":
            assert work.source[1] in scores.OPENSCORE_PATHS, work.id
        else:
            assert "/".join(work.source[1].split("/")[:2]) in scores.OTHERS, work.id
        for begins, changes in work.breaks:
            assert set(changes) <= {"name", "tonic", "moods", "role", "serves", "light"}, work.id
    covered = {mood for work in scores.WORKS.values() for mood in work.moods}
    assert covered == set(kinds.KINDS), "a kind of place has no real music"
    assert sum(work.light for work in scores.WORKS.values()) >= 30, "too little light music"


def test_a_part_of_a_work_has_its_own_tags_and_not_the_last_parts():
    tell = scores.WORKS["tell"]
    assert scores._tags(tell, 10.0)["role"] == "wander"
    assert scores._tags(tell, 200.0)["role"] == "storm"
    assert scores._tags(tell, 320.0)["role"] == "wander" and scores._tags(tell, 320.0)["light"]
    assert scores._tags(tell, 500.0)["role"] == "battle"


# --- from a score to a staged track, and into a bucket -----------------------------------------------

@pytest.mark.skipif(not (fluid.HOME / "usr" / "bin" / "fluidsynth").is_file(), reason="FluidSynth is not unpacked on this machine")
def test_a_work_is_played_staged_and_taken_into_a_bucket(tmp_path, monkeypatch):
    strings, cellos, horn, timpani = score.Voice(48), score.Voice(42), score.Voice(60), score.Voice(47)
    for bar in range(40):                        # eighty seconds at 120 to the minute: quiet, then loud, then quiet
        loud = 0.9 if 16 <= bar < 28 else 0.3
        for pitch in (62, 65, 69):
            strings.add(bar * 4.0, 4.0, pitch, loud)
        cellos.add(bar * 4.0, 4.0, 38, loud)
        if 16 <= bar < 28:
            horn.add(bar * 4.0, 2.0, 62, 0.9)
            timpani.add(bar * 4.0, 1.0, 38, 0.9)
    folder = tmp_path / "scores" / "made" / "up"
    folder.mkdir(parents=True)
    score.write_midi(folder / "piece.mid", [strings, cellos, horn, timpani], 120.0, 160.0)
    monkeypatch.setattr(scores, "VAR", tmp_path)
    monkeypatch.setitem(scores.WORKS, "made-up", scores.Work(
        "made-up", "Nobody: A Piece", ("midi", "made/up/piece.mid"), "D minor", ("haunted",), terms="Score: written for this test"))
    rows = scores.stage_work("made-up", out=tmp_path / "studio" / "warcraft")
    assert len(rows) == 1
    row = rows[0]
    assert row["family"] == "real-made-up-01" and row["channels"] == ["bass", "drums", "rhythm", "texture"]
    assert row["peak"] <= 0.9
    stories = [section["story"] for section in row["sections"]]
    assert "moment" in stories and stories[0] == "open"
    moment = next(section for section in row["sections"] if section["story"] == "moment")
    assert moment["lufs"] > row["sections"][0]["lufs"] + 6.0, "the moment is not louder than the opening"

    meta, parts = studio.read_track(tmp_path / "studio" / "warcraft" / "real-made-up-01" / "1")
    bars = sum(section["bars"] for section in meta["sections"])
    frames = int(round(bars * meta["bar_frames"])) + int(round(meta["post_s"] * studio.RATE))
    assert all(len(audio) == frames for audio in parts.values())
    assert 78.0 <= bars * meta["bar_frames"] / studio.RATE <= 82.0
    assert meta["floor"]["moment"] == scores.FLOOR and meta["moods"] == ["haunted"] and meta["role"] == "wander"
    assert "Nobody: A Piece" in meta["credit"] and "written for this test" in meta["credit"]

    held = scores.check_track(tmp_path / "studio" / "warcraft" / "real-made-up-01" / "1")
    assert held["wrong"] == [] and abs(held["tuning_cents"]) < 8 and held["in_key"] > 0.9

    bucket = forever.Bucket(tmp_path / "buckets", "anywhere", "warcraft", 80, "D minor")
    ids = studio.import_track(bucket, tmp_path / "studio" / "warcraft" / "real-made-up-01" / "1")
    assert len(ids) == len(meta["sections"])
    assert [bucket.pieces[piece]["story"] for piece in ids] == stories
    assert bucket.pieces[ids[0]]["next"] == ids[1]
    assert studio.import_track(bucket, tmp_path / "studio" / "warcraft" / "real-made-up-01" / "1") == [], "it went in twice"

    # Staging it again takes the place of what was staged before.
    again = scores.stage_work("made-up", out=tmp_path / "studio" / "warcraft")
    assert [each["family"] for each in again] == ["real-made-up-01"]


# --- checks nobody has to listen for ---------------------------------------------------------------

def _line(name, sound, pitches, shift=0):
    tones = [scores.Tone(index * 0.5, 0.5, pitch + shift, 0.6) for index, pitch in enumerate(pitches)]
    return scores.Player(name, sound, 0, tones=tones)


def test_a_part_read_at_the_wrong_pitch_is_found_out():
    tune = [60, 64, 67, 72, 71, 67, 64, 62] * 10
    strings = _line("Violin 1", "strings.violin", tune)
    right = _line("Flute 1", "wind.flutes.flute", tune)
    wrong = _line("Bb Clarinet", "wind.reed.clarinet.bflat", tune, shift=-2)
    reading = scores.Reading([strings, right, wrong], 40.0, 120.0)
    found = scores.off_pitch(reading)
    assert len(found) == 1 and found[0].startswith("Bb Clarinet") and "moved by 2 semitones" in found[0]


def test_a_player_the_table_leaves_out_is_not_played():
    reading = scores.Reading([_line("Violin 1", "strings.violin", [60, 62]), _line("Flute 1", "wind.flutes.flute", [72, 74])], 2.0, 120.0)
    voices = scores.voices_of(reading, kinds={"Flute 1": ""})
    assert voices["texture"] and not voices["lead"]
    assert scores.voices_of(reading, kinds={"Flute 1": "oboe"})["lead"][0].program == 68


def test_picking_takes_the_scarce_moments_first_and_stops_at_the_minutes_asked_for(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(scores, "VAR", tmp_path)
    staged = tmp_path / "scores" / "staged"
    staged.mkdir(parents=True)

    def row(work, number, role, moods, light):
        return {"work": work, "family": "real-%s-%02d" % (work, number), "seconds": 180.0, "role": role, "moods": moods,
                "light": light, "sections": [{"story": "open", "bars": 10}, {"story": "moment", "bars": 10}]}

    (staged / "beethoven-5-1.json").write_text(json.dumps([row("beethoven-5-1", 1, "battle", ["infernal"], False)]))
    (staged / "beethoven-6-1.json").write_text(json.dumps([row("beethoven-6-1", n, "wander", ["pastoral"], True) for n in (1, 2, 3)]))
    (staged / "mass-01.json").write_text(json.dumps([row("mass-01", n, "wander", ["haunted"], False) for n in (1, 2, 3)]))
    families = scores.pick(12.0)
    assert families[0] == "real-beethoven-5-1-01", "the fight did not come first"
    assert len(families) == 4
    assert {"real-beethoven-6-1-01", "real-mass-01-01"} <= set(families), "the kinds of place did not take turns"
    assert len(scores.pick(1000.0)) == 7, "asked for more than there is, it gives all there is"
