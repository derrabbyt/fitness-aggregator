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

import datetime

from fa_coach import messaging, progression
from fakes import exercise, food, reply, session, tool_call
from test_web_home_training import TWO_WEEKS
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


# --- training ------------------------------------------------------------------------------
# The lifts of test_web_home_training (TWO_WEEKS, 10-18 Nov): in W47 (16-22 Nov) Bench and Row
# improved, Squat stalled (its third session without progress); PRs: Bench and Row on 16 Nov,
# Bench on 18 Nov. The seeded plan has 8 sessions a week that aren't optional (Mon Pull, Tue
# Push and a workout run, Wed Legs, Thu Upper, Fri Wrestling, Sat Legs, Sun long run).


def lifts_known(coach, clock) -> None:
    """Classified up front, so no new-exercise message asks the model."""
    for exercise_id in ("bench-press", "squat", "row"):
        progression.classify(coach, exercise_id, "counts", None, clock.current)


async def test_a_judged_weeks_training_is_lifts_progressing_stalls_prs_sessions_and_steps(phase, api, clock, model):
    lifts_known(phase, clock)
    api.sessions += TWO_WEEKS
    await three_weeks(phase, api, clock, model)

    t = week(phase, "2026-W47")["training"]

    assert t["source"] == "check_in"
    lifts = t["lifts"]
    assert (lifts["progressing"], lifts["counted"], lifts["deload_signal"]) == (2, 3, False)
    assert lifts["stalls"] == [{"exercise_id": "squat", "name": "Squat"}]
    assert [(pr["name"], pr["date"]) for pr in lifts["prs"]] == [
        ("Bench Press", "2026-11-16"), ("Row", "2026-11-16"), ("Bench Press", "2026-11-18")]
    # Done: the Hevy sessions on Mon 16 and Wed 18 and Friday's wrestling (counted as planned).
    assert t["sessions"] == {"done": 3, "planned": 8, "skipped": 0}
    s = t["steps"]
    assert (s["goal"], s["average"], s["days_at_goal"]) == (10000, 9000, 0)
    assert [d["steps"] for d in s["days"]] == [9000] * 7


async def test_the_week_in_progress_shows_training_so_far(phase, api, clock, model):
    lifts_known(phase, clock)
    api.sessions += [*TWO_WEEKS, session("s6", "2026-12-01", exercise("Bench Press", (107.5, 10)))]
    await week_4_so_far(phase, api, clock, model)

    t = week(phase, "2026-W49")["training"]

    # Squat and Row weren't trained in the last 14 days: stale, not counted.
    assert t["source"] == "so_far"
    assert (t["lifts"]["progressing"], t["lifts"]["counted"], t["lifts"]["stalls"]) == (1, 1, [])
    assert [(pr["name"], pr["date"]) for pr in t["lifts"]["prs"]] == [("Bench Press", "2026-12-01")]
    assert t["sessions"] == {"done": 1, "planned": 8, "skipped": 0}
    assert len(t["steps"]["days"]) == 3


async def test_a_week_without_lifts_has_no_lift_numbers(phase, api, clock, model):
    clock.current = at("2026-11-11")

    t = week(phase, "2026-W46")["training"]

    assert t["lifts"] is None and t["sessions"]["done"] == 0


# --- notes and flags -----------------------------------------------------------------------
# Waist every 2 weeks after the start and photos at the start and every 2 weeks: both are due
# on Mon 23 Nov, the first day after W47 (16-22 Nov).

FIBER = {"code": "fiber_off", "severity": "watch", "detail": "Fiber under target on 3 days.", "exercise_id": None}


async def notes_week(phase, api, clock, model) -> None:
    """W47 with a context note (Thu 19 Nov) and a deferred item (Wed 18 Nov), judged on 23 Nov with a flag."""
    fill_week(api, 1)
    fill_week(api, 2)
    await check_in(phase, clock, model, "2026-11-16", verdict("2026-W46", scenario="glycogen_window"))
    clock.current = at("2026-11-19", 20)
    model.script(tool_call("add_context_note", applies_from="2026-11-19", applies_to="2026-11-19",
                           tags=["sleep_poor"], suggest_unusable="no"), reply("Noted."))
    await phase.on_message("slept badly")
    messaging.defer(phase, datetime.date(2026, 11, 18), "Protein was low on Wednesday.", "evening-recap",
                    at("2026-11-18", 21))


async def test_a_judged_weeks_notes_are_its_context_notes_flags_deferred_items_and_whats_due(
        phase, api, clock, model):
    await notes_week(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-23", verdict("2026-W47", scenario="glycogen_window", flags=[FIBER]))

    n = week(phase, "2026-W47")["notes"]

    assert [(c["text"], c["applies_from"], c["applies_to"], c["tags"]) for c in n["context_notes"]] == [
        ("slept badly", "2026-11-19", "2026-11-19", ["sleep_poor"])]
    assert n["flags"] == [{"code": "fiber_off", "severity": "watch", "detail": "Fiber under target on 3 days."}]
    assert n["deferred"] == [{"date": "2026-11-18", "text": "Protein was low on Wednesday."}]
    assert n["due_next_week"] == [{"date": "2026-11-23", "kind": "waist"}, {"date": "2026-11-23", "kind": "photos"}]


async def test_a_judged_week_without_flags_has_none_and_a_week_in_progress_isnt_flagged_yet(
        phase, api, clock, model):
    await notes_week(phase, api, clock, model)

    in_progress = week(phase, "2026-W47")["notes"]
    await check_in(phase, clock, model, "2026-11-23", verdict("2026-W47", scenario="glycogen_window"))
    judged = week(phase, "2026-W47")["notes"]

    assert in_progress["flags"] is None
    assert [c["text"] for c in in_progress["context_notes"]] == ["slept badly"]
    assert in_progress["deferred"] == [{"date": "2026-11-18", "text": "Protein was low on Wednesday."}]
    assert len(in_progress["due_next_week"]) == 2
    assert judged["flags"] == []


async def test_a_week_before_any_phase_has_no_number_blocks(phase, api, clock, model):
    clock.current = at("2026-11-11")

    w = week(phase, "2026-W45")

    assert (w["weight"], w["intake"], w["training"], w["notes"]) == (None, None, None, None)
