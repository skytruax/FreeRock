"""The whole of FreeRock as one server: the game link and the music together.

server.py is the game link on its own; conductor.py is the music side. This puts the two
together the way `freerock serve` runs them, and says on start-up where to point the gaming PC.
"""
from __future__ import annotations

import logging
import socket

from aiohttp import web

from . import conductor, server
from .settings import Settings

log = logging.getLogger("freerock")


def build_app(config: server.ServerConfig | None = None, *, music: bool = True,
              settings: Settings | None = None) -> web.Application:
    """The server with everything attached; music=False gives the game link alone."""
    config = config or server.ServerConfig(front_page="/player" if music else "/")
    app = server.create_app(config)
    if music:
        conductor.attach(app, settings=settings or Settings.load())
    return app


def addresses() -> list[str]:
    """This machine's addresses on the local network, for telling the gaming PC where to look.
    Found by asking which address would be used to reach the outside; nothing is sent."""
    found = []
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))          # a documentation-only address; no packet leaves
        found.append(probe.getsockname()[0])
    except OSError as error:
        log.info("could not work out this machine's network address: %s", error)
    finally:
        probe.close()
    return found


def serve(host: str = "0.0.0.0", port: int = 8765, *, music: bool = True) -> None:
    """Runs FreeRock until it is stopped."""
    config = server.ServerConfig(host=host, port=port, front_page="/player" if music else "/")
    app = build_app(config, music=music)
    here = addresses() or ["<this machine>"]
    print("FreeRock is running on port %d." % port)
    for address in here:
        print("  On the gaming PC, in a browser:  http://%s:%d/FreeRock.cmd  (the launcher; run what it downloads)" % (address, port))
        print("  What FreeRock sees:              http://%s:%d/" % (address, port))
        if music:
            print("  The player:                      http://%s:%d/player" % (address, port))
    print("  On this machine use http://localhost:%d/player (it has a pretend game to try the music with)." % port)
    web.run_app(app, host=host, port=port, print=None)
