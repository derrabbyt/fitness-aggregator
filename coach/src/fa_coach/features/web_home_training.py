"""Home's training part (coach-web ticket 05): the day's sessions in two
blocks, as they stood that day.

- Workouts (ticket 14): Hevy sessions (name, PRs set in it, time of day,
  duration), a planned lift reported done without a Hevy session, lifting
  extras; the 14-day strength trend with its rate (`strength_trend.compute`)
  and the summary over the last `training.lift_recency_days` (14) days
  (`progression.week`: counted lifts progressing, stalls, PRs).
- Other activities: Strava runs (distance, duration, pace), a planned run
  reported done when Strava has none, wrestling (planned from the active
  phase's start on, as counted activity counts it, or reported), planned
  "other" sessions reported done, and extras.

Each line carries `kcal_counted` (ticket 15): the kcal it adds to the day's
target, from counted activity (`training_plan.counted_activity_on`), so the
lines agree with the food target line; null when it adds nothing (not
counted, or no target: before a phase).

A planned session reported skipped is not listed (it did not happen). Unreported
runs, lifts and optional sessions are not listed: they show once they sync.
HealthKit copies in MFP never show (as in counted activity).
"""

import datetime
from typing import Any

from .. import history, phases, progression, strength_trend, views
from ..registry import registry
from . import training_plan

Date = datetime.date
TIME_LABELS = {"morning": "08:00", "midday": "12:00", "afternoon": "15:00", "evening": "19:00"}  # sort order only


@registry.view_part("home", "training", schema="web_home_training", order=40)
def training(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    lifts = progression.lifts(coach, day)
    prs = _prs_per_session(lifts)
    kcal = _kcal_per_line(coach, day)
    workouts, other = [], []
    for item in sessions(coach, day, now):
        session_id = item.pop("session_id")
        counted = kcal.get(item.pop("ref"))
        item["kcal_counted"] = round(counted) if counted else None
        if item["type"] == "lift":
            workouts.append({**item, "prs": prs.get(session_id, 0) if session_id else None})
        else:
            other.append(item)
    return {
        "workouts": {"sessions": workouts, "strength_trend": strength_trend.compute(coach, day, lifts=lifts),
                     "summary": summary(coach, day)},
        "other_activities": {"sessions": other},
    }


def _kcal_per_line(coach, day: Date) -> dict[tuple, float]:
    """Counted kcal per line ref ({} without a target that day)."""
    if phases.daily_target(coach, day) is None:
        return {}
    activity = training_plan.counted_activity_on(coach, day, phases.params(coach)["activity"], refs=True)
    return {s["ref"]: s["kcal_counted"] for s in activity["sessions"] if s["status"] != "skipped"}


def _prs_per_session(lifts: dict[str, dict[str, Any]]) -> dict[str, int]:
    """PRs per Hevy session (paused exercises set none, as in progression.week)."""
    out: dict[str, int] = {}
    for lift in lifts.values():
        if not lift["paused"]:
            for e in lift["entries"]:
                if e["is_pr"]:
                    out[e["session_id"]] = out.get(e["session_id"], 0) + 1
    return out


def sessions(coach, day: Date, now: datetime.datetime) -> list[dict[str, Any]]:
    """The day's sessions, one line each, in time order (untimed last)."""
    iso = day.isoformat()
    out: list[dict[str, Any]] = []
    lifts = history.sessions(coach.db, iso, iso)
    for s in lifts:
        out.append({**_line("lift", s["name"] or "Workout", _clock(s["start"], now), s["minutes"],
                            ref=("hevy", s["id"])), "session_id": s["id"]})
    record = history.day(coach.db, iso)
    strava = [e for e in (record["exercises"] if record else [])
              if e["run"] and (e["source"] or "").lower() == "strava"]
    for n, e in enumerate(strava):
        out.append(_line("run", e["name"] or "Run", _clock(e.get("start_at"), now), e["minutes"],
                         distance_km=e["distance_km"], ref=("strava", n)))
    reported = training_plan.statuses(coach, day)
    by_session = {s["session_id"]: s for s in reported if s["session_id"]}
    phase = phases.active(coach)
    planned_counts = phase is not None and day >= Date.fromisoformat(phase["start_date"])
    plan = training_plan.plan_for(coach, day)
    for planned in plan["days"][training_plan.WEEKDAYS[day.weekday()]] if plan else []:
        report = by_session.get(planned["id"])
        status = report["status"] if report else None
        kind, name, time, ref = planned["type"], planned["name"], planned["time"], ("plan", planned["id"])
        if status == "skipped":
            continue
        elif kind == "wrestling" and (status == "done" or planned_counts):
            out.append(_reported_line(kind, name, time, report, ref))
        elif status != "done":
            continue
        elif (kind == "lift" and not lifts) or (kind == "run" and not strava) or kind == "other":
            out.append(_reported_line(kind, name, time, report, ref))
    for extra in (s for s in reported if s["status"] == "extra"):
        out.append(_reported_line(extra["type"], extra["name"] or extra["type"].capitalize(), None, extra,
                                   ("extra", extra["id"])))
    return sorted(out, key=lambda s: (s["time"] is None, TIME_LABELS.get(s["time"], s["time"] or "")))


def summary(coach, day: Date) -> dict[str, int] | None:
    """Counted lifts progressing of counted, stalls, and PRs over the
    `lift_recency_days` (14) days up to `day` (the lift status's recency
    window); None before any lift was trained."""
    recency = phases.params(coach)["training"]["lift_recency_days"]
    week = progression.week(coach, day - (recency - 1) * datetime.timedelta(days=1), day)
    if not week["tracked_lifts"]:
        return None
    return {"progressing": week["improved_lifts"], "counted": week["counted_lifts"], "stalls": len(week["stalls"]),
            "prs": len(week["prs"])}


def _reported_line(kind: str, name: str, time: str | None, report: dict[str, Any] | None,
                   ref: tuple) -> dict[str, Any]:
    minutes = report["duration_min"] if report else None
    distance = report["distance_km"] if report else None
    return _line(kind, name, time, minutes, distance_km=distance, ref=ref)


def _line(kind: str, name: str, time: str | None, minutes: float | None, *, distance_km: float | None = None,
          ref: tuple | None = None) -> dict[str, Any]:
    pace = round(minutes * 60 / distance_km) if kind == "run" and minutes and distance_km else None
    return {"type": kind, "name": name, "time": time, "minutes": round(minutes) if minutes is not None else None,
            "distance_km": round(distance_km, 2) if distance_km is not None else None,
            "pace_s_per_km": pace, "session_id": None, "ref": ref}


def _clock(start: str | None, now: datetime.datetime) -> str | None:
    """HH:MM in the coach's local time from an ISO timestamp, None if unknown."""
    if not start:
        return None
    try:
        at = datetime.datetime.fromisoformat(start)
    except ValueError:
        return None
    if at.tzinfo is not None and now.tzinfo is not None:
        at = at.astimezone(now.tzinfo)
    return at.strftime("%H:%M")
