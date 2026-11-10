"""Lift progression (spec, "Training data rules"; ticket 08 decisions).
Tables from migrations/08_lifts.sql; sessions from history.py.

Every exercise logged in Hevy is recorded, each with its own history
(alternatives such as pull-ups and lat pulldowns are separate exercises).
The model classifies each one as `counts` (the default: compounds, machines,
most bigger isolation work) or `excluded` (prehab/rehab and slow movers);
the user can flip any. Only counting exercises decide `progression_met`, the
stalls and the deload signal; excluded ones are still listed and their PRs
named.

Per session of an exercise:
- Performance = the heaviest working set with `training.rep_range` reps
  (warm-ups and sets outside the range never count). Bodyweight exercises
  use the effective load: bodyweight (7-day trend, else the latest weigh-in)
  plus added load, minus assistance.
- Compared with the best of the previous `compare_best_of_last_sessions`
  sessions of its history (needing `min_sessions_for_compare` sessions
  including this one). Same effective load: more reps improved, same reps
  same, fewer declined. Different load: estimated 1RM (Epley, w x (1 + r/30))
  within ±`e1rm_same_band_pct` % is same, above improved, below declined.
- Not judged: the first session of an exercise or after a baseline reset
  (`new_baseline`, starts the history, no PR); the first session after a
  break longer than `lift_recency_days` (`not_judged`, `after_break`; it joins
  the history, so the next one compares with sessions from before the break
  too). Sessions on a day with an `other_location` context note, and sessions
  without a working set in the rep range, are ignored: not judged, no
  baseline, no PR, no reset question (`not_judged`, with the reason).
- A PR beats the best session since the baseline by the same comparison.
  `no_progress_streak` / `decline_streak` count consecutive judged sessions
  without improvement / declining (a new baseline or break restarts them);
  `stalled` once the streak reaches `stall_sessions` (`new_stall` exactly
  then). `possible_reset`: the estimated 1RM dropped `big_drop_pct_ask_reset`
  % or more below the best recent session and no reset / injury / pain note
  covers the day.
- A paused exercise is not judged (`paused`).

Read API:
- `session(coach, session_id)`: every exercise of one session, judged as
  above (training feedback, ticket 12).
- `week(coach, start, end)`: the `training` section of the weekly facts.
- `exercises(coach, since, until)`: exercises in the Hevy history with
  their settings (phase start, chat).
Writes: `classify`, `set_paused`, `mark_reset`.
"""

import datetime
import functools
from typing import TYPE_CHECKING, Any

from . import history, phases
from .features import context_notes

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)

# Hevy exercise types whose load is bodyweight +1 x added load or -1 x assistance.
BODYWEIGHT_TYPES = {"bodyweight_reps": 1, "bodyweight_weighted": 1, "reps_only": 1, "bodyweight_assisted_reps": -1}
OTHER_LOCATION_TAG = "other_location"
RESET_NOTE_TAGS = ("baseline_reset", "injury", "pain")
JUDGED = ("improved", "same", "declined")
CLASSES = ("counts", "excluded")
SAME_LOAD_KG = 0.01


# --- settings ----------------------------------------------------------------------


def settings(coach: "Coach") -> dict[str, dict[str, Any]]:
    return {r["exercise_id"]: dict(r) for r in coach.db.all("SELECT * FROM exercise_settings")}


def known_exercise(coach: "Coach", exercise_id: str) -> dict[str, Any] | None:
    """The exercise as Hevy last sent it ({exercise_id, title, exercise_type}), or None."""
    row = coach.db.one(
        "SELECT e.exercise_id, e.title, e.exercise_type FROM lift_exercises e JOIN lift_sessions s"
        " ON s.id = e.session_id WHERE e.exercise_id = ? ORDER BY s.start_at DESC LIMIT 1", (exercise_id,))
    return dict(row) if row else None


def _upsert(coach: "Coach", exercise_id: str, now: datetime.datetime, **values: Any) -> None:
    known = known_exercise(coach, exercise_id)
    title = known["title"] if known else None
    at = now.isoformat(timespec="seconds")
    columns = ", ".join(values)
    updates = ", ".join(f"{k} = excluded.{k}" for k in values)
    coach.db.execute(
        f"INSERT INTO exercise_settings (exercise_id, title, {columns}, updated_at)"
        f" VALUES (?, ?, {', '.join('?' * len(values))}, ?)"
        f" ON CONFLICT (exercise_id) DO UPDATE SET title = COALESCE(excluded.title, title), {updates},"
        " updated_at = excluded.updated_at",
        (exercise_id, title, *values.values(), at),
    )


def classify(coach: "Coach", exercise_id: str, classification: str, reason: str | None,
             now: datetime.datetime) -> None:
    """`counts` or `excluded`."""
    if classification not in CLASSES:
        raise ValueError(f"classification must be one of {CLASSES}")
    _upsert(coach, exercise_id, now, classification=classification, class_reason=reason)


def set_paused(coach: "Coach", exercise_id: str, paused: bool, reason: str | None, now: datetime.datetime) -> None:
    _upsert(coach, exercise_id, now, paused=int(paused), paused_reason=reason)


def mark_reset(coach: "Coach", exercise_id: str, from_date: Date, now: datetime.datetime, *,
               session_id: str | None = None, reason: str | None = None) -> None:
    """The first session of the exercise on or after `from_date` (or the
    given session) starts a new baseline."""
    coach.db.execute(
        "INSERT INTO baseline_resets (exercise_id, from_date, session_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (exercise_id, from_date.isoformat(), session_id, reason, now.isoformat(timespec="seconds")),
    )


def exercises(coach: "Coach", since: Date, until: Date) -> list[dict[str, Any]]:
    """Exercises with a session from `since` to `until`, most often done
    first: {exercise_id, title, exercise_type, bodyweight_exercise, sessions,
    last_date, classification (null = not classified yet, counts), paused}."""
    found: dict[str, dict[str, Any]] = {}
    for s in history.sessions(coach.db, since.isoformat(), until.isoformat()):
        for ex in s["exercises"]:
            if not ex["exercise_id"]:
                continue
            item = found.setdefault(ex["exercise_id"], {"exercise_id": ex["exercise_id"], "sessions": 0})
            if item.get("last_date") != s["date"]:
                item["sessions"] += 1
            item.update(title=ex["title"], exercise_type=ex["exercise_type"], last_date=s["date"],
                        bodyweight_exercise=ex["exercise_type"] in BODYWEIGHT_TYPES)
    stored = settings(coach)
    for item in found.values():
        row = stored.get(item["exercise_id"], {})
        item.update(classification=row.get("classification"), paused=bool(row.get("paused")))
    return sorted(found.values(), key=lambda o: (-o["sessions"], o["title"] or ""))


def unclassified(coach: "Coach", since: Date, until: Date) -> list[dict[str, Any]]:
    """Exercises in that range the model hasn't classified yet."""
    return [e for e in exercises(coach, since, until) if e["classification"] is None]


# --- judging -----------------------------------------------------------------------


def e1rm(load: float, reps: int) -> float:
    return round(load * (1 + reps / 30), 2)


def compare(cur: dict[str, Any], ref: dict[str, Any], band_pct: float) -> str:
    """improved / same / declined for two set summaries."""
    if abs(cur["effective_load_kg"] - ref["effective_load_kg"]) < SAME_LOAD_KG:
        return "improved" if cur["reps"] > ref["reps"] else "declined" if cur["reps"] < ref["reps"] else "same"
    change = (cur["e1rm_kg"] / ref["e1rm_kg"] - 1) * 100 if ref["e1rm_kg"] else 0.0
    return "improved" if change > band_pct else "declined" if change < -band_pct else "same"


class _Judge:
    """Judges every synced session of every exercise up to `until`, oldest first."""

    def __init__(self, coach: "Coach", until: Date):
        self.coach = coach
        self.p = phases.params(coach)["training"]
        self.until = until
        self.sessions = history.sessions(coach.db, "0000-01-01", until.isoformat())
        self.settings = settings(coach)
        self.resets: dict[str, list[dict[str, Any]]] = {}
        for r in coach.db.all("SELECT * FROM baseline_resets ORDER BY from_date, id"):
            self.resets.setdefault(r["exercise_id"], []).append(dict(r))
        first = self.sessions[0]["date"] if self.sessions else until.isoformat()
        self.notes = context_notes.between(coach, Date.fromisoformat(first), until)
        self.weigh_ins = history.weigh_ins(coach.db, "0000-01-01", until.isoformat())

    @functools.cache
    def bodyweight(self, day: str) -> float:
        trend = phases.trend_weight(self.coach, Date.fromisoformat(day))
        if trend is not None:
            return trend
        before = [w for d, w in self.weigh_ins.items() if d <= day]
        if before:
            return before[-1]
        return next(iter(self.weigh_ins.values()), 0.0)

    def _notes_on(self, day: str, exercise_id: str, tags: tuple[str, ...]) -> bool:
        return any(n["applies_from"] <= day <= (n["applies_to"] or "9999-12-31")
                   and any(t in tags for t in n["tags"]) and n["exercise_id"] in (None, exercise_id)
                   for n in self.notes)

    def _top(self, sets: list[dict[str, Any]], exercise_type: str | None, day: str) -> dict[str, Any] | None:
        low, high = self.p["rep_range"]
        sign = BODYWEIGHT_TYPES.get(exercise_type or "")
        best = None
        for s in sets:
            if s["type"] == "warmup" or s["reps"] is None or not low <= s["reps"] <= high:
                continue
            load = s["weight_kg"] or 0.0
            effective = round(self.bodyweight(day) + sign * load, 2) if sign else load
            summary = {"load_kg": load, "reps": s["reps"], "effective_load_kg": effective,
                       "e1rm_kg": e1rm(effective, s["reps"])}
            if best is None or (effective, s["reps"]) > (best["effective_load_kg"], best["reps"]):
                best = summary
        return best

    def all(self) -> dict[str, dict[str, Any]]:
        """{exercise_id: {exercise_id, name, exercise_type, bodyweight_exercise,
        counts, classification, paused, entries}}, entries oldest first."""
        occurrences: dict[str, list[dict[str, Any]]] = {}
        lifts: dict[str, dict[str, Any]] = {}
        for s in self.sessions:
            merged: dict[str, dict[str, Any]] = {}
            for ex in s["exercises"]:
                if not ex["exercise_id"]:
                    continue
                item = merged.setdefault(ex["exercise_id"], {"session_id": s["id"], "date": s["date"], "sets": []})
                item["sets"] += ex["sets"]
                row = self.settings.get(ex["exercise_id"], {})
                lifts[ex["exercise_id"]] = {
                    "exercise_id": ex["exercise_id"], "name": ex["title"] or ex["exercise_id"],
                    "exercise_type": ex["exercise_type"],
                    "bodyweight_exercise": (ex["exercise_type"] or "") in BODYWEIGHT_TYPES,
                    "classification": row.get("classification"),
                    "counts": row.get("classification") != "excluded",
                    "paused": bool(row.get("paused")),
                }
            for exercise_id, item in merged.items():
                occurrences.setdefault(exercise_id, []).append(item)
        for exercise_id, lift in lifts.items():
            lift["entries"] = self._judge(lift, occurrences[exercise_id])
        return lifts

    def _judge(self, lift: dict[str, Any], occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
        p = self.p
        exercise_id = lift["exercise_id"]
        resets = list(self.resets.get(exercise_id, []))
        pool: list[dict[str, Any]] = []
        best_ever = None
        last_day = None
        no_progress = decline = 0
        entries = []
        for occ in occurrences:
            top = self._top(occ["sets"], lift["exercise_type"], occ["date"])
            entry = {
                "session_id": occ["session_id"], "date": occ["date"],
                "sets": [{"load_kg": s["weight_kg"] or 0.0, "reps": s["reps"]} for s in occ["sets"]
                         if s["type"] != "warmup" and s["reps"] is not None],
                "top": top, "status": "not_judged", "not_judged_reason": None, "best_recent": None,
                "sessions_considered": 0, "is_pr": False, "drop_pct_vs_best_recent": None, "possible_reset": False,
            }
            reset_here = False
            while resets and (resets[0]["session_id"] == occ["session_id"]
                              or (resets[0]["session_id"] is None and resets[0]["from_date"] <= occ["date"])):
                resets.pop(0)
                reset_here = True
            if reset_here:
                pool, best_ever, no_progress, decline = [], None, 0, 0
            if top is None:
                entry["not_judged_reason"] = "no_working_sets"
            elif self._notes_on(occ["date"], exercise_id, (OTHER_LOCATION_TAG,)):
                entry["not_judged_reason"] = "other_location"
            elif not pool:
                entry["status"] = "new_baseline"
                entry["not_judged_reason"] = "baseline_reset" if reset_here else "first_session"
            elif (Date.fromisoformat(occ["date"]) - Date.fromisoformat(last_day)).days > p["lift_recency_days"]:
                entry["not_judged_reason"] = "after_break"
                no_progress = decline = 0
            elif len(pool) + 1 < p["min_sessions_for_compare"]:
                entry["not_judged_reason"] = "building_baseline"
            else:
                recent = pool[-p["compare_best_of_last_sessions"]:]
                best = max(recent, key=lambda t: (t["e1rm_kg"], t["reps"]))
                status = compare(top, best, p["e1rm_same_band_pct"])
                drop = round(max(0.0, (best["e1rm_kg"] - top["e1rm_kg"]) / best["e1rm_kg"] * 100), 1) \
                    if best["e1rm_kg"] else 0.0
                no_progress = 0 if status == "improved" else no_progress + 1
                decline = decline + 1 if status == "declined" else 0
                entry.update(
                    status=status, best_recent=best, sessions_considered=len(recent),
                    is_pr=compare(top, best_ever, p["e1rm_same_band_pct"]) == "improved",
                    drop_pct_vs_best_recent=drop,
                    possible_reset=drop >= p["big_drop_pct_ask_reset"]
                    and not self._notes_on(occ["date"], exercise_id, RESET_NOTE_TAGS),
                )
            if entry["status"] == "new_baseline":
                no_progress = decline = 0
            entry["no_progress_streak"] = no_progress
            entry["decline_streak"] = decline
            entry["stalled"] = entry["status"] in JUDGED and no_progress >= p["stall_sessions"]
            entry["new_stall"] = entry["status"] in JUDGED and no_progress == p["stall_sessions"]
            if entry["not_judged_reason"] not in ("no_working_sets", "other_location"):
                pool.append(top)
                last_day = occ["date"]
                if best_ever is None or (top["e1rm_kg"], top["reps"]) > (best_ever["e1rm_kg"], best_ever["reps"]):
                    best_ever = top
            entries.append(entry)
        return entries


def _summary(top: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if top is None else {k: top[k] for k in ("load_kg", "reps", "effective_load_kg", "e1rm_kg")}


def _exercise_view(lift: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    paused = lift["paused"]
    flags = not paused and lift["counts"]  # excluded exercises get no stall flags
    return {
        "exercise_id": lift["exercise_id"],
        "name": lift["name"],
        "counts": lift["counts"],
        "classification": lift["classification"],
        "bodyweight_exercise": lift["bodyweight_exercise"],
        "sets": entry["sets"],
        "top_set": _summary(entry["top"]),
        "status": "paused" if paused else entry["status"],
        "not_judged_reason": None if paused else entry["not_judged_reason"],
        "best_recent": _summary(entry["best_recent"]),
        "is_pr": entry["is_pr"] and not paused,
        "drop_pct_vs_best_recent": entry["drop_pct_vs_best_recent"],
        "possible_reset": entry["possible_reset"] and not paused,
        "no_progress_streak": entry["no_progress_streak"],
        "decline_streak": entry["decline_streak"],
        "stalled": entry["stalled"] and flags,
        "new_stall": entry["new_stall"] and flags,
    }


def session(coach: "Coach", session_id: str) -> dict[str, Any] | None:
    """One synced session, every exercise judged: {session_id, date,
    exercises: [{exercise_id, name, counts, classification,
    bodyweight_exercise, sets, top_set, status, not_judged_reason,
    best_recent, is_pr, drop_pct_vs_best_recent, possible_reset,
    no_progress_streak, decline_streak, stalled, new_stall}]}; None if unknown."""
    row = coach.db.one("SELECT date FROM lift_sessions WHERE id = ?", (session_id,))
    if row is None:
        return None
    lifts = _Judge(coach, Date.fromisoformat(row["date"])).all()
    out = []
    for lift in lifts.values():
        out += [_exercise_view(lift, e) for e in lift["entries"] if e["session_id"] == session_id]
    order = [ex["exercise_id"] for s in history.sessions(coach.db, row["date"], row["date"])
             if s["id"] == session_id for ex in s["exercises"]]
    out.sort(key=lambda e: order.index(e["exercise_id"]) if e["exercise_id"] in order else len(order))
    return {"session_id": session_id, "date": row["date"], "exercises": out}


# --- the week ----------------------------------------------------------------------


def week(coach: "Coach", start: Date, end: Date, phase_start: Date | None = None) -> dict[str, Any]:
    """The weekly facts' `training` section (without `missed_sessions`) for
    the week `start`..`end`. Lists every exercise trained since `phase_start`
    or within the recency window, counting ones first; a lift's status is that
    of its latest session that wasn't ignored. Only counting lifts decide
    `progression_met` (one exercise, one vote), stalls and the deload signal."""
    p = phases.params(coach)["training"]
    window_start = end - (p["lift_recency_days"] - 1) * DAY
    since = min(window_start, phase_start or window_start)
    lifts = _Judge(coach, end).all()
    listed, prs = [], []
    for lift in lifts.values():
        if not any(since.isoformat() <= e["date"] for e in lift["entries"]):
            continue
        relevant = [e for e in lift["entries"] if e["not_judged_reason"] not in ("no_working_sets", "other_location")]
        latest = relevant[-1] if relevant else None
        if lift["paused"]:
            status = "paused"
        elif latest is None or latest["date"] < window_start.isoformat():
            status = "stale"
        else:
            status = latest["status"]
        active = status not in ("paused", "stale")
        listed.append({
            "exercise_id": lift["exercise_id"],
            "name": lift["name"],
            "bodyweight_exercise": lift["bodyweight_exercise"],
            "counts": lift["counts"],
            "classification": lift["classification"],
            "status": status,
            "not_judged_reason": latest["not_judged_reason"] if latest and status == "not_judged" else None,
            "counted": status in JUDGED and lift["counts"],
            "last_session_date": latest["date"] if latest else None,
            "sessions_considered": latest["sessions_considered"] if latest else 0,
            "best_recent": _summary(latest["best_recent"]) if latest else None,
            "latest": _summary(latest["top"]) if latest else None,
            "no_progress_streak": latest["no_progress_streak"] if latest and active else 0,
            "decline_streak": latest["decline_streak"] if latest and active else 0,
            "stalled": bool(latest and active and lift["counts"] and latest["stalled"]),
        })
        if not lift["paused"]:
            prs += [{"exercise_id": lift["exercise_id"], "name": lift["name"], "date": e["date"],
                     "top_set": _summary(e["top"])}
                    for e in lift["entries"] if e["is_pr"] and start.isoformat() <= e["date"] <= end.isoformat()]
    listed.sort(key=lambda lift: (not lift["counts"], lift["name"]))
    counted = [lift for lift in listed if lift["counted"]]
    improved = [lift for lift in counted if lift["status"] == "improved"]
    share = round(len(improved) / len(counted), 2) if counted else None
    declining = [lift for lift in listed
                 if lift["counts"] and lift["decline_streak"] >= p["decline_sessions_for_deload"]]
    week_sessions = history.sessions(coach.db, start.isoformat(), end.isoformat())
    set_counts = [sum(1 for ex in s["exercises"] for st in ex["sets"] if st["type"] != "warmup")
                  for s in week_sessions]
    return {
        "tracked_lifts": listed,
        "counted_lifts": len(counted),
        "improved_lifts": len(improved),
        "share_improved": share,
        "progression_met": None if not counted else len(improved) >= p["progression_min_share"] * len(counted),
        "stalls": [lift["exercise_id"] for lift in listed if lift["stalled"]],
        "declining_lifts": [lift["exercise_id"] for lift in declining],
        "deload_signal": len(declining) >= p["deload_min_lifts_declining"],
        "prs": sorted(prs, key=lambda pr: (pr["date"], pr["name"])),
        "excluded_lifts": [lift["exercise_id"] for lift in listed if not lift["counts"]],
        "lifting_sessions": len(week_sessions),
        "max_sets_in_a_session": max(set_counts) if set_counts else None,
        "max_sets_per_muscle_in_a_session": None,  # Hevy's muscle groups aren't synced
    }
