"""Three judges that listen to a staged take (2026-11-19: "find out if there are packages python or otherwise that are
somehow subjective about music sounding good for a genre", "use the best 3 and use the output to improve the songs", "add it
to the recursive loop for all genres"; docs/plan.md, "Judges that listen").

- **TuneJury** (Carnegie Mellon and Sony AI, 2026; github.com/yonghyunk1m/TuneJury, weights CC BY-NC 4.0): a text brief and
  the music in, how much a listener would prefer it out, learned from about 17,500 human choices between two pieces (Music
  Arena, MusicPrefs, AIME, SongEval). It hears through LAION-CLAP-Music and MERT-v1-330M and was made for instrumental
  music. Each style is judged against its own brief (`BRIEFS`), so it judges a take as music of its kind; the empty brief
  is scored as well (the authors' safe reading where a brief is far from what it learned from).
- **SongEval** (ASLP at NPU, 2025; github.com/ASLP-lab/SongEval, CC BY-NC-SA 4.0): five aesthetic scores learned from
  professional listeners' ratings of 2,399 whole songs: coherence, musicality, memorability, clarity of structure, and the
  naturalness of a singer's breathing, which means nothing for music without a voice and is kept only as recorded. It
  hears through MuQ (large, MSD).
- **Audiobox Aesthetics** (Meta, 2025, CC BY 4.0): enjoyment of the content (CE), its usefulness (CU), the production's
  complexity (PC) and quality (PQ).

None of them was trained on long instrumental game music or on stems, and two hear only through encoders made for clips: so
they are voters and pointers, never targets (the plan). A take is its five stems summed and set to one loudness. TuneJury and
Audiobox hear twenty seconds from the middle of each part of the story; SongEval hears two minutes from the first theme on.
Each take is one line in var/passes/judged3.jsonl. All of it runs on this machine; no audio leaves it.

    "var/tools/judges/.venv/bin/python" tools/judges.py knight/pastoral-banner-ride-1/5 house/coast-03/1 ...
    ... --folder <a staged take's folder, a demo's> [--label "the licks, after"]   (--threads N, default 4)
    ... --watch --since "2026-11-19 08:30"      the loop: every take of every style staged (or made again) since then and
                                                 not judged since, newest first, the list read again after each; looks again
                                                 every 5 minutes when none is waiting
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("WANDB_MODE", "disabled")           # laion_clap brings wandb with it; nothing is ever logged anywhere
os.environ.setdefault("WANDB_SILENT", "true")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import numpy as np
import soundfile

ROOT = Path(__file__).resolve().parents[1]
VAR = ROOT / "var"
JUDGES = VAR / "tools" / "judges" / "src"
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
EXCERPT_S = 20.0             # what TuneJury and Audiobox hear of each part of the story
SONG_S = 120.0               # what SongEval hears, from the first theme on
LEVEL_DB = -20.0             # every excerpt brought to this RMS level, so that loudness does not sway a judge
# The brief each style is judged against: what the music is meant to be, in the words a listener would use.
BRIEFS = {
    "knight": "instrumental 1970s hard rock, a riff band with crunchy rhythm guitars, bass and drums, guitar licks and a guitar solo",
    "warcraft": "instrumental orchestral fantasy adventure game soundtrack with strings, brass, choir and war drums",
    "house": "instrumental progressive house, four-on-the-floor kick, big synths, risers and drops",
}
SONGEVAL_AXES = ("Coherence", "Musicality", "Memorability", "Clarity", "Naturalness")
AUDIOBOX_AXES = ("CE", "CU", "PC", "PQ")


def mix(folder: Path) -> tuple[np.ndarray, int]:
    """The take as the player plays it at its full mix: its five stems summed."""
    parts, rate = [], 48000
    for channel in CHANNELS:
        path = folder / (channel + ".flac")
        if path.is_file():
            audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
            parts.append(audio)
    if not parts:
        raise FileNotFoundError("no stems in %s" % folder)
    length = max(len(part) for part in parts)
    return sum(np.pad(part, ((0, length - len(part)), (0, 0))) for part in parts), rate


def level(audio: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    if rms <= 1e-6:
        return audio
    return np.clip(audio * (10 ** (LEVEL_DB / 20.0) / rms), -1.0, 1.0).astype(np.float32)


def parts_of(meta: dict, audio: np.ndarray, rate: int, names: list[str] | None = None) -> list[tuple[str, np.ndarray]]:
    """Twenty seconds from the middle of each part of the story (the whole part where it is shorter, none under five seconds),
    by the part's own name on the sheet (open, first, second, build, arrival, valley, climb, summit, close); a take without a
    sheet numbers its story's words (a story has three themes, two rises and two moments: 2026-11-19, by the story word alone
    the later parts had stood in for the earlier)."""
    out, at = [], 0
    seen: dict[str, int] = {}
    for index, section in enumerate(meta["sections"]):
        frames = int(round(section["bars"] * meta["bar_frames"]))
        piece = audio[at:at + frames]
        at += frames
        if names and index < len(names):
            name = names[index]
        else:
            seen[section["story"]] = seen.get(section["story"], 0) + 1
            name = "%s %d" % (section["story"], seen[section["story"]])
        if len(piece) < 5 * rate:
            continue
        keep = int(EXCERPT_S * rate)
        if len(piece) > keep:
            start = (len(piece) - keep) // 2
            piece = piece[start:start + keep]
        out.append((name, level(piece)))
    return out


def song_of(meta: dict, audio: np.ndarray, rate: int) -> np.ndarray:
    """Two minutes from where the first theme begins (after the opening)."""
    opening = meta["sections"][0]
    start = int(round(opening["bars"] * meta["bar_frames"])) if opening["story"] == "open" else 0
    return level(audio[start:start + int(SONG_S * rate)])


class Bench:
    """The three judges, loaded once; or SongEval alone (`only="songeval"`), which is all the gate reads (tools/gate.py): a whole take
    in a minute or two, where the three take twenty."""

    def __init__(self, threads: int, only: str = "") -> None:
        import torch
        torch.set_num_threads(threads)
        self.torch = torch
        if only not in ("", "songeval"):
            raise ValueError("--only is songeval or nothing, not %r" % only)
        self.only = only
        self.tunejury = self.audiobox = None
        if not only:
            sys.path.insert(0, str(JUDGES / "TuneJury"))
            from tunejury import Scorer
            self.tunejury = Scorer.from_pretrained(str(JUDGES / "TuneJury" / "checkpoints" / "tunejury.pt"), device="cpu")
        sys.path.insert(0, str(JUDGES / "SongEval"))
        from hydra.utils import instantiate
        from muq import MuQ
        from omegaconf import OmegaConf
        from safetensors.torch import load_file
        config = OmegaConf.load(str(JUDGES / "SongEval" / "config.yaml"))
        self.songeval = instantiate(config.generator).eval()
        self.songeval.load_state_dict(load_file(str(JUDGES / "SongEval" / "ckpt" / "model.safetensors"), device="cpu"), strict=False)
        self.muq = MuQ.from_pretrained("OpenMuQ/MuQ-large-msd-iter").eval()
        if not only:
            from audiobox_aesthetics.infer import initialize_predictor
            self.audiobox = initialize_predictor()

    def tune(self, audio: np.ndarray, rate: int, brief: str) -> float:
        return round(float(self.tunejury.score_waveform(audio.T, rate, text=brief)), 4)

    def song(self, audio: np.ndarray, rate: int) -> dict[str, float]:
        import librosa
        mono = librosa.resample(audio.mean(axis=1), orig_sr=rate, target_sr=24000)
        with self.torch.no_grad():
            hidden = self.muq(self.torch.tensor(mono).unsqueeze(0), output_hidden_states=True)["hidden_states"][6]
            scores = self.songeval(hidden).squeeze(0)
        return {axis: round(float(scores[index]), 3) for index, axis in enumerate(SONGEVAL_AXES)}

    def box(self, audio: np.ndarray, rate: int) -> dict[str, float]:
        wav = self.torch.from_numpy(np.ascontiguousarray(audio.T))
        found = self.audiobox.forward([{"path": wav, "sample_rate": rate}])[0]
        return {axis: round(float(found[axis]), 2) for axis in AUDIOBOX_AXES}


def judge(bench: Bench, folder: Path, label: str = "") -> dict:
    began = time.time()
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    style = folder.parent.parent.name if folder.parent.parent.name in BRIEFS else meta.get("style", "knight")
    audio, rate = mix(folder)
    sheet = folder / "sheet.json"
    form = json.loads(sheet.read_text(encoding="utf-8")).get("form", []) if sheet.is_file() else []
    # (A House sheet's form does not name its parts as the orchestra's does: its story's words are numbered instead.)
    names = [part["part"] for part in form] if form and all(isinstance(part, dict) and "part" in part for part in form) else None
    song = bench.song(song_of(meta, audio, rate), rate)
    mean = lambda values: round(float(np.mean(values)), 4) if values else None
    record = {
        "at": datetime.datetime.now().isoformat(timespec="minutes"), "folder": str(folder.resolve()), "style": style,
        "take": "%s/%s" % (folder.parent.name, folder.name), "title": meta.get("title", ""), "label": label,
        "songeval": song,
    }
    if not bench.only:
        pieces = parts_of(meta, audio, rate, names)
        brief = BRIEFS.get(style, "")
        tune = {part: {"brief": bench.tune(piece, rate, brief), "plain": bench.tune(piece, rate, "")} for part, piece in pieces}
        box = {part: bench.box(piece, rate) for part, piece in pieces}
        record["tunejury"] = {"brief": mean([each["brief"] for each in tune.values()]), "plain": mean([each["plain"] for each in tune.values()]), "parts": tune}
        record["audiobox"] = {"mean": {axis: mean([each[axis] for each in box.values()]) for axis in AUDIOBOX_AXES}, "parts": box}
    else:
        record["only"] = bench.only
    record["seconds"] = round(time.time() - began)
    with (VAR / "passes" / "judged3.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")
    return record


def line(record: dict) -> str:
    song = record["songeval"]
    if "tunejury" not in record:          # SongEval alone (--only songeval)
        return ("%-34s %-26s SongEval mean %.2f  mus %.2f mem %.2f coh %.2f clar %.2f nat %.2f  %s  (%d s)"
                % (record["take"], record["title"][:26], sum(song.values()) / len(song), song["Musicality"], song["Memorability"], song["Coherence"],
                   song["Clarity"], song["Naturalness"], record["label"], record["seconds"]))
    tune, box = record["tunejury"], record["audiobox"]["mean"]
    return ("%-34s %-26s TuneJury %+.3f (plain %+.3f)  SongEval mus %.2f mem %.2f coh %.2f clar %.2f  Audiobox CE %.2f PQ %.2f  %s"
            % (record["take"], record["title"][:26], tune["brief"], tune["plain"], song["Musicality"], song["Memorability"],
               song["Coherence"], song["Clarity"], box["CE"], box["PQ"], record["label"]))


def waiting(since: float) -> list[Path]:
    """The staged takes of every style written since a time and not judged since they were written, newest first: a
    judgment takes ten to twenty-five minutes beside the renders, about as long as a take takes to make, so the newest
    code is heard first and the older takes are judged as the time allows."""
    judged: dict[str, float] = {}
    log = VAR / "passes" / "judged3.jsonl"
    if log.exists():
        for number, row in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
            if not row.strip():
                continue
            try:
                record = json.loads(row)
            except ValueError as error:
                raise ValueError("%s, line %d is not a record (%s): the log has been written by two at once, or cut short" % (log, number, error)) from error
            at = datetime.datetime.fromisoformat(record["at"]).timestamp()
            judged[record["folder"]] = max(judged.get(record["folder"], 0.0), at)
    found = []
    for meta in (VAR / "studio").glob("*/*/*/track.json"):
        made = meta.stat().st_mtime
        folder = meta.parent.resolve()
        if made >= since and judged.get(str(folder), 0.0) < made - 60 and any((folder / (c + ".flac")).is_file() for c in CHANNELS):
            found.append((made, folder))
    return [folder for _, folder in sorted(found, reverse=True)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TuneJury, SongEval and Audiobox Aesthetics on staged takes.")
    parser.add_argument("takes", nargs="*", help='staged takes: "knight/pastoral-banner-ride-1/5"')
    parser.add_argument("--folder", action="append", default=[], help="a staged take's folder, anywhere (a demo's)")
    parser.add_argument("--label", default="", help="a word kept with each record (\"before\", \"after\")")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--only", default="", help='"songeval": that judge alone, which is all tools/gate.py reads: a whole take in a minute or two')
    parser.add_argument("--watch", action="store_true", help="judge every take staged since --since as it comes, for good")
    parser.add_argument("--since", default="", help='"YYYY-MM-DD HH:MM" (with --watch; default: now)')
    args = parser.parse_args(argv)
    folders = [VAR / "studio" / take for take in args.takes] + [Path(folder) for folder in args.folder]
    if not folders and not args.watch:
        parser.print_help()
        return 2
    bench = Bench(args.threads, args.only)
    # (2026-11-26, the audit: one take that could not be judged ended the whole list, and the watch for good: it had been dead since 11-23, 20:00, and
    # no new take was judged whole after that.) A take that fails is said with its error, the others are judged, and the command ends with 1.
    failed: list[Path] = []
    for folder in folders:
        try:
            print(line(judge(bench, folder, args.label)), flush=True)
        except Exception:
            failed.append(folder)
            print("FAILED %s\n%s" % (folder, traceback.format_exc()), flush=True)
    if args.watch:
        since = datetime.datetime.fromisoformat(args.since).timestamp() if args.since else time.time()
        failed_as: dict[Path, float] = {}          # a take that failed, as it was written then: tried again only when it is written again
        while True:
            # A take still being written has its stems replaced one by one: only one written a minute ago or more. The list
            # is read again after every judgment, so a take staged meanwhile is next.
            ready = [folder for folder in waiting(since) if time.time() - (folder / "track.json").stat().st_mtime >= 60
                     and failed_as.get(folder) != (folder / "track.json").stat().st_mtime]
            if not ready:
                time.sleep(300)
                continue
            try:
                print(line(judge(bench, ready[0], args.label)), flush=True)
            except Exception:
                failed_as[ready[0]] = (ready[0] / "track.json").stat().st_mtime
                print("FAILED %s\n%s" % (ready[0], traceback.format_exc()), flush=True)
    if failed:
        print("%d could not be judged: %s" % (len(failed), ", ".join(str(folder) for folder in failed)), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
