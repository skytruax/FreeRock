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
    "riff-driven late-1970s arena hard rock",
    "two crunchy overdriven rhythm guitars playing open-chord riffs with space between the hits",
    "prominent driving eighth-note bass guitar on the root",
    "plain hard-hitting live drum kit with a heavy backbeat",
    "raw dry live-room sound",
    "great production quality",
]
# The knight half.
KNIGHT = ["medieval colour: lute and hurdy-gurdy"]
# Never wanted anywhere; said in the first part.
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
class Reference:
    """A stretch of an earlier song that new music should stay close to, so a later set sounds
    like the same band as the zone's first one. ElevenLabs allows up to 30 seconds."""
    song_id: str
    start_ms: int
    end_ms: int
    strength: str = "medium"      # low | medium | high | xhigh

    def __post_init__(self) -> None:
        if not 0 < self.end_ms - self.start_ms <= 30_000:
            raise ValueError("A reference must be between 0 and 30 seconds long")


@dataclass
class PartSpec:
    """One part of a request before it is given a place in time."""
    name: str
    bars: int
    styles: list[str]
    avoid: list[str]
    adherence: str = "medium"     # how closely the part follows what came before it


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


def _calm_band(rock: float) -> list[str]:
    """How the band plays in the calm parts for a given amount of rock, from 0 (hardly any) to 1
    (a lot). Battle and Boss are always the full band at full crunch."""
    if not 0.0 <= rock <= 1.0:
        raise ValueError("rock must be between 0 and 1, got %r" % (rock,))
    if rock < 0.34:
        return ["clean chiming electric guitars, the riff played gently",
                "soft steady drums, warm round bass"]
    if rock < 0.67:
        return ["lightly overdriven guitars, the riff played open and loose",
                "steady unhurried drums, eighth-note bass sitting on the root"]
    return ["crunchy rhythm guitars, the riff played with swagger",
            "solid backbeat, driving eighth-note bass"]


def vocabulary(profile: ZoneProfile, rock: float = 0.5) -> dict[str, PartSpec]:
    """Every part FreeRock knows how to ask for, worded for this zone."""
    calm = _calm_band(rock)
    zone = profile.colours + profile.mood
    drone = profile.tonic.split()[0]
    quiet = ["vocals", "tempo changes", "guitar solo"]
    loud = ["vocals", "tempo changes"]

    def wander(name: str, opening: list[str]) -> PartSpec:
        return PartSpec(name, 16, opening + ["relaxed mid-tempo groove"] + calm + zone, quiet)

    def battle(name: str, opening: list[str]) -> PartSpec:
        return PartSpec(name, 16, opening + [
            "full band at full crunch", "harder and louder", "crash cymbal accents",
            "bass pushing hard on the root", "blues-scale lead guitar with wide bends"] + profile.colours, loud)

    parts = [
        PartSpec("Arrival", 4, ["hurdy-gurdy drone on %s swells" % drone,
                                "one guitar alone states the riff"], [], "high"),
        PartSpec("Wander A", 16, ["full band enters on the downbeat", "main riff in four-bar phrases",
                                  "lute carries the melody over the riff", "relaxed mid-tempo groove"]
                 + calm + zone, quiet, "high"),
        wander("Wander B", ["a second riff on the same groove", "lute takes the lead line"]),
        wander("Wander C", ["a third riff on the same groove", "guitar and lute trade the melody"]),
        wander("Wander D", ["a fourth riff, lower and warmer", "hurdy-gurdy carries the melody"]),
        wander("Wander E", ["a new riff with a lift in it", "lute carries the melody"]),
        wander("Wander F", ["a new riff, laid back", "clean guitar carries the melody"]),
        wander("Wander G", ["a new riff, a little brighter", "lute and guitar in unison"]),
        battle("Battle", ["palm-muted galloping riff"]),
        battle("Battle B", ["a different riff, stabbing chords on the off-beats"]),
        battle("Battle C", ["a different riff, low and grinding, then opening up"]),
        PartSpec("Boss", 16, ["full band at full crunch", "double-time feel",
                              "screaming lead guitar over the riff", "fast drum fills",
                              "heroic and dangerous", "bass pushing hard on the root"] + profile.colours, loud),
        PartSpec("Ember", 16, ["half-time feel", "calm after the fight", "clean guitar arpeggios",
                               "lute melody", "hurdy-gurdy drone", "soft drums", "warm round bass"] + zone,
                 ["vocals", "tempo changes", "distorted guitars"]),
        PartSpec("Ember B", 16, ["half-time feel", "resting by the fire", "fingerpicked clean guitar",
                                 "slow lute melody", "soft drums", "warm round bass"] + zone,
                 ["vocals", "tempo changes", "distorted guitars"]),
        PartSpec("Depths", 16, ["dark low-register riff", "floor toms", "low drone",
                                "spacious and echoing", "sparse", "bass low and slow"] + profile.colours,
                 ["vocals", "tempo changes", "bright cymbals"]),
        PartSpec("Depths B", 16, ["slow heavy riff deep underground", "floor toms and a distant kick",
                                  "low drone", "long echoes", "bass low and slow"] + profile.colours,
                 ["vocals", "tempo changes", "bright cymbals"]),
        PartSpec("Night", 16, ["night-time", "sparser and cooler", "clean guitar arpeggios",
                               "slow lute melody", "low hurdy-gurdy drone", "soft brushed drums",
                               "warm round bass"] + profile.colours,
                 ["vocals", "tempo changes", "distorted guitars"]),
        PartSpec("Storm", 16, ["a storm rolling in", "rolling floor toms", "tremolo-picked guitar",
                               "tense and dark", "minor-tinged riff", "bass rumbling on the root"]
                 + profile.colours, loud),
    ]
    return {part.name: part for part in parts}


CORE_SUITE = ("Arrival", "Wander A", "Wander B", "Battle", "Ember", "Depths")
SECOND_SET = ("Wander C", "Wander D", "Night", "Storm", "Battle B", "Boss")
FRESH_SET = ("Wander E", "Wander F", "Wander G", "Ember B", "Depths B", "Battle C")


def build(profile: ZoneProfile, names: tuple[str, ...] | list[str], seed: int | None = None,
          rock: float = 0.5, bars: dict[str, int] | None = None,
          reference: Reference | None = None) -> Request:
    """A request for the named parts, in order.

    The first part carries the whole style, because ElevenLabs takes its tone from there. With a
    `reference`, every part is told to stay close to that stretch of an earlier song.
    """
    words = vocabulary(profile, rock)
    tempo = ["%d BPM" % profile.bpm, profile.tonic, "steady straight 4/4 rock beat"]
    chunks, parts, clock = [], [], 0
    for index, name in enumerate(names):
        spec = words[name]
        count = (bars or {}).get(name, spec.bars)
        length = bars_ms(profile.bpm, count)
        if index == 0:
            styles = tempo + ["instrumental"] + ROCK + KNIGHT + profile.colours + profile.mood + spec.styles
            avoid = NEVER + [word for word in spec.avoid if word not in NEVER]
        else:
            styles = tempo + ["instrumental"] + spec.styles
            avoid = spec.avoid
        chunk: dict[str, Any] = {
            "text": "[%s]" % name, "duration_ms": length,
            "positive_styles": list(dict.fromkeys(styles)),   # each word once, in order
            "negative_styles": avoid, "context_adherence": spec.adherence}
        if reference is not None:
            chunk["conditioning_ref"] = {"song_id": reference.song_id,
                                         "range": {"start_ms": reference.start_ms, "end_ms": reference.end_ms}}
            chunk["condition_strength"] = reference.strength
        chunks.append(chunk)
        parts.append(Part(name, count, clock, clock + length))
        clock += length
    return Request(plan={"chunks": chunks}, parts=parts, bpm=profile.bpm, tonic=profile.tonic, seed=seed)


def core_suite(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
               bars: dict[str, int] | None = None) -> Request:
    """A zone's first music: Arrival, two Wander riffs, Battle, Ember, Depths."""
    return build(profile, CORE_SUITE, seed=seed, rock=rock, bars=bars)


def second_set(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
               reference: Reference | None = None) -> Request:
    """Added after a while in a zone: two more Wander riffs, Night, Storm, a second Battle, Boss."""
    return build(profile, SECOND_SET, seed=seed, rock=rock, reference=reference)


def fresh_set(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
              reference: Reference | None = None) -> Request:
    """Added on later visits: three more Wander riffs, a second Ember and Depths, a third Battle."""
    return build(profile, FRESH_SET, seed=seed, rock=rock, reference=reference)
