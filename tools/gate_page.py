"""The page of what the judges passed, for the listener (var/listen/gate.html).

(2026-11-26, the audit after "most of the music we heard last night sucked, the new bands a lot of time just sound random": every new song is held to
the liked library by the judges (tools/gate.py), and of the first twenty-eight new Knight Rock songs they read, the seven that passed were every one
a band's. A band's, a company's or an act's song does not come into the player on the judges' word alone: the listener hears the ones that passed and
says. This is the page they hear them on.)

    cd app && uv run --no-sync python ../tools/gate_page.py gate-1126 [gate-1127 ...] [--only]
        (the labels given and every other gate label the log has, so that whichever copy of the gate writes it, the page is of all that
        waits for the listener; --only: the labels given alone)

For the labels given, a style at a time: the songs that passed and have been let into the player (tools/rest.py back writes them down); the songs that
passed and are a band's, a company's or an act's and wait for the listener's word, band by band; each to listen to (its whole
file on the listening pages, var/listen/<style>/, written here where it is missing or older than the take); where a song was written again, the take
of before beside it (kept under var/studio-demo/retold-audit-1126/resting; its whole file is written to var/listen/gate/); then the house's own
players' songs that passed (they come into the player at the next build); then, by name and number only, the ones that were held. A song whose
reading was made before it was performed again is not on the page (gate.standing).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
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


def mixed(folder: Path, out: Path) -> bool:
    """Writes a take's channels together as one file to listen to, as the listening pages write a whole file (tools/listen.py: the channels summed, the
    loudest sample at 0.89, FLAC). False, and nothing written, where the folder has no recordings."""
    import numpy as np
    import soundfile
    parts = [soundfile.read(str(Path(folder) / (channel + ".flac")), dtype="float32", always_2d=True) for channel in CHANNELS if (Path(folder) / (channel + ".flac")).is_file()]
    if not parts:
        return False
    rate = parts[0][1]
    length = max(len(audio) for audio, _ in parts)
    mix = sum(np.pad(audio, ((0, length - len(audio)), (0, 0))) for audio, _ in parts)
    peak = float(np.abs(mix).max())
    if peak <= 0.0:
        raise ValueError("The take in %s is silent" % folder)
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch = out.with_name(out.stem + ".%d.part.flac" % os.getpid())
    soundfile.write(str(scratch), mix * (0.89 / peak), rate, format="FLAC", subtype="PCM_16")
    scratch.replace(out)
    return True


def whole_of(var: Path, style: str, take: str, write: bool = False) -> tuple[str, bool]:
    """A staged take's whole file on the listening pages, as a path from var/listen ("" where there is none), and whether it is older than the take as it
    is staged (the take was performed again since the file was written). With `write`, a file that is missing or older is written first, here, from the
    take's channels (2026-11-26: the first song written again that passed stood on the page with the file of the take before it: the listening pages'
    own pass over everything had not come to it in three hours)."""
    meta = staged(var, style, take)
    if not meta:
        return "", False
    name = "%s - take %s (%s).flac" % (meta["title"], meta["take"], meta["family"])       # (tools/listen.py, `names`)
    path = Path(var) / "listen" / style / name
    made = (Path(var) / "studio" / style / take / "track.json").stat().st_mtime
    if write and (not path.is_file() or path.stat().st_mtime < made):
        mixed(Path(var) / "studio" / style / take, path)
    if not path.is_file():
        return "", False
    return "%s/%s" % (style, name), path.stat().st_mtime < made


def before_of(var: Path, style: str, take: str) -> str:
    """The whole file of the take of before a song was written again, as a path from var/listen, written from its kept channels if it is not there or is
    older than them; "" where no take of before is kept."""
    kept = Path(var).joinpath(*BEFORE) / style / take
    if not (kept / "track.json").is_file():
        return ""
    out = Path(var) / "listen" / "gate" / ("%s--%s--before.flac" % (style, take.replace("/", "--")))
    if out.is_file() and out.stat().st_mtime >= (kept / "track.json").stat().st_mtime:
        return "gate/" + out.name
    if not mixed(kept, out):
        raise ValueError("The take of before kept in %s has no recordings" % kept)
    return "gate/" + out.name


GATE_LABEL = re.compile(r"^gate-\d{4}$")         # the gate's own labels: gate-<month><day> (gate-1126); not the watch's, a demo's or a revision's


def every_label(rows: list[dict], given: list[str]) -> list[str]:
    """The labels given and every other gate label the log has, the one read most lately last: a song read under two counts by the newer.
    (2026-11-28: the day's gate copy and the night's each wrote this page of their own labels only, one over the other, so what waited for the
    listener's word went from 82 songs to 57 and back as they took turns.)"""
    latest: dict[str, str] = {}
    for row in rows:
        label = str(row.get("label") or "")
        if GATE_LABEL.match(label) or label in given:
            latest[label] = max(latest.get(label, ""), str(row.get("at") or ""))
    for label in given:
        latest.setdefault(label, "")
    return sorted(latest, key=lambda label: (latest[label], label))


def songs(var: Path, rows: list[dict], labels: list[str]) -> list[dict]:
    """Every song read under the labels as the gate has it (a song read under two labels counts by its newer reading, and by the later label given where
    the two were read at one time): its verdict, whose it is, what to listen to, and the take of before where it was written again."""
    by: dict[tuple[str, str], dict] = {}
    when: dict[tuple[str, str], str] = {}
    for label in labels:
        kept, _ = gate.standing(rows, label)
        read_at: dict[tuple[str, str], str] = {}
        for row in kept:
            if row.get("label") == label:
                key = (row.get("style"), row.get("take"))
                read_at[key] = max(read_at.get(key, ""), str(row.get("at") or ""))
        found = gate.check(kept, label)
        through = set(gate.passed(found))
        for each in found:
            key = (each["style"], each["take"])
            at = read_at.get(key, "")
            if key in by and at < when[key]:
                continue                               # (read more lately under another label: that reading counts)
            by[key], when[key] = dict(each, label=label, passes=each["take"] in through), at
    out = []
    inside: dict[str, set[str]] = {}
    for (style, take), each in sorted(by.items()):
        meta = staged(var, style, take)
        if not meta:
            continue                                   # (read and since taken away: nothing to listen to)
        whole, stale = whole_of(var, style, take, write=each["passes"])
        each.update(whose=gate.whose(var, style, take), inside=take in inside.setdefault(style, gate.let_in(var, style)), whole=whole, stale=stale,
                    title=meta.get("title") or each.get("title") or take,
                    tempo=meta.get("tempo"), metre=metre_of(Path(var) / "studio" / style / take),
                    before=before_of(var, style, take) if each["passes"] else "",
                    before_metre=metre_of(Path(var).joinpath(*BEFORE) / style / take))
        out.append(each)
    return out


def _row(each: dict, who: bool = False) -> str:
    said = "the judges %.2f, memorability %.2f" % (each["score"], each["memorability"])     # (the bar is said once a style, 2026-11-27: it stood on all 123 rows, two lines of every one on a phone)
    about = " · ".join(part for part in ("%.0f to the minute" % each["tempo"] if each.get("tempo") else "", "in " + each["metre"] if each["metre"] else "") if part)
    if each["whole"]:
        now = '<audio controls preload="none" src="%s"></audio>' % quote(each["whole"])
        if each["stale"]:
            now += "<br><small>this file is of the take before it was performed again: the new one is written within the half hour</small>"
    else:
        now = "<small>(its file to listen to is not written yet: within the half hour)</small>"
    by = " · the %s" % html.escape(each["whose"]) if who and each["whose"] else ""
    cells = "<td><b>%s</b><br><small>%s%s</small><br>%s</td><td>%s%s</td>" % (
        html.escape(each["title"]), html.escape(each["take"]), by, said, ("<small>%s</small><br>" % html.escape(about)) if about else "", now)
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
        inside = [each for each in through if each["inside"]]
        theirs: dict[str, list[dict]] = defaultdict(list)
        for each in through:
            if each["whose"] and not each["inside"]:
                theirs[each["whose"]].append(each)
        own = [each for each in through if not each["whose"] and not each["inside"]]
        held = [each for each in mine if not each["passes"]]
        bars = [each["bar"] for each in mine if each["bar"]]
        held_at = (" A song of this style passes when the judges give it %.2f and its memorability %.2f, which is where the songs you liked stand three in four of the way down." %
                   (bars[0]["score"], bars[0]["memorability"])) if bars else ""
        parts.append("<h2>%s</h2><p>%d songs read: %d passed (%d let into the player; %d of a band, a company or an act waiting for your word; %d of the house's own players for the next build), %d were held.%s</p>" % (
            name, len(mine), len(through), len(inside), sum(len(each) for each in theirs.values()), len(own), len(held), held_at))
        if inside:
            parts.append("<h3>Passed, and let into the player</h3><table>%s</table>" % "\n".join(_row(each, who=True) for each in sorted(inside, key=lambda each: -each["score"])))
        if theirs:
            parts.append("<h3>Passed, and waiting for your word</h3>")
            # (2026-11-27: 57 songs waited here at once, which is 57 decisions. A band is one decision, so each band says how ALL of its songs
            # read in this style — the held ones too — and they stand best band first. "Yes to the baroque" is the answer this page wants.)
            allof: dict[str, list[dict]] = defaultdict(list)
            for each in mine:
                if each["whose"]:
                    allof[each["whose"]].append(each)
            def standing(who: str) -> float:
                return sum(each["score"] for each in allof[who]) / len(allof[who])
            for who in sorted(theirs, key=lambda who: (-standing(who), who)):
                every = allof[who]
                through_ = [each for each in every if each["passes"]]
                parts.append("<h4>%s</h4><p class=\"band\">%d of its songs read, %d passed; they read <b>%.2f</b> on average (the bar is above). %d %s waiting for your word.</p><table>%s</table>" % (
                    html.escape(who), len(every), len(through_), standing(who),
                    len(theirs[who]), "is" if len(theirs[who]) == 1 else "are",
                    "\n".join(_row(each) for each in sorted(theirs[who], key=lambda each: -each["score"]))))
        if own:
            parts.append("<h3>Passed, the house's own players: in the player at its next build</h3><table>%s</table>" % "\n".join(_row(each) for each in sorted(own, key=lambda each: -each["score"])))
        if held:
            parts.append("<h3>Held</h3><p class=\"held\">%s</p>" % "; ".join("%s <small>(%s%.2f, memorability %.2f)</small>" % (
                html.escape(each["title"]), html.escape(each["whose"] + ", ") if each["whose"] else "", each["score"], each["memorability"]) for each in sorted(held, key=lambda each: -each["score"])))
    when = time.strftime("%d %B, %H:%M", time.localtime(now))
    return """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>What the judges passed</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:16px;background:#14161a;color:#e8e6e1}table{border-collapse:collapse;width:100%%}td{border-top:1px solid #333;padding:10px 8px;vertical-align:top;width:33%%}
audio{width:100%%;max-width:420px}small{color:#a8a59c}h1{font-size:22px}h2{font-size:20px;margin-top:28px}h3{font-size:17px;margin-top:20px}h4{font-size:16px;margin:14px 0 2px;text-transform:capitalize}
.held{color:#c9c6bd}.band{color:#a8a59c;font-size:14px;margin:0 0 6px}.band b{color:#e8e6e1}@media(max-width:700px){td{display:block;border-top:0;width:auto}tr{display:block;border-top:1px solid #333;padding:6px 0}}</style>
<h1>What the judges passed</h1>
<p>Every new song is read by the judges and held to the songs you liked: it passes when it reads no worse than three in four of them. Until then it is not in the player.
A song of one of the new bands, companies or acts that passed is here for you to hear: say which bands may come in, or which songs; the ones you have let in are first.
The house's own players' songs that passed come in by themselves at the next build. Where a song was written again (its tune told plainly, in an even metre), the take you heard before is beside it.</p>
<p><small>Written %s, from the readings under %s.</small></p>
%s""" % (when, ", ".join(labels), "\n".join(parts) or "<p>Nothing has been read under these labels yet.</p>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The page of what the judges passed, for the listener.")
    parser.add_argument("labels", nargs="+", help="the labels the songs were read under (gate-1126)")
    parser.add_argument("--only", action="store_true", help="only the labels given, not every gate label the log has")
    parser.add_argument("--var", default=str(VAR))
    parser.add_argument("--log", default="")
    parser.add_argument("--out", default="gate.html", help="the page's name under var/listen")
    args = parser.parse_args(argv)
    var = Path(args.var)
    rows = gate.rows_of(Path(args.log) if args.log else var / "passes" / "judged3.jsonl")
    labels = list(args.labels) if args.only else every_label(rows, args.labels)
    found = songs(var, rows, labels)
    out = var / "listen" / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch = out.with_name(out.name + ".part")
    scratch.write_text(page(found, labels), encoding="utf-8")
    scratch.replace(out)
    through = [each for each in found if each["passes"]]
    print("%s: %d songs read, %d passed (%d let in; %d a band's, a company's or an act's waiting), %d of them with the take of before beside" % (
        out, len(found), len(through), sum(1 for each in through if each["inside"]), sum(1 for each in through if each["whose"] and not each["inside"]),
        sum(1 for each in through if each["before"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
