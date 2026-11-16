"""The music commands of `freerock`: make a zone's music now, list the library, show the spend.

    freerock make "Duskwood"       make that zone's first music now (uses the allowance)
    freerock adopt <folder>        look again at a track that failed its checks; keep it if it passes now
    freerock settings [name value] show the allowances and the amount of rock, or change one
    freerock library               what music FreeRock has
    freerock ledger                what has been spent this month and what is left
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

from . import atlas
from .cli import add_command
from .eleven import AllowanceExceeded, ElevenError, Gateway
from .ingest import Ingest, TrackFailedChecks
from .ledger import day_start, month_start
from .library import Library
from .settings import MissingKey, Settings


def _settings() -> Settings:
    return Settings.load()


def _ingest(settings: Settings) -> tuple[Ingest, Gateway]:
    gateway = Gateway(settings)
    return Ingest(gateway, Library(settings.library_dir)), gateway


# -- make ---------------------------------------------------------------------------------------
def _make_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("zone", help="the zone's name as the game shows it, in quotes if it has spaces")
    parser.add_argument("--rock", type=float,
                        help="how much of the rock the calm parts carry, 0 to 1 (default: the rock setting)")
    parser.add_argument("--again", action="store_true", help="make it even if the zone already has music")
    parser.add_argument("--set", choices=("core", "second", "fresh"), default="core",
                        help="which music to make: the zone's first (core), or a later set that adds to it "
                             "(second has Night, Storm and Boss; fresh has more riffs)")


def _make(arguments: argparse.Namespace) -> int:
    settings = _settings()
    profile = atlas.profile_for(arguments.zone)
    library = Library(settings.library_dir)
    have = library.assets(profile.key)
    core = next((asset for asset in library.usable(profile.key) if asset.set == "core"), None)
    if arguments.set == "core" and have and not arguments.again:
        print("%s already has music (%s). Use --again to make more, or --set second to add to it."
              % (arguments.zone, ", ".join(a.id for a in have)))
        return 0
    if arguments.set != "core" and core is None:
        print("%s has no core suite to add a %s set to. Make that first: freerock make \"%s\""
              % (arguments.zone, arguments.set, arguments.zone), file=sys.stderr)
        return 1
    if not atlas.is_known(arguments.zone):
        print("%r is not one of the game's zones FreeRock has a profile for; using one worked out from its name."
              % arguments.zone)
    print("Making music for %s: %d BPM, %s, %s." % (arguments.zone, profile.bpm, profile.tonic, ", ".join(profile.colours)))

    async def run() -> int:
        ingest, gateway = _ingest(settings)
        try:
            if arguments.set == "core":
                made = await ingest.core_suite(arguments.zone, rock=arguments.rock)
            else:
                made = await ingest.later_set(core, arguments.zone, arguments.set, rock=arguments.rock)
        except TrackFailedChecks as failed:
            print("It came back, but not as asked for, and was not put in the library: %s."
                  % "; ".join(failed.checks["failed"]), file=sys.stderr)
            if failed.kept is not None:
                print("The audio and the measurements are in %s" % failed.kept, file=sys.stderr)
            return 1
        except (AllowanceExceeded, ElevenError, MissingKey) as refused:
            print(str(refused), file=sys.stderr)
            return 1
        finally:
            await gateway.aclose()
        asset = made.asset
        print("Done: %s (%s set), %.2f minutes of music. First audio after %.1f s, all of it after %.1f s, layers split in %.0f s."
              % (asset.id, asset.set, asset.minutes, made.first_audio_s or 0.0, made.total_s or 0.0, made.split_s))
        for name, part in asset.checks["parts"].items():
            print("  %-9s tempo %+.3f%%, starts %+.1f ms from a beat, heard as %s"
                  % (name, part["tempo_off_percent"], part["start_to_beat_ms"], part["heard_as"]))
        return 0

    return asyncio.run(run())


# -- adopt --------------------------------------------------------------------------------------
def _adopt_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("folder", help="a folder under var/rejected holding a track that failed its checks")


def _adopt(arguments: argparse.Namespace) -> int:
    settings = _settings()

    async def run() -> int:
        ingest, gateway = _ingest(settings)
        try:
            made = await ingest.adopt(arguments.folder)
        except TrackFailedChecks as failed:
            print("It still fails: %s." % "; ".join(failed.checks["failed"]), file=sys.stderr)
            return 1
        finally:
            await gateway.aclose()
        print("Put in the library as %s (%s, %.2f minutes)." % (made.asset.id, made.asset.zone, made.asset.minutes))
        return 0

    return asyncio.run(run())


# -- settings -----------------------------------------------------------------------------------
def _settings_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", nargs="?", help="one of: " + ", ".join(Settings.CHANGEABLE))
    parser.add_argument("value", nargs="?", help="the new value (a number, or for genre one of: %s)"
                        % ", ".join(Settings.GENRES))


def _show_settings(arguments: argparse.Namespace) -> int:
    settings = _settings()
    if arguments.name is not None:
        if arguments.value is None:
            print("Give a value as well, for example: freerock settings %s 40" % arguments.name, file=sys.stderr)
            return 1
        try:
            value = arguments.value if arguments.name in Settings.WORDS else float(arguments.value)
        except ValueError:
            print("%s takes a number, not %r" % (arguments.name, arguments.value), file=sys.stderr)
            return 1
        try:
            settings.change(arguments.name, value)
        except ValueError as problem:
            print(str(problem), file=sys.stderr)
            return 1
        settings.save()
        print("Saved in %s. A running server uses it from its next start." % settings.file)
    print("monthly_minutes     %g   new music FreeRock may make in a calendar month" % settings.monthly_minutes)
    print("daily_minutes       %g   and in one day" % settings.daily_minutes)
    print("hours_per_month     %g   hours of play the month's music is paced over" % settings.hours_per_month)
    print("rock                %g   how much of the rock the calm parts of new music carry, 0 to 1" % settings.rock)
    print("rest_every_minutes  %g   about this much calm music between rests (0: never rest)" % settings.rest_every_minutes)
    print("rest_seconds        %g   about this long without music in a rest" % settings.rest_seconds)
    print("genre               %s   the style played and made: %s" % (settings.genre, ", ".join(Settings.GENRES)))
    print("mode                %s   how the music is put together: %s" % (settings.mode, ", ".join(Settings.MODES)))
    return 0


# -- library ------------------------------------------------------------------------------------
def _library(arguments: argparse.Namespace) -> int:
    assets = Library(_settings().library_dir).assets()
    if not assets:
        print("The library is empty.")
        return 0
    for asset in assets:
        marks = (" loved" if asset.loved else "") + (" banned" if asset.banned else "")
        where = asset.zone + (" / " + asset.subzone if asset.subzone else "")
        print("%-34s %-8s %-6s %s  %.2f min  %3d BPM  %-14s %s%s" % (
            where, asset.genre, asset.set, asset.id, asset.minutes, asset.bpm, asset.tonic,
            time.strftime("%Y-%m-%d %H:%M", time.localtime(asset.created)), marks))
    print("%d pieces of music for %d places, %.1f minutes in all."
          % (len(assets), len({asset.zone for asset in assets}), sum(asset.minutes for asset in assets)))
    return 0


# -- ledger -------------------------------------------------------------------------------------
def _ledger(arguments: argparse.Namespace) -> int:
    settings = _settings()
    gateway = Gateway(settings)
    ledger = gateway.ledger
    now = time.time()
    month, today = ledger.month_minutes(), ledger.day_minutes()
    print("This month: %.2f of %.0f minutes (about $%.2f). Today: %.2f of %.0f minutes."
          % (month, settings.monthly_minutes, month * settings.usd_per_minute, today, settings.daily_minutes))
    for purpose, minutes, calls in ledger.by_purpose(month_start(now)):
        print("  %-46s %6.2f min  %d call%s" % (purpose, minutes, calls, "" if calls == 1 else "s"))
    spent_today = ledger.by_purpose(day_start(now))
    if spent_today:
        print("Today: " + ", ".join("%s %.2f" % (purpose, minutes) for purpose, minutes, _ in spent_today))

    async def account() -> None:
        try:
            found = await gateway.subscription()
        except (ElevenError, MissingKey) as problem:
            print("The account's own balance could not be read: %s" % problem)
            return
        finally:
            await gateway.aclose()
        used, limit = found.get("character_count"), found.get("character_limit")
        print("ElevenLabs account: %s plan, %s of %s credits used." % (found.get("tier"), used, limit))

    asyncio.run(account())
    return 0


add_command("make", "make a zone's first music now", _make_arguments, _make)
add_command("adopt", "look again at a track that failed its checks and keep it if it now passes",
            _adopt_arguments, _adopt)
add_command("settings", "show the allowances and the amount of rock, or change one",
            _settings_arguments, _show_settings)
add_command("library", "list the music FreeRock has", lambda parser: None, _library)
add_command("ledger", "what has been spent this month and what is left", lambda parser: None, _ledger)
