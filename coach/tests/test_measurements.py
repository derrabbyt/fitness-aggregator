"""Waist and photo check-ins (spec, "Measurements"): due dates computed by
code from the measurement params and the phase start, one reminder per due
date, photos and waist values stored with their date, photos optional.

Worked example: the reverse starts Mon 9 Nov 2026 with waist and photos every
2 weeks. Photos are due on the start date (the baseline set) and then on
23 Nov, 7 Dec, ...; the waist was recorded at the start (setup), so it is due
on 23 Nov, 7 Dec, ..."""

import datetime
import json

from fa_coach import messaging, phases
from fa_coach.features import measurements
from fakes import TZ, reply, tool_call

D = datetime.date
START = "2026-11-09"
SETUP = {
    "phase_id": "reverse_bulk",
    "start_date": START,
    "training_plan_source": "saved_plan",
    "maintenance_includes_activity": True,
    "tracked_lifts": [{"exercise_id": "bench-press", "name": "Bench Press", "bodyweight_exercise": False}],
    "starting_calories_kcal": 2000,
    "starting_trend_weight_kg": 80.5,
    "maintenance_estimate_kcal": 2536,
    "run_kcal_discount": 0.75,
    "wrestling_kcal_per_session": 600,
    "lifting_kcal_per_session": 300,
    "fat_g_per_kg_start": 0.9,
    "week1_increase_kcal": 300,
    "time_goal_weeks": None,
    "photos_enabled": True,
    "waist_cm_start": 84.5,
    "logistics": {"weekly_checkin": "sun 18:00", "evening_reminder_time": "20:30",
                  "max_unprompted_messages_per_day": 2, "soft_floor_min_days": 5},
}


def activate(coach, **changes) -> None:
    """An active reverse phase as a confirmed phase start leaves it."""
    setup = {**SETUP, **changes}
    at = f"{setup['start_date']}T09:00:00+01:00"
    coach.db.execute("INSERT INTO phase_setups (id, phase_id, status, created_at, updated_at) VALUES"
                     " ('s1', 'reverse_bulk', 'confirmed', ?, ?)", (at, at))
    coach.db.execute("INSERT INTO phases (id, phase_id, setup_id, status, start_date, setup, started_at) VALUES"
                     " ('p1', 'reverse_bulk', 's1', 'active', ?, ?, ?)", (setup["start_date"], json.dumps(setup), at))


def at(day: str, hour: int = 9, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(D.fromisoformat(day), datetime.time(hour, minute), tzinfo=TZ)


# --- due dates -------------------------------------------------------------------


def test_nothing_is_due_without_an_active_phase(coach):
    assert measurements.measurements_due(coach, D(2026, 11, 1), D(2026, 12, 31)) == []


def test_due_dates_follow_the_phase_start_and_the_measurement_params(coach):
    activate(coach)

    due = measurements.measurements_due(coach, D(2026, 11, 9), D(2026, 12, 7))

    assert due == [
        {"date": "2026-11-09", "kind": "photos"},
        {"date": "2026-11-23", "kind": "waist"},
        {"date": "2026-11-23", "kind": "photos"},
        {"date": "2026-12-07", "kind": "waist"},
        {"date": "2026-12-07", "kind": "photos"},
    ]


def test_a_week_window_gives_what_is_due_in_that_week(coach):
    activate(coach)

    assert measurements.measurements_due(coach, D(2026, 11, 16), D(2026, 11, 22)) == []
    assert measurements.measurements_due(coach, D(2026, 11, 23), D(2026, 11, 29)) == [
        {"date": "2026-11-23", "kind": "waist"}, {"date": "2026-11-23", "kind": "photos"}]


# --- reminders -------------------------------------------------------------------

PROTOCOL = ("same spot", "same light", "hip height", "morning", "fasted", "unpumped", "same poses")


def reminders(outbox) -> list[str]:
    return [t for t in outbox.texts if "waist" in t.lower() or "photo" in t.lower()]


async def test_the_reminder_is_sent_once_when_due(coach, make_coach, outbox):
    activate(coach)
    await coach.run_due_jobs(at("2026-11-09", 9))
    outbox.clear()

    await coach.run_due_jobs(at("2026-11-22", 20))
    await coach.run_due_jobs(at("2026-11-23", 6, 59))
    assert reminders(outbox) == []

    await coach.run_due_jobs(at("2026-11-23", 7))
    await coach.run_due_jobs(at("2026-11-23", 7, 1))
    await make_coach().run_due_jobs(at("2026-11-24", 7))  # after a restart, the next day

    [text] = reminders(outbox)
    assert "waist" in text.lower() and "photo" in text.lower()
    for words in PROTOCOL:
        assert words in text.lower(), words


async def test_the_baseline_photo_set_is_asked_for_on_the_start_date_without_the_waist(coach, outbox):
    activate(coach)

    await coach.run_due_jobs(at("2026-11-09", 9))

    [text] = reminders(outbox)
    assert "photo" in text.lower() and "waist" not in text.lower()
    for words in PROTOCOL:
        assert words in text.lower(), words


async def test_a_missed_due_date_is_reminded_late_but_only_for_the_current_period(coach, outbox):
    activate(coach)

    await coach.run_due_jobs(at("2026-11-26", 12))  # the coach was down on 23 Nov

    [text] = reminders(outbox)
    assert "waist" in text.lower() and "photo" in text.lower()


async def test_reminders_count_toward_the_daily_message_limit(coach, outbox):
    activate(coach)  # at most 2 unprompted messages a day
    await coach.run_due_jobs(at("2026-11-09", 9))  # the baseline photo reminder
    assert messaging.sent_today(coach, at("2026-11-09", 9)) == 1
    outbox.clear()

    early = at("2026-11-23", 6)
    assert messaging.send(coach, "one", early, kind="test") and messaging.send(coach, "two", early, kind="test")
    outbox.clear()
    await coach.run_due_jobs(at("2026-11-23", 7))
    await coach.run_due_jobs(at("2026-11-24", 6, 59))
    assert reminders(outbox) == []  # held back by the limit, not lost

    await coach.run_due_jobs(at("2026-11-24", 7))
    await coach.run_due_jobs(at("2026-11-24", 8))
    [text] = reminders(outbox)
    assert "waist" in text.lower() and "photo" in text.lower()
    assert messaging.sent_today(coach, at("2026-11-24", 8)) == 1


async def test_no_reminder_without_an_active_phase(coach, outbox):
    await coach.run_due_jobs(at("2026-11-23", 7))

    assert outbox.texts == []


# --- storing -----------------------------------------------------------------------


async def test_photos_are_stored_as_a_dated_set_in_the_state_directory(coach, outbox, tmp_path):
    activate(coach)

    await coach.on_photo(b"front", None, at("2026-11-23", 7, 30))
    await coach.on_photo(b"side", "side", at("2026-11-23", 7, 31))
    await coach.on_photo(b"front2", None, at("2026-12-07", 7, 30))

    sets = measurements.photo_sets(coach)
    assert [s["date"] for s in sets] == ["2026-11-23", "2026-12-07"]
    first = sets[0]["photos"]
    assert [(tmp_path / p["path"]).read_bytes() for p in first] == [b"front", b"side"]
    assert all(p["path"].startswith("photos/2026-11-23/") for p in first)
    assert first[1]["caption"] == "side"
    assert len(outbox.texts) == 3
    assert "photo 1 of the 2026-11-23 set" in outbox.texts[0]
    assert "photo 2 of the 2026-11-23 set" in outbox.texts[1]


async def test_photos_are_kept_even_without_an_active_phase(coach, tmp_path):
    await coach.on_photo(b"front", None, at("2026-11-02"))

    [photo_set] = measurements.photo_sets(coach)
    assert (tmp_path / photo_set["photos"][0]["path"]).read_bytes() == b"front"


async def test_a_waist_value_is_stored_with_its_date_and_acknowledged(coach, model, outbox):
    activate(coach)

    await coach.on_message("Waist: 85,2 cm", at("2026-11-23", 8))

    assert measurements.waist_values(coach) == [{"date": "2026-11-23", "cm": 85.2}]
    assert model.requests == []
    [text] = outbox.texts
    assert "85.2" in text and "2026-11-23" in text


async def test_a_waist_in_a_sentence_is_stored_but_a_question_about_it_goes_to_the_chat(coach, model, outbox):
    activate(coach)
    await coach.on_message("measured my waist this morning, 84.5cm", at("2026-11-23", 8))
    model.script(reply("It was 84.5 cm."), reply("Two weeks ago."))

    await coach.on_message("what was my waist 2 weeks ago?", at("2026-11-23", 9))
    await coach.on_message("waist went from 84 to 85", at("2026-11-23", 9))

    assert measurements.waist_values(coach) == [{"date": "2026-11-23", "cm": 84.5}]
    assert len(model.requests) == 2


async def test_a_bare_number_counts_as_the_waist_only_while_a_waist_reminder_is_open(coach, model, outbox):
    activate(coach)
    model.script(reply("What is 84?"))
    await coach.on_message("84", at("2026-11-20", 8))
    assert measurements.waist_values(coach) == []

    await coach.run_due_jobs(at("2026-11-23", 7))
    await coach.on_message("84.5 cm", at("2026-11-23", 7, 30))
    model.script(reply("Okay."))
    await coach.on_message("85", at("2026-11-23", 8))

    assert measurements.waist_values(coach) == [{"date": "2026-11-23", "cm": 84.5}]


async def test_switching_photos_off_in_chat_stops_photo_reminders_and_nothing_else(coach, model, outbox):
    activate(coach)
    before = phases.params(coach)
    model.script(tool_call("record_setup_value", key="photos_enabled", value=False), reply("Photos are off."))

    await coach.on_message("stop asking for photos", at("2026-11-20", 8))

    after = phases.params(coach)
    assert after["measurements"]["photos_enabled"] is False
    after["measurements"]["photos_enabled"] = True
    assert after == before
    assert measurements.measurements_due(coach, D(2026, 11, 23), D(2026, 12, 7)) == [
        {"date": "2026-11-23", "kind": "waist"}, {"date": "2026-12-07", "kind": "waist"}]
    outbox.clear()

    await coach.run_due_jobs(at("2026-11-23", 7))

    [text] = reminders(outbox)
    assert "waist" in text.lower() and "photo" not in text.lower()


async def test_what_arrived_before_the_reminder_is_not_asked_for_again(coach, outbox):
    activate(coach)
    await coach.run_due_jobs(at("2026-11-09", 9))
    await coach.on_message("waist 84", at("2026-11-23", 6, 30))
    await coach.on_photo(b"front", None, at("2026-11-23", 6, 31))
    outbox.clear()

    await coach.run_due_jobs(at("2026-11-23", 7))

    assert reminders(outbox) == []
