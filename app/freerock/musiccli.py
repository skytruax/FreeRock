"""The music commands of `freerock`: the settings, the stems, the written pieces, the spend.

    freerock settings [name value] show the settings, or change one
    freerock ledger                what has been spent this month and what is left
    freerock stems                 keep every phrase as an audio file, with a table of what each is
    freerock pieces add [style]    put every track staged by the studio in the style's bucket
    freerock pieces list [style]   what written pieces a style has
    freerock pieces drop style from   take out for good every piece that came from somewhere ("knight/" for the
                                   studio's Knight Rock, "warcraft/real-" for the real scores, "song/" for the
                                   pieces cut from the first design's songs)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

from . import composer, forever, pieces
from .cli import add_command
from .eleven import ElevenError, Gateway
from .ledger import day_start, month_start
from .settings import MissingKey, Settings
from .stemstore import StemStore


def _settings() -> Settings:
    return Settings.load()


# -- settings -----------------------------------------------------------------------------------
def _settings_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", nargs="?", help="one of: " + ", ".join(Settings.CHANGEABLE))
    parser.add_argument("value", nargs="?", help="the new value (a number; for genre one of %s; for pieces on or off)"
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
    print("monthly_minutes     %g   new music FreeRock may buy in a calendar month" % settings.monthly_minutes)
    print("daily_minutes       %g   and in one day" % settings.daily_minutes)
    print("rest_every_minutes  %g   about this much music between moments of silence (0: none)" % settings.rest_every_minutes)
    print("rest_seconds        %g   about this long a moment of silence lasts" % settings.rest_seconds)
    print("genre               %s   the style played: %s" % (settings.genre, ", ".join(Settings.GENRES)))
    print("pieces              %s   whether the written pieces are played (off: only the loose phrases)" % settings.pieces)
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


add_command("settings", "show the settings, or change one", _settings_arguments, _show_settings)


# -- stems -----------------------------------------------------------------------------------------
def _stems_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--to", help="the folder to write them to (default: var/stems)")


def _stems(arguments: argparse.Namespace) -> int:
    """Every phrase in every bucket as a FLAC file, with a table of what each is."""
    settings = _settings()
    store = StemStore(arguments.to or settings.var_dir / "stems")
    written, total = store.sync(settings.var_dir / "buckets")
    print("%d phrases in %s (%d written now), with stems.csv saying what each is." % (total, store.root, written))
    return 0


add_command("stems", "keep every phrase as an audio file, with a table of what each is", _stems_arguments, _stems)


# -- pieces ----------------------------------------------------------------------------------------
def _pieces_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("what", choices=("add", "list", "drop"),
                        help="add: put the studio's staged tracks in the bucket; list: say what written pieces the "
                             "style has; drop: take pieces out for good")
    parser.add_argument("style", nargs="?", help="one of: %s (default: the style in force)" % ", ".join(Settings.GENRES))
    parser.add_argument("source", nargs="?", help="for drop: what the pieces' source begins with, such as knight/ or song/")
    parser.add_argument("--zone", help="for a style with no bucket yet: the zone to begin one in")
    parser.add_argument("--port", type=int, default=8765,
                        help="where the FreeRock server listens, to check that it is stopped (default: %(default)s)")


def _print_summary(bucket: forever.Bucket) -> None:
    found = pieces.summary(bucket)
    label = composer.GENRES[bucket.genre]["label"]
    if not found["pieces"]:
        print("%s (%s) has no written pieces. It has %d loose phrases." % (label, bucket.key, found["loose"]))
        return
    print("%s (%s): %d written pieces in %d tracks, %.1f minutes, kept as %d parts; %d loose phrases beside them."
          % (label, bucket.key, found["pieces"], found["tracks"], found["minutes"], found["parts"], found["loose"]))
    print("  for the kind of moment:  " + ",  ".join(
        "%s %d (%.1f min)" % (role, count, minutes) for role, (count, minutes) in sorted(found["by_role"].items())))
    print("  for the kind of place:   " + ",  ".join(
        "%s %d (%.1f min)" % (kind, count, minutes) for kind, (count, minutes) in sorted(found["by_kind"].items())))
    print("  light %d, heavy %d%s%s" % (
        found["light"], found["heavy"],
        "; %d families of pieces that lend each other their parts" % found["families"] if found["families"] else "",
        "; %d banned" % found["banned"] if found["banned"] else ""))


def _pieces(arguments: argparse.Namespace) -> int:
    settings = _settings()
    style = arguments.style or settings.genre
    try:
        bucket = pieces.home_bucket(settings.var_dir, style, arguments.zone)
    except ValueError as problem:
        print(str(problem), file=sys.stderr)
        return 1
    if arguments.what == "list":
        _print_summary(bucket)
        return 0
    if pieces.server_is_up(arguments.port):
        print("The FreeRock server is running (something answers on port %d). Stop it first: it keeps the bucket's "
              "list in memory and would write over what is put in here." % arguments.port, file=sys.stderr)
        return 1
    if arguments.what == "drop":
        if not arguments.source:
            print("Say which pieces: what their source begins with, such as knight/ or warcraft/real- or song/.", file=sys.stderr)
            return 1
        gone = pieces.drop_from(bucket, arguments.source)
        print("%d pieces whose source begins with %r taken out of %s for good." % (gone, arguments.source, bucket.key))
        _print_summary(bucket)
        return 0
    done = pieces.add_staged(bucket, settings.var_dir, style)
    failed = 0
    for folder, ids, problem in done:
        name = "%s/%s" % (folder.parent.name, folder.name)
        if problem:
            failed += 1
            print("NOT PUT IN %-40s %s" % (name, problem), file=sys.stderr)
        else:
            print("%-9s %-40s %s" % ("added" if ids else "there", name, "%d pieces" % len(ids) if ids else ""))
    print("%d staged tracks for %s: %d put in %s now, %d were there already%s."
          % (len(done), composer.GENRES[style]["label"], sum(1 for _, ids, problem in done if ids),
             bucket.key, sum(1 for _, ids, problem in done if not ids and not problem),
             ", %d could not be put in (see above)" % failed if failed else ""))
    _print_summary(bucket)
    return 1 if failed else 0


add_command("pieces", "written pieces: add the studio's tracks, list them, or take some out",
            _pieces_arguments, _pieces)
add_command("ledger", "what has been spent this month and what is left", lambda parser: None, _ledger)
