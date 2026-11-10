"""`/today` and `get_today` (ticket 18): the live balance of a day. Code
syncs first, then shows the steps against the step goal and the steps to
go, the step kcal so far vs the goal, the target build-up (base at the step
goal, steps, each counted session, surplus), what was eaten and what's left.
Today is provisional until the day ends; past days use their final steps.
"""

import datetime
from typing import Any

from .. import history, phases
from ..ask import ToolError
from ..registry import registry

NO_PHASE = "No phase is active, so there is no daily target yet. Start one with “start reverse”."


def view(coach, day: datetime.date, now: datetime.datetime) -> dict[str, Any] | None:
    """The day's balance, None outside the active phase."""
    target = phases.daily_target(coach, day)
    if target is None:
        return None
    record = history.day(coach.db, day.isoformat())
    eaten = round(record["kcal"]) if record and record["logged"] and record["kcal"] is not None else None
    steps = target["steps"]
    return {
        "date": day.isoformat(),
        "provisional": day == now.date(),
        "steps": None if steps is None else {
            **steps, "to_go": max(0, steps["goal"] - steps["steps"]) if steps["tracked"] else None},
        "build_up": {
            "base_at_step_goal_kcal": target["base_at_step_goal_kcal"],
            "step_kcal": steps["kcal"] if steps else None,
            "sessions": [{k: s[k] for k in ("type", "status", "kcal_counted", "note")}
                         for s in target["activity"]["sessions"] if s["status"] != "skipped"],
            "surplus_kcal": target["surplus_kcal"],
        },
        "target_kcal": target["kcal"],
        "macros": {k: target["macros"][k] for k in ("protein_g", "fat_g", "carbs_g")},
        "eaten_kcal": eaten,
        "left_kcal": target["kcal"] - eaten if eaten is not None else target["kcal"],
    }


def render(v: dict[str, Any]) -> str:
    day = datetime.date.fromisoformat(v["date"])
    label = "Today" if v["provisional"] else day.strftime("%a %-d %b")
    lines = [f"{label}{' so far' if v['provisional'] else ''}:"]
    steps, b = v["steps"], v["build_up"]
    if steps is None:
        lines.append("Steps: no step model in these targets.")
    elif not steps["tracked"]:
        lines.append(f"Steps: not tracked (under the tracking threshold), counted at your average "
                     f"{steps['avg_day_steps']:,}: {steps['kcal']:+,} kcal vs the {steps['goal']:,} goal.")
    else:
        to_go = f", {steps['to_go']:,} to go" if steps["to_go"] else ", goal reached"
        removed = f" ({steps['run_steps_removed']:,} run steps left out)" if steps["run_steps_removed"] else ""
        so_far = " so far" if v["provisional"] else ""
        lines.append(f"Steps: {steps['steps']:,} / {steps['goal']:,}{to_go}{removed}.")
        lines.append(f"Step kcal{so_far}: {steps['kcal']:+,} kcal vs the goal "
                     f"({steps['kcal_per_1000_steps']:g} kcal per 1,000 steps).")
    parts = [f"base at step goal {b['base_at_step_goal_kcal']:,}"]
    if b["step_kcal"] is not None:
        parts.append(f"steps {b['step_kcal']:+,}")
    parts += [f"{s['note'] or s['type']} {round(s['kcal_counted']):+,}" for s in b["sessions"]]
    parts.append(f"surplus {b['surplus_kcal']:+,}")
    lines.append(f"Target: {v['target_kcal']:,} kcal = " + ", ".join(parts) + ".")
    m = v["macros"]
    lines.append(f"Macros: P {m['protein_g']} g · F {m['fat_g']} g · C {m['carbs_g']} g.")
    if v["eaten_kcal"] is None:
        lines.append(f"Eaten: nothing logged yet. Left: {v['left_kcal']:,} kcal.")
    else:
        lines.append(f"Eaten: {v['eaten_kcal']:,} kcal. Left: {v['left_kcal']:,} kcal.")
    if v["provisional"]:
        lines.append("Provisional: the target moves with your steps until the day ends.")
    return "\n".join(lines)


@registry.command("today", "Today's steps, target build-up, eaten and left")
async def today_command(coach, args: str, now: datetime.datetime) -> None:
    await coach.sync(now)
    v = view(coach, now.date(), now)
    coach.say(render(v) if v else NO_PHASE)


@registry.tool(
    "get_today",
    "A day's live balance (default today), after a fresh sync: steps vs the step goal and steps to go, step kcal "
    "vs the goal (today: so far, provisional until the day ends), the target build-up (base at the step goal, "
    "step kcal, each counted session, surplus), macros, eaten and left. Past days use their final steps.",
    {"type": "object", "additionalProperties": False, "properties": {"date": {"type": "string", "format": "date"}}},
)
async def get_today(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    day = datetime.date.fromisoformat(args["date"]) if args.get("date") else now.date()
    if day > now.date():
        raise ToolError("that day hasn't started yet")
    await coach.sync(now)
    v = view(coach, day, now)
    if v is None:
        raise ToolError("that day is outside the active phase")
    return v
