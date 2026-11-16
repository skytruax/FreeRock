"""From what the game is doing to what should be heard.

The director is told the game state and the time, and answers with a Target: which kind of
section should be playing, how loud each of the three layers is, and the tone (muffled, echoing,
thin). It holds the little bits of memory the rules need: how long a fight has lasted, when it
ended, how long the player has been indoors.

Two things move at different speeds. Layer levels and tone change at once and can be undone at
once, so they follow the game directly. The section changes on a bar line and stays a while, so
it waits until the game has stayed the same for a moment.

Only state the game leaves unsealed is used. Health and threat are not available and are not
needed: intensity comes from combat, what is targeted, boss encounters, where the player is, and
the weather (a rain storm brings the whole band in).

The music follows what the player does, not only where they are. Moving brings the drums in and
standing still takes them out; fights close together keep the band in between them; a level
gained or a quest handed in gets the whole band for a moment; crossing into another part of the
zone changes the riff. And no single part is left to loop: at night, in a cave, in a city and in
a storm the part made for that joins the zone's other riffs instead of replacing them.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from .state import GameState

# Kinds of section, most urgent first. A zone's music may not have every kind; `FALLBACK` says
# what to play instead.
PLACES = ("boss", "battle", "depths", "storm", "night", "ember", "wander")
FALLBACK = {"boss": "battle", "battle": "wander", "storm": "wander", "night": "ember",
            "depths": "ember", "ember": "wander", "arrival": "wander"}

OPEN_HZ = 20000.0     # a low-pass up here does nothing
FLOOR_HZ = 20.0       # a high-pass down here does nothing


@dataclass(frozen=True)
class Target:
    """What the player should be doing right now."""
    place: str = "wander"
    # Other kinds of section that take turns with `place` for as long as it lasts, so that one
    # part is never left to loop: the zone's riffs in a cave, the Night part at night.
    also: tuple[str, ...] = ()
    scene: int = 0                    # goes up when the player crosses into another part of the zone
    cut: str = "bar"                  # how soon a change of place should land: bar | beat
    bed: float = 1.0                  # layer levels, 0 to 1
    drums: float = 0.0
    bass: float = 0.0
    bed_highpass_hz: float = 110.0    # keeps the bass register clear of the bed while the bass is out
    lowpass_hz: float = OPEN_HZ
    highpass_hz: float = FLOOR_HZ
    reverb: float = 0.0               # 0 to 0.6
    volume: float = 1.0               # 0 to 1, on top of the player's own volume control
    silent: bool = False              # fade right out (a cinematic, or FreeRock switched off in game)
    rest: bool = False                # a stretch without music, as the game has between pieces
    gap_s: float = 30.0               # about how long the silence after a song is
    fade_s: float = 0.4               # how long the levels and tone take to get there
    intensity: float = 0.0            # 0 to 1, for the log and the control page
    why: tuple[str, ...] = ()         # the rules in force, for the log

    def as_dict(self) -> dict:
        return {name: (list(value) if isinstance(value, tuple) else value)
                for name, value in self.__dict__.items()}


@dataclass
class Rules:
    """The numbers behind the rules, in one place so they can be tuned after real evenings.

    One number, the intensity, says how much is going on. It picks the kind of section and how
    much of the band plays, so the music climbs and comes down a ladder of loops:

        idle        the calm part joins the riffs, guitars alone
        still       a riff, guitars alone
        on foot     the drums come in; keep going and the bass joins and the band fills out
        riding      drums and bass at once; a long ride reaches the zone's hard-rock part
        in sights   something to fight is targeted: the bass leans in
        a fight     the Battle part with the whole band, on the next beat
        a boss      the heaviest part
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
    # Where the layers and the hard-rock part come in on the way up, and go on the way down.
    drums_on: float = 0.33
    bass_on: float = 0.55
    bass_off: float = 0.47
    charge_at: float = 0.70           # out of a fight, this much going on moves to the hard-rock part
    charge_off: float = 0.62
    decay_per_s: float = 0.12         # how fast the intensity comes down when things calm
    hold_after_combat_s: float = 3.0
    battle_after_s: float = 0.0       # how long into a fight the Battle section comes: at once
    battle_after_elite_s: float = 0.0
    afterglow_s: float = 8.0          # Ember after a fight that reached Battle...
    afterglow_fight_s: float = 10.0   # ...and lasted at least this long; a short one goes straight back
    depths_after_s: float = 1.0
    depths_release_s: float = 2.0
    rain_drums_at: float = 0.3        # rain this strong brings the drums in
    storm_at: float = 0.6             # rain this strong is a rain storm: the whole band comes in
    storm_after_s: float = 4.0        # a storm that lasts this long moves to the Storm section
    storm_release_at: float = 0.4
    storm_release_s: float = 20.0
    storm_floor: float = 0.6          # intensity at the edge of a storm...
    storm_ceiling: float = 0.8        # ...and in the thick of one
    mounted_after_s: float = 1.0
    # Movement: the music follows your feet.
    moving_after_s: float = 0.2       # on the move this long before it counts
    still_after_s: float = 1.5        # stopped this long before it counts
    linger_after_s: float = 15.0      # stopped this long and the calm part joins the rotation
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
    scene_every_s: float = 6.0        # crossing back and forth over a border changes the riff no oftener
    stealth_bass: bool = True         # stealth drops the band to the bass line and quiet drums
    # Rests: after about this much calm music the music stops for a while, as the game's own does
    # between pieces. Anything happening brings it straight back. rest_every_s of 0 means never.
    rest_every_s: float = 360.0
    rest_for_s: float = 60.0
    rest_spread: float = 0.4          # each is varied by up to this fraction either way
    calm_before_rest_s: float = 30.0  # arriving somewhere new, at least this much music before a rest
    rest_fade_s: float = 6.0          # how long the music takes to fade away into a rest
    rest_at_least_s: float = 15.0     # a rest lasts at least this long even if a fight starts in it


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
    elite_since: float | None = None
    place_key: tuple | None = None       # where the player was last seen, to notice a new place
    play_until: float | None = None      # when the music next takes a rest
    rest_until: float | None = None      # when the rest that is going on ends
    rest_since: float | None = None      # when it began
    position: tuple | None = None        # (map, x, y) at the last look
    moved_at: float | None = None        # when the position last changed
    moving_since: float | None = None
    still_since: float | None = None
    on_the_move: bool = False
    heat: float = 0.0                    # how many fights there have been lately, 0 to 1
    swell_until: float = 0.0             # a moment is being answered until then...
    swell_level: float = 0.0             # ...at this intensity...
    swell_name: str = ""                 # ...because of this
    subzone: str | None = None
    scene: int = 0
    scene_at: float | None = None        # when the riff last changed for a crossing
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
    """A layer level in twentieths, so the player is not sent a new target for every hair."""
    return round(level * 20.0) / 20.0


class Director:
    def __init__(self, rules: Rules | None = None, rng: random.Random | None = None):
        self.rules = rules or Rules()
        self.rng = rng or random.Random()
        self._m = _Memory()

    @property
    def heat(self) -> float:
        """How much fighting there has been lately, 0 to 1."""
        return self._m.heat

    def _about(self, seconds: float) -> float:
        """`seconds`, give or take the spread, so rests do not come round like clockwork."""
        return seconds * (1.0 + self.rules.rest_spread * (2.0 * self.rng.random() - 1.0))

    def moment(self, name: str, now: float) -> bool:
        """Something happened in the game that the band answers at once: a level gained, a quest
        handed in, a boss beaten. Returns whether this is a moment the rules know."""
        if name not in self.rules.moments:
            return False
        level, seconds = self.rules.moments[name]
        m = self._m
        if now + seconds >= m.swell_until or level > m.swell_level:
            m.swell_until, m.swell_level, m.swell_name = now + seconds, level, name
        return True

    def _movement(self, state: GameState, now: float) -> tuple[bool | None, bool, float]:
        """Whether the player is on the move (None when there is no telling: an older addon in
        a dungeon, where the game gives no position), whether they have stood still for a good
        while, and for how long they have been going."""
        rules, m = self.rules, self._m
        if state.speed is not None:
            # The addon says how fast the player is going. That works in dungeons too.
            m.position = None
            moving = state.speed > 0.5 and not state.on_taxi and not state.loading
        elif state.position is None:
            m.position = m.moved_at = m.moving_since = m.still_since = None
            m.on_the_move = False
            return None, False, 0.0
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
        lingering = not moving and now - m.still_since >= rules.linger_after_s
        going = now - m.moving_since if m.on_the_move and m.moving_since is not None else 0.0
        return m.on_the_move, lingering, going

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

        boss = state.encounter or (state.in_combat and state.target_class == "worldboss")
        elite = state.in_combat and state.target_class in ("elite", "rareelite", "worldboss")
        dungeon = state.in_instance and state.instance_kind in ("party", "raid", "scenario")
        fallen = state.dead or state.ghost
        inn = state.resting and state.indoors      # a city's streets are not an inn
        on_the_move, lingering, going = self._movement(state, now)

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
        elif lingering:
            floor = rules.idle
            why.append("standing still for a while")
        else:
            floor = rules.still
            why.append("standing still")
        if dungeon and on_the_move is not None:
            floor += rules.base_dungeon - rules.base_world
        # Something to fight is targeted and the fight has not started: the music leans in.
        sizing_up = (state.has_target and state.target_hostile is True and not state.in_combat
                     and not fallen and not state.resting and not state.on_taxi)
        if sizing_up:
            m.sizing_since = m.sizing_since if m.sizing_since is not None else now
            if now - m.sizing_since >= rules.sizing_after_s:
                big = state.target_class in ("elite", "rare", "rareelite", "worldboss")
                floor = max(floor, rules.big_game if big else rules.sizing)
                why.append("something big in your sights" if big else "a target in your sights")
        else:
            m.sizing_since = None
        # Enemies in view, none of them fought yet: not the moment to sit right back.
        company = state.enemies or 0
        if (company >= rules.company_from and not state.in_combat and not fallen and not state.resting
                and not state.on_taxi):
            floor = max(floor, min(rules.company + rules.company_step * company, rules.company_ceiling))
            why.append("enemies close by")
        if inn:
            floor = min(floor, rules.inn_ceiling)

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
                m.elite_since = m.elite_since if m.elite_since is not None else now
            else:
                m.elite_since = None
            if boss:
                m.intensity = 1.0
        else:
            m.heat *= 0.5 ** (elapsed / rules.heat_half_life_s)
            hold = rules.hold_after_combat_s + rules.roll_hold_s * roll()
            if m.combat_since is not None:
                fought = now - m.combat_since
                m.combat_since, m.combat_ended, m.elite_since = None, now, None
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
        bass = 0.7 + 0.3 * _share(intensity, rules.bass_on, rules.combat_start) if m.bass_in else 0.0
        drums = 0.45 + 0.55 * _share(intensity, rules.drums_on, rules.combat_start) \
            if intensity >= rules.drums_on else 0.0
        bed = 1.0

        # --- which section -------------------------------------------------------------------
        in_combat_long = m.combat_since is not None and now - m.combat_since >= rules.battle_after_s
        elite_long = m.elite_since is not None and now - m.elite_since >= rules.battle_after_elite_s
        if in_combat_long or elite_long:
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

        if state.weather == "rain" and strength >= rules.storm_at:
            m.calm_weather_since = None
            m.stormy_since = m.stormy_since if m.stormy_since is not None else now
            if now - m.stormy_since >= rules.storm_after_s:
                m.in_storm = True
        else:
            m.stormy_since = None
            if strength < rules.storm_release_at:
                m.calm_weather_since = m.calm_weather_since if m.calm_weather_since is not None else now
                if now - m.calm_weather_since >= rules.storm_release_s:
                    m.in_storm = False

        # Out of a fight, with this much going on (a long ride, a roll between pulls), the music
        # moves up to the zone's hard-rock part. It is what is going on now that counts, not the
        # intensity still coming down from a fight that is over.
        drive = floor + rules.roll_lift * roll()
        if m.combat_since is None and not fallen and not inn and drive >= rules.charge_at:
            m.charging = True
        elif drive < rules.charge_off or fallen or inn:
            m.charging = False

        # The subzone the player is in: crossing into another one changes the riff.
        if state.subzone_name and state.subzone_name != m.subzone:
            if m.subzone is not None and (m.scene_at is None or now - m.scene_at >= rules.scene_every_s):
                m.scene += 1
                m.scene_at = now
            m.subzone = state.subzone_name

        # `place` is where the music goes now; `also` is what takes turns with it for as long as
        # it lasts, so that one part is never left to loop.
        cut, also = "bar", []
        if boss and not fallen:
            place, cut = "boss", "beat"
            also.append("battle")
            why.append("boss")
        elif m.combat_since is not None and m.reached_battle:
            place, cut = "battle", "beat"
            # A fight takes turns through every hard piece the place has: its Battle parts, its
            # hard-rock part, and against something big the heaviest part as well.
            also.append("storm")
            if elite or dungeon:
                also.append("boss")
            why.append("a fight")
        elif fallen:
            place = "ember"
            also.append("wander")
        elif now < m.afterglow_until and m.combat_ended is not None and now - m.combat_ended >= hold:
            place = "ember"
            why.append("after the fight")
        elif m.combat_ended is not None and m.reached_battle and now - m.combat_ended < hold:
            place = "battle"       # the next pull may be coming; do not leave Battle yet
            also.append("storm")
        elif m.in_depths:
            place, cut = "depths", "beat"
            also.append("wander")
            why.append("indoors for a while")
        elif inn:
            place = "ember"
            also.append("wander")
            why.append("resting")
        elif m.in_storm and not state.indoors:
            place, cut = "storm", "beat"
            also.append("wander")
            why.append("a storm that has set in")
        elif m.charging:
            place = "storm"
            also.append("wander")
            why.append("at full tilt")
        else:
            place = "wander"
            if dungeon:
                also.append("depths")
            if state.daytime is False:
                also.append("night")
                why.append("night")
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
        elif state.weather == "snow" and strength > 0:
            tint("snow", low=6000.0, wet=0.20 + 0.25 * strength)
            drums *= 1.0 - 0.3 * strength
        elif state.weather == "sandstorm" and strength > 0:
            tint("sandstorm", low=3000.0 + 5000.0 * (1.0 - strength), high=300.0 * strength)
        if state.daytime is False and not storming:
            tint("darker at night", low=5000.0)
            drums *= 0.7
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

        # --- rests -------------------------------------------------------------------------------
        # The game's own music stops between pieces, and the quiet is part of how a zone feels.
        # After a stretch of calm music FreeRock rests too, and anything happening (a fight, a
        # storm, stealth, a new place) brings the music straight back.
        here = (state.in_instance, state.instance_id, state.map_id, state.zone_name)
        new_place = m.place_key is not None and here != m.place_key
        m.place_key = here
        # A rest waits for a lull: not in the middle of a fight or of the moment after one. It
        # does not wait for the player to stand still. Once it has begun, a fight, stealth, a
        # storm or a new place ends it; walking about does not.
        # The music plays as songs: after a while it fades out, stays out for a time, and fades
        # back in with something else. A rest begins in a lull (not in the middle of a fight) and
        # may take the place of the calm part after one. Once begun it is a real silence: a
        # fight, stealth or a storm brings the music back only after a quarter of a minute, so
        # the quiet is long enough to be heard. A boss, a moment or a new place ends it at once.
        held_now = m.combat_ended is not None and now - m.combat_ended < hold
        lull = (m.combat_since is None and not held_now and not fallen and not swelling
                and not state.loading)
        stirring = (m.combat_since is not None or storming
                    or (state.stealthed and rules.stealth_bass) or sizing_up)
        urgent = (boss and not fallen) or swelling or new_place
        rest = False
        if rules.rest_every_s > 0:
            if m.play_until is None:
                m.play_until = now + self._about(rules.rest_every_s)
            if m.rest_until is not None:
                long_enough = now - m.rest_since >= rules.rest_at_least_s
                if urgent or now >= m.rest_until or (stirring and long_enough):
                    m.rest_until = m.rest_since = None
                    m.play_until = now + self._about(rules.rest_every_s)
                else:
                    rest = True
            elif new_place:
                m.play_until = max(m.play_until, now + rules.calm_before_rest_s)
            elif now >= m.play_until and lull and not stirring:
                m.rest_until, m.rest_since = now + self._about(rules.rest_for_s), now
                rest = True
        if rest:
            fade = rules.rest_fade_s
            why.append("a rest, as the game has between pieces")

        return Target(place=place, also=tuple(also), scene=m.scene, cut=cut, gap_s=rules.rest_for_s,
                      bed=round(bed, 3), drums=_step(drums), bass=_step(bass),
                      bed_highpass_hz=FLOOR_HZ if bass > 0 else 110.0,
                      lowpass_hz=round(lowpass, 1), highpass_hz=round(highpass, 1),
                      reverb=round(min(reverb, 0.6), 3), volume=round(volume, 3), rest=rest, fade_s=fade,
                      intensity=round(intensity, 3), why=tuple(dict.fromkeys(why)))


def playable(place: str, roles: set[str]) -> str:
    """The kind of section to play for `place` given the kinds this zone's music actually has."""
    seen = set()
    while place not in roles:
        if place in seen or place not in FALLBACK:
            raise ValueError("Nothing to play for %r; the music has only %s" % (place, sorted(roles)))
        seen.add(place)
        place = FALLBACK[place]
    return place
