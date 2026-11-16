"""The desk: a track of music as a REAPER project, and its stems as REAPER renders them.

Everything that makes a sound is in REAPER. A sampled instrument is a REAPER track of REAPER's
own sampler (ReaSamplOmatic5000), one sampler to each recording's zone; a synth is the Surge XT
plug-in on a track with one of its patches; the effects are REAPER's and JSFX. Each instrument
is built once and kept as a track template (the same .RTrackTemplate file REAPER writes for
"Save track as template"), in var/reaper/templates.

A piece of music becomes a project file (.rpp, plain text): a folder track for each channel
the player has (texture, lead, rhythm, drums, bass), and under it a track for every instrument
line, made from its template with the notes written in. REAPER renders the five folder tracks
as five files. The project stays on disk beside them, so it can be opened in REAPER's window,
listened to, changed and rendered again by hand.
"""
from __future__ import annotations

import base64
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile

from . import reaper
from .samples import SAMPLES, Patch
from .score import Note

RATE = 48000
TICKS = 960                    # to a quarter note, in the notes REAPER is given
# Every project begins with this much silence, which is cut from what REAPER renders. Some
# instruments (the AVL drum kits, DrumGizmo) fetch their recordings when the first stretch of
# sound is asked of them, and play nothing in it: a note on the first beat would be lost.
LEAD = 1.0
VAR = Path(__file__).resolve().parents[3] / "var"
TEMPLATES = VAR / "reaper" / "templates"
LUA = Path(__file__).resolve().parent / "lua"
SURGE = reaper.TOOLS / "surge" / "share" / "surge-xt"
WAV_FLOAT = "ZXZhdyAAAA=="       # how REAPER writes "WAV, 32 bit floating point": a part that goes over full scale is not clipped
_LUA_WORDS = {"and", "break", "do", "else", "elseif", "end", "false", "for", "function", "goto", "if", "in", "local", "nil", "not",
              "or", "repeat", "return", "then", "true", "until", "while"}
_GUID = re.compile(r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}")


# ---------------------------------------------------------------------------------------------
# Building instruments
# ---------------------------------------------------------------------------------------------
def lua(value: object, depth: int = 0) -> str:
    """A Python value written as Lua."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    if isinstance(value, Path):
        return lua(str(value))
    pad = "  " * (depth + 1)
    if isinstance(value, dict):
        rows = []
        for key, each in value.items():
            plain = isinstance(key, str) and re.fullmatch(r"[A-Za-z_]\w*", key) and key not in _LUA_WORDS
            name = "[%d]" % key if isinstance(key, int) else key if plain else "[%s]" % lua(str(key))
            rows.append("%s%s = %s" % (pad, name, lua(each, depth + 1)))
        return "{\n%s\n%s}" % (",\n".join(rows), "  " * depth) if rows else "{}"
    if isinstance(value, (list, tuple)):
        return "{\n%s\n%s}" % (",\n".join(pad + lua(each, depth + 1) for each in value), "  " * depth) if value else "{}"
    raise TypeError("Cannot write %r as Lua" % (value,))


def sampler(patch: Patch, *, gain: float = 0.0, attack: float | None = None, release: float | None = None) -> list[dict]:
    """A patch as what the track builder is told: one of REAPER's samplers for each zone."""
    out = []
    for zone in patch.zones:
        out.append({"kind": "sampler", "files": [str(SAMPLES / file) for file in zone.files], "low": zone.low, "high": zone.high,
                    "root": zone.root, "soft": zone.soft, "hard": zone.hard, "tune": zone.tune, "gain": zone.gain + gain,
                    "attack": patch.attack if attack is None else attack, "release": patch.release if release is None else release,
                    "held": patch.held, "floor": patch.floor, "follow": zone.low != zone.high or patch.held})
        if zone.loop:
            out[-1].update(loop=zone.loop, cross=min(400.0, zone.loop * 0.5), **{"until": zone.until})
    return out


def surge(patch: str) -> dict:
    """The Surge XT synth with one of its patches: `patch` is a file under Surge's patch
    folders, for example "patches_factory/Pads/Aurora.fxp"."""
    path = SURGE / patch
    data = path.read_bytes()
    if data[:4] != b"CcnK" or data[8:12] != b"FPCh":
        raise ValueError("%s is not a Surge patch file" % path)
    # A patch file is a 60-byte wrapper around what the synth itself keeps as its state.
    return {"kind": "clap", "name": "CLAPi: Surge XT", "chunk": base64.b64encode(data[60:]).decode("ascii")}


def effect(name: str, *, params: dict[int, float] | None = None, values: dict[int, float] | None = None,
           named: list[tuple[str, object]] | None = None) -> dict:
    """An effect by the name REAPER knows it by ("ReaEQ", "JS: Saturation"), with its settings
    by number: `params` from 0 to 1, `values` in the effect's own units; and `named`, the
    settings that have names instead, told in the order given."""
    out: dict = {"kind": "fx", "name": name}
    if params:
        out["params"] = params
    if values:
        out["values"] = values
    if named:
        out["named"] = [[key, value] for key, value in named]
    return out


def reverb(impulse: Path) -> dict:
    """REAPER's convolution reverb playing an impulse response, giving only what the hall adds
    (whoever sends to it keeps their own sound on their own track)."""
    return effect("ReaVerb", named=[("ITEM0", 'FILELDR "%s" 60' % impulse), ("DONE", "")],
                  params={0: 0.5, 1: 0.0, 6: 0.0, 7: 0.0})      # wet at 0 dB, dry off, and the two low-latency modes off: nobody is playing live


def js(name: str, *settings: float | str) -> str:
    """One of REAPER's bundled JSFX effects as it is written in a project: its file under
    Effects ("sstillwell/hpflpf") and its sliders in order."""
    slots = ["%.6g" % each if isinstance(each, (int, float)) else '"%s"' % each for each in settings]
    return "<JS %s \"\"\n%s\n>\nWAK 0 0" % (name, " ".join(slots + ["-"] * (64 - len(slots))))


def make_tracks(tracks: list[dict], *, display: str, out: Path = TEMPLATES) -> str:
    """Has REAPER build each track ({"name": ..., "fx": [...]}) and save it as a template in
    `out`. Returns what the builder wrote down."""
    out.mkdir(parents=True, exist_ok=True)
    job = out / "make_tracks.job.lua"
    job.write_text("return " + lua({"out": str(out), "tracks": tracks}) + "\n", encoding="utf-8")
    done = out / "make_tracks.done"
    reaper.run([str(LUA / "make_tracks.lua")], display=display, work=out, timeout=90.0 + 0.05 * sum(len(each["fx"]) for each in tracks),
               env={"FREEROCK_JOB": str(job)}, done=done)
    notes = (out / "make_tracks.log").read_text(encoding="utf-8")
    if done.read_text(encoding="utf-8").strip() != "ok":
        raise RuntimeError("REAPER could not build every instrument:\n" + notes)
    return notes


def template(name: str, folder: Path = TEMPLATES) -> str:
    path = folder / (name + ".RTrackTemplate")
    if not path.is_file():
        raise FileNotFoundError("There is no instrument called %r in %s (build it first)" % (name, folder))
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# The plug-ins there are, and writing one into a project
# ---------------------------------------------------------------------------------------------
CATALOGUE = VAR / "reaper" / "catalogue.json"
_catalogue: dict[str, dict] | None = None


def plugins(*, display: str) -> list[tuple[str, str]]:
    """Every plug-in REAPER has found: (its name as REAPER shows it, how REAPER identifies it)."""
    out = VAR / "reaper" / "plugins.tsv"
    done = Path(str(out) + ".done")
    reaper.run([str(LUA / "list_plugins.lua")], display=display, work=out.parent, timeout=400.0, env={"FREEROCK_OUT": str(out)}, done=done)
    return [tuple(line.split("\t", 1)) for line in out.read_text(encoding="utf-8", errors="replace").splitlines() if "\t" in line]


def _read_chunk(text: str) -> dict | None:
    """What a track's state says about the one LV2 plug-in on it: name, URI, its settings in
    order with their starting values, and the lines of its saved state."""
    rows = text.split("\n")
    for at, row in enumerate(rows):
        if row.startswith("<LV2 "):
            found = re.match(r'<LV2 "(.*)" (\S+) ""', row)
            if not found:
                return None
            ports: list[list] = []
            state: list[str] = []
            other: list[str] = []           # whatever else REAPER wrote: where its notes come in, its outputs
            depth, inside = 1, False
            for each in rows[at + 1:]:
                if each.startswith("<STATE") and depth == 1:
                    inside, depth = True, depth + 1
                    continue
                if each.startswith("<"):
                    depth += 1
                elif each == ">":
                    depth -= 1
                    if depth == 0:
                        break
                    if inside and depth == 1:
                        inside = False
                        continue
                if inside:
                    state.append(each)
                elif each.startswith("P ") and depth == 1:
                    words = each.split()[1:]
                    ports += [[words[index], float(words[index + 1])] for index in range(0, len(words) - 1, 2)]
                else:
                    other.append(each)
            return {"name": found.group(1), "uri": found.group(2), "ports": ports, "state": state, "other": other}
    return None


def catalogue(names: list[str], *, display: str, batch: int = 40) -> dict[str, dict]:
    """Loads each named plug-in once in REAPER and keeps what was learned (catalogue.json):
    for every LV2 plug-in its settings by name with their starting values. A plug-in that
    brings REAPER down or makes it wait is noted as unusable and the rest go on."""
    work = VAR / "reaper" / "catalogue"
    work.mkdir(parents=True, exist_ok=True)
    known = json.loads(CATALOGUE.read_text(encoding="utf-8")) if CATALOGUE.is_file() else {}
    todo = [name for name in names if name not in known]
    at = 0
    while at < len(todo):
        some = todo[at:at + batch]
        for old in list(work.glob("*.chunk")) + [work / "describe.log", work / "describe.done"]:
            old.unlink(missing_ok=True)
        job = work / "describe.job.lua"
        job.write_text("return " + lua({"out": str(work), "first": 1, "names": some}) + "\n", encoding="utf-8")
        problem = None
        try:
            reaper.run([str(LUA / "describe_plugins.lua")], display=display, work=work, timeout=30.0 + 2.0 * len(some),
                       env={"FREEROCK_JOB": str(job)}, done=work / "describe.done")
        except RuntimeError as error:
            problem = error
        log = (work / "describe.log").read_text(encoding="utf-8", errors="replace").splitlines() if (work / "describe.log").is_file() else []
        finished = {int(line.split("\t")[1]) for line in log if line.startswith(("done\t", "missing\t"))}
        for number, name in enumerate(some, start=1):
            chunk = work / ("%d.chunk" % number)
            if chunk.is_file():
                read = _read_chunk(chunk.read_text(encoding="utf-8", errors="replace"))
                known[name] = read if read else {"name": name, "unusable": "REAPER does not write it as an LV2 plug-in"}
            elif number in finished:
                known[name] = {"name": name, "unusable": "REAPER could not load it"}
        if problem is not None or not (work / "describe.done").is_file():
            # The one that was being loaded when REAPER stopped is the culprit; go on after it.
            started = [int(line.split("\t")[1]) for line in log if line.startswith("loading\t")]
            culprit = max(started) if started else 1
            if culprit not in finished:
                known[some[culprit - 1]] = {"name": some[culprit - 1], "unusable": "REAPER stopped or waited while loading it"}
            at += culprit
        else:
            at += len(some)
        CATALOGUE.write_text(json.dumps(known, indent=1), encoding="utf-8")
    global _catalogue
    _catalogue = known
    return known


def lv2(name: str, **settings: float) -> str:
    """An LV2 plug-in as it is written in a project: found in the catalogue by a part of its
    name (which must fit exactly one plug-in), with its settings as they start out except the
    ones given here by their names (the port symbols the catalogue lists)."""
    global _catalogue
    if _catalogue is None:
        if not CATALOGUE.is_file():
            raise FileNotFoundError("The plug-ins have not been looked over yet (%s)" % CATALOGUE)
        _catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    fits = [each for key, each in _catalogue.items() if name.lower() in key.lower() and "uri" in each]
    exact = [each for each in fits if each["name"].split(" (")[0].split(": ", 1)[-1].lower() == name.lower()]
    if len(exact) == 1:
        fits = exact
    if len(fits) != 1:
        raise KeyError("%d usable plug-ins are called something like %r: %s" % (len(fits), name, [each["name"] for each in fits][:8]))
    found = fits[0]
    have = dict((symbol, value) for symbol, value in found["ports"])
    for symbol in settings:
        if symbol not in have:
            raise KeyError("%s has no setting %r; it has %s" % (found["name"], symbol, ", ".join(have)))
    have.update(settings)
    rows = ['<LV2 "%s" %s ""' % (found["name"], found["uri"])] + list(found.get("other") or ['CFG 0 0 0 ""'])
    pairs = ["%s %.9g" % (symbol, have[symbol]) for symbol, _ in found["ports"]]
    for start in range(0, len(pairs), 8):
        rows.append("P " + " ".join(pairs[start:start + 8]))
    if found["state"]:
        rows += ["<STATE"] + found["state"] + [">"]
    rows += [">", "WAK 0 0"]
    return "\n".join(rows)


def sfizz(instrument: Path) -> str:
    """The sfizz sampler playing an SFZ instrument file, as it is written in a project. Its
    settings are left exactly as it starts with them: asked for more than its usual 64 voices,
    it stops REAPER's render dead (found 2026-11-16, sfizz 1.2.3 in REAPER 7.86)."""
    return "\n".join([
        '<LV2 "LV2i: sfizz (SFZTools) (2 out)" http://sfztools.github.io/sfizz ""', 'CFG 0 0 0 ""', "MIDI control 0 0 ",
        "P volume 0 num_voices 64 oversampling 1 preload_size 8192 scala_root_key 60 tuning_frequency 440 stretched_tuning 0",
        # Rendering, it would use its costliest way of bending a recording to pitch (10); 3 is clean and twice as fast.
        "P sample_quality 2 oscillator_quality 1 freewheeling_sample_quality 3 freewheeling_oscillator_quality 3",
        "P sustain_cancels_release 0", "<STATE", 'P http://sfztools.github.io/sfizz:sfzfile "%s" 1' % instrument, ">", ">", "WAK 0 0"])


GEONKICK = Path("/usr/share/geonkick/presets")


def geonkick(preset: str) -> str:
    """The Geonkick drum synthesiser playing one of its presets ("SPKickPresetsVol1/kick-07":
    a file under its preset folder), as it is written in a project. It answers every key
    with that one drum; how hard the key is struck is how loud it is. A preset file is one
    instrument as the plug-in keeps it, and the plug-in's saved state is a kit of such
    instruments, so the state is written here from the preset."""
    path = GEONKICK / (preset + ".gkick")
    drum = json.loads(path.read_text(encoding="utf-8"))
    drum["kick"].update(id=0, channel=0, midiChannel=-1, noteOffEnabled=False, mute=False, solo=False, playing_key=-1)
    kit = json.dumps({"KitAppVersion": 198400, "name": Path(preset).name, "author": "", "url": "", "instruments": [drum]})
    packed = base64.b64encode(kit.encode("utf-8")).decode("ascii")
    rows = ['<LV2 "LV2i: Geonkick Single (Iurie Nistor) (4 out)" http://geonkick.org/geonkick/single ""', 'CFG 0 0 0 ""', "<OUT_PINS", ">",
            "MIDI midi_in 0 0 ", "<STATE", "<X http://geonkick.org/geonkick/single#state http://lv2plug.in/ns/ext/atom#Chunk 3"]
    rows += [packed[start:start + 280] for start in range(0, len(packed), 280)]
    return "\n".join(rows + [">", ">", ">", "WAK 0 0"])


def bare(name: str, effects: list[str]) -> str:
    """A track with these effects on it and nothing else, as a template: for instruments and
    effects that are written as text (`sfizz`, `lv2`, `js`)."""
    return "\n".join(["<TRACK", "NAME " + _quote(name), "VOLPAN 1 0 -1 -1 1", "ISBUS 0 0", "NCHAN 2", "FX 1", "MAINSEND 1 0",
                      "<FXCHAIN", "BYPASS 0 0 0"] + effects + [">", ">"]) + "\n"


def pruned(text: str, keep: set[int]) -> str:
    """A sampled instrument's template with only the samplers numbered in `keep` (counted from
    0 in the order they stand). An instrument has a sampler for every recording; a line that
    stays in one octave at one strength needs a handful of them, and a project with a tenth of
    the samplers loads and renders several times faster."""
    rows = text.rstrip().split("\n")
    try:
        first = rows.index("<FXCHAIN")
    except ValueError:
        return text
    depth, last = 0, None
    for at in range(first, len(rows)):
        if rows[at].startswith("<"):
            depth += 1
        elif rows[at] == ">":
            depth -= 1
            if depth == 0:
                last = at
                break
    if last is None:
        raise ValueError("The template's effects do not end")
    chain = rows[first + 1:last]
    starts = [index for index, row in enumerate(chain) if row.startswith("BYPASS ")]
    if not starts:
        return text
    out, number = chain[:starts[0]], -1
    for begin, end in zip(starts, starts[1:] + [len(chain)]):
        entry = chain[begin:end]
        if any("ReaSamplOmatic" in row for row in entry[:3]):
            number += 1
            if number not in keep:
                continue
        out += entry
    return "\n".join(rows[:first + 1] + out + rows[last:]) + "\n"


# ---------------------------------------------------------------------------------------------
# Writing a project
# ---------------------------------------------------------------------------------------------
@dataclass
class Line:
    """One track of a project: an instrument (or a bus) and what it plays."""
    name: str
    template: str                                                # the text of its track template
    notes: list[Note] = field(default_factory=list)              # in beats (quarter notes)
    volume: float = 1.0                                          # 1 is as the template has it
    pan: float = 0.0
    moves: list[tuple[float, float]] = field(default_factory=list)      # (beat, gain): the volume riding up and down
    controls: list[tuple[float, int, int]] = field(default_factory=list)   # (beat, controller, value 0 to 127): written among the notes
    early: float = 0.0                                           # seconds it is played ahead
    send: float = 0.0                                            # how much of it goes to its folder's hall (1 is all of it)
    effects: list[str] = field(default_factory=list)             # effects put after its own, as `js` writes them
    clips: list[tuple[float, float, str]] = field(default_factory=list)      # recordings laid on it: (seconds in, seconds long, file)


def _quote(text: str) -> str:
    clean = text.replace('"', "'").replace("\n", " ")
    return '"%s"' % clean


def _events(notes: list[Note], bpm: float, seconds: float, early: float, controls: list[tuple[float, int, int]] | None = None) -> list[str]:
    """The notes as REAPER writes them in a project: `E <ticks since the last> <status> <note> <strength>`,
    with the controller moves among them."""
    ahead = early * bpm / 60.0
    end = int(round(seconds * bpm / 60.0 * TICKS))
    spans: dict[int, list[list[int]]] = {}
    for note in sorted(notes, key=lambda each: each.start):
        on = min(max(int(round((note.start - ahead) * TICKS)), 0), end - 2)
        off = min(max(int(round((note.start - ahead + note.length) * TICKS)), on + 1), end - 1)
        same = spans.setdefault(note.pitch, [])
        # A note struck again before it has ended is ended first.
        if same and same[-1][1] > on - 1:
            same[-1][1] = max(on - 1, same[-1][0] + 1)
        if same and same[-1][0] >= on:
            continue
        same.append([on, off, min(max(int(round(note.loud * 127)), 1), 127)])
    events: list[tuple[int, int, str]] = []
    for pitch, played in spans.items():
        for on, off, loud in played:
            events.append((on, 2, "90 %02x %02x" % (pitch, loud)))
            events.append((off, 0, "80 %02x 00" % pitch))
    last: dict[int, int] = {}
    for beat, controller, value in sorted(controls or []):
        tick = min(max(int(round((beat - ahead) * TICKS)), 0), end - 2)
        value = min(max(int(round(value)), 0), 127)
        if last.get(controller) == value:
            continue
        last[controller] = value
        events.append((tick, 1, "b0 %02x %02x" % (controller, value)))      # a controller move at a note's start comes before the note
    events.sort()
    out, now = [], 0
    for tick, _, message in events:
        out.append("E %d %s" % (tick - now, message))
        now = tick
    out.append("E %d b0 7b 00" % max(end - now, 0))
    return out


def track(line: Line, *, bpm: float, seconds: float, folder: int = 0, selected: bool = False, number: int = 0,
          receives: list[tuple[int, float]] | None = None) -> str:
    """One track of the project as text: the template with its name, level, place in the
    folders, notes and volume moves written in. `receives` is what is sent to it from other
    tracks: (which track, counted from 0 down the project, how much of it)."""
    fresh: dict[str, str] = {}

    def renew(found: re.Match) -> str:
        old = found.group(0)
        if old not in fresh:
            fresh[old] = "{%s}" % str(uuid.uuid5(uuid.NAMESPACE_OID, "%s/%d/%s" % (line.name, number, old))).upper()
        return fresh[old]

    rows = _GUID.sub(renew, line.template).rstrip().split("\n")
    if not rows[0].startswith("<TRACK") or rows[-1].strip() != ">":
        raise ValueError("The template for %s is not a REAPER track" % line.name)
    gain, pan = line.volume, line.pan
    out = []
    depth, chained, placed = 0, False, False
    for row in rows[:-1]:
        word = row.strip().split(" ", 1)[0]
        if depth == 1:                         # the track's own settings, not those of something inside it
            if word == "NAME":
                row = "NAME " + _quote(line.name)
            elif word == "VOLPAN":
                had = row.split()
                row = "VOLPAN %.6f %.4f -1 -1 1" % (float(had[1]) * gain, pan)
            elif word == "ISBUS":
                # The template does not say whether the track is selected: that is said here,
                # since the selected tracks are the ones REAPER renders.
                row = ("ISBUS 1 1" if folder > 0 else "ISBUS 2 -1" if folder < 0 else "ISBUS 0 0") + "\nSEL %d" % (1 if selected else 0)
                for source, amount in receives or []:
                    row += "\nAUXRECV %d 0 %.6f 0 0 0 0 0 0 -1:U 0 -1 ''" % (source, amount)
            elif word in ("SEL", "AUXRECV"):
                continue
            elif word == "FX" and line.effects:
                row = "FX 1"
            elif word == "<FXCHAIN":
                chained = True
        if row.lstrip().startswith("<"):
            depth += 1
        elif row.strip() == ">":
            depth -= 1
            if depth == 1 and chained and not placed and line.effects:
                out += line.effects                 # after the track's own effects, inside its chain
                placed = True
        out.append(row)
    if depth != 1 or not any(row.startswith("ISBUS") for row in out):
        raise ValueError("The template for %s is not a whole REAPER track" % line.name)
    if line.effects and not placed:
        out += ["<FXCHAIN", "BYPASS 0 0 0"] + line.effects + [">"]
    if line.moves:
        ahead = line.early
        out += ["    <VOLENV2", "      ACT 1 -1", "      VIS 1 1 1", "      LANEHEIGHT 0 0", "      ARM 0", "      DEFSHAPE 0 -1 -1"]
        last = -1.0
        for beat, level in sorted(line.moves):
            at = max(beat * 60.0 / bpm - ahead, 0.0) + LEAD
            if at <= last:
                at = last + 0.001
            out.append("      PT %.4f %.5f 0" % (at, max(level, 0.0)))
            last = at
        out.append("    >")
    if line.notes:
        out += ["    <ITEM", "      POSITION %.6f" % LEAD, "      LENGTH %.6f" % seconds, "      LOOP 0", "      NAME " + _quote(line.name),
                "      <SOURCE MIDI", "        HASDATA 1 %d QN" % TICKS]
        out += ["        " + event for event in _events(line.notes, bpm, seconds, line.early, line.controls)]
        out += ["      >", "    >"]
    for at, long, file in line.clips:
        out += ["    <ITEM", "      POSITION %.6f" % (at + LEAD), "      LENGTH %.6f" % long, "      LOOP 0", "      <SOURCE WAVE",
                "        FILE " + _quote(file), "      >", "    >"]
    out.append("  >")
    return "\n".join(out)


def project(folders: list[tuple[Line, list[Line]]], *, bpm: float, seconds: float, out: Path, tail: float = 0.0,
            hall: str | None = None) -> str:
    """A whole project as text: each folder (a bus track and the tracks under it) one after the
    other, set up to render every folder as its own file, `seconds` long plus `tail` (after
    LEAD seconds of silence, which `stems` and `heard` take off again), into `out`, 48 kHz,
    named after the folder. With `hall` (the template of a reverb track), every
    folder gets a hall of its own as its last track, and each track under the folder sends to
    it as much as its `send` says: so each rendered file carries its own share of the room."""
    rows = ['<REAPER_PROJECT 0.1 "7.86/linux-x86_64" 0 0', "  RIPPLE 0 0", "  AUTOXFADE 129", "  PANLAW 1", "  PANMODE 3",
            "  SAMPLERATE %d 0 0" % RATE,
            "  RENDER_FILE " + _quote(str(out)), "  RENDER_PATTERN $track", "  RENDER_FMT 0 2 %d" % RATE, "  RENDER_1X 0 0",
            "  RENDER_RANGE 0 0 %.6f 0 0" % (LEAD + seconds + tail), "  RENDER_RESAMPLE 3 0 1", "  RENDER_ADDTOPROJ 0", "  RENDER_STEMS 3",
            "  RENDER_DITHER 0", "  <RENDER_CFG", "    %s" % WAV_FLOAT, "  >",
            "  TEMPO %.6f 4 4 0" % bpm, "  MASTER_NCH 2 2", "  MASTER_VOLUME 1 0 -1 -1 1"]
    number = 0
    for bus, lines in folders:
        if not lines:
            continue
        number += 1
        rows.append(track(bus, bpm=bpm, seconds=seconds, folder=1, selected=True, number=number))
        sends = []
        for index, line in enumerate(lines):
            number += 1
            last = index == len(lines) - 1 and hall is None
            rows.append(track(line, bpm=bpm, seconds=seconds, folder=-1 if last else 0, number=number))
            if line.send > 0.0:
                sends.append((number - 1, line.send))          # tracks are counted from 0 down the project
        if hall is not None:
            number += 1
            rows.append(track(Line(bus.name + " hall", hall), bpm=bpm, seconds=seconds, folder=-1, number=number, receives=sends))
    rows.append(">")
    return "\n".join(rows) + "\n"


def project_flat(folders: list[tuple[Line, list[Line]]], *, bpm: float, seconds: float, out: Path, tail: float = 0.0) -> str:
    """A project of tracks that stand alone, each rendered as its own file: for hearing
    instruments one by one. Takes the same list as `project`, with nothing under any track."""
    whole = project([], bpm=bpm, seconds=seconds, out=out, tail=tail).rstrip().split("\n")[:-1]
    for number, (line, under) in enumerate(folders):
        if under:
            raise ValueError("project_flat is for tracks with nothing under them")
        whole.append(track(line, bpm=bpm, seconds=seconds, selected=True, number=number + 1))
    whole.append(">")
    return "\n".join(whole) + "\n"


def render(rpp: Path, *, display: str, timeout: float = 600.0) -> None:
    """Has REAPER render a project as the project says. REAPER ends by itself when it is done;
    if something is wrong with the project it puts up a message and waits, which the time
    limit ends, leaving a picture of the message."""
    reaper.run(["-renderproject", str(rpp)], display=display, work=rpp.parent, timeout=timeout)


def heard(path: Path) -> np.ndarray:
    """One file REAPER rendered, without the silence every project begins with."""
    if not path.is_file():
        raise FileNotFoundError("REAPER did not render %s" % path)
    audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    if rate != RATE:
        raise RuntimeError("REAPER rendered %s at %d Hz, not %d" % (path, rate, RATE))
    return audio[int(round(LEAD * RATE)):]


def stems(folder: Path, names: list[str], frames: int) -> dict[str, np.ndarray]:
    """The files REAPER rendered into `folder`, by name, each exactly `frames` long."""
    out = {}
    for name in names:
        audio = heard(folder / (name + ".wav"))
        if len(audio) < frames:
            audio = np.concatenate([audio, np.zeros((frames - len(audio), audio.shape[1]), dtype=np.float32)])
        out[name] = audio[:frames]
    return out
