"""Block review (coach-reviews ticket 02): every `block_weeks` weeks (a setup
value with history, default 5) from the phase start, code computes the
block's training facts and the block-review skill writes the report and its
advice in words, never a proposal. "Block done" (chat tool `end_block`) ends
the current block today and restarts the count. Each review is sent and
stored once.

The reverse of test_weekly_checkin starts Mon 9 Nov 2026 (bench 80 x 5 on
10 Oct before it). With 5-week blocks block 1 is 9 Nov - 13 Dec, reviewed on
Mon 14 Dec; block 2 is 14 Dec - 17 Jan. The seeded plan has 5 planned lifting
sessions a week (Mon, Tue, Wed, Thu, Sat): 25 in a 5-week block.

Only the block-review job runs here (`reviewer`): the other jobs (weekly
check-in, new exercises, training feedback) have their own tests.
"""

import copy
import datetime

from fa_coach import phases, progression, reviews
from fa_coach.registry import default_registry
from fakes import exercise, reply, reply_json, session, tool_call
from test_weekly_checkin import at, phase  # noqa: F401

Date = datetime.date


def message(text: str) -> dict:
    return {"send": True, "text": text, "buttons": [], "deferred_to_weekly": []}


def reviewer(make_coach):
    """The same database with only the block-review job registered."""
    registry = copy.copy(default_registry())
    registry._jobs = {k: v for k, v in registry._jobs.items() if k == "block-review"}
    return make_coach(registry=registry)


def block_requests(model) -> list:
    return [r for r in model.requests if r.task_skills == ("block-review",)]


def block_reviews(coach) -> list[dict]:
    return reviews.sent_between(coach, Date(2026, 1, 1), Date(2027, 12, 31))


def last_tool_result(model):
    """The result of the last tool call in a chat (block reviews run inside the end_block call)."""
    chat = [r for r in model.requests if r.task_skills != ("block-review",) and r.steps][-1]
    return chat.steps[-1][1][0]


async def run_jobs(coach, clock, when: datetime.datetime) -> None:
    clock.current = when
    await coach.run_due_jobs()


async def set_block_weeks(coach, model, weeks: int, now: datetime.datetime) -> None:
    start = len(model.requests)
    model.script(tool_call("record_setup_value", key="block_weeks", value=weeks), reply("Done."))
    await coach.on_message(f"my blocks are {weeks} weeks", now)
    assert not model.results(start)[0].is_error


# --- schedule --------------------------------------------------------------------------------


async def test_a_block_is_reviewed_the_day_after_its_last_day_once(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await run_jobs(coach, clock, at("2026-12-13", 21))
    assert block_requests(model) == [] and outbox.texts == []

    model.script(reply_json(message("Block 1: solid.")))
    await run_jobs(coach, clock, at("2026-12-14", 7))
    await run_jobs(coach, clock, at("2026-12-14", 8))  # once

    request = block_requests(model)[0]
    assert len(block_requests(model)) == 1
    assert request.decision is True and request.tools == () and request.output_schema == "coach_message"
    assert coach.skills.errors(request.input, "block_facts") == []
    assert request.input["block"] == {"number": 1, "start_date": "2026-11-09", "end_date": "2026-12-13",
                                      "days": 35, "block_weeks": 5, "ended_early": False, "reason": None}
    assert outbox.texts == ["Block 1: solid."]
    [stored] = block_reviews(coach)
    assert (stored["kind"], stored["period_start"], stored["period_end"]) == ("block", "2026-11-09", "2026-12-13")
    assert stored["facts"]["block"]["number"] == 1


async def test_the_next_block_starts_the_day_after_the_last_one_ended(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    model.script(reply_json(message("Block 1.")), reply_json(message("Block 2.")))
    await run_jobs(coach, clock, at("2026-12-14", 7))
    await run_jobs(coach, clock, at("2027-01-17", 21))
    assert outbox.texts == ["Block 1."]

    await run_jobs(coach, clock, at("2027-01-18", 7))

    assert outbox.texts == ["Block 1.", "Block 2."]
    assert block_requests(model)[1].input["block"]["number"] == 2
    assert [(r["period_start"], r["period_end"]) for r in block_reviews(coach)] == [
        ("2026-11-09", "2026-12-13"), ("2026-12-14", "2027-01-17")]


async def test_block_weeks_is_a_setup_value_with_history(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await set_block_weeks(coach, model, 4, at("2026-11-20", 12))

    assert phases.params_on(coach, Date(2026, 11, 19))["reviews"]["block_weeks"] == 5
    assert phases.params_on(coach, Date(2026, 11, 20))["reviews"]["block_weeks"] == 4
    await run_jobs(coach, clock, at("2026-12-06", 21))
    assert block_requests(model) == []

    model.script(reply_json(message("Four weeks done.")))
    await run_jobs(coach, clock, at("2026-12-07", 7))

    assert block_requests(model)[0].input["block"]["end_date"] == "2026-12-06"
    assert block_requests(model)[0].input["block"]["block_weeks"] == 4
    assert outbox.texts[-1] == "Four weeks done."


async def test_a_block_weeks_value_out_of_range_is_refused(phase, clock, model):
    start = len(model.requests)
    model.script(tool_call("record_setup_value", key="block_weeks", value=0), reply("No."))
    await phase.on_message("blocks of 0 weeks", at("2026-11-20", 12))
    assert model.results(start)[0].is_error


async def test_without_an_active_phase_no_block_is_reviewed(coach, make_coach, clock, model, outbox):
    await run_jobs(reviewer(make_coach), clock, at("2026-12-14", 7))
    assert block_requests(model) == [] and outbox.texts == []


# --- "block done" ----------------------------------------------------------------------------


async def test_block_done_ends_the_block_today_and_restarts_the_count(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    clock.current = at("2026-11-25", 19)
    model.script(tool_call("end_block", reason="Felt beat up, deloading next week."),
                 reply_json(message("Block 1 (ended early): time for a lighter week.")),
                 reply("Done, block 1 is closed."))

    await coach.on_message("block done, I'm deloading next week")

    assert not last_tool_result(model).is_error
    facts = block_requests(model)[0].input
    assert facts["block"] == {"number": 1, "start_date": "2026-11-09", "end_date": "2026-11-25", "days": 17,
                              "block_weeks": 5, "ended_early": True,
                              "reason": "Felt beat up, deloading next week."}
    assert outbox.texts == ["Block 1 (ended early): time for a lighter week.", "Done, block 1 is closed."]

    # Block 2 starts 26 Nov and ends 5 weeks later, 30 Dec.
    await run_jobs(coach, clock, at("2026-12-30", 21))
    assert len(block_requests(model)) == 1
    model.script(reply_json(message("Block 2.")))
    await run_jobs(coach, clock, at("2026-12-31", 7))
    assert block_requests(model)[1].input["block"]["start_date"] == "2026-11-26"
    assert block_requests(model)[1].input["block"]["end_date"] == "2026-12-30"


async def test_block_done_twice_on_one_day_is_refused(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    clock.current = at("2026-11-25", 19)
    model.script(tool_call("end_block", reason="done"), reply_json(message("Block 1.")), reply("Closed."),
                 tool_call("end_block", reason="done again"), reply("Already closed."))
    await coach.on_message("block done")
    await coach.on_message("block done")

    assert last_tool_result(model).is_error
    assert len(block_reviews(coach)) == 1


async def test_without_a_model_answer_the_review_still_goes_out_with_codes_summary(
        phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    model.script(reply("not json"))
    await run_jobs(coach, clock, at("2026-12-14", 7))
    await run_jobs(coach, clock, at("2026-12-14", 8))

    assert len(outbox.texts) == 1 and outbox.texts[0].startswith("Block review: block 1 (9 Nov - 13 Dec)")
    assert len(block_reviews(coach)) == 1


# --- facts -----------------------------------------------------------------------------------


def lifting(api) -> None:
    """Block 1: bench holds at 80 x 5 (back from a break on 16 Nov, then 3 sessions without
    progress: stalled); squat and deadlift improve on 19 Nov, then decline twice (deload
    signal); 30 Nov is a long session (22 working sets); curls are excluded."""
    api.sessions += [
        session("s1", "2026-11-16", exercise("Bench Press", (80, 5)), exercise("Squat", (100, 5)),
                exercise("Deadlift", (140, 5))),
        session("s2", "2026-11-19", exercise("Squat", (105, 5)), exercise("Deadlift", (145, 5))),
        session("s3", "2026-11-23", exercise("Bench Press", (80, 5)), exercise("Squat", (100, 5)),
                exercise("Deadlift", (140, 5))),
        session("s4", "2026-11-30", exercise("Bench Press", *[(80, 5)] * 6), exercise("Squat", *[(95, 5)] * 6),
                exercise("Deadlift", *[(135, 5)] * 4), exercise("Bicep Curl", *[(15, 10)] * 6)),
        session("s5", "2026-12-07", exercise("Bench Press", (80, 5))),
    ]


async def block_one_facts(phase, make_coach, api, clock, model) -> dict:
    lifting(api)
    clock.current = at("2026-12-14", 6)
    await phase.sync()
    coach = reviewer(make_coach)
    progression.classify(coach, "bicep-curl", "excluded", "slow mover", at("2026-11-30", 12))
    model.script(reply_json(message("Block 1.")))
    await run_jobs(coach, clock, at("2026-12-14", 7))
    facts = block_requests(model)[0].input
    assert coach.skills.errors(facts, "block_facts") == []
    return facts


async def test_block_facts_name_stalls_and_the_deload_signal(phase, make_coach, api, clock, model):
    facts = await block_one_facts(phase, make_coach, api, clock, model)

    lifts = {lift["name"]: lift for lift in facts["lifts"]}
    assert set(lifts) == {"Bench Press", "Squat", "Deadlift", "Bicep Curl"}
    bench, squat = lifts["Bench Press"], lifts["Squat"]
    assert (bench["sessions"], bench["statuses"], bench["stalled_at_end"]) == (
        4, {"improved": 0, "same": 3, "declined": 0}, True)
    assert (squat["statuses"], squat["decline_streak_at_end"], squat["change_pct"]) == (
        {"improved": 1, "same": 0, "declined": 2}, 2, -5.0)
    assert squat["first"]["top_set"]["load_kg"] == 100 and squat["last"]["top_set"]["load_kg"] == 95
    assert lifts["Bicep Curl"]["counts"] is False and lifts["Bicep Curl"]["stalled_at_end"] is False

    t = facts["training"]
    assert t["stalls"] == ["Bench Press"]
    assert t["declining_lifts"] == ["Deadlift", "Squat"]
    assert t["deload_signal"] is True
    assert t["strength_trend"]["direction"] == "falling"
    assert t["strength_trend"]["change_pct"] == -2.9  # mean of bench 0, squat -5, deadlift -3.6
    assert t["prs"] == [{"name": "Deadlift", "date": "2026-11-19"}, {"name": "Squat", "date": "2026-11-19"}]


async def test_block_facts_count_sessions_against_the_plan(phase, make_coach, api, clock, model):
    facts = await block_one_facts(phase, make_coach, api, clock, model)

    assert facts["sessions"] == {"done": 5, "planned": 25, "skipped": 0}


async def test_block_facts_note_long_sessions_with_sets_per_exercise(phase, make_coach, api, clock, model):
    facts = await block_one_facts(phase, make_coach, api, clock, model)

    volume = facts["volume"]
    assert (volume["max_sets_per_session"], volume["max_sets_per_muscle_per_session"]) == (20, 4)
    assert [(s["date"], s["working_sets"], s["over_limit"]) for s in volume["sessions"]] == [
        ("2026-11-16", 3, False), ("2026-11-19", 2, False), ("2026-11-23", 3, False), ("2026-11-30", 22, True),
        ("2026-12-07", 1, False)]
    long = volume["sessions"][3]
    assert long["exercises"] == [{"name": "Bench Press", "working_sets": 6}, {"name": "Squat", "working_sets": 6},
                                 {"name": "Deadlift", "working_sets": 4}, {"name": "Bicep Curl", "working_sets": 6}]
