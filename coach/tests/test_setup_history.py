"""Setup values as of the day (coach-followups ticket 03): every setup change
is stored with the day it takes effect (`setup_changes`), and every reader
of a day uses the values in force that day (`phases.params_on`), so a later
calibration or step-goal change doesn't rewrite past days, and an ended
phase's days keep their targets and band.

The reverse of test_weekly_checkin starts Mon 9 Nov 2026 (worked example in
test_steps: 9,000 average steps, k = 0.0345 kcal per step, base 2536 at the
average, surplus -236; a lifting session counts 300).
"""

import datetime

from fa_coach import phases, views
from fa_coach.db import MIGRATIONS, Database
from fakes import exercise, reply, session, tool_call
from test_phase_end import confirm
from test_proposals import request
from test_weekly_checkin import at, fill_week, phase  # noqa: F401

Date = datetime.date


def target(coach, day: str) -> dict:
    return phases.daily_target(coach, Date.fromisoformat(day))


def home(coach, day: str, now: datetime.datetime) -> dict:
    data = coach.view("home", {"day": day}, now=now)
    assert views.errors(coach, "home", data) == []
    return data


async def set_step_goal(coach, model, goal: int) -> None:
    start = len(model.requests)
    model.script(tool_call("record_setup_value", key="step_goal", value=goal), reply("Done."))
    await coach.on_message(f"my step goal is {goal}")
    assert not model.results(start)[0].is_error


# --- step goal -------------------------------------------------------------------------------


async def test_a_step_goal_change_applies_from_its_day_and_leaves_past_days_alone(phase, api, clock, model):
    api.days["2026-11-10"] = {"steps": 11000}
    api.days["2026-11-16"] = {"steps": 11000}
    clock.current = at("2026-11-16", 20)
    await phase.sync()

    await set_step_goal(phase, model, 11000)

    past, today = target(phase, "2026-11-10"), target(phase, "2026-11-16")
    assert past["steps"]["goal"] == 10000 and past["steps"]["kcal"] in (34, 35)  # 1,000 over the old goal
    assert past["base_at_step_goal_kcal"] in (2570, 2571)
    assert today["steps"]["goal"] == 11000 and today["steps"]["kcal"] == 0
    assert today["base_at_step_goal_kcal"] == 2605
    assert past["kcal"] == today["kcal"] == 2369  # the energy doesn't move, only where 0 is
    assert phases.params_on(phase, Date(2026, 11, 15))["steps"]["step_goal"] == 10000
    assert phases.params(phase)["steps"]["step_goal"] == 11000
    steps = phase.view("home", {"day": "2026-11-10"})["steps"]
    assert (steps["goal"], steps["to_go"]) == (10000, 0)


async def test_two_changes_on_one_day_keep_the_last(phase, api, clock, model):
    clock.current = at("2026-11-16", 20)
    await set_step_goal(phase, model, 11000)
    await set_step_goal(phase, model, 12000)

    assert phases.params_on(phase, Date(2026, 11, 16))["steps"]["step_goal"] == 12000
    assert phases.params_on(phase, Date(2026, 11, 15))["steps"]["step_goal"] == 10000


async def test_a_logistics_change_keeps_the_other_logistics_values(phase, clock, model):
    clock.current = at("2026-11-16", 20)
    model.script(tool_call("record_setup_value", key="logistics.evening_reminder_time", value="21:15"),
                 reply("Done."))
    await phase.on_message("remind me at 21:15")

    before, after = (phases.params_on(phase, Date(2026, 11, d))["messaging"] for d in (15, 16))
    assert (before["evening_reminder_time"], after["evening_reminder_time"]) == ("20:30", "21:15")
    assert before["weekly_checkin"] == after["weekly_checkin"] == "mon 09:00"


# --- calibration -----------------------------------------------------------------------------


async def test_a_calibration_change_leaves_past_days_alone(phase, api, clock, model, outbox):
    api.sessions.append(session("s1", "2026-11-10", exercise("Bench Press", (80, 8))))
    api.days["2026-11-10"] = {"steps": 9000}
    clock.current = at("2026-11-10", 20)
    await phase.sync()
    assert target(phase, "2026-11-10")["kcal"] == 2600  # 2300 + the 300-kcal lift

    result = await request(phase, clock, model, type="calibration_change",
                           new_values={"lifting_kcal_per_session": 200})
    await phase.on_button("approve_proposal", result["id"], at("2026-12-08", 13))

    assert phases.params(phase)["activity"]["lifting_kcal_per_session"] == 200
    assert target(phase, "2026-11-10")["kcal"] == 2600
    assert target(phase, "2026-11-10")["activity"]["kcal"] == 300
    assert phases.params_on(phase, Date(2026, 12, 7))["activity"]["lifting_kcal_per_session"] == 300
    assert phases.params_on(phase, Date(2026, 12, 8))["activity"]["lifting_kcal_per_session"] == 200


# --- an ended phase ----------------------------------------------------------------------------


async def test_an_ended_phases_days_keep_their_target_and_band(phase, api, clock, outbox):
    for week in (1, 2, 3, 4):
        fill_week(api, week)
    clock.current = at("2026-12-06", 20)
    await phase.sync()
    before = home(phase, "2026-12-02", at("2026-12-06", 20))
    week_before = phase.view("week", {"week": "2026-W49"}, now=at("2026-12-06", 20))
    assert before["food"]["kcal"]["target"] == 2300
    assert before["weight"]["vs_band"] not in (None, "not_evaluated")

    clock.current = at("2026-12-07", 12)
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-12-07", 13))
    assert phases.active(phase) is None

    now = at("2026-12-07", 14)
    after = home(phase, "2026-12-02", now)
    assert after["food"] == before["food"]
    assert after["weight"]["vs_band"] == before["weight"]["vs_band"]
    detail = phase.view("home/weight", {"day": "2026-12-02"}, now=now)
    assert detail["band"] is not None
    assert any(d["band_low_kg"] is not None for d in detail["series"])
    week = phase.view("week", {"week": "2026-W49"}, now=now)
    assert week["weight"]["band"] == week_before["weight"]["band"] is not None
    assert week["intake"]["days"] == week_before["intake"]["days"]
    assert home(phase, "2026-12-07", now)["food"]["kcal"]["target"] is None  # no target from the end on


async def test_erasing_a_phase_removes_its_setup_history(phase, clock, outbox):
    clock.current = at("2026-11-09", 18)
    await phase.on_message("/endphase")
    await confirm(phase, outbox, at("2026-11-09", 19))

    assert phase.db.value("SELECT COUNT(*) FROM setup_changes") == 0


# --- migration ---------------------------------------------------------------------------------


def test_the_migration_seeds_each_phases_setup_at_its_start(tmp_path, make_coach, db_path, clock):
    older = tmp_path / "before"
    older.mkdir()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name < "23_":
            (older / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    db = Database(db_path, migrations=older)
    db.execute("INSERT INTO phase_setups (id, phase_id, status, created_at, updated_at) VALUES"
               " ('s1', 'reverse_bulk', 'confirmed', 'x', 'x')")
    db.execute(
        "INSERT INTO phases (id, phase_id, setup_id, status, start_date, end_date, setup, started_at) VALUES"
        " ('p1', 'reverse_bulk', 's1', 'active', '2026-10-05', NULL, ?, '2026-10-05T09:00:00+02:00')",
        ('{"step_goal": 9000, "run_kcal_discount": 0.8, "photos_enabled": false, "time_goal_weeks": null,'
         ' "starting_trend_weight_kg": 80.5, "logistics": {"weekly_checkin": "mon 09:00",'
         ' "evening_reminder_time": "20:30"}}',))
    db.conn.close()

    coach = make_coach()
    # A later change from chat must not reach back before its day.
    clock.current = at("2026-11-10", 12)
    with coach.db.transaction():
        phases.record_setup_change(coach, "p1", {"step_goal": 12000, "logistics.weekly_checkin": "sun 18:00"},
                                   valid_from=Date(2026, 11, 10), source="test", now=clock.current)
        coach.db.execute("UPDATE phases SET setup = json_set(setup, '$.step_goal', 12000,"
                         " '$.logistics.weekly_checkin', 'sun 18:00') WHERE id = 'p1'")

    then = phases.params_on(coach, Date(2026, 10, 20))
    assert then["steps"]["step_goal"] == 9000
    assert then["activity"]["run_kcal_discount"] == 0.8
    assert then["measurements"]["photos_enabled"] is False
    assert then["time_goal_weeks"] is None
    assert then["messaging"]["weekly_checkin"] == "mon 09:00"
    assert then["messaging"]["evening_reminder_time"] == "20:30"
    now = phases.params_on(coach, Date(2026, 11, 10))
    assert (now["steps"]["step_goal"], now["messaging"]["weekly_checkin"]) == (12000, "sun 18:00")
    assert phases.params_on(coach, Date(2026, 10, 1)) == coach.skills.params()  # before any phase
