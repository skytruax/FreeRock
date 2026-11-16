"""Runs REAPER on a screen nobody sees, has it build a phrase from notes and render its stems,
and measures what came out.

    cd app && uv run --no-sync python ../tools/stems/reaper_try.py

REAPER is looked for in var/tools/reaper (see docs/own-stems.md). Pictures of the unseen screen
are kept in the output folder, so that a window waiting for a click can be seen.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
REAPER_DIR = REPO / "var" / "tools" / "reaper" / "reaper_linux_x86_64" / "REAPER"
OUT = REPO / "var" / "stems-own" / "reaper-test"
DISPLAY = ":97"
WAIT_S = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0


def picture(name: str) -> None:
    """What is on the unseen screen right now, as a PNG in the output folder."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "1280x800", "-i", DISPLAY,
                    "-frames:v", "1", str(OUT / name)], check=False, timeout=20)


def main() -> int:
    if not (REAPER_DIR / "reaper").is_file():
        print("REAPER is not at %s" % REAPER_DIR)
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    # Its settings stay beside it (a reaper.ini next to the program makes it keep them there),
    # so nothing of this touches the settings of a REAPER the user may install for themselves.
    (REAPER_DIR / "reaper.ini").touch()
    screen = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    env = dict(os.environ, DISPLAY=DISPLAY, FREEROCK_OUT=str(OUT))
    env.pop("WAYLAND_DISPLAY", None)
    began = time.monotonic()
    reaper = subprocess.Popen([str(REAPER_DIR / "reaper"), "-nosplash", "-newinst", "-ignoreerrors",
                               str(HERE / "reaper_phrase_test.lua")], cwd=str(REAPER_DIR), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    shots = 0
    try:
        while reaper.poll() is None and time.monotonic() - began < WAIT_S:
            time.sleep(1.0)
            if int(time.monotonic() - began) in (6, 20, 45) and shots < 3:
                shots += 1
                picture("screen-%d.png" % shots)
        if reaper.poll() is None:
            picture("screen-stuck.png")
            print("REAPER was still running after %.0f s and was stopped." % WAIT_S)
            reaper.terminate()
            try:
                reaper.wait(10)
            except subprocess.TimeoutExpired:
                reaper.kill()
        else:
            print("REAPER finished by itself after %.1f s with exit code %s." % (time.monotonic() - began, reaper.returncode))
        said = reaper.stdout.read().decode("utf-8", "replace").strip()
        if said:
            print("REAPER said:\n" + said[-1500:])
    finally:
        screen.terminate()
        screen.wait(10)
    log = OUT / "log.txt"
    print("the script's own notes:\n" + (log.read_text() if log.is_file() else "(none: the script did not start)"))
    print("files:", sorted(path.name for path in OUT.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
