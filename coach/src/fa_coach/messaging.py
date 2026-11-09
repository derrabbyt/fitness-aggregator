"""Unprompted messages: the daily message limit and items deferred to the
weekly report (tables from migrations/11_messaging.sql). Shared by every
feature that messages the user on its own (jobs), as opposed to replies in
the chat.

Daily message limit (`messaging.max_unprompted_messages_per_day`, a setup
value; no limit while it is unset):
- `send(coach, text, now, kind=..., buttons=..., ref=..., exempt=False)`:
  sends through `coach.say` and counts it, unless today's limit is reached,
  then sends nothing and returns False. `exempt=True` always sends and does
  not count (the "was this a reset?" question, story 81, and the weekly
  check-in, the one weekly message the user expects).
- `sent_today(coach, now)`: counted messages sent today (local date of `now`).
- `limit(coach)`, `can_send(coach, now)`.

Deferred items (non-urgent observations held back for the weekly report):
- `defer(coach, day, text, source, now)` stores one.
- `deferred(coach, start, end)`: items whose day falls in [start, end]
  (dates inclusive), oldest first; the weekly report reads its week's here.
"""

import datetime
from typing import TYPE_CHECKING, Any

from . import phases
from .ports import Buttons

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date


def limit(coach: "Coach") -> int | None:
    """Today's limit on unprompted messages; None = no limit set."""
    return phases.params(coach)["messaging"].get("max_unprompted_messages_per_day")


def sent_today(coach: "Coach", now: datetime.datetime) -> int:
    return coach.db.value(
        "SELECT COUNT(*) FROM unprompted_messages WHERE day = ? AND exempt = 0", (now.date().isoformat(),)
    )


def can_send(coach: "Coach", now: datetime.datetime) -> bool:
    cap = limit(coach)
    return cap is None or sent_today(coach, now) < cap


def send(
    coach: "Coach",
    text: str,
    now: datetime.datetime,
    *,
    kind: str,
    buttons: Buttons = (),
    ref: str | None = None,
    exempt: bool = False,
) -> bool:
    """Send one unprompted message if today's limit allows it (always when
    `exempt`). Returns whether it was sent. `kind` names the sender, e.g.
    "evening-reminder"."""
    with coach.db.transaction():
        if not exempt and not can_send(coach, now):
            return False
        coach.db.execute(
            "INSERT INTO unprompted_messages (day, kind, exempt, at) VALUES (?, ?, ?, ?)",
            (now.date().isoformat(), kind, int(exempt), now.isoformat(timespec="seconds")),
        )
    coach.say(text, buttons, ref)
    return True


def defer(coach: "Coach", day: Date, text: str, source: str, now: datetime.datetime) -> None:
    """Hold `text` (about `day`) back for the weekly report."""
    coach.db.execute(
        "INSERT INTO deferred_items (day, source, text, created_at) VALUES (?, ?, ?, ?)",
        (day.isoformat(), source, text, now.isoformat(timespec="seconds")),
    )


def deferred(coach: "Coach", start: Date, end: Date) -> list[dict[str, Any]]:
    """Deferred items about days from `start` to `end` (inclusive): {day, source, text}."""
    rows = coach.db.all(
        "SELECT day, source, text FROM deferred_items WHERE day BETWEEN ? AND ? ORDER BY day, id",
        (start.isoformat(), end.isoformat()),
    )
    return [dict(row) for row in rows]
