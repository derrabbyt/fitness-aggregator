"""The web page's Home read model, food part (coach-web ticket 02): kcal eaten
against the coach's daily target with kcal left, macros and fiber against
their targets, the check-in week so far, freshness, and refresh.

Uses the worked example of test_weekly_checkin: the reverse starts Mon 9 Nov
2026, Monday 09:00 check-ins, base maintenance 2536 at 9,000 average steps,
surplus -236. A 9,000-step rest day is 2300 kcal. Phase week 1 takes its
macros at the starting trend weight 80.5 kg: protein 2.0 g/kg = 161 g, fat
0.9 g/kg = 72 g, carbs (2300 - 161 x 4 - 72.45 x 9) / 4 = 251 g, fiber
0.3-0.5 g/kg = 24-40 g. Approving +100 on Mon 7 Dec (test_proposals) makes a
rest day 2400 kcal from then on.
"""

import datetime

import pytest

from fa_coach import phases, views
from fakes import exercise, food, run, session
from test_proposals import approve_tap, two_c_weeks
from test_weekly_checkin import at, phase  # noqa: F401


def home(coach, day: str | None = None) -> dict:
    data = coach.view("home", {"day": day} if day else {})
    assert views.errors(coach, "home", data) == []
    return data


async def eat(coach, api, clock, day: str, now: str, **values) -> None:
    api.days[day] = {"steps": 9000, **values}
    clock.current = at(now, 20)
    await coach.sync()


# --- Home: food -------------------------------------------------------------------------


async def test_today_shows_eaten_against_the_daily_target_and_whats_left(phase, api, clock):
    await eat(phase, api, clock, "2026-11-10", "2026-11-10",
              food=food(1980, protein_g=128, carbs_g=214, fat_g=61, fiber_g=19))

    h = home(phase)

    assert (h["date"], h["is_today"]) == ("2026-11-10", True)
    f = h["food"]
    assert f["kcal"] == {"eaten": 1980, "target": 2300, "left": 320}
    assert f["logged"] == "complete"
    assert f["macros"] == {
        "protein": {"eaten_g": 128, "target_g": 161},
        "carbs": {"eaten_g": 214, "target_g": 251},
        "fat": {"eaten_g": 61, "target_g": 72},
        "fiber": {"eaten_g": 19, "target_g": 24, "target_max_g": 40},
    }


async def test_a_day_with_nothing_logged_has_the_whole_target_left(phase, api, clock):
    await eat(phase, api, clock, "2026-11-10", "2026-11-10")

    f = home(phase)["food"]

    assert f["kcal"] == {"eaten": None, "target": 2300, "left": 2300}
    assert f["logged"] == "missing"
    assert f["macros"]["protein"] == {"eaten_g": None, "target_g": 161}


async def test_a_past_day_shows_its_values_as_they_stood_that_day(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await approve_tap(phase, outbox)  # +100 from Mon 7 Dec
    await eat(phase, api, clock, "2026-12-08", "2026-12-08", food=food(2000))

    before = home(phase, "2026-12-01")
    after = home(phase, "2026-12-08")

    assert before["is_today"] is False
    assert before["food"]["kcal"] == {"eaten": 2300, "target": 2300, "left": 0}  # fill_week ate 2300
    assert after["food"]["kcal"] == {"eaten": 2000, "target": 2400, "left": 400}


async def test_before_any_phase_food_has_no_target(coach, api, clock):
    api.days["2026-11-09"] = {"food": food(2410, protein_g=142, carbs_g=260, fat_g=78, fiber_g=24), "steps": 11230}
    await coach.sync()

    f = home(coach)["food"]

    assert f["kcal"] == {"eaten": 2410, "target": None, "left": None}
    assert f["macros"]["protein"] == {"eaten_g": 142, "target_g": None}
    assert f["macros"]["fiber"] == {"eaten_g": 24, "target_g": None, "target_max_g": None}
    assert f["build_up"] is None  # no target, so no math line


async def test_a_day_before_the_phase_started_has_no_target(phase, api, clock):
    f = home(phase, "2026-11-01")["food"]

    assert f["kcal"] == {"eaten": 2000, "target": None, "left": None}  # the diet history ate 2000
    assert f["build_up"] is None


# --- the target build-up (tickets 14, 15) ---------------------------------------------------
# Base at the 10,000-step goal is 2570 or 2571 (2536 at the 9,000 average + 34.5); a lifting
# session counts 300, planned wrestling 600, a Strava run 0.75 x its kcal. Activity is one
# number: the sessions and the step kcal (about -34.5 at the 9,000 average).


async def build_up(coach, api, clock, day: str, **values) -> dict:
    api.days[day] = {"steps": 9000, **values}
    clock.current = at(day, 20)
    await coach.sync()
    b = home(coach)["food"]["build_up"]
    assert set(b) == {"base_kcal", "activity_kcal", "surplus_kcal", "total_kcal"}
    assert b["base_kcal"] + b["activity_kcal"] + b["surplus_kcal"] == b["total_kcal"] == home(coach)["food"]["kcal"]["target"]
    assert b["base_kcal"] in (2570, 2571)
    return b


def surplus(coach, kcal: float, day: str) -> None:
    """A new targets row from `day` on with the same base and another surplus."""
    current = phases.targets(coach, datetime.date.fromisoformat(day))
    with coach.db.transaction():
        phases.set_targets(coach, phases.active(coach)["id"], {**current, "surplus_kcal": kcal},
                           valid_from=datetime.date.fromisoformat(day), source="test", now=at(day, 7))


async def test_a_rest_day_is_base_steps_and_a_deficit(phase, api, clock):
    b = await build_up(phase, api, clock, "2026-11-11")  # Wed: Legs not in Hevy

    assert (b["surplus_kcal"], b["total_kcal"]) == (-236, 2300)  # the reverse starts below maintenance
    assert b["activity_kcal"] in (-34, -35)  # only the steps: 1,000 under the goal


async def test_a_lifting_day_adds_the_workout_to_activity(phase, api, clock):
    api.sessions.append(session("s1", "2026-11-10", exercise("Bench Press", (80, 8))))

    b = await build_up(phase, api, clock, "2026-11-10")

    assert b["total_kcal"] == 2600 and b["activity_kcal"] - 300 in (-34, -35)


async def test_a_run_and_wrestling_day_adds_both_to_activity(phase, api, clock):
    # Fri: planned wrestling (600) and a 5 km Strava run of 400 kcal (300); its 6,000 steps are left out.
    b = await build_up(phase, api, clock, "2026-11-13", steps=15000, exercises=[run(400, 5, 30)])

    assert b["total_kcal"] == 3200 and b["activity_kcal"] - 900 in (-34, -35)


async def test_a_day_below_the_step_goal_takes_its_step_kcal_off_activity(phase, api, clock):
    b = await build_up(phase, api, clock, "2026-11-12", steps=7000)  # Thu, no session

    assert b["total_kcal"] == 2231  # 2300 - 0.0345 x 2,000
    assert b["activity_kcal"] in (-103, -104, -105)  # 0.0345 x -3,000 vs the goal


async def test_a_day_with_untracked_steps_counts_the_average(phase, api, clock):
    b = await build_up(phase, api, clock, "2026-11-12", steps=1800)  # under the tracking threshold

    assert b["total_kcal"] == 2300 and b["activity_kcal"] in (-34, -35)  # counted at the 9,000 average


async def test_a_surplus_is_positive(phase, api, clock):
    surplus(phase, 250, "2026-11-12")

    b = await build_up(phase, api, clock, "2026-11-12")

    assert (b["surplus_kcal"], b["total_kcal"]) == (250, 2786)  # 2300 + 486


async def test_maintenance_has_a_zero_surplus(phase, api, clock):
    surplus(phase, 0, "2026-11-12")

    b = await build_up(phase, api, clock, "2026-11-12")

    assert (b["surplus_kcal"], b["total_kcal"]) == (0, 2536)


# --- freshness ---------------------------------------------------------------------------


async def test_fresh_after_a_sync_and_stale_past_the_limit(phase, api, clock):
    clock.current = at("2026-11-10", 8)
    await phase.sync()
    assert home(phase)["freshness"] == {"last_sync_at": "2026-11-10T08:00:00+01:00", "age_hours": 0.0,
                                        "stale": False}

    clock.current = at("2026-11-11", 21)  # 37 h later; the limit is 36 h

    fresh = home(phase)["freshness"]
    assert (fresh["stale"], fresh["age_hours"]) == (True, 37.0)


async def test_never_synced_is_stale(coach):
    assert home(coach)["freshness"] == {"last_sync_at": None, "age_hours": None, "stale": True}


# --- food detail: the check-in week so far -----------------------------------------------


async def test_food_detail_shows_each_day_of_the_check_in_week_so_far(phase, api, clock):
    api.days["2026-11-09"] = {"food": food(2250), "steps": 9000}
    api.days["2026-11-10"] = {"food": food(2400), "steps": 9000}
    await eat(phase, api, clock, "2026-11-11", "2026-11-11")  # nothing logged yet

    d = phase.view("home/food", {"day": "2026-11-11"})

    assert views.errors(phase, "home/food", d) == []
    assert (d["start"], d["end"], d["date"]) == ("2026-11-09", "2026-11-15", "2026-11-11")
    assert [(x["date"], x["eaten_kcal"], x["target_kcal"], x["logged"]) for x in d["days"]] == [
        ("2026-11-09", 2250, 2300, "complete"),
        ("2026-11-10", 2400, 2300, "complete"),
        ("2026-11-11", None, 2300, "missing"),
    ]
    assert {k: v for k, v in d["so_far"].items() if k != "balance"} == {
        "days_logged": 2, "eaten_kcal": 4650, "target_kcal": 4600, "deviation_pct": 1.1}


async def test_food_detail_before_any_phase_lists_what_was_eaten(coach, api, clock):
    api.days["2026-11-09"] = {"food": food(2410)}
    await coach.sync()

    d = coach.view("home/food", {})

    assert views.errors(coach, "home/food", d) == []
    assert (d["start"], d["date"]) == ("2026-11-09", "2026-11-09")  # no check-in day: ISO week
    assert [(x["eaten_kcal"], x["target_kcal"]) for x in d["days"]] == [(2410, None)]
    assert d["so_far"] == {"days_logged": 1, "eaten_kcal": 2410, "target_kcal": None, "deviation_pct": None,
                           "balance": {"kcal": None, "days": 0, "kg": None}}
    assert d["days"][0]["balance_kcal"] is None  # no burn estimate outside a phase


async def test_food_detail_shows_each_days_surplus_or_deficit_and_the_weeks_total(phase, api, clock):
    api.days["2026-11-09"] = {"food": food(2250), "steps": 9000}
    api.days["2026-11-10"] = {"food": food(2400), "steps": 9000}
    await eat(phase, api, clock, "2026-11-11", "2026-11-11")

    d = phase.view("home/food", {"day": "2026-11-11"})

    # Balance = eaten - burned, burned = the day's target without its planned surplus.
    surplus = phases.daily_target(phase, datetime.date(2026, 11, 9))["surplus_kcal"]
    assert [x["balance_kcal"] for x in d["days"]] == [2250 - 2300 + surplus, 2400 - 2300 + surplus, None]
    total = 4650 - 4600 + 2 * surplus
    assert d["so_far"]["balance"] == {"kcal": total, "days": 2, "kg": round(total / 7500, 2)}


async def test_today_has_no_surplus_or_deficit_until_the_day_is_over(phase, api, clock):
    api.days["2026-11-09"] = {"food": food(2250), "steps": 9000}
    api.days["2026-11-10"] = {"food": food(350), "steps": 2000}  # breakfast so far
    await eat(phase, api, clock, "2026-11-10", "2026-11-10")
    clock.current = at("2026-11-10", 9)

    d = phase.view("home/food", {})

    assert [x["balance_kcal"] is None for x in d["days"]] == [False, True]
    assert d["so_far"]["balance"]["days"] == 1


# --- refresh and errors -------------------------------------------------------------------


async def test_refresh_syncs_then_returns_the_view(phase, api, clock):
    clock.current = at("2026-11-10", 12)
    api.days["2026-11-10"] = {"food": food(900), "steps": 9000}

    h = await phase.refresh("home", {})

    assert ("mfp_days" in [name for name, _ in api.calls])
    assert h["food"]["kcal"]["eaten"] == 900
    assert h["freshness"]["stale"] is False


async def test_a_future_day_or_a_bad_date_is_refused(phase, clock):
    clock.current = at("2026-11-10", 12)
    with pytest.raises(views.WebError) as future:
        phase.view("home", {"day": "2026-11-11"})
    with pytest.raises(views.WebError) as bad:
        phase.view("home", {"day": "11/10"})

    assert future.value.status == 400 and "hasn't started" in future.value.message
    assert bad.value.status == 400


async def test_an_unknown_view_is_not_found(coach):
    with pytest.raises(views.WebError) as missing:
        coach.view("nope", {})

    assert missing.value.status == 404
