"""The web page's Home steps block (coach-web ticket 04): day steps against
the step goal with the steps to go and the step kcal so far, a not-tracked
state under `steps.not_tracked_below`, and the detail `home/steps` (14 days
against the goal).

Uses the worked example of test_steps: k = 0.0345 kcal per step (34.5 per
1,000), the default step goal 10,000, average day steps 9,000 in the
maintenance window. A day's step kcal = k x (day steps - goal).
"""

from fa_coach import views
from fakes import run
from test_weekly_checkin import at, phase  # noqa: F401


def steps(coach, day: str | None = None) -> dict:
    data = coach.view("home", {"day": day} if day else {})
    assert views.errors(coach, "home", data) == []
    return data["steps"]


async def on(coach, api, clock, now: str, days: dict[str, dict]) -> None:
    for date, values in days.items():
        api.days[date] = values
    clock.current = at(now, 15)
    await coach.sync()


async def test_below_the_goal_shows_the_steps_to_go_and_the_kcal_so_far(phase, api, clock):
    await on(phase, api, clock, "2026-11-12", {"2026-11-12": {"steps": 6000}})

    s = steps(phase)

    assert s == {"tracked": True, "steps": 6000, "goal": 10000, "to_go": 4000, "kcal": -138,
                 "run_steps_removed": 0, "provisional": True}


async def test_above_the_goal_has_nothing_to_go_and_adds_kcal(phase, api, clock):
    await on(phase, api, clock, "2026-11-12", {"2026-11-12": {"steps": 14000}})

    s = steps(phase)

    assert (s["steps"], s["to_go"], s["kcal"]) == (14000, 0, 138)


async def test_a_day_under_the_tracking_threshold_is_not_tracked(phase, api, clock):
    await on(phase, api, clock, "2026-11-12", {"2026-11-12": {"steps": 1800}})

    s = steps(phase)

    assert s == {"tracked": False, "steps": None, "goal": 10000, "to_go": None, "kcal": None,
                 "run_steps_removed": 0, "provisional": True}


async def test_a_run_day_leaves_the_run_steps_out(phase, api, clock):
    """15,000 steps with a 5 km Strava run (6,000 steps): 9,000 day steps."""
    await on(phase, api, clock, "2026-11-12", {"2026-11-12": {"steps": 15000, "exercises": [run(400, 5, 30)]}})

    s = steps(phase)

    assert (s["steps"], s["run_steps_removed"], s["to_go"]) == (9000, 6000, 1000)
    assert s["kcal"] in (-34, -35)  # 1,000 below the goal at 34.5 per 1,000


async def test_a_past_day_shows_its_final_steps(phase, api, clock):
    await on(phase, api, clock, "2026-11-12", {"2026-11-10": {"steps": 14000}, "2026-11-12": {"steps": 2500}})

    s = steps(phase, "2026-11-10")

    assert (s["steps"], s["to_go"], s["kcal"], s["provisional"]) == (14000, 0, 138, False)


async def test_before_any_phase_steps_have_no_kcal(coach, api, clock):
    await on(coach, api, clock, "2026-11-09", {"2026-11-09": {"steps": 11230}})

    s = steps(coach)

    assert (s["tracked"], s["steps"], s["goal"], s["to_go"], s["kcal"]) == (True, 11230, 10000, 0, None)


# --- steps detail: 14 days against the goal ------------------------------------------------


async def test_the_detail_shows_the_14_days_ending_on_the_day(phase, api, clock):
    """The maintenance window before the phase has 9,000 steps a day (no step
    kcal before the start, 9 Nov); then 14,000, not tracked, and 6,000."""
    await on(phase, api, clock, "2026-11-12", {
        "2026-11-09": {"steps": 9000}, "2026-11-10": {"steps": 14000}, "2026-11-11": {"steps": 1800},
        "2026-11-12": {"steps": 6000}})

    d = phase.view("home/steps", {"day": "2026-11-12"})

    assert views.errors(phase, "home/steps", d) == []
    assert (d["date"], d["goal"], len(d["days"])) == ("2026-11-12", 10000, 14)
    assert d["days"][0] == {"date": "2026-10-30", "tracked": True, "steps": 9000, "kcal": None, "run_steps_removed": 0}
    assert [(x["date"], x["steps"], x["kcal"]) for x in d["days"][-3:]] == [
        ("2026-11-10", 14000, 138), ("2026-11-11", None, None), ("2026-11-12", 6000, -138)]
    assert (d["days_tracked"], d["days_at_goal"]) == (13, 1)
    assert d["average_steps"] == 9154  # (11 x 9,000 + 14,000 + 6,000) / 13


async def test_the_detail_of_a_past_day_ends_on_that_day(phase, api, clock):
    await on(phase, api, clock, "2026-11-12", {"2026-11-10": {"steps": 14000}})

    d = phase.view("home/steps", {"day": "2026-11-10"})

    assert (d["days"][0]["date"], d["days"][-1]["date"], d["days"][-1]["steps"]) == ("2026-10-28", "2026-11-10", 14000)
