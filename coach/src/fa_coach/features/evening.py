"""Evening reminder and recap (ticket 11; spec "Daily messages").

Once a day, at the evening reminder time (setup value
`messaging.evening_reminder_time`) and only while a phase is active:

1. Sync, so a log made since the last scheduled sync counts.
2. If today's food, weight or steps are missing: the missing-log reminder,
   code only, naming what's missing. Nothing else that evening.
3. If today's intake is in question (a suspected partial or implausibly
   high day, not confirmed; ticket 20), code asks with buttons
   (features/day_questions.py) and there is no recap.
4. Otherwise code computes the daily facts (kind evening) and the
   evening-recap skill returns a coach message. `send: false` sends nothing;
   `deferred_to_weekly` items are stored for the weekly report
   (`messaging.deferred`).

Both messages count toward the daily message limit (`messaging.send`). A
reminder or recap held back by the limit is stored as a deferred item instead. In the
glycogen window the facts carry no weight values, so the recap can't comment
on weight.
"""

import datetime
import logging
from typing import Any

from .. import daycheck, history, messaging, phases
from ..registry import registry
from . import context_notes, day_questions, training_plan

logger = logging.getLogger("fa-coach")

Date = datetime.date
DAY = datetime.timedelta(days=1)
SKILL = "evening-recap"
REMINDER = "evening-reminder"


@registry.job("evening", order=5)  # before stale-data: its own sync counts there
async def evening(coach, now: datetime.datetime) -> None:
    phase = phases.active(coach)
    if phase is None:
        return
    p = phases.params(coach)
    reminder_at = p["messaging"].get("evening_reminder_time")
    if not reminder_at or now.time() < datetime.time.fromisoformat(reminder_at):
        return
    today = now.date()
    if phases.daily_target(coach, today) is None or not coach.db.once(f"evening:{today.isoformat()}", now):
        return
    await coach.sync(now)
    record = history.day(coach.db, today.isoformat())
    missing = _missing(record)
    if missing:
        if p["messaging"].get("missing_log_reminders_per_day", 1) > 0:
            text = _reminder(missing)
            if not messaging.send(coach, text, now, kind=REMINDER):
                messaging.defer(coach, today, text, REMINDER, now)
        return
    if day_questions.ask_today(coach, now):  # today's intake is in question: ask, no recap
        return
    await _recap(coach, phase, p, record, now)


def _missing(record: dict[str, Any] | None) -> list[str]:
    if record is None:
        return ["food", "weight", "steps"]
    missing = []
    if not record["logged"]:
        missing.append("food")
    if record["weight_kg"] is None:
        missing.append("weight")
    if not record["steps"]:
        missing.append("steps")
    return missing


def _reminder(missing: list[str]) -> str:
    names = missing[0] if len(missing) == 1 else ", ".join(missing[:-1]) + " and " + missing[-1]
    verb = "is" if len(missing) == 1 else "are"
    return f"Evening check: today's {names} {verb} not in MyFitnessPal yet."


async def _recap(coach, phase: dict[str, Any], p: dict[str, Any], record: dict[str, Any],
                 now: datetime.datetime) -> None:
    today = now.date()
    facts = daily_facts(coach, phase, p, record, now)
    problems = coach.skills.errors(facts, "daily_facts")
    if problems:
        logger.error("evening facts don't match the schema, no recap: %s", problems)
        return
    answer = await coach.ask((SKILL,), facts, tools=(), output_schema="coach_message", now=now)
    if answer.data is None:
        logger.warning("evening recap not usable: %s", answer.errors)
        return
    for item in answer.data["deferred_to_weekly"]:
        messaging.defer(coach, today, item, SKILL, now)
    text = answer.data["text"].strip()
    if answer.data["send"] and text:
        if not messaging.send(coach, text, now, kind=SKILL):
            messaging.defer(coach, today, text, SKILL, now)


def daily_facts(coach, phase: dict[str, Any], p: dict[str, Any], record: dict[str, Any],
                now: datetime.datetime) -> dict[str, Any]:
    """Daily facts (kind evening) for today, per daily_facts.schema.json."""
    today = now.date()
    week = phases.phase_week(phase, today)
    glycogen = phases.in_glycogen_window(coach, today)
    target = phases.daily_target(coach, today)
    week_start = Date.fromisoformat(phase["start_date"]) + (week - 1) * 7 * DAY
    intake = _intake(record, target["kcal"], daycheck.status(coach, today, p))
    macro_targets = {k: target["macros"][k] for k in ("protein_g", "fat_g", "carbs_g", "reference_weight_kg")}
    activity = training_plan.counted_activity_on(coach, today, p["activity"])
    factor = p["data"]["implausible_intake_factor"]
    return {
        "schema_version": 1,
        "date": today.isoformat(),
        "kind": "evening",
        "phase_id": phase["phase_id"],
        "phase_week": week,
        "in_glycogen_window": glycogen,
        "messages_sent_today": messaging.sent_today(coach, now),
        "context_notes_today": context_notes.between(coach, today, today),
        "day": {
            "intake": intake,
            "macro_targets": macro_targets,
            "vs_target": {
                "kcal_pct": _pct(intake["actual_kcal"], target["kcal"]),
                "protein_pct": _pct(intake["protein_g"], macro_targets["protein_g"]),
                "fat_pct": _pct(intake["fat_g"], macro_targets["fat_g"]),
            },
            "checks": {
                "implausible_intake": (intake["actual_kcal"] or 0) > factor * target["kcal"],
            },
            "weight": _weight(coach, record, today, glycogen),
            "steps": record["steps"],
            "target_build_up": _build_up(target),
            "sessions": activity["sessions"],
            "week_to_date": _week_to_date(coach, week_start, today, p),
        },
        "params": p,
    }


def _build_up(target: dict[str, Any]) -> dict[str, Any]:
    """How today's target is made: base at the step goal + step kcal (so far:
    today's steps are provisional) + counted sessions + surplus."""
    steps = target["steps"]
    return {
        "base_at_step_goal_kcal": target["base_at_step_goal_kcal"],
        "step_goal": steps["goal"] if steps else None,
        "day_steps": steps["steps"] if steps else None,
        "steps_tracked": steps["tracked"] if steps else False,
        "step_kcal": steps["kcal"] if steps else None,
        "sessions_kcal": round(target["activity"]["kcal"]),
        "surplus_kcal": target["surplus_kcal"],
        "target_kcal": target["kcal"],
    }


def _intake(record: dict[str, Any], target_kcal: float, check: dict[str, Any] | None) -> dict[str, Any]:
    # MFP can't tell a partial day from a complete one; code suspects one from
    # its kcal (daycheck.py) and asks before the recap runs.
    check = check or {}
    return {
        "date": record["date"],
        "logged": ("partial" if check.get("incomplete") else "complete") if record["logged"] else "missing",
        "target_kcal": target_kcal,
        "actual_kcal": _round(record["kcal"]),
        "protein_g": _round(record["protein_g"]),
        "fat_g": _round(record["fat_g"]),
        "carbs_g": _round(record["carbs_g"]),
        "fiber_g": _round(record["fiber_g"]),
        "produce_g": _round(record["produce_g"]),
        "partial_suspected": bool(check.get("partial_suspected")),
        "confirmed": bool(check.get("confirmed")),
    }


def _weight(coach, record: dict[str, Any], today: Date, glycogen: bool) -> dict[str, Any]:
    if glycogen:
        return {"kg": None, "avg_7d_kg": None, "outlier": False, "withheld": True}
    trend = phases.trend_weight(coach, today)
    return {"kg": record["weight_kg"], "avg_7d_kg": round(trend, 1) if trend is not None else None,
            "outlier": record["weight_outlier"], "withheld": False}


def _week_to_date(coach, week_start: Date, today: Date, p: dict[str, Any]) -> dict[str, Any]:
    """The phase week so far (its first day to today), over the days with
    food logged (unconfirmed partial days left out)."""
    incomplete = daycheck.incomplete_days(coach, week_start, today, p)
    logged = [d for d in history.days(coach.db, week_start.isoformat(), today.isoformat())
              if d["logged"] and d["kcal"] is not None and d["date"] not in incomplete]
    target = sum(phases.daily_target(coach, Date.fromisoformat(d["date"]))["kcal"] for d in logged)
    actual = round(sum(d["kcal"] for d in logged)) if logged else None
    return {
        "days_elapsed": (today - week_start).days + 1,
        "days_logged": len(logged),
        "target_kcal_so_far": target,
        "actual_kcal_so_far": actual,
        "deviation_pct": round((actual - target) / target * 100, 1) if logged and target else None,
    }


def _pct(actual: float | None, target: float) -> float | None:
    return round(actual / target * 100, 1) if actual is not None and target else None


def _round(value: float | None) -> float | None:
    return round(value) if value is not None else None
