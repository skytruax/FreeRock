"""The forever song: a bucket of single-instrument phrases, and the filling of it.

The music for a place is not a set of songs. It is a bucket of phrases, each one instrument alone:
drums, bass, a rhythm part, a tune, a drone. Every phrase in a bucket is on the same tempo and
the same tonal centre, so any drums fit any bass fit any riff fit any tune. The player keeps one
phrase of each going and changes them a few at a time, like a DJ with five decks, so the music
never stops and never comes round again as a whole. What the player is doing in the game decides
which channels are up and how hard their phrases are.

A phrase is one turn of the song's form: a verse, a build-up and a chorus, about three quarters
of a minute in all. The three are the same lengths for every channel, so whichever five phrases
are playing, the whole band builds up together and reaches the chorus together.

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
import soundfile

from . import analysis, atlas, composer
from .audio import PcmStream
from .eleven import ElevenError, Gateway

log = logging.getLogger("freerock.forever")

FORMAT, RATE, CHANNELS_OUT = "pcm_48000", 48000, 2

# The channels, in the order a new bucket is filled: what makes a place sound like itself first.
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
TIERS = (0, 1, 2)                       # calm, steady, hard
TIER_WORDS = ("calm", "steady", "hard")
SECTIONS = ("verse", "build", "chorus")
# How loud each channel is brought to before the player mixes them (LUFS).
LEVEL = {"texture": -26.0, "lead": -19.0, "rhythm": -20.0, "drums": -17.0, "bass": -18.0}
# How many phrases each pool (a channel at a tier) is filled to: enough to start, then enough to
# keep changing, then the most it holds. Past that the most worn phrase makes room for a new one.
# How deep the pools are filled. Every pool gets its first phrase at once (START), then every
# pool is brought to DEPTH, both as fast as phrases can be made. After that a pool the music is
# drawing on is kept AHEAD phrases in front of what has been heard, so that the next change is
# always to something new, and whatever is left over goes on deepening the pools up to MOST.
# A pool goes on growing past MOST as its phrases are heard, up to KEEP; past that the most worn
# phrase makes room for each new one.
START, DEPTH, AHEAD, MOST, KEEP = 1, 3, 2, 8, 60
MAX_TEMPO_OFF = 0.2            # percent, by the fit of a beat grid
MAX_REPEAT_OFF = 0.3           # percent, by how the phrase repeats itself two bars later
MAX_BEAT_OFF_MS = 45.0         # further than this from the beat and the phrase is asked for again
MAX_TUNING_CENTS = 20.0
# A calm tune is given more room: a slow melody a quarter of a percent behind the pulse cannot
# be heard to be late, and being held to the same line as a drum part kept the calm tunes of
# one style out of its bucket altogether.
LOOSE = 2.5                    # how many times wider the lines are for a calm tune
DENSE = 0.6                    # a phrase with something struck on this share of its beats can be timed by them
REPEATS = 0.45                 # a phrase that is this like itself two bars later can be timed by that
TRIES = 3
CHANGES = 2                    # how many decks may take a new phrase each time the form comes round
# How the player shapes each turn of the form on top of what the phrases do themselves, by
# style: how far the verse is held back (dB), and how high the lows of the drums and the bass
# are swept away over the second half of the build-up before the chorus lands (Hz; 0 for not
# at all). The sweep is the dance floor's way of building; a band and an orchestra build by
# playing louder.
ARC = {"knight": {"verse_db": -3.5, "sweep_hz": 0}, "warcraft": {"verse_db": -4.5, "sweep_hz": 0},
       "house": {"verse_db": -3.0, "sweep_hz": 250}}
# The pools a bucket is filled in order of, before anything else: what the music cannot start
# without, then one phrase for every other pool, so that whatever the game does there is an answer.
FIRST = (("texture", 0), ("lead", 0), ("rhythm", 1), ("drums", 1), ("bass", 1), ("rhythm", 0), ("lead", 1),
         ("drums", 0), ("drums", 2), ("bass", 2), ("rhythm", 2), ("lead", 2), ("bass", 0))
# How often each channel takes a new phrase compared with the others: tunes and riffs are what
# the ear follows, so they are replaced soonest.
APPETITE = {"lead": 1.5, "rhythm": 1.3, "drums": 1.0, "bass": 1.0, "texture": 0.7}

# How hard each channel plays, by how much is going on (the director's intensity, 0 to 1): calm
# below the first number, hard from the second, steady between. A fight starts at 0.8: the
# drums and the riff go hard at once. A second enemy in the fight (0.85) brings the hard lead,
# and a third (0.90) the hard bass line; a fight against one enemy gets there too, slowly, as
# it goes on. An elite or a boss is everything at once.
GEARS = {"lead": (0.52, 0.83), "rhythm": (0.52, 0.74), "drums": (0.52, 0.74), "bass": (0.50, 0.88)}
# How far past a line the intensity has to be before a channel changes gear, so that one hovering
# on a line does not flicker. It has to be less than the step another enemy makes (two enemies
# are 0.85 and three 0.90, each 0.02 past its line), or that enemy would change nothing.
GEAR_SLACK = 0.015
RHYTHM_FROM = 0.30             # the rhythm part plays once the player is on the move
CALM_PLACES = ("ember",)       # an inn, the moment after a fight, a death: everything plays calm

# Pieces: written music, kept as its parts. See Bucket.add_piece.
PIECE_LEVEL = -13.0            # how loud a piece is with every part playing (LUFS): what five decks of phrases come to
POST_S = 6.0                   # how much of what follows is kept after each stretch of a part, for fading out under what comes next
WINDOW_S = 52.0                # a part is kept in stretches no longer than this, so that no one of them is slow to fetch
FREE_SHARE = 0.12              # how often a stretch of loose phrases comes between two tracks, where there are enough of them
STORY = ("open", "theme", "rise", "moment", "close")       # where in a story a piece belongs; "" for one that is a story in itself

_ONLY = "nothing else"
_TIGHT = "steady timing, tight to the beat"
# A slow tune played alone wanders from the beat if it is left to (it came back a percent and a
# half slow, three times running, for the orchestra's calm tunes). These words hold it.
_STRICT = "played in strict time to a steady pulse, no rubato"

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
        0: [["solo lute", "only a lute, " + _ONLY, "unaccompanied", "a slow singing melody in {key}", _STRICT],
            ["solo {colour}", "only the {colour}, " + _ONLY, "unaccompanied", "a wistful tune in {key}", _STRICT],
            ["solo clean electric guitar", "only one guitar, " + _ONLY, "unaccompanied", "a gentle melody of long notes in {key}", _STRICT],
            ["solo hurdy-gurdy", "only the hurdy-gurdy, " + _ONLY, "a slow modal tune in {key}", _STRICT]],
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
        0: [["solo oboe", "only an oboe, " + _ONLY, "unaccompanied", "a pastoral tune in {key}, a note to every beat", _STRICT],
            ["solo flute", "only a flute, " + _ONLY, "unaccompanied", "a gentle melody in {key} in even notes", _STRICT],
            ["solo french horn", "only a horn, " + _ONLY, "unaccompanied", "a noble slow melody in {key} in long even notes", _STRICT],
            ["solo cello", "only a cello, " + _ONLY, "unaccompanied", "a singing melody in {key} in even notes", _STRICT],
            ["solo harp", "only a harp, " + _ONLY, "unaccompanied", "a simple tune in {key} picked out a note to every beat", _STRICT]],
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

# Uplifting progressive house: happy, warm and laid back. Everything is in a major key, and
# nothing is harsh: no distortion, no acid lines, no sirens.
_NO_KIT = "no drums"
HOUSE = {
    "texture": {0: [
        ["a warm lush synth pad holding a chord of {key}, slowly evolving", "only the pad, " + _ONLY, "no melody", _NO_KIT],
        ["an airy pad with soft white-noise sweeps on {note}", "only the pad, " + _ONLY, "no melody", _NO_KIT],
        ["soft electric-piano chords of {key} held long, with a gentle shimmer", "only the electric piano, " + _ONLY, "no melody", _NO_KIT],
        ["a glassy shimmering pad in {key}, bright and calm", "only the pad, " + _ONLY, "no melody", _NO_KIT],
    ]},
    "lead": {
        0: [["a bell-like synth melody with long echoes in {key}", "only the one synth, " + _ONLY, _NO_KIT, "gentle and spacious", _STRICT],
            ["a soft piano melody in {key}, simple and warm", "only a piano, " + _ONLY, _NO_KIT, "gentle and spacious", _STRICT],
            ["a marimba-like plucked synth playing a sunny tune in {key}", "only the one synth, " + _ONLY, _NO_KIT, _STRICT]],
        1: [["a warm gliding synth lead melody in {key}, happy and singing", "only the one synth, " + _ONLY, _NO_KIT, _TIGHT],
            ["a plucked synth hook in {key}, bouncing and bright", "only the one synth, " + _ONLY, _NO_KIT, _TIGHT],
            ["a house piano riff melody in {key}, joyful", "only a piano, " + _ONLY, _NO_KIT, _TIGHT]],
        2: [["an uplifting anthem lead in {key}, bright and euphoric but smooth", "only the one synth, " + _ONLY, _NO_KIT, _TIGHT],
            ["a soaring string-like synth melody in {key}, hands-in-the-air happy", "only the one synth, " + _ONLY, _NO_KIT, _TIGHT],
            ["a bright piano hook in octaves in {key}, big and joyful", "only a piano, " + _ONLY, _NO_KIT, _TIGHT]],
    },
    "rhythm": {
        0: [["soft electric-piano chords in {key}, one to a bar, mellow", "only the electric piano, " + _ONLY, _NO_KIT, _TIGHT],
            ["a muted plucked synth arpeggio around {note} with a long echo, steady eighth notes", "only the arpeggio, " + _ONLY, _NO_KIT, _TIGHT],
            ["gentle clean guitar-like plucks in {key}, a light repeating figure", "only the one instrument, " + _ONLY, _NO_KIT, _TIGHT]],
        1: [["classic house piano chords in {key}, bouncing on the off-beats", "only a piano, " + _ONLY, _NO_KIT, _TIGHT],
            ["warm synth chord stabs in {key} pulsing in eighth notes", "only the chords, " + _ONLY, _NO_KIT, _TIGHT],
            ["a bright plucked arpeggio rising and falling in {key}, sixteenth notes", "only the arpeggio, " + _ONLY, _NO_KIT, _TIGHT]],
        2: [["big uplifting piano chords in {key}, a chord on every off-beat, joyful", "only a piano, " + _ONLY, _NO_KIT, _TIGHT],
            ["bright wide synth chord stabs in {key} on the off-beats", "only the chords, " + _ONLY, _NO_KIT, _TIGHT],
            ["a sparkling arpeggio at full brightness in {key}, sixteenth notes", "only the arpeggio, " + _ONLY, _NO_KIT, _TIGHT]],
    },
    "drums": {
        0: [["electronic house drums", "only drums, " + _ONLY, "a soft shaker and a rim click, no kick drum"],
            ["electronic house drums", "only drums, " + _ONLY, "a soft four-on-the-floor kick and a closed hi-hat, quiet"],
            ["hand percussion", "only percussion, " + _ONLY, "congas and a shaker in a laid-back pattern, no kick drum"]],
        1: [["electronic house drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "off-beat open hi-hats", "clap on two and four"],
            ["electronic house drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "a shuffling shaker in straight time", "clap on two and four"],
            ["electronic house drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "off-beat hi-hats and congas", "snap on two and four"]],
        2: [["electronic house drums", "only drums, " + _ONLY, "punchy four-on-the-floor kick drum", "open hi-hats on every off-beat",
             "claps on two and four", "a crash on the first beat"],
            ["electronic house drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "a bright ride cymbal on every beat", "claps on two and four"],
            ["electronic house drums", "only drums, " + _ONLY, "four-on-the-floor kick drum", "rolling percussion and tambourine", "claps on two and four"]],
    },
    "bass": {
        0: [["a deep warm sub bass", "only the bass, " + _ONLY, _NO_KIT, "one long note on {note} to every bar"],
            ["a soft round synth bass", "only the bass, " + _ONLY, _NO_KIT, "gentle notes on {note}, two to a bar"]],
        1: [["an off-beat house bass", "only the bass, " + _ONLY, _NO_KIT, "one warm note on {note} on every off-beat", _TIGHT],
            ["a groovy house bassline", "only the bass, " + _ONLY, _NO_KIT, "a bouncing line around {note} in eighth notes", _TIGHT],
            ["a warm plucked synth bass", "only the bass, " + _ONLY, _NO_KIT, "steady eighth notes on {note} with a little walk every fourth bar", _TIGHT]],
        2: [["a rolling house bassline", "only the bass, " + _ONLY, _NO_KIT, "sixteenth notes on {note} between the beats, driving but warm", _TIGHT],
            ["a funky synth bass", "only the bass, " + _ONLY, _NO_KIT, "a syncopated riff around {note}, playful", _TIGHT],
            ["a pumping house bass", "only the bass, " + _ONLY, _NO_KIT, "a strong note on every off-beat on {note} with octave jumps", _TIGHT]],
    },
}

RECIPES = {"knight": KNIGHT, "warcraft": WARCRAFT, "house": HOUSE}

# What each channel does in each part of the form, on top of the way of playing it was asked
# for: held back in the verse, rising through the build-up, and all out in the chorus.
SECTION_WORDS = {
    "drums": {"verse": ["the verse: restrained, leaving room"],
              "build": ["a build-up: fills on the snare drum and toms getting busier and louder bar by bar",
                        "ending in a big fill into the chorus"],
              "chorus": ["the chorus: the same beat bigger and wider, open cymbals", "a crash on the first beat"]},
    "bass": {"verse": ["the verse: restrained and steady"],
             "build": ["a build-up: the line climbs step by step and gets louder"],
             "chorus": ["the chorus: fuller and driving, moving between the root and the fifth"]},
    "rhythm": {"verse": ["the verse: restrained and tight, leaving space"],
               "build": ["a build-up: rising, getting louder and busier towards the chorus"],
               "chorus": ["the chorus: big, open and ringing, the main figure played wide and proud"]},
    "lead": {"verse": ["the verse: short answering phrases with space between them"],
             "build": ["a build-up: a line that climbs higher and higher"],
             "chorus": ["the chorus: the main hook, a strong melody one could sing, played out in full"]},
    "texture": {"verse": ["low and still"], "build": ["slowly swelling and rising"],
                "chorus": ["fuller and brighter, wide open"]},
}
# Where a style has its own words for a part of the form, they stand in for the ones above.
STYLE_SECTION_WORDS = {
    "house": {
        "drums": {"verse": ["the breakdown: stripped back and light"],
                  "build": ["the build-up: a snare roll that gets busier bar by bar", "a rising noise sweep"],
                  "chorus": ["the drop: the full groove, happy and bouncing", "a crash on the first beat"]},
        "bass": {"verse": ["the breakdown: held back and soft"],
                 "build": ["the build-up: the filter opens bar by bar, rising"],
                 "chorus": ["the drop: the full bassline, warm and bouncing"]},
        "rhythm": {"verse": ["the breakdown: filtered and soft"],
                   "build": ["the build-up: the filter opens bar by bar, rising and brightening"],
                   "chorus": ["the drop: bright, wide and joyful"]},
        "lead": {"verse": ["the breakdown: a few notes of the hook, far away"],
                 "build": ["the build-up: the hook rising and getting brighter"],
                 "chorus": ["the drop: the full hook, uplifting, played out"]},
    },
    "warcraft": {
        "drums": {"build": ["a crescendo: rolls on the timpani and snare drum growing louder", "ending in a cymbal crash"],
                  "chorus": ["the full statement: broad and grand, cymbals on the strong beats"]},
        "bass": {"build": ["a crescendo: the line climbs step by step and grows louder"],
                 "chorus": ["the full statement: broad, strong and marching"]},
        "rhythm": {"build": ["a crescendo: the figure rises through the registers and grows louder"],
                   "chorus": ["the full statement: broad and grand"]},
        "lead": {"chorus": ["the full theme: broad, noble and memorable, played out"]},
    },
}
SECTION_NAMES = {"verse": "Verse", "build": "Build-up", "chorus": "Chorus"}


def section_words(genre: str, channel: str, section: str) -> list[str]:
    own = STYLE_SECTION_WORDS.get(genre, {}).get(channel, {})
    return list(own.get(section) or SECTION_WORDS[channel][section])
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
    return {"knight": "lute", "warcraft": "oboe", "house": "synth"}[genre]


def tiers_of(channel: str) -> tuple[int, ...]:
    return (0,) if channel == "texture" else TIERS


def form(bpm: int) -> tuple[int, int, int]:
    """The song's form at a tempo: the lengths of the verse, the build-up and the chorus in bars.
    Twice as many bars at the faster tempos, so that a turn of the form is always somewhere
    between forty seconds and a minute, half of it chorus."""
    return (4, 4, 8) if bpm <= 110 else (8, 8, 16)


def cycle_bars(bpm: int) -> int:
    """How long one turn of the form is, in bars: the length of every phrase at that tempo."""
    return sum(form(bpm))


def bars_of(channel: str, bpm: int) -> int:
    """A phrase's length in bars: one turn of the form, whatever the channel."""
    return cycle_bars(bpm)


@dataclass
class Ask:
    """One phrase to ask for."""
    channel: str
    tier: int
    variant: int
    bars: int                      # the whole phrase: one turn of the form
    sections: tuple[int, ...]      # the bars of its verse, build-up and chorus
    plan: dict[str, Any]
    seed: int
    words: list[str]

    @property
    def minutes(self) -> float:
        return sum(chunk["duration_ms"] for chunk in self.plan["chunks"]) / 60000.0


def ask(profile: composer.ZoneProfile, genre: str, channel: str, tier: int, variant: int, seed: int,
        context: list[str] | None = None) -> Ask:
    """The request for one phrase: a verse, a build-up and a chorus for one instrument, each a
    part of the request with its own words and its own exact length, so that the build-up and
    the chorus start at the same moment in every phrase of the bucket. `profile` is the zone's
    as the style uses it (composer.for_genre)."""
    recipe = composer.genre_of(genre)
    ways = RECIPES[genre][channel][tier]
    note = profile.tonic.split()[0]
    fill = {"note": note, "key": profile.tonic, "colour": tune_instrument(profile, genre)}
    words = [phrase.format(**fill) for phrase in ways[variant % len(ways)]]
    # The mood of the place and of the moment colours the tune and the drone; the parts that
    # keep time are asked for plainly, which is what keeps them steady.
    if channel in ("lead", "texture"):
        words += list(profile.mood[:2]) + list(context or [])
    sections = form(profile.bpm)
    # The words for the time are the ones the experiment held its tempo with. A style's own words
    # for its beat name the instruments that keep it, which a phrase for one instrument must not.
    timing = [] if channel == "texture" else ["steady straight 4/4 beat"]
    common = ["%d BPM" % profile.bpm, profile.tonic] + timing + ["instrumental"]
    avoid = list(dict.fromkeys(recipe["never"] + OTHERS[channel]))
    # ElevenLabs takes whole milliseconds, and at some tempos (110 is one) a bar is not a whole
    # number of them. Each part ends at the nearest millisecond to where it should, so the parts
    # are never more than half a millisecond from their places and the whole is not out at all.
    edges = [round(240000.0 * bars / profile.bpm) for bars in (0, sections[0], sections[0] + sections[1], sum(sections))]
    chunks = [{"text": "[%s]" % SECTION_NAMES[section], "duration_ms": last - first,
               "positive_styles": list(dict.fromkeys(common + words + section_words(genre, channel, section))),
               "negative_styles": avoid, "context_adherence": "high"}
              for section, first, last in zip(SECTIONS, edges, edges[1:])]
    return Ask(channel=channel, tier=tier, variant=variant, bars=sum(sections), sections=sections,
               plan={"chunks": chunks}, seed=seed, words=words)


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


def _timing(audio: np.ndarray, rate: int, bpm: int, bars: int, room: float = 1.0) -> dict[str, Any]:
    """How a stretch of a phrase keeps time: its tempo against the one asked for, how it comes
    round on the bar, and where its beat falls against its own start. `room` widens the lines
    it is held to."""
    bar_s = 240.0 / bpm
    grid = analysis.fit_grid(audio, rate, bpm)
    off = (grid.bpm / bpm - 1.0) * 100.0
    repeat, strength = _repeat_off(audio, rate, bar_s)
    half_beat = 30000.0 / bpm
    beat = grid.distance_to_beat_s(0.0) * 1000.0
    beat = (beat + half_beat / 2.0) % half_beat - half_beat / 2.0      # the beat or the off-beat: see ingest
    # A stretch of long notes has too little struck on its beats for a beat to be fitted to it,
    # and what the fit then says means nothing. Such a stretch is judged only by whether it
    # comes round on the bar, and if it does not repeat either, it is taken as it is: a few long
    # notes cannot be heard to be out of time.
    dense = grid.beats_checked >= DENSE * bars * 4
    found = {"tempo_off": round(off, 3), "repeat_off": round(repeat, 3), "repeat": round(strength, 2),
             "beat_ms": round(beat, 1), "struck": grid.beats_checked, "dense": bool(dense)}
    problems = []
    if dense and abs(off) > MAX_TEMPO_OFF * room:
        problems.append("it is %.2f%% off tempo" % off)
    elif strength >= REPEATS and abs(repeat) > MAX_REPEAT_OFF * room:
        problems.append("it comes round %.2f%% off the bar" % repeat)
    if dense and abs(beat) > MAX_BEAT_OFF_MS * room:
        problems.append("it starts %.0f ms from the beat" % beat)
    found["problems"] = problems
    return found


def measure(audio: np.ndarray, rate: int, bpm: int, channel: str,
            sections: int | tuple[int, ...], tier: int = 1) -> dict[str, Any]:
    """What a phrase is: its length, level, timing and tuning, and in `problems` everything that
    makes it unfit for the bucket (empty when it is fit). `sections` is the bars of its verse,
    build-up and chorus, or one number for a phrase that is a single stretch.

    The verse and the chorus are each held to the tempo and to the beat on their own, since each
    starts at an exact moment and is what the other channels play against. The build-up is not:
    fills and rolls that speed up are what a build-up is."""
    sections = (sections,) if isinstance(sections, int) else tuple(sections)
    bars = sum(sections)
    bar_s = 240.0 / bpm
    asked = bars * bar_s
    room = LOOSE if channel == "lead" and tier == 0 else 1.0
    found: dict[str, Any] = {"seconds": round(len(audio) / rate, 3), "lufs": round(analysis.loudness_lufs(audio, rate), 1),
                             "peak": round(analysis.peak(audio), 3)}
    problems: list[str] = []
    if abs(found["seconds"] - asked) > 0.05:
        problems.append("it is %.2f s long, not %.2f" % (found["seconds"], asked))
    if found["lufs"] < -50.0:
        problems.append("it is all but silent (%.0f LUFS)" % found["lufs"])
    if channel != "texture" and not problems:
        if len(sections) == 1:
            timing = _timing(audio, rate, bpm, bars, room)
            problems += timing.pop("problems")
            found.update(timing)
        else:
            start = 0
            for name, length in zip(SECTIONS, sections):
                first, last = int(round(start * bar_s * rate)), int(round((start + length) * bar_s * rate))
                start += length
                if name == "build":
                    continue
                timing = _timing(audio[first:last], rate, bpm, length, room)
                problems += ["in the %s %s" % (name, problem) for problem in timing.pop("problems")]
                found[name] = timing
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
    frames = int(round(bars * rate * 240.0 / bpm))
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
    seed: int | None = None        # the seed it was asked for with, for anyone studying what came back
    place: str = ""                # the place whose colours and mood it was asked for in
    piece: str = ""                # the piece it is a part of; none for a phrase that stands alone
    order: int = 0                 # which stretch of that piece it is, counting from nought
    post: int = 0                  # samples kept after its end: what the music went on to


class Bucket:
    """The phrases for one place in one style, on disk."""

    def __init__(self, root: Path, zone: str, genre: str, bpm: int, tonic: str):
        self.root, self.zone, self.genre, self.bpm, self.tonic = Path(root), zone, genre, bpm, tonic
        self.folder = self.root / genre / zone
        self.clips: list[Clip] = []
        self.pieces: dict[str, dict[str, Any]] = {}       # written music: what each piece is, by its id
        self._loose_for, self._loose_kept = -1, []
        self.version = 0
        self.everything = False        # play the worn phrases too: set when no new ones can be made
        index = self.folder / "bucket.json"
        if index.is_file():
            kept = json.loads(index.read_text(encoding="utf-8"))
            self.bpm, self.tonic = kept["bpm"], kept["tonic"]      # what its phrases were made at
            self.clips = [Clip(**clip) for clip in kept["clips"]]
            self.pieces = kept.get("pieces", {})
            self.version = kept.get("version", len(self.clips))
            # A pool keeps up to KEEP phrases in play. Phrases that were set aside when a pool
            # held fewer than that come back: the bucket is meant to grow.
            for channel, tier in FIRST:
                room = KEEP - len(self.pool(channel, tier))
                aside = [clip for clip in self.clips if clip.channel == channel and clip.tier == tier
                         and clip.retired and not clip.banned and clip.bars == self.cycle and not clip.piece]
                for clip in aside[:max(room, 0)]:
                    clip.retired = False

    @property
    def key(self) -> str:
        return "%s/%s" % (self.genre, self.zone)

    @property
    def bar_frames(self) -> float:
        """How long a bar is, in samples. At most tempos a whole number; at some (110) not."""
        return RATE * 240.0 / self.bpm

    def frames_of(self, bars: int) -> int:
        """How many samples a phrase of so many bars is, to the nearest one."""
        return int(round(bars * self.bar_frames))

    @property
    def cycle(self) -> int:
        """The length of every phrase in play, in bars: one turn of the form at this tempo."""
        return cycle_bars(self.bpm)

    def _in_play(self, clip: Clip) -> bool:
        if clip.piece:
            # A part of a piece is in play for as long as the piece is: it is never set aside
            # as worn, and a ban is on the whole piece.
            piece = self.pieces.get(clip.piece)
            return piece is not None and not piece.get("banned") and not clip.banned
        # Phrases of another length were made before phrases were a whole turn of the form.
        # They are kept on disk and left out of the music.
        return clip.bars == self.cycle and not clip.banned and (self.everything or not clip.retired)

    def pool(self, channel: str, tier: int) -> list[Clip]:
        """The phrases that stand alone, for one channel at one strength. The parts of pieces are
        not in any pool: they are played as the piece they belong to."""
        return [clip for clip in self._loose() if clip.channel == channel and clip.tier == tier and self._in_play(clip)]

    def _loose(self) -> list[Clip]:
        """The phrases that are not parts of pieces. Kept, since a bucket may hold thousands of
        parts and the pools are looked at many times a second."""
        if self._loose_for != len(self.clips):
            self._loose_kept = [clip for clip in self.clips if not clip.piece]
            self._loose_for = len(self.clips)
        return self._loose_kept

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
                 "version": self.version, "pieces": self.pieces, "clips": [asdict(clip) for clip in self.clips]}
        scratch = self.folder / "bucket.json.new"
        scratch.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
        scratch.replace(self.folder / "bucket.json")

    def add(self, audio: np.ndarray, *, channel: str, tier: int, variant: int = 0, words: list[str] | None = None,
            measured: dict[str, Any] | None = None, source: str = "elevenlabs", seed: int | None = None,
            place: str = "") -> Clip:
        """Puts a phrase in the bucket. `audio` is stereo at 48 kHz and exactly a whole number of
        bars long, beat on the start (see `fit`). This is the way in for any phrase, wherever it
        was made."""
        bars = int(round(len(audio) / self.bar_frames))
        if not bars or len(audio) != self.frames_of(bars):
            raise ValueError("A phrase is a whole number of bars: %d frames is not, at %.2f a bar" % (len(audio), self.bar_frames))
        measured = dict(measured or {})
        lufs = measured.get("lufs")
        if lufs is None:
            lufs = measured["lufs"] = round(analysis.loudness_lufs(audio, RATE), 1)
        # Never more than full scale after the gain, whatever the level says.
        gain = min(LEVEL[channel] - lufs, -20.0 * float(np.log10(max(analysis.peak(audio), 1e-6))) - 1.0)
        clip = Clip(id=uuid.uuid4().hex[:10], channel=channel, tier=tier, variant=variant, bars=bars, frames=len(audio),
                    gain_db=round(gain, 2), created=time.time(), words=list(words or []), measured=measured, source=source,
                    seed=seed, place=place)
        (self.folder / "clips").mkdir(parents=True, exist_ok=True)
        np.save(self.folder / "clips" / (clip.id + ".npy"),
                np.round(np.clip(audio, -1.0, 32767 / 32768) * 32768).astype("<i2"))
        self.clips.append(clip)
        self._save()
        return clip

    def add_piece(self, parts: dict[tuple[str, int], np.ndarray], *, title: str, bar_frames: float, bars: int,
                  post: int = 0, tonic: str = "", story: str = "", moods: tuple[str, ...] | list[str] = (),
                  role: str = "wander", serves: tuple[int, ...] | list[int] = (0, 1),
                  follow: dict[str, list[str]] | None = None, floor: dict[str, float] | None = None,
                  track: str = "", after: str = "", gain_db: float | None = None, source: str = "",
                  credit: str = "", family: str = "", light: bool = False) -> str:
        """Puts a piece of written music in the bucket and returns its id.

        A piece is music that was written as a whole and is kept as its parts: `parts` holds one
        recording for each channel that plays in it (and, where the writer made them, for more
        than one strength of a channel), every one the same length and in step with the others.
        The player plays the parts together, as loud as the game asks for each, so a piece keeps
        its own harmony and its own shape however the channels come and go.

        A piece keeps its own time: `bar_frames` is the length of one of its bars in samples and
        need not be the bucket's. Each recording is the piece (a whole number of samples of it)
        followed by `post` samples of whatever the music went on to, which is what is heard
        fading away under the next piece. A long part is kept in stretches of `bars` bars.

        `story` says where in a story the piece belongs (STORY), `moods` the kinds of place it
        was written for (atlas.KINDS), `role` the director's kind of moment (director.PLACES)
        and `serves` the strengths of what the game asks for that it answers (0 calm, 1 steady,
        2 hard). `follow` makes a channel as loud as the loudest of some others (a band kept
        as one part stands in for the tune and the drone), and `floor` is the least each
        channel is ever played at, so that the moment a story comes to is whole whatever the
        game is doing. `track` is the larger work it was cut from and `after` the piece of
        that work it follows: the player goes on from one to the next without a seam.
        `family` names the changes it was written over: pieces of one family that stand at
        the same place in the story are the same length, bar for bar and chord for chord, so
        the player may take any channel of one with the other channels of another. `light`
        says the piece is of the lighter kind; light and heavy take turns.
        """
        if not parts:
            raise ValueError("A piece needs at least one part")
        lengths = {len(audio) for audio in parts.values()}
        if len(lengths) != 1:
            raise ValueError("The parts of a piece are all one length; these are %s" % sorted(lengths))
        whole = lengths.pop() - post
        if whole <= 0 or post < 0:
            raise ValueError("A piece of %d samples cannot be followed by %d of them" % (whole + post, post))
        if story and story not in STORY:
            raise ValueError("A piece's place in a story is one of %s, not %r" % (", ".join(STORY), story))
        if after and after not in self.pieces:
            raise KeyError("No piece %r for this one to follow" % after)
        for (channel, tier), audio in parts.items():
            if channel not in CHANNELS or tier not in TIERS or audio.ndim != 2 or audio.shape[1] != CHANNELS_OUT:
                raise ValueError("A part is stereo audio for one of %s at a strength of 0, 1 or 2" % (CHANNELS,))
        # One gain for the whole piece, so that its parts keep the balance they were written
        # with: it brings the piece, every channel playing at its middle strength, to the level
        # five decks of phrases come to, and never lets the hardest of it pass full scale.
        if gain_db is None:
            middle = np.zeros((whole, CHANNELS_OUT), dtype=np.float32)
            loudest = np.zeros((whole, CHANNELS_OUT), dtype=np.float32)
            for channel in CHANNELS:
                have = sorted(tier for name, tier in parts if name == channel)
                if not have:
                    continue
                middle += parts[(channel, min(have, key=lambda tier: abs(tier - 1)))][:whole]
                loudest += parts[(channel, have[-1])][:whole]
            lufs = analysis.loudness_lufs(middle, RATE)
            if lufs < -60.0:
                raise ValueError("The piece %r is all but silent (%.0f LUFS)" % (title, lufs))
            peak = max(analysis.peak(middle), analysis.peak(loudest), 1e-6)
            gain_db = min(PIECE_LEVEL - lufs, -20.0 * float(np.log10(peak)) - 1.0)
        window = bars * bar_frames
        # (A bar is not always a whole number of samples, and a part that is one sample over
        # so many bars is not given a stretch of one sample for it.)
        count = max(int(np.ceil((whole - 1.0) / window)), 1)
        edges = [min(int(round(index * window)), whole) for index in range(count)] + [whole]
        piece_id = uuid.uuid4().hex[:10]
        (self.folder / "clips").mkdir(parents=True, exist_ok=True)
        keep = int(POST_S * RATE)
        for (channel, tier), audio in sorted(parts.items()):
            for order, (first, last) in enumerate(zip(edges, edges[1:])):
                stretch = audio[first:min(last + keep, len(audio))]
                clip = Clip(id=uuid.uuid4().hex[:10], channel=channel, tier=tier, variant=0,
                            bars=max(int(round((last - first) / bar_frames)), 1), frames=last - first,
                            gain_db=round(float(gain_db), 2), created=time.time(), words=[title], source=source or "written",
                            piece=piece_id, order=order, post=len(stretch) - (last - first))
                # The parts of pieces are kept as FLAC: the same samples in half the room. (There
                # are thousands of them; the loose phrases, which are few, are kept raw.)
                scratch = self.folder / "clips" / (clip.id + ".part")
                soundfile.write(str(scratch), np.round(np.clip(stretch, -1.0, 32767 / 32768) * 32768).astype("<i2"), RATE,
                                format="FLAC", subtype="PCM_16")
                scratch.replace(self.folder / "clips" / (clip.id + ".flac"))
                self.clips.append(clip)
        self.pieces[piece_id] = {
            "title": title, "track": track, "next": "", "story": story, "moods": list(moods), "role": role,
            "serves": sorted(set(int(tier) for tier in serves)), "bar_frames": float(bar_frames), "bars": int(bars),
            "frames": int(whole), "windows": count, "tonic": tonic, "follow": follow or {}, "floor": floor or {},
            "source": source, "credit": credit, "family": family, "light": bool(light), "created": time.time(),
            "banned": False, "loved": False}
        if after:
            self.pieces[after]["next"] = piece_id
        self._save()
        return piece_id

    def drop_piece(self, piece_id: str) -> None:
        """Takes a piece out of the bucket for good, with the recordings of its parts."""
        if piece_id not in self.pieces:
            raise KeyError("No piece %r in the bucket for %s" % (piece_id, self.key))
        for clip in [clip for clip in self.clips if clip.piece == piece_id]:
            self._file(clip.id).unlink()
            self.clips.remove(clip)
        del self.pieces[piece_id]
        for piece in self.pieces.values():
            if piece.get("next") == piece_id:
                piece["next"] = ""
        self._save()

    def live_pieces(self) -> dict[str, dict[str, Any]]:
        """The pieces in play, by id."""
        return {piece_id: piece for piece_id, piece in self.pieces.items() if not piece.get("banned")}

    def mark(self, clip_ids: list[str], *, retired: bool | None = None, banned: bool | None = None,
             loved: bool | None = None) -> list[Clip]:
        """Sets a phrase aside, bans it or marks it as loved. Returns the phrases it found.

        A ban or a love that lands on a part of a piece is for the whole piece: every part of
        it is marked and returned. A piece is never set aside as worn."""
        wanted, found = set(clip_ids), []
        pieces = {clip.piece for clip in self.clips if clip.id in wanted and clip.piece}
        for piece_id in pieces:
            for name, value in (("banned", banned), ("loved", loved)):
                if value is not None:
                    self.pieces[piece_id][name] = value
        for clip in self.clips:
            if clip.id in wanted or clip.piece in pieces:
                found.append(clip)
                for name, value in (("retired", retired), ("banned", banned), ("loved", loved)):
                    if value is not None and not (name == "retired" and clip.piece):
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
        return self.audio(clip_id).tobytes()

    def _file(self, clip_id: str) -> Path:
        """Where a recording is kept: raw samples for a loose phrase (and for the pieces put in
        before pieces were kept as FLAC), FLAC for the part of a piece."""
        raw = self.folder / "clips" / (clip_id + ".npy")
        return raw if raw.is_file() else self.folder / "clips" / (clip_id + ".flac")

    def audio(self, clip_id: str) -> np.ndarray:
        """A recording as 16-bit stereo samples: for a part of a piece, the stretch and then
        what the music went on to."""
        path = self._file(clip_id)
        if path.suffix == ".npy":
            return np.load(path)
        samples, rate = soundfile.read(str(path), dtype="int16", always_2d=True)
        if rate != RATE:
            raise ValueError("%s is at %d Hz, not %d" % (path, rate, RATE))
        return np.ascontiguousarray(samples, dtype="<i2")

    def describe(self) -> dict[str, Any]:
        """What the player needs to know to play from this bucket."""
        verse, build, chorus = form(self.bpm)
        return {"key": self.key, "zone": self.zone, "genre": self.genre, "bpm": self.bpm, "tonic": self.tonic,
                "rate": RATE, "bar_frames": self.bar_frames, "version": self.version,
                # Every phrase is one turn of this form. The decks take new phrases where it
                # comes round, `changes` of them at most, so the song moves on a verse at a time.
                "cycle_bars": self.cycle, "form": {"verse": verse, "build": build, "chorus": chorus},
                "changes": CHANGES, "arc": ARC[self.genre],
                # Written music: what each piece is. Its parts are among the clips.
                "pieces": {piece_id: {name: piece[name] for name in (
                    "title", "track", "next", "story", "moods", "role", "serves", "bar_frames", "bars", "frames",
                    "windows", "tonic", "follow", "floor", "family", "light")}
                    for piece_id, piece in self.live_pieces().items()},
                "free_share": FREE_SHARE,
                "clips": [self.brief(clip) for clip in self.live()]}

    @staticmethod
    def brief(clip: Clip) -> dict[str, Any]:
        """One phrase as the player is told of it."""
        told = {"id": clip.id, "channel": clip.channel, "tier": clip.tier, "bars": clip.bars,
                "frames": clip.frames, "gain_db": clip.gain_db, "new": clip.plays == 0}
        if clip.piece:
            told.update(piece=clip.piece, order=clip.order, post=clip.post, plays=clip.plays)
        return told

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
               skip: set[tuple[str, int]] | None = None) -> tuple[tuple[str, int], bool] | None:
        """The pool to add a phrase to next, and whether it is wanted in a hurry (two requests
        at a time) or at leisure (one at a time). None when the bucket holds all it can and the
        music has plenty that nobody has heard. `active` is the pools the music is drawing on
        right now (which channels are up, and how hard); `also` counts phrases already on their
        way; `skip` is pools to leave alone for now.

        In a hurry: whatever the music is drawing on that has nothing at all, then one phrase
        for every pool, then every pool to DEPTH (what is in use first, then the hard phrases a
        fight will want, then the rest). At leisure: a pool in use that is running out of
        phrases nobody has heard, then the shallowest pool, until every pool is at MOST."""
        also, skip = also or {}, skip or set()
        active = [pool for pool in (active or []) if pool not in skip]
        pools = [pool for pool in FIRST if pool not in skip]

        def have(pool: tuple[str, int]) -> int:
            return len(self.pool(*pool)) + also.get(pool, 0)

        def unheard(pool: tuple[str, int]) -> int:
            return sum(1 for clip in self.pool(*pool) if clip.plays == 0) + also.get(pool, 0)

        for pool in active + pools:
            if have(pool) < START:
                return pool, True
        # What is in use comes first, then the hard phrases, then the rest; within each, the
        # pool with the fewest, and of two as shallow the channel that changes phrase more often.
        order = active + [pool for pool in pools if pool[1] == 2 and pool not in active] \
            + [pool for pool in pools if pool[1] != 2 and pool not in active]

        def shallowest(limit: int) -> tuple[str, int] | None:
            short = [pool for pool in order if have(pool) < limit]
            if not short:
                return None
            fewest = min(have(pool) for pool in short)
            return next(pool for pool in short if have(pool) == fewest)

        pool = shallowest(DEPTH)
        if pool is not None:
            return pool, True
        hungry = [pool for pool in active if unheard(pool) < AHEAD]
        if hungry:
            return min(hungry, key=lambda pool: (unheard(pool) / APPETITE[pool[0]], have(pool))), False
        pool = shallowest(MOST)
        return (pool, False) if pool is not None else None

    def make_room(self, channel: str, tier: int) -> list[Clip]:
        """Sets aside the most worn phrases of a pool that holds more than it should (KEEP).
        They stay on disk, and come back into play if a day comes when no new ones can be made."""
        gone = []
        while True:
            pool = self.pool(channel, tier)
            spare = [clip for clip in pool if not clip.loved]
            if len(pool) <= KEEP or not spare or self.everything:
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
        self._home: dict[str, Bucket] = {}       # the one bucket each style plays from

    def get(self, place_name: str | None, genre: str) -> Bucket:
        profile = composer.for_genre(atlas.profile_for(place_name), genre)
        key = "%s/%s" % (genre, profile.key)
        if key not in self._have:
            self._have[key] = Bucket(self.root, profile.key, genre, profile.bpm, profile.tonic)
        return self._have[key]

    def home(self, genre: str, place_name: str | None) -> Bucket | None:
        """The bucket a style's song is played from, wherever the player goes.

        A style has one bucket, and it goes on growing: the song does not start again at a
        zone's border. Its tempo and key are those of the place it was begun in; phrases asked
        for later are made in the colours of wherever the player then is, so the song takes on
        each place as it is fed. It is the bucket on disk with the most phrases in play for
        that style, or a new one for `place_name` if the style has none yet; None if it has
        none and the place is not known yet."""
        if genre in self._home:
            return self._home[genre]
        best = None
        for index in sorted((self.root / genre).glob("*/bucket.json")):
            bucket = self.by_key("%s/%s" % (genre, index.parent.name))
            if bucket.live() and (best is None or len(bucket.live()) > len(best.live())):
                best = bucket
        if best is None:
            if not place_name:
                return None
            best = self.get(place_name, genre)
        self._home[genre] = best
        return best

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
        place = profile.key
        styled = composer.for_genre(profile, bucket.genre)
        profile = composer.ZoneProfile(key=bucket.zone, bpm=bucket.bpm, tonic=bucket.tonic,
                                       colours=styled.colours, mood=styled.mood)
        variant = len([clip for clip in bucket.clips if clip.channel == channel and clip.tier == tier and not clip.piece])
        problems: list[str] = []
        for attempt in range(TRIES):
            request = ask(profile, bucket.genre, channel, tier, variant + attempt, self.rng.randrange(2 ** 31), context)
            audio = await self._generate(request, bucket.zone)
            # Measuring takes about a second of arithmetic; it is done off to one side so that
            # the game goes on being followed meanwhile.
            found = await asyncio.to_thread(measure, audio, RATE, bucket.bpm, channel, request.sections, tier)
            problems = found.pop("problems")
            if not problems:
                return bucket.add(fit(audio, RATE, bucket.bpm, request.bars), channel=channel, tier=tier,
                                  variant=request.variant, words=request.words, measured=found,
                                  seed=request.seed, place=place)
            self.turned_away += 1
            log.info("a phrase for %s (%s %s) was turned away: %s", bucket.key, channel, TIER_WORDS[tier], "; ".join(problems))
        raise PhraseFailed(channel, tier, problems)


__all__ = ["Ask", "Bucket", "Buckets", "Clip", "Filler", "PhraseFailed", "ask", "measure", "fit", "CHANNELS", "TIERS",
           "FIRST", "MOST", "ElevenError", "mix", "in_use", "form", "cycle_bars", "STORY", "PIECE_LEVEL"]
