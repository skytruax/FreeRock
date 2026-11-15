"""Experiment 1: how long until the first audio when streaming, and how fast does the rest arrive?

Asks for 30 seconds in two parts (Arrival, then the first Wander riff), streamed, and notes when
each piece of audio arrives. Also asks ElevenLabs to keep the song for later reference, to learn
whether this plan allows that. Cost: 0.5 minutes.
"""
import asyncio
import time

from common import describe, gateway, save, write_report
from freerock.audio import PcmStream
from freerock.composer import ZoneProfile, core_suite
from freerock.eleven import ElevenError

import numpy as np

FORMAT, RATE, CHANNELS = "pcm_48000", 48000, 2
ZONE = ZoneProfile(key="elwynn", bpm=120, tonic="G mixolydian",
                   colours=["chiming clean electric guitar arpeggios", "fiddle"],
                   mood=["pastoral", "sunny", "hopeful"])


async def main() -> None:
    gate = gateway()
    request = core_suite(ZONE, seed=1101, bars={"Wander A": 11}).first(2)   # 4 + 11 bars = 30 s
    report: dict = {"asked_seconds": request.parts[-1].end_ms / 1000, "plan": request.plan}
    try:
        for keep in (True, False):
            arrivals: list[tuple[float, int]] = []
            decoder = PcmStream(CHANNELS)
            pieces = []
            try:
                async with gate.stream_music(purpose="experiment 1: streaming", zone=ZONE.key,
                                             plan=request.plan, seed=request.seed, output_format=FORMAT,
                                             store_for_inpainting=keep) as stream:
                    started = time.perf_counter()
                    async for chunk in stream:
                        arrivals.append((time.perf_counter() - started, len(chunk)))
                        pieces.append(decoder.feed(chunk))
            except ElevenError as error:
                if not keep:
                    raise
                print("keeping the song for reference was refused:", error)
                report["store_for_inpainting"] = {"accepted": False, "error": str(error), "status": error.status}
                continue
            report.setdefault("store_for_inpainting", {"accepted": keep, "song_id": stream.song_id})
            break

        audio = np.concatenate(pieces)
        seconds = len(audio) / RATE
        first, total = stream.first_audio_s, stream.total_s
        # How many seconds of music had arrived at each moment, to see whether it comes steadily.
        arrived, timeline = 0, []
        for moment, size in arrivals:
            arrived += size
            timeline.append((round(moment, 2), round(arrived / (2 * CHANNELS * RATE), 2)))
        step = max(1, len(timeline) // 12)
        report.update({
            "first_audio_s": round(first, 2), "total_s": round(total, 2),
            "music_seconds": round(seconds, 2),
            "music_seconds_per_second_after_first_audio": round(seconds / max(total - first, 1e-6), 1),
            "music_seconds_per_second_overall": round(seconds / total, 1),
            "pieces": len(arrivals), "timeline_wall_s_vs_music_s": timeline[::step] + timeline[-1:],
            "headers": stream.headers,
            "measured": describe(audio, RATE, bpm=request.bpm, tonic=request.tonic),
            "files": save("s1_stream", audio, RATE),
        })
        passes = {
            "first audio within 3 s": first <= 3.0,
            "at least 3 s of music per second": seconds / total >= 3.0,
            "tempo within 1%": abs(report["measured"]["tempo"]["off_percent"]) <= 1.0,
        }
        report["passes"] = passes
        print({k: report[k] for k in ("first_audio_s", "total_s", "music_seconds",
                                      "music_seconds_per_second_overall", "store_for_inpainting")})
        print("tempo:", report["measured"]["tempo"])
        print("key:", report["measured"]["key"])
        print("passes:", passes)
    finally:
        print("report:", write_report("s1", report))
        await gate.aclose()


if __name__ == "__main__":
    asyncio.run(main())
