"""Phase review (coach-reviews ticket 03): every `reviews.phase_review_every_weeks`
(10) weeks from the phase start and whenever a phase ends, code computes the
phase's facts (weight against the band and the time goal, the strength trend,
the maintenance estimate, waist, body-fat estimates, the calibration drift)
and the phase-review skill writes the review. A drifted run discount or
wrestling kcal becomes a calibration proposal (source `phase_review`) the
user approves with a tap; after a phase end the review asks what comes next.

The reverse of test_weekly_checkin starts Mon 9 Nov 2026: phase week 10 ends
Sun 17 Jan 2027, so the first review goes out on Mon 18 Jan; week 20 ends
Sun 28 Mar. The glycogen window covers phase weeks 1-2, so weeks 3-10 are the
eight weeks the calibration check can use. The plan has wrestling on Fridays
(600 kcal a session in the setup), the setup's run discount is 0.75.

Only the phase-review job runs here (`reviewer`), so no other job uses the
scripted model replies.
"""

import copy
import datetime

from fa_coach import proposals, reviews
from fa_coach.ports import ModelError
from fa_coach.registry import default_registry
from fakes import food, reply_json, run
from test_phase_end import confirm, end_card
from test_weekly_checkin import at, phase  # noqa: F401

Date = datetime.date
DAY = datetime.timedelta(days=1)
PHASE_START = Date(2026, 11, 9)
KCAL_PER_KG = 7500


def message(text: str) -> dict:
    return {"send": True, "text": text, "buttons": [], "deferred_to_weekly": []}


def reviewer(make_coach):
    """The same database with only the phase-review job registered."""
    registry = copy.copy(default_registry())
    registry._jobs = {k: v for k, v in registry._jobs.items() if k == "phase-review"}
    return make_coach(registry=registry)


def phase_requests(model) -> list:
    return [r for r in model.requests if r.task_skills == ("phase-review",)]


def phase_reviews(coach) -> list[dict]:
    return [r for r in reviews.sent_between(coach, Date(2026, 1, 1), Date(2027, 12, 31)) if r["kind"] == "phase"]


async def run_jobs(coach, clock, when: datetime.datetime) -> None:
    clock.current = when
    await coach.run_due_jobs()


# Raw Strava kcal per phase week (one run on the Tuesday): varied, so the
# weekly energy balance shows what a run really adds.
RUN_KCAL = {1: 0, 2: 1400, 3: 2800, 4: 0, 5: 2800, 6: 1400, 7: 0, 8: 2800, 9: 1400, 10: 0}


def weeks_with_runs(api, *, true_discount: float, weeks: int = 10, intake: float = 2600) -> None:
    """Phase weeks 1..`weeks`: 2600 kcal eaten every day, a weigh-in every day,
    and a body that burns 2400 + true_discount x the run's kcal + 600 per
    Friday wrestling session (per day: / 7). Each week's weight is last week's
    plus the energy balance / 7,500 kcal per kg."""
    weight = 80.5  # the week before the start (diet history)
    for week in range(1, weeks + 1):
        burned = 2400 + (true_discount * RUN_KCAL[week] + 600) / 7
        weight += (intake - burned) * 7 / KCAL_PER_KG
        for n in range(7):
            day = PHASE_START + ((week - 1) * 7 + n) * DAY
            api.days[day.isoformat()] = {"food": food(intake), "weight_kg": round(weight, 3), "steps": 9000}
            if n == 1 and RUN_KCAL[week]:
                api.days[day.isoformat()]["exercises"] = [run(RUN_KCAL[week], 10, 60)]


# --- schedule --------------------------------------------------------------------------------


async def test_a_phase_is_reviewed_every_10_weeks_once(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await run_jobs(coach, clock, at("2027-01-17", 21))
    assert phase_requests(model) == [] and outbox.texts == []

    model.script(reply_json(message("Ten weeks in.")))
    await run_jobs(coach, clock, at("2027-01-18", 7))
    await run_jobs(coach, clock, at("2027-01-18", 8))  # once

    [request] = phase_requests(model)
    assert request.decision is True and request.tools == () and request.output_schema == "coach_message"
    assert coach.skills.errors(request.input, "phase_summary") == []
    facts = request.input
    assert (facts["reason"], facts["start_date"], facts["end_date"], facts["weeks_elapsed"]) == (
        "scheduled", "2026-11-09", "2027-01-17", 10)
    assert facts["is_first_review_of_phase"] is True and facts["ask_what_next"] is False
    assert outbox.texts == ["Ten weeks in."]
    [stored] = phase_reviews(coach)
    assert (stored["period_start"], stored["period_end"]) == ("2026-11-09", "2027-01-17")

    await run_jobs(coach, clock, at("2027-03-28", 21))
    model.script(reply_json(message("Twenty weeks in.")))
    await run_jobs(coach, clock, at("2027-03-29", 7))

    assert outbox.texts == ["Ten weeks in.", "Twenty weeks in."]
    second = phase_requests(model)[1].input
    assert (second["end_date"], second["weeks_elapsed"], second["is_first_review_of_phase"]) == (
        "2027-03-28", 20, False)


async def test_ending_a_phase_reviews_it_and_asks_what_comes_next(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await coach.on_message("/endphase", at("2026-12-07", 10))
    model.script(reply_json(message("The reverse in review. What comes next?")))
    await confirm(coach, outbox, at("2026-12-07", 11))

    [request] = phase_requests(model)
    assert "phase-reverse-bulk" in request.prefix_skills  # the ended phase's skill, though none is active
    assert coach.skills.errors(request.input, "phase_summary") == []
    facts = request.input
    assert (facts["reason"], facts["start_date"], facts["end_date"], facts["ask_what_next"]) == (
        "phase_end", "2026-11-09", "2026-12-06", True)
    assert outbox.texts[-1] == "The reverse in review. What comes next?"

    await run_jobs(coach, clock, at("2026-12-07", 12))
    await run_jobs(coach, clock, at("2026-12-08", 9))
    assert len(phase_requests(model)) == 1 and len(phase_reviews(coach)) == 1


async def test_without_a_usable_model_answer_code_sends_its_own_end_review(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await coach.on_message("/endphase", at("2026-12-07", 10))
    model.script(ModelError("down"))
    await confirm(coach, outbox, at("2026-12-07", 11))

    [stored] = phase_reviews(coach)
    assert stored["text"].startswith("Phase review: Reverse") and "What comes next" in stored["text"]
    assert outbox.texts[-1] == stored["text"]


async def crashed_end(coach, outbox, model) -> None:
    """End the phase on Mon 7 Dec 11:00 with the review crashing before it was stored."""
    await coach.on_message("/endphase", at("2026-12-07", 10))
    model.script(RuntimeError("crashed before the review was stored"))
    await confirm(coach, outbox, at("2026-12-07", 11))
    assert phase_reviews(coach) == []


async def test_the_job_catches_up_on_a_missed_end_review(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await crashed_end(coach, outbox, model)

    model.script(reply_json(message("Late, but here.")))
    await run_jobs(coach, clock, at("2026-12-08", 9))

    assert [r["text"] for r in phase_reviews(coach)] == ["Late, but here."]
    assert phase_requests(model)[-1].input["reason"] == "phase_end"


async def test_a_phase_ended_days_ago_gets_no_late_review(phase, make_coach, clock, model, outbox):
    coach = reviewer(make_coach)
    await crashed_end(coach, outbox, model)

    await run_jobs(coach, clock, at("2026-12-10", 9))

    assert phase_reviews(coach) == [] and len(phase_requests(model)) == 1


# --- calibration -----------------------------------------------------------------------------


async def test_a_drifted_run_discount_becomes_a_calibration_proposal(phase, make_coach, api, clock, model, outbox):
    weeks_with_runs(api, true_discount=0.5)
    coach = reviewer(make_coach)
    clock.current = at("2027-01-18", 6)
    await coach.sync()
    model.script(reply_json(message("Ten weeks in; runs count for less than set.")))
    await run_jobs(coach, clock, at("2027-01-18", 7))

    calibration = phase_requests(model)[0].input["calibration"]
    run_item = calibration["run_kcal_discount"]
    assert calibration["weeks_used"] == 8
    assert (run_item["current"], run_item["implied"], run_item["suggested"], run_item["drifted"]) == (
        0.75, 0.5, 0.5, True)
    wrestling = calibration["wrestling_kcal_per_session"]
    assert (wrestling["judged"], wrestling["drifted"], wrestling["proposal"]) == (False, False, None)

    [proposal] = proposals.open_proposals(coach)
    assert (proposal["type"], proposal["source"], proposal["new_values"]) == (
        "calibration_change", "phase_review", {"run_kcal_discount": 0.5})
    assert run_item["proposal"] == {"id": proposal["id"], "status": "open"}
    review, card = outbox.sent[-2:]
    assert review.text == "Ten weeks in; runs count for less than set."
    assert card.ref == f"proposal:{proposal['id']}" and card.buttons[0][0].action == "approve_proposal"

    await coach.on_button("approve_proposal", proposal["id"], at("2027-01-18", 8))
    assert proposals.get(coach, proposal["id"])["status"] == "approved"


async def test_a_run_discount_that_holds_makes_no_proposal(phase, make_coach, api, clock, model, outbox):
    weeks_with_runs(api, true_discount=0.75)
    coach = reviewer(make_coach)
    clock.current = at("2027-01-18", 6)
    await coach.sync()
    model.script(reply_json(message("Ten weeks in.")))
    await run_jobs(coach, clock, at("2027-01-18", 7))

    run_item = phase_requests(model)[0].input["calibration"]["run_kcal_discount"]
    assert (run_item["implied"], run_item["drifted"], run_item["proposal"]) == (0.75, False, None)
    assert proposals.open_proposals(coach) == []
    assert outbox.texts == ["Ten weeks in."]


async def test_too_few_usable_weeks_are_not_judged(phase, make_coach, api, clock, model, outbox):
    weeks_with_runs(api, true_discount=0.5, weeks=6)  # weeks 3-6: four usable weeks
    coach = reviewer(make_coach)
    clock.current = at("2026-12-21", 6)
    await coach.sync()
    await coach.on_message("/endphase", at("2026-12-21", 10))
    model.script(reply_json(message("Done.")))
    await confirm(coach, outbox, at("2026-12-21", 11))

    calibration = phase_requests(model)[0].input["calibration"]
    assert calibration["weeks_used"] == 4
    assert calibration["run_kcal_discount"]["judged"] is False and proposals.listing(coach) == []
