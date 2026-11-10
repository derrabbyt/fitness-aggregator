"""Sync history from the api: MFP food totals, weight, steps and runs; Hevy
lifting sessions. Read the result through `fa_coach.history`.

- The first sync loads `HISTORY_DAYS` (16 weeks up to today). Later syncs
  fetch from where the last one ended, and always re-read the last
  `RECHECK_DAYS` so late edits in MFP or Hevy land.
- Weigh-in outliers are marked here, in code, and never messaged about.
- Each source records its last attempt and success (`sync_state`). When the
  last successful sync is older than `data.sync_max_age_hours`, the
  `stale-data` job sends one notice per stale stretch.
- `/sync` syncs now and says what came in.
"""

import datetime
import statistics
from typing import Any

from .. import errors, history
from ..registry import registry

HISTORY_DAYS = 16 * 7
RECHECK_DAYS = 7
MFP_CHUNK_DAYS = 28  # days per api request (the api reads MFP day by day)

Date = datetime.date


# --- syncers -----------------------------------------------------------------


@registry.syncer("mfp", order=10)
async def sync_mfp(coach, now: datetime.datetime) -> None:
    async with _Run(coach, "mfp", now) as run:
        failed: list[str] = []
        start = run.start
        while start <= run.end:
            end = min(start + datetime.timedelta(days=MFP_CHUNK_DAYS - 1), run.end)
            records = await coach.api.mfp_days(start, end)
            good = [r for r in records if not r.get("error")]
            if records and not good:
                raise NoDayRead(f"MFP couldn't read any day from {start} to {end}")
            failed += [r["date"] for r in records if r.get("error")]
            with coach.db.transaction():
                for record in good:
                    _store_day(coach.db, record, now)
                _set(coach.db, "mfp", synced_through=end.isoformat())
            run.count += len(good)
            start = end + datetime.timedelta(days=1)
        _mark_outliers(coach.db, coach.skills.params()["data"])
        if failed:
            run.warning = f"MFP couldn't read {', '.join(failed)}"


@registry.syncer("hevy", order=20)
async def sync_hevy(coach, now: datetime.datetime) -> None:
    async with _Run(coach, "hevy", now) as run:
        sessions = await coach.api.hevy_sessions(run.start, run.end)
        db = coach.db
        known = {
            r[0]
            for r in db.all(
                "SELECT id FROM lift_sessions WHERE date BETWEEN ? AND ?", (run.start.isoformat(), run.end.isoformat())
            )
        }
        with db.transaction():
            # Sessions deleted in Hevy disappear here too.
            gone = known - {s["id"] for s in sessions}
            for session_id in gone:
                db.execute("DELETE FROM lift_sessions WHERE id = ?", (session_id,))
            for s in sessions:
                _store_session(db, s, now)
            _set(db, "hevy", synced_through=run.end.isoformat())
        run.count = len(sessions)
        run.new = len({s["id"] for s in sessions} - known)


class _Run:
    def __init__(self, coach, source: str, now: datetime.datetime):
        self.coach, self.source, self.now = coach, source, now
        today = now.date()
        through = coach.db.value("SELECT synced_through FROM sync_state WHERE source = ?", (source,))
        first = today - datetime.timedelta(days=HISTORY_DAYS - 1)
        if through is None:
            self.start = first
        else:
            resume = Date.fromisoformat(through) + datetime.timedelta(days=1)
            recheck = today - datetime.timedelta(days=RECHECK_DAYS - 1)
            self.start = max(first, min(resume, recheck))
        self.end = today
        self.count = 0
        self.new: int | None = None
        self.warning: str | None = None

    async def __aenter__(self) -> "_Run":
        db = self.coach.db
        db.execute("INSERT OR IGNORE INTO sync_state (source) VALUES (?)", (self.source,))
        _set(db, self.source, last_attempt_at=self.now.isoformat())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            error = str(exc) if isinstance(exc, NoDayRead) else errors.brief("the sync failed", exc)
            _set(self.coach.db, self.source, last_error=error, last_count=None, last_new=None)
            return  # the core logs it; other sources still run
        _set(
            self.coach.db,
            self.source,
            last_success_at=self.now.isoformat(),
            last_error=self.warning,
            last_start=self.start.isoformat(),
            last_end=self.end.isoformat(),
            last_count=self.count,
            last_new=self.new,
        )




def _set(db, source: str, **values: Any) -> None:
    columns = ", ".join(f"{k} = ?" for k in values)
    db.execute(f"UPDATE sync_state SET {columns} WHERE source = ?", (*values.values(), source))


class NoDayRead(RuntimeError):
    """Every day of a chunk failed. Its message is the coach's own (shown to the user)."""


# --- storing -----------------------------------------------------------------


def _store_day(db, record: dict[str, Any], now: datetime.datetime) -> None:
    day = record["date"]
    food = record.get("food") or {}
    db.execute(
        "INSERT OR REPLACE INTO mfp_days (date, kcal, protein_g, carbs_g, fat_g, fiber_g, produce_g, complete,"
        " food_entries, steps, synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            day,
            food.get("kcal"),
            food.get("protein_g"),
            food.get("carbs_g"),
            food.get("fat_g"),
            food.get("fiber_g"),
            food.get("produce_g"),
            int(bool(food.get("complete"))),
            int(food.get("entries") or 0),
            record.get("steps"),
            now.isoformat(),
        ),
    )
    db.execute("DELETE FROM mfp_exercises WHERE date = ?", (day,))
    for i, e in enumerate(record.get("exercises") or []):
        db.execute(
            "INSERT INTO mfp_exercises (date, position, name, source, is_run, kcal, distance_km, minutes, start_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (day, i, e.get("name"), e.get("source"), int(bool(e.get("run"))), e.get("kcal"), e.get("distance_km"),
             e.get("minutes"), e.get("start")),
        )
    weight = record.get("weight_kg")
    if weight is None:
        db.execute("DELETE FROM weigh_ins WHERE date = ?", (day,))
    else:
        db.execute(
            "INSERT INTO weigh_ins (date, weight_kg, synced_at) VALUES (?, ?, ?)"
            " ON CONFLICT (date) DO UPDATE SET weight_kg = excluded.weight_kg, synced_at = excluded.synced_at",
            (day, float(weight), now.isoformat()),
        )


def _store_session(db, s: dict[str, Any], now: datetime.datetime) -> None:
    db.execute(
        "INSERT INTO lift_sessions (id, date, name, start_at, end_at, minutes, first_seen_at, synced_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET date = excluded.date, name = excluded.name,"
        " start_at = excluded.start_at, end_at = excluded.end_at, minutes = excluded.minutes,"
        " synced_at = excluded.synced_at",
        (s["id"], s["date"], s.get("name"), s.get("start"), s.get("end"), s.get("minutes"), now.isoformat(),
         now.isoformat()),
    )
    db.execute("DELETE FROM lift_exercises WHERE session_id = ?", (s["id"],))
    db.execute("DELETE FROM lift_sets WHERE session_id = ?", (s["id"],))
    for i, e in enumerate(s.get("exercises") or []):
        db.execute(
            "INSERT INTO lift_exercises (session_id, position, exercise_id, title, exercise_type) VALUES (?, ?, ?, ?, ?)",
            (s["id"], i, e.get("exercise_id"), e.get("title"), e.get("exercise_type")),
        )
        for j, x in enumerate(e.get("sets") or []):
            db.execute(
                "INSERT INTO lift_sets (session_id, exercise_position, position, type, weight_kg, reps, distance_m,"
                " duration_s, rpe) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s["id"], i, j, x.get("type"), x.get("weight_kg"), x.get("reps"), x.get("distance_m"),
                 x.get("duration_s"), x.get("rpe")),
            )


def _mark_outliers(db, params: dict[str, Any]) -> None:
    """A weigh-in is an outlier when it is more than `weight_outlier_kg` from
    the median of the other weigh-ins within `weight_outlier_window_days`
    either side (at least two needed). Recomputed over all weigh-ins, so a
    flag can change as neighbours arrive."""
    limit, window = params["weight_outlier_kg"], params["weight_outlier_window_days"]
    weights = [(Date.fromisoformat(r[0]), r[1]) for r in db.all("SELECT date, weight_kg FROM weigh_ins ORDER BY date")]
    with db.transaction():
        for day, kg in weights:
            neighbours = [w for d, w in weights if d != day and abs((d - day).days) <= window]
            outlier = len(neighbours) >= 2 and abs(kg - statistics.median(neighbours)) > limit
            db.execute("UPDATE weigh_ins SET outlier = ? WHERE date = ?", (int(outlier), day.isoformat()))


# --- /sync -------------------------------------------------------------------


@registry.command("sync", "Sync MFP and Hevy now")
async def sync_command(coach, args: str, now: datetime.datetime) -> None:
    await coach.sync(now)
    state = {r["source"]: r for r in coach.db.all("SELECT * FROM sync_state")}
    done, problems = [], []
    for source, label in (("mfp", "MFP"), ("hevy", "Hevy")):
        row = state.get(source)
        if row is None or row["last_attempt_at"] != now.isoformat():
            continue
        if row["last_success_at"] == now.isoformat():
            done.append(_what_came_in(source, row))
            if row["last_error"]:
                problems.append(row["last_error"] + ".")
        else:
            problems.append(f"{label} failed: {row['last_error']}")
    lines = [f"Synced {' and '.join(done)}." if done else "Nothing synced."] + problems
    lines.append(f"Last sync: {_when(freshness(coach, now)['last_sync_at'])}.")
    coach.say("\n".join(lines))


def _what_came_in(source: str, row) -> str:
    if source == "mfp":
        return f"{_plural(row['last_count'], 'day')} from MFP ({row['last_start']} to {row['last_end']})"
    return f"{_plural(row['last_count'], 'Hevy session')} ({row['last_new']} new)"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _when(iso: str | None) -> str:
    if iso is None:
        return "never"
    t = datetime.datetime.fromisoformat(iso)
    return f"{t:%a} {t.day} {t:%b %H:%M}"


# --- freshness ---------------------------------------------------------------


def freshness(coach, now: datetime.datetime) -> dict[str, Any]:
    """`history.freshness` with the stale limit from params, for facts."""
    return history.freshness(coach.db, now, coach.skills.params()["data"]["sync_max_age_hours"])


@registry.job("stale-data", order=10)
async def stale_notice(coach, now: datetime.datetime) -> None:
    """One notice per stale stretch (keyed by the last good sync), and none
    before the first sync attempt."""
    if coach.db.value("SELECT COUNT(*) FROM sync_state WHERE last_attempt_at IS NOT NULL") == 0:
        return
    fresh = freshness(coach, now)
    if fresh["fresh"] or not coach.db.once(f"stale-notice:{fresh['last_sync_at']}", now):
        return
    reasons = [
        f"{label}: {s['last_error']}"
        for name, label in (("mfp", "MFP"), ("hevy", "Hevy"))
        if (s := fresh["sources"][name])["last_error"] and s["last_attempt_at"] != s["last_success_at"]
    ]
    why = f" ({'; '.join(reasons)})" if reasons else ""
    since = f"since {_when(fresh['last_sync_at'])}" if fresh["last_sync_at"] else "yet"
    coach.say(
        f"No successful sync {since}{why}. "
        "Weeks without fresh data may not count. /sync retries."
    )
