"""Training feedback (ticket 12): a newly synced lifting session gets daily
facts (kind training) and the training-feedback skill once; PRs are named,
a stall is flagged the first time, a big drop asks "was this a reset?" with
buttons (exempt from the daily limit), and unremarkable sessions stay quiet.

The reverse from test_weekly_checkin starts Mon 9 Nov 2026 with a bench
history of 80 x 5 on 10 Oct; the daily message limit is 2.
"""

import datetime

from fa_coach import messaging, progression
from fa_coach.ports import ModelError
from fakes import TZ, exercise, reply, reply_json, session, tool_call, tool_calls
from test_weekly_checkin import phase  # noqa: F401


def bench(kg: float, reps: int = 5) -> dict:
    return exercise("Bench Press", (kg, reps))


def at(date: str, hour: int = 12) -> datetime.datetime:
    return datetime.datetime.combine(datetime.date.fromisoformat(date), datetime.time(hour), tzinfo=TZ)


def message(text: str = "", *, send: bool = True, deferred: list[str] | None = None) -> dict:
    return {"send": send, "text": text, "buttons": [], "deferred_to_weekly": deferred or []}


async def lifted(coach, api, clock, when: str, *sessions: dict) -> None:
    """Sessions appear in Hevy; the coach syncs and runs its jobs at noon on `when`."""
    api.sessions += sessions
    clock.current = at(when)
    await coach.sync()
    await coach.run_due_jobs()


def feedback_requests(model) -> list:
    return [r for r in model.requests if r.task_skills == ("training-feedback",)]


def feedback(outbox) -> list:
    """Training feedback messages (the photo reminder also sends on these days)."""
    return [m for m in outbox.sent if (m.ref or "").startswith("training:")]


def deferred(coach, day: str) -> list[str]:
    d = datetime.date.fromisoformat(day)
    return [i["text"] for i in messaging.deferred(coach, d, d)]


def counted(coach, day: str) -> int:
    """Training feedback messages counted toward that day's limit."""
    return coach.db.value("SELECT COUNT(*) FROM unprompted_messages WHERE day = ? AND kind = 'training-feedback'"
                          " AND exempt = 0", (day,))


async def test_a_pr_is_named_once(phase, api, clock, model, outbox):
    model.script(reply_json(message("PR: bench 82.5 × 5.")))

    # n1 is the first session after a break (not judged, nothing to say); n2 beats 80 x 5
    await lifted(phase, api, clock, "2026-11-12", session("n1", "2026-11-10", bench(80)),
                 session("n2", "2026-11-12", bench(82.5)))
    clock.current = at("2026-11-12", 18)
    await phase.sync()
    await phase.run_due_jobs()

    requests = feedback_requests(model)
    assert len(requests) == 1
    facts = requests[0].input
    assert phase.skills.errors(facts, "daily_facts") == []
    assert (facts["kind"], facts["date"], facts["session"]["session_id"]) == ("training", "2026-11-12", "n2")
    ex = facts["session"]["exercises"][0]
    assert (ex["name"], ex["status"], ex["is_pr"]) == ("Bench Press", "improved", True)
    assert requests[0].output_schema == "coach_message" and requests[0].tools == ()
    assert [m.text for m in feedback(outbox)] == ["PR: bench 82.5 × 5."]
    assert feedback(outbox)[0].buttons == ()
    assert counted(phase, "2026-11-12") == 1


async def test_a_stall_is_flagged_the_first_time_only(phase, api, clock, model, outbox):
    model.script(reply_json(message(send=False)), reply_json(message(send=False)),
                 reply_json(message("Bench has stalled: 3 sessions at 80 × 5.")),
                 reply_json(message("Bench still at 80 × 5.")))

    await lifted(phase, api, clock, "2026-11-10", session("n1", "2026-11-10", bench(80)))  # after a break
    for n, day in enumerate(("2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14"), start=2):
        await lifted(phase, api, clock, day, session(f"n{n}", day, bench(80)))

    stalls = [(r.input["session"]["session_id"], r.input["session"]["exercises"][0]["new_stall"])
              for r in feedback_requests(model)]
    assert stalls == [("n2", False), ("n3", False), ("n4", True), ("n5", False)]
    assert [m.text for m in feedback(outbox)] == ["Bench has stalled: 3 sessions at 80 × 5."]
    # the repeat goes to the weekly report, not the chat
    assert deferred(phase, "2026-11-14") == ["Bench still at 80 × 5."]


async def test_an_unremarkable_session_sends_nothing_and_defers_its_note(phase, api, clock, model, outbox):
    model.script(reply_json(message(send=False, deferred=["Bench steady at 80 × 5."])))

    await lifted(phase, api, clock, "2026-11-11", session("n1", "2026-11-10", bench(80)),
                 session("n2", "2026-11-11", bench(80)))

    assert len(feedback_requests(model)) == 1 and feedback(outbox) == []
    assert deferred(phase, "2026-11-11") == ["Bench steady at 80 × 5."]


async def reset_question(phase, api, clock, model, outbox):
    """80 x 5 on the 10th (after a break) and 11th, then 65 x 5 on the 12th: e1RM 93.33 -> 75.83,
    18.8 % down. The day's limit is used up before the session syncs."""
    model.script(reply_json(message(send=False)), reply_json(message("Lighter bench today.")))
    await lifted(phase, api, clock, "2026-11-11", session("n1", "2026-11-10", bench(80)),
                 session("n2", "2026-11-11", bench(80)))
    clock.current = at("2026-11-12", 8)
    while messaging.can_send(phase, clock.now()):
        messaging.send(phase, "something else", clock.now(), kind="test")
    await lifted(phase, api, clock, "2026-11-12", session("n3", "2026-11-12", bench(65)))
    [card] = feedback(outbox)
    return card


async def test_a_big_drop_asks_about_a_reset_past_the_limit_and_mark_reset_starts_a_new_baseline(
        phase, api, clock, model, outbox):
    card = await reset_question(phase, api, clock, model, outbox)

    assert card.text.startswith("Lighter bench today.\n\nBench Press: 18.8 % below your best recent session.")
    assert "technique or range-of-motion change, or an exercise swap" in card.text
    [[mark, keep]] = card.buttons
    assert (mark.action, keep.action, mark.ref_id == keep.ref_id) == ("mark_reset", "not_a_reset", True)

    await phase.on_button(mark.action, mark.ref_id)
    await phase.on_button(keep.action, keep.ref_id)  # a late second tap changes nothing

    n3 = progression.session(phase, "n3")["exercises"][0]
    assert (n3["status"], n3["not_judged_reason"]) == ("new_baseline", "baseline_reset")
    edits = [e for e in outbox.edits if e.ref == card.ref]
    assert edits and all(e.buttons == () for e in edits)
    assert all(e.text.endswith("✓ Bench Press: new baseline from this session.") for e in edits)
    assert phase.db.value("SELECT COUNT(*) FROM baseline_resets") == 1


async def test_not_a_reset_keeps_the_history_and_removes_the_buttons(phase, api, clock, model, outbox):
    card = await reset_question(phase, api, clock, model, outbox)

    await phase.on_button("not_a_reset", card.buttons[0][1].ref_id)

    assert progression.session(phase, "n3")["exercises"][0]["status"] == "declined"
    [edit] = [e for e in outbox.edits if e.ref == card.ref]
    assert edit.buttons == () and edit.text.endswith("✓ Bench Press: not a reset, compared as usual.")
    assert phase.db.value("SELECT COUNT(*) FROM baseline_resets") == 0


async def test_without_a_model_answer_the_reset_question_still_goes_out(phase, api, clock, model, outbox):
    model.script(reply_json(message(send=False)), ModelError("overloaded"))
    await lifted(phase, api, clock, "2026-11-11", session("n1", "2026-11-10", bench(80)),
                 session("n2", "2026-11-11", bench(80)))
    await lifted(phase, api, clock, "2026-11-12", session("n3", "2026-11-12", bench(65)))

    [card] = feedback(outbox)
    assert card.text.startswith("Bench Press: 18.8 % below") and len(card.buttons) == 1


# --- chat: pause and reset -------------------------------------------------------------


async def test_an_injury_note_does_not_pause_and_a_paused_exercise_is_not_judged(phase, api, clock, model, outbox):
    model.script(reply_json(message(send=False)))
    await lifted(phase, api, clock, "2026-11-11", session("n1", "2026-11-10", bench(80)),
                 session("n2", "2026-11-11", bench(80)))
    model.script(tool_call("add_context_note", applies_from="2026-11-11", tags=["injury"],
                           exercise_id="bench-press", suggest_unusable="no"),
                 reply("Noted. Want me to pause bench tracking while the shoulder heals?"))
    await phase.on_message("my shoulder hurts on bench")
    assert progression.settings(phase).get("bench-press", {}).get("paused", 0) == 0

    start = len(model.requests)
    model.script(tool_call("set_exercise_paused", exercise_id="bench-press", paused=True, reason="shoulder"),
                 reply("Bench is paused."))
    await phase.on_message("yes, pause it")
    assert model.results(start)[0].content["paused"] is True

    await lifted(phase, api, clock, "2026-11-13", session("n3", "2026-11-13", bench(90)))  # would be a PR

    assert progression.session(phase, "n3")["exercises"][0]["status"] == "paused"
    assert len(feedback_requests(model)) == 1 and feedback(outbox) == []  # no model call for n3


async def test_mark_baseline_reset_from_chat_starts_a_new_baseline_from_that_day(phase, api, clock, model, outbox):
    model.script(reply_json(message(send=False)))
    await lifted(phase, api, clock, "2026-11-11", session("n1", "2026-11-10", bench(80)),
                 session("n2", "2026-11-11", bench(80)))
    start = len(model.requests)
    model.script(tool_calls(("mark_baseline_reset", {"exercise_id": "nope", "reason": "rom_change"}),
                            ("mark_baseline_reset", {"exercise_id": "bench-press", "reason": "rom_change"})),
                 reply("New baseline for bench from today's session."))
    clock.current = at("2026-11-11", 18)
    await phase.on_message("I paused at the chest today and will from now on")

    unknown, ok = model.results(start)
    assert unknown.is_error and "not in the synced Hevy history" in unknown.content["error"]
    assert ok.content["new_baseline_session_date"] == "2026-11-11"

    model.script(reply_json(message(send=False)))
    await lifted(phase, api, clock, "2026-11-12", session("n3", "2026-11-12", bench(85)))
    assert progression.session(phase, "n2")["exercises"][0]["status"] == "new_baseline"
    n3 = progression.session(phase, "n3")["exercises"][0]
    assert n3["status"] == "improved" and n3["best_recent"]["load_kg"] == 80
