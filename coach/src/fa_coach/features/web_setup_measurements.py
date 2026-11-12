"""Setup › Measurements (coach-web ticket 12): waist values (the one taken at
the phase start, then every stored value, newest first) and the photo sets
by date, with what is due next. Adding a waist value runs the chat's waist
code (same range check, same table):

    POST setup/measurements/waist {cm, date?}   (date: default today, never in the future)

Photos are served read-only, one at a time, by the coach API's photo route
(`GET /api/coach/photos/<date>/<n>`, `Coach.photo`); the view lists their
URLs relative to /api/coach/. Photos are never changed from the web.
"""

import datetime
from typing import Any

from .. import phases, views
from ..registry import registry
from . import measurements, web_setup

Date = datetime.date
LOOK_AHEAD_DAYS = 7 * 26


def _short(day: str) -> str:
    d = Date.fromisoformat(day)
    return f"{d.day} {d:%b}"


def _next_due(coach, kind: str, today: Date) -> str | None:
    """The first due date from today on that hasn't had its value yet."""
    for item in measurements.measurements_due(coach, today, today + datetime.timedelta(days=LOOK_AHEAD_DAYS)):
        if item["kind"] == kind and not measurements.received_since(coach, kind, item["date"]):
            return item["date"]
    return None


def _start(coach) -> dict[str, Any] | None:
    phase = phases.active(coach)
    cm = phase["setup"].get("waist_cm_start") if phase else None
    return {"date": phase["start_date"], "cm": float(cm)} if cm is not None else None


def _waist(coach) -> list[dict[str, Any]]:
    return list(reversed(measurements.waist_values(coach)))


def _sets(coach) -> list[dict[str, Any]]:
    out = []
    for s in reversed(measurements.photo_sets(coach)):
        out.append({"date": s["date"], "photos": [
            {"number": n, "url": f"photos/{s['date']}/{n}", "caption": p["caption"], "received_at": p["received_at"]}
            for n, p in enumerate(s["photos"], start=1)]})
    return out


@registry.view_part("setup", "measurements", schema="web_setup_summary", order=80)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    values, start, sets = _waist(coach), _start(coach), _sets(coach)
    if values:
        waist = f"Waist {values[0]['cm']:g} cm on {_short(values[0]['date'])}"
    elif start:
        waist = f"Waist {start['cm']:g} cm at the start"
    else:
        waist = "No waist values"
    if sets:
        photos = f"{len(sets)} photo set{'' if len(sets) == 1 else 's'}, latest {_short(sets[0]['date'])}"
    else:
        photos = "no photo sets"
    return {"summary": f"{waist} · {photos}"}


@registry.view("setup/measurements", schema="web_setup_measurements")
def measurements_view(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    today = now.date()
    phase = phases.active(coach)
    return {
        "today": today.isoformat(),
        "waist": {"start": _start(coach), "values": _waist(coach), "next_due": _next_due(coach, "waist", today),
                  "min": measurements.WAIST_CM[0], "max": measurements.WAIST_CM[1]},
        "photos": {"enabled": bool(phases.params(coach)["measurements"]["photos_enabled"]) if phase else None,
                   "next_due": _next_due(coach, "photos", today), "sets": _sets(coach)},
    }


@registry.web_command("setup/measurements/waist")
async def add_waist(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    cm = web_setup.field(body, "cm")
    if cm is None:
        raise views.WebError(400, "cm is missing.")
    if isinstance(cm, bool) or not isinstance(cm, int | float):
        raise views.WebError(400, f"cm: {cm!r} is not a number.")
    day = views.day({"day": body.get("date") or ""}, now)
    problem = measurements.waist_problem(cm)
    if problem:
        lo, hi = measurements.WAIST_CM
        raise views.WebError(400, f"{problem} ({lo}–{hi} cm).")
    measurements.add_waist(coach, float(cm), day, now)
    return measurements_view(coach, {}, now)
