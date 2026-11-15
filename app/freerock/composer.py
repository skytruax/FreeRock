"""Turns a zone's music profile into the request FreeRock sends to ElevenLabs.

A request is a list of parts, each with its own style words and an exact length. Every part states
the tempo and key again and is a whole number of bars long, so the parts loop, change on bar
lines, and line up with each other. Requests are written by hand here rather than by ElevenLabs'
own planner, so the same profile always gives the same structure.

ElevenLabs rejects prompts that name artists, so the sound is described in musical terms. Zone
and game names are kept out too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

BEATS_PER_BAR = 4

# The rock half of the recipe, said once in the first part of every request.
ROCK = [
    "instrumental",
    "riff-driven late-1970s arena hard rock",
    "two crunchy overdriven rhythm guitars playing open-chord riffs with space between the hits",
    "prominent driving eighth-note bass guitar on the root",
    "plain hard-hitting live drum kit with a heavy backbeat",
    "raw dry live-room sound",
    "great production quality",
]
# The knight half.
KNIGHT = ["medieval colour: lute and hurdy-gurdy"]
# Never wanted anywhere.
NEVER = ["vocals", "singing", "choir", "spoken word", "synthesizer", "electronic drums",
         "orchestra", "tempo changes", "swing feel", "fade out"]


@dataclass
class ZoneProfile:
    """What makes one zone's music its own."""
    key: str                      # short name used in file names and the ledger, e.g. "elwynn"
    bpm: int
    tonic: str                    # e.g. "G mixolydian", "A minor", "D dorian"
    colours: list[str]            # two or three instruments or textures that belong to the zone
    mood: list[str] = field(default_factory=list)  # a few words for how the zone feels


@dataclass
class Part:
    name: str
    bars: int
    start_ms: int
    end_ms: int

    @property
    def seconds(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0


@dataclass
class Request:
    plan: dict[str, Any]
    parts: list[Part]
    bpm: int
    tonic: str
    seed: int | None

    @property
    def minutes(self) -> float:
        return self.parts[-1].end_ms / 60000.0

    def part(self, name: str) -> Part:
        for part in self.parts:
            if part.name == name:
                return part
        raise KeyError(name)

    def first(self, count: int) -> "Request":
        """The same request cut down to its first `count` parts."""
        return Request(plan={"chunks": self.plan["chunks"][:count]}, parts=self.parts[:count],
                       bpm=self.bpm, tonic=self.tonic, seed=self.seed)


def bars_ms(bpm: int, bars: int) -> int:
    """Length of `bars` bars in milliseconds. ElevenLabs takes whole milliseconds, so a tempo and
    bar count that do not come out whole are refused here rather than rounded: a rounded part
    would drift off the bar line."""
    exact = Fraction(60_000 * BEATS_PER_BAR * bars, bpm)
    if exact.denominator != 1:
        raise ValueError("%d bars at %d BPM is %s ms, not a whole number" % (bars, bpm, exact))
    return int(exact)


def _rock_words(rock: float) -> dict[str, list[str]]:
    """How the calm parts are worded for a given amount of rock, from 0 (hardly any) to 1 (a lot).
    Battle is always the full band at full crunch."""
    if not 0.0 <= rock <= 1.0:
        raise ValueError("rock must be between 0 and 1, got %r" % (rock,))
    if rock < 0.34:
        guitars = "clean chiming electric guitars, the riff played gently"
        band = "soft steady drums, warm round bass"
    elif rock < 0.67:
        guitars = "lightly overdriven guitars, the riff played open and loose"
        band = "steady unhurried drums, eighth-note bass sitting on the root"
    else:
        guitars = "crunchy rhythm guitars, the riff played with swagger"
        band = "solid backbeat, driving eighth-note bass"
    return {"guitars": [guitars], "band": [band]}


def _chunk(name: str, duration_ms: int, styles: list[str], avoid: list[str],
           adherence: str) -> dict[str, Any]:
    return {"text": "[%s]" % name, "duration_ms": duration_ms, "positive_styles": styles,
            "negative_styles": avoid, "context_adherence": adherence}


def _layout(bpm: int, parts: list[tuple[str, int]]) -> list[Part]:
    laid, clock = [], 0
    for name, bars in parts:
        length = bars_ms(bpm, bars)
        laid.append(Part(name, bars, clock, clock + length))
        clock += length
    return laid


def core_suite(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
               bars: dict[str, int] | None = None) -> Request:
    """The request for a zone's first music: Arrival, two Wander riffs, Battle, Ember, Depths."""
    counts = {"Arrival": 4, "Wander A": 16, "Wander B": 16, "Battle": 16, "Ember": 16, "Depths": 16}
    counts.update(bars or {})
    parts = _layout(profile.bpm, list(counts.items()))
    words = _rock_words(rock)
    tempo = ["%d BPM" % profile.bpm, profile.tonic, "steady straight 4/4 rock beat"]
    drone_note = profile.tonic.split()[0]
    zone = profile.colours + profile.mood

    styles = {
        # The first part carries the whole style; ElevenLabs takes its tone from there.
        "Arrival": tempo + ROCK + KNIGHT + zone + [
            "hurdy-gurdy drone on %s swells" % drone_note, "one guitar alone states the riff"],
        "Wander A": tempo + ["instrumental", "full band enters on the downbeat",
                             "main riff in four-bar phrases", "lute carries the melody over the riff",
                             "relaxed mid-tempo groove"] + words["guitars"] + words["band"] + zone,
        "Wander B": tempo + ["instrumental", "a second riff on the same groove",
                             "lute takes the lead line", "relaxed mid-tempo groove"]
                          + words["guitars"] + words["band"] + zone,
        "Battle": tempo + ["instrumental", "full band at full crunch", "harder and louder",
                           "palm-muted galloping riff", "crash cymbal accents",
                           "bass pushing hard on the root", "blues-scale lead guitar with wide bends"]
                        + profile.colours,
        "Ember": tempo + ["instrumental", "half-time feel", "calm after the fight",
                          "clean guitar arpeggios", "lute melody", "hurdy-gurdy drone",
                          "soft drums", "warm round bass"] + zone,
        "Depths": tempo + ["instrumental", "dark low-register riff", "floor toms", "low drone",
                           "spacious and echoing", "sparse", "bass low and slow"] + profile.colours,
    }
    avoid = {
        "Arrival": NEVER,
        "Wander A": ["vocals", "tempo changes", "guitar solo"],
        "Wander B": ["vocals", "tempo changes", "guitar solo"],
        "Battle": ["vocals", "tempo changes"],
        "Ember": ["vocals", "tempo changes", "distorted guitars"],
        "Depths": ["vocals", "tempo changes", "bright cymbals"],
    }
    adherence = {"Arrival": "high", "Wander A": "high"}
    chunks = [_chunk(part.name, part.end_ms - part.start_ms, styles[part.name], avoid[part.name],
                     adherence.get(part.name, "medium")) for part in parts]
    return Request(plan={"chunks": chunks}, parts=parts, bpm=profile.bpm, tonic=profile.tonic, seed=seed)
