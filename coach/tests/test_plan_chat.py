"""Chat about the plan (ticket 10): questions answered from stored facts and
verdicts, change requests weighed against the guardrails, counters by reply,
the optional reason after a reject, and calibration changes through
proposals.

Uses the worked example of test_weekly_checkin / test_proposals: the reverse
starts Mon 9 Nov 2026 at 2300 kcal on average, Monday 09:00 check-ins; W48
and W49 point up, so the W49 report carries an open +100 proposal.
"""

import pytest

from fa_coach import phases, progression, proposals
from fakes import exercise, reply, session, tool_call, tool_calls
from test_phase_start import SETUP
from test_proposals import goal_writes, last_card, two_c_weeks
from test_weekly_checkin import at, check_in, fill_week, phase, three_weeks, verdict  # noqa: F401


def tool_result(model, n: int = -2):
    """The first tool result code sent back after model turn `n` (default:
    the turn before the final reply)."""
    return model.results(len(model.requests) + n)[0]


# --- read tools ------------------------------------------------------------------------


async def test_why_did_you_hold_is_answered_from_the_stored_verdict(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    held = verdict("2026-W48", scenario="A", rules=["WD-USABLE-CODE", "WD-TABLE", "RB-A"])
    await check_in(phase, clock, model, "2026-11-30", held)
    clock.current = at("2026-11-30", 12)

    model.script(tool_call("get_weekly_facts"),
                 reply("I held because your weight rose 0.2 kg, inside the 0.1-0.3 kg band (rule A)."))
    await phase.on_message("why did you hold?")

    result = tool_result(model)
    assert not result.is_error
    week = result.content
    assert week["iso_week"] == "2026-W48"
    assert week["verdict"]["scenario"] == "A" and week["verdict"]["direction"] == "hold"
    assert week["rules_applied"] == ["WD-USABLE-CODE", "WD-TABLE", "RB-A"]
    assert week["facts"]["weight"]["weekly_rate_kg"] == 0.2
    assert week["counts_for_confirmation"] is True
    assert outbox.texts[-1].startswith("I held because")


async def test_weekly_facts_of_a_week_without_a_check_in_say_which_weeks_exist(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    model.script(tool_call("get_weekly_facts", iso_week="2026-W40"), reply("No check-in for that week."))

    await phase.on_message("what happened in week 40?")

    result = tool_result(model)
    assert result.is_error
    assert "2026-W47" in result.content["error"]


async def test_how_are_my_squats_gets_the_lift_history_since_the_last_baseline(phase, api, clock, model):
    api.sessions += [
        session("s1", "2026-11-10", exercise("Squat", (100, 5))),
        session("s2", "2026-11-13", exercise("Squat", (100, 6))),
        session("s3", "2026-11-17", exercise("Squat", (105, 6))),
        session("s4", "2026-11-20", exercise("Squat", (90, 8))),  # a new baseline after a depth change
        session("s5", "2026-11-24", exercise("Squat", (92.5, 8))),
    ]
    clock.current = at("2026-11-24", 12)
    await phase.sync()
    progression.mark_reset(phase, "squat", at("2026-11-20").date(), clock.now(), session_id="s4", reason="depth")

    model.script(tool_call("get_lift_history", exercise_id="squat", n_sessions=5), reply("Up 2.5 kg since the reset."))
    await phase.on_message("how are my squats?")

    history = tool_result(model).content
    assert history["name"] == "Squat" and history["counts"] is True and history["paused"] is False
    assert [(s["date"], s["status"]) for s in history["sessions"]] == [
        ("2026-11-20", "new_baseline"), ("2026-11-24", "improved")]
    latest = history["sessions"][-1]
    assert latest["top_set"]["load_kg"] == 92.5 and latest["top_set"]["reps"] == 8 and latest["is_pr"] is True
    assert history["baseline_from"] == "2026-11-20"


async def test_an_unknown_exercise_is_refused(phase, model):
    model.script(tool_call("get_lift_history", exercise_id="nope"), reply("I don't see that one."))

    await phase.on_message("how are my nopes?")

    assert tool_result(model).is_error


async def test_daily_facts_of_a_day_with_its_judged_lift_sessions(phase, api, clock, model):
    fill_week(api, 1)
    api.sessions += [session("s0", "2026-11-09", exercise("Bench Press", (80, 5))),
                     session("s1", "2026-11-10", exercise("Bench Press", (82.5, 5)))]
    clock.current = at("2026-11-11", 12)
    await phase.sync()

    model.script(tool_call("get_daily_facts", date="2026-11-10"), reply("Tuesday was on target."))
    await phase.on_message("how was yesterday?")

    day = tool_result(model).content
    facts = day["daily_facts"]
    assert phase.skills.errors(facts, "daily_facts") == []
    assert facts["date"] == "2026-11-10" and facts["day"]["intake"]["actual_kcal"] == 2200
    assert facts["day"]["intake"]["target_kcal"] == 2514  # rest day 2214 + the Hevy session's 300
    [lifts] = day["lift_sessions"]
    assert lifts["session_id"] == "s1"
    assert [(e["name"], e["status"]) for e in lifts["exercises"]] == [("Bench Press", "improved")]


async def test_daily_facts_before_the_phase_or_without_data_are_refused(phase, model):
    model.script(tool_call("get_daily_facts", date="2026-11-01"), reply("Nothing for that day."))

    await phase.on_message("how was 1 Nov?")

    assert tool_result(model).is_error


async def test_load_skill_gives_another_skill_by_name(phase, model):
    model.script(tool_calls(("load_skill", {"name": "phase-review"}), ("load_skill", {"name": "../secrets"})),
                 reply("ok"))

    await phase.on_message("end the bulk")

    loaded, refused = model.results(len(model.requests) - 2)
    assert loaded.content["skill"] == phase.skills.skill("phase-review")
    assert refused.is_error and "phase-review" in refused.content["error"]


# --- change requests -------------------------------------------------------------------


async def test_a_blocked_request_says_which_guardrail_and_when_it_could_pass(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    clock.current = at("2026-11-30", 12)
    outbox.clear()

    model.script(tool_call("get_weekly_facts"),
                 tool_call("propose_change", type="calorie_change", delta_kcal=300, reason="User wants more food.",
                           source="user_request"),
                 reply("That's blocked: more than 200 at once, and one more week pointing up is needed."))
    await phase.on_message("can I go up 300? I still want it")

    result = tool_result(model)
    assert result.content["status"] == "blocked_by_guardrail"
    assert result.content["guardrail"]["violations"] == ["exceeds_max_change", "lockout", "confirmation_not_met"]
    details = result.content["guardrail"]["details"]
    assert details[0]["earliest_checkin"] is None and "±200 kcal" in details[0]["text"]
    assert details[1]["earliest_checkin"] == details[2]["earliest_checkin"] == "2026-12-07"
    assert not [m for m in outbox.sent if m.buttons]  # nothing to approve
    assert phases.targets(phase, clock.now().date())["avg_daily_target_kcal"] == 2300


# --- counters --------------------------------------------------------------------------


async def counter_tap(coach, outbox) -> tuple[str, object]:
    """Tap counter on the latest report; (proposal id, the report card)."""
    card = last_card(outbox)
    pid = card.buttons[0][2].ref_id
    await coach.on_button("counter_proposal", pid, at("2026-12-07", 10))
    return pid, card


async def test_a_number_after_a_counter_tap_supersedes_the_proposal(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid, report = await counter_tap(phase, outbox)
    clock.current = at("2026-12-07", 10, 5)
    asked = len(model.requests)

    await phase.on_message("+50")

    assert len(model.requests) == asked  # code handles a plain number
    old, new = proposals.get(phase, pid), proposals.listing(phase, "open")[0]
    assert old["status"] == "superseded"
    assert (new["source"], new["counter_of"], new["delta_kcal"], new["based_on_week"]) == (
        "user_counter", pid, 50, "2026-W49")
    assert new["guardrail"]["passed"] is True  # same direction: inherits the confirmation
    edit = [e for e in outbox.edits if e.ref == report.ref][-1]
    assert edit.buttons == () and "Replaced by your counter" in edit.text
    card = outbox.sent[-1]
    assert [(b.action, b.ref_id) for row in card.buttons for b in row] == [
        ("approve_proposal", new["id"]), ("reject_proposal", new["id"]), ("counter_proposal", new["id"])]
    assert "+50 kcal" in card.text
    assert "I'd have gone with +100 kcal" in card.text  # said once, on the card
    assert new["agent_disagrees"]

    await phase.on_button("approve_proposal", new["id"], at("2026-12-07", 11))
    assert phases.targets(phase, at("2026-12-07").date())["avg_daily_target_kcal"] == 2350
    assert [g["kcal"] for g in goal_writes(api)] == [2350]


async def test_the_coach_disagrees_only_once_per_counter_chain(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await counter_tap(phase, outbox)
    await phase.on_message("+50")
    first = proposals.listing(phase, "open")[0]

    await phase.on_button("counter_proposal", first["id"], at("2026-12-07", 10, 10))
    await phase.on_message("make it 80")

    second = proposals.listing(phase, "open")[0]
    assert (second["delta_kcal"], second["counter_of"]) == (80, first["id"])
    assert second["agent_disagrees"] is None
    assert "I'd have gone" not in outbox.sent[-1].text


async def test_a_counter_equal_to_the_proposal_changes_nothing(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid, _ = await counter_tap(phase, outbox)

    await phase.on_message("100")

    assert proposals.get(phase, pid)["status"] == "open"
    assert len(proposals.listing(phase)) == 1
    assert "already" in outbox.texts[-1]


async def test_a_blocked_counter_leaves_the_proposal_open_and_says_why(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid, report = await counter_tap(phase, outbox)

    await phase.on_message("+300")

    assert proposals.get(phase, pid)["status"] == "open"
    blocked = proposals.listing(phase, "blocked_by_guardrail")[0]
    assert blocked["counter_of"] == pid and blocked["source"] == "user_counter"
    assert "±200 kcal" in outbox.texts[-1] and "still open" in outbox.texts[-1]
    assert not outbox.sent[-1].buttons
    assert not [e for e in outbox.edits if e.ref == report.ref]


async def test_other_text_after_a_counter_tap_goes_to_the_chat(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid, _ = await counter_tap(phase, outbox)
    model.script(reply("Your weight rose 0.1 kg a week."))

    await phase.on_message("I slept 7 hours, why +100?")

    assert outbox.texts[-1] == "Your weight rose 0.1 kg a week."
    assert model.requests[-1].state["proposals"]["counter_awaited"] == pid
    assert proposals.get(phase, pid)["status"] == "open"


async def test_a_number_without_a_counter_tap_goes_to_the_chat(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    model.script(reply("Is that your weight?"))

    await phase.on_message("+50")

    assert outbox.texts[-1] == "Is that your weight?"
    assert len(proposals.listing(phase)) == 1


async def test_a_counter_on_a_decided_proposal_goes_to_the_chat(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid, _ = await counter_tap(phase, outbox)
    await phase.on_button("reject_proposal", pid, at("2026-12-07", 10, 1))
    model.script(reply("ok"))

    await phase.on_message("+50")

    assert len(proposals.listing(phase)) == 1
    assert outbox.texts[-1] == "ok"


# --- rejection reasons -----------------------------------------------------------------


async def test_a_reason_after_a_reject_is_stored_and_a_life_reason_becomes_a_note(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    pid = last_card(outbox).buttons[0][1].ref_id
    await phase.on_button("reject_proposal", pid, at("2026-12-07", 10))
    clock.current = at("2026-12-07", 10, 5)
    said = "Family trip next week, I'd rather keep food simple"
    model.script(
        tool_calls(("add_rejection_reason", {"proposal_id": pid, "reason": said}),
                   ("add_context_note", {"applies_from": "2026-12-14", "applies_to": "2026-12-20", "tags": ["travel"],
                                         "suggest_unusable": "maybe"})),
        reply("Noted: no increase for now; trip 14-20 Dec recorded."))

    await phase.on_message(said)

    assert model.requests[-2].state["proposals"]["rejected_awaiting_reason"] == pid
    assert proposals.get(phase, pid)["user_reason"] == said
    assert proposals.last_rejected(phase)["user_reason"] == said
    note = model.results(len(model.requests) - 2)[1].content
    assert note["text"] == said and note["tags"] == ["travel"]
    assert outbox.texts[-1].startswith("Noted")


# --- setup values and calibration ------------------------------------------------------


async def ask_for_wrestling_500(coach, clock, model, day: str = "2026-12-08") -> dict:
    """The user gives a new wrestling kcal value; record_setup_value refuses a
    calibration value during a phase, so the chat proposes it. The proposal."""
    clock.current = at(day, 12)
    model.script(tool_call("record_setup_value", key="wrestling_kcal_per_session", value=500),
                 tool_call("propose_change", type="calibration_change", new_values={"wrestling_kcal_per_session": 500},
                           reason="You say wrestling burns about 500 kcal.", source="user_request"),
                 reply("That goes through a proposal: tap Approve to count 500 from today."))
    await coach.on_message("wrestling is more like 500 kcal")
    refused, proposed = model.results(len(model.requests) - 3)[0], model.results(len(model.requests) - 2)[0]
    assert refused.is_error and "proposal" in refused.content["error"]
    assert proposed.content["status"] == "open"
    return proposed.content


async def test_setup_values_in_chat_are_recorded(phase, clock, model):
    model.script(tool_call("record_setup_value", key="logistics.evening_reminder_time", value="21:00"), reply("Done."))

    await phase.on_message("remind me at 9pm instead")

    assert phases.params(phase)["messaging"]["evening_reminder_time"] == "21:00"


async def test_an_approved_calibration_change_recomputes_the_targets(phase, api, clock, model, outbox):
    """Maintenance includes activity: 600 -> 500 kcal per wrestling session
    lowers the expected counted activity by 4 x 100 / 28 = 14.29 kcal a day
    (four planned Fridays in the 28 days before), so base maintenance rises
    by as much (2450.29 -> 2464.57) and the average stays 2300: rest days
    2229, Fridays 2729. No MFP goal write."""
    result = await ask_for_wrestling_500(phase, clock, model)

    await phase.on_button("approve_proposal", result["id"], at("2026-12-08", 13))

    today = at("2026-12-08").date()
    targets = phases.targets(phase, today)
    assert targets["avg_daily_target_kcal"] == 2300
    assert round(targets["base_maintenance_kcal"], 2) == 2464.57
    assert round(targets["surplus_kcal"]) == -236
    assert phases.daily_target(phase, at("2026-12-09").date())["kcal"] == 2229
    assert phases.daily_target(phase, at("2026-12-11").date())["kcal"] == 2729
    assert goal_writes(api) == []
    text = [e for e in outbox.edits if e.ref == f"proposal:{result['id']}"][-1].text
    assert "Approved" in text and "2,300 kcal" in text


@pytest.fixture
def activity_on_top(monkeypatch):
    """Maintenance without activity: base 2536, surplus 2300 - 2536 - 85.71 = -321.71."""
    monkeypatch.setitem(SETUP, "maintenance_includes_activity", False)


async def test_a_calibration_change_that_moves_the_average_sets_the_mfp_goal_once(
        activity_on_top, phase, api, clock, model, outbox):
    """Activity on top of maintenance: the average drops by 14.29 to 2286 kcal
    and the MFP goal follows, once, macros at the start weight 80.5 kg (no
    weigh-ins since): protein 161 g, fat 72 g, carbs (2285.71 - 644 - 652.05) / 4 = 247 g."""
    assert phases.targets(phase, at("2026-11-09").date())["base_maintenance_kcal"] == 2536
    result = await ask_for_wrestling_500(phase, clock, model)

    await phase.on_button("approve_proposal", result["id"], at("2026-12-08", 13))
    await phase.on_button("approve_proposal", result["id"], at("2026-12-08", 13, 1))

    targets = phases.targets(phase, at("2026-12-08").date())
    assert round(targets["avg_daily_target_kcal"]) == 2286
    assert targets["base_maintenance_kcal"] == 2536
    assert goal_writes(api) == [{"kcal": 2286, "protein_g": 161, "carbs_g": 247, "fat_g": 72}]
    text = [e for e in outbox.edits if e.ref == f"proposal:{result['id']}"][-1].text
    assert "2,286 kcal" in text and "MyFitnessPal now shows" in text


async def test_a_calibration_change_does_not_restart_the_lockout(phase, api, clock, model, outbox):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    result = await ask_for_wrestling_500(phase, clock, model, "2026-12-02")
    await phase.on_button("approve_proposal", result["id"], at("2026-12-02", 13))
    fill_week(api, 4)
    await check_in(phase, clock, model, "2026-12-07", verdict(
        "2026-W49", scenario="C", direction="increase",
        proposal={"type": "calorie_change", "delta_kcal": 100, "size": "small", "reason": "Below the band.",
                  "is_phase_first_change": False, "returning_rejected_proposal_id": None}))

    assert proposals.listing(phase, "open")[0]["delta_kcal"] == 100
