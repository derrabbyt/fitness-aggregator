"""Paths and settings. In Docker everything comes from the environment; on the
host, the repo's .env is read too."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STATE = Path(os.environ.get("FA_STATE_DIR", REPO / "state"))


def load_env() -> dict[str, str]:
    """KEY=VALUE lines from the repo's .env (if any); the process environment wins."""
    values: dict[str, str] = {}
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update(os.environ)
    return values
