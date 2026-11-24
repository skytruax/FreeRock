"""How hard, dark and raw a song sounds against how soft, sweet and cheesy (2026-11-24: House heard as sweet, twice). The judges' model that hears audio against words (LAION-CLAP's music
checkpoint, the one TuneJury hears through; tools/judges.py) scores ten seconds of the song's drops and of its themes against three pairs of descriptions; each axis is the one side less the other, times
a hundred, and the windows are always the same, so the same audio has the same score. Of the House staged that day the sweet songs stood at -9 to -18 and the hard ones' drops at +1 to +11. A pointer,
never a target: it says which songs to listen to first. All of it runs on this machine; no audio leaves it.

    "var/tools/judges/.venv/bin/python" tools/hardness.py house/regal-08/1 house/coast-03/1 ...
    ... --folder <a staged take's folder, a demo's> [--channel lead,bass] [--without lead] [--windows 2] [--threads 2] [--label "before"]

One line for each, and one record in var/passes/hardness.jsonl."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("WANDB_MODE", "disabled")           # laion_clap brings wandb with it; nothing is ever logged anywhere
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import numpy as np
import soundfile

ROOT = Path(__file__).resolve().parents[1]
VAR = ROOT / "var"
CHECKPOINT = VAR / "tools" / "judges" / "src" / "TuneJury" / "checkpoints" / "music_audioset_epoch_15_esc_90.14.pt"
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
RATE, SECONDS, LEVEL_DB = 48000, 10, -20.0
AXES = {
    "hard": (("aggressive hard techno with a distorted kick drum", "heavy pounding industrial techno", "hard hitting peak time warehouse techno"),
             ("soft gentle chill house music", "light relaxing tropical house", "calm mellow lounge house")),
    "dark": (("dark gritty menacing club music", "ominous brooding underground techno", "sinister dark electronic music"),
             ("sweet happy cheerful dance pop", "uplifting bright euphoric trance", "cute cheerful video game music")),
    "raw": (("raw underground warehouse rave with analog synthesizers", "gritty acid techno with a screaming 303", "rough distorted synthesizer riff"),
            ("cheesy euro dance pop", "polished commercial festival pop house", "clean bright bell-like synthesizer melody")),
}


def unit(rows: np.ndarray) -> np.ndarray:
    return rows / np.linalg.norm(rows, axis=-1, keepdims=True)


def load(folder: Path, channels: tuple[str, ...]) -> tuple[dict, np.ndarray]:
    """A staged take's channels summed, at 48 kHz, and what its track says of it (its bar's frames at that rate)."""
    meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
    parts, rate = [], RATE
    for channel in channels:
        for suffix in (".flac", ".mp3"):
            if (folder / (channel + suffix)).is_file():
                audio, rate = soundfile.read(str(folder / (channel + suffix)), dtype="float32", always_2d=True)
                parts.append(audio)
                break
    if not parts:
        raise FileNotFoundError("no stems of %s in %s" % (", ".join(channels), folder))
    length = min(len(part) for part in parts)
    mix = sum(part[:length] for part in parts)
    if rate != RATE:
        import librosa
        mix = librosa.resample(mix.T, orig_sr=rate, target_sr=RATE).T
        meta = dict(meta, bar_frames=meta["bar_frames"] * RATE / rate)
    return meta, mix


def windows(meta: dict, mix: np.ndarray, story: str, each: int) -> list[np.ndarray]:
    """Ten seconds from the fifth bar of every part of that story of eight bars or more, and so on evenly through it, each brought to one level."""
    out, at = [], 0
    for section in meta["sections"]:
        frames = int(round(section["bars"] * meta["bar_frames"]))
        if section["story"] == story and section["bars"] >= 8:
            for index in range(each):
                start = at + int((4 + index * max(0, (section["bars"] - 4) // each)) * meta["bar_frames"])
                piece = mix[start:start + SECONDS * RATE]
                if len(piece) < SECONDS * RATE or start + SECONDS * RATE > at + frames + SECONDS * RATE // 2:
                    continue
                mono = piece.mean(axis=1)
                level = float(np.sqrt(np.mean(mono ** 2)))
                if level > 1e-5:
                    out.append(np.clip(mono * (10 ** (LEVEL_DB / 20.0) / level), -1.0, 1.0).astype(np.float32))
        at += frames
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="How hard a song sounds against how sweet.")
    parser.add_argument("takes", nargs="*", help='staged takes: "house/regal-08/1"')
    parser.add_argument("--folder", action="append", default=[], help="a staged take's folder, anywhere (a demo's)")
    parser.add_argument("--channel", default="", help="only these channels, with commas")
    parser.add_argument("--without", default="", help="all but these channels, with commas")
    parser.add_argument("--windows", type=int, default=2, help="how many of ten seconds in each part")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)
    folders = [(take, VAR / "studio" / take) for take in args.takes] + [("/".join(Path(each).parts[-3:]), Path(each)) for each in args.folder]
    if not folders:
        parser.print_help()
        return 2
    channels = tuple(each for each in (args.channel.split(",") if args.channel else CHANNELS) if each not in args.without.split(","))
    import torch
    torch.set_num_threads(args.threads)
    import laion_clap
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base")
    model.load_ckpt(ckpt=str(CHECKPOINT), verbose=False)
    words = {axis: (unit(model.get_text_embedding(list(this))), unit(model.get_text_embedding(list(that)))) for axis, (this, that) in AXES.items()}
    for name, folder in folders:
        meta, mix = load(folder, channels)
        record: dict = {"at": datetime.datetime.now().isoformat(timespec="minutes"), "take": name, "folder": str(folder.resolve()), "title": meta.get("title", ""), "tempo": meta.get("tempo"),
                        "channels": channels, "label": args.label}
        for story, key in (("moment", "drop"), ("theme", "theme")):
            pieces = windows(meta, mix, story, args.windows)
            if not pieces:
                continue
            with torch.no_grad():
                heard = unit(model.get_audio_embedding_from_data(x=np.stack(pieces), use_tensor=False))
            record[key] = {axis: round(float(100.0 * ((heard @ this.T).mean() - (heard @ that.T).mean())), 2) for axis, (this, that) in words.items()}
            record[key]["all"] = round(float(np.mean([record[key][axis] for axis in AXES])), 2)
        with (VAR / "passes" / "hardness.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
        print("%-28s %-22s %4s  %s  %s" % (name, record["title"][:22], record["tempo"], "  ".join(
            "%s %+.1f (hard %+.1f dark %+.1f raw %+.1f)" % (key, record[key]["all"], record[key]["hard"], record[key]["dark"], record[key]["raw"]) for key in ("drop", "theme") if key in record),
            args.label), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
