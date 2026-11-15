"""From what the game is doing to what should be heard.

The director is told the game state and the time, and answers with a Target: which kind of
section should be playing, how loud each of the three layers is, and the tone (muffled, echoing,
thin). It holds the little bits of memory the rules need: how long a fight has lasted, when it
ended, how long the player has been indoors.

Two things move at different speeds. Layer levels and tone change at once and can be undone at
once, so they follow the game directly. The section changes on a bar line and stays a while, so
it waits until the game has stayed the same for a moment.

Only state the game leaves unsealed is used. Health and threat are not available and are not
needed: intensity comes from combat, what is targeted, boss encounters and where the player is.
"""
from __future__ import annotations

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
    fade_s: float = 0.4               # how long the levels and tone take to get there
    intensity: float = 0.0            # 0 to 1, for the log and the control page
    why: tuple[str, ...] = ()         # the rules in force, for the log

    def as_dict(self) -> dict:
        return {name: (list(value) if isinstance(value, tuple) else value)
                for name, value in self.__dict__.items()}


@dataclass
class Rules:
    """The numbers behind the rules, in one place so they can be tuned after real evenings."""
    base_world: float = 0.25
    base_resting: float = 0.0
    base_dungeon: float = 0.35
    combat_start: float = 0.60
    combat_rise_per_s: float = 0.02
    combat_ceiling: float = 0.80
    elite_floor: float = 0.80
    hold_after_combat_s: float = 5.0
    decay_per_s: float = 0.08
    bass_on: float = 0.55
    bass_off: float = 0.40
    battle_at: float = 0.75
    battle_after_s: float = 6.0       # a fight this long moves to the Battle section...
    battle_after_elite_s: float = 2.0  # ...sooner against an elite
    afterglow_s: float = 8.0          # Ember after a fight that reached Battle
    depths_after_s: float = 2.5
    depths_release_s: float = 4.0
    storm_at: float = 0.6
    storm_after_s: float = 10.0
    storm_release_at: float = 0.4
    storm_release_s: float = 20.0
    mounted_after_s: float = 1.0
    calm_drums: float = 0.0           # drums while nothing is happening; 0 leaves the bed alone
    stealth_bass: bool = True         # stealth drops the band to the bass line and quiet drums


@dataclass
class _Memory:
    intensity: float = 0.0
    bass_in: bool = False
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


def _weather_strength(state: GameState) -> float:
    """The game's weather intensity as 0 to 1. Its real range is not documented; until it has
    been seen in the game it is taken as 0 to 1 and held inside that."""
    if state.weather in (None, "clear") or state.weather_intensity is None:
        return 0.0
    return min(max(float(state.weather_intensity), 0.0), 1.0)


class Director:
    def __init__(self, rules: Rules | None = None):
        self.rules = rules or Rules()
        self._m = _Memory()

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

        # --- intensity ---------------------------------------------------------------------------
        base = rules.base_resting if state.resting else rules.base_dungeon if dungeon else rules.base_world
        if state.in_combat and not fallen:
            if m.combat_since is None:
                m.combat_since, m.combat_ended, m.reached_battle = now, None, False
                m.intensity = max(m.intensity, rules.combat_start)
            else:
                m.intensity = min(max(m.intensity, rules.combat_start) + rules.combat_rise_per_s * elapsed,
                                  max(rules.combat_ceiling, m.intensity))
            if elite:
                m.intensity = max(m.intensity, rules.elite_floor)
                m.elite_since = m.elite_since if m.elite_since is not None else now
            else:
                m.elite_since = None
            if boss:
                m.intensity = 1.0
        else:
            if m.combat_since is not None:
                m.combat_since, m.combat_ended, m.elite_since = None, now, None
                if m.reached_battle:
                    m.afterglow_until = now + rules.hold_after_combat_s + rules.afterglow_s
            held = m.combat_ended is not None and now - m.combat_ended < rules.hold_after_combat_s
            if fallen:
                m.intensity, m.combat_ended, m.afterglow_until = 0.0, None, 0.0
            elif not held:
                m.intensity = max(m.intensity - rules.decay_per_s * elapsed, base)
            else:
                why.append("holding after the fight")
        if m.intensity < base and not fallen:
            m.intensity = min(m.intensity + rules.decay_per_s * elapsed, base)
        intensity = m.intensity

        # --- layers ------------------------------------------------------------------------------
        if intensity >= rules.bass_on:
            m.bass_in = True
        elif intensity < rules.bass_off:
            m.bass_in = False
        bass = 1.0 if m.bass_in else 0.0
        drums = 0.75 + 0.25 * min((intensity - rules.bass_off) / (1.0 - rules.bass_off), 1.0) if m.bass_in \
            else rules.calm_drums
        bed = 1.0

        # --- which section -------------------------------------------------------------------
        in_combat_long = (m.combat_since is not None and intensity >= rules.battle_at
                          and now - m.combat_since >= rules.battle_after_s)
        elite_long = m.elite_since is not None and now - m.elite_since >= rules.battle_after_elite_s
        if in_combat_long or elite_long:
            m.reached_battle = True

        if state.indoors and not state.resting:
            m.outdoors_since = None
            m.indoors_since = m.indoors_since if m.indoors_since is not None else now
            if now - m.indoors_since >= rules.depths_after_s:
                m.in_depths = True
        else:
            m.indoors_since = None
            m.outdoors_since = m.outdoors_since if m.outdoors_since is not None else now
            if now - m.outdoors_since >= rules.depths_release_s:
                m.in_depths = False

        strength = _weather_strength(state)
        if strength >= rules.storm_at:
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

        cut = "bar"
        if boss and not fallen:
            place, cut = "boss", "beat"
            why.append("boss")
        elif m.combat_since is not None and m.reached_battle:
            place = "battle"
            why.append("a fight that has lasted")
        elif fallen:
            place = "ember"
        elif now < m.afterglow_until and m.combat_ended is not None \
                and now - m.combat_ended >= rules.hold_after_combat_s:
            place = "ember"
            why.append("after the fight")
        elif m.combat_ended is not None and m.reached_battle \
                and now - m.combat_ended < rules.hold_after_combat_s:
            place = "battle"       # the next pull may be coming; do not leave Battle yet
        elif m.in_depths:
            place = "depths"
            why.append("indoors")
        elif state.resting:
            place = "ember"
            why.append("resting")
        elif m.in_storm and not state.indoors:
            place = "storm"
            why.append("heavy weather")
        elif state.daytime is False:
            place = "night"
            why.append("night")
        else:
            place = "wander"
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

        if state.indoors:
            tint("indoors: muffled and echoing", low=2500.0, wet=0.40)
        if state.submerged:
            tint("under water", low=500.0)
            fade = 0.15
        if state.weather == "rain" and strength > 0:
            tint("rain", low=8000.0 - 5000.0 * strength, wet=0.10 + 0.15 * strength)
        elif state.weather == "snow" and strength > 0:
            tint("snow", low=6000.0, wet=0.20 + 0.25 * strength)
            drums *= 1.0 - 0.3 * strength
        elif state.weather == "sandstorm" and strength > 0:
            tint("sandstorm", low=3000.0 + 5000.0 * (1.0 - strength), high=300.0 * strength)
        if state.daytime is False:
            tint("night", low=5000.0)
            drums *= 0.7
        if state.resting:
            tint("resting", gain=0.63)                # about 4 dB down
            bass = 0.0
        if state.on_taxi:
            tint("flight path", high=150.0, wet=0.30)
            bass = 0.0
        if state.loading:
            tint("loading screen", low=800.0, gain=0.5)

        if state.mounted and not state.on_taxi:
            m.mounted_since = m.mounted_since if m.mounted_since is not None else now
            if now - m.mounted_since >= rules.mounted_after_s and not fallen:
                drums = max(drums, 0.6)
                why.append("mounted")
        else:
            m.mounted_since = None

        if state.stealthed and not state.in_combat and not fallen and rules.stealth_bass:
            bed, drums, bass = 0.0, 0.35, 0.7
            fade = 0.25
            why.append("stealth: the bass line alone")
        if fallen:
            bed, drums, bass = 1.0, 0.0, 0.0
            lowpass, reverb, volume = min(lowpass, 1200.0), max(reverb, 0.6), volume * 0.4
            why.append("dead")

        return Target(place=place, cut=cut, bed=round(bed, 3), drums=round(drums, 3), bass=round(bass, 3),
                      bed_highpass_hz=FLOOR_HZ if bass > 0 else 110.0,
                      lowpass_hz=round(lowpass, 1), highpass_hz=round(highpass, 1),
                      reverb=round(min(reverb, 0.6), 3), volume=round(volume, 3), fade_s=fade,
                      intensity=round(intensity, 3), why=tuple(why))


def playable(place: str, roles: set[str]) -> str:
    """The kind of section to play for `place` given the kinds this zone's music actually has."""
    seen = set()
    while place not in roles:
        if place in seen or place not in FALLBACK:
            raise ValueError("Nothing to play for %r; the music has only %s" % (place, sorted(roles)))
        seen.add(place)
        place = FALLBACK[place]
    return place
