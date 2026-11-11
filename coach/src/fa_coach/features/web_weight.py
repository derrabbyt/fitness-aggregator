"""The web page's weight (coach-web ticket 03): Home's `weight` part and the
weight detail `home/weight`, as they stood on the day shown.

The 7-day trend is `phases.trend_weight` (outliers left out), the weekly
rate the trend minus the trend 7 days earlier, judged against the active
phase's band for the day's phase week the way the weekly check-in judges it
(`weekly_facts`).
"""

import datetime
from typing import Any

from .. import phases, views, weekdata, weekly_facts
from ..registry import registry
from . import measurements, web_home

Date = datetime.date
DAY = datetime.timedelta(days=1)
HOME_DAYS = 14
DETAIL_WEEKS = ("4", "12")
RECENT = 14  # weigh-ins listed in the detail
WAIST = 12  # waist values listed in the detail


@registry.view_part("home", "weight", schema="web_home_weight", order=20)
def home_weight(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    rate = weekly_rate(coach, day)
    return {
        "weigh_in": latest_weigh_in(coach, day),
        "weekly_rate_kg": rate,
        "vs_band": Bands(coach).vs_band(day, rate),
        "series": [{"date": d.isoformat(), "trend_kg": phases.trend_weight(coach, d)}
                   for d in weekdata.dates(day - (HOME_DAYS - 1) * DAY, day)],
    }


@registry.view("home/weight", schema="web_home_weight_detail")
def weight_detail(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    """The weight detail: `?weeks=4` (default) or 12 of weigh-ins, trend and
    band ending the day."""
    day = views.day(query, now)
    raw = query.get("weeks") or "4"
    if raw not in DETAIL_WEEKS:
        raise views.WebError(400, "Weeks must be 4 or 12.")
    weeks = int(raw)
    rate = weekly_rate(coach, day)
    bands = Bands(coach)
    return {
        "date": day.isoformat(),
        "weeks": weeks,
        "weigh_in": latest_weigh_in(coach, day),
        "trend_kg": phases.trend_weight(coach, day),
        "weekly_rate_kg": rate,
        "vs_band": bands.vs_band(day, rate),
        "band": bands.on(day),
        "series": _series(coach, day - (weeks * 7 - 1) * DAY, day),
        "recent": [{"date": r["date"], "kg": r["weight_kg"], "outlier": bool(r["outlier"])} for r in coach.db.all(
            "SELECT date, weight_kg, outlier FROM weigh_ins WHERE date <= ? ORDER BY date DESC LIMIT ?",
            (day.isoformat(), RECENT))],
        "waist": _waist(coach, day),
        "prediction": _prediction(coach, day),
    }


def _waist(coach, day: Date) -> list[dict[str, Any]]:
    """Waist values up to `day`, newest first, with the active phase's start
    value (a setup value) on its start date."""
    values = [w for w in measurements.waist_values(coach) if w["date"] <= day.isoformat()]
    phase = phases.active(coach)
    start = phase["setup"].get("waist_cm_start") if phase else None
    if start is not None and phase["start_date"] <= day.isoformat() \
            and all(w["date"] != phase["start_date"] for w in values):
        values.append({"date": phase["start_date"], "cm": start})
    return sorted(values, key=lambda w: w["date"], reverse=True)[:WAIST]


def _prediction(coach, day: Date) -> dict[str, Any] | None:
    """The check-in week holding `day`: the trend predicted for its end (last
    week's trend plus the planned surplus over 7 days, as the weekly check-in
    predicts it) against the trend on `day`."""
    start = web_home.check_in_week_start(coach, day)
    end = start + 6 * DAY
    prev, at_start = phases.trend_weight(coach, start - DAY), phases.targets(coach, start)
    if prev is None or at_start is None:
        return None
    kcal_per_kg = phases.params(coach)["maintenance_estimate"]["kcal_per_kg"]
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
    corridor: from the trend on the first judged day in the range (inside the
    active phase, past the glycogen window), rising by the band's low and
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


def weekly_rate(coach, day: Date) -> float | None:
    now, before = phases.trend_weight(coach, day), phases.trend_weight(coach, day - 7 * DAY)
    return round(now - before, 2) if now is not None and before is not None else None


class Bands:
    """The active phase's weight band by day (read once per view)."""

    def __init__(self, coach):
        self.phase = phases.active(coach)
        self.params = phases.params(coach)
        self.window = self.params.get("glycogen_window_weeks", 0)

    def on(self, day: Date) -> dict[str, Any] | None:
        """The band for `day`'s phase week; None before the phase or without
        a band (e.g. a cut before its band is decided)."""
        if self.phase is None or not self.params.get("weight_band_kg_per_week"):
            return None
        week = phases.phase_week(self.phase, day)
        return weekly_facts._band(self.params, week) if week >= 1 else None

    def judged(self, day: Date) -> bool:
        """`day` has a band and is past the glycogen window."""
        return self.on(day) is not None and phases.phase_week(self.phase, day) > self.window

    def vs_band(self, day: Date, rate: float | None) -> str | None:
        """The rate of the 7 days ending `day` against the band, as the weekly
        check-in judges a week: "not_evaluated" while any of those days is in
        the glycogen window; None without a rate or a band."""
        band = self.on(day)
        if rate is None or band is None:
            return None
        if not self.judged(day - 6 * DAY):
            return "not_evaluated"
        return weekly_facts._vs_band(rate, band)

