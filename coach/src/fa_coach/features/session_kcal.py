"""The kcal of a session the user reports in chat (spec, story 19).

`resolve(...)` picks, in this order: the user's own number (`reported`); code's
estimate, MET x current 7-day trend weight (kg) x hours with the MET from
`activity.met_by_activity` (`estimated`); the model's own number when code
can't estimate (unknown activity, no trend weight; `model_estimate`).
Wrestling and lifting without the user's number count their per-session setup
values instead, so they store no kcal. Used by `set_session_status`
(features/training_plan.py).
"""

import datetime
import re
from typing import Any

from .. import history
from ..ask import ToolError

SETUP_TYPES = ("wrestling", "lift")


def resolve(coach, args: dict[str, Any], kind: str, now: datetime.datetime, *, required: bool) -> dict[str, Any]:
    """Columns for session_statuses (kcal, kcal_source, activity, duration_min,
    met, trend_weight_kg) plus `say`, the line the model passes on. With
    `required` false (a planned run that may still sync) no inputs at all is
    fine; otherwise missing inputs raise ToolError telling the model what to do."""
    activity = _key(args.get("activity")) or ("running" if kind == "run" else None)
    duration = args.get("duration_min")
    row = {"kcal": None, "kcal_source": None, "activity": activity if "activity" in args or duration else None,
           "duration_min": duration, "met": None, "trend_weight_kg": None}
    if "kcal" in args:
        return {**row, "kcal": args["kcal"], "kcal_source": "reported",
                "say": f"Counted {_n(args['kcal'])} kcal as the user gave them."}
    if kind in SETUP_TYPES:
        return {**row, "say": f"Counts the {kind} kcal per session from setup; the user can give a number instead."}
    estimate = args.get("kcal_estimate")
    if duration is None and estimate is None:
        if not required and "activity" not in args:
            return {**row, "say": "No kcal: counts only if it syncs from Strava; a duration would let code estimate."}
        if activity is None:
            raise ToolError("give the user's kcal, or `activity` + `duration_min` so code estimates them")
        raise ToolError("no duration: ask the user how long (once), or pass `duration_min` if the description "
                        "makes it obvious; if you can't, pass your own `kcal_estimate`")
    met = coach.skills.params()["activity"]["met_by_activity"].get(activity) if activity else None
    weight = history.trend_weight_kg(coach.db, now.date().isoformat())
    if met is not None and weight is not None and duration is not None:
        kcal = round(met * weight * duration / 60)
        return {**row, "kcal": kcal, "kcal_source": "estimated", "met": met, "trend_weight_kg": weight,
                "estimate": {"activity": activity, "met": met, "trend_weight_kg": weight, "duration_min": duration},
                "say": f"Counted {kcal} kcal, estimated by code ({activity}, {_n(duration)} min at {weight} kg); "
                       "say it's an estimate the user can correct."}
    if activity is None:
        reason = "no activity type given"
    elif met is None:
        reason = f"code has no MET for {activity!r} (known: {', '.join(coach.skills.params()['activity']['met_by_activity'])})"
    elif weight is None:
        reason = "there is no trend weight yet (no weigh-ins in the last 7 days)"
    else:
        reason = "no duration given"
    if estimate is None:
        raise ToolError(f"code can't estimate: {reason}. Pass your own `kcal_estimate`, or ask the user for the kcal")
    return {**row, "kcal": estimate, "kcal_source": "model_estimate",
            "say": f"Counted {_n(estimate)} kcal, your estimate ({reason}); say it's your estimate so the user can "
                   "correct it."}


def _key(activity: str | None) -> str | None:
    return re.sub(r"[\s-]+", "_", activity.strip().lower()) if activity else None


def _n(x: float) -> str:
    return f"{x:g}"
