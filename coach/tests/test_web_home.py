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

import pytest

from fa_coach import views
from fakes import food
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


async def test_a_day_before_the_phase_started_has_no_target(phase, api, clock):
    f = home(phase, "2026-11-01")["food"]

    assert f["kcal"] == {"eaten": 2000, "target": None, "left": None}  # the diet history ate 2000


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
    assert d["so_far"] == {"days_logged": 2, "eaten_kcal": 4650, "target_kcal": 4600, "deviation_pct": 1.1}


async def test_food_detail_before_any_phase_lists_what_was_eaten(coach, api, clock):
    api.days["2026-11-09"] = {"food": food(2410)}
    await coach.sync()

    d = coach.view("home/food", {})

    assert views.errors(coach, "home/food", d) == []
    assert (d["start"], d["date"]) == ("2026-11-09", "2026-11-09")  # no check-in day: ISO week
    assert [(x["eaten_kcal"], x["target_kcal"]) for x in d["days"]] == [(2410, None)]
    assert d["so_far"] == {"days_logged": 1, "eaten_kcal": 2410, "target_kcal": None, "deviation_pct": None}


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
