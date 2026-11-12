"""Exercise classification and pause as of the day (coach-followups ticket 04):
every change is stored with the day it takes effect (the day it is made);
judging uses the setting in force on each session's day, and "counts" the
setting in force on the day shown. An exercise's first classification
describes the exercise, so it applies to its whole history."""

import datetime

from fa_coach import progression, strength_trend
from fakes import exercise, session
from test_lift_progression import bench, classify, synced, week

D = datetime.date


def two_weeks():
    """Bench and squat improve in the week to 29 Nov and again in the week to 6 Dec."""
    squat = lambda kg: exercise("Squat", (kg, 6))  # noqa: E731
    return [
        session("s1", "2026-11-19", bench((100, 8)), squat(120)),
        session("s2", "2026-11-26", bench((100, 9)), squat(125)),
        session("s3", "2026-12-03", bench((100, 10)), squat(130)),
    ]


def at(clock, day: str) -> None:
    clock.current = datetime.datetime.combine(D.fromisoformat(day), datetime.time(9), tzinfo=clock.current.tzinfo)


async def test_a_lift_excluded_later_still_counts_on_earlier_weeks(coach, api, clock, model):
    await synced(coach, api, clock, two_weeks(), now="2026-12-04")
    at(clock, "2026-11-27")
    await classify(coach, model, ("bench-press", "counts"), ("squat", "counts"))
    at(clock, "2026-12-04")
    await classify(coach, model, ("squat", "excluded"))

    earlier = week(coach, "2026-11-29")
    assert (earlier["counted_lifts"], earlier["excluded_lifts"]) == (2, [])
    later = week(coach, "2026-12-06")
    assert (later["counted_lifts"], later["excluded_lifts"]) == (1, ["squat"])

    assert progression.lifts(coach, D(2026, 11, 29))["squat"]["counts"] is True
    assert progression.lifts(coach, D(2026, 12, 4))["squat"]["counts"] is False
    # the strength trend's earlier points still include squat (two lifts), today's only bench
    trend = strength_trend.compute(coach, D(2026, 12, 4), days=14)
    by_day = {p["date"]: p["pct"] for p in trend["points"]}
    # 26 Nov: bench 100x9 = 130 vs 126.67 (102.6 %), squat 125x6 = 150 vs 144 (104.2 %): mean 103.4
    assert by_day["2026-11-26"] == 103.4
    # 4 Dec: bench alone, 100x10 = 133.33 vs 126.67 = 105.3 %
    assert by_day["2026-12-04"] == 105.3
    assert trend["lifts"] == 1


async def test_a_first_classification_applies_to_the_whole_history(coach, api, clock, model):
    await synced(coach, api, clock, two_weeks(), now="2026-12-04")
    await classify(coach, model, ("squat", "excluded"))

    assert week(coach, "2026-11-29")["excluded_lifts"] == ["squat"]


async def test_a_pause_covers_only_its_days(coach, api, clock):
    await synced(coach, api, clock, two_weeks(), now="2026-12-04")
    progression.set_paused(coach, "squat", True, "knee", datetime.datetime(2026, 11, 22, 9))
    progression.set_paused(coach, "squat", False, None, datetime.datetime(2026, 11, 30, 9))

    def squat_in(session_id: str) -> dict:
        return next(e for e in progression.session(coach, session_id)["exercises"] if e["name"] == "Squat")

    assert [squat_in(s)["status"] for s in ("s1", "s2", "s3")] == ["new_baseline", "paused", "improved"]
    assert squat_in("s3")["is_pr"] is True

    statuses = lambda end: {lift["exercise_id"]: lift["status"] for lift in week(coach, end)["tracked_lifts"]}  # noqa: E731
    assert statuses("2026-11-21")["squat"] == "new_baseline"
    assert statuses("2026-11-29")["squat"] == "paused"
    assert statuses("2026-12-06")["squat"] == "improved"
    assert [pr["date"] for pr in week(coach, "2026-11-29")["prs"] if pr["exercise_id"] == "squat"] == []


def test_settings_from_before_the_upgrade_apply_to_the_whole_history(tmp_path, make_coach, db_path):
    import shutil

    from fa_coach.db import MIGRATIONS, Database

    old = tmp_path / "old_migrations"
    shutil.copytree(MIGRATIONS, old, ignore=lambda d, names: [n for n in names if n >= "24"])
    db = Database(db_path, migrations=old)
    db.execute("INSERT INTO exercise_settings (exercise_id, title, classification, paused, paused_reason, updated_at)"
               " VALUES ('squat', 'Squat', 'excluded', 1, 'knee', '2026-11-20T09:00:00')")
    db.conn.close()

    coach = make_coach()

    assert progression.setting_on(coach, "squat", D(2020, 1, 1)) == {
        "classification": "excluded", "paused": True, "paused_reason": "knee"}
    assert progression.setting_on(coach, "bench-press", D(2020, 1, 1)) == {
        "classification": None, "paused": False, "paused_reason": None}
