"""The cut (skill phase-cut): phase start from a level or a goal, the band
from the target rate, the weekly decisions, macros and the end date.

Worked example (diet history as test_phase_start; clock Mon 9 Nov 2026):
maintenance estimate 2536 kcal, no counted activity in the window, starting
trend weight 80.5 kg. Moderate = 750 kcal a day: start kcal 2536 - 750 =
1786 (the MFP goal, a rest day), target rate 750 x 7 / 7500 = -0.7 kg/week,
band -0.7 x (1 +- 0.4) = -0.98 to -0.42. Macros at 80.5 kg: protein 2.5 g/kg
= 201 g, fat 0.6 g/kg = 48 g, carbs (1786 - 805 - 434.7) / 4 = 137 g.
"""

import datetime

import pytest

from fa_coach import phases
from fa_coach.features import weekly_checkin
from fakes import exercise, food, reply, session, tool_call, tool_calls
from test_phase_start import CLASSES, SETUP, card, diet_history  # noqa: F401
from test_weekly_checkin import check_in, decision_requests, fill_week, verdict

DAY = datetime.timedelta(days=1)
CUT_SETUP = {k: v for k, v in SETUP.items() if k not in ("fat_g_per_kg_start", "week1_increase_kcal")}


async def collect_cut(coach, model, **cut_values) -> dict:
    """'start cut', record the setup values plus `cut_values`, then start_phase.
    Returns the start_phase tool result (the preview, or an error)."""
    model.script(reply("Let's set up the cut."))
    await coach.on_message("start cut")
    start = len(model.requests)
    calls = [("classify_exercises", {"exercises": CLASSES})]
    calls += [("record_setup_value", {"key": k, "value": v}) for k, v in {**CUT_SETUP, **cut_values}.items()]
    model.script(tool_calls(*calls), tool_call("start_phase"), reply("Preview below."))
    await coach.on_message("all as you said")
    assert not any(r.is_error for r in model.results(start))  # recording itself never fails here
    return model.results(len(model.requests) - 2)[0]


async def test_a_moderate_cut_starts_at_maintenance_minus_750_with_its_band(diet_history, model, outbox):
    result = await collect_cut(diet_history, model, cut_level="moderate")

    assert not result.is_error, result.content
    preview = result.content
    assert preview["average_daily_target_kcal"] == 1786
    assert preview["mfp_goal"] == {"kcal": 1786, "protein_g": 201, "carbs_g": 137, "fat_g": 48}
    assert preview["cut"] == {
        "level": "moderate", "deficit_kcal": 750, "source": "level", "target_rate_kg_per_week": -0.7,
        "band": {"low": -0.98, "high": -0.42}, "goal": None, "warning": None}
    text = card(outbox).text
    assert "Cut: moderate, 750 kcal a day below maintenance" in text
    assert "target rate -0.70 kg/week (band -0.98 to -0.42)" in text
    assert "glycogen" not in text.lower()

    confirm = card(outbox).buttons[0][0]
    await diet_history.on_button(confirm.action, confirm.ref_id)
    assert phases.active(diet_history)["phase_id"] == "cut"
    assert round(phases.targets(diet_history)["surplus_kcal"]) == -750
    p = phases.params(diet_history)
    assert p["weight_band_kg_per_week"] == [{"from_week": 1, "to_week": None, "low": -0.98, "high": -0.42}]
    assert (p["macros"]["protein_g_per_kg"], p["macros"]["fat_g_per_kg_start"]) == (2.5, 0.6)


async def test_cut_macros_are_protein_2_5_and_fat_at_the_floor_on_the_trend_weight(cut_phase, api, clock, model):
    """Week 2's macros use week 1's trend, 79.5 kg: protein 199 g, fat 48 g (0.6 x 79.5 = 47.7)."""
    day = phases.daily_target(cut_phase, datetime.date(2026, 11, 17))

    assert day["kcal"] == 1786
    m = day["macros"]
    assert (m["protein_g"], m["fat_g"], m["reference_weight_kg"]) == (199, 48, 79.5)
    assert (m["protein_g_per_kg"], m["fat_g_per_kg"]) == (2.5, 0.6)


async def test_aggressive_warns_that_it_is_for_experienced_dieters(diet_history, model, outbox):
    result = await collect_cut(diet_history, model, cut_level="aggressive")

    plan = result.content["cut"]
    assert (plan["deficit_kcal"], plan["target_rate_kg_per_week"], plan["band"]) == (
        1000, -0.93, {"low": -1.31, "high": -0.56})
    assert result.content["average_daily_target_kcal"] == 1536
    assert "experienced dieters" in plan["warning"]
    assert "⚠️" in card(outbox).text and "experienced dieters" in card(outbox).text


async def test_a_goal_weight_sets_the_deficit_it_needs_and_suggests_the_level(diet_history, model, outbox):
    """80.5 -> 75 kg in 6 weeks: 0.92 kg/week, 5.5 x 7500 / 42 days = 982 -> 980 kcal a day."""
    result = await collect_cut(diet_history, model, goal={"weight_kg": 75, "date": "2026-12-21"})

    assert not result.is_error, result.content
    plan = result.content["cut"]
    assert (plan["source"], plan["level"], plan["deficit_kcal"]) == ("goal", "aggressive", 980)
    assert plan["goal"]["needed_rate_kg_per_week"] == -0.92 and plan["goal"]["capped"] is False
    assert "experienced dieters" in plan["warning"]  # past moderate
    assert result.content["average_daily_target_kcal"] == 2536 - 980
    assert "Goal: 75 kg by 2026-12-21 needs -0.92 kg/week" in card(outbox).text


async def test_a_goal_needing_more_than_the_cap_is_capped_with_a_warning(diet_history, model):
    """80.5 -> 72 kg in 6 weeks needs ~1520 kcal a day: capped at 1000, which
    takes 8.5 x 7500 / 1000 = 64 days (until 12 Jan)."""
    result = await collect_cut(diet_history, model, goal={"weight_kg": 72, "date": "2026-12-21"})

    plan = result.content["cut"]
    assert (plan["deficit_kcal"], plan["goal"]["needed_deficit_kcal"], plan["goal"]["capped"]) == (1000, 1520, True)
    assert "capped at 1,000" in plan["warning"] and "2027-01-12" in plan["warning"]


async def test_a_body_fat_goal_keeps_the_lean_mass(diet_history, model):
    """20 % -> 15 % at the same lean mass: 80.5 x 0.8 / 0.85 = 75.8 kg; 4.74 kg in
    16 weeks = 0.30 kg/week, about 320 kcal a day: conservative, no warning."""
    result = await collect_cut(diet_history, model,
                               goal={"body_fat_pct": 15, "current_body_fat_pct": 20, "date": "2027-03-01"})

    plan = result.content["cut"]
    assert (plan["level"], plan["deficit_kcal"], plan["warning"]) == ("conservative", 320, None)
    assert plan["goal"]["goal_weight_kg"] == 75.8


async def test_a_level_wins_over_a_goal_which_is_shown_against_it(diet_history, model):
    result = await collect_cut(diet_history, model, cut_level="moderate", goal={"weight_kg": 75, "date": "2026-12-21"})

    plan = result.content["cut"]
    assert (plan["source"], plan["deficit_kcal"], plan["warning"]) == ("level", 750, None)
    assert plan["goal"]["needed_deficit_kcal"] == 980


async def test_a_goal_above_the_current_weight_is_refused(diet_history, model):
    result = await collect_cut(diet_history, model, goal={"weight_kg": 82, "date": "2026-12-21"})

    assert result.is_error and "isn't below" in result.content["error"]
    assert phases.pending_setup(diet_history) is None


async def test_a_cut_needs_a_level_or_a_goal_and_other_phases_refuse_cut_values(diet_history, model):
    model.script(reply("Setup."))
    await diet_history.on_message("start cut")
    setup = model.requests[-1].input["setup"]
    assert "cut_level" in setup["still_needed"] and "fat_g_per_kg_start" not in setup["still_needed"]
    model.script(tool_calls(("record_setup_value", {"key": "goal", "value": {"weight_kg": 75, "date": "2026-12-21"}})),
                 reply("ok"))
    await diet_history.on_message("75 kg by 21 Dec")
    model.script(reply("ok"))
    await diet_history.on_message("what's left?")
    assert "cut_level" not in model.requests[-1].input["setup"]["still_needed"]

    model.script(reply("Reverse setup."))
    await diet_history.on_message("start reverse")
    start = len(model.requests)
    model.script(tool_calls(("record_setup_value", {"key": "cut_level", "value": "moderate"})), reply("no"))
    await diet_history.on_message("moderate")
    assert model.results(start)[0].is_error
    assert "cut_level" not in model.requests[start - 1].input["setup"]["still_needed"]


def end_cards(outbox) -> list:
    return [m for m in outbox.sent if any(b.action == "confirm_phase_end" for row in m.buttons for b in row)]


async def test_a_mini_cut_asks_to_end_the_phase_the_day_after_its_end_date_once(diet_history, model, outbox, clock):
    quiet = {"logistics.weekly_checkin": None, "logistics.evening_reminder_time": None}
    await collect_cut(diet_history, model, cut_level="conservative", end_date="2026-11-22", **quiet)
    confirm = card(outbox).buttons[0][0]
    await diet_history.on_button(confirm.action, confirm.ref_id)
    assert phases.active(diet_history)["setup"]["end_date"] == "2026-11-22"

    for moment in ("2026-11-22T20:00", "2026-11-23T08:00"):
        clock.current = datetime.datetime.fromisoformat(moment).replace(tzinfo=clock.current.tzinfo)
        await diet_history.run_due_jobs()
        assert end_cards(outbox) == []
    clock.current = clock.current.replace(hour=10)
    await diet_history.run_due_jobs()
    await diet_history.run_due_jobs()

    cards = end_cards(outbox)
    assert len(cards) == 1
    assert "End the phase “Cut”?" in cards[0].text and "Sun 22 Nov" in cards[0].text
    await diet_history.on_button("confirm_phase_end", cards[0].buttons[0][0].ref_id)
    ended = phases.latest(diet_history)
    assert (ended["status"], ended["end_date"]) == ("ended", "2026-11-22")


async def test_the_end_date_can_move_during_the_mini_cut(diet_history, model, outbox):
    await collect_cut(diet_history, model, cut_level="moderate", end_date="2026-11-22")
    confirm = card(outbox).buttons[0][0]
    await diet_history.on_button(confirm.action, confirm.ref_id)
    start = len(model.requests)
    model.script(tool_calls(("record_setup_value", {"key": "end_date", "value": "2026-12-06"}),
                            ("record_setup_value", {"key": "cut_level", "value": "aggressive"})), reply("ok"))

    await diet_history.on_message("two more weeks, and make it aggressive")

    assert [r.is_error for r in model.results(start)] == [False, True]  # the level defines the start
    assert phases.active(diet_history)["setup"]["end_date"] == "2026-12-06"


# --- weekly decisions --------------------------------------------------------------------
# The moderate cut confirmed Mon 9 Nov, Monday 09:00 check-ins. Eating the rest-day target
# 1786 every day (Friday's wrestling target is 2386): weekly 12502 of 13102 kcal, -4.6 %,
# within the adherence tolerance. Week 1 (W46) drops 1.0 kg of water to 79.5 kg.


@pytest.fixture
async def cut_phase(coach, api, clock, model, outbox):
    day = datetime.date(2026, 10, 12)
    for week_avg in (82.0, 81.5, 81.0, 80.5):
        for _ in range(7):
            api.days[day.isoformat()] = {"food": food(2000), "weight_kg": week_avg, "steps": 9000}
            day += DAY
    api.sessions = [session("w0", "2026-10-10", exercise("Bench Press", (80, 5)),
                            exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps"))]
    await coach.sync()
    await collect_cut(coach, model, cut_level="moderate", **{"logistics.weekly_checkin": "mon 09:00"})
    confirm = card(outbox).buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)
    outbox.clear()
    fill_week(api, 1, kcal=1786, avg=79.5)
    await check_in(coach, clock, model, "2026-11-16", cut_verdict("2026-W46"))
    return coach


def cut_verdict(iso: str, *, scenario: str = "target_met", direction: str = "hold", delta: int | None = None,
                **kwargs) -> dict:
    proposal = None if delta is None else {
        "type": "calorie_change", "delta_kcal": delta, "size": "small", "reason": "the trend",
        "is_phase_first_change": False, "returning_rejected_proposal_id": None}
    return {**verdict(iso, scenario=scenario, direction=direction, proposal=proposal, rules=["WD-TABLE"], **kwargs),
            "phase_id": "cut"}


async def week2(coach, api, clock, model, avg: float, data: dict, kcal: float = 1786) -> dict:
    fill_week(api, 2, kcal=kcal, avg=avg)
    await check_in(coach, clock, model, "2026-11-23", data)
    return weekly_checkin.stored(coach, "2026-W47")


def report_input(model) -> dict:
    return [r for r in model.requests if r.task_skills == ("weekly-report",)][-1].input


async def test_week_1_is_not_judged_and_there_is_no_glycogen_window(cut_phase, model):
    facts = decision_requests(model)[-1].input
    stored = weekly_checkin.stored(cut_phase, "2026-W46")

    assert facts["week"]["in_glycogen_window"] is False
    assert (facts["weight"]["weekly_rate_kg"], facts["weight"]["vs_band"]) == (-1.0, "not_evaluated")
    assert (facts["weight"]["band"]["low"], facts["weight"]["band"]["high"]) == (-0.98, -0.42)
    assert stored["direction"] == "hold" and stored["code_adjustments"] == []


async def test_on_target_holds(cut_phase, api, clock, model):
    stored = await week2(cut_phase, api, clock, model, 78.8,
                         cut_verdict("2026-W47", direction="decrease", scenario="stalled", delta=-100))

    assert decision_requests(model)[-1].input["weight"]["vs_band"] == "in_band"
    assert (stored["verdict"]["direction"], stored["verdict"]["proposal"], stored["direction"]) == (
        "hold", None, "hold")


async def test_stalled_with_adherence_eats_less_by_the_distance_from_the_band(cut_phase, api, clock, model):
    # -0.35 kg/week: 0.07 above the band's -0.42, the small step
    slight = await week2(cut_phase, api, clock, model, 79.15,
                         cut_verdict("2026-W47", scenario="stalled", direction="decrease", delta=-200))
    assert decision_requests(model)[-1].input["weight"]["vs_band"] == "above_band"
    assert (slight["verdict"]["proposal"]["delta_kcal"], slight["direction"]) == (-100, "decrease")
    # -0.1 kg/week in week 3: 0.32 above the band, the large step; the second week down confirms it
    fill_week(api, 3, kcal=1786, avg=79.05)
    await check_in(cut_phase, clock, model, "2026-11-30",
                   cut_verdict("2026-W48", scenario="stalled", direction="decrease", delta=-100))

    result = report_input(model)["proposal_result"]
    assert (result["status"], result["delta_kcal"]) == ("open", -200), result


async def test_stalled_without_adherence_changes_nothing(cut_phase, api, clock, model):
    stored = await week2(cut_phase, api, clock, model, 79.4,
                         cut_verdict("2026-W47", scenario="stalled", direction="decrease", delta=-200), kcal=2300)

    assert (stored["skip_reason"], stored["counts_for_confirmation"]) == ("adherence_gate", False)
    assert stored["verdict"]["proposal"] is None
    assert report_input(model)["proposal_result"] is None


async def test_too_fast_eats_100_more_after_one_week(cut_phase, api, clock, model):
    # -1.3 kg/week: 0.32 below the band's -0.98, far off, but a cut's increase is always 100
    stored = await week2(cut_phase, api, clock, model, 78.2,
                         cut_verdict("2026-W47", scenario="too_fast", direction="increase", delta=200))

    assert decision_requests(model)[-1].input["weight"]["vs_band"] == "below_band"
    assert stored["code_adjustments"][0].startswith("proposal +200 -> +100 kcal")
    result = report_input(model)["proposal_result"]
    assert (result["status"], result["delta_kcal"]) == ("open", 100), result
