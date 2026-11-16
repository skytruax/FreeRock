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
