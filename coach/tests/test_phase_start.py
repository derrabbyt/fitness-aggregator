"""Phase start: "start reverse" collects the setup values (prefilled from the
synced history where code can read them), `start_phase` returns a week-1
preview computed by code, and nothing is active until the user taps confirm.

Worked example used below (clock: Mon 9 Nov 2026): four fully logged diet
weeks (12 Oct - 8 Nov) at 2000 kcal, weekly weight averages 82.0, 81.5,
81.0, 80.5 kg. Maintenance = 2000 + 1.5 kg x 7500 / 21 days = 2536 kcal.
The seeded plan has wrestling on Fridays, but those 28 days are before the
phase start, where planned wrestling doesn't count: no counted activity, so
base maintenance = 2536. Week 1 = 2000 + 300 = 2300 kcal on average, i.e.
surplus = -236 kcal: rest day 2300 (the MFP goal), lifting day (+300) 2600,
wrestling day (+600) 2900. Macros at 80.5 kg: protein 161 g, fat 72 g,
carbs (2300 - 644 - 652.05) / 4 = 251 g."""

import datetime
import shutil

import pytest

from fa_coach import phases
from fa_coach.skills import DEFAULT_ROOT, SkillsPackage
from fakes import exercise, food, reply, run, session, tool_call, tool_calls

SETUP = {
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
    "logistics.weekly_checkin": "sun 18:00",
    "logistics.evening_reminder_time": "20:30",
    "logistics.max_unprompted_messages_per_day": 2,
    "logistics.soft_floor_min_days": 5,
}
CLASSES = [{"exercise_id": "bench-press", "classification": "counts", "reason": "main compound"},
           {"exercise_id": "pull-up", "classification": "counts", "reason": "main compound"}]


@pytest.fixture
async def diet_history(coach, api):
    day = datetime.date(2026, 10, 12)
    for week_avg in (82.0, 81.5, 81.0, 80.5):
        for _ in range(7):
            api.days[day.isoformat()] = {"food": food(2000), "weight_kg": week_avg, "steps": 9000}
            day += datetime.timedelta(days=1)
    api.days["2026-11-09"] = {"weight_kg": 80.5}
    api.sessions = [session("w1", "2026-11-09", exercise("Bench Press", (80, 5)),
                            exercise("Pull Up", (None, 8), exercise_type="bodyweight_reps"))]
    await coach.sync()
    return coach


def recorded_ok(model, start: int) -> None:
    """No tool call since model request `start` came back as an error."""
    errors = [r.content for request in model.requests[start:] for _, results in request.steps[-1:]
              for r in results if r.is_error]
    assert errors == []


async def start_and_collect(coach, model) -> None:
    """'start reverse', then one reply that records every value and asks for the preview."""
    model.script(reply("Here is what I read from your history. Confirm?"))
    await coach.on_message("start reverse")
    start = len(model.requests)
    calls = [("classify_exercises", {"exercises": CLASSES})]
    calls += [("record_setup_value", {"key": k, "value": v}) for k, v in SETUP.items()]
    model.script(tool_calls(*calls), tool_call("start_phase"), reply("Preview below."))
    await coach.on_message("yes, all as you said; bench and pull-ups; 0.75, 600, 300, 0.9, +300, no time goal")
    recorded_ok(model, start)


def card(outbox):
    cards = [m for m in outbox.sent if m.buttons]
    assert cards, "no preview card sent"
    return cards[-1]


# --- refusal and prefill ------------------------------------------------------


async def test_a_draft_phase_with_open_values_is_refused_listing_them(make_coach, model, outbox, tmp_path):
    # Every shipped phase is decided now; a copy of the package with the cut back as a draft.
    root = tmp_path / "coach-skills"
    shutil.copytree(DEFAULT_ROOT, root)
    params = root / "skills" / "phase-cut" / "params.yaml"
    text = params.read_text().replace("draft: false", "draft: true").replace(
        "weight_lower_limit_kg_per_week: null", "weight_lower_limit_kg_per_week: null  # TO DECIDE")
    params.write_text(text)
    coach = make_coach(skills=SkillsPackage(root))

    await coach.on_message("start cut")

    assert model.requests == []
    assert len(outbox.texts) == 1
    text = outbox.texts[0]
    assert "draft" in text.lower()
    assert "weight_lower_limit_kg_per_week" in text
    assert phases.active(coach) is None


async def test_start_reverse_loads_phase_start_with_the_reverse_skill_and_prefills_from_history(
        diet_history, model, outbox):
    model.script(reply("I read these from your history: ..."))

    await diet_history.on_message("start reverse")

    request = model.requests[0]
    assert request.prefix_skills == ("coach-core", "phase-reverse-bulk")
    assert request.task_skills == ("phase-start",)
    setup = request.input["setup"]
    assert setup["phase_id"] == "reverse_bulk"
    prefill = setup["prefill"]
    assert prefill["starting_calories_kcal"]["value"] == 2000
    assert prefill["starting_trend_weight_kg"]["value"] == 80.5
    assert prefill["maintenance_estimate_kcal"]["value"] == 2536
    assert {(o["exercise_id"], o["classification"]) for o in setup["exercises"]} == {("bench-press", None), ("pull-up", None)}
    assert "exercise_classification" in setup["still_needed"] and "lifting_kcal_per_session" in setup["still_needed"]
    assert setup["limits"]["fat_g_per_kg_start"] == [0.8, 1.0]
    assert setup["limits"]["week1_increase_kcal"] == [300, 400]
    assert outbox.texts == ["I read these from your history: ..."]


async def test_short_history_prefills_nothing_it_cannot_read(coach, api, model):
    api.days["2026-11-07"] = {"food": food(2000), "weight_kg": 80.0}
    await coach.sync()
    model.script(reply("I need a few numbers from you."))

    await coach.on_message("start reverse")

    prefill = model.requests[0].input["setup"]["prefill"]
    for key in ("starting_calories_kcal", "starting_trend_weight_kg", "maintenance_estimate_kcal"):
        assert prefill[key]["value"] is None
        assert prefill[key]["missing"]  # says why, so the coach asks instead of guessing


# --- recording values ----------------------------------------------------------


async def test_setup_values_are_validated_against_params_and_schema(diet_history, model):
    model.script(reply("Setup started."))
    await diet_history.on_message("start reverse")
    start = len(model.requests)
    model.script(
        tool_calls(
            ("record_setup_value", {"key": "fat_g_per_kg_start", "value": 1.3}),  # above the phase's max
            ("record_setup_value", {"key": "week1_increase_kcal", "value": 600}),  # outside 300..400
            ("record_setup_value", {"key": "run_kcal_discount", "value": 1.5}),
            ("record_setup_value", {"key": "logistics.weekly_checkin", "value": "Sunday evening"}),
            ("record_setup_value", {"key": "fat_g_per_kg_start", "value": 0.9}),
        ),
        reply("Fat 0.9 g/kg noted; the rest needs another look."),
    )

    await diet_history.on_message("fat 1.3, then 0.9; +600; discount 1.5; sunday evening")

    assert [r.is_error for r in model.results(start)] == [True, True, True, True, False]
    model.script(reply("ok"))
    await diet_history.on_message("what's left?")
    setup = model.requests[-1].input["setup"]
    assert setup["recorded"] == {"fat_g_per_kg_start": 0.9}


async def test_start_phase_refuses_while_values_are_missing(diet_history, model):
    model.script(reply("Setup started."))
    await diet_history.on_message("start reverse")
    start = len(model.requests)
    model.script(tool_call("start_phase"), reply("I still need a few values."))

    await diet_history.on_message("just start")

    result = model.results(start)[0]
    assert result.is_error
    assert "exercise_classification" in result.content["error"]
    assert phases.pending_setup(diet_history) is None


# --- preview, confirm, edit -----------------------------------------------------


async def test_the_mfp_goal_is_base_plus_surplus_with_activity_on_top(diet_history, api, model, outbox):
    """A 400 kcal Strava run in the window (Tue 3 Nov, synced late): 300
    counted / 28 = 10.71 kcal a day, base 2536 - 10.71 = 2525.29, surplus
    -236. The MFP goal is the rest day, 2525.29 - 236 = 2289 kcal (carbs
    (2289.29 - 644 - 652.05) / 4 = 248 g), below the 2300 average; runs come
    on top (run day 2289 + 300)."""
    api.days["2026-11-03"]["exercises"] = [run(400, 7, 40)]
    await diet_history.sync()

    await start_and_collect(diet_history, model)

    preview = model.results(len(model.requests) - 2)[0].content
    assert preview["average_daily_target_kcal"] == 2300
    goal = {"kcal": 2289, "protein_g": 161, "carbs_g": 248, "fat_g": 72}
    assert preview["mfp_goal"] == goal
    assert preview["daily_targets_kcal"]["rest"] == 2289
    assert preview["daily_targets_kcal"]["run"] == 2589
    text = card(outbox).text
    assert "MyFitnessPal goal: 2,289 kcal" in text and "activity comes on top" in text
    await diet_history.on_button(*_confirm(card(outbox)))
    assert api.goal_writes() == [goal]
    assert phases.targets(diet_history)["mfp_goal_kcal"] == 2289


def _confirm(preview_card) -> tuple[str, str]:
    button = preview_card.buttons[0][0]
    return button.action, button.ref_id


async def test_full_start_previews_then_confirms_once(diet_history, model, outbox, api):
    coach = diet_history
    await start_and_collect(coach, model)

    preview = model.results(len(model.requests) - 2)[0].content  # the start_phase result
    assert preview["average_daily_target_kcal"] == 2300
    assert preview["mfp_goal"] == {"kcal": 2300, "protein_g": 161, "carbs_g": 251, "fat_g": 72}
    days = preview["daily_targets_kcal"]
    assert (days["rest"], days["lifting"], days["wrestling"]) == (2300, 2600, 2900)
    assert preview["avg_counted_activity_kcal"] == 0  # planned wrestling before the start doesn't count
    assert days["run"] is None  # no synced run to base a typical run on
    assert preview["macros"]["protein_g"] == 161 and preview["macros"]["fat_g"] == 72

    preview_card = card(outbox)
    assert "2300" in preview_card.text.replace(",", "") and "glycogen" in preview_card.text.lower()
    assert "1–2 kg" in preview_card.text
    actions = [b.action for row in preview_card.buttons for b in row]
    assert actions == ["confirm_phase_start", "edit_phase_start"]
    assert outbox.texts[-2] == "Preview below."

    # Nothing is active before confirm.
    assert phases.active(coach) is None
    assert coach.active_phase_id() is None
    assert phases.daily_target(coach, datetime.date(2026, 11, 13)) is None

    confirm = preview_card.buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)

    phase = phases.active(coach)
    assert phase["phase_id"] == "reverse_bulk"
    assert phase["start_date"] == "2026-11-09"
    assert phase["first_change_applied"] is True
    assert phase["setup"]["logistics"]["weekly_checkin"] == "sun 18:00"
    assert "Lifts that count for progression: Bench Press, Pull Up." in preview_card.text
    assert coach.active_phase_id() == "reverse_bulk"
    targets = phases.targets(coach)
    assert targets["avg_daily_target_kcal"] == 2300 and targets["mfp_goal_kcal"] == 2300
    assert round(targets["surplus_kcal"]) == -236
    friday = phases.daily_target(coach, datetime.date(2026, 11, 13))
    assert friday["kcal"] == 2900  # from the phase start on, planned wrestling counts
    params = phases.params(coach)
    assert params["activity"]["lifting_kcal_per_session"] == 300
    assert params["messaging"]["evening_reminder_time"] == "20:30"
    assert params["macros"]["fat_g_per_kg_start"] == 0.9
    edits = [e for e in outbox.edits if e.ref == preview_card.ref]
    # "Started", then again with the MFP goal line (test_mfp_goal.py); never buttons again.
    assert edits and all(e.buttons == () for e in edits)
    assert "✅ Started 2026-11-09" in edits[0].text

    before = list(outbox.items)
    await coach.on_button(confirm.action, confirm.ref_id)  # double tap

    assert outbox.items == before
    assert coach.db.value("SELECT COUNT(*) FROM phases") == 1
    assert len(phases.target_history(coach)) == 1


async def test_edit_returns_to_collecting_and_a_new_preview_can_be_confirmed(diet_history, model, outbox):
    coach = diet_history
    await start_and_collect(coach, model)
    first = card(outbox)
    edit = first.buttons[0][1]

    await coach.on_button(edit.action, edit.ref_id)

    assert phases.active(coach) is None
    assert any(e.ref == first.ref and e.buttons == () for e in outbox.edits)
    start = len(model.requests)
    model.script(
        tool_calls(("record_setup_value", {"key": "week1_increase_kcal", "value": 400})),
        tool_call("start_phase"),
        reply("New preview."),
    )
    await coach.on_message("make it +400")  # goes to the setup, not the chat
    recorded_ok(model, start)
    assert model.requests[start].task_skills == ("phase-start",)
    second = card(outbox)
    assert second.ref != first.ref

    stale = first.buttons[0][0]
    await coach.on_button(stale.action, stale.ref_id)  # the old card can't start anything
    assert phases.active(coach) is None

    confirm = second.buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)
    assert phases.targets(coach)["avg_daily_target_kcal"] == 2400

    model.script(reply("Hi."))
    await coach.on_message("hello")  # the setup is over: back to the chat
    assert model.requests[-1].task_skills == ("coach-chat", "context-log")
    assert model.requests[-1].prefix_skills == ("coach-core", "phase-reverse-bulk")


async def test_after_the_start_photos_can_be_switched_off_but_calibration_needs_a_proposal(
        diet_history, model, outbox):
    coach = diet_history
    await start_and_collect(coach, model)
    confirm = card(outbox).buttons[0][0]
    await coach.on_button(confirm.action, confirm.ref_id)
    start = len(model.requests)
    model.script(
        tool_calls(
            ("record_setup_value", {"key": "photos_enabled", "value": False}),
            ("record_setup_value", {"key": "lifting_kcal_per_session", "value": 400}),
        ),
        reply("Photos are off."),
    )

    await coach.on_message("no more photos, and lifting is more like 400")

    assert [r.is_error for r in model.results(start)] == [False, True]
    assert phases.params(coach)["measurements"]["photos_enabled"] is False
    assert phases.params(coach)["activity"]["lifting_kcal_per_session"] == 300


async def test_confirm_hooks_run_once_after_the_phase_is_stored(diet_history, model, outbox, monkeypatch):
    seen = []

    async def hook(coach, phase, now):
        seen.append((phase["phase_id"], phases.targets(coach)["mfp_goal"]["kcal"]))

    monkeypatch.setattr(phases, "confirm_hooks", [hook])
    await start_and_collect(diet_history, model)
    confirm = card(outbox).buttons[0][0]

    await diet_history.on_button(confirm.action, confirm.ref_id)
    await diet_history.on_button(confirm.action, confirm.ref_id)

    assert seen == [("reverse_bulk", 2300)]


async def test_cancel_ends_the_setup_without_starting_anything(diet_history, model, outbox):
    model.script(reply("Setup started."))
    await diet_history.on_message("start reverse")

    await diet_history.on_message("cancel")

    assert "cancel" in outbox.texts[-1].lower()
    assert phases.open_setup(diet_history) is None
    assert phases.active(diet_history) is None
