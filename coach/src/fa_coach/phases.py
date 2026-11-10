"""Phases, their setup values and targets (tables from migrations/05_phases.sql).
Every number here is computed by code; the model only sees the results.

Read API for features:
- `active(coach)`: the active phase {id, phase_id, start_date, setup,
  first_change_applied, started_at} or None (nothing is active before the
  user confirms a phase start).
- `params(coach)`: coach-core params merged with the active phase's params
  and its setup values (run discount, wrestling/lifting kcal, fat start,
  photos, time goal, logistics -> `messaging` and `activity.soft_floor_min_days`).
  This is the `params` block facts carry.
- `setup_value(coach, "logistics.weekly_checkin")`: one setup value of the active phase.
- `targets(coach, day)`: the targets row in force on `day` (base maintenance,
  surplus, expected counted activity, average daily target, MFP goal).
  `set_targets(...)` adds a row (phase start, approved proposals).
- `daily_target(coach, day)`: base + counted activity + surplus for that day,
  with macros.
- `macros(params, kcal, weight_kg)`, `macro_reference_weight(coach, day)`,
  `trend_weight(coach, day)`, `phase_week(phase, day)`, `in_glycogen_window(coach, day)`.
- `maintenance_estimate(coach, end, params)`: back-calculated from logged
  intake and the weight trend over 3+ usable weeks.
- `on_confirmed`: hooks run once after a phase start is confirmed (the MFP
  goal is set there, features/phase_goal.py).

Setup collection (features/phase_start.py): `open_setup`, `pending_setup`,
`prefill`, `preview`.
"""

import datetime
import json
import statistics
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from . import history

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)

# Prefill thresholds: below these code reads nothing and the coach asks.
INTAKE_DAYS = 7  # last diet intake = average of the last 7 complete days ...
MIN_LOGGED_DAYS = 5  # ... of which at least this many are logged
TREND_DAYS = 7  # 7-day trend weight ...
MIN_TREND_WEIGH_INS = 3  # ... from at least this many weigh-ins
MAX_ESTIMATE_WEEKS = 6  # the maintenance estimate uses at most the last 6 usable weeks
ACTIVITY_DAYS = 28  # expected counted activity when no estimate window exists
HISTORY_WEEKS = 16  # as far back as the first sync reads

# Setup values that are calibration (changed later only through a proposal)
# and values that only define the start (fixed for the phase).
CALIBRATION_KEYS = ("run_kcal_discount", "wrestling_kcal_per_session", "lifting_kcal_per_session")
START_KEYS = ("starting_calories_kcal", "starting_trend_weight_kg", "maintenance_estimate_kcal",
              "maintenance_includes_activity", "fat_g_per_kg_start", "week1_increase_kcal")


# --- phases ---------------------------------------------------------------------


def active(coach: "Coach") -> dict[str, Any] | None:
    row = coach.db.one("SELECT * FROM phases WHERE status = 'active'")
    return _phase(row) if row else None


def latest(coach: "Coach") -> dict[str, Any] | None:
    """The active phase, else the most recently ended one."""
    row = coach.db.one("SELECT * FROM phases ORDER BY status = 'active' DESC, started_at DESC LIMIT 1")
    return _phase(row) if row else None


def _phase(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "phase_id": row["phase_id"],
        "status": row["status"],
        "start_date": row["start_date"],
        "setup": json.loads(row["setup"]),
        "first_change_applied": row["first_change_applied_at"] is not None,
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
    }


def setup_value(coach: "Coach", key: str) -> Any:
    """A setup value of the active phase by key path, e.g. "photos_enabled" or
    "logistics.evening_reminder_time". None without an active phase."""
    phase = active(coach)
    value: Any = phase["setup"] if phase else None
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def params(coach: "Coach") -> dict[str, Any]:
    """Core params merged with the active phase's params and setup values
    (core params alone without an active phase)."""
    phase = active(coach)
    if phase is None:
        return coach.skills.params()
    return params_for(coach.skills, phase["phase_id"], phase["setup"])


def params_for(skills, phase_id: str, setup: dict[str, Any]) -> dict[str, Any]:
    merged = skills.params(phase_id)
    activity = merged["activity"]
    for key in CALIBRATION_KEYS:
        if setup.get(key) is not None:
            activity[key] = setup[key]
    logistics = setup.get("logistics") or {}
    if logistics.get("soft_floor_min_days") is not None:
        activity["soft_floor_min_days"] = logistics["soft_floor_min_days"]
    for key in ("weekly_checkin", "evening_reminder_time", "max_unprompted_messages_per_day"):
        if logistics.get(key) is not None:
            merged["messaging"][key] = logistics[key]
    if setup.get("fat_g_per_kg_start") is not None:
        merged["macros"]["fat_g_per_kg_start"] = setup["fat_g_per_kg_start"]
    if setup.get("photos_enabled") is not None:
        merged["measurements"]["photos_enabled"] = setup["photos_enabled"]
    if "time_goal_weeks" in setup:
        merged["time_goal_weeks"] = setup["time_goal_weeks"]
    return merged


def phase_week(phase: dict[str, Any], day: Date) -> int:
    """1 for the start date and the six days after it, and so on (0 or less before the start)."""
    return (day - Date.fromisoformat(phase["start_date"])).days // 7 + 1


def in_glycogen_window(coach: "Coach", day: Date) -> bool:
    phase = active(coach)
    if phase is None:
        return False
    week = phase_week(phase, day)
    return 1 <= week <= params(coach).get("glycogen_window_weeks", 0)


# --- targets --------------------------------------------------------------------


def set_targets(coach: "Coach", phase_row_id: str, values: dict[str, Any], *, valid_from: Date, source: str,
                now: datetime.datetime, ref: str | None = None) -> None:
    """Add a targets row. `values`: base_maintenance_kcal, surplus_kcal,
    avg_activity_kcal, maintenance_estimate_kcal, avg_daily_target_kcal,
    mfp_goal {kcal, protein_g, carbs_g, fat_g}. Call inside the caller's transaction."""
    coach.db.execute(
        "INSERT INTO targets (phase_row_id, valid_from, source, ref, base_maintenance_kcal, surplus_kcal,"
        " avg_activity_kcal, maintenance_estimate_kcal, avg_daily_target_kcal, mfp_goal, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (phase_row_id, valid_from.isoformat(), source, ref, values["base_maintenance_kcal"], values["surplus_kcal"],
         values["avg_activity_kcal"], values["maintenance_estimate_kcal"], values["avg_daily_target_kcal"],
         json.dumps(values["mfp_goal"]), now.isoformat(timespec="seconds")),
    )


def targets(coach: "Coach", day: Date | None = None) -> dict[str, Any] | None:
    """The active phase's targets in force on `day` (default today)."""
    phase = active(coach)
    if phase is None:
        return None
    day = day or coach.clock.now().date()
    row = coach.db.one(
        "SELECT * FROM targets WHERE phase_row_id = ? AND valid_from <= ? ORDER BY valid_from DESC, id DESC LIMIT 1",
        (phase["id"], day.isoformat()),
    )
    return _targets(row) if row else None


def target_history(coach: "Coach") -> list[dict[str, Any]]:
    """Every targets row of the active phase, oldest first."""
    phase = active(coach)
    if phase is None:
        return []
    return [_targets(r) for r in coach.db.all("SELECT * FROM targets WHERE phase_row_id = ? ORDER BY id", (phase["id"],))]


def _targets(row) -> dict[str, Any]:
    out = {k: row[k] for k in ("valid_from", "source", "ref", "base_maintenance_kcal", "surplus_kcal",
                               "avg_activity_kcal", "maintenance_estimate_kcal", "avg_daily_target_kcal")}
    out["mfp_goal"] = json.loads(row["mfp_goal"])
    out["mfp_goal_kcal"] = out["mfp_goal"]["kcal"]
    return out


def daily_target(coach: "Coach", day: Date) -> dict[str, Any] | None:
    """`day`'s target: base maintenance + counted activity + surplus, with
    macros at the macro reference weight. None without an active phase or
    before its start."""
    from .features import training_plan  # features import this module

    phase = active(coach)
    current = targets(coach, day)
    if phase is None or current is None or phase_week(phase, day) < 1:
        return None
    p = params(coach)
    activity = training_plan.counted_activity_on(coach, day, p["activity"])
    kcal = current["base_maintenance_kcal"] + activity["kcal"] + current["surplus_kcal"]
    return {
        "date": day.isoformat(),
        "kcal": round(kcal),
        "base_maintenance_kcal": round(current["base_maintenance_kcal"]),
        "surplus_kcal": round(current["surplus_kcal"]),
        "activity": activity,
        "macros": macros(p, kcal, macro_reference_weight(coach, day)),
    }


def macros(p: dict[str, Any], kcal: float, weight_kg: float) -> dict[str, Any]:
    """Protein and fat in g/kg of `weight_kg`, carbs the remainder (grams rounded)."""
    protein = p["macros"]["protein_g_per_kg"] * weight_kg
    fat = p["macros"]["fat_g_per_kg_start"] * weight_kg
    carbs = (kcal - protein * 4 - fat * 9) / 4
    return {"protein_g": round(protein), "fat_g": round(fat), "carbs_g": round(carbs),
            "protein_g_per_kg": p["macros"]["protein_g_per_kg"], "fat_g_per_kg": p["macros"]["fat_g_per_kg_start"],
            "reference_weight_kg": round(weight_kg, 1)}


def trend_weight(coach: "Coach", day: Date) -> float | None:
    """Mean of the non-outlier weigh-ins in the 7 days ending `day`; None
    with fewer than MIN_TREND_WEIGH_INS."""
    weights = list(history.weigh_ins(coach.db, (day - (TREND_DAYS - 1) * DAY).isoformat(), day.isoformat()).values())
    return round(statistics.fmean(weights), 2) if len(weights) >= MIN_TREND_WEIGH_INS else None


def macro_reference_weight(coach: "Coach", day: Date) -> float:
    """The weight macros use on `day`: the starting trend weight in phase week
    1, then the 7-day trend at the end of the previous phase week
    (recalculated weekly), falling back to the starting trend weight."""
    phase = active(coach)
    start_weight = phase["setup"]["starting_trend_weight_kg"]
    week = phase_week(phase, day)
    if week <= 1:
        return start_weight
    week_start = Date.fromisoformat(phase["start_date"]) + (week - 1) * 7 * DAY
    return trend_weight(coach, week_start - DAY) or start_weight


# --- maintenance estimate --------------------------------------------------------


def maintenance_estimate(coach: "Coach", end: Date, p: dict[str, Any]) -> dict[str, Any]:
    """Back-calculated maintenance from the most recent run of usable weeks
    ending at or before `end` (each week fully logged, enough weigh-ins, no
    note marking it unusable, outside an earlier phase's glycogen window):
    average intake - weight change x kcal_per_kg / days between the first and
    last week. Needs `maintenance_estimate.min_window_weeks` weeks; otherwise
    `value` is None and `missing` says why."""
    cfg = p["maintenance_estimate"]
    need = cfg["min_window_weeks"]
    first = end - HISTORY_WEEKS * 7 * DAY + DAY
    days = {d["date"]: d for d in history.days(coach.db, first.isoformat(), end.isoformat())}
    weights = history.weigh_ins(coach.db, first.isoformat(), end.isoformat())
    blocked = _unusable_days(coach, first, end, cfg)
    run: list[tuple[Date, Date]] = []
    for k in range(HISTORY_WEEKS):
        week_end = end - 7 * k * DAY
        week_start = week_end - 6 * DAY
        dates = [(week_start + n * DAY).isoformat() for n in range(7)]
        usable = (
            all(d in days and days[d]["logged"] and days[d]["kcal"] is not None for d in dates)
            and sum(d in weights for d in dates) >= p["data"]["min_weighins_per_week"]
            and not any(d in blocked for d in dates)
        )
        if usable:
            run.append((week_start, week_end))
            if len(run) == MAX_ESTIMATE_WEEKS:
                break
        elif run:
            break
    if len(run) < need:
        return {"value": None, "missing": f"needs {need} usable weeks (fully logged, at least "
                f"{p['data']['min_weighins_per_week']} weigh-ins) in a row; the history has {len(run)}"}
    run.reverse()
    window = [(run[0][0] + n * DAY).isoformat() for n in range((run[-1][1] - run[0][0]).days + 1)]
    intake = statistics.fmean(days[d]["kcal"] for d in window)

    def week_avg(week: tuple[Date, Date]) -> float:
        return statistics.fmean(w for d, w in weights.items() if week[0].isoformat() <= d <= week[1].isoformat())

    change = week_avg(run[-1]) - week_avg(run[0])
    value = intake - change * cfg["kcal_per_kg"] / ((len(run) - 1) * 7)
    return {"value": round(value), "weeks": len(run), "start": window[0], "end": window[-1],
            "avg_intake_kcal": round(intake), "weight_change_kg": round(change, 2)}


def _unusable_days(coach: "Coach", start: Date, end: Date, cfg: dict[str, Any]) -> set[str]:
    from .features import context_notes

    out: set[str] = set()
    for note in context_notes.between(coach, start, end):
        if note["suggest_unusable"] == "yes":
            out |= _dates(max(start, Date.fromisoformat(note["applies_from"])),
                          min(end, Date.fromisoformat(note["applies_to"] or end.isoformat())))
    if cfg["exclude_glycogen_window"]:
        for row in coach.db.all("SELECT phase_id, start_date FROM phases"):
            weeks = coach.skills.params(row["phase_id"]).get("glycogen_window_weeks", 0)
            begin = Date.fromisoformat(row["start_date"])
            out |= _dates(begin, begin + (weeks * 7 - 1) * DAY)
    return out


def _dates(start: Date, end: Date) -> set[str]:
    return {(start + n * DAY).isoformat() for n in range((end - start).days + 1)}


# --- setup collection -------------------------------------------------------------


def open_setup(coach: "Coach") -> dict[str, Any] | None:
    """The setup being collected or waiting for confirm, if any."""
    row = coach.db.one(
        "SELECT * FROM phase_setups WHERE status IN ('collecting', 'pending') ORDER BY created_at DESC LIMIT 1"
    )
    return _setup(row) if row else None


def pending_setup(coach: "Coach") -> dict[str, Any] | None:
    setup = open_setup(coach)
    return setup if setup and setup["status"] == "pending" else None


def get_setup(coach: "Coach", setup_id: str) -> dict[str, Any] | None:
    row = coach.db.one("SELECT * FROM phase_setups WHERE id = ?", (setup_id,))
    return _setup(row) if row else None


def _setup(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "phase_id": row["phase_id"],
        "status": row["status"],
        "values": json.loads(row["setup_values"]),
        "preview": json.loads(row["preview"]) if row["preview"] else None,
        "preview_no": row["preview_no"],
        "turns": json.loads(row["turns"]),
        "updated_at": row["updated_at"],
    }


def prefill(coach: "Coach", phase_id: str, now: datetime.datetime) -> dict[str, Any]:
    """What code can read from the synced history, each as {value, source} or
    {value: None, missing: why}: last diet intake, starting trend weight,
    maintenance estimate."""
    today = now.date()
    yesterday = today - DAY
    p = coach.skills.params(phase_id)
    out: dict[str, Any] = {}

    first = yesterday - (INTAKE_DAYS - 1) * DAY
    logged = [d for d in history.days(coach.db, first.isoformat(), yesterday.isoformat())
              if d["logged"] and d["kcal"] is not None]
    if len(logged) >= MIN_LOGGED_DAYS:
        out["starting_calories_kcal"] = {
            "value": round(statistics.fmean(d["kcal"] for d in logged)),
            "source": f"MFP: daily average of the {len(logged)} logged days {first} to {yesterday}",
        }
    else:
        out["starting_calories_kcal"] = {
            "value": None,
            "missing": f"only {len(logged)} of the {INTAKE_DAYS} days {first} to {yesterday} are logged in MFP",
        }

    weight = trend_weight(coach, today)
    start = today - (TREND_DAYS - 1) * DAY
    if weight is not None:
        out["starting_trend_weight_kg"] = {"value": round(weight, 1),
                                           "source": f"MFP: mean of the weigh-ins {start} to {today}"}
    else:
        out["starting_trend_weight_kg"] = {
            "value": None, "missing": f"fewer than {MIN_TREND_WEIGH_INS} weigh-ins from {start} to {today}"}

    estimate = maintenance_estimate(coach, yesterday, p)
    if estimate["value"] is not None:
        out["maintenance_estimate_kcal"] = {
            "value": estimate["value"],
            "source": (f"back-calculated from {estimate['weeks']} weeks {estimate['start']} to {estimate['end']}: "
                       f"average intake {estimate['avg_intake_kcal']} kcal, weight change "
                       f"{estimate['weight_change_kg']:+} kg"),
        }
    else:
        out["maintenance_estimate_kcal"] = {"value": None, "missing": estimate["missing"]}
    return out


# --- preview -----------------------------------------------------------------------


def preview(coach: "Coach", setup: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """The week-1 preview of a complete setup (phase_setup schema): average
    daily target and the MFP goal it sets, targets by day type, macros, and
    the targets row confirm stores. Raises ValueError if the numbers don't
    work out (e.g. no room for carbs)."""
    from .features import training_plan

    p = params_for(coach.skills, setup["phase_id"], setup)
    yesterday = now.date() - DAY
    estimate = maintenance_estimate(coach, yesterday, p)
    if estimate["value"] is not None:
        window = (Date.fromisoformat(estimate["start"]), Date.fromisoformat(estimate["end"]))
    else:
        window = (yesterday - (ACTIVITY_DAYS - 1) * DAY, yesterday)
    days = [window[0] + n * DAY for n in range((window[1] - window[0]).days + 1)]
    counted = [training_plan.counted_activity_on(coach, d, p["activity"]) for d in days]
    avg_activity = statistics.fmean(c["kcal"] for c in counted)
    maintenance = setup["maintenance_estimate_kcal"]
    base = maintenance - avg_activity if setup.get("maintenance_includes_activity", True) else maintenance

    start = p["start"]
    if "week1_increase_kcal" in start:
        average = setup["starting_calories_kcal"] + setup["week1_increase_kcal"]
        surplus = average - base - avg_activity
    else:
        surplus = start.get("surplus_kcal", -start.get("deficit_kcal", 0))
        average = base + avg_activity + surplus

    runs = [e["kcal"] for d in history.days(coach.db, days[0].isoformat(), days[-1].isoformat())
            for e in d["exercises"] if e["run"] and (e["source"] or "").lower() == "strava" and e["kcal"]]
    typical_run = statistics.median(runs) * p["activity"]["run_kcal_discount"] if runs else None
    rest = base + surplus
    weight = setup["starting_trend_weight_kg"]
    at_average = macros(p, average, weight)
    if at_average["carbs_g"] < 0:
        raise ValueError("protein and fat alone exceed the average daily target; check the values")
    goal = {"kcal": round(average), "protein_g": at_average["protein_g"], "carbs_g": at_average["carbs_g"],
            "fat_g": at_average["fat_g"]}
    return {
        "phase_id": setup["phase_id"],
        "phase_name": p.get("name", setup["phase_id"]),
        "average_daily_target_kcal": round(average),
        "mfp_goal": goal,
        "daily_targets_kcal": {
            "rest": round(rest),
            "lifting": round(rest + p["activity"]["lifting_kcal_per_session"]),
            "run": round(rest + typical_run) if typical_run is not None else None,
            "wrestling": round(rest + p["activity"]["wrestling_kcal_per_session"]),
        },
        "typical_run_kcal_counted": round(typical_run) if typical_run is not None else None,
        "macros": at_average,
        "base_maintenance_kcal": round(base),
        "avg_counted_activity_kcal": round(avg_activity),
        "activity_window": {"start": days[0].isoformat(), "end": days[-1].isoformat()},
        "surplus_kcal": round(surplus),
        "glycogen_window_weeks": p.get("glycogen_window_weeks", 0),
        "glycogen_jump_kg": p.get("glycogen_jump_kg"),
        "targets": {
            "base_maintenance_kcal": base,
            "surplus_kcal": surplus,
            "avg_activity_kcal": avg_activity,
            "maintenance_estimate_kcal": maintenance,
            "avg_daily_target_kcal": average,
            "mfp_goal": goal,
        },
    }


# --- confirm hooks -------------------------------------------------------------------

ConfirmHook = Callable[["Coach", dict[str, Any], datetime.datetime], Awaitable[str | None]]
confirm_hooks: list[ConfirmHook] = []


def on_confirmed(fn: ConfirmHook) -> ConfirmHook:
    """Run `fn(coach, phase, now)` once after a phase start is confirmed (the
    phase and its targets are already stored and the card says so). A hook
    may return a line to add to the confirmation card. The MFP goal write
    (features/phase_goal.py) is one: `phase` has the new phase and
    `targets(coach)` the goal."""
    confirm_hooks.append(fn)
    return fn
