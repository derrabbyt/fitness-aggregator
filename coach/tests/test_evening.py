"""Evening reminder and recap (ticket 11), driven through the Coach seam.

The phase is the worked example of test_phase_start: reverse started Mon
9 Nov 2026, evening reminder at 20:30, at most 2 unprompted messages a day.
Week 1 daily targets: rest day 2300 kcal, lifting day (Hevy session) 2600,
Friday wrestling 2900. Macros at 80.5 kg: protein 161 g, fat 72 g. The
glycogen window is phase weeks 1-2 (9-22 Nov).
"""

import datetime

import pytest

from fa_coach import messaging, phases
from fakes import TZ, exercise, food, reply, reply_json, session, tool_call
from test_phase_start import card, start_and_collect

EVENING = datetime.time(20, 30)


def at(day: str, time: datetime.time = EVENING) -> datetime.datetime:
    return datetime.datetime.combine(datetime.date.fromisoformat(day), time, tzinfo=TZ)


def message(text: str = "", *, send: bool = True, deferred: list[str] | None = None) -> dict:
    return {"send": send, "urgent": False, "text": text if send else "", "buttons": [],
            "deferred_to_weekly": deferred or []}


def log(api, day: str, kcal: float = 2300, *, protein_g: float = 161, fat_g: float = 72,
        weight_kg: float | None = 80.6, steps: int | None = 9000) -> None:  # 9,000: the average, no step kcal
    api.days[day] = {"food": food(kcal, protein_g=protein_g, fat_g=fat_g), "weight_kg": weight_kg, "steps": steps}


@pytest.fixture
async def reverse(coach, api, model, outbox):
    """Four diet weeks of history, then the reverse confirmed on Mon 9 Nov."""
    day = datetime.date(2026, 10, 12)
    for week_avg in (82.0, 81.5, 81.0, 80.5):
        for _ in range(7):
            api.days[day.isoformat()] = {"food": food(2000), "weight_kg": week_avg, "steps": 9000}
            day += datetime.timedelta(days=1)
    api.sessions = [session("w1", "2026-11-09", exercise("Bench Press", (80, 5)),
                            exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps"))]
    await coach.sync()
    await start_and_collect(coach, model)
    confirm = card(outbox).buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)
    assert phases.active(coach)["start_date"] == "2026-11-09"
    await coach.run_due_jobs(at("2026-11-09", datetime.time(9, 5)))  # the baseline photo reminder goes out
    outbox.clear()
    model.requests.clear()
    return coach


def recap_facts(coach, model):
    requests = [r for r in model.requests if r.task_skills == ("evening-recap",)]
    assert len(requests) == 1, "expected one evening-recap call"
    facts = requests[0].input
    assert coach.skills.errors(facts, "daily_facts") == []
    assert requests[0].output_schema == "coach_message"
    return facts


# --- missing-log reminder ------------------------------------------------------------


async def test_missing_log_reminder_names_what_is_missing_once_a_day_without_the_model(reverse, api, model, outbox):
    coach = reverse
    log(api, "2026-11-10", weight_kg=None, steps=None)  # food logged, weight and steps not

    await coach.run_due_jobs(at("2026-11-10", datetime.time(20, 29)))
    assert outbox.items == []  # not yet

    await coach.run_due_jobs(at("2026-11-10"))
    assert len(outbox.texts) == 1
    text = outbox.texts[0].lower()
    assert "weight" in text and "steps" in text and "food" not in text
    assert model.requests == []

    log(api, "2026-11-10")  # logged later the same evening: no recap, no second reminder
    await coach.run_due_jobs(at("2026-11-10", datetime.time(21, 30)))
    await coach.run_due_jobs(at("2026-11-10", datetime.time(23, 59)))
    assert len(outbox.texts) == 1 and model.requests == []


async def test_an_unlogged_day_gets_a_reminder_that_names_food(reverse, api, model, outbox):
    api.days["2026-11-10"] = {"weight_kg": 80.6}

    await reverse.run_due_jobs(at("2026-11-10"))

    text = outbox.texts[0].lower()
    assert "food" in text and "steps" in text and "weight" not in text


async def test_the_evening_syncs_before_deciding_so_a_late_log_counts(reverse, api, model, outbox):
    log(api, "2026-11-10")  # logged after the last scheduled sync; the job syncs itself
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-10"))

    assert outbox.items == []
    assert recap_facts(reverse, model)["day"]["intake"]["actual_kcal"] == 2300


async def test_nothing_runs_without_an_active_phase(coach, api, model, outbox):
    api.days["2026-11-10"] = {}

    await coach.run_due_jobs(at("2026-11-10"))

    assert outbox.items == [] and model.requests == []


# --- recap -------------------------------------------------------------------------


async def test_a_silent_evening_stores_its_deferred_item_for_that_week(reverse, api, model, outbox):
    coach = reverse
    log(api, "2026-11-09", 2600)  # Monday: Bench + Pull-up session in Hevy -> lifting day
    log(api, "2026-11-10", 2300, protein_g=120)
    model.script(reply_json(message(send=False, deferred=["Protein was 120 g on Tuesday vs 161 g."])))

    await coach.run_due_jobs(at("2026-11-10"))

    assert outbox.items == []
    facts = recap_facts(coach, model)
    assert facts["kind"] == "evening" and facts["date"] == "2026-11-10"
    assert facts["phase_week"] == 1 and facts["in_glycogen_window"] is True
    assert facts["messages_sent_today"] == 0
    day = facts["day"]
    assert day["intake"]["target_kcal"] == 2300 and day["intake"]["actual_kcal"] == 2300
    build = day["target_build_up"]
    assert (build["day_steps"], build["step_goal"], build["steps_tracked"]) == (9000, 10000, True)
    assert build["target_kcal"] == 2300
    assert build["step_kcal"] in (-34, -35)  # 1,000 below the goal, at the average: base at goal is 2570.5
    assert day["intake"]["logged"] == "complete"
    assert day["intake"]["protein_g"] == 120
    assert day["macro_targets"]["protein_g"] == 161 and day["macro_targets"]["fat_g"] == 72
    assert day["vs_target"]["protein_pct"] == 74.5  # 120 / 161
    week = day["week_to_date"]
    assert week["days_elapsed"] == 2 and week["days_logged"] == 2
    assert week["target_kcal_so_far"] == 2600 + 2300 and week["actual_kcal_so_far"] == 2600 + 2300
    assert week["deviation_pct"] == 0
    assert facts["params"]["messaging"]["max_unprompted_messages_per_day"] == 2

    items = messaging.deferred(coach, datetime.date(2026, 11, 9), datetime.date(2026, 11, 15))
    assert items == [{"day": "2026-11-10", "source": "evening-recap",
                      "text": "Protein was 120 g on Tuesday vs 161 g."}]
    assert messaging.deferred(coach, datetime.date(2026, 11, 16), datetime.date(2026, 11, 22)) == []

    await coach.run_due_jobs(at("2026-11-10", datetime.time(22, 0)))  # once per evening
    assert len(model.requests) == 1


async def test_an_off_target_week_gets_a_note(reverse, api, model, outbox):
    coach = reverse
    for day in ("2026-11-09", "2026-11-10", "2026-11-11"):
        log(api, day, 2700)
    note = "Week so far: 8100 kcal vs 7200 target (+12.5%)."
    model.script(reply_json(message(note)))

    await coach.run_due_jobs(at("2026-11-11"))

    assert outbox.texts == [note]
    week = recap_facts(coach, model)["day"]["week_to_date"]
    assert week["target_kcal_so_far"] == 2600 + 2300 + 2300
    assert week["actual_kcal_so_far"] == 8100
    assert week["deviation_pct"] == 12.5  # (8100 - 7200) / 7200


async def test_the_week_so_far_counts_only_logged_days(reverse, api, model):
    api.days["2026-11-09"] = {"weight_kg": 80.6}  # Monday not logged
    log(api, "2026-11-10", 2000)
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-10"))

    week = recap_facts(reverse, model)["day"]["week_to_date"]
    assert week["days_elapsed"] == 2 and week["days_logged"] == 1
    assert week["target_kcal_so_far"] == 2300 and week["actual_kcal_so_far"] == 2000
    assert week["deviation_pct"] == -13.0


async def test_an_implausible_day_gets_codes_question_and_no_recap(reverse, api, model, outbox):
    # Ticket 20: code asks (Real / Typo) with buttons; test_day_confirmation covers the answers.
    log(api, "2026-11-10", 12000)

    await reverse.run_due_jobs(at("2026-11-10"))

    [card] = outbox.sent
    assert "12,000" in card.text and card.buttons
    assert model.requests == []


async def test_a_confirmed_implausible_day_is_flagged_in_the_recap(reverse, api, model, outbox):
    log(api, "2026-11-10", 12000)
    await reverse.sync(at("2026-11-10", datetime.time(19)))
    model.script(tool_call("confirm_day", date="2026-11-10", kind="real"), reply("Noted."))
    await reverse.on_message("today's 12,000 is real, birthday", at("2026-11-10", datetime.time(19)))
    model.requests.clear()
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-10"))

    day = recap_facts(reverse, model)["day"]
    assert day["checks"]["implausible_intake"] is True
    assert day["intake"]["confirmed"] is True and day["intake"]["logged"] == "complete"


async def test_a_normal_day_is_not_flagged_implausible(reverse, api, model):
    log(api, "2026-11-10", 3000)
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-10"))

    assert recap_facts(reverse, model)["day"]["checks"]["implausible_intake"] is False


async def test_an_invalid_recap_sends_nothing(reverse, api, model, outbox):
    log(api, "2026-11-10")
    model.script(reply_json({"send": True, "text": "missing fields"}))

    await reverse.run_due_jobs(at("2026-11-10"))

    assert outbox.items == []


# --- glycogen window ---------------------------------------------------------------


async def test_weight_is_withheld_from_the_recap_in_the_glycogen_window(reverse, api, model):
    log(api, "2026-11-10", weight_kg=81.9)
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-10"))

    weight = recap_facts(reverse, model)["day"]["weight"]
    assert weight == {"kg": None, "avg_7d_kg": None, "outlier": False, "withheld": True}


async def test_weight_is_shown_after_the_glycogen_window(reverse, api, model):
    for n in range(23, 26):
        log(api, f"2026-11-{n}", weight_kg=81.0)
    model.script(reply_json(message(send=False)))

    await reverse.run_due_jobs(at("2026-11-25"))

    facts = recap_facts(reverse, model)
    assert facts["phase_week"] == 3 and facts["in_glycogen_window"] is False
    assert facts["day"]["weight"] == {"kg": 81.0, "avg_7d_kg": 81.0, "outlier": False, "withheld": False}


# --- daily message limit -----------------------------------------------------------


async def test_the_daily_limit_holds_back_the_reminder_and_the_recap(reverse, api, model, outbox):
    coach = reverse
    morning = at("2026-11-10", datetime.time(8, 0))
    assert messaging.limit(coach) == 2
    assert messaging.send(coach, "one", morning, kind="test")
    assert messaging.send(coach, "reset?", morning, kind="test", exempt=True)  # doesn't count
    assert messaging.send(coach, "two", morning, kind="test")
    assert not messaging.send(coach, "three", morning, kind="test")
    assert outbox.texts == ["one", "reset?", "two"]
    assert messaging.sent_today(coach, morning) == 2
    outbox.clear()

    api.days["2026-11-10"] = {"weight_kg": 80.6}  # nothing logged: a reminder would be due
    await coach.run_due_jobs(at("2026-11-10"))
    assert outbox.items == []  # held back for the weekly report
    held = messaging.deferred(coach, datetime.date(2026, 11, 10), datetime.date(2026, 11, 10))
    assert [(i["source"], i["text"]) for i in held] == [
        ("evening-reminder", "Evening check: today's food and steps are not in MyFitnessPal yet.")]

    # Next day the limit starts over; a recap the model wants to send past the
    # limit is held back for the weekly report instead.
    assert messaging.send(coach, "a", at("2026-11-11", datetime.time(8)), kind="test")
    assert messaging.send(coach, "b", at("2026-11-11", datetime.time(9)), kind="test")
    outbox.clear()
    log(api, "2026-11-11", 2900)
    model.script(reply_json(message("Week so far is well over target.")))
    await coach.run_due_jobs(at("2026-11-11"))

    assert outbox.items == []
    assert recap_facts(coach, model)["messages_sent_today"] == 2
    texts = [i["text"] for i in messaging.deferred(coach, datetime.date(2026, 11, 11), datetime.date(2026, 11, 11))]
    assert texts == ["Week so far is well over target."]


async def test_the_reminder_counts_toward_the_limit(reverse, api, outbox):
    api.days["2026-11-10"] = {"weight_kg": 80.6}

    await reverse.run_due_jobs(at("2026-11-10"))

    assert len(outbox.texts) == 1
    assert messaging.sent_today(reverse, at("2026-11-10")) == 1
