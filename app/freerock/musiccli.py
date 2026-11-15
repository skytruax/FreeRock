"""The music commands of `freerock`: make a zone's music now, list the library, show the spend.

    freerock make "Duskwood"       make that zone's first music now (uses the allowance)
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
    return Settings()


def _ingest(settings: Settings) -> tuple[Ingest, Gateway]:
    gateway = Gateway(settings)
    return Ingest(gateway, Library(settings.library_dir)), gateway


# -- make ---------------------------------------------------------------------------------------
def _make_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("zone", help="the zone's name as the game shows it, in quotes if it has spaces")
    parser.add_argument("--rock", type=float, default=0.5,
                        help="how much of the rock the calm parts carry, 0 to 1 (default: %(default)s)")
    parser.add_argument("--again", action="store_true", help="make it even if the zone already has music")


def _make(arguments: argparse.Namespace) -> int:
    settings = _settings()
    profile = atlas.profile_for(arguments.zone)
    library = Library(settings.library_dir)
    have = library.assets(profile.key)
    if have and not arguments.again:
        print("%s already has music (%s). Use --again to make more." % (arguments.zone, ", ".join(a.id for a in have)))
        return 0
    if not atlas.is_known(arguments.zone):
        print("%r is not one of the game's zones FreeRock has a profile for; using one worked out from its name."
              % arguments.zone)
    print("Making music for %s: %d BPM, %s, %s." % (arguments.zone, profile.bpm, profile.tonic, ", ".join(profile.colours)))

    async def run() -> int:
        ingest, gateway = _ingest(settings)
        try:
            made = await ingest.core_suite(arguments.zone, rock=arguments.rock)
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
        print("Done: %s, %.2f minutes of music. First audio after %.1f s, all of it after %.1f s, layers split in %.0f s."
              % (asset.id, asset.minutes, made.first_audio_s or 0.0, made.total_s or 0.0, made.split_s))
        for name, part in asset.checks["parts"].items():
            print("  %-9s tempo %+.3f%%, starts %+.1f ms from a beat, heard as %s"
                  % (name, part["tempo_off_percent"], part["start_to_beat_ms"], part["heard_as"]))
        return 0

    return asyncio.run(run())


# -- library ------------------------------------------------------------------------------------
def _library(arguments: argparse.Namespace) -> int:
    assets = Library(_settings().library_dir).assets()
    if not assets:
        print("The library is empty.")
        return 0
    for asset in assets:
        marks = (" loved" if asset.loved else "") + (" banned" if asset.banned else "")
        print("%-22s %-6s %s  %.2f min  %3d BPM  %-20s %s%s" % (
            asset.zone, asset.set, asset.id, asset.minutes, asset.bpm, asset.tonic,
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
add_command("library", "list the music FreeRock has", lambda parser: None, _library)
add_command("ledger", "what has been spent this month and what is left", lambda parser: None, _ledger)
