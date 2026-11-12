"""The strength trend (coach-web tickets 05, 08 and 14): whether lifting is
improving overall, as of a day. Shown as a 14-day line on Home's Workouts
card and (ticket 08, paused) larger on the Training tab; both call `compute`.
Schema: coach-skills/schemas/web_strength_trend.schema.json.

- A lift's value per session is the heaviest working set as estimated 1RM,
  the value the lift status uses (progression.py; effective load for
  bodyweight lifts). Ignored sessions (no working set, other location) are
  left out; excluded lifts never count. Whether a lift counts is its
  classification on each point's day (coach-followups ticket 04), so a lift
  excluded later still counts on earlier points.
- Each day D of the series looks back over the `training.strength_trend_days`
  (28) days ending on D. Every counting lift trained in that window gives
  its latest value as % of its first value in the window (its latest
  baseline reset inside the window starts it instead). A lift needs at least
  2 sessions there (since its last reset) to count, so a new lift doesn't pull
  the line toward 100 %. D's point is the mean over those lifts (null without any), so
  the line steps when sessions happen and when old sessions leave the window.
- The rate measures each counting lift as of the last day over its real span:
  its change (latest as % of first, as above) divided by the weeks from its
  first session in the window (or its reset) to its latest one, at least
  `MIN_SPAN_DAYS` (7), so a lift trained only lately or reset a week ago isn't
  spread over the whole window. The rate is the mean of those % per week:
  within ±`training.e1rm_same_band_pct` it is flat, above rising, below
  falling. The chart points stay % vs the window start.
- `lifts` counts the lifts in the rate; `lifts_trained` the counting lifts
  with any session in the window ending on the day (so the page can tell
  "nothing trained" from "not enough sessions yet").
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
MIN_SPAN_DAYS = 7


def compute(coach: "Coach", day: Date, *, days: int = SERIES_DAYS,
            lifts: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The `days`-day series ending on `day` and the rate as of `day`.
    `lifts`: `progression.lifts(coach, day)` when the caller has it."""
    p = phases.params(coach)["training"]
    window, band = p["strength_trend_days"], p["e1rm_same_band_pct"]
    histories = [(lift, _values(lift["entries"])) for lift in (lifts or progression.lifts(coach, day)).values()]
    points, rates = [], []
    for n in range(days - 1, -1, -1):
        d = day - n * DAY
        changes = [c for c in (_change(h, d - (window - 1) * DAY, d) for lift, h in histories
                               if progression.counts_on(lift, d)) if c is not None]
        pcts = [pct for pct, _ in changes]
        points.append({"date": d.isoformat(), "pct": round(sum(pcts) / len(pcts), 1) if pcts else None})
        rates = [(pct - 100) / (max(span, MIN_SPAN_DAYS) / 7) for pct, span in changes]
    trained = len(rates)
    rate = round(sum(rates) / trained, 1) if rates else None
    first, last = (day - (window - 1) * DAY).isoformat(), day.isoformat()
    in_window = sum(1 for lift, h in histories
                    if progression.counts_on(lift, day) and any(first <= v[0] <= last for v in h))
    direction = None if rate is None else "rising" if rate > band else "falling" if rate < -band else "flat"
    return {"window_days": window, "start": points[0]["date"], "end": day.isoformat(), "points": points,
            "rate_pct_per_week": rate, "direction": direction, "lifts": trained,
            "lifts_trained": in_window}


def _values(entries: list[dict[str, Any]]) -> list[tuple[str, float, bool]]:
    """(date, e1RM, starts a baseline) per usable session, oldest first."""
    return [(e["date"], e["top"]["e1rm_kg"], e["not_judged_reason"] == "baseline_reset") for e in entries
            if e["top"] is not None and e["top"]["e1rm_kg"] and e["not_judged_reason"] not in IGNORED]


def _change(history: list[tuple[str, float, bool]], start: Date, end: Date) -> tuple[float, int] | None:
    """The lift's latest value in start..end as % of its first one there (after a reset), and the days
    between those two sessions; None with fewer than 2 sessions."""
    window = [v for v in history if start.isoformat() <= v[0] <= end.isoformat()]
    resets = [n for n, v in enumerate(window) if v[2]]
    if resets:
        window = window[resets[-1]:]
    if len(window) < 2:  # a lift needs two sessions in the window to show a change
        return None
    span = (Date.fromisoformat(window[-1][0]) - Date.fromisoformat(window[0][0])).days
    return window[-1][1] / window[0][1] * 100, span
