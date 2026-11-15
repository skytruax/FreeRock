"""The game link and the music put together as one server."""
import pytest
from aiohttp.test_utils import TestClient, TestServer

from freerock import main, settings as settings_module
from freerock.server import ServerConfig
from freerock.settings import MissingKey, Settings


def routes(app):
    return {route.resource.canonical for route in app.router.routes()}


def config(tmp_path):
    return ServerConfig(var_dir=tmp_path / "var", keep_log=False, front_page="/player")


def test_the_link_alone(tmp_path):
    app = main.build_app(config(tmp_path), music=False)
    assert "/ws/sensor" in routes(app) and "/player" not in routes(app) and "conductor" not in app


def test_music_without_new_music_never_touches_elevenlabs(tmp_path, monkeypatch):
    def no_key_needed():
        raise AssertionError("the key was looked for although new music is off")

    monkeypatch.setattr(main, "find_key", no_key_needed)
    app = main.build_app(config(tmp_path), new_music=False, settings=Settings(var_dir=tmp_path / "var"))
    assert {"/ws/sensor", "/player", "/ws/player", "/api/pretend"} <= routes(app)
    assert app["conductor"].ingest is None
    assert "New music is switched off" in app["conductor"].notes[0]


def test_without_a_key_it_plays_the_library_and_says_why(tmp_path, monkeypatch):
    def missing():
        raise MissingKey("No ElevenLabs key found.")

    monkeypatch.setattr(main, "find_key", missing)
    app = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var"))
    assert app["conductor"].ingest is None
    assert "No ElevenLabs key found. Playing only what is in the library." in app["conductor"].notes[0]


async def test_with_a_key_it_can_make_music_and_serves_both_halves(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "find_key", lambda: ("EL_BIG_BAD_KEY", "sk_test"))
    monkeypatch.setattr(settings_module, "find_key", lambda: ("EL_BIG_BAD_KEY", "sk_test"))
    app = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var"))
    assert app["conductor"].ingest is not None and app["conductor"].notes == []
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        assert (await client.get("/player")).status == 200
        assert (await client.get("/")).status == 200
        launcher = await (await client.get("/FreeRock.cmd")).text()
        assert "/player" in launcher and "sensor.py" in launcher
        music = await (await client.get("/api/music")).json()
        assert music["players_connected"] == 0 and music["making"] is None
    finally:
        await client.close()


def test_addresses_are_plain_ip_addresses():
    for address in main.addresses():
        assert address.count(".") == 3 and all(part.isdigit() for part in address.split("."))


def test_the_rests_and_the_pacing_come_from_the_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "find_key", lambda: ("EL_BIG_BAD_KEY", "sk_test"))
    settings = Settings(var_dir=tmp_path / "var", rest_every_minutes=9.0, rest_seconds=45.0, hours_per_month=60.0)
    app = main.build_app(config(tmp_path), settings=settings)
    music = app["conductor"]
    assert music.director.rules.rest_every_s == 540.0 and music.director.rules.rest_for_s == 45.0
    assert music.settings.hours_per_month == 60.0
    assert music.playtime.path == tmp_path / "var" / "playtime.json"
    never = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var", rest_every_minutes=0.0),
                           new_music=False)
    assert never["conductor"].director.rules.rest_every_s == 0.0
