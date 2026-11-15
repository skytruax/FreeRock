"""The one place FreeRock can spend ElevenLabs credits.

Every call that costs something goes through `Gateway`. Before a request goes out it checks the
monthly and daily allowance and writes a ledger row; afterwards it closes the row. Nothing else in
FreeRock talks to ElevenLabs, so the allowance cannot be passed by accident.

The key is read when the first request is made and is never logged, stored or put in an error.
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from .ledger import Ledger
from .settings import Settings, find_key


class AllowanceExceeded(RuntimeError):
    """FreeRock refused to make a call because it would pass the monthly or daily allowance."""


class ElevenError(RuntimeError):
    """ElevenLabs answered with an error. Carries everything it said."""

    def __init__(self, http_status: int, detail: Any, raw: str):
        self.http_status = http_status
        self.detail = detail
        self.raw = raw
        super().__init__(self._describe())

    @classmethod
    def from_response(cls, http_status: int, raw: bytes) -> "ElevenError":
        text = raw.decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            return cls(http_status, None, text)
        detail = body.get("detail", body) if isinstance(body, dict) else body
        return cls(http_status, detail, text)

    @property
    def status(self) -> str | None:
        """ElevenLabs' short name for what went wrong, such as bad_prompt or quota_exceeded."""
        if isinstance(self.detail, dict):
            for name in ("status", "code", "type"):
                if isinstance(self.detail.get(name), str):
                    return self.detail[name]
        return None

    @property
    def message(self) -> str:
        if isinstance(self.detail, dict) and isinstance(self.detail.get("message"), str):
            return self.detail["message"]
        if isinstance(self.detail, str):
            return self.detail
        return self.raw[:500]

    @property
    def suggestion(self) -> Any:
        """The wording ElevenLabs proposes instead of a prompt or plan it rejected, if it gave one."""
        if not isinstance(self.detail, dict):
            return None
        data = self.detail.get("data")
        if not isinstance(data, dict):
            return None
        return data.get("composition_plan_suggestion") or data.get("prompt_suggestion")

    def _describe(self) -> str:
        return "ElevenLabs answered HTTP %d (%s): %s" % (
            self.http_status, self.status or "no status given", self.message)


@dataclass
class Delivery:
    """What came back from one paid call."""
    call_id: int
    nbytes: int
    first_audio_s: float | None
    total_s: float | None
    song_id: str | None
    content_type: str | None
    headers: dict[str, str]


# Response headers worth keeping with a result: what was made, what it cost, how busy the account is.
KEPT_HEADERS = ("song-id", "character-cost", "request-id", "content-type",
                "current-concurrent-requests", "maximum-concurrent-requests")


def plan_minutes(plan: dict[str, Any]) -> float:
    """Length of the music a composition plan asks for, in minutes."""
    total_ms = 0
    for chunk in plan.get("chunks", []):
        if "duration_ms" in chunk:
            total_ms += chunk["duration_ms"]
        elif "range" in chunk:  # a slice of an earlier song placed into this one
            total_ms += chunk["range"]["end_ms"] - chunk["range"]["start_ms"]
        else:
            raise ValueError("A plan chunk has neither duration_ms nor range: %r" % (chunk,))
    return total_ms / 60000.0


class MusicStream:
    """Audio arriving from ElevenLabs. Iterate it for the bytes; the timings fill in as it goes."""

    def __init__(self, response: httpx.Response, started: float, call_id: int):
        self._response = response
        self._started = started
        self.call_id = call_id  # this call's row in the ledger
        self.nbytes = 0
        self.first_audio_s: float | None = None
        self.total_s: float | None = None
        self.finished = False

    @property
    def headers(self) -> dict[str, str]:
        return {name: self._response.headers[name] for name in KEPT_HEADERS
                if name in self._response.headers}

    @property
    def song_id(self) -> str | None:
        return self._response.headers.get("song-id")

    @property
    def content_type(self) -> str | None:
        return self._response.headers.get("content-type")

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_bytes():
            if not chunk:
                continue
            if self.first_audio_s is None:
                self.first_audio_s = time.perf_counter() - self._started
            self.nbytes += len(chunk)
            yield chunk
        self.total_s = time.perf_counter() - self._started
        self.finished = True

    async def read(self) -> bytes:
        parts = [chunk async for chunk in self]
        return b"".join(parts)


class Gateway:
    def __init__(self, settings: Settings | None = None, ledger: Ledger | None = None,
                 client: httpx.AsyncClient | None = None, key: str | None = None):
        self.settings = settings or Settings()
        self.ledger = ledger or Ledger(self.settings.ledger_path)
        self._key = key
        self._client = client or httpx.AsyncClient(
            # A three-minute suite takes around half a minute to make; the long read timeout is
            # for the calls that return everything at once.
            timeout=httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        if self._key is None:
            _, self._key = find_key()
        return {"xi-api-key": self._key}

    def _url(self, path: str) -> str:
        return self.settings.api_base.rstrip("/") + path

    # --- the allowance ---------------------------------------------------------------------------

    def remaining(self, *, reroll: bool = False) -> tuple[float, float]:
        """(minutes left this month, minutes left today). A re-roll may dip into the reserve."""
        monthly = self.settings.monthly_minutes
        if not reroll:
            monthly *= 1.0 - self.settings.reroll_reserve
        return (monthly - self.ledger.month_minutes(),
                self.settings.daily_minutes - self.ledger.day_minutes())

    def check_allowance(self, minutes: float, *, kind: str, purpose: str, zone: str | None = None,
                        reroll: bool = False) -> None:
        month_left, day_left = self.remaining(reroll=reroll)
        problem = None
        if minutes > month_left + 1e-9:
            problem = "%.2f min asked for, %.2f left of this month's allowance" % (minutes, max(month_left, 0.0))
        elif minutes > day_left + 1e-9:
            problem = "%.2f min asked for, %.2f left of today's allowance" % (minutes, max(day_left, 0.0))
        if problem:
            self.ledger.refused(kind=kind, purpose=purpose, minutes=minutes, error=problem, zone=zone)
            raise AllowanceExceeded("FreeRock did not make this call (%s): %s." % (purpose, problem))

    # --- music -----------------------------------------------------------------------------------

    @asynccontextmanager
    async def stream_music(self, *, purpose: str, output_format: str, zone: str | None = None,
                           plan: dict[str, Any] | None = None, prompt: str | None = None,
                           music_length_ms: int | None = None, seed: int | None = None,
                           force_instrumental: bool | None = None,
                           store_for_inpainting: bool = False,
                           reroll: bool = False) -> AsyncIterator[MusicStream]:
        """Asks for music and hands back the audio as it is made.

        Give either a composition plan or a prompt with a length. Use as
        `async with gateway.stream_music(...) as stream: async for chunk in stream: ...`.
        """
        if (plan is None) == (prompt is None):
            raise ValueError("Give exactly one of plan or prompt.")
        body: dict[str, Any] = {"model_id": self.settings.model_id}
        if plan is not None:
            if music_length_ms is not None or force_instrumental is not None:
                raise ValueError("music_length_ms and force_instrumental only work with a prompt.")
            body["composition_plan"] = plan
            minutes = plan_minutes(plan)
            if seed is not None:
                body["seed"] = seed
        else:
            if music_length_ms is None:
                raise ValueError("A prompt needs music_length_ms, so the cost is known beforehand.")
            if seed is not None:
                raise ValueError("ElevenLabs accepts a seed only with a composition plan.")
            body["prompt"] = prompt
            body["music_length_ms"] = music_length_ms
            if force_instrumental is not None:
                body["force_instrumental"] = force_instrumental
            minutes = music_length_ms / 60000.0
        if store_for_inpainting:
            body["store_for_inpainting"] = True

        self.check_allowance(minutes, kind="music", purpose=purpose, zone=zone, reroll=reroll)
        call_id = self.ledger.start(kind="music", purpose=purpose, minutes=minutes, zone=zone,
                                    model=self.settings.model_id,
                                    request={"output_format": output_format, **body})
        started = time.perf_counter()
        stream: MusicStream | None = None
        try:
            async with self._client.stream(
                    "POST", self._url("/v1/music/stream"), params={"output_format": output_format},
                    json=body, headers=self._headers()) as response:
                if response.status_code != 200:
                    raise ElevenError.from_response(response.status_code, await response.aread())
                stream = MusicStream(response, started, call_id)
                yield stream
        except ElevenError as error:
            # Turned down before any audio was made: it cost nothing.
            self.ledger.fail(call_id, error=str(error), keep_minutes=False, http_status=error.http_status)
            raise
        except BaseException as error:
            got_audio = stream is not None and stream.nbytes > 0
            self.ledger.fail(call_id, error=repr(error), keep_minutes=got_audio,
                             http_status=200 if stream is not None else None,
                             nbytes=stream.nbytes if stream else None,
                             first_audio_s=stream.first_audio_s if stream else None)
            raise
        if not stream.finished:
            # The caller stopped listening part-way. ElevenLabs made the audio all the same.
            self.ledger.fail(call_id, error="the download was stopped before the end",
                             keep_minutes=True, http_status=200, nbytes=stream.nbytes,
                             first_audio_s=stream.first_audio_s)
        else:
            self.ledger.finish(call_id, http_status=200, song_id=stream.song_id, nbytes=stream.nbytes,
                               first_audio_s=stream.first_audio_s, total_s=stream.total_s)

    async def music(self, **kwargs: Any) -> tuple[bytes, Delivery]:
        """The same as stream_music, collected into one piece."""
        async with self.stream_music(**kwargs) as stream:
            audio = await stream.read()
        return audio, Delivery(call_id=stream.call_id, nbytes=stream.nbytes,
                               first_audio_s=stream.first_audio_s, total_s=stream.total_s,
                               song_id=stream.song_id, content_type=stream.content_type,
                               headers=stream.headers)

    async def create_plan(self, prompt: str, music_length_ms: int) -> dict[str, Any]:
        """Has ElevenLabs turn a prompt into a composition plan. Free, so it is not in the ledger."""
        response = await self._client.post(
            self._url("/v1/music/plan"), headers=self._headers(),
            json={"prompt": prompt, "music_length_ms": music_length_ms,
                  "model_id": self.settings.model_id})
        if response.status_code != 200:
            raise ElevenError.from_response(response.status_code, response.content)
        return response.json()

    # --- sound effects, stems, account -------------------------------------------------------

    async def sound_effect(self, *, purpose: str, text: str, duration_seconds: float,
                           output_format: str, loop: bool = False,
                           prompt_influence: float | None = None,
                           model_id: str | None = None) -> tuple[bytes, Delivery]:
        """A short clip from the sound-effects endpoint. Its seconds count against the allowance."""
        body: dict[str, Any] = {"text": text, "duration_seconds": duration_seconds, "loop": loop}
        if prompt_influence is not None:
            body["prompt_influence"] = prompt_influence
        if model_id is not None:
            body["model_id"] = model_id
        minutes = duration_seconds / 60.0
        return await self._paid_post(
            "/v1/sound-generation", kind="sfx", purpose=purpose, minutes=minutes,
            params={"output_format": output_format}, json_body=body, model=model_id)

    async def separate_stems(self, *, purpose: str, audio: bytes, filename: str, minutes: float,
                             variation: str = "six_stems_v1",
                             output_format: str | None = None) -> tuple[bytes, Delivery]:
        """ElevenLabs' own stem separation; returns a ZIP. Counted as the length of the audio sent."""
        params = {"output_format": output_format} if output_format else None
        return await self._paid_post(
            "/v1/music/stem-separation", kind="stems", purpose=purpose, minutes=minutes,
            params=params, files={"file": (filename, audio)}, data={"stem_variation_id": variation},
            request_note={"filename": filename, "bytes": len(audio), "stem_variation_id": variation})

    async def _paid_post(self, path: str, *, kind: str, purpose: str, minutes: float,
                         params: dict[str, str] | None = None, json_body: Any = None,
                         files: Any = None, data: Any = None, model: str | None = None,
                         request_note: Any = None) -> tuple[bytes, Delivery]:
        self.check_allowance(minutes, kind=kind, purpose=purpose)
        call_id = self.ledger.start(kind=kind, purpose=purpose, minutes=minutes, model=model,
                                    request=request_note if request_note is not None else json_body)
        started = time.perf_counter()
        try:
            response = await self._client.post(self._url(path), params=params, json=json_body,
                                               files=files, data=data, headers=self._headers())
        except BaseException as error:
            # No answer at all: nothing came back, so nothing is counted.
            self.ledger.fail(call_id, error=repr(error), keep_minutes=False)
            raise
        total = time.perf_counter() - started
        if response.status_code != 200:
            error = ElevenError.from_response(response.status_code, response.content)
            self.ledger.fail(call_id, error=str(error), keep_minutes=False,
                             http_status=response.status_code, total_s=total)
            raise error
        self.ledger.finish(call_id, http_status=200, song_id=response.headers.get("song-id"),
                           nbytes=len(response.content), total_s=total)
        headers = {name: response.headers[name] for name in KEPT_HEADERS if name in response.headers}
        return response.content, Delivery(
            call_id=call_id, nbytes=len(response.content), first_audio_s=None, total_s=total,
            song_id=response.headers.get("song-id"),
            content_type=response.headers.get("content-type"), headers=headers)

    async def subscription(self) -> dict[str, Any]:
        """The account's plan and credit balance. Free."""
        response = await self._client.get(self._url("/v1/user/subscription"), headers=self._headers())
        if response.status_code != 200:
            raise ElevenError.from_response(response.status_code, response.content)
        return response.json()
