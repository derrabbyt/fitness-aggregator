"""The web page's weight (coach-web ticket 03): Home's `weight` part and the
weight detail `home/weight`, as they stood on the day shown.

The 7-day trend is `phases.trend_weight` (outliers left out), the weekly
rate the trend minus the trend 7 days earlier, judged against the band of
the day's phase (active or ended) for its phase week the way the weekly
check-in judges it (`weekly_facts`).
"""

import datetime
from typing import Any

from .. import phases, views, weekdata, weekly_facts
from ..registry import registry
from . import measurements, web_home

Date = datetime.date
DAY = datetime.timedelta(days=1)
HOME_DAYS = 14
DETAIL_WEEKS = ("1", "2", "4", "12", "26", "all")  # the detail's range dropdown
WAIST = 12  # waist values listed in the detail


@registry.view_part("home", "weight", schema="web_home_weight", order=20)
def home_weight(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    rate = weekly_facts.weekly_rate(coach, day)
    return {
        "weigh_in": latest_weigh_in(coach, day),
        "weekly_rate_kg": rate,
        "vs_band": Bands(coach).vs_band(day, rate),
        "series": [{"date": d.isoformat(), "trend_kg": phases.trend_weight(coach, d)}
                   for d in weekdata.dates(day - (HOME_DAYS - 1) * DAY, day)],
    }


@registry.view("home/weight", schema="web_home_weight_detail")
def weight_detail(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    """The weight detail: `?weeks=` 1, 2, 4 (default), 12 or 26 weeks, or `all`
    (from the first weigh-in) of weigh-ins, trend and band ending the day, and
    every weigh-in up to the day (the page shows the latest and expands)."""
    day = views.day(query, now)
    raw = query.get("weeks") or "4"
    if raw not in DETAIL_WEEKS:
        raise views.WebError(400, "Weeks must be one of " + ", ".join(DETAIL_WEEKS) + ".")
    if raw == "all":
        first = coach.db.one("SELECT MIN(date) AS d FROM weigh_ins WHERE date <= ?", (day.isoformat(),))["d"]
        start = min(Date.fromisoformat(first), day - 6 * DAY) if first else day - 6 * DAY
        weeks: int | str = "all"
    else:
        weeks = int(raw)
        start = day - (weeks * 7 - 1) * DAY
    rate = weekly_facts.weekly_rate(coach, day)
    bands = Bands(coach)
    return {
        "date": day.isoformat(),
        "weeks": weeks,
        "weigh_in": latest_weigh_in(coach, day),
        "trend_kg": phases.trend_weight(coach, day),
        "weekly_rate_kg": rate,
        "vs_band": bands.vs_band(day, rate),
        "band": bands.on(day),
        "series": _series(coach, start, day),
        "recent": [{"date": r["date"], "kg": r["weight_kg"], "outlier": bool(r["outlier"])} for r in coach.db.all(
            "SELECT date, weight_kg, outlier FROM weigh_ins WHERE date <= ? ORDER BY date DESC",
            (day.isoformat(),))],
        "waist": _waist(coach, day),
        "prediction": _prediction(coach, day),
    }


def _waist(coach, day: Date) -> list[dict[str, Any]]:
    """Waist values up to `day`, newest first, with each phase's start value
    (a setup value, active or ended phase) on its start date: the chat's
    `waist_history` without its source."""
    return [{"date": w["date"], "cm": w["cm"]} for w in measurements.waist_history(coach, day)[:WAIST]]


def _prediction(coach, day: Date) -> dict[str, Any] | None:
    """The check-in week holding `day`: the trend predicted for its end (last
    week's trend plus the planned surplus over 7 days, as the weekly check-in
    predicts it) against the trend on `day`."""
    start = web_home.check_in_week_start(coach, day)
    end = start + 6 * DAY
    prev, at_start = phases.trend_weight(coach, start - DAY), phases.targets(coach, start)
    if prev is None or at_start is None:
        return None
    kcal_per_kg = phases.params_on(coach, start)["maintenance_estimate"]["kcal_per_kg"]
    predicted = round(prev + at_start["surplus_kcal"] * 7 / kcal_per_kg, 2)
    actual = phases.trend_weight(coach, day)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "predicted_kg": predicted,
        "actual_kg": actual,
        "difference_kg": round(actual - predicted, 2) if actual is not None else None,
        "complete": day >= end,
    }


def _series(coach, start: Date, end: Date) -> list[dict[str, Any]]:
    """Each day: the weigh-in (outliers marked), the 7-day trend and the band
    corridor: from the trend on the first judged day in the range (inside a
    phase, past the glycogen window), rising by the band's low and
    high rate a week for each day's phase week."""
    rows = {r["date"]: r for r in coach.db.all(
        "SELECT date, weight_kg, outlier FROM weigh_ins WHERE date BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()))}
    bands = Bands(coach)
    out = []
    corridor: tuple[float, float] | None = None
    for d in weekdata.dates(start, end):
        row = rows.get(d.isoformat())
        trend = phases.trend_weight(coach, d)
        if corridor is not None:
            band = bands.on(d)
            corridor = (corridor[0] + band["low"] / 7, corridor[1] + band["high"] / 7) if band else None
        elif trend is not None and bands.judged(d):
            corridor = (trend, trend)
        out.append({
            "date": d.isoformat(),
            "kg": row["weight_kg"] if row else None,
            "outlier": bool(row["outlier"]) if row else False,
            "trend_kg": trend,
            "band_low_kg": round(corridor[0], 2) if corridor else None,
            "band_high_kg": round(corridor[1], 2) if corridor else None,
        })
    return out


def latest_weigh_in(coach, day: Date) -> dict[str, Any] | None:
    """The most recent weigh-in on or before `day` (outliers too, marked)."""
    row = coach.db.one("SELECT date, weight_kg, outlier FROM weigh_ins WHERE date <= ? ORDER BY date DESC LIMIT 1",
                       (day.isoformat(),))
    return {"date": row["date"], "kg": row["weight_kg"], "outlier": bool(row["outlier"])} if row else None


class Bands:
    """The weight band by day: the band of the phase of that day (active or
    ended, `phases.on`) with its params as of that day (`phases.params_on`)."""

    def __init__(self, coach):
        self.coach = coach

    def _phase(self, day: Date) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        return phases.on(self.coach, day), phases.params_on(self.coach, day)

    def on(self, day: Date) -> dict[str, Any] | None:
        """The band for `day`'s phase week; None outside a phase or without
        a band (e.g. a cut before its band is decided)."""
        phase, p = self._phase(day)
        if phase is None or not p.get("weight_band_kg_per_week"):
            return None
        week = phases.phase_week(phase, day)
        return weekly_facts.weight_band(p, week) if week >= 1 else None

    def judged(self, day: Date) -> bool:
        """`day` has a band and is past the glycogen window."""
        phase, p = self._phase(day)
        return self.on(day) is not None and phases.phase_week(phase, day) > p.get("glycogen_window_weeks", 0)

    def vs_band(self, day: Date, rate: float | None) -> str | None:
        """The rate of the 7 days ending `day` against the band, as the weekly
        check-in judges a week: "not_evaluated" while any of those days is in
        the glycogen window; None without a rate or a band."""
        band = self.on(day)
        if rate is None or band is None:
            return None
        phase, p = self._phase(day)
        if weekly_facts.in_glycogen_window(phase, day, p):
            return "not_evaluated"
        return weekly_facts.vs_band(rate, band)

