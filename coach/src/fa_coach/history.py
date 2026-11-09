"""Reading the synced history (tables from migrations/02_sync.sql, filled by
features/sync.py). Facts and jobs read MFP and Hevy data only through here.

Dates are "YYYY-MM-DD" strings, ranges inclusive.
"""

import datetime
from typing import Any

from .db import Database

SOURCES = ("mfp", "hevy")


def days(db: Database, start: str, end: str) -> list[dict[str, Any]]:
    """Synced MFP days in the range, oldest first: food totals (kcal,
    protein_g, carbs_g, fat_g, fiber_g, produce_g; null if unknown), `logged`
    (any food entry, or the day marked complete in MFP), `complete`, `steps`,
    `weight_kg` with `weight_outlier`, and `runs` / `exercises` from MFP."""
    rows = db.all(
        "SELECT d.*, w.weight_kg, w.outlier FROM mfp_days d LEFT JOIN weigh_ins w ON w.date = d.date"
        " WHERE d.date BETWEEN ? AND ? ORDER BY d.date",
        (start, end),
    )
    exercises: dict[str, list[dict[str, Any]]] = {}
    for e in db.all("SELECT * FROM mfp_exercises WHERE date BETWEEN ? AND ? ORDER BY date, position", (start, end)):
        exercises.setdefault(e["date"], []).append(
            {
                "name": e["name"],
                "source": e["source"],
                "run": bool(e["is_run"]),
                "kcal": e["kcal"],
                "distance_km": e["distance_km"],
                "minutes": e["minutes"],
            }
        )
    out = []
    for r in rows:
        day_exercises = exercises.get(r["date"], [])
        out.append(
            {
                "date": r["date"],
                "kcal": r["kcal"],
                "protein_g": r["protein_g"],
                "carbs_g": r["carbs_g"],
                "fat_g": r["fat_g"],
                "fiber_g": r["fiber_g"],
                "produce_g": r["produce_g"],
                "logged": bool(r["complete"] or r["food_entries"] > 0),
                "complete": bool(r["complete"]),
                "steps": r["steps"],
                "weight_kg": r["weight_kg"],
                "weight_outlier": bool(r["outlier"]) if r["weight_kg"] is not None else False,
                "runs": [
                    {k: e[k] for k in ("kcal", "distance_km", "minutes")} for e in day_exercises if e["run"]
                ],
                "exercises": day_exercises,
            }
        )
    return out


def weigh_ins(db: Database, start: str, end: str, *, include_outliers: bool = False) -> dict[str, float]:
    """Weigh-ins by date. Trend inputs: outliers are left out unless asked for."""
    sql = "SELECT date, weight_kg FROM weigh_ins WHERE date BETWEEN ? AND ?"
    if not include_outliers:
        sql += " AND outlier = 0"
    return {r["date"]: r["weight_kg"] for r in db.all(sql + " ORDER BY date", (start, end))}


def outlier_days(db: Database, start: str, end: str) -> list[str]:
    return [r[0] for r in db.all("SELECT date FROM weigh_ins WHERE outlier = 1 AND date BETWEEN ? AND ? ORDER BY date", (start, end))]


def sessions(db: Database, start: str, end: str) -> list[dict[str, Any]]:
    """Hevy sessions in the range, oldest first, with exercises (`exercise_id`,
    `title`, `exercise_type`) and their sets (`type`, `weight_kg`, `reps`;
    distance, duration and RPE only when Hevy has them)."""
    rows = db.all(
        "SELECT * FROM lift_sessions WHERE date BETWEEN ? AND ? ORDER BY start_at, id", (start, end)
    )
    return [_session(db, r) for r in rows]


def _session(db: Database, r) -> dict[str, Any]:
    exercises = []
    for e in db.all("SELECT * FROM lift_exercises WHERE session_id = ? ORDER BY position", (r["id"],)):
        sets = []
        for s in db.all(
            "SELECT * FROM lift_sets WHERE session_id = ? AND exercise_position = ? ORDER BY position",
            (r["id"], e["position"]),
        ):
            one = {"type": s["type"], "weight_kg": s["weight_kg"], "reps": s["reps"]}
            one.update({k: s[k] for k in ("distance_m", "duration_s", "rpe") if s[k] is not None})
            sets.append(one)
        exercises.append(
            {"exercise_id": e["exercise_id"], "title": e["title"], "exercise_type": e["exercise_type"], "sets": sets}
        )
    return {
        "id": r["id"],
        "date": r["date"],
        "name": r["name"],
        "start": r["start_at"],
        "end": r["end_at"],
        "minutes": r["minutes"],
        "first_seen_at": r["first_seen_at"],
        "exercises": exercises,
    }


def freshness(db: Database, now: datetime.datetime, max_age_hours: float) -> dict[str, Any]:
    """How current the synced data is. `last_sync_at` is the older of the
    sources' last successful syncs (null until both have succeeded); `fresh`
    is false when that is missing or older than `max_age_hours`."""
    state = {r["source"]: r for r in db.all("SELECT * FROM sync_state")}
    sources = {}
    for name in SOURCES:
        row = state.get(name)
        sources[name] = {
            "last_success_at": row["last_success_at"] if row else None,
            "last_attempt_at": row["last_attempt_at"] if row else None,
            "last_error": row["last_error"] if row else None,
        }
    successes = [s["last_success_at"] for s in sources.values()]
    last = None if None in successes else min(successes, key=datetime.datetime.fromisoformat)
    age = None if last is None else (now - datetime.datetime.fromisoformat(last)).total_seconds() / 3600
    return {
        "last_sync_at": last,
        "age_hours": None if age is None else round(age, 1),
        "fresh": age is not None and age <= max_age_hours,
        "sources": sources,
    }
