"""The weekly check-in (spec, "Weekly decision and report").

At the user's check-in time (`messaging.weekly_checkin`, e.g. "mon 09:00"),
once per week, code computes the weekly facts for the 7 days ending the day
before the check-in day (weekly_facts.py), the decision model turns them
into a verdict (weekly-decision, COACH_DECISION_MODEL), code applies its own
rules to it, stores it with the facts and rule ids, and the weekly-report
skill writes the report. Its messages are exempt from the daily message
limit (`messaging.send(..., exempt=True)`). An invalid verdict is not acted
on: the user is told the check-in failed and can run it again with /checkin.

Code's rules on the verdict:
- A week with a `sport_load` context note gives no "raise calories" and no
  "training needs a look": an increase becomes hold, the flag is dropped
  (WD-SPORT).
- In a week that counts, a verdict pointing to a change must point the way
  the trend does (increase below the band, decrease above it), else it
  becomes a hold and its proposal is dropped; a proposal gets the RB-SIZE
  step code computes (WD-GUARD, `apply_band_rules`). Holds stay unchanged.
- A week skipped for confirmation (unusable, glycogen window, adherence
  gate, sport load) carries no proposal; it neither counts nor breaks a
  streak (`weekly_facts.skip_reason`).

Hooks for later tickets:
- `report_hooks`: `fn(coach, facts, verdict, now) -> dict` merged into the
  weekly-report input (proposals: `proposal_result`, `changes_applied`).
- `report_finish_hooks`: `fn(coach, report_input, text, buttons, by_model)
  -> (text, buttons)`, run on the final report before it is sent (code
  decides the proposal buttons; `by_model` False = code's fallback text).
- Deferred items come from `messaging.deferred` (the week's days); due
  measurements from `measurements.measurements_due` (the 7 days from the check-in day).

Read API: `stored(coach, iso_week=None)`: the stored check-in (latest week
by default) with facts and verdict.
"""

import datetime
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .. import messaging, phases, proposals, weekly_facts
from ..ports import Button, Buttons, ModelError
from ..registry import registry
from . import measurements

logger = logging.getLogger("fa-coach")

Date = datetime.date
DAY = datetime.timedelta(days=1)
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DECISION_SKILLS = ("weekly-decision",)
REPORT_SKILLS = ("weekly-report",)
BUTTON_LABEL_LIMIT = 32

ReportHook = Callable[[Any, dict[str, Any], dict[str, Any], datetime.datetime], Awaitable[dict[str, Any]]]
report_hooks: list[ReportHook] = []
FinishHook = Callable[[Any, dict[str, Any], str, Buttons, bool], tuple[str, Buttons]]
report_finish_hooks: list[FinishHook] = []


# --- schedule ------------------------------------------------------------------------


def latest_moment(setting: str | None, now: datetime.datetime) -> datetime.datetime | None:
    """The most recent check-in moment at or before `now` for a setting like
    "sun 18:00"; None if it's not set."""
    if not setting:
        return None
    day, _, time = setting.strip().lower().partition(" ")
    hour, minute = (int(x) for x in time.split(":"))
    back = (now.weekday() - WEEKDAYS.index(day[:3])) % 7
    moment = datetime.datetime.combine(now.date() - back * DAY, datetime.time(hour, minute), tzinfo=now.tzinfo)
    return moment - 7 * DAY if moment > now else moment


def _due_week(coach, now: datetime.datetime) -> tuple[dict[str, Any], datetime.datetime, Date] | None:
    """(phase, check-in moment, last day of the week to evaluate), or None
    before the phase's first check-in moment."""
    phase = phases.active(coach)
    if phase is None:
        return None
    moment = latest_moment(phases.params(coach)["messaging"]["weekly_checkin"], now)
    if moment is None or moment <= datetime.datetime.fromisoformat(phase["started_at"]):
        return None
    return phase, moment, moment.date() - DAY


@registry.job("weekly-checkin", order=50)
async def weekly_job(coach, now: datetime.datetime) -> None:
    due = _due_week(coach, now)
    if due is None:
        return
    phase, moment, end = due
    if not coach.db.once(f"weekly-checkin:{phase['id']}:{end.isoformat()}", now):
        return
    await _run(coach, phase, moment, end, now)


@registry.command("checkin", "Run the weekly check-in now (if it hasn't run this week)")
async def checkin_command(coach, args: str, now: datetime.datetime) -> None:
    due = _due_week(coach, now)
    if due is None:
        coach.say("There's no weekly check-in yet: it starts with an active phase and a check-in time.")
        return
    phase, moment, end = due
    coach.db.once(f"weekly-checkin:{phase['id']}:{end.isoformat()}", now)  # the job won't run it again
    done = stored(coach, weekly_facts.iso_week(end))
    if done is not None:
        coach.say(f"The check-in for {done['iso_week']} already ran on {done['created_at'][:10]}.")
        return
    await _run(coach, phase, moment, end, now)


# --- the check-in ----------------------------------------------------------------------


async def _run(coach, phase, moment: datetime.datetime, end: Date, now: datetime.datetime) -> None:
    start = end - 6 * DAY
    if start < Date.fromisoformat(phase["start_date"]):
        nxt = moment + 7 * DAY
        _send(coach, f"No weekly check-in today: the first full week of the phase isn't over yet. "
              f"The first one comes {nxt.strftime('%A %d %b')} at {nxt.strftime('%H:%M')}.", now)
        return
    iso = weekly_facts.iso_week(end)
    facts = None
    try:
        facts = weekly_facts.compute(coach, end, now)
        problems = coach.skills.errors(facts, "weekly_facts")
        if problems:
            raise CheckinError("the weekly facts don't match their schema", problems)
        try:
            answer = await coach.ask(DECISION_SKILLS, facts, tools=(), output_schema="weekly_verdict",
                                     decision=True, now=now)
        except ModelError as exc:
            raise CheckinError(f"the decision model can't be reached ({exc})") from exc
        if answer.data is None:
            raise CheckinError("the decision model's verdict was invalid", answer.errors)
        verdict = answer.data
        mismatch = [f"{key}: {verdict[key]!r}, expected {want!r}"
                    for key, want in (("iso_week", iso), ("phase_id", phase["phase_id"])) if verdict[key] != want]
        if mismatch:
            raise CheckinError("the decision model's verdict was for another week or phase", mismatch)
    except CheckinError as exc:
        logger.warning("weekly check-in %s failed: %s %s", iso, exc, exc.details)
        _store_failed(coach, phase, iso, start, end, facts, [str(exc), *exc.details], now)
        _send(coach, f"⚠️ The weekly check-in for {iso} failed: {exc}. Nothing was changed. "
              f"Send /checkin to try again.", now)
        return

    verdict, adjustments = apply_code_rules(verdict, facts)
    skip = weekly_facts.skip_reason(facts, verdict)
    if skip is None:
        verdict, guarded = apply_band_rules(verdict, facts)
        adjustments += guarded
    if skip is not None and verdict["proposal"] is not None:
        verdict["proposal"] = None
        adjustments.append(f"proposal dropped: the week is skipped for confirmation ({skip})")
    checkin_id = _store_ok(coach, phase, iso, start, end, facts, verdict, skip, adjustments, now)
    await _report(coach, checkin_id, facts, verdict, start, end, now)


def _send(coach, text: str, now: datetime.datetime, **kwargs: Any) -> None:
    """The weekly message the user expects: the daily message limit never holds it back."""
    messaging.send(coach, text, now, kind="weekly-checkin", exempt=True, **kwargs)


class CheckinError(Exception):
    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = list(details or [])


def apply_code_rules(verdict: dict[str, Any], facts: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """WD-SPORT in code: a sport-load week gives no calorie increase and no
    "training needs a look". Returns the (copied) verdict and what changed."""
    verdict = json.loads(json.dumps(verdict))
    changes: list[str] = []
    if not facts["activity"]["sport_load_high"]:
        return verdict, changes
    applied = False
    if verdict["direction"] == "increase":
        verdict["direction"] = "hold"
        changes.append("direction increase -> hold (sport-load week)")
        applied = True
    if verdict["proposal"] is not None and verdict["proposal"]["delta_kcal"] > 0:
        verdict["proposal"] = None
        changes.append("increase proposal dropped (sport-load week)")
        applied = True
    looks = [f for f in verdict["flags"] if f["code"] == "training_needs_look"]
    if looks:
        verdict["flags"] = [f for f in verdict["flags"] if f["code"] != "training_needs_look"]
        changes.append("training_needs_look flag dropped (sport-load week)")
        applied = True
    if applied or verdict["sport_load_applied"]:
        verdict["sport_load_applied"] = True
        if not any(f["code"] == "sport_load_week" for f in verdict["flags"]):
            verdict["flags"].append({"code": "sport_load_week", "severity": "info",
                                     "detail": "Heavy sport week: no calorie increase or training call from it.",
                                     "exercise_id": None})
        if "WD-SPORT" not in verdict["rules_applied"]:
            verdict["rules_applied"].append("WD-SPORT")
    return verdict, changes


def expected_change(weight: dict[str, Any], d: dict[str, Any]) -> tuple[str, float | None, str]:
    """What the week's trend calls for, by code (RB-SIZE; symmetric, so other
    phases can reuse it): (direction, step kcal or None, why). Below the band
    (or its lower limit) an increase, above it a decrease, in it a hold; the
    large step from `far_off_margin_kg_per_week` beyond the band edge, else
    the small one."""
    rate, band, where = weight["weekly_rate_kg"], weight["band"], weight["vs_band"]
    if where == "not_evaluated" or rate is None:
        return "hold", None, "the trend was not evaluated"
    edges = f"the band {band['low']:g} to {band['high']:g}"
    if where == "in_band":
        return "hold", None, f"the trend {rate:+.2f} kg/week is in {edges}"
    below = where in ("below_band", "below_limit")
    beyond = round(band["low"] - rate if below else rate - band["high"], 2)
    far = beyond >= d["far_off_margin_kg_per_week"]
    step = d["large_step_kcal"] if far else d["small_step_kcal"]
    return ("increase" if below else "decrease", step,
            f"the trend {rate:+.2f} kg/week is {beyond:.2f} {'below' if below else 'above'} {edges}")


def apply_band_rules(verdict: dict[str, Any], facts: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The weekly decision guard, for a week that counts: a verdict pointing
    to a change must point the way the trend does (else it becomes a hold and
    its proposal is dropped), and its proposal must have the step size the
    trend calls for (else it gets it; a phase's first change keeps its start
    range). A hold stays as it is (a proposal on a hold is left to
    `propose_change`, which blocks it). Returns the (copied) verdict and what
    changed."""
    verdict = json.loads(json.dumps(verdict))
    changes: list[str] = []
    proposal = verdict["proposal"]
    if verdict["direction"] == "hold":
        return verdict, changes
    d = facts["params"]["decisions"]
    want, step, why = expected_change(facts["weight"], d)
    if verdict["direction"] != want:
        changes.append(f"direction {verdict['direction']} -> hold ({why})")
        verdict["direction"] = "hold"
    if proposal is None:
        return verdict, changes
    delta = proposal["delta_kcal"]
    if verdict["direction"] == "hold" or (delta > 0) != (want == "increase") or delta == 0:
        verdict["proposal"] = None
        calls = "no change" if want == "hold" else f"an {want}"
        changes.append(f"proposal {delta:+g} kcal dropped (the trend calls for {calls})")
        return verdict, changes
    if proposal["is_phase_first_change"]:
        return verdict, changes
    sign = 1 if want == "increase" else -1
    size = "large" if step == d["large_step_kcal"] and step != d["small_step_kcal"] else "small"
    if abs(abs(delta) - step) > proposals.STEP_TOLERANCE_KCAL:
        proposal["delta_kcal"] = sign * step
        changes.append(f"proposal {delta:+g} -> {sign * step:+g} kcal (the {size} step: {why})")
    if proposal["size"] != size:
        changes.append(f"proposal size {proposal['size']} -> {size}")
        proposal["size"] = size
    return verdict, changes


async def _report(coach, checkin_id: int, facts, verdict, start: Date, end: Date, now: datetime.datetime) -> None:
    held = messaging.deferred(coach, start, end)
    due = measurements.measurements_due(coach, end + DAY, end + 7 * DAY)
    report_input: dict[str, Any] = {
        "facts": facts,
        "verdict": verdict,
        "proposal_result": None,
        "changes_applied": [],
        "deferred": [{"date": d["day"], "text": d["text"]} for d in held],
        "due": due,
    }
    for hook in report_hooks:
        report_input.update(await hook(coach, facts, verdict, now))
    text, buttons = None, ()
    try:
        answer = await coach.ask(REPORT_SKILLS, report_input, tools=(), output_schema="coach_message", now=now)
        if answer.data is not None and answer.data["text"].strip():
            text, buttons = answer.data["text"].strip(), _buttons(coach, answer.data["buttons"])
        else:
            logger.warning("weekly report invalid: %s", answer.errors)
    except ModelError as exc:
        logger.warning("weekly report model error: %s", exc)
    by_model = text is not None
    if text is None:
        text = _fallback(facts, verdict, held, due)
    for finish in report_finish_hooks:
        text, buttons = finish(coach, report_input, text, buttons, by_model)
    _send(coach, text, now, buttons=buttons, ref=f"weekly:{checkin_id}")
    coach.db.execute("UPDATE weekly_checkins SET report = ? WHERE id = ?", (text, checkin_id))


def _buttons(coach, items: list[dict[str, Any]]) -> tuple:
    """Buttons whose action code handles, one per row."""
    rows = []
    for b in items:
        if b["action"] in coach.registry.buttons and b.get("ref_id"):
            try:
                rows.append((Button(b["label"][:BUTTON_LABEL_LIMIT], b["action"], b["ref_id"]),))
            except ValueError:
                logger.warning("button %s/%s dropped", b["action"], b["ref_id"])
    return tuple(rows)


def training_summary(t: dict[str, Any]) -> str:
    """The report's training section in one line: counting lifts improved,
    PRs, stalls, deload signal (or that progression wasn't evaluated)."""
    names = {lift["exercise_id"]: lift["name"] for lift in t["tracked_lifts"]}
    if t["progression_met"] is None:
        parts = [f"Training: lift progression not evaluated ({t['lifting_sessions']} sessions this week)"]
    else:
        parts = [f"Training: {t['improved_lifts']} of {t['counted_lifts']} counting lifts improved"]
    if t["prs"]:
        parts.append("PRs: " + ", ".join(pr["name"] for pr in t["prs"]))
    if t["stalls"]:
        parts.append("stalled: " + ", ".join(names[i] for i in t["stalls"]))
    if t["deload_signal"]:
        parts.append("deload signal: " + ", ".join(names[i] for i in t["declining_lifts"]) + " declining")
    return "; ".join(parts)


def _fallback(facts, verdict, held, due) -> str:
    """The report written by code when the report model fails: the verdict's
    own words and the main numbers."""
    w, i = facts["weight"], facts["intake"]
    lines = [f"Weekly check-in {facts['week']['iso_week']} (phase week {facts['week']['phase_week']})",
             verdict["reasoning"]]
    if w["avg_7d_kg"] is not None:
        lines.append(f"Weight: 7-day average {w['avg_7d_kg']} kg"
                     + (f", {w['weekly_rate_kg']:+} kg/week" if w["weekly_rate_kg"] is not None else ""))
    if i["weekly_actual_kcal"] is not None:
        lines.append(f"Food: {i['weekly_actual_kcal']} of {i['weekly_target_kcal']} kcal this week")
    lines.append(training_summary(facts["training"]))
    lines += [f"- {d['text']}" for d in held]
    if due:
        lines.append("Due next week: " + ", ".join(f"{d['kind']} ({d['date']})" for d in due))
    lines += verdict["questions_for_user"]
    return "\n".join(lines)


# --- storage ---------------------------------------------------------------------------


def _store_ok(coach, phase, iso, start, end, facts, verdict, skip, adjustments, now) -> int:
    cur = coach.db.execute(
        "INSERT INTO weekly_checkins (phase_row_id, iso_week, start_date, end_date, status, facts, verdict,"
        " rules_applied, direction, counts_for_confirmation, skip_reason, code_adjustments, created_at)"
        " VALUES (?, ?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?, ?, ?)",
        (phase["id"], iso, start.isoformat(), end.isoformat(), json.dumps(facts), json.dumps(verdict),
         json.dumps(verdict["rules_applied"]), verdict["direction"], int(skip is None), skip,
         json.dumps(adjustments), now.isoformat(timespec="seconds")),
    )
    return cur.lastrowid


def _store_failed(coach, phase, iso, start, end, facts, errors, now) -> None:
    coach.db.execute(
        "INSERT INTO weekly_checkins (phase_row_id, iso_week, start_date, end_date, status, facts, errors,"
        " created_at) VALUES (?, ?, ?, ?, 'failed', ?, ?, ?)",
        (phase["id"], iso, start.isoformat(), end.isoformat(), json.dumps(facts) if facts else None,
         json.dumps(errors), now.isoformat(timespec="seconds")),
    )


def stored(coach, iso_week: str | None = None) -> dict[str, Any] | None:
    """The successful check-in for `iso_week` (default: the latest one):
    {iso_week, start_date, end_date, facts, verdict, rules_applied,
    counts_for_confirmation, skip_reason, code_adjustments, report, created_at}."""
    sql = "SELECT * FROM weekly_checkins WHERE status = 'ok'"
    params: tuple = ()
    if iso_week is not None:
        sql += " AND iso_week = ?"
        params = (iso_week,)
    row = coach.db.one(sql + " ORDER BY end_date DESC, id DESC LIMIT 1", params)
    if row is None:
        return None
    return {
        "iso_week": row["iso_week"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "facts": json.loads(row["facts"]),
        "verdict": json.loads(row["verdict"]),
        "rules_applied": json.loads(row["rules_applied"]),
        "counts_for_confirmation": bool(row["counts_for_confirmation"]),
        "skip_reason": row["skip_reason"],
        "code_adjustments": json.loads(row["code_adjustments"]),
        "report": row["report"],
        "created_at": row["created_at"],
    }
