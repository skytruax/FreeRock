"""The paid-call gateway against a stand-in for ElevenLabs. No real request is made."""
import asyncio
import json

import httpx
import pytest

from freerock.eleven import AllowanceExceeded, ElevenError, Gateway, plan_minutes
from freerock.ledger import Ledger
from freerock.settings import Settings

KEY = "sk_test_not_a_real_key_0123456789"
PLAN = {"chunks": [
    {"text": "[Arrival]", "duration_ms": 8000, "positive_styles": ["120 BPM", "A minor"]},
    {"text": "[Wander A]", "duration_ms": 32000, "positive_styles": ["120 BPM", "A minor"]},
]}


def make_gateway(tmp_path, handler, **settings):
    """A gateway whose requests go to `handler` instead of the network."""
    config = Settings(var_dir=tmp_path, **settings)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Gateway(config, Ledger(config.ledger_path), client=client, key=KEY)


def audio_handler(pieces, seen, delay=0.0, headers=None):
    async def body():
        for piece in pieces:
            if delay:
                await asyncio.sleep(delay)
            yield piece

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body(), headers={"song-id": "song123", **(headers or {})})
    return handler


async def test_stream_passes_audio_through_and_records_it(tmp_path):
    seen = []
    pieces = [b"a" * 1000, b"b" * 2000, b"c" * 500]
    gateway = make_gateway(tmp_path, audio_handler(pieces, seen, delay=0.01))
    got = []
    async with gateway.stream_music(purpose="test suite", zone="elwynn", plan=PLAN, seed=7,
                                    output_format="pcm_48000") as stream:
        async for chunk in stream:
            got.append(chunk)
    assert b"".join(got) == b"".join(pieces)
    assert stream.finished and stream.nbytes == 3500 and stream.song_id == "song123"
    assert stream.first_audio_s is not None and stream.total_s >= stream.first_audio_s

    request = seen[0]
    assert request.url.path == "/v1/music/stream"
    assert request.url.params["output_format"] == "pcm_48000"
    sent = json.loads(request.content)
    assert sent["model_id"] == "music_v2_5", "the default model is deprecated; ours must always be named"
    assert sent["composition_plan"] == PLAN and sent["seed"] == 7
    assert request.headers["xi-api-key"] == KEY

    row = gateway.ledger.rows()[0]
    assert row["status"] == "done" and row["kind"] == "music" and row["zone"] == "elwynn"
    assert row["minutes"] == pytest.approx(40 / 60)
    assert row["bytes"] == 3500 and row["song_id"] == "song123"
    assert gateway.ledger.month_minutes() == pytest.approx(40 / 60)
    await gateway.aclose()


async def test_the_key_is_never_written_down(tmp_path):
    gateway = make_gateway(tmp_path, audio_handler([b"x"], []))
    await gateway.music(purpose="t", plan=PLAN, output_format="mp3_48000_192")
    for row in gateway.ledger.rows():
        assert KEY not in json.dumps(row)
    await gateway.aclose()


async def test_monthly_allowance_stops_the_call_before_it_is_made(tmp_path):
    seen = []
    gateway = make_gateway(tmp_path, audio_handler([b"x"], seen), monthly_minutes=1.0, reroll_reserve=0.0)
    await gateway.music(purpose="first", plan=PLAN, output_format="pcm_48000")  # 0.67 min
    with pytest.raises(AllowanceExceeded) as refusal:
        await gateway.music(purpose="second", plan=PLAN, output_format="pcm_48000")
    assert "this month's allowance" in str(refusal.value)
    assert len(seen) == 1, "the refused call must not reach ElevenLabs"
    rows = gateway.ledger.rows()
    assert rows[0]["status"] == "refused" and rows[0]["minutes"] == 0
    assert gateway.ledger.month_minutes() == pytest.approx(40 / 60)
    await gateway.aclose()


async def test_daily_allowance_and_the_reserve_for_rerolls(tmp_path):
    gateway = make_gateway(tmp_path, audio_handler([b"x"], []),
                           monthly_minutes=1.0, daily_minutes=10.0, reroll_reserve=0.5)
    # 0.67 min is over the 0.5 an ordinary call may use, but a re-roll may use the reserve.
    with pytest.raises(AllowanceExceeded):
        await gateway.music(purpose="ordinary", plan=PLAN, output_format="pcm_48000")
    await gateway.music(purpose="re-roll", plan=PLAN, output_format="pcm_48000", reroll=True)

    tight = make_gateway(tmp_path / "day", audio_handler([b"x"], []), daily_minutes=0.5)
    with pytest.raises(AllowanceExceeded) as refusal:
        await tight.music(purpose="t", plan=PLAN, output_format="pcm_48000")
    assert "today's allowance" in str(refusal.value)
    await gateway.aclose()
    await tight.aclose()


async def test_a_rejected_plan_costs_nothing_and_keeps_the_suggestion(tmp_path):
    suggestion = {"chunks": [{"text": "[Intro]", "duration_ms": 8000, "positive_styles": ["hard rock"]}]}

    def handler(request):
        return httpx.Response(400, json={"detail": {
            "status": "bad_composition_plan", "message": "The plan names an artist.",
            "data": {"composition_plan_suggestion": suggestion}}})

    gateway = make_gateway(tmp_path, handler)
    with pytest.raises(ElevenError) as rejected:
        await gateway.music(purpose="t", plan=PLAN, output_format="pcm_48000")
    error = rejected.value
    assert error.http_status == 400 and error.status == "bad_composition_plan"
    assert error.suggestion == suggestion and "names an artist" in str(error)
    assert KEY not in str(error)
    row = gateway.ledger.rows()[0]
    assert row["status"] == "failed" and row["minutes"] == 0 and row["http_status"] == 400
    assert gateway.ledger.month_minutes() == 0
    await gateway.aclose()


async def test_a_download_that_breaks_part_way_is_still_counted(tmp_path):
    async def body():
        yield b"some audio"
        raise httpx.ReadError("connection lost")

    gateway = make_gateway(tmp_path, lambda request: httpx.Response(200, content=body()))
    with pytest.raises(httpx.ReadError):
        await gateway.music(purpose="t", plan=PLAN, output_format="pcm_48000")
    row = gateway.ledger.rows()[0]
    assert row["status"] == "failed" and row["minutes"] == pytest.approx(40 / 60)
    assert "connection lost" in row["error"] and row["bytes"] == len(b"some audio")
    await gateway.aclose()


async def test_stopping_early_is_recorded_and_counted(tmp_path):
    gateway = make_gateway(tmp_path, audio_handler([b"a", b"b", b"c"], []))
    async with gateway.stream_music(purpose="t", plan=PLAN, output_format="pcm_48000") as stream:
        async for _ in stream:
            break
    row = gateway.ledger.rows()[0]
    assert row["status"] == "failed" and "stopped before the end" in row["error"]
    assert row["minutes"] == pytest.approx(40 / 60)
    await gateway.aclose()


async def test_prompt_requests_and_argument_rules(tmp_path):
    seen = []
    gateway = make_gateway(tmp_path, audio_handler([b"x"], seen))
    await gateway.music(purpose="t", prompt="hard rock", music_length_ms=3000,
                        force_instrumental=True, output_format="pcm_48000")
    sent = json.loads(seen[0].content)
    assert sent == {"model_id": "music_v2_5", "prompt": "hard rock", "music_length_ms": 3000,
                    "force_instrumental": True}
    assert gateway.ledger.rows()[0]["minutes"] == pytest.approx(0.05)
    with pytest.raises(ValueError):
        await gateway.music(purpose="t", prompt="x", output_format="pcm_48000")  # no length
    with pytest.raises(ValueError):
        await gateway.music(purpose="t", prompt="x", music_length_ms=3000, seed=1, output_format="pcm_48000")
    with pytest.raises(ValueError):
        await gateway.music(purpose="t", plan=PLAN, prompt="x", music_length_ms=3000, output_format="pcm_48000")
    with pytest.raises(ValueError):
        await gateway.music(purpose="t", plan=PLAN, force_instrumental=True, output_format="pcm_48000")
    await gateway.aclose()


async def test_sound_effects_are_counted_by_their_seconds(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"clip", headers={"character-cost": "320"})

    gateway = make_gateway(tmp_path, handler)
    audio, delivery = await gateway.sound_effect(purpose="drone", text="hurdy-gurdy drone on A",
                                                 duration_seconds=8.0, loop=True,
                                                 output_format="mp3_44100_192")
    assert audio == b"clip" and delivery.headers["character-cost"] == "320"
    assert seen[0].url.path == "/v1/sound-generation"
    assert json.loads(seen[0].content) == {"text": "hurdy-gurdy drone on A", "duration_seconds": 8.0, "loop": True}
    row = gateway.ledger.rows()[0]
    assert row["kind"] == "sfx" and row["minutes"] == pytest.approx(8 / 60) and row["status"] == "done"
    await gateway.aclose()


async def test_an_account_error_is_reported_in_full(tmp_path):
    def handler(request):
        return httpx.Response(401, json={"detail": {
            "type": "authentication_error", "code": "unauthorized", "status": "quota_exceeded",
            "message": "This request exceeds your quota."}})

    gateway = make_gateway(tmp_path, handler)
    with pytest.raises(ElevenError) as failure:
        await gateway.subscription()
    assert failure.value.status == "quota_exceeded" and "exceeds your quota" in str(failure.value)
    await gateway.aclose()


def test_plan_minutes_counts_generated_and_reused_parts():
    plan = {"chunks": [
        {"text": "[A]", "duration_ms": 30000, "positive_styles": []},
        {"song_id": "s", "range": {"start_ms": 1000, "end_ms": 31000}},
    ]}
    assert plan_minutes(plan) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        plan_minutes({"chunks": [{"text": "no length"}]})
