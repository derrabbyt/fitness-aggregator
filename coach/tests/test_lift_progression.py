"""Lift progression (ticket 08): every Hevy exercise is judged on its heaviest
working set with 4-20 reps against the best of its previous 3 sessions;
only exercises classified as counting decide `progression_met`, stalls and
the deload signal.

Worked numbers: Epley e1RM = load x (1 + reps / 30), used only when load and reps move in
opposite directions. 100 x 8 = 126.67;
102.5 x 7 = 126.42 (-0.2 %: same); 105 x 8 = 133.0 (+5 %: improved);
85 x 8 = 107.67 (-15 %: a possible reset).
"""

import datetime

import pytest

from fa_coach import progression
from fa_coach.features import weekly_checkin
from fakes import TZ, exercise, reply, reply_json, session, tool_call, tool_calls
from test_weekly_checkin import check_in, decision_requests, phase, reports, three_weeks, verdict  # noqa: F401

D = datetime.date
DAY = datetime.timedelta(days=1)


def bench(*sets, title: str = "Bench Press"):
    return exercise(title, *sets)


def warmup(ex: dict, weight: float, reps: int) -> dict:
    ex["sets"].insert(0, {"type": "warmup", "weight_kg": weight, "reps": reps, "distance_m": None,
                          "duration_s": None, "rpe": None})
    return ex


async def synced(coach, api, clock, sessions, *, weigh_ins: dict[str, float] | None = None,
                 now: str = "2026-11-30") -> None:
    api.sessions = list(sessions)
    for day, kg in (weigh_ins or {}).items():
        api.days.setdefault(day, {})["weight_kg"] = kg
    clock.current = datetime.datetime.combine(D.fromisoformat(now), datetime.time(9), tzinfo=TZ)
    await coach.sync()


def judged(coach, session_id: str, name: str = "Bench Press") -> dict:
    return next(e for e in progression.session(coach, session_id)["exercises"] if e["name"] == name)


def statuses(coach, ids, name: str = "Bench Press") -> list[str]:
    return [judged(coach, i, name)["status"] for i in ids]


def week(coach, end: str = "2026-11-29") -> dict:
    """The training section for the week ending `end`, in a phase that started 2 Nov."""
    end_date = D.fromisoformat(end)
    return progression.week(coach, end_date - 6 * DAY, end_date, D(2026, 11, 2))


def days(start: str, n: int, kg: float) -> dict[str, float]:
    first = D.fromisoformat(start)
    return {(first + k * DAY).isoformat(): kg for k in range(n)}


# --- one session -----------------------------------------------------------------------


async def test_more_reps_at_the_same_load_improves_and_warm_ups_and_singles_dont_count(coach, api, clock):
    await synced(coach, api, clock, [
        session("s1", "2026-11-16", bench((100, 8))),
        session("s2", "2026-11-19", bench((100, 8))),
        session("s3", "2026-11-23", warmup(bench((120, 2), (100, 9), (100, 7)), 60, 10)),
    ])

    s3 = judged(coach, "s3")
    assert s3["status"] == "improved"
    assert s3["top_set"] == {"load_kg": 100, "reps": 9, "effective_load_kg": 100, "e1rm_kg": 130.0}
    assert s3["best_recent"]["reps"] == 8 and s3["is_pr"] is True
    assert s3["sets"] == [{"load_kg": 120, "reps": 2}, {"load_kg": 100, "reps": 9}, {"load_kg": 100, "reps": 7}]


async def test_same_load_compares_reps_and_a_different_load_compares_e1rm_within_one_percent(coach, api, clock):
    first = [bench((100, 8), title=t) for t in ("A", "B", "C", "E")]
    second = [bench((102.5, 7), title="A"), bench((100, 7), title="B"), bench((105, 8), title="C"),
              bench((100, 8), title="E")]
    await synced(coach, api, clock, [session("s1", "2026-11-16", *first), session("s2", "2026-11-19", *second)])

    result = {e["name"]: e["status"] for e in progression.session(coach, "s2")["exercises"]}
    assert result == {"A": "same", "B": "declined", "C": "improved", "E": "same"}
    assert judged(coach, "s2", "B")["no_progress_streak"] == 1 and judged(coach, "s2", "B")["decline_streak"] == 1


async def compared(coach, api, clock, before: tuple[float, int], *after: tuple[float, int]) -> list[str]:
    """Status of each `after` set (its own exercise) against `before`."""
    titles = [f"L{k}" for k in range(len(after))]
    await synced(coach, api, clock, [
        session("s1", "2026-11-16", *[bench(before, title=t) for t in titles]),
        session("s2", "2026-11-19", *[bench(a, title=t) for a, t in zip(after, titles)]),
    ])
    return [judged(coach, "s2", t)["status"] for t in titles]


async def test_a_micro_progression_counts_even_inside_the_e1rm_band(coach, api, clock):
    # 100 x 8 -> 100.5 x 8 is e1RM +0.5 %, inside the 1 % band, but more load at the same reps
    assert await compared(coach, api, clock, (100, 8), (100.5, 8), (99.5, 8), (100.5, 9)) == [
        "improved", "declined", "improved"]
    assert judged(coach, "s2", "L0")["is_pr"] is True


async def test_one_more_rep_at_the_same_load_improves_and_one_fewer_declines(coach, api, clock):
    assert await compared(coach, api, clock, (100, 8), (100, 9), (100, 7), (100, 8), (99.5, 7)) == [
        "improved", "declined", "same", "declined"]


async def test_load_and_reps_moving_in_opposite_directions_compare_e1rm_within_one_percent(coach, api, clock):
    # 100 x 8 = 126.67; 105 x 6 = 126.0 (-0.5 %); 110 x 6 = 132.0 (+4 %); 95 x 9 = 123.5 (-2.5 %);
    # 99 x 9 = 128.7 (+1.6 %)
    assert await compared(coach, api, clock, (100, 8), (105, 6), (110, 6), (95, 9), (99, 9)) == [
        "same", "improved", "declined", "improved"]


async def test_the_first_session_starts_the_history_without_a_pr(coach, api, clock):
    await synced(coach, api, clock, [session("s1", "2026-11-16", bench((100, 8)))])

    s1 = judged(coach, "s1")
    assert (s1["status"], s1["not_judged_reason"], s1["is_pr"]) == ("new_baseline", "first_session", False)


async def test_bodyweight_gained_counts_as_added_load(coach, api, clock):
    pull = lambda: exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps")  # noqa: E731
    dips = lambda: exercise("Dip", (10, 8), exercise_type="bodyweight_reps")  # noqa: E731
    await synced(coach, api, clock, [session("s1", "2026-11-05", pull(), dips()),
                                     session("s2", "2026-11-16", pull(), dips())],
                 weigh_ins={**days("2026-10-30", 7, 80.0), **days("2026-11-10", 7, 82.0)})

    s2 = judged(coach, "s2", "Pull Up")
    assert s2["status"] == "improved"  # 80 kg x 8 -> 82 kg x 8: e1RM +2.5 %
    assert (s2["best_recent"]["effective_load_kg"], s2["top_set"]["effective_load_kg"]) == (80.0, 82.0)
    assert judged(coach, "s2", "Dip")["top_set"]["effective_load_kg"] == 92.0


async def test_a_bodyweight_change_under_one_kg_is_the_same_load(coach, api, clock):
    # trend 80.0 -> 81.2 (+1.2 kg) at 8 reps: improved; then 80.9 (-0.3 kg vs 81.2) at 8 reps: same
    pull = lambda: exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps")  # noqa: E731
    await synced(coach, api, clock, [session("s1", "2026-11-05", pull()), session("s2", "2026-11-16", pull()),
                                     session("s3", "2026-11-26", pull())],
                 weigh_ins={**days("2026-10-30", 7, 80.0), **days("2026-11-10", 7, 81.2),
                            **days("2026-11-20", 7, 80.9)})

    assert statuses(coach, ["s2", "s3"], "Pull Up") == ["improved", "same"]
    assert [judged(coach, s, "Pull Up")["is_pr"] for s in ("s2", "s3")] == [True, False]


async def test_bodyweight_drift_is_no_pr(coach, api, clock):
    # trend 80.0 -> 80.5 at the same 8 reps and the same 10 kg added
    dips = lambda: exercise("Dip", (10, 8), exercise_type="bodyweight_reps")  # noqa: E731
    await synced(coach, api, clock, [session("s1", "2026-11-05", dips()), session("s2", "2026-11-16", dips())],
                 weigh_ins={**days("2026-10-30", 7, 80.0), **days("2026-11-10", 7, 80.5)})

    s2 = judged(coach, "s2", "Dip")
    assert (s2["status"], s2["is_pr"]) == ("same", False)


async def test_three_sessions_without_progress_are_a_stall_flagged_once_and_never_for_excluded(
        coach, api, clock, model):
    abs_ = lambda: exercise("Crunch", (20, 12))  # noqa: E731
    ids = ["s1", "s2", "s3", "s4", "s5"]
    dates = ["2026-11-09", "2026-11-12", "2026-11-16", "2026-11-19", "2026-11-23"]
    await synced(coach, api, clock, [session(i, d, bench((100, 8)), abs_()) for i, d in zip(ids, dates)])
    model.script(tool_call("classify_exercises", exercises=[{"exercise_id": "crunch", "classification": "excluded"}]),
                 reply("Crunches won't count."))
    await coach.on_message("don't count crunches")

    assert [judged(coach, i)["no_progress_streak"] for i in ids] == [0, 1, 2, 3, 4]
    assert [judged(coach, i)["new_stall"] for i in ids] == [False, False, False, True, False]
    assert judged(coach, "s5")["stalled"] is True
    assert not any(judged(coach, i, "Crunch")["stalled"] for i in ids)
    t = week(coach, "2026-11-29")
    assert t["stalls"] == ["bench-press"] and t["excluded_lifts"] == ["crunch"]


async def test_after_a_break_the_first_session_back_is_not_judged_and_the_next_compares_with_older_ones(
        coach, api, clock):
    await synced(coach, api, clock, [
        session("s1", "2026-10-01", bench((100, 8))),
        session("s2", "2026-10-05", bench((100, 8))),
        session("s3", "2026-10-26", bench((90, 8))),  # 21 days later
        session("s4", "2026-10-29", bench((100, 9))),
    ])

    s3, s4 = judged(coach, "s3"), judged(coach, "s4")
    assert (s3["status"], s3["not_judged_reason"], s3["possible_reset"]) == ("not_judged", "after_break", False)
    assert s4["status"] == "improved" and s4["best_recent"]["load_kg"] == 100  # best of s1, s2, s3


async def test_a_day_at_another_gym_is_not_judged_not_a_baseline_and_gives_no_pr(coach, api, clock, model):
    await synced(coach, api, clock, [
        session("s1", "2026-11-16", bench((100, 8))),
        session("s2", "2026-11-19", bench((110, 8))),  # other machine: much heavier
        session("s3", "2026-11-23", bench((100, 9))),
    ])
    clock.current = datetime.datetime(2026, 11, 30, 10, tzinfo=TZ)
    model.script(tool_call("add_context_note", applies_from="2026-11-19", applies_to="2026-11-19",
                           tags=["travel", "other_location"], suggest_unusable="no"), reply("Noted."))
    await coach.on_message("on the 19th I trained at the hotel gym")

    s2, s3 = judged(coach, "s2"), judged(coach, "s3")
    assert (s2["status"], s2["not_judged_reason"], s2["is_pr"]) == ("not_judged", "other_location", False)
    assert s3["status"] == "improved" and s3["best_recent"]["load_kg"] == 100 and s3["is_pr"] is True


async def test_a_big_drop_asks_about_a_reset_and_a_marked_reset_starts_a_new_baseline(coach, api, clock):
    await synced(coach, api, clock, [
        session("s1", "2026-11-16", bench((100, 8))),
        session("s2", "2026-11-19", bench((85, 8))),
        session("s3", "2026-11-23", bench((85, 9))),
    ])

    s2 = judged(coach, "s2")
    assert (s2["status"], s2["drop_pct_vs_best_recent"], s2["possible_reset"]) == ("declined", 15.0, True)
    assert judged(coach, "s3")["status"] == "declined"  # still below 100 x 8

    progression.mark_reset(coach, "bench-press", D(2026, 11, 19), clock.now(), session_id="s2", reason="ROM change")

    s2, s3 = judged(coach, "s2"), judged(coach, "s3")
    assert (s2["status"], s2["not_judged_reason"], s2["possible_reset"]) == ("new_baseline", "baseline_reset", False)
    assert (s3["status"], s3["best_recent"]["load_kg"], s3["is_pr"]) == ("improved", 85, True)


async def test_a_pain_note_for_the_day_stops_the_reset_question(coach, api, clock, model):
    await synced(coach, api, clock, [session("s1", "2026-11-16", bench((100, 8))),
                                     session("s2", "2026-11-19", bench((80, 8)))])
    model.script(tool_call("add_context_note", applies_from="2026-11-19", applies_to="2026-11-19",
                           tags=["pain"], exercise_id="bench-press", suggest_unusable="no"), reply("Noted."))
    await coach.on_message("shoulder hurt on bench on the 19th")

    assert judged(coach, "s2")["possible_reset"] is False


# --- the week --------------------------------------------------------------------------


def counting_week():
    """Bench and squat improve, row is the same, lateral raise improves (excluded), curl last
    trained 3 weeks ago."""
    raise_ = lambda r: exercise("Lateral Raise", (10, r))  # noqa: E731
    return [
        session("s0", "2026-11-05", exercise("Curl", (20, 10))),
        session("s1", "2026-11-19", bench((100, 8)), exercise("Squat", (120, 6)), exercise("Row", (80, 10)),
                raise_(12)),
        session("s2", "2026-11-26", bench((100, 9)), exercise("Squat", (125, 6)), exercise("Row", (80, 10)),
                raise_(14)),
    ]


async def classify(coach, model, *pairs) -> None:
    start = len(model.requests)
    model.script(tool_call("classify_exercises", exercises=[{"exercise_id": i, "classification": c}
                                                           for i, c in pairs]), reply("Done."))
    await coach.on_message("classify")
    assert not model.results(start)[0].is_error


async def test_progression_is_met_when_half_of_the_counted_lifts_improved(coach, api, clock, model):
    await synced(coach, api, clock, counting_week())
    await classify(coach, model, ("lateral-raise", "excluded"))

    t = week(coach)
    lifts = {lift["exercise_id"]: lift for lift in t["tracked_lifts"]}
    assert lifts["curl"]["status"] == "stale" and lifts["curl"]["counted"] is False
    assert lifts["lateral-raise"]["counted"] is False and lifts["lateral-raise"]["status"] == "improved"
    assert (t["counted_lifts"], t["improved_lifts"], t["share_improved"], t["progression_met"]) == (3, 2, 0.67, True)
    assert [pr["name"] for pr in t["prs"]] == ["Bench Press", "Lateral Raise", "Squat"]  # excluded PRs still named
    assert [lift["name"] for lift in t["tracked_lifts"]][-1] == "Lateral Raise"  # counting ones first
    assert (t["lifting_sessions"], t["max_sets_in_a_session"]) == (1, 4)

    await classify(coach, model, ("squat", "excluded"))
    t = week(coach)
    assert (t["counted_lifts"], t["improved_lifts"], t["progression_met"]) == (2, 1, True)
    await classify(coach, model, ("bench-press", "excluded"))
    assert week(coach)["progression_met"] is False


async def test_progression_is_null_when_no_lift_could_be_counted(coach, api, clock):
    await synced(coach, api, clock, [session("s1", "2026-11-26", bench((100, 8)))])

    t = week(coach)
    assert t["tracked_lifts"][0]["status"] == "new_baseline"
    assert (t["counted_lifts"], t["progression_met"], t["share_improved"]) == (0, None, None)


async def test_two_lifts_declining_two_sessions_in_a_row_give_the_deload_signal(coach, api, clock):
    squat = lambda kg: exercise("Squat", (kg, 6))  # noqa: E731
    await synced(coach, api, clock, [
        session("s1", "2026-11-16", bench((100, 8)), squat(120)),
        session("s2", "2026-11-19", bench((100, 7)), squat(115)),
        session("s3", "2026-11-23", bench((100, 6)), squat(110)),
    ])

    t = week(coach)
    assert t["declining_lifts"] == ["bench-press", "squat"] and t["deload_signal"] is True

    progression.set_paused(coach, "squat", True, "knee", clock.now())
    t = week(coach, clock.now().date().isoformat())  # a pause applies from the day it's made
    assert {lift["exercise_id"]: lift["status"] for lift in t["tracked_lifts"]}["squat"] == "paused"
    assert t["deload_signal"] is False and t["counted_lifts"] == 1


# --- classification in chat -------------------------------------------------------------


async def test_the_model_reads_and_classifies_exercises_and_unknown_ids_are_refused(coach, api, clock, model):
    await synced(coach, api, clock, counting_week())
    start = len(model.requests)
    model.script(tool_calls(("get_tracked_exercises", {}),
                            ("classify_exercises", {"exercises": [{"exercise_id": "nope", "classification": "counts"}]}),
                            ("classify_exercises", {"exercises": [{"exercise_id": "row", "classification": "excluded",
                                                                   "reason": "user asked"}]})),
                 reply("Rows no longer count."))

    await coach.on_message("stop counting rows")

    listed, unknown, ok = model.results(start)
    assert {e["exercise_id"] for e in listed.content["exercises"]} == {"bench-press", "squat", "row",
                                                                         "lateral-raise", "curl"}
    assert unknown.is_error and "not in the synced Hevy history" in unknown.content["error"]
    assert ok.content == {"classified": [{"exercise_id": "row", "name": "Row", "classification": "excluded"}]}
    assert {lift["exercise_id"]: lift["counts"] for lift in week(coach)["tracked_lifts"]}["row"] is False


# --- in the weekly check-in (phase from test_weekly_checkin: bench and pull-ups counting) ---


def lifting(api, *, week3_bench: int, week3_pull: int) -> None:
    """Bench and pull-ups on Mon/Thu of week 2 and the Thursday of week 3 (reps there as given)."""
    pull = lambda reps: exercise("Pull Up", (None, reps), exercise_type="bodyweight_reps")  # noqa: E731
    api.sessions += [
        session("w2a", "2026-11-16", bench((100, 8)), pull(8)),
        session("w2b", "2026-11-19", bench((100, 8)), pull(8)),
        session("w3", "2026-11-26", bench((100, week3_bench)), pull(week3_pull)),
    ]


async def run_week3(coach, api, clock, model, *, avg: float | None, bench_reps: int, pull_reps: int,
                    data: dict) -> dict:
    lifting(api, week3_bench=bench_reps, week3_pull=pull_reps)
    await three_weeks(coach, api, clock, model, avg=avg, kcal=2350)
    await check_in(coach, clock, model, "2026-11-30", data)
    return decision_requests(model)[-1].input


async def test_b_not_gaining_but_lifts_progressing_holds(phase, api, clock, model):
    facts = await run_week3(phase, api, clock, model, avg=81.85, bench_reps=9, pull_reps=9,
                            data=verdict("2026-W48", scenario="B", rules=["WD-TABLE", "RB-B"]))

    assert facts["weight"]["vs_band"] == "below_band" and facts["data_quality"]["code_usable"] is True
    t = facts["training"]
    assert (t["counted_lifts"], t["improved_lifts"], t["progression_met"]) == (2, 2, True)
    assert [pr["name"] for pr in t["prs"]] == ["Bench Press", "Pull Up"]
    stored = weekly_checkin.stored(phase, "2026-W48")
    assert stored["verdict"]["scenario"] == "B" and stored["verdict"]["direction"] == "hold"
    assert stored["counts_for_confirmation"] is True
    assert model.requests[-1].input["facts"]["training"] == t  # the report sees the training section


async def test_c_not_gaining_and_not_progressing_points_to_an_increase(phase, api, clock, model):
    facts = await run_week3(phase, api, clock, model, avg=81.85, bench_reps=8, pull_reps=8,
                            data=verdict("2026-W48", scenario="C", direction="increase",
                                         rules=["WD-TABLE", "RB-C"]))

    assert facts["weight"]["vs_band"] == "below_band"
    t = facts["training"]
    assert (t["counted_lifts"], t["improved_lifts"], t["progression_met"]) == (2, 0, False)
    stored = weekly_checkin.stored(phase, "2026-W48")
    assert (stored["verdict"]["scenario"], stored["verdict"]["direction"]) == ("C", "increase")
    assert stored["counts_for_confirmation"] is True


async def test_d_gaining_but_not_progressing_flags_training_and_the_fallback_report_says_so(
        phase, api, clock, model, outbox):
    looks = {"code": "training_needs_look", "severity": "watch", "detail": "no lift improved", "exercise_id": None}
    lifting(api, week3_bench=7, week3_pull=8)
    await three_weeks(phase, api, clock, model, kcal=2250)
    clock.current = datetime.datetime(2026, 11, 30, 9, tzinfo=TZ)
    await phase.sync()
    model.script(reply_json(verdict("2026-W48", scenario="D", flags=[looks], rules=["WD-TABLE", "RB-D"])),
                 reply("not a coach message"))
    await phase.run_due_jobs()

    facts = decision_requests(model)[-1].input
    assert facts["weight"]["vs_band"] == "in_band"
    t = facts["training"]
    assert (t["counted_lifts"], t["improved_lifts"], t["progression_met"]) == (2, 0, False)
    assert {lift["name"]: lift["status"] for lift in t["tracked_lifts"]} == {"Bench Press": "declined",
                                                                              "Pull Up": "same"}
    # pull-ups: same reps at a trend 82.0 -> 81.91, under bodyweight_same_load_kg: the same load
    stored = weekly_checkin.stored(phase, "2026-W48")
    assert stored["verdict"]["scenario"] == "D" and stored["verdict"]["direction"] == "hold"
    assert [f["code"] for f in stored["verdict"]["flags"]] == ["training_needs_look"]
    assert "Training: 0 of 2 counting lifts improved" in reports(outbox)[-1]


# --- tracked lifts from ticket 05 are retired --------------------------------------------


def test_an_old_setup_with_tracked_lifts_loses_them_on_upgrade(tmp_path, make_coach, db_path):
    import json
    import shutil

    from fa_coach import phases
    from fa_coach.db import MIGRATIONS, Database

    old = tmp_path / "old_migrations"
    shutil.copytree(MIGRATIONS, old, ignore=lambda d, names: [n for n in names if n >= "08"])
    db = Database(db_path, migrations=old)
    setup = {"phase_id": "reverse_bulk", "start_date": "2026-11-09",
             "tracked_lifts": [{"exercise_id": None, "name": "Bench Press", "bodyweight_exercise": False}]}
    db.execute("INSERT INTO phase_setups (id, phase_id, status, setup_values, created_at, updated_at) VALUES"
               " ('s1', 'reverse_bulk', 'confirmed', ?, 'x', 'x')", (json.dumps(setup),))
    db.execute("INSERT INTO phases (id, phase_id, setup_id, status, start_date, setup, started_at) VALUES"
               " ('p1', 'reverse_bulk', 's1', 'active', '2026-11-09', ?, 'x')", (json.dumps(setup),))
    db.conn.close()

    coach = make_coach()

    assert "tracked_lifts" not in phases.active(coach)["setup"]
    assert "tracked_lifts" not in phases.get_setup(coach, "s1")["values"]


# --- new exercises during a phase ---------------------------------------------------------


async def test_a_new_exercise_during_the_phase_is_classified_by_the_model_and_shown_once(
        phase, api, clock, model, outbox):
    api.sessions.append(session("n1", "2026-11-12", bench((100, 8)), exercise("Tibialis Raise", (0, 15))))
    clock.current = datetime.datetime(2026, 11, 12, 12, tzinfo=TZ)
    await phase.sync()
    text = "New in Hevy: Tibialis Raise – excluded (prehab). Say if it should count."
    model.script(tool_call("classify_exercises", exercises=[{"exercise_id": "tibialis-raise",
                                                             "classification": "excluded", "reason": "prehab"}]),
                 reply(text))

    await phase.run_due_jobs()
    await phase.run_due_jobs()

    requests = [r for r in model.requests if r.task_skills == ("new-exercise",) and not r.steps]
    assert len(requests) == 1  # one task (its tool loop has a second turn), not one per job run
    assert [e["exercise_id"] for e in requests[0].input["new_exercises"]] == ["tibialis-raise"]
    assert [t["name"] for t in requests[0].tools] == ["classify_exercises"]
    assert outbox.texts.count(text) == 1
    classes = {e["exercise_id"]: e["classification"] for e in progression.exercises(phase, D(2026, 11, 1),
                                                                                       D(2026, 11, 12))}
    assert classes == {"bench-press": "counts", "tibialis-raise": "excluded"}
