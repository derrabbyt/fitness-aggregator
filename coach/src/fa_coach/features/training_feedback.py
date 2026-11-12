"""Training feedback after lifting (ticket 12; spec stories 69, 80, 81).

The `training-feedback` job looks at every Hevy session dated within the
last `FRESH_DAYS` days and first synced after a cut-off (`_since`), once per
session (`once`). The cut-off is the active phase's start; without an
active phase it is the latest of: the moment the latest phase ended, the
latest erase of a phase, and the job's first run without any phase (so no
backlog floods in after a deploy or an erase):

- Code judges it (progression.session). A session where no exercise was
  judged or started a baseline (after a break, another gym, paused, no
  working sets) gets nothing, not even a model call.
- Otherwise code builds daily facts (kind training) and the training-feedback
  skill returns a coach message. Its `deferred_to_weekly` items are stored for
  the weekly report.
- Code decides whether anything goes out: only for a PR, a new stall (the
  first session of a stall on a counting exercise) or a possible reset. A
  message for anything else is held back for the weekly report instead.
- A possible reset: code appends the "was this a reset?" question and the
  `mark_reset` / `not_a_reset` buttons (one row per exercise) and sends the
  message exempt from the daily limit (urgent). Without a usable model
  answer, the question goes out on its own. A tap claims the question once:
  `mark_reset` starts a new baseline from that session; either tap removes
  that exercise's buttons and adds the outcome to the message.
- Other messages count toward the daily limit; past it they're deferred.

Model tools for the chat: `mark_baseline_reset` (technique / ROM change,
exercise swap) and `set_exercise_paused` (injury: the skills offer a pause,
the user decides).
"""

import datetime
import logging
from typing import TYPE_CHECKING, Any

from .. import messaging, phases, progression
from ..ask import ToolError
from ..ports import Button, Buttons, ModelError
from ..registry import registry
from . import context_notes, phase_end

if TYPE_CHECKING:
    from ..core import Coach

logger = logging.getLogger("fa-coach")

Date = datetime.date
DAY = datetime.timedelta(days=1)
SKILL = "training-feedback"
FRESH_DAYS = 2  # sessions dated today or up to this many days back get feedback
RESET_REASONS = ("technique_change", "rom_change", "exercise_swap", "other")


# --- the job -----------------------------------------------------------------------


@registry.job("training-feedback", order=35)  # after new-exercises classified any new lift
async def training_feedback(coach: "Coach", now: datetime.datetime) -> None:
    phase = phases.active(coach)
    for session_id in _new_sessions(coach, phase, now):
        if coach.db.once(f"training-feedback:{session_id}", now):
            await _feedback(coach, phase, session_id, now)


NO_PHASE_SINCE = "training-feedback-without-phase-since"  # once key: the job's first run without any phase


def _since(coach: "Coach", phase: dict[str, Any] | None, now: datetime.datetime) -> tuple[Date, datetime.datetime]:
    """(first session date, first-seen cut-off) for feedback."""
    fresh = now.date() - FRESH_DAYS * DAY
    if phase is not None:
        return max(Date.fromisoformat(phase["start_date"]), fresh), datetime.datetime.fromisoformat(phase["started_at"])
    ended = coach.db.value("SELECT MAX(ended_at) FROM phases")
    marks = [datetime.datetime.fromisoformat(ended) if ended else None, phase_end.last_erase_at(coach)]
    if not any(marks):  # never a phase: from the first run on
        coach.db.once(NO_PHASE_SINCE, now)
    # An older first run never moves the cut-off back before an end or an erase.
    return fresh, max(m for m in (*marks, coach.db.once_at(NO_PHASE_SINCE)) if m is not None)


def _new_sessions(coach: "Coach", phase: dict[str, Any] | None, now: datetime.datetime) -> list[str]:
    since, cutoff = _since(coach, phase, now)
    rows = coach.db.all("SELECT id, first_seen_at FROM lift_sessions WHERE date BETWEEN ? AND ? ORDER BY start_at, id",
                        (since.isoformat(), now.date().isoformat()))
    return [r["id"] for r in rows if datetime.datetime.fromisoformat(r["first_seen_at"]) >= cutoff]


def _noteworthy(ex: dict[str, Any]) -> bool:
    return ex["is_pr"] or ex["new_stall"] or ex["possible_reset"]


async def _feedback(coach: "Coach", phase: dict[str, Any] | None, session_id: str, now: datetime.datetime) -> None:
    judged = progression.session(coach, session_id)
    if judged is None or not any(e["status"] in (*progression.JUDGED, "new_baseline") for e in judged["exercises"]):
        return
    day = Date.fromisoformat(judged["date"])
    resets = [e for e in judged["exercises"] if e["possible_reset"]]
    text = await _model_text(coach, phase, judged, now)
    if not any(_noteworthy(e) for e in judged["exercises"]):
        if text:
            messaging.defer(coach, day, text, SKILL, now)
        return
    if not resets:
        if text and not messaging.send(coach, text, now, kind=SKILL, ref=_ref(session_id)):
            messaging.defer(coach, day, text, SKILL, now)
        return
    with coach.db.transaction():
        for ex in resets:
            coach.db.execute(
                "INSERT OR IGNORE INTO reset_questions (session_id, exercise_id, name, session_date, drop_pct,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, ex["exercise_id"], ex["name"], judged["date"], ex["drop_pct_vs_best_recent"],
                 now.isoformat(timespec="seconds")),
            )
    full = "\n\n".join(part for part in (text, _question(resets)) if part)
    coach.db.execute("INSERT OR REPLACE INTO training_feedback (session_id, ref, text, sent_at) VALUES (?, ?, ?, ?)",
                     (session_id, _ref(session_id), full, now.isoformat(timespec="seconds")))
    messaging.send(coach, full, now, kind="reset-question", buttons=_buttons(coach, session_id),
                   ref=_ref(session_id), exempt=True)


async def _model_text(coach: "Coach", phase: dict[str, Any] | None, judged: dict[str, Any], now: datetime.datetime) -> str:
    """The skill's message text ('' when it sends nothing); stores its deferred items."""
    facts = daily_facts(coach, phase, judged, now)
    problems = coach.skills.errors(facts, "daily_facts")
    if problems:
        logger.error("training facts don't match the schema, no feedback text: %s", problems)
        return ""
    try:
        answer = await coach.ask((SKILL,), facts, tools=(), output_schema="coach_message", now=now)
    except ModelError as exc:
        logger.warning("training feedback: model error %s", exc)
        return ""
    if answer.data is None:
        logger.warning("training feedback not usable: %s", answer.errors)
        return ""
    day = Date.fromisoformat(judged["date"])
    for item in answer.data["deferred_to_weekly"]:
        messaging.defer(coach, day, item, SKILL, now)
    return answer.data["text"].strip() if answer.data["send"] else ""


def daily_facts(coach: "Coach", phase: dict[str, Any] | None, judged: dict[str, Any],
                now: datetime.datetime) -> dict[str, Any]:
    """Daily facts (kind training) for one judged session, per
    daily_facts.schema.json (phase_id and phase_week null without an active phase)."""
    day = Date.fromisoformat(judged["date"])
    return {
        "schema_version": 1,
        "date": judged["date"],
        "kind": "training",
        "phase_id": phase["phase_id"] if phase else None,
        "phase_week": phases.phase_week(phase, day) if phase else None,
        "in_glycogen_window": phases.in_glycogen_window(coach, day),
        "messages_sent_today": messaging.sent_today(coach, now),
        "context_notes_today": context_notes.between(coach, day, day),
        "session": judged,
        "params": phases.params(coach),
    }


def _ref(session_id: str) -> str:
    return f"training:{session_id}"


def _question(resets: list[dict[str, Any]]) -> str:
    lines = [f"{ex['name']}: {ex['drop_pct_vs_best_recent']:g} % below your best recent session." for ex in resets]
    lines.append("Was that a technique or range-of-motion change, or an exercise swap? A reset starts a new "
                 "baseline from this session.")
    return "\n".join(lines)


def _buttons(coach, session_id: str) -> Buttons:
    rows = coach.db.all("SELECT * FROM reset_questions WHERE session_id = ? ORDER BY id", (session_id,))
    several = len(rows) > 1
    return tuple(
        (Button(f"Reset: {r['name']}"[:32] if several else "Mark reset", "mark_reset", str(r["id"])),
         Button("Not a reset", "not_a_reset", str(r["id"])))
        for r in rows if r["status"] == "open"
    )


# --- buttons -----------------------------------------------------------------------


@registry.button("mark_reset")
async def mark_reset_tapped(coach, ref_id: str, now: datetime.datetime) -> None:
    await _answer(coach, ref_id, "reset", now)


@registry.button("not_a_reset")
async def not_a_reset_tapped(coach, ref_id: str, now: datetime.datetime) -> None:
    await _answer(coach, ref_id, "not_reset", now)


async def _answer(coach, ref_id: str, status: str, now: datetime.datetime) -> None:
    question = coach.db.one("SELECT * FROM reset_questions WHERE id = ?", (ref_id,)) if ref_id.isdigit() else None
    if question is None:
        logger.warning("tap on unknown reset question %r", ref_id)
        return
    with coach.db.transaction():
        claimed = coach.db.execute(
            "UPDATE reset_questions SET status = ?, answered_at = ? WHERE id = ? AND status = 'open'",
            (status, now.isoformat(timespec="seconds"), question["id"]),
        ).rowcount == 1
        if claimed and status == "reset":
            progression.mark_reset(coach, question["exercise_id"], Date.fromisoformat(question["session_date"]), now,
                                   session_id=question["session_id"], reason="big drop: marked as a reset")
    session_id = question["session_id"]
    message = coach.db.one("SELECT * FROM training_feedback WHERE session_id = ?", (session_id,))
    if message is None:
        return
    answered = coach.db.all("SELECT * FROM reset_questions WHERE session_id = ? AND status != 'open' ORDER BY id",
                            (session_id,))
    outcomes = [f"✓ {r['name']}: new baseline from this session." if r["status"] == "reset"
                else f"✓ {r['name']}: not a reset, compared as usual." for r in answered]
    coach.edit(message["ref"], "\n\n".join([message["text"], "\n".join(outcomes)]), _buttons(coach, session_id))


# --- chat tools --------------------------------------------------------------------


def _known(coach, exercise_id: str) -> dict[str, Any]:
    known = progression.known_exercise(coach, exercise_id)
    if known is None:
        raise ToolError(f"exercise_id {exercise_id!r} is not in the synced Hevy history; see get_tracked_exercises")
    return known


@registry.tool(
    "mark_baseline_reset",
    "Start a new baseline for one exercise after a technique change, range-of-motion change or exercise swap the "
    "user told you about: its first session on or after `date` (default today) starts a new history (not judged, "
    "no PR); older sessions are no longer compared. Use the exercise id from get_tracked_exercises.",
    {
        "type": "object",
        "properties": {
            "exercise_id": {"type": "string"},
            "date": {"type": "string", "format": "date", "description": "From this day on (default today)."},
            "reason": {"enum": list(RESET_REASONS)},
        },
        "required": ["exercise_id", "reason"],
        "additionalProperties": False,
    },
)
async def mark_baseline_reset(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    known = _known(coach, args["exercise_id"])
    try:
        day = Date.fromisoformat(args["date"]) if "date" in args else now.date()
    except ValueError:
        raise ToolError("date must be YYYY-MM-DD") from None
    progression.mark_reset(coach, args["exercise_id"], day, now, reason=args["reason"])
    first = coach.db.value(
        "SELECT MIN(s.date) FROM lift_sessions s JOIN lift_exercises e ON e.session_id = s.id"
        " WHERE e.exercise_id = ? AND s.date >= ?", (args["exercise_id"], day.isoformat()))
    return {"exercise_id": args["exercise_id"], "name": known["title"], "from_date": day.isoformat(),
            "reason": args["reason"], "new_baseline_session_date": first,
            "say": f"New baseline for {known['title']} from "
                   f"{'the session on ' + first if first else 'the next session'}."}


@registry.tool(
    "set_exercise_paused",
    "Pause (or resume) judging one exercise, e.g. while the user modifies it around an injury: a paused exercise is "
    "still logged but not judged, gives no PR, stall or reset question and doesn't count for progression. Only "
    "after the user agreed to the pause; never pause on your own because of an injury note.",
    {
        "type": "object",
        "properties": {
            "exercise_id": {"type": "string"},
            "paused": {"type": "boolean"},
            "reason": {"type": "string", "description": "A few words, e.g. 'left shoulder'."},
        },
        "required": ["exercise_id", "paused"],
        "additionalProperties": False,
    },
)
async def set_exercise_paused(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    known = _known(coach, args["exercise_id"])
    progression.set_paused(coach, args["exercise_id"], args["paused"], args.get("reason"), now)
    return {"exercise_id": args["exercise_id"], "name": known["title"], "paused": args["paused"],
            "reason": args.get("reason")}
