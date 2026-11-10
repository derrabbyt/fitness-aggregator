"""Weekly facts (weekly_facts.schema.json): every number the weekly decision
and report see, computed in code for one 7-day week of the active phase.

- `compute(coach, end, now)`: the facts for the week ending `end`.
- `facts_hooks`: later tickets fill their sections here, e.g. lift progression
  (`training`), proposals (`history.open_proposals`, `last_rejected`) or
  measurements: `fn(coach, facts, now)` changes `facts` in place.
- `skip_reason(facts, verdict)`: why a week is skipped for confirmation, or None.
- `previous_verdicts(coach, before, phase_row_id)` and
  `confirmation_streaks(...)`: the stored verdict history as the decision
  and the guardrails count it.
"""

import datetime
import json
import statistics
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from . import history, phases, weekdata
from .features import context_notes, measurements

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
PREVIOUS_VERDICTS = 6
SPORT_LOAD_TAG = "sport_load"

FactsHook = Callable[["Coach", dict[str, Any], datetime.datetime], None]
facts_hooks: list[FactsHook] = []


def compute(coach: "Coach", end: Date, now: datetime.datetime) -> dict[str, Any]:
    """Facts for the 7 days ending `end` (all inside the active phase)."""
    phase = phases.active(coach)
    if phase is None:
        raise ValueError("no active phase")
    start = end - 6 * DAY
    p = phases.params(coach)
    week = _week(coach, phase, start, end, p)
    food = weekdata.intake(coach, start, end)
    summary = weekdata.intake_summary(food["days"], p)
    weigh_ins = history.weigh_ins(coach.db, start.isoformat(), end.isoformat())
    fresh = history.freshness(coach.db, now, p["data"]["sync_max_age_hours"])
    reasons = []
    if len(weigh_ins) < p["data"]["min_weighins_per_week"]:
        reasons.append("too_few_weigh_ins")
    if not summary["complete"] and p["adherence"]["require_all_eating_logged"]:
        reasons.append("incomplete_food_log")
    if not fresh["fresh"]:
        reasons.append("stale_sync")
    notes = context_notes.between(coach, start, end)
    current = phases.targets(coach, end)
    facts = {
        "schema_version": 1,
        "week": week,
        "data_quality": {
            "weigh_in_count": len(weigh_ins),
            "food_days_logged": summary["days_logged"],
            "food_log_complete": summary["complete"],
            "sync_fresh": fresh["fresh"],
            "last_sync_at": fresh["last_sync_at"],
            "code_usable": not reasons,
            "code_unusable_reasons": reasons,
        },
        "weight": _weight(coach, phase, start, end, week, not reasons, p),
        "intake": _intake(food, summary, p),
        "activity": {
            **weekdata.steps(coach, start, end, p),
            "sessions": food["sessions"],
            **_sport_load(notes),
        },
        "training": _training(food["sessions"]),
        "targets": {
            "surplus_kcal": round(current["surplus_kcal"]),
            "base_maintenance_kcal": round(current["base_maintenance_kcal"]),
            "avg_daily_target_kcal": round(current["avg_daily_target_kcal"]),
            "maintenance_estimate": _maintenance(coach, end, p),
            "mfp_goal_kcal": current["mfp_goal_kcal"],
        },
        "history": _history(coach, phase, start),
        "context_notes": notes,
        "measurements": _measurements(coach, phase, end, p),
        "params": p,
    }
    for hook in facts_hooks:
        hook(coach, facts, now)
    return facts


def iso_week(day: Date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _week(coach, phase, start: Date, end: Date, p) -> dict[str, Any]:
    number = phases.phase_week(phase, end)
    return {
        "iso_week": iso_week(end),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "phase_id": phase["phase_id"],
        "phase_week": number,
        # Any day of the week inside the window keeps the week "not judged".
        "in_glycogen_window": phases.phase_week(phase, start) <= p.get("glycogen_window_weeks", 0),
        "phase_first_change_pending": not phase["first_change_applied"],
    }


def _band(p: dict[str, Any], week: int) -> dict[str, Any]:
    rows = [b for b in p["weight_band_kg_per_week"]
            if b["from_week"] <= week and (b["to_week"] is None or week <= b["to_week"])]
    band = rows[0] if rows else p["weight_band_kg_per_week"][-1]
    return {"low": band["low"], "high": band["high"], "lower_limit": p.get("weight_lower_limit_kg_per_week"),
            "upper_limit": p.get("weight_upper_limit_kg_per_week")}


def _vs_band(rate: float, band: dict[str, Any]) -> str:
    if band["upper_limit"] is not None and rate > band["upper_limit"]:
        return "above_limit"
    if band["lower_limit"] is not None and rate < band["lower_limit"]:
        return "below_limit"
    if rate > band["high"]:
        return "above_band"
    if rate < band["low"]:
        return "below_band"
    return "in_band"


def _weight(coach, phase, start: Date, end: Date, week: dict, usable: bool, p) -> dict[str, Any]:
    avg = phases.trend_weight(coach, end)
    prev = phases.trend_weight(coach, start - DAY)
    rate = round(avg - prev, 2) if avg is not None and prev is not None else None
    band = _band(p, week["phase_week"])
    evaluated = usable and not week["in_glycogen_window"] and rate is not None
    # The prediction made at the start of the week: last week's average plus
    # the planned daily surplus over 7 days.
    at_start = phases.targets(coach, start)
    predicted = None
    if prev is not None and at_start is not None:
        predicted = round(prev + at_start["surplus_kcal"] * 7 / p["maintenance_estimate"]["kcal_per_kg"], 2)
    error = round(avg - predicted, 2) if avg is not None and predicted is not None else None
    daily = history.weigh_ins(coach.db, start.isoformat(), end.isoformat(), include_outliers=True)
    return {
        "avg_7d_kg": avg,
        "prev_avg_7d_kg": prev,
        "weekly_rate_kg": rate,
        "band": band,
        "vs_band": _vs_band(rate, band) if evaluated else "not_evaluated",
        "predicted_avg_7d_kg": predicted,
        "prediction_error_kg": error,
        "prediction_miss": error is not None and abs(error) > p["decisions"]["prediction_miss_kg"],
        "daily": [{"date": d.isoformat(), "kg": daily.get(d.isoformat())} for d in weekdata.dates(start, end)],
        "outlier_days": history.outlier_days(coach.db, start.isoformat(), end.isoformat()),
    }


def _intake(food: dict[str, Any], summary: dict[str, Any], p) -> dict[str, Any]:
    macros = food["macros"]
    reference = macros[-1]["reference_weight_kg"] if macros else 0
    fiber = p["nutrition"]["fiber_g_per_kg"]
    return {
        "weekly_target_kcal": summary["target_kcal"],
        "weekly_actual_kcal": summary["actual_kcal"],
        "deviation_pct": summary["deviation_pct"],
        "adherence_ok": summary["adherence_ok"],
        "macro_targets": {
            "protein_g": round(statistics.fmean(m["protein_g"] for m in macros)) if macros else 0,
            "fat_g": round(statistics.fmean(m["fat_g"] for m in macros)) if macros else 0,
            "carbs_g": round(statistics.fmean(m["carbs_g"] for m in macros)) if macros else 0,
            "reference_weight_kg": reference,
        },
        "fiber_target_g": [round(fiber[0] * reference, 1), round(fiber[1] * reference, 1)],
        "produce_min_g": p["nutrition"]["produce_min_g_per_day"],
        "daily": food["days"],
    }


def _sport_load(notes: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [n["id"] for n in notes if SPORT_LOAD_TAG in n["tags"]]
    return {"sport_load_high": bool(ids), "sport_load_note_ids": ids}


def _training(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Missed sessions; lift progression is added by features/lifts.py (a facts hook)."""
    return {"missed_sessions": [{"planned_date": s["date"], "type": s["type"]}
                                for s in sessions if s["status"] == "skipped"]}


def _measurements(coach, phase, end: Date, p) -> dict[str, Any]:
    waist = [w["cm"] for w in measurements.waist_values(coach) if w["date"] <= end.isoformat()]
    return {
        "photos_enabled": bool(p["measurements"]["photos_enabled"]),
        "waist_cm_latest": waist[-1] if waist else None,
        "waist_cm_prev": waist[-2] if len(waist) > 1 else None,
        "waist_cm_phase_start": phase["setup"].get("waist_cm_start"),
        "latest_bf_estimate": None,
    }


def _maintenance(coach, end: Date, p) -> dict[str, Any]:
    """The back-calculated estimate as base maintenance (its window's average
    counted activity taken off); the weeks after the estimate's window up to
    `end` were left out (glycogen window or unusable)."""
    from .features import training_plan

    estimate = phases.maintenance_estimate(coach, end, p)
    if estimate["value"] is None:
        return {"base_kcal": None, "window_weeks": 0, "updated_on": None, "excluded_weeks": []}
    first, last = Date.fromisoformat(estimate["start"]), Date.fromisoformat(estimate["end"])
    activity = statistics.fmean(training_plan.counted_activity_on(coach, d, p["activity"])["kcal"]
                                for d in weekdata.dates(first, last))
    excluded = []
    week_end = end
    while week_end > last:
        excluded.append(iso_week(week_end))
        week_end -= 7 * DAY
    return {"base_kcal": round(estimate["value"] - activity), "window_weeks": estimate["weeks"],
            "updated_on": estimate["end"], "excluded_weeks": sorted(excluded)}


# --- verdict history ---------------------------------------------------------------


def skip_reason(facts: dict[str, Any], verdict: dict[str, Any]) -> str | None:
    """Why the week is skipped for confirmation (it neither counts nor breaks
    a streak), or None when it counts."""
    if not verdict["usable"] or not facts["data_quality"]["code_usable"]:
        return "unusable"
    if facts["week"]["in_glycogen_window"]:
        return "glycogen_window"
    if verdict["adherence_gate"] == "fail" or not facts["intake"]["adherence_ok"]:
        return "adherence_gate"
    if facts["activity"]["sport_load_high"]:
        return "sport_load"
    return None


def previous_verdicts(coach: "Coach", before: Date, phase_row_id: str) -> list[dict[str, Any]]:
    """Stored verdicts of the phase for weeks ending before `before`, newest
    first (the latest successful check-in per week)."""
    rows = coach.db.all(
        "SELECT * FROM weekly_checkins WHERE status = 'ok' AND phase_row_id = ? AND end_date < ?"
        " ORDER BY end_date DESC, id DESC",
        (phase_row_id, before.isoformat()),
    )
    out, seen = [], set()
    for r in rows:
        if r["iso_week"] in seen:
            continue
        seen.add(r["iso_week"])
        verdict = json.loads(r["verdict"])
        out.append({
            "iso_week": r["iso_week"],
            "start_date": r["start_date"],
            "usable": verdict["usable"],
            "scenario": verdict["scenario"],
            "direction": r["direction"],
            "counts_for_confirmation": bool(r["counts_for_confirmation"]),
            "skip_reason": r["skip_reason"],
        })
    return out


def confirmation_streaks(verdicts: list[dict[str, Any]], since: str | None) -> dict[str, int]:
    """Consecutive earlier weeks (newest first in `verdicts`) pointing to an
    increase or a decrease, skipped weeks left out, counting only weeks that
    start on or after `since` (the last change)."""
    streak = {"increase": 0, "decrease": 0}
    direction = None
    for v in verdicts:
        if since is not None and v["start_date"] < since:
            break
        if not v["counts_for_confirmation"]:
            continue
        if direction is None:
            direction = v["direction"]
        if v["direction"] != direction or direction not in streak:
            break
        streak[direction] += 1
    return streak


def _history(coach, phase, start: Date) -> dict[str, Any]:
    changes = [t for t in phases.target_history(coach) if t["valid_from"] <= start.isoformat()] or \
        phases.target_history(coach)[:1]
    last = changes[-1] if changes else None
    last_change = None
    if last is not None:
        # The surplus moves only with calorie changes (calibration rows can move the average).
        before = changes[-2]["surplus_kcal"] if len(changes) > 1 else None
        delta = (last["surplus_kcal"] - before if before is not None
                 else phase["setup"].get("week1_increase_kcal") or 0)
        last_change = {"proposal_id": last["ref"], "source": last["source"], "applied_on": last["valid_from"],
                       "delta_kcal": round(delta)}
    verdicts = previous_verdicts(coach, start, phase["id"])
    since = last["valid_from"] if last else None
    counted_since = [v for v in verdicts if v["counts_for_confirmation"] and (since is None or v["start_date"] >= since)]
    return {
        "weeks_since_last_change": len(counted_since) + 1 if last else None,
        "last_change": last_change,
        "previous_verdicts": [{k: v[k] for k in ("iso_week", "usable", "scenario", "direction",
                                                 "counts_for_confirmation", "skip_reason")}
                              for v in verdicts[:PREVIOUS_VERDICTS]],
        "confirmation_streaks": confirmation_streaks(verdicts, since),
        "open_proposals": [],
        "last_rejected": None,
    }
