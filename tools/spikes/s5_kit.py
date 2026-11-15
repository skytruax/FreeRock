"""Experiments 5 and 6: solo parts from the music endpoint, and clips from the sound-effects one.

Experiment 5 asks for a bass guitar alone and a drum kit alone on the core suite's tempo and key,
to learn whether "solo" is obeyed and whether such parts could be layered over a zone's music
later. Experiment 6 asks the cheaper sound-effects endpoint for the kit FreeRock needs whatever
else happens: a drone to bridge the first seconds in a new zone, a hit for a boss pull, and a
drum loop. Cost: 0.53 minutes of music and 19 seconds of sound effects.

    cd app && uv run --no-sync python ../tools/spikes/s5_kit.py           # generate and measure
    cd app && uv run --no-sync python ../tools/spikes/s5_kit.py --reuse   # measure stored clips
"""
import asyncio
import sys

import numpy as np

from common import OUT, describe, gateway, save, write_report
from freerock import analysis
from freerock.audio import PcmStream, db, decode_bytes, read_audio, resample, rms, to_stereo
from freerock.composer import NEVER
from freerock.eleven import ElevenError
from freerock.stems import split

FORMAT, RATE, CHANNELS = "pcm_48000", 48000, 2
BPM, TONIC = 120, "G mixolydian"
BAR = RATE * 60 * 4 // BPM
REUSE = "--reuse" in sys.argv

SOLOS = {
    "bass": {"styles": ["solo electric bass guitar", "only bass guitar, nothing else",
                        "driving eighth notes on the root", "dry and close"],
             "avoid": NEVER + ["drums", "guitar", "percussion", "cymbals"], "layer": "bass"},
    "drums": {"styles": ["solo rock drum kit", "only drums, nothing else", "plain heavy backbeat",
                         "kick on one and three, snare on two and four", "eighth-note hi-hat", "dry room"],
              "avoid": NEVER + ["bass guitar", "guitar", "melody"], "layer": "drums"},
}
EFFECTS = {
    "drone": {"text": "A sustained hurdy-gurdy drone on the note G, steady and unbroken, no melody, no rhythm",
              "seconds": 8.0, "loop": True},
    "hit": {"text": "One huge distorted electric guitar power chord on G with a crash cymbal and a kick drum, ringing out",
            "seconds": 3.0, "loop": False},
    "drum_loop": {"text": "Rock drum kit loop, plain heavy backbeat, kick on one and three, snare on two and four, "
                          "eighth-note hi-hat, 120 BPM, four bars",
                  "seconds": 8.0, "loop": True},
}


def seam(audio: np.ndarray, rate: int) -> dict:
    """What happens where a loop's end meets its start: the level step across the join, and how
    big the onset there is compared with the ordinary onsets in the clip."""
    doubled = np.concatenate([audio, audio])
    window = int(0.05 * rate)
    before, after = audio[-window:], audio[:window]
    envelope, env_rate = analysis.onset_envelope(doubled, rate)
    join = int(len(audio) / rate * env_rate)
    near = envelope[max(join - 8, 0):join + 8]
    return {"level_step_db": round(db(rms(after) / (rms(before) + 1e-12)), 1),
            "onset_at_join_vs_typical": round(float(near.max() / (np.percentile(envelope, 90) + 1e-9)), 2)}


async def solos(gate) -> dict:
    results = {}
    for name, spec in SOLOS.items():
        path = OUT / ("s5_solo_%s.flac" % name)
        if REUSE and path.is_file():
            audio = read_audio(path)[0]
        else:
            plan = {"chunks": [{"text": "[Solo %s]" % name, "duration_ms": 16000,
                                "positive_styles": ["%d BPM" % BPM, TONIC, "steady straight 4/4 rock beat",
                                                    "instrumental"] + spec["styles"],
                                "negative_styles": spec["avoid"], "context_adherence": "high"}]}
            decoder, pieces = PcmStream(CHANNELS), []
            async with gate.stream_music(purpose="experiment 5: solo %s" % name, plan=plan, seed=5500,
                                         output_format=FORMAT) as stream:
                async for chunk in stream:
                    pieces.append(decoder.feed(chunk))
            audio = np.concatenate(pieces)
            save("s5_solo_%s" % name, audio, RATE)
        # How solo it really is: split it and see how much lands outside the layer it should be.
        layers = split(audio, RATE)
        levels = {"bed": db(rms(layers.bed)), "drums": db(rms(layers.drums)), "bass": db(rms(layers.bass))}
        own = levels[spec["layer"]]
        others = max(level for layer, level in levels.items() if layer != spec["layer"])
        results[name] = {**describe(audio, RATE, bpm=BPM, tonic=TONIC if name == "bass" else None),
                         "layer_levels_db": {k: round(v, 1) for k, v in levels.items()},
                         "loudest_other_layer_below_own_db": round(own - others, 1),
                         "files": {"flac": "s5_solo_%s.flac" % name, "mp3": "s5_solo_%s.mp3" % name}}
        print("solo %-5s: tempo %+.3f%%, other layers %.1f dB below its own" % (
            name, results[name]["tempo"]["off_percent"], own - others))
    return results


async def effects(gate) -> dict:
    results = {}
    for name, spec in EFFECTS.items():
        path = OUT / ("s6_%s.flac" % name)
        entry: dict = {"asked": spec}
        if REUSE and path.is_file():
            audio, rate = read_audio(path)
        else:
            try:
                data, delivery = await gate.sound_effect(
                    purpose="experiment 6: %s" % name, text=spec["text"], duration_seconds=spec["seconds"],
                    loop=spec["loop"], output_format="mp3_44100_192", model_id="eleven_text_to_sound_v3")
            except ElevenError as error:
                print("sound effect %s refused: %s" % (name, error))
                results[name] = {**entry, "refused": str(error)}
                continue
            audio, rate = decode_bytes(data)
            audio = to_stereo(resample(audio, rate, RATE))
            rate = RATE
            entry["delivery"] = {"seconds_to_make": round(delivery.total_s, 2), "headers": delivery.headers}
            save("s6_%s" % name, audio, RATE)
        entry["files"] = {"flac": "s6_%s.flac" % name, "mp3": "s6_%s.mp3" % name}
        entry["seconds"] = round(len(audio) / rate, 3)
        if name == "drone":
            key = analysis.estimate_key(audio, rate)
            entry["strongest_note"] = analysis.PITCH_NAMES[int(np.argmax(key.chroma))]
            entry["tuning_cents"] = round(key.tuning_cents, 1)
            entry["rank_of_G"] = key.rank_of(analysis.parse_tonic("G"))
            entry["seam"] = seam(audio, rate)
        elif name == "drum_loop":
            grid = analysis.fit_grid(audio, rate, BPM)
            entry["tempo"] = {"measured_bpm": round(grid.bpm, 3), "off_percent": round((grid.bpm / BPM - 1) * 100, 3),
                              "jitter_ms": round(grid.jitter_ms, 2)}
            entry["bars_at_120"] = round(len(audio) / BAR, 3)
            entry["seam"] = seam(audio, rate)
        else:
            entry["peak"] = round(analysis.peak(audio), 3)
            entry["loudness_lufs"] = round(analysis.loudness_lufs(audio, rate), 1)
        results[name] = entry
        print("effect %-9s:" % name, {k: v for k, v in entry.items() if k not in ("asked", "files", "delivery")})
    return results


async def main() -> None:
    gate = gateway()
    report: dict = {}
    try:
        report["s5_solos"] = await solos(gate)
        report["s6_effects"] = await effects(gate)
        solo, fx = report["s5_solos"], report["s6_effects"]
        report["passes"] = {
            "5: the solo bass really is solo (other layers at least 20 dB down)": solo["bass"]["loudest_other_layer_below_own_db"] >= 20,
            "5: the solo drums really are solo (other layers at least 20 dB down)": solo["drums"]["loudest_other_layer_below_own_db"] >= 20,
            "5: both hold the tempo within 0.5%": all(abs(solo[n]["tempo"]["off_percent"]) <= 0.5 for n in solo),
            "6: the drone is on G and within 15 cents": "refused" not in fx["drone"] and fx["drone"]["rank_of_G"] == 1 and abs(fx["drone"]["tuning_cents"]) <= 15,
            "6: the drone loops without a bump": "refused" not in fx["drone"] and abs(fx["drone"]["seam"]["level_step_db"]) <= 3,
            "6: the drum loop is four bars at 120 within 1%": "refused" not in fx["drum_loop"] and abs(fx["drum_loop"]["bars_at_120"] - 4) <= 0.04 and abs(fx["drum_loop"]["tempo"]["off_percent"]) <= 1,
        }
        for line, passed in report["passes"].items():
            print("  %s  %s" % ("PASS" if passed else "FAIL", line))
    finally:
        print("report:", write_report("s5", report))
        await gate.aclose()


if __name__ == "__main__":
    asyncio.run(main())
