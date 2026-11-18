"""From what the game is doing to what should be heard.

The director is told the game state and the time, and answers with a Target: what kind of
moment it is (and so what kind of music should be playing), how loud the drums, the bass and the
rest of the band are, and the tone (muffled, echoing, thin). It holds the little bits of memory
the rules need: how long a fight has lasted, when it ended, how long the player has been indoors.

Two things move at different speeds. The channels' levels and the tone change at once and can be
undone at once, so they follow the game directly. The kind of music changes on a bar line and stays
a while, so it waits until the game has stayed the same for a moment.

Only state the game leaves unsealed is used. Health and threat are not available and are not
needed: intensity comes from combat, what is targeted, boss encounters, where the player is, and
the weather (a rain storm brings the whole band in).

The music follows what the player does, not only where they are. Moving brings the drums in and
standing still takes them out; fights close together keep the band in between them; a level
gained or a quest handed in gets the whole band for a moment. And no one piece is heard over and
over: at night, in a cave, in a city and in a storm the pieces made for that take turns with the
walking music of the place instead of replacing it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .state import GameState

# The kinds of moment, most urgent first: what a written piece's role is one of.
PLACES = ("boss", "battle", "battleground", "town", "depths", "storm", "camp", "night", "ember", "wander")

OPEN_HZ = 20000.0     # a low-pass up here does nothing
FLOOR_HZ = 20.0       # a high-pass down here does nothing
NIGHT_LEAN = 0.12     # at night, a walking piece counts this much (in tenths of a kind of moment) against it
NIGHT_TOP = 3800.0    # Hz: the top of the music at night
NIGHT_GAIN = 0.89     # about 1 dB softer at night
NIGHT_HUSH = 0.75     # and the drums' and the bass's least kept at three quarters


@dataclass(frozen=True)
class Target:
    """What the player should be doing right now."""
    place: str = "wander"
    # Other kinds of music that take turns with `place` for as long as it lasts, so that no one piece
    # is heard over and over: the walking music in a cave, the night pieces at night.
    also: tuple[str, ...] = ()
    # Whether `place` is named for where the player stands (a cave, an inn) and not for what is
    # going on (the calm after a fight): the forever song goes there within a few bars, and comes
    # back when the player leaves ("make sure our location changes CHANGE SONGS", 2026-11-16).
    sited: bool = False
    # How much a piece for one of the `also` kinds counts against it beside one written for `place` itself: 0 is not
    # at all (they take turns), and at night a little, so that night music comes first and the walking music still
    # comes when the night's has been heard lately ("night should feel like night", 2026-11-16).
    lean: float = 0.0
    # How much of the least the drums and the bass are played at (a piece's floor) is kept: 1 all of it, at night less.
    hush: float = 1.0
    bed: float = 1.0                  # channel levels, 0 to 1
    drums: float = 0.0
    bass: float = 0.0
    bed_highpass_hz: float = 110.0    # keeps the bass register clear of the bed while the bass is out
    lowpass_hz: float = OPEN_HZ
    highpass_hz: float = FLOOR_HZ
    reverb: float = 0.0               # 0 to 0.6
    volume: float = 1.0               # 0 to 1, on top of the player's own volume control
    silent: bool = False              # fade right out (a cinematic, or FreeRock switched off in game)
    fade_s: float = 0.4               # how long the levels and tone take to get there
    intensity: float = 0.0            # 0 to 1, for the log and the music's status
    why: tuple[str, ...] = ()         # the rules in force, for the log
    # A fight is on (or has just ended and the band is still in it): the player drives the song that is playing on to its
    # own rise and moment, the same song further on ("fights shouldnt start new songs", "need to do a better job
    # dynamically to match the mood in general", 2026-11-17).
    fight: bool = False
    # The storm is the weather's (it has set in), not a long ride at full tilt: only the weather's changes the song
    # ("abrupt storms should change the song", 2026-11-17; a ride is no change of place).
    rain_storm: bool = False

    def as_dict(self) -> dict:
        return {name: (list(value) if isinstance(value, tuple) else value)
                for name, value in self.__dict__.items()}


@dataclass
class Rules:
    """The numbers behind the rules, in one place so they can be tuned after real evenings.

    One number, the intensity, says how much is going on. It picks the kind of music and how much
    of the band plays, so the music climbs and comes down:

        idle        the calm music joins the round, the band thinned
        still       the tune and its chords, the drums and bass out
        on foot     the drums come in; keep going and the bass joins and the band fills out
        riding      drums and bass at once; a long ride brings in the storm's heavy music
        in sights   something to fight is targeted: the bass leans in
        a fight     the whole band, in the song that is playing: no other piece comes in for it
        a boss      a dungeon's boss has music of its own: the heaviest there is
    """
    # The rungs, as intensity from 0 to 1.
    idle: float = 0.10
    still: float = 0.25
    on_foot: float = 0.40
    on_foot_build: float = 0.17       # keeping going adds up to this much...
    on_foot_build_s: float = 20.0     # ...over this long
    riding: float = 0.60
    riding_build: float = 0.15
    riding_build_s: float = 25.0
    sizing: float = 0.57              # something to fight is targeted
    big_game: float = 0.68            # an elite, a rare or a boss in your sights
    combat_start: float = 0.80
    # A fight builds as it goes on, slowly: it is more enemies joining that makes it jump.
    combat_rise_per_s: float = 0.006
    combat_ceiling: float = 0.90
    # How many enemies are in the fight, when the addon says (it counts the nameplates on screen
    # of enemies that are fighting): the intensity the fight is held at for two of them, three,
    # four, and five or more. One enemy is an ordinary fight.
    crowd: tuple[float, ...] = (0.85, 0.90, 0.93, 0.96)
    # Out of a fight, with this many enemies in view or more, the music does not sit right
    # back: it is held at `company` plus `company_step` for each of them, up to the ceiling.
    company_from: int = 3
    company: float = 0.44
    company_step: float = 0.03
    company_ceiling: float = 0.62
    elite_floor: float = 0.92         # (a boss is 1.0)
    base_world: float = 0.25          # with no word on movement at all, as if standing
    base_dungeon: float = 0.40        # a dungeon is tenser than the open world
    inn_ceiling: float = 0.30         # inside an inn nothing but a fight rises above this
    # Where the channels and the heavy music come in on the way up, and go on the way down.
    # (2026-11-16, twice. In the afternoon: "theres not much difference between quet and full, we want more ...
    # drasticness", and a calm game was given no drums and a third of the bass, a fight bringing them in whole. Played
    # that evening: "the abruptness between fighting and not, its way too much now, it should only be a subtle
    # difference like before". So these are as they were before: twenty seconds on foot bring the drums to about
    # 73% and the bass to 72%, and a fight adds the last quarter.)
    drums_on: float = 0.33
    drums_least: float = 0.45         # how much of the drums there is the moment they come in
    bass_on: float = 0.55
    bass_off: float = 0.47
    bass_least: float = 0.7
    charge_at: float = 0.70           # out of a fight, this much going on brings in the heavy music
    charge_off: float = 0.62
    decay_per_s: float = 0.12         # how fast the intensity comes down when things calm
    hold_after_combat_s: float = 3.0
    afterglow_s: float = 8.0          # Ember after a boss's fight...
    afterglow_fight_s: float = 10.0   # ...that lasted at least this long; a short one goes straight back
    depths_after_s: float = 1.0
    depths_release_s: float = 2.0
    rain_drums_at: float = 0.3        # rain this strong brings the drums in
    storm_at: float = 0.6             # rain this strong is a rain storm: the whole band comes in
    storm_after_s: float = 4.0        # a storm that lasts this long brings in the storm's music
    storm_release_at: float = 0.4
    storm_release_s: float = 20.0
    storm_floor: float = 0.6          # intensity at the edge of a storm...
    storm_ceiling: float = 0.8        # ...and in the thick of one
    mounted_after_s: float = 1.0
    # Movement: the music follows your feet.
    moving_after_s: float = 0.2       # on the move this long before it counts
    still_after_s: float = 1.5        # stopped this long before it counts
    linger_after_s: float = 15.0      # stopped this long and the calm music joins the round
    camp_after_s: float = 45.0        # stood this long out of doors and it is a camp: waiting on a spawn, a rare, a friend
    # Standing still quiets the music ("and standing still should quiet the tracks", 2026-11-16): every channel at
    # this much of its level on stopping, and at this much once stood a while. Moving brings it straight back.
    still_bed: float = 0.85           # about 1.4 dB down
    linger_bed: float = 0.65          # about 3.7 dB down
    # ...and darker, as a band playing softly loses its edge, so that a held pad or drone left nearly alone in a quiet
    # stretch does not whine over the rest ("sometimes when one synth stays in when youre sitting its whiny and annoying
    # mix better", 2026-11-17, played: a bagpipe and organ drone in a band's quiet middle, between pulls). The top comes
    # down slowly (`sit_fade_s`) and opens again the moment the player moves or a fight starts.
    still_top: float = 6500.0         # Hz: the top of the music on stopping...
    linger_top: float = 3400.0        # ...and once stood (or sat) a while
    sit_fade_s: float = 3.0
    sizing_after_s: float = 0.2
    # A roll: fights close together keep the band in between them.
    heat_per_fight: float = 0.34      # what each fight adds, out of 1
    heat_half_life_s: float = 40.0    # how fast it cools between fights
    roll_hold_s: float = 10.0         # on a full roll the band stays this much longer after a fight
    roll_lift: float = 0.32           # ...the intensity between fights is this much higher
    roll_start: float = 0.08          # ...and the next fight starts this much hotter
    # Moments: what the whole band answers with, as (intensity, seconds).
    moments: dict = field(default_factory=lambda: {
        "level_up": (1.0, 10.0), "quest_turned_in": (0.7, 5.0), "boss_defeated": (0.9, 10.0),
        "achievement": (0.8, 6.0)})
    stealth_bass: bool = True         # stealth drops the band to the bass line and quiet drums


@dataclass
class _Memory:
    intensity: float = 0.0
    bass_in: bool = False
    charging: bool = False
    last_time: float | None = None
    combat_since: float | None = None
    combat_ended: float | None = None
    reached_battle: bool = False
    afterglow_until: float = 0.0
    indoors_since: float | None = None
    outdoors_since: float | None = None
    in_depths: bool = False
    stormy_since: float | None = None
    calm_weather_since: float | None = None
    in_storm: bool = False
    mounted_since: float | None = None
    position: tuple | None = None        # (map, x, y) at the last look
    moved_at: float | None = None        # when the position last changed
    moving_since: float | None = None
    still_since: float | None = None
    on_the_move: bool = False
    heat: float = 0.0                    # how many fights there have been lately, 0 to 1
    swell_until: float = 0.0             # a moment is being answered until then...
    swell_level: float = 0.0             # ...at this intensity...
    swell_name: str = ""                 # ...because of this
    sizing_since: float | None = None    # since when something to fight has been targeted


def _weather_strength(state: GameState) -> float:
    """The game's weather intensity as 0 to 1. Its real range is not documented; until it has
    been seen in the game it is taken as 0 to 1 and held inside that."""
    if state.weather in (None, "clear") or state.weather_intensity is None:
        return 0.0
    return min(max(float(state.weather_intensity), 0.0), 1.0)


def _share(value: float, low: float, high: float) -> float:
    """How far `value` has got from `low` to `high`, 0 to 1."""
    return min(max((value - low) / max(high - low, 1e-9), 0.0), 1.0)


def _step(level: float) -> float:
    """A channel's level in twentieths, so the player is not sent a new target for every hair."""
    return round(level * 20.0) / 20.0


class Director:
    def __init__(self, rules: Rules | None = None):
        self.rules = rules or Rules()
        self._m = _Memory()

    def moment(self, name: str, now: float) -> bool:
        """Something happened in the game that the band answers at once: a level gained, a quest
        handed in, a boss beaten. Returns whether this is a moment the rules know."""
        if name not in self.rules.moments:
            return False
        level, seconds = self.rules.moments[name]
        m = self._m
        if now >= m.swell_until:
            m.swell_until, m.swell_level, m.swell_name = now + seconds, level, name
        elif level >= m.swell_level:
            # As big or bigger than the one being answered: it takes over, for as long as the longer of the two.
            m.swell_until, m.swell_level, m.swell_name = max(m.swell_until, now + seconds), level, name
        # A smaller one while a bigger one is being answered is in it already (a quest handed in seconds after a level
        # gained once dropped the whole band from 1.0 to 0.7).
        return True

    def _movement(self, state: GameState, now: float) -> tuple[bool | None, bool, bool, float]:
        """Whether the player is on the move (None when there is no telling: an older addon in
        a dungeon, where the game gives no position), whether they have stood still for a good
        while, whether long enough out of the saddle of a flight path to be camping, and for how
        long they have been going."""
        rules, m = self.rules, self._m
        if state.speed is not None:
            # The addon says how fast the player is going. That works in dungeons too.
            m.position = None
            moving = state.speed > 0.5 and not state.on_taxi and not state.loading
        elif state.position is None:
            m.position = m.moved_at = m.moving_since = m.still_since = None
            m.on_the_move = False
            return None, False, False, 0.0
        else:
            here = (state.map_id, state.position[0], state.position[1])
            before, m.position = m.position, here
            if before is not None and before[0] == here[0] and not state.on_taxi and not state.loading:
                # One step of the strip's position is about a twentieth of a yard; anything is a move.
                if abs(here[1] - before[1]) + abs(here[2] - before[2]) > 1e-5:
                    m.moved_at = now
            moving = m.moved_at is not None and now - m.moved_at <= 0.6 and not state.on_taxi
        if moving:
            m.still_since = None
            m.moving_since = m.moving_since if m.moving_since is not None else now
            if now - m.moving_since >= rules.moving_after_s:
                m.on_the_move = True
        else:
            m.still_since = m.still_since if m.still_since is not None else now
            if now - m.still_since >= rules.still_after_s:
                m.on_the_move = False
                m.moving_since = None        # a real stop: the next run builds from the beginning
        # A flight path is a journey, not a wait: nothing on one is lingering or camping.
        lingering = not moving and not state.on_taxi and now - m.still_since >= rules.linger_after_s
        camping = not moving and not state.on_taxi and now - m.still_since >= rules.camp_after_s
        going = now - m.moving_since if m.on_the_move and m.moving_since is not None else 0.0
        return m.on_the_move, lingering, camping, going

    def update(self, state: GameState, now: float) -> Target:
        """Call whenever the state changes, and a few times a second in between."""
        rules, m = self.rules, self._m
        elapsed = 0.0 if m.last_time is None else max(now - m.last_time, 0.0)
        m.last_time = now
        why: list[str] = []

        if not state.enabled:
            return Target(silent=True, fade_s=1.0, why=("FreeRock is switched off in the game",))
        if state.cinematic:
            return Target(silent=True, fade_s=0.3, why=("cinematic",))

        # A dungeon's boss (the game says when its encounter begins and ends) is the one fight that has music of its
        # own. Every other fight, an elite's and a world boss's too, is answered by the song that is playing, with its
        # drums and bass brought up ("in normal fights dont play a separate battle piece dungeon bosses ONLY",
        # 2026-11-16: a piece of its own for every pull was a different song every half minute, cut in on the beat).
        boss = state.encounter
        elite = state.in_combat and state.target_class in ("elite", "rare", "rareelite", "worldboss")
        dungeon = state.in_instance and state.instance_kind in ("party", "raid", "scenario")
        fallen = state.dead or state.ghost
        inn = state.resting and state.indoors      # a city's streets are not an inn
        # A town or a city: resting out of doors, in its streets ("whenever in an alliance base should be a family of
        # songs", 2026-11-16); and a battleground or an arena ("or in a battleground, a family").
        town = state.resting and not state.indoors
        battleground = state.in_instance and state.instance_kind in ("battleground", "arena")
        on_the_move, lingering, camping, going = self._movement(state, now)

        # A roll is how far beyond one fight the heat has got: nothing after a single fight, full
        # after three close together.
        def roll() -> float:
            return min(max(m.heat - rules.heat_per_fight, 0.0) / max(1.0 - rules.heat_per_fight, 1e-9), 1.0)

        # --- the floor: how much is going on with no fight at all ---------------------------------
        if state.mounted and not state.on_taxi:
            m.mounted_since = m.mounted_since if m.mounted_since is not None else now
        else:
            m.mounted_since = None
        mounted = m.mounted_since is not None
        if on_the_move is None:
            # No word on movement at all (an older addon in a dungeon): a steady level, and a
            # mount counts as riding once it has been sat on for a moment.
            floor = rules.base_dungeon if dungeon else rules.base_world
            if mounted and now - m.mounted_since >= rules.mounted_after_s:
                floor = rules.riding
                why.append("mounted")
        elif on_the_move and mounted:
            floor = rules.riding + rules.riding_build * min(going / rules.riding_build_s, 1.0)
            why.append("riding")
        elif on_the_move:
            build = min(going / rules.on_foot_build_s, 1.0)
            floor = rules.on_foot + rules.on_foot_build * build
            why.append("on the move" if build < 0.9 else "on the move for a while: the band has filled out")
        elif state.on_taxi:
            floor = rules.still            # carried along: calm, and not quieter as the time goes ("flight path" says why)
        elif lingering:
            floor = rules.idle
            why.append("standing still for a while")
        else:
            floor = rules.still
            why.append("standing still")
        # A dungeon is tenser. What full tilt is judged by (`pace`) leaves that out: it is for what the player is doing,
        # and the tension alone once took seventeen seconds of walking in a dungeon to the heavy music.
        pace = floor
        if dungeon and on_the_move is not None:
            floor += rules.base_dungeon - rules.base_world
        # Something to fight is targeted and the fight has not started: the music leans in.
        sizing_up = (state.has_target and state.target_hostile is True and not state.in_combat
                     and not fallen and not state.resting and not state.on_taxi)
        if sizing_up:
            m.sizing_since = m.sizing_since if m.sizing_since is not None else now
            if now - m.sizing_since >= rules.sizing_after_s:
                big = state.target_class in ("elite", "rare", "rareelite", "worldboss")
                floor, pace = max(floor, rules.big_game if big else rules.sizing), max(pace, rules.big_game if big else rules.sizing)
                why.append("something big in your sights" if big else "a target in your sights")
        else:
            m.sizing_since = None
        # Enemies in view, none of them fought yet: not the moment to sit right back.
        company = state.enemies or 0
        if (company >= rules.company_from and not state.in_combat and not fallen and not state.resting
                and not state.on_taxi):
            held_up = min(rules.company + rules.company_step * company, rules.company_ceiling)
            floor, pace = max(floor, held_up), max(pace, held_up)
            why.append("enemies close by")
        if inn:
            floor, pace = min(floor, rules.inn_ceiling), min(pace, rules.inn_ceiling)

        # --- intensity ---------------------------------------------------------------------------
        if state.in_combat and not fallen:
            if m.combat_since is None:
                m.heat = min(m.heat + rules.heat_per_fight, 1.0)
                m.combat_since, m.combat_ended, m.reached_battle = now, None, False
                m.intensity = max(m.intensity, rules.combat_start + rules.roll_start * roll())
            else:
                m.intensity = min(max(m.intensity, rules.combat_start) + rules.combat_rise_per_s * elapsed,
                                  max(rules.combat_ceiling, m.intensity))
            # More than one enemy in the fight: it jumps, the more of them the higher.
            crowd = state.fighting or 0
            if crowd >= 2:
                m.intensity = max(m.intensity, rules.crowd[min(crowd - 2, len(rules.crowd) - 1)])
                why.append("%s enemies in the fight" % ("14 or more" if crowd >= 14 else crowd))
            if elite:
                m.intensity = max(m.intensity, rules.elite_floor)
            if boss or state.target_class == "worldboss":
                m.intensity = 1.0
        else:
            m.heat *= 0.5 ** (elapsed / rules.heat_half_life_s)
            hold = rules.hold_after_combat_s + rules.roll_hold_s * roll()
            if m.combat_since is not None:
                fought = now - m.combat_since
                m.combat_since, m.combat_ended = None, now
                if m.reached_battle and fought >= rules.afterglow_fight_s:
                    m.afterglow_until = now + hold + rules.afterglow_s
            held = m.combat_ended is not None and now - m.combat_ended < hold
            if fallen:
                m.intensity, m.combat_ended, m.afterglow_until, m.heat = 0.0, None, 0.0, 0.0
            elif not held:
                m.intensity = max(m.intensity - rules.decay_per_s * elapsed, floor + rules.roll_lift * roll())
            else:
                why.append("holding after the fight")
            if roll() >= 0.5 and not fallen:
                why.append("on a roll: fights close together")
        hold = rules.hold_after_combat_s + rules.roll_hold_s * roll()
        # Going up is at once: the music answers what the player does. Coming down takes a moment.
        if not fallen:
            m.intensity = max(m.intensity, floor)
        # A moment in the game (a level, a quest handed in) gets the whole band for a few seconds.
        swelling = now < m.swell_until and not fallen
        if swelling:
            m.intensity = max(m.intensity, m.swell_level)
            why.append({"level_up": "a level gained", "quest_turned_in": "a quest handed in",
                        "boss_defeated": "the boss is down", "achievement": "an achievement"}.get(m.swell_name, m.swell_name))
        # A rain storm rocks: out in heavy rain the whole band comes in, harder the heavier it is.
        strength = _weather_strength(state)
        storming = (state.weather == "rain" and strength >= rules.storm_at and not state.indoors
                    and not inn and not fallen)
        if storming:
            depth = (strength - rules.storm_at) / max(1.0 - rules.storm_at, 1e-9)
            m.intensity = max(m.intensity, rules.storm_floor + (rules.storm_ceiling - rules.storm_floor) * depth)
        intensity = m.intensity

        # --- layers: how much of the band plays at this intensity --------------------------------
        if intensity >= rules.bass_on:
            m.bass_in = True
        elif intensity < rules.bass_off:
            m.bass_in = False
        bass = rules.bass_least + (1.0 - rules.bass_least) * _share(intensity, rules.bass_on, rules.combat_start) if m.bass_in else 0.0
        drums = rules.drums_least + (1.0 - rules.drums_least) * _share(intensity, rules.drums_on, rules.combat_start) \
            if intensity >= rules.drums_on else 0.0
        bed = 1.0
        # Standing still: quieter, a little at once and more after a while, every channel (the player brings them down
        # over its slow fades, and back up the moment the player moves). Not in a fight, nor in a storm, nor in an inn,
        # which is quiet already.
        if not state.in_combat and m.combat_since is None and not fallen and not storming and not inn and not state.on_taxi:
            if lingering:
                bed *= rules.linger_bed
                why.append("stood a while: quieter")
            elif on_the_move is False:
                bed *= rules.still_bed
                why.append("standing still: a little quieter")

        # --- which music ---------------------------------------------------------------------
        if boss and m.combat_since is not None:
            m.reached_battle = True

        # A dungeon is indoors from end to end; its own music is made for that. The cave rules
        # are for stepping into a mine or a building out in the world.
        cave = state.indoors and not dungeon
        if cave and not state.resting:
            m.outdoors_since = None
            m.indoors_since = m.indoors_since if m.indoors_since is not None else now
            if now - m.indoors_since >= rules.depths_after_s:
                m.in_depths = True
        else:
            m.indoors_since = None
            m.outdoors_since = m.outdoors_since if m.outdoors_since is not None else now
            if now - m.outdoors_since >= rules.depths_release_s:
                m.in_depths = False

        # A storm sets in after rain this heavy for a few seconds, and ends after it has been light (or snow, or dry) for
        # twenty seconds together: rain between the two keeps it, and starts that count again.
        rain = strength if state.weather == "rain" else 0.0
        if rain >= rules.storm_at:
            m.calm_weather_since = None
            m.stormy_since = m.stormy_since if m.stormy_since is not None else now
            if now - m.stormy_since >= rules.storm_after_s:
                m.in_storm = True
        else:
            m.stormy_since = None
            if rain < rules.storm_release_at:
                m.calm_weather_since = m.calm_weather_since if m.calm_weather_since is not None else now
                if now - m.calm_weather_since >= rules.storm_release_s:
                    m.in_storm = False
            else:
                m.calm_weather_since = None

        # Out of a fight, with this much going on (a long ride, a roll between pulls), the music
        # moves up to the heavy music. It is what is going on now that counts, not the
        # intensity still coming down from a fight that is over.
        drive = pace + rules.roll_lift * roll()
        if m.combat_since is None and not fallen and not inn and drive >= rules.charge_at:
            m.charging = True
        elif drive < rules.charge_off or fallen or inn:
            m.charging = False

        # `place` is where the music goes now; `also` is what takes turns with it for as long as
        # it lasts, so that no one piece is heard over and over.
        also, sited, lean, rain_storm = [], False, 0.0, False
        if boss and not fallen:
            place = "boss"
            also.append("battle")
            why.append("boss")
        elif m.combat_since is not None and m.reached_battle:
            # The boss's encounter is over and the fight is not (what it called in is still up): the pieces
            # written for a fight go on, and the heaviest with them.
            place = "battle"
            also += ["storm", "boss"]
            why.append("a fight")
        elif battleground:
            # A battleground's own music, through its fights and its deaths alike: one dies often there, and the
            # music of the dead every time would be a different song every minute.
            place, sited = "battleground", True
            also.append("wander")
            why.append("a battleground")
        elif fallen:
            place = "ember"
            also.append("wander")
        elif now < m.afterglow_until and m.combat_ended is not None and now - m.combat_ended >= hold:
            place = "ember"
            why.append("after the fight")
        elif m.combat_ended is not None and m.reached_battle and now - m.combat_ended < hold:
            place = "battle"       # just after a boss: its music is not left at once
            also.append("storm")
        elif m.in_depths:
            place, sited = "depths", True
            also.append("wander")
            why.append("indoors for a while")
        elif inn:
            place, sited = "ember", True
            also.append("wander")
            why.append("resting")
        elif town:
            place, sited = "town", True
            also.append("wander")
            why.append("in a town")
        elif m.in_storm and not state.indoors:
            place, rain_storm = "storm", True
            also.append("wander")
            why.append("a storm that has set in")
        elif m.charging:
            place = "storm"
            also.append("wander")
            why.append("at full tilt")
        elif camping and not dungeon and not state.indoors and not state.in_combat and m.combat_since is None:
            # Camping ("camping should get its own tunes", 2026-11-17): stood a long while out of doors, waiting on a
            # spawn, a rare or a friend, with no fight (the spawn has come) and no storm. A place of its own, followed into at once; the
            # walking music and an inn's calm take turns with it, and the night's at night.
            place, sited = "camp", True
            also += ["wander", "ember"]
            if state.daytime is False:
                also.append("night")
            why.append("camping")
        elif state.daytime is False and not dungeon:
            # Night out of doors is a place of its own: its music first, the walking music when that has been heard.
            place, lean = "night", NIGHT_LEAN
            also.append("wander")
            why.append("night")
            if lingering:
                also.append("ember")
        else:
            place = "wander"
            if dungeon:
                also.append("depths")      # (and no night: the sky cannot be seen in there)
            if lingering:
                also.append("ember")
        if m.combat_since is not None and not m.reached_battle:
            why.append("a fight has started")

        # --- tone: the lowest low-pass, the highest high-pass and the largest reverb win -----
        # The cut-offs are low because of what the music is: guitars and lute have little above
        # 6 kHz, and a rendered session showed a 6 kHz cut changing nothing that could be measured.
        lowpass, highpass, reverb, volume, fade = OPEN_HZ, FLOOR_HZ, 0.0, 1.0, 0.4

        def tint(name: str, *, low: float = OPEN_HZ, high: float = FLOOR_HZ, wet: float = 0.0,
                 gain: float = 1.0) -> None:
            nonlocal lowpass, highpass, reverb, volume
            lowpass, highpass, reverb = min(lowpass, low), max(highpass, high), max(reverb, wet)
            volume *= gain
            why.append(name)

        if cave:
            tint("indoors: muffled and echoing", low=2500.0, wet=0.40)
        if state.submerged:
            tint("under water", low=500.0)
            fade = 0.15
        if state.weather == "rain" and strength > 0 and not state.indoors:
            # Rain is not muffled: it gets a little more space, then the drums, then (a storm)
            # the whole band, which the intensity above has already brought in.
            tint("a rain storm: the whole band" if storming else "rain", wet=0.08 + 0.12 * strength)
            if strength >= rules.rain_drums_at and not fallen and not inn:
                drums = max(drums, 0.6)
        elif state.weather == "snow" and strength > 0 and not state.indoors:
            tint("snow", low=6000.0, wet=0.20 + 0.25 * strength)
            drums *= 1.0 - 0.3 * strength
        elif state.weather == "sandstorm" and strength > 0 and not state.indoors:
            tint("sandstorm", low=3000.0 + 5000.0 * (1.0 - strength), high=300.0 * strength)
        # Sitting down between pulls, waiting on a spawn: softer and darker the longer it lasts (the levels came down above).
        # (Not with something to fight in sight, where the music leans in; under water and a loading screen move fast.)
        sitting = (not state.in_combat and m.combat_since is None and not fallen and not storming and not inn
                   and not state.on_taxi and not state.submerged and not state.loading and not sizing_up)
        if sitting:
            if lingering:
                tint("sat a while: darker", low=rules.linger_top)
                fade = max(fade, rules.sit_fade_s)
            elif on_the_move is False:
                tint("standing still: a little darker", low=rules.still_top)
                fade = max(fade, rules.sit_fade_s)
        hush = 1.0
        if state.daytime is False and not storming and not state.indoors and not dungeon:
            # Night out of doors: darker, further off and softer, the drums and the bass well back ("night should feel like
            # night"). Not in a cave, an inn or a dungeon, where the sky cannot be seen.
            tint("darker at night", low=NIGHT_TOP, wet=0.15, gain=NIGHT_GAIN)
            drums *= 0.7
            hush = NIGHT_HUSH
        if inn:
            tint("quieter in an inn", gain=0.63)   # about 4 dB down
            bass = 0.0
        if state.on_taxi:
            tint("flight path", high=150.0, wet=0.30)
            bass = 0.0
        if state.loading:
            tint("loading screen", low=800.0, gain=0.5)

        if state.stealthed and not state.in_combat and not fallen and rules.stealth_bass:
            bed, drums, bass = 0.0, 0.35, 0.7
            fade = 0.25
            why.append("stealth: the bass line alone")
        if fallen:
            bed, drums, bass = 1.0, 0.0, 0.0
            lowpass, reverb, volume = min(lowpass, 1200.0), max(reverb, 0.6), volume * 0.4
            why.append("dead")

        return Target(place=place, also=tuple(also), sited=sited, lean=lean, hush=hush,
                      bed=round(bed, 3), drums=_step(drums), bass=_step(bass),
                      bed_highpass_hz=FLOOR_HZ if bass > 0 else 110.0,
                      lowpass_hz=round(lowpass, 1), highpass_hz=round(highpass, 1),
                      reverb=round(min(reverb, 0.6), 3), volume=round(volume, 3), fade_s=fade,
                      intensity=round(intensity, 3), why=tuple(dict.fromkeys(why)),
                      fight=bool(state.in_combat and not fallen), rain_storm=rain_storm)
