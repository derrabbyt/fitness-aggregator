"""Deferred items: observations held back from daily messages (evening recap,
training feedback) for the weekly report (table from migrations/07_weekly.sql).

- `add(coach, day, text, source, now)`: hold one back (e.g. a coach_message's
  `deferred_to_weekly` entries).
- `pending(coach, through)`: items not yet reported, dated up to `through`.
- `mark_reported(coach, ids, iso_week)`: the weekly report carried them.
"""

import datetime
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import Coach


def add(coach: "Coach", day: datetime.date, text: str, source: str, now: datetime.datetime) -> None:
    coach.db.execute(
        "INSERT INTO deferred_items (date, source, text, created_at) VALUES (?, ?, ?, ?)",
        (day.isoformat(), source, text, now.isoformat(timespec="seconds")),
    )


def pending(coach: "Coach", through: datetime.date) -> list[dict[str, Any]]:
    """Unreported items dated on or before `through`, oldest first: {id, date, source, text}."""
    rows = coach.db.all(
        "SELECT id, date, source, text FROM deferred_items WHERE reported_week IS NULL AND date <= ?"
        " ORDER BY date, id",
        (through.isoformat(),),
    )
    return [dict(r) for r in rows]


def mark_reported(coach: "Coach", ids: Iterable[int], iso_week: str) -> None:
    for item_id in ids:
        coach.db.execute("UPDATE deferred_items SET reported_week = ? WHERE id = ?", (iso_week, item_id))
