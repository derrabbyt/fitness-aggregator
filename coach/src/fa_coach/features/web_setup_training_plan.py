"""Setup › Training plan (coach-web ticket 11): the saved week (sessions with
times, optional runs) and this week day by day with what the user reported.

Edits run chat's tools through `web_setup.run_tool`, so they follow the same
rules and estimates as chat:

- `setup/training-plan/day` {weekday, sessions, from?}: a lasting change to
  one weekday (`update_training_plan`; from today unless `from` says later).
- `setup/training-plan/session` {date, status, ...}: this week's session
  status (`set_session_status`): a planned session `skipped` or `done`, an
  `extra` session with the user's kcal or activity + duration (code
  estimates), or `clear` to undo a report. The web never passes the model's
  own `kcal_estimate`; when code can't estimate, the page asks for the kcal.

The training plan isn't a phase setup value: chat changes it with or without
an active phase, and so does the page (it needs a saved plan).
"""

import datetime
from typing import Any

from .. import phases, views
from ..registry import registry
from . import training_plan, web_setup

SESSION_FIELDS = ("date", "status", "session_id", "extra_id", "type", "name", "kcal", "activity", "duration_min",
                  "distance_km")


def _plan(coach, now: datetime.datetime) -> dict[str, Any] | None:
    """What get_training_plan returns in chat, None without a saved plan."""
    return training_plan.overview(coach, now) if training_plan.ensure_seeded(coach, now) else None


@registry.view_part("setup", "training_plan", schema="web_setup_summary", order=40)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    result = _plan(coach, now)
    if result is None:
        return {"summary": "No training plan saved yet"}
    sessions = [s for day in result["plan"]["days"].values() for s in day]
    required = [s for s in sessions if not s["optional"]]
    parts = []
    for kind, one, many in (("lift", "lift", "lifts"), ("wrestling", "wrestling", "wrestling"),
                            ("run", "run", "runs"), ("other", "other session", "other sessions")):
        n = sum(1 for s in required if s["type"] == kind)
        if n:
            parts.append(f"{n} {one if n == 1 else many}")
    optional = len(sessions) - len(required)
    if optional:
        parts.append(f"{optional} optional")
    if result["upcoming"]:
        parts.append(f"changes from {result['upcoming'][0]['valid_from']}")
    return {"summary": " · ".join(parts) or "Rest all week"}


@registry.view("setup/training-plan", schema="web_setup_training_plan")
def plan(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    result = _plan(coach, now)
    activities = sorted(phases.params(coach)["activity"]["met_by_activity"])
    if result is None:
        return {"editable": False, "valid_from": None, "upcoming": [], "days": [], "this_week": [],
                "activities": activities}
    session = ("id", "time", "name", "type", "optional")
    return {
        "editable": True,
        "valid_from": result["plan"]["valid_from"],
        "upcoming": result["upcoming"],
        "days": [{"weekday": day, "sessions": [{k: s[k] for k in session} for s in result["plan"]["days"][day]]}
                 for day in training_plan.WEEKDAYS],
        "this_week": [{"date": d["date"], "weekday": d["weekday"], "today": d["date"] == now.date().isoformat(),
                       "sessions": [{k: s[k] for k in (*session, "status", "kcal", "kcal_source")}
                                    for s in d["sessions"]],
                       "extras": d["extras"]}
                      for d in result["this_week"]],
        "activities": activities,
    }


@registry.web_command("setup/training-plan/day")
async def set_day(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{weekday, sessions: [{name, type, time?, optional?}], from?}: a lasting
    change to that weekday ([] = rest day). Returns the section."""
    weekday = views.field(body, "weekday")
    if weekday not in training_plan.WEEKDAYS:
        raise views.WebError(400, f"weekday must be one of {', '.join(training_plan.WEEKDAYS)}.")
    args: dict[str, Any] = {"days": {weekday: views.field(body, "sessions")}}
    if body.get("from") is not None:
        args["from"] = body["from"]
    await views.run_tool(coach, "update_training_plan", args, now)
    return plan(coach, {}, now)


@registry.web_command("setup/training-plan/session")
async def set_session(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{date, status, session_id?, extra_id?, type?, name?, kcal?, activity?,
    duration_min?, distance_km?}: one report for a day of this week. Returns
    {reported (kcal, kcal_source, kcal_counted, estimate?; null for a skip or
    a cleared report), section}."""
    unknown = sorted(set(body) - set(SESSION_FIELDS))
    if unknown:
        raise views.WebError(400, f"{', '.join(unknown)} isn't a session report field.")
    day = views.field(body, "date")
    this_week = {d.isoformat() for d in training_plan.week_dates(now.date())}
    if day not in this_week:
        raise views.WebError(400, OTHER_WEEK)
    try:
        result = await views.run_tool(coach, "set_session_status", body, now)
    except views.WebError as refused:
        raise views.WebError(refused.status, _for_the_page(refused.message)) from None
    reported = result.get("reported")
    if reported is not None:
        reported = {k: v for k, v in reported.items() if k != "say"}
    return {"reported": reported, "section": plan(coach, {}, now)}


OTHER_WEEK = "Only this week's sessions can be reported here; report earlier ones in Telegram."


def _for_the_page(reason: str) -> str:
    """session_kcal's refusals tell the model what to do next (ask the user,
    pass its own estimate); on the page the user is the one to act."""
    if reason.startswith("code can't estimate: "):
        why = reason.removeprefix("code can't estimate: ").split(". Pass your own", 1)[0]
        return f"Code can't estimate the kcal: {why}. Give the kcal."
    if reason.startswith("give the user's kcal, or `activity`"):
        return "Give the kcal, or an activity and a duration so code estimates them."
    if reason.startswith("no duration: "):
        return "Give the duration (or the kcal)."
    return reason
