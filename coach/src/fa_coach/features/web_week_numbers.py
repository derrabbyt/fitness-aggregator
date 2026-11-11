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
from typing import Any

from .. import history, phases, weekdata, weekly_facts
from ..registry import registry
from . import web_week, web_weight

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
        band = bands.on(w.end)
        rate = web_weight.weekly_rate(coach, last)
        out = {
            "source": "so_far",
            "trend_kg": phases.trend_weight(coach, last),
            "prev_trend_kg": phases.trend_weight(coach, w.start - DAY),
            "weekly_rate_kg": rate,
            "rate_window": "last_7_days",
            "band": {"low": band["low"], "high": band["high"]} if band else None,
            "vs_band": bands.vs_band(last, rate),
            "weigh_ins": len(history.weigh_ins(coach.db, w.start.isoformat(), last.isoformat())),
            "weigh_ins_needed": phases.params(coach)["data"]["min_weighins_per_week"],
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
        p, source, result = phases.params(coach), "so_far", "not_judged"
        food = weekdata.intake(coach, w.start, _last(w))
        for day in food["days"]:
            if day["date"] == w.today.isoformat() and day["logged"] == "partial":
                day["logged"] = "complete"  # today isn't over: never a partial day (as on Home)
        if not food["days"]:
            return None
        summary = weekdata.intake_summary(food["days"], p)
        section = weekly_facts._intake(food, summary, p)
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
