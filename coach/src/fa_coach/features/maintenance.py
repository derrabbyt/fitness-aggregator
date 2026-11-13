"""Maintenance (skill phase-maintenance): the weekly decision guard's rule.

Flat is the band (the phase's `weight_band_kg_per_week`); a small drift up
to the limits (`weight_lower_limit_kg_per_week` / `weight_upper_limit_kg_per_week`)
is watched and stored as a hold, so it counts for no streak. Beyond a limit the
trend calls for `small_step_kcal` toward flat (MAINT-SIZE), and the core's
confirmation (`decisions.confirmation_weeks` counted weeks) gates the
proposal. Phase start needs nothing here: `start.surplus_kcal` 0 makes the
start kcal the maintenance estimate (phases.preview).
"""

from typing import Any

from . import weekly_checkin


def expected_change(weight: dict[str, Any], decisions: dict[str, Any]) -> tuple[str, float | None, str | None, str]:
    rate, band, where = weight["weekly_rate_kg"], weight["band"], weight["vs_band"]
    if where == "not_evaluated" or rate is None:
        return "hold", None, None, "the trend was not evaluated"
    limits = f"the drift limits {band['lower_limit']:g} to {band['upper_limit']:g}"
    if where not in ("above_limit", "below_limit"):
        return "hold", None, None, f"the trend {rate:+.2f} kg/week is within {limits}"
    up = where == "above_limit"
    return ("decrease" if up else "increase", decisions["small_step_kcal"], "small",
            f"the trend {rate:+.2f} kg/week is {'above' if up else 'below'} {limits}")


weekly_checkin.phase_expected_change["maintenance"] = expected_change
