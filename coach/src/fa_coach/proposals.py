"""Proposals (spec, "Proposals" and "Facts, rules and guardrails"; tables
from migrations/09_proposals.sql). Code runs every guardrail, stores the
proposal, and applies it only after the user's tap. The model only asks.

- `propose(coach, spec, now)`: runs the guardrails and stores the proposal as
  `open` or `blocked_by_guardrail` (with violations and, per violation, what
  failed and when it could pass). An identical open proposal is returned
  instead (`referenced: True`), not duplicated. Never applies anything.
- `approve(coach, id, now)`: one atomic claim; the change applies exactly
  once (targets, then the MFP goal through `mfp_goal.set_once`: sent once,
  read back, never retried). A second tap returns None. A calibration change
  updates the setup and recomputes the targets (`_apply_calibration`: the
  measured maintenance stays, so base moves); the MFP goal (base + surplus,
  a rest day) is set the same way when it moved. `mfp_goal_after` is the
  goal an approval would set, for the cards.
- `reject(coach, id, now)`, `add_reason(coach, id, reason)`.
- `get`, `listing`, `open_proposals`, `last_rejected`: proposal.schema.json dicts.
- `changes_applied(coach, iso_week, now)`: approved changes not yet in a
  weekly report (marked as reported in `iso_week`).
- Cards: `add_card(coach, id, ref, text)` records a message showing a
  proposal's buttons; every decision edits them (`close_cards`: buttons
  removed, outcome shown).
- `withdraw_open(coach, phase_row_id, now)`: a phase ended; its open
  proposals are closed as superseded (features/phase_end.py).

Guardrails (coach-skills/schemas/TOOLS.md):
1. exceeds_max_change: |delta| > decisions.max_change_kcal, unless it is the
   phase's first change (still pending) within the phase's start range.
2. lockout: fewer than the required usable weeks since the last change
   (confirmation_weeks, or confirmation_weeks_fast_lane when the week's
   scenario is the phase's "too fast" one).
3. confirmation_not_met: fewer consecutive usable weeks pointing the
   proposal's way than required (skipped weeks neither count nor break). A
   counter in the same direction as the open proposal it replaces inherits
   that proposal's confirmation.
4. rejected_return_too_early: same direction as the last rejected proposal
   and fewer than decisions.rejected_return_weeks usable weeks since then
   still pointing that way.
5. week_unusable / adherence_gate: the week the proposal is based on.
6. invalid_values: calibration values outside phase_setup's ranges.
7. size_or_direction_mismatch (weekly_decision only): the direction the
   scenario calls for and the step size the trend calls for
   (`_size_or_direction`).
`phase_start` skips 2-4; a calibration change is checked only by 6.
"""

import datetime
import json
import secrets
from typing import TYPE_CHECKING, Any

from . import mfp_goal, phases, weekly_facts

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
# The phase decision table's "too fast" scenario: one confirming week is enough.
FAST_LANE_SCENARIO = {"reverse_bulk": "E", "cut": "too_fast"}
# The phase decision table's scenarios that change calories (all others: no
# calorie change). Phases not listed (drafts) get no size/direction check.
SCENARIO_DIRECTION = {"reverse_bulk": {"C": "increase", "E": "decrease"}}
STEP_TOLERANCE_KCAL = 25
CALIBRATION_KEYS = phases.CALIBRATION_KEYS
DECIDED = ("approved", "rejected", "superseded")


class ProposalError(ValueError):
    """The proposal can't be considered at all (no active phase, a counter
    of a proposal that isn't open, ...). The message says why."""


# --- propose ---------------------------------------------------------------------------


def propose(coach: "Coach", spec: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """Check `spec` (propose_change input: type, delta_kcal or new_values,
    reason, source, based_on_week, is_phase_first_change, counter_of,
    returning_rejected_proposal_id, agent_disagrees) and store it. Returns the
    stored proposal, plus `referenced: True` when an identical open one was
    returned instead."""
    phase = phases.active(coach)
    if phase is None:
        raise ProposalError("there is no active phase, so there is nothing to change")
    kind = spec["type"]
    delta = spec.get("delta_kcal")
    values = spec.get("new_values")
    if kind == "calorie_change" and (delta is None or round(delta) == 0):
        raise ProposalError("a calorie change needs a non-zero delta_kcal")
    if kind == "calibration_change" and not values:
        raise ProposalError("a calibration change needs new_values")
    original = None
    if spec.get("counter_of"):
        original = get(coach, spec["counter_of"])
        if original is None or original["status"] != "open":
            raise ProposalError(f"proposal {spec['counter_of']} isn't open, so it can't be countered")

    same = _identical(coach, phase, kind, delta, values)
    if same is not None:
        return {**same, "referenced": True}

    based_on = spec.get("based_on_week") or (original or {}).get("based_on_week") or _latest_week(coach, phase)
    violations, details = _guardrails(coach, phase, spec, based_on, original, now)
    proposal_id = f"p_{secrets.token_hex(4)}"
    status = "blocked_by_guardrail" if violations else "open"
    with coach.db.transaction():
        coach.db.execute(
            "INSERT INTO proposals (id, phase_row_id, type, source, status, based_on_week, reason, delta_kcal,"
            " is_phase_first_change, new_values, counter_of, returning_rejected_proposal_id, agent_disagrees,"
            " violations, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (proposal_id, phase["id"], kind, spec["source"], status, based_on, spec["reason"],
             round(delta) if kind == "calorie_change" else None, int(bool(spec.get("is_phase_first_change"))),
             json.dumps(values) if kind == "calibration_change" else None, spec.get("counter_of"),
             spec.get("returning_rejected_proposal_id"), spec.get("agent_disagrees"), json.dumps(violations),
             json.dumps(details), now.isoformat(timespec="seconds")),
        )
        if original is not None and status == "open":
            coach.db.execute("UPDATE proposals SET status = 'superseded', decided_at = ? WHERE id = ? AND status = 'open'",
                             (now.isoformat(timespec="seconds"), original["id"]))
    if original is not None and status == "open":
        close_cards(coach, original["id"], f"↪️ Replaced by your counter ({describe_change(get(coach, proposal_id))}).")
    return get(coach, proposal_id)


def _identical(coach, phase, kind: str, delta, values) -> dict[str, Any] | None:
    for p in open_proposals(coach, phase):
        if p["type"] != kind:
            continue
        if kind == "calorie_change" and round(p["delta_kcal"]) == round(delta):
            return p
        if kind == "calibration_change" and p["new_values"] == values:
            return p
    return None


def _latest_week(coach, phase) -> str | None:
    return coach.db.value(
        "SELECT iso_week FROM weekly_checkins WHERE status = 'ok' AND phase_row_id = ? ORDER BY end_date DESC, id DESC"
        " LIMIT 1", (phase["id"],))


def _guardrails(coach, phase, spec, based_on: str | None, original, now) -> tuple[list[str], list[dict[str, Any]]]:
    p = phases.params(coach)
    found: list[tuple[str, str, Date | None]] = []
    if spec["type"] == "calibration_change":
        bad = _invalid_values(coach, spec["new_values"])
        if bad:
            found.append(("invalid_values", "; ".join(bad) + ". Values inside those ranges could pass.", None))
        return _pack(found)

    d = p["decisions"]
    delta = round(spec["delta_kcal"])
    direction = "increase" if delta > 0 else "decrease"
    first = bool(spec.get("is_phase_first_change")) and not phase["first_change_applied"]
    start_range = p.get("start", {}).get("week1_increase_kcal")
    if first and start_range:
        if not start_range[0] <= abs(delta) <= start_range[1]:
            found.append(("exceeds_max_change", f"A phase's first change must be {start_range[0]}–{start_range[1]} "
                          f"kcal a day; this one is {delta:+} kcal. A change in that range could pass.", None))
    elif abs(delta) > d["max_change_kcal"]:
        found.append(("exceeds_max_change", f"{delta:+} kcal a day is more than the largest single change, "
                      f"±{d['max_change_kcal']:g} kcal. A change of up to ±{d['max_change_kcal']:g} kcal could pass.",
                      None))

    verdicts = _verdicts(coach, phase, based_on)
    based = next((v for v in verdicts if v["iso_week"] == based_on), None)
    if spec["source"] != "phase_start":
        history = phases.target_history(coach)
        since = weekly_facts.window_start(coach, history[-1]) if history else None
        fast = based is not None and based["scenario"] == FAST_LANE_SCENARIO.get(phase["phase_id"])
        need = d["confirmation_weeks_fast_lane"] if fast else d["confirmation_weeks"]
        counted = [v for v in verdicts if v["counts_for_confirmation"] and (since is None or v["start_date"] >= since)]
        if len(counted) < need:
            missing = need - len(counted)
            found.append(("lockout", f"Only {_weeks(len(counted))} counted since the last change on "
                          f"{history[-1]['valid_from']}; "
                          f"a change needs {need}.", _earliest(coach, now, missing)))
        inherits = (spec["source"] == "user_counter" and original is not None and original["type"] == "calorie_change"
                    and (original["delta_kcal"] > 0) == (delta > 0))
        streak = weekly_facts.confirmation_streaks(verdicts, since)[direction]
        if not inherits and streak < need:
            found.append(("confirmation_not_met", f"{_weeks(streak)} in a row point to an {direction}; "
                          f"{need} are needed.", _earliest(coach, now, need - streak)))
        rejected = last_rejected(coach, phase)
        if rejected is not None and rejected["direction"] == direction:
            back = weekly_facts.confirmation_streaks(verdicts, rejected["rejected_on"])[direction]
            if back < d["rejected_return_weeks"]:
                found.append(("rejected_return_too_early",
                              f"You rejected an {direction} on {rejected['rejected_on']}; it can come back after "
                              f"{d['rejected_return_weeks']} usable weeks still pointing that way ({back} so far).",
                              _earliest(coach, now, d["rejected_return_weeks"] - back)))
    if based is not None and based["skip_reason"] == "unusable":
        found.append(("week_unusable", f"Week {based_on} was unusable, so no change can be based on it.",
                      _earliest(coach, now, 1)))
    if based is not None and based["skip_reason"] == "adherence_gate":
        found.append(("adherence_gate", f"Week {based_on} failed the adherence gate (intake off target or "
                      "incomplete logs), so no change can be based on it.", _earliest(coach, now, 1)))
    if spec["source"] == "weekly_decision" and based is not None:
        wrong = _size_or_direction(coach, phase, based, delta, first, d)
        if wrong:
            found.append(("size_or_direction_mismatch", wrong, None))
    return _pack(found)


def _size_or_direction(coach, phase, based: dict[str, Any], delta: int, first: bool, d) -> str | None:
    """What a verdict's calorie change should be, by code: the direction from
    the scenario, the size from how far the trend is outside the band
    (`decisions.far_off_margin_kg_per_week` or more: the large step, else the
    small one, ±STEP_TOLERANCE_KCAL). A phase's first change keeps its start
    range (exceeds_max_change). None if it matches, else what code expected."""
    table = SCENARIO_DIRECTION.get(phase["phase_id"])
    if table is None:
        return None  # no decision table in code for this phase yet
    want = table.get(based["scenario"])
    week = f"week {based['iso_week']} (scenario {based['scenario']})"
    if want is None:
        return f"For {week} code expected no calorie change; this is {delta:+} kcal a day."
    sign = 1 if want == "increase" else -1
    expected, why = f"an {want}", ""
    step = None
    if not first:  # a phase's first change keeps its start range (exceeds_max_change)
        facts = coach.db.value("SELECT facts FROM weekly_checkins WHERE status = 'ok' AND phase_row_id = ?"
                               " AND iso_week = ? ORDER BY id DESC LIMIT 1", (phase["id"], based["iso_week"]))
        weight = json.loads(facts)["weight"] if facts else {}
        rate, band = weight.get("weekly_rate_kg"), weight.get("band")
        if rate is not None and band is not None:
            beyond = round(band["low"] - rate if want == "increase" else rate - band["high"], 2)
            far = beyond >= d["far_off_margin_kg_per_week"]
            step = d["large_step_kcal"] if far else d["small_step_kcal"]
            expected += f" of about {sign * step:+g} kcal a day"
            why = (f": the trend ({rate:+.2f} kg/week) is {max(beyond, 0):.2f} kg/week outside the band "
                   f"({'at least' if far else 'less than'} {d['far_off_margin_kg_per_week']:g})")
    if delta * sign > 0 and (step is None or abs(abs(delta) - step) <= STEP_TOLERANCE_KCAL):
        return None
    return f"For {week} code expected {expected}{why}; this is {delta:+} kcal a day."


def _pack(found) -> tuple[list[str], list[dict[str, Any]]]:
    details = []
    for violation, text, earliest in found:
        if earliest is not None:
            text += f" Earliest: the check-in on {earliest.strftime('%a %d %b')}, if the weeks until then count."
        details.append({"violation": violation, "text": text,
                        "earliest_checkin": earliest.isoformat() if earliest else None})
    return [v for v, _, _ in found], details


def _weeks(n: int) -> str:
    return f"{n} usable week" + ("" if n == 1 else "s")


def _verdicts(coach, phase, based_on: str | None) -> list[dict[str, Any]]:
    """Stored verdicts of the phase up to and including `based_on`, newest first."""
    end = None
    if based_on is not None:
        end = coach.db.value("SELECT MAX(end_date) FROM weekly_checkins WHERE status = 'ok' AND phase_row_id = ?"
                             " AND iso_week = ?", (phase["id"], based_on))
    before = Date.fromisoformat(end) + DAY if end else Date.max
    return weekly_facts.previous_verdicts(coach, before, phase["id"])


def _invalid_values(coach, values: dict[str, Any]) -> list[str]:
    ranges = coach.skills.schema("phase_setup")["properties"]
    bad = []
    for key, value in values.items():
        if key not in CALIBRATION_KEYS:
            bad.append(f"{key} isn't a calibration value ({', '.join(CALIBRATION_KEYS)})")
            continue
        errors = coach.skills.errors({key: value}, "phase_setup")
        if any(e.startswith(f"{key}:") for e in errors) or not isinstance(value, (int, float)):
            rule = ranges[key]
            low = rule.get("exclusiveMinimum", rule.get("minimum"))
            bad.append(f"{key} = {value} is outside {low}–{rule.get('maximum')}")
    return bad


# --- check-in dates ----------------------------------------------------------------------


def _earliest(coach, now: datetime.datetime, weeks: int) -> Date | None:
    """The check-in that has seen `weeks` more weeks: the next one after
    `now`, plus `weeks - 1` weeks."""
    weekday = weekly_facts.checkin_weekday(coach)
    if weekday is None:
        return None
    return checkin_on_or_after(now.date() + DAY, weekday) + (max(weeks, 1) - 1) * 7 * DAY


def checkin_on_or_after(day: Date, weekday: int) -> Date:
    return day + ((weekday - day.weekday()) % 7) * DAY


def recheck_on(coach, applied_on: Date, source: str) -> Date | None:
    """The first check-in that can confirm the next change after one applied
    on `applied_on`: its weeks start on or after the change's window start
    (`weekly_facts.window_start`)."""
    weekday = weekly_facts.checkin_weekday(coach)
    if weekday is None:
        return None
    need = phases.params(coach)["decisions"]["confirmation_weeks"]
    start = Date.fromisoformat(weekly_facts.window_start(coach, {"source": source,
                                                                 "valid_from": applied_on.isoformat()}))
    return checkin_on_or_after(start + 7 * DAY, weekday) + (need - 1) * 7 * DAY


# --- decide ------------------------------------------------------------------------------


async def approve(coach: "Coach", proposal_id: str, now: datetime.datetime) -> dict[str, Any] | None:
    """Apply an open proposal exactly once. Returns the outcome, or None if it
    wasn't open (a second tap, an old card). The cards show the outcome."""
    at = now.isoformat(timespec="seconds")
    today = now.date()
    with coach.db.transaction():
        claimed = coach.db.execute(
            "UPDATE proposals SET status = 'approved', decided_at = ? WHERE id = ? AND status = 'open'",
            (at, proposal_id)).rowcount == 1
        if not claimed:
            return None
        proposal = get(coach, proposal_id)
        phase = phases.active(coach)
        current = phases.targets(coach, today)
        row = coach.db.one("SELECT phase_row_id FROM proposals WHERE id = ?", (proposal_id,))
        if phase is None or current is None or row["phase_row_id"] != phase["id"]:
            coach.db.execute("UPDATE proposals SET status = 'superseded' WHERE id = ?", (proposal_id,))
            outcome = None
        elif proposal["type"] == "calorie_change":
            outcome = _apply_calories(coach, phase, proposal, current, today, now)
        else:
            outcome = _apply_calibration(coach, phase, proposal, current, today, now)
        others = []
        if outcome is not None and proposal["type"] == "calorie_change":
            others = [r["id"] for r in coach.db.all(
                "SELECT id FROM proposals WHERE phase_row_id = ? AND status = 'open' AND type = 'calorie_change'",
                (phase["id"],))]
            coach.db.execute(
                "UPDATE proposals SET status = 'superseded', decided_at = ? WHERE phase_row_id = ? AND status = 'open'"
                " AND type = 'calorie_change'", (at, phase["id"]))
        if outcome is not None:
            coach.db.execute("UPDATE proposals SET outcome = ? WHERE id = ?", (json.dumps(outcome), proposal_id))
    if outcome is None:
        close_cards(coach, proposal_id, "This proposal belongs to a phase that has ended. Nothing was changed.")
        return None
    for other in others:
        close_cards(coach, other, "↪️ Not needed any more: another change was just approved. Nothing changed from this one.")
    lines = [f"✅ Approved: {outcome['summary']}"]
    close_cards(coach, proposal_id, lines[0])
    if outcome.get("mfp_goal") is not None:
        result = await mfp_goal.set_once(coach, f"proposal:{proposal_id}", outcome["mfp_goal"], now)
        if result is not None:
            outcome["mfp_goal_status"] = result["status"]
            coach.db.execute("UPDATE proposals SET outcome = ? WHERE id = ?", (json.dumps(outcome), proposal_id))
            lines.append(mfp_goal.describe(result))
            close_cards(coach, proposal_id, "\n".join(lines))
    return outcome


def _apply_calories(coach, phase, proposal, current, today: Date, now) -> dict[str, Any]:
    delta = proposal["delta_kcal"]
    p = phases.params(coach)
    average = current["avg_daily_target_kcal"] + delta
    surplus = current["surplus_kcal"] + delta
    goal = phases.mfp_goal_for(p, current["base_maintenance_kcal"], surplus, phases.macro_reference_weight(coach, today))
    values = {k: current[k] for k in ("base_maintenance_kcal", "avg_activity_kcal", "maintenance_estimate_kcal",
                                      "step_kcal_per_step", "avg_day_steps")}
    values.update(surplus_kcal=surplus, avg_daily_target_kcal=average, mfp_goal=goal)
    phases.set_targets(coach, phase["id"], values, valid_from=today, source=proposal["source"], now=now,
                       ref=proposal["id"])
    if proposal["is_phase_first_change"] and not phase["first_change_applied"]:
        coach.db.execute("UPDATE phases SET first_change_applied_at = ? WHERE id = ?",
                         (now.isoformat(timespec="seconds"), phase["id"]))
    before, after = round(current["avg_daily_target_kcal"]), round(average)
    return {
        "applied_on": today.isoformat(),
        "avg_daily_target_before_kcal": before,
        "avg_daily_target_after_kcal": after,
        "surplus_before_kcal": round(current["surplus_kcal"]),
        "surplus_after_kcal": round(surplus),
        "mfp_goal": goal,
        "mfp_goal_status": None,
        "summary": (f"{round(delta):+} kcal a day on average. Your average daily target is now {after:,} kcal "
                    f"(was {before:,}), from today. {mfp_goal_line(goal['kcal'])}"),
    }


def mfp_goal_line(kcal: float) -> str:
    """What MyFitnessPal shows, for cards: the rest-day number, activity on top."""
    return (f"MyFitnessPal's goal: {round(kcal):,} kcal, a rest day; activity comes on top "
            "(exact in each day's target here).")


def _calibrated(coach, phase, new_values: dict[str, Any], current, today: Date) -> dict[str, Any]:
    """Targets with `new_values` (not stored). The measured maintenance stays:
    the expected counted activity moves by what the new values change over
    the last ACTIVITY_DAYS days, and with maintenance including activity base
    maintenance moves the other way (the average stays). The MFP goal (base +
    surplus) moves with the base."""
    from .features import training_plan  # features import this module

    setup = {**phase["setup"], **new_values}
    old_p = phases.params_for(coach.skills, phase["phase_id"], phase["setup"])
    new_p = phases.params_for(coach.skills, phase["phase_id"], setup)
    window = [today - n * DAY for n in range(1, phases.ACTIVITY_DAYS + 1)]

    def avg_activity(p) -> float:
        return sum(training_plan.counted_activity_on(coach, d, p["activity"])["kcal"] for d in window) / len(window)

    shift = avg_activity(new_p) - avg_activity(old_p)
    base = current["base_maintenance_kcal"] - (shift if setup.get("maintenance_includes_activity", True) else 0)
    activity = current["avg_activity_kcal"] + shift
    goal = phases.mfp_goal_for(new_p, base, current["surplus_kcal"], phases.macro_reference_weight(coach, today))
    return {"setup": setup, "base_maintenance_kcal": base, "avg_activity_kcal": activity,
            "avg_daily_target_kcal": base + activity + current["surplus_kcal"], "mfp_goal": goal}


def mfp_goal_after(coach: "Coach", proposal: dict[str, Any], today: Date) -> int | None:
    """The MFP goal kcal approving `proposal` would set (None without targets)."""
    phase, current = phases.active(coach), phases.targets(coach, today)
    if phase is None or current is None:
        return None
    if proposal["type"] == "calorie_change":
        return round(current["base_maintenance_kcal"] + current["surplus_kcal"] + proposal["delta_kcal"])
    return _calibrated(coach, phase, proposal["new_values"], current, today)["mfp_goal"]["kcal"]


def _apply_calibration(coach, phase, proposal, current, today: Date, now) -> dict[str, Any]:
    """New setup values, and targets recomputed from today (`_calibrated`).
    The surplus never changes, so this is not a calorie change (no lockout).
    The MFP goal is set when its kcal moved."""
    before = {k: phase["setup"].get(k) for k in proposal["new_values"]}
    new = _calibrated(coach, phase, proposal["new_values"], current, today)
    coach.db.execute("UPDATE phases SET setup = ? WHERE id = ?", (json.dumps(new["setup"]), phase["id"]))
    phases.record_setup_change(coach, phase["id"], proposal["new_values"], valid_from=today,
                               source=phases.CALIBRATION_SOURCE, now=now, ref=proposal["id"])
    average = new["avg_daily_target_kcal"]
    was, now_avg = round(current["avg_daily_target_kcal"]), round(average)
    old_goal = round(current["mfp_goal"]["kcal"])
    goal = new["mfp_goal"] if new["mfp_goal"]["kcal"] != old_goal else None
    phases.set_targets(coach, phase["id"], {
        "base_maintenance_kcal": new["base_maintenance_kcal"], "surplus_kcal": current["surplus_kcal"],
        "avg_activity_kcal": new["avg_activity_kcal"], "maintenance_estimate_kcal": current["maintenance_estimate_kcal"],
        "avg_daily_target_kcal": average, "mfp_goal": goal or current["mfp_goal"],
        "step_kcal_per_step": current["step_kcal_per_step"], "avg_day_steps": current["avg_day_steps"]},
        valid_from=today, source=phases.CALIBRATION_SOURCE, now=now, ref=proposal["id"])
    changes = ", ".join(f"{k.replace('_', ' ')} {before[k]} → {v}" for k, v in proposal["new_values"].items())
    effect = (f"Your average daily target is now {now_avg:,} kcal (was {was:,})." if now_avg != was
              else f"Your average daily target stays {was:,} kcal; the days' targets follow the new values.")
    shown = (f"{mfp_goal_line(goal['kcal'])} Was {old_goal:,} kcal." if goal
             else f"MyFitnessPal's goal stays {old_goal:,} kcal.")
    return {"applied_on": today.isoformat(), "before": before, "after": proposal["new_values"],
            "avg_daily_target_before_kcal": was, "avg_daily_target_after_kcal": now_avg,
            "mfp_goal": goal, "mfp_goal_status": None,
            "summary": f"{changes}. Days are counted with the new values from today. {effect} {shown}"}


def reject(coach: "Coach", proposal_id: str, now: datetime.datetime) -> bool:
    """Mark an open proposal rejected; False if it wasn't open."""
    claimed = coach.db.execute(
        "UPDATE proposals SET status = 'rejected', decided_at = ? WHERE id = ? AND status = 'open'",
        (now.isoformat(timespec="seconds"), proposal_id)).rowcount == 1
    if claimed:
        close_cards(coach, proposal_id, "❌ Rejected. Nothing changes.")
    return claimed


def add_reason(coach: "Coach", proposal_id: str, reason: str) -> dict[str, Any] | None:
    """Store the user's reason on a rejected proposal; None if there's no such rejection."""
    done = coach.db.execute("UPDATE proposals SET user_reason = ? WHERE id = ? AND status = 'rejected'",
                            (reason, proposal_id)).rowcount == 1
    return get(coach, proposal_id) if done else None


# --- cards ---------------------------------------------------------------------------------


def add_card(coach: "Coach", proposal_id: str, ref: str, text: str | None = None) -> None:
    coach.db.execute("INSERT OR IGNORE INTO proposal_cards (proposal_id, ref, text) VALUES (?, ?, ?)",
                     (proposal_id, ref, text))


def withdraw_open(coach: "Coach", phase_row_id: str, now: datetime.datetime) -> list[str]:
    """Close a phase's open proposals as superseded (the phase ended). Call
    inside the caller's transaction; edit their cards afterwards with
    `close_cards`. Returns their ids."""
    ids = [r["id"] for r in coach.db.all("SELECT id FROM proposals WHERE phase_row_id = ? AND status = 'open'",
                                         (phase_row_id,))]
    coach.db.execute("UPDATE proposals SET status = 'superseded', decided_at = ? WHERE phase_row_id = ?"
                     " AND status = 'open'", (now.isoformat(timespec="seconds"), phase_row_id))
    return ids


def close_cards(coach, proposal_id: str, outcome: str) -> None:
    """Edit every message showing this proposal's buttons: no buttons, the outcome below."""
    for ref, text in card_edits(coach, proposal_id, outcome):
        coach.edit(ref, text)


def card_edits(coach, proposal_id: str, outcome: str) -> list[tuple[str, str]]:
    """(ref, new text) for every message showing this proposal's buttons, read
    now (before an erase deletes the rows they come from)."""
    edits = []
    for card in coach.db.all("SELECT ref, text FROM proposal_cards WHERE proposal_id = ?", (proposal_id,)):
        text = card["text"]
        if text is None and card["ref"].startswith("weekly:"):
            text = coach.db.value("SELECT report FROM weekly_checkins WHERE id = ?", (int(card["ref"][7:]),))
        edits.append((card["ref"], f"{text}\n\n{outcome}" if text else outcome))
    return edits


# --- read ------------------------------------------------------------------------------------


def get(coach: "Coach", proposal_id: str) -> dict[str, Any] | None:
    row = coach.db.one("SELECT * FROM proposals WHERE id = ?", (proposal_id,))
    return _proposal(row) if row else None


def listing(coach: "Coach", status: str | None = None) -> list[dict[str, Any]]:
    """The active phase's proposals, newest first (optionally one status)."""
    phase = phases.active(coach)
    if phase is None:
        return []
    sql, params = "SELECT * FROM proposals WHERE phase_row_id = ?", [phase["id"]]
    if status:
        sql += " AND status = ?"
        params.append(status)
    return [_proposal(r) for r in coach.db.all(sql + " ORDER BY created_at DESC, rowid DESC", tuple(params))]


def open_proposals(coach: "Coach", phase: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    phase = phase or phases.active(coach)
    if phase is None:
        return []
    rows = coach.db.all("SELECT * FROM proposals WHERE phase_row_id = ? AND status = 'open' ORDER BY created_at, rowid",
                        (phase["id"],))
    return [_proposal(r) for r in rows]


def last_rejected(coach: "Coach", phase: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The phase's last rejected calorie change: {proposal_id, direction,
    rejected_on, user_reason}."""
    phase = phase or phases.active(coach)
    if phase is None:
        return None
    row = coach.db.one("SELECT * FROM proposals WHERE phase_row_id = ? AND status = 'rejected' AND"
                       " type = 'calorie_change' ORDER BY decided_at DESC, rowid DESC LIMIT 1", (phase["id"],))
    if row is None:
        return None
    return {"proposal_id": row["id"], "direction": "increase" if row["delta_kcal"] > 0 else "decrease",
            "rejected_on": row["decided_at"][:10], "user_reason": row["user_reason"]}


def changes_applied(coach: "Coach", iso_week: str, now: datetime.datetime) -> list[dict[str, Any]]:
    """Approved changes no weekly report has listed yet, for the report of
    `iso_week` (which then counts as having listed them)."""
    phase = phases.active(coach)
    if phase is None:
        return []
    rows = coach.db.all("SELECT * FROM proposals WHERE phase_row_id = ? AND status = 'approved' AND outcome IS NOT NULL"
                        " AND (reported_in IS NULL OR reported_in = ?) ORDER BY decided_at", (phase["id"], iso_week))
    kcal_per_kg = phases.params(coach)["maintenance_estimate"]["kcal_per_kg"]
    out = []
    for row in rows:
        p, outcome = _proposal(row), json.loads(row["outcome"])
        applied = Date.fromisoformat(outcome["applied_on"])
        recheck = recheck_on(coach, applied, p["source"])
        item = {"proposal_id": p["id"], "type": p["type"], "source": p["source"], "approved_on": applied.isoformat(),
                "why": p["reason"], "what": outcome["summary"], "recheck_on": recheck.isoformat() if recheck else None}
        if p["type"] == "calorie_change":
            item.update(delta_kcal=p["delta_kcal"],
                        avg_daily_target_before_kcal=outcome["avg_daily_target_before_kcal"],
                        avg_daily_target_after_kcal=outcome["avg_daily_target_after_kcal"],
                        expected_weekly_rate_change_kg=round(p["delta_kcal"] * 7 / kcal_per_kg, 2),
                        mfp_goal=outcome["mfp_goal"], mfp_goal_status=outcome.get("mfp_goal_status"))
        else:
            item.update(new_values=outcome["after"], previous_values=outcome["before"])
        out.append(item)
    if rows:
        coach.db.execute(
            f"UPDATE proposals SET reported_in = ? WHERE id IN ({','.join('?' * len(rows))})",
            (iso_week, *[r["id"] for r in rows]))
    return out


def describe_change(p: dict[str, Any]) -> str:
    if p["type"] == "calorie_change":
        return f"{round(p['delta_kcal']):+} kcal a day on average"
    return ", ".join(f"{k.replace('_', ' ')} → {v}" for k, v in p["new_values"].items())


def _proposal(row) -> dict[str, Any]:
    violations = json.loads(row["violations"])
    return {
        "id": row["id"],
        "type": row["type"],
        "source": row["source"],
        "status": row["status"],
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
        "based_on_week": row["based_on_week"],
        "reason": row["reason"],
        "delta_kcal": row["delta_kcal"],
        "is_phase_first_change": bool(row["is_phase_first_change"]),
        "new_values": json.loads(row["new_values"]) if row["new_values"] else None,
        "counter_of": row["counter_of"],
        "returning_rejected_proposal_id": row["returning_rejected_proposal_id"],
        "agent_disagrees": row["agent_disagrees"],
        "user_reason": row["user_reason"],
        "guardrail": {"passed": not violations, "violations": violations, "details": json.loads(row["details"])},
    }
