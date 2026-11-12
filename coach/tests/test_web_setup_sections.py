"""The web page's remaining Setup sections (coach-web ticket 12): Exercises
(counting or not, paused), Context notes (list, add, delete), Profile (view,
edit) and Measurements (waist values, adding one; photo sets, each photo
served read-only). Edits run the chat tools (`classify_exercises`,
`set_exercise_paused`, `add_context_note`, `delete_context_note`,
`update_coach_profile`) or the chat's waist code, so they are validated the
same way and refused with the same reasons.
"""

import datetime

import pytest

from fa_coach import views
from fakes import TZ, exercise, session
from test_weekly_checkin import phase  # noqa: F401

D = datetime.date


def view(coach, name: str) -> dict:
    data = coach.view(name)
    assert views.errors(coach, name, data) == []
    return data


def at(day: str, hour: int = 9, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(D.fromisoformat(day), datetime.time(hour, minute), tzinfo=TZ)


async def refused(coach, name: str, body: dict) -> tuple[int, str]:
    with pytest.raises(views.WebError) as err:
        await coach.command(name, body)
    return err.value.status, err.value.message


# --- Exercises ------------------------------------------------------------------------------


@pytest.fixture
async def trained(coach, api, clock):
    """Bench and squat twice, a lateral raise once, synced on 26 Nov."""
    api.sessions = [
        session("s1", "2026-11-19", exercise("Bench Press", (100, 8)), exercise("Squat", (120, 6)),
                exercise("Lateral Raise", (10, 12))),
        session("s2", "2026-11-26", exercise("Bench Press", (100, 9)), exercise("Squat", (125, 6))),
    ]
    clock.current = at("2026-11-26", 12)
    await coach.sync()
    return coach


async def test_exercises_lists_every_synced_exercise_alphabetically_as_counting_until_classified(trained):
    ex = view(trained, "setup/exercises")

    assert [(e["exercise_id"], e["title"], e["counts"], e["classified"], e["paused"], e["sessions"], e["last_date"])
            for e in ex["exercises"]] == [
        ("bench-press", "Bench Press", True, False, False, 2, "2026-11-26"),
        ("lateral-raise", "Lateral Raise", True, False, False, 1, "2026-11-19"),
        ("squat", "Squat", True, False, False, 2, "2026-11-26"),
    ]
    assert view(trained, "setup")["exercises"]["summary"] == "3 counting · 0 not counted"


async def test_switching_an_exercise_to_not_counted_and_back_runs_chat_classification(trained):
    result = await trained.command("setup/exercises/classify", {"exercise_id": "lateral-raise",
                                                               "classification": "excluded"})

    assert views.errors(trained, "setup/exercises", result) == []
    raise_ = next(e for e in result["exercises"] if e["exercise_id"] == "lateral-raise")
    assert (raise_["counts"], raise_["classified"]) == (False, True)
    assert view(trained, "setup")["exercises"]["summary"] == "2 counting · 1 not counted"
    # the same store chat's get_tracked_exercises reads
    tracked = await trained.registry.tools["get_tracked_exercises"].fn(trained, {}, trained.clock.now())
    assert {e["exercise_id"]: e["classification"] for e in tracked["exercises"]}["lateral-raise"] == "excluded"

    back = await trained.command("setup/exercises/classify", {"exercise_id": "lateral-raise",
                                                             "classification": "counts"})
    assert next(e for e in back["exercises"] if e["exercise_id"] == "lateral-raise")["counts"] is True


@pytest.mark.parametrize("body, reason", [
    ({"exercise_id": "deadlift", "classification": "excluded"},
     "exercise_id 'deadlift' is not in the synced Hevy history; see get_tracked_exercises"),
    ({"exercise_id": "squat", "classification": "maybe"},
     "exercises/0/classification: 'maybe' is not one of ['counts', 'excluded']"),
    ({"classification": "counts"}, "exercise_id is missing."),
])
async def test_a_bad_classification_is_refused_with_the_chat_reason(trained, body, reason):
    assert await refused(trained, "setup/exercises/classify", body) == (400, reason)
    assert all(e["counts"] and not e["classified"] for e in view(trained, "setup/exercises")["exercises"])


async def test_pausing_an_exercise_runs_chat_pause_and_resuming_clears_it(trained):
    result = await trained.command("setup/exercises/pause", {"exercise_id": "squat", "paused": True,
                                                            "reason": "left knee"})

    squat = next(e for e in result["exercises"] if e["exercise_id"] == "squat")
    assert (squat["paused"], squat["paused_reason"], squat["counts"]) == (True, "left knee", True)
    assert view(trained, "setup")["exercises"]["summary"] == "3 counting · 0 not counted · 1 paused"

    result = await trained.command("setup/exercises/pause", {"exercise_id": "squat", "paused": False})
    squat = next(e for e in result["exercises"] if e["exercise_id"] == "squat")
    assert (squat["paused"], squat["paused_reason"]) == (False, None)


async def test_pausing_an_unknown_exercise_is_refused(trained):
    assert await refused(trained, "setup/exercises/pause", {"exercise_id": "nope", "paused": True}) == (
        400, "exercise_id 'nope' is not in the synced Hevy history; see get_tracked_exercises")
    assert await refused(trained, "setup/exercises/pause", {"exercise_id": "squat", "paused": "yes"}) == (
        400, "paused: 'yes' is not of type 'boolean'")


async def test_without_any_hevy_sessions_the_section_says_so(coach):
    assert view(coach, "setup/exercises")["exercises"] == []
    assert view(coach, "setup")["exercises"]["summary"] == "No exercises synced from Hevy yet"


# --- Context notes ----------------------------------------------------------------------------


async def test_a_note_added_on_the_page_is_stored_like_chat_with_the_users_words(coach, clock):
    clock.current = at("2026-11-12", 8)
    result = await coach.command("setup/context-notes/add", {
        "text": "Camp week, double sessions", "applies_from": "2026-11-16", "applies_to": "2026-11-20",
        "tags": ["sport_load"]})

    assert views.errors(coach, "setup/context-notes", result) == []
    [note] = result["notes"]
    assert {k: note[k] for k in ("text", "applies_from", "applies_to", "tags", "suggest_unusable", "created_at")} == {
        "text": "Camp week, double sessions", "applies_from": "2026-11-16", "applies_to": "2026-11-20",
        "tags": ["sport_load"], "suggest_unusable": "no", "created_at": "2026-11-12T08:00:00+01:00"}
    # the chat's read path sees it
    found = await coach.registry.tools["get_context_notes"].fn(coach, {"from": "2026-11-18", "to": "2026-11-18"},
                                                               clock.now())
    assert [n["id"] for n in found["notes"]] == [note["id"]]
    assert coach.current_message is None
    assert view(coach, "setup")["context_notes"]["summary"] == "1 note · none apply today"


async def test_notes_are_listed_newest_first_and_the_summary_counts_todays(coach, clock):
    clock.current = at("2026-11-12", 8)
    for text, start, end, tags in (("Creatine 5 g", "2026-10-01", None, ["supplement_change"]),
                                   ("Flu", "2026-11-10", "2026-11-13", ["illness"]),
                                   ("Trip to Rome", "2026-11-02", "2026-11-04", ["travel"])):
        await coach.command("setup/context-notes/add", {"text": text, "applies_from": start, "applies_to": end,
                                                        "tags": tags, "suggest_unusable": "maybe"})

    notes = view(coach, "setup/context-notes")
    assert [n["text"] for n in notes["notes"]] == ["Flu", "Trip to Rome", "Creatine 5 g"]
    assert "sport_load" in notes["tag_options"]
    assert view(coach, "setup")["context_notes"]["summary"] == "3 notes · 2 apply today"


@pytest.mark.parametrize("body, reason", [
    ({"text": "Trip", "applies_from": "2026-11-09", "applies_to": "2026-11-02", "tags": ["travel"]},
     "applies_to is before applies_from"),
    ({"text": "Trip", "applies_from": "9 Nov", "tags": ["travel"]}, "applies_from: '9 Nov' is not a 'date'"),
    ({"text": "Trip", "applies_from": "2026-11-09", "tags": ["holiday"]},
     "tags/0: 'holiday' is not one of ['illness', 'travel', 'alcohol', 'salty_or_large_meal', 'supplement_change', "
     "'medication_change', 'sport_load', 'extra_session', 'session_skipped', 'injury', 'pain', 'baseline_reset', "
     "'hunger_high', 'hunger_low', 'energy_low', 'sleep_poor', 'stress', 'digestion', 'other_location', "
     "'logging_issue', 'plan_change', 'goal_change', 'other']"),
    ({"text": "  ", "applies_from": "2026-11-09", "tags": []}, "a context note needs a message from the user"),
    ({"applies_from": "2026-11-09", "tags": []}, "text is missing."),
])
async def test_a_bad_note_is_refused_with_the_chat_reason_and_nothing_stored(coach, body, reason):
    assert await refused(coach, "setup/context-notes/add", body) == (400, reason)
    assert view(coach, "setup/context-notes")["notes"] == []
    assert coach.current_message is None


async def test_deleting_a_note_runs_chat_delete_and_an_unknown_id_is_refused(coach):
    added = await coach.command("setup/context-notes/add", {"text": "Knee hurts", "applies_from": "2026-11-09",
                                                            "tags": ["pain"]})
    note_id = added["notes"][0]["id"]

    result = await coach.command("setup/context-notes/delete", {"id": note_id})

    assert result["notes"] == []
    assert view(coach, "setup")["context_notes"]["summary"] == "No notes yet"
    assert await refused(coach, "setup/context-notes/delete", {"id": note_id}) == (
        400, f"no context note with id {note_id!r}")


# --- Profile ------------------------------------------------------------------------------------


async def test_the_profile_is_edited_through_chats_update_and_shows_in_profile(coach, outbox):
    assert view(coach, "setup")["profile"]["summary"] == "Empty"

    result = await coach.command("setup/profile", {"patch": {"quiet hours": "before 9:00", "units": "kg"}})

    assert views.errors(coach, "setup/profile", result) == []
    assert result["entries"] == [{"key": "quiet hours", "value": "before 9:00"}, {"key": "units", "value": "kg"}]
    assert (result["max_key"], result["max_value"], result["max_entries"]) == (40, 200, 30)
    assert view(coach, "setup")["profile"]["summary"] == "2 entries: quiet hours, units"

    result = await coach.command("setup/profile", {"patch": {"quiet hours": None, "units": "lb"}})
    assert result["entries"] == [{"key": "units", "value": "lb"}]
    await coach.on_message("/profile")
    assert outbox.texts == ["Your coach profile:\n- units: lb"]


@pytest.mark.parametrize("patch, reason", [
    ({"knee": "x" * 201}, "profile values are 1–200 characters; keep it short"),
    ({"k" * 41: "fine"}, "profile keys are 1–40 characters"),
    ({}, "patch: {} should be non-empty"),
])
async def test_a_bad_profile_edit_is_refused_with_the_chat_reason(coach, patch, reason):
    assert await refused(coach, "setup/profile", {"patch": patch}) == (400, reason)
    assert view(coach, "setup/profile")["entries"] == []


# --- Measurements -------------------------------------------------------------------------------
# The phase of test_weekly_checkin starts Mon 9 Nov 2026 with waist 84.5 cm; waist every 2 weeks,
# photos every 2 weeks (on), so both are due on 23 Nov.


async def test_measurements_show_the_start_waist_the_values_and_whats_due(phase, clock):
    clock.current = at("2026-11-12", 8)
    m = view(phase, "setup/measurements")

    assert m["waist"]["start"] == {"date": "2026-11-09", "cm": 84.5}
    assert (m["waist"]["values"], m["waist"]["next_due"], m["waist"]["min"], m["waist"]["max"]) == (
        [], "2026-11-23", 40, 200)
    assert (m["photos"]["enabled"], m["photos"]["next_due"], m["photos"]["sets"]) == (True, "2026-11-23", [])
    assert view(phase, "setup")["measurements"]["summary"] == "Waist 84.5 cm at the start · no photo sets"


async def test_a_waist_value_added_on_the_page_is_stored_like_one_sent_in_chat(phase, clock, outbox):
    clock.current = at("2026-11-23", 8)
    await phase.on_message("waist 83.5")
    result = await phase.command("setup/measurements/waist", {"cm": 83, "date": "2026-11-22"})

    assert views.errors(phase, "setup/measurements", result) == []
    assert result["waist"]["values"] == [{"date": "2026-11-23", "cm": 83.5}, {"date": "2026-11-22", "cm": 83.0}]
    assert result["waist"]["next_due"] == "2026-12-07"
    assert view(phase, "setup")["measurements"]["summary"] == "Waist 83.5 cm on 23 Nov · no photo sets"
    assert outbox.texts == ["📏 Saved: waist 83.5 cm on 2026-11-23."]  # the page says nothing in Telegram


@pytest.mark.parametrize("body, reason", [
    ({"cm": 12}, "12 cm doesn't look like a waist measurement (40–200 cm)."),
    ({"cm": "84"}, "cm: '84' is not a number."),
    ({"cm": 84, "date": "2026-11-24"}, "That day hasn't started yet."),
    ({"cm": 84, "date": "soon"}, "'soon' is not a date (YYYY-MM-DD)."),
    ({}, "cm is missing."),
])
async def test_a_bad_waist_value_is_refused_and_nothing_stored(phase, clock, body, reason):
    clock.current = at("2026-11-23", 8)
    assert await refused(phase, "setup/measurements/waist", body) == (400, reason)
    assert view(phase, "setup/measurements")["waist"]["values"] == []


async def test_photo_sets_are_listed_newest_first_and_each_photo_is_served_read_only(coach):
    await coach.on_photo(b"front", None, at("2026-11-09", 7, 30))
    await coach.on_photo(b"side", "side", at("2026-11-23", 7, 30))
    await coach.on_photo(b"back", None, at("2026-11-23", 7, 31))

    m = view(coach, "setup/measurements")

    assert m["photos"]["enabled"] is None and m["waist"]["start"] is None  # no phase
    assert [(s["date"], [(p["number"], p["url"], p["caption"]) for p in s["photos"]]) for s in m["photos"]["sets"]] == [
        ("2026-11-23", [(1, "photos/2026-11-23/1", "side"), (2, "photos/2026-11-23/2", None)]),
        ("2026-11-09", [(1, "photos/2026-11-09/1", None)]),
    ]
    assert view(coach, "setup")["measurements"]["summary"] == "No waist values · 2 photo sets, latest 23 Nov"
    assert coach.photo("2026-11-23", 2) == b"back"
    assert coach.photo("2026-11-09", 1) == b"front"
    for day, number in (("2026-11-23", 3), ("2026-11-10", 1), ("../../coach.db", 1), ("2026-11-23", 0)):
        with pytest.raises(views.WebError) as err:
            coach.photo(day, number)
        assert (err.value.status, err.value.message) == (404, "There is no such photo.")
