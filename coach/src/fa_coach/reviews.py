"""Reviews: the block, phase and photo reviews (coach-reviews tickets 02-04)
store and send through here; the Week page lists them (features/web_week.py).
Table `reviews` (migrations/25_reviews.sql).

- `sent(coach, kind, key)`: whether the review for `key` already went out.
  Check it before asking the model, so a review isn't written twice.
- `send(coach, kind=, key=, phase_row_id=, period_start=, period_end=,
  facts=, text=, now=, buttons=(), ref=None)`: stores the review and sends
  `text` in Telegram, once per (kind, key); returns the new review's id, or
  None when that key was already sent (nothing is sent then). Reviews are
  messages the user expects, like the weekly check-in, so they don't count
  toward the daily message limit (`messaging.send(..., exempt=True)`, kind
  "<kind>-review"). `key` is the caller's: unique within the kind and stable
  across retries (e.g. block: "<phase id>:<block n>", phase:
  "<phase id>:week-10" / "<phase id>:end", photo: the photo set's date).
- `model_text(coach, skill, facts, facts_schema, now, phase=None, images=())`:
  the review's text from its skill (COACH_DECISION_MODEL, no tools, output
  `coach_message`); "" when the facts don't match `facts_schema`, the model
  fails or doesn't send, so the caller sends its own summary instead.
- `get(coach, review_id)`, `sent_between(coach, start, end)`: stored reviews
  as dicts {id, kind, phase_row_id, period_start, period_end, facts, text,
  created_at}; `sent_between` takes those sent on local dates start..end
  (inclusive), oldest first.
- `for_phase(coach, phase_row_id, kind)`: a phase's reviews of one kind,
  oldest first; `count(coach, phase_row_id, kind)` how many.
- `ids_for_phase(coach, phase_row_id)` and `phase_rows(phase_row_id)` (a
  `FROM` clause and its params): all of a phase's reviews, for the undo of a
  phase (features/phase_end.py erases them).
"""

import datetime
import json
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from . import messaging
from .ports import Buttons, Image, ModelError

if TYPE_CHECKING:
    from .core import Coach

logger = logging.getLogger("fa-coach")
Date = datetime.date
KINDS = ("block", "phase", "photo")
TITLES = {"block": "Block review", "phase": "Phase review", "photo": "Photo review"}


def _key(kind: str, key: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"{kind!r} is not a review kind ({', '.join(KINDS)}).")
    return f"{kind}:{key}"


def sent(coach: "Coach", kind: str, key: str) -> bool:
    return bool(coach.db.value("SELECT COUNT(*) FROM reviews WHERE key = ?", (_key(kind, key),)))


def send(
    coach: "Coach",
    *,
    kind: str,
    key: str,
    phase_row_id: str | None,
    period_start: str,
    period_end: str,
    facts: dict[str, Any],
    text: str,
    now: datetime.datetime,
    buttons: Buttons = (),
    ref: str | None = None,
) -> int | None:
    cur = coach.db.execute(
        "INSERT OR IGNORE INTO reviews (key, kind, phase_row_id, period_start, period_end, facts, text, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (_key(kind, key), kind, phase_row_id, period_start, period_end, json.dumps(facts), text,
         now.isoformat(timespec="seconds")),
    )
    if cur.rowcount != 1:
        return None
    messaging.send(coach, text, now, kind=f"{kind}-review", buttons=buttons, ref=ref, exempt=True)
    return cur.lastrowid


async def model_text(coach: "Coach", skill: str, facts: dict[str, Any], facts_schema: str, now: datetime.datetime,
                     *, phase: str | None = None, images: Sequence[Image] = ()) -> str:
    problems = coach.skills.errors(facts, facts_schema)
    if problems:
        logger.error("%s: the facts don't match %s, code's summary goes out: %s", skill, facts_schema, problems)
        return ""
    try:
        answer = await coach.ask((skill,), facts, tools=(), output_schema="coach_message", decision=True,
                                 phase=phase, images=images, now=now)
    except ModelError as exc:
        logger.warning("%s: model error %s", skill, exc)
        return ""
    if answer.data is None or not answer.data["send"]:
        logger.warning("%s not usable: %s", skill, answer.errors or "send false")
        return ""
    return answer.data["text"].strip()


def _row(row) -> dict[str, Any]:
    return {"id": row["id"], "kind": row["kind"], "phase_row_id": row["phase_row_id"],
            "period_start": row["period_start"], "period_end": row["period_end"], "facts": json.loads(row["facts"]),
            "text": row["text"], "created_at": row["created_at"]}


def get(coach: "Coach", review_id: int) -> dict[str, Any] | None:
    row = coach.db.one("SELECT * FROM reviews WHERE id = ?", (review_id,))
    return _row(row) if row else None


def sent_between(coach: "Coach", start: Date, end: Date) -> list[dict[str, Any]]:
    rows = coach.db.all("SELECT * FROM reviews WHERE substr(created_at, 1, 10) BETWEEN ? AND ?"
                        " ORDER BY created_at, id", (start.isoformat(), end.isoformat()))
    return [_row(r) for r in rows]


def for_phase(coach: "Coach", phase_row_id: str, kind: str) -> list[dict[str, Any]]:
    _key(kind, "")
    rows = coach.db.all("SELECT * FROM reviews WHERE kind = ? AND phase_row_id = ? ORDER BY id", (kind, phase_row_id))
    return [_row(r) for r in rows]


def count(coach: "Coach", phase_row_id: str, kind: str) -> int:
    _key(kind, "")
    return coach.db.value("SELECT COUNT(*) FROM reviews WHERE kind = ? AND phase_row_id = ?", (kind, phase_row_id))


def phase_rows(phase_row_id: str) -> tuple[str, tuple]:
    return "reviews WHERE phase_row_id = ?", (phase_row_id,)


def ids_for_phase(coach: "Coach", phase_row_id: str) -> list[int]:
    return [r["id"] for r in coach.db.all("SELECT id FROM reviews WHERE phase_row_id = ?", (phase_row_id,))]
