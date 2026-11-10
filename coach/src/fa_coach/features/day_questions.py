"""Questions about a day whose intake looks wrong, and the user's confirmations
(ticket 20). What counts as suspected is daycheck.py; the coach never writes
to the MFP diary, confirmations live in the coach.

- A suspected partial day gets **That's all I ate** / **I'll log the rest**, an
  implausibly high one **Real** / **Typo, I'll fix it in MFP**. "That's all I
  ate" and "Real" store a confirmation at the day's current kcal
  (`daycheck.confirm`); the other answers store nothing.
- Each question is asked once per day, kind and kcal: if the day's kcal change
  later and it is still suspected, it is asked again.
- Today is asked at the evening job (`ask_today`, instead of the recap). Days
  found later, by the `day-checks` syncer (the last 7 days of the active
  phase, today left out), wait for the next unprompted message and go out
  right after it (`messaging.after_send`).
- Questions are unprompted messages: they count toward the daily limit, and a
  question held back by it waits for the next message.
- Chat tool `confirm_day(date, kind)` for "Tuesday was complete" / "yesterday's
  4,000 was real".
"""

import datetime
import logging
from typing import Any

from .. import daycheck, messaging, phases
from ..ask import ToolError
from ..ports import Button
from ..registry import registry

logger = logging.getLogger("fa-coach")

Date = datetime.date
DAY = datetime.timedelta(days=1)
KIND = "day-question"  # messaging kind
LOOKBACK_DAYS = 7

ANSWERS = {  # button action: (question kind, answer, confirmation kind or None)
    "day_complete": ("partial", "complete", "complete"),
    "day_log_rest": ("partial", "log_rest", None),
    "day_real": ("implausible", "real", "real"),
    "day_typo": ("implausible", "typo", None),
}


def suspicion(status: dict[str, Any] | None) -> str | None:
    """The question a day's status calls for: 'partial', 'implausible' or None."""
    if status is None or status["confirmed"]:
        return None
    if status["partial_suspected"]:
        return "partial"
    if status["implausible"]:
        return "implausible"
    return None


def find(coach, start: Date, end: Date, now: datetime.datetime) -> None:
    """Queue a question for each suspected day from `start` to `end` not asked
    yet at its current kcal."""
    for date, status in daycheck.statuses(coach, start, end, phases.params(coach)).items():
        kind = suspicion(status)
        if kind is not None:
            coach.db.execute(
                "INSERT OR IGNORE INTO day_questions (date, kind, kcal, status, found_at) VALUES (?, ?, ?, 'pending', ?)",
                (date, kind, status["kcal"], now.isoformat(timespec="seconds")),
            )


def flush(coach, now: datetime.datetime) -> None:
    """Send the pending questions, oldest day first, while the daily limit
    allows. One whose day is no longer suspected at those kcal is dropped."""
    p = phases.params(coach)
    for row in coach.db.all("SELECT * FROM day_questions WHERE status = 'pending' ORDER BY date, id"):
        status = daycheck.status(coach, Date.fromisoformat(row["date"]), p)
        if suspicion(status) != row["kind"] or round(status["kcal"]) != round(row["kcal"]):
            coach.db.execute("UPDATE day_questions SET status = 'dropped' WHERE id = ?", (row["id"],))
            continue
        if not messaging.send(coach, _text(row, status, p, now), now, kind=KIND, buttons=_buttons(row),
                              ref=_ref(row["id"])):
            return
        coach.db.execute("UPDATE day_questions SET status = 'asked', asked_at = ? WHERE id = ?",
                         (now.isoformat(timespec="seconds"), row["id"]))


def ask_today(coach, now: datetime.datetime) -> bool:
    """The evening: ask about today if it is suspected (and send whatever else
    is pending). True if today is in question, so the recap waits."""
    today = now.date()
    if suspicion(daycheck.status(coach, today, phases.params(coach))) is None:
        return False
    find(coach, today, today, now)
    flush(coach, now)
    return True


def _after_send(coach, kind: str, now: datetime.datetime) -> None:
    if kind != KIND:
        flush(coach, now)


messaging.after_send.append(_after_send)


@registry.syncer("day-checks", order=50)  # after the MFP sync
async def check_recent_days(coach, now: datetime.datetime) -> None:
    phase = phases.active(coach)
    if phase is None:
        return
    end = now.date() - DAY  # today is still being logged
    start = max(Date.fromisoformat(phase["start_date"]), end - (LOOKBACK_DAYS - 1) * DAY)
    if start <= end:
        find(coach, start, end, now)


# --- text and buttons ---------------------------------------------------------------


def _ref(question_id: int) -> str:
    return f"day-question:{question_id}"


def _label(day: Date, now: datetime.datetime) -> str:
    if day == now.date():
        return "Today"
    if day == now.date() - DAY:
        return "Yesterday"
    return f"{day:%a} {day.day} {day:%b}"


def _text(row, status: dict[str, Any], p: dict[str, Any], now: datetime.datetime) -> str:
    day = _label(Date.fromisoformat(row["date"]), now)
    kcal = round(status["kcal"])
    if row["kind"] == "partial":
        return (f"{day}: {kcal:,} kcal in MyFitnessPal, under half your usual {round(status['reference_kcal']):,}. "
                "Is that all you ate? Until you confirm, the day doesn't count toward your week.")
    factor = p["data"]["implausible_intake_factor"]
    return (f"{day}: {kcal:,} kcal in MyFitnessPal, more than {factor:g}× the day's target "
            f"({round(status['target_kcal']):,}). Real, or a typo in MyFitnessPal?")


def _buttons(row) -> tuple[tuple[Button, ...], ...]:
    rid = str(row["id"])
    if row["kind"] == "partial":
        return ((Button("That's all I ate", "day_complete", rid), Button("I'll log the rest", "day_log_rest", rid)),)
    return ((Button("Real", "day_real", rid), Button("Typo, I'll fix it in MFP", "day_typo", rid)),)


# --- buttons -----------------------------------------------------------------------


def _register(action: str) -> None:
    @registry.button(action)
    async def tapped(coach, ref_id: str, now: datetime.datetime) -> None:
        await _answer(coach, action, ref_id, now)


for _action in ANSWERS:
    _register(_action)


async def _answer(coach, action: str, ref_id: str, now: datetime.datetime) -> None:
    question = coach.db.one("SELECT * FROM day_questions WHERE id = ?", (ref_id,)) if ref_id.isdigit() else None
    kind, answer, confirmation = ANSWERS[action]
    if question is None or question["kind"] != kind:
        logger.warning("tap on unknown day question %r", ref_id)
        return
    day = Date.fromisoformat(question["date"])
    label = _label(day, now)
    kcal = round(question["kcal"])
    with coach.db.transaction():
        claimed = coach.db.execute(
            "UPDATE day_questions SET status = 'answered', answer = ?, answered_at = ? WHERE id = ? AND status = 'asked'",
            (answer, now.isoformat(timespec="seconds"), question["id"]),
        ).rowcount == 1
        if not claimed:
            return
        current = daycheck.status(coach, day, phases.params(coach))
        changed = current is None or round(current["kcal"]) != kcal
        if confirmation and not changed:
            daycheck.confirm(coach, day, confirmation, "button", now)
    if confirmation and changed:
        text = f"{label} changed in MyFitnessPal since I asked, so I'll check it again."
    elif answer == "complete":
        text = f"✓ {label} counts as complete at {kcal:,} kcal."
    elif answer == "real":
        text = f"✓ {label}'s {kcal:,} kcal count as real."
    elif answer == "log_rest":
        text = f"OK: {label} ({kcal:,} kcal) doesn't count until the rest is in MyFitnessPal."
    else:
        text = f"OK: {label}'s {kcal:,} kcal stay as they are until you fix them in MyFitnessPal."
    coach.edit(_ref(question["id"]), text)


# --- chat tool ---------------------------------------------------------------------


@registry.tool(
    "confirm_day",
    "Confirm a day's intake as synced from MyFitnessPal when the user says so: kind 'complete' when the "
    "user says a low day is all they ate (e.g. \"Tuesday was complete\"), 'real' when a high day is not a "
    "typo (e.g. \"yesterday's 4,000 was real\"). The day then counts normally until its kcal change in MFP. "
    "Never for a day the user still means to log or fix.",
    {
        "type": "object",
        "required": ["date", "kind"],
        "additionalProperties": False,
        "properties": {
            "date": {"type": "string", "format": "date", "description": "The day, YYYY-MM-DD (today or earlier)."},
            "kind": {"enum": ["complete", "real"]},
        },
    },
)
async def confirm_day(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    try:
        day = Date.fromisoformat(args["date"])
    except ValueError as exc:
        raise ToolError(f"not a date: {args['date']!r}") from exc
    if day > now.date():
        raise ToolError("that day hasn't happened yet")
    kcal = daycheck.confirm(coach, day, args["kind"], "chat", now)
    if kcal is None:
        raise ToolError(f"no food is logged in MyFitnessPal for {day.isoformat()} (as of the last sync)")
    return {"date": day.isoformat(), "kind": args["kind"], "kcal": round(kcal),
            "note": "Counts normally now; if the day's kcal change in MFP, it is checked again."}
