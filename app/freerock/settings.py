"""Where FreeRock keeps things, how much it may spend, and how it finds the ElevenLabs key.

Nothing here prints or logs the key. The key is looked up when it is first needed, so the parts of
FreeRock that never call ElevenLabs (the game link, the tests) run without one.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# <repo>/app/freerock/settings.py -> <repo>
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Everything made or downloaded at run time: the music library, the ledger, captured strips, logs.
VAR_DIR = REPO_ROOT / "var"

# The names the key may be stored under, in order of preference. EL_BIG_BAD_KEY is the unrestricted
# key on the Pro plan; ELEVENLABS_API_KEY is an older restricted one kept as a fallback.
KEY_NAMES = ("EL_BIG_BAD_KEY", "ELEVENLABS_API_KEY")

# Where a .env file may be: the repository itself, or the workspace folder that holds it.
ENV_FILES = (REPO_ROOT / ".env", REPO_ROOT.parent / ".env")


class MissingKey(RuntimeError):
    """No ElevenLabs key was found in the environment or in a .env file."""


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def find_key() -> tuple[str, str]:
    """Returns (name, key). The environment wins over .env files; raises MissingKey if none has it."""
    for name in KEY_NAMES:
        value = os.environ.get(name)
        if value:
            return name, value
    for path in ENV_FILES:
        if not path.is_file():
            continue
        values = _read_env_file(path)
        for name in KEY_NAMES:
            if values.get(name):
                return name, values[name]
    raise MissingKey(
        "No ElevenLabs key found. Looked for %s in the environment and in %s."
        % (" or ".join(KEY_NAMES), ", ".join(str(p) for p in ENV_FILES))
    )


@dataclass
class Settings:
    # How many minutes of new music FreeRock may generate in a calendar month, and in one day.
    # 300 sits under the lower of the two monthly caps ElevenLabs publishes for the Pro plan.
    monthly_minutes: float = 300.0
    daily_minutes: float = 30.0
    # How many hours a month the game is played with FreeRock on. The minutes that go on growing
    # a place's music are paced against this, so the month's allowance lasts the month.
    hours_per_month: float = 100.0
    # Held back from the monthly allowance for re-rolls when a track fails its checks.
    reroll_reserve: float = 0.10

    # How much of the rock the calm parts of new music carry, from 0 (hardly any) to 1 (a lot).
    # Battle and Boss are always the full band.
    rock: float = 0.5

    # The kind of music: "knight" (riff rock with lute and hurdy-gurdy), "warcraft" (an orchestral
    # fantasy score in the old style) or "trance". New music is made in it, and what the library
    # already has in it is what is played. See composer.GENRES.
    genre: str = "knight"

    # How the music is put together. "forever": one song that never ends, built as it goes from a
    # bucket of single-instrument phrases, with new phrases asked for the whole time the game is
    # played. "songs": whole songs made a few minutes at a time and played start to finish.
    mode: str = "forever"

    # Rests: about this many minutes of calm music, then about this many seconds without any, as
    # the game's own music has between pieces. rest_every_minutes of 0 means the music never rests.
    rest_every_minutes: float = 6.0
    rest_seconds: float = 60.0

    model_id: str = "music_v2_5"
    api_base: str = "https://api.elevenlabs.io"
    # What ElevenLabs charges per generated minute of music, for the ledger's dollar column.
    usd_per_minute: float = 0.15

    var_dir: Path = field(default_factory=lambda: VAR_DIR)

    @property
    def ledger_path(self) -> Path:
        return self.var_dir / "ledger.sqlite3"

    @property
    def library_dir(self) -> Path:
        return self.var_dir / "library"

    # The settings that may be changed in var/settings.json or with `freerock settings`.
    CHANGEABLE = ("monthly_minutes", "daily_minutes", "hours_per_month", "rock",
                  "rest_every_minutes", "rest_seconds", "genre", "mode")
    GENRES = ("knight", "warcraft", "trance")
    MODES = ("forever", "songs")
    WORDS = ("genre", "mode")       # the settings that are a word, not a number

    @property
    def file(self) -> Path:
        return self.var_dir / "settings.json"

    @classmethod
    def load(cls, var_dir: Path | None = None) -> "Settings":
        """The settings as changed in var/settings.json, or the defaults if there is no such file.
        A name the file should not have, or a value that makes no sense, is an error here rather
        than something found out later from a bill."""
        settings = cls(var_dir=var_dir) if var_dir is not None else cls()
        if not settings.file.is_file():
            return settings
        changes = json.loads(settings.file.read_text(encoding="utf-8"))
        for name, value in changes.items():
            settings.change(name, value)
        return settings

    def change(self, name: str, value: float | str) -> None:
        if name not in self.CHANGEABLE:
            raise ValueError("%r is not a setting; the settings are %s" % (name, ", ".join(self.CHANGEABLE)))
        if name == "genre":
            if value not in self.GENRES:
                raise ValueError("genre must be one of %s, not %r" % (", ".join(self.GENRES), value))
            self.genre = str(value)
            return
        if name == "mode":
            if value not in self.MODES:
                raise ValueError("mode must be one of %s, not %r" % (", ".join(self.MODES), value))
            self.mode = str(value)
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("%s must be a number, not %r" % (name, value))
        if name == "rock" and not 0.0 <= value <= 1.0:
            raise ValueError("rock must be between 0 and 1, not %r" % (value,))
        if name != "rock" and value < 0:
            raise ValueError("%s cannot be less than nothing" % name)
        if name == "hours_per_month" and value <= 0:
            raise ValueError("hours_per_month must be more than nothing")
        setattr(self, name, float(value))

    def save(self) -> None:
        """Writes the changeable settings that differ from the defaults to var/settings.json."""
        defaults = type(self)(var_dir=self.var_dir)
        changed = {name: getattr(self, name) for name in self.CHANGEABLE
                   if getattr(self, name) != getattr(defaults, name)}
        self.var_dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
