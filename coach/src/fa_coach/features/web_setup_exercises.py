"""Setup › Exercises (coach-web ticket 12): every exercise in the synced Hevy
history (the last 16 weeks, as chat's `get_tracked_exercises`) as counting
or not counted, and whether it's paused. The toggles run the chat tools:

    POST setup/exercises/classify {exercise_id, classification: counts|excluded}
    POST setup/exercises/pause    {exercise_id, paused, reason?}

Neither needs an active phase (chat doesn't either). Both return the section.
"""

import datetime
from typing import Any

from .. import progression, views
from ..registry import registry
from . import lifts

WEB_REASON = "set on the web page"


def _exercises(coach, now: datetime.datetime) -> list[dict[str, Any]]:
    today = now.date()
    stored = progression.settings(coach)
    out = []
    for e in progression.exercises(coach, lifts.history_start(today), today):
        row = stored.get(e["exercise_id"], {})
        out.append({
            "exercise_id": e["exercise_id"],
            "title": e["title"] or e["exercise_id"],
            "counts": e["classification"] != "excluded",
            "classified": e["classification"] is not None,
            "paused": e["paused"],
            "paused_reason": row.get("paused_reason") if e["paused"] else None,
            "bodyweight": e["bodyweight_exercise"],
            "sessions": e["sessions"],
            "last_date": e["last_date"],
        })
    return sorted(out, key=lambda e: (e["title"].lower(), e["exercise_id"]))


@registry.view_part("setup", "exercises", schema="web_setup_summary", order=50)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    ex = _exercises(coach, now)
    if not ex:
        return {"summary": "No exercises synced from Hevy yet"}
    counting = sum(e["counts"] for e in ex)
    parts = [f"{counting} counting", f"{len(ex) - counting} not counted"]
    paused = sum(e["paused"] for e in ex)
    if paused:
        parts.append(f"{paused} paused")
    return {"summary": " · ".join(parts)}


@registry.view("setup/exercises", schema="web_setup_exercises")
def exercises(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    return {"since": lifts.history_start(now.date()).isoformat(), "exercises": _exercises(coach, now)}


@registry.web_command("setup/exercises/classify")
async def classify(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{exercise_id, classification}: chat's classify_exercises for one exercise."""
    item = {"exercise_id": views.field(body, "exercise_id"),
            "classification": views.field(body, "classification"), "reason": WEB_REASON}
    await views.run_tool(coach, "classify_exercises", {"exercises": [item]}, now)
    return exercises(coach, {}, now)


@registry.web_command("setup/exercises/pause")
async def pause(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{exercise_id, paused, reason?}: chat's set_exercise_paused."""
    args = {"exercise_id": views.field(body, "exercise_id"), "paused": views.field(body, "paused")}
    reason = (body.get("reason") or "").strip() if isinstance(body.get("reason"), str) else None
    if reason:
        args["reason"] = reason
    await views.run_tool(coach, "set_exercise_paused", args, now)
    return exercises(coach, {}, now)
