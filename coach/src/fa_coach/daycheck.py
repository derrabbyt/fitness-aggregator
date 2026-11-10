"""Day checks (ticket 20): whether a logged day's intake can be trusted.

MFP can't tell a partly logged day from a complete one, so code looks at the
number:

- **partial suspected**: the day's kcal are below `data.partial_day_share` of
  the median of the other logged days within 3 days either side (the daily
  target when fewer than 3 such days are logged; no check without either).
- **implausible**: the day's kcal exceed `data.implausible_intake_factor` x
  its daily target (only days with a target, i.e. in the active phase).
- **confirmed**: the user confirmed the day (`complete` or `real`) at exactly
  its current synced kcal. A later change in MFP lapses the confirmation.
- **incomplete** = partial suspected and not confirmed: left out of the
  maintenance estimate (its week is not usable), weekly logging completeness
  and adherence / intake vs target.

- `statuses(coach, start, end, p)`: {date: status} for the logged days in the range.
- `incomplete_days(coach, start, end, p)`: the incomplete dates in the range.
- `confirm(coach, day, kind, source, now)`: store a confirmation at the day's current kcal.
"""

import datetime
import statistics
from typing import TYPE_CHECKING, Any

from . import history

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
NEIGHBOUR_DAYS = 3  # the 7 days around a day: 3 either side
MIN_NEIGHBOURS = 3  # fewer logged neighbours: compare with the daily target
KINDS = ("complete", "real")


def statuses(coach: "Coach", start: Date, end: Date, p: dict[str, Any], *,
             high_side: bool = True) -> dict[str, dict[str, Any]]:
    """{date: {kcal, reference_kcal (what partial is judged against),
    target_kcal, partial_suspected, implausible, confirmed, confirmation,
    incomplete}} for the days from `start` to `end` with food logged.
    `high_side=False` skips the implausible check (and the daily target
    unless partial needs it): enough for `incomplete`, and much cheaper."""
    from . import phases  # phases imports this module

    rows = history.days(coach.db, (start - NEIGHBOUR_DAYS * DAY).isoformat(),
                        (end + NEIGHBOUR_DAYS * DAY).isoformat())
    eaten = {r["date"]: r["kcal"] for r in rows if r["logged"] and r["kcal"] is not None}
    confirmations = {r["date"]: dict(r) for r in coach.db.all(
        "SELECT date, kind, kcal, source, confirmed_at FROM day_confirmations WHERE date BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()))}
    share, factor = p["data"]["partial_day_share"], p["data"]["implausible_intake_factor"]
    out = {}
    day = start
    while day <= end:
        iso = day.isoformat()
        kcal = eaten.get(iso)
        if kcal is not None:
            others = [eaten[d.isoformat()] for d in _around(day) if d.isoformat() in eaten]
            target = phases.daily_target(coach, day) if high_side or len(others) < MIN_NEIGHBOURS else None
            target_kcal = target["kcal"] if target else None
            reference = statistics.median(others) if len(others) >= MIN_NEIGHBOURS else target_kcal
            partial = reference is not None and kcal < share * reference
            implausible = target_kcal is not None and kcal > factor * target_kcal
            confirmation = confirmations.get(iso)
            confirmed = confirmation is not None and round(confirmation["kcal"]) == round(kcal)
            out[iso] = {
                "kcal": kcal,
                "reference_kcal": reference,
                "target_kcal": target_kcal,
                "partial_suspected": partial,
                "implausible": implausible,
                "confirmed": confirmed,
                "confirmation": confirmation if confirmed else None,
                "incomplete": partial and not confirmed,
            }
        day += DAY
    return out


def status(coach: "Coach", day: Date, p: dict[str, Any]) -> dict[str, Any] | None:
    """One day's status, None if no food is logged that day."""
    return statuses(coach, day, day, p).get(day.isoformat())


def incomplete_days(coach: "Coach", start: Date, end: Date, p: dict[str, Any]) -> set[str]:
    return {d for d, s in statuses(coach, start, end, p, high_side=False).items() if s["incomplete"]}


def confirm(coach: "Coach", day: Date, kind: str, source: str, now: datetime.datetime) -> float | None:
    """Confirm `day` at its current synced kcal (replacing an earlier
    confirmation). Returns those kcal, None if no food is logged that day."""
    if kind not in KINDS:
        raise ValueError(f"unknown confirmation kind {kind!r}")
    record = history.day(coach.db, day.isoformat())
    if record is None or not record["logged"] or record["kcal"] is None:
        return None
    coach.db.execute(
        "INSERT OR REPLACE INTO day_confirmations (date, kind, kcal, source, confirmed_at) VALUES (?, ?, ?, ?, ?)",
        (day.isoformat(), kind, record["kcal"], source, now.isoformat(timespec="seconds")),
    )
    return record["kcal"]


def _around(day: Date) -> list[Date]:
    return [day + n * DAY for n in range(-NEIGHBOUR_DAYS, NEIGHBOUR_DAYS + 1) if n]
