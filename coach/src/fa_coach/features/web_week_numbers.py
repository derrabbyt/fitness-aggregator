"""The Week page's number blocks (coach-web ticket 07), parts of the `week`
view (web_week.py): `weight`, `intake`, `training` and `notes`.

- A judged week (`week.stored`) reads the numbers its check-in stored in the
  weekly facts (`source: "check_in"`): what the coach judged.
- Any other week inside a phase shows them so far (`source: "so_far"`), from
  the same code the weekly facts use (weekdata.py, progression.py), over the
  week's days up to today.
- A week with no phase during it has no number blocks (null).

Every block also reads a few things the facts don't keep: the weight chart
(trend and weigh-ins by day), the planned sessions, the context notes and
deferred items about the week, and the measurements due the week after.
"""

import datetime
from typing import TYPE_CHECKING, Any

from .. import history, messaging, phases, progression, weekdata, weekly_facts
from ..registry import registry
from . import context_notes, measurements, training_plan, web_home_steps, web_week, web_weight

if TYPE_CHECKING:
    from ..core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)


def _week(coach, query: dict[str, str], now: datetime.datetime) -> web_week.Week | None:
    """The week, or None when no phase was active during it (and it wasn't judged)."""
    w = web_week.resolve(coach, query, now)
    if w.stored is None and web_week.phase_during(coach, w) is None:
        return None
    return w


def _last(w: web_week.Week) -> Date:
    """The week's last day so far."""
    return min(w.today, w.end)


def _in_phase(coach: "Coach", w: web_week.Week, day: Date) -> Date:
    """`day`, or the last day of the week's phase when it ended before."""
    phase = web_week.phase_during(coach, w)
    if phase and phase["end_date"] and phase["end_date"] < day.isoformat():
        return Date.fromisoformat(phase["end_date"])
    return day


def _params(coach: "Coach", w: web_week.Week) -> dict[str, Any]:
    """The params in force on the week's last day so far inside its phase."""
    return phases.params_on(coach, _in_phase(coach, w, _last(w)))


# --- weight --------------------------------------------------------------------------------


@registry.view_part("week", "weight", schema="web_week_weight", order=10)
def weight(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any] | None:
    w = _week(coach, query, now)
    if w is None:
        return None
    last = _last(w)
    if w.stored is not None:
        facts = w.stored["facts"]
        fw = facts["weight"]
        out = {
            "source": "check_in",
            "trend_kg": fw["avg_7d_kg"],
            "prev_trend_kg": fw["prev_avg_7d_kg"],
            "weekly_rate_kg": fw["weekly_rate_kg"],
            "rate_window": "week",
            "band": {"low": fw["band"]["low"], "high": fw["band"]["high"]},
            "vs_band": fw["vs_band"],
            "weigh_ins": facts["data_quality"]["weigh_in_count"],
            "weigh_ins_needed": facts["params"]["data"]["min_weighins_per_week"],
        }
    else:
        # So far: the 7-day rate ending today, as Home shows it.
        bands = web_weight.Bands(coach)
        band = bands.on(_in_phase(coach, w, w.end))
        rate = weekly_facts.weekly_rate(coach, last)
        out = {
            "source": "so_far",
            "trend_kg": phases.trend_weight(coach, last),
            "prev_trend_kg": phases.trend_weight(coach, w.start - DAY),
            "weekly_rate_kg": rate,
            "rate_window": "last_7_days",
            "band": {"low": band["low"], "high": band["high"]} if band else None,
            "vs_band": bands.vs_band(last, rate),
            "weigh_ins": len(history.weigh_ins(coach.db, w.start.isoformat(), last.isoformat())),
            "weigh_ins_needed": _params(coach, w)["data"]["min_weighins_per_week"],
        }
    out["days"] = (last - w.start).days + 1
    judged = out["band"] is not None and out["vs_band"] != "not_evaluated"
    out["series"] = _series(coach, w.start - DAY, last, out["band"] if judged else None)
    return out


# --- intake --------------------------------------------------------------------------------


@registry.view_part("week", "intake", schema="web_week_intake", order=20)
def intake(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any] | None:
    w = _week(coach, query, now)
    if w is None:
        return None
    if w.stored is not None:
        facts = w.stored["facts"]
        section, p, source = facts["intake"], facts["params"], "check_in"
        result = "pass" if section["adherence_ok"] else "fail"
    else:
        p, source, result = _params(coach, w), "so_far", "not_judged"
        food = weekdata.intake(coach, w.start, _last(w))
        for day in food["days"]:
            if day["date"] == w.today.isoformat() and day["logged"] == "partial":
                day["logged"] = "complete"  # today isn't over: never a partial day (as on Home)
        if not food["days"]:
            return None
        summary = weekdata.intake_summary(food["days"], p)
        section = weekly_facts.intake(food, summary, p)
    days = section["daily"]
    counted = [d for d in days if d["logged"] == "complete"]

    def avg(key: str) -> int | None:
        values = [d[key] for d in counted if d[key] is not None]
        return round(sum(values) / len(values)) if values else None

    targets = section["macro_targets"]
    low, high = p["nutrition"]["fiber_g_per_kg"]
    weight = targets["reference_weight_kg"]
    return {
        "source": source,
        "days": [{"date": d["date"], "eaten_kcal": round(d["actual_kcal"]) if d["actual_kcal"] is not None else None,
                  "target_kcal": round(d["target_kcal"]), "logged": d["logged"]} for d in days],
        "average": {"eaten_kcal": avg("actual_kcal"), "target_kcal": avg("target_kcal"), "days": len(counted)},
        "adherence": {"result": result, "deviation_pct": section["deviation_pct"],
                      "tolerance_pct": p["adherence"]["weekly_intake_tolerance_pct"],
                      "days_logged": len(counted), "days": len(days)},
        "macros": {
            "protein": {"eaten_g": avg("protein_g"), "target_g": targets["protein_g"]},
            "carbs": {"eaten_g": avg("carbs_g"), "target_g": targets["carbs_g"]},
            "fat": {"eaten_g": avg("fat_g"), "target_g": targets["fat_g"]},
            # As on Home: g/kg of the macro reference weight, whole grams.
            "fiber": {"eaten_g": avg("fiber_g"), "target_g": round(low * weight) if weight else None,
                      "target_max_g": round(high * weight) if weight else None},
        },
    }


# --- training ------------------------------------------------------------------------------


@registry.view_part("week", "training", schema="web_week_training", order=30)
def training(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any] | None:
    w = _week(coach, query, now)
    if w is None:
        return None
    last = _last(w)
    if w.stored is not None:
        facts = w.stored["facts"]
        section, sessions, source = facts["training"], facts["activity"]["sessions"], "check_in"
    else:
        phase = web_week.phase_during(coach, w)
        section = progression.week(coach, w.start, last, Date.fromisoformat(phase["start_date"]))
        sessions, source = weekdata.intake(coach, w.start, last)["sessions"], "so_far"
    names = {lift["exercise_id"]: lift["name"] for lift in section["tracked_lifts"]}
    lifts = None
    if section["tracked_lifts"]:
        lifts = {
            "progressing": section["improved_lifts"],
            "counted": section["counted_lifts"],
            "stalls": [{"exercise_id": i, "name": names[i]} for i in section["stalls"]],
            "prs": [{"exercise_id": pr["exercise_id"], "name": pr["name"], "date": pr["date"],
                     "e1rm_kg": pr["top_set"]["e1rm_kg"] if pr["top_set"] else None} for pr in section["prs"]],
            "deload_signal": section["deload_signal"],
        }
    lifting = [s for s in sessions if s["type"] == "lift"]
    steps = [web_home_steps.day_steps(coach, d) for d in weekdata.dates(w.start, last)]
    tracked = [d["steps"] for d in steps if d["tracked"]]
    goal = steps[-1]["goal"]  # the goal on the week's last day so far; each day is judged by its own
    return {
        "source": source,
        "lifts": lifts,
        "sessions": {"done": sum(1 for s in lifting if s["status"] != "skipped"),
                     "planned": _planned(coach, w),
                     "skipped": sum(1 for s in lifting if s["status"] == "skipped")},
        "steps": {"goal": goal, "average": round(sum(tracked) / len(tracked)) if tracked else None,
                  "days_at_goal": sum(1 for d in steps if d["tracked"] and d["steps"] >= d["goal"]),
                  "days": [{"date": d["date"], "tracked": d["tracked"], "steps": d["steps"] if d["tracked"] else None}
                           for d in steps]},
    }


def _planned(coach, w: web_week.Week) -> int:
    """The week's lifting sessions in the plan in force each day, optional ones left out."""
    count = 0
    for day in weekdata.dates(w.start, w.end):
        plan = training_plan.plan_for(coach, day)
        count += sum(1 for s in plan["days"][training_plan.WEEKDAYS[day.weekday()]]
                     if s["type"] == "lift" and not s["optional"]) if plan else 0
    return count


# --- notes and flags -----------------------------------------------------------------------


@registry.view_part("week", "notes", schema="web_week_notes", order=40)
def notes(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any] | None:
    """The week's context notes, the check-in's flags (null before it ran),
    the items held back for its report and the measurements due the week after."""
    w = _week(coach, query, now)
    if w is None:
        return None
    flags = None
    if w.stored is not None:
        flags = [{k: f[k] for k in ("code", "severity", "detail")} for f in w.stored["verdict"]["flags"]]
    return {
        "context_notes": [{k: n[k] for k in ("id", "text", "applies_from", "applies_to", "tags")}
                          for n in context_notes.between(coach, w.start, w.end)],
        "flags": flags,
        "deferred": [{"date": d["day"], "text": d["text"]} for d in messaging.deferred(coach, w.start, w.end)],
        "due_next_week": measurements.measurements_due(coach, w.end + DAY, w.end + 7 * DAY),
    }


def _series(coach, first: Date, last: Date, band: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Each day from `first` (the day before the week, where its rate starts)
    to `last`: the weigh-in (outliers marked), the 7-day trend and the band
    corridor: from the trend on `first`, rising by the band's low and high
    rate a week (none when the week isn't judged against a band)."""
    rows = {r["date"]: r for r in coach.db.all(
        "SELECT date, weight_kg, outlier FROM weigh_ins WHERE date BETWEEN ? AND ?",
        (first.isoformat(), last.isoformat()))}
    anchor = phases.trend_weight(coach, first) if band else None
    out = []
    for d in weekdata.dates(first, last):
        row = rows.get(d.isoformat())
        weeks = (d - first).days / 7
        out.append({
            "date": d.isoformat(),
            "kg": row["weight_kg"] if row else None,
            "outlier": bool(row["outlier"]) if row else False,
            "trend_kg": phases.trend_weight(coach, d),
            "band_low_kg": round(anchor + band["low"] * weeks, 2) if anchor is not None else None,
            "band_high_kg": round(anchor + band["high"] * weeks, 2) if anchor is not None else None,
        })
    return out
