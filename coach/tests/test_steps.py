"""Steps as live activity: each day's target moves with its steps against a
step goal; base is shown at the goal, the math stays anchored to the
measured maintenance.

Worked example (the reverse of test_weekly_checkin, confirmed Mon 9 Nov
2026): the maintenance window (12 Oct - 8 Nov) has 9,000 steps every day,
so the average day steps are 9,000. k = 0.04 x 80.5 / 70 x 0.75 = 0.0345
kcal per step (34.5 per 1,000). Base maintenance 2536 (at 9,000 steps),
surplus -236: an average-steps rest day is 2300 kcal, the MFP goal. With
the default goal of 10,000 the base at the goal is 2536 + 34.5 = 2570.5;
with a goal of 11,000 it is 2536 + 69 = 2605. A day's target = base at goal
+ 0.0345 x (day steps - goal) + sessions + surplus = 2300 + 0.0345 x (day
steps - 9,000) + sessions.
"""

import datetime
import json

from fa_coach import phases
from fa_coach.features import phase_start
from fakes import food, reply, run, tool_call, tool_calls
from test_weekly_checkin import at, phase  # noqa: F401

DAY = datetime.date


async def steps_on(coach, api, clock, days: dict[str, dict]) -> None:
    for date, values in days.items():
        api.days[date] = values
    clock.current = at("2026-11-15", 20)
    await coach.sync()


def target(coach, date: str) -> dict:
    return phases.daily_target(coach, DAY.fromisoformat(date))


async def set_step_goal(coach, model, goal: int) -> None:
    start = len(model.requests)
    model.script(tool_call("record_setup_value", key="step_goal", value=goal), reply("Done."))
    await coach.on_message(f"my step goal is {goal}")
    assert not model.results(start)[0].is_error


async def test_an_average_steps_day_is_the_current_formula(phase, api, clock):
    await steps_on(phase, api, clock, {"2026-11-10": {"steps": 9000}})

    day = target(phase, "2026-11-10")

    assert day["kcal"] == 2300  # base 2536 + surplus -236, as without steps
    assert day["kcal"] == phases.targets(phase)["mfp_goal_kcal"]
    assert day["base_at_step_goal_kcal"] in (2570, 2571)
    assert day["steps"]["kcal"] in (-34, -35)  # 1,000 below the 10,000 goal


async def test_days_above_and_below_the_goal(phase, api, clock):
    await steps_on(phase, api, clock, {"2026-11-10": {"steps": 13000}, "2026-11-11": {"steps": 7000}})

    assert target(phase, "2026-11-10")["kcal"] == 2438  # 2300 + 0.0345 x 4,000
    assert target(phase, "2026-11-11")["kcal"] == 2231  # 2300 - 0.0345 x 2,000


async def test_a_day_at_the_goal_after_the_goal_changed_in_chat(phase, api, clock, model):
    await steps_on(phase, api, clock, {"2026-11-15": {"steps": 11000}})

    await set_step_goal(phase, model, 11000)  # on Sun 15 Nov: from that day on (test_setup_history)

    assert phases.params(phase)["steps"]["step_goal"] == 11000
    day = target(phase, "2026-11-15")
    assert (day["steps"]["kcal"], day["base_at_step_goal_kcal"], day["kcal"]) == (0, 2605, 2369)
    assert phases.targets(phase)["mfp_goal_kcal"] == 2300  # the goal only moves where 0 is shown


async def test_a_day_under_the_tracking_threshold_is_not_tracked(phase, api, clock):
    await steps_on(phase, api, clock, {"2026-11-10": {"steps": 1800}})

    day = target(phase, "2026-11-10")

    assert day["steps"]["tracked"] is False and day["steps"]["steps"] is None
    assert day["kcal"] == 2300  # counted at the average: no step adjustment


async def test_run_steps_are_removed_so_the_run_counts_once(phase, api, clock):
    """Thursday: 15,000 steps with a 5 km Strava run (6,000 steps) of 400 kcal:
    9,000 day steps (no step adjustment) + the run's 400 x 0.75 = 300."""
    await steps_on(phase, api, clock, {"2026-11-12": {"steps": 15000, "exercises": [run(400, 5, 30)]}})

    day = target(phase, "2026-11-12")

    assert (day["steps"]["raw"], day["steps"]["steps"], day["steps"]["run_steps_removed"]) == (15000, 9000, 6000)
    assert day["kcal"] == 2600


async def test_a_reported_walk_with_a_distance_removes_its_steps(phase, api, clock, model):
    await steps_on(phase, api, clock, {"2026-11-11": {"steps": 14000}})
    model.script(tool_calls(("set_session_status", {"date": "2026-11-11", "status": "extra", "type": "other",
                                                    "name": "Hike", "kcal": 200, "distance_km": 2.5})),
                 reply("Noted."))
    await phase.on_message("hiked 2.5 km, about 200 kcal")

    day = target(phase, "2026-11-11")

    assert (day["steps"]["steps"], day["steps"]["run_steps_removed"]) == (11000, 3000)
    assert day["kcal"] == 2300 + 69 + 200


async def test_the_mfp_goal_is_a_normal_step_rest_day(phase, api):
    """Set on confirm: base at the average 9,000 steps + surplus, not base at
    the 10,000 goal + surplus (2334.5)."""
    assert api.goal_writes()[0]["kcal"] == 2300
    current = phases.targets(phase)
    assert round(current["avg_day_steps"]) == 9000 and round(current["step_kcal_per_step"], 4) == 0.0345


async def test_the_preview_shows_base_at_the_step_goal(phase):
    preview = json.loads(phase.db.value("SELECT preview FROM phase_setups WHERE status = 'confirmed'"))

    assert preview["steps"] == {"step_goal": 10000, "avg_day_steps": 9000, "kcal_per_1000_steps": 34.5,
                                "base_at_step_goal_kcal": preview["steps"]["base_at_step_goal_kcal"]}
    assert preview["steps"]["base_at_step_goal_kcal"] in (2570, 2571)
    assert preview["mfp_goal"]["kcal"] == 2300 and preview["daily_targets_kcal"]["rest"] == 2300
    text = phase_start.render_card(preview)
    assert "base at your step goal (10,000 steps)" in text and "34.5 kcal per 1,000 steps" in text


async def test_today_syncs_and_shows_the_live_balance(phase, api, clock, model, outbox):
    await set_step_goal(phase, model, 11000)
    api.days["2026-11-12"] = {"steps": 7000, "food": food(1500)}
    clock.current = at("2026-11-12", 15)
    outbox.clear()
    calls = len(api.calls)

    await phase.on_message("/today")

    assert "mfp_days" in [n for n, _ in api.calls[calls:]]  # synced first
    assert outbox.texts == ["\n".join([
        "Today so far:",
        "Steps: 7,000 / 11,000, 4,000 to go.",
        "Step kcal so far: -138 kcal vs the goal (34.5 kcal per 1,000 steps).",
        "Target: 2,231 kcal = base at step goal 2,605, steps -138, surplus -236.",
        "Macros: P 161 g · F 72 g · C 234 g.",
        "Eaten: 1,500 kcal. Left: 731 kcal.",
        "Provisional: the target moves with your steps until the day ends.",
    ])]


async def test_the_chat_tool_gives_a_past_day_with_its_final_steps(phase, api, clock, model):
    api.days["2026-11-10"] = {"steps": 13000, "food": food(2400)}
    clock.current = at("2026-11-12", 15)
    start = len(model.requests)
    model.script(tool_call("get_today", date="2026-11-10"), reply("Tuesday: 2,438 target."))

    await phase.on_message("how did tuesday balance out?")

    result = model.results(start)[0]
    assert not result.is_error
    v = result.content
    assert (v["provisional"], v["target_kcal"], v["eaten_kcal"], v["left_kcal"]) == (False, 2438, 2400, 38)
    assert v["steps"]["to_go"] == 0
