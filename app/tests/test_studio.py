"""The studio: keys and chords, the orchestra's writer, staging a track and putting it in a bucket."""
import random
import struct

import numpy as np
import pytest

from freerock import forever, kinds, studio
from freerock.studio import build, fluid, orchestra, score
from freerock.studio.theory import Key, Line, tones, voiced

RATE = forever.RATE


# --- keys and chords -----------------------------------------------------------------------------

def test_a_scale_step_becomes_a_pitch_in_the_key():
    key = Key(2, "minor")                                  # D minor
    assert key.name == "D minor"
    assert [key.pitch(step, 62) for step in range(8)] == [62, 64, 65, 67, 69, 70, 72, 74]
    assert key.pitch(-1, 62) == 60 and key.pitch(7, 62) == 74
    assert key.pitch(0, 50) == 50 and key.pitch(0, 57) == 62          # the key note nearest to where it is asked for
    assert key.lifted(2).name == "E minor"


def test_the_dominant_of_a_minor_key_has_its_third_raised_and_the_tune_follows_it():
    key = Key(9, "minor")                                  # A minor
    plain, raised = key.chord("5"), key.chord("5+")
    assert sorted(pitch % 12 for pitch in tones(key, plain, 60, 71)) == [4, 7, 11]         # E G B
    assert {pitch % 12 for pitch in tones(key, raised, 60, 71)} == {4, 8, 11}              # E G# B
    assert key.pitch(6, 69, raised) == key.pitch(6, 69) + 1                                # the tune's G becomes G#
    assert key.pitch(2, 69, raised) == key.pitch(2, 69)                                    # its C does not move


def test_a_chord_is_laid_out_close_and_the_players_move_as_little_as_they_can():
    key = Key(0, "major")
    first = voiced(key, key.chord("1"), None, 3, 60)
    assert {pitch % 12 for pitch in first} == {0, 4, 7} and max(first) - min(first) <= 12
    second = voiced(key, key.chord("4"), first, 3, 60)
    assert {pitch % 12 for pitch in second} == {5, 9, 0}
    assert sum(abs(now - was) for now, was in zip(second, first)) <= 5, "the players jumped about"


# --- the orchestra's writer ----------------------------------------------------------------------

def test_every_character_names_instruments_and_grooves_that_exist():
    for character in orchestra.CHARACTERS:
        for name in character.leads + character.strong + character.under + character.pads + character.plucks \
                + character.basses + character.drums:
            assert name in orchestra.INSTRUMENTS and name in orchestra.LOUD, "%s: %s" % (character.name, name)
        assert all(groove in orchestra.GROOVES for groove in character.grooves), character.name
        assert all(kind in kinds.KINDS for kind in character.kinds), character.name
        assert character.role in studio.ROLES
        assert all(mode in orchestra.THEMES for mode in character.modes)


def test_every_kind_of_place_has_light_and_heavy_music_to_walk_about_to():
    for kind in kinds.KINDS:
        mine = [character for character in orchestra.CHARACTERS if character.role == "wander" and kind in character.kinds]
        assert any(character.light for character in mine), "%s has no light music" % kind
        assert any(not character.light for character in mine), "%s has no heavy music" % kind
        assert len(mine) >= 4
    roles = {character.role for character in orchestra.CHARACTERS}
    assert roles == set(studio.ROLES), "a kind of moment has no music: %s" % (set(studio.ROLES) - roles)


def test_a_family_is_a_story_of_about_three_minutes():
    for index, character in enumerate(orchestra.CHARACTERS):
        fam = orchestra.family(character, 100 + index, "f", "F")
        assert [section.story for section in fam.sections] == list(forever.STORY)
        assert all(len(section.chords) == section.bars for section in fam.sections)
        assert 100 <= fam.seconds <= 240, "%s is %d s long" % (character.name, fam.seconds)
        theme, moment = fam.sections[1], fam.sections[3]
        assert theme.bars % 8 == 0 and moment.bars == theme.bars
        assert theme.chords[7] == "1" and fam.sections[4].chords[-1] == "1", "it does not come home"
        assert moment.level[0] >= max(section.level[1] for section in fam.sections[:2]), "the moment is not the top"


def test_a_tune_is_eight_bars_that_come_home_and_never_sits_on_one_note():
    for index, character in enumerate(orchestra.CHARACTERS):
        fam = orchestra.family(character, 300 + index, "f", "F")
        chords = [fam.key.chord(figure) for figure in fam.sections[1].chords[:8]]
        tune = orchestra.theme(random.Random(index), fam, chords, character.busy)
        starts = [start for start, _, _, _ in tune.notes]
        assert starts == sorted(starts) and starts[0] == 0
        assert max(start + length for start, length, _, _ in tune.notes) <= 8 * fam.beats + 1e-6
        assert tune.notes[-1][2] % 7 == 0, "%s does not end on the key note" % character.name
        assert tune.top - tune.bottom <= 14, "its range is too wide to sing"
        steps = [step for _, _, step, _ in tune.notes]
        assert not any(a == b == c for a, b, c in zip(steps, steps[1:], steps[2:])), "a note three times running"
        assert max(abs(b - a) for a, b in zip(steps, steps[1:])) <= 7
        # A long note on a strong beat is a note of the chord under it.
        for start, length, step, _ in tune.notes:
            bar = int(start / fam.beats + 1e-6)
            if length >= 1.0 and abs(start - bar * fam.beats) < 1e-6:
                assert step % 7 in {note % 7 for note in chords[bar].steps}, "%s bar %d" % (character.name, bar + 1)


def test_takes_of_a_family_share_its_changes_and_differ_in_what_they_play():
    fam = orchestra.family(orchestra.CHARACTERS[0], 7, "f", "F")
    one, two = orchestra.Take(fam, 1), orchestra.Take(fam, 2)
    assert one.total == two.total == fam.bars * fam.beats
    assert [(start, step) for start, _, step, _ in one.tune.notes] != [(start, step) for start, _, step, _ in two.tune.notes]
    for take in (one, two):
        assert all(len(voices) <= 15 for voices in take.voices.values())
        for channel in ("lead", "rhythm", "bass", "texture"):
            notes = [note for voice in take.voices[channel].values() for note in voice.notes]
            assert notes, "nothing is written for the %s" % channel
            assert max(note.start for note in notes) < take.total
            assert all(0 <= note.pitch <= 127 for note in notes)


def test_the_plan_is_a_big_library_with_names_of_its_own():
    families = build.plan()
    names = [fam.name for fam, _ in families]
    titles = [fam.title for fam, _ in families]
    assert len(set(names)) == len(names)
    assert len(set(titles)) >= len(titles) - 3, "too many families share a title"
    assert sum(takes for _, takes in families) >= 150
    assert sum(fam.seconds * takes for fam, takes in families) / 60.0 >= 400


# --- the MIDI file -------------------------------------------------------------------------------

def test_a_midi_file_holds_every_voice_and_ends_a_note_before_striking_it_again(tmp_path):
    voice = score.Voice(48)
    voice.add(0.0, 4.0, 60, 0.8)
    voice.add(2.0, 4.0, 60, 0.8)                           # the same note again while the first still sounds
    kit = score.Voice(0, drums=True)
    kit.add(0.0, 0.5, 36, 0.9)
    path = tmp_path / "t.mid"
    score.write_midi(path, [voice, kit], 120, 8)
    data = path.read_bytes()
    assert data[:4] == b"MThd"
    assert struct.unpack(">HHH", data[8:14]) == (1, 3, score.TICKS)         # the tempo track and the two voices
    track = data.split(b"MTrk")[2]
    ons = [index for index in range(len(track) - 2) if track[index] == 0x90 and track[index + 1] == 60]
    offs = [index for index in range(len(track) - 2) if track[index] == 0x80 and track[index + 1] == 60]
    assert len(ons) == 2 and len(offs) == 2 and offs[0] < ons[1], "the first note was not ended before the second began"
    assert b"\x99\x24" in data, "the drums are not on the drum channel"


@pytest.mark.skipif(not (fluid.HOME / "usr" / "bin" / "fluidsynth").is_file(), reason="FluidSynth is not unpacked on this machine")
def test_the_sampled_orchestra_plays_a_part(tmp_path):
    voice = score.Voice(48)
    for beat in range(4):
        voice.add(beat, 0.9, 60 + beat, 0.7)
    score.write_midi(tmp_path / "t.mid", [voice], 120, 6)
    audio = fluid.render(tmp_path / "t.mid", tmp_path / "t.wav")
    assert audio.shape[1] == 2 and len(audio) / RATE >= 2.9          # it plays on until the last note has died away
    assert float(np.abs(audio[:RATE]).max()) > 0.01, "nothing came out"


# --- staging a track and putting it in a bucket --------------------------------------------------

def tone(frames, hz, level=0.2):
    wave = level * np.sin(2 * np.pi * hz * np.arange(frames) / RATE)
    return np.stack([wave, wave], axis=1).astype(np.float32)


def made_track(folder, take=1, quiet_drums=True):
    """A staged track of five two-second sections at a bar a second, with a second of ringing-on."""
    bar = RATE
    sections = [{"story": story, "bars": 2} for story in forever.STORY]
    sections[3]["tonic"] = "E minor"
    frames = 10 * bar + RATE
    drums = tone(frames, 90, 0.3)
    if quiet_drums:
        drums[:2 * bar] = 0.0                              # nothing in the opening
    lead = tone(frames, 440 + 20 * take, 0.1)
    lead[6 * bar:8 * bar] *= 4.0                           # the moment is the loudest
    meta = {"style": "warcraft", "family": "test-family", "take": take, "title": "Test Piece", "tempo": 240.0, "beats": 4,
            "bar_frames": float(bar), "tonic": "D minor", "moods": ["haunted"], "role": "wander", "serves": [0, 1],
            "light": False, "sections": sections, "floor": {"moment": {"drums": 0.9}}, "follow": {"rhythm": ["lead"]},
            "post_s": 1.0, "credit": "a test", "seed": 1}
    studio.write_track(folder, meta, {"lead": lead, "drums": drums})
    return meta


def test_a_staged_track_is_read_back_as_it_was_written(tmp_path):
    meta = made_track(tmp_path / "warcraft" / "test-family" / "1")
    back, parts = studio.read_track(tmp_path / "warcraft" / "test-family" / "1")
    assert back == meta
    assert set(parts) == {"lead", "drums"} and len(parts["lead"]) == 11 * RATE
    with pytest.raises(ValueError):
        studio.write_track(tmp_path / "bad", meta, {"lead": tone(RATE, 440)})          # not the length the story says


def test_a_staged_track_becomes_the_pieces_of_its_story_each_going_into_the_next(tmp_path):
    folder = tmp_path / "studio" / "warcraft" / "test-family" / "1"
    made_track(folder)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    ids = studio.import_track(bucket, folder)
    assert len(ids) == 5
    pieces = [bucket.pieces[piece_id] for piece_id in ids]
    assert [piece["story"] for piece in pieces] == list(forever.STORY)
    assert [piece["next"] for piece in pieces] == ids[1:] + [""]
    assert [piece["tonic"] for piece in pieces] == ["D minor"] * 3 + ["E minor", "D minor"]
    assert all(piece["family"] == "warcraft/test-family" and piece["track"] == "warcraft/test-family/1" for piece in pieces)
    assert pieces[3]["floor"] == {"drums": 0.9} and pieces[0]["floor"] == {}
    # One gain for the whole track, so the story keeps its shape.
    clips = [clip for clip in bucket.clips if clip.piece]
    assert len({clip.gain_db for clip in clips}) == 1
    # The drums are silent in the opening, so the opening has no drums.
    assert {clip.channel for clip in clips if clip.piece == ids[0]} == {"lead"}
    assert {clip.channel for clip in clips if clip.piece == ids[1]} == {"lead", "drums"}
    # Every recording is the piece and then what the music went on to.
    for clip in clips:
        samples = np.load(bucket.folder / "clips" / (clip.id + ".npy"))
        assert len(samples) == clip.frames + clip.post
        assert clip.frames == 2 * RATE
        # ...up to six seconds of it, or as much as there is: the last piece has only the ringing-on.
        left = (4 - ids.index(clip.piece)) * 2 * RATE + RATE
        assert clip.post == min(int(forever.POST_S * RATE), left)
    # A second time adds nothing.
    assert studio.import_track(bucket, folder) == []
    # And another take of the family is its kin.
    other = tmp_path / "studio" / "warcraft" / "test-family" / "2"
    made_track(other, take=2)
    assert len(studio.import_track(bucket, other)) == 5
    assert studio.staged(tmp_path, "warcraft") == [folder, other]


def test_the_player_is_told_of_pieces_and_a_ban_is_on_the_whole_piece(tmp_path):
    folder = tmp_path / "studio" / "warcraft" / "test-family" / "1"
    made_track(folder)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    ids = studio.import_track(bucket, folder)
    told = bucket.describe()
    assert set(told["pieces"]) == set(ids)
    assert told["pieces"][ids[3]]["story"] == "moment" and told["pieces"][ids[3]]["serves"] == [0, 1]
    parts = [clip for clip in told["clips"] if clip.get("piece")]
    assert parts and all({"piece", "order", "post", "plays"} <= set(clip) for clip in parts)
    # Parts of pieces are in no pool: the feed asks for loose phrases as if they were not there.
    assert all(not bucket.pool(channel, tier) for channel, tier in forever.FIRST)
    assert bucket.wanted() is not None
    # Banning one part bans the piece, and the bucket remembers after it is read again.
    one = next(clip for clip in bucket.clips if clip.piece == ids[1])
    marked = bucket.mark([one.id], banned=True)
    assert {clip.piece for clip in marked} == {ids[1]} and len(marked) == 2
    again = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    assert ids[1] not in again.describe()["pieces"]
    assert not any(clip.get("piece") == ids[1] for clip in again.describe()["clips"])
    again.drop_piece(ids[4])
    assert again.pieces[ids[3]]["next"] == "" and ids[4] not in again.pieces


def test_a_long_part_is_kept_in_stretches(tmp_path):
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor")
    bar = RATE * 2
    audio = tone(40 * bar + RATE, 220)                     # forty bars of two seconds, and a second after
    piece = bucket.add_piece({("rhythm", 1): audio, ("drums", 1): audio}, title="Long", bar_frames=bar, bars=16, post=RATE)
    clips = sorted((clip for clip in bucket.clips if clip.piece == piece and clip.channel == "rhythm"), key=lambda clip: clip.order)
    assert [clip.bars for clip in clips] == [16, 16, 8]
    assert [clip.frames for clip in clips] == [16 * bar, 16 * bar, 8 * bar]
    assert clips[0].post == int(forever.POST_S * RATE) and clips[2].post == RATE
    assert bucket.pieces[piece]["windows"] == 3 and bucket.pieces[piece]["frames"] == 40 * bar
    with pytest.raises(ValueError):
        bucket.add_piece({("rhythm", 1): audio, ("drums", 1): audio[:-5]}, title="Uneven", bar_frames=bar, bars=16)
