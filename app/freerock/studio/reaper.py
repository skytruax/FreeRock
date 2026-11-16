"""REAPER as the studio's mixing desk and plug-in host, run headless.

REAPER is a studio program with a window. On this machine it runs without one, on a virtual
display (Xvfb) that is started here and stopped when REAPER is done: the standard way to run a
windowed program on a machine nobody sits at. It is not installed in the usual way (that needs
the administrator): it is unpacked under var/tools/reaper and keeps its settings beside itself
(a reaper.ini next to the program), so a REAPER the user installs for themselves is not touched.

The plug-ins are unpacked under var/tools as well, and `configure` writes where they are into
that reaper.ini. What a plug-in keeps for itself (presets, caches) goes under var/tools/xdg,
through the standard XDG variables, so that nothing is left in the user's own folders.

tools/stems/README.md says how each piece was fetched and under what licence.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "var" / "tools"
HOME = TOOLS / "reaper" / "reaper_linux_x86_64" / "REAPER"
XDG = TOOLS / "xdg"
JSFX = Path(__file__).resolve().parent / "jsfx"       # effects of the studio's own, written for REAPER
# Where REAPER is to look for plug-ins of each kind: the key in reaper.ini, and the folders.
# The studio's own (unpacked under var/tools) first, then wherever the system's packages and the
# user's own installs put theirs, so that a plug-in installed in the usual way is found too.
_HOME = Path.home()
PLUGINS = {
    "clap_path_linux-x86_64": [TOOLS / "surge" / "lib" / "clap", TOOLS / "plugins" / "clap", _HOME / ".clap", Path("/usr/lib/clap"),
                               Path("/usr/local/lib/clap")],
    "vstpath": [TOOLS / "surge" / "lib" / "vst3", TOOLS / "plugins" / "vst3", TOOLS / "plugins" / "vst", _HOME / ".vst3", _HOME / ".vst",
                Path("/usr/lib/vst3"), Path("/usr/local/lib/vst3"), Path("/usr/lib/vst"), Path("/usr/local/lib/vst"),
                Path("/usr/lib/x86_64-linux-gnu/vst3"), Path("/usr/lib/x86_64-linux-gnu/vst")],
    "lv2path_linux": [TOOLS / "plugins" / "lv2", _HOME / ".lv2", Path("/usr/lib/lv2"), Path("/usr/local/lib/lv2"),
                      Path("/usr/lib/x86_64-linux-gnu/lv2")],
}
SCREEN = "1280x800x24"
# Other settings written into reaper.ini. One REAPER uses this many processor threads: several
# render side by side, and each taking every core at once makes all of them slower.
SETTINGS = {"workthreads": "6", "autonbworkerthreads": "0"}       # the second turns off REAPER's own count of the cores, which overrides the first


def configure() -> None:
    """Writes the plug-in folders that exist into REAPER's settings. Safe to call again."""
    ini = HOME / "reaper.ini"
    if not (HOME / "reaper").is_file():
        raise FileNotFoundError("REAPER is not unpacked at %s (see tools/stems/README.md)" % HOME)
    lines = ini.read_text(encoding="utf-8").splitlines() if ini.is_file() else []
    if "[reaper]" not in [line.strip().lower() for line in lines]:
        lines += ["", "[reaper]"]
    wants = {key: ";".join(str(folder) for folder in folders if folder.is_dir()) for key, folders in PLUGINS.items()}
    wants.update(SETTINGS)
    for key, value in wants.items():
        wanted = "%s=%s" % (key, value)
        found = [index for index, line in enumerate(lines) if line.startswith(key + "=")]
        if found:
            lines[found[0]] = wanted
        else:
            at = [line.strip().lower() for line in lines].index("[reaper]")
            lines.insert(at + 1, wanted)
    ini.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The studio's own effects (plain-text JSFX) go where REAPER looks for them by name.
    ours = HOME / "Effects" / "freerock"
    ours.mkdir(parents=True, exist_ok=True)
    for source in sorted(JSFX.iterdir()):
        target = ours / source.name
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            target.write_bytes(source.read_bytes())


class Display:
    """A virtual display for REAPER's window: `with Display() as name:` gives its name (":93")."""

    def __init__(self) -> None:
        self.name = ""
        self.server: subprocess.Popen | None = None

    def __enter__(self) -> str:
        for number in range(90, 130):
            if Path("/tmp/.X%d-lock" % number).exists() or Path("/tmp/.X11-unix/X%d" % number).exists():
                continue
            server = subprocess.Popen(["Xvfb", ":%d" % number, "-screen", "0", SCREEN, "-nolisten", "tcp"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(50):
                if Path("/tmp/.X11-unix/X%d" % number).exists():
                    break
                if server.poll() is not None:
                    break
                time.sleep(0.1)
            if server.poll() is None and Path("/tmp/.X11-unix/X%d" % number).exists():
                self.server, self.name = server, ":%d" % number
                return self.name
            if server.poll() is None:
                server.terminate()
                server.wait(10)
        raise RuntimeError("No virtual display could be started (is Xvfb installed?)")

    def __exit__(self, *exc: object) -> None:
        if self.server is not None:
            self.server.terminate()
            self.server.wait(10)


def picture(display: str, to: Path) -> None:
    """What is on the virtual display right now, as a PNG: for seeing a window that waits for a click."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", SCREEN.rsplit("x", 1)[0],
                    "-i", display, "-frames:v", "1", str(to)], check=False, timeout=30)


def environment(display: str, more: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ, DISPLAY=display)
    env.pop("WAYLAND_DISPLAY", None)
    for name, folder in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache"),
                         ("XDG_DOCUMENTS_DIR", "documents")):
        (XDG / folder).mkdir(parents=True, exist_ok=True)
        env[name] = str(XDG / folder)
    env.update(more or {})
    return env


def run(arguments: list[str], *, display: str, work: Path, timeout: float = 300.0,
        env: dict[str, str] | None = None, done: Path | None = None) -> str:
    """Runs REAPER with these arguments and returns what it printed.

    Rendering a project (`-renderproject file.rpp`) ends by itself. A script does not: REAPER
    asks about saving before it will quit, and there is nobody to answer. So a script writes the
    file `done` as its last act, and REAPER is stopped when that file appears.

    If REAPER is still running after `timeout` seconds without either, it is stopped, a picture
    of its window is left in `work`, and that is an error: a REAPER that waits is a REAPER with
    a question open."""
    work.mkdir(parents=True, exist_ok=True)
    if done is not None:
        done.unlink(missing_ok=True)
    began = time.monotonic()
    heard = work / ("reaper-%d.out" % os.getpid())
    with open(heard, "wb") as out:
        reaper = subprocess.Popen([str(HOME / "reaper"), "-nosplash", "-newinst", "-ignoreerrors", *arguments], cwd=str(HOME),
                                  env=environment(display, env), stdout=out, stderr=subprocess.STDOUT)
        stopped = False
        while reaper.poll() is None:
            if done is not None and done.exists():
                stopped = True
                reaper.terminate()
                try:
                    reaper.wait(5)
                except subprocess.TimeoutExpired:
                    reaper.kill()
                    reaper.wait(10)
                break
            if time.monotonic() - began > timeout:
                shot = work / "reaper-waiting.png"
                picture(display, shot)
                reaper.kill()
                reaper.wait(10)
                raise RuntimeError("REAPER was still running after %.0f s and was stopped. Its window is pictured in %s. It said: %s" % (
                    timeout, shot, heard.read_text(encoding="utf-8", errors="replace").strip()[-1500:]))
            time.sleep(0.1)
    text = heard.read_text(encoding="utf-8", errors="replace").strip()
    heard.unlink()
    if not stopped and reaper.returncode != 0:
        raise RuntimeError("REAPER ended with exit code %s after %.1f s. It said: %s" % (
            reaper.returncode, time.monotonic() - began, text[-1500:]))
    return text
