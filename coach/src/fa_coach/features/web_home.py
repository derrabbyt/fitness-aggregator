"""The web page's Home (coach-web ticket 02): the `home` view (the day, its
freshness) with its food part, and the food detail `home/food` (the check-in
week so far). Other Home blocks (weight, steps, training, banner) are parts
in their own modules: `@registry.view_part("home", "<key>", schema=...)`.

Food is the coach's daily target (`phases.daily_target`: base at the step
goal, steps, counted sessions, surplus), never MFP's goal, as it stood that
day. Before a phase (or before its start) food has no targets.
"""

import datetime
from typing import Any

from .. import daycheck, history, phases, views, weekdata, weekly_facts
from ..registry import registry

Date = datetime.date
DAY = datetime.timedelta(days=1)
MACROS = ("protein", "carbs", "fat")


@registry.view("home", schema="web_home")
def home(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    return {"date": day.isoformat(), "is_today": day == now.date(), "freshness": views.freshness(coach, now)}


@registry.view_part("home", "food", schema="web_home_food", order=10)
def food(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    target = phases.daily_target(coach, day)
    eaten = _eaten(coach, day, now)
    macros: dict[str, Any] = {
        k: {"eaten_g": eaten[f"{k}_g"], "target_g": target["macros"][f"{k}_g"] if target else None} for k in MACROS
    }
    fiber = _fiber_target(coach, target)
    macros["fiber"] = {"eaten_g": eaten["fiber_g"], "target_g": fiber[0], "target_max_g": fiber[1]}
    kcal_target = target["kcal"] if target else None
    left = None if kcal_target is None else kcal_target - (eaten["kcal"] or 0)
    return {
        "kcal": {"eaten": eaten["kcal"], "target": kcal_target, "left": left},
        "build_up": build_up(target),
        "logged": eaten["logged"],
        "macros": macros,
    }


def build_up(target: dict[str, Any] | None) -> dict[str, int] | None:
    """How the daily target is built (ticket 15): base at the step goal +
    activity (counted sessions and the step kcal ±, one number) + surplus
    (signed; negative is a deficit) = the target, exactly (rounding goes to
    activity). None without a target."""
    if target is None:
        return None
    base, surplus = target["base_at_step_goal_kcal"], target["surplus_kcal"]
    return {"base_kcal": base, "activity_kcal": target["kcal"] - base - surplus, "surplus_kcal": surplus,
            "total_kcal": target["kcal"]}


@registry.view("home/food", schema="web_home_food_detail")
def food_detail(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    """The check-in week (the 7 days the weekly check-in judges) up to the day."""
    day = views.day(query, now)
    start = check_in_week_start(coach, day)
    days = []
    for d in weekdata.dates(start, day):
        target = phases.daily_target(coach, d)
        eaten = _eaten(coach, d, now)
        days.append({"date": d.isoformat(), "eaten_kcal": eaten["kcal"],
                     "target_kcal": target["kcal"] if target else None, "logged": eaten["logged"]})
    counted = [d for d in days if d["logged"] == "complete"]
    eaten_total = sum(d["eaten_kcal"] for d in counted) if counted else None
    with_target = bool(counted) and all(d["target_kcal"] is not None for d in counted)
    target_total = sum(d["target_kcal"] for d in counted) if with_target else None
    deviation = (round((eaten_total - target_total) / target_total * 100, 1)
                 if eaten_total is not None and target_total else None)
    return {
        "date": day.isoformat(),
        "start": start.isoformat(),
        "end": (start + 6 * DAY).isoformat(),
        "iso_week": weekly_facts.iso_week(start + 6 * DAY),
        "days": days,
        "so_far": {"days_logged": len(counted), "eaten_kcal": eaten_total, "target_kcal": target_total,
                   "deviation_pct": deviation},
    }


def check_in_week_start(coach, day: Date) -> Date:
    """The first day of the check-in week holding `day`: the check-in judges
    the 7 days before its weekday, so a week starts on that weekday (Monday
    without a check-in day)."""
    weekday = weekly_facts.checkin_weekday(coach)
    weekday = 0 if weekday is None else weekday
    return day - ((day.weekday() - weekday) % 7) * DAY


def _eaten(coach, day: Date, now: datetime.datetime) -> dict[str, Any]:
    """The day's synced food (whole numbers) and how it is logged: complete,
    partial (an earlier day suspected partly logged and not confirmed;
    daycheck.py) or missing."""
    record = history.day(coach.db, day.isoformat())
    logged = bool(record and record["logged"] and record["kcal"] is not None)
    out: dict[str, Any] = {k: _round(record[k]) if logged else None
                           for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")}
    status = "missing"
    if logged:
        check = daycheck.status(coach, day, phases.params_on(coach, day)) if day < now.date() else None
        status = "partial" if check and check["incomplete"] else "complete"
    out["logged"] = status
    return out


def _fiber_target(coach, target: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """Fiber in g/kg of the macro reference weight (a range), None without a target."""
    if target is None:
        return None, None
    low, high = phases.params_on(coach, Date.fromisoformat(target["date"]))["nutrition"]["fiber_g_per_kg"]
    weight = target["macros"]["reference_weight_kg"]
    return round(low * weight), round(high * weight)


def _round(value: float | None) -> int | None:
    return round(value) if value is not None else None
