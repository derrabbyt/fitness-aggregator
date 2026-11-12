"""The web page's lift detail (coach-web ticket 09): the `lift` view, as of a
day (default today), and the lift's controls.

GET lift?exercise_id=…&day=…&offset=0&limit=3

- The head: name, status and latest heaviest set as on the Training list
  (`web_training`), plus whether it counts and is paused.
- `chart`: every session's heaviest working set as estimated 1RM, oldest
  first (bodyweight lifts on the effective load, like the status), each
  marked `pr` (beat the best since the baseline; never while paused, as in
  the weekly facts) and `baseline_reset` (the session that starts a new
  history after a reset). Sessions without a working set in the rep range
  or at another location are left out (they are ignored for progression).
- `resets`: the baseline resets up to the day, with their reason and the
  session that started each (null while none has yet).
- `sessions`: one line per session, newest first (date, heaviest working
  set, status), `limit` from `offset` ("show more" asks for the next page);
  ignored sessions are listed with their reason.
- `controls`: the state the page's controls start from.

The controls run the chat tools through `web_setup.run_tool`, so values are
checked by the tools' schemas and refusals carry their words. Counts / not
counted and pause reuse Setup › Exercises' commands (ticket 12):
`setup/exercises/classify {exercise_id, classification}` and
`setup/exercises/pause {exercise_id, paused, reason?}`; this module adds
`lift/reset {exercise_id, reason, date?}` (`mark_baseline_reset`).
"""

import datetime
from typing import Any

from .. import progression, views
from ..registry import registry
from . import training_feedback, web_training
from .web_setup import field, run_tool

Date = datetime.date
DAY = datetime.timedelta(days=1)
PAGE = 3  # sessions shown before "show more"
MAX_PAGE = 50
IGNORED = web_training.IGNORED
SESSION_STATUS = {"improved": "progressing", "declined": "declining"}


@registry.view("lift", schema="web_lift")
def lift(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    day = views.day(query, now)
    exercise_id = query.get("exercise_id") or ""
    offset, limit = _int(query, "offset", 0, 0), _int(query, "limit", PAGE, 1, MAX_PAGE)
    data = progression.lifts(coach, day).get(exercise_id)
    if data is None:
        raise views.WebError(404, f"There is no lift {exercise_id!r} in the synced Hevy history.")
    row = next(r for r in progression.week(coach, day - 6 * DAY, day, Date.min)["tracked_lifts"]
               if r["exercise_id"] == exercise_id)
    head = web_training._lift(row, data)
    paused = data["paused"]
    stored = progression.settings(coach).get(exercise_id, {})
    entries = data["entries"]
    lines = list(reversed(entries))
    return {
        "date": day.isoformat(),
        "freshness": views.freshness(coach, now),
        **{k: head[k] for k in ("exercise_id", "name", "status", "not_judged_reason", "bodyweight_exercise",
                                "last_session_date", "latest")},
        "counts": data["counts"],
        "paused": paused,
        "chart": [{"date": e["date"], "session_id": e["session_id"], **_set(e["top"]),
                   "pr": e["is_pr"] and not paused, "baseline_reset": e["not_judged_reason"] == "baseline_reset"}
                  for e in entries if e["top"] is not None and e["not_judged_reason"] not in IGNORED],
        "resets": _resets(coach, exercise_id, day, entries),
        "sessions": {
            "items": [_line(e, data["counts"], paused) for e in lines[offset:offset + limit]],
            "offset": offset,
            "total": len(lines),
            "next_offset": offset + limit if offset + limit < len(lines) else None,
        },
        "controls": {
            "classification": data["classification"],
            "paused_reason": stored.get("paused_reason") if paused else None,
            "reset_reasons": list(training_feedback.RESET_REASONS),
        },
    }


def _int(query: dict[str, str], key: str, default: int, low: int, high: int | None = None) -> int:
    raw = query.get(key)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise views.WebError(400, f"{key} must be a whole number.") from None
    if value < low or (high is not None and value > high):
        raise views.WebError(400, f"{key} must be between {low} and {high}." if high is not None
                             else f"{key} must be at least {low}.")
    return value


def _set(top: dict[str, Any]) -> dict[str, Any]:
    return {k: top[k] for k in ("load_kg", "reps", "effective_load_kg", "e1rm_kg")}


def _line(entry: dict[str, Any], counts: bool, paused: bool) -> dict[str, Any]:
    status = entry["status"]
    if entry["stalled"] and counts:
        status = "stall"
    return {
        "date": entry["date"],
        "session_id": entry["session_id"],
        "top_set": _set(entry["top"]) if entry["top"] is not None else None,
        "status": SESSION_STATUS.get(status, status),
        "not_judged_reason": entry["not_judged_reason"] if status == "not_judged" else None,
        "pr": entry["is_pr"] and not paused,
    }


def _resets(coach, exercise_id: str, day: Date, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each reset up to `day` with the session that started its new baseline
    (the first session on or after its date that the judge marked, else null)."""
    started = [e for e in entries if e["not_judged_reason"] == "baseline_reset"]
    out = []
    for r in coach.db.all("SELECT from_date, session_id, reason FROM baseline_resets"
                          " WHERE exercise_id = ? AND from_date <= ? ORDER BY from_date, id",
                          (exercise_id, day.isoformat())):
        first = next((e for e in started if e["session_id"] == r["session_id"]
                      or (r["session_id"] is None and e["date"] >= r["from_date"])), None)
        out.append({"from_date": r["from_date"], "reason": r["reason"],
                    "session_date": first["date"] if first else None})
    return out


# --- commands ------------------------------------------------------------------------


@registry.web_command("lift/reset")
async def reset(coach, body: dict[str, Any], now: datetime.datetime) -> Any:
    args = {"exercise_id": field(body, "exercise_id"), "reason": field(body, "reason")}
    if body.get("date"):
        args["date"] = body["date"]
    return await run_tool(coach, "mark_baseline_reset", args, now)
