"""Where FreeRock keeps things, and the settings that may be changed."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# <repo>/app/freerock/settings.py -> <repo>
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Everything made or downloaded at run time: the buckets, the studio's tracks, captured strips, logs.
VAR_DIR = REPO_ROOT / "var"


@dataclass
class Settings:
    # The kind of music: "knight" (riff rock with lute and hurdy-gurdy), "warcraft" (an orchestral
    # fantasy score in the old style) or "house" (uplifting progressive house, happy and chill).
    # Each has a bucket of its own, a song that never ends; the one named here is played. See
    # composer.GENRES.
    genre: str = "knight"

    # Whether the written pieces in the buckets are played ("on") or only the loose phrases
    # ("off"): a way back to how the forever song was before there were pieces.
    pieces: str = "on"

    # Moments of silence: about this many minutes of music, then about this many seconds without
    # any, as the game's own music has between pieces. rest_every_minutes of 0 means none.
    rest_every_minutes: float = 6.0
    rest_seconds: float = 60.0

    var_dir: Path = field(default_factory=lambda: VAR_DIR)

    # The settings that may be changed in var/settings.json or with `freerock settings`.
    CHANGEABLE = ("rest_every_minutes", "rest_seconds", "genre", "pieces")
    GENRES = ("knight", "warcraft", "house")
    WORDS = ("genre", "pieces")               # the settings that are a word, not a number
    # Settings an older var/settings.json may still hold, from when FreeRock bought its music from
    # ElevenLabs and played it as songs: they are passed over when the file is read, and left out
    # when it is next written.
    FORMER = ("monthly_minutes", "daily_minutes", "hours_per_month", "rock", "mode")

    @property
    def file(self) -> Path:
        return self.var_dir / "settings.json"

    @classmethod
    def load(cls, var_dir: Path | None = None) -> "Settings":
        """The settings as changed in var/settings.json, or the defaults if there is no such file.
        A name the file should not have, or a value that makes no sense, is an error here rather
        than something found out later from the music."""
        settings = cls(var_dir=var_dir) if var_dir is not None else cls()
        if not settings.file.is_file():
            return settings
        changes = json.loads(settings.file.read_text(encoding="utf-8"))
        for name, value in changes.items():
            if name not in cls.FORMER:
                settings.change(name, value)
        return settings

    def change(self, name: str, value: float | str) -> None:
        if name not in self.CHANGEABLE:
            raise ValueError("%r is not a setting; the settings are %s" % (name, ", ".join(self.CHANGEABLE)))
        if name == "genre":
            # The style that was trance is now progressive house. A settings file written
            # before that still names it the old way, and means the style it has become.
            if value == "trance":
                value = "house"
            if value not in self.GENRES:
                raise ValueError("genre must be one of %s, not %r" % (", ".join(self.GENRES), value))
            self.genre = str(value)
            return
        if name == "pieces":
            if value not in ("on", "off"):
                raise ValueError("pieces must be on or off, not %r" % (value,))
            self.pieces = str(value)
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("%s must be a number, not %r" % (name, value))
        if value < 0:
            raise ValueError("%s cannot be less than nothing" % name)
        setattr(self, name, float(value))

    def save(self) -> None:
        """Writes the changeable settings that differ from the defaults to var/settings.json."""
        defaults = type(self)(var_dir=self.var_dir)
        changed = {name: getattr(self, name) for name in self.CHANGEABLE
                   if getattr(self, name) != getattr(defaults, name)}
        self.var_dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
