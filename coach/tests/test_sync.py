"""Sync: the coach fills its database from the api (MFP food, weight, steps and
runs; Hevy sessions), first 16 weeks, then only what's new or recent. Weigh-in
outliers are marked silently; stale data gets one notice."""

from fa_coach import history
from fa_coach.features.sync import freshness
from fakes import exercise, food, run, session


async def test_first_sync_loads_16_weeks_of_history(coach, api, outbox):
    api.days["2026-07-21"] = {"food": food(2100, complete=True), "weight_kg": 80.0, "steps": 9000}
    api.days["2026-11-08"] = {"food": food(2400), "weight_kg": 81.2, "steps": 12000, "exercises": [run(600, 8.2, 45)]}
    api.sessions = [
        session("w-old", "2026-07-20", exercise("Bench Press", (80, 5))),
        session("w1", "2026-07-21", exercise("Bench Press", (80, 5), (80, 5))),
        session("w2", "2026-11-09", exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps")),
    ]

    await coach.sync()

    days = history.days(coach.db, "2026-07-20", "2026-11-09")
    assert days[0]["date"] == "2026-07-21"  # 16 weeks = 112 days up to today
    assert len(days) == 112
    assert days[0]["kcal"] == 2100 and days[0]["logged"] and days[0]["steps"] == 9000
    nov8 = days[-2]
    assert (nov8["kcal"], nov8["protein_g"], nov8["fiber_g"], nov8["produce_g"]) == (2400, 180, 30, None)
    assert nov8["runs"] == [{"kcal": 600, "distance_km": 8.2, "minutes": 45}]
    assert days[-1]["logged"] is False  # nothing eaten today yet
    assert history.weigh_ins(coach.db, "2026-07-01", "2026-11-09") == {"2026-07-21": 80.0, "2026-11-08": 81.2}

    sessions = history.sessions(coach.db, "2026-07-01", "2026-11-09")
    assert [s["id"] for s in sessions] == ["w1", "w2"]
    assert sessions[0]["exercises"] == [
        {"exercise_id": "bench-press", "title": "Bench Press", "exercise_type": "weight_reps",
         "sets": [{"type": "normal", "weight_kg": 80, "reps": 5}, {"type": "normal", "weight_kg": 80, "reps": 5}]}
    ]
    assert sessions[1]["exercises"][0]["sets"] == [{"type": "normal", "weight_kg": None, "reps": 8}]
    assert outbox.items == []  # syncing is silent


async def test_later_syncs_fetch_only_new_and_recent_days(coach, api, clock):
    api.sessions = [session("w1", "2026-11-05", exercise("Squat", (100, 5)))]
    await coach.sync()
    api.calls.clear()

    api.days["2026-11-04"] = {"food": food(2600)}  # late edit, five days back
    api.sessions = [session("w2", "2026-11-10", exercise("Squat", (102.5, 5)))]  # w1 deleted in Hevy
    await coach.sync(clock.advance(days=1))

    assert api.ranges("mfp_days") == [("2026-11-04", "2026-11-10")]
    assert api.ranges("hevy_sessions") == [("2026-11-04", "2026-11-10")]
    assert history.days(coach.db, "2026-11-04", "2026-11-04")[0]["kcal"] == 2600
    assert [s["id"] for s in history.sessions(coach.db, "2026-10-01", "2026-11-10")] == ["w2"]


async def test_a_sync_after_a_long_gap_resumes_where_it_stopped(coach, api, clock):
    await coach.sync()
    api.calls.clear()

    await coach.sync(clock.advance(days=20))

    assert api.ranges("mfp_days") == [("2026-11-10", "2026-11-29")]


async def test_a_failed_source_keeps_its_place_and_the_other_still_syncs(coach, api, clock):
    await coach.sync()
    api.calls.clear()
    api.fail = {"mfp_days"}
    api.sessions = [session("w2", "2026-11-12", exercise("Squat", (102.5, 5)))]

    await coach.sync(clock.advance(days=3))
    api.fail = set()
    api.calls.clear()
    await coach.sync(clock.advance(days=10))

    assert api.ranges("mfp_days") == [("2026-11-10", "2026-11-22")]
    assert [s["id"] for s in history.sessions(coach.db, "2026-11-01", "2026-11-30")] == ["w2"]


async def test_sync_command_reports_what_came_in(coach, api, outbox):
    api.sessions = [session("w1", "2026-11-03", exercise("Squat", (100, 5)))]

    await coach.on_message("/sync")

    assert outbox.texts == [
        "Synced 112 days from MFP (2026-07-21 to 2026-11-09) and 1 Hevy session (1 new).\n"
        "Last sync: Mon 9 Nov 09:00."
    ]


async def test_sync_command_says_which_source_failed(coach, api, outbox):
    api.fail = {"hevy_sessions"}

    await coach.on_message("/sync")

    assert outbox.texts == [
        "Synced 112 days from MFP (2026-07-21 to 2026-11-09).\n"
        "Hevy failed: 502 Bad Gateway\n"
        "Last sync: never."
    ]


async def test_a_typo_far_from_its_neighbours_is_marked_silently_and_left_out_of_the_trend(coach, api, outbox):
    # 3.5 kg above the median (80.2) of the weigh-ins within 3 days either side
    weights = {"2026-11-02": 80.0, "2026-11-03": 80.2, "2026-11-04": 80.1, "2026-11-05": 83.7,
               "2026-11-06": 80.3, "2026-11-07": 80.2, "2026-11-08": 80.4}
    for day, kg in weights.items():
        api.days[day] = {"weight_kg": kg}

    await coach.sync()
    await coach.run_due_jobs()

    assert history.outlier_days(coach.db, "2026-11-01", "2026-11-09") == ["2026-11-05"]
    trend = history.weigh_ins(coach.db, "2026-11-01", "2026-11-09")
    assert "2026-11-05" not in trend and len(trend) == 6
    assert history.weigh_ins(coach.db, "2026-11-01", "2026-11-09", include_outliers=True)["2026-11-05"] == 83.7
    assert outbox.items == []


async def test_a_normal_spike_stays_in_the_trend(coach, api):
    """The scale records every weigh-in, so a spike of a few kg is real: only
    clear typos (more than 3 kg from the neighbours) are dropped."""
    weights = {"2026-11-02": 80.0, "2026-11-03": 80.2, "2026-11-04": 80.1, "2026-11-05": 82.7,
               "2026-11-06": 80.3, "2026-11-07": 80.2, "2026-11-08": 80.4}
    for day, kg in weights.items():
        api.days[day] = {"weight_kg": kg}

    await coach.sync()

    assert history.outlier_days(coach.db, "2026-11-01", "2026-11-09") == []
    assert history.weigh_ins(coach.db, "2026-11-01", "2026-11-09")["2026-11-05"] == 82.7


async def test_a_steady_gain_is_not_an_outlier(coach, api):
    for i, kg in enumerate([80.0, 80.4, 80.8, 81.2, 81.6, 82.0, 82.4]):
        api.days[f"2026-11-0{i + 2}"] = {"weight_kg": kg}

    await coach.sync()

    assert history.outlier_days(coach.db, "2026-11-01", "2026-11-09") == []


async def test_an_outlier_corrected_in_mfp_is_no_longer_marked(coach, api, clock):
    for day, kg in {"2026-11-05": 80.0, "2026-11-06": 80.2, "2026-11-07": 84.0, "2026-11-08": 80.1}.items():
        api.days[day] = {"weight_kg": kg}
    await coach.sync()
    assert history.outlier_days(coach.db, "2026-11-01", "2026-11-09") == ["2026-11-07"]

    api.days["2026-11-07"] = {"weight_kg": 80.3}
    await coach.sync(clock.advance(hours=4))

    assert history.outlier_days(coach.db, "2026-11-01", "2026-11-09") == []


async def test_stale_data_gets_one_notice_per_stale_stretch(coach, api, clock, outbox):
    await coach.sync()
    await coach.run_due_jobs(clock.advance(hours=30))
    assert outbox.items == []

    api.fail = {"mfp_days"}
    await coach.sync(clock.advance(hours=7))  # 37 h since the last good sync
    await coach.run_due_jobs()
    await coach.run_due_jobs(clock.advance(hours=4))

    assert outbox.texts == [
        "No successful sync since Mon 9 Nov 09:00 (MFP: 502 Bad Gateway). "
        "Weeks without fresh data may not count. /sync retries."
    ]
    assert freshness(coach, clock.now())["fresh"] is False
    assert freshness(coach, clock.now())["last_sync_at"] == "2026-11-09T09:00:00+01:00"

    api.fail = set()
    await coach.sync(clock.advance(hours=1))
    await coach.run_due_jobs()
    assert freshness(coach, clock.now())["fresh"] is True

    api.fail = {"hevy_sessions"}
    await coach.sync(clock.advance(hours=40))
    await coach.run_due_jobs()

    assert len(outbox.texts) == 2
    assert outbox.texts[1].startswith("No successful sync since Wed 11 Nov 03:00 (Hevy: 502 Bad Gateway).")


async def test_a_day_mfp_could_not_read_is_skipped_and_reported(coach, api, outbox):
    api.days["2026-11-08"] = {"error": "500 Server Error"}
    api.days["2026-11-07"] = {"food": food(2300)}

    await coach.on_message("/sync")

    assert [d["date"] for d in history.days(coach.db, "2026-11-07", "2026-11-09")] == ["2026-11-07", "2026-11-09"]
    assert outbox.texts[0].splitlines()[1] == "MFP couldn't read 2026-11-08."


async def test_a_first_sync_that_fails_gets_a_notice(coach, api, outbox):
    api.fail = {"mfp_days", "hevy_sessions"}

    await coach.sync()
    await coach.run_due_jobs()

    assert outbox.texts == [
        "No successful sync yet (MFP: 502 Bad Gateway; Hevy: 502 Bad Gateway). "
        "Weeks without fresh data may not count. /sync retries."
    ]


async def test_no_stale_notice_before_the_first_sync(coach, clock, outbox):
    await coach.run_due_jobs(clock.advance(days=3))

    assert outbox.items == []
