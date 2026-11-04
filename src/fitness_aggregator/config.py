"""Repo paths and settings from .env. Secrets and sessions live in state/ (gitignored)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get("FA_STATE_DIR", ROOT / "state"))


def load_env() -> dict[str, str]:
    """KEY=VALUE lines from .env; real environment variables win."""
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update({k: v for k, v in os.environ.items() if k in values})
    return values
