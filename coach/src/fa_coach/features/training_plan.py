"""The training plan and counted activity (spec, "Training plan").

- The plan is seeded once, on first start, from `SEED_CSV` (the export of the
  user's sheet: a week grid of sessions with times and optional runs, above
  per-session exercise lists). After that it lives in the database and changes
  only through the chat; the CSV is never read again.
- Lasting changes (`update_training_plan`) add a plan version valid from a
  date, so past days keep the plan they had. Single days (`set_session_status`)
  get a planned session skipped or done, or an extra session; its kcal are
  the user's, or estimated (`session_kcal.resolve`).
- `counted_activity(...)` turns one day's plan, synced data and reports into
  the kcal that day's sessions add to its daily target (planned wrestling
  only from the phase start on; before it only synced and reported sessions);
  `counted_activity_on(coach, day, params)` loads those inputs from the database.

Read API for other features: `plan_for(coach, day)`, `statuses(coach, day)`,
`exercise_lists(coach)`, `counted_activity`, `counted_activity_on`.
"""

import csv
import datetime
import io
import json
import logging
import re
import secrets
from pathlib import Path
from typing import Any

from .. import history, phases
from ..ask import ToolError
from ..registry import registry
from . import session_kcal

logger = logging.getLogger("fa-coach")

SEED_CSV = Path(__file__).resolve().parents[3] / "data" / "training_plan.csv"
SEED_VALID_FROM = "0001-01-01"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
TYPES = ("lift", "run", "wrestling", "other")
TIME_PATTERN = r"^(([01][0-9]|2[0-3]):[0-5][0-9]|morning|midday|afternoon|evening)$"
GRID_GAP_ROWS = 3  # this many blank rows end the week grid; the exercise lists follow
MAX_KCAL = 3000
SETUP_KCAL = {"wrestling": "wrestling_kcal_per_session", "lift": "lifting_kcal_per_session"}

Date = datetime.date


# --- parsing the sheet export --------------------------------------------------


def parse_csv(text: str) -> dict[str, Any]:
    """The sheet export as a plan. The row starting with "Monday" heads the
    week grid (columns Monday..Sunday); each filled cell below it is a session
    ("06:30 - Pull", "Mid day: Legs", "opt easy run") until a gap of blank
    rows; the next filled row names the exercise lists, one per column."""
    rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text))]
    header = next((i for i, row in enumerate(rows) if row and row[0].lower() == "monday"), None)
    if header is None:
        raise ValueError("no row starting with Monday")
    days: dict[str, list[dict[str, Any]]] = {day: [] for day in WEEKDAYS}
    i, blanks = header + 1, 0
    while i < len(rows) and blanks < GRID_GAP_ROWS:
        row = rows[i]
        i += 1
        if not any(row):
            blanks += 1
            continue
        blanks = 0
        for col, cell in enumerate(row[: len(WEEKDAYS)]):
            if cell:
                days[WEEKDAYS[col]].append(_session(cell))
    rest = [row for row in rows[i:]]
    lists: dict[str, list[dict[str, Any]]] = {}
    start = next((j for j, row in enumerate(rest) if any(row)), None)
    if start is not None:
        for col, name in enumerate(rest[start]):
            if name:
                lists[name] = [_exercise(row[col]) for row in rest[start + 1 :] if col < len(row) and row[col]]
    return _with_ids({"days": days, "exercise_lists": lists})


def _session(cell: str) -> dict[str, Any]:
    optional = False
    text = cell
    if m := re.match(r"(?i)^opt(?:ional)?\.?\s+(.+)$", text):
        optional, text = True, m.group(1)
    time = None
    if m := re.match(r"^(\d{1,2}):(\d{2})\s*[-–:]\s*(.+)$", text):
        time, text = f"{int(m.group(1)):02d}:{m.group(2)}", m.group(3)
    elif m := re.match(r"(?i)^(morning|mid ?day|noon|afternoon|evening)\s*:\s*(.+)$", text):
        label = m.group(1).lower().replace(" ", "")
        time, text = ("midday" if label == "noon" else label), m.group(2)
    name = text.strip()
    name = name[:1].upper() + name[1:]
    return {"time": time, "name": name, "type": _type(name), "optional": optional}


def _type(name: str) -> str:
    lower = name.lower()
    if re.search(r"\brun", lower) or "jog" in lower:
        return "run"
    if "wrestl" in lower:
        return "wrestling"
    if re.search(r"\b(pull|push|legs?|upper|lower|full ?body|lift(ing)?|gym|strength)\b", lower):
        return "lift"
    return "other"


def _exercise(text: str) -> dict[str, Any]:
    """"(Chest Press)" is optional; "A / B" and "A and/or B" are alternatives
    ("KB/Cable" without spaces is one name)."""
    optional = text.startswith("(") and text.endswith(")")
    body = text[1:-1].strip() if optional else text
    names = [n.strip() for n in re.split(r"\s+/\s+|\s+and/or\s+", body) if n.strip()]
    return {"text": text, "names": names, "optional": optional}


def _with_ids(plan: dict[str, Any]) -> dict[str, Any]:
    """Session ids are the weekday and position, e.g. "fri-1"."""
    for day, sessions in plan["days"].items():
        for n, session in enumerate(sessions, start=1):
            session["id"] = f"{day[:3]}-{n}"
    return plan


# --- the saved plan ------------------------------------------------------------


def ensure_seeded(coach, now: datetime.datetime) -> bool:
    """Seed the plan from the CSV unless a plan exists. False when there is
    still no plan (CSV missing or unreadable)."""
    if coach.db.value("SELECT 1 FROM training_plan LIMIT 1"):
        return True
    try:
        plan = parse_csv(SEED_CSV.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        logger.warning("training plan not seeded from %s: %s", SEED_CSV, exc)
        return False
    with coach.db.transaction():
        if not coach.db.value("SELECT 1 FROM training_plan LIMIT 1"):
            _store(coach, plan, SEED_VALID_FROM, "seed", now)
    return True


def _store(coach, plan: dict[str, Any], valid_from: str, source: str, now: datetime.datetime) -> None:
    coach.db.execute(
        "INSERT INTO training_plan (valid_from, source, plan, created_at) VALUES (?, ?, ?, ?)",
        (valid_from, source, json.dumps(plan), now.isoformat(timespec="seconds")),
    )


def _version(coach, day: Date) -> dict[str, Any] | None:
    row = coach.db.one(
        "SELECT valid_from, source, plan FROM training_plan WHERE valid_from <= ? ORDER BY valid_from DESC, id DESC LIMIT 1",
        (day.isoformat(),),
    )
    if row is None:
        return None
    return {"valid_from": None if row["source"] == "seed" else row["valid_from"], "plan": json.loads(row["plan"])}


def plan_for(coach, day: Date) -> dict[str, Any] | None:
    """The plan in force on `day`: {days: {weekday: [session]}, exercise_lists},
    a session being {id, time, name, type, optional}. None without a plan."""
    ensure_seeded(coach, coach.clock.now())
    version = _version(coach, day)
    return version["plan"] if version else None


def exercise_lists(coach, day: Date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Exercise lists per session ({text, names, optional} items), for offering
    tracked lifts by name."""
    plan = plan_for(coach, day or coach.clock.now().date())
    return plan["exercise_lists"] if plan else {}


def statuses(coach, day: Date) -> list[dict[str, Any]]:
    """The user's reports for `day`: planned sessions skipped or done, extras."""
    rows = coach.db.all(
        "SELECT id, session_id, status, type, name, kcal, kcal_source, activity, duration_min, met, trend_weight_kg"
        " FROM session_statuses WHERE date = ? ORDER BY created_at, id",
        (day.isoformat(),),
    )
    return [dict(row) for row in rows]


def _week_dates(today: Date) -> list[Date]:
    monday = today - datetime.timedelta(days=today.weekday())
    return [monday + datetime.timedelta(days=n) for n in range(7)]


def _day_view(coach, day: Date) -> dict[str, Any]:
    plan = plan_for(coach, day)
    reported = statuses(coach, day)
    by_session = {s["session_id"]: s for s in reported if s["session_id"]}
    sessions = []
    for session in plan["days"][WEEKDAYS[day.weekday()]] if plan else []:
        status = by_session.get(session["id"])
        sessions.append({**session, "status": status["status"] if status else None,
                         "kcal": status["kcal"] if status else None,
                         "kcal_source": status["kcal_source"] if status else None})
    extras = [
        {"extra_id": s["id"], "type": s["type"], "name": s["name"], "kcal": s["kcal"], "kcal_source": s["kcal_source"]}
        for s in reported
        if s["status"] == "extra"
    ]
    return {"date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()], "sessions": sessions, "extras": extras}


def _require_plan(coach, now: datetime.datetime) -> None:
    if not ensure_seeded(coach, now):
        raise ToolError("no training plan is saved yet (the plan file couldn't be read); tell the user")


# --- counted activity ----------------------------------------------------------


def counted_activity(
    day: Date,
    plan: dict[str, Any] | None,
    synced: dict[str, Any],
    statuses: list[dict[str, Any]],
    params: dict[str, Any],
    *,
    count_planned: bool = True,
) -> dict[str, Any]:
    """The kcal that `day`'s sessions add to its daily target.

    - `plan`: the plan in force that day (`plan_for`).
    - `synced`: {"exercises": MFP exercise entries of the day (as in
      `history.days`), "lift_sessions": Hevy sessions of the day}.
    - `statuses`: the user's reports for the day (`statuses`).
    - `params`: run_kcal_discount, wrestling_kcal_per_session,
      lifting_kcal_per_session (a needed one missing raises ValueError).

    Rules: a run counts when Strava synced it (kcal x run discount), or when the
    user marked a planned run done with its kcal and Strava has no run that
    day. HealthKit entries (copies of runs, "Strength training") never count.
    Each Hevy session counts lifting_kcal_per_session; a planned lift marked
    done with no Hevy session that day counts the same. Planned wrestling counts
    unless reported skipped, but only with `count_planned` (days from the
    active phase's start on); before that only a wrestling session reported
    done counts. Extras count with their reported kcal (runs
    discounted); a wrestling or lifting extra without kcal counts its setup
    value. Reported kcal may be the user's, code's estimate or the model's
    (`kcal_source`); all count alike. Optional sessions that didn't happen
    count nothing.

    Returns {date, kcal, sessions, types}: `sessions` in the weekly-facts
    session shape (type, source, status done/planned/skipped, kcal_counted,
    note), skipped planned sessions included at 0; `types` = the counted
    session types (empty on a rest day).
    """

    def param(key: str) -> float:
        value = params.get(key)
        if value is None:
            raise ValueError(f"{key} is not set")
        return value

    def add(type_: str, source: str, status: str, kcal: float, note: str | None) -> None:
        sessions.append({"date": day.isoformat(), "type": type_, "source": source, "status": status,
                         "kcal_counted": round(kcal, 2), "note": note})

    sessions: list[dict[str, Any]] = []
    strava = [e for e in synced.get("exercises", []) if e.get("run") and (e.get("source") or "").lower() == "strava"]
    lifts = synced.get("lift_sessions", [])
    for entry in strava:
        add("run", "strava", "done", (entry.get("kcal") or 0) * param("run_kcal_discount"), entry.get("name"))
    for lift in lifts:
        add("lift", "training_log", "done", param("lifting_kcal_per_session"), lift.get("name"))
    reported = {s["session_id"]: s for s in statuses if s.get("session_id")}
    for planned in plan["days"][WEEKDAYS[day.weekday()]] if plan else []:
        report = reported.get(planned["id"])
        status = report["status"] if report else None
        kind, name = planned["type"], planned["name"]
        if status == "skipped":
            add(kind, "plan", "skipped", 0, name)
        elif kind == "wrestling" and (status == "done" or count_planned):
            add(kind, "plan", "done" if status == "done" else "planned", param("wrestling_kcal_per_session"), name)
        elif kind == "wrestling":
            continue  # before the phase start only synced and reported sessions count
        elif status != "done":
            continue  # runs and lifts count when they sync; optional ones that didn't happen count nothing
        elif kind == "lift" and not lifts:
            add(kind, "manual", "done", param("lifting_kcal_per_session"), name)
        elif kind == "run" and not strava and report["kcal"] is not None:
            add(kind, "manual", "done", report["kcal"] * param("run_kcal_discount"), name)
        elif kind == "other" and report["kcal"] is not None:
            add(kind, "manual", "done", report["kcal"], name)
    for extra in (s for s in statuses if s["status"] == "extra"):
        if extra["kcal"] is None and extra["type"] in SETUP_KCAL:
            kcal = param(SETUP_KCAL[extra["type"]])
        else:
            kcal = (extra["kcal"] or 0) * (param("run_kcal_discount") if extra["type"] == "run" else 1)
        add(extra["type"], "manual", "done", kcal, extra.get("name"))
    counted = [s for s in sessions if s["status"] != "skipped"]
    total = round(sum(s["kcal_counted"] for s in counted), 2)
    return {"date": day.isoformat(), "kcal": total, "sessions": sessions,
            "types": sorted({s["type"] for s in counted}, key=TYPES.index)}


_PHASE_START = object()


def counted_activity_on(coach, day: Date, params: dict[str, Any], *,
                        planned_from: Any = _PHASE_START) -> dict[str, Any]:
    """`counted_activity` for `day` with the plan, synced data and reports
    from the database. Planned (unreported) wrestling counts only on days
    from `planned_from` on: by default the active phase's start date; None
    (no phase) counts none. The phase-start preview passes the new phase's
    start."""
    if planned_from is _PHASE_START:
        phase = phases.active(coach)
        planned_from = Date.fromisoformat(phase["start_date"]) if phase else None
    iso = day.isoformat()
    mfp = history.days(coach.db, iso, iso)
    synced = {"exercises": mfp[0]["exercises"] if mfp else [], "lift_sessions": history.sessions(coach.db, iso, iso)}
    return counted_activity(day, plan_for(coach, day), synced, statuses(coach, day), params,
                            count_planned=planned_from is not None and day >= planned_from)


@registry.job("training-plan-seed", order=0)
async def seed_job(coach, now: datetime.datetime) -> None:
    ensure_seeded(coach, now)


# --- chat tools ----------------------------------------------------------------


@registry.tool(
    "get_training_plan",
    "The saved training plan in force today (sessions per weekday with id, time, name, type, optional; exercise "
    "lists per session) and this week day by day with what the user reported (status skipped/done, extras). "
    "`upcoming` lists lasting changes that start later.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_training_plan(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    _require_plan(coach, now)
    today = now.date()
    version = _version(coach, today)
    upcoming = [
        {"valid_from": row["valid_from"]}
        for row in coach.db.all(
            "SELECT DISTINCT valid_from FROM training_plan WHERE valid_from > ? ORDER BY valid_from",
            (today.isoformat(),),
        )
    ]
    return {
        "plan": {"valid_from": version["valid_from"], **version["plan"]},
        "this_week": [_day_view(coach, day) for day in _week_dates(today)],
        "upcoming": upcoming,
    }


_SESSION_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 40},
        "type": {"enum": list(TYPES)},
        "time": {"type": ["string", "null"], "pattern": TIME_PATTERN},
        "optional": {"type": "boolean"},
    },
    "required": ["name", "type"],
    "additionalProperties": False,
}


@registry.tool(
    "update_training_plan",
    "A lasting change to the saved plan (\"wrestling moves to Thursday from now on\"). `days` replaces the whole "
    "session list of each weekday given (send every session that day keeps; [] = rest day); other days stay. "
    "Session: name, type (lift/run/wrestling/other), time (HH:MM, morning, midday, afternoon, evening or null), "
    "optional (true for sessions that may not happen, e.g. an optional easy run). `exercise_lists` replaces the "
    "list of each session named (items as written, \"(X)\" = optional, \"A / B\" = alternatives; null removes "
    "it). `from`: first day it applies (default today; this week at the earliest). For one day only, use "
    "set_session_status instead. Returns the new plan; confirm the change in one line.",
    {
        "type": "object",
        "properties": {
            "days": {
                "type": "object",
                "propertyNames": {"enum": list(WEEKDAYS)},
                "additionalProperties": {"type": "array", "maxItems": 6, "items": _SESSION_SCHEMA},
            },
            "exercise_lists": {
                "type": "object",
                "propertyNames": {"minLength": 1, "maxLength": 40},
                "additionalProperties": {
                    "type": ["array", "null"],
                    "maxItems": 30,
                    "items": {"type": "string", "minLength": 1, "maxLength": 80},
                },
            },
            "from": {"type": "string", "format": "date"},
        },
        "anyOf": [{"required": ["days"]}, {"required": ["exercise_lists"]}],
        "additionalProperties": False,
    },
)
async def update_training_plan(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    _require_plan(coach, now)
    today = now.date()
    start = Date.fromisoformat(args["from"]) if "from" in args else today
    if start < _week_dates(today)[0]:
        raise ToolError("a lasting change starts this week at the earliest; past weeks keep their plan")
    plan = plan_for(coach, start)
    for day, sessions in args.get("days", {}).items():
        plan["days"][day] = [
            {"time": s.get("time"), "name": s["name"].strip(), "type": s["type"], "optional": s.get("optional", False)}
            for s in sessions
        ]
    for name, items in args.get("exercise_lists", {}).items():
        if items is None:
            plan["exercise_lists"].pop(name.strip(), None)
        else:
            plan["exercise_lists"][name.strip()] = [_exercise(item.strip()) for item in items]
    plan = _with_ids(plan)
    with coach.db.transaction():
        _store(coach, plan, start.isoformat(), "chat", now)
    changed = sorted(args.get("days", {}), key=WEEKDAYS.index)
    return {"plan": {"valid_from": start.isoformat(), **plan}, "changed_days": changed}


@registry.tool(
    "set_session_status",
    "Report one day of this week (or last week, for late reports): a planned session `skipped` or `done` "
    "(`session_id` from get_training_plan, e.g. \"fri-1\"), an `extra` session (`type`, short `name`), or `clear` "
    "to undo a report (`session_id`, or `extra_id` of an extra). "
    "kcal for done and extra sessions: `kcal` only as the user gives it (always wins); otherwise `activity` (a key "
    "of the core param `activity.met_by_activity`, e.g. running, cycling, football, martial_arts, or the user's "
    "word) + `duration_min`, and code estimates. Only when code says it can't (unknown activity, no trend weight) "
    "pass your own `kcal_estimate`. A missing duration: ask once, or pass it if the description makes it obvious. "
    "Wrestling and lifting without the user's kcal count their setup values per session. "
    "Counting: runs and lifting count on their own when they sync (Strava, Hevy), so don't add those as extras; "
    "a planned run marked done counts its kcal only if it won't sync. Wrestling counts as planned unless "
    "skipped. Optional sessions that didn't happen need no report. Returns that day and `reported` (kcal, "
    "kcal_source reported/estimated/model_estimate, kcal_counted, `say`); confirm in one line with the kcal "
    "counted and whether they were estimated.",
    {
        "type": "object",
        "properties": {
            "date": {"type": "string", "format": "date"},
            "status": {"enum": ["skipped", "done", "extra", "clear"]},
            "session_id": {"type": "string"},
            "extra_id": {"type": "string"},
            "type": {"enum": list(TYPES)},
            "name": {"type": "string", "minLength": 1, "maxLength": 40},
            "kcal": {"type": "number", "minimum": 0, "maximum": MAX_KCAL},
            "activity": {"type": "string", "minLength": 1, "maxLength": 40},
            "duration_min": {"type": "number", "exclusiveMinimum": 0, "maximum": 600},
            "kcal_estimate": {"type": "number", "minimum": 0, "maximum": MAX_KCAL},
        },
        "required": ["date", "status"],
        "additionalProperties": False,
    },
)
async def set_session_status(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    _require_plan(coach, now)
    day = Date.fromisoformat(args["date"])
    this_week = _week_dates(now.date())
    if not this_week[0] - datetime.timedelta(days=7) <= day <= this_week[-1]:
        raise ToolError("sessions can be reported for this week and last week only")
    status, db, at = args["status"], coach.db, now.isoformat(timespec="seconds")
    if status == "extra":
        if "type" not in args:
            raise ToolError("an extra session needs its type")
        kcal = session_kcal.resolve(coach, args, args["type"], now, required=True)
        _insert(db, f"x_{secrets.token_hex(4)}", day, None, "extra", args["type"], args.get("name"), kcal, at)
        return {**_day_view(coach, day), "reported": _reported(coach, args["type"], kcal)}
    if status == "clear" and "extra_id" in args:
        deleted = db.execute(
            "DELETE FROM session_statuses WHERE id = ? AND date = ? AND status = 'extra'",
            (args["extra_id"], day.isoformat()),
        ).rowcount
        if deleted != 1:
            raise ToolError(f"no extra session {args['extra_id']!r} on {day}")
        return _day_view(coach, day)
    planned = {s["id"]: s for s in plan_for(coach, day)["days"][WEEKDAYS[day.weekday()]]}
    session = planned.get(args.get("session_id", ""))
    if session is None:
        options = ", ".join(f"{s['id']} ({s['name']})" for s in planned.values()) or "none; use extra"
        raise ToolError(f"give the session_id of a session planned on {WEEKDAYS[day.weekday()]} {day}: {options}")
    if status == "clear":
        db.execute("DELETE FROM session_statuses WHERE date = ? AND session_id = ?", (day.isoformat(), session["id"]))
        return _day_view(coach, day)
    if status == "skipped":
        _insert(db, f"s_{secrets.token_hex(4)}", day, session["id"], status, session["type"], session["name"], {}, at)
        return _day_view(coach, day)
    kcal = session_kcal.resolve(coach, args, session["type"], now, required=session["type"] != "run")
    _insert(db, f"s_{secrets.token_hex(4)}", day, session["id"], status, session["type"], session["name"], kcal, at)
    return {**_day_view(coach, day), "reported": _reported(coach, session["type"], kcal)}


_KCAL_COLUMNS = ("kcal", "kcal_source", "activity", "duration_min", "met", "trend_weight_kg")


def _insert(db, id_: str, day: Date, session_id: str | None, status: str, type_: str, name: str | None,
            kcal: dict[str, Any], at: str) -> None:
    """One report; a planned session's report replaces its earlier one."""
    columns = ", ".join(_KCAL_COLUMNS)
    db.execute(
        f"INSERT INTO session_statuses (id, date, session_id, status, type, name, created_at, {columns})"
        f" VALUES (?, ?, ?, ?, ?, ?, ?, {', '.join('?' * len(_KCAL_COLUMNS))})"
        " ON CONFLICT (date, session_id) WHERE session_id IS NOT NULL DO UPDATE SET"
        " status = excluded.status, created_at = excluded.created_at, "
        + ", ".join(f"{c} = excluded.{c}" for c in _KCAL_COLUMNS),
        (id_, day.isoformat(), session_id, status, type_, name, at, *(kcal.get(c) for c in _KCAL_COLUMNS)),
    )


def _reported(coach, type_: str, kcal: dict[str, Any]) -> dict[str, Any]:
    """What the confirmation line needs: the kcal, where they came from and
    what they count (null while a needed setup value isn't set yet)."""
    setup = phases.params(coach)["activity"]
    if kcal.get("kcal") is None:
        counted = setup.get(SETUP_KCAL[type_]) if type_ in SETUP_KCAL else None
    elif type_ == "run":
        discount = setup.get("run_kcal_discount")
        counted = None if discount is None else round(kcal["kcal"] * discount, 2)
    else:
        counted = kcal["kcal"]
    out = {"kcal": kcal.get("kcal"), "kcal_source": kcal.get("kcal_source"), "kcal_counted": counted,
           "say": kcal.get("say")}
    if "estimate" in kcal:
        out["estimate"] = kcal["estimate"]
    return out

