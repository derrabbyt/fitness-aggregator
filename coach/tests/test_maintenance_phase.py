"""Maintenance (phase-maintenance): phase start at the maintenance estimate,
a flat band of ±0.1 kg/week, and a drift beyond ±0.2 kg/week for 2 counted
weeks proposes `small_step_kcal` (100) toward flat.

Worked example (as test_phase_start's diet history): maintenance 2536 kcal,
no counted activity in the window, so base 2536 and surplus 0: the average
daily target and the rest day are 2536, the wrestling Friday 3136. The phase
starts Mon 9 Nov 2026 with Monday 09:00 check-ins; the week before averages
80.5 kg. Eating 2536 a day is 17752 of 18352 kcal a week (-3.3 %, adherent).
Week averages 80.55 (+0.05, flat), 80.65 (+0.15, small drift), 80.75 and
81.0 (+0.25 each, drifting up).
"""

import datetime

import pytest

from fa_coach import phases
from fa_coach.features import weekly_checkin
from fakes import exercise, food, reply, session, tool_call, tool_calls
from test_phase_start import CLASSES, SETUP, card, recorded_ok
from test_weekly_checkin import check_in, decision_requests, fill_week, verdict

DAY = datetime.timedelta(days=1)
MAINTENANCE_SETUP = {k: v for k, v in SETUP.items() if k != "week1_increase_kcal"} | {
    "logistics.weekly_checkin": "mon 09:00"}


@pytest.fixture
async def maintenance(coach, api, model, outbox):
    day = datetime.date(2026, 10, 12)
    for week_avg in (82.0, 81.5, 81.0, 80.5):
        for _ in range(7):
            api.days[day.isoformat()] = {"food": food(2000), "weight_kg": week_avg, "steps": 9000}
            day += DAY
    api.sessions = [session("w0", "2026-10-10", exercise("Bench Press", (80, 5)),
                            exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps"))]
    await coach.sync()
    model.script(reply("Here is what I read from your history. Confirm?"))
    await coach.on_message("start maintenance")
    start = len(model.requests)
    calls = [("classify_exercises", {"exercises": CLASSES})]
    calls += [("record_setup_value", {"key": k, "value": v}) for k, v in MAINTENANCE_SETUP.items()]
    model.script(tool_calls(*calls), tool_call("start_phase"), reply("Preview below."))
    await coach.on_message("yes, all as you said")
    recorded_ok(model, start)
    confirm = card(outbox).buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)
    outbox.clear()
    return coach


def mverdict(iso_week: str, **kwargs) -> dict:
    return verdict(iso_week, **kwargs) | {"phase_id": "maintenance", "rules_applied": ["WD-TABLE", "MAINT-FLAT"]}


def change(delta: int, size: str = "small") -> dict:
    return {"type": "calorie_change", "delta_kcal": delta, "size": size, "reason": "the drift",
            "is_phase_first_change": False, "returning_rejected_proposal_id": None}


async def test_maintenance_starts_at_the_maintenance_estimate(maintenance, outbox):
    phase = phases.active(maintenance)
    assert phase["phase_id"] == "maintenance"
    targets = phases.targets(maintenance, datetime.date(2026, 11, 9))
    assert (round(targets["avg_daily_target_kcal"]), round(targets["surplus_kcal"])) == (2536, 0)
    assert targets["mfp_goal"]["kcal"] == 2536


async def test_flat_and_small_drift_hold(maintenance, api, clock, model):
    fill_week(api, 1, kcal=2536, avg=80.55)
    await check_in(maintenance, clock, model, "2026-11-16",
                   mverdict("2026-W46", scenario="drift_up", direction="decrease", proposal=change(-100)))
    fill_week(api, 2, kcal=2536, avg=80.7)
    await check_in(maintenance, clock, model, "2026-11-23",
                   mverdict("2026-W47", scenario="drift_up", direction="decrease", proposal=change(-100)))

    w1, w2 = weekly_checkin.stored(maintenance, "2026-W46"), weekly_checkin.stored(maintenance, "2026-W47")
    assert (w1["facts"]["weight"]["vs_band"], w2["facts"]["weight"]["vs_band"]) == ("in_band", "above_band")
    for stored in (w1, w2):
        assert stored["counts_for_confirmation"] is True
        assert (stored["verdict"]["direction"], stored["verdict"]["proposal"], stored["direction"]) == (
            "hold", None, "hold")
    assert w2["code_adjustments"][0] == ("direction decrease -> hold (the trend +0.15 kg/week is within the "
                                         "drift limits -0.2 to 0.2)")


async def test_drift_beyond_the_limit_for_two_weeks_proposes_the_small_step(maintenance, api, clock, model):
    fill_week(api, 1, kcal=2536, avg=80.75)
    await check_in(maintenance, clock, model, "2026-11-16",
                   mverdict("2026-W46", scenario="drift_up", direction="decrease"))
    fill_week(api, 2, kcal=2536, avg=81.0)
    await check_in(maintenance, clock, model, "2026-11-23",
                   mverdict("2026-W47", scenario="drift_up", direction="decrease", proposal=change(-200, "large")))

    assert decision_requests(model)[-1].input["weight"]["vs_band"] == "above_limit"
    stored = weekly_checkin.stored(maintenance, "2026-W47")
    p = stored["verdict"]["proposal"]
    assert (p["delta_kcal"], p["size"]) == (-100, "small")
    result = model.requests[-1].input["proposal_result"]
    assert (result["status"], result["delta_kcal"]) == ("open", -100)


async def test_one_drifting_week_is_not_enough(maintenance, api, clock, model):
    fill_week(api, 1, kcal=2536, avg=80.25)  # -0.25: drifting down
    await check_in(maintenance, clock, model, "2026-11-16",
                   mverdict("2026-W46", scenario="drift_down", direction="increase", proposal=change(100)))

    assert weekly_checkin.stored(maintenance, "2026-W46")["direction"] == "increase"
    result = model.requests[-1].input["proposal_result"]
    assert result["status"] != "open"
