"""The forever song's bucket and mixing desk: the written pieces kept on disk, how a stretch of
a part is held to the beat, and how the five channels are mixed for what the game asks for."""
import json

import numpy as np
import pytest

from freerock import atlas, forever
from freerock.director import Rules, Target

RATE = forever.RATE
BAR = 2 * RATE                 # a two-second bar: 120 beats a minute


def phrase(bpm=120, bars=4, hz=220.0, level=0.2, every=0.5, stretch=1.0, seed=1):
    """A made-up stretch of a part: a note struck every `every` beats, exactly `bars` long.
    `stretch` plays it a little slow or fast, as a part that drifts from the tempo does."""
    frames = bars * RATE * 240 // bpm
    step = RATE * 60.0 / bpm * every * stretch
    out = np.zeros(frames, dtype=np.float32)
    rng = np.random.default_rng(seed)
    note = int(RATE * 0.12)
    shape = np.exp(-np.arange(note) / (RATE * 0.03)).astype(np.float32)
    position = 0.0
    while position + note < frames:
        start = int(round(position))
        pitch = hz * rng.choice([1.0, 1.5, 2.0])
        out[start:start + note] += level * shape * np.sin(2 * np.pi * pitch * np.arange(note) / RATE).astype(np.float32)
        position += step
    return np.stack([out, out], axis=1)


def bucket_at(tmp_path, bpm=120, zone="elwynn-forest", genre="knight"):
    return forever.Bucket(tmp_path / "buckets", zone, genre, bpm, "G mixolydian")


def tone(hz, bars, post_s=1.0, level=0.2):
    """A held note, `bars` two-second bars long and `post_s` seconds of what the music went on to."""
    frames = bars * BAR + int(post_s * RATE)
    wave = level * np.sin(2 * np.pi * hz * np.arange(frames) / RATE).astype(np.float32)
    return np.stack([wave, wave], axis=1)


PITCH = {"texture": 110.0, "lead": 440.0, "rhythm": 220.0, "drums": 80.0, "bass": 55.0}


def stock(bucket, title="Made Up", channels=forever.CHANNELS, tiers=(1,), bars=8, **more):
    """Puts a made-up piece in a bucket and returns its id: a held note for every channel named, at
    every strength in `tiers`, `bars` two-second bars long and kept in one stretch, answering
    whatever strength the game asks for."""
    parts = {(channel, tier): tone(PITCH[channel] * (1 + 0.5 * tier), bars) for channel in channels for tier in tiers}
    said = {"title": title, "bar_frames": BAR, "bars": bars, "post": RATE, "tonic": "D minor", "serves": (0, 1, 2),
            "source": "test/" + title}
    said.update(more)
    return bucket.add_piece(parts, **said)


# --- the form -------------------------------------------------------------------------------------

def test_a_phrase_is_one_turn_of_the_form():
    assert forever.form(80) == (4, 4, 8) and forever.form(128) == (8, 8, 16)
    for bpm in atlas.TEMPOS:
        verse, build, chorus = forever.form(bpm)
        assert chorus == verse + build, "half of a turn is chorus"
        seconds = forever.cycle_bars(bpm) * 240.0 / bpm
        assert 38.0 <= seconds <= 64.0, "a turn of the form at %d BPM is %.0f s" % (bpm, seconds)


def test_a_tempo_whose_bars_are_not_whole_samples_is_kept_to_the_nearest(tmp_path):
    """At 110 beats a minute a bar is 104,727.27 samples."""
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "house", 110, "D major")
    assert bucket.describe()["bar_frames"] == pytest.approx(104727.2727, abs=1e-3)
    assert forever.measure(phrase(110, 16), RATE, 110, "drums", 16)["problems"] == []


# --- measuring ----------------------------------------------------------------------------------

def test_a_stretch_on_the_tempo_keeps_time():
    found = forever.measure(phrase(), RATE, 120, "rhythm", 4)
    assert found["problems"] == []
    assert abs(found["tempo_off"]) < 0.05 and found["dense"]


def test_a_stretch_that_drifts_does_not():
    found = forever.measure(phrase(stretch=1.007), RATE, 120, "rhythm", 4)
    assert any("tempo" in problem or "bar" in problem for problem in found["problems"])


def test_a_stretch_of_a_few_long_notes_is_not_judged_by_a_beat_it_does_not_have():
    sparse = phrase(every=8.0)             # one note every two bars
    found = forever.measure(sparse, RATE, 120, "bass", 4)
    assert not found["dense"]
    assert found["problems"] == []


def test_a_stretch_of_the_wrong_length_or_an_empty_one_is_not_fit():
    short = phrase()[:RATE * 6]
    assert any("long" in problem for problem in forever.measure(short, RATE, 120, "rhythm", 4)["problems"])
    silent = np.zeros((RATE * 8, 2), dtype=np.float32)
    silent[::4800] = 1e-5
    assert any("silent" in problem for problem in forever.measure(silent, RATE, 120, "texture", 4)["problems"])


def test_a_texture_is_not_held_to_a_beat():
    time = np.arange(RATE * 16) / RATE
    drone = 0.2 * np.sin(2 * np.pi * 220.0 * time)
    found = forever.measure(np.stack([drone, drone], axis=1).astype(np.float32), RATE, 120, "texture", 8)
    assert found["problems"] == [] and "tempo_off" not in found


# --- the bucket ---------------------------------------------------------------------------------

def test_a_bucket_keeps_its_pieces_on_disk(tmp_path):
    bucket = bucket_at(tmp_path)
    piece = stock(bucket, channels=("drums",))
    again = bucket_at(tmp_path)
    assert [clip.piece for clip in again.clips] == [piece] and again.clips[0].source == "test/Made Up"
    clip = again.clips[0]
    data = again.samples(clip.id)
    assert len(data) == (clip.frames + clip.post) * 4 == (8 * BAR + RATE) * 4
    with pytest.raises(KeyError):
        again.samples("nothing")


def test_a_bucket_written_in_the_days_of_loose_phrases_is_read_without_them(tmp_path):
    """A bucket from before 2026-11-17 may still hold loose phrases bought from ElevenLabs, and its
    parts the fields they had: the phrases are not played and the fields are passed over."""
    bucket = bucket_at(tmp_path)
    piece = stock(bucket, channels=("drums",))
    kept = json.loads((bucket.folder / "bucket.json").read_text(encoding="utf-8"))
    for clip in kept["clips"]:
        clip.update(variant=0, words=["Made Up"], measured={}, retired=False, seed=None, place="")
    kept["clips"].append({"id": "loose00001", "channel": "drums", "tier": 1, "variant": 0, "bars": 32, "frames": 3072000,
                          "gain_db": -3.0, "created": 0.0, "words": ["solo drum kit"], "measured": {"lufs": -20.0},
                          "plays": 4, "retired": True, "banned": False, "loved": False, "source": "elevenlabs",
                          "seed": 7, "place": "duskwood", "piece": "", "order": 0, "post": 0})
    (bucket.folder / "bucket.json").write_text(json.dumps(kept), encoding="utf-8")
    again = bucket_at(tmp_path)
    assert len(again.clips) == 2 and [clip.piece for clip in again.live()] == [piece]
    assert [clip["id"] for clip in again.describe()["clips"]] == [clip.id for clip in again.live()]
    again.played([again.clips[0].id])          # written back without the old fields
    assert "retired" not in json.loads((again.folder / "bucket.json").read_text(encoding="utf-8"))["clips"][0]


def test_a_style_has_one_bucket_wherever_the_player_goes(tmp_path):
    buckets = forever.Buckets(tmp_path / "buckets")
    assert buckets.home("knight", None) is None, "no bucket yet and no place to begin one in"
    # It is begun where the player first is, at that place's tempo and key, and named for no place
    # ("why are all the buckets in elywn-forest folders" ... "fix it", 2026-11-20).
    home = buckets.home("knight", "Duskwood")
    assert (home.key, home.bpm, home.tonic) == ("knight/all", 80, "D minor")
    assert buckets.home("knight", "Westfall") is home and buckets.home("knight", None) is home
    assert buckets.home("house", "Westfall").key == "house/all"
    # Of the buckets a style already has on disk (some begun before then, named for zones), the one
    # with the most to play is its bucket.
    stock(forever.Bucket(tmp_path / "buckets", "elwynn-forest", "warcraft", 120, "G major"), channels=("drums", "bass"))
    stock(forever.Bucket(tmp_path / "buckets", "duskwood", "warcraft", 80, "D minor"))
    later = forever.Buckets(tmp_path / "buckets")
    assert later.home("warcraft", "Westfall").key == "warcraft/duskwood"


def test_buckets_are_kept_by_style(tmp_path):
    buckets = forever.Buckets(tmp_path / "buckets")
    knight = buckets.get("Duskwood", "knight")
    house = buckets.get("Duskwood", "house")
    assert knight is buckets.get("Duskwood", "knight") is buckets.get("Westfall", "knight")
    assert (knight.key, knight.bpm, knight.tonic) == ("knight/all", 80, "D minor")
    assert (house.key, house.bpm, house.tonic) == ("house/all", 110, "D major")
    assert knight.folder == tmp_path / "buckets" / "knight" / forever.ALL
    stock(knight, channels=("texture",))
    again = forever.Buckets(tmp_path / "buckets")
    assert again.by_key("knight/all").clips[0].channel == "texture"
    # Kept at the tempo and key it was begun at, wherever it is asked for from next.
    assert (again.get("Westfall", "knight").bpm, again.get("Westfall", "knight").tonic) == (80, "D minor")
    with pytest.raises(KeyError):
        forever.Buckets(tmp_path / "buckets").by_key("knight/nowhere")


# --- the mixing desk ------------------------------------------------------------------------------

def up(mixed):
    """The channels a mix has up, at the strength each plays."""
    return [(channel, mixed[channel]["tier"]) for channel in forever.CHANNELS if mixed[channel]["level"] > 0]


def test_standing_still_is_a_drone_and_a_tune():
    mixed = forever.mix(Target(intensity=0.25, bed=1.0, drums=0.0, bass=0.0))
    assert [name for name, channel in mixed.items() if channel["level"] > 0] == ["texture", "lead"]
    assert all(channel["tier"] == 0 for channel in mixed.values())


def test_walking_brings_the_rhythm_part_and_the_drums_and_a_fight_brings_everything_hard():
    walking = forever.mix(Target(intensity=0.40, drums=0.55, bass=0.0))
    assert up(walking) == [("texture", 0), ("lead", 0), ("rhythm", 0), ("drums", 0)]
    riding = forever.mix(Target(intensity=0.65, drums=0.8, bass=0.8))
    assert up(riding) == [("texture", 0), ("lead", 1), ("rhythm", 1), ("drums", 1), ("bass", 1)]
    # A fight against one enemy: the drums and the riff go hard at once.
    fight = forever.mix(Target(place="battle", intensity=0.80, drums=1.0, bass=1.0))
    assert up(fight) == [("texture", 0), ("lead", 1), ("rhythm", 2), ("drums", 2), ("bass", 1)]
    assert fight["texture"]["level"] < 1.0, "the drone makes room for the band"
    # A second enemy brings the hard lead, and a third the hard bass line.
    two = forever.mix(Target(place="battle", intensity=0.85, drums=1.0, bass=1.0))
    assert (two["lead"]["tier"], two["bass"]["tier"]) == (2, 1)
    three = forever.mix(Target(place="battle", intensity=0.90, drums=1.0, bass=1.0))
    assert (three["lead"]["tier"], three["bass"]["tier"]) == (2, 2)


def test_another_enemy_joining_a_fight_that_is_on_changes_gear():
    """The step another enemy makes is small, and has to get past the margin that keeps a
    channel from flickering on a line. Checked with the fight already on, as it is in play."""
    rules = Rules()
    one = forever.mix(Target(place="battle", intensity=rules.combat_start, drums=1.0, bass=1.0))
    assert (one["lead"]["tier"], one["bass"]["tier"]) == (1, 1)
    two = forever.mix(Target(place="battle", intensity=rules.crowd[0], drums=1.0, bass=1.0), one)
    assert (two["lead"]["tier"], two["bass"]["tier"]) == (2, 1), "a second enemy did not bring the hard lead"
    three = forever.mix(Target(place="battle", intensity=rules.crowd[1], drums=1.0, bass=1.0), two)
    assert (three["lead"]["tier"], three["bass"]["tier"]) == (2, 2), "a third enemy did not bring the hard bass"
    # And back down as they fall: gone below the line by more than the margin.
    after = forever.mix(Target(place="battle", intensity=rules.combat_start, drums=1.0, bass=1.0), three)
    assert (after["lead"]["tier"], after["bass"]["tier"]) == (1, 1)


def test_an_intensity_hovering_on_a_line_does_not_change_gear_back_and_forth():
    steady = forever.mix(Target(intensity=0.76, drums=1.0, bass=1.0))
    assert steady["drums"]["tier"] == 2
    hovering = forever.mix(Target(intensity=0.73, drums=1.0, bass=1.0), steady)
    assert hovering["drums"]["tier"] == 2
    eased = forever.mix(Target(intensity=0.68, drums=1.0, bass=1.0), hovering)
    assert eased["drums"]["tier"] == 1


def test_the_moment_after_a_fight_everything_plays_calm():
    after = forever.mix(Target(place="ember", intensity=0.6, drums=0.5, bass=0.0))
    assert all(channel["tier"] == 0 for channel in after.values())
