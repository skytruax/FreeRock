"""The `freerock` command.

    freerock serve                 run FreeRock: the game link, the music and the pages
    freerock sim <scenario>        play a scripted session against a running server, without the game
    freerock sim --list            the scenarios that come with FreeRock
    freerock read <picture>        read the strip out of a saved picture and say what it holds

Other parts of FreeRock add their own commands by calling add_command() before main() runs.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import Callable

# name -> (help, function that adds arguments to the sub-parser, function that runs it)
_COMMANDS: dict[str, tuple[str, Callable[[argparse.ArgumentParser], None], Callable[[argparse.Namespace], int]]] = {}


def add_command(name: str, help: str, configure: Callable[[argparse.ArgumentParser], None],
                run: Callable[[argparse.Namespace], int]) -> None:
    if name in _COMMANDS:
        raise ValueError(f"there is already a freerock command called {name}")
    _COMMANDS[name] = (help, configure, run)


# -- serve ----------------------------------------------------------------------
def _serve_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on (default: every address of this machine)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--link-only", action="store_true", help="run the game link and its page without the music")
    parser.add_argument("--no-new-music", action="store_true",
                        help="play what is in the library and never ask ElevenLabs for more")


def _serve(arguments: argparse.Namespace) -> int:
    from freerock import main as whole

    whole.serve(host=arguments.host, port=arguments.port, music=not arguments.link_only,
                new_music=not arguments.no_new_music)
    return 0


# -- sim --------------------------------------------------------------------------
def _sim_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("scenario", nargs="?", help="a scenario's name (see --list) or the path of a scenario file")
    parser.add_argument("--list", action="store_true", help="list the scenarios that come with FreeRock")
    parser.add_argument("--server", default="http://127.0.0.1:8765", help="the running FreeRock server (default: %(default)s)")
    parser.add_argument("--speed", type=float, default=1.0, help="play faster or slower than real time (default: 1)")


def _sim(arguments: argparse.Namespace) -> int:
    from freerock import sim
    from freerock.web import sensor

    if arguments.list or not arguments.scenario:
        for path in sorted(sim.SCENARIOS.glob("*.json")):
            about = json.loads(path.read_text(encoding="utf-8")).get("about", "")
            print(f"{path.stem}: {about}")
        return 0
    scenario = sim.load_scenario(arguments.scenario)
    if arguments.speed <= 0:
        raise SystemExit("--speed must be more than 0")
    try:
        sim.play(scenario, arguments.server, speed=arguments.speed)
    except (OSError, sensor.LinkClosed) as error:
        print(f"Cannot reach FreeRock at {arguments.server}: {error}. Start it with: freerock serve", file=sys.stderr)
        return 1
    return 0


# -- read -------------------------------------------------------------------------
def _read_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("picture", help="a saved picture (PNG, JPEG, BMP) that should have the strip in it")


def _read(arguments: argparse.Namespace) -> int:
    import numpy as np
    from PIL import Image

    from freerock import beacon, state

    with Image.open(arguments.picture) as picture:
        pixels = np.asarray(picture.convert("RGB"))
    reading = beacon.read(pixels)
    print(f"picture: {pixels.shape[1]} x {pixels.shape[0]} px")
    if not reading.ok:
        print(f"no frame read: {reading.problem} (rows of squares seen: {list(reading.rows_seen) or 'none'})")
        return 1
    x, y, width, height = reading.box
    print(f"strip at {x}, {y}: {width} x {height} px, squares of {reading.pitch:.2f} px")
    if reading.frame.kind == beacon.KIND_TEST:
        print("it is the addon's test pattern, read correctly")
        return 0
    print("frame: " + json.dumps(dataclasses.asdict(reading.frame), default=lambda value: value.hex()))
    tracker = state.StateTracker()
    tracker.feed(reading.frame)
    print("state: " + json.dumps(tracker.state.as_dict()))
    return 0


add_command("serve", "run the FreeRock server", _serve_arguments, _serve)
add_command("sim", "play a scripted session against a running server", _sim_arguments, _sim)
add_command("read", "read the strip out of a saved picture", _read_arguments, _read)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="freerock", description="FreeRock: generated game music that follows the game.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, configure, run) in _COMMANDS.items():
        sub = commands.add_parser(name, help=help_text)
        configure(sub)
        sub.set_defaults(run=run)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    return arguments.run(arguments)


if __name__ == "__main__":
    sys.exit(main())
