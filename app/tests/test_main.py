"""The game link and the music put together as one server."""
from aiohttp.test_utils import TestClient, TestServer

from freerock import main
from freerock.server import ServerConfig
from freerock.settings import Settings


def routes(app):
    return {route.resource.canonical for route in app.router.routes()}


def config(tmp_path):
    return ServerConfig(var_dir=tmp_path / "var", keep_log=False, front_page="/player")


def test_the_link_alone(tmp_path):
    app = main.build_app(config(tmp_path), music=False)
    assert "/ws/sensor" in routes(app) and "/player" not in routes(app) and "conductor" not in app


async def test_the_link_and_the_music_are_served_together(tmp_path):
    app = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var"))
    assert {"/ws/sensor", "/player", "/ws/player", "/api/pretend", "/phrase/{genre}/{zone}/{clip}"} <= routes(app)
    assert app["conductor"].notes == []
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
    # The song takes its moments of silence where its form comes round: the player page is told
    # how often and how long.
    assert music._silences == {"every_s": 540.0, "for_s": 45.0}
    never = main.build_app(config(tmp_path), settings=Settings(var_dir=tmp_path / "var", rest_every_minutes=0.0))
    assert never["conductor"]._silences["every_s"] == 0.0
