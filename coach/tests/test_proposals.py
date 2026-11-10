"""Proposals: the weekly verdict's calorie change goes through `propose_change`
(guardrails in code), the report shows an open one with approve / reject /
counter buttons, and approve applies it exactly once (targets, then the MFP
goal set once and read back).

Uses the worked example of test_weekly_checkin: the reverse starts Mon 9 Nov
2026 at 2300 kcal on average (surplus -236), Monday 09:00 check-ins, the
glycogen window covers W46-W47. W48 (23-29 Nov) and W49 (30 Nov-6 Dec) are
the first weeks that count. Approving +100 on Mon 7 Dec gives an average
daily target of 2400 kcal; macros at the W49 trend weight 82.1 kg: protein
164 g, fat 74 g (0.9 g/kg), carbs (2400 - 164.2 x 4 - 73.9 x 9) / 4 = 270 g.
"""

from fa_coach import phases, proposals
from fakes import reply, reply_json, tool_call
from test_weekly_checkin import at, check_in, fill_week, phase, three_weeks, verdict  # noqa: F401

UP = {"type": "calorie_change", "delta_kcal": 100, "size": "small", "reason": "Gaining below the band.",
      "is_phase_first_change": False, "returning_rejected_proposal_id": None}
NEW_GOAL = {"kcal": 2400, "protein_g": 164, "carbs_g": 270, "fat_g": 74}


def c_week(iso: str, *, delta: int = 100, scenario: str = "C") -> dict:
    return verdict(iso, scenario=scenario, direction="increase" if delta > 0 else "decrease",
                   proposal={**UP, "delta_kcal": delta})


def last_card(outbox):
    return [m for m in outbox.sent if (m.ref or "").startswith("weekly:")][-1]


def report_input(model) -> dict:
    return [r for r in model.requests if r.task_skills == ("weekly-report",)][-1].input


def goal_writes(api) -> list[dict]:
    """MFP goal writes after the phase start's own."""
    return api.goal_writes()[1:]


def decision_input(model) -> dict:
    return [r for r in model.requests if r.task_skills == ("weekly-decision",)][-1].input


async def two_c_weeks(coach, api, clock, model, *, delta: int = 100) -> None:
    """W48 points one way (no proposal: one week), W49 the same way with a proposal."""
    await three_weeks(coach, api, clock, model)
    await check_in(coach, clock, model, "2026-11-30",
                   verdict("2026-W48", scenario="C", direction="increase" if delta > 0 else "decrease"))
    fill_week(api, 4)
    await check_in(coach, clock, model, "2026-12-07", c_week("2026-W49", delta=delta))


# --- open proposal on the report ------------------------------------------------------


async def test_an_open_proposal_is_on_the_report_with_approve_reject_and_counter(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)

    result = report_input(model)["proposal_result"]
    assert result["status"] == "open" and result["delta_kcal"] == 100
    assert result["source"] == "weekly_decision" and result["based_on_week"] == "2026-W49"
    assert result["guardrail"]["passed"] is True and result["guardrail"]["violations"] == []
    assert phase.skills.errors(result, "proposal") == []
    actions = [(b.action, b.ref_id) for row in last_card(outbox).buttons for b in row]
    assert actions == [("approve_proposal", result["id"]), ("reject_proposal", result["id"]),
                       ("counter_proposal", result["id"])]


async def test_code_adds_the_buttons_and_the_proposal_when_the_report_model_fails(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    fill_week(api, 4)
    clock.current = at("2026-12-06", 23)
    await phase.sync()
    clock.current = at("2026-12-07")
    await phase.sync()
    model.script(reply_json(c_week("2026-W49")), reply("not JSON"))
    await phase.run_due_jobs()

    card = last_card(outbox)
    assert "Proposal: +100 kcal a day on average" in card.text
    assert [b.action for row in card.buttons for b in row] == ["approve_proposal", "reject_proposal",
                                                                "counter_proposal"]


async def test_an_identical_open_proposal_is_referenced_not_duplicated(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    first = report_input(model)["proposal_result"]
    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", c_week("2026-W50"))

    again = report_input(model)["proposal_result"]
    assert again["id"] == first["id"] and again["referenced"] is True
    assert [p["id"] for p in proposals.listing(phase)] == [first["id"]]
    assert [b.ref_id for row in last_card(outbox).buttons for b in row] == [first["id"]] * 3


# --- approve ---------------------------------------------------------------------------


async def approve_tap(coach, outbox, taps: int = 1) -> str:
    """Tap approve on the latest report `taps` times; the card's final text."""
    card = last_card(outbox)
    button = card.buttons[0][0]
    assert button.action == "approve_proposal"
    for _ in range(taps):
        await coach.on_button(button.action, button.ref_id, at("2026-12-07", 10))
    edits = [e for e in outbox.edits if e.ref == card.ref]
    assert edits and all(e.buttons == () for e in edits)
    return edits[-1].text


async def test_approve_applies_once_even_on_a_double_tap(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)

    text = await approve_tap(phase, outbox, taps=2)

    targets = phases.targets(phase, at("2026-12-07").date())
    assert (targets["avg_daily_target_kcal"], round(targets["surplus_kcal"])) == (2400, -136)
    assert targets["mfp_goal"] == NEW_GOAL
    assert len(phases.target_history(phase)) == 2
    assert goal_writes(api) == [NEW_GOAL]
    assert "Approved" in text and "2,400 kcal" in text and "MyFitnessPal now shows" in text
    assert proposals.listing(phase)[0]["status"] == "approved"


async def test_a_failed_goal_write_is_reported_not_retried_and_the_targets_stand(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    api.goal = {"kcal": 2300, "protein_g": 161, "carbs_g": 251, "fat_g": 72}
    api.goal_write = "rejected"

    text = await approve_tap(phase, outbox, taps=2)

    assert goal_writes(api) == [NEW_GOAL]
    assert "not set" in text and "won't retry" in text
    assert phases.targets(phase, at("2026-12-07").date())["avg_daily_target_kcal"] == 2400


async def test_the_next_report_lists_the_applied_change_once(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await approve_tap(phase, outbox)
    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", verdict("2026-W50", scenario="A"))

    applied = report_input(model)["changes_applied"]
    assert len(applied) == 1
    change = applied[0]
    assert (change["delta_kcal"], change["avg_daily_target_before_kcal"], change["avg_daily_target_after_kcal"]) == (
        100, 2300, 2400)
    assert change["why"] == "Gaining below the band." and change["approved_on"] == "2026-12-07"
    assert change["recheck_on"] == "2026-12-21"  # two weeks that start on or after 7 Dec
    assert change["expected_weekly_rate_change_kg"] == 0.09  # 100 x 7 / 7500
    assert change["mfp_goal_status"] == "set"
    assert decision_input(model)["history"]["last_change"]["delta_kcal"] == 100

    fill_week(api, 6, avg=82.3)
    await check_in(phase, clock, model, "2026-12-21", verdict("2026-W51", scenario="A"))
    assert report_input(model)["changes_applied"] == []


async def test_approving_one_change_retires_other_open_calorie_proposals(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    older = last_card(outbox)
    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", c_week("2026-W50", delta=150))

    await phase.on_button("approve_proposal", last_card(outbox).buttons[0][0].ref_id, at("2026-12-14", 10))

    assert [p["status"] for p in proposals.listing(phase)] == ["approved", "superseded"]
    assert "Not needed any more" in [e for e in outbox.edits if e.ref == older.ref][-1].text
    await phase.on_button("approve_proposal", older.buttons[0][0].ref_id, at("2026-12-14", 11))
    assert [g["kcal"] for g in goal_writes(api)] == [2450]


# --- reject, counter, silence ----------------------------------------------------------


async def test_reject_changes_nothing_removes_the_buttons_and_asks_why(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    card = last_card(outbox)
    pid = card.buttons[0][1].ref_id

    await phase.on_button("reject_proposal", pid, at("2026-12-07", 10))
    await phase.on_button("approve_proposal", pid, at("2026-12-07", 10, 1))

    edit = [e for e in outbox.edits if e.ref == card.ref][-1]
    assert edit.buttons == () and "Rejected" in edit.text
    assert "reason" in outbox.texts[-1]
    assert proposals.get(phase, pid)["status"] == "rejected"
    assert phases.targets(phase, at("2026-12-07").date())["avg_daily_target_kcal"] == 2300
    assert goal_writes(api) == []

    clock.current = at("2026-12-07", 10, 5)
    model.script(tool_call("add_rejection_reason", proposal_id=pid, reason="Camp next week, I'll eat more anyway."),
                 reply("Noted."))
    await phase.on_message("camp next week, I'll eat more anyway")
    assert proposals.get(phase, pid)["user_reason"] == "Camp next week, I'll eat more anyway."
    assert model.requests[-2].state["proposals"]["rejected_awaiting_reason"] == pid


async def test_counter_asks_for_a_number_and_keeps_the_proposal_open(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid = last_card(outbox).buttons[0][2].ref_id

    await phase.on_button("counter_proposal", pid, at("2026-12-07", 10))

    assert "Reply with your number" in outbox.texts[-1]
    assert proposals.get(phase, pid)["status"] == "open"


async def test_an_unanswered_proposal_changes_nothing(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid = report_input(model)["proposal_result"]["id"]
    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", verdict("2026-W50", scenario="A"))

    assert phases.targets(phase, at("2026-12-14").date())["avg_daily_target_kcal"] == 2300
    assert goal_writes(api) == []
    assert [p["id"] for p in decision_input(model)["history"]["open_proposals"]] == [pid]


# --- guardrails ------------------------------------------------------------------------


def blocked(model) -> dict:
    result = report_input(model)["proposal_result"]
    assert result["status"] == "blocked_by_guardrail" and result["guardrail"]["passed"] is False
    return result


async def test_a_change_above_the_max_is_blocked_and_the_report_has_no_buttons(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model, delta=300)

    result = blocked(model)
    assert result["guardrail"]["violations"] == ["exceeds_max_change"]
    assert "±200 kcal" in result["guardrail"]["details"][0]["text"]
    assert last_card(outbox).buttons == ()


async def test_a_change_too_soon_after_the_last_one_is_locked_out(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", c_week("2026-W48"))

    result = blocked(model)
    assert result["guardrail"]["violations"] == ["lockout", "confirmation_not_met"]
    lockout = result["guardrail"]["details"][0]
    assert lockout["earliest_checkin"] == "2026-12-07" and "Mon 07 Dec" in lockout["text"]


async def test_the_lockout_counts_from_the_check_in_week_whatever_day_the_change_is_approved(
        phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await phase.on_button("approve_proposal", last_card(outbox).buttons[0][0].ref_id, at("2026-12-08", 10))
    fill_week(api, 5, kcal=2400)  # W50 (7-13 Dec) is week 1 of the new window although approved on the 8th
    await check_in(phase, clock, model, "2026-12-14", verdict("2026-W50", scenario="C", direction="increase"))
    assert report_input(model)["changes_applied"][0]["recheck_on"] == "2026-12-21"
    fill_week(api, 6, kcal=2400, avg=82.3)
    await check_in(phase, clock, model, "2026-12-21", c_week("2026-W51"))

    assert report_input(model)["proposal_result"]["status"] == "open"


async def test_too_fast_needs_only_one_confirming_week(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", c_week("2026-W48", delta=-100, scenario="E"))

    assert report_input(model)["proposal_result"]["status"] == "open"


async def test_a_direction_without_confirming_weeks_is_blocked(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model, delta=-100)  # W48 and W49 point down: that passes
    assert report_input(model)["proposal_result"]["status"] == "open"
    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", c_week("2026-W50", delta=100))

    result = blocked(model)
    assert result["guardrail"]["violations"] == ["confirmation_not_met"]
    assert result["guardrail"]["details"][0]["earliest_checkin"] == "2026-12-21"


async def test_a_rejected_direction_returns_only_after_enough_weeks(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await phase.on_button("reject_proposal", last_card(outbox).buttons[0][1].ref_id, at("2026-12-07", 10))
    fill_week(api, 5)
    await check_in(phase, clock, model, "2026-12-14", c_week("2026-W50"))

    rejected = decision_input(model)["history"]["last_rejected"]
    assert (rejected["direction"], rejected["rejected_on"], rejected["usable_weeks_since"]) == (
        "increase", "2026-12-07", 0)
    result = blocked(model)
    assert result["guardrail"]["violations"] == ["rejected_return_too_early"]
    assert result["guardrail"]["details"][0]["earliest_checkin"] == "2026-12-21"

    fill_week(api, 6, avg=82.3)
    await check_in(phase, clock, model, "2026-12-21", c_week("2026-W51"))
    assert report_input(model)["proposal_result"]["status"] == "open"


async def request(coach, clock, model, **args) -> dict:
    """The chat model calls propose_change for a user request; the tool's result."""
    clock.current = at("2026-12-08", 12)
    model.script(tool_call("propose_change", reason="User asked.", source="user_request", **args), reply("OK."))
    await coach.on_message("can I change it?")
    return model.results(len(model.requests) - 2)[0].content


async def test_a_request_based_on_an_unusable_week_is_blocked(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    fill_week(api, 4, weigh_ins=2)
    await check_in(phase, clock, model, "2026-12-07", verdict("2026-W49", scenario="unusable", usable=False))

    result = await request(phase, clock, model, type="calorie_change", delta_kcal=100)

    assert "week_unusable" in result["guardrail"]["violations"] and result["based_on_week"] == "2026-W49"
    assert "adherence_gate" not in result["guardrail"]["violations"]


async def test_a_request_based_on_a_failed_adherence_week_is_blocked(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    fill_week(api, 4, kcal=2600)
    await check_in(phase, clock, model, "2026-12-07",
                   verdict("2026-W49", scenario="adherence_gate", adherence="fail", direction="increase"))

    result = await request(phase, clock, model, type="calorie_change", delta_kcal=100)

    assert "adherence_gate" in result["guardrail"]["violations"]


async def test_calibration_values_out_of_range_are_blocked(phase, api, clock, model, outbox):
    result = await request(phase, clock, model, type="calibration_change",
                           new_values={"run_kcal_discount": 1.5, "wrestling_kcal_per_session": 500})

    assert result["status"] == "blocked_by_guardrail"
    assert result["guardrail"]["violations"] == ["invalid_values"]
    assert "run_kcal_discount" in result["guardrail"]["details"][0]["text"]
    assert not [m for m in outbox.sent if m.buttons]


async def test_an_approved_calibration_change_updates_the_setup_without_a_goal_write(phase, api, clock, model, outbox):
    result = await request(phase, clock, model, type="calibration_change",
                           new_values={"wrestling_kcal_per_session": 500})
    assert result["status"] == "open"
    card = [m for m in outbox.sent if m.buttons][-1]

    await phase.on_button("approve_proposal", result["id"], at("2026-12-08", 13))

    assert phases.params(phase)["activity"]["wrestling_kcal_per_session"] == 500
    assert goal_writes(api) == []
    assert "Approved" in [e for e in outbox.edits if e.ref == card.ref][-1].text
