"""The web page's Setup (coach-web ticket 10): the section list with one-line
summaries, Phase & targets (with the step goal edit), Messaging (saved
directly) and Activity values (a change becomes a calibration proposal
approved in Telegram). Edits go through the chat tools (`record_setup_value`,
`propose_change`), so they are validated the same way and refused with the
same reasons.

Uses the worked example of test_weekly_checkin: the reverse starts Mon 9 Nov
2026 with Monday 09:00 check-ins, base maintenance 2536 at 9,000 average
steps, surplus -236, run discount 0.75, wrestling 600 kcal, lifting 300 kcal,
evening reminder 20:30, 2 messages a day, step-floor window 5 days, the
default step goal 10,000.
"""

import pytest

from fa_coach import phases, proposals, views
from fa_coach.features import web_setup
from fakes import reply
from test_weekly_checkin import at, phase  # noqa: F401


def view(coach, name: str) -> dict:
    data = coach.view(name)
    assert views.errors(coach, name, data) == []
    return data


# --- the section list ---------------------------------------------------------------------


async def test_setup_lists_the_sections_with_one_line_summaries(phase):
    s = view(phase, "setup")

    assert s["phase_active"] is True
    assert s["phase_targets"]["summary"] == "Reverse into bulk · week 1 · step goal 10,000"
    assert s["activity"]["summary"] == "Runs 75 % · wrestling 600 kcal · lifting 300 kcal"
    assert s["messaging"]["summary"] == "Check-in Mon 09:00 · reminder 20:30 · 2 messages a day"


async def test_before_any_phase_setup_says_so_and_nothing_is_editable(coach):
    s = view(coach, "setup")

    assert (s["phase_active"], s["setup_open"]) == (False, False)
    assert s["phase_targets"]["summary"] == "No active phase · step goal 10,000"
    pt = view(coach, "setup/phase-targets")
    assert (pt["phase"], pt["targets"], pt["step_goal"]["editable"]) == (None, None, False)
    assert view(coach, "setup/messaging")["editable"] is False
    assert view(coach, "setup/activity")["editable"] is False


# --- Phase & targets ------------------------------------------------------------------------


async def test_phase_and_targets_show_the_phase_and_the_targets_in_force(phase):
    pt = view(phase, "setup/phase-targets")

    assert pt["phase"] == {"phase_id": "reverse_bulk", "name": "Reverse into bulk", "start_date": "2026-11-09",
                           "week": 1}
    t = pt["targets"]
    # k = 0.04 x 80.5 / 70 x 0.75 = 0.0345 kcal/step; base at 10,000 = 2536 + 0.0345 x 1,000 = 2570.5
    assert (t["base_maintenance_kcal"], t["avg_day_steps"], t["base_at_step_goal_kcal"]) == (2536, 9000, 2570)
    assert (t["surplus_kcal"], t["avg_daily_target_kcal"], t["mfp_goal_kcal"]) == (-236, 2300, 2300)
    assert t["at_step_goal"] == {"rest": 2334, "lifting": 2634, "wrestling": 2934}  # 2334.5 + 300 / 600
    assert t["today"] == {"kcal": 2300, "protein_g": 161, "carbs_g": 251, "fat_g": 72}  # 9,000 steps today
    assert pt["step_goal"] == {"value": 10000, "default": 10000, "min": 1000, "max": 40000, "editable": True}


async def test_changing_the_step_goal_moves_only_where_zero_is(phase, api, outbox):
    result = await phase.command("setup/step-goal", {"step_goal": 8000})

    assert views.errors(phase, "setup/phase-targets", result) == []
    assert result["step_goal"]["value"] == 8000
    t = view(phase, "setup/phase-targets")["targets"]
    # base at 8,000 = 2536 - 0.0345 x 1,000 = 2501.5; the targets row and the MFP goal stay
    assert (t["base_at_step_goal_kcal"], t["at_step_goal"]["rest"]) == (2502, 2266)
    assert (t["base_maintenance_kcal"], t["surplus_kcal"], t["mfp_goal_kcal"]) == (2536, -236, 2300)
    assert t["today"]["kcal"] == 2300  # the energy doesn't change
    assert phases.params(phase)["steps"]["step_goal"] == 8000
    assert api.goal_writes()[1:] == [] and outbox.sent == []


@pytest.mark.parametrize("body, reason", [
    ({"step_goal": 500}, "step_goal: 500 is less than the minimum of 1000"),
    ({"step_goal": 9500.5}, "step_goal: 9500.5 is not of type 'integer'"),
    ({}, "step_goal is missing."),
])
async def test_a_step_goal_out_of_range_is_refused_with_the_chat_reason(phase, body, reason):
    with pytest.raises(views.WebError) as refused:
        await phase.command("setup/step-goal", body)

    assert (refused.value.status, refused.value.message) == (400, reason)
    assert phases.params(phase)["steps"]["step_goal"] == 10000


async def test_without_a_phase_the_step_goal_is_refused(coach):
    with pytest.raises(views.WebError) as refused:
        await coach.command("setup/step-goal", {"step_goal": 8000})

    assert (refused.value.status, refused.value.message) == (409, web_setup.NO_PHASE)


async def test_while_a_phase_setup_is_open_in_telegram_nothing_is_edited(phase, model):
    model.script(reply("Here is what I read. Confirm?"))
    await phase.on_message("start reverse")
    assert view(phase, "setup")["setup_open"] is True
    assert view(phase, "setup/messaging")["editable"] is False

    for name, body in (("setup/step-goal", {"step_goal": 8000}),
                       ("setup/messaging", {"field": "evening_reminder_time", "value": "21:00"}),
                       ("setup/activity", {"values": {"lifting_kcal_per_session": 250}})):
        with pytest.raises(views.WebError) as refused:
            await phase.command(name, body)
        assert (refused.value.status, refused.value.message) == (409, web_setup.SETUP_OPEN)
    assert phases.params(phase)["messaging"]["evening_reminder_time"] == "20:30"


# --- Messaging --------------------------------------------------------------------------------


async def test_messaging_shows_when_the_coach_writes(phase):
    assert view(phase, "setup/messaging") == {
        "editable": True,
        "weekly_checkin": {"day": "mon", "time": "09:00"},
        "evening_reminder_time": "20:30",
        "max_unprompted_messages_per_day": 2,
        "soft_floor_min_days": 5,
    }


@pytest.mark.parametrize("field, value, shown", [
    ("weekly_checkin", "sun 18:00", {"day": "sun", "time": "18:00"}),
    ("evening_reminder_time", "21:15", "21:15"),
    ("max_unprompted_messages_per_day", 3, 3),
    ("soft_floor_min_days", 4, 4),
    ("evening_reminder_time", None, None),
])
async def test_each_messaging_value_saves_directly(phase, outbox, field, value, shown):
    result = await phase.command("setup/messaging", {"field": field, "value": value})

    assert views.errors(phase, "setup/messaging", result) == []
    assert result[field] == shown
    assert view(phase, "setup/messaging")[field] == shown
    assert outbox.sent == []


async def test_a_new_check_in_day_moves_the_check_in_week(phase):
    await phase.command("setup/messaging", {"field": "weekly_checkin", "value": "thu 18:00"})

    assert view(phase, "setup")["messaging"]["summary"].startswith("Check-in Thu 18:00")
    assert phase.view("home/food")["start"] == "2026-11-05"  # the check-in week now starts on Thursday


@pytest.mark.parametrize("body, reason", [
    ({"field": "evening_reminder_time", "value": "25:00"},
     "logistics.evening_reminder_time: '25:00' does not match '^([01][0-9]|2[0-3]):[0-5][0-9]$'"),
    ({"field": "weekly_checkin", "value": "sunday 18:00"},
     "logistics.weekly_checkin: 'sunday 18:00' does not match "
     "'^(mon|tue|wed|thu|fri|sat|sun) ([01][0-9]|2[0-3]):[0-5][0-9]$'"),
    ({"field": "max_unprompted_messages_per_day", "value": 0},
     "logistics.max_unprompted_messages_per_day: 0 is less than the minimum of 1"),
    ({"field": "soft_floor_min_days", "value": "five"},
     "logistics.soft_floor_min_days: 'five' is not of type 'integer', 'null'"),
    ({"field": "step_goal", "value": 8000},
     "'step_goal' isn't a messaging value (weekly_checkin, evening_reminder_time, "
     "max_unprompted_messages_per_day, soft_floor_min_days)."),
    ({"field": "evening_reminder_time"}, "value is missing."),
])
async def test_a_bad_messaging_value_is_refused_with_its_reason(phase, body, reason):
    with pytest.raises(views.WebError) as refused:
        await phase.command("setup/messaging", body)

    assert (refused.value.status, refused.value.message) == (400, reason)
    assert view(phase, "setup/messaging")["evening_reminder_time"] == "20:30"


# --- Activity values: calibration proposals ---------------------------------------------------


async def test_activity_values_show_the_calibration_values_and_their_ranges(phase):
    a = view(phase, "setup/activity")

    assert a["values"] == {
        "run_kcal_discount": {"value": 0.75, "min": 0, "max": 1, "min_exclusive": True},
        "wrestling_kcal_per_session": {"value": 600, "min": 0, "max": 3000},
        "lifting_kcal_per_session": {"value": 300, "min": 0, "max": 2000},
    }
    assert (a["editable"], a["pending"]) == (True, [])


async def test_an_activity_change_becomes_a_proposal_approved_in_telegram(phase, api, clock, outbox):
    clock.current = at("2026-11-10", 12)
    result = await phase.command("setup/activity",
                                 {"values": {"wrestling_kcal_per_session": 500, "lifting_kcal_per_session": 300}})

    p = result["proposal"]
    assert p["new_values"] == {"wrestling_kcal_per_session": 500}  # only what changed
    assert p["change"] == "wrestling kcal per session → 500"
    assert p["referenced"] is False
    stored = proposals.get(phase, p["id"])
    assert (stored["type"], stored["status"], stored["source"]) == ("calibration_change", "open", "user_request")
    # Nothing changes yet; the section shows the change waiting.
    assert view(phase, "setup/activity")["values"]["wrestling_kcal_per_session"]["value"] == 600
    assert [x["id"] for x in result["section"]["pending"]] == [p["id"]]
    assert view(phase, "setup")["activity"]["summary"].endswith("· change waiting in Telegram")
    # The card goes to Telegram with approve / reject / counter.
    card = [m for m in outbox.sent if m.buttons][-1]
    assert card.text.startswith("Proposal: wrestling kcal per session → 500. Changed on the web page.")
    assert [b.action for b in card.buttons[0]] == ["approve_proposal", "reject_proposal", "counter_proposal"]

    await phase.on_button("approve_proposal", p["id"])

    assert view(phase, "setup/activity")["values"]["wrestling_kcal_per_session"]["value"] == 500
    assert view(phase, "setup/activity")["pending"] == []


async def test_the_same_change_again_points_to_the_open_proposal(phase, outbox):
    first = await phase.command("setup/activity", {"values": {"run_kcal_discount": 0.8}})
    again = await phase.command("setup/activity", {"values": {"run_kcal_discount": 0.8}})

    assert again["proposal"]["id"] == first["proposal"]["id"]
    assert again["proposal"]["referenced"] is True
    assert len([m for m in outbox.sent if m.buttons]) == 1


@pytest.mark.parametrize("values, reason", [
    ({"run_kcal_discount": 1.5}, "Runs counted 150 % is outside 0–100 %. Values inside those ranges could pass."),  # the web takes a percentage
    ({"lifting_kcal_per_session": -10},
     "lifting_kcal_per_session = -10 is outside 0–2000. Values inside those ranges could pass."),
    ({"soft_step_floor": 8000},
     "soft_step_floor isn't a calibration value (run_kcal_discount, wrestling_kcal_per_session, "
     "lifting_kcal_per_session). Values inside those ranges could pass."),
    ({"run_kcal_discount": "high"}, "new_values/run_kcal_discount: 'high' is not of type 'number'"),
    ({"run_kcal_discount": 0.75}, "Those are the current values; nothing to change."),
    ({}, "values must name at least one activity value."),
])
async def test_a_bad_activity_value_is_refused_with_its_reason_and_no_card(phase, outbox, values, reason):
    with pytest.raises(views.WebError) as refused:
        await phase.command("setup/activity", {"values": values})

    assert (refused.value.status, refused.value.message) == (400, reason)
    assert not [m for m in outbox.sent if m.buttons]
    assert proposals.open_proposals(phase) == []
    assert phases.params(phase)["activity"]["run_kcal_discount"] == 0.75


async def test_no_web_edit_changes_targets_or_the_mfp_goal(phase, api):
    before = phases.targets(phase)

    await phase.command("setup/step-goal", {"step_goal": 12000})
    await phase.command("setup/messaging", {"field": "max_unprompted_messages_per_day", "value": 1})
    await phase.command("setup/activity", {"values": {"lifting_kcal_per_session": 250}})

    assert phases.targets(phase) == before
    assert api.goal_writes()[1:] == []
    assert phases.active(phase)["phase_id"] == "reverse_bulk"
