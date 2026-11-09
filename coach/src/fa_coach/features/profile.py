"""The coach profile: short, user-visible entries (preferences, known issues).
`/profile` shows it; the chat changes it (ticket 03)."""

from ..registry import registry

EMPTY = "Your coach profile is empty."


def load(coach) -> dict[str, str]:
    return {row["key"]: row["value"] for row in coach.db.all("SELECT key, value FROM profile ORDER BY key")}


def render(profile: dict[str, str]) -> str:
    if not profile:
        return EMPTY
    return "Your coach profile:\n" + "\n".join(f"- {key}: {value}" for key, value in profile.items())


@registry.command("profile", "Show your coach profile")
async def profile_command(coach, args: str, now) -> None:
    coach.say(render(load(coach)))
