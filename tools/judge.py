"""A judge that listens: Meta's Audiobox Aesthetics on a staged take (2026-11-18: "find more music judging packages,
that will rate a song", "add those to the recursive loop"; docs/plan.md, "Judges that listen").

It scores sound on four axes, each about 1 to 10: CE, how much the content is enjoyed; CU, how useful it is as
material; PC, how complex the production is; PQ, the production's quality. It hears 16 kHz mono in ten-second windows,
and was trained on speech, sound and songs, not on long instrumental game music or on stems. So it is a gate and a
pointer, never a target: a take far under its family's others, or a part of the story far under the rest of its own
take, is worth a listen. The whole mix is judged (the five stems summed), and each part of the story on its own.

It runs in an environment of its own, with PyTorch for the processor alone (var/tools/judges, see its install.log),
and the model is fetched once from Hugging Face (facebook/audiobox-aesthetics, CC BY 4.0) and kept in its cache. No
audio leaves this machine.

    "var/tools/judges/.venv/bin/python" tools/judge.py house/highland-01/2 knight/anywhere-banner-war-2/1 ...
    ... --folder <a staged take's folder>      (a take staged somewhere else, a demo's)
    ... --parts                                (each part of the story as well: twice the time)

Each take's scores are added to var/passes/judged.jsonl.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np
import soundfile

VAR = Path(__file__).resolve().parents[1] / "var"
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
AXES = ("CE", "CU", "PC", "PQ")


def mix(folder: Path) -> tuple[np.ndarray, int]:
    """The take as the player plays it at its full mix: its five stems summed."""
    parts, rate = [], 48000
    for channel in CHANNELS:
        for suffix in (".flac", ".mp3"):
            path = folder / (channel + suffix)
            if path.is_file():
                audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
                parts.append(audio)
                break
    if not parts:
        raise FileNotFoundError("no stems in %s" % folder)
    length = max(len(part) for part in parts)
    return sum(np.pad(part, ((0, length - len(part)), (0, 0))) for part in parts), rate


def judge(predictor, audio: np.ndarray, rate: int) -> dict[str, float]:
    import torch
    wav = torch.from_numpy(np.ascontiguousarray(audio.T))
    return {axis: round(float(value), 2) for axis, value in predictor.forward([{"path": wav, "sample_rate": rate}])[0].items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audiobox Aesthetics on staged takes, whole and part by part.")
    parser.add_argument("takes", nargs="*", help='staged takes: "house/coast-03/1"')
    parser.add_argument("--folder", action="append", default=[], help="a staged take's folder, anywhere")
    parser.add_argument("--threads", type=int, default=4, help="processor threads for the model (default 4)")
    parser.add_argument("--parts", action="store_true", help="judge each part of the story as well (twice the time)")
    args = parser.parse_args(argv)
    folders = [VAR / "studio" / take for take in args.takes] + [Path(folder) for folder in args.folder]
    if not folders:
        parser.print_help()
        return 2
    import torch
    from audiobox_aesthetics.infer import initialize_predictor
    torch.set_num_threads(args.threads)
    predictor = initialize_predictor()
    out = VAR / "passes" / "judged.jsonl"
    for folder in folders:
        meta = json.loads((folder / "track.json").read_text(encoding="utf-8"))
        audio, rate = mix(folder)
        whole = judge(predictor, audio, rate)
        parts = []
        at = 0
        for section in meta["sections"]:
            frames = int(round(section["bars"] * meta["bar_frames"]))
            piece = audio[at:at + frames]
            at += frames
            if args.parts and len(piece) >= rate * 5:
                parts.append((section["story"], judge(predictor, piece, rate)))
        print("%s (%s)" % (meta.get("title", folder.name), folder))
        print("   whole   " + "  ".join("%s %.2f" % (axis, whole[axis]) for axis in AXES))
        if parts:
            print("   by part " + "  ".join("%s %.1f/%.1f" % (story[:5], scores["CE"], scores["PQ"]) for story, scores in parts) + "   (CE/PQ)")
        with out.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="minutes"), "folder": str(folder),
                                  "title": meta.get("title", ""), "whole": whole, "parts": parts}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
