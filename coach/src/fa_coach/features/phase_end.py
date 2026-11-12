"""Ending and undoing a phase from Telegram (coach-followups tickets 01 and
02; table phase_end_requests in migrations/22_phase_end.sql).

- `/endphase` and the chat tool `request_phase_end` (mode `end`) only send a
  card (`send_card`); nothing changes before Confirm. A newer card supersedes
  older open ones.
- The card says what ending does (`render_card`): no target from today, open
  proposals withdrawn, check-ins and reminders stop, training feedback and
  day questions keep running, the MFP goal stays as it is.
- Mode `undo` (the chat tool only, when the user explicitly asks to undo or
  erase a phase): the card (`render_undo_card`) is about the active phase,
  else the latest ended one (`target`), and lists what Confirm deletes, with
  the counts (`erase_counts`). Its effect is always `erase`.
- Confirm (`confirm_phase_end`) claims the card once (one conditional UPDATE
  in the same transaction as the change) and then:
  - effect `end`: the phase gets status 'ended', `ended_at` and `end_date` =
    yesterday (`phases.end_active`; `phases.on(day)` reads the span); its open
    proposals are withdrawn (`proposals.withdraw_open`) and their cards edited.
    Then the phase review of the ended phase goes out (features/phase_review.py).
  - effect `erase` (an undo card, or an end card on the phase's start day,
    where an end would leave an empty phase): `erase` deletes the phase and
    everything that hangs on it in the same transaction; its open proposals'
    cards are edited.
  The effect is fixed on the card; a tap when it would be different (an end
  card after the phase ended or on another day, an undo card once another
  phase is the target) changes nothing.
- Day questions and confirmations belong to the days, not the phase: an
  erase keeps them (they run without a phase since ticket 06).
- `last_erase_at`: when the latest erase was confirmed (training feedback's
  cut-off without a phase).
- Jobs: the weekly check-in, the evening reminder/recap and the measurement
  reminders return without an active phase; training feedback and day
  questions don't.

A new table that hangs on a phase gets a row in `_erase_parts` (and a
`LABELS` entry to show on the undo card).
"""

import datetime
import logging
import secrets
from typing import TYPE_CHECKING, Any

from .. import phases, proposals
from ..ask import ToolError
from ..ports import Button
from ..registry import registry

if TYPE_CHECKING:
    from ..core import Coach

logger = logging.getLogger("fa-coach")
Date = datetime.date
DAY = datetime.timedelta(days=1)
# What a card was asked for (`mode`) and what Confirm does (`effect`).
MODE_END, MODE_UNDO = "end", "undo"
MODES = (MODE_END, MODE_UNDO)
EFFECT_END, EFFECT_ERASE = "end", "erase"
ERASED = "⏹ Phase erased. Nothing changed from this proposal."


# --- effect -----------------------------------------------------------------------------


def effect(phase: dict[str, Any], today: Date) -> str:
    """What ending `phase` today does: EFFECT_END, or EFFECT_ERASE on its start day."""
    return EFFECT_ERASE if today <= Date.fromisoformat(phase["start_date"]) else EFFECT_END


def end(coach: "Coach", phase: dict[str, Any], now: datetime.datetime) -> list[str]:
    """End the active `phase` today: its last day is yesterday. Withdraws its
    open proposals and returns their ids (edit their cards after the
    transaction). Call inside the caller's transaction."""
    phases.end_active(coach, now, now.date() - DAY)
    return proposals.withdraw_open(coach, phase["id"], now)


def _erase_parts(coach: "Coach", phase: dict[str, Any]) -> list[tuple[str, str, tuple]]:
    """What erasing `phase` deletes, in delete order: (kind, `FROM table WHERE
    ...`, params). Add a row here for a new table that hangs on a phase; give
    it a LABELS entry if the undo card should show it."""
    pid = (phase["id"],)
    setup = (coach.db.value("SELECT setup_id FROM phases WHERE id = ?", pid),)
    in_phase = "SELECT id FROM proposals WHERE phase_row_id = ?"
    return [
        ("counter_taps", f"counter_taps WHERE proposal_id IN ({in_phase})", pid),
        ("proposal_cards", f"proposal_cards WHERE proposal_id IN ({in_phase})", pid),
        ("proposals", "proposals WHERE phase_row_id = ?", pid),
        ("weekly_checkins", "weekly_checkins WHERE phase_row_id = ?", pid),
        ("targets", "targets WHERE phase_row_id = ?", pid),
        ("setup_changes", "setup_changes WHERE phase_row_id = ?", pid),  # "its setup" on the card
        ("phases", "phases WHERE id = ?", pid),
        ("phase_setups", "phase_setups WHERE id = ?", setup),
    ]


def erase_counts(coach: "Coach", phase: dict[str, Any]) -> dict[str, int]:
    """The rows `erase` would delete now, per kind."""
    return {kind: coach.db.value(f"SELECT COUNT(*) FROM {rows}", params)
            for kind, rows, params in _erase_parts(coach, phase)}


def erase(coach: "Coach", phase: dict[str, Any]) -> dict[str, int]:
    """Delete `phase` and what hangs on it: its setup (and setup history),
    targets, proposals (and their cards and counter taps), weekly verdicts and
    reports. Other phases, and the day questions and confirmations of its days,
    stay. Returns the deleted rows per kind. Call inside the caller's
    transaction."""
    return {kind: coach.db.execute(f"DELETE FROM {rows}", params).rowcount
            for kind, rows, params in _erase_parts(coach, phase)}


def last_erase_at(coach: "Coach") -> datetime.datetime | None:
    """When the latest confirmed erase happened (the claim's `decided_at`), or None."""
    at = coach.db.value("SELECT MAX(decided_at) FROM phase_end_requests WHERE effect = ? AND status = 'confirmed'",
                        (EFFECT_ERASE,))
    return datetime.datetime.fromisoformat(at) if at else None


# --- the card ---------------------------------------------------------------------------


def _day(d: Date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def _name(coach: "Coach", phase: dict[str, Any]) -> str:
    return coach.skills.params(phase["phase_id"]).get("name") or phase["phase_id"]


# What the undo card and its outcome show, per erase kind (singular, plural);
# kinds without a label (cards, counter taps) go with their proposals.
LABELS = {
    "targets": ("target", "targets"),
    "proposals": ("proposal", "proposals"),
    "weekly_checkins": ("weekly verdict and report", "weekly verdicts and reports"),
}


def _counted(counts: dict[str, int]) -> list[str]:
    """'the phase and its setup', then '4 weekly verdicts and reports', ..."""
    items = ["the phase and its setup"]
    for kind, (one, many) in LABELS.items():
        n = counts.get(kind, 0)
        items.append(f"{n} {one if n == 1 else many}")
    return items


def _span(phase: dict[str, Any]) -> str:
    start = _day(Date.fromisoformat(phase["start_date"]))
    if phase["end_date"] is None:
        return f"{start} – today"
    return f"{start} – {_day(Date.fromisoformat(phase['end_date']))}, ended"


def _keep(coach: "Coach", today: Date) -> str:
    targets = phases.targets(coach, today)
    goal = f" ({round(targets['mfp_goal']['kcal']):,} kcal)" if targets else ""
    return f"Your MyFitnessPal goal stays as it is{goal}; the coach doesn't touch it. Change it yourself if you like."


def render_undo_card(coach: "Coach", phase: dict[str, Any], today: Date) -> str:
    lines = [f"Erase the phase “{_name(coach, phase)}” ({_span(phase)})?",
             "This deletes it as if it never ran:"]
    lines += [f"- {item}" for item in _counted(erase_counts(coach, phase))]
    lines.append("Kept: everything synced from MyFitnessPal and Hevy, day questions and confirmations, waist and "
                 "photos, your profile, notes and exercise settings, and other phases.")
    if phase["status"] == "active":
        lines.append("From today there's no target. Weekly check-ins, evening reminders and waist/photo reminders "
                     "stop; training feedback and day questions keep running.")
    lines.append(_keep(coach, today))
    lines.append("This can't be undone.")
    return "\n".join(lines) + "\n\nNothing changes until you tap Confirm."


def render_card(coach: "Coach", phase: dict[str, Any], kind: str, today: Date) -> str:
    name = _name(coach, phase)
    open_count = len(proposals.open_proposals(coach, phase))
    keep = _keep(coach, today)
    if kind == EFFECT_ERASE:
        lines = [
            f"End the phase “{name}”?",
            f"It started today ({_day(today)}), so ending it erases it, as if it never started: the phase, its "
            "setup, targets and proposals are deleted, and from today there's no target.",
            "Weekly check-ins, evening reminders and waist/photo reminders stop. Training feedback and day "
            "questions keep running.",
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
            "- Training feedback and day questions keep running.",
            f"- {keep}",
        ]
    return "\n".join(lines) + "\n\nNothing changes until you tap Confirm."


def target(coach: "Coach", mode: str) -> dict[str, Any] | None:
    """The phase a card of this mode is about: the active one to end; the
    active one, else the latest ended one, to undo."""
    return phases.latest(coach) if mode == MODE_UNDO else phases.active(coach)


def _ref(request_id: str) -> str:
    return f"phase-end:{request_id}"


def send_card(coach: "Coach", mode: str, reason: str | None, now: datetime.datetime) -> dict[str, Any]:
    """Send the confirm card for ending the active phase (mode end) or for
    erasing a phase to undo it (mode undo); older open cards are superseded.
    Raises ToolError when there is no such phase."""
    phase = target(coach, mode)
    if phase is None:
        raise ToolError("there is no phase to erase" if mode == MODE_UNDO else "there is no active phase to end")
    if mode == MODE_UNDO:
        kind, text = EFFECT_ERASE, render_undo_card(coach, phase, now.date())
    else:
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
async def endphase_command(coach: "Coach", args: str, now: datetime.datetime) -> None:
    try:
        send_card(coach, MODE_END, args or None, now)
    except ToolError:
        coach.say("No phase is active, so there's nothing to end.")


@registry.tool(
    "request_phase_end",
    "Send the user a confirm card for ending the active phase, when they ask to end or stop it without starting a "
    "new one (mode end). Ending changes nothing until they tap Confirm: then today has no target, open proposals "
    "are withdrawn, check-ins and reminders stop, and the phase stays in the history. Mode undo only when the "
    "user's message explicitly asks to undo or erase a phase (e.g. 'undo it, that was a test'), never to end one: "
    "its card offers to delete the active phase, else the latest ended one, with its setup, targets, proposals, "
    "weekly verdicts and reports, listing the counts. The MFP goal is untouched either "
    "way. This tool itself changes nothing; tell the user the card is below.",
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
async def request_phase_end(coach: "Coach", args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    sent = send_card(coach, args["mode"], args["reason"], now)
    if args["mode"] == MODE_UNDO:
        return {**sent, "say": f"The card to erase “{sent['phase']}” is below with what gets deleted; nothing "
                               "changes until you tap Confirm."}
    erase_note = " It started today, so the card says Confirm erases it." if sent["effect"] == EFFECT_ERASE else ""
    return {**sent, "say": f"The card to end “{sent['phase']}” is below; nothing changes until you tap Confirm."
                           + erase_note}


# --- buttons ----------------------------------------------------------------------------


@registry.button("confirm_phase_end")
async def confirm_phase_end(coach: "Coach", ref_id: str, now: datetime.datetime) -> None:
    at = now.isoformat(timespec="seconds")
    withdrawn: list[str] = []
    ended: str | None = None  # the phase this tap ended
    card_edits: list[tuple[str, str]] = []
    with coach.db.transaction():
        claimed = coach.db.execute(
            "UPDATE phase_end_requests SET status = 'confirmed', decided_at = ? WHERE id = ? AND status = 'open'",
            (at, ref_id)).rowcount == 1
        if not claimed:
            return  # a second tap, a cancelled or replaced card
        request = coach.db.one("SELECT * FROM phase_end_requests WHERE id = ?", (ref_id,))
        undo = request["mode"] == MODE_UNDO
        phase = target(coach, request["mode"])
        if (phase is None or phase["id"] != request["phase_row_id"]
                or (not undo and effect(phase, now.date()) != request["effect"])):
            coach.db.execute("UPDATE phase_end_requests SET status = 'superseded' WHERE id = ?", (ref_id,))
            outcome = ("This card is out of date. Nothing changed; ask again if you still want to erase a phase."
                       if undo else
                       "This card is out of date. Nothing changed; send /endphase again if you still want to end it.")
        elif request["effect"] == EFFECT_ERASE:
            card_edits = [edit for p in proposals.open_proposals(coach, phase)
                          for edit in proposals.card_edits(coach, p["id"], ERASED)]
            counts = erase(coach, phase)
            outcome = f"✅ Erased: {', '.join(_counted(counts))}."
            if phase["status"] == "active":
                outcome += " There's no phase now and no target from today."
            outcome += " MyFitnessPal's goal is unchanged."
        else:
            withdrawn = end(coach, phase, now)
            ended = phase["id"]
            outcome = (f"✅ Ended. Its last day was {_day(now.date() - DAY)}; no target from today. "
                       "MyFitnessPal's goal is unchanged.")
            if withdrawn:
                outcome += f" Withdrawn: {len(withdrawn)} open proposal{'s' if len(withdrawn) > 1 else ''}."
    coach.edit(_ref(ref_id), f"{request['text']}\n\n{outcome}")
    for ref, text in card_edits:
        coach.edit(ref, text)
    for proposal_id in withdrawn:
        proposals.close_cards(coach, proposal_id, "⏹ Phase ended. Nothing changed from this proposal.")
    if ended is not None:
        await _review(coach, ended, now)


async def _review(coach: "Coach", phase_row_id: str, now: datetime.datetime) -> None:
    """The phase review of the phase just ended (coach-reviews ticket 03). A failure never undoes
    the end: it's logged, and the phase-review job catches up."""
    from . import phase_review

    try:
        await phase_review.review_end(coach, phases.get(coach, phase_row_id), now)
    except Exception:
        logger.exception("phase review after the phase end failed")


@registry.button("cancel_phase_end")
async def cancel_phase_end(coach: "Coach", ref_id: str, now: datetime.datetime) -> None:
    claimed = coach.db.execute(
        "UPDATE phase_end_requests SET status = 'cancelled', decided_at = ? WHERE id = ? AND status = 'open'",
        (now.isoformat(timespec="seconds"), ref_id)).rowcount == 1
    if claimed:
        text = coach.db.value("SELECT text FROM phase_end_requests WHERE id = ?", (ref_id,))
        coach.edit(_ref(ref_id), f"{text}\n\n✖️ Cancelled. The phase goes on.")
