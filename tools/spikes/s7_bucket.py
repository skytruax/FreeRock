"""Experiment 7: a bucket of solo phrases that can be played in any combination.

The forever song is put together from single-instrument phrases, all on one tempo and one tonal
centre, so that any drums fit any bass fit any riff fit any tune. This asks for a small bucket in
one zone's tempo and key and measures what that needs to be true: each phrase is the instrument
alone, holds the tempo, starts on the beat, and is in tune with the others.

    cd app && uv run --no-sync python ../tools/spikes/s7_bucket.py           # generate and measure
    cd app && uv run --no-sync python ../tools/spikes/s7_bucket.py --reuse   # measure stored clips
"""
import asyncio
import sys

import numpy as np

from common import OUT, gateway, save, write_report
from freerock import analysis
from freerock.audio import PcmStream, db, read_audio, rms
from freerock.stems import split

FORMAT, RATE, CHANNELS = "pcm_48000", 48000, 2
BPM, TONIC = 80, "D minor"
NOTE = TONIC.split()[0]
BAR_MS = 60000 * 4 // BPM
REUSE = "--reuse" in sys.argv
NEVER = ["vocals", "singing", "choir", "spoken word", "tempo changes", "swing feel", "fade out"]

# name -> (bars, which separated layer it should land in, what is asked, what is ruled out)
PHRASES = {
    "drums_mid": (4, "drums", ["solo rock drum kit", "only drums, nothing else", "plain heavy backbeat",
                               "kick on one and three, snare on two and four", "eighth-note hi-hat", "dry room"],
                  ["bass guitar", "guitar", "melody", "synthesizer"]),
    "drums_high": (4, "drums", ["solo rock drum kit", "only drums, nothing else", "a hard driving beat",
                                "crash cymbal on the first beat of every bar", "floor-tom fills", "dry room"],
                   ["bass guitar", "guitar", "melody", "synthesizer"]),
    "bass_mid": (4, "bass", ["solo electric bass guitar", "only bass guitar, nothing else",
                             "steady eighth notes on the note %s" % NOTE, "dry and close"],
                 ["drums", "guitar", "percussion", "cymbals", "synthesizer"]),
    "rhythm_mid": (4, "bed", ["solo overdriven electric rhythm guitar", "only one guitar, nothing else",
                              "an open-chord riff that keeps coming back to a %s chord" % NOTE,
                              "space between the hits", "dry amplifier sound"],
                   ["drums", "bass guitar", "percussion", "cymbals", "synthesizer"]),
    "lead_calm": (8, "bed", ["solo lute", "only a lute, nothing else", "unaccompanied",
                             "a slow singing melody in %s" % TONIC, "dry and close"],
                  ["drums", "bass guitar", "percussion", "electric guitar", "synthesizer"]),
    "lead_high": (8, "bed", ["solo lead electric guitar", "only one guitar, nothing else", "unaccompanied",
                             "blues-scale licks with wide bends in %s" % TONIC, "gritty overdrive"],
                  ["drums", "bass guitar", "percussion", "cymbals", "synthesizer"]),
    "texture": (8, "bed", ["solo hurdy-gurdy drone on the note %s" % NOTE, "only the drone, nothing else",
                           "slow swells", "no melody", "no rhythm"],
                ["drums", "bass guitar", "percussion", "electric guitar", "synthesizer"]),
}


async def make(gate, name: str, gate_slots: asyncio.Semaphore) -> np.ndarray:
    bars, _, styles, avoid = PHRASES[name]
    path = OUT / ("s7_%s.flac" % name)
    if REUSE and path.is_file():
        return read_audio(path)[0]
    plan = {"chunks": [{"text": "[%s]" % name.replace("_", " "), "duration_ms": bars * BAR_MS,
                        "positive_styles": ["%d BPM" % BPM, TONIC, "steady straight 4/4 beat", "instrumental"] + styles,
                        "negative_styles": NEVER + avoid, "context_adherence": "high"}]}
    async with gate_slots:
        decoder, pieces = PcmStream(CHANNELS), []
        async with gate.stream_music(purpose="experiment 7: %s" % name, plan=plan, seed=7000 + len(name),
                                     output_format=FORMAT) as stream:
            async for chunk in stream:
                pieces.append(decoder.feed(chunk))
        audio = np.concatenate(pieces)
        made = {"first_audio_s": stream.first_audio_s, "total_s": stream.total_s}
    save("s7_%s" % name, audio, RATE)
    print("made %-11s %.1f s of audio, first audio after %.1f s, all of it after %.1f s" % (
        name, len(audio) / RATE, made["first_audio_s"] or 0, made["total_s"] or 0))
    return audio


def measure(name: str, audio: np.ndarray) -> dict:
    bars, layer, _, _ = PHRASES[name]
    found = {"bars": bars, "seconds": round(len(audio) / RATE, 3), "asked_seconds": bars * BAR_MS / 1000.0,
             "loudness_lufs": round(analysis.loudness_lufs(audio, RATE), 1), "peak": round(analysis.peak(audio), 3)}
    if name != "texture":
        grid = analysis.fit_grid(audio, RATE, BPM)
        found["tempo_off_percent"] = round((grid.bpm / BPM - 1) * 100, 3)
        found["start_to_beat_ms"] = round(grid.distance_to_beat_s(0.0) * 1000, 1)
    if layer != "drums":
        key = analysis.estimate_key(audio, RATE)
        found["heard_as"] = key.name
        found["strongest_note"] = analysis.PITCH_NAMES[int(np.argmax(key.chroma))]
        found["rank_of_%s" % NOTE] = key.rank_of(analysis.parse_tonic(NOTE))
        found["tuning_cents"] = round(key.tuning_cents, 1)
    layers = split(audio, RATE)
    levels = {"bed": db(rms(layers.bed)), "drums": db(rms(layers.drums)), "bass": db(rms(layers.bass))}
    others = max(level for other, level in levels.items() if other != layer)
    found["layer_levels_db"] = {k: round(v, 1) for k, v in levels.items()}
    found["others_below_its_own_db"] = round(levels[layer] - others, 1)
    return found


async def main() -> None:
    gate = gateway()
    slots = asyncio.Semaphore(2)
    try:
        clips = dict(zip(PHRASES, await asyncio.gather(*(make(gate, name, slots) for name in PHRASES))))
    finally:
        await gate.aclose()
    report = {"bpm": BPM, "tonic": TONIC, "phrases": {}}
    for name, audio in clips.items():
        report["phrases"][name] = found = measure(name, audio)
        print("%-11s %s" % (name, {k: v for k, v in found.items() if k not in ("layer_levels_db",)}))
    # Everything at once, as the player would: the phrases laid over each other from their
    # starts (the short ones twice), to hear, and to see that the beat of the whole is one beat.
    length = max(len(audio) for audio in clips.values())
    mix = np.zeros((length, 2), dtype=np.float32)
    for name, audio in clips.items():
        if name in ("drums_high", "lead_high"):
            continue
        gain = 10 ** ((-18.0 - report["phrases"][name]["loudness_lufs"]) / 20.0)
        for start in range(0, length, len(audio)):
            piece = audio[:length - start]
            mix[start:start + len(piece)] += piece * gain
    save("s7_all_together", mix, RATE)
    grid = analysis.fit_grid(mix, RATE, BPM)
    report["together"] = {"tempo_off_percent": round((grid.bpm / BPM - 1) * 100, 3),
                          "start_to_beat_ms": round(grid.distance_to_beat_s(0.0) * 1000, 1),
                          "peak": round(analysis.peak(mix), 3)}
    tunings = [found["tuning_cents"] for found in report["phrases"].values() if "tuning_cents" in found]
    beats = [found["start_to_beat_ms"] for found in report["phrases"].values() if "start_to_beat_ms" in found]
    report["passes"] = {
        "every phrase is the length asked for (within 20 ms)": all(
            abs(found["seconds"] - found["asked_seconds"]) <= 0.02 for found in report["phrases"].values()),
        "every phrase holds the tempo within 0.15%": all(
            abs(found.get("tempo_off_percent", 0.0)) <= 0.15 for found in report["phrases"].values()),
        "every phrase is its instrument alone (others at least 15 dB down)": all(
            found["others_below_its_own_db"] >= 15 for found in report["phrases"].values()),
        "the phrases start within 40 ms of one another on the beat": max(beats) - min(beats) <= 40,
        "the pitched phrases are within 25 cents of one another": max(tunings) - min(tunings) <= 25,
    }
    print("together:", report["together"])
    for line, passed in report["passes"].items():
        print("  %s  %s" % ("PASS" if passed else "FAIL", line))
    write_report("s7", report)


if __name__ == "__main__":
    asyncio.run(main())
