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

# ---------------------------------------------------------------------------------------------
# Styles. The same game, the same ladder of pieces (an opening, exploring pieces, a hard piece, battle
# pieces, a boss piece, a calm one, one for caves, one for night), asked for in three different
# kinds of music. Which one new music is made in is a setting (settings.genre); what is in the
# library is kept by style, so changing the setting changes what is heard and what is made next.
#
# Each style gives: what is said once at the head of every request; what is never wanted; how the
# beat is described; and, for every kind of piece, a list of feels to go down. The lists are what
# make ten pieces in a request ten different ideas.
# ---------------------------------------------------------------------------------------------
KNIGHT = {
    "label": "Knight Rock",
    "about": "riff rock with lute and hurdy-gurdy",
    "base": [
        "riff-driven late-1970s arena hard rock, loud and simple",
        "two crunchy overdriven rhythm guitars locked tight, open-chord riffs with space between the hits",
        "prominent driving eighth-note bass guitar on the root",
        "plain hard-hitting live drum kit with a heavy backbeat, no frills",
        "gritty blues-scale lead guitar with wide bends",
        "raw dry live-room sound, every instrument clear and separate",
        "great production quality",
        "each section has its own feel and its own tune",
        "medieval colour: lute and hurdy-gurdy",
    ],
    "never": ["vocals", "singing", "choir", "spoken word", "synthesizer", "electronic drums",
              "orchestra", "tempo changes", "swing feel", "fade out"],
    "beat": "steady straight 4/4 rock beat",
    "arrival": ["hurdy-gurdy drone on {tonic} swells", "one guitar alone states the riff"],
    "wander": (
        ["the main riff, stated plainly by the whole band", "four-bar phrases", "lute doubles the riff"],
        ["half-time swagger: the snare falls on beat three", "wide open chords left ringing", "slow bends on the lead guitar"],
        ["clean guitar arpeggios", "the lute carries a singing melody in front", "rim clicks and light hi-hat"],
        ["a stop-and-go riff: the whole band hits together and leaves gaps", "drum fills answer in the gaps"],
        ["call and answer: the guitar asks a phrase and the lute answers it", "steady groove underneath"],
        ["a loping walking groove", "hurdy-gurdy drone and melody on top", "guitars chop on the off-beats"],
        ["twin guitars in harmony play a proud tune", "marching snare"],
        ["a quiet verse: bass and drums carry it", "guitars play single muted notes", "lute fills in between"],
        ["bright open strumming", "tambourine on the backbeat", "a tune you could whistle"],
        ["a low riff on the bottom strings", "tom-tom groove instead of cymbals", "dark and steady"],
        ["a skipping folk-dance tune over the rock groove", "fiddle-like bends on the lead guitar"],
        ["a slow build: it starts sparse and an instrument joins every two bars"],
    ),
    "battle": (
        ["palm-muted galloping riff"],
        ["stabbing chords on the off-beats", "busy bass line running under them"],
        ["a low grinding riff that opens up into big chords"],
        ["a fast unison riff, guitars and bass locked together"],
        ["pounding kick drum on every beat", "chant-like guitar hook"],
        ["a riff that keeps falling by steps", "snare rolls into every fourth bar"],
    ),
    "battle always": ["full band at full crunch", "harder and louder", "crash cymbal accents",
                      "bass pushing hard on the root"],
    "storm": (
        ["a hard driving riff, loud and wide open", "pounding floor toms and crash cymbals like thunder"],
        ["a galloping charge: palm-muted riff in straight time", "driving snare on every beat"],
        ["big ringing power chords with the drums rolling underneath", "lead guitar howling over the top"],
    ),
    "storm always": ["full band at full crunch", "bass pushing hard on the root",
                     "blues-scale lead guitar with wide bends"],
    "boss": (
        ["full band at full crunch", "double-time feel", "screaming lead guitar over the riff",
         "fast drum fills", "heroic and dangerous", "bass pushing hard on the root"],
        ["full band at full crunch", "double-time feel", "a second, lower riff under a screaming lead",
         "fast drum fills", "heroic and dangerous", "bass pushing hard on the root"],
    ),
    "calm": (
        ["half-time feel", "clean guitar arpeggios", "lute melody", "hurdy-gurdy drone", "soft drums", "warm round bass"],
        ["half-time feel", "fingerpicked clean guitar", "slow lute melody", "brushed drums", "long warm bass notes"],
        ["half-time feel", "a gentle lilt", "lute and clean guitar in turn", "soft hand drum"],
    ),
    "deep": (
        ["dark low-register riff", "floor toms", "low drone", "spacious and echoing", "sparse", "bass low and slow"],
        ["slow heavy riff deep underground", "floor toms and a distant kick", "low drone", "long echoes", "bass low and slow"],
        ["single low guitar notes left to ring", "a heartbeat kick drum", "scraping harmonics far off", "bass low and slow"],
    ),
    "night": (
        ["night-time", "sparser and cooler", "clean guitar arpeggios", "slow lute melody",
         "low hurdy-gurdy drone", "soft brushed drums", "warm round bass"],
        ["deep in the night", "a lone clean guitar and a far-off drone", "brushed drums barely there",
         "long warm bass notes"],
    ),
    "theme": (["this place's own theme, stated plainly", "full band enters on the downbeat",
               "a memorable riff in four-bar phrases"],
              ["the same theme answered", "the melody moves to another instrument", "a lift in the last four bars"]),
    "soft avoid": ["distorted guitars"],
    "colours": "all",          # the zone's instruments are this style's own
    # A song: what each of its sections is, in this style. The verse and the bridge also take a
    # feel from the list above, so that no two songs are built the same.
    "song": {
        "Intro": ["intro: one guitar states the main riff alone", "the band crashes in on the last bar"],
        "Verse": ["verse: tight and dry, leaving room"],
        "Chorus": ["chorus: big open chords and the hook, a tune to shout along to",
                   "lead guitar and lute play the hook together", "crash cymbals"],
        "Verse B": ["second verse: the riff of the first verse again", "a new answering melody on top"],
        "Chorus B": ["chorus again: the same hook, a little bigger"],
        "Bridge": ["bridge: a change of scene"],
        "Solo": ["solo: the lead guitar takes a blues-scale solo over the verse riff", "the band digs in behind it"],
        "Chorus C": ["last chorus: the same hook at full strength", "lead guitar soaring over it"],
        "Outro": ["outro: the main riff one last time", "ends on a single held chord left to ring"],
    },
}

WARCRAFT = {
    "label": "Warcraft",
    "about": "an orchestral fantasy score in the old style",
    "base": [
        "orchestral fantasy adventure score for a role-playing game",
        "live symphony orchestra: strings, french horns, woodwinds, harp and percussion",
        "a memorable sweeping melody",
        "warm concert-hall sound, every section of the orchestra clear",
        "great production quality",
        "each section has its own feel and its own tune",
    ],
    "never": ["vocals", "singing", "choir", "spoken word", "electric guitar", "drum kit", "synthesizer",
              "electronic drums", "tempo changes", "rubato", "fade out"],
    "beat": "steady 4/4 pulse kept by the low strings and percussion",
    "arrival": ["a soft swell of strings on {tonic}", "a solo horn states the theme"],
    "wander": (
        ["the main theme on full strings, broad and warm", "harp arpeggios underneath"],
        ["a pastoral tune on solo oboe over quiet strings", "pizzicato basses walking"],
        ["a noble horn melody over a gentle string ostinato"],
        ["a lilting woodwind dance", "pizzicato strings and tambourine"],
        ["a solo cello sings the tune", "harp and flute answer it"],
        ["a walking string ostinato with a clarinet melody on top", "soft timpani on the first beat"],
        ["a playful duet of bassoon and flute over light percussion"],
        ["violins carry the tune high and sweet", "horns hold long warm chords"],
        ["a slow build: one section of the orchestra joins every two bars"],
        ["a wistful melody on solo violin", "low strings moving slowly beneath"],
        ["a marching tune for horns and snare drum, proud and unhurried"],
        ["harp and celesta trade a light figure", "strings breathe long chords"],
    ),
    "battle": (
        ["a driving ostinato in the low strings", "brass stabs on the off-beats"],
        ["a snare-drum march with trumpets calling", "racing violins"],
        ["fast swirling strings and crashing cymbals", "trombones hammering the beat"],
        ["a heavy stamping rhythm for the whole orchestra", "horns in unison carry a fierce tune"],
        ["a chase: staccato strings and xylophone, timpani rolling"],
        ["low brass and basses grind a dark figure", "high strings scream above"],
    ),
    "battle always": ["pounding timpani and war drums", "the full orchestra, loud and urgent"],
    "storm": (
        ["a galloping string ostinato", "horns in full cry", "rolling timpani"],
        ["a great surging theme for full brass", "strings racing underneath", "cymbal crashes"],
        ["a ride at full tilt: driving snare drum and trumpets", "the tune leaping upward"],
    ),
    "storm always": ["the full orchestra at full strength", "heroic and wide open"],
    "boss": (
        ["the full orchestra at its loudest", "pounding war drums and low brass", "strings racing",
         "a fierce heroic theme on the horns", "dangerous"],
        ["the full orchestra at its loudest", "hammering timpani", "trombones and tuba on a grim march",
         "violins in frantic runs", "dangerous"],
    ),
    "calm": (
        ["solo harp and a quiet flute", "soft sustained strings", "slow and still"],
        ["a gentle tune on clarinet", "muted strings holding long chords", "harp now and then"],
        ["strings alone, hushed, a slow hymn-like tune"],
    ),
    "deep": (
        ["low strings and contrabassoon", "a deep drum far off", "eerie sustained high strings", "sparse and echoing"],
        ["a slow dark figure in the basses", "tremolo strings shivering", "a low gong now and then"],
        ["bass clarinet alone in the dark", "harp harmonics like dripping water", "a heartbeat drum"],
    ),
    "night": (
        ["night-time", "celesta and harp under a still string chord", "a lone clarinet"],
        ["deep in the night", "muted horns far away", "a slow harp figure", "strings barely there"],
    ),
    "theme": (["this place's own theme, stated plainly by the orchestra", "a tune to remember"],
              ["the same theme answered by another section of the orchestra", "a lift in the last four bars"]),
    "soft avoid": ["loud brass"],
    "colours": "acoustic",     # the zone's instruments, without the guitars and the rock band
    "song": {
        "Intro": ["introduction: a solo horn states the theme over a soft string chord"],
        "Verse": ["first statement of the tune, unhurried"],
        "Chorus": ["the main theme on full strings, broad and warm", "horns answer each phrase", "harp sweeping"],
        "Verse B": ["the opening tune again on a different solo instrument", "a counter-melody in the violas"],
        "Chorus B": ["the main theme again, fuller"],
        "Bridge": ["a quieter middle section with a new tune"],
        "Solo": ["a solo passage: one instrument sings a variation of the tune over quiet strings",
                 "the orchestra gathers under it"],
        "Chorus C": ["the main theme at its grandest: the full orchestra, timpani rolling"],
        "Outro": ["closing: the theme winds down to harp and one held string chord", "ends softly"],
    },
}

TRANCE = {
    "label": "Trance",
    "about": "uplifting trance, built for bringing parts in and out",
    "base": [
        "uplifting trance",
        "four-on-the-floor kick drum with off-beat open hi-hats and claps",
        "rolling sixteenth-note bassline locked to the kick",
        "bright supersaw chords, plucked arpeggios and wide lush pads",
        "clean modern club production, every part clear and separate",
        "great production quality",
        "each section has its own feel and its own tune",
    ],
    "never": ["vocals", "singing", "choir", "spoken word", "vocal chops", "tempo changes", "swing feel",
              "fade out"],
    "beat": "steady four-on-the-floor beat",
    "arrival": ["a warm pad swells in on {tonic}", "a filtered arpeggio slowly opens"],
    "wander": (
        ["a plucked arpeggio carries the tune over warm pads", "light kick and hi-hats"],
        ["a gliding lead melody over the rolling bass", "soft claps"],
        ["gated pads pulsing with the beat", "a bell-like motif on top"],
        ["stripped back: kick, bass and one filtered arpeggio slowly opening"],
        ["call and answer between a pluck and a soft lead"],
        ["a hypnotic acid line weaving round the bass", "shuffling hi-hats in straight time"],
        ["a piano-like chord figure with the kick underneath", "a rising pad"],
        ["bright trance-gate chords", "a simple hook on a square lead"],
        ["deep and rolling: mostly bass and drums, a pad breathing behind"],
        ["an arpeggio that climbs a step every two bars", "open hi-hats lifting it"],
        ["a slow build: one part joins every two bars"],
        ["a plucked melody with long echoes", "sub bass and a soft kick"],
    ),
    "battle": (
        ["full-on peak: a supersaw anthem lead", "snare rolls into every eighth bar"],
        ["a hard stabbing lead riff", "the bassline at its busiest"],
        ["a racing arpeggio at full brightness", "crash cymbals on the downbeats"],
        ["a pounding tech-trance groove: distorted bass stabs and a siren-like lead"],
        ["an anthem in octaves over galloping bass"],
        ["a dark driving riff that opens into bright chords"],
    ),
    "battle always": ["driving bass and pounding kick", "loud and urgent"],
    "storm": (
        ["a build that keeps rising: snare roll and a filter sweeping up", "then the full anthem"],
        ["a soaring lead over the full groove, wide open", "white-noise sweeps"],
        ["galloping bass and a climbing arpeggio", "claps on every beat"],
    ),
    "storm always": ["the full track at full energy", "euphoric"],
    "boss": (
        ["the hardest drop: a distorted lead, pounding kick, huge reverse crashes", "fierce and dangerous"],
        ["a relentless acid riff over the hardest kick", "sirens rising", "fierce and dangerous"],
    ),
    "calm": (
        ["a breakdown with no kick", "lush pads and a slow piano-like melody", "soft sub bass"],
        ["ambient pads and a distant pluck", "a gentle shaker", "long warm bass notes"],
        ["a slow arpeggio under a held pad", "no drums but a soft heartbeat kick"],
    ),
    "deep": (
        ["dark and deep: a sub bass pulse", "echoing drips of sound", "a low drone", "sparse"],
        ["a slow rumbling bass and far-off metallic echoes", "a muffled kick"],
        ["a cold pad and a single low note repeating", "clicks and distant reverbs"],
    ),
    "night": (
        ["night-time", "a chilled breakdown under the stars: soft pads and a slow arpeggio", "no kick"],
        ["deep in the night", "a glassy pad, a few plucked notes with long echoes", "soft sub bass"],
    ),
    "theme": (["this place's own hook, stated plainly on a plucked lead", "full groove from the first beat"],
              ["the same hook answered by a brighter lead", "a lift in the last four bars"]),
    "soft avoid": ["distorted lead"],
    "colours": "none",         # a zone gives trance its key and its mood, not its instruments
    "song": {
        "Intro": ["intro: kick drum and a filtered arpeggio", "the filter slowly opens"],
        "Verse": ["the groove settles in"],
        "Chorus": ["the drop: a supersaw lead plays the anthem hook over the full groove", "crash on the downbeat"],
        "Verse B": ["breakdown: the kick drops out", "pads and the hook on a soft lead",
                    "a snare roll builds in the last two bars"],
        "Chorus B": ["the drop again: the same anthem hook, brighter"],
        "Bridge": ["a stripped-back stretch of groove"],
        "Solo": ["the build: a snare roll and a rising sweep over the arpeggio", "everything climbs toward the final drop"],
        "Chorus C": ["final drop: the anthem with a counter-melody on top, full energy"],
        "Outro": ["outro: the parts drop away one by one", "ends on the kick and one last pad chord"],
    },
}

GENRES = {"knight": KNIGHT, "warcraft": WARCRAFT, "trance": TRANCE}
# What kind of song the next one is. Each song a place gets takes the next of these, so that
# one song after another is not the same song again.
CHARACTERS = (
    "an anthem with a big hook that sticks",
    "a light-footed travelling song",
    "a brooding slow-burner that builds to a blaze",
    "a swaggering mid-tempo stomp",
    "a wistful song that opens out in the chorus",
    "a tense, coiled song that lets go in the chorus",
    "a triumphant march of a song",
    "a playful, cheeky song with a spring in its step",
    "a wide-open song for the long road",
    "a dark, heavy song with a defiant chorus",
)
DEFAULT_GENRE = "knight"
# Kept for callers that only want the rock recipe's words.
ROCK = KNIGHT["base"][:-1]
NEVER = KNIGHT["never"]
WANDER_FEELS, BATTLE_FEELS = KNIGHT["wander"], KNIGHT["battle"]

# Words in a zone's colours that belong to a rock band and have no place in an orchestra.
_BAND_WORDS = ("guitar", "riff", "chord", "wah", "palm-muted", "power", "twelve-string", "strum", "slide")


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
    bars: int                     # 16 stands for "a full piece" and 32 for "twice that"; see build()
    styles: list[str]
    avoid: list[str]
    adherence: str = "medium"     # how closely the part follows what came before it
    song: bool = False            # a section of the request's song, played in order with the others


@dataclass
class Part:
    name: str
    bars: int
    start_ms: int
    end_ms: int
    song: str | None = None       # the song this part is a section of, if it is one

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
    """How hard the band plays in the exploring pieces for a given amount of rock, from 0 (hardly
    any) to 1 (a lot). Battle and Boss are always the full band at full crunch. Knight Rock only:
    the other styles have no rock to turn up."""
    if not 0.0 <= rock <= 1.0:
        raise ValueError("rock must be between 0 and 1, got %r" % (rock,))
    if rock < 0.34:
        return ["clean chiming electric guitars", "soft drums, warm round bass"]
    if rock < 0.67:
        return ["overdriven guitars with a bit of bite", "eighth-note bass sitting on the root"]
    return ["crunchy rhythm guitars with swagger", "driving eighth-note bass on the root"]


def genre_of(key: str | None) -> dict[str, Any]:
    """The recipe for a style by its short name. An unknown name is an error, not Knight Rock."""
    if key not in GENRES:
        raise ValueError("No style called %r; the styles are %s" % (key, ", ".join(GENRES)))
    return GENRES[key]


def for_genre(profile: ZoneProfile, genre: str = DEFAULT_GENRE) -> ZoneProfile:
    """A zone's profile as one style uses it. Knight Rock takes it whole. The orchestra keeps the
    zone's tempo, key and mood and those of its instruments that are not a rock band's. Trance
    keeps the key note and the mood, in a minor key at a dance tempo."""
    recipe = genre_of(genre)
    if recipe["colours"] == "all":
        return profile
    if recipe["colours"] == "acoustic":
        colours = [colour for colour in profile.colours if not any(word in colour for word in _BAND_WORDS)]
        return ZoneProfile(key=profile.key, bpm=profile.bpm, tonic=profile.tonic, colours=colours,
                           mood=list(profile.mood))
    return ZoneProfile(key=profile.key, bpm=150 if profile.bpm >= 150 else 128,
                       tonic=profile.tonic.split()[0] + " minor", colours=[], mood=list(profile.mood))


def vocabulary(profile: ZoneProfile, rock: float = 0.5, turn: int = 0,
               genre: str = DEFAULT_GENRE) -> dict[str, PartSpec]:
    """Every part FreeRock knows how to ask for, worded for this zone in one style. `profile` is
    the zone's profile as that style uses it (for_genre). `turn` moves down the lists of feels,
    so that a zone's third fresh set is not asked for in the words of its first."""
    recipe = genre_of(genre)
    if not 0.0 <= rock <= 1.0:
        raise ValueError("rock must be between 0 and 1, got %r" % (rock,))
    calm = _calm_band(rock) if genre == "knight" else []
    zone = profile.colours + profile.mood
    tonic = profile.tonic.split()[0]
    quiet = ["vocals", "tempo changes"] + (["guitar solo"] if genre == "knight" else [])
    loud = ["vocals", "tempo changes"]
    soft = ["vocals", "tempo changes"] + recipe["soft avoid"]
    dark = ["vocals", "tempo changes", "bright cymbals"]

    def feel(kind: str, index: int) -> list[str]:
        feels = recipe[kind]
        return list(feels[(index + turn * 3) % len(feels)])

    def wander(letter: str, index: int, adherence: str = "medium") -> PartSpec:
        return PartSpec("Wander " + letter, 16, feel("wander", index) + calm + zone, quiet, adherence)

    def battle(name: str, index: int) -> PartSpec:
        return PartSpec(name, 16, feel("battle", index) + recipe["battle always"] + profile.colours, loud)

    def storm(name: str, index: int) -> PartSpec:
        # The hard piece without a fight: a rain storm, a long ride at full tilt, a roll between pulls.
        return PartSpec(name, 16, feel("storm", index) + recipe["storm always"] + profile.colours, loud)

    def boss(name: str, index: int) -> PartSpec:
        return PartSpec(name, 16, list(recipe["boss"][index % len(recipe["boss"])]) + profile.colours, loud)

    # The sections of a song. The verse and the bridge each take a feel, a different pair for
    # every song a zone gets; the choruses share one hook and are told to stay close to it.
    said = recipe["song"]
    # Said of every section of a song: it goes somewhere. Without it a sixteen-bar verse comes
    # back as one four-bar riff played four times.
    onward = ["the tune keeps developing: no four bars the same as the last"]
    song = [
        PartSpec("Intro", 4, list(said["Intro"]) + zone, [], "high", song=True),
        PartSpec("Verse", 32, list(said["Verse"]) + feel("wander", 0) + onward + calm + zone, quiet, "high", song=True),
        PartSpec("Chorus", 16, list(said["Chorus"]) + zone, loud, "medium", song=True),
        PartSpec("Verse B", 16, list(said["Verse B"]) + onward + calm, quiet, "high", song=True),
        PartSpec("Chorus B", 16, list(said["Chorus B"]), loud, "high", song=True),
        PartSpec("Bridge", 16, list(said["Bridge"]) + feel("wander", 1) + onward + calm, quiet, "medium", song=True),
        PartSpec("Solo", 16, list(said["Solo"]) + onward, loud, "high", song=True),
        PartSpec("Chorus C", 16, list(said["Chorus C"]), loud, "high", song=True),
        PartSpec("Outro", 4, list(said["Outro"]), [], "high", song=True),
    ]
    theme_a, theme_b = recipe["theme"]
    parts = song + [
        PartSpec("Arrival", 4, [words.format(tonic=tonic) for words in recipe["arrival"]], [], "high"),
        wander("A", 0, "high"),
        *[wander(letter, index) for index, letter in enumerate("BCDEFGHIJKL", start=1)],
        # A named place's own piece: eight bars of theme and eight that answer it.
        PartSpec("Theme A", 8, list(theme_a) + calm + zone, quiet, "high", song=True),
        PartSpec("Theme B", 8, list(theme_b) + calm + zone, quiet, song=True),
        battle("Battle", 0), battle("Battle B", 1), battle("Battle C", 2),
        battle("Battle D", 3), battle("Battle E", 4), battle("Battle F", 5),
        # In a song set the battle piece is twice the length: there is one of it, and fights are long.
        PartSpec("Fight", 32, feel("battle", 0) + recipe["battle always"]
                 + ["it develops: a second riff answers the first half-way through"] + profile.colours, loud),
        boss("Boss", 0), boss("Boss B", 1),
        storm("Storm", 0), storm("Storm B", 1), storm("Storm C", 2),
        PartSpec("Ember", 16, ["calm after the fight"] + feel("calm", 0) + zone, soft),
        PartSpec("Ember B", 16, ["resting by the fire"] + feel("calm", 1) + zone, soft),
        PartSpec("Ember C", 16, ["a quiet hour"] + feel("calm", 2) + zone, soft),
        PartSpec("Depths", 16, feel("deep", 0) + profile.colours, dark),
        PartSpec("Depths B", 16, feel("deep", 1) + profile.colours, dark),
        PartSpec("Depths C", 16, feel("deep", 2) + profile.colours, dark),
        PartSpec("Night", 16, list(recipe["night"][0]) + profile.colours, soft),
        PartSpec("Night B", 16, list(recipe["night"][1]) + profile.colours, soft),
    ]
    return {part.name: part for part in parts}


# What a request holds. Its heart is a song: an intro, a long verse, a chorus, a second verse,
# the chorus again, a bridge, a solo, the last chorus and an ending, played in that order from
# start to finish: seventy-two bars, two and a half to three and a half minutes of music that goes
# somewhere. With it comes a battle piece of twice the usual length, and after a zone's first
# request one more piece the game calls for, a different one each time. Every set a place gets
# is another song.
SONG = ("Intro", "Verse", "Chorus", "Verse B", "Chorus B", "Bridge", "Solo", "Chorus C", "Outro")
CORE_SUITE = SONG + ("Fight",)
SECOND_SET = SONG + ("Fight", "Ember")
EXTRAS = ("Storm", "Boss", "Depths", "Night")     # one with each fresh set, in turn
FRESH_SET = SONG + ("Fight", "Storm")
PLACE_PIECE = ("Theme A", "Theme B")
# The older kind of request: ten short pieces. Still understood, for music made before.
PIECES = ("Arrival", "Wander A", "Wander B", "Wander C", "Storm", "Battle", "Battle B", "Boss", "Ember", "Depths")


def build(profile: ZoneProfile, names: tuple[str, ...] | list[str], seed: int | None = None,
          rock: float = 0.5, bars: dict[str, int] | None = None,
          reference: Reference | None = None, part_bars: int = 8, turn: int = 0,
          genre: str = DEFAULT_GENRE, context: list[str] | None = None) -> Request:
    """A request for the named parts, in order.

    The first part carries the whole style, because ElevenLabs takes its tone from there. With a
    `reference`, every part is told to stay close to that stretch of an earlier song.

    `part_bars` is the length of the full-length parts (everything but Arrival). Sixteen suits
    most tempos; a slow zone uses fewer so its music does not run past four minutes a request,
    and a fast one uses more. `bars` sets single parts by name and wins over it.
    """
    if part_bars % 4:
        raise ValueError("Parts are cut into four-bar cells, so part_bars must be a multiple of 4")
    recipe = genre_of(genre)
    profile = for_genre(profile, genre)       # trance moves a zone to a dance tempo and a minor key
    words = vocabulary(profile, rock, turn, genre)
    tempo = ["%d BPM" % profile.bpm, profile.tonic, recipe["beat"]]
    chunks, parts, clock = [], [], 0
    for index, name in enumerate(names):
        spec = words[name]
        # A long verse is twice a piece at a brisk tempo; at a slow one that is the best part of
        # a minute on one idea, so it is a single piece there.
        full = {16: part_bars, 32: 2 * part_bars if profile.bpm >= 110 else part_bars}.get(spec.bars, spec.bars)
        count = (bars or {}).get(name, full)
        length = bars_ms(profile.bpm, count)
        if index == 0:
            # `context` is what is true in the game as the song is written (night, rain, a run of
            # fights); with the song's character it goes at the head, where the whole song takes
            # its tone from.
            moment = ([CHARACTERS[turn % len(CHARACTERS)]] if any(words[n].song for n in names) else []) \
                + list(context or [])
            styles = tempo + ["instrumental"] + recipe["base"] + moment + profile.colours + profile.mood + spec.styles
            avoid = recipe["never"] + [word for word in spec.avoid if word not in recipe["never"]]
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
        parts.append(Part(name, count, clock, clock + length, song="a" if spec.song else None))
        clock += length
    return Request(plan={"chunks": chunks}, parts=parts, bpm=profile.bpm, tonic=profile.tonic, seed=seed)


def core_suite(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
               bars: dict[str, int] | None = None, part_bars: int = 8,
               genre: str = DEFAULT_GENRE, context: list[str] | None = None) -> Request:
    """A zone's first music: a song and a battle piece."""
    return build(profile, CORE_SUITE, seed=seed, rock=rock, bars=bars, part_bars=part_bars, genre=genre,
                 context=context)


def second_set(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
               reference: Reference | None = None, part_bars: int = 8,
               genre: str = DEFAULT_GENRE, context: list[str] | None = None) -> Request:
    """Added soon after: a second song, another battle piece and a calm piece. Its words go one
    step down the lists of feels from the first song's."""
    return build(profile, SECOND_SET, seed=seed, rock=rock, reference=reference, part_bars=part_bars,
                 turn=1, genre=genre, context=context)


def fresh_set(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
              reference: Reference | None = None, part_bars: int = 8, turn: int = 0,
              genre: str = DEFAULT_GENRE, context: list[str] | None = None) -> Request:
    """Added while the player stays: another song, another battle piece, and one more piece the
    game calls for (a hard piece, a boss piece, one for caves, one for night, in turn). `turn`
    is how many fresh sets the place already has; each goes further down the lists of feels."""
    names = SONG + ("Fight", EXTRAS[turn % len(EXTRAS)])
    return build(profile, names, seed=seed, rock=rock, reference=reference, part_bars=part_bars,
                 turn=turn + 2, genre=genre, context=context)


def place_piece(profile: ZoneProfile, seed: int | None = None, rock: float = 0.5,
                reference: Reference | None = None, genre: str = DEFAULT_GENRE) -> Request:
    """A short piece for one named place inside a zone: sixteen bars, quick to make. `profile`
    carries the zone's tempo and key and the place's own colours (atlas.place_profile)."""
    return build(profile, PLACE_PIECE, seed=seed, rock=rock, reference=reference, genre=genre)
