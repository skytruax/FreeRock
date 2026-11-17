"""The Muse cache's old WAV performances kept as FLAC instead (2026-11-17: "were going to get an 8tb drive for this
project so switch it all back to flac"; the 2,719 WAVs from before the night of 2026-11-16 took 385 GB).

    cd app && setsid nohup nice -n 19 ionice -c3 taskset -c 15-19 uv run --no-sync python ../tools/muse_flac.py &

Each WAV MuseScore wrote (32-bit float) is written as 24-bit FLAC, as every performance has been kept since that night
(`muse._performed`), read back and checked against the WAV (the same length, and nowhere further from it than the
24-bit step), and only then put in the WAV's place: `muse.perform` looks for the FLAC first, so the cache answers as
before. Left alone: WAVs from the night of 2026-11-16 on, and any WAV a REAPER project in var/reaper/projects names
(a render may be about to play it). A WAV that does not check out is reported by name and kept.
"""
from __future__ import annotations

import re
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import soundfile

VAR = Path(__file__).resolve().parents[1] / "var"
CACHE = VAR / "reaper" / "muse"
PROJECTS = VAR / "reaper" / "projects"
BEFORE = time.mktime(time.strptime("2026-11-16 23:30", "%Y-%m-%d %H:%M"))
STEP = 2.0 ** -23                     # the 24-bit step, as soundfile scales it


def named_by_projects() -> set[str]:
    """The cache files some REAPER project lays in."""
    names = set()
    for project in PROJECTS.rglob("*.rpp"):
        names |= set(re.findall(r"muse/([0-9a-f]{20}\.wav)", project.read_text(encoding="utf-8", errors="replace")))
    return names


def main() -> int:
    busy = named_by_projects()
    waves = sorted(path for path in CACHE.glob("*.wav") if path.stat().st_mtime < BEFORE and path.name not in busy)
    print("%d old WAV performances to keep as FLAC (%.1f GB); %d left alone because a project names them"
          % (len(waves), sum(path.stat().st_size for path in waves) / 1e9, len(busy)), flush=True)
    freed, wrong = 0, []
    for index, wave in enumerate(waves, 1):
        kept = wave.with_suffix(".flac")
        if kept.exists():
            wrong.append((wave, "a FLAC of the same name is there already"))
            continue
        audio, rate = soundfile.read(str(wave), dtype="float32", always_2d=True)
        if float(np.max(np.abs(audio), initial=0.0)) >= 1.0:
            wrong.append((wave, "it goes past full scale, which 24-bit FLAC cannot keep"))
            continue
        scratch = CACHE / ("%s.%s.part.flac" % (wave.stem, uuid.uuid4().hex[:10]))
        soundfile.write(str(scratch), audio, rate, format="FLAC", subtype="PCM_24")
        back, back_rate = soundfile.read(str(scratch), dtype="float32", always_2d=True)
        if back_rate != rate or back.shape != audio.shape or float(np.max(np.abs(back - audio), initial=0.0)) > STEP:
            scratch.unlink()
            wrong.append((wave, "the FLAC did not read back as the WAV"))
            continue
        size = wave.stat().st_size
        scratch.replace(kept)
        wave.unlink()
        freed += size - kept.stat().st_size
        if index % 100 == 0:
            print("%s %d of %d done, %.1f GB freed" % (time.strftime("%H:%M:%S"), index, len(waves), freed / 1e9), flush=True)
    print("%s all done: %.1f GB freed" % (time.strftime("%H:%M:%S"), freed / 1e9), flush=True)
    for wave, problem in wrong:
        print("NOT kept as FLAC: %s: %s" % (wave.name, problem), flush=True)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
