"""Proposals in the coach (ticket 09): the weekly verdict's proposal goes
through `propose_change`, the report shows an open one with approve /
reject / counter buttons (added by code, whatever the report model wrote),
and the taps decide it once. The logic lives in fa_coach/proposals.py.

- Weekly check-in: a facts hook fills `history.open_proposals` and
  `history.last_rejected`; a report hook stores the verdict's proposal and
  passes `proposal_result` and `changes_applied`; a finish hook sets the
  report's buttons (and, when code wrote the report, the proposal lines).
- Buttons: `approve_proposal` (one atomic claim; targets, then the MFP goal
  once), `reject_proposal` (asks for an optional reason), `counter_proposal`
  (asks for the user's number; the reply goes to the chat, ticket 10).
- Model tools: `propose_change`, `get_proposals`, `add_rejection_reason`.
"""

import datetime
from typing import Any

from .. import phases, proposals, weekly_facts
from ..ask import ToolError
from ..ports import Button, Buttons
from ..registry import registry
from . import weekly_checkin

ACTIONS = ("approve_proposal", "reject_proposal", "counter_proposal")
REASON_WINDOW = datetime.timedelta(hours=24)


def buttons_for(proposal_id: str) -> Buttons:
    return ((Button("✅ Approve", "approve_proposal", proposal_id), Button("❌ Reject", "reject_proposal", proposal_id),
             Button("✏️ Counter", "counter_proposal", proposal_id)),)


# --- weekly check-in -------------------------------------------------------------------


def _facts(coach, facts: dict[str, Any], now: datetime.datetime) -> None:
    phase = phases.active(coach)
    history = facts["history"]
    history["open_proposals"] = proposals.open_proposals(coach, phase)
    rejected = proposals.last_rejected(coach, phase)
    if rejected is not None:
        start = datetime.date.fromisoformat(facts["week"]["start_date"])
        verdicts = weekly_facts.previous_verdicts(coach, start, phase["id"])
        rejected["usable_weeks_since"] = sum(1 for v in verdicts if v["counts_for_confirmation"]
                                             and v["start_date"] >= rejected["rejected_on"])
    history["last_rejected"] = rejected


weekly_facts.facts_hooks.append(_facts)


async def _report_input(coach, facts, verdict, now: datetime.datetime) -> dict[str, Any]:
    result = None
    offer = verdict.get("proposal")
    if offer is not None:
        result = proposals.propose(coach, {
            "type": offer["type"], "delta_kcal": offer["delta_kcal"], "reason": offer["reason"],
            "source": "weekly_decision", "based_on_week": verdict["iso_week"],
            "is_phase_first_change": offer["is_phase_first_change"],
            "returning_rejected_proposal_id": offer.get("returning_rejected_proposal_id"),
        }, now)
        if result["status"] == "open":
            checkin_id = coach.db.value("SELECT MAX(id) FROM weekly_checkins WHERE status = 'ok' AND iso_week = ?",
                                        (verdict["iso_week"],))
            proposals.add_card(coach, result["id"], f"weekly:{checkin_id}")
    return {"proposal_result": result, "changes_applied": proposals.changes_applied(coach, verdict["iso_week"], now)}


def _finish(coach, report_input: dict[str, Any], text: str, buttons: Buttons, by_model: bool) -> tuple[str, Buttons]:
    """Only code decides which proposal buttons a report carries."""
    rows = tuple(row for row in (tuple(b for b in r if b.action not in ACTIONS) for r in buttons) if row)
    result = report_input.get("proposal_result")
    if result is not None and result["status"] == "open":
        rows += buttons_for(result["id"])
    if not by_model:
        lines = []
        if result is not None and result["status"] == "open":
            lines.append(f"Proposal: {proposals.describe_change(result)}. {result['reason']}")
        elif result is not None:
            lines.append("No change is possible yet:")
            lines += [f"- {d['text']}" for d in result["guardrail"]["details"]]
        for change in report_input.get("changes_applied", []):
            lines.append(f"Changed this week: {change['what']} Why: {change['why']}"
                         + (f" Re-checked at the check-in on {change['recheck_on']}." if change["recheck_on"] else ""))
        if lines:
            text = "\n".join([text, *lines])
    return text, rows


weekly_checkin.report_hooks.append(_report_input)
weekly_checkin.report_finish_hooks.append(_finish)


# --- buttons ------------------------------------------------------------------------------


@registry.button("approve_proposal")
async def approve(coach, ref_id: str, now: datetime.datetime) -> None:
    await proposals.approve(coach, ref_id, now)


@registry.button("reject_proposal")
async def reject(coach, ref_id: str, now: datetime.datetime) -> None:
    if proposals.reject(coach, ref_id, now):
        coach.say("Why not? Optional: reply with a reason and I'll remember it, or just ignore this.")


@registry.button("counter_proposal")
async def counter(coach, ref_id: str, now: datetime.datetime) -> None:
    proposal = proposals.get(coach, ref_id)
    if proposal is None or proposal["status"] != "open":
        return
    coach.say(f"Reply with your number instead of {proposals.describe_change(proposal)} (e.g. “+50”) and I'll "
              "check it against the guardrails. Until then nothing changes.")


@registry.state("proposals")
def proposals_state(coach, now: datetime.datetime) -> dict[str, Any] | None:
    """Open proposals and a rejection waiting for its optional reason, so a
    reply can be matched to them."""
    open_ = [{k: p[k] for k in ("id", "type", "delta_kcal", "new_values", "reason")}
             for p in proposals.open_proposals(coach)]
    rejected = proposals.listing(coach, "rejected")[:1]
    waiting = [p["id"] for p in rejected if p["user_reason"] is None and p["decided_at"]
               and now - datetime.datetime.fromisoformat(p["decided_at"]) <= REASON_WINDOW]
    if not open_ and not waiting:
        return None
    return {"open": open_, "rejected_awaiting_reason": waiting[0] if waiting else None}


# --- model tools ---------------------------------------------------------------------------

PROPOSE_SCHEMA = {
    "type": "object",
    "required": ["type", "reason", "source"],
    "additionalProperties": False,
    "properties": {
        "type": {"enum": ["calorie_change", "calibration_change"]},
        "delta_kcal": {"type": ["number", "null"], "description": "calorie_change: signed change to the daily average."},
        "new_values": {
            "type": ["object", "null"], "additionalProperties": {"type": "number"},
            "description": "calibration_change: run_kcal_discount, wrestling_kcal_per_session, lifting_kcal_per_session.",
        },
        "reason": {"type": "string"},
        "source": {"enum": ["user_request", "user_counter", "phase_review"]},
        "based_on_week": {"type": ["string", "null"], "pattern": "^[0-9]{4}-W[0-9]{2}$"},
        "is_phase_first_change": {"type": "boolean"},
        "counter_of": {"type": ["string", "null"]},
        "returning_rejected_proposal_id": {"type": ["string", "null"]},
        "agent_disagrees": {"type": ["string", "null"]},
    },
}


@registry.tool(
    "propose_change",
    "Propose a calorie or calibration change. Code runs every guardrail and stores it as open (the user gets a card "
    "with approve / reject / counter buttons) or blocked_by_guardrail with each violation and when it could pass. "
    "It never applies anything; an identical open proposal is returned instead of a new one.",
    PROPOSE_SCHEMA,
)
async def propose_change(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    try:
        result = proposals.propose(coach, args, now)
    except proposals.ProposalError as exc:
        raise ToolError(str(exc)) from exc
    if result["status"] == "open" and not result.get("referenced"):
        ref = f"proposal:{result['id']}"
        text = f"Proposal: {proposals.describe_change(result)}. {result['reason']}"
        if result["agent_disagrees"]:
            text += f"\nMy view: {result['agent_disagrees']}"
        coach.say(text + "\n\nNothing changes until you tap Approve.", buttons_for(result["id"]), ref=ref)
        proposals.add_card(coach, result["id"], ref, text + "\n\nNothing changes until you tap Approve.")
    return result


@registry.tool(
    "get_proposals",
    "Proposals of the active phase, newest first, optionally only one status (open, approved, rejected, superseded, "
    "blocked_by_guardrail), with guardrail violations and when they could pass.",
    {"type": "object", "additionalProperties": False,
     "properties": {"status": {"enum": ["open", "approved", "rejected", "superseded", "blocked_by_guardrail"]}}},
)
async def get_proposals(coach, args: dict[str, Any], now: datetime.datetime) -> list[dict[str, Any]]:
    return proposals.listing(coach, args.get("status"))


@registry.tool(
    "add_rejection_reason",
    "Store the reason the user gave for rejecting a proposal (their words).",
    {"type": "object", "required": ["proposal_id", "reason"], "additionalProperties": False,
     "properties": {"proposal_id": {"type": "string"}, "reason": {"type": "string", "minLength": 1}}},
)
async def add_rejection_reason(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    stored = proposals.add_reason(coach, args["proposal_id"], args["reason"])
    if stored is None:
        raise ToolError(f"no rejected proposal {args['proposal_id']}")
    return stored
