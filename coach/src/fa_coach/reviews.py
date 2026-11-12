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
- `get(coach, review_id)`, `sent_between(coach, start, end)`: stored reviews
  as dicts {id, kind, phase_row_id, period_start, period_end, facts, text,
  created_at}; `sent_between` takes those sent on local dates start..end
  (inclusive), oldest first.
"""

import datetime
import json
from typing import TYPE_CHECKING, Any

from . import messaging
from .ports import Buttons

if TYPE_CHECKING:
    from .core import Coach

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
