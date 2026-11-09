"""Setting the MFP goal: once, read back once, never retried (spec, stories 54-55).

Code only: the model never gets a tool for this. Callers (phase confirm,
ticket 09's approved proposals) pass a key naming the change:

    result = await mfp_goal.set_once(coach, f"phase-start:{phase_id}", goal, now)
    if result is not None:
        line = mfp_goal.describe(result)  # for the confirmation message

`set_once` claims the key in `mfp_goal_writes` before sending, so a second
call with the same key (double tap, restart, replayed button) sends nothing
and returns None. It calls `api.set_mfp_goal` exactly once, then
`api.mfp_goal` exactly once, and never raises for MFP or api failures.

Result `status`:
- "set": MFP shows the requested goal (within a gram/kcal of rounding).
- "not_set": the write was answered, but MFP shows something else
  (`stored`, None = no goal).
- "uncertain": the goal couldn't be read back, or the write got no reply
  and MFP doesn't show it (yet): it may still land.
"""

import datetime
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import Coach

KEYS = ("kcal", "protein_g", "carbs_g", "fat_g")
TOLERANCE = 1  # kcal or g: MFP may round what it stores


async def set_once(coach: "Coach", key: str, goal: dict[str, Any], now: datetime.datetime) -> dict[str, Any] | None:
    """Set the MFP goal {kcal, protein_g, carbs_g, fat_g} for the change `key`,
    unless that key was already used. See the module docstring."""
    requested = {k: round(goal[k]) for k in KEYS}
    at = now.isoformat(timespec="seconds")
    claimed = coach.db.execute(
        "INSERT OR IGNORE INTO mfp_goal_writes (key, requested, status, created_at) VALUES (?, ?, 'sending', ?)",
        (key, json.dumps(requested), at),
    ).rowcount == 1
    if not claimed:
        return None

    errors: list[str] = []
    reply_stored = None
    try:
        reply = await coach.api.set_mfp_goal(requested)
        write = reply.get("write") or "sent"
        reply_stored = reply.get("stored")
        if reply.get("error"):
            errors.append(str(reply["error"]))
    except Exception as exc:  # noqa: BLE001 - the outcome is unknown; read back, never resend
        write = "no_reply"
        errors.append(_short(exc))

    try:
        stored, known = await coach.api.mfp_goal(), True
    except Exception as exc:  # noqa: BLE001
        errors.append(f"reading it back failed: {_short(exc)}")
        stored, known = reply_stored, reply_stored is not None  # the api's own read-back after the write

    if known and matches(stored, requested):
        status = "set"
    elif known and write in ("sent", "rejected", "not_sent"):
        status = "not_set"
    else:
        status = "uncertain"  # nothing read back, or the write's fate is unknown (it may still land)
    result = {"key": key, "status": status, "write": write, "requested": requested,
              "stored": _clean(stored), "error": "; ".join(errors) or None}
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


def matches(stored: dict[str, Any] | None, requested: dict[str, Any]) -> bool:
    if not stored:
        return False
    try:
        return all(abs(float(stored[k]) - requested[k]) <= TOLERANCE for k in KEYS)
    except (KeyError, TypeError, ValueError):
        return False


def describe(result: dict[str, Any]) -> str:
    """One line for the user about how the goal write went."""
    wanted = fmt(result["requested"])
    if result["status"] == "set":
        return f"🎯 MyFitnessPal now shows the new goal: {fmt(result['stored'])}."
    why = f" ({result['error']})" if result["error"] else ""
    if result["status"] == "not_set":
        shows = f"it still shows {fmt(result['stored'])}" if result["stored"] else "it shows no goal I can read"
        return (f"⚠️ MyFitnessPal goal not set{why}: {shows}. Please set it by hand to {wanted}; "
                "I won't retry. Your coach targets above are in force either way.")
    shows = f" (just now it showed {fmt(result['stored'])})" if result["stored"] else ""
    return (f"⚠️ I couldn't check whether MyFitnessPal took the new goal{why}{shows}. Please check it shows "
            f"{wanted} and set it by hand if not; I won't retry. Your coach targets above are in force either way.")


def fmt(goal: dict[str, Any]) -> str:
    return (f"{round(goal['kcal']):,} kcal · P {round(goal['protein_g'])} g · C {round(goal['carbs_g'])} g · "
            f"F {round(goal['fat_g'])} g")


def _clean(stored: Any) -> dict[str, Any] | None:
    if not isinstance(stored, dict):
        return None
    try:
        return {k: stored[k] for k in KEYS}
    except KeyError:
        return None


def _short(exc: Exception) -> str:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return text[:200]
