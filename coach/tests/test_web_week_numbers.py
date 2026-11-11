"""The Week page's number blocks (coach-web ticket 07): weight, intake,
training, and notes and flags, as parts of the `week` view. A judged week
reads the numbers its check-in stored; the week in progress shows them so
far.

Worked example (test_weekly_checkin): the reverse starts Mon 9 Nov 2026,
Monday 09:00 check-ins, so W48 = 23-29 Nov, judged Mon 30 Nov. Week 3: trend
82.0 kg (81.8 the week before), +0.2 kg (band 0.1-0.3: in band), 7
weigh-ins; 2300 kcal eaten a day against 6 x 2300 + 2900 (Friday wrestling)
= 16700 (-3.6 %, within ±5 %); macro targets at 81.8 kg protein 163.6 g,
fat 73.6 g, carbs the rest (245.75 g a day, 395.75 g on Friday: 267 g on
average), fiber 25-41 g.
"""

from fakes import food
from test_web_week import week
from test_weekly_checkin import at, check_in, fill_week, phase, three_weeks, verdict  # noqa: F401


# --- weight -------------------------------------------------------------------------------


async def test_a_judged_weeks_weight_is_its_trend_rate_and_weigh_ins_against_the_band(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"))

    w = week(phase, "2026-W48")["weight"]

    assert w["source"] == "check_in"
    assert (w["trend_kg"], w["prev_trend_kg"], w["weekly_rate_kg"], w["rate_window"]) == (82.0, 81.8, 0.2, "week")
    assert (w["band"], w["vs_band"]) == ({"low": 0.1, "high": 0.3}, "in_band")
    assert (w["weigh_ins"], w["weigh_ins_needed"], w["days"]) == (7, 5, 7)
    # The chart: the day before the week (where the rate starts) to its end, the band
    # corridor rising from that day's trend by the band's low and high rate.
    first, last = w["series"][0], w["series"][-1]
    assert (len(w["series"]), first["date"], last["date"]) == (8, "2026-11-22", "2026-11-29")
    assert (first["trend_kg"], first["band_low_kg"], first["band_high_kg"]) == (81.8, 81.8, 81.8)
    assert (last["kg"], last["trend_kg"], last["band_low_kg"], last["band_high_kg"]) == (82.0, 82.0, 81.9, 82.1)


async def week_4_so_far(phase, api, clock, model, **food_days) -> None:
    """W48 judged; W49 (30 Nov - 6 Dec) in progress on Wed 2 Dec at noon, weighing 82.1."""
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"))
    for day in ("2026-11-30", "2026-12-01", "2026-12-02"):
        api.days[day] = {"weight_kg": 82.1, "steps": 9000, **food_days.get(day, {})}
    clock.current = at("2026-12-02", 12)
    await phase.sync()


async def test_the_week_in_progress_shows_its_weight_so_far_with_the_last_7_days_rate(phase, api, clock, model):
    await week_4_so_far(phase, api, clock, model)

    w = week(phase, "2026-W49")["weight"]

    assert (w["source"], w["rate_window"], w["days"], w["weigh_ins"]) == ("so_far", "last_7_days", 3, 3)
    # Trend 26 Nov - 2 Dec: (4 x 82.0 + 3 x 82.1) / 7 = 82.04; 7 days earlier 81.89.
    assert (w["trend_kg"], w["prev_trend_kg"], w["weekly_rate_kg"], w["vs_band"]) == (82.04, 82.0, 0.15, "in_band")
    assert [s["date"] for s in w["series"]] == ["2026-11-29", "2026-11-30", "2026-12-01", "2026-12-02"]
    assert (w["series"][0]["band_low_kg"], w["series"][-1]["kg"]) == (82.0, 82.1)


# --- intake --------------------------------------------------------------------------------


async def test_a_judged_weeks_intake_is_each_day_against_target_the_average_adherence_and_macros(
        phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"))

    i = week(phase, "2026-W48")["intake"]

    assert i["source"] == "check_in"
    assert [(d["date"][-2:], d["eaten_kcal"], d["target_kcal"], d["logged"]) for d in i["days"]] == [
        ("23", 2300, 2300, "complete"), ("24", 2300, 2300, "complete"), ("25", 2300, 2300, "complete"),
        ("26", 2300, 2300, "complete"), ("27", 2300, 2900, "complete"), ("28", 2300, 2300, "complete"),
        ("29", 2300, 2300, "complete")]
    assert i["average"] == {"eaten_kcal": 2300, "target_kcal": 2386, "days": 7}
    assert i["adherence"] == {"result": "pass", "deviation_pct": -3.6, "tolerance_pct": 5, "days_logged": 7,
                              "days": 7}
    assert i["macros"] == {"protein": {"eaten_g": 180, "target_g": 164}, "carbs": {"eaten_g": 250, "target_g": 267},
                           "fat": {"eaten_g": 70, "target_g": 74},
                           "fiber": {"eaten_g": 30, "target_g": 25, "target_max_g": 41}}


async def test_a_partial_day_is_marked_and_left_out_of_the_average_and_adherence(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    api.days["2026-11-25"]["food"] = food(800)  # under the partial share of the days around it
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="unusable", usable=False))

    i = week(phase, "2026-W48")["intake"]

    assert [d["logged"] for d in i["days"]] == ["complete", "complete", "partial", "complete", "complete",
                                                "complete", "complete"]
    assert i["days"][2]["eaten_kcal"] == 800
    assert i["average"] == {"eaten_kcal": 2300, "target_kcal": 2400, "days": 6}
    assert i["adherence"] == {"result": "fail", "deviation_pct": None, "tolerance_pct": 5, "days_logged": 6,
                              "days": 7}


async def test_the_week_in_progress_shows_intake_so_far_with_today_never_partial(phase, api, clock, model):
    await week_4_so_far(phase, api, clock, model, **{
        "2026-11-30": {"food": food(2300)}, "2026-12-01": {"food": food(800)}, "2026-12-02": {"food": food(600)}})

    i = week(phase, "2026-W49")["intake"]

    assert i["source"] == "so_far"
    assert [(d["eaten_kcal"], d["target_kcal"], d["logged"]) for d in i["days"]] == [
        (2300, 2300, "complete"), (800, 2300, "partial"), (600, 2300, "complete")]
    assert i["average"] == {"eaten_kcal": 1450, "target_kcal": 2300, "days": 2}
    assert i["adherence"] == {"result": "not_judged", "deviation_pct": None, "tolerance_pct": 5, "days_logged": 2,
                              "days": 3}
