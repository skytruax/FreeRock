"""The page of what the judges passed, for the listener (var/listen/gate.html).

(2026-11-26, the audit after "most of the music we heard last night sucked, the new bands a lot of time just sound random": every new song is held to
the liked library by the judges (tools/gate.py), and of the first twenty-eight new Knight Rock songs they read, the seven that passed were every one
a band's. A band's, a company's or an act's song does not come into the player on the judges' word alone: the listener hears the ones that passed and
says. This is the page they hear them on.)

    cd app && uv run --no-sync python ../tools/gate_page.py gate-1126 [gate-1127 ...]

For the labels given, a style at a time: the songs that passed and are a band's, a company's or an act's, band by band, each to listen to (its whole
file on the listening pages, var/listen/<style>/); where a song was written again, the take of before beside it (kept under
var/studio-demo/retold-audit-1126/resting; its whole file is written to var/listen/gate/ as the listening pages write theirs); then the house's own
players' songs that passed (they come into the player at the next build); then, by name and number only, the ones that were held. A song whose
reading was made before it was performed again is not on the page (gate.standing).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402

VAR = Path(__file__).resolve().parent.parent / "var"
STYLES = (("knight", "Knight Rock"), ("warcraft", "Warcraft"), ("house", "House"))
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
BEFORE = ("studio-demo", "retold-audit-1126", "resting")     # where the takes of before a song was written again are kept


def staged(var: Path, style: str, take: str) -> dict:
    """What a staged take says of itself (its track.json), or {} where it is not staged."""
    path = Path(var) / "studio" / style / take / "track.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def metre_of(folder: Path) -> str:
    """The metre a take's sheet says it is in, or "" where there is no sheet."""
    sheet = Path(folder) / "sheet.json"
    return str((json.loads(sheet.read_text(encoding="utf-8")).get("about") or {}).get("metre") or "") if sheet.is_file() else ""


def whole_of(var: Path, style: str, take: str) -> tuple[str, bool]:
    """A staged take's whole file on the listening pages, as a path from var/listen ("" where there is none yet), and whether it is older than the take
    as it is staged (the take was performed again, and the listening pages have not written it again yet)."""
    meta = staged(var, style, take)
    if not meta:
        return "", False
    name = "%s - take %s (%s).flac" % (meta["title"], meta["take"], meta["family"])       # (tools/listen.py, `names`)
    path = Path(var) / "listen" / style / name
    if not path.is_file():
        return "", False
    return "%s/%s" % (style, name), path.stat().st_mtime < (Path(var) / "studio" / style / take / "track.json").stat().st_mtime


def before_of(var: Path, style: str, take: str) -> str:
    """The whole file of the take of before a song was written again, as a path from var/listen, written from its kept channels if it is not there or is
    older than them; "" where no take of before is kept."""
    import numpy as np
    import soundfile
    kept = Path(var).joinpath(*BEFORE) / style / take
    if not (kept / "track.json").is_file():
        return ""
    out = Path(var) / "listen" / "gate" / ("%s--%s--before.flac" % (style, take.replace("/", "--")))
    if out.is_file() and out.stat().st_mtime >= (kept / "track.json").stat().st_mtime:
        return "gate/" + out.name
    parts = [soundfile.read(str(kept / (channel + ".flac")), dtype="float32", always_2d=True) for channel in CHANNELS if (kept / (channel + ".flac")).is_file()]
    if not parts:
        raise ValueError("The take of before kept in %s has no recordings" % kept)
    rate = parts[0][1]
    length = max(len(audio) for audio, _ in parts)
    mix = sum(np.pad(audio, ((0, length - len(audio)), (0, 0))) for audio, _ in parts)
    peak = float(np.abs(mix).max())
    if peak <= 0.0:
        raise ValueError("The take of before kept in %s is silent" % kept)
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch = out.with_name(out.stem + ".%d.part.flac" % os.getpid())
    soundfile.write(str(scratch), mix * (0.89 / peak), rate, format="FLAC", subtype="PCM_16")       # (as the listening pages write a whole file)
    scratch.replace(out)
    return "gate/" + out.name


def songs(var: Path, rows: list[dict], labels: list[str]) -> list[dict]:
    """Every song read under the labels as the gate has it (a song read under two labels counts by the later one given): its verdict, whose it is, what to
    listen to, and the take of before where it was written again."""
    by: dict[tuple[str, str], dict] = {}
    for label in labels:
        kept, _ = gate.standing(rows, label)
        found = gate.check(kept, label)
        through = set(gate.passed(found))
        for each in found:
            by[(each["style"], each["take"])] = dict(each, label=label, passes=each["take"] in through)
    out = []
    for (style, take), each in sorted(by.items()):
        meta = staged(var, style, take)
        if not meta:
            continue                                   # (read and since taken away: nothing to listen to)
        whole, stale = whole_of(var, style, take)
        each.update(whose=gate.whose(var, style, take), whole=whole, stale=stale, title=meta.get("title") or each.get("title") or take,
                    tempo=meta.get("tempo"), metre=metre_of(Path(var) / "studio" / style / take),
                    before=before_of(var, style, take) if each["passes"] else "",
                    before_metre=metre_of(Path(var).joinpath(*BEFORE) / style / take))
        out.append(each)
    return out


def _row(each: dict) -> str:
    bar = each["bar"] or {"score": float("nan"), "memorability": float("nan")}
    said = "the judges %.2f, memorability %.2f <small>(a song passes at %.2f and %.2f)</small>" % (each["score"], each["memorability"], bar["score"], bar["memorability"])
    about = " · ".join(part for part in ("%.0f to the minute" % each["tempo"] if each.get("tempo") else "", "in " + each["metre"] if each["metre"] else "") if part)
    if each["whole"]:
        now = '<audio controls preload="none" src="%s"></audio>' % quote(each["whole"])
        if each["stale"]:
            now += "<br><small>this file is of the take before it was performed again: the new one is written within the half hour</small>"
    else:
        now = "<small>(its file to listen to is not written yet: within the half hour)</small>"
    cells = "<td><b>%s</b><br><small>%s</small><br>%s</td><td>%s%s</td>" % (
        html.escape(each["title"]), html.escape(each["take"]), said, ("<small>%s</small><br>" % html.escape(about)) if about else "", now)
    if each["before"]:
        was = " in %s" % html.escape(each["before_metre"]) if each["before_metre"] and each["before_metre"] != each["metre"] else ""
        cells += '<td><small>as it was before it was written again%s</small><br><audio controls preload="none" src="%s"></audio></td>' % (was, quote(each["before"]))
    else:
        cells += "<td></td>"
    return "<tr>%s</tr>" % cells


def page(found: list[dict], labels: list[str], now: float | None = None) -> str:
    """The page: what passed and is a band's (the listener says), what passed and is the house's own (it comes in), and what was held."""
    parts = []
    for style, name in STYLES:
        mine = [each for each in found if each["style"] == style]
        if not mine:
            continue
        through = [each for each in mine if each["passes"]]
        theirs: dict[str, list[dict]] = defaultdict(list)
        for each in through:
            if each["whose"]:
                theirs[each["whose"]].append(each)
        own = [each for each in through if not each["whose"]]
        held = [each for each in mine if not each["passes"]]
        parts.append("<h2>%s</h2><p>%d songs read: %d passed (%d of a band, a company or an act; %d of the house's own players), %d were held.</p>" % (
            name, len(mine), len(through), sum(len(each) for each in theirs.values()), len(own), len(held)))
        if theirs:
            parts.append("<h3>Passed, and waiting for your word</h3>")
            for who in sorted(theirs, key=lambda who: (-len(theirs[who]), who)):
                parts.append("<h4>%s</h4><table>%s</table>" % (html.escape(who), "\n".join(_row(each) for each in sorted(theirs[who], key=lambda each: -each["score"]))))
        if own:
            parts.append("<h3>Passed, the house's own players: in the player at its next build</h3><table>%s</table>" % "\n".join(_row(each) for each in sorted(own, key=lambda each: -each["score"])))
        if held:
            parts.append("<h3>Held</h3><p class=\"held\">%s</p>" % "; ".join("%s <small>(%s%.2f, memorability %.2f)</small>" % (
                html.escape(each["title"]), html.escape(each["whose"] + ", ") if each["whose"] else "", each["score"], each["memorability"]) for each in sorted(held, key=lambda each: -each["score"])))
    when = time.strftime("%d %B, %H:%M", time.localtime(now))
    return """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>What the judges passed</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:16px;background:#14161a;color:#e8e6e1}table{border-collapse:collapse;width:100%%}td{border-top:1px solid #333;padding:10px 8px;vertical-align:top;width:33%%}
audio{width:100%%;max-width:420px}small{color:#a8a59c}h1{font-size:22px}h2{font-size:20px;margin-top:28px}h3{font-size:17px;margin-top:20px}h4{font-size:16px;margin:14px 0 2px;text-transform:capitalize}
.held{color:#c9c6bd}@media(max-width:700px){td{display:block;border-top:0;width:auto}tr{display:block;border-top:1px solid #333;padding:6px 0}}</style>
<h1>What the judges passed</h1>
<p>Every new song is read by the judges and held to the songs you liked: it passes when it reads no worse than three in four of them. Nothing here is in the player yet.
A song of one of the new bands, companies or acts that passed is here for you to hear: say which bands may come in, or which songs. The house's own players' songs that passed come in by themselves at the next build.
Where a song was written again (its tune told plainly, in an even metre), the take you heard before is beside it.</p>
<p><small>Written %s, from the readings under %s.</small></p>
%s""" % (when, ", ".join(labels), "\n".join(parts) or "<p>Nothing has been read under these labels yet.</p>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The page of what the judges passed, for the listener.")
    parser.add_argument("labels", nargs="+", help="the labels the songs were read under (gate-1126)")
    parser.add_argument("--var", default=str(VAR))
    parser.add_argument("--log", default="")
    parser.add_argument("--out", default="gate.html", help="the page's name under var/listen")
    args = parser.parse_args(argv)
    var = Path(args.var)
    rows = gate.rows_of(Path(args.log) if args.log else var / "passes" / "judged3.jsonl")
    found = songs(var, rows, args.labels)
    out = var / "listen" / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch = out.with_name(out.name + ".part")
    scratch.write_text(page(found, args.labels), encoding="utf-8")
    scratch.replace(out)
    through = [each for each in found if each["passes"]]
    print("%s: %d songs read, %d passed (%d a band's, a company's or an act's), %d of them with the take of before beside" % (
        out, len(found), len(through), sum(1 for each in through if each["whose"]), sum(1 for each in through if each["before"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
