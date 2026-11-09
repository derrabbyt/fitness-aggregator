"""Per-day numbers shared by the weekly facts and the daily facts (week so
far): intake vs daily targets, steps, counted sessions. Every number is
computed here in code; dates are inclusive.

- `intake(coach, start, end, params)`: one entry per day (the weekly-facts
  `intake_day` shape) plus the counted sessions and macro targets behind them.
- `intake_summary(days, params)`: target and actual totals, deviation and
  the adherence check for those days.
- `steps(coach, start, end, params)`: steps per day, average, days below the floor.

The 7-day trend weight is `phases.trend_weight`.
"""

import datetime
import statistics
from typing import TYPE_CHECKING, Any

from . import history, phases

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)


def dates(start: Date, end: Date) -> list[Date]:
    return [start + n * DAY for n in range((end - start).days + 1)]


def intake(coach: "Coach", start: Date, end: Date) -> dict[str, Any]:
    """{days: [intake_day], sessions: [counted sessions], macros: [daily
    macro targets]} for the days of the active phase from `start` to `end`.
    A day is `complete` when food is logged in MFP (any entry, or the day
    marked complete), else `missing`; MFP can't tell a partly logged day."""
    synced = {d["date"]: d for d in history.days(coach.db, start.isoformat(), end.isoformat())}
    out: dict[str, Any] = {"days": [], "sessions": [], "macros": []}
    for day in dates(start, end):
        target = phases.daily_target(coach, day)
        if target is None:
            continue
        food = synced.get(day.isoformat()) or {}
        logged = bool(food.get("logged")) and food.get("kcal") is not None
        out["days"].append({
            "date": day.isoformat(),
            "logged": "complete" if logged else "missing",
            "target_kcal": target["kcal"],
            "actual_kcal": food.get("kcal") if logged else None,
            **{k: food.get(k) if logged else None for k in ("protein_g", "fat_g", "carbs_g", "fiber_g", "produce_g")},
        })
        out["sessions"].extend(target["activity"]["sessions"])
        out["macros"].append(target["macros"])
    return out


def intake_summary(days: list[dict[str, Any]], p: dict[str, Any]) -> dict[str, Any]:
    """Totals over `days` (intake_day entries): target, actual (logged days),
    deviation in % (only when every day is logged) and adherence: every day
    logged (if required) and the deviation within the weekly tolerance."""
    target = sum(d["target_kcal"] for d in days)
    logged = [d for d in days if d["logged"] == "complete"]
    complete = len(logged) == len(days) and bool(days)
    actual = round(sum(d["actual_kcal"] for d in logged)) if logged else None
    deviation = round((actual - target) / target * 100, 1) if complete and target else None
    all_logged_ok = complete or not p["adherence"]["require_all_eating_logged"]
    adherence = (all_logged_ok and deviation is not None
                 and abs(deviation) <= p["adherence"]["weekly_intake_tolerance_pct"])
    return {"target_kcal": target, "actual_kcal": actual, "deviation_pct": deviation, "days_logged": len(logged),
            "complete": complete, "adherence_ok": adherence}


def steps(coach: "Coach", start: Date, end: Date, p: dict[str, Any]) -> dict[str, Any]:
    synced = {d["date"]: d["steps"] for d in history.days(coach.db, start.isoformat(), end.isoformat())}
    daily = [{"date": d.isoformat(), "steps": synced.get(d.isoformat())} for d in dates(start, end)]
    known = [d["steps"] for d in daily if d["steps"] is not None]
    floor = p["activity"]["soft_step_floor"]
    return {
        "steps_daily": daily,
        "avg_steps": round(statistics.fmean(known)) if known else None,
        "soft_step_floor": floor,
        "days_below_floor": sum(1 for s in known if s < floor),
    }
