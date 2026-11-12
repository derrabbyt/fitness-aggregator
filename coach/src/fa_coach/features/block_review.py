"""Block review (coach-reviews ticket 02; spec, "Block review").

- Schedule: a training block is `reviews.block_weeks` weeks (the setup value
  `block_weeks`, default 5, with history: the value in force today counts).
  Block 1 starts on the phase start; block n+1 starts the day after block n
  ended. On the day after a block's last day the `block-review` job reviews
  it. "Block done" (chat tool `end_block`) ends the current block today and
  reviews it right away, so the count restarts tomorrow. Where a block ended
  comes from the stored reviews themselves (`reviews` table): the next block
  starts the day after the phase's latest block review's `period_end`.
- Facts (code, `block_facts.schema.json`): per lift its sessions, statuses,
  PRs, change in estimated 1RM and stall / decline streaks at the block's
  end (progression.py); the strength trend (mean change of the counting
  lifts); stalls; the deload signal (`training.deload_min_lifts_declining`
  counting lifts declining `decline_sessions_for_deload` sessions in a row
  at the end); lifting sessions done vs planned (the plan's non-optional
  lifting sessions) and skipped; per session its working sets (flag over
  `volume_note_max_sets_per_session`) and working sets per exercise. Hevy
  sends no muscle groups, so the model judges the per-muscle note
  (`volume_note_max_sets_per_muscle_per_session`) from the exercise titles,
  worded as an estimate. Context notes of the block are included.
- Text: the block-review skill (COACH_DECISION_MODEL, no tools) writes the
  report and its advice in words, a deload week included when the signals
  point there; never a proposal and no buttons. Without a usable answer code
  sends its own short summary, so every block gets exactly one review.
- Once: `reviews.send` with key "<phase id>:<block n>".

The chat reads a stored review with `get_block_review` to talk about it.
"""

import datetime
import logging
import statistics
from typing import TYPE_CHECKING, Any

from .. import history, phases, progression, reviews
from ..ask import ToolError
from ..ports import ModelError
from ..registry import registry
from . import context_notes, training_plan

if TYPE_CHECKING:
    from ..core import Coach

logger = logging.getLogger("fa-coach")

Date = datetime.date
DAY = datetime.timedelta(days=1)
SKILL = "block-review"
KIND = "block"
IGNORED = ("no_working_sets", "other_location")


# --- schedule ------------------------------------------------------------------------


def current_block(coach: "Coach", phase: dict[str, Any]) -> tuple[int, Date]:
    """(number, first day) of the phase's block in progress."""
    rows = coach.db.all("SELECT period_end FROM reviews WHERE kind = ? AND phase_row_id = ? ORDER BY id",
                        (KIND, phase["id"]))
    if not rows:
        return 1, Date.fromisoformat(phase["start_date"])
    return len(rows) + 1, Date.fromisoformat(rows[-1]["period_end"]) + DAY


def block_weeks(coach: "Coach", day: Date) -> int:
    return phases.params_on(coach, day)["reviews"]["block_weeks"]


@registry.job("block-review", order=60)
async def block_review_job(coach: "Coach", now: datetime.datetime) -> None:
    phase = phases.active(coach)
    if phase is None:
        return
    number, start = current_block(coach, phase)
    weeks = block_weeks(coach, now.date())
    end = start + (weeks * 7 - 1) * DAY
    if now.date() <= end:
        return
    await _review(coach, phase, number, start, end, weeks, None, now)


@registry.tool(
    "end_block",
    "Only when the user says their training block is done (\"block done\", \"starting a new block\"): ends the "
    "current block today and restarts the block count from tomorrow (blocks are block_weeks weeks, a setup "
    "value). Code sends the block review right away; tell the user it's out, don't repeat it. reason: why, in "
    "the user's words (e.g. deload week, new program).",
    {
        "type": "object",
        "properties": {"reason": {"type": "string", "minLength": 1, "maxLength": 300}},
        "required": ["reason"],
        "additionalProperties": False,
    },
)
async def end_block(coach: "Coach", args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    phase = phases.active(coach)
    if phase is None:
        raise ToolError("no phase is active: blocks are counted within a phase")
    today = now.date()
    number, start = current_block(coach, phase)
    if start > today:
        raise ToolError(f"block {number - 1} already ended today; block {number} starts tomorrow")
    weeks = block_weeks(coach, today)
    await _review(coach, phase, number, start, today, weeks, args["reason"], now)
    return {"ended_block": number, "start_date": start.isoformat(), "end_date": today.isoformat(),
            "review_sent": True, "next_block_starts": (today + DAY).isoformat(),
            "next_review_on": (today + (weeks * 7 + 1) * DAY).isoformat()}


@registry.tool(
    "get_block_review",
    "A block review that was sent (the latest by default, or block `number` of the current or latest phase): "
    "its text, period and the facts code computed for it. Use it when the user asks about a block review.",
    {
        "type": "object",
        "properties": {"number": {"type": "integer", "minimum": 1}},
        "additionalProperties": False,
    },
)
async def get_block_review(coach: "Coach", args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    phase = phases.latest(coach)
    rows = [] if phase is None else coach.db.all(
        "SELECT id FROM reviews WHERE kind = ? AND phase_row_id = ? ORDER BY id", (KIND, phase["id"]))
    if not rows:
        raise ToolError("no block review was sent in this phase yet")
    number = args.get("number", len(rows))
    if number > len(rows):
        raise ToolError(f"only {len(rows)} block review(s) were sent in this phase")
    review = reviews.get(coach, rows[number - 1]["id"])
    return {"number": number, "period_start": review["period_start"], "period_end": review["period_end"],
            "sent_at": review["created_at"], "text": review["text"], "facts": review["facts"]}


async def _review(coach: "Coach", phase: dict[str, Any], number: int, start: Date, end: Date, weeks: int,
                  reason: str | None, now: datetime.datetime) -> None:
    key = f"{phase['id']}:{number}"
    if reviews.sent(coach, KIND, key):
        return
    data = facts(coach, number, start, end, weeks, reason)
    text = await _model_text(coach, data, now) or fallback_text(data)
    reviews.send(coach, kind=KIND, key=key, phase_row_id=phase["id"], period_start=start.isoformat(),
                 period_end=end.isoformat(), facts=data, text=text, now=now)


async def _model_text(coach: "Coach", data: dict[str, Any], now: datetime.datetime) -> str:
    problems = coach.skills.errors(data, "block_facts")
    if problems:
        logger.error("block facts don't match the schema, code's summary goes out: %s", problems)
        return ""
    try:
        answer = await coach.ask((SKILL,), data, tools=(), output_schema="coach_message", decision=True, now=now)
    except ModelError as exc:
        logger.warning("block review: model error %s", exc)
        return ""
    if answer.data is None or not answer.data["send"]:
        logger.warning("block review not usable: %s", answer.errors or "send false")
        return ""
    return answer.data["text"].strip()


def fallback_text(data: dict[str, Any]) -> str:
    b, t, s = data["block"], data["training"], data["sessions"]
    lines = [f"Block review: block {b['number']} ({_day(b['start_date'])} - {_day(b['end_date'])})"]
    lines.append(f"Lifting sessions: {s['done']} done, {s['planned']} planned.")
    trend = t["strength_trend"]
    if trend["change_pct"] is not None:
        lines.append(f"Strength: {trend['change_pct']:+.1f} % over the block ({trend['direction']}).")
    if t["stalls"]:
        lines.append("Stalled: " + ", ".join(t["stalls"]) + ".")
    if t["deload_signal"]:
        lines.append("Declining: " + ", ".join(t["declining_lifts"]) + ". A deload week may be worth considering.")
    long = [_day(x["date"]) for x in data["volume"]["sessions"] if x["over_limit"]]
    if long:
        lines.append(f"Sessions over {data['volume']['max_sets_per_session']} working sets: " + ", ".join(long) + ".")
    return "\n".join(lines)


def _day(iso: str) -> str:
    d = Date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


# --- facts ---------------------------------------------------------------------------


def facts(coach: "Coach", number: int, start: Date, end: Date, weeks: int, reason: str | None) -> dict[str, Any]:
    """The block's facts (`block_facts.schema.json`)."""
    p = phases.params_on(coach, end)["training"]
    lifts, training = lifts_over(coach, start, end)
    return {
        "schema_version": 1,
        "block": {"number": number, "start_date": start.isoformat(), "end_date": end.isoformat(),
                  "days": (end - start).days + 1, "block_weeks": weeks, "ended_early": reason is not None,
                  "reason": reason},
        "lifts": lifts,
        "training": training,
        "sessions": _sessions(coach, start, end),
        "volume": _volume(coach, start, end, p),
        "context_notes": [{k: n[k] for k in ("applies_from", "applies_to", "tags", "text")}
                          for n in context_notes.between(coach, start, end)],
        "params": {k: p[k] for k in ("stall_sessions", "decline_sessions_for_deload", "deload_min_lifts_declining",
                                     "e1rm_same_band_pct", "volume_note_max_sets_per_session",
                                     "volume_note_max_sets_per_muscle_per_session")},
    }


def lifts_over(coach: "Coach", start: Date, end: Date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(lifts, training) of `block_facts` over start..end; the phase review uses it for a whole phase."""
    p = phases.params_on(coach, end)["training"]
    lifts = [_lift(lift, start, end) for lift in progression.lifts(coach, end).values()]
    lifts = sorted((lift for lift in lifts if lift is not None), key=lambda lift: (not lift["counts"], lift["name"]))
    judged = [lift for lift in lifts if lift["counts"] and not lift["paused"]]
    changes = [lift["_change"] for lift in judged if lift["_change"] is not None]
    for lift in lifts:
        del lift["_change"]
    change = round(statistics.fmean(changes), 1) if changes else None
    band = p["e1rm_same_band_pct"]
    declining = sorted(lift["name"] for lift in judged
                       if lift["decline_streak_at_end"] >= p["decline_sessions_for_deload"])
    return lifts, {
        "strength_trend": {"change_pct": change, "lifts": len(changes),
                           "direction": None if change is None else "rising" if change > band
                           else "falling" if change < -band else "flat"},
        "stalls": sorted(lift["name"] for lift in judged if lift["stalled_at_end"]),
        "declining_lifts": declining,
        "deload_signal": len(declining) >= p["deload_min_lifts_declining"],
        "prs": sorted(({"name": lift["name"], "date": d} for lift in lifts for d in lift["prs"]),
                      key=lambda pr: (pr["date"], pr["name"])),
    }


def _lift(lift: dict[str, Any], start: Date, end: Date) -> dict[str, Any] | None:
    """One exercise trained in the block, or None."""
    entries = [e for e in lift["entries"] if start.isoformat() <= e["date"] <= end.isoformat()]
    if not entries:
        return None
    usable = [e for e in entries if e["top"] is not None and e["not_judged_reason"] not in IGNORED]
    resets = [n for n, e in enumerate(usable) if e["not_judged_reason"] == "baseline_reset"]
    since_reset = usable[resets[-1]:] if resets else usable
    change = None
    if len(since_reset) >= 2 and since_reset[0]["top"]["e1rm_kg"]:
        change = (since_reset[-1]["top"]["e1rm_kg"] / since_reset[0]["top"]["e1rm_kg"] - 1) * 100
    last = usable[-1] if usable else None
    paused = lift["paused"]
    flags = lift["counts"] and not paused
    counted = [e for e in entries if not e["paused"] and e["status"] in progression.JUDGED]
    return {
        "exercise_id": lift["exercise_id"],
        "name": lift["name"],
        "counts": lift["counts"],
        "paused": paused,
        "sessions": len(entries),
        "first": _point(usable[0]) if usable else None,
        "last": _point(last) if last else None,
        "change_pct": None if change is None else round(change, 1),
        "statuses": {s: sum(1 for e in counted if e["status"] == s) for s in progression.JUDGED},
        "prs": [e["date"] for e in entries if e["is_pr"] and not e["paused"]],
        "baseline_resets": [e["date"] for e in usable if e["not_judged_reason"] == "baseline_reset"],
        "no_progress_streak_at_end": last["no_progress_streak"] if last and not paused else 0,
        "decline_streak_at_end": last["decline_streak"] if last and not paused else 0,
        "stalled_at_end": bool(flags and last and last["stalled"]),
        "_change": change,
    }


def _point(entry: dict[str, Any]) -> dict[str, Any]:
    top = entry["top"]
    return {"date": entry["date"],
            "top_set": {k: top[k] for k in ("load_kg", "reps", "effective_load_kg", "e1rm_kg")}}


def _sessions(coach: "Coach", start: Date, end: Date) -> dict[str, int]:
    """Hevy lifting sessions done; the plan's non-optional lifting sessions; those reported skipped."""
    planned = skipped = 0
    day = start
    while day <= end:
        plan = training_plan.plan_for(coach, day)
        day_sessions = plan["days"][training_plan.WEEKDAYS[day.weekday()]] if plan else []
        planned += sum(1 for s in day_sessions if s["type"] == "lift" and not s["optional"])
        skipped += sum(1 for s in training_plan.statuses(coach, day) if s["status"] == "skipped" and s["type"] == "lift")
        day += DAY
    done = len(history.sessions(coach.db, start.isoformat(), end.isoformat()))
    return {"done": done, "planned": planned, "skipped": skipped}


def _volume(coach: "Coach", start: Date, end: Date, p: dict[str, Any]) -> dict[str, Any]:
    limit = p["volume_note_max_sets_per_session"]
    out = []
    for s in history.sessions(coach.db, start.isoformat(), end.isoformat()):
        exercises: dict[str, int] = {}
        for ex in s["exercises"]:
            name = ex["title"] or ex["exercise_id"] or "?"
            exercises[name] = exercises.get(name, 0) + sum(1 for st in ex["sets"] if st["type"] != "warmup")
        total = sum(exercises.values())
        out.append({"date": s["date"], "name": s["name"], "working_sets": total, "over_limit": total > limit,
                    "exercises": [{"name": n, "working_sets": c} for n, c in exercises.items()]})
    return {"max_sets_per_session": limit,
            "max_sets_per_muscle_per_session": p["volume_note_max_sets_per_muscle_per_session"],
            "sessions": out}
