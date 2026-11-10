"""Phase start (spec, "Phase start"): "start reverse" in the chat.

- Code refuses a draft phase with values still marked TO DECIDE, listing them.
- Otherwise a setup opens and every message goes to the phase-start skill
  (with the target phase's skill in the prefix) until it is confirmed,
  cancelled ("cancel") or left idle for `IDLE`. The model gets what code read
  from the history (`phases.prefill`), the values recorded so far and what is
  still needed; it records each value with `record_setup_value` (validated
  against the phase-setup schema and the phase's params) and calls
  `start_phase` for the code-computed preview.
- Code then sends the preview card with confirm / edit buttons. Nothing is
  active until confirm; confirm claims the setup atomically, so a second tap
  does nothing. Confirm stores the phase and its targets, marks the phase's
  first change applied and runs `phases.on_confirmed` hooks (the MFP goal
  write, features/phase_goal.py); lines they return are added to the card.
- Every exercise in the Hevy history must be classified (counts / excluded,
  `classify_exercises`, features/lifts.py) before the preview; the card
  lists the classification.
- After the start, `record_setup_value` changes logistics, photos, time goal
  and waist of the active phase; calibration values need a proposal and
  start values are fixed.
"""

import datetime
import json
import logging
import re
import secrets
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .. import phases, progression
from ..ask import ToolError
from ..ports import Button, ChatTurn, ModelError
from ..registry import registry
from . import lifts, training_plan

logger = logging.getLogger("fa-coach")

SKILLS = ("phase-start",)
TOOLS = ("record_setup_value", "start_phase", "get_training_plan", "update_training_plan", "get_coach_profile",
         "get_context_notes", "classify_exercises", "get_tracked_exercises", "confirm_day")
IDLE = datetime.timedelta(hours=24)  # an idle setup stops taking over the chat ("start reverse" resumes it)
TURNS = 8
NO_ANSWER = "I don't have an answer to that."

START = re.compile(r"(?i)^\s*(?:let'?s\s+|please\s+)?start\s+(?:the\s+|a\s+)?(.+?)\s*[.!]*\s*$")
CANCEL = re.compile(r"(?i)^\s*(cancel|stop|abort)(\s+(the\s+)?(setup|phase start|start))?\s*[.!]*\s*$")
PHASE_WORDS = (("reverse", "reverse_bulk"), ("bulk", "reverse_bulk"), ("cut", "cut"), ("mainten", "maintenance"))

LOGISTICS = ("weekly_checkin", "evening_reminder_time", "max_unprompted_messages_per_day", "soft_floor_min_days")
KEYS = ("starting_calories_kcal", "starting_trend_weight_kg", "maintenance_estimate_kcal",
        "maintenance_includes_activity", "run_kcal_discount", "wrestling_kcal_per_session",
        "lifting_kcal_per_session", "fat_g_per_kg_start", "week1_increase_kcal", "time_goal_weeks",
        "photos_enabled", "waist_cm_start", "step_goal") + tuple(f"logistics.{k}" for k in LOGISTICS)
# Have a default (maintenance includes activity; the step goal from core params): never need asking.
OPTIONAL = ("maintenance_includes_activity", "step_goal")
CLASSIFY = "exercise_classification"  # not a setup value: every Hevy exercise classified (features/lifts.py)


# --- chat ------------------------------------------------------------------------


@registry.text(order=50)
async def phase_start_text(coach, text: str, now: datetime.datetime) -> bool:
    if m := START.match(text):
        phase_id = _phase_from(m.group(1))
        if phase_id is not None:
            await _start(coach, phase_id, text, now)
            return True
    setup = phases.open_setup(coach)
    if setup is None or now - datetime.datetime.fromisoformat(setup["updated_at"]) > IDLE:
        return False
    if CANCEL.match(text):
        _close(coach, setup, "cancelled", now)
        coach.say("Phase setup cancelled. Nothing was started; the values you gave are kept for next time.")
        return True
    await _converse(coach, setup, text, now)
    return True


def _phase_from(words: str) -> str | None:
    lower = words.lower()
    return next((phase_id for word, phase_id in PHASE_WORDS if word in lower), None)


async def _start(coach, phase_id: str, text: str, now: datetime.datetime) -> None:
    phase_params = coach.skills.phase_params(phase_id)
    if phase_params.get("draft"):
        undecided = coach.skills.undecided(phase_id)
        what = ("These values must be decided first: " + ", ".join(undecided) + ".") if undecided else \
            "Its values must be reviewed and the draft mark removed first."
        coach.say(f"{phase_params.get('name', phase_id)} is still a draft, so it can't start. {what}")
        return
    training_plan.ensure_seeded(coach, now)
    setup = phases.open_setup(coach)
    if setup is not None and setup["phase_id"] != phase_id:
        _close(coach, setup, "superseded", now)
        setup = None
    if setup is None:
        values = _previous_values(coach, phase_id)
        setup_id = f"s_{secrets.token_hex(4)}"
        at = now.isoformat(timespec="seconds")
        coach.db.execute(
            "INSERT INTO phase_setups (id, phase_id, status, setup_values, created_at, updated_at)"
            " VALUES (?, ?, 'collecting', ?, ?, ?)",
            (setup_id, phase_id, json.dumps(values), at, at),
        )
        setup = phases.get_setup(coach, setup_id)
    await _converse(coach, setup, text, now)


def _previous_values(coach, phase_id: str) -> dict[str, Any]:
    """An earlier abandoned setup of this phase keeps its values; nothing
    else is carried over without the user confirming it."""
    row = coach.db.one(
        "SELECT setup_values FROM phase_setups WHERE phase_id = ? AND status IN ('cancelled', 'superseded')"
        " ORDER BY updated_at DESC LIMIT 1",
        (phase_id,),
    )
    return json.loads(row["setup_values"]) if row else {}


def _close(coach, setup: dict[str, Any], status: str, now: datetime.datetime) -> None:
    coach.db.execute(
        "UPDATE phase_setups SET status = ?, updated_at = ? WHERE id = ? AND status IN ('collecting', 'pending')",
        (status, now.isoformat(timespec="seconds"), setup["id"]),
    )
    if setup["status"] == "pending":
        _retire_card(coach, setup, "Not started: this setup was " + status + ".")


async def _converse(coach, setup: dict[str, Any], text: str, now: datetime.datetime) -> None:
    history = [ChatTurn(t["role"], t["text"]) for t in setup["turns"]]
    try:
        answer = await coach.ask(SKILLS, {"message": text, "setup": setup_state(coach, setup, now)}, tools=TOOLS,
                                 history=history, phase=setup["phase_id"], now=now)
    except ModelError as exc:
        coach.say(f"⚠️ The coach model can't be reached right now ({exc}). Try again later.")
        return
    previewed = any(c.name == "start_phase" and not c.is_error for c in answer.calls)
    if answer.text:
        coach.say(answer.text)
    pending = phases.pending_setup(coach)
    if previewed and pending is not None and pending["id"] == setup["id"]:
        _send_card(coach, pending)
    elif not answer.text:
        coach.say(NO_ANSWER)
    turns = setup["turns"] + [{"role": "user", "text": text}, {"role": "assistant", "text": answer.text or "(preview)"}]
    coach.db.execute("UPDATE phase_setups SET turns = ?, updated_at = ? WHERE id = ?",
                     (json.dumps(turns[-TURNS:]), now.isoformat(timespec="seconds"), setup["id"]))


def setup_state(coach, setup: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """What the phase-start skill gets: values recorded, what's still needed,
    what code read from the history, the Hevy exercises with their
    classification and the limits values must respect."""
    p = coach.skills.params(setup["phase_id"])
    current = phases.active(coach)
    return {
        "phase_id": setup["phase_id"],
        "phase_name": p.get("name"),
        "status": setup["status"],
        "recorded": _flat(setup["values"]),
        "still_needed": still_needed(coach, setup["phase_id"], setup["values"], now.date()),
        "prefill": phases.prefill(coach, setup["phase_id"], now),
        "exercises": progression.exercises(coach, lifts.history_start(now.date()), now.date()),
        "plan_exercise_lists": {name: [i["text"] for i in items]
                                for name, items in training_plan.exercise_lists(coach, now.date()).items()},
        "limits": _limits(p),
        "current_phase": None if current is None else {"phase_id": current["phase_id"],
                                                       "start_date": current["start_date"]},
        "previous_phase_setup": _flat(phases.latest(coach)["setup"]) if phases.latest(coach) else None,
    }


def _limits(p: dict[str, Any]) -> dict[str, Any]:
    limits = {"fat_g_per_kg_start": [p["macros"]["fat_g_per_kg_min"], p["macros"]["fat_g_per_kg_max"]],
              "run_kcal_discount": "more than 0, at most 1"}
    if "week1_increase_kcal" in p["start"]:
        limits["week1_increase_kcal"] = p["start"]["week1_increase_kcal"]
    return limits


def _flat(values: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in values.items() if k != "logistics"}
    out.update({f"logistics.{k}": v for k, v in (values.get("logistics") or {}).items()})
    return out


def still_needed(coach, phase_id: str, values: dict[str, Any], today: datetime.date) -> list[str]:
    """Setup keys not recorded yet, plus `exercise_classification` while an
    exercise in the Hevy history isn't classified (`classify_exercises`)."""
    recorded = _flat(values)
    uses_increase = "week1_increase_kcal" in coach.skills.params(phase_id)["start"]
    unclassified = progression.unclassified(coach, lifts.history_start(today), today)
    return ([CLASSIFY] if unclassified else []) + [
        k for k in KEYS if k not in recorded and k not in OPTIONAL and (k != "week1_increase_kcal" or uses_increase)]


# --- tools -----------------------------------------------------------------------


@registry.tool(
    "record_setup_value",
    "Store one phase setup value as soon as the user gives or confirms it (validated by code against the "
    "phase-setup schema and the phase's params). Logistics keys: logistics.weekly_checkin ('sun 18:00'), "
    "logistics.evening_reminder_time ('20:30'), logistics.max_unprompted_messages_per_day, "
    "logistics.soft_floor_min_days. step_goal (default 10,000 steps: where step kcal are 0; it doesn't change "
    "the energy the user gets). Optional values the user declines are recorded as null. After the phase "
    "started, changes logistics, photos_enabled, time_goal_weeks, waist_cm_start and step_goal of the active "
    "phase. "
    "Returns what is still needed (exercise_classification: classify the exercises with classify_exercises).",
    {
        "type": "object",
        "properties": {"key": {"enum": list(KEYS)}, "value": {}},
        "required": ["key", "value"],
        "additionalProperties": False,
    },
)
async def record_setup_value(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    key, value = args["key"], args["value"]
    setup = phases.open_setup(coach)
    if setup is None:
        return _change_active_phase(coach, key, value, now)
    problems = validate_value(coach, setup["phase_id"], key, value)
    if problems:
        raise ToolError(f"{key}: " + "; ".join(problems))
    values = _with(setup["values"], key, value)
    with coach.db.transaction():
        coach.db.execute(
            "UPDATE phase_setups SET setup_values = ?, status = 'collecting', updated_at = ? WHERE id = ?",
            (json.dumps(values), now.isoformat(timespec="seconds"), setup["id"]),
        )
    if setup["status"] == "pending":
        _retire_card(coach, setup, "Out of date: a value changed after this preview. Nothing was started.")
    return {"recorded": {key: value}, "still_needed": still_needed(coach, setup["phase_id"], values, now.date())}


def _change_active_phase(coach, key: str, value: Any, now: datetime.datetime) -> dict[str, Any]:
    phase = phases.active(coach)
    if phase is None:
        raise ToolError("no phase setup is open and no phase is active; the user starts one with 'start reverse'")
    if key in phases.CALIBRATION_KEYS:
        raise ToolError(f"{key} is a calibration value: during a phase it changes only through a proposal")
    if key in phases.START_KEYS:
        raise ToolError(f"{key} defines the phase start and is fixed for this phase")
    problems = validate_value(coach, phase["phase_id"], key, value)
    setup = _with(phase["setup"], key, value)
    problems += coach.skills.errors(setup, "phase_setup")
    if problems:
        raise ToolError(f"{key}: " + "; ".join(problems))
    coach.db.execute("UPDATE phases SET setup = ? WHERE id = ?", (json.dumps(setup), phase["id"]))
    return {"updated": {key: value}, "phase_id": phase["phase_id"]}


def _with(values: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    out = json.loads(json.dumps(values))
    if key.startswith("logistics."):
        out.setdefault("logistics", {})[key.split(".", 1)[1]] = value
    else:
        out[key] = value
    return out


def validate_value(coach, phase_id: str, key: str, value: Any) -> list[str]:
    schema = coach.skills.schema("phase_setup")["properties"]
    if key.startswith("logistics."):
        subschema = schema["logistics"]["properties"][key.split(".", 1)[1]]
    else:
        subschema = schema[key]
    problems = [e.message for e in Draft202012Validator(subschema, format_checker=FormatChecker()).iter_errors(value)]
    if problems:
        return problems
    p = coach.skills.params(phase_id)
    if key == "fat_g_per_kg_start":
        low, high = p["macros"]["fat_g_per_kg_min"], p["macros"]["fat_g_per_kg_max"]
        if value < low or (high is not None and value > high):
            problems.append(f"must be within {low}..{high} g/kg for this phase")
    if key == "week1_increase_kcal":
        bounds = p["start"].get("week1_increase_kcal")
        if bounds is None:
            problems.append("this phase has no week-1 increase")
        elif value is None or not bounds[0] <= value <= bounds[1]:
            problems.append(f"must be within {bounds[0]}..{bounds[1]} kcal")
    return problems


@registry.tool(
    "start_phase",
    "When every setup value is recorded: code validates the setup, stores it as pending and returns the "
    "week-1 preview (average daily target, the MyFitnessPal goal it will set, daily targets on rest / lifting / "
    "run / wrestling days, macros). Code then sends the preview card with the numbers, the glycogen-window note "
    "and confirm / edit buttons right after your reply. Nothing starts until the user taps confirm.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def start_phase(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    setup = phases.open_setup(coach)
    if setup is None:
        raise ToolError("no phase setup is open; the user starts one with 'start reverse'")
    missing = still_needed(coach, setup["phase_id"], setup["values"], now.date())
    if missing:
        raise ToolError("still needed: " + ", ".join(missing))
    full = _full_setup(setup, now.date())
    problems = coach.skills.errors(full, "phase_setup")
    if problems:
        raise ToolError("invalid setup: " + "; ".join(problems))
    try:
        result = phases.preview(coach, full, now)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    result["exercises"] = [{"name": e["title"], "classification": e["classification"]}
                           for e in progression.exercises(coach, lifts.history_start(now.date()), now.date())]
    with coach.db.transaction():
        coach.db.execute(
            "UPDATE phase_setups SET status = 'pending', preview = ?, preview_no = preview_no + 1, updated_at = ?"
            " WHERE id = ?",
            (json.dumps({"setup": full, **result}), now.isoformat(timespec="seconds"), setup["id"]),
        )
    if setup["status"] == "pending":
        _retire_card(coach, setup, "Replaced by a newer preview. Nothing was started.")
    return {k: v for k, v in result.items() if k != "targets"}


def _full_setup(setup: dict[str, Any], today: datetime.date) -> dict[str, Any]:
    values = setup["values"]
    return {
        "phase_id": setup["phase_id"],
        "start_date": today.isoformat(),
        "training_plan_source": "saved_plan",
        "maintenance_includes_activity": values.get("maintenance_includes_activity", True),
        **values,
    }


@registry.tool(
    "get_targets",
    "The active phase (phase week, glycogen window) and its current targets: base maintenance, surplus, expected "
    "counted activity, average daily target, MyFitnessPal goal; plus this week's daily targets with counted "
    "activity and macros.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_targets(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    phase = phases.active(coach)
    if phase is None:
        return {"phase": None, "note": "no active phase; targets start when the user confirms a phase start"}
    today = now.date()
    monday = today - datetime.timedelta(days=today.weekday())
    week = [phases.daily_target(coach, monday + datetime.timedelta(days=n)) for n in range(7)]
    return {
        "phase": _phase_state(coach, phase, today),
        "targets": phases.targets(coach, today),
        "this_week": [{"date": d["date"], "kcal": d["kcal"], "macros": d["macros"],
                       "counted_activity": [{k: s[k] for k in ("type", "status", "kcal_counted")}
                                            for s in d["activity"]["sessions"]]}
                      for d in week if d is not None],
    }


def _phase_state(coach, phase: dict[str, Any], today: datetime.date) -> dict[str, Any]:
    return {"phase_id": phase["phase_id"], "start_date": phase["start_date"],
            "phase_week": phases.phase_week(phase, today), "in_glycogen_window": phases.in_glycogen_window(coach, today)}


@registry.state("phase")
def phase_state(coach, now: datetime.datetime) -> dict[str, Any] | None:
    phase = phases.active(coach)
    return _phase_state(coach, phase, now.date()) if phase else None


# --- the preview card and its buttons ------------------------------------------------


def _ref(setup: dict[str, Any]) -> str:
    return f"phase-start:{setup['id']}:{setup['preview_no']}"


def _send_card(coach, setup: dict[str, Any]) -> None:
    ref_id = f"{setup['id']}.{setup['preview_no']}"
    buttons = ((Button("✅ Confirm", "confirm_phase_start", ref_id), Button("✏️ Edit", "edit_phase_start", ref_id)),)
    coach.say(render_card(setup["preview"]) + "\n\nNothing changes until you tap Confirm.", buttons, ref=_ref(setup))


def _retire_card(coach, setup: dict[str, Any], why: str) -> None:
    if setup["preview"] is not None:
        coach.edit(_ref(setup), f"{render_card(setup['preview'])}\n\n{why}")


def render_card(preview: dict[str, Any]) -> str:
    goal, days, m = preview["mfp_goal"], preview["daily_targets_kcal"], preview["macros"]
    run = f"{days['run']:,} kcal (typical run)" if days["run"] is not None else "rest day + the synced run's kcal"
    lines = [
        f"Week-1 preview: {preview['phase_name']}",
        f"Average daily target: {preview['average_daily_target_kcal']:,} kcal",
        f"MyFitnessPal goal: {goal['kcal']:,} kcal · P {goal['protein_g']} g · C {goal['carbs_g']} g · "
        f"F {goal['fat_g']} g (a rest day; activity comes on top: add it in your head in MyFitnessPal, "
        "the coach counts it exactly in each day's target)",
        "Daily targets:",
        f"- Rest day: {days['rest']:,} kcal",
        f"- Lifting day: {days['lifting']:,} kcal",
        f"- Run day: {run}",
        f"- Wrestling day: {days['wrestling']:,} kcal",
        f"Macros: protein {m['protein_g']} g ({m['protein_g_per_kg']} g/kg), fat {m['fat_g']} g "
        f"({m['fat_g_per_kg']} g/kg) at {m['reference_weight_kg']} kg trend weight; carbs take the rest.",
        f"Each day: base maintenance {preview['base_maintenance_kcal']:,} kcal + that day's counted activity "
        f"{preview['surplus_kcal']:+,} kcal surplus.",
    ]
    steps = preview.get("steps") or {}
    if steps.get("kcal_per_1000_steps") is not None:
        lines.append(
            f"Steps: base at your step goal ({steps['step_goal']:,} steps) is {steps['base_at_step_goal_kcal']:,} "
            f"kcal; each day moves {steps['kcal_per_1000_steps']:g} kcal per 1,000 steps above or below it (run "
            f"steps left out). The targets above are at your average {steps['avg_day_steps']:,} steps.")
    weeks, jump = preview["glycogen_window_weeks"], preview.get("glycogen_jump_kg")
    if weeks:
        span = "Week 1" if weeks == 1 else f"Weeks 1–{weeks}"
        size = f"about {_num(jump[0])}–{_num(jump[1])} kg " if jump else ""
        lines.append(f"{span}: glycogen window. Expect an early jump of {size}from glycogen and water, not fat. "
                     "No weight-based decisions until it's over.")
    exercises = preview.get("exercises") or []
    for label, cls in (("Lifts that count for progression", "counts"), ("Excluded (logged, PRs named)", "excluded")):
        names = [e["name"] for e in exercises if (e["classification"] or "counts") == cls]
        if names:
            lines.append(f"{label}: {', '.join(names)}.")
    return "\n".join(lines)


def _num(x: float) -> str:
    return f"{x:g}"


def _parse_ref(ref_id: str) -> tuple[str, int] | None:
    setup_id, _, number = ref_id.rpartition(".")
    return (setup_id, int(number)) if setup_id and number.isdigit() else None


@registry.button("confirm_phase_start")
async def confirm_phase_start(coach, ref_id: str, now: datetime.datetime) -> None:
    parsed = _parse_ref(ref_id)
    if parsed is None:
        return
    setup_id, number = parsed
    claimed = coach.db.execute(
        "UPDATE phase_setups SET status = 'confirming', updated_at = ? WHERE id = ? AND status = 'pending'"
        " AND preview_no = ?",
        (now.isoformat(timespec="seconds"), setup_id, number),
    ).rowcount == 1
    setup = phases.get_setup(coach, setup_id)
    if not claimed:
        return  # a second tap, or a card already replaced (its buttons were removed then)
    stored = setup["preview"]
    full = {**stored["setup"], "start_date": now.date().isoformat()}
    phase_row_id = f"p_{secrets.token_hex(4)}"
    at = now.isoformat(timespec="seconds")
    with coach.db.transaction():
        coach.db.execute("UPDATE phases SET status = 'ended', ended_at = ? WHERE status = 'active'", (at,))
        coach.db.execute(
            "INSERT INTO phases (id, phase_id, setup_id, status, start_date, setup, first_change_applied_at,"
            " started_at) VALUES (?, ?, ?, 'active', ?, ?, ?, ?)",
            (phase_row_id, setup["phase_id"], setup_id, full["start_date"], json.dumps(full), at, at),
        )
        phases.set_targets(coach, phase_row_id, stored["targets"], valid_from=now.date(), source="phase_start",
                           now=now)
        coach.db.execute("UPDATE phase_setups SET status = 'confirmed', confirmed_at = ? WHERE id = ?", (at, setup_id))
    started = f"{render_card(stored)}\n\n✅ Started {full['start_date']}. These targets apply from today."
    coach.edit(_ref(setup), started)
    phase = phases.active(coach)
    lines = []
    for hook in phases.confirm_hooks:
        try:
            line = await hook(coach, phase, now)
        except Exception:
            logger.exception("phase confirm hook %s failed", getattr(hook, "__name__", hook))
            continue
        if line:
            lines.append(line)
    if lines:
        coach.edit(_ref(setup), "\n".join([started, *lines]))


@registry.button("edit_phase_start")
async def edit_phase_start(coach, ref_id: str, now: datetime.datetime) -> None:
    parsed = _parse_ref(ref_id)
    if parsed is None:
        return
    setup_id, number = parsed
    claimed = coach.db.execute(
        "UPDATE phase_setups SET status = 'collecting', updated_at = ? WHERE id = ? AND status = 'pending'"
        " AND preview_no = ?",
        (now.isoformat(timespec="seconds"), setup_id, number),
    ).rowcount == 1
    if not claimed:
        return
    setup = phases.get_setup(coach, setup_id)
    coach.edit(_ref(setup), f"{render_card(setup['preview'])}\n\n✏️ Editing. Nothing was started.")
    coach.say("What should change?")
