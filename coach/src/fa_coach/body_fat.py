"""Body-fat estimates (table `body_fat_estimates`, migrations/25_reviews.sql):
the photo review's (source "model", coach-reviews ticket 04) and the user's
own (source "user", chat tool `record_body_fat`). For a date the user's
latest estimate wins over any model estimate; otherwise the latest model one.

- `problem(pct)`: why `pct` can't be stored, or None (range `PCT`).
- `add(coach, day, pct, source, now, review_id=None)`: stores one; raises
  ValueError for a bad pct or source (check `problem` first to answer the user).
- `estimates(coach)`: the winning estimate per date, newest first:
  [{date, pct, source, model_pct}]; `model_pct` is the latest model estimate
  a user's estimate overrides (else None).
- `on(coach, day)`: that date's winning estimate, or None.
- `latest(coach, day)`: the newest winning estimate on or before `day`, or None.
- `detach(coach, review_ids)`: the estimates of those reviews lose their link
  (an undone phase's reviews are erased; the estimates are about the person).
"""

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import Coach

PCT = (3, 50)  # as photo_review.schema.json's bf_estimate
SOURCES = ("model", "user")


def problem(pct: Any) -> str | None:
    if isinstance(pct, bool) or not isinstance(pct, int | float):
        return f"{pct!r} is not a number."
    if not PCT[0] <= pct <= PCT[1]:
        return f"{pct:g} % doesn't look like a body-fat estimate ({PCT[0]}–{PCT[1]} %)."
    return None


def add(coach: "Coach", day: datetime.date | str, pct: float, source: str, now: datetime.datetime,
        review_id: int | None = None) -> int:
    if source not in SOURCES:
        raise ValueError(f"{source!r} is not a body-fat source ({', '.join(SOURCES)}).")
    if (why := problem(pct)) is not None:
        raise ValueError(why)
    day = day if isinstance(day, str) else day.isoformat()
    cur = coach.db.execute(
        "INSERT INTO body_fat_estimates (date, pct, source, review_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (day, float(pct), source, review_id, now.isoformat(timespec="seconds")))
    return cur.lastrowid


def _by_date(coach: "Coach", where: str = "", params: tuple = ()) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, float]] = {}
    for r in coach.db.all(f"SELECT date, pct, source FROM body_fat_estimates {where} ORDER BY created_at, id",
                          params):
        latest.setdefault(r["date"], {})[r["source"]] = r["pct"]
    out = []
    for day in sorted(latest, reverse=True):
        found = latest[day]
        source = "user" if "user" in found else "model"
        out.append({"date": day, "pct": found[source], "source": source,
                    "model_pct": found.get("model") if source == "user" else None})
    return out


def estimates(coach: "Coach") -> list[dict[str, Any]]:
    return _by_date(coach)


def on(coach: "Coach", day: datetime.date | str) -> dict[str, Any] | None:
    day = day if isinstance(day, str) else day.isoformat()
    found = _by_date(coach, "WHERE date = ?", (day,))
    return found[0] if found else None


def latest(coach: "Coach", day: datetime.date | str) -> dict[str, Any] | None:
    day = day if isinstance(day, str) else day.isoformat()
    found = _by_date(coach, "WHERE date <= ?", (day,))
    return found[0] if found else None


def detach(coach: "Coach", review_ids: list[int]) -> None:
    for review_id in review_ids:
        coach.db.execute("UPDATE body_fat_estimates SET review_id = NULL WHERE review_id = ?", (review_id,))
