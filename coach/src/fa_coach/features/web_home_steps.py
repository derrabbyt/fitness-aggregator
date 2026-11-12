"""The web page's Home steps block (coach-web ticket 04): the `steps` part of
`home` and the detail `home/steps` (the 14 days ending on the day).

Day steps are MFP's steps minus run steps (`phases.day_steps`); a day under
`steps.not_tracked_below` isn't tracked (no steps, no kcal). The step kcal
is the step part of the day's target, k x (day steps - goal), under the
targets valid that day; null without a step model (before a phase or its
start). The step goal is the one in force that day (`phases.params_on`), as
in `phases.daily_target`.
"""

import datetime
from typing import TYPE_CHECKING, Any

from .. import phases, views, weekdata
from ..registry import registry

if TYPE_CHECKING:
    from ..core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
DETAIL_DAYS = 14


@registry.view_part("home", "steps", schema="web_home_steps", order=30)
def steps(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    d = day_steps(coach, day)
    to_go = max(0, d["goal"] - d["steps"]) if d["tracked"] else None
    return {"tracked": d["tracked"], "steps": d["steps"], "goal": d["goal"], "to_go": to_go, "kcal": d["kcal"],
            "run_steps_removed": d["run_steps_removed"], "provisional": day == now.date()}


@registry.view("home/steps", schema="web_home_steps_detail")
def steps_detail(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    days = [day_steps(coach, d) for d in weekdata.dates(day - (DETAIL_DAYS - 1) * DAY, day)]
    tracked = [d["steps"] for d in days if d["tracked"]]
    return {
        "date": day.isoformat(),
        "goal": days[-1]["goal"],
        "days": [{k: d[k] for k in ("date", "tracked", "steps", "kcal", "run_steps_removed")} for d in days],
        "average_steps": round(sum(tracked) / len(tracked)) if tracked else None,
        "days_tracked": len(tracked),
        "days_at_goal": sum(1 for d in days if d["tracked"] and d["steps"] >= d["goal"]),
    }


def day_steps(coach: "Coach", day: Date) -> dict[str, Any]:
    """The day's steps, its step goal and its step kcal (None when not
    tracked or without a step model), with the values in force that day."""
    p = phases.params_on(coach, day)
    target = phases.daily_target(coach, day)
    part = target["steps"] if target else None
    d = part or {**phases.day_steps(coach, day, p), "goal": p["steps"]["step_goal"]}
    kcal = part["kcal"] if part and d["tracked"] else None
    return {"date": day.isoformat(), "tracked": d["tracked"], "steps": d["steps"], "goal": d["goal"], "kcal": kcal,
            "run_steps_removed": d["run_steps_removed"]}
