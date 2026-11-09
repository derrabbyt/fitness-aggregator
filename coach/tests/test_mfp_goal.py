"""The MFP goal on phase confirm: code sets it once to the confirmed average
daily target and macros, reads it back once, says in the confirmation
message whether MFP now shows it, and never retries. The phase and the
coach targets stand whatever MFP does.

Uses the worked example of test_phase_start.py: the reverse starts at
2300 kcal, P 161 g, C 251 g, F 72 g."""

from fa_coach import phases
from test_phase_start import card, diet_history, start_and_collect  # noqa: F401 (fixture)

GOAL = {"kcal": 2300, "protein_g": 161, "carbs_g": 251, "fat_g": 72}
OLD = {"kcal": 2000, "protein_g": 150, "carbs_g": 220, "fat_g": 67}


async def confirm(coach, model, outbox, taps: int = 1) -> str:
    """Start the reverse, tap confirm `taps` times; the card's final text."""
    await start_and_collect(coach, model)
    preview = card(outbox)
    button = preview.buttons[0][0]
    for _ in range(taps):
        await coach.on_button(button.action, button.ref_id)
    return [e for e in outbox.edits if e.ref == preview.ref][-1].text


def assert_phase_stands(coach) -> None:
    assert phases.active(coach)["phase_id"] == "reverse_bulk"
    assert phases.targets(coach)["avg_daily_target_kcal"] == 2300


async def test_confirm_sets_the_goal_once_and_says_mfp_shows_it(diet_history, model, outbox, api):
    api.goal = OLD

    text = await confirm(diet_history, model, outbox)

    assert api.goal_writes() == [GOAL]
    assert [n for n, _ in api.calls if n in ("set_mfp_goal", "mfp_goal")] == ["set_mfp_goal", "mfp_goal"]
    assert "MyFitnessPal now shows" in text and "2,300 kcal" in text
    assert_phase_stands(diet_history)


async def test_a_second_tap_does_not_write_again(diet_history, model, outbox, api):
    await confirm(diet_history, model, outbox, taps=2)

    assert api.goal_writes() == [GOAL]


async def test_a_rejected_write_is_reported_and_not_retried(diet_history, model, outbox, api):
    api.goal = OLD
    api.goal_write = "rejected"

    text = await confirm(diet_history, model, outbox, taps=2)

    assert api.goal_writes() == [GOAL]
    assert "not set" in text and "2,000 kcal" in text  # what MFP still shows
    assert "won't retry" in text
    assert_phase_stands(diet_history)


async def test_a_lost_reply_is_read_back_and_shows_the_goal_landed(diet_history, model, outbox, api):
    api.goal = OLD
    api.goal_write = "lost"

    text = await confirm(diet_history, model, outbox)

    assert api.goal_writes() == [GOAL]
    assert "MyFitnessPal now shows" in text


async def test_an_unreachable_api_with_no_read_back_is_reported_as_uncertain(diet_history, model, outbox, api):
    api.goal_write = "error"
    api.fail.add("mfp_goal")

    text = await confirm(diet_history, model, outbox)

    assert api.goal_writes() == [GOAL]
    assert "couldn't check" in text and "won't retry" in text
    assert_phase_stands(diet_history)


async def test_no_reply_and_the_old_goal_read_back_is_uncertain_not_failed(diet_history, model, outbox, api):
    api.goal = OLD
    api.goal_write = "error"  # the write may still be on its way to MFP

    text = await confirm(diet_history, model, outbox, taps=2)

    assert api.goal_writes() == [GOAL]
    assert "couldn't check" in text and "2,000 kcal" in text and "won't retry" in text


async def test_mfp_rounding_a_macro_by_a_gram_still_counts_as_set(diet_history, model, outbox, api):
    async def rounded(goal):
        api.calls.append(("set_mfp_goal", {"goal": dict(goal)}))
        api.goal = {**goal, "carbs_g": goal["carbs_g"] + 1}
        return {"write": "sent", "stored": api.goal, "error": None}

    api.set_mfp_goal = rounded

    text = await confirm(diet_history, model, outbox)

    assert "MyFitnessPal now shows" in text


async def test_a_goal_stored_differently_is_reported_with_what_mfp_shows(diet_history, model, outbox, api):
    async def macros_as_percent(goal):
        api.calls.append(("set_mfp_goal", {"goal": dict(goal)}))
        api.goal = {**goal, "carbs_g": 240, "fat_g": 77}
        return {"write": "sent", "stored": api.goal, "error": None}

    api.set_mfp_goal = macros_as_percent

    text = await confirm(diet_history, model, outbox)

    assert api.goal_writes() == [GOAL]
    assert "C 240 g" in text and "F 77 g" in text
    assert "MyFitnessPal now shows" not in text


def test_the_coach_model_is_never_offered_a_goal_write(coach):
    names = set(coach.registry.tools)
    assert not [n for n in names if "goal" in n or "mfp" in n]


async def test_the_coach_model_gets_no_goal_tool_during_phase_start(diet_history, model, outbox):
    await confirm(diet_history, model, outbox)

    offered = {t["name"] for request in model.requests for t in request.tools}
    assert offered and not [n for n in offered if "goal" in n]
