"""The strength trend (coach-web tickets 05, 08 and 14): whether lifting is
improving overall, as of a day. Shown as a 14-day line on Home's Workouts
card and (ticket 08, paused) larger on the Training tab; both call `compute`.
Schema: coach-skills/schemas/web_strength_trend.schema.json.

- A lift's value per session is the heaviest working set as estimated 1RM,
  the value the lift status uses (progression.py; effective load for
  bodyweight lifts). Ignored sessions (no working set, other location) are
  left out; excluded lifts never count.
- Each day D of the series looks back over the `training.strength_trend_days`
  (28) days ending on D. Every counting lift trained in that window gives
  its latest value as % of its first value in the window (its latest
  baseline reset inside the window starts it instead). A lift trained once
  is at 100 %. D's point is the mean over those lifts (null without any), so
  the line steps when sessions happen and when old sessions leave the window.
- The rate is the last point's change over the window in % per week
  ((point - 100) / (window days / 7)): within ±`training.e1rm_same_band_pct`
  it is flat, above rising, below falling.
"""

import datetime
from typing import TYPE_CHECKING, Any

from . import phases, progression

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
IGNORED = ("no_working_sets", "other_location")
SERIES_DAYS = 14


def compute(coach: "Coach", day: Date, *, days: int = SERIES_DAYS,
            lifts: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The `days`-day series ending on `day` and the rate as of `day`.
    `lifts`: `progression.lifts(coach, day)` when the caller has it."""
    p = phases.params(coach)["training"]
    window, band = p["strength_trend_days"], p["e1rm_same_band_pct"]
    histories = [_values(lift["entries"]) for lift in (lifts or progression.lifts(coach, day)).values()
                 if lift["counts"]]
    points, trained = [], 0
    for n in range(days - 1, -1, -1):
        d = day - n * DAY
        pcts = [pct for pct in (_pct(h, d - (window - 1) * DAY, d) for h in histories) if pct is not None]
        points.append({"date": d.isoformat(), "pct": round(sum(pcts) / len(pcts), 1) if pcts else None})
        trained = len(pcts)
    last = points[-1]["pct"]
    rate = None if last is None else round((last - 100) / (window / 7), 1)
    direction = None if rate is None else "rising" if rate > band else "falling" if rate < -band else "flat"
    return {"window_days": window, "start": points[0]["date"], "end": day.isoformat(), "points": points,
            "rate_pct_per_week": rate, "direction": direction, "lifts": trained}


def _values(entries: list[dict[str, Any]]) -> list[tuple[str, float, bool]]:
    """(date, e1RM, starts a baseline) per usable session, oldest first."""
    return [(e["date"], e["top"]["e1rm_kg"], e["not_judged_reason"] == "baseline_reset") for e in entries
            if e["top"] is not None and e["top"]["e1rm_kg"] and e["not_judged_reason"] not in IGNORED]


def _pct(history: list[tuple[str, float, bool]], start: Date, end: Date) -> float | None:
    """The lift's latest value in start..end as % of its first one there (after a reset), None if untrained."""
    window = [v for v in history if start.isoformat() <= v[0] <= end.isoformat()]
    resets = [n for n, v in enumerate(window) if v[2]]
    if resets:
        window = window[resets[-1]:]
    if not window:
        return None
    return window[-1][1] / window[0][1] * 100
