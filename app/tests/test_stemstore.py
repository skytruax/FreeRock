"""The copy of every phrase kept for listening and study: a FLAC file each, and one table."""
import csv

import numpy as np
import soundfile

from freerock import forever
from freerock.stemstore import COLUMNS, StemStore
from test_forever import bucket_at, phrase


def rows(store):
    with (store.root / "stems.csv").open(newline="", encoding="utf-8") as table:
        return list(csv.DictReader(table))


def test_a_new_phrase_is_kept_as_a_file_with_a_row_saying_what_it_is(tmp_path):
    bucket = bucket_at(tmp_path, bpm=80, zone="duskwood", genre="warcraft")
    audio = phrase(80, bucket.cycle)
    clip = bucket.add(audio, channel="lead", tier=2, words=["solo trumpet", "a battle fanfare in D minor"],
                      measured={"lufs": -14.0, "tuning_cents": 3.0, "verse": {"tempo_off": 0.01}, "chorus": {"tempo_off": -0.02}},
                      seed=4242, place="westfall")
    store = StemStore(tmp_path / "stems")
    store.add(bucket, clip)
    path = tmp_path / "stems" / "warcraft" / "lead-hard" / ("80bpm-G-mixolydian-%s.flac" % clip.id)
    assert path.is_file() and (tmp_path / "stems" / "README.txt").is_file()
    samples, rate = soundfile.read(str(path), dtype="int16")
    assert rate == 48000 and samples.shape == (len(audio), 2)
    assert np.array_equal(samples, np.frombuffer(bucket.samples(clip.id), dtype="<i2").reshape(-1, 2)), "the copy is exact"
    (row,) = rows(store)
    assert set(row) == set(COLUMNS)
    assert row["file"] == "warcraft/lead-hard/80bpm-G-mixolydian-%s.flac" % clip.id
    assert (row["style"], row["channel"], row["strength"], row["bpm"], row["key"]) == ("warcraft", "lead", "hard", "80", "G mixolydian")
    assert (row["bars"], row["verse_bars"], row["build_bars"], row["chorus_bars"]) == ("16", "4", "4", "8")
    assert (row["seed"], row["made_for"], row["source"]) == ("4242", "westfall", "elevenlabs")
    assert row["asked_for"] == "solo trumpet; a battle fanfare in D minor"
    assert (row["verse_tempo_off_percent"], row["chorus_tempo_off_percent"], row["times_played"]) == ("0.01", "-0.02", "0")


def test_the_folder_is_brought_up_to_date_from_the_buckets(tmp_path):
    bucket = bucket_at(tmp_path, bpm=80, zone="duskwood", genre="knight")
    first = bucket.add(phrase(80, bucket.cycle), channel="drums", tier=1, measured={"lufs": -18.0})
    old = bucket.add(phrase(80, 4), channel="drums", tier=1, measured={"lufs": -18.0, "tempo_off": 0.0})   # from before the form
    store = StemStore(tmp_path / "stems")
    store.add(bucket, first)
    bucket.played([first.id])
    bucket.played([first.id])
    second = bucket.add(phrase(80, bucket.cycle, seed=2), channel="bass", tier=0, measured={"lufs": -20.0})
    written, total = store.sync(tmp_path / "buckets")
    assert (written, total) == (2, 3), "the file that was there is not written again"
    table = {row["id"]: row for row in rows(store)}
    assert set(table) == {first.id, old.id, second.id}
    assert table[first.id]["times_played"] == "2", "the table is written afresh, with the plays since"
    assert (table[old.id]["bars"], table[old.id]["in_play"], table[old.id]["verse_bars"]) == ("4", "no", "")
    assert table[second.id]["in_play"] == "yes"
    assert store.sync(tmp_path / "buckets") == (0, 3)


def test_the_parts_of_a_written_piece_are_kept_in_the_pieces_own_folder(tmp_path):
    bucket = bucket_at(tmp_path, bpm=80, zone="duskwood", genre="knight")
    loose = bucket.add(phrase(80, bucket.cycle), channel="drums", tier=1, measured={"lufs": -18.0})
    # A piece at its own tempo (100: a bar is 115200 samples), 24 bars with two seconds of what
    # the music went on to, kept in stretches of 16 bars: two stretches for each of two parts.
    bar, post = 115200, 2 * forever.RATE
    band, drums = phrase(100, 25, hz=220.0, seed=3)[:24 * bar + post], phrase(100, 25, hz=110.0, seed=4)[:24 * bar + post]
    piece = bucket.add_piece({("rhythm", 1): band, ("drums", 2): drums}, title="The Long Dark (theme)", bar_frames=bar,
                             bars=16, post=post, tonic="A dorian", story="theme", moods=["haunted", "regal"],
                             role="wander", track="song/abc", source="song/abc/4")
    store = StemStore(tmp_path / "stems")
    written, total = store.sync(tmp_path / "buckets")
    assert (written, total) == (5, 5)
    table = {row["id"]: row for row in rows(store)}
    parts = sorted((row for row in table.values() if row["piece"]), key=lambda row: row["file"])
    assert [row["file"] for row in parts] == ["knight/pieces/%s/%s" % (piece, name) for name in
                                              ("drums-hard-0.flac", "drums-hard-1.flac", "rhythm-0.flac", "rhythm-1.flac")]
    first = next(row for row in parts if row["file"].endswith("rhythm-0.flac"))
    assert (first["piece"], first["order"], first["title"]) == (piece, "0", "The Long Dark (theme)")
    assert (first["bpm"], first["key"], first["bars"], first["in_play"]) == ("100", "A dorian", "16", "yes")
    assert (first["verse_bars"], first["seconds"]) == ("", "38.4"), "a piece has its own shape, and seconds is the stretch alone"
    assert (first["made_for"], first["asked_for"], first["source"]) == ("haunted, regal", "theme; for wander; track song/abc", "song/abc/4")
    last = next(row for row in parts if row["file"].endswith("rhythm-1.flac"))
    assert (last["bars"], last["order"]) == ("8", "1")
    # A file holds its stretch and then what the music went on to: here the rest of the piece, and its last two seconds.
    clip = next(kept for kept in bucket.clips if kept.id == first["id"])
    samples, rate = soundfile.read(str(tmp_path / "stems" / first["file"]), dtype="int16")
    assert rate == 48000 and len(samples) == clip.frames + clip.post == 16 * bar + min(8 * bar + post, int(forever.POST_S * forever.RATE))
    assert np.array_equal(samples, np.frombuffer(bucket.samples(clip.id), dtype="<i2").reshape(-1, 2))
    # The loose phrase is where it always was, and says it belongs to no piece.
    assert (table[loose.id]["piece"], table[loose.id]["order"], table[loose.id]["title"]) == ("", "", "")
    assert table[loose.id]["file"].startswith("knight/drums-steady/80bpm-")
    # A ban on any part is a ban on the piece.
    bucket.mark([first["id"]], banned=True)
    store.sync(tmp_path / "buckets")
    assert {row["in_play"] for row in rows(store) if row["piece"]} == {"no"}
    assert next(row for row in rows(store) if row["id"] == loose.id)["in_play"] == "yes"
