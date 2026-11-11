"""The web page's Training tab (coach-web ticket 08): every lift with its
status and a small chart, lifts that don't count apart, the 4-week strength
trend, and the recent runs and other sessions.

Strength trend worked numbers (shown day Mon 30 Nov 2026, 28-day window
3-30 Nov, ISO weeks 45-49): e1RM = load x (1 + reps / 30), so at 8 reps the
% change is the load's. Bench 100 (4 Nov), 102 (11 Nov), 105 (18 Nov),
108 (25 Nov): +0, +2, +5, +8 %. Squat 100 (5 Nov), 104 (19 Nov): +0, +4 %.
Mean per week, each lift carrying its last value: 0, 1, 4.5, 6, 6.
"""

import datetime

from fa_coach import progression, views
from fakes import TZ, exercise, reply, run, session, tool_calls
from test_weekly_checkin import at, phase  # noqa: F401

D = datetime.date


def training(coach, day: str | None = None) -> dict:
    data = coach.view("training", {"day": day} if day else {})
    assert views.errors(coach, "training", data) == []
    return data


async def synced(coach, api, clock, sessions, *, weigh_ins: dict[str, float] | None = None,
                 now: str = "2026-11-30") -> None:
    api.sessions = list(sessions)
    for day, kg in (weigh_ins or {}).items():
        api.days.setdefault(day, {})["weight_kg"] = kg
    clock.current = datetime.datetime.combine(D.fromisoformat(now), datetime.time(9), tzinfo=TZ)
    await coach.sync()


def lift(title: str, kg: float | None, reps: int = 8, **kw) -> dict:
    return exercise(title, (kg, reps), **kw)


def rising() -> list[dict]:
    return [
        session("a", "2026-11-04", lift("Bench Press", 100)),
        session("b", "2026-11-05", lift("Squat", 100)),
        session("c", "2026-11-11", lift("Bench Press", 102)),
        session("d", "2026-11-18", lift("Bench Press", 105)),
        session("e", "2026-11-19", lift("Squat", 104)),
        session("f", "2026-11-25", lift("Bench Press", 108)),
    ]


async def classify(coach, exercise_id: str, classification: str) -> None:
    progression.classify(coach, exercise_id, classification, None, coach.clock.now())


def points(trend: dict) -> list:
    return [p["change_pct"] for p in trend["points"]]


# --- strength trend ----------------------------------------------------------------------


async def test_strength_trend_rises_with_the_mean_change_of_the_counting_lifts(coach, api, clock):
    await synced(coach, api, clock, rising())

    trend = training(coach)["strength_trend"]

    assert [p["week"] for p in trend["points"]] == ["2026-W45", "2026-W46", "2026-W47", "2026-W48", "2026-W49"]
    assert points(trend) == [0.0, 1.0, 4.5, 6.0, 6.0]
    assert (trend["change_pct"], trend["direction"], trend["lifts"], trend["days"]) == (6.0, "rising", 2, 28)


async def test_strength_trend_within_one_percent_is_flat_and_below_it_falling(coach, api, clock):
    # bench 100 -> 100.6 (+0.6 %), row 100 -> 95 (-5 %): mean -2.2 -> falling; bench alone: flat
    await synced(coach, api, clock, [
        session("a", "2026-11-16", lift("Bench Press", 100), lift("Row", 100)),
        session("b", "2026-11-23", lift("Bench Press", 100.6), lift("Row", 95)),
    ])
    trend = training(coach)["strength_trend"]
    assert (trend["change_pct"], trend["direction"]) == (-2.2, "falling")
    assert points(trend) == [None, None, 0.0, -2.2, -2.2]  # nothing trained in weeks 45 and 46

    await classify(coach, "row", "excluded")
    trend = training(coach)["strength_trend"]
    assert (trend["change_pct"], trend["direction"], trend["lifts"]) == (0.6, "flat", 1)


async def test_a_lift_with_one_session_in_the_window_and_a_paused_lift_are_left_out(coach, api, clock):
    await synced(coach, api, clock, [
        session("a", "2026-10-20", lift("Squat", 100)),  # before the window
        session("b", "2026-11-16", lift("Bench Press", 100), lift("Row", 100)),
        session("c", "2026-11-23", lift("Bench Press", 105), lift("Squat", 120), lift("Row", 110)),
    ])
    progression.set_paused(coach, "row", True, "elbow", clock.now())

    trend = training(coach)["strength_trend"]

    assert (trend["change_pct"], trend["lifts"]) == (5.0, 1)


async def test_a_baseline_reset_restarts_the_lifts_change(coach, api, clock):
    await synced(coach, api, clock, [
        session("a", "2026-11-04", lift("Bench Press", 100)),
        session("b", "2026-11-11", lift("Bench Press", 110)),
        session("c", "2026-11-18", lift("Bench Press", 90)),
        session("d", "2026-11-25", lift("Bench Press", 99)),
    ])
    progression.mark_reset(coach, "bench-press", D(2026, 11, 18), clock.now(), session_id="c", reason="ROM")

    trend = training(coach)["strength_trend"]

    assert points(trend) == [None, None, 0.0, 10.0, 10.0]  # 90 -> 99, from the reset on
    assert trend["direction"] == "rising"


async def test_without_a_qualifying_lift_there_is_no_trend(coach, api, clock):
    await synced(coach, api, clock, [session("a", "2026-11-23", lift("Bench Press", 100))])

    trend = training(coach)["strength_trend"]

    assert (trend["change_pct"], trend["direction"], trend["lifts"]) == (None, None, 0)
    assert set(points(trend)) == {None}


async def test_a_past_day_shows_the_trend_as_it_stood_that_day(coach, api, clock):
    await synced(coach, api, clock, rising())

    trend = training(coach, "2026-11-18")["strength_trend"]  # window 22 Oct - 18 Nov

    assert [p["week"] for p in trend["points"]][-1] == "2026-W47"
    assert (trend["change_pct"], trend["lifts"]) == (5.0, 1)  # squat has one session by then


async def test_bodyweight_lifts_use_the_effective_load(coach, api, clock):
    # pull-ups at 80 kg bodyweight, then +4 kg added: 80 -> 84 = +5 %
    await synced(coach, api, clock, [
        session("a", "2026-11-16", lift("Pull Up", None, exercise_type="bodyweight_reps")),
        session("b", "2026-11-23", lift("Pull Up", 4, exercise_type="bodyweight_weighted")),
    ], weigh_ins={(D(2026, 11, 10) + k * datetime.timedelta(days=1)).isoformat(): 80.0 for k in range(20)})

    assert training(coach)["strength_trend"]["change_pct"] == 5.0


# --- the lift list -----------------------------------------------------------------------


def weigh_ins_80() -> dict[str, float]:
    return {(D(2026, 11, 10) + k * datetime.timedelta(days=1)).isoformat(): 80.0 for k in range(20)}


def lift_week() -> list[dict]:
    """As of Mon 30 Nov (lifts count when trained since 17 Nov): bench improves, row stays the same,
    squat declines, deadlift has 3 sessions without progress, overhead press is paused, lat pulldown
    is new, curl was last trained 5 Nov, lateral raise doesn't count, pull-ups on bodyweight."""
    dl = lambda: lift("Deadlift", 140, 5)  # noqa: E731
    pull = lambda: lift("Pull Up", None, exercise_type="bodyweight_reps")  # noqa: E731
    return [
        session("s0", "2026-11-05", lift("Curl", 20, 10)),
        session("s1", "2026-11-12", dl()),
        session("s2", "2026-11-16", dl()),
        session("s3", "2026-11-19", lift("Bench Press", 100), lift("Row", 80, 10), lift("Squat", 120, 6), dl(),
                lift("Overhead Press", 60), lift("Lateral Raise", 10, 12), pull()),
        session("s4", "2026-11-26", lift("Bench Press", 100, 9), lift("Row", 80, 10), lift("Squat", 115, 6), dl(),
                lift("Overhead Press", 62), lift("Lateral Raise", 10, 14), pull(), lift("Lat Pulldown", 70, 10)),
    ]


async def lift_list(coach, api, clock) -> dict:
    await synced(coach, api, clock, lift_week(), weigh_ins=weigh_ins_80())
    await classify(coach, "lateral-raise", "excluded")
    progression.set_paused(coach, "overhead-press", True, "shoulder", clock.now())
    return training(coach)


async def test_every_counting_lift_is_listed_alphabetically_with_its_status(coach, api, clock):
    t = await lift_list(coach, api, clock)

    assert [(x["name"], x["status"]) for x in t["lifts"]] == [
        ("Bench Press", "progressing"),
        ("Curl", "not_recent"),
        ("Deadlift", "stall"),
        ("Lat Pulldown", "new_baseline"),
        ("Overhead Press", "paused"),
        ("Pull Up", "same"),
        ("Row", "same"),
        ("Squat", "declining"),
    ]


async def test_lifts_that_dont_count_sit_apart(coach, api, clock):
    t = await lift_list(coach, api, clock)

    assert [(x["name"], x["status"]) for x in t["not_counted"]] == [("Lateral Raise", "progressing")]
    assert "Lateral Raise" not in [x["name"] for x in t["lifts"]]


async def test_each_lift_has_its_latest_heaviest_set_and_a_series_for_its_chart(coach, api, clock):
    lifts = {x["name"]: x for x in (await lift_list(coach, api, clock))["lifts"]}

    bench = lifts["Bench Press"]
    assert bench["last_session_date"] == "2026-11-26"
    assert bench["latest"] == {"load_kg": 100, "reps": 9, "effective_load_kg": 100, "e1rm_kg": 130.0}
    assert bench["series"] == [{"date": "2026-11-19", "e1rm_kg": 126.67}, {"date": "2026-11-26", "e1rm_kg": 130.0}]
    assert bench["bodyweight_exercise"] is False
    assert [p["e1rm_kg"] for p in lifts["Deadlift"]["series"]] == [163.33] * 4


async def test_a_bodyweight_lift_shows_its_effective_load(coach, api, clock):
    pull = {x["name"]: x for x in (await lift_list(coach, api, clock))["lifts"]}["Pull Up"]

    assert pull["bodyweight_exercise"] is True
    assert pull["latest"] == {"load_kg": 0.0, "reps": 8, "effective_load_kg": 80.0, "e1rm_kg": 101.33}


# --- runs and other sessions ---------------------------------------------------------------
# The reverse starts Mon 9 Nov (test_weekly_checkin's `phase`): run discount 0.75, wrestling
# 600 kcal, lifting 300 kcal per session. The seeded plan has wrestling on Fridays.


async def report(coach, model, **args) -> None:
    start = len(model.requests)
    model.script(tool_calls(("set_session_status", args)), reply("Noted."))
    await coach.on_message("session report")
    assert not model.results(start)[0].is_error


async def test_runs_and_other_sessions_are_listed_newest_first_with_the_kcal_they_count(phase, api, clock, model):
    api.days["2026-11-10"] = {"exercises": [run(519, 11.5, 62)]}
    api.sessions = [session("w1", "2026-11-09", lift("Bench Press", 100))]
    clock.current = at("2026-11-15", 20)
    await phase.sync()
    await report(phase, model, date="2026-11-11", status="extra", type="other", name="Climbing", kcal=350,
                 duration_min=90)
    clock.current = at("2026-11-22", 20)
    await report(phase, model, date="2026-11-20", status="skipped", session_id="fri-1")

    t = training(phase)

    assert t["activities"] == [
        {"date": "2026-11-20", "type": "wrestling", "name": "Wrestling", "status": "skipped",
         "distance_km": None, "minutes": None, "kcal_counted": 0},
        {"date": "2026-11-13", "type": "wrestling", "name": "Wrestling", "status": "planned",
         "distance_km": None, "minutes": None, "kcal_counted": 600},
        {"date": "2026-11-11", "type": "other", "name": "Climbing", "status": "done",
         "distance_km": None, "minutes": 90, "kcal_counted": 350},
        {"date": "2026-11-10", "type": "run", "name": "Running (jogging)", "status": "done",
         "distance_km": 11.5, "minutes": 62, "kcal_counted": 389},
    ]  # the Hevy session on 9 Nov is a lift, and planned wrestling before the phase start doesn't count


async def test_before_any_phase_sessions_are_listed_without_kcal(coach, api, clock):
    api.days["2026-11-10"] = {"exercises": [run(519, 11.5, 62)]}
    clock.current = at("2026-11-12", 20)
    await coach.sync()

    assert training(coach)["activities"] == [
        {"date": "2026-11-10", "type": "run", "name": "Running (jogging)", "status": "done",
         "distance_km": 11.5, "minutes": 62, "kcal_counted": None}]
