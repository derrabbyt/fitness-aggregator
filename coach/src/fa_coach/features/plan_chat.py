"""Chat about the plan (ticket 10; spec stories 57-59, 63-64, 71).

Read tools for the coach chat, all aggregated by code: `get_weekly_facts`
(a stored check-in: facts, verdict, rules), `get_daily_facts` (a day's
facts plus its judged lift sessions), `get_lift_history` (one exercise's
sessions since its last baseline) and `load_skill`. Targets, the training
plan, context notes, proposals, the coach profile and tracked exercises have
their tools in their own features.

Questions, change requests, rejection reasons and setup values are the chat
model's (coach-chat skill), with `propose_change`, `add_rejection_reason`
and `record_setup_value`. Counters are code's: after a counter tap, a reply
that is just a number becomes a `user_counter` proposal (see
`counter_reply`).
"""

import datetime
from typing import Any

from .. import history, phases, progression
from ..ask import ToolError
from ..registry import registry
from . import context_notes, evening, weekly_checkin

DEFAULT_SESSIONS = 6  # get_lift_history


def _stored_weeks(coach) -> list[str]:
    return [r["iso_week"] for r in coach.db.all(
        "SELECT DISTINCT iso_week FROM weekly_checkins WHERE status = 'ok' ORDER BY iso_week")]


@registry.tool(
    "get_weekly_facts",
    "A stored weekly check-in (default: the latest): the week's facts as code computed them, the verdict "
    "(scenario, direction, confirmation, proposal, reasoning), the rule ids applied, whether the week counts "
    "for confirmation (else skip_reason) and code's adjustments to the verdict. Answer \"why did you ...\" from this.",
    {"type": "object", "additionalProperties": False,
     "properties": {"iso_week": {"type": "string", "pattern": "^[0-9]{4}-W[0-9]{2}$"}}},
)
async def get_weekly_facts(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    week = weekly_checkin.stored(coach, args.get("iso_week"))
    if week is None:
        weeks = _stored_weeks(coach)
        raise ToolError(f"no stored check-in for {args.get('iso_week') or 'any week'}; stored weeks: "
                        + (", ".join(weeks) if weeks else "none yet"))
    week.pop("report", None)
    return week


@registry.tool(
    "get_lift_history",
    "One exercise's sessions since its last baseline (first session or reset), oldest first, the latest "
    "`n_sessions` (default 6): date, working sets, top set (load, reps, effective load for bodyweight "
    "exercises, estimated 1RM), status vs the best recent session, PR, streaks, and context notes about the "
    "exercise that day. The exercise id comes from get_tracked_exercises.",
    {"type": "object", "required": ["exercise_id"], "additionalProperties": False,
     "properties": {"exercise_id": {"type": "string"}, "n_sessions": {"type": "integer", "minimum": 1, "maximum": 20}}},
)
async def get_lift_history(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    exercise_id = args["exercise_id"]
    lift = progression.lifts(coach, now.date()).get(exercise_id)
    if lift is None:
        raise ToolError(f"no exercise {exercise_id!r} in the synced Hevy history; see get_tracked_exercises")
    entries = lift["entries"]
    starts = [i for i, e in enumerate(entries) if e["status"] == "new_baseline"]
    since = entries[starts[-1]:] if starts else entries
    shown = since[-args.get("n_sessions", DEFAULT_SESSIONS):]
    notes = context_notes.between(coach, datetime.date.fromisoformat(shown[0]["date"]), now.date()) if shown else []
    return {
        "exercise_id": exercise_id,
        "name": lift["name"],
        "counts": lift["counts"],
        "classification": lift["classification"],
        "paused": lift["paused"],
        "bodyweight_exercise": lift["bodyweight_exercise"],
        "baseline_from": since[0]["date"] if since else None,
        "sessions_since_baseline": len(since),
        "sessions": [_lift_session(e, exercise_id, notes) for e in shown],
    }


@registry.tool(
    "get_daily_facts",
    "One day of the active phase (default today) as code computed it: intake vs that day's target and macros, "
    "weight (withheld in the glycogen window), steps, counted sessions, the phase week so far, context notes; "
    "plus every Hevy session that day with each exercise judged (status, PR, streaks).",
    {"type": "object", "additionalProperties": False, "properties": {"date": {"type": "string", "format": "date"}}},
)
async def get_daily_facts(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    day = datetime.date.fromisoformat(args["date"]) if args.get("date") else now.date()
    phase = phases.active(coach)
    if phase is None:
        raise ToolError("no active phase, so there are no daily facts")
    if day > now.date() or phases.daily_target(coach, day) is None:
        raise ToolError(f"{day} is outside the active phase (it started {phase['start_date']}; today is {now.date()})")
    record = history.day(coach.db, day.isoformat())
    if record is None:
        raise ToolError(f"nothing synced for {day} yet")
    moment = now if day == now.date() else datetime.datetime.combine(day, datetime.time(23, 59), tzinfo=now.tzinfo)
    facts = evening.daily_facts(coach, phase, phases.params(coach), record, moment)
    sessions = [progression.session(coach, s["id"]) for s in history.sessions(coach.db, day.isoformat(), day.isoformat())]
    return {"daily_facts": facts, "lift_sessions": [s for s in sessions if s is not None]}


@registry.tool(
    "load_skill",
    "Another skill's instructions by name (e.g. phase-review, photo-review, training-feedback).",
    {"type": "object", "required": ["name"], "additionalProperties": False, "properties": {"name": {"type": "string"}}},
)
async def load_skill(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    names = _skill_names(coach)
    if args["name"] not in names:
        raise ToolError(f"no skill {args['name']!r}; skills: {', '.join(names)}")
    return {"name": args["name"], "skill": coach.skills.skill(args["name"])}


def _skill_names(coach) -> list[str]:
    return sorted(p.parent.name for p in (coach.skills.root / "skills").glob("*/SKILL.md"))


def _lift_session(entry: dict[str, Any], exercise_id: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
    day = entry["date"]
    return {
        "date": day,
        "sets": entry["sets"],
        "top_set": entry["top"],
        "status": entry["status"],
        "not_judged_reason": entry["not_judged_reason"],
        "best_recent": entry["best_recent"],
        "is_pr": entry["is_pr"],
        "no_progress_streak": entry["no_progress_streak"],
        "decline_streak": entry["decline_streak"],
        "stalled": entry["stalled"],
        "notes": [{"text": n["text"], "tags": n["tags"]} for n in notes
                  if n["exercise_id"] == exercise_id and n["applies_from"] <= day <= (n["applies_to"] or "9999-12-31")],
    }
