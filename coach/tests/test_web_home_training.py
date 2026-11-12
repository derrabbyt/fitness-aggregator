"""Home's training blocks and banner (coach-web tickets 05 and 14): the
Workouts card (lifting sessions, one line each with their PRs, the 14-day
strength trend and its rate, the 14-day lift summary) and the Other
activities block (runs with distance, duration and pace;
wrestling; extra sessions), and the banner (an open proposal or a coach
question waiting in Telegram; only on today).

The reverse phase starts Mon 9 Nov 2026 with the seeded plan: Tue 06:30 Push
and an evening workout run, Fri 12:00 Wrestling, optional easy runs.
"""

import datetime
from unittest.mock import ANY

from fa_coach import progression, views
from fakes import exercise, reply, run, session, tool_calls
from test_weekly_checkin import at, phase  # noqa: F401


def home(coach, day: str | None = None) -> dict:
    data = coach.view("home", {"day": day} if day else {})
    assert views.errors(coach, "home", data) == []
    return data


def line(type_: str, name: str, time: str | None = None, minutes: int | None = None, *,
         distance_km: float | None = None, pace_s_per_km: int | None = None,
         prs: int | None = 0, kcal: int | None = None) -> dict:
    """A session line with the kcal it adds to the target; lifts also carry their PR count (null
    when reported without Hevy)."""
    out = {"type": type_, "name": name, "time": time, "minutes": minutes, "distance_km": distance_km,
           "pace_s_per_km": pace_s_per_km, "kcal_counted": kcal}
    return {**out, "prs": prs} if type_ == "lift" else out


async def synced(coach, api, clock, now: str, hour: int = 20) -> None:
    clock.current = at(now, hour)
    await coach.sync()


# --- the day's sessions ----------------------------------------------------------------


async def test_a_lifting_day_lists_the_hevy_session_in_the_workouts_card(phase, api, clock):
    api.sessions.append(session("s1", "2026-11-10", exercise("Bench Press", (80, 8))))
    await synced(phase, api, clock, "2026-11-10")

    t = home(phase)["training"]

    assert t["workouts"]["sessions"] == [line("lift", "Pull", "06:30", 60, kcal=300)]
    assert t["other_activities"]["sessions"] == []


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

    assert t["other_activities"]["sessions"] == [line("run", "Running (jogging)", "18:05", 62, distance_km=11.5,
                                           pace_s_per_km=323, kcal=389)]  # 62 min / 11.5 km = 5:23 per km
    assert t["workouts"]["sessions"] == []  # Push is planned but not in Hevy: not listed


async def test_planned_wrestling_is_listed_like_any_other_activity(phase, api, clock):
    await synced(phase, api, clock, "2026-11-13", hour=8)  # Fri 12:00 Wrestling, not reported

    assert home(phase)["training"]["other_activities"]["sessions"] == [line("wrestling", "Wrestling", "12:00", kcal=600)]


async def test_a_skipped_session_is_not_listed(phase, api, clock, model):
    await synced(phase, api, clock, "2026-11-13")
    await report(phase, model, date="2026-11-13", status="skipped", session_id="fri-1")

    assert home(phase)["training"]["other_activities"]["sessions"] == []  # it did not happen


async def test_an_extra_session_is_listed_with_its_duration(phase, api, clock, model):
    api.sessions.append(session("s1", "2026-11-11", exercise("Squat", (100, 5)), hour=17))
    await synced(phase, api, clock, "2026-11-11")
    await report(phase, model, date="2026-11-11", status="extra", type="other", name="Football",
                 activity="football", duration_min=90)

    t = home(phase)["training"]

    assert t["workouts"]["sessions"] == [line("lift", "Pull", "17:30", 60, kcal=300)]
    assert t["other_activities"]["sessions"] == [line("other", "Football", None, 90, kcal=ANY)]


async def test_only_runs_get_a_pace(phase, api, clock, model):
    await synced(phase, api, clock, "2026-11-11")
    await report(phase, model, date="2026-11-11", status="extra", type="other", name="Hike", activity="hiking",
                 duration_min=150, distance_km=9.4)

    assert home(phase)["training"]["other_activities"]["sessions"] == [line("other", "Hike", None, 150, distance_km=9.4, kcal=ANY)]


async def test_a_day_without_a_workout_has_no_session_lines(phase, api, clock):
    await synced(phase, api, clock, "2026-11-11")

    rest = home(phase)["training"]  # Wed: Legs not in Hevy, the optional easy run not run
    before = home(phase, "2026-11-06")["training"]  # a Friday before the phase: planned wrestling not listed

    assert (rest["workouts"]["sessions"], rest["other_activities"]["sessions"]) == ([], [])
    assert (before["workouts"]["sessions"], before["other_activities"]["sessions"]) == ([], [])


# --- kcal per session (ticket 15): what each adds to the day's target ------------------------
# A lifting session counts 300, planned wrestling 600, a run 0.75 x its kcal.


async def test_each_line_carries_the_kcal_it_adds_and_they_sum_to_the_activity(phase, api, clock, model):
    # Fri: a Hevy session, planned wrestling, a 400 kcal Strava run and an extra with its kcal.
    api.sessions.append(session("s1", "2026-11-13", exercise("Squat", (100, 5)), hour=7))
    api.days["2026-11-13"] = {"steps": 15000, "exercises": [{**run(400, 5, 30), "start": "2026-11-13T18:00:00+01:00"}]}
    await synced(phase, api, clock, "2026-11-13")
    await report(phase, model, date="2026-11-13", status="extra", type="other", name="Climbing", kcal=350)

    data = home(phase)
    t = data["training"]

    assert [s["kcal_counted"] for s in t["workouts"]["sessions"]] == [300]
    assert [(s["name"], s["kcal_counted"]) for s in t["other_activities"]["sessions"]] == [
        ("Wrestling", 600), ("Running (jogging)", 300), ("Climbing", 350)]
    b = data["food"]["build_up"]
    assert b["activity_kcal"] - 1550 in (-34, -35)  # the sessions plus the step kcal (1,000 under the goal)


async def test_a_run_reported_done_counts_its_kcal_discounted(phase, api, clock, model):
    await synced(phase, api, clock, "2026-11-10")  # Tue: the evening run, not in Strava
    await report(phase, model, date="2026-11-10", status="done", session_id="tue-2", kcal=500)
    done = home(phase)["training"]["other_activities"]["sessions"]

    assert [(s["type"], s["kcal_counted"]) for s in done] == [("run", 375)]  # reported kcal, discounted


async def test_before_a_phase_no_line_adds_kcal(phase, api, clock):
    await synced(phase, api, clock, "2026-11-11")  # the fixture's Hevy session on Sat 10 Oct, before the phase

    assert [s["kcal_counted"] for s in home(phase, "2026-10-10")["training"]["workouts"]["sessions"]] == [None]


# --- the summary line and PRs per session --------------------------------------------------


def lifts(bench, squat, row) -> tuple:
    return (exercise("Bench Press", bench), exercise("Squat", squat), exercise("Row", row))


TWO_WEEKS = [  # Tue 10 Nov to Wed 18 Nov
    session("s1", "2026-11-10", *lifts((100, 8), (100, 5), (60, 10))),  # Bench back after a break: not judged
    session("s2", "2026-11-11", *lifts((100, 9), (100, 5), (60, 10))),  # Bench improved (PR), Squat, Row same
    session("s3", "2026-11-13", *lifts((100, 10), (100, 5), (60, 9))),  # Bench PR, Squat same, Row declined
    session("s4", "2026-11-16", *lifts((102.5, 10), (100, 5), (62.5, 10))),  # PRs; Squat's 3rd same: a stall
    session("s5", "2026-11-18", exercise("Bench Press", (105, 10))),  # Bench PR
]


async def test_the_summary_covers_the_last_14_days(phase, api, clock):
    api.sessions += TWO_WEEKS
    await synced(phase, api, clock, "2026-11-19")

    summary = home(phase)["training"]["workouts"]["summary"]

    # 6..19 Nov: Bench and Row improved, Squat stalled; the old Pull Up is out of the window.
    # PRs: Bench on 11, 13, 16 and 18 Nov, Row on 16 Nov.
    assert summary == {"progressing": 2, "counted": 3, "stalls": 1, "prs": 5}


async def test_the_summary_on_a_past_day_is_as_it_stood_that_day(phase, api, clock):
    api.sessions += TWO_WEEKS
    await synced(phase, api, clock, "2026-11-19")

    assert home(phase, "2026-11-12")["training"]["workouts"]["summary"] == {
        "progressing": 1, "counted": 3, "stalls": 0, "prs": 1}  # Bench's PR on Wed 11
    assert home(phase, "2026-11-10")["training"]["workouts"]["summary"] == {
        "progressing": 0, "counted": 0, "stalls": 0, "prs": 0}  # first sessions: nothing judged yet


async def test_each_session_line_counts_its_prs(phase, api, clock, model):
    api.sessions += TWO_WEEKS
    await synced(phase, api, clock, "2026-11-19")

    assert home(phase, "2026-11-16")["training"]["workouts"]["sessions"] == [
        line("lift", "Pull", "06:30", 60, prs=2, kcal=300)]  # Bench and Row
    assert home(phase, "2026-11-10")["training"]["workouts"]["sessions"] == [line("lift", "Pull", "06:30", 60, kcal=300)]


# --- the strength trend ------------------------------------------------------------------
# Each day looks back 28 days. e1RM (Epley) = load x (1 + reps/30); at 5 reps x 7/6, so
# 105 kg is 105 % of 100 kg, 104 kg 104 %, 95 kg 95 %, 84 kg 105 % of 80 kg.


async def lifted(coach, api, clock, *sessions, now: str = "2026-11-29") -> dict:
    api.sessions = list(sessions)
    await synced(coach, api, clock, now)
    return home(coach)["training"]["workouts"]["strength_trend"]


def pcts(trend: dict) -> list:
    return [p["pct"] for p in trend["points"]]


RISING = [
    session("r1", "2026-11-02", exercise("Bench Press", (100, 5))),
    session("r2", "2026-11-09", exercise("Squat", (100, 5)), exercise("Lateral Raise", (10, 12))),
    session("r3", "2026-11-16", exercise("Bench Press", (105, 5)), exercise("Lateral Raise", (5, 12))),
    session("r4", "2026-11-23", exercise("Squat", (104, 5))),
]


async def test_a_rising_trend_steps_with_the_sessions(coach, api, clock):
    counted_too = await lifted(coach, api, clock, *RISING)
    assert counted_too["lifts"] == 3  # Lateral Raise (50 %) counts until it is excluded
    progression.classify(coach, "lateral-raise", "excluded", "slow mover", clock.now())  # never counts

    trend = home(coach)["training"]["workouts"]["strength_trend"]

    assert (trend["window_days"], trend["start"], trend["end"]) == (28, "2026-11-16", "2026-11-29")
    assert [p["date"] for p in trend["points"]][:2] == ["2026-11-16", "2026-11-17"]
    # 16-22 Nov: Bench 105, Squat trained once (doesn't count yet); from 23 Nov Squat 104.
    assert pcts(trend) == [105.0] * 7 + [104.5] * 7
    # Each lift over its own span: Bench +5 % in 14 days (2.5 %/wk), Squat +4 % in 14 days (2.0 %/wk).
    assert (trend["rate_pct_per_week"], trend["direction"], trend["lifts"]) == (2.2, "rising", 2)


async def test_within_the_one_percent_band_the_trend_is_flat(coach, api, clock):
    trend = await lifted(coach, api, clock,
                         session("f1", "2026-11-03", exercise("Bench Press", (100, 5)), exercise("Squat", (100, 5))),
                         session("f2", "2026-11-24", exercise("Bench Press", (100, 5)), exercise("Squat", (101, 5))))

    assert pcts(trend) == [None] * 8 + [100.5] * 6  # one session per lift until 24 Nov: no change to show
    # Bench 0 %, Squat +1 % in 21 days (0.33 %/wk): mean 0.17 %/wk, inside the 1 % band.
    assert (trend["rate_pct_per_week"], trend["direction"]) == (0.2, "flat")


async def test_a_falling_trend(coach, api, clock):
    trend = await lifted(coach, api, clock, session("d1", "2026-11-03", exercise("Bench Press", (100, 5))),
                         session("d2", "2026-11-17", exercise("Bench Press", (95, 5))))

    assert pcts(trend) == [None] + [95.0] * 13
    assert (trend["rate_pct_per_week"], trend["direction"]) == (-2.5, "falling")  # -5 % in 14 days


async def test_a_reset_lift_starts_at_its_reset(coach, api, clock):
    api.sessions = [session("x1", "2026-11-02", exercise("Bench Press", (100, 5))),
                    session("x2", "2026-11-22", exercise("Bench Press", (80, 5))),
                    session("x3", "2026-11-29", exercise("Bench Press", (84, 5)))]
    await synced(coach, api, clock, "2026-11-29")
    progression.mark_reset(coach, "bench-press", datetime.date(2026, 11, 22), clock.now(), reason="shoulder")

    trend = home(coach)["training"]["workouts"]["strength_trend"]

    # Reset a week ago: one session since then until today's 84 kg, 105 % of 80 kg (not 84 % of 100 kg).
    assert pcts(trend) == [None] * 13 + [105.0]
    # +5 % in the 7 days since the reset, not spread over the 28-day window.
    assert (trend["rate_pct_per_week"], trend["direction"]) == (5.0, "rising")


async def test_a_lift_trained_only_lately_is_measured_over_its_own_span(coach, api, clock):
    trend = await lifted(coach, api, clock, session("n1", "2026-11-20", exercise("Bench Press", (100, 5))),
                         session("n2", "2026-11-27", exercise("Bench Press", (104, 5))))

    assert pcts(trend) == [None] * 11 + [104.0] * 3
    # +4 % in 7 days: 4 %/wk, not +4 % over 28 days (1 %/wk, flat).
    assert (trend["rate_pct_per_week"], trend["direction"]) == (4.0, "rising")


async def test_a_span_shorter_than_a_week_counts_as_a_week(coach, api, clock):
    trend = await lifted(coach, api, clock, session("w1", "2026-11-23", exercise("Bench Press", (100, 5))),
                         session("w2", "2026-11-26", exercise("Bench Press", (103, 5))))

    assert pcts(trend)[-1] == 103.0
    assert (trend["rate_pct_per_week"], trend["direction"]) == (3.0, "rising")  # 3 days count as 7


async def test_old_sessions_leave_the_window(coach, api, clock):
    trend = await lifted(coach, api, clock, session("o1", "2026-10-20", exercise("Row", (60, 10))),
                         session("o2", "2026-11-10", exercise("Row", (66, 10))), now="2026-11-20")

    # 7-9 Nov: trained once (no point); 10-16 Nov 110 % of 20 Oct; from 17 Nov only 10 Nov is left.
    assert pcts(trend) == [None] * 3 + [110.0] * 7 + [None] * 4
    assert (trend["rate_pct_per_week"], trend["direction"], trend["lifts"]) == (None, None, 0)


async def test_the_strength_trend_on_a_past_day_ends_that_day(coach, api, clock):
    await lifted(coach, api, clock, *RISING)
    progression.classify(coach, "lateral-raise", "excluded", "slow mover", clock.now())

    trend = home(coach, "2026-11-22")["training"]["workouts"]["strength_trend"]

    assert (trend["start"], trend["end"]) == ("2026-11-09", "2026-11-22")
    assert pcts(trend) == [None] * 7 + [105.0] * 7  # Squat has one session; its 104 kg on 23 Nov hasn't happened
    assert (trend["rate_pct_per_week"], trend["direction"]) == (2.5, "rising")  # Bench +5 % in 14 days


async def test_before_any_lift_there_is_no_trend_and_no_workout(coach):
    workouts = home(coach)["training"]["workouts"]

    assert workouts["sessions"] == [] and workouts["summary"] is None
    assert pcts(workouts["strength_trend"]) == [None] * 14
    assert (workouts["strength_trend"]["rate_pct_per_week"], workouts["strength_trend"]["direction"]) == (None, None)
