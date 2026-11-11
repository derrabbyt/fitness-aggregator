"""The strength trend: is lifting improving overall? (coach-web tickets 05
and 08, decision of 2026-11-10). Shown on Home's Gym block and at the top of
the Training tab; both call `compute`.

As of a day, over the `training.strength_trend_days` (28) days ending that
day:
- each counting lift (not excluded, not paused) with at least 2 sessions in
  the window, counted from its latest baseline reset if one falls inside;
- a session's value is the estimated 1RM of its heaviest working set, the
  same value the lift status uses (`progression.lifts`; effective load for
  bodyweight lifts); sessions progression ignores (no working set in the rep
  range, another location) are left out;
- per ISO week touching the window, each lift's best value as % change from
  its first session in the window;
- the week's point is the mean over the lifts trained by then, each carrying
  its last value forward (null before any lift was trained).
`change_pct` is the last point; `direction` is flat within
±`training.e1rm_same_band_pct` %, else rising or falling.
"""

import datetime
from typing import TYPE_CHECKING, Any

from . import phases, progression, weekly_facts

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
IGNORED = ("no_working_sets", "other_location")


def compute(coach: "Coach", day: Date, lifts: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """{days, band_pct, change_pct, direction, lifts, points: [{week, start,
    change_pct}]}. `lifts` is `progression.lifts(coach, day)` when the caller
    already has it."""
    p = phases.params(coach)["training"]
    days, band = p["strength_trend_days"], p["e1rm_same_band_pct"]
    start = day - (days - 1) * DAY
    if lifts is None:
        lifts = progression.lifts(coach, day)
    weeks = _weeks(start, day)
    per_lift = [s for s in (_lift_series(lift, start, day, weeks) for lift in lifts.values()) if s is not None]
    points = []
    for k, (week, monday) in enumerate(weeks):
        values = [s[k] for s in per_lift if s[k] is not None]
        mean = round(sum(values) / len(values), 1) if values else None
        points.append({"week": week, "start": monday.isoformat(), "change_pct": mean})
    change = points[-1]["change_pct"] if per_lift else None
    direction = None if change is None else "rising" if change > band else "falling" if change < -band else "flat"
    return {"days": days, "band_pct": band, "change_pct": change, "direction": direction,
            "lifts": len(per_lift), "points": points}


def _weeks(start: Date, end: Date) -> list[tuple[str, Date]]:
    monday = start - start.weekday() * DAY
    out = []
    while monday <= end:
        out.append((weekly_facts.iso_week(monday), monday))
        monday += 7 * DAY
    return out


def _lift_series(lift: dict[str, Any], start: Date, end: Date,
                 weeks: list[tuple[str, Date]]) -> list[float | None] | None:
    """The lift's % change per week (carried forward), None when it doesn't count."""
    if not lift["counts"] or lift["paused"]:
        return None
    entries = [e for e in lift["entries"]
               if start.isoformat() <= e["date"] <= end.isoformat() and e["top"] is not None
               and e["not_judged_reason"] not in IGNORED]
    resets = [k for k, e in enumerate(entries) if e["not_judged_reason"] == "baseline_reset"]
    if resets:
        entries = entries[resets[-1]:]
    if len(entries) < 2:
        return None
    base = entries[0]["top"]["e1rm_kg"]
    if not base:
        return None
    series: list[float | None] = []
    last = None
    for _, monday in weeks:
        sunday = (monday + 6 * DAY).isoformat()
        in_week = [e["top"]["e1rm_kg"] for e in entries if monday.isoformat() <= e["date"] <= sunday]
        if in_week:
            last = (max(in_week) / base - 1) * 100
        series.append(last)
    return series
