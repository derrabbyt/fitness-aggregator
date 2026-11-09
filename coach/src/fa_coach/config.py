"""Settings from the environment (docker-compose.yml passes them from .env)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]  # coach/
STATE = Path(os.environ.get("FA_STATE_DIR", PROJECT.parent / "state"))


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    allowed_user_id: int
    api_url: str
    tools_url: str
    model: str
    decision_model: str
    anthropic_api_key: str | None
    anthropic_base_url: str | None
    state_dir: Path

    @property
    def db_path(self) -> Path:
        return self.state_dir / "coach.db"

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        for key in ("COACH_TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_ID"):
            if not env.get(key):
                raise SystemExit(f"fa-coach: {key} is not set (.env)")
        return cls(
            telegram_token=env["COACH_TELEGRAM_BOT_TOKEN"],
            allowed_user_id=int(env["TELEGRAM_ALLOWED_USER_ID"]),
            api_url=env.get("FA_API_URL") or "http://127.0.0.1:8000",
            tools_url=env.get("FA_TOOLS_URL") or "http://127.0.0.1:8001",
            model=env.get("COACH_MODEL") or "claude-sonnet-5-5",
            decision_model=env.get("COACH_DECISION_MODEL") or "claude-opus-5-5",
            # The coach's own endpoint and key, else the shared ones (ADR 0003).
            anthropic_api_key=env.get("COACH_ANTHROPIC_API_KEY") or env.get("ANTHROPIC_API_KEY") or None,
            anthropic_base_url=env.get("COACH_ANTHROPIC_BASE_URL") or env.get("ANTHROPIC_BASE_URL") or None,
            state_dir=STATE / "coach",
        )
