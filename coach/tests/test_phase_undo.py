"""Undoing (erasing) a phase (coach-followups ticket 02): only when the user's
message explicitly asks, the chat tool `request_phase_end` with mode `undo`
sends a card listing what would be deleted, with counts. Confirm deletes the
phase and everything that hangs on it in one transaction; other phases and
the MFP goal stay. It works on the active phase and on the latest ended one.

The reverse from test_weekly_checkin starts Mon 9 Nov 2026 09:00.
"""

import datetime

from fa_coach import body_fat, phases, reviews
from fa_coach.features import training_feedback
from fakes import reply, reply_json, session, tool_call
from test_phase_end import at, bench, button, end_card, feedback, lifted, message
from test_phase_start import card as start_card
from test_phase_start import start_and_collect
from test_proposals import last_card, two_c_weeks
from test_weekly_checkin import phase  # noqa: F401


async def ask_undo(coach, model, now: datetime.datetime, words: str = "undo the phase, it was a test") -> None:
    model.script(tool_call("request_phase_end", mode="undo", reason="it was a test"), reply("The card is below."))
    await coach.on_message(words, now)


async def confirm(coach, outbox, now: datetime.datetime, taps: int = 1) -> None:
    tap = button(end_card(outbox), "confirm_phase_end")
    for _ in range(taps):
        await coach.on_button(tap.action, tap.ref_id, now)


def day_question(coach, date: str) -> None:
    coach.db.execute("INSERT INTO day_questions (date, kind, kcal, status, found_at)"
                     " VALUES (?, 'partial', 900, 'asked', 'x')", (date,))


def day_confirmation(coach, date: str) -> None:
    coach.db.execute("INSERT INTO day_confirmations (date, kind, kcal, source, confirmed_at)"
                     " VALUES (?, 'complete', 900, 'button', 'x')", (date,))


def count(coach, table: str) -> int:
    return coach.db.value(f"SELECT COUNT(*) FROM {table}")


# --- the card ----------------------------------------------------------------------------


async def test_the_undo_card_lists_what_goes_with_counts_and_changes_nothing(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    day_question(phase, "2026-11-20")
    day_confirmation(phase, "2026-11-21")
    day_confirmation(phase, "2026-11-22")

    await ask_undo(phase, model, at("2026-12-07", 10))

    text = end_card(outbox).text
    assert "Erase" in text and "Reverse" in text
    for line in ("- 4 weekly verdicts and reports", "- 1 proposal", "- 1 target"):
        assert line in text, line
    assert "- 1 day question" not in text and "- 2 day confirmations" not in text  # they belong to the days
    assert "day questions and confirmations" in text  # on the Kept line
    assert "MyFitnessPal goal" in text and "Nothing changes until you tap Confirm" in text
    assert phases.active(phase) is not None and count(phase, "weekly_checkins") == 4
    result = model.results(len(model.requests) - 2)[0]
    assert not result.is_error and result.content["effect"] == "erase"


# --- confirm ------------------------------------------------------------------------------


TABLES = ("phases", "phase_setups", "targets", "proposals", "proposal_cards", "weekly_checkins")


async def test_confirm_erases_the_active_phase_once_and_closes_its_proposal_cards(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    day_question(phase, "2026-11-20")
    day_confirmation(phase, "2026-11-21")
    day_confirmation(phase, "2026-11-01")  # before the phase
    report = last_card(outbox)
    writes = list(api.goal_writes())
    await ask_undo(phase, model, at("2026-12-07", 10))

    await confirm(phase, outbox, at("2026-12-07", 11), taps=2)

    assert phases.latest(phase) is None
    assert {t: count(phase, t) for t in TABLES} == {t: 0 for t in TABLES}
    # Day questions and confirmations belong to the days, not the phase: they stay.
    assert (count(phase, "day_questions"), count(phase, "day_confirmations")) == (1, 2)
    assert api.goal_writes() == writes
    edits = [e for e in outbox.edits if e.ref == end_card(outbox).ref]
    assert len(edits) == 1 and edits[0].buttons == ()
    assert "Erased" in edits[0].text and "4 weekly verdicts and reports" in edits[0].text
    report_edits = [e for e in outbox.edits if e.ref == report.ref]
    assert report_edits and "Phase erased" in report_edits[-1].text and report_edits[-1].buttons == ()


def review(coach, kind: str, key: str, phase_row_id: str, day: str) -> int:
    return reviews.send(coach, kind=kind, key=key, phase_row_id=phase_row_id, period_start=day, period_end=day,
                        facts={}, text=f"{kind} review {key}", now=at(day, 9))


async def test_undo_erases_the_phases_reviews_and_keeps_the_body_fat_estimates(phase, clock, model, outbox):
    pid = phases.active(phase)["id"]
    photo = review(phase, "photo", "2026-11-09", pid, "2026-11-09")
    body_fat.add(phase, "2026-11-09", 19.0, "model", at("2026-11-09", 9), review_id=photo)
    review(phase, "block", f"{pid}:1", pid, "2026-11-20")
    review(phase, "block", "other:1", "other", "2026-11-20")  # another phase's

    await ask_undo(phase, model, at("2026-11-22", 10))
    assert "- 2 reviews" in end_card(outbox).text
    await confirm(phase, outbox, at("2026-11-22", 11))

    assert [r["text"] for r in reviews.sent_between(phase, datetime.date(2026, 11, 1), datetime.date(2026, 12, 1))] \
        == ["block review other:1"]
    assert body_fat.on(phase, "2026-11-09")["pct"] == 19.0
    assert "2 reviews" in [e for e in outbox.edits if e.ref == end_card(outbox).ref][-1].text


async def test_undo_erases_only_its_phase(phase, clock, model, outbox):
    # The reverse from 9 Nov is replaced on 20 Nov: it ends on the 19th.
    clock.current = at("2026-11-20")
    await start_and_collect(phase, model)
    confirm_start = start_card(outbox).buttons[0][0]
    await phase.on_button(confirm_start.action, confirm_start.ref_id, at("2026-11-20", 13))
    older = phases.on(phase, datetime.date(2026, 11, 19))
    before = {t: count(phase, t) for t in TABLES}

    await ask_undo(phase, model, at("2026-11-22", 10))
    await confirm(phase, outbox, at("2026-11-22", 11))

    assert phases.active(phase) is None
    assert phases.latest(phase) == older
    assert {t: count(phase, t) for t in ("phases", "phase_setups", "targets")} == {
        "phases": before["phases"] - 1, "phase_setups": before["phase_setups"] - 1,
        "targets": before["targets"] - 1}


async def test_undo_erases_the_latest_ended_phase(phase, clock, model, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-11-20", 13))

    await ask_undo(phase, model, at("2026-11-21", 10), "erase that phase too, it was a test")
    card = end_card(outbox)
    assert "Mon 9 Nov – Thu 19 Nov, ended" in card.text and "From today there's no target" not in card.text
    await confirm(phase, outbox, at("2026-11-21", 11))

    assert phases.latest(phase) is None and count(phase, "targets") == 0
    assert phases.on(phase, datetime.date(2026, 11, 12)) is None


async def test_the_erase_is_one_transaction(phase, api, clock, model, outbox, monkeypatch):
    await two_c_weeks(phase, api, clock, model)
    await ask_undo(phase, model, at("2026-12-07", 10))
    before = {t: count(phase, t) for t in TABLES}
    execute = phase.db.execute

    def failing(sql, *args, **kwargs):
        if sql.startswith("DELETE FROM phases"):
            raise RuntimeError("disk full")
        return execute(sql, *args, **kwargs)

    monkeypatch.setattr(phase.db, "execute", failing)
    try:
        await confirm(phase, outbox, at("2026-12-07", 11))
    except RuntimeError:
        pass
    monkeypatch.undo()

    assert {t: count(phase, t) for t in TABLES} == before
    assert phases.active(phase) is not None
    await confirm(phase, outbox, at("2026-12-07", 12))  # the card is still open
    assert phases.latest(phase) is None


async def test_an_undo_card_is_out_of_date_once_another_phase_is_the_latest(phase, clock, model, outbox):
    clock.current = at("2026-11-20")
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-11-20", 13))
    ended = phases.latest(phase)
    await ask_undo(phase, model, at("2026-11-21", 10))
    undo_card = end_card(outbox)
    clock.current = at("2026-11-23")
    await start_and_collect(phase, model)
    confirm_start = start_card(outbox).buttons[0][0]
    await phase.on_button(confirm_start.action, confirm_start.ref_id, at("2026-11-23", 13))

    tap = button(undo_card, "confirm_phase_end")
    await phase.on_button(tap.action, tap.ref_id, at("2026-11-23", 14))

    assert phases.on(phase, datetime.date(2026, 11, 12)) == ended and phases.active(phase) is not None
    assert "out of date" in [e for e in outbox.edits if e.ref == undo_card.ref][-1].text


async def test_without_any_phase_there_is_nothing_to_undo(coach, model, outbox):
    await ask_undo(coach, model, at("2026-11-21", 10))

    result = model.results(0)[0]
    assert result.is_error and "no phase to erase" in str(result.content)
    assert not [m for m in outbox.sent if (m.ref or "").startswith("phase-end:")]


async def test_after_an_erase_training_feedback_starts_with_sessions_seen_after_it(phase, api, clock, model, outbox):
    phase.db.once(training_feedback.NO_PHASE_SINCE, at("2026-11-01"))  # the job ran before there was a phase
    # n1 (dated before the phase start) is synced during the phase: no feedback then, nor after the erase.
    await lifted(phase, api, clock, "2026-11-10", session("n0", "2026-11-07", bench(80)),
                 session("n1", "2026-11-08", bench(85)))
    await ask_undo(phase, model, at("2026-11-10", 13))
    await confirm(phase, outbox, at("2026-11-10", 14))
    clock.current = at("2026-11-10", 15)
    await phase.run_due_jobs()
    assert feedback(outbox) == [] and not [r for r in model.requests if r.task_skills == ("training-feedback",)]

    model.script(reply_json(message("PR: bench 87.5 × 5.")))
    await lifted(phase, api, clock, "2026-11-11", session("n2", "2026-11-11", bench(87.5)))

    assert [m.text for m in feedback(outbox)] == ["PR: bench 87.5 × 5."]
