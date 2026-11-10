"""Weekly check-in: code computes the facts for the week that just ended, the
decision model returns a verdict, code stores it with its facts and rule ids,
and the weekly report goes out.

Worked example (as test_phase_start): the reverse starts Mon 9 Nov 2026 at
2300 kcal on average (base maintenance 2536, surplus -236; rest day 2300,
Friday wrestling 2900), check-in Mondays 09:00. The glycogen window covers
phase weeks 1-2. Weekly weight averages: 81.5, 81.8, then week 3 (23-29 Nov)
82.0. Week 3: rate +0.2 kg (band 0.1-0.3: in band); weekly target 6 x 2300 +
2900 = 16700 kcal, eaten 2300 a day = 16100 (-3.6 %, within 5 %); predicted
81.8 - 236 x 7 / 7500 = 81.58 kg, error +0.42 kg > 0.3 kg: a miss. Macros at
the week-2 trend weight 81.8 kg: protein 164 g, fat 74 g; fiber 24.5-40.9 g.
"""

import datetime

import pytest

from fa_coach import messaging
from fa_coach.features import weekly_checkin
from fakes import TZ, exercise, food, reply, reply_json, session, tool_call
from test_phase_start import SETUP, card, start_and_collect

DAY = datetime.timedelta(days=1)
PHASE_START = datetime.date(2026, 11, 9)
WEEK_AVG = {1: 81.5, 2: 81.8, 3: 82.0, 4: 82.1, 5: 82.2}


def at(date: str, hour: int = 9, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(datetime.date.fromisoformat(date), datetime.time(hour, minute), tzinfo=TZ)


def week_dates(week: int) -> list[str]:
    return [(PHASE_START + ((week - 1) * 7 + n) * DAY).isoformat() for n in range(7)]


def fill_week(api, week: int, *, kcal: float = 2300, avg: float | None = None, weigh_ins: int = 7,
              logged: int = 7) -> None:
    avg = WEEK_AVG[week] if avg is None else avg
    for n, day in enumerate(week_dates(week)):
        api.days[day] = {"food": food(kcal) if n < logged else None, "steps": 9000,
                         "weight_kg": avg if n < weigh_ins else None}
        if api.days[day]["food"] is None:
            del api.days[day]["food"]


@pytest.fixture
async def phase(coach, api, model, outbox, monkeypatch):
    """Diet history, then the reverse confirmed on Mon 9 Nov with Monday 09:00 check-ins."""
    monkeypatch.setitem(SETUP, "logistics.weekly_checkin", "mon 09:00")
    day = datetime.date(2026, 10, 12)
    for week_avg in (82.0, 81.5, 81.0, 80.5):
        for _ in range(7):
            api.days[day.isoformat()] = {"food": food(2000), "weight_kg": week_avg, "steps": 9000}
            day += DAY
    # The tracked lifts' Hevy history, before the maintenance window so the targets stay as above.
    api.sessions = [session("w0", "2026-10-10", exercise("Bench Press", (80, 5)),
                            exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps"))]
    await coach.sync()
    await start_and_collect(coach, model)
    confirm = card(outbox).buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)
    outbox.clear()
    return coach


def verdict(iso_week: str, *, scenario: str = "A", direction: str = "hold", usable: bool = True,
            adherence: str = "pass", proposal: dict | None = None, flags: list | None = None,
            rules: list | None = None) -> dict:
    return {
        "schema_version": 1, "iso_week": iso_week, "phase_id": "reverse_bulk", "usable": usable,
        "unusable_reasons": [] if usable else ["too_few_weigh_ins"], "scenario": scenario,
        "weight_assessment": "in_band", "progression": "not_evaluated", "direction": direction,
        "confirmation": {"consecutive_usable_weeks_same_direction": 1, "required_weeks": 2, "met": False},
        "adherence_gate": adherence, "sport_load_applied": False, "proposal": proposal, "flags": flags or [],
        "rules_applied": rules or ["WD-USABLE-CODE", "WD-TABLE", "RB-A"], "confidence": "medium",
        "reasoning": "Weight is in the band.", "questions_for_user": [],
    }


def message(text: str) -> dict:
    return {"send": True, "text": text, "buttons": [], "deferred_to_weekly": []}


async def check_in(coach, clock, model, date: str, data: dict, report: str = "Report.") -> None:
    """Sync late the evening before (as the scheduler does through the day), then
    sync and run the jobs at 09:00 on `date` with a scripted verdict and report."""
    clock.current = at(date) - datetime.timedelta(hours=10)
    await coach.sync()
    clock.current = at(date)
    await coach.sync()
    model.script(reply_json(data), reply_json(message(report)))
    await coach.run_due_jobs()


def reports(outbox) -> list[str]:
    """Weekly check-in messages (other jobs, e.g. measurement reminders, also send)."""
    return [m.text for m in outbox.sent if (m.ref or "").startswith("weekly:") or "check-in for" in m.text]


def decision_requests(model) -> list:
    return [r for r in model.requests if r.task_skills == ("weekly-decision",)]


async def three_weeks(coach, api, clock, model, **week3) -> None:
    fill_week(api, 1)
    fill_week(api, 2)
    fill_week(api, 3, **week3)
    await check_in(coach, clock, model, "2026-11-16", verdict("2026-W46", scenario="glycogen_window"))
    await check_in(coach, clock, model, "2026-11-23", verdict("2026-W47", scenario="glycogen_window"))


# --- facts, verdict, report ------------------------------------------------------------


async def test_the_decision_model_gets_schema_valid_facts_with_the_weeks_numbers(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"), report="Week 3: on track.")

    request = decision_requests(model)[-1]
    assert request.decision is True and request.output_schema == "weekly_verdict" and request.tools == ()
    facts = request.input
    assert phase.skills.errors(facts, "weekly_facts") == []
    assert facts["week"] == {"iso_week": "2026-W48", "start_date": "2026-11-23", "end_date": "2026-11-29",
                             "phase_id": "reverse_bulk", "phase_week": 3, "in_glycogen_window": False,
                             "phase_first_change_pending": False}
    dq = facts["data_quality"]
    assert (dq["weigh_in_count"], dq["food_days_logged"], dq["food_log_complete"]) == (7, 7, True)
    assert dq["sync_fresh"] is True and dq["code_usable"] is True
    w = facts["weight"]
    assert (w["avg_7d_kg"], w["prev_avg_7d_kg"], w["weekly_rate_kg"]) == (82.0, 81.8, 0.2)
    assert (w["band"]["low"], w["band"]["high"], w["band"]["upper_limit"]) == (0.1, 0.3, 0.5)
    assert w["vs_band"] == "in_band"
    assert (w["predicted_avg_7d_kg"], w["prediction_error_kg"], w["prediction_miss"]) == (81.58, 0.42, True)
    i = facts["intake"]
    assert (i["weekly_target_kcal"], i["weekly_actual_kcal"], i["deviation_pct"]) == (16700, 16100, -3.6)
    assert i["adherence_ok"] is True
    assert [d["target_kcal"] for d in i["daily"]] == [2300, 2300, 2300, 2300, 2900, 2300, 2300]
    assert (i["macro_targets"]["protein_g"], i["macro_targets"]["fat_g"]) == (164, 74)
    assert i["macro_targets"]["reference_weight_kg"] == 81.8
    assert i["fiber_target_g"] == [24.5, 40.9]
    a = facts["activity"]
    assert [(s["date"], s["type"], s["kcal_counted"]) for s in a["sessions"]] == [("2026-11-27", "wrestling", 600)]
    assert (a["avg_steps"], a["days_below_floor"], a["sport_load_high"]) == (9000, 7, False)
    assert facts["training"]["progression_met"] is None
    assert facts["targets"]["avg_daily_target_kcal"] == 2300 and facts["targets"]["mfp_goal_kcal"] == 2300
    assert facts["history"]["last_change"]["source"] == "phase_start"
    assert facts["params"]["decisions"]["prediction_miss_kg"] == 0.3

    report = model.requests[-1]
    assert report.task_skills == ("weekly-report",) and report.decision is False
    assert report.input["verdict"]["iso_week"] == "2026-W48" and report.input["facts"] == facts
    assert reports(outbox)[-1] == "Week 3: on track."


async def test_a_prediction_error_within_the_fixed_threshold_is_no_miss(phase, api, clock, model):
    await three_weeks(phase, api, clock, model, avg=81.85)  # error +0.27: above the 0.2 band width, below 0.3
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"))

    w = decision_requests(model)[-1].input["weight"]
    assert (w["weekly_rate_kg"], w["vs_band"]) == (0.05, "below_band")
    assert (w["prediction_error_kg"], w["prediction_miss"]) == (0.27, False)


async def test_the_verdict_is_stored_with_its_facts_and_rule_ids(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"), report="Week 3.")

    stored = weekly_checkin.stored(phase, "2026-W48")
    assert stored["verdict"]["scenario"] == "A"
    assert stored["rules_applied"] == ["WD-USABLE-CODE", "WD-TABLE", "RB-A"]
    assert stored["facts"] == decision_requests(model)[-1].input
    assert stored["counts_for_confirmation"] is True and stored["report"] == "Week 3."


async def test_the_job_runs_at_the_check_in_time_once_per_week(phase, api, clock, model, outbox):
    fill_week(api, 1)
    clock.current = at("2026-11-16", 8, 59)
    await phase.sync()
    await phase.run_due_jobs()
    assert decision_requests(model) == []  # not yet

    await check_in(phase, clock, model, "2026-11-16", verdict("2026-W46", scenario="glycogen_window"))
    clock.current = at("2026-11-16", 20)
    await phase.run_due_jobs()  # same week again: nothing
    await phase.run_due_jobs()

    assert len(decision_requests(model)) == 1
    assert decision_requests(model)[0].input["week"]["in_glycogen_window"] is True
    assert reports(outbox) == ["Report."]


async def test_an_invalid_verdict_is_not_acted_on_and_the_user_is_told(phase, api, clock, model, outbox):
    fill_week(api, 1)
    clock.current = at("2026-11-16")
    await phase.sync()
    bad = verdict("2026-W46")
    del bad["direction"]
    model.script(reply_json(bad))

    await phase.run_due_jobs()

    assert model.requests[-1].task_skills == ("weekly-decision",)  # no report was written
    assert "failed" in reports(outbox)[-1] and "/checkin" in reports(outbox)[-1]
    assert weekly_checkin.stored(phase, "2026-W46") is None

    model.script(reply("not even JSON"))  # /checkin tries again, still nothing stored
    await phase.on_message("/checkin")
    assert weekly_checkin.stored(phase, "2026-W46") is None

    model.script(reply_json(verdict("2026-W46", scenario="glycogen_window")), reply_json(message("Report.")))
    await phase.on_message("/checkin")
    assert weekly_checkin.stored(phase, "2026-W46") is not None and reports(outbox)[-1] == "Report."


# --- skipped weeks ---------------------------------------------------------------------


async def test_skipped_weeks_neither_count_nor_break_confirmation(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    fill_week(api, 4, kcal=2600)  # 18200 vs 16700-ish: adherence gate fails
    await check_in(phase, clock, model, "2026-12-07",
                   verdict("2026-W49", scenario="adherence_gate", adherence="fail", direction="increase"))
    fill_week(api, 5, weigh_ins=3)  # too few weigh-ins: unusable
    await check_in(phase, clock, model, "2026-12-14", verdict("2026-W50", scenario="unusable", usable=False))
    fill_week(api, 6, avg=82.25)
    await check_in(phase, clock, model, "2026-12-21", verdict("2026-W51", scenario="C", direction="increase"))

    week4, week5, week6 = (r.input for r in decision_requests(model)[-3:])
    assert week4["intake"]["adherence_ok"] is False
    assert week5["data_quality"]["code_unusable_reasons"] == ["too_few_weigh_ins"]
    history = week6["history"]
    assert [(v["iso_week"], v["counts_for_confirmation"], v["skip_reason"]) for v in history["previous_verdicts"]] == [
        ("2026-W50", False, "unusable"), ("2026-W49", False, "adherence_gate"), ("2026-W48", True, None),
        ("2026-W47", False, "glycogen_window"), ("2026-W46", False, "glycogen_window")]
    assert history["confirmation_streaks"] == {"increase": 1, "decrease": 0}
    assert history["weeks_since_last_change"] == 2


async def test_a_sport_load_week_is_skipped_and_gives_no_increase_or_training_call(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    clock.current = at("2026-11-30", 12)
    model.script(tool_call("add_context_note", applies_from="2026-11-30", applies_to="2026-12-06",
                           tags=["sport_load"], suggest_unusable="no"), reply("Noted: camp week."))
    await phase.on_message("wrestling camp all week")
    fill_week(api, 4)
    proposal = {"type": "calorie_change", "delta_kcal": 100, "size": "small", "reason": "not gaining",
                "is_phase_first_change": False, "returning_rejected_proposal_id": None}
    looks = {"code": "training_needs_look", "severity": "watch", "detail": "stalls", "exercise_id": None}
    await check_in(phase, clock, model, "2026-12-07",
                   verdict("2026-W49", scenario="C", direction="increase", proposal=proposal, flags=[looks]))

    facts = decision_requests(model)[-1].input
    assert facts["activity"]["sport_load_high"] is True and facts["data_quality"]["code_usable"] is True
    assert [n["tags"] for n in facts["context_notes"]] == [["sport_load"]]
    stored = weekly_checkin.stored(phase, "2026-W49")
    v = stored["verdict"]
    assert v["direction"] == "hold" and v["proposal"] is None and v["sport_load_applied"] is True
    assert [f["code"] for f in v["flags"]] == ["sport_load_week"]
    assert "WD-SPORT" in v["rules_applied"]
    assert (stored["counts_for_confirmation"], stored["skip_reason"]) == (False, "sport_load")
    assert model.requests[-1].input["verdict"] == v  # the report gets the stored verdict

    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", verdict("2026-W50", scenario="C", direction="increase"))
    history = decision_requests(model)[-1].input["history"]
    assert history["confirmation_streaks"] == {"increase": 1, "decrease": 0}  # W48 still counts


# --- report inputs ---------------------------------------------------------------------


async def test_the_weeks_deferred_items_and_due_measurements_go_into_the_report(phase, api, clock, model):
    fill_week(api, 1)
    fill_week(api, 2)
    messaging.defer(phase, datetime.date(2026, 11, 12), "Protein was low on Thursday.", "evening-recap",
                    at("2026-11-12", 21))
    await check_in(phase, clock, model, "2026-11-16", verdict("2026-W46", scenario="glycogen_window"))

    report = model.requests[-1].input
    assert report["deferred"] == [{"date": "2026-11-12", "text": "Protein was low on Thursday."}]
    assert report["due"] == []  # the coming week, 16-22 Nov: nothing due

    await check_in(phase, clock, model, "2026-11-23", verdict("2026-W47", scenario="glycogen_window"))
    report = model.requests[-1].input
    assert report["deferred"] == []  # only the week's own items
    # Waist every 2 weeks after the start, photos at the start and every 2 weeks: both on 23 Nov.
    assert report["due"] == [{"date": "2026-11-23", "kind": "waist"}, {"date": "2026-11-23", "kind": "photos"}]


async def test_the_first_check_in_waits_for_a_full_phase_week(phase, api, clock, model, outbox):
    clock.current = at("2026-11-15", 18)
    await phase.run_due_jobs()  # moment Mon 9 Nov 09:00 was before the phase started
    assert reports(outbox) == [] and model.requests[-1].task_skills == ("phase-start",)


async def test_an_item_the_evening_recap_held_back_appears_in_the_next_weekly_report(phase, api, clock, model):
    fill_week(api, 1)
    clock.current = at("2026-11-12", 21)
    model.script(reply_json({"send": False, "text": "", "buttons": [],
                             "deferred_to_weekly": ["Fiber was low on Thursday."]}))
    await phase.run_due_jobs()  # the evening recap, silent
    assert model.requests[-1].task_skills == ("evening-recap",)

    await check_in(phase, clock, model, "2026-11-16", verdict("2026-W46", scenario="glycogen_window"))

    assert model.requests[-1].input["deferred"] == [{"date": "2026-11-12", "text": "Fiber was low on Thursday."}]


async def test_the_daily_message_limit_never_holds_the_report_back(phase, api, clock, model, outbox):
    fill_week(api, 1)
    for n in range(2):  # the setup's limit: 2 unprompted messages a day
        assert messaging.send(phase, f"note {n}", at("2026-11-16", 8), kind="test")
    assert not messaging.can_send(phase, at("2026-11-16", 8))

    await check_in(phase, clock, model, "2026-11-16", verdict("2026-W46", scenario="glycogen_window"),
                   report="Week 1 report.")

    assert reports(outbox) == ["Week 1 report."]
