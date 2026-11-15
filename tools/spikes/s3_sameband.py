"""Experiments 3 and 4: does a second request for the same zone sound like the same band?

Later sets for a zone are separate requests from its core suite, so this decides how they are
made. Experiment 3 asks for a new Wander riff and a Boss part with a new seed and nothing else to
go on. Experiment 4 asks for the same Wander riff while telling ElevenLabs to stay close to thirty
seconds of the core suite. Both are compared with the core suite's Wander A.
Cost: 1.07 + 0.53 minutes.

    cd app && uv run --no-sync python ../tools/spikes/s3_sameband.py           # generate and compare
    cd app && uv run --no-sync python ../tools/spikes/s3_sameband.py --reuse   # compare stored audio
"""
import asyncio
import sys

import numpy as np

from common import OUT, describe, gateway, read_report, save, write_report
from freerock import analysis, render
from freerock.audio import PcmStream, read_audio
from freerock.composer import Reference, ZoneProfile, build
from freerock.eleven import ElevenError

FORMAT, RATE, CHANNELS = "pcm_48000", 48000, 2
ZONE = ZoneProfile(key="elwynn", bpm=120, tonic="G mixolydian",
                   colours=["chiming clean electric guitar arpeggios", "fiddle"],
                   mood=["pastoral", "sunny", "hopeful"])
BAR = RATE * 60 * 4 // ZONE.bpm


async def generate(gate, purpose: str, request) -> tuple[np.ndarray, dict]:
    decoder, pieces = PcmStream(CHANNELS), []
    async with gate.stream_music(purpose=purpose, zone=ZONE.key, plan=request.plan, seed=request.seed,
                                 output_format=FORMAT, store_for_inpainting=True) as stream:
        async for chunk in stream:
            pieces.append(decoder.feed(chunk))
    return np.concatenate(pieces), {"song_id": stream.song_id, "first_audio_s": round(stream.first_audio_s, 2),
                                    "total_s": round(stream.total_s, 2)}


def compare(label: str, suite: np.ndarray, new: np.ndarray, yardstick: float) -> dict:
    """Holds 16 bars of new music against the core suite's Wander A."""
    wander_a = suite[4 * BAR:20 * BAR]
    new_riff = new[:16 * BAR]
    measured = describe(new_riff, RATE, bpm=ZONE.bpm, tonic=ZONE.tonic)
    reference = describe(wander_a, RATE, bpm=ZONE.bpm, tonic=ZONE.tonic)
    difference = analysis.profile_difference_db(analysis.band_profile(wander_a, RATE),
                                                analysis.band_profile(new_riff, RATE))
    # Cut back and forth between the two every four bars and see whether the beat survives.
    both = np.concatenate([suite, new])
    offset = len(suite)
    spans = []
    for cell in range(3):
        spans.append((4 * BAR + cell * 4 * BAR, 4 * BAR + (cell + 1) * 4 * BAR))          # Wander A
        spans.append((offset + cell * 4 * BAR, offset + (cell + 1) * 4 * BAR))             # the new riff
    splice = render.sequence(both, spans, RATE)
    grid = analysis.fit_grid(splice, RATE, ZONE.bpm)
    result = {
        "new_riff": measured, "core_wander_a": reference,
        "tuning_gap_cents": round(measured["key"]["tuning_cents"] - reference["key"]["tuning_cents"], 1),
        "loudness_gap_db": round(measured["loudness_lufs"] - reference["loudness_lufs"], 2),
        "tone_difference_db": round(difference, 2),
        "tone_difference_between_two_parts_of_the_core_suite_db": round(yardstick, 2),
        "splice": {"measured_bpm": round(grid.bpm, 3), "jitter_ms": round(grid.jitter_ms, 2),
                   "outliers": grid.outliers, "beats_checked": grid.beats_checked,
                   "what": "Four bars of the core suite's Wander A, then four of the new riff, three times over.",
                   "files": save(label + "_splice", render.limit(splice), RATE)},
    }
    print("%s: tempo %+.3f%%, tuning gap %+.1f cents, loudness gap %+.1f dB, tone difference %.2f dB "
          "(two parts of the core suite differ by %.2f), splice %d of %d beats off"
          % (label, measured["tempo"]["off_percent"], result["tuning_gap_cents"], result["loudness_gap_db"],
             difference, yardstick, grid.outliers, grid.beats_checked))
    return result


async def main() -> None:
    reuse = "--reuse" in sys.argv
    suite, rate = read_audio(OUT / "s2_suite.flac")
    if rate != RATE:
        raise RuntimeError("The stored suite is at %d Hz, expected %d" % (rate, RATE))
    core_song = read_report("s2_delivery")["delivery"]["song_id"]
    yardstick = analysis.profile_difference_db(analysis.band_profile(suite[4 * BAR:20 * BAR], RATE),
                                               analysis.band_profile(suite[20 * BAR:36 * BAR], RATE))
    report: dict = {"core_song_id": core_song}
    gate = gateway()
    try:
        # Experiment 3: a new seed and nothing else.
        plain = build(ZONE, ("Wander C", "Boss"), seed=2203)
        if reuse:
            audio3 = read_audio(OUT / "s3_unconditioned.flac")[0]
            report["s3_delivery"] = read_report("s3_delivery")["s3"]
        else:
            audio3, report["s3_delivery"] = await generate(gate, "experiment 3: second request, no reference", plain)
            save("s3_unconditioned", audio3, RATE)
            write_report("s3_delivery", {"s3": report["s3_delivery"]})
        report["s3"] = compare("s3", suite, audio3, yardstick)
        report["s3"]["boss"] = describe(audio3[16 * BAR:32 * BAR], RATE, bpm=ZONE.bpm, tonic=ZONE.tonic)

        # Experiment 4: the same riff, told to stay close to 30 s of the core suite's Wander A.
        guided = build(ZONE, ("Wander C",), seed=2204, reference=Reference(core_song, 8000, 38000))
        try:
            if reuse and (OUT / "s4_conditioned.flac").is_file():
                audio4 = read_audio(OUT / "s4_conditioned.flac")[0]
                report["s4_delivery"] = read_report("s4_delivery")["s4"]
            else:
                audio4, report["s4_delivery"] = await generate(gate, "experiment 4: second request, with reference", guided)
                save("s4_conditioned", audio4, RATE)
                write_report("s4_delivery", {"s4": report["s4_delivery"]})
            report["s4"] = {"accepted": True, **compare("s4", suite, audio4, yardstick)}
        except ElevenError as error:
            print("the reference was refused:", error)
            report["s4"] = {"accepted": False, "error": str(error), "status": error.status,
                            "suggestion": error.suggestion}

        s3 = report["s3"]
        report["passes"] = {
            "3: tempo within 0.5%": abs(s3["new_riff"]["tempo"]["off_percent"]) <= 0.5,
            "3: tuning within 10 cents of the core suite": abs(s3["tuning_gap_cents"]) <= 10,
            "3: cutting between the two keeps the beat": s3["splice"]["outliers"] == 0,
            "4: the reference was accepted": report["s4"]["accepted"],
        }
        if report["s4"]["accepted"]:
            s4 = report["s4"]
            report["passes"]["4: closer in tone to the core suite than 3 is"] = \
                s4["tone_difference_db"] < s3["tone_difference_db"]
            report["passes"]["4: cutting between the two keeps the beat"] = s4["splice"]["outliers"] == 0
        for line, passed in report["passes"].items():
            print("  %s  %s" % ("PASS" if passed else "FAIL", line))
    finally:
        print("report:", write_report("s3", report))
        await gate.aclose()


if __name__ == "__main__":
    asyncio.run(main())
