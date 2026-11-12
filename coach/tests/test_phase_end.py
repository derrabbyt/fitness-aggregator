"""Ending a phase (coach-followups ticket 01): `/endphase` or the chat tool
`request_phase_end` (mode end) sends a confirm card; nothing changes until
Confirm. Confirm ends the active phase right away (its last day is
yesterday), withdraws open proposals, stops the check-ins and reminders,
and leaves the MFP goal alone. Training feedback keeps running.

The reverse from test_weekly_checkin starts Mon 9 Nov 2026 09:00.
"""

import datetime

from fa_coach import phases, proposals
from fa_coach.db import MIGRATIONS, Database
from fakes import TZ, exercise, reply, reply_json, session, tool_call
from test_phase_start import card as start_card
from test_phase_start import start_and_collect
from test_proposals import last_card, two_c_weeks
from test_weekly_checkin import fill_week, phase  # noqa: F401


def at(date: str, hour: int = 12) -> datetime.datetime:
    return datetime.datetime.combine(datetime.date.fromisoformat(date), datetime.time(hour), tzinfo=TZ)


def end_card(outbox):
    cards = [m for m in outbox.sent if (m.ref or "").startswith("phase-end:")]
    assert cards, "no end card sent"
    return cards[-1]


def button(card, action: str):
    return next(b for row in card.buttons for b in row if b.action == action)


async def confirm(coach, outbox, now, taps: int = 1) -> None:
    tap = button(end_card(outbox), "confirm_phase_end")
    for _ in range(taps):
        await coach.on_button(tap.action, tap.ref_id, now)


# --- the card ----------------------------------------------------------------------------


async def test_endphase_sends_a_card_and_changes_nothing(phase, clock, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")

    card = end_card(outbox)
    assert [b.action for row in card.buttons for b in row] == ["confirm_phase_end", "cancel_phase_end"]
    assert "Reverse" in card.text or "reverse" in card.text
    for words in ("no target", "withdrawn", "check-ins", "reminders", "MyFitnessPal goal", "Training feedback"):
        assert words in card.text, words
    assert "19 Nov" in card.text or "2026-11-19" in card.text  # the last day
    assert phases.active(phase) is not None


async def test_confirm_ends_the_phase_from_today_once(phase, clock, api, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")
    writes = list(api.goal_writes())

    await confirm(phase, outbox, at("2026-11-20", 13), taps=2)

    assert phases.active(phase) is None
    ended = phases.latest(phase)
    assert (ended["status"], ended["end_date"]) == ("ended", "2026-11-19")
    assert ended["ended_at"].startswith("2026-11-20T13:00")
    assert phases.daily_target(phase, datetime.date(2026, 11, 20)) is None
    assert api.goal_writes() == writes  # the MFP goal is left alone
    edits = [e for e in outbox.edits if e.ref == end_card(outbox).ref]
    assert len(edits) == 1 and edits[0].buttons == ()
    assert "Ended" in edits[0].text


async def test_cancel_changes_nothing_and_a_later_confirm_is_ignored(phase, clock, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")
    card = end_card(outbox)

    await phase.on_button("cancel_phase_end", button(card, "cancel_phase_end").ref_id, at("2026-11-20", 13))
    await confirm(phase, outbox, at("2026-11-20", 14))

    assert phases.active(phase) is not None
    edits = [e for e in outbox.edits if e.ref == card.ref]
    assert len(edits) == 1 and "Cancelled" in edits[0].text and edits[0].buttons == ()


async def test_a_newer_card_replaces_the_older_one(phase, clock, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")
    first = end_card(outbox)
    await phase.on_message("/endphase")

    assert end_card(outbox).ref != first.ref
    assert [e.text.endswith("Nothing changed.") for e in outbox.edits if e.ref == first.ref] == [True]
    await phase.on_button("confirm_phase_end", button(first, "confirm_phase_end").ref_id, at("2026-11-20", 13))
    assert phases.active(phase) is not None


async def test_the_chat_tool_only_sends_the_card(phase, clock, model, outbox):
    clock.current = at("2026-11-20")
    model.script(tool_call("request_phase_end", mode="end", reason="test phase"), reply("The card is below."))
    await phase.on_message("let's end the reverse, it was a test")

    assert phases.active(phase) is not None
    assert "Nothing changes until you tap Confirm" in end_card(outbox).text
    result = model.results(len(model.requests) - 2)[0]
    assert not result.is_error and result.content["effect"] == "end"
    await confirm(phase, outbox, at("2026-11-20", 13))
    assert phases.active(phase) is None


async def test_without_an_active_phase_there_is_no_card(coach, outbox):
    await coach.on_message("/endphase")

    assert outbox.texts == ["No phase is active, so there's nothing to end."]


# --- span ----------------------------------------------------------------------------------


async def test_the_ended_phase_covers_its_days_only(phase, clock, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-11-20", 13))

    assert phases.on(phase, datetime.date(2026, 11, 8)) is None
    assert phases.on(phase, datetime.date(2026, 11, 9))["status"] == "ended"
    assert phases.on(phase, datetime.date(2026, 11, 19))["status"] == "ended"
    assert phases.on(phase, datetime.date(2026, 11, 20)) is None
    week = phase.view("week", {"week": "2026-W47"}, now=at("2026-11-20", 14))
    assert week["phase_week"] == 2


# --- ending on the start day ---------------------------------------------------------------


async def test_ending_on_the_start_day_erases_the_phase(phase, clock, outbox):
    clock.current = at("2026-11-09", 18)
    await phase.on_message("/endphase")
    card = end_card(outbox)
    assert "erases" in card.text

    await confirm(phase, outbox, at("2026-11-09", 19))

    assert phases.latest(phase) is None and phases.on(phase, datetime.date(2026, 11, 9)) is None
    assert phase.db.value("SELECT COUNT(*) FROM targets") == 0
    assert phase.db.value("SELECT COUNT(*) FROM phase_setups") == 0
    assert "Erased" in [e for e in outbox.edits if e.ref == card.ref][-1].text


async def test_a_phase_replaced_on_another_day_ends_the_day_before(phase, clock, model, outbox):
    clock.current = at("2026-11-20")
    await start_and_collect(phase, model)
    confirm_start = start_card(outbox).buttons[0][0]
    await phase.on_button(confirm_start.action, confirm_start.ref_id, at("2026-11-20", 13))

    old = phases.on(phase, datetime.date(2026, 11, 19))
    assert (old["status"], old["end_date"]) == ("ended", "2026-11-19")
    assert phases.on(phase, datetime.date(2026, 11, 20))["status"] == "active"


# --- effects --------------------------------------------------------------------------------


async def test_open_proposals_are_withdrawn_and_their_cards_edited(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    proposal = proposals.open_proposals(phase)[0]
    report = last_card(outbox)

    await phase.on_message("/endphase", at("2026-12-07", 10))
    assert "1 open" in end_card(outbox).text
    await confirm(phase, outbox, at("2026-12-07", 11))

    assert proposals.get(phase, proposal["id"])["status"] == "superseded"
    edits = [e for e in outbox.edits if e.ref == report.ref]
    assert edits and "Phase ended" in edits[-1].text and edits[-1].buttons == ()
    assert "Withdrawn: 1 open proposal" in [e for e in outbox.edits if e.ref == end_card(outbox).ref][-1].text
    await phase.on_button("approve_proposal", proposal["id"], at("2026-12-07", 12))
    assert proposals.get(phase, proposal["id"])["status"] == "superseded"


async def test_check_ins_and_reminders_stop(phase, api, clock, model, outbox):
    fill_week(api, 1)
    fill_week(api, 2)
    clock.current = at("2026-11-12")
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-11-12", 13))
    outbox.clear()

    # The evening of the end day, the next Monday's check-in time and the
    # measurement days that follow: nothing is sent and the model isn't asked.
    for day, hour in (("2026-11-12", 22), ("2026-11-16", 9), ("2026-11-16", 22), ("2026-11-23", 9),
                      ("2026-11-23", 22)):
        clock.current = at(day, hour)
        await phase.sync()
        await phase.run_due_jobs()

    assert outbox.sent == []
    assert phase.db.value("SELECT COUNT(*) FROM weekly_checkins") == 0


# --- training feedback ------------------------------------------------------------------------


def bench(kg: float, reps: int = 5) -> dict:
    return exercise("Bench Press", (kg, reps))


async def lifted(coach, api, clock, when: str, *sessions: dict) -> None:
    api.sessions += sessions
    clock.current = at(when)
    await coach.sync()
    await coach.run_due_jobs()


def feedback(outbox) -> list:
    return [m for m in outbox.sent if (m.ref or "").startswith("training:")]


def message(text: str) -> dict:
    return {"send": True, "text": text, "buttons": [], "deferred_to_weekly": []}


async def test_training_feedback_keeps_running_after_the_phase_ended(phase, api, clock, model, outbox):
    clock.current = at("2026-11-12")
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-11-12", 13))
    model.script(reply_json(message("PR: bench 82.5 × 5.")))

    # n1 is the first session after a break (a baseline, nothing to say); n2 beats it
    await lifted(phase, api, clock, "2026-11-13", session("n1", "2026-11-13", bench(80)))
    await lifted(phase, api, clock, "2026-11-14", session("n2", "2026-11-14", bench(82.5)))

    assert [m.text for m in feedback(outbox)] == ["PR: bench 82.5 × 5."]
    facts = [r for r in model.requests if r.task_skills == ("training-feedback",)][-1].input
    assert (facts["phase_id"], facts["phase_week"]) == (None, None)
    assert phase.skills.errors(facts, "daily_facts") == []


async def test_without_any_phase_feedback_starts_with_sessions_seen_after_the_first_run(coach, api, clock, model,
                                                                                         outbox):
    # The backlog synced on the first run gets nothing, though n2 would be a PR.
    await lifted(coach, api, clock, "2026-11-10", session("n0", "2026-10-10", bench(80)),
                 session("n1", "2026-11-09", bench(80)), session("n2", "2026-11-10", bench(82.5)))
    assert feedback(outbox) == []

    model.script(reply_json(message("PR: bench 85 × 5.")))
    await lifted(coach, api, clock, "2026-11-11", session("n3", "2026-11-11", bench(85)))

    assert [m.text for m in feedback(outbox)] == ["PR: bench 85 × 5."]


# --- migration ------------------------------------------------------------------------------


def test_the_migration_gives_ended_phases_their_last_day(tmp_path, make_coach, db_path):
    older = tmp_path / "before"
    older.mkdir()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name < "22_":
            (older / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    db = Database(db_path, migrations=older)
    db.execute("INSERT INTO phase_setups (id, phase_id, status, created_at, updated_at) VALUES"
               " ('s1', 'reverse_bulk', 'confirmed', 'x', 'x'), ('s2', 'reverse_bulk', 'confirmed', 'x', 'x')")
    db.execute("INSERT INTO phases (id, phase_id, setup_id, status, start_date, setup, started_at, ended_at) VALUES"
               " ('p1', 'reverse_bulk', 's1', 'ended', '2026-09-01', '{}', '2026-09-01T09:00:00+02:00',"
               "  '2026-10-05T09:00:00+02:00'),"
               " ('p2', 'reverse_bulk', 's2', 'active', '2026-10-05', '{}', '2026-10-05T09:00:00+02:00', NULL)")
    db.conn.close()

    coach = make_coach()

    assert phases.on(coach, datetime.date(2026, 10, 4))["id"] == "p1"
    assert phases.on(coach, datetime.date(2026, 10, 5))["id"] == "p2"
    assert phases.latest(coach)["end_date"] is None


async def test_a_start_day_card_tapped_the_next_day_changes_nothing(phase, clock, outbox):
    clock.current = at("2026-11-09", 18)
    await phase.on_message("/endphase")

    await confirm(phase, outbox, at("2026-11-10", 8))

    assert phases.active(phase) is not None
    assert "out of date" in outbox.edits[-1].text
