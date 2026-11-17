"""The forever song's bucket and mixing desk: the loose phrases kept on disk, how a phrase is
measured, and how the five channels are mixed for what the game asks for."""
import numpy as np
import pytest

from freerock import atlas, forever
from freerock.director import Rules, Target

RATE = forever.RATE


def phrase(bpm=120, bars=4, hz=220.0, level=0.2, every=0.5, stretch=1.0, seed=1):
    """A made-up phrase: a note struck every `every` beats, exactly `bars` long. `stretch` plays
    it a little slow or fast, as a phrase that drifts from the tempo does."""
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


def fill(bucket, pools, each=1):
    """Puts made-up loose phrases in a bucket, `each` of them for every pool named."""
    for channel, tier in pools:
        for index in range(each):
            bucket.add(phrase(bucket.bpm, bucket.cycle, seed=index), channel=channel, tier=tier, source="test",
                       measured={"lufs": -20.0})


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
    assert bucket.cycle == 16 and bucket.frames_of(16) == 1675636
    whole = phrase(110, 16)
    clip = bucket.add(whole, channel="drums", tier=1, source="test", measured={"lufs": -20.0})
    assert clip.bars == 16 and bucket.live() == [clip]
    described = bucket.describe()
    assert described["bar_frames"] == pytest.approx(104727.2727, abs=1e-3) and described["clips"][0]["frames"] == 1675636
    assert forever.measure(whole, RATE, 110, "drums", (4, 4, 8))["problems"] == []
    with pytest.raises(ValueError):
        bucket.add(whole[:-9], channel="drums", tier=1, source="test")


# --- measuring ----------------------------------------------------------------------------------

def test_each_part_of_a_phrase_is_held_to_the_beat_on_its_own():
    # Sixteen bars at 120: a verse of eight, a build-up of eight... as the form at that tempo has it.
    sections = (4, 4, 8)
    good = phrase(bars=16)
    found = forever.measure(good, RATE, 120, "rhythm", sections)
    assert found["problems"] == [] and found["verse"]["dense"] and found["chorus"]["dense"]
    assert "build" not in found, "a build-up is not held to the tempo: fills and rolls are what it is"
    # The chorus comes in a sixth of a second late: every other channel's chorus would be early.
    bar = RATE * 2
    late = np.concatenate([good[:8 * bar], np.zeros((RATE // 6, 2), dtype=np.float32), good[8 * bar:]])[:16 * bar]
    found = forever.measure(late, RATE, 120, "rhythm", sections)
    assert any(problem.startswith("in the chorus it starts") for problem in found["problems"])
    assert not any("verse" in problem for problem in found["problems"])
    # A build-up that speeds up is no fault.
    roll = good.copy()
    roll[4 * bar:8 * bar] = phrase(bars=4, every=0.37, seed=3)
    assert forever.measure(roll, RATE, 120, "drums", sections)["problems"] == []


def test_a_phrase_on_the_tempo_is_fit_to_be_played():
    found = forever.measure(phrase(), RATE, 120, "rhythm", 4)
    assert found["problems"] == []
    assert abs(found["tempo_off"]) < 0.05 and found["dense"]


def test_a_phrase_that_drifts_is_not():
    found = forever.measure(phrase(stretch=1.007), RATE, 120, "rhythm", 4)
    assert any("tempo" in problem or "bar" in problem for problem in found["problems"])


def test_a_phrase_of_a_few_long_notes_is_not_judged_by_a_beat_it_does_not_have():
    sparse = phrase(every=8.0)             # one note every two bars
    found = forever.measure(sparse, RATE, 120, "bass", 4)
    assert not found["dense"]
    assert found["problems"] == []


def test_a_phrase_of_the_wrong_length_or_an_empty_one_is_not_fit():
    short = phrase()[:RATE * 6]
    assert any("long" in problem for problem in forever.measure(short, RATE, 120, "rhythm", 4)["problems"])
    silent = np.zeros((RATE * 8, 2), dtype=np.float32)
    silent[::4800] = 1e-5
    assert any("silent" in problem for problem in forever.measure(silent, RATE, 120, "texture", 4)["problems"])


def test_a_drone_is_judged_by_its_tuning_alone():
    time = np.arange(RATE * 16) / RATE
    drone = 0.2 * np.sin(2 * np.pi * 220.0 * time)
    assert forever.measure(np.stack([drone, drone], axis=1).astype(np.float32), RATE, 120, "texture", 8)["problems"] == []
    sour = 0.2 * np.sin(2 * np.pi * 220.0 * 2 ** (40 / 1200) * time)
    found = forever.measure(np.stack([sour, sour], axis=1).astype(np.float32), RATE, 120, "texture", 8)
    assert any("tune" in problem for problem in found["problems"])


def test_a_calm_tune_is_given_more_room_than_a_drum_part():
    slow = phrase(bars=16, stretch=1.004)             # four tenths of a percent behind the pulse
    sections = (4, 4, 8)
    assert forever.measure(slow, RATE, 120, "lead", sections, tier=0)["problems"] == []
    assert forever.measure(slow, RATE, 120, "lead", sections, tier=1)["problems"]
    assert forever.measure(slow, RATE, 120, "drums", sections, tier=0)["problems"]


# --- the bucket ---------------------------------------------------------------------------------

def test_a_bucket_keeps_its_phrases_on_disk(tmp_path):
    bucket = bucket_at(tmp_path)
    audio = phrase()
    clip = bucket.add(audio, channel="drums", tier=1, source="test", words=["solo drum kit"], measured={"lufs": -20.0})
    assert clip.bars == 4 and clip.frames == len(audio)
    assert clip.gain_db == pytest.approx(forever.LEVEL["drums"] + 20.0, abs=0.01)
    again = bucket_at(tmp_path)
    assert [kept.id for kept in again.clips] == [clip.id]
    data = again.samples(clip.id)
    assert len(data) == len(audio) * 4
    assert np.frombuffer(data, dtype="<i2")[:200:2] == pytest.approx(np.round(audio[:100, 0] * 32768), abs=1)
    with pytest.raises(KeyError):
        again.samples("nothing")


def test_phrases_from_before_the_form_are_kept_but_left_out_of_the_music(tmp_path):
    bucket = bucket_at(tmp_path)
    short = bucket.add(phrase(bars=4), channel="drums", tier=1, source="test", measured={"lufs": -20.0})
    whole = bucket.add(phrase(bars=bucket.cycle), channel="drums", tier=1, source="test", measured={"lufs": -20.0})
    assert [clip.id for clip in bucket.live()] == [whole.id]
    assert [clip["id"] for clip in bucket.describe()["clips"]] == [whole.id]
    assert len(bucket.samples(short.id)) == short.frames * 4        # still on disk
    described = bucket.describe()
    assert described["cycle_bars"] == 32 and described["form"] == {"verse": 8, "build": 8, "chorus": 16}
    assert described["changes"] == 2 and described["arc"] == forever.ARC["knight"]


def test_a_phrase_must_be_a_whole_number_of_bars(tmp_path):
    with pytest.raises(ValueError):
        bucket_at(tmp_path).add(phrase()[:-7], channel="drums", tier=1, source="test")


def test_a_quiet_phrase_is_not_turned_up_past_full_scale(tmp_path):
    spiky = np.zeros((4 * RATE * 2, 2), dtype=np.float32)
    spiky[::RATE] = 0.9
    clip = bucket_at(tmp_path).add(spiky, channel="drums", tier=1, source="test", measured={"lufs": -40.0})
    assert 0.9 * 10 ** (clip.gain_db / 20) <= 10 ** (-1 / 20) + 1e-3      # the gain is kept to a hundredth of a dB


def test_phrases_once_set_aside_as_worn_are_played_and_a_ban_is_for_good(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, [("drums", 1)], each=3)
    worn, kept, banned = bucket.pool("drums", 1)
    worn.retired = True                    # as the phrases bought while the game was played left some
    bucket.mark([banned.id], banned=True)
    again = bucket_at(tmp_path)
    assert [clip.id for clip in again.pool("drums", 1)] == [worn.id, kept.id]
    assert [clip["id"] for clip in again.describe()["clips"]] == [worn.id, kept.id]
    assert again.counts()["drums steady"] == 2 and len(again.counts()) == len(forever.POOLS) == 13


def test_a_style_has_one_bucket_wherever_the_player_goes(tmp_path):
    buckets = forever.Buckets(tmp_path / "buckets")
    assert buckets.home("knight", None) is None, "no bucket yet and no place to begin one in"
    # It is begun where the player first is, at that place's tempo and key.
    home = buckets.home("knight", "Duskwood")
    assert (home.key, home.bpm, home.tonic) == ("knight/duskwood", 80, "D minor")
    assert buckets.home("knight", "Westfall") is home and buckets.home("knight", None) is home
    assert buckets.home("house", "Westfall").key == "house/westfall"
    # Of the buckets a style already has on disk, the one with the most to play is its bucket.
    fill(buckets.get("Elwynn Forest", "warcraft"), forever.POOLS[:2])
    fill(buckets.get("Duskwood", "warcraft"), forever.POOLS[:5])
    later = forever.Buckets(tmp_path / "buckets")
    assert later.home("warcraft", "Westfall").key == "warcraft/duskwood"


def test_buckets_are_kept_by_place_and_style(tmp_path):
    buckets = forever.Buckets(tmp_path / "buckets")
    knight = buckets.get("Duskwood", "knight")
    house = buckets.get("Duskwood", "house")
    assert knight is buckets.get("Duskwood", "knight")
    assert (knight.key, knight.bpm, knight.tonic) == ("knight/duskwood", 80, "D minor")
    assert (house.key, house.bpm, house.tonic) == ("house/duskwood", 110, "D major")
    fill(knight, [("texture", 0)])
    assert forever.Buckets(tmp_path / "buckets").by_key("knight/duskwood").clips[0].channel == "texture"
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
