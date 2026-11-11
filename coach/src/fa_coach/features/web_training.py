"""The web page's Training tab (coach-web ticket 08): the `training` view,
as of a day (default today).

- `strength_trend`: `strength_trend.compute` (shared with Home's Workouts
  card) with a `TREND_DAYS`-day line.
- `lifts`: every lift in the Hevy history that counts, alphabetically, with
  its status and a short series for its small chart; `not_counted`: the
  excluded ones, the same way. Status comes from `progression.week` (a lift's
  latest session that wasn't ignored, judged against its history):
  progressing / same / declining, `stall` once a counting lift has
  `training.stall_sessions` sessions in a row without progress, `paused`,
  `new_baseline` (first session or after a reset), `not_judged` (back after a
  break, history still building) and `not_recent` (not trained within
  `training.lift_recency_days`).
- `activities`: runs and other sessions (wrestling, extras, sessions reported
  done without Hevy) of the last `ACTIVITY_DAYS` days, newest first, with
  the kcal they add to the day's target (`training_plan.counted_activity_on`;
  null before the activity setup values exist). Hevy lifting sessions are
  the lifts above, so they aren't repeated here.
"""

import datetime
from typing import Any

from .. import history, phases, progression, strength_trend, views, weekdata
from ..registry import registry
from . import training_plan

Date = datetime.date
DAY = datetime.timedelta(days=1)
TREND_DAYS = 28  # the strength trend's line here (Home shows 14 days)
SERIES_SESSIONS = 12  # sessions in a lift's small chart
ACTIVITY_DAYS = 28
IGNORED = ("no_working_sets", "other_location")
STATUS = {"improved": "progressing", "declined": "declining", "stale": "not_recent"}


@registry.view("training", schema="web_training")
def training(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    lifts = progression.lifts(coach, day)
    listed = [_lift(row, lifts[row["exercise_id"]])
              for row in progression.week(coach, day - 6 * DAY, day, Date.min)["tracked_lifts"]]
    listed.sort(key=lambda x: (x["name"].casefold(), x["exercise_id"]))
    counts = {x["exercise_id"]: x.pop("counts") for x in listed}
    return {
        "date": day.isoformat(),
        "freshness": views.freshness(coach, now),
        "strength_trend": strength_trend.compute(coach, day, days=TREND_DAYS, lifts=lifts),
        "lifts": [x for x in listed if counts[x["exercise_id"]]],
        "not_counted": [x for x in listed if not counts[x["exercise_id"]]],
        "activities": activities(coach, day - (ACTIVITY_DAYS - 1) * DAY, day),
    }


def activities(coach, start: Date, end: Date) -> list[dict[str, Any]]:
    """Runs and other sessions from `start` to `end`, newest first (module docstring)."""
    params = phases.params(coach)["activity"]
    known = all(params.get(k) is not None for k in training_plan.SETUP_KCAL.values()) \
        and params.get("run_kcal_discount") is not None
    if not known:  # list the sessions anyway; kcal only once the setup values exist
        params = {**params, **{k: params.get(k) or 0 for k in ("run_kcal_discount", *training_plan.SETUP_KCAL.values())}}
    out: list[dict[str, Any]] = []
    for day in reversed(weekdata.dates(start, end)):
        out += [{**item, "kcal_counted": item["kcal_counted"] if known else None}
                for item in _day(coach, day, params)]
    return out


def _day(coach, day: Date, params: dict[str, Any]) -> list[dict[str, Any]]:
    """The day's counted sessions (`counted_activity_on`), with distance and
    minutes from what they came from: the Strava entry, or the user's report."""
    iso = day.isoformat()
    counted = training_plan.counted_activity_on(coach, day, params, refs=True)["sessions"]
    record = history.day(coach.db, iso)
    strava = [e for e in (record["exercises"] if record else [])
              if e["run"] and (e["source"] or "").lower() == "strava"]
    reports = training_plan.statuses(coach, day)
    by_session = {s["session_id"]: s for s in reports if s["session_id"]}
    by_id = {s["id"]: s for s in reports}
    out = []
    for item in counted:
        kind, key = item["ref"]
        if kind == "hevy":
            continue  # a Hevy session: it's in the lifts
        if kind == "strava":
            origin = {"distance_km": strava[key]["distance_km"], "duration_min": strava[key]["minutes"]}
        else:
            origin = (by_session if kind == "plan" else by_id).get(key)
        out.append({"date": iso, "type": item["type"], "name": item["note"], "status": item["status"],
                    "distance_km": origin["distance_km"] if origin else None,
                    "minutes": origin["duration_min"] if origin else None,
                    "kcal_counted": round(item["kcal_counted"])})
    return out


def _lift(row: dict[str, Any], lift: dict[str, Any]) -> dict[str, Any]:
    status = "stall" if row["stalled"] else STATUS.get(row["status"], row["status"])
    entries = [e for e in lift["entries"] if e["top"] is not None and e["not_judged_reason"] not in IGNORED]
    resets = [k for k, e in enumerate(entries) if e["not_judged_reason"] == "baseline_reset"]
    if resets:
        entries = entries[resets[-1]:]
    return {
        "exercise_id": row["exercise_id"],
        "name": row["name"],
        "counts": row["counts"],
        "status": status,
        "not_judged_reason": row["not_judged_reason"],
        "bodyweight_exercise": row["bodyweight_exercise"],
        "last_session_date": row["last_session_date"],
        "latest": row["latest"],
        "series": [{"date": e["date"], "e1rm_kg": e["top"]["e1rm_kg"]} for e in entries[-SERIES_SESSIONS:]],
    }
