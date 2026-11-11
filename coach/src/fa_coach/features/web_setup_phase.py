"""Setup › Phase & targets (coach-web ticket 10): the active phase, its week,
base maintenance, surplus, the step goal and the current daily targets; the
step goal is the one value edited here (`setup/step-goal`, through
`record_setup_value`, as in chat). The targets themselves change only through
proposals approved in Telegram, and a phase starts only there.
"""

import datetime
from typing import Any

from .. import phases
from ..registry import registry
from . import web_setup


@registry.view_part("setup", "phase_targets", schema="web_setup_summary", order=10)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    phase = phases.active(coach)
    goal = f"step goal {phases.params(coach)['steps']['step_goal']:,}"
    if phase is None:
        return {"summary": f"No active phase · {goal}"}
    p = phases.params(coach)
    week = phases.phase_week(phase, now.date())
    when = f"week {week}" if week >= 1 else f"starts {_day(phase['start_date'])}"
    return {"summary": f"{p.get('name', phase['phase_id'])} · {when} · {goal}"}


@registry.view("setup/phase-targets", schema="web_setup_phase_targets")
def phase_targets(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    phase = phases.active(coach)
    p = phases.params(coach)
    goal = p["steps"]["step_goal"]
    out: dict[str, Any] = {
        "phase": None,
        "targets": None,
        "step_goal": {"value": goal, "default": coach.skills.params()["steps"]["step_goal"],
                      **web_setup.setup_range(coach, "step_goal"), "editable": web_setup.editable(coach)},
    }
    if phase is None:
        return out
    week = phases.phase_week(phase, now.date())
    out["phase"] = {"phase_id": phase["phase_id"], "name": p.get("name", phase["phase_id"]),
                    "start_date": phase["start_date"], "week": week if week >= 1 else None}
    current = phases.targets(coach, now.date())
    if current is None:
        return out
    base = current["base_maintenance_kcal"]
    k, avg = current.get("step_kcal_per_step"), current.get("avg_day_steps")
    base_at_goal = base - k * (avg - goal) if k is not None and avg is not None else base
    rest = base_at_goal + current["surplus_kcal"]
    activity = p["activity"]
    today = phases.daily_target(coach, now.date())
    out["targets"] = {
        "valid_from": current["valid_from"],
        "base_maintenance_kcal": round(base),
        "avg_day_steps": round(avg) if avg is not None else None,
        "base_at_step_goal_kcal": round(base_at_goal),
        "surplus_kcal": round(current["surplus_kcal"]),
        "avg_daily_target_kcal": round(current["avg_daily_target_kcal"]),
        "mfp_goal_kcal": round(current["mfp_goal_kcal"]),
        "at_step_goal": {
            "rest": round(rest),
            "lifting": round(rest + activity["lifting_kcal_per_session"]),
            "wrestling": round(rest + activity["wrestling_kcal_per_session"]),
        },
        "today": None if today is None else {
            "kcal": today["kcal"], **{k: today["macros"][k] for k in ("protein_g", "carbs_g", "fat_g")}},
    }
    return out


@registry.web_command("setup/step-goal")
async def set_step_goal(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{step_goal}: recorded like chat's `record_setup_value`; returns the section."""
    web_setup.require_editable(coach)
    value = web_setup.field(body, "step_goal")
    await web_setup.run_tool(coach, "record_setup_value", {"key": "step_goal", "value": value}, now)
    return phase_targets(coach, {}, now)


def _day(iso: str) -> str:
    return datetime.date.fromisoformat(iso).strftime("%a %-d %b")
