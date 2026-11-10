"""Partial days and confirming a day (ticket 20), driven through the Coach seam.

History as test_evening: four diet weeks 12 Oct - 8 Nov 2026 at 2000 kcal a day
(weekly weights 82.0, 81.5, 81.0, 80.5), so the maintenance estimate over those
four weeks is 2000 + 1.5 kg x 7500 / 21 days = 2536. With
`data.partial_day_share` 0.5, a day below half the median of its logged
neighbours (3 days either side) is a suspected partial day: 158 kcal among
2000s is one, 1200 is not.
"""

import datetime

import pytest

from fa_coach import messaging, phases, weekly_facts
from fakes import TZ, food, reply, reply_json, tool_call
from test_evening import EVENING, at, log, message, recap_facts, reverse  # noqa: F401 (fixture)

Date = datetime.date
DAY = datetime.timedelta(days=1)
HISTORY_END = Date(2026, 11, 8)


def diet_history(api, **days: float) -> None:
    day = Date(2026, 10, 12)
    for week_avg in (82.0, 81.5, 81.0, 80.5):
        for _ in range(7):
            api.days[day.isoformat()] = {"food": food(days.get(day.isoformat(), 2000)), "weight_kg": week_avg,
                                         "steps": 9000}
            day += DAY


def estimate(coach):
    return phases.maintenance_estimate(coach, HISTORY_END, phases.params(coach))


def questions(outbox):
    return [m for m in outbox.sent if m.buttons and (m.ref or "").startswith("day-question:")]


def labels(card) -> list[str]:
    return [b.label for row in card.buttons for b in row]


async def tap(coach, card, label: str, now=None) -> None:
    button = next(b for row in card.buttons for b in row if b.label == label)
    await coach.on_button(button.action, button.ref_id, now)


# --- maintenance estimate ---------------------------------------------------------------


async def test_a_partial_day_makes_its_week_unusable_for_the_maintenance_estimate(coach, api):
    diet_history(api, **{"2026-10-20": 158})  # week 2 of 4: the run of usable weeks is 2
    await coach.sync()

    assert estimate(coach)["value"] is None


async def test_a_low_but_plausible_day_still_counts(coach, api):
    diet_history(api, **{"2026-10-20": 1200})
    await coach.sync()

    assert estimate(coach)["weeks"] == 4


# --- weekly intake and adherence -------------------------------------------------------


def phase_week_1(api, **days: float) -> None:
    """Week 1 of the reverse (9-15 Nov), eaten to target: 2300, Monday's Hevy session
    2600, Friday wrestling 2900."""
    targets = {"2026-11-09": 2600, "2026-11-13": 2900}
    for n in range(7):
        day = (Date(2026, 11, 9) + n * DAY).isoformat()
        log(api, day, days.get(day, targets.get(day, 2300)))


async def week_1_facts(coach, clock, sync: bool = True):
    if sync:
        clock.current = at("2026-11-15", datetime.time(23))
        await coach.sync()
    return weekly_facts.compute(coach, Date(2026, 11, 15), at("2026-11-16", datetime.time(9)))


async def test_a_partial_day_is_left_out_of_completeness_and_adherence(reverse, api, clock, outbox):
    phase_week_1(api, **{"2026-11-11": 158})

    facts = await week_1_facts(reverse, clock)

    assert reverse.skills.errors(facts, "weekly_facts") == []
    wednesday = next(d for d in facts["intake"]["daily"] if d["date"] == "2026-11-11")
    assert wednesday["logged"] == "partial" and wednesday["actual_kcal"] == 158
    assert wednesday["partial_suspected"] is True and wednesday["confirmed"] is False
    assert facts["data_quality"]["food_days_logged"] == 6, facts["intake"]["daily"]
    assert facts["data_quality"]["food_log_complete"] is False
    assert "incomplete_food_log" in facts["data_quality"]["code_unusable_reasons"]
    assert facts["intake"]["weekly_actual_kcal"] == 2600 + 2900 + 4 * 2300
    assert facts["intake"]["deviation_pct"] is None and facts["intake"]["adherence_ok"] is False


# --- the evening question ---------------------------------------------------------------


async def test_a_partial_evening_asks_instead_of_the_recap(reverse, api, model, outbox):
    log(api, "2026-11-10", 158)  # Tue: only 2 logged neighbours (7, 8 Nov), so vs the 2300 target

    await reverse.run_due_jobs(at("2026-11-10"))

    [card] = questions(outbox)
    assert outbox.sent == [card]
    assert "158" in card.text
    assert labels(card) == ["That's all I ate", "I'll log the rest"]
    assert model.requests == []  # no recap on a day in question
    assert messaging.sent_today(reverse, at("2026-11-10")) == 1  # counts toward the limit

    await reverse.run_due_jobs(at("2026-11-10", datetime.time(22)))
    assert len(questions(outbox)) == 1  # once


async def test_thats_all_i_ate_confirms_the_day_and_it_counts(reverse, api, clock, model, outbox):
    phase_week_1(api, **{"2026-11-11": 158})
    await reverse.run_due_jobs(at("2026-11-11"))
    [card] = questions(outbox)

    await tap(reverse, card, "That's all I ate", at("2026-11-11", datetime.time(20, 40)))

    edit = outbox.items[-1]
    assert edit.ref == card.ref and edit.buttons == () and "158" in edit.text
    facts = await week_1_facts(reverse, clock)
    wednesday = next(d for d in facts["intake"]["daily"] if d["date"] == "2026-11-11")
    assert wednesday["logged"] == "complete" and wednesday["confirmed"] is True
    assert wednesday["partial_suspected"] is True
    assert facts["data_quality"]["food_log_complete"] is True
    assert facts["intake"]["weekly_actual_kcal"] == 2600 + 2900 + 4 * 2300 + 158


async def test_ill_log_the_rest_confirms_nothing(reverse, api, clock, model, outbox):
    phase_week_1(api, **{"2026-11-11": 158})
    await reverse.run_due_jobs(at("2026-11-11"))
    [card] = questions(outbox)

    await tap(reverse, card, "I'll log the rest", at("2026-11-11", datetime.time(20, 40)))

    assert outbox.items[-1].ref == card.ref and outbox.items[-1].buttons == ()
    facts = await week_1_facts(reverse, clock)
    assert facts["data_quality"]["food_log_complete"] is False


async def test_a_high_day_asks_real_or_typo_and_real_confirms_it(reverse, api, clock, model, outbox):
    phase_week_1(api, **{"2026-11-10": 12000})

    await reverse.run_due_jobs(at("2026-11-10"))

    [card] = questions(outbox)
    assert "12,000" in card.text
    assert labels(card) == ["Real", "Typo, I'll fix it in MFP"]
    assert model.requests == []

    await tap(reverse, card, "Real", at("2026-11-10", datetime.time(21)))

    assert "12,000" in outbox.items[-1].text and outbox.items[-1].buttons == ()
    facts = await week_1_facts(reverse, clock)
    tuesday = next(d for d in facts["intake"]["daily"] if d["date"] == "2026-11-10")
    assert tuesday["confirmed"] is True and tuesday["logged"] == "complete"


async def test_after_real_the_recap_counts_the_confirmed_day(reverse, api, model, outbox):
    log(api, "2026-11-10", 12000)
    await reverse.run_due_jobs(at("2026-11-10"))
    await tap(reverse, questions(outbox)[0], "Real", at("2026-11-10", datetime.time(20, 35)))
    log(api, "2026-11-11", 2300)
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-11"))

    week = recap_facts(reverse, model)["day"]["week_to_date"]
    assert week["actual_kcal_so_far"] == 12000 + 2300


# --- found later: asked with the next message -------------------------------------------


async def test_a_day_found_at_a_later_sync_is_asked_once_after_the_next_message(reverse, api, clock, outbox):
    coach = reverse
    phase_week_1(api)
    api.days["2026-11-11"]["food"] = food(158)  # Wednesday: no evening question (say the job was down)
    clock.current = at("2026-11-12", datetime.time(8))
    await coach.sync()
    assert outbox.items == []  # a sync alone sends nothing

    assert messaging.send(coach, "Morning note.", at("2026-11-12", datetime.time(9)), kind="test")

    [card] = questions(outbox)
    assert outbox.texts == ["Morning note.", card.text]
    assert card.text.startswith("Yesterday: 158 kcal")
    assert messaging.sent_today(coach, at("2026-11-12")) == 2  # the question counts

    await coach.sync()
    messaging.send(coach, "Next day.", at("2026-11-13", datetime.time(9)), kind="test")
    assert len(questions(outbox)) == 1  # asked once


async def test_a_question_past_the_daily_limit_waits_for_the_next_message(reverse, api, clock, outbox):
    coach = reverse
    phase_week_1(api, **{"2026-11-11": 158})
    clock.current = at("2026-11-12", datetime.time(8))
    await coach.sync()
    messaging.send(coach, "one", at("2026-11-12", datetime.time(8)), kind="test")  # the question goes after it
    outbox.clear()
    log(api, "2026-11-10", 300)  # Tuesday edited down later: another partial day
    await coach.sync()

    messaging.send(coach, "too many", at("2026-11-12", datetime.time(10)), kind="test")
    assert outbox.items == []  # the limit (2) is reached: neither goes

    messaging.send(coach, "next day", at("2026-11-13", datetime.time(9)), kind="test")
    [card] = questions(outbox)
    assert "300 kcal" in card.text


# --- chat ---------------------------------------------------------------------------------


async def test_the_user_confirms_a_day_in_chat_and_the_week_counts(reverse, api, clock, model, outbox):
    phase_week_1(api, **{"2026-11-11": 158})
    assert (await week_1_facts(reverse, clock))["data_quality"]["food_log_complete"] is False
    model.script(tool_call("confirm_day", date="2026-11-11", kind="complete"),
                 reply("Noted: Wednesday counts as complete at 158 kcal."))

    await reverse.on_message("Wednesday was complete, I really only ate 158", at("2026-11-16", datetime.time(8)))

    [result] = model.results(0)
    assert not result.is_error and result.content["kcal"] == 158
    facts = await week_1_facts(reverse, clock, sync=False)
    assert facts["data_quality"]["food_log_complete"] is True
    assert facts["intake"]["adherence_ok"] is False  # 158 kcal is far below the week's target


async def test_a_day_without_food_logged_cant_be_confirmed(reverse, api, model):
    model.script(tool_call("confirm_day", date="2026-11-11", kind="complete"), reply("Nothing is logged."))

    await reverse.on_message("Wednesday was complete", at("2026-11-12", datetime.time(8)))

    assert model.results(0)[0].is_error


async def test_a_confirmed_week_is_usable_again_for_the_maintenance_estimate(coach, api, model):
    diet_history(api, **{"2026-10-20": 158})
    await coach.sync()
    assert estimate(coach)["value"] is None
    model.script(tool_call("confirm_day", date="2026-10-20", kind="complete"), reply("Noted."))

    await coach.on_message("20 Oct was complete, I was sick")

    assert estimate(coach)["weeks"] == 4


async def test_a_confirmation_lapses_when_the_day_changes_in_mfp(reverse, api, clock, outbox):
    coach = reverse
    phase_week_1(api, **{"2026-11-11": 158})
    await coach.run_due_jobs(at("2026-11-11"))
    await tap(coach, questions(outbox)[0], "That's all I ate", at("2026-11-11", datetime.time(20, 40)))
    assert (await week_1_facts(coach, clock))["data_quality"]["food_log_complete"] is True

    log(api, "2026-11-11", 400)  # Wednesday edited later, still low
    facts = await week_1_facts(coach, clock)

    wednesday = next(d for d in facts["intake"]["daily"] if d["date"] == "2026-11-11")
    assert wednesday["confirmed"] is False and wednesday["logged"] == "partial"
    assert facts["data_quality"]["food_log_complete"] is False
    messaging.send(coach, "Next message.", at("2026-11-16", datetime.time(8)), kind="test")
    card = questions(outbox)[-1]
    assert len(questions(outbox)) == 2 and "400 kcal" in card.text  # checked again
