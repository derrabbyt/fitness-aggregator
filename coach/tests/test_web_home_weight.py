"""The web page's Home weight block and its detail (coach-web ticket 03).

Uses the worked example of test_weekly_checkin: the reverse starts Mon 9 Nov
2026 (diet history before it: weekly weigh-ins 82.0, 81.5, 81.0, 80.5 from
12 Oct), Monday 09:00 check-ins, weekly averages 81.5, 81.8, 82.0 in phase
weeks 1-3, band 0.1-0.3 kg a week in weeks 1-6 (upper limit 0.5), glycogen
window weeks 1-2. On Sun 29 Nov (week 3) the 7-day trend is 82.0, a week
earlier 81.8: +0.2 kg a week, in the band.
"""

import pytest

from fa_coach import views
from test_weekly_checkin import at, fill_week, phase  # noqa: F401


def weight(coach, day: str | None = None) -> dict:
    data = coach.view("home", {"day": day} if day else {})
    assert views.errors(coach, "home", data) == []
    return data["weight"]


async def weeks(coach, api, clock, *numbers: int, now: str = "2026-11-29", **kw) -> None:
    for n in numbers:
        fill_week(api, n, **kw)
    clock.current = at(now, 20)
    await coach.sync()


# --- Home: weight -----------------------------------------------------------------------


async def test_the_days_weigh_in_with_the_weekly_rate_in_the_band(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)

    w = weight(phase)

    assert w["weigh_in"] == {"date": "2026-11-29", "kg": 82.0, "outlier": False}
    assert (w["weekly_rate_kg"], w["vs_band"]) == (0.2, "in_band")


async def test_the_rate_under_the_band(phase, api, clock):
    await weeks(phase, api, clock, 1, 2)
    await weeks(phase, api, clock, 3, avg=81.8)

    w = weight(phase)

    assert (w["weekly_rate_kg"], w["vs_band"]) == (0.0, "below_band")


async def test_the_rate_over_the_band_and_over_the_limit(phase, api, clock):
    await weeks(phase, api, clock, 1, 2)
    await weeks(phase, api, clock, 3, avg=82.2)
    assert (weight(phase)["weekly_rate_kg"], weight(phase)["vs_band"]) == (0.4, "above_band")

    await weeks(phase, api, clock, 3, avg=82.4)
    assert (weight(phase)["weekly_rate_kg"], weight(phase)["vs_band"]) == (0.6, "above_limit")


async def test_a_day_without_a_weigh_in_shows_the_last_one(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3, weigh_ins=5)  # Mon-Fri

    w = weight(phase, "2026-11-29")

    assert w["weigh_in"] == {"date": "2026-11-27", "kg": 82.0, "outlier": False}
    assert (w["weekly_rate_kg"], w["vs_band"]) == (0.2, "in_band")


async def test_the_glycogen_window_isnt_judged(phase, api, clock):
    await weeks(phase, api, clock, 1, now="2026-11-15")

    w = weight(phase)

    assert (w["weekly_rate_kg"], w["vs_band"]) == (1.0, "not_evaluated")  # 80.5 -> 81.5 in week 1


async def test_a_14_day_line_of_the_trend_ending_the_day(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)

    series = weight(phase)["series"]

    assert len(series) == 14
    assert series[0] == {"date": "2026-11-16", "trend_kg": 81.54}  # 6 x 81.5 and 81.8
    assert series[6] == {"date": "2026-11-22", "trend_kg": 81.8}
    assert series[-1] == {"date": "2026-11-29", "trend_kg": 82.0}


async def test_a_past_day_shows_its_weight_as_it_stood_that_day(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)
    await weeks(phase, api, clock, 4, avg=83.0, now="2026-12-06")

    w = weight(phase, "2026-11-29")

    assert w["weigh_in"] == {"date": "2026-11-29", "kg": 82.0, "outlier": False}
    assert (w["weekly_rate_kg"], w["vs_band"]) == (0.2, "in_band")
    assert w["series"][-1] == {"date": "2026-11-29", "trend_kg": 82.0}


async def test_before_any_phase_the_rate_isnt_judged(coach, api, clock):
    for n in range(14):
        api.days[f"2026-10-{27 + n}" if n < 5 else f"2026-11-{n - 4:02d}"] = {"weight_kg": 80.0 if n < 7 else 80.5}
    await coach.sync()

    w = weight(coach, "2026-11-09")

    assert w["weigh_in"] == {"date": "2026-11-09", "kg": 80.5, "outlier": False}
    assert (w["weekly_rate_kg"], w["vs_band"]) == (0.5, None)


async def test_an_outlier_weigh_in_is_marked_and_left_out_of_the_trend(phase, api, clock):
    fill_week(api, 1)
    fill_week(api, 2)
    fill_week(api, 3)
    api.days["2026-11-29"]["weight_kg"] = 92.0  # a typo
    clock.current = at("2026-11-29", 20)
    await phase.sync()

    w = weight(phase)

    assert w["weigh_in"] == {"date": "2026-11-29", "kg": 92.0, "outlier": True}
    assert (w["weekly_rate_kg"], w["series"][-1]["trend_kg"]) == (0.2, 82.0)


# --- the weight detail --------------------------------------------------------------------


def detail(coach, day: str | None = None, **query) -> dict:
    data = coach.view("home/weight", {**({"day": day} if day else {}), **query})
    assert views.errors(coach, "home/weight", data) == []
    return data


async def test_the_detail_charts_4_weeks_of_weigh_ins_and_trend_with_the_band(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)

    d = detail(phase)

    assert (d["date"], d["weeks"]) == ("2026-11-29", 4)
    assert (d["trend_kg"], d["weekly_rate_kg"], d["vs_band"]) == (82.0, 0.2, "in_band")
    assert d["band"] == {"low": 0.1, "high": 0.3, "lower_limit": None, "upper_limit": 0.5}
    s = d["series"]
    assert (len(s), s[0]["date"], s[-1]["date"]) == (28, "2026-11-02", "2026-11-29")
    assert s[0] == {"date": "2026-11-02", "kg": 80.5, "outlier": False, "trend_kg": 80.93,  # 6 x 81.0, 80.5
                    "band_low_kg": None, "band_high_kg": None}
    # The band runs from the trend on the first judged day (23 Nov, after the
    # glycogen window: 6 x 81.8 and 82.0 = 81.83) at 0.1-0.3 kg a week.
    assert s[21]["date"] == "2026-11-23"
    assert (s[20]["band_low_kg"], s[21]["band_low_kg"], s[21]["band_high_kg"]) == (None, 81.83, 81.83)
    assert (s[-1]["band_low_kg"], s[-1]["band_high_kg"]) == (81.92, 82.09)


async def test_the_detail_shows_12_weeks_on_request(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)

    s = detail(phase, weeks="12")["series"]

    assert (len(s), s[0]["date"]) == (84, "2026-09-07")
    assert s[0]["kg"] is None and s[0]["trend_kg"] is None  # before the synced history


@pytest.mark.parametrize("range_,days", [("1", 7), ("2", 14), ("26", 182)])
async def test_the_detail_takes_the_ranges_of_its_dropdown(phase, api, clock, range_, days):
    await weeks(phase, api, clock, 1, 2, 3)

    d = detail(phase, weeks=range_)

    assert (d["weeks"], len(d["series"]), d["series"][-1]["date"]) == (int(range_), days, "2026-11-29")


async def test_all_time_starts_at_the_first_weigh_in(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)

    d = detail(phase, weeks="all")

    first = min(w["date"] for w in d["recent"])
    assert (d["weeks"], d["series"][0]["date"], d["series"][-1]["date"]) == ("all", first, "2026-11-29")


async def test_an_unknown_range_is_refused(phase):
    with pytest.raises(views.WebError):
        phase.view("home/weight", {"weeks": "5"})


async def test_recent_weigh_ins_newest_first_with_outliers_marked(phase, api, clock):
    fill_week(api, 1)
    fill_week(api, 2)
    fill_week(api, 3, weigh_ins=6)  # none on Sun 29 Nov
    api.days["2026-11-27"]["weight_kg"] = 92.0  # a typo
    clock.current = at("2026-11-29", 20)
    await phase.sync()

    recent = detail(phase)["recent"]

    assert len(recent) > 14 and recent[-1]["date"] < "2026-11-09"  # all of them, the diet history too
    assert [r["date"] for r in recent] == sorted((r["date"] for r in recent), reverse=True)
    assert recent[:3] == [{"date": "2026-11-28", "kg": 82.0, "outlier": False},
                          {"date": "2026-11-27", "kg": 92.0, "outlier": True},
                          {"date": "2026-11-26", "kg": 82.0, "outlier": False}]


async def test_waist_values_up_to_the_day_newest_first_with_the_phase_start(phase, api, clock):
    await phase.on_message("waist 84", at("2026-11-23", 6, 30))
    await phase.on_message("waist 84.8", at("2026-12-07", 6, 30))
    await weeks(phase, api, clock, 1, 2, 3)

    assert detail(phase)["waist"] == [{"date": "2026-11-23", "cm": 84.0},
                                      {"date": "2026-11-09", "cm": 84.5}]  # the phase setup's start value


async def test_no_waist_values_before_any_phase(coach):
    assert detail(coach)["waist"] == []


async def test_this_weeks_predicted_against_actual_weight(phase, api, clock):
    await weeks(phase, api, clock, 1, 2, 3)

    # The check-in week 23-29 Nov: last week's trend 81.8 plus the planned
    # surplus, -236 x 7 / 7500 = 81.58; the trend on Sunday is 82.0.
    assert detail(phase)["prediction"] == {"start": "2026-11-23", "end": "2026-11-29", "predicted_kg": 81.58,
                                           "actual_kg": 82.0, "difference_kg": 0.42, "complete": True}
    # Mid-week: the trend so far (4 x 81.8, 3 x 82.0 = 81.89), not final yet.
    mid = detail(phase, "2026-11-25")["prediction"]
    assert (mid["predicted_kg"], mid["actual_kg"], mid["difference_kg"], mid["complete"]) == (81.58, 81.89, 0.31,
                                                                                              False)


async def test_no_prediction_before_any_phase(coach, api):
    api.days["2026-11-09"] = {"weight_kg": 80.0}
    await coach.sync()

    assert detail(coach)["prediction"] is None


async def test_the_detail_refuses_other_ranges(phase):
    with pytest.raises(views.WebError) as e:
        phase.view("home/weight", {"weeks": "5"})
    assert e.value.status == 400

