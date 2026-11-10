"""Setting the MFP goal: once, read back once, never retried (spec, stories 54-55).

Code only: the model never gets a tool for this. Callers (phase confirm,
ticket 09's approved proposals) pass a key naming the change:

    result = await mfp_goal.set_once(coach, f"phase-start:{phase_id}", goal, now)
    if result is not None:
        line = mfp_goal.describe(result)  # for the confirmation message

`set_once` claims the key in `mfp_goal_writes` before sending, so a second
call with the same key (double tap, restart, replayed button) sends nothing
and returns None. It calls `api.set_mfp_goal` exactly once and takes the
api's own read-back (`stored`, `matches`); only when that reply never
arrived does it read the goal itself (`api.mfp_goal`, once). It never raises
for MFP or api failures.

Result `status`:
- "set": MFP shows the requested goal (the api allows a gram/kcal of rounding),
  or the requested kcal with each macro within MFP's 5 %-of-calories rounding
  (`macros_rounded`: a free account stores macros as a percentage split).
  A calorie mismatch is never "set".
- "not_set": the write was answered, but MFP shows something else
  (`stored`, None = no goal), or the api refused it before sending
  (`write` "not_sent": nothing was sent).
- "uncertain": the goal couldn't be read back, or the write got no reply
  and MFP doesn't show it (yet): it may still land.
"""

import datetime
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from . import errors
from .ports import Goal

if TYPE_CHECKING:
    from .core import Coach

TOLERANCE = 1  # kcal or g: MFP may round what it stores (as the api's `matches`)
MACRO_STEP_PCT = 5  # without premium MFP stores macros as a % split in these steps


async def set_once(coach: "Coach", key: str, goal: Goal | Mapping[str, Any],
                   now: datetime.datetime) -> dict[str, Any] | None:
    """Set the MFP goal for the change `key`, unless that key was already
    used. `goal` is a Goal or a stored {kcal, protein_g, carbs_g, fat_g}
    dict. See the module docstring."""
    goal = goal if isinstance(goal, Goal) else Goal.of(goal)
    requested = Goal(*(round(v) for v in (goal.kcal, goal.protein_g, goal.carbs_g, goal.fat_g)))
    at = now.isoformat(timespec="seconds")
    claimed = coach.db.execute(
        "INSERT OR IGNORE INTO mfp_goal_writes (key, requested, status, created_at) VALUES (?, ?, 'sending', ?)",
        (key, json.dumps(requested.as_dict()), at),
    ).rowcount == 1
    if not claimed:
        return None

    problems: list[str] = []
    try:
        reply = await coach.api.set_mfp_goal(requested)
    except Exception as exc:  # noqa: BLE001 - the outcome is unknown; read back, never resend
        reply = None
        problems.append(errors.brief("no reply from the api", exc))

    if reply is not None:
        write = reply.get("write") or "sent"
        stored = reply.get("stored")
        if reply.get("error"):
            problems.append(str(reply["error"]))
        if write == "not_sent":
            status = "not_set"
        elif reply.get("matches") is True:
            status = "set"
        elif write == "sent" and rounded_match(stored, requested):
            status = "set"  # a free account stores macros as a split in 5 % steps
        elif reply.get("matches") is False and write in ("sent", "rejected"):
            status = "not_set"
        else:
            status = "uncertain"  # not read back, or MFP never answered the write (it may still land)
    else:
        write = "no_reply"
        try:
            stored = await coach.api.mfp_goal()
        except Exception as exc:  # noqa: BLE001
            stored = None
            problems.append(errors.brief("reading it back failed", exc))
        status = "set" if matches(stored, requested) or rounded_match(stored, requested) else "uncertain"

    result = {"key": key, "status": status, "write": write, "requested": requested.as_dict(),
              "stored": stored.as_dict() if stored is not None else None, "error": "; ".join(problems) or None,
              "macros_rounded": status == "set" and not matches(stored, requested)}
    coach.db.execute(
        "UPDATE mfp_goal_writes SET status = ?, write = ?, stored = ?, error = ?, finished_at = ? WHERE key = ?",
        (status, write, json.dumps(result["stored"]) if result["stored"] is not None else None, result["error"],
         coach.clock.now().isoformat(timespec="seconds"), key),
    )
    return result


def get(coach: "Coach", key: str) -> dict[str, Any] | None:
    """The goal write recorded for `key`, if any."""
    row = coach.db.one("SELECT * FROM mfp_goal_writes WHERE key = ?", (key,))
    if row is None:
        return None
    return {"key": row["key"], "status": row["status"], "write": row["write"],
            "requested": json.loads(row["requested"]),
            "stored": json.loads(row["stored"]) if row["stored"] else None, "error": row["error"]}


def matches(stored: Goal | None, requested: Goal) -> bool:
    """Only for a goal the coach read back itself (the api's reply carries its own `matches`)."""
    if stored is None:
        return False
    return all(abs(a - b) <= TOLERANCE for a, b in zip(stored.as_dict().values(), requested.as_dict().values()))


def rounded_match(stored: Goal | None, requested: Goal) -> bool:
    """Calories match (±TOLERANCE kcal) and each macro is within MFP's
    rounding of a percentage split in MACRO_STEP_PCT steps of the calories
    (accounts without premium store macros that way)."""
    if stored is None or abs(stored.kcal - requested.kcal) > TOLERANCE:
        return False
    step = requested.kcal * MACRO_STEP_PCT / 100
    return all(abs(getattr(stored, k) - getattr(requested, k)) * per_g <= step
               for k, per_g in (("protein_g", 4), ("carbs_g", 4), ("fat_g", 9)))


def describe(result: dict[str, Any]) -> str:
    """One line for the user about how the goal write went."""
    wanted = fmt(result["requested"])
    if result["status"] == "set" and result.get("macros_rounded"):
        return (f"🎯 MyFitnessPal now shows the new goal: {round(result['stored']['kcal']):,} kcal. It rounds macros "
                f"to {MACRO_STEP_PCT} % steps, so it shows {fmt_macros(result['stored'])}; the exact grams are "
                f"in the coach ({fmt_macros(result['requested'])}).")
    if result["status"] == "set":
        return f"🎯 MyFitnessPal now shows the new goal: {fmt(result['stored'])}."
    if result["write"] == "not_sent":
        why = f": {result['error']}" if result["error"] else ""
        return (f"⚠️ MyFitnessPal goal not set (nothing sent{why}). Please set it by hand to {wanted}. "
                "Your coach targets above are in force either way.")
    why = f" ({result['error']})" if result["error"] else ""
    if result["status"] == "not_set":
        shows = f"it still shows {fmt(result['stored'])}" if result["stored"] else "it shows no goal I can read"
        return (f"⚠️ MyFitnessPal goal not set{why}: {shows}. Please set it by hand to {wanted}; "
                "I won't retry. Your coach targets above are in force either way.")
    shows = f" (just now it showed {fmt(result['stored'])})" if result["stored"] else ""
    return (f"⚠️ I couldn't check whether MyFitnessPal took the new goal{why}{shows}. Please check it shows "
            f"{wanted} and set it by hand if not; I won't retry. Your coach targets above are in force either way.")


def fmt(goal: dict[str, Any]) -> str:
    return f"{round(goal['kcal']):,} kcal · {fmt_macros(goal)}"


def fmt_macros(goal: dict[str, Any]) -> str:
    return f"P {round(goal['protein_g'])} g · C {round(goal['carbs_g'])} g · F {round(goal['fat_g'])} g"
