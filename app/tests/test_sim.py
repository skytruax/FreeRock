"""The pretend game: its frames, its screen, and the scenarios that come with FreeRock."""
import json

import numpy as np
import pytest

from freerock import beacon, cli, sim, state
from freerock.web import sensor


def quiet(*_):
    pass


def session_for(name, **options):
    return sim.SimSession(sim.load_scenario(name), say=quiet, real_sleep=lambda seconds: None, **options)


def read_edge(session):
    """What the reader makes of the edge of the pretend screen the strip is on."""
    band = sensor.BAND
    top = 0 if session.edge == "top" else session.height - band
    pixels = np.frombuffer(session.copy(0, top, session.width, band), np.uint8).reshape(band, session.width, 4)
    return beacon.read(pixels)


@pytest.mark.parametrize("name", ["elwynn-walk", "deadmines"])
def test_scenarios_play_through_and_every_picture_reads(name):
    session = session_for(name)
    tracker = state.StateTracker(clock=session.clock)
    said = []
    session.say = said.append
    events = []
    while not session.finished:
        session.advance(0.05)
        reading = read_edge(session)
        if session.hidden:
            assert reading.problem == "no strip"
            events += tracker.tick()
        else:
            assert reading.ok, f"{name} at {session.now:.2f} s: {reading.problem}"
            events += tracker.feed(reading.frame)
    assert len(said) == len(session.steps), "every step said what it did"
    assert tracker.name_rejects == 0
    kinds = {type(event).__name__ for event in events}
    assert {"StateChanged", "LinkChanged", "MomentReceived"} <= kinds
    if name == "elwynn-walk":
        game = tracker.state
        assert game.zone_name == "Westfall" and game.map_id == 1436 and game.pvp_kind == "contested"
        assert game.daytime is False and game.game_minutes == 19 * 60 + 5
        assert game.weather == "clear"
        assert [event.name for event in events if isinstance(event, state.CommandReceived)] == ["skip", "love"]
        assert [event.name for event in events if isinstance(event, state.MomentReceived)] == ["level_up"]
        assert any(isinstance(event, state.TestPatternSeen) for event in events)
        changed = set().union(*(event.changed for event in events if isinstance(event, state.StateChanged)))
        assert {"indoors", "mounted", "stealthed", "in_combat", "target_class", "weather", "weather_intensity",
                "daytime", "subzone_name", "resting", "position", "map_id"} <= changed
    else:
        game = tracker.state
        assert game.in_instance and game.instance_kind == "party" and game.instance_name == "The Deadmines"
        assert game.position is None and game.weather is None and game.daytime is None and game.game_minutes is None
        assert not game.encounter and not game.dead and not game.cinematic
        assert [event.name for event in events if isinstance(event, state.MomentReceived)] == ["died", "boss_defeated"]
        names = [event.state.encounter_name for event in events if isinstance(event, state.StateChanged)]
        assert "Edwin VanCleef" in names


def test_walking_moves_the_position_smoothly():
    session = session_for("elwynn-walk")
    session.advance(4.0)
    start = (session.game.x, session.game.y)
    session.advance(4.0)
    half = (session.game.x, session.game.y)
    session.advance(4.5)
    assert start == pytest.approx((0.42, 0.65), abs=0.01)
    assert half == pytest.approx((0.405, 0.725), abs=0.01)
    assert (session.game.x, session.game.y) == pytest.approx((0.39, 0.80), abs=1e-6)


def test_the_pretend_screen_hands_out_exactly_the_rectangle_asked_for():
    session = session_for("elwynn-walk")
    whole = np.frombuffer(session.copy(0, 0, 2560, 40), np.uint8).reshape(40, 2560, 4)
    piece = np.frombuffer(session.copy(300, 3, 500, 9), np.uint8).reshape(9, 500, 4)
    assert np.array_equal(piece, whole[3:12, 300:800])
    assert (whole[:, :, 3] == 255).all()
    middle = np.frombuffer(session.copy(0, 600, 64, 8), np.uint8).reshape(8, 64, 4)
    assert (middle[:, :, :3] == 0).all(), "nothing is drawn away from the edges"
    with pytest.raises(ValueError, match="outside the pretend screen"):
        session.copy(2500, 0, 100, 10)


def test_a_scenario_that_sets_something_unknown_is_refused():
    with pytest.raises(ValueError, match="does not have"):
        sim.SimSession({"start": {"mana": 5}}, say=quiet)
    session = sim.SimSession({"steps": [{"at": 0.1, "jump": True}]}, say=quiet, real_sleep=lambda seconds: None)
    with pytest.raises(ValueError, match="does not know"):
        session.advance(0.2)


def test_an_unknown_scenario_lists_the_ones_there_are():
    with pytest.raises(FileNotFoundError, match="deadmines, elwynn-walk"):
        sim.load_scenario("nowhere")


def test_freerock_sim_list(capsys):
    assert cli.main(["sim", "--list"]) == 0
    out = capsys.readouterr().out
    assert "elwynn-walk:" in out and "deadmines:" in out


def test_freerock_sim_without_a_server_says_how_to_start_one(capsys):
    import socket

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert cli.main(["sim", "deadmines", "--server", f"http://127.0.0.1:{port}"]) == 1
    assert "freerock serve" in capsys.readouterr().err


def test_freerock_read_reads_a_saved_picture(tmp_path, capsys):
    from PIL import Image

    session = session_for("elwynn-walk")
    session.advance(6.0)
    pixels = np.frombuffer(session.copy(0, 0, 2560, 40), np.uint8).reshape(40, 2560, 4)
    path = tmp_path / "screen.png"
    Image.fromarray(np.ascontiguousarray(pixels[:, :, 2::-1])).save(path)
    assert cli.main(["read", str(path)]) == 0
    out = capsys.readouterr().out
    assert "strip at 18, 2: 1032 x 6 px, squares of 3.00 px" in out
    shown = json.loads(out.split("state: ", 1)[1])
    assert shown["map_id"] == 1429 and shown["resting"] is False

    blank = tmp_path / "blank.png"
    Image.new("RGB", (1500, 30), (40, 40, 40)).save(blank)
    assert cli.main(["read", str(blank)]) == 1
    assert "no frame read: no strip" in capsys.readouterr().out
