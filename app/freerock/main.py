"""The whole of FreeRock as one server: the game link and the music together.

server.py is the game link on its own; conductor.py is the music side. This puts the two
together the way `freerock serve` runs them, and says on start-up where to point the gaming PC.
"""
from __future__ import annotations

import logging
import socket

from aiohttp import web

from . import conductor, forever, server
from .director import Director, Rules
from .eleven import Gateway
from .ingest import Ingest
from .library import Library
from .settings import MissingKey, Settings, find_key

log = logging.getLogger("freerock")


def build_app(config: server.ServerConfig | None = None, *, music: bool = True, new_music: bool = False,
              settings: Settings | None = None) -> web.Application:
    """The server with everything attached.

    music=False gives the game link alone. new_music=True also buys new phrases from ElevenLabs
    while the game is played; as a rule it is off, and what is in the buckets is played.
    Without a key, new music is off whatever is asked and the control page says why.
    """
    config = config or server.ServerConfig(front_page="/player" if music else "/")
    app = server.create_app(config)
    if not music:
        return app
    settings = settings or Settings.load()
    library = Library(settings.library_dir)
    ingest, filler, note = None, None, None
    if not new_music:
        note = "Nothing is bought from ElevenLabs; playing what is in the buckets."
    else:
        try:
            find_key()
        except MissingKey as missing:
            note = "%s Playing only what is in the library." % missing
            log.warning(note)
        else:
            gateway = Gateway(settings)
            ingest = Ingest(gateway, library)
            filler = forever.Filler(gateway)

            async def close_gateway(app: web.Application) -> None:
                await gateway.aclose()

            app.on_cleanup.append(close_gateway)
    # The rests come from the settings: about so many minutes of music, then so many seconds without.
    rules = Rules(rest_every_s=settings.rest_every_minutes * 60.0, rest_for_s=settings.rest_seconds)
    music_side = conductor.attach(app, library=library, ingest=ingest, director=Director(rules),
                                  settings=settings, filler=filler)
    if note:
        music_side.notes.append(note)
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


def serve(host: str = "0.0.0.0", port: int = 8765, *, music: bool = True, new_music: bool = False) -> None:
    """Runs FreeRock until it is stopped."""
    config = server.ServerConfig(host=host, port=port, front_page="/player" if music else "/")
    app = build_app(config, music=music, new_music=new_music)
    here = addresses() or ["<this machine>"]
    print("FreeRock is running on port %d." % port)
    for address in here:
        print("  On the gaming PC, in a browser:  http://%s:%d/FreeRock.cmd  (the launcher; run what it downloads)" % (address, port))
        print("  What FreeRock sees:              http://%s:%d/" % (address, port))
        if music:
            print("  The player:                      http://%s:%d/player" % (address, port))
    print("  On this machine use http://localhost:%d/player (it has a pretend game to try the music with)." % port)
    web.run_app(app, host=host, port=port, print=None)
