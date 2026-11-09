"""The coach profile: short, user-visible entries (preferences, known issues).
`/profile` shows it; the chat changes it through `update_coach_profile`; every
model task gets it in its state snapshot."""

import datetime
from typing import Any

from ..ask import ToolError
from ..registry import registry

EMPTY = "Your coach profile is empty."
MAX_KEY = 40
MAX_VALUE = 200
MAX_ENTRIES = 30


def load(coach) -> dict[str, str]:
    return {row["key"]: row["value"] for row in coach.db.all("SELECT key, value FROM profile ORDER BY key")}


def render(profile: dict[str, str]) -> str:
    if not profile:
        return EMPTY
    return "Your coach profile:\n" + "\n".join(f"- {key}: {value}" for key, value in profile.items())


@registry.command("profile", "Show your coach profile")
async def profile_command(coach, args: str, now) -> None:
    coach.say(render(load(coach)))


@registry.state("profile")
def profile_state(coach, now: datetime.datetime) -> dict[str, str]:
    return load(coach)


@registry.tool(
    "get_coach_profile",
    "The coach profile: short entries the user asked the coach to know (preferences, known issues).",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_coach_profile(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    return {"profile": load(coach)}


@registry.tool(
    "update_coach_profile",
    "Change the coach profile when the user states a preference about how the coach should talk or what it "
    f"should know. `patch` maps a short key (≤ {MAX_KEY} chars, e.g. 'quiet hours') to a short value "
    f"(≤ {MAX_VALUE} chars), or to null to remove the entry. Returns the whole profile; tell the user what changed.",
    {
        "type": "object",
        "properties": {
            "patch": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": {"type": ["string", "null"]},
            }
        },
        "required": ["patch"],
        "additionalProperties": False,
    },
)
async def update_coach_profile(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    patch = {key.strip(): (value.strip() if isinstance(value, str) else None) for key, value in args["patch"].items()}
    for key, value in patch.items():
        if not key or len(key) > MAX_KEY:
            raise ToolError(f"profile keys are 1–{MAX_KEY} characters")
        if value is not None and (not value or len(value) > MAX_VALUE):
            raise ToolError(f"profile values are 1–{MAX_VALUE} characters; keep it short")
    current = load(coach)
    after = {k: v for k, v in {**current, **patch}.items() if v is not None}
    if len(after) > MAX_ENTRIES:
        raise ToolError(f"the profile holds at most {MAX_ENTRIES} entries; remove one first")
    with coach.db.transaction():
        for key, value in patch.items():
            if value is None:
                coach.db.execute("DELETE FROM profile WHERE key = ?", (key,))
            else:
                coach.db.execute(
                    "INSERT INTO profile (key, value, updated_at) VALUES (?, ?, ?)"
                    " ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                    (key, value, now.isoformat(timespec="seconds")),
                )
    return {"profile": load(coach)}
