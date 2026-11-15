"""Where FreeRock keeps things, how much it may spend, and how it finds the ElevenLabs key.

Nothing here prints or logs the key. The key is looked up when it is first needed, so the parts of
FreeRock that never call ElevenLabs (the game link, the tests) run without one.
"""
from __future__ import annotations

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
    daily_minutes: float = 20.0
    # Held back from the monthly allowance for re-rolls when a track fails its checks.
    reroll_reserve: float = 0.10

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
