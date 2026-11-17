"""The game link and the music put together as one server."""
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


def test_nothing_is_bought_from_elevenlabs_unless_it_is_asked_for(tmp_path, monkeypatch):
    """("stop buying eleven labs were making music now", 2026-11-16.)"""
    def no_key_needed():
        raise AssertionError("the key was looked for although nothing is to be bought")

    monkeypatch.setattr(main, "find_key", no_key_needed)
    app = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var"))
    assert {"/ws/sensor", "/player", "/ws/player", "/api/pretend"} <= routes(app)
    assert app["conductor"].filler is None
    assert "Nothing is bought from ElevenLabs" in app["conductor"].notes[0]


def test_without_a_key_it_plays_what_is_in_the_buckets_and_says_why(tmp_path, monkeypatch):
    def missing():
        raise MissingKey("No ElevenLabs key found.")

    monkeypatch.setattr(main, "find_key", missing)
    app = main.build_app(config(tmp_path), new_music=True, settings=Settings(var_dir=tmp_path / "var"))
    assert app["conductor"].filler is None
    assert "No ElevenLabs key found. Playing only what is in the buckets." in app["conductor"].notes[0]


async def test_with_a_key_it_can_make_music_and_serves_both_halves(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "find_key", lambda: ("EL_BIG_BAD_KEY", "sk_test"))
    monkeypatch.setattr(settings_module, "find_key", lambda: ("EL_BIG_BAD_KEY", "sk_test"))
    app = main.build_app(config(tmp_path), new_music=True, settings=Settings(var_dir=tmp_path / "var"))
    assert app["conductor"].filler is not None and app["conductor"].notes == []
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        assert (await client.get("/player")).status == 200
        assert (await client.get("/")).status == 200
        launcher = await (await client.get("/FreeRock.cmd")).text()
        assert "/player" in launcher and "sensor.py" in launcher
        music = await (await client.get("/api/music")).json()
        assert music["players_connected"] == 0 and music["forever"]["bucket"] is None
    finally:
        await client.close()


def test_addresses_are_plain_ip_addresses():
    for address in main.addresses():
        assert address.count(".") == 3 and all(part.isdigit() for part in address.split("."))


def test_the_moments_of_silence_come_from_the_settings(tmp_path):
    settings = Settings(var_dir=tmp_path / "var", rest_every_minutes=9.0, rest_seconds=45.0)
    music = main.build_app(config(tmp_path), settings=settings)["conductor"]
    # The forever song takes its own moments of silence, where its form comes round: the player
    # page is told how often and how long, and the director's rests, which cut in anywhere, are off.
    assert music._silences == {"every_s": 540.0, "for_s": 45.0}
    assert music.director.rules.rest_every_s == 0.0
    never = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var", rest_every_minutes=0.0))
    assert never["conductor"]._silences["every_s"] == 0.0
