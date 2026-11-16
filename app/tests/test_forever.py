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
                    chunk = asked.plan["chunks"][0]
                    assert chunk["duration_ms"] == composer.bars_ms(profile.bpm, asked.bars)
                    assert "%d BPM" % profile.bpm in chunk["positive_styles"]
                    assert profile.tonic in chunk["positive_styles"]
                    assert "{" not in " ".join(chunk["positive_styles"]), "a word was left unfilled"
                    # One instrument alone: the others are ruled out by name.
                    assert set(forever.OTHERS[channel]) <= set(chunk["negative_styles"])


def test_a_drone_is_not_asked_to_keep_a_beat_and_a_tune_carries_the_moment():
    profile = composer.for_genre(atlas.profile_for("Duskwood"), "knight")
    drone = forever.ask(profile, "knight", "texture", 0, 0, seed=1, context=["nocturnal"])
    drums = forever.ask(profile, "knight", "drums", 1, 0, seed=1, context=["nocturnal"])
    assert not any("beat" in word for word in drone.plan["chunks"][0]["positive_styles"])
    assert "nocturnal" in drone.plan["chunks"][0]["positive_styles"]
    assert "steady straight 4/4 beat" in drums.plan["chunks"][0]["positive_styles"]
    assert "nocturnal" not in drums.plan["chunks"][0]["positive_styles"], "the parts that keep time are asked for plainly"


def test_phrases_are_twice_as_many_bars_at_the_fastest_tempos():
    assert forever.bars_of("drums", 120) == 4 and forever.bars_of("lead", 120) == 8
    assert forever.bars_of("drums", 150) == 8 and forever.bars_of("lead", 150) == 16


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
        pool = bucket.wanted()
        asked.append(pool)
        fill(bucket, [pool])
    assert asked == list(forever.FIRST)
    assert asked[:5] == [("texture", 0), ("lead", 0), ("rhythm", 1), ("drums", 1), ("bass", 1)]
    assert bucket.ready() and bucket.started()


def test_what_the_music_is_drawing_on_comes_before_the_rest(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, forever.FIRST[:5])
    fight = [("texture", 0), ("lead", 2), ("rhythm", 2), ("drums", 2), ("bass", 2)]
    assert bucket.wanted(fight) == ("lead", 2)
    # Phrases already on their way count, so two requests at once go to two different pools.
    assert bucket.wanted(fight, also={("lead", 2): 1}) == ("rhythm", 2)
    assert bucket.wanted(fight, skip={("lead", 2)}) == ("rhythm", 2)


def test_a_full_bucket_is_fed_where_the_fewest_phrases_are_unheard(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, forever.FIRST, each=2)
    calm = [("texture", 0), ("lead", 0), ("rhythm", 0), ("drums", 0)]
    bucket.played([clip.id for clip in bucket.pool("rhythm", 0)])
    assert bucket.wanted(calm) == ("rhythm", 0)
    bucket.played([clip.id for clip in bucket.pool("lead", 0)])
    assert bucket.wanted(calm) == ("lead", 0), "tunes are replaced soonest"
    # It follows the game: with a fight on, the hard phrases are what is asked for.
    assert bucket.wanted([("drums", 2), ("bass", 2)])[1] == 2


def test_the_most_worn_phrase_makes_room_and_comes_back_when_no_more_can_be_made(tmp_path):
    bucket = bucket_at(tmp_path)
    fill(bucket, [("drums", 1)], each=forever.MOST + 1)
    clips = bucket.pool("drums", 1)
    bucket.played([clips[3].id, clips[3].id, clips[5].id])
    bucket.mark([clips[3].id], loved=True)                 # loved: never set aside
    gone = bucket.make_room("drums", 1)
    assert [worn.id for worn in gone] == [clips[5].id]
    assert len(bucket.pool("drums", 1)) == forever.MOST
    assert clips[5].id not in [clip["id"] for clip in bucket.describe()["clips"]]
    bucket.everything = True
    assert len(bucket.pool("drums", 1)) == forever.MOST + 1
    bucket.mark([clips[0].id], banned=True)                # banned: never again, whatever happens
    assert clips[0].id not in [clip.id for clip in bucket.pool("drums", 1)]


def test_buckets_are_kept_by_place_and_style(tmp_path):
    buckets = forever.Buckets(tmp_path / "buckets")
    knight = buckets.get("Duskwood", "knight")
    trance = buckets.get("Duskwood", "trance")
    assert knight is buckets.get("Duskwood", "knight")
    assert (knight.key, knight.bpm, knight.tonic) == ("knight/duskwood", 80, "D minor")
    assert (trance.key, trance.bpm, trance.tonic) == ("trance/duskwood", 128, "D minor")
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
    fight = forever.mix(Target(place="battle", intensity=0.80, drums=1.0, bass=1.0))
    assert forever.in_use(fight) == [("texture", 0), ("lead", 1), ("rhythm", 2), ("drums", 2), ("bass", 2)]
    assert fight["texture"]["level"] < 1.0, "the drone makes room for the band"
    long_fight = forever.mix(Target(place="battle", intensity=0.90, drums=1.0, bass=1.0))
    assert long_fight["lead"]["tier"] == 2, "the lead joins a fight that lasts"


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
        chunk = plan["chunks"][0]
        bpm = int(chunk["positive_styles"][0].split()[0])
        bars = round(chunk["duration_ms"] * bpm / 240000)
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
    assert bucket.pool("rhythm", 1) == [clip] and clip.measured["tempo_off"] == pytest.approx(0.0, abs=0.05)


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
        assert status["forever"]["pools"]["drums hard"] == 1
    finally:
        await client.close()


async def test_once_started_the_bucket_is_fed_in_real_time_and_follows_the_game(tmp_path):
    clock = Clock()
    client, app, conductor, filler = await running(tmp_path, clock=clock)
    try:
        socket = await client.ws_connect("/ws/player")
        publish(app)
        bucket = conductor.buckets.get("Elwynn Forest", "knight")
        await until(bucket.started)
        await asyncio.sleep(0.6)
        first = len(filler.asked)
        assert first == len(forever.FIRST), "phrases went on being asked for without a pause"
        # Four bars later one more is asked for, and one only.
        clock.now += 4 * 240.0 / bucket.bpm + 0.1
        await until(lambda: len(filler.asked) == first + 1)
        await asyncio.sleep(0.6)
        assert len(filler.asked) == first + 1
        # A fight: what is asked for now is hard.
        publish(app, in_combat=True)
        await asyncio.sleep(0.4)
        for _ in range(4):
            clock.now += 4 * 240.0 / bucket.bpm + 0.1
            count = len(filler.asked)
            await until(lambda: len(filler.asked) == count + 1)
        assert all(tier == 2 for _, channel, tier, _, _ in filler.asked[-4:] if channel in ("drums", "bass", "rhythm"))
        assert {channel for _, channel, _, _, _ in filler.asked[-4:]} >= {"drums", "bass"}
        assert filler.most_at_once <= music.FILL_AT_ONCE
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
        await until(lambda: len(bucket.live()) == len(forever.FIRST) - 1)
        await asyncio.sleep(0.5)
        assert [pool for _, *pool, _, _ in filler.asked].count(["lead", 0]) == 1
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
        assert len(bucket.live()) == len(forever.FIRST) - 1
    finally:
        await client.close()


async def test_the_old_place_plays_on_until_the_new_has_enough(tmp_path):
    client, app, conductor, filler = await running(tmp_path, with_filler=False)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), forever.FIRST[:5])
        westfall = conductor.buckets.get("Westfall", "knight")
        fill(westfall, [("texture", 0)])
        socket = await client.ws_connect("/ws/player")
        publish(app)
        assert (await next_of(socket, "bucket"))["bucket"]["zone"] == "elwynn-forest"
        publish(app, zone_name="Westfall")
        await asyncio.sleep(0.6)
        assert conductor.bucket.zone == "elwynn-forest", "a thin bucket took over"
        fill(westfall, forever.FIRST[1:5])
        assert (await next_of(socket, "bucket"))["bucket"]["zone"] == "westfall"
    finally:
        await client.close()


async def test_a_new_style_takes_over_as_soon_as_it_has_anything(tmp_path):
    client, app, conductor, filler = await running(tmp_path, with_filler=False)
    try:
        fill(conductor.buckets.get("Elwynn Forest", "knight"), forever.FIRST[:5])
        fill(conductor.buckets.get("Elwynn Forest", "trance"), [("texture", 0)])
        socket = await client.ws_connect("/ws/player")
        publish(app)
        assert (await next_of(socket, "bucket"))["bucket"]["genre"] == "knight"
        response = await client.post("/api/style", json={"genre": "trance"})
        assert response.status == 200
        described = (await next_of(socket, "bucket"))["bucket"]
        assert (described["genre"], described["bpm"]) == ("trance", 128)
    finally:
        await client.close()


def test_the_mix_is_what_the_player_is_sent():
    conductor = types.SimpleNamespace(forever=True, mix=None, target=Target(intensity=0.8, drums=1.0, bass=1.0),
                                      hub=types.SimpleNamespace(state=None, link=game.Link.LIVE), bucket=None,
                                      borrowed=False, scene_tag=lambda state: None)
    message = music.Conductor._target_message(conductor)
    assert message["target"]["channels"]["drums"] == {"level": 1.0, "tier": 2}
