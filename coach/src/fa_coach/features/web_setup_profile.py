"""Setup › Profile (coach-web ticket 12): the coach profile (what `/profile`
shows), edited through chat's `update_coach_profile`:

    POST setup/profile {patch: {key: value | null}}

A null value removes the entry. Doesn't need an active phase. Returns the
section.
"""

import datetime
from typing import Any

from .. import views
from ..registry import registry
from . import profile


@registry.view_part("setup", "profile", schema="web_setup_summary", order=70)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    entries = profile.load(coach)
    if not entries:
        return {"summary": "Empty"}
    n = len(entries)
    return {"summary": f"{n} entr{'y' if n == 1 else 'ies'}: {', '.join(entries)}"}


@registry.view("setup/profile", schema="web_setup_profile")
def profile_view(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    return {"entries": [{"key": k, "value": v} for k, v in profile.load(coach).items()],
            "max_key": profile.MAX_KEY, "max_value": profile.MAX_VALUE, "max_entries": profile.MAX_ENTRIES}


@registry.web_command("setup/profile")
async def update(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    await views.run_tool(coach, "update_coach_profile", {"patch": views.field(body, "patch")}, now)
    return profile_view(coach, {}, now)
