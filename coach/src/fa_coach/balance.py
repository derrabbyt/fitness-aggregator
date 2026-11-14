"""A day's energy balance for the web page: what was eaten minus what the day
burned by the coach's estimate (base maintenance at the step goal + the step
part + counted activity, i.e. the daily target without its planned surplus).
Positive is a surplus, negative a deficit. Only days inside a phase have an
estimate; outside one the balance is None. Today has none either: the day
isn't over, so a half-eaten day would read as a big deficit.

The week's total adds the complete days (partial and missing days don't count)
and turns it into kg at the core `maintenance_estimate.kcal_per_kg` (7,500 kcal
a kg, the factor the weekly check-in uses), as a rough guide only.
"""

import datetime
from typing import TYPE_CHECKING, Any

from . import phases

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date


def burned(coach: "Coach", day: Date) -> float | None:
    """The day's estimated burn: its target minus the planned surplus; None outside a phase."""
    target = phases.daily_target(coach, day)
    return target["kcal"] - target["surplus_kcal"] if target else None


def of_day(coach: "Coach", day: Date, eaten_kcal: float | None, today: Date) -> int | None:
    """Eaten minus burned, whole kcal; None without food, outside a phase, or for `today` and later."""
    if eaten_kcal is None or day >= today:
        return None
    burn = burned(coach, day)
    return round(eaten_kcal - burn) if burn is not None else None


def total(coach: "Coach", days: list[dict[str, Any]]) -> dict[str, Any]:
    """{kcal, days, kg} over the complete days that have a balance (`days`
    items carry `logged` and `balance_kcal`); kcal and kg are None without any."""
    counted = [d["balance_kcal"] for d in days if d["logged"] == "complete" and d["balance_kcal"] is not None]
    if not counted:
        return {"kcal": None, "days": 0, "kg": None}
    kcal = sum(counted)
    per_kg = phases.params(coach)["maintenance_estimate"]["kcal_per_kg"]
    return {"kcal": kcal, "days": len(counted), "kg": round(kcal / per_kg, 2)}
