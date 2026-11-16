"""Frames into game state: names, commands, holding the last good state, and the hub."""
import asyncio
import dataclasses

import pytest

from freerock import beacon, state
from freerock.state import Link


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


BASE = beacon.Frame(flags=beacon.FLAG_ENABLED, map_id=1429)


def name_frames(field, text, revision=0, base=BASE):
    """The frames that carry one name, six bytes at a time."""
    data = beacon.truncate_utf8(text)
    for chunk in range(-(-len(data) // 6)):
        piece = data[chunk * 6:chunk * 6 + 6].ljust(6, b"\0")
        yield dataclasses.replace(base, text_field=field, text_revision=revision, text_chunk=chunk,
                                  text_length=len(data), text_bytes=piece)


def subzone(text, **changes):
    return dataclasses.replace(BASE, subzone_hash=beacon.text_hash(beacon.truncate_utf8(text)), **changes)


def test_first_frame_makes_the_state_and_the_link_live():
    tracker = state.StateTracker(clock=Clock())
    assert tracker.link == Link.NEVER and tracker.state is None
    events = tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED | beacon.FLAG_INDOORS))
    assert events[0] == state.LinkChanged(Link.LIVE, Link.NEVER)
    changed = events[1]
    assert isinstance(changed, state.StateChanged) and changed.previous is None
    assert changed.state.indoors and changed.state.map_id == 1429
    assert "indoors" in changed.changed and "map_id" in changed.changed


def test_only_real_changes_are_reported_and_they_name_the_fields():
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(BASE)
    assert tracker.feed(dataclasses.replace(BASE, beat=9)) == [], "the beat alone is not a change"
    events = tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED | beacon.FLAG_COMBAT, beat=10))
    assert len(events) == 1
    assert events[0].changed == frozenset({"in_combat"})
    assert events[0].previous.in_combat is False and events[0].state.in_combat is True


def test_names_are_put_together_in_any_order_and_dropped_when_the_revision_changes():
    tracker = state.StateTracker(clock=Clock())
    chunks = list(name_frames(beacon.TEXT_ZONE, "Elwynn Forest"))
    for frame in (chunks[2], chunks[0]):
        tracker.feed(frame)
        assert tracker.state.zone_name is None
    tracker.feed(chunks[1])
    assert tracker.state.zone_name == "Elwynn Forest"
    # A new name with a new revision: the old one goes at its first chunk.
    newer = list(name_frames(beacon.TEXT_ZONE, "Westfall", revision=1))
    tracker.feed(newer[0])
    assert tracker.state.zone_name is None
    tracker.feed(newer[1])
    assert tracker.state.zone_name == "Westfall"


def test_a_name_is_dropped_when_its_place_changes():
    tracker = state.StateTracker(clock=Clock())
    for frame in name_frames(beacon.TEXT_ZONE, "Elwynn Forest"):
        tracker.feed(frame)
    assert tracker.state.zone_name == "Elwynn Forest"
    tracker.feed(dataclasses.replace(BASE, map_id=1436))
    assert tracker.state.map_id == 1436 and tracker.state.zone_name is None


def test_the_subzone_name_must_match_the_mark_in_the_frame():
    tracker = state.StateTracker(clock=Clock())
    base = subzone("Goldshire")
    for frame in name_frames(beacon.TEXT_SUBZONE, "Goldshire", base=base):
        tracker.feed(frame)
    assert tracker.state.subzone_name == "Goldshire" and tracker.state.has_subzone
    # The mark changes before the new name arrives: the old name must not be shown for it.
    tracker.feed(subzone("Fargodeep Mine"))
    assert tracker.state.has_subzone and tracker.state.subzone_name is None
    # Chunks of some other name arriving under this mark are thrown away.
    for frame in name_frames(beacon.TEXT_SUBZONE, "Fargodeep Mill", revision=1, base=subzone("Fargodeep Mine")):
        tracker.feed(frame)
    assert tracker.state.subzone_name is None
    assert tracker.name_rejects == 1
    for frame in name_frames(beacon.TEXT_SUBZONE, "Fargodeep Mine", revision=2, base=subzone("Fargodeep Mine")):
        tracker.feed(frame)
    assert tracker.state.subzone_name == "Fargodeep Mine"
    # No subzone at all.
    tracker.feed(BASE)
    assert not tracker.state.has_subzone and tracker.state.subzone_name is None


def test_chunks_that_do_not_make_text_are_thrown_away_and_counted():
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(dataclasses.replace(BASE, text_field=beacon.TEXT_ZONE, text_chunk=0, text_length=4, text_bytes=b"\xff\xfe\xfd\xfc\0\0"))
    assert tracker.state.zone_name is None
    assert tracker.name_rejects == 1
    # A chunk number past the end of the name, and a name longer than the format allows.
    tracker.feed(dataclasses.replace(BASE, text_field=beacon.TEXT_ZONE, text_chunk=5, text_length=4, text_bytes=b"abcd\0\0"))
    tracker.feed(dataclasses.replace(BASE, text_field=beacon.TEXT_ZONE, text_chunk=0, text_length=200, text_bytes=b"abcdef"))
    assert tracker.name_rejects == 3
    assert tracker.state.zone_name is None


def test_commands_and_moments_fire_when_their_count_changes_and_not_at_the_start():
    tracker = state.StateTracker(clock=Clock())
    assert not [e for e in tracker.feed(dataclasses.replace(BASE, command=1, command_count=7, moment=1, moment_count=3))
                if isinstance(e, (state.CommandReceived, state.MomentReceived))]
    assert tracker.feed(dataclasses.replace(BASE, command=1, command_count=7, moment=1, moment_count=3)) == []
    events = tracker.feed(dataclasses.replace(BASE, command=2, command_count=8, moment=1, moment_count=3))
    assert events == [state.CommandReceived("love", 8)]
    events = tracker.feed(dataclasses.replace(BASE, command=2, command_count=8, moment=4, moment_count=4))
    assert events == [state.MomentReceived("died", 4)]
    # The same command twice in a row is two commands.
    events = tracker.feed(dataclasses.replace(BASE, command=2, command_count=9, moment=4, moment_count=4))
    assert events == [state.CommandReceived("love", 9)]
    # A code this version does not know moves the count on without an event.
    assert tracker.feed(dataclasses.replace(BASE, command=99, command_count=10, moment=4, moment_count=4)) == []


def test_the_last_good_state_is_held_while_the_strip_cannot_be_read():
    clock = Clock()
    tracker = state.StateTracker(clock=clock, stale_after=1.5, lost_after=30)
    tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED | beacon.FLAG_INDOORS))
    held = tracker.state
    clock.now += 1.0
    assert tracker.tick() == []
    clock.now += 1.0
    assert tracker.tick() == [state.LinkChanged(Link.STALE, Link.LIVE)]
    assert tracker.tick() == [], "said once"
    assert tracker.state is held, "the state is kept"
    clock.now += 40
    assert tracker.tick() == [state.LinkChanged(Link.LOST, Link.STALE)]
    assert tracker.state is held
    assert tracker.seconds_since_good() == pytest.approx(42.0)
    # It comes back.
    events = tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED | beacon.FLAG_INDOORS))
    assert events == [state.LinkChanged(Link.LIVE, Link.LOST)], "back, and nothing about the game changed"


def test_off_in_the_strip_is_off_and_stays_off_when_the_strip_goes():
    clock = Clock()
    tracker = state.StateTracker(clock=clock)
    tracker.feed(BASE)
    events = tracker.feed(dataclasses.replace(BASE, flags=0))
    assert state.LinkChanged(Link.OFF, Link.LIVE) in events
    assert tracker.state.enabled is False
    clock.now += 100
    assert tracker.tick() == [], "the game said off; silence afterwards is expected"
    assert tracker.link == Link.OFF
    assert state.LinkChanged(Link.LIVE, Link.OFF) in tracker.feed(BASE)


def test_test_frames_keep_the_link_live_and_leave_the_state_alone():
    clock = Clock()
    tracker = state.StateTracker(clock=clock)
    tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED | beacon.FLAG_COMBAT))
    held = tracker.state
    events = tracker.feed(beacon.Frame(kind=beacon.KIND_TEST))
    assert events == [state.TestPatternSeen()]
    clock.now += 0.05
    assert tracker.feed(beacon.Frame(kind=beacon.KIND_TEST)) == [], "one event for a burst"
    assert tracker.state is held
    clock.now += 5
    assert tracker.tick() == [state.LinkChanged(Link.STALE, Link.LIVE)]
    assert tracker.feed(beacon.Frame(kind=beacon.KIND_TEST)) == [
        state.TestPatternSeen(), state.LinkChanged(Link.LIVE, Link.STALE)], "a new burst, and the link is back"


def test_unknown_kinds_become_other_and_missing_values_none():
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(dataclasses.replace(BASE, instance_kind=9, target_class=12, pvp_kind=8, weather_kind=11,
                                     flags=beacon.FLAG_ENABLED | beacon.FLAG_WEATHER_KNOWN, weather_intensity=1500))
    game = tracker.state
    assert (game.instance_kind, game.target_class, game.pvp_kind, game.weather) == ("other",) * 4
    assert game.weather_intensity == 1.5
    tracker.feed(BASE)
    game = tracker.state
    assert game.weather is None and game.weather_intensity is None and game.daytime is None
    assert game.position is None and game.game_minutes is None


def test_state_as_dict_is_plain_data():
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED | beacon.FLAG_POSITION_KNOWN, x=32767, y=0))
    data = tracker.state.as_dict()
    assert data["position"] == [pytest.approx(0.5, abs=1e-4), 0.0]
    assert data["map_id"] == 1429 and data["enabled"] is True
    import json
    json.dumps(data)


async def test_the_hub_hands_every_event_to_every_listener_and_keeps_the_latest_state():
    hub = state.Hub()
    first, second = hub.subscribe(), hub.subscribe()
    tracker = state.StateTracker(clock=Clock())
    for event in tracker.feed(BASE):
        hub.publish(event)
    assert hub.state == tracker.state and hub.link == Link.LIVE
    for listener in (first, second):
        assert isinstance(await listener.get(), state.LinkChanged)
        assert isinstance(await listener.get(), state.StateChanged)
    second.close()
    hub.publish(state.CommandReceived("skip", 1))
    assert await first.get() == state.CommandReceived("skip", 1)
    assert second._queue.empty()


async def test_a_listener_that_falls_behind_is_told_instead_of_silently_missing_events():
    hub = state.Hub()
    slow = hub.subscribe(size=2)
    for count in range(5):
        hub.publish(state.CommandReceived("skip", count))
    assert await slow.get() == state.CommandReceived("skip", 0)
    assert await slow.get() == state.CommandReceived("skip", 1)
    with pytest.raises(state.Overrun):
        await slow.get()
    hub.publish(state.CommandReceived("ban", 9))
    assert await slow.get() == state.CommandReceived("ban", 9), "it carries on after being told"


async def test_a_listener_can_be_used_as_a_loop():
    hub = state.Hub()
    seen = []

    async def listen():
        with hub.subscribe() as events:
            async for event in events:
                seen.append(event)
                if len(seen) == 2:
                    break

    task = asyncio.create_task(listen())
    await asyncio.sleep(0)
    hub.publish(state.CommandReceived("skip", 1))
    hub.publish(state.CommandReceived("love", 2))
    await asyncio.wait_for(task, 1)
    assert [event.name for event in seen] == ["skip", "love"]
    assert not hub._subscriptions


def test_the_game_closing_is_not_held_through():
    """The strip out of sight is held for two minutes (the interface hidden for a screenshot);
    the game window gone is the end at once."""
    clock = Clock()
    tracker = state.StateTracker(clock=clock)
    assert tracker.lost_after == 120.0
    assert tracker.gone() == [], "nothing was ever read: nothing to end"
    tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED))
    clock.now += 60
    assert tracker.tick() == [state.LinkChanged(Link.STALE, Link.LIVE)]
    assert tracker.tick() == [], "a minute without the strip is still held"
    assert tracker.gone() == [state.LinkChanged(Link.LOST, Link.STALE)]
    assert tracker.gone() == []


def test_speed_and_a_target_that_can_be_fought_come_with_version_two():
    tracker = state.StateTracker(clock=Clock())
    said = dataclasses.replace(BASE, version=2, speed=14,
                               flags=beacon.FLAG_ENABLED | beacon.FLAG_HAS_TARGET | beacon.FLAG_TARGET_HOSTILE)
    tracker.feed(said)
    assert tracker.state.speed == 7.0 and tracker.state.target_hostile is True
    tracker.feed(dataclasses.replace(said, speed=beacon.UNKNOWN_SPEED, flags=beacon.FLAG_ENABLED))
    assert tracker.state.speed is None and tracker.state.target_hostile is False


def test_an_addon_of_version_one_is_still_read_and_says_nothing_about_them():
    """The addon on the gaming PC may be older than the program. Its frames have an empty byte
    where the speed now is, which must not be read as standing still."""
    old = dataclasses.replace(BASE, version=1, speed=0, flags=beacon.FLAG_ENABLED | beacon.FLAG_HAS_TARGET)
    payload = beacon.pack(old)
    assert payload[0] >> 4 == 1
    assert beacon.unpack(payload) == old
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(beacon.unpack(payload))
    assert tracker.state.speed is None and tracker.state.target_hostile is None
    assert tracker.state.has_target is True


def test_the_enemies_in_view_come_with_version_three():
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(dataclasses.replace(BASE, enemies=4, fighting=2))
    assert (tracker.state.enemies, tracker.state.fighting) == (4, 2)
    tracker.feed(dataclasses.replace(BASE, enemies=beacon.MANY, fighting=0))
    assert (tracker.state.enemies, tracker.state.fighting) == (14, 0)
    # The game would not say, or the addon is an older one: not known, which is not the same as none.
    tracker.feed(dataclasses.replace(BASE, enemies=beacon.UNKNOWN_COUNT, fighting=beacon.UNKNOWN_COUNT))
    assert tracker.state.enemies is None and tracker.state.fighting is None
    old = state.StateTracker(clock=Clock())
    old.feed(dataclasses.replace(BASE, version=2))
    assert old.state.enemies is None and old.state.fighting is None


def test_a_version_this_program_does_not_know_is_refused():
    body = bytes([4 << 4]) + bytes(37)
    with pytest.raises(beacon.BeaconError, match="strip version 4"):
        beacon.unpack(body + beacon.crc16(body).to_bytes(2, "big"))
    with pytest.raises(beacon.BeaconError):
        beacon.pack(dataclasses.replace(BASE, version=4))


def test_an_achievement_is_reported_once():
    tracker = state.StateTracker(clock=Clock())
    tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED, moment=6, moment_count=4))
    events = tracker.feed(dataclasses.replace(BASE, flags=beacon.FLAG_ENABLED, moment=6, moment_count=5))
    assert state.MomentReceived("achievement", 5) in events
