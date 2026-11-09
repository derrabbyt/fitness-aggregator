"""Context in any form becomes a stored context note: the user's words
unchanged, dates, tags, optional exercise id and `suggest_unusable`; the
reply confirms it in one line."""

import datetime

from fa_coach.features import context_notes
from fakes import reply, tool_call

TUESDAY = datetime.date(2026, 11, 3)
TODAY = datetime.date(2026, 11, 9)  # the fake clock's Monday


async def test_context_is_stored_in_the_users_words_and_confirmed(coach, model, outbox):
    message = "Sick since Tuesday, feeling rough"
    model.script(
        tool_call(
            "add_context_note",
            applies_from="2026-11-03",
            applies_to=None,
            tags=["illness"],
            suggest_unusable="yes",
        ),
        reply("Noted: sick since Tue 3 Nov; last week may not count for decisions."),
    )

    await coach.on_message(message)

    [note] = context_notes.between(coach, TUESDAY, TODAY)
    assert note["text"] == message
    assert note["applies_from"] == "2026-11-03"
    assert note["applies_to"] is None
    assert note["tags"] == ["illness"]
    assert note["suggest_unusable"] == "yes"
    assert coach.skills.errors(note, "context_note") == []
    assert model.results(0)[0].content["id"] == note["id"]
    assert outbox.texts == ["Noted: sick since Tue 3 Nov; last week may not count for decisions."]


async def test_a_heavy_week_is_a_sport_load_note(coach, model):
    model.script(
        tool_call(
            "add_context_note",
            applies_from="2026-11-16",
            applies_to="2026-11-22",
            tags=["sport_load", "travel"],
            suggest_unusable="maybe",
        ),
        reply("Noted: wrestling camp 16–22 Nov, tagged as a heavy week."),
    )

    await coach.on_message("wrestling camp next week, training twice a day")

    [note] = context_notes.between(coach, datetime.date(2026, 11, 20), datetime.date(2026, 11, 20))
    assert note["tags"] == ["sport_load", "travel"]
    assert note["applies_to"] == "2026-11-22"


async def test_an_exercise_note_keeps_its_exercise_id(coach, model):
    model.script(
        tool_call(
            "add_context_note",
            applies_from="2026-11-09",
            tags=["pain"],
            exercise_id="D04AC939",
            suggest_unusable="no",
            follow_up_question="Should I pause tracking for squats?",
        ),
        reply("Noted: knee pain on squats today. Should I pause tracking for squats?"),
    )

    await coach.on_message("knee hurt on squats today")

    [note] = context_notes.between(coach, TODAY, TODAY)
    assert note["exercise_id"] == "D04AC939"
    assert note["follow_up_question"] == "Should I pause tracking for squats?"


async def test_notes_are_found_by_the_dates_they_apply_to(coach, model):
    model.script(
        tool_call("add_context_note", applies_from="2026-11-02", applies_to="2026-11-04", tags=["travel"], suggest_unusable="yes"),
        reply("Noted."),
        tool_call("add_context_note", applies_from="2026-10-01", applies_to=None, tags=["supplement_change"], suggest_unusable="no"),
        reply("Noted."),
    )
    await coach.on_message("was in Berlin Mon to Wed last week")
    await coach.on_message("started creatine on 1 October")

    week_before = context_notes.between(coach, datetime.date(2026, 10, 26), datetime.date(2026, 11, 1))
    last_week = context_notes.between(coach, datetime.date(2026, 11, 2), datetime.date(2026, 11, 8))

    # An open-ended note (no applies_to) counts from its start onwards.
    assert [n["tags"] for n in week_before] == [["supplement_change"]]
    assert [n["tags"] for n in last_week] == [["supplement_change"], ["travel"]]


async def test_a_note_ending_before_it_starts_is_refused(coach, model):
    model.script(
        tool_call("add_context_note", applies_from="2026-11-09", applies_to="2026-11-02", tags=["travel"], suggest_unusable="yes"),
        reply("Which dates were you away?"),
    )

    await coach.on_message("travelling")

    assert model.results(0)[0].is_error
    assert context_notes.between(coach, datetime.date(2026, 1, 1), datetime.date(2027, 1, 1)) == []


async def test_the_model_can_read_notes_and_delete_a_wrong_one(coach, model, outbox):
    model.script(
        tool_call("add_context_note", applies_from="2026-11-09", applies_to="2026-11-15", tags=["sport_load"], suggest_unusable="no"),
        reply("Noted: heavy week."),
    )
    await coach.on_message("camp week")
    [note] = context_notes.between(coach, TODAY, TODAY)

    model.script(
        tool_call("get_context_notes", **{"from": "2026-11-09", "to": "2026-11-15"}),
        tool_call("delete_context_note", id=note["id"]),
        reply("Removed the heavy-week note."),
    )
    await coach.on_message("it wasn't actually heavy this week")

    assert [n["id"] for n in model.results(2)[0].content["notes"]] == [note["id"]]
    assert context_notes.between(coach, TODAY, TODAY) == []
    assert outbox.texts[-1] == "Removed the heavy-week note."
