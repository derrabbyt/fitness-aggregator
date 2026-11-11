"""Home's training blocks and banner (coach-web ticket 05): the Gym block
(lifting sessions, one line each, the lift trend line and the 4-week strength
trend) and the Other activities block (runs with distance, duration and pace;
wrestling; extra sessions), and the banner (an open proposal or a coach
question waiting in Telegram; only on today).

The reverse phase starts Mon 9 Nov 2026 with the seeded plan: Tue 06:30 Push
and an evening workout run, Fri 12:00 Wrestling, optional easy runs.
"""

import datetime

from fa_coach import progression, views
from fakes import exercise, reply, run, session, tool_calls
from test_weekly_checkin import at, phase  # noqa: F401


def home(coach, day: str | None = None) -> dict:
    data = coach.view("home", {"day": day} if day else {})
    assert views.errors(coach, "home", data) == []
    return data


def line(type_: str, name: str, time: str | None = None, minutes: int | None = None, *,
         distance_km: float | None = None, pace_s_per_km: int | None = None, skipped: bool = False) -> dict:
    return {"type": type_, "name": name, "time": time, "minutes": minutes, "distance_km": distance_km,
            "pace_s_per_km": pace_s_per_km, "skipped": skipped}


async def synced(coach, api, clock, now: str, hour: int = 20) -> None:
    clock.current = at(now, hour)
    await coach.sync()


# --- the day's sessions ----------------------------------------------------------------


async def test_a_lifting_day_lists_the_hevy_session_in_the_gym_block(phase, api, clock):
    api.sessions.append(session("s1", "2026-11-10", exercise("Bench Press", (80, 8))))
    await synced(phase, api, clock, "2026-11-10")

    t = home(phase)["training"]

    assert t["gym"]["sessions"] == [line("lift", "Pull", "06:30", 60)]
    assert t["other"]["sessions"] == []


async def report(coach, model, **args) -> None:
    """The user reports a session in chat (set_session_status), as in test_counted_activity."""
    start = len(model.requests)
    model.script(tool_calls(("set_session_status", args)), reply("Noted."))
    await coach.on_message("session report")
    assert not model.results(start)[0].is_error


async def test_a_run_day_lists_the_strava_run_with_distance_duration_and_pace(phase, api, clock):
    api.days["2026-11-10"] = {"exercises": [{**run(519, 11.5, 62), "start": "2026-11-10T18:05:00+01:00"}]}
    await synced(phase, api, clock, "2026-11-10")

    t = home(phase)["training"]

    assert t["other"]["sessions"] == [line("run", "Running (jogging)", "18:05", 62, distance_km=11.5,
                                           pace_s_per_km=323)]  # 62 min / 11.5 km = 5:23 per km
    assert t["gym"]["sessions"] == []  # Push is planned but not in Hevy: not listed


async def test_planned_wrestling_is_listed_like_any_other_activity(phase, api, clock):
    await synced(phase, api, clock, "2026-11-13", hour=8)  # Fri 12:00 Wrestling, not reported

    assert home(phase)["training"]["other"]["sessions"] == [line("wrestling", "Wrestling", "12:00")]


async def test_skipped_wrestling_stays_listed_as_skipped(phase, api, clock, model):
    await synced(phase, api, clock, "2026-11-13")
    await report(phase, model, date="2026-11-13", status="skipped", session_id="fri-1")

    assert home(phase)["training"]["other"]["sessions"] == [line("wrestling", "Wrestling", "12:00", skipped=True)]


async def test_an_extra_session_is_listed_with_its_duration(phase, api, clock, model):
    api.sessions.append(session("s1", "2026-11-11", exercise("Squat", (100, 5)), hour=17))
    await synced(phase, api, clock, "2026-11-11")
    await report(phase, model, date="2026-11-11", status="extra", type="other", name="Football",
                 activity="football", duration_min=90)

    t = home(phase)["training"]

    assert t["gym"]["sessions"] == [line("lift", "Pull", "17:30", 60)]
    assert t["other"]["sessions"] == [line("other", "Football", None, 90)]


async def test_a_day_without_sessions_has_empty_blocks(phase, api, clock):
    await synced(phase, api, clock, "2026-11-11")

    rest = home(phase)["training"]  # Wed: Legs not in Hevy, the optional easy run not run
    before = home(phase, "2026-11-06")["training"]  # a Friday before the phase: planned wrestling not listed

    assert (rest["gym"]["sessions"], rest["other"]["sessions"]) == ([], [])
    assert (before["gym"]["sessions"], before["other"]["sessions"]) == ([], [])


# --- the lift trend line -----------------------------------------------------------------


def lifts(bench, squat, row) -> tuple:
    return (exercise("Bench Press", bench), exercise("Squat", squat), exercise("Row", row))


TWO_WEEKS = [  # Tue 10 Nov to Wed 18 Nov
    session("s1", "2026-11-10", *lifts((100, 8), (100, 5), (60, 10))),  # Bench back after a break: not judged
    session("s2", "2026-11-11", *lifts((100, 9), (100, 5), (60, 10))),  # Bench improved (PR), Squat, Row same
    session("s3", "2026-11-13", *lifts((100, 10), (100, 5), (60, 9))),  # Bench PR, Squat same, Row declined
    session("s4", "2026-11-16", *lifts((102.5, 10), (100, 5), (62.5, 10))),  # PRs; Squat's 3rd same: a stall
    session("s5", "2026-11-18", exercise("Bench Press", (105, 10))),  # Bench PR
]


async def test_the_trend_line_counts_lifts_progressing_stalls_and_this_weeks_prs(phase, api, clock):
    api.sessions += TWO_WEEKS
    await synced(phase, api, clock, "2026-11-19")

    trend = home(phase)["training"]["gym"]["trend"]

    # Bench and Row improved, Squat stalled; the old Pull Up is out of the recency window.
    assert trend == {"progressing": 2, "counted": 3, "stalls": 1, "prs": 3}  # Bench Mon 16 and Wed 18, Row Mon 16


async def test_the_trend_line_on_a_past_day_is_as_it_stood_that_day(phase, api, clock):
    api.sessions += TWO_WEEKS
    await synced(phase, api, clock, "2026-11-19")

    trend = home(phase, "2026-11-12")["training"]["gym"]["trend"]

    assert trend == {"progressing": 1, "counted": 3, "stalls": 0, "prs": 1}  # week of Mon 9: Bench's PR on Wed 11

    trend = home(phase, "2026-11-10")["training"]["gym"]["trend"]

    assert trend == {"progressing": 0, "counted": 0, "stalls": 0, "prs": 0}  # first sessions: nothing judged yet


# --- the strength trend ------------------------------------------------------------------
# As of Sun 29 Nov the 28-day window is Mon 2 Nov .. Sun 29 Nov: ISO weeks 45-48.
# e1RM (Epley) = load x (1 + reps/30); at 5 reps x 7/6: 100 -> 116.67, 105 -> 122.5 (+5.0 %),
# 104 -> 121.33 (+4.0 %), 95 -> 110.83 (-5.0 %), 80 -> 93.33, 84 -> 98.0 (+5.0 %).

WEEKS = ["2026-W45", "2026-W46", "2026-W47", "2026-W48"]


async def lifted(coach, api, clock, *sessions, now: str = "2026-11-29") -> dict:
    api.sessions = list(sessions)
    await synced(coach, api, clock, now)
    return home(coach)["training"]["gym"]["strength_trend"]


def weekly(trend: dict) -> list:
    return [w["change_pct"] for w in trend["weeks"]]


RISING = [
    session("r1", "2026-11-02", exercise("Bench Press", (100, 5))),
    session("r2", "2026-11-09", exercise("Squat", (100, 5)), exercise("Lateral Raise", (10, 12))),
    session("r3", "2026-11-16", exercise("Bench Press", (105, 5)), exercise("Lateral Raise", (5, 12))),
    session("r4", "2026-11-23", exercise("Squat", (104, 5))),
]


async def test_a_rising_trend_averages_each_lifts_change_and_carries_it_forward(coach, api, clock):
    counted_too = await lifted(coach, api, clock, *RISING)
    assert counted_too["lifts"] == 3  # Lateral Raise (-50 %) counts until it is excluded
    progression.classify(coach, "lateral-raise", "excluded", "slow mover", clock.now())  # never counts

    trend = home(coach)["training"]["gym"]["strength_trend"]

    assert (trend["days"], trend["start"], trend["end"]) == (28, "2026-11-02", "2026-11-29")
    assert [w["iso_week"] for w in trend["weeks"]] == WEEKS
    # W45 Bench 0; W46 Bench 0 carried, Squat 0; W47 Bench +5, Squat 0; W48 Bench +5 carried, Squat +4.
    assert weekly(trend) == [0.0, 0.0, 2.5, 4.5]
    assert (trend["change_pct"], trend["direction"], trend["lifts"]) == (4.5, "rising", 2)


async def test_within_the_one_percent_band_the_trend_is_flat(coach, api, clock):
    trend = await lifted(coach, api, clock,
                         session("f1", "2026-11-03", exercise("Bench Press", (100, 5)), exercise("Squat", (100, 5))),
                         session("f2", "2026-11-24", exercise("Bench Press", (100, 5)), exercise("Squat", (101, 5))))

    assert weekly(trend) == [0.0, 0.0, 0.0, 0.5]
    assert (trend["change_pct"], trend["direction"]) == (0.5, "flat")


async def test_a_falling_trend(coach, api, clock):
    trend = await lifted(coach, api, clock, session("d1", "2026-11-03", exercise("Bench Press", (100, 5))),
                         session("d2", "2026-11-17", exercise("Bench Press", (95, 5))))

    assert weekly(trend) == [0.0, 0.0, -5.0, -5.0]
    assert (trend["change_pct"], trend["direction"]) == (-5.0, "falling")


async def test_a_reset_lift_starts_its_window_at_the_reset(coach, api, clock):
    api.sessions = [session("x1", "2026-11-02", exercise("Bench Press", (100, 5))),
                    session("x2", "2026-11-09", exercise("Bench Press", (80, 5))),
                    session("x3", "2026-11-16", exercise("Bench Press", (84, 5)))]
    await synced(coach, api, clock, "2026-11-29")
    progression.mark_reset(coach, "bench-press", datetime.date(2026, 11, 9), clock.now(), reason="shoulder")

    trend = home(coach)["training"]["gym"]["strength_trend"]

    assert weekly(trend) == [None, 0.0, 5.0, 5.0]  # from 80 kg, not -16 % from 100 kg
    assert (trend["change_pct"], trend["direction"]) == (5.0, "rising")


async def test_a_lift_with_one_session_in_the_window_doesnt_count(coach, api, clock):
    trend = await lifted(coach, api, clock, session("o1", "2026-10-20", exercise("Row", (60, 10))),
                         session("o2", "2026-11-20", exercise("Row", (70, 10))))  # the first is before the window

    assert weekly(trend) == [None, None, None, None]
    assert (trend["change_pct"], trend["direction"], trend["lifts"]) == (None, None, 0)


async def test_the_strength_trend_on_a_past_day_ends_that_day(coach, api, clock):
    await lifted(coach, api, clock, *RISING)
    progression.classify(coach, "lateral-raise", "excluded", "slow mover", clock.now())

    trend = home(coach, "2026-11-22")["training"]["gym"]["strength_trend"]

    # 26 Oct .. 22 Nov: Squat's +4 % on 23 Nov hasn't happened, so only Bench has 2 sessions.
    assert (trend["start"], trend["end"]) == ("2026-10-26", "2026-11-22")
    assert weekly(trend) == [None, 0.0, 0.0, 5.0]
    assert (trend["change_pct"], trend["lifts"]) == (5.0, 1)


async def test_before_any_lift_there_is_no_trend(coach):
    gym = home(coach)["training"]["gym"]

    assert gym["trend"] is None
    assert (gym["strength_trend"]["change_pct"], gym["strength_trend"]["direction"]) == (None, None)
