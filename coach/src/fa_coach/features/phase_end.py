"""Ending a phase from Telegram (coach-followups ticket 01; table
phase_end_requests in migrations/22_phase_end.sql).

- `/endphase` and the chat tool `request_phase_end` (mode `end`) only send a
  card (`send_card`); nothing changes before Confirm. A newer card supersedes
  older open ones.
- The card says what ending does (`render_card`): no target from today, open
  proposals withdrawn, check-ins and reminders stop, training feedback keeps
  running, the MFP goal stays as it is.
- Confirm (`confirm_phase_end`) claims the card once (one conditional UPDATE
  in the same transaction as the change) and then:
  - effect `end`: the phase gets status 'ended', `ended_at` and `end_date` =
    yesterday (`phases.on(day)` reads the span); its open proposals are
    withdrawn (`proposals.withdraw_open`) and their cards edited.
  - effect `erase`: on the phase's start day an end would leave an empty
    phase, so the card says it erases it instead and Confirm deletes it
    (`erase`).
  The effect is fixed on the card; a tap on a day when it would be different
  (or after the phase already ended) changes nothing.
- Jobs: the weekly check-in, the evening reminder/recap and the measurement
  reminders return without an active phase; training feedback doesn't
  (features/training_feedback.py).

For ticket 02 (undo): `request_phase_end` takes a `mode`; `erase(coach,
phase)` deletes a phase and everything that hangs on it in the caller's
transaction and returns the counts.
"""

import datetime
import secrets
from typing import TYPE_CHECKING, Any

from .. import phases, proposals
from ..ask import ToolError
from ..ports import Button
from ..registry import registry

if TYPE_CHECKING:
    from ..core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
MODES = ("end",)


# --- effect -----------------------------------------------------------------------------


def effect(phase: dict[str, Any], today: Date) -> str:
    """What ending `phase` today does: 'end', or 'erase' on its start day."""
    return "erase" if today <= Date.fromisoformat(phase["start_date"]) else "end"


def end(coach: "Coach", phase: dict[str, Any], now: datetime.datetime) -> list[str]:
    """End the active `phase` today: its last day is yesterday. Withdraws its
    open proposals and returns their ids (edit their cards after the
    transaction). Call inside the caller's transaction."""
    coach.db.execute("UPDATE phases SET status = 'ended', ended_at = ?, end_date = ? WHERE id = ?",
                     (now.isoformat(timespec="seconds"), (now.date() - DAY).isoformat(), phase["id"]))
    return proposals.withdraw_open(coach, phase["id"], now)


def erase(coach: "Coach", phase: dict[str, Any], today: Date) -> dict[str, int]:
    """Delete `phase` and what hangs on it: its setup (and setup history), targets, proposals (and
    their cards and counter taps), weekly verdicts and reports, and the day
    questions and confirmations from its days (start_date..end_date, today
    while active). Other phases stay. Returns the deleted rows per kind. Call
    inside the caller's transaction."""
    pid = (phase["id"],)
    last = phase["end_date"] or today.isoformat()
    days = (phase["start_date"], last)
    in_phase = "SELECT id FROM proposals WHERE phase_row_id = ?"
    counts = {
        "counter_taps": coach.db.execute(f"DELETE FROM counter_taps WHERE proposal_id IN ({in_phase})", pid).rowcount,
        "proposal_cards": coach.db.execute(f"DELETE FROM proposal_cards WHERE proposal_id IN ({in_phase})",
                                           pid).rowcount,
        "proposals": coach.db.execute("DELETE FROM proposals WHERE phase_row_id = ?", pid).rowcount,
        "weekly_checkins": coach.db.execute("DELETE FROM weekly_checkins WHERE phase_row_id = ?", pid).rowcount,
        "targets": coach.db.execute("DELETE FROM targets WHERE phase_row_id = ?", pid).rowcount,
        "setup_changes": coach.db.execute("DELETE FROM setup_changes WHERE phase_row_id = ?", pid).rowcount,
        "day_questions": coach.db.execute("DELETE FROM day_questions WHERE date BETWEEN ? AND ?", days).rowcount,
        "day_confirmations": coach.db.execute("DELETE FROM day_confirmations WHERE date BETWEEN ? AND ?",
                                              days).rowcount,
    }
    setup_id = coach.db.value("SELECT setup_id FROM phases WHERE id = ?", pid)
    counts["phases"] = coach.db.execute("DELETE FROM phases WHERE id = ?", pid).rowcount
    counts["phase_setups"] = coach.db.execute("DELETE FROM phase_setups WHERE id = ?", (setup_id,)).rowcount
    return counts


# --- the card ---------------------------------------------------------------------------


def _day(d: Date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def _name(coach, phase: dict[str, Any]) -> str:
    return coach.skills.params(phase["phase_id"]).get("name") or phase["phase_id"]


def render_card(coach: "Coach", phase: dict[str, Any], kind: str, today: Date) -> str:
    name = _name(coach, phase)
    open_count = len(proposals.open_proposals(coach, phase))
    targets = phases.targets(coach, today)
    goal = f" ({round(targets['mfp_goal']['kcal']):,} kcal)" if targets else ""
    keep = (f"Your MyFitnessPal goal stays as it is{goal}; the coach doesn't touch it. Change it yourself "
            "if you like.")
    if kind == "erase":
        lines = [
            f"End the phase “{name}”?",
            f"It started today ({_day(today)}), so ending it erases it, as if it never started: the phase, its "
            "setup, targets and proposals are deleted, and from today there's no target.",
            "Weekly check-ins, evening reminders and waist/photo reminders stop. Training feedback keeps running.",
            keep,
        ]
    else:
        start = Date.fromisoformat(phase["start_date"])
        lines = [
            f"End the phase “{name}”?",
            f"- Its last day is yesterday, {_day(today - DAY)} (phase week {phases.phase_week(phase, today - DAY)}). "
            f"From today there's no target. The phase stays in the history ({_day(start)} – {_day(today - DAY)}) "
            "with its weeks, verdicts and targets.",
            f"- Open proposals are withdrawn ({open_count} open)." if open_count
            else "- Open proposals are withdrawn (none open now).",
            "- Weekly check-ins, evening reminders and waist/photo reminders stop.",
            "- Training feedback keeps running.",
            f"- {keep}",
        ]
    return "\n".join(lines) + "\n\nNothing changes until you tap Confirm."


def _ref(request_id: str) -> str:
    return f"phase-end:{request_id}"


def send_card(coach: "Coach", mode: str, reason: str | None, now: datetime.datetime) -> dict[str, Any]:
    """Send the confirm card for ending the active phase; older open cards are
    superseded. Raises ToolError without an active phase."""
    phase = phases.active(coach)
    if phase is None:
        raise ToolError("there is no active phase to end")
    kind = effect(phase, now.date())
    text = render_card(coach, phase, kind, now.date())
    request_id = f"e_{secrets.token_hex(4)}"
    at = now.isoformat(timespec="seconds")
    older = coach.db.all("SELECT id, text FROM phase_end_requests WHERE status = 'open'")
    with coach.db.transaction():
        coach.db.execute("UPDATE phase_end_requests SET status = 'superseded', decided_at = ? WHERE status = 'open'",
                         (at,))
        coach.db.execute(
            "INSERT INTO phase_end_requests (id, phase_row_id, mode, effect, status, reason, text, created_at)"
            " VALUES (?, ?, ?, ?, 'open', ?, ?, ?)", (request_id, phase["id"], mode, kind, reason, text, at))
    for row in older:
        coach.edit(_ref(row["id"]), f"{row['text']}\n\n↪️ Replaced by a newer card. Nothing changed.")
    buttons = ((Button("✅ Confirm", "confirm_phase_end", request_id), Button("✖️ Cancel", "cancel_phase_end",
                                                                             request_id)),)
    coach.say(text, buttons, ref=_ref(request_id))
    return {"request_id": request_id, "effect": kind, "phase": _name(coach, phase)}


# --- triggers ---------------------------------------------------------------------------


@registry.command("endphase", "End the active phase (asks to confirm first)")
async def endphase_command(coach, args: str, now: datetime.datetime) -> None:
    try:
        send_card(coach, "end", args or None, now)
    except ToolError:
        coach.say("No phase is active, so there's nothing to end.")


@registry.tool(
    "request_phase_end",
    "Send the user a confirm card for ending the active phase, when they ask to end or stop it without starting a "
    "new one (mode end). Ending changes nothing until they tap Confirm: then today has no target, open proposals "
    "are withdrawn, check-ins and reminders stop, and the phase stays in the history. The MFP goal is untouched. "
    "This tool itself changes nothing; tell the user the card is below.",
    {
        "type": "object",
        "required": ["mode", "reason"],
        "additionalProperties": False,
        "properties": {
            "mode": {"enum": list(MODES)},
            "reason": {"type": "string", "description": "The user's reason, in a few of their words."},
        },
    },
)
async def request_phase_end(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    sent = send_card(coach, args["mode"], args["reason"], now)
    erase_note = " It started today, so the card says Confirm erases it." if sent["effect"] == "erase" else ""
    return {**sent, "say": f"The card to end “{sent['phase']}” is below; nothing changes until you tap Confirm."
                           + erase_note}


# --- buttons ----------------------------------------------------------------------------


@registry.button("confirm_phase_end")
async def confirm_phase_end(coach, ref_id: str, now: datetime.datetime) -> None:
    at = now.isoformat(timespec="seconds")
    withdrawn: list[str] = []
    with coach.db.transaction():
        claimed = coach.db.execute(
            "UPDATE phase_end_requests SET status = 'confirmed', decided_at = ? WHERE id = ? AND status = 'open'",
            (at, ref_id)).rowcount == 1
        if not claimed:
            return  # a second tap, a cancelled or replaced card
        request = coach.db.one("SELECT * FROM phase_end_requests WHERE id = ?", (ref_id,))
        phase = phases.active(coach)
        if phase is None or phase["id"] != request["phase_row_id"] or effect(phase, now.date()) != request["effect"]:
            coach.db.execute("UPDATE phase_end_requests SET status = 'superseded' WHERE id = ?", (ref_id,))
            outcome = "This card is out of date. Nothing changed; send /endphase again if you still want to end it."
        elif request["effect"] == "erase":
            erase(coach, phase, now.date())
            outcome = "✅ Erased. There's no phase now and no target from today. MyFitnessPal's goal is unchanged."
        else:
            withdrawn = end(coach, phase, now)
            outcome = (f"✅ Ended. Its last day was {_day(now.date() - DAY)}; no target from today. "
                       "MyFitnessPal's goal is unchanged.")
            if withdrawn:
                outcome += f" Withdrawn: {len(withdrawn)} open proposal{'s' if len(withdrawn) > 1 else ''}."
    coach.edit(_ref(ref_id), f"{request['text']}\n\n{outcome}")
    for proposal_id in withdrawn:
        proposals.close_cards(coach, proposal_id, "⏹ Phase ended. Nothing changed from this proposal.")


@registry.button("cancel_phase_end")
async def cancel_phase_end(coach, ref_id: str, now: datetime.datetime) -> None:
    claimed = coach.db.execute(
        "UPDATE phase_end_requests SET status = 'cancelled', decided_at = ? WHERE id = ? AND status = 'open'",
        (now.isoformat(timespec="seconds"), ref_id)).rowcount == 1
    if claimed:
        text = coach.db.value("SELECT text FROM phase_end_requests WHERE id = ?", (ref_id,))
        coach.edit(_ref(ref_id), f"{text}\n\n✖️ Cancelled. The phase goes on.")
