"""Estimated kcal for reported sessions (story 19).

The user may report a session by type and duration alone; code estimates the
kcal as MET x current 7-day trend weight (kg) x hours, with the MET from the
table in core params. When code can't (unknown activity, no trend weight),
the model may pass its own estimate, stored as `model_estimate`. A kcal
number the user gives always wins."""

import datetime

import pytest

from fa_coach.features import training_plan
from fakes import reply, tool_calls

PARAMS = {"run_kcal_discount": 0.75, "wrestling_kcal_per_session": 600, "lifting_kcal_per_session": 400}


@pytest.fixture
async def weighed(coach, api, clock):
    """Monday 9 Nov 2026, 20:00; weigh-ins over the last days average 80.0 kg."""
    for day, kg in {"2026-11-05": 79.6, "2026-11-06": 80.4, "2026-11-07": 80.2, "2026-11-08": 79.8}.items():
        api.days[day] = {"weight_kg": kg}
    clock.current = datetime.datetime(2026, 11, 9, 20, 0, tzinfo=clock.current.tzinfo)
    await coach.sync()
    return coach


async def _report(coach, model, **args):
    """One chat turn in which the model calls set_session_status once; returns
    what code sent back to the model."""
    start = len(model.requests)
    model.script(tool_calls(("set_session_status", args)), reply("Noted."))
    await coach.on_message("session report")
    [result] = model.results(start)
    return result


def counted(coach, date: str = "2026-11-09") -> list[tuple]:
    day = training_plan.counted_activity_on(coach, datetime.date.fromisoformat(date), PARAMS)
    return [(s["type"], s["source"], s["status"], s["kcal_counted"]) for s in day["sessions"]]


async def test_an_extra_session_without_kcal_is_estimated_from_met_weight_and_duration(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="other", name="Football",
                           activity="football", duration_min=90)

    assert not result.is_error
    report = result.content["reported"]
    assert report["kcal"] == 840  # football MET 7.0 x 80.0 kg x 1.5 h
    assert report["kcal_source"] == "estimated"
    assert report["kcal_counted"] == 840
    assert report["estimate"] == {"activity": "football", "met": 7.0, "trend_weight_kg": 80.0, "duration_min": 90}
    assert result.content["extras"][0]["kcal_source"] == "estimated"
    assert ("other", "manual", "done", 840) in counted(weighed)


async def test_a_kcal_the_user_gives_wins_over_the_estimate(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="other", name="Football",
                           activity="football", duration_min=90, kcal=500)

    report = result.content["reported"]
    assert (report["kcal"], report["kcal_source"]) == (500, "reported")
    assert ("other", "manual", "done", 500) in counted(weighed)


async def test_an_unknown_activity_uses_the_models_estimate_marked_as_such(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="other", name="Climbing",
                           activity="climbing", duration_min=60, kcal_estimate=450)

    report = result.content["reported"]
    assert (report["kcal"], report["kcal_source"]) == (450, "model_estimate")
    assert "climbing" in report["say"] and "your estimate" in report["say"]
    assert ("other", "manual", "done", 450) in counted(weighed)


async def test_the_code_estimate_wins_over_the_models_when_code_can_estimate(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="other", name="Football",
                           activity="football", duration_min=90, kcal_estimate=1200)

    assert (result.content["reported"]["kcal"], result.content["reported"]["kcal_source"]) == (840, "estimated")


async def test_an_unknown_activity_without_a_model_estimate_is_sent_back(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="other", name="Climbing",
                           activity="climbing", duration_min=60)

    assert result.is_error
    assert "climbing" in result.content["error"] and "kcal_estimate" in result.content["error"]
    assert training_plan.statuses(weighed, datetime.date(2026, 11, 9)) == []


async def test_a_missing_duration_makes_the_model_ask_and_stores_nothing(weighed, model):
    start = len(model.requests)
    model.script(tool_calls(("set_session_status", dict(date="2026-11-09", status="extra", type="other", name="Football",
                           activity="football"))),
                 reply("How long did you play?"))

    await weighed.on_message("played football tonight")

    [result] = model.results(start)
    assert result.is_error
    assert "duration" in result.content["error"] and "ask" in result.content["error"]
    assert weighed.outbox.texts[-1] == "How long did you play?"
    assert ("other", "manual", "done", 840) not in counted(weighed)
    assert [s for s in training_plan.statuses(weighed, datetime.date(2026, 11, 9)) if s["status"] == "extra"] == []


async def test_without_a_trend_weight_the_models_estimate_is_used(coach, model):
    refused = await _report(coach, model, date="2026-11-09", status="extra", type="other", name="Football",
                            activity="football", duration_min=90)
    result = await _report(coach, model, date="2026-11-09", status="extra", type="other", name="Football",
                           activity="football", duration_min=90, kcal_estimate=700)

    assert refused.is_error and "weight" in refused.content["error"]
    report = result.content["reported"]
    assert (report["kcal"], report["kcal_source"]) == (700, "model_estimate")
    assert "trend weight" in report["say"]
    assert [(s["kcal"], s["kcal_source"]) for s in training_plan.statuses(coach, datetime.date(2026, 11, 9))] \
        == [(700, "model_estimate")]


async def test_a_run_without_strava_is_estimated_and_discounted(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="done", session_id="mon-2", duration_min=30)

    report = result.content["reported"]
    assert (report["kcal"], report["kcal_source"]) == (320, "estimated")  # running MET 8.0 x 80 kg x 0.5 h
    assert report["estimate"]["activity"] == "running"
    assert ("run", "manual", "done", 240) in counted(weighed)  # x 0.75 run discount


async def test_wrestling_and_lifting_without_kcal_use_their_setup_values(weighed, model):
    await _report(weighed, model, date="2026-11-09", status="extra", type="wrestling", name="Open mat",
                  activity="martial_arts", duration_min=90)
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="lift", name="Gym")

    assert not result.is_error
    rows = counted(weighed)
    assert ("wrestling", "manual", "done", 600) in rows
    assert ("lift", "manual", "done", 400) in rows


async def test_an_other_session_with_neither_kcal_nor_activity_is_refused(weighed, model):
    result = await _report(weighed, model, date="2026-11-09", status="extra", type="other", name="Something")

    assert result.is_error
    assert "activity" in result.content["error"]
