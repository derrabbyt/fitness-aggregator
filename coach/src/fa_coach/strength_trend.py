"""The strength trend (coach-web tickets 05 and 08): whether lifting is
improving overall over the last `training.strength_trend_days` (28) days,
as of a day. Shown small on Home's Gym block and larger on the Training tab;
both call `compute`. Schema: coach-skills/schemas/web_strength_trend.schema.json.

- Each counting lift (excluded ones never count), each session: the heaviest
  working set as estimated 1RM, the value the lift status uses
  (progression.py; effective load for bodyweight lifts). Ignored sessions
  (no working set, other location) are left out.
- The window starts after the lift's latest baseline reset inside it, if
  any; a lift needs at least 2 sessions in it.
- Per ISO week the window touches: the lift's best value that week as %
  change from its first session in the window. A week without a session
  carries the lift's last value forward; before its first session the lift
  isn't in the mean yet.
- A week's value is the mean over the lifts trained up to that week; the
  change is the last week's value. Within ±`training.e1rm_same_band_pct` it
  is flat, above rising, below falling.
"""

import datetime
from typing import TYPE_CHECKING, Any

from . import phases, progression

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
IGNORED = ("no_working_sets", "other_location")


def compute(coach: "Coach", day: Date) -> dict[str, Any]:
    p = phases.params(coach)["training"]
    days, band = p["strength_trend_days"], p["e1rm_same_band_pct"]
    start = day - (days - 1) * DAY
    weeks = _iso_weeks(start, day)
    series: list[list[float | None]] = []
    for lift in progression.lifts(coach, day).values():
        if lift["counts"]:
            values = _lift_series(lift["entries"], start, day, weeks)
            if values is not None:
                series.append(values)
    points = []
    for n in range(len(weeks)):
        trained = [s[n] for s in series if s[n] is not None]
        points.append(round(sum(trained) / len(trained), 1) if trained else None)
    change = points[-1] if series else None
    direction = None if change is None else "rising" if change > band else "falling" if change < -band else "flat"
    return {
        "days": days,
        "start": start.isoformat(),
        "end": day.isoformat(),
        "weeks": [{"iso_week": w, "change_pct": v} for w, v in zip(weeks, points)],
        "change_pct": change,
        "direction": direction,
        "lifts": len(series),
    }


def _lift_series(entries: list[dict[str, Any]], start: Date, end: Date, weeks: list[str]) -> list[float | None] | None:
    """The lift's % change per week (carried forward), None if it doesn't qualify."""
    window = [e for e in entries if e["top"] is not None and e["not_judged_reason"] not in IGNORED
              and start.isoformat() <= e["date"] <= end.isoformat()]
    resets = [n for n, e in enumerate(window) if e["not_judged_reason"] == "baseline_reset"]
    if resets:
        window = window[resets[-1]:]
    if len(window) < 2 or not window[0]["top"]["e1rm_kg"]:
        return None
    base = window[0]["top"]["e1rm_kg"]
    best: dict[str, float] = {}
    for e in window:
        week = _iso_week(Date.fromisoformat(e["date"]))
        best[week] = max(best.get(week, 0.0), e["top"]["e1rm_kg"])
    out: list[float | None] = []
    last = None
    for week in weeks:
        if week in best:
            last = (best[week] / base - 1) * 100
        out.append(last)
    return out


def _iso_weeks(start: Date, end: Date) -> list[str]:
    monday = start - start.weekday() * DAY
    out = []
    while monday <= end:
        out.append(_iso_week(monday))
        monday += 7 * DAY
    return out


def _iso_week(day: Date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"
