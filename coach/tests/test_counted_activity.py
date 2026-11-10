"""Counted activity: what a day's sessions add to its daily target.

Runs count only when a Strava run synced (kcal x run discount) or the user
reported one; lifting counts at a fixed kcal per Hevy session; wrestling counts
as planned unless reported skipped; extras count with their reported kcal.
MFP also lists HealthKit copies of runs and HealthKit "Strength training";
those never count."""

import datetime

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from fa_coach.features import training_plan
from fakes import exercise, reply, run, session, tool_calls

PARAMS = {"run_kcal_discount": 0.75, "wrestling_kcal_per_session": 600, "lifting_kcal_per_session": 400}
START = datetime.date(2026, 11, 9)  # the phase start: planned wrestling counts from here on


def healthkit(name: str, kcal: float, *, is_run: bool) -> dict:
    return {"name": name, "source": "healthkit", "run": is_run, "kcal": kcal,
            "distance_km": 11.5 if is_run else None, "minutes": 60, "start": None}


async def _report(coach, model, **args) -> None:
    start = len(model.requests)
    model.script(tool_calls(("set_session_status", args)), reply("Noted."))
    await coach.on_message("session report")
    assert not model.results(start)[0].is_error


@pytest.fixture
async def week(coach, api, clock, model):
    """Week of Mon 9 Nov 2026 with the seeded plan, synced on Sunday evening."""
    api.days["2026-11-09"] = {"exercises": [healthkit("Strength training", 310, is_run=False)]}
    api.days["2026-11-10"] = {"exercises": [run(519, 11.5, 62), healthkit("Running", 574, is_run=True)]}
    api.days["2026-11-11"] = {"exercises": [healthkit("Running", 300, is_run=True)]}  # watch only, no Strava
    api.sessions = [session("w1", "2026-11-09", exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps"))]
    clock.current = datetime.datetime(2026, 11, 15, 20, 0, tzinfo=clock.current.tzinfo)
    await coach.sync()
    return coach


def counted(coach, date: str) -> dict:
    return training_plan.counted_activity_on(coach, datetime.date.fromisoformat(date), PARAMS, planned_from=START)


def summary(day: dict) -> list[tuple]:
    return [(s["type"], s["source"], s["status"], s["kcal_counted"]) for s in day["sessions"]]


async def test_a_hevy_session_counts_lifting_and_healthkit_strength_does_not(week):
    day = counted(week, "2026-11-09")  # Pull + Hevy session; optional easy run not run

    assert summary(day) == [("lift", "training_log", "done", 400)]
    assert day["kcal"] == 400


async def test_a_synced_strava_run_counts_discounted_once(week):
    day = counted(week, "2026-11-10")  # Push not in Hevy; Workout run from Strava and HealthKit

    assert summary(day) == [("run", "strava", "done", 389.25)]
    assert day["kcal"] == 389.25


async def test_an_unrun_optional_run_counts_nothing(week):
    day = counted(week, "2026-11-11")  # Legs not in Hevy, optional run only in HealthKit

    assert day["sessions"] == []
    assert day["kcal"] == 0


async def test_planned_wrestling_counts_without_a_report(week):
    day = counted(week, "2026-11-13")

    assert summary(day) == [("wrestling", "plan", "planned", 600)]
    assert day["kcal"] == 600


async def test_skipped_wrestling_counts_nothing(week, model):
    await _report(week, model, date="2026-11-13", status="skipped", session_id="fri-1")

    day = counted(week, "2026-11-13")

    assert summary(day) == [("wrestling", "plan", "skipped", 0)]
    assert day["kcal"] == 0


async def test_an_extra_session_counts_with_its_reported_kcal(week, model):
    await _report(week, model, date="2026-11-11", status="extra", type="other", name="Climbing", kcal=350)

    assert summary(counted(week, "2026-11-11")) == [("other", "manual", "done", 350)]


async def test_a_run_reported_done_counts_only_when_strava_has_none(week, model):
    await _report(week, model, date="2026-11-11", status="done", session_id="wed-2", kcal=300)
    await _report(week, model, date="2026-11-10", status="done", session_id="tue-2", kcal=500)

    assert summary(counted(week, "2026-11-11")) == [("run", "manual", "done", 225)]
    assert summary(counted(week, "2026-11-10")) == [("run", "strava", "done", 389.25)]  # not twice


async def test_a_day_with_everything(week, model):
    """Saturday: planned Legs logged in Hevy, a Strava run plus its HealthKit
    copy, an extra session, and a skipped optional run."""
    week.api.days["2026-11-14"] = {"exercises": [run(400, 8, 45), healthkit("Running", 450, is_run=True),
                                                 healthkit("Strength training", 280, is_run=False)]}
    week.api.sessions.append(session("w2", "2026-11-14", exercise("Hacksquat", (120, 8)), hour=11))
    await week.sync()
    await _report(week, model, date="2026-11-14", status="skipped", session_id="sat-2")
    await _report(week, model, date="2026-11-14", status="extra", type="wrestling", name="Open mat", kcal=500)

    day = counted(week, "2026-11-14")

    assert sorted(summary(day)) == sorted([
        ("run", "strava", "done", 300),
        ("lift", "training_log", "done", 400),
        ("run", "plan", "skipped", 0),
        ("wrestling", "manual", "done", 500),
    ])
    assert day["kcal"] == 1200


async def test_counted_sessions_fit_the_weekly_facts_schema(week, model):
    await _report(week, model, date="2026-11-14", status="skipped", session_id="sat-2")
    await _report(week, model, date="2026-11-11", status="extra", type="run", name="Treadmill", kcal=200)
    days = [counted(week, f"2026-11-{d:02d}") for d in range(9, 16)]
    validator = Draft202012Validator(week.skills.schema("weekly_facts")["$defs"]["session"],
                                     format_checker=FormatChecker())
    statuses = {s["status"] for day in days for s in day["sessions"]}
    assert statuses == {"done", "planned", "skipped"}
    for day in days:
        for s in day["sessions"]:
            assert list(validator.iter_errors(s)) == []
    assert days[2]["sessions"] == [{"date": "2026-11-11", "type": "run", "source": "manual", "status": "done",
                                    "kcal_counted": 150, "note": "Treadmill"}]  # extra runs are discounted too


async def test_a_missing_setup_value_is_an_error_not_a_guess(week):
    with pytest.raises(ValueError, match="wrestling_kcal_per_session"):
        training_plan.counted_activity_on(
            week, datetime.date(2026, 11, 13), {**PARAMS, "wrestling_kcal_per_session": None}, planned_from=START
        )


def counted_before_start(coach, date: str) -> dict:
    """As if the phase started after `date` (the preview and maintenance windows)."""
    return training_plan.counted_activity_on(coach, datetime.date.fromisoformat(date), PARAMS,
                                             planned_from=datetime.date(2026, 11, 16))


async def test_before_the_phase_start_planned_wrestling_counts_only_when_reported(week, model):
    assert counted_before_start(week, "2026-11-13")["sessions"] == []  # planned, not reported

    await _report(week, model, date="2026-11-13", status="done", session_id="fri-1")

    assert summary(counted_before_start(week, "2026-11-13")) == [("wrestling", "plan", "done", 600)]


async def test_before_the_phase_start_synced_sessions_still_count(week):
    assert summary(counted_before_start(week, "2026-11-09")) == [("lift", "training_log", "done", 400)]
    assert summary(counted_before_start(week, "2026-11-10")) == [("run", "strava", "done", 389.25)]


async def test_without_an_active_phase_no_planned_wrestling_counts(week):
    day = training_plan.counted_activity_on(week, datetime.date(2026, 11, 13), PARAMS)

    assert day["kcal"] == 0
