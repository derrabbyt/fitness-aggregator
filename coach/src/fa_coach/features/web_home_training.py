"""Home's training part (coach-web ticket 05): the day's sessions in two
blocks, as they stood that day.

- Gym: Hevy sessions (name, time of day, duration), a planned lift reported
  done without a Hevy session, lifting extras; under them the lift trend line
  (`progression.week` as of the day: counted lifts progressing, stalls, PRs
  in the check-in week so far) and the 4-week strength trend
  (`strength_trend.compute`).
- Other activities: Strava runs (distance, duration, pace), a planned run
  reported done when Strava has none, wrestling (planned from the active
  phase's start on, as counted activity counts it, or reported), planned
  "other" sessions reported done, and extras.

A planned session reported skipped stays listed, marked skipped. Unreported
runs, lifts and optional sessions are not listed: they show once they sync.
HealthKit copies in MFP never show (as in counted activity).
"""

import datetime
from typing import Any

from .. import history, phases, progression, strength_trend, views
from ..registry import registry
from . import training_plan
from .web_home import check_in_week_start

Date = datetime.date
TIME_LABELS = {"morning": "08:00", "midday": "12:00", "afternoon": "15:00", "evening": "19:00"}  # sort order only


@registry.view_part("home", "training", schema="web_home_training", order=40)
def training(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    gym, other = [], []
    for item in sessions(coach, day, now):
        (gym if item["type"] == "lift" else other).append(item)
    return {
        "gym": {"sessions": gym, "trend": trend_line(coach, day), "strength_trend": strength_trend.compute(coach, day)},
        "other": {"sessions": other},
    }


def sessions(coach, day: Date, now: datetime.datetime) -> list[dict[str, Any]]:
    """The day's sessions, one line each, in time order (untimed last)."""
    iso = day.isoformat()
    out: list[dict[str, Any]] = []
    lifts = history.sessions(coach.db, iso, iso)
    for s in lifts:
        out.append(_line("lift", s["name"] or "Workout", _clock(s["start"], now), s["minutes"]))
    record = history.day(coach.db, iso)
    strava = [e for e in (record["exercises"] if record else [])
              if e["run"] and (e["source"] or "").lower() == "strava"]
    for e in strava:
        out.append(_line("run", e["name"] or "Run", _clock(e.get("start_at"), now), e["minutes"],
                         distance_km=e["distance_km"]))
    reported = training_plan.statuses(coach, day)
    by_session = {s["session_id"]: s for s in reported if s["session_id"]}
    phase = phases.active(coach)
    planned_counts = phase is not None and day >= Date.fromisoformat(phase["start_date"])
    plan = training_plan.plan_for(coach, day)
    for planned in plan["days"][training_plan.WEEKDAYS[day.weekday()]] if plan else []:
        report = by_session.get(planned["id"])
        status = report["status"] if report else None
        kind, name, time = planned["type"], planned["name"], planned["time"]
        if status == "skipped":
            out.append(_line(kind, name, time, None, skipped=True))
        elif kind == "wrestling" and (status == "done" or planned_counts):
            out.append(_reported_line(kind, name, time, report))
        elif status != "done":
            continue
        elif (kind == "lift" and not lifts) or (kind == "run" and not strava) or kind == "other":
            out.append(_reported_line(kind, name, time, report))
    for extra in (s for s in reported if s["status"] == "extra"):
        out.append(_reported_line(extra["type"], extra["name"] or extra["type"].capitalize(), None, extra))
    return sorted(out, key=lambda s: (s["time"] is None, TIME_LABELS.get(s["time"], s["time"] or "")))


def trend_line(coach, day: Date) -> dict[str, int] | None:
    """Counted lifts progressing of counted, stalls, and PRs from the start of
    the check-in week to `day`; None before any lift was trained."""
    week = progression.week(coach, check_in_week_start(coach, day), day)
    if not week["tracked_lifts"]:
        return None
    return {"progressing": week["improved_lifts"], "counted": week["counted_lifts"], "stalls": len(week["stalls"]),
            "prs": len(week["prs"])}


def _reported_line(kind: str, name: str, time: str | None, report: dict[str, Any] | None) -> dict[str, Any]:
    minutes = report["duration_min"] if report else None
    distance = report["distance_km"] if report else None
    return _line(kind, name, time, minutes, distance_km=distance)


def _line(kind: str, name: str, time: str | None, minutes: float | None, *, distance_km: float | None = None,
          skipped: bool = False) -> dict[str, Any]:
    pace = round(minutes * 60 / distance_km) if minutes and distance_km else None
    return {"type": kind, "name": name, "time": time, "minutes": round(minutes) if minutes is not None else None,
            "distance_km": round(distance_km, 2) if distance_km is not None else None,
            "pace_s_per_km": pace, "skipped": skipped}


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
