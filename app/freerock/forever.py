"""The forever song: a bucket of single-instrument phrases, and the filling of it.

The music for a place is not a set of songs. It is a bucket of short phrases, each one instrument
alone: drums, bass, a rhythm part, a tune, a drone. Every phrase in a bucket is on the same tempo
and the same tonal centre, so any drums fit any bass fit any riff fit any tune. The player keeps
one phrase of each going and changes one of them at a time with a crossfade, like a DJ with five
decks, so the music never stops and never comes round again as a whole. What the player is doing
in the game decides which channels are up and how hard their phrases are.

This file is the bucket and the asking. A bucket does not care where its phrases come from: today
they are asked of ElevenLabs a few seconds at a time, and `Bucket.add` takes any audio, so a
library of stems made some other way can fill the same bucket later.

What was measured before this was built (tools/spikes/s7_bucket.py, 2026-11-15): asked for one
instrument alone, ElevenLabs gives one instrument alone (others 35 to 60 dB down); a phrase
arrives in two to three seconds; pitched phrases agree to within about 6 cents; most hold the
tempo exactly and about one in four drifts by a third to nearly one percent, which is measured
here and asked for again.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import analysis, atlas, composer
from .audio import PcmStream
from .eleven import ElevenError, Gateway

log = logging.getLogger("freerock.forever")

FORMAT, RATE, CHANNELS_OUT = "pcm_48000", 48000, 2

# The channels, in the order a new bucket is filled: what makes a place sound like itself first.
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
TIERS = (0, 1, 2)                       # calm, steady, hard
TIER_WORDS = ("calm", "steady", "hard")
# How long a phrase is, in bars. Tunes and drones get room; the parts that keep time are short,
# so they can be changed often.
BARS = {"texture": 8, "lead": 8, "rhythm": 4, "drums": 4, "bass": 4}
# How loud each channel is brought to before the player mixes them (LUFS).
LEVEL = {"texture": -26.0, "lead": -19.0, "rhythm": -20.0, "drums": -17.0, "bass": -18.0}
# How many phrases each pool (a channel at a tier) is filled to: enough to start, then enough to
# keep changing, then the most it holds. Past that the most worn phrase makes room for a new one.
START, MOST = 1, 12
MAX_TEMPO_OFF = 0.2            # percent, by the fit of a beat grid
MAX_REPEAT_OFF = 0.3           # percent, by how the phrase repeats itself two bars later
MAX_BEAT_OFF_MS = 45.0         # further than this from the beat and the phrase is asked for again
MAX_TUNING_CENTS = 20.0
DENSE = 0.6                    # a phrase with something struck on this share of its beats can be timed by them
REPEATS = 0.45                 # a phrase that is this like itself two bars later can be timed by that
TRIES = 3
# The pools a bucket is filled in order of, before anything else: what the music cannot start
# without, then one phrase for every other pool, so that whatever the game does there is an answer.
FIRST = (("texture", 0), ("lead", 0), ("rhythm", 1), ("drums", 1), ("bass", 1), ("rhythm", 0), ("lead", 1),
         ("drums", 0), ("drums", 2), ("bass", 2), ("rhythm", 2), ("lead", 2), ("bass", 0))
# How often each channel takes a new phrase compared with the others: tunes and riffs are what
# the ear follows, so they are replaced soonest.
APPETITE = {"lead": 1.5, "rhythm": 1.3, "drums": 1.0, "bass": 1.0, "texture": 0.7}

# How hard each channel plays, by how much is going on (the director's intensity, 0 to 1): calm
# below the first number, hard from the second, steady between. A fight starts at 0.8, so in a
# fight the drums, the bass and the riff are all hard at once, and the lead joins them when the
# fight has lasted a few seconds or the enemy is a strong one.
GEARS = {"lead": (0.52, 0.86), "rhythm": (0.52, 0.74), "drums": (0.52, 0.74), "bass": (0.50, 0.74)}
GEAR_SLACK = 0.03              # how far past a line the intensity goes before a channel changes gear back
RHYTHM_FROM = 0.30             # the rhythm part plays once the player is on the move
CALM_PLACES = ("ember",)       # an inn, the moment after a fight, a death: everything plays calm

_ONLY = "nothing else"
_TIGHT = "steady timing, tight to the beat"

# What is asked for, by style, channel and tier. Each entry is one way of playing; a pool takes
# them in turn, so that six phrases in a pool are six different ideas. {note} is the tonal centre
# ("D"), {key} the key ("D minor"), {colour} the zone's own tune instrument where it has one.
KNIGHT = {
    "texture": {0: [
        ["solo hurdy-gurdy drone on the note {note}", "only the drone, " + _ONLY, "slow swells", "no melody", "no rhythm"],
        ["a low bowed drone on {note} with the fifth above it", "only the drone, " + _ONLY, "no melody", "no rhythm"],
        ["a soft organ chord of {key} held without moving", "only the organ, " + _ONLY, "no melody", "no rhythm"],
        ["guitar feedback humming on the note {note}, far away", "only the hum, " + _ONLY, "no melody", "no rhythm"],
    ]},
    "lead": {
        0: [["solo lute", "only a lute, " + _ONLY, "unaccompanied", "a slow singing melody in {key}"],
            ["solo {colour}", "only the {colour}, " + _ONLY, "unaccompanied", "a wistful tune in {key}"],
            ["solo clean electric guitar", "only one guitar, " + _ONLY, "unaccompanied", "a gentle melody of long notes in {key}"],
            ["solo hurdy-gurdy", "only the hurdy-gurdy, " + _ONLY, "a slow modal tune in {key}"]],
        1: [["solo lute", "only a lute, " + _ONLY, "unaccompanied", "a lively dance tune in {key}", _TIGHT],
            ["solo {colour}", "only the {colour}, " + _ONLY, "unaccompanied", "a bright skipping tune in {key}", _TIGHT],
            ["solo lead electric guitar, lightly overdriven", "only one guitar, " + _ONLY, "unaccompanied",
             "a singing melody with bends in {key}"],
            ["two lead guitars in harmony", "only the two guitars, " + _ONLY, "a proud tune in {key}"]],
        2: [["solo lead electric guitar", "only one guitar, " + _ONLY, "unaccompanied",
             "blues-scale licks with wide bends in {key}", "gritty overdrive"],
            ["solo lead electric guitar", "only one guitar, " + _ONLY, "unaccompanied",
             "fast screaming runs and held high notes in {key}", "gritty overdrive"],
            ["solo lead electric guitar", "only one guitar, " + _ONLY, "unaccompanied",
             "a defiant anthem melody played hard in {key}", "gritty overdrive"]],
    },
    "rhythm": {
        0: [["solo clean electric guitar", "only one guitar, " + _ONLY, "gentle arpeggios around a {note} chord in steady eighth notes", _TIGHT],
            ["solo clean electric guitar", "only one guitar, " + _ONLY, "softly strummed chords, a new chord every bar, coming back to {note}", _TIGHT],
            ["solo lute", "only a lute, " + _ONLY, "steady plucked chords around {note}, a new chord every bar", _TIGHT]],
        1: [["solo overdriven electric rhythm guitar", "only one guitar, " + _ONLY,
             "steady strummed open chords around {note}, a new chord every bar", _TIGHT],
            ["solo overdriven electric rhythm guitar", "only one guitar, " + _ONLY,
             "a chugging eighth-note riff on a {note} power chord with accents", _TIGHT],
            ["solo overdriven electric rhythm guitar", "only one guitar, " + _ONLY,
             "an open-chord riff in steady eighth notes that keeps coming back to a {note} chord", _TIGHT],
            ["two overdriven rhythm guitars", "only the guitars, " + _ONLY, "a swaggering riff in {key}", _TIGHT]],
        2: [["solo crunchy electric rhythm guitar", "only one guitar, " + _ONLY, "a palm-muted galloping riff on {note}, loud", _TIGHT],
            ["solo crunchy electric rhythm guitar", "only one guitar, " + _ONLY, "big ringing power chords, a hit on every beat, around {note}", _TIGHT],
            ["solo crunchy electric rhythm guitar", "only one guitar, " + _ONLY, "a fast unison riff on the low strings in {key}", _TIGHT]],
    },
    "drums": {
        0: [["solo drum kit", "only drums, " + _ONLY, "soft: rim clicks and a light closed hi-hat"],
            ["solo hand drum and tambourine", "only percussion, " + _ONLY, "a gentle steady pattern"],
            ["solo drum kit", "only drums, " + _ONLY, "half-time feel: kick on one, soft snare on three, brushes"]],
        1: [["solo rock drum kit", "only drums, " + _ONLY, "plain heavy backbeat", "kick on one and three, snare on two and four",
             "eighth-note hi-hat", "dry room"],
            ["solo rock drum kit", "only drums, " + _ONLY, "a loping groove with open hi-hat on the off-beats", "dry room"],
            ["solo rock drum kit", "only drums, " + _ONLY, "a tom-tom groove instead of cymbals, steady", "dry room"],
            ["solo rock drum kit", "only drums, " + _ONLY, "backbeat with a marching snare feel", "dry room"]],
        2: [["solo rock drum kit", "only drums, " + _ONLY, "a hard driving beat", "crash cymbal on the first beat of every bar",
             "floor-tom fills"],
            ["solo rock drum kit", "only drums, " + _ONLY, "double-time feel, snare on every beat, fast fills"],
            ["solo rock drum kit", "only drums, " + _ONLY, "pounding floor toms and kick on every beat, crashes"]],
    },
    "bass": {
        0: [["solo electric bass guitar", "only bass guitar, " + _ONLY, "long warm notes on {note}, one to a bar"],
            ["solo electric bass guitar", "only bass guitar, " + _ONLY, "soft half notes on {note} with a little walk every second bar"]],
        1: [["solo electric bass guitar", "only bass guitar, " + _ONLY, "steady eighth notes on the note {note}", "dry and close"],
            ["solo electric bass guitar", "only bass guitar, " + _ONLY, "a driving rock riff on {note} with a fill every fourth bar"],
            ["solo electric bass guitar", "only bass guitar, " + _ONLY, "eighth notes on {note} with octave jumps on the backbeat"]],
        2: [["solo electric bass guitar", "only bass guitar, " + _ONLY, "fast driving notes on {note} with octave jumps, aggressive"],
            ["solo electric bass guitar", "only bass guitar, " + _ONLY, "a galloping line on {note}, loud and busy"],
            ["solo electric bass guitar", "only bass guitar, " + _ONLY, "a heavy riff on the low strings around {note}"]],
    },
}

WARCRAFT = {
    "texture": {0: [
        ["a soft sustained string chord of {key}, slowly swelling", "only strings, " + _ONLY, "no melody", "no rhythm"],
        ["low strings holding the note {note}, very quiet", "only low strings, " + _ONLY, "no melody", "no rhythm"],
        ["a high shimmering violin tremolo over a held {note}", "only strings, " + _ONLY, "no melody", "no rhythm"],
        ["muted horns holding a soft chord of {key}", "only horns, " + _ONLY, "no melody", "no rhythm"],
    ]},
    "lead": {
        0: [["solo oboe", "only an oboe, " + _ONLY, "unaccompanied", "a pastoral tune in {key}"],
            ["solo flute", "only a flute, " + _ONLY, "unaccompanied", "a gentle wandering melody in {key}"],
            ["solo french horn", "only a horn, " + _ONLY, "unaccompanied", "a noble slow melody in {key}"],
            ["solo cello", "only a cello, " + _ONLY, "unaccompanied", "a singing melody in {key}"]],
        1: [["solo clarinet", "only a clarinet, " + _ONLY, "unaccompanied", "a lilting dance tune in {key}", _TIGHT],
            ["violins in unison", "only violins, " + _ONLY, "a broad warm tune in {key}"],
            ["solo trumpet", "only a trumpet, " + _ONLY, "unaccompanied", "a bright calling melody in {key}"],
            ["solo {colour}", "only the {colour}, " + _ONLY, "unaccompanied", "a folk-like tune in {key}", _TIGHT]],
        2: [["french horns in unison", "only horns, " + _ONLY, "a fierce heroic theme in {key}, loud"],
            ["trumpets in unison", "only trumpets, " + _ONLY, "a battle fanfare in {key}, loud"],
            ["violins in octaves", "only violins, " + _ONLY, "racing runs and a soaring tune in {key}, urgent"]],
    },
    "rhythm": {
        0: [["solo harp", "only a harp, " + _ONLY, "gentle arpeggios around {key} in steady eighth notes", _TIGHT],
            ["pizzicato strings", "only plucked strings, " + _ONLY, "a soft steady figure around {note}", _TIGHT],
            ["solo celesta", "only a celesta, " + _ONLY, "a light repeating figure in {key}", _TIGHT]],
        1: [["violas and second violins", "only strings, " + _ONLY, "a pulsing ostinato in steady eighth notes around {note}", _TIGHT],
            ["pizzicato strings and harp", "only plucked strings and harp, " + _ONLY, "a walking figure around {note}", _TIGHT],
            ["woodwinds", "only woodwinds, " + _ONLY, "a bubbling staccato figure in {key}", _TIGHT]],
        2: [["full strings", "only strings, " + _ONLY, "fast staccato figures in sixteenth notes around {note}, urgent", _TIGHT],
            ["brass", "only brass, " + _ONLY, "hammering chords on every beat around {note}, loud", _TIGHT],
            ["strings and xylophone", "only strings and xylophone, " + _ONLY, "a racing chase figure in {key}", _TIGHT]],
    },
    "drums": {
        0: [["orchestral percussion", "only percussion, " + _ONLY, "a soft timpani stroke on the first beat of every bar"],
            ["orchestral percussion", "only percussion, " + _ONLY, "a light tambourine and a soft hand drum, steady"],
            ["orchestral percussion", "only percussion, " + _ONLY, "a distant bass drum every second bar and a soft triangle"]],
        1: [["orchestral percussion", "only percussion, " + _ONLY, "a steady march for snare drum and timpani"],
            ["orchestral percussion", "only percussion, " + _ONLY, "timpani on one and three, tambourine on two and four"],
            ["orchestral percussion", "only percussion, " + _ONLY, "a rolling frame-drum pattern with soft cymbal swells"]],
        2: [["orchestral percussion", "only percussion, " + _ONLY, "pounding war drums and timpani on every beat, crashing cymbals"],
            ["orchestral percussion", "only percussion, " + _ONLY, "a fast snare-drum march with bass drum and cymbal crashes"],
            ["orchestral percussion", "only percussion, " + _ONLY, "thundering timpani rolls and huge drum hits"]],
    },
    "bass": {
        0: [["cellos and double basses", "only low strings, " + _ONLY, "holding the note {note} in long bows"],
            ["double basses", "only double basses, " + _ONLY, "soft plucked notes on {note}, two to a bar"]],
        1: [["cellos and double basses", "only low strings, " + _ONLY, "a walking pizzicato line around {note}", _TIGHT],
            ["cellos and double basses", "only low strings, " + _ONLY, "a steady bowed ostinato in eighth notes on {note}", _TIGHT],
            ["bassoons and double basses", "only bassoons and basses, " + _ONLY, "a steady stepping line around {note}", _TIGHT]],
        2: [["cellos, double basses and low brass", "only low strings and low brass, " + _ONLY,
             "a driving ostinato in fast notes on {note}, loud", _TIGHT],
            ["trombones and tuba", "only low brass, " + _ONLY, "a grim heavy march on {note}", _TIGHT],
            ["cellos and double basses", "only low strings, " + _ONLY, "furious repeated notes on {note} with accents", _TIGHT]],
    },
}

TRANCE = {
    "texture": {0: [
        ["a warm lush synth pad holding a chord of {key}, slowly evolving", "only the pad, " + _ONLY, "no melody", "no drums"],
        ["an airy pad with slow white-noise sweeps on {note}", "only the pad, " + _ONLY, "no melody", "no drums"],
        ["a deep sub drone on the note {note} with a slow filter", "only the drone, " + _ONLY, "no melody", "no drums"],
        ["a glassy shimmering pad in {key}", "only the pad, " + _ONLY, "no melody", "no drums"],
    ]},
    "lead": {
        0: [["a bell-like synth melody with long echoes in {key}", "only the one synth, " + _ONLY, "no drums", "slow and spacious"],
            ["a soft piano-like melody in {key}", "only the one instrument, " + _ONLY, "no drums", "slow and spacious"],
            ["a single plucked synth playing a slow tune in {key}", "only the one synth, " + _ONLY, "no drums"]],
        1: [["a gliding synth lead melody in {key}", "only the one synth, " + _ONLY, "no drums", _TIGHT],
            ["a plucked synth hook in {key}, bouncing", "only the one synth, " + _ONLY, "no drums", _TIGHT],
            ["a square-wave lead playing a simple catchy hook in {key}", "only the one synth, " + _ONLY, "no drums", _TIGHT]],
        2: [["a supersaw anthem lead in {key}, euphoric and loud", "only the one synth, " + _ONLY, "no drums", _TIGHT],
            ["a screaming distorted synth lead in {key}", "only the one synth, " + _ONLY, "no drums", _TIGHT],
            ["a supersaw lead in octaves playing a rising hook in {key}", "only the one synth, " + _ONLY, "no drums", _TIGHT]],
    },
    "rhythm": {
        0: [["a soft plucked synth arpeggio in {key}, slowly filtered, steady sixteenth notes", "only the arpeggio, " + _ONLY, "no drums", _TIGHT],
            ["a muted synth arpeggio around {note} with a long echo, steady eighth notes", "only the arpeggio, " + _ONLY, "no drums", _TIGHT],
            ["a gentle marimba-like synth pattern in {key}", "only the one synth, " + _ONLY, "no drums", _TIGHT]],
        1: [["gated trance chords pulsing in eighth notes in {key}", "only the chords, " + _ONLY, "no drums", _TIGHT],
            ["a bright plucked arpeggio climbing and falling in {key}, sixteenth notes", "only the arpeggio, " + _ONLY, "no drums", _TIGHT],
            ["an acid synth line weaving around {note}, squelchy, sixteenth notes", "only the one synth, " + _ONLY, "no drums", _TIGHT]],
        2: [["supersaw chord stabs in {key}, bright and loud, on the off-beats", "only the chords, " + _ONLY, "no drums", _TIGHT],
            ["a racing arpeggio at full brightness in {key}, sixteenth notes", "only the arpeggio, " + _ONLY, "no drums", _TIGHT],
            ["a hard distorted synth riff on {note}, stabbing", "only the one synth, " + _ONLY, "no drums", _TIGHT]],
    },
    "drums": {
        0: [["electronic drums", "only drums, " + _ONLY, "a soft shaker and a rim click, no kick drum"],
            ["electronic drums", "only drums, " + _ONLY, "a soft four-on-the-floor kick and a closed hi-hat, quiet"],
            ["electronic drums", "only drums, " + _ONLY, "closed hi-hats in sixteenth notes and a soft clap on two and four, no kick drum"]],
        1: [["electronic trance drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "off-beat open hi-hats", "clap on two and four"],
            ["electronic trance drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "rolling closed hi-hats", "snare on two and four"],
            ["electronic trance drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "shuffling percussion loops in straight time", "clap on two and four"]],
        2: [["electronic trance drums", "only drums, " + _ONLY, "pounding four-on-the-floor kick drum", "open hi-hats on every off-beat",
             "a snare roll into the last bar", "crash on the first beat"],
            ["electronic trance drums", "only drums, " + _ONLY, "hard kick drum on every beat", "fast rolling hi-hats", "claps and crashes"],
            ["electronic trance drums", "only drums, " + _ONLY, "driving kick drum and a relentless ride cymbal", "snare on two and four"]],
    },
    "bass": {
        0: [["a deep sub bass", "only the bass, " + _ONLY, "no drums", "one long note on {note} to every bar"],
            ["a soft round synth bass", "only the bass, " + _ONLY, "no drums", "slow notes on {note}, two to a bar"]],
        1: [["a rolling trance bassline", "only the bass, " + _ONLY, "no drums", "sixteenth notes on the note {note}, between the beats", _TIGHT],
            ["an off-beat trance bass", "only the bass, " + _ONLY, "no drums", "one note on {note} on every off-beat", _TIGHT],
            ["a plucked synth bass", "only the bass, " + _ONLY, "no drums", "a bouncing eighth-note line around {note}", _TIGHT]],
        2: [["a driving acid bassline", "only the bass, " + _ONLY, "no drums", "squelchy and busy sixteenth notes on {note}", _TIGHT],
            ["a hard distorted bass", "only the bass, " + _ONLY, "no drums", "pounding eighth notes on {note}", _TIGHT],
            ["a galloping trance bass", "only the bass, " + _ONLY, "no drums", "a galloping pattern on {note}, loud", _TIGHT]],
    },
}

RECIPES = {"knight": KNIGHT, "warcraft": WARCRAFT, "trance": TRANCE}
# What must never be in a phrase of each channel, on top of what the style never wants.
OTHERS = {
    "texture": ["drums", "percussion", "bass guitar", "melody"],
    "lead": ["drums", "percussion", "bass guitar", "cymbals"],
    "rhythm": ["drums", "percussion", "bass guitar", "cymbals"],
    "drums": ["bass guitar", "guitar", "melody", "keyboard", "strings"],
    "bass": ["drums", "percussion", "guitar", "cymbals", "melody"],
}
# Instruments in a zone's colours that can carry a tune alone.
_TUNE_INSTRUMENTS = ("fiddle", "tin whistle", "wooden flute", "low flute", "mandolin", "organ", "drone pipes",
                     "harp", "flute", "whistle")


def tune_instrument(profile: composer.ZoneProfile, genre: str) -> str:
    """The zone's own instrument for a tune, where it has one; a lute or an oboe otherwise."""
    for colour in profile.colours:
        for name in _TUNE_INSTRUMENTS:
            if name in colour:
                return name
    return {"knight": "lute", "warcraft": "oboe", "trance": "synth"}[genre]


def tiers_of(channel: str) -> tuple[int, ...]:
    return (0,) if channel == "texture" else TIERS


def bars_of(channel: str, bpm: int) -> int:
    """A phrase's length in bars; twice as many at the fastest tempos, where a bar is very short."""
    return BARS[channel] * (2 if bpm >= 150 else 1)


@dataclass
class Ask:
    """One phrase to ask for."""
    channel: str
    tier: int
    variant: int
    bars: int
    plan: dict[str, Any]
    seed: int
    words: list[str]

    @property
    def minutes(self) -> float:
        return self.plan["chunks"][0]["duration_ms"] / 60000.0


def ask(profile: composer.ZoneProfile, genre: str, channel: str, tier: int, variant: int, seed: int,
        context: list[str] | None = None) -> Ask:
    """The request for one phrase. `profile` is the zone's as the style uses it (composer.for_genre)."""
    recipe = composer.genre_of(genre)
    ways = RECIPES[genre][channel][tier]
    note = profile.tonic.split()[0]
    fill = {"note": note, "key": profile.tonic, "colour": tune_instrument(profile, genre)}
    words = [phrase.format(**fill) for phrase in ways[variant % len(ways)]]
    # The mood of the place and of the moment colours the tune and the drone; the parts that
    # keep time are asked for plainly, which is what keeps them steady.
    if channel in ("lead", "texture"):
        words += list(profile.mood[:2]) + list(context or [])
    bars = bars_of(channel, profile.bpm)
    # The words for the time are the ones the experiment held its tempo with. A style's own words
    # for its beat name the instruments that keep it, which a phrase for one instrument must not.
    timing = [] if channel == "texture" else ["steady straight 4/4 beat"]
    plan = {"chunks": [{
        "text": "[%s]" % channel, "duration_ms": composer.bars_ms(profile.bpm, bars),
        "positive_styles": list(dict.fromkeys(["%d BPM" % profile.bpm, profile.tonic] + timing + ["instrumental"] + words)),
        "negative_styles": list(dict.fromkeys(recipe["never"] + OTHERS[channel])),
        "context_adherence": "high"}]}
    return Ask(channel=channel, tier=tier, variant=variant, bars=bars, plan=plan, seed=seed, words=words)


def mix(target: Any, before: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Which channels are up, and how hard each plays, for what the director asks for: the mixing
    desk for the five decks. `target` is the director's Target; `before` is the last mix, so that
    an intensity hovering on a line does not make a channel change gear back and forth.

    The drums and the bass take their levels straight from the director: the drums come in when
    the player moves and the bass with a fight or a long ride. The drone is always there, the
    tune nearly always, and the rhythm part whenever the player is on the move."""
    intensity = target.intensity
    calm = target.place in CALM_PLACES
    out: dict[str, dict[str, Any]] = {}
    for channel in CHANNELS:
        tier = 0
        if channel != "texture" and not calm:
            low, high = GEARS[channel]
            tier = 0 if intensity < low else 1 if intensity < high else 2
            was = before[channel]["tier"] if before else None
            if was is not None and abs(tier - was) == 1:
                edge = low if min(tier, was) == 0 else high
                if abs(intensity - edge) < GEAR_SLACK:
                    tier = was
        if channel == "drums":
            level = target.drums
        elif channel == "bass":
            level = target.bass
        elif channel == "texture":
            level = target.bed * (0.6 if intensity >= 0.8 else 1.0)      # room for the band at full tilt
        elif channel == "rhythm":
            moving = intensity >= RHYTHM_FROM - (GEAR_SLACK if before and before["rhythm"]["level"] > 0 else 0.0)
            level = target.bed if moving else 0.0
        else:
            level = target.bed
        out[channel] = {"level": round(float(level), 3), "tier": tier}
    return out


def in_use(mixed: dict[str, dict[str, Any]] | None) -> list[tuple[str, int]]:
    """The pools a mix is drawing on: every channel that is up, at the strength it is playing."""
    if not mixed:
        return []
    return [(channel, mixed[channel]["tier"]) for channel in CHANNELS if mixed[channel]["level"] > 0]


# ---------------------------------------------------------------------------------------------
# Measuring a phrase
# ---------------------------------------------------------------------------------------------
def _repeat_off(audio: np.ndarray, rate: int, bar_s: float) -> tuple[float, float]:
    """How far the phrase is from repeating itself exactly two bars later, in percent of tempo,
    and how strongly it repeats (0 to 1). A phrase that keeps the tempo comes round on the bar."""
    envelope, env_rate = analysis.onset_envelope(audio, rate)
    envelope = envelope - envelope.mean()
    centre = int(round(2 * bar_s * env_rate))
    if centre * 1.5 > len(envelope):
        centre = int(round(bar_s * env_rate))
    reach = max(int(centre * 0.03), 4)
    best = (-2.0, centre)
    for lag in range(centre - reach, centre + reach + 1):
        a, b = envelope[:-lag], envelope[lag:]
        score = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
        if score > best[0]:
            best = (score, lag)
    return (centre / best[1] - 1.0) * 100.0, best[0]


def measure(audio: np.ndarray, rate: int, bpm: int, channel: str, bars: int) -> dict[str, Any]:
    """What a phrase is: its length, level, tempo, where its beat falls and how it is tuned,
    and in `problems` everything that makes it unfit for the bucket (empty when it is fit)."""
    bar_s = 240.0 / bpm
    asked = bars * bar_s
    found: dict[str, Any] = {"seconds": round(len(audio) / rate, 3), "lufs": round(analysis.loudness_lufs(audio, rate), 1),
                             "peak": round(analysis.peak(audio), 3)}
    problems: list[str] = []
    if abs(found["seconds"] - asked) > 0.05:
        problems.append("it is %.2f s long, not %.2f" % (found["seconds"], asked))
    if found["lufs"] < -50.0:
        problems.append("it is all but silent (%.0f LUFS)" % found["lufs"])
    if channel != "texture":
        grid = analysis.fit_grid(audio, rate, bpm)
        off = (grid.bpm / bpm - 1.0) * 100.0
        repeat, strength = _repeat_off(audio, rate, bar_s)
        half_beat = 30000.0 / bpm
        beat = grid.distance_to_beat_s(0.0) * 1000.0
        beat = (beat + half_beat / 2.0) % half_beat - half_beat / 2.0      # the beat or the off-beat: see ingest
        # A phrase of long notes has too little struck on its beats for a beat to be fitted to
        # it, and what the fit then says means nothing. Such a phrase is judged only by whether
        # it comes round on the bar, and if it does not repeat either, it is taken as it is: a
        # few long notes cannot be heard to be out of time.
        dense = grid.beats_checked >= DENSE * bars * 4
        found.update(tempo_off=round(off, 3), repeat_off=round(repeat, 3), repeat=round(strength, 2),
                     beat_ms=round(beat, 1), struck=grid.beats_checked, dense=dense)
        if dense and abs(off) > MAX_TEMPO_OFF:
            problems.append("it is %.2f%% off tempo" % off)
        elif strength >= REPEATS and abs(repeat) > MAX_REPEAT_OFF:
            problems.append("it comes round %.2f%% off the bar" % repeat)
        if dense and abs(beat) > MAX_BEAT_OFF_MS:
            problems.append("it starts %.0f ms from the beat" % beat)
    if channel != "drums":
        key = analysis.estimate_key(audio, rate)
        found.update(tuning_cents=round(key.tuning_cents, 1), strongest_note=analysis.PITCH_NAMES[int(np.argmax(key.chroma))])
        if abs(key.tuning_cents) > MAX_TUNING_CENTS:
            problems.append("it is %.0f cents out of tune" % key.tuning_cents)
    found["problems"] = problems
    return found


def fit(audio: np.ndarray, rate: int, bpm: int, bars: int) -> np.ndarray:
    """A phrase made exactly `bars` long, to the sample. ElevenLabs gives the length asked for to
    within a few samples; the audio itself is left as it came (a phrase that does not start on
    the beat is asked for again, not moved)."""
    frames = bars * rate * 240 // bpm
    if len(audio) > frames:
        return audio[:frames]
    if len(audio) < frames:
        return np.concatenate([audio, np.zeros((frames - len(audio), audio.shape[1]), dtype=audio.dtype)])
    return audio


# ---------------------------------------------------------------------------------------------
# The bucket
# ---------------------------------------------------------------------------------------------
@dataclass
class Clip:
    id: str
    channel: str
    tier: int
    variant: int
    bars: int
    frames: int
    gain_db: float                 # brings it to its channel's level
    created: float
    words: list[str] = field(default_factory=list)
    measured: dict[str, Any] = field(default_factory=dict)
    plays: int = 0
    retired: bool = False          # worn: set aside for a newer phrase, and brought back if no new ones can be made
    banned: bool = False           # never played again (/rock ban)
    loved: bool = False            # never set aside (/rock love)
    source: str = "elevenlabs"     # where it came from: today always ElevenLabs


class Bucket:
    """The phrases for one place in one style, on disk."""

    def __init__(self, root: Path, zone: str, genre: str, bpm: int, tonic: str):
        self.root, self.zone, self.genre, self.bpm, self.tonic = Path(root), zone, genre, bpm, tonic
        self.folder = self.root / genre / zone
        self.clips: list[Clip] = []
        self.version = 0
        self.everything = False        # play the worn phrases too: set when no new ones can be made
        index = self.folder / "bucket.json"
        if index.is_file():
            kept = json.loads(index.read_text(encoding="utf-8"))
            self.bpm, self.tonic = kept["bpm"], kept["tonic"]      # what its phrases were made at
            self.clips = [Clip(**clip) for clip in kept["clips"]]
            self.version = kept.get("version", len(self.clips))

    @property
    def key(self) -> str:
        return "%s/%s" % (self.genre, self.zone)

    @property
    def bar_frames(self) -> int:
        return RATE * 240 // self.bpm

    def _in_play(self, clip: Clip) -> bool:
        return not clip.banned and (self.everything or not clip.retired)

    def pool(self, channel: str, tier: int) -> list[Clip]:
        return [clip for clip in self.clips if clip.channel == channel and clip.tier == tier and self._in_play(clip)]

    def live(self) -> list[Clip]:
        return [clip for clip in self.clips if self._in_play(clip)]

    def ready(self) -> bool:
        """Enough to start playing: a drone, a tune, a rhythm part, drums and bass."""
        return (bool(self.pool("texture", 0)) and any(self.pool("lead", tier) for tier in (0, 1))
                and any(self.pool("rhythm", tier) for tier in (0, 1))
                and bool(self.pool("drums", 1)) and bool(self.pool("bass", 1)))

    def _save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.version += 1
        index = {"zone": self.zone, "genre": self.genre, "bpm": self.bpm, "tonic": self.tonic,
                 "version": self.version, "clips": [asdict(clip) for clip in self.clips]}
        scratch = self.folder / "bucket.json.new"
        scratch.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
        scratch.replace(self.folder / "bucket.json")

    def add(self, audio: np.ndarray, *, channel: str, tier: int, variant: int = 0, words: list[str] | None = None,
            measured: dict[str, Any] | None = None, source: str = "elevenlabs") -> Clip:
        """Puts a phrase in the bucket. `audio` is stereo at 48 kHz and exactly a whole number of
        bars long, beat on the start (see `fit`). This is the way in for any phrase, wherever it
        was made."""
        bars, extra = divmod(len(audio), self.bar_frames)
        if extra or not bars:
            raise ValueError("A phrase is a whole number of bars: %d frames is not, at %d a bar" % (len(audio), self.bar_frames))
        measured = dict(measured or {})
        lufs = measured.get("lufs")
        if lufs is None:
            lufs = measured["lufs"] = round(analysis.loudness_lufs(audio, RATE), 1)
        # Never more than full scale after the gain, whatever the level says.
        gain = min(LEVEL[channel] - lufs, -20.0 * float(np.log10(max(analysis.peak(audio), 1e-6))) - 1.0)
        clip = Clip(id=uuid.uuid4().hex[:10], channel=channel, tier=tier, variant=variant, bars=bars, frames=len(audio),
                    gain_db=round(gain, 2), created=time.time(), words=list(words or []), measured=measured, source=source)
        (self.folder / "clips").mkdir(parents=True, exist_ok=True)
        np.save(self.folder / "clips" / (clip.id + ".npy"),
                np.round(np.clip(audio, -1.0, 32767 / 32768) * 32768).astype("<i2"))
        self.clips.append(clip)
        self._save()
        return clip

    def mark(self, clip_ids: list[str], *, retired: bool | None = None, banned: bool | None = None,
             loved: bool | None = None) -> list[Clip]:
        """Sets a phrase aside, bans it or marks it as loved. Returns the phrases it found."""
        wanted, found = set(clip_ids), []
        for clip in self.clips:
            if clip.id in wanted:
                found.append(clip)
                for name, value in (("retired", retired), ("banned", banned), ("loved", loved)):
                    if value is not None:
                        setattr(clip, name, value)
        if found:
            self._save()
        return found

    def played(self, clip_ids: list[str]) -> None:
        """Counts one more play for each of these phrases. A phrase the bucket does not have (the
        page is still playing another place's) is passed over."""
        wanted, found = set(clip_ids), False
        for clip in self.clips:
            if clip.id in wanted:
                clip.plays += 1
                found = True
        if found:
            self._save()

    def samples(self, clip_id: str) -> bytes:
        """A whole phrase as 16-bit little-endian stereo."""
        if not any(clip.id == clip_id for clip in self.clips):
            raise KeyError("No phrase %r in the bucket for %s" % (clip_id, self.key))
        return np.load(self.folder / "clips" / (clip_id + ".npy")).tobytes()

    def describe(self) -> dict[str, Any]:
        """What the player needs to know to play from this bucket."""
        return {"key": self.key, "zone": self.zone, "genre": self.genre, "bpm": self.bpm, "tonic": self.tonic,
                "rate": RATE, "bar_frames": self.bar_frames, "version": self.version,
                "clips": [self.brief(clip) for clip in self.live()]}

    @staticmethod
    def brief(clip: Clip) -> dict[str, Any]:
        """One phrase as the player is told of it."""
        return {"id": clip.id, "channel": clip.channel, "tier": clip.tier, "bars": clip.bars,
                "frames": clip.frames, "gain_db": clip.gain_db, "new": clip.plays == 0}

    def counts(self) -> dict[str, int]:
        """How many phrases each pool has in play, for the control page: "drums hard": 4."""
        return {"%s %s" % (channel, TIER_WORDS[tier]): len(self.pool(channel, tier)) for channel, tier in FIRST}

    # --- what to ask for next ----------------------------------------------------------------
    def started(self, also: dict[tuple[str, int], int] | None = None) -> bool:
        """Whether every pool has its first phrase, counting `also` (phrases on their way)."""
        also = also or {}
        return all(len(self.pool(channel, tier)) + also.get((channel, tier), 0) >= START for channel, tier in FIRST)

    def wanted(self, active: list[tuple[str, int]] | None = None,
               also: dict[tuple[str, int], int] | None = None,
               skip: set[tuple[str, int]] | None = None) -> tuple[str, int]:
        """The pool to add a phrase to next. `active` is the pools the music is drawing on right
        now (which channels are up, and how hard); `also` counts phrases already on their way;
        `skip` is pools to leave alone for now.

        First whatever the music is drawing on that has nothing at all, then one phrase for every
        pool. After that the bucket follows the game: of the pools in use, the one with the fewest
        phrases nobody has heard yet, so that the next change the player makes is to something new."""
        also, skip = also or {}, skip or set()
        active = [pool for pool in (active or []) if pool not in skip]

        def have(pool: tuple[str, int]) -> int:
            return len(self.pool(*pool)) + also.get(pool, 0)

        for pool in active:
            if have(pool) < START:
                return pool
        for pool in FIRST:
            if pool not in skip and have(pool) < START:
                return pool
        choices = active or [pool for pool in FIRST if pool not in skip] or list(FIRST)

        def hunger(pool: tuple[str, int]) -> tuple[float, int]:
            unheard = sum(1 for clip in self.pool(*pool) if clip.plays == 0) + also.get(pool, 0)
            return unheard / APPETITE[pool[0]], have(pool)

        return min(choices, key=hunger)

    def make_room(self, channel: str, tier: int) -> list[Clip]:
        """Sets aside the most worn phrases of a pool that holds more than it should. They stay
        on disk, and come back into play if a day comes when no new ones can be made."""
        gone = []
        while True:
            pool = self.pool(channel, tier)
            spare = [clip for clip in pool if not clip.loved]
            if len(pool) <= MOST or not spare or self.everything:
                break
            worn = max(spare, key=lambda clip: (clip.plays, -clip.created))
            worn.retired = True
            gone.append(worn)
        if gone:
            self._save()
        return gone


class Buckets:
    """Every bucket, by place and style."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._have: dict[str, Bucket] = {}

    def get(self, place_name: str | None, genre: str) -> Bucket:
        profile = composer.for_genre(atlas.profile_for(place_name), genre)
        key = "%s/%s" % (genre, profile.key)
        if key not in self._have:
            self._have[key] = Bucket(self.root, profile.key, genre, profile.bpm, profile.tonic)
        return self._have[key]

    def by_key(self, key: str) -> Bucket:
        if key not in self._have:
            genre, _, zone = key.partition("/")
            index = self.root / genre / zone / "bucket.json"
            if not index.is_file():
                raise KeyError("No bucket %r" % key)
            kept = json.loads(index.read_text(encoding="utf-8"))
            self._have[key] = Bucket(self.root, zone, genre, kept["bpm"], kept["tonic"])
        return self._have[key]


# ---------------------------------------------------------------------------------------------
# Filling it
# ---------------------------------------------------------------------------------------------
class PhraseFailed(RuntimeError):
    """A phrase came back unfit every time it was asked for; `problems` says how the last was."""

    def __init__(self, channel: str, tier: int, problems: list[str]):
        self.channel, self.tier, self.problems = channel, tier, problems
        super().__init__("No fit phrase for %s (%s) in %d tries: %s." % (channel, TIER_WORDS[tier], TRIES, "; ".join(problems)))


class Filler:
    """Asks ElevenLabs for phrases and puts the fit ones in a bucket."""

    def __init__(self, gateway: Gateway, rng: random.Random | None = None):
        self.gateway = gateway
        self.rng = rng or random.Random()
        self.turned_away = 0           # phrases that failed their checks and were asked for again

    async def _generate(self, request: Ask, zone: str) -> np.ndarray:
        decoder, pieces = PcmStream(CHANNELS_OUT), []
        async with self.gateway.stream_music(
                purpose="phrase: %s %s" % (request.channel, TIER_WORDS[request.tier]), zone=zone, plan=request.plan,
                seed=request.seed, output_format=FORMAT) as stream:
            async for chunk in stream:
                pieces.append(decoder.feed(chunk))
        if decoder.leftover_bytes:
            raise RuntimeError("The audio from ElevenLabs ended in the middle of a sample")
        return np.concatenate(pieces)

    async def phrase(self, bucket: Bucket, profile: composer.ZoneProfile, channel: str, tier: int,
                     context: list[str] | None = None) -> Clip:
        """One new phrase for a pool. `profile` is the place the player is in (atlas.profile_for,
        or atlas.place_profile for a named corner of a zone): its instruments and its mood colour
        the phrase, while the tempo and the key are the bucket's. A phrase that drifts from the
        tempo, starts off the beat or is out of tune is asked for again, in other words, up to
        TRIES times."""
        styled = composer.for_genre(profile, bucket.genre)
        profile = composer.ZoneProfile(key=bucket.zone, bpm=bucket.bpm, tonic=bucket.tonic,
                                       colours=styled.colours, mood=styled.mood)
        variant = len([clip for clip in bucket.clips if clip.channel == channel and clip.tier == tier])
        problems: list[str] = []
        for attempt in range(TRIES):
            request = ask(profile, bucket.genre, channel, tier, variant + attempt, self.rng.randrange(2 ** 31), context)
            audio = await self._generate(request, bucket.zone)
            # Measuring takes about a second of arithmetic; it is done off to one side so that
            # the game goes on being followed meanwhile.
            found = await asyncio.to_thread(measure, audio, RATE, bucket.bpm, channel, request.bars)
            problems = found.pop("problems")
            if not problems:
                return bucket.add(fit(audio, RATE, bucket.bpm, request.bars), channel=channel, tier=tier,
                                  variant=request.variant, words=request.words, measured=found)
            self.turned_away += 1
            log.info("a phrase for %s (%s %s) was turned away: %s", bucket.key, channel, TIER_WORDS[tier], "; ".join(problems))
        raise PhraseFailed(channel, tier, problems)


__all__ = ["Ask", "Bucket", "Buckets", "Clip", "Filler", "PhraseFailed", "ask", "measure", "fit", "CHANNELS", "TIERS",
           "FIRST", "MOST", "ElevenError", "mix", "in_use"]
