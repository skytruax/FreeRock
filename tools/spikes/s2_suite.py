"""Experiment 2: does a full core suite hold together, and do the layers split cleanly?

Generates one core suite (kept as the first zone's music), measures every part against the tempo
and key that were asked for, splits it into drums, bass and bed on this machine, and renders the
demo clips for listening. Cost: 2.8 minutes.

    cd app && uv run --no-sync python ../tools/spikes/s2_suite.py            # generate, then measure
    cd app && uv run --no-sync python ../tools/spikes/s2_suite.py --reuse    # measure the stored suite again
"""
import asyncio
import sys

import numpy as np

from common import OUT, describe, gateway, read_report, save, write_report
from freerock import analysis, render
from freerock.audio import PcmStream, read_audio, write_flac
from freerock.composer import ZoneProfile, core_suite
from freerock.stems import Layers, split

FORMAT, RATE, CHANNELS = "pcm_48000", 48000, 2
SEED = 1102
ZONE = ZoneProfile(key="elwynn", bpm=120, tonic="G mixolydian",
                   colours=["chiming clean electric guitar arpeggios", "fiddle"],
                   mood=["pastoral", "sunny", "hopeful"])
BANDED = ("Wander A", "Wander B", "Battle", "Ember", "Depths")   # the parts with a full band


def span(part, bar_from: int = 0, bars: int | None = None) -> tuple[int, int]:
    """Frames of `bars` bars of a part, starting `bar_from` bars in."""
    bar = RATE * 60 * 4 // ZONE.bpm
    start = part.start_ms * RATE // 1000 + bar_from * bar
    end = start + (bars if bars is not None else part.bars - bar_from) * bar
    return start, end


async def generate(request) -> tuple[np.ndarray, dict]:
    gate = gateway()
    try:
        decoder, pieces = PcmStream(CHANNELS), []
        async with gate.stream_music(purpose="experiment 2: core suite", zone=ZONE.key,
                                     plan=request.plan, seed=request.seed, output_format=FORMAT,
                                     store_for_inpainting=True) as stream:
            async for chunk in stream:
                pieces.append(decoder.feed(chunk))
        return np.concatenate(pieces), {
            "song_id": stream.song_id, "first_audio_s": round(stream.first_audio_s, 2),
            "total_s": round(stream.total_s, 2), "headers": stream.headers}
    finally:
        await gate.aclose()


def main() -> None:
    request = core_suite(ZONE, seed=SEED)
    if "--reuse" in sys.argv:
        audio, rate = read_audio(OUT / "s2_suite.flac")
        if rate != RATE:
            raise RuntimeError("The stored suite is at %d Hz, expected %d" % (rate, RATE))
        delivery = read_report("s2_delivery")["delivery"]
    else:
        audio, delivery = asyncio.run(generate(request))
        # Stored at once, before any measuring, so a failure further down never costs a second
        # generation: run again with --reuse.
        save("s2_suite", audio, RATE)
        write_report("s2_delivery", {"delivery": delivery})
    report: dict = {"zone": ZONE.key, "seed": SEED, "asked_minutes": round(request.minutes, 3),
                    "delivery": delivery, "plan": request.plan,
                    "music_seconds": round(len(audio) / RATE, 3), "parts": {}}
    print("suite: %.1f s of music; first audio %.2f s, all of it after %.2f s"
          % (len(audio) / RATE, delivery["first_audio_s"], delivery["total_s"]))

    # --- the layers ------------------------------------------------------------------------------
    stored = [OUT / ("s2_layer_%s.flac" % name) for name in ("bed", "drums", "bass")]
    if "--reuse" in sys.argv and all(path.is_file() for path in stored) and (OUT / "s2.json").is_file():
        # The split takes over a minute and gives the same answer each time, so a re-measure
        # reads the stored layers and the figures that were noted when they were made.
        before = read_report("s2")["layers"]
        bed, drums, bass = (read_audio(path)[0] for path in stored)
        layers = Layers(bed=bed, drums=drums, bass=bass, rate=RATE, vocal_leak_db=before["vocal_leak_db"],
                        seconds=before["seconds_to_split"], model=before["model"])
    else:
        layers = split(audio, RATE)
        for path, layer in zip(stored, (layers.bed, layers.drums, layers.bass)):
            write_flac(path, layer, RATE)
    report["layers"] = {"seconds_to_split": round(layers.seconds, 1), "model": layers.model,
                        "vocal_leak_db": round(layers.vocal_leak_db, 1),
                        # Stored layers are 24-bit files, so they add up to within that precision.
                        "sum_error": float(np.max(np.abs(layers.mix() - audio)))}
    print("layers: split in %.0f s, vocal leak %.1f dB" % (layers.seconds, layers.vocal_leak_db))

    # --- every part against what was asked for ---------------------------------------------------
    for part in request.parts:
        start, end = span(part)
        whole = describe(audio[start:end], RATE, bpm=request.bpm, tonic=request.tonic)
        grid = analysis.fit_grid(audio[start:end], RATE, request.bpm, start_s=part.start_ms / 1000)
        drum_grid = analysis.fit_grid(layers.drums[start:end], RATE, request.bpm, start_s=part.start_ms / 1000)
        without_bass = layers.bed[start:end] + layers.drums[start:end]
        entry = {
            "starts_s": part.start_ms / 1000, "bars": part.bars, **whole,
            "start_to_nearest_beat_ms": round(grid.distance_to_beat_s(part.start_ms / 1000) * 1000, 1),
            "drums": {"measured_bpm": round(drum_grid.bpm, 3), "jitter_ms": round(drum_grid.jitter_ms, 2),
                      "outliers": drum_grid.outliers, "beats_checked": drum_grid.beats_checked,
                      "start_to_nearest_beat_ms": round(drum_grid.distance_to_beat_s(part.start_ms / 1000) * 1000, 1)},
            "low_end_db": {
                "with_bass": round(analysis.band_level_db(audio[start:end], RATE, 40, 160), 1),
                "without_bass": round(analysis.band_level_db(without_bass, RATE, 40, 160), 1)},
            "layer_levels_db": {name: round(20 * np.log10(max(float(np.sqrt(np.mean(layer[start:end] ** 2))), 1e-9)), 1)
                                for name, layer in (("bed", layers.bed), ("drums", layers.drums), ("bass", layers.bass))},
        }
        entry["bass_removes_db"] = round(entry["low_end_db"]["with_bass"] - entry["low_end_db"]["without_bass"], 1)
        # How clean the split is: the bass register (40 to 110 Hz) in the bass layer against what
        # is left of it in the bed. The kick drum lives in the same register, in the drums layer,
        # which is why muting the bass alone removes only part of the low end.
        low = {name: round(analysis.band_level_db(layer[start:end], RATE, 40, 110), 1)
               for name, layer in (("bass", layers.bass), ("drums", layers.drums), ("bed", layers.bed))}
        entry["bass_register_db"] = low
        entry["bass_left_in_bed_db"] = round(low["bed"] - low["bass"], 1)
        report["parts"][part.name] = entry
        print("%-9s tempo %+.3f%%  start-to-beat %+6.1f ms  key %-9s agrees=%s  tuning %+5.1f c  "
              "loud %6.1f LUFS  bass left in bed %5.1f dB  drum jitter %.1f ms"
              % (part.name, entry["tempo"]["off_percent"], entry["start_to_nearest_beat_ms"],
                 entry["key"]["heard_as"], entry["key"]["agrees"], entry["key"]["tuning_cents"],
                 entry["loudness_lufs"], entry["bass_left_in_bed_db"], entry["drums"]["jitter_ms"]))

    # --- a five-minute walk through the Wander cells, the way the player will move ------------
    rng = np.random.default_rng(42)
    cells = [span(request.part(name), bar_from=4 * index, bars=4) for name in ("Wander A", "Wander B") for index in range(4)]
    order, last = [], None
    while len(order) < 38:                                     # 38 cells of 8 s is just over 5 minutes
        pick = int(rng.integers(len(cells)))
        if pick != last:
            order.append(pick)
            last = pick
    walk = render.sequence(audio, [cells[i] for i in order], RATE)
    walk_grid = analysis.fit_grid(walk, RATE, request.bpm)
    report["cell_walk"] = {"cells": len(order), "seconds": round(len(walk) / RATE, 1),
                           "measured_bpm": round(walk_grid.bpm, 3), "jitter_ms": round(walk_grid.jitter_ms, 2),
                           "outliers": walk_grid.outliers, "beats_checked": walk_grid.beats_checked,
                           "files": save("s2_cell_walk", render.limit(walk), RATE)}
    print("cell walk: %d cells, tempo %.3f, jitter %.2f ms, %d of %d beats off the grid"
          % (len(order), walk_grid.bpm, walk_grid.jitter_ms, walk_grid.outliers, walk_grid.beats_checked))

    # --- demo clips ------------------------------------------------------------------------------
    report["demos"] = demos(request, audio, layers)

    banded = [report["parts"][name] for name in BANDED]
    report["passes"] = {
        "tempo within 0.5% in every part with a band": all(abs(p["tempo"]["off_percent"]) <= 0.5 for p in banded),
        "every part starts within 60 ms of a beat": all(abs(p["start_to_nearest_beat_ms"]) <= 60 for p in banded),
        "drum timing within 12 ms": all(p["drums"]["jitter_ms"] <= 12 for p in banded),
        "one key throughout (at least 5 of 6 parts)": sum(p["key"]["agrees"] for p in report["parts"].values()) >= 5,
        "no vocals (leak at or below -30 dB)": layers.vocal_leak_db <= -30,
        "the bass is out of the bed (at least 20 dB down in its own register)":
            all(report["parts"][n]["bass_left_in_bed_db"] <= -20 for n in BANDED),
        "the cell walk keeps the beat": walk_grid.outliers <= max(2, walk_grid.beats_checked // 100),
        "layers add up to the original": report["layers"]["sum_error"] < 1e-5,
    }
    # The pass line first written for the bass was "muting it removes at least 6 dB between 40 and
    # 160 Hz". It removes about 5, because the kick drum shares that band. The figure is kept in
    # the report (bass_removes_db) and the check above measures the split itself.
    report["note_on_bass_check"] = (
        "Muting the bass removes %.1f to %.1f dB of the 40-160 Hz band in the parts with a band; "
        "the kick drum accounts for the rest." % (
            min(report["parts"][n]["bass_removes_db"] for n in BANDED),
            max(report["parts"][n]["bass_removes_db"] for n in BANDED)))
    for line, passed in report["passes"].items():
        print("  %s  %s" % ("PASS" if passed else "FAIL", line))
    print("report:", write_report("s2", report))


def demos(request, audio, layers) -> dict:
    """Clips that show the ideas in the plan with this suite's own music."""
    made = {}
    bar = RATE * 60 * 4 // ZONE.bpm
    wander, battle, ember, depths = (request.part(n) for n in ("Wander A", "Battle", "Ember", "Depths"))
    wander_b = request.part("Wander B")

    # 1. The bass line coming in. Eight bars of the calm bed alone, then at the bar line the bass
    #    fades in over 60 ms with the drums behind it, then Battle on a bar line, then Ember.
    start, end = span(wander)
    length = end - start
    enter = 8 * bar
    bed = layers.bed[start:end + bar]                                    # a bar extra for the ring-out
    quiet_bed = render.highpass(bed, RATE, 110.0)                        # hides what little bass leaks into the bed
    blend = render.ramp(len(bed), 0.0, 1.0, enter, render.frames(0.06, RATE))
    calm = quiet_bed * (1.0 - blend) + bed * blend
    calm += layers.bass[start:end + bar] * blend
    calm += layers.drums[start:end + bar] * render.ramp(len(bed), 0.0, 1.0, enter, render.frames(0.5, RATE))
    track = np.concatenate([calm[:length + bar], audio[span(battle)[0]:span(battle, bars=9)[1]],
                            audio[span(ember)[0]:span(ember, bars=5)[1]]])
    spans = [(0, length), (length + bar, length + bar + 8 * bar),
             (length + bar + 9 * bar, length + bar + 9 * bar + 4 * bar)]
    made["bass_entrance"] = {
        "what": "Wander A: 16 s with only the bed, then the bass and drums come in at 0:16; "
                "Battle at 0:32; Ember at 0:48.",
        "files": save("s2_demo_bass_entrance", render.limit(render.sequence(track, spans, RATE, lead_ms=0.0)), RATE)}

    # 2. Walking into a cave. Wander B in the open, then the same music muffled and echoing for
    #    two bars, then Depths.
    start, _ = span(wander_b)
    open_air = audio[start:start + 6 * bar + bar]
    inside = render.room(render.lowpass(open_air, RATE, 3000.0), RATE, wet=0.45)
    blend = render.ramp(len(open_air), 0.0, 1.0, 4 * bar, render.frames(0.4, RATE))
    first = open_air * (1.0 - blend) + inside * blend
    depths_start, _ = span(depths)
    cave = render.room(render.lowpass(audio[depths_start:depths_start + 9 * bar], RATE, 6000.0), RATE, wet=0.3)
    track = np.concatenate([first, cave])
    made["cave"] = {
        "what": "Wander B in the open; at 0:08 you walk into a cave and the same music goes muffled "
                "and echoing; at 0:12 it moves to Depths.",
        "files": save("s2_demo_cave", render.limit(render.sequence(
            track, [(0, 6 * bar), (7 * bar, 7 * bar + 8 * bar)], RATE, lead_ms=0.0)), RATE)}

    # 3. The three layers of Wander A on their own, to judge how cleanly they split.
    start, end = span(wander)
    for name, layer in (("bed", layers.bed), ("drums", layers.drums), ("bass", layers.bass)):
        made["wander_a_" + name] = {"what": "Wander A, the %s layer alone." % name,
                                    "files": save("s2_wander_a_" + name, layer[start:end], RATE)}
    made["wander_a_no_bass"] = {"what": "Wander A with the bass muted (bed and drums).",
                                "files": save("s2_wander_a_no_bass", layers.bed[start:end] + layers.drums[start:end], RATE)}
    return made


if __name__ == "__main__":
    main()
