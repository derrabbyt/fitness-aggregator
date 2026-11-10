"""The MFP goal on phase confirm: code sets it once to base maintenance +
surplus (a rest day; activity comes on top) and macros, reads it back once,
says in the confirmation message whether MFP now shows it, and never
retries. The phase and the coach targets stand whatever MFP does.

Uses the worked example of test_phase_start.py: no counted activity in the
preview window, so the MFP goal is 2536 - 236 = 2300 kcal, P 161 g,
C 251 g, F 72 g."""

from fa_coach import phases
from fa_coach.ports import Goal
from test_phase_start import card, diet_history, start_and_collect  # noqa: F401 (fixture)

GOAL = {"kcal": 2300, "protein_g": 161, "carbs_g": 251, "fat_g": 72}
OLD = Goal(kcal=2000, protein_g=150, carbs_g=220, fat_g=67)


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
    assert [n for n, _ in api.calls if n in ("set_mfp_goal", "mfp_goal")] == ["set_mfp_goal"]  # the api read it back
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


async def test_the_apis_read_back_decides_whether_the_goal_is_set(diet_history, model, outbox, api):
    async def rounded(goal):  # MFP rounded the carbs by a gram, which the api counts as a match
        api.calls.append(("set_mfp_goal", {"goal": goal.as_dict()}))
        api.goal = Goal(**{**goal.as_dict(), "carbs_g": goal.carbs_g + 1})
        return {"write": "sent", "stored": api.goal, "matches": True, "error": None}

    api.set_mfp_goal = rounded

    text = await confirm(diet_history, model, outbox)

    assert "MyFitnessPal now shows" in text


def stores(api, **changed):
    """A set that MFP answers by storing the goal with `changed` values."""
    async def set_goal(goal):
        api.calls.append(("set_mfp_goal", {"goal": goal.as_dict()}))
        api.goal = Goal(**{**goal.as_dict(), **changed})
        return {"write": "sent", "stored": api.goal, "matches": False, "error": None}

    return set_goal


async def test_macros_rounded_to_mfps_percent_steps_count_as_set(diet_history, model, outbox, api):
    """A free account stores macros as a split in 5 % steps: 28 % protein of
    2300 kcal = 161 g, 43 % carbs = 247.25 g, 29 % fat = 74.1 g. Each is
    within 5 % of the calories (115 kcal) of the request."""
    api.set_mfp_goal = stores(api, carbs_g=247, fat_g=74)

    text = await confirm(diet_history, model, outbox)

    assert api.goal_writes() == [GOAL]
    assert "MyFitnessPal now shows the new goal: 2,300 kcal" in text
    assert "rounds macros" in text and "C 247 g" in text and "C 251 g" in text  # shown and exact
    assert diet_history.db.value("SELECT status FROM mfp_goal_writes") == "set"


async def test_a_macro_off_by_more_than_mfps_rounding_is_not_set(diet_history, model, outbox, api):
    api.set_mfp_goal = stores(api, carbs_g=220)  # 31 g = 124 kcal off, more than 5 % of 2300

    text = await confirm(diet_history, model, outbox)

    assert "C 220 g" in text and "MyFitnessPal now shows" not in text and "won't retry" in text


async def test_a_calorie_mismatch_is_not_set_even_with_matching_macros(diet_history, model, outbox, api):
    api.set_mfp_goal = stores(api, kcal=2250)

    text = await confirm(diet_history, model, outbox)

    assert api.goal_writes() == [GOAL]
    assert "not set" in text and "2,250 kcal" in text
    assert "MyFitnessPal now shows" not in text
    assert diet_history.db.value("SELECT status FROM mfp_goal_writes") == "not_set"


async def test_a_goal_the_api_refuses_before_sending_is_not_set_and_nothing_was_sent(diet_history, model, outbox,
                                                                                     api):
    api.goal = OLD
    api.goal_write = "refused"  # e.g. no current goal in MFP: the api sends nothing

    text = await confirm(diet_history, model, outbox)

    assert "not set (nothing sent" in text and "couldn't check" not in text
    assert_phase_stands(diet_history)


def test_the_coach_model_is_never_offered_a_goal_write(coach):
    names = set(coach.registry.tools)
    assert not [n for n in names if "goal" in n or "mfp" in n]


async def test_the_coach_model_gets_no_goal_tool_during_phase_start(diet_history, model, outbox):
    await confirm(diet_history, model, outbox)

    offered = {t["name"] for request in model.requests for t in request.tools}
    assert offered and not [n for n in offered if "goal" in n]
