"""The forever song on the server: the bucket of phrases, what is asked for next, the mixing desk
for the five channels, and the conductor keeping a bucket fed while the game is played."""
import asyncio
import json
import types

import numpy as np
import pytest
from aiohttp.test_utils import TestClient, TestServer

from freerock import atlas, composer, forever
from freerock import conductor as music
from freerock import state as game
from freerock.director import Target
from freerock.eleven import ElevenError
from freerock.library import Library
from freerock.playtime import Playtime
from freerock.server import ServerConfig, create_app
from freerock.settings import Settings

RATE = forever.RATE


def phrase(bpm=120, bars=4, hz=220.0, level=0.2, every=0.5, stretch=1.0, seed=1):
    """A made-up phrase: a note struck every `every` beats, exactly `bars` long. `stretch` plays
    it a little slow or fast, as a phrase that drifts from the tempo does."""
    frames = bars * RATE * 240 // bpm
    step = RATE * 60.0 / bpm * every * stretch
    time = np.arange(frames) / RATE
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
    del time
    return np.stack([out, out], axis=1)


def bucket_at(tmp_path, bpm=120, zone="elwynn-forest", genre="knight"):
    return forever.Bucket(tmp_path / "buckets", zone, genre, bpm, "G mixolydian")


def fill(bucket, pools, each=1):
    for channel, tier in pools:
        for index in range(each):
            bucket.add(phrase(bucket.bpm, forever.bars_of(channel, bucket.bpm), seed=index),
                       channel=channel, tier=tier, measured={"lufs": -20.0})


# --- asking -------------------------------------------------------------------------------------

def test_every_phrase_can_be_asked_for_in_every_style():
    for genre in forever.RECIPES:
        for name in ("Duskwood", "Elwynn Forest", "Tanaris", "The Hall of Thanes"):
            profile = composer.for_genre(atlas.profile_for(name), genre)
            for channel, tier in forever.FIRST:
                for variant in range(len(forever.RECIPES[genre][channel][tier])):
                    asked = forever.ask(profile, genre, channel, tier, variant, seed=1)
                    # A verse, a build-up and a chorus, each a part of the request of its own length.
                    chunks = asked.plan["chunks"]
                    assert [chunk["text"] for chunk in chunks] == ["[Verse]", "[Build-up]", "[Chorus]"]
                    assert asked.sections == forever.form(profile.bpm) and asked.bars == sum(asked.sections)
                    # Each part is its bars long to the nearest millisecond, and the whole exactly.
                    assert sum(chunk["duration_ms"] for chunk in chunks) == round(240000 * asked.bars / profile.bpm)
                    for chunk, bars in zip(chunks, asked.sections):
                        assert abs(chunk["duration_ms"] - 240000 * bars / profile.bpm) < 1
                        assert "%d BPM" % profile.bpm in chunk["positive_styles"]
                        assert profile.tonic in chunk["positive_styles"]
                        assert "{" not in " ".join(chunk["positive_styles"]), "a word was left unfilled"
                        # One instrument alone: the others are ruled out by name, in every part.
                        assert set(forever.OTHERS[channel]) <= set(chunk["negative_styles"])
                        # The way of playing is the same all through; what differs is the part's own words.
                        assert set(asked.words) <= set(chunk["positive_styles"])
                    assert len({tuple(chunk["positive_styles"]) for chunk in chunks}) == 3
                    assert 0.55 <= asked.minutes <= 1.1


def test_a_drone_is_not_asked_to_keep_a_beat_and_a_tune_carries_the_moment():
    profile = composer.for_genre(atlas.profile_for("Duskwood"), "knight")
    drone = forever.ask(profile, "knight", "texture", 0, 0, seed=1, context=["nocturnal"])
    drums = forever.ask(profile, "knight", "drums", 1, 0, seed=1, context=["nocturnal"])
    assert not any("beat" in word for word in drone.plan["chunks"][0]["positive_styles"])
    assert "nocturnal" in drone.plan["chunks"][0]["positive_styles"]
    assert "steady straight 4/4 beat" in drums.plan["chunks"][0]["positive_styles"]
    assert "nocturnal" not in drums.plan["chunks"][0]["positive_styles"], "the parts that keep time are asked for plainly"


def test_a_phrase_is_one_turn_of_the_form_whatever_the_channel():
    assert forever.form(80) == (4, 4, 8) and forever.form(128) == (8, 8, 16)
    for bpm in atlas.TEMPOS:
        verse, build, chorus = forever.form(bpm)
        assert chorus == verse + build, "half of a turn is chorus"
        seconds = forever.cycle_bars(bpm) * 240.0 / bpm
        assert 38.0 <= seconds <= 64.0, "a turn of the form at %d BPM is %.0f s" % (bpm, seconds)
        assert {forever.bars_of(channel, bpm) for channel in forever.CHANNELS} == {forever.cycle_bars(bpm)}


def test_the_house_style_is_happy_and_laid_back_wherever_the_player_is():
    for place in ("Duskwood", "Tanaris", "Stormwind City"):
        profile = composer.for_genre(atlas.profile_for(place), "house")
        zone = atlas.profile_for(place)
        assert profile.bpm == 110 and profile.tonic == zone.tonic.split()[0] + " major"
        assert profile.mood == ["happy and carefree", "warm and laid-back"], "a gloomy zone does not make it gloomy"
        asked = forever.ask(profile, "house", "lead", 1, 0, seed=1)
        said = " ".join(" ".join(chunk["positive_styles"]) for chunk in asked.plan["chunks"])
        assert "110 BPM" in said and "major" in said and "happy" in said
        for harsh in ("distort", "acid", "siren", "minor"):
            assert harsh not in said


def test_a_tempo_whose_bars_are_not_whole_samples_or_milliseconds_is_kept_to_the_nearest(tmp_path):
    """At 110 beats a minute a bar is 104,727.27 samples and 2,181.82 milliseconds."""
    profile = composer.for_genre(atlas.profile_for("Duskwood"), "house")
    asked = forever.ask(profile, "house", "drums", 1, 0, seed=1)
    lengths = [chunk["duration_ms"] for chunk in asked.plan["chunks"]]
    assert lengths == [8727, 8728, 17454] and sum(lengths) == round(240000 * 16 / 110)
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "house", 110, "D major")
    assert bucket.cycle == 16 and bucket.frames_of(16) == 1675636
    # What ElevenLabs sends is a whole number of milliseconds long: four samples short of the
    # sixteen bars. It is brought to the nearest sample and taken into the bucket.
    came = phrase(110, 16)[:sum(lengths) * 48]
    fitted = forever.fit(came, RATE, 110, 16)
    assert len(fitted) == 1675636
    clip = bucket.add(fitted, channel="drums", tier=1, measured={"lufs": -20.0})
    assert clip.bars == 16 and bucket.live() == [clip]
    described = bucket.describe()
    assert described["bar_frames"] == pytest.approx(104727.2727, abs=1e-3) and described["clips"][0]["frames"] == 1675636
    assert forever.measure(fitted, RATE, 110, "drums", (4, 4, 8))["problems"] == []
    with pytest.raises(ValueError):
        bucket.add(fitted[:-9], channel="drums", tier=1)


def test_a_style_has_its_own_words_for_the_parts_of_the_form():
    assert "snare roll" in " ".join(forever.section_words("house", "drums", "build"))
    assert "crescendo" in " ".join(forever.section_words("warcraft", "drums", "build"))
    assert forever.section_words("knight", "lead", "chorus") == forever.SECTION_WORDS["lead"]["chorus"]
    # Where a style says nothing of its own, the common words stand.
    assert forever.section_words("warcraft", "lead", "verse") == forever.SECTION_WORDS["lead"]["verse"]


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


# --- measuring ----------------------------------------------------------------------------------

def test_a_phrase_on_the_tempo_is_fit_for_the_bucket():
    found = forever.measure(phrase(), RATE, 120, "rhythm", 4)
    assert found["problems"] == []
    assert abs(found["tempo_off"]) < 0.05 and found["dense"]


def test_a_phrase_that_drifts_is_turned_away():
    found = forever.measure(phrase(stretch=1.007), RATE, 120, "rhythm", 4)
    assert any("tempo" in problem or "bar" in problem for problem in found["problems"])


def test_a_phrase_of_a_few_long_notes_is_not_judged_by_a_beat_it_does_not_have():
    sparse = phrase(every=8.0)             # one note every two bars
    found = forever.measure(sparse, RATE, 120, "bass", 4)
    assert not found["dense"]
    assert found["problems"] == []


def test_a_phrase_of_the_wrong_length_or_an_empty_one_is_turned_away():
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


# --- the bucket ---------------------------------------------------------------------------------

def test_a_bucket_keeps_its_phrases_on_disk(tmp_path):
    bucket = bucket_at(tmp_path)
    audio = phrase()
    clip = bucket.add(audio, channel="drums", tier=1, words=["solo drum kit"], measured={"lufs": -20.0})
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
    short = bucket.add(phrase(bars=4), channel="drums", tier=1, measured={"lufs": -20.0})
    whole = bucket.add(phrase(bars=bucket.cycle), channel="drums", tier=1, measured={"lufs": -20.0})
    assert [clip.id for clip in bucket.live()] == [whole.id]
    assert [clip["id"] for clip in bucket.describe()["clips"]] == [whole.id]
    assert len(bucket.samples(short.id)) == short.frames * 4        # still on disk
    described = bucket.describe()
    assert described["cycle_bars"] == 32 and described["form"] == {"verse": 8, "build": 8, "chorus": 16}
    assert described["changes"] == 2 and described["arc"] == forever.ARC["knight"]


def test_a_phrase_must_be_a_whole_number_of_bars(tmp_path):
    with pytest.raises(ValueError):
        bucket_at(tmp_path).add(phrase()[:-7], channel="drums", tier=1)


def test_a_quiet_phrase_is_not_turned_up_past_full_scale(tmp_path):
    spiky = np.zeros((4 * RATE * 2, 2), dtype=np.float32)
    spiky[::RATE] = 0.9
    clip = bucket_at(tmp_path).add(spiky, channel="drums", tier=1, measured={"lufs": -40.0})
    assert 0.9 * 10 ** (clip.gain_db / 20) <= 10 ** (-1 / 20) + 1e-3      # the gain is kept to a hundredth of a dB


def test_the_first_phrases_are_what_the_music_cannot_start_without(tmp_path):
    bucket = bucket_at(tmp_path)
    asked = []
    for _ in range(len(forever.FIRST)):
        pool, hurry = bucket.wanted()
        assert hurry, "the first phrases are wanted in a hurry"
        asked.append(pool)
        fill(bucket, [pool])
    assert asked == list(forever.FIRST)
    assert asked[:5] == [("texture", 0), ("lead", 0), ("rhythm", 1), ("drums", 1), ("bass", 1)]
    assert bucket.ready() and bucket.started()


def test_what_the_music_is_drawing_on_comes_before_the_rest(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, forever.FIRST[:5])
    fight = [("texture", 0), ("lead", 2), ("rhythm", 2), ("drums", 2), ("bass", 2)]
    assert bucket.wanted(fight) == (("lead", 2), True)
    # Phrases already on their way count, so two requests at once go to two different pools.
    assert bucket.wanted(fight, also={("lead", 2): 1}) == (("rhythm", 2), True)
    assert bucket.wanted(fight, skip={("lead", 2)}) == (("rhythm", 2), True)


def test_every_pool_is_given_depth_in_a_hurry_the_hard_phrases_before_the_calm(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, forever.FIRST)
    walking = [("texture", 0), ("lead", 0), ("rhythm", 0), ("drums", 0)]
    asked = []
    while True:
        pool, hurry = bucket.wanted(walking)
        if not hurry:
            break
        asked.append(pool)
        fill(bucket, [pool])
    assert len(asked) == len(forever.FIRST) * (forever.DEPTH - 1)
    assert all(len(bucket.pool(*pool)) == forever.DEPTH for pool in forever.FIRST)
    # Round by round: what is playing, then what a fight will want, then the rest.
    first_round = asked[:len(forever.FIRST)]
    assert first_round[:4] == walking
    assert [tier for _, tier in first_round[4:8]] == [2, 2, 2, 2]


def test_a_deep_bucket_is_fed_where_the_music_is_running_out_of_new_phrases(tmp_path, monkeypatch):
    monkeypatch.setattr(forever, "DEPTH", 3)
    monkeypatch.setattr(forever, "MOST", 4)
    bucket = bucket_at(tmp_path)
    fill(bucket, forever.FIRST, each=3)
    calm = [("texture", 0), ("lead", 0), ("rhythm", 0), ("drums", 0)]
    # Two of the rhythm part's three have been heard: one unheard is not enough in hand.
    bucket.played([clip.id for clip in bucket.pool("rhythm", 0)[:2]])
    assert bucket.wanted(calm) == (("rhythm", 0), False)
    bucket.played([clip.id for clip in bucket.pool("lead", 0)[:2]])
    assert bucket.wanted(calm) == (("lead", 0), False), "tunes are replaced soonest"
    # Nothing in use is short of new phrases: the shallowest pool is deepened, what is in use first.
    fill(bucket, [("rhythm", 0), ("lead", 0)])
    assert bucket.wanted(calm) == (("texture", 0), False)
    # And when every pool holds all it can, nothing more is asked for until something is heard.
    fill(bucket, [pool for pool in forever.FIRST if len(bucket.pool(*pool)) < 4])
    assert bucket.wanted(calm) is None
    bucket.played([clip.id for clip in bucket.pool("drums", 0)[:3]])
    assert bucket.wanted(calm) == (("drums", 0), False)


def test_the_most_worn_phrase_makes_room_and_comes_back_when_no_more_can_be_made(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, [("drums", 1)], each=forever.KEEP + 1)
    clips = bucket.pool("drums", 1)
    bucket.played([clips[1].id, clips[1].id, clips[2].id])
    bucket.mark([clips[1].id], loved=True)                 # loved: never set aside
    gone = bucket.make_room("drums", 1)
    assert [worn.id for worn in gone] == [clips[2].id]
    assert len(bucket.pool("drums", 1)) == forever.KEEP
    assert clips[2].id not in [clip["id"] for clip in bucket.describe()["clips"]]
    bucket.everything = True
    assert len(bucket.pool("drums", 1)) == forever.KEEP + 1
    bucket.mark([clips[0].id], banned=True)                # banned: never again, whatever happens
    assert clips[0].id not in [clip.id for clip in bucket.pool("drums", 1)]


def test_a_pool_goes_on_growing_and_phrases_set_aside_when_it_was_small_come_back(tmp_path, monkeypatch):
    monkeypatch.setattr(forever, "KEEP", 3)
    bucket = bucket_at(tmp_path)
    fill(bucket, [("drums", 1)], each=5)
    assert len(bucket.make_room("drums", 1)) == 2 and len(bucket.pool("drums", 1)) == 3
    # The pool may now hold six: the two that were set aside are back when the bucket is next opened.
    monkeypatch.setattr(forever, "KEEP", 6)
    again = bucket_at(tmp_path)
    assert len(again.pool("drums", 1)) == 5 and not any(clip.retired for clip in again.clips)
    assert again.make_room("drums", 1) == []


def test_a_style_has_one_bucket_wherever_the_player_goes(tmp_path):
    buckets = forever.Buckets(tmp_path / "buckets")
    assert buckets.home("knight", None) is None, "no bucket yet and no place to begin one in"
    # It is begun where the player first is, at that place's tempo and key.
    home = buckets.home("knight", "Duskwood")
    assert (home.key, home.bpm, home.tonic) == ("knight/duskwood", 80, "D minor")
    assert buckets.home("knight", "Westfall") is home and buckets.home("knight", None) is home
    assert buckets.home("house", "Westfall").key == "house/westfall"
    # Of the buckets a style already has on disk, the one with the most to play is its bucket.
    fill(buckets.get("Elwynn Forest", "warcraft"), forever.FIRST[:2])
    fill(buckets.get("Duskwood", "warcraft"), forever.FIRST[:5])
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

def test_standing_still_is_a_drone_and_a_tune():
    mixed = forever.mix(Target(intensity=0.25, bed=1.0, drums=0.0, bass=0.0))
    assert [name for name, channel in mixed.items() if channel["level"] > 0] == ["texture", "lead"]
    assert all(channel["tier"] == 0 for channel in mixed.values())


def test_walking_brings_the_rhythm_part_and_the_drums_and_a_fight_brings_everything_hard():
    walking = forever.mix(Target(intensity=0.40, drums=0.55, bass=0.0))
    assert forever.in_use(walking) == [("texture", 0), ("lead", 0), ("rhythm", 0), ("drums", 0)]
    riding = forever.mix(Target(intensity=0.65, drums=0.8, bass=0.8))
    assert forever.in_use(riding) == [("texture", 0), ("lead", 1), ("rhythm", 1), ("drums", 1), ("bass", 1)]
    # A fight against one enemy: the drums and the riff go hard at once.
    fight = forever.mix(Target(place="battle", intensity=0.80, drums=1.0, bass=1.0))
    assert forever.in_use(fight) == [("texture", 0), ("lead", 1), ("rhythm", 2), ("drums", 2), ("bass", 1)]
    assert fight["texture"]["level"] < 1.0, "the drone makes room for the band"
    # A second enemy brings the hard lead, and a third the hard bass line.
    two = forever.mix(Target(place="battle", intensity=0.85, drums=1.0, bass=1.0))
    assert (two["lead"]["tier"], two["bass"]["tier"]) == (2, 1)
    three = forever.mix(Target(place="battle", intensity=0.90, drums=1.0, bass=1.0))
    assert (three["lead"]["tier"], three["bass"]["tier"]) == (2, 2)


def test_another_enemy_joining_a_fight_that_is_on_changes_gear():
    """The step another enemy makes is small, and has to get past the margin that keeps a
    channel from flickering on a line. Checked with the fight already on, as it is in play."""
    from freerock.director import Rules
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


def test_a_calm_tune_is_given_more_room_than_a_drum_part():
    slow = phrase(bars=16, stretch=1.004)             # four tenths of a percent behind the pulse
    sections = (4, 4, 8)
    assert forever.measure(slow, RATE, 120, "lead", sections, tier=0)["problems"] == []
    assert forever.measure(slow, RATE, 120, "lead", sections, tier=1)["problems"]
    assert forever.measure(slow, RATE, 120, "drums", sections, tier=0)["problems"]


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


# --- the filler -----------------------------------------------------------------------------------

class StandInStream:
    def __init__(self, audio):
        self.audio = audio

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        data = np.round(np.clip(self.audio, -1, 1) * 32767).astype("<i2").tobytes()
        self._pieces = [data[start:start + 50_001] for start in range(0, len(data), 50_001)]
        return self

    async def __anext__(self):
        if not self._pieces:
            raise StopAsyncIteration
        return self._pieces.pop(0)


class StandInGateway:
    """Hands back made-up audio for each request, in order; a number stands for "drifts by this much"."""

    def __init__(self, stretches=()):
        self.stretches = list(stretches)
        self.asked = []

    def stream_music(self, *, purpose, plan, seed, output_format, zone=None):
        self.asked.append({"purpose": purpose, "plan": plan, "seed": seed, "zone": zone})
        bpm = int(plan["chunks"][0]["positive_styles"][0].split()[0])
        bars = round(sum(chunk["duration_ms"] for chunk in plan["chunks"]) * bpm / 240000)
        stretch = self.stretches.pop(0) if self.stretches else 1.0
        return StandInStream(phrase(bpm, bars, stretch=stretch, seed=len(self.asked)))


async def test_a_phrase_that_drifts_is_asked_for_again_in_other_words(tmp_path):
    gateway = StandInGateway(stretches=[1.008, 1.0])
    filler = forever.Filler(gateway)
    bucket = bucket_at(tmp_path)
    clip = await filler.phrase(bucket, atlas.profile_for("Elwynn Forest"), "rhythm", 1)
    assert len(gateway.asked) == 2 and filler.turned_away == 1
    first, second = (asked["plan"]["chunks"][0]["positive_styles"] for asked in gateway.asked)
    assert first != second, "the second try was asked for in the same words"
    assert gateway.asked[0]["seed"] != gateway.asked[1]["seed"]
    assert gateway.asked[0]["zone"] == "elwynn-forest"
    assert bucket.pool("rhythm", 1) == [clip] and clip.bars == bucket.cycle
    assert clip.measured["verse"]["tempo_off"] == pytest.approx(0.0, abs=0.05)
    assert clip.measured["chorus"]["tempo_off"] == pytest.approx(0.0, abs=0.05)


async def test_a_phrase_that_fails_every_time_says_how(tmp_path):
    filler = forever.Filler(StandInGateway(stretches=[1.008] * forever.TRIES))
    bucket = bucket_at(tmp_path)
    with pytest.raises(forever.PhraseFailed) as failed:
        await filler.phrase(bucket, atlas.profile_for("Elwynn Forest"), "drums", 1)
    assert failed.value.problems and not bucket.clips


# --- the conductor --------------------------------------------------------------------------------

class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class StandInFiller:
    """Makes made-up phrases the way the real filler would, without ElevenLabs. `failures` maps
    a pool to the error raised when it is asked for."""

    def __init__(self, failures=None):
        self.failures = failures or {}
        self.asked = []
        self.turned_away = 0
        self.at_once = self.most_at_once = 0

    async def phrase(self, bucket, profile, channel, tier, context=None):
        self.asked.append((bucket.key, channel, tier, tuple(context or ()), tuple(profile.mood)))
        self.at_once += 1
        self.most_at_once = max(self.most_at_once, self.at_once)
        try:
            await asyncio.sleep(0.02)
            if (channel, tier) in self.failures:
                raise self.failures[(channel, tier)]
            return bucket.add(phrase(bucket.bpm, forever.bars_of(channel, bucket.bpm), seed=len(self.asked)),
                              channel=channel, tier=tier, measured={"lufs": -20.0})
        finally:
            self.at_once -= 1


@pytest.fixture(autouse=True)
def shallow_pools(monkeypatch):
    """The conductor tests fill small buckets, so that they take no time."""
    monkeypatch.setattr(forever, "DEPTH", 2)
    monkeypatch.setattr(forever, "MOST", 3)
    monkeypatch.setattr(forever, "KEEP", 3)


async def running(tmp_path, filler=None, clock=None, with_filler=True):
    app = create_app(ServerConfig(var_dir=tmp_path / "var", keep_log=False))
    settings = Settings(var_dir=tmp_path / "var")
    assert settings.mode == "forever"
    filler = filler or (StandInFiller() if with_filler else None)
    conductor = music.attach(app, library=Library(tmp_path / "library"), settings=settings, filler=filler,
                             playtime=Playtime(tmp_path / "var" / "playtime.json"),
                             **({"clock": clock} if clock else {}))
    client = TestClient(TestServer(app))
    await client.start_server()
    return client, app, conductor, filler


def publish(app, **fields):
    hub = app["hub"]
    if hub.link is not game.Link.LIVE:
        hub.publish(game.LinkChanged(link=game.Link.LIVE, previous=hub.link))
    previous = hub.state
    state = game.GameState(**{"daytime": True, "zone_name": "Elwynn Forest", **fields})
    hub.publish(game.StateChanged(state=state, previous=previous, changed=frozenset(fields)))


async def next_of(socket, kind, timeout=3.0):
    while True:
        message = json.loads(await asyncio.wait_for(socket.receive_str(), timeout))
        if message["type"] == kind:
            return message


async def until(condition, timeout=5.0):
    for _ in range(int(timeout / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("it never happened")


async def test_a_new_place_gets_its_first_phrases_at_once_and_the_player_its_bucket(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app)
        described = (await next_of(socket, "bucket"))["bucket"]
        assert described["key"] == "knight/elwynn-forest" and described["rate"] == 48000
        assert described["bar_frames"] == 48000 * 240 // described["bpm"]
        assert described["clips"] and described["clips"][0]["channel"] == "texture"
        target = (await next_of(socket, "target"))["target"]
        assert set(target["channels"]) == set(forever.CHANNELS)
        await until(lambda: conductor.buckets.get("Elwynn Forest", "knight").started())
        assert [(channel, tier) for _, channel, tier, _, _ in filler.asked[:len(forever.FIRST)]] == list(forever.FIRST)
        assert filler.most_at_once == music.FILL_AT_ONCE, "the first phrases are made two at a time"
        # Every phrase after the first is told to the player as it arrives.
        arrived = await next_of(socket, "phrase")
        assert arrived["key"] == "knight/elwynn-forest" and arrived["clip"]["new"] is True
        # The audio of a phrase is there to be fetched, whole.
        clip = described["clips"][0]
        response = await client.get("/phrase/knight/elwynn-forest/" + clip["id"])
        assert response.status == 200 and len(await response.read()) == clip["frames"] * 4
        assert (await client.get("/phrase/knight/elwynn-forest/nothing")).status == 404
        assert (await client.get("/phrase/knight/nowhere/nothing")).status == 404
        status = await (await client.get("/api/music")).json()
        assert status["mode"] == "forever" and status["forever"]["bucket"] == "knight/elwynn-forest"
        assert status["forever"]["pools"]["drums hard"] >= 1
    finally:
        await client.close()


async def test_the_bucket_is_filled_to_the_brim_and_then_fed_as_phrases_are_heard(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app)
        bucket = conductor.buckets.get("Elwynn Forest", "knight")
        await until(lambda: len(bucket.live()) == len(forever.FIRST) * forever.MOST, timeout=20)
        await asyncio.sleep(0.6)
        full = len(filler.asked)
        assert full == len(forever.FIRST) * forever.MOST, "it went on asking with every pool full and nothing heard"
        assert filler.most_at_once == music.FILL_AT_ONCE
        # A fight, and the player says it has heard two of the three hard drum phrases: the
        # drums are running out of new ones, so one is asked for, and the most worn makes room.
        publish(app, in_combat=True)
        heard = [clip.id for clip in bucket.pool("drums", 2)[:2]]
        await socket.send_str(json.dumps({"type": "status", "forever": True, "started": True, "context": "running",
                                          "bucket": bucket.key, "heard": heard, "playing": {}}))
        await until(lambda: len(filler.asked) > full)
        assert filler.asked[full][1:3] == ("drums", 2)
        await until(lambda: any(clip.retired for clip in bucket.clips))
        assert len(bucket.pool("drums", 2)) == forever.MOST
    finally:
        await client.close()


async def test_the_feed_goes_on_while_the_game_is_out_of_sight_for_a_moment(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        await client.ws_connect("/ws/player")
        publish(app)
        hub = app["hub"]
        hub.publish(game.LinkChanged(link=game.Link.STALE, previous=hub.link))
        bucket = conductor.buckets.get("Elwynn Forest", "knight")
        await until(lambda: len(bucket.live()) >= len(forever.FIRST) + 2, timeout=10)
        # Gone for good: nothing more.
        hub.publish(game.LinkChanged(link=game.Link.LOST, previous=hub.link))
        await asyncio.sleep(0.4)
        asked = len(filler.asked)
        await asyncio.sleep(0.6)
        assert len(filler.asked) == asked
    finally:
        await client.close()


async def test_phrases_are_made_for_the_corner_of_the_zone_and_the_hour(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        await client.ws_connect("/ws/player")
        publish(app, subzone_name="Goldshire Inn", daytime=False, weather="rain", weather_intensity=0.6)
        await until(lambda: len(filler.asked) >= 2)
        _, _, _, words, mood = filler.asked[0]
        assert words == ("nocturnal", "rain-soaked")
        assert mood == tuple(atlas.place_profile("Elwynn Forest", "Goldshire Inn").mood)
    finally:
        await client.close()


async def test_nothing_is_asked_for_with_nobody_listening(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        publish(app)                                  # no player page is open
        await asyncio.sleep(0.6)
        assert filler.asked == []
        await client.ws_connect("/ws/player")
        publish(app, on_taxi=True)                    # a flight path crosses zones without stopping
        await asyncio.sleep(0.6)
        assert filler.asked == []
    finally:
        await client.close()


async def test_the_player_says_what_it_has_heard_and_it_is_counted(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app)
        described = (await next_of(socket, "bucket"))["bucket"]
        clip = described["clips"][0]["id"]
        await socket.send_str(json.dumps({"type": "status", "forever": True, "started": True, "context": "running",
                                          "bucket": described["key"], "heard": [clip],
                                          "playing": {"texture": {"id": clip, "tier": 0}}}))
        bucket = conductor.buckets.by_key(described["key"])
        await until(lambda: next(kept for kept in bucket.clips if kept.id == clip).plays == 1)
        assert conductor.heard() == {"connected": 1, "playing": 1}
        # /rock ban is about what is playing at this moment.
        app["hub"].publish(game.CommandReceived(name="ban", count=1))
        gone = await next_of(socket, "retired")
        assert gone == {"type": "retired", "key": described["key"], "ids": [clip]}
        assert clip not in [kept.id for kept in bucket.live()]
    finally:
        await client.close()


async def test_a_pool_that_keeps_failing_is_left_alone_and_the_rest_go_on(tmp_path):
    failed = forever.PhraseFailed("lead", 0, ["it is 0.61% off tempo"])
    client, app, conductor, filler = await running(tmp_path, filler=StandInFiller({("lead", 0): failed}))
    try:
        await client.ws_connect("/ws/player")
        publish(app)
        bucket = conductor.buckets.get("Elwynn Forest", "knight")
        # Every other pool fills up; the one that fails is asked for once and then left alone.
        await until(lambda: len(bucket.live()) == (len(forever.FIRST) - 1) * forever.MOST, timeout=15)
        await asyncio.sleep(0.5)
        assert [pool for _, *pool, _, _ in filler.asked].count(["lead", 0]) == 1
        assert not bucket.pool("lead", 0)
        assert any("off tempo" in note for note in conductor.notes)
    finally:
        await client.close()


async def test_when_the_credits_run_out_the_song_goes_on_from_the_bucket(tmp_path):
    spent = ElevenError(401, {"status": "quota_exceeded", "message": "You have no credits left."}, "{}")
    clock = Clock()
    client, app, conductor, filler = await running(tmp_path, clock=clock, filler=StandInFiller({("bass", 0): spent}))
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app)
        bucket = conductor.buckets.get("Elwynn Forest", "knight")
        await until(lambda: any("no credits left" in note for note in conductor.notes))
        asked = len(filler.asked)
        clock.now += 600.0
        await asyncio.sleep(0.6)
        assert len(filler.asked) == asked, "it went on asking with nothing to pay with"
        assert bucket.everything, "the worn phrases were not brought back"
        assert not bucket.pool("bass", 0)
    finally:
        await client.close()


async def test_the_bucket_goes_with_the_player_and_takes_on_each_place(tmp_path, monkeypatch):
    monkeypatch.setattr(forever, "KEEP", 10)       # room for the bucket to grow
    clock = Clock()
    client, app, conductor, filler = await running(tmp_path, clock=clock)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app, speed=7.0)
        described = (await next_of(socket, "bucket"))["bucket"]
        assert described["key"] == "knight/elwynn-forest" and described["style"] == "Knight Rock"
        bucket = conductor.buckets.home("knight", None)
        await until(lambda: len(bucket.live()) == len(forever.FIRST) * forever.MOST, timeout=20)
        await asyncio.sleep(0.4)
        full = len(filler.asked)
        # Across the border. Nothing changes at once: the player may only be passing through.
        publish(app, zone_name="Westfall", speed=7.0)
        await asyncio.sleep(0.6)
        assert len(filler.asked) == full and conductor.bucket is bucket
        # Still there a little later: a phrase for every channel that is up, in Westfall's colours,
        # into the same bucket, at the bucket's own tempo and key.
        clock.now += music.SETTLE_S + 1
        await until(lambda: len(filler.asked) >= full + 4)
        await asyncio.sleep(0.5)
        greeting = filler.asked[full:]
        assert {key for key, *_ in greeting} == {"knight/elwynn-forest"}
        assert {channel for _, channel, *_ in greeting} >= {"texture", "lead", "rhythm", "drums"}
        assert len(greeting) == len({(channel, tier) for _, channel, tier, *_ in greeting}), "one for each channel that is up"
        assert all(mood == tuple(atlas.profile_for("Westfall").mood) for *_, mood in greeting)
        assert conductor.bucket is bucket and not (tmp_path / "var" / "buckets" / "knight" / "westfall").exists()
        assert any("Now in Westfall" in note for note in conductor.notes)
        # The player is told of each as it arrives, and nothing is set aside for them: the bucket grows.
        assert len(bucket.live()) == full + len(greeting)
        # Standing in Westfall does not go on greeting it.
        asked = len(filler.asked)
        clock.now += 60.0
        await asyncio.sleep(0.6)
        assert len(filler.asked) == asked
    finally:
        await client.close()


async def test_a_new_style_takes_over_as_soon_as_it_has_anything(tmp_path):
    client, app, conductor, filler = await running(tmp_path, with_filler=False)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), forever.FIRST[:5])
        fill(conductor.buckets.get("Elwynn Forest", "house"), [("texture", 0)])
        socket = await client.ws_connect("/ws/player")
        publish(app)
        assert (await next_of(socket, "bucket"))["bucket"]["genre"] == "knight"
        response = await client.post("/api/style", json={"genre": "house"})
        assert response.status == 200
        described = (await next_of(socket, "bucket"))["bucket"]
        assert (described["genre"], described["bpm"], described["style"]) == ("house", 110, "Progressive House")
        assert described["bar_frames"] == pytest.approx(48000 * 240 / 110)
    finally:
        await client.close()


def test_the_mix_is_what_the_player_is_sent():
    conductor = types.SimpleNamespace(forever=True, mix=None, target=Target(intensity=0.8, drums=1.0, bass=1.0),
                                      hub=types.SimpleNamespace(state=None, link=game.Link.LIVE), bucket=None,
                                      borrowed=False, scene_tag=lambda state: None)
    message = music.Conductor._target_message(conductor)
    assert message["target"]["channels"]["drums"] == {"level": 1.0, "tier": 2}
