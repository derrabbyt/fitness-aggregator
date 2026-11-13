"""The cut's numbers (skill phase-cut, params `cut`), computed by code.

- `plan(p, setup)`: the deficit from the setup's `cut_level`, or from its
  `goal` (the rate it needs, capped at `cut.max_deficit_kcal`, with the level
  it suggests), the target rate (deficit x 7 / kcal_per_kg, negative) and the
  band (target x (1 +- `cut.band_tolerance`)), plus a warning past
  `cut.warn_above_kcal`. Raises ValueError for a goal that can't be planned.
  Phase start stores the deficit in the setup (`deficit_kcal`) and shows the
  plan on the preview card.
- `apply(p, deficit)`: puts a setup's deficit and its band into merged params
  (`phases.params_for`), so the start, the weekly band and the decision guard
  use them.
"""

import datetime
from typing import Any

PHASE_ID = "cut"
# Setup values only a cut takes (phase_setup schema); end_date is optional (a mini-cut).
SETUP_KEYS = ("cut_level", "goal", "end_date")
LEVELS = ("conservative", "moderate", "aggressive")
MIN_GOAL_WEEKS = 1


def _rate(p: dict[str, Any], deficit: float) -> float:
    """The weekly weight change a daily deficit makes (kg/week, negative), unrounded."""
    return -deficit * 7 / p["maintenance_estimate"]["kcal_per_kg"]


def target_rate(p: dict[str, Any], deficit: float) -> float:
    return round(_rate(p, deficit), 2)


def band(p: dict[str, Any], deficit: float) -> dict[str, float]:
    rate, tolerance = _rate(p, deficit), p["cut"]["band_tolerance"]
    return {"low": round(rate * (1 + tolerance), 2), "high": round(rate * (1 - tolerance), 2)}


def apply(p: dict[str, Any], deficit: float) -> None:
    p["start"]["deficit_kcal"] = deficit
    p["weight_band_kg_per_week"] = [{"from_week": 1, "to_week": None, **band(p, deficit)}]


def suggested_level(p: dict[str, Any], deficit: float) -> str:
    """The smallest level that covers `deficit`."""
    levels = p["cut"]["levels_kcal"]
    return next((name for name in LEVELS if deficit <= levels[name]), LEVELS[-1])


def plan(p: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    cfg = p["cut"]
    goal = _goal(p, setup) if setup.get("goal") else None
    if setup.get("cut_level"):
        level, source = setup["cut_level"], "level"
        deficit = cfg["levels_kcal"][level]
    elif goal is not None:
        deficit, source = goal["deficit_kcal"], "goal"
        level = goal["suggested_level"]
    else:
        level, source = cfg["default_level"], "level"
        deficit = cfg["levels_kcal"][level]
    warnings = []
    if goal is not None and goal["capped"]:
        warnings.append(f"The goal needs about {goal['needed_deficit_kcal']:,} kcal a day below maintenance; "
                        f"the cut is capped at {cfg['max_deficit_kcal']:,}, so at the cap it takes until about "
                        f"{goal['date_at_cap']}.")
    if deficit > cfg["warn_above_kcal"]:
        warnings.append(f"{deficit:,} kcal a day is an aggressive deficit, meant for experienced dieters: hunger "
                        f"and adherence get hard. A moderate {cfg['levels_kcal']['moderate']:,} is the default.")
    return {"level": level, "deficit_kcal": deficit, "source": source, "target_rate_kg_per_week": target_rate(p, deficit),
            "band": band(p, deficit), "goal": goal, "warning": " ".join(warnings) or None}


def _goal(p: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    """What the goal needs: the goal weight (from a body-fat goal: the same
    lean mass at the goal body fat), the rate to reach it by its date, the
    deficit for that rate (capped) and the level it suggests."""
    g, cfg = setup["goal"], p["cut"]
    weight = setup["starting_trend_weight_kg"]
    start = datetime.date.fromisoformat(setup["start_date"])
    by = datetime.date.fromisoformat(g["date"])
    weeks = (by - start).days / 7
    if weeks < MIN_GOAL_WEEKS:
        raise ValueError(f"the goal date {by} must be at least {MIN_GOAL_WEEKS} week after the start ({start})")
    if "weight_kg" in g:
        goal_weight = g["weight_kg"]
    else:
        if g["body_fat_pct"] >= g["current_body_fat_pct"]:
            raise ValueError("the goal body fat must be below the current body fat")
        goal_weight = weight * (1 - g["current_body_fat_pct"] / 100) / (1 - g["body_fat_pct"] / 100)
    loss = weight - goal_weight
    if loss <= 0:
        raise ValueError(f"the goal weight {goal_weight:.1f} kg isn't below the starting trend weight {weight} kg")
    rate = loss / weeks
    needed = round(rate * p["maintenance_estimate"]["kcal_per_kg"] / 7 / 10) * 10
    deficit = min(needed, cfg["max_deficit_kcal"])
    at_cap = start + datetime.timedelta(days=round(loss * p["maintenance_estimate"]["kcal_per_kg"] / deficit))
    return {"goal_weight_kg": round(goal_weight, 1), "date": by.isoformat(), "weeks": round(weeks, 1),
            "needed_rate_kg_per_week": round(-rate, 2), "needed_deficit_kcal": needed, "deficit_kcal": deficit,
            "capped": needed > cfg["max_deficit_kcal"], "date_at_cap": at_cap.isoformat(),
            "suggested_level": suggested_level(p, needed)}
