"""The web page's Training tab (coach-web ticket 08): the strength trend
(`strength_trend.compute`, ticket 14, over a 28-day line here), every lift
with its status and a small chart, lifts that don't count apart, and the
recent runs and other sessions.

Strength trend worked numbers (shown day Mon 30 Nov 2026, look-back 3-30
Nov): e1RM = load x (1 + reps / 30), so at 8 reps the % is the load's.
Bench 100 (4 Nov) ... 108 (25 Nov): 108 %. Squat 100 (5 Nov), 104 (19 Nov):
104 %. Mean 106 %: (106 - 100) / 4 weeks = +1.5 % per week.
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


# --- strength trend ----------------------------------------------------------------------


async def test_the_strength_trend_is_a_four_week_line_with_its_weekly_rate(coach, api, clock):
    await synced(coach, api, clock, rising())

    trend = training(coach)["strength_trend"]

    assert (trend["start"], trend["end"], len(trend["points"])) == ("2026-11-03", "2026-11-30", 28)
    assert trend["points"][-1]["pct"] == 106.0
    assert (trend["rate_pct_per_week"], trend["direction"], trend["lifts"]) == (1.5, "rising", 2)


async def test_a_past_day_shows_the_strength_trend_as_it_stood_that_day(coach, api, clock):
    await synced(coach, api, clock, rising())

    trend = training(coach, "2026-11-18")["strength_trend"]  # look-back 22 Oct - 18 Nov

    assert trend["end"] == "2026-11-18"
    assert (trend["points"][-1]["pct"], trend["lifts"]) == (105.0, 1)  # squat has one session by then


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
