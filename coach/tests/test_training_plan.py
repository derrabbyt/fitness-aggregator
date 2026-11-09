"""The training plan: seeded once from the CSV in coach/data, then changed only
through the chat (`update_training_plan` for good, `set_session_status` for
this week), and read with `get_training_plan`."""

import datetime

import pytest

from fa_coach.features import training_plan
from fakes import reply, tool_call, tool_calls


async def _tool(coach, model, name: str, message: str = "plan", **args):
    """One chat turn in which the model calls `name` once; returns what code
    sent back to the model."""
    start = len(model.requests)
    model.script(tool_call(name, **args), reply("ok"))
    await coach.on_message(message)
    [result] = model.results(start)
    return result


def _week(plan_result):
    return {day: [(s["time"], s["name"], s["type"], s["optional"]) for s in sessions]
            for day, sessions in plan_result["plan"]["days"].items()}


async def test_the_plan_is_seeded_from_the_csv_on_first_start(coach, model):
    result = await _tool(coach, model, "get_training_plan")

    assert not result.is_error
    week = _week(result.content)
    assert week["monday"] == [("06:30", "Pull", "lift", False), (None, "Easy run", "run", True)]
    assert week["tuesday"] == [("06:30", "Push", "lift", False), ("evening", "Workout run", "run", False)]
    assert week["thursday"] == [("06:30", "Upper", "lift", False), (None, "Easy run", "run", True)]
    assert week["friday"] == [("12:00", "Wrestling", "wrestling", False), (None, "Easy run", "run", True)]
    assert week["saturday"] == [("midday", "Legs", "lift", False), (None, "Easy run", "run", True)]
    assert week["sunday"] == [("morning", "Long Run", "run", False)]
    lists = result.content["plan"]["exercise_lists"]
    assert list(lists) == ["Legs A", "Legs B", "Push", "Pull", "Upper"]
    assert lists["Legs A"][2] == {"text": "Hacksquat", "names": ["Hacksquat"], "optional": False}
    assert lists["Push"][1] == {"text": "(Chest Press)", "names": ["Chest Press"], "optional": True}
    assert lists["Pull"][0]["names"] == ["Pull-Ups", "Lat Pulldown"]
    assert lists["Upper"][4]["names"] == ["Lateral Raises", "Shoulder Press"]
    assert lists["Legs B"][-1]["text"] == "Hip Flexor KB/Cable Raises"


async def test_after_seeding_the_csv_is_not_read_again(make_coach, model, tmp_path, monkeypatch):
    coach = make_coach()
    await coach.run_due_jobs()  # first start seeds the plan
    other = tmp_path / "other.csv"
    other.write_text(",,,,,,\nMonday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday\n12:00 - Swim,,,,,,\n")
    monkeypatch.setattr(training_plan, "SEED_CSV", other)

    restarted = make_coach()
    await restarted.run_due_jobs()
    result = await _tool(restarted, model, "get_training_plan")

    assert _week(result.content)["monday"][0][1] == "Pull"


async def test_a_missing_csv_leaves_no_plan_and_seeds_later(coach, model, tmp_path, monkeypatch):
    monkeypatch.setattr(training_plan, "SEED_CSV", tmp_path / "missing.csv")
    result = await _tool(coach, model, "get_training_plan")
    assert result.is_error

    monkeypatch.undo()
    result = await _tool(coach, model, "get_training_plan")
    assert _week(result.content)["monday"][0][1] == "Pull"


async def test_a_lasting_change_applies_from_today_and_keeps_past_days(make_coach, model, outbox):
    coach = make_coach()
    model.script(
        tool_call(
            "update_training_plan",
            days={
                "thursday": [
                    {"time": "06:30", "name": "Upper", "type": "lift"},
                    {"time": "18:00", "name": "Wrestling", "type": "wrestling"},
                ],
                "friday": [{"time": None, "name": "Easy run", "type": "run", "optional": True}],
            },
        ),
        reply("Saved: wrestling moves to Thursday 18:00 from today; Friday is an optional easy run."),
    )

    await coach.on_message("wrestling is on Thursday evenings from now on")

    [result] = model.results(0)
    assert not result.is_error
    assert outbox.texts == ["Saved: wrestling moves to Thursday 18:00 from today; Friday is an optional easy run."]
    restarted = make_coach()
    week = _week((await _tool(restarted, model, "get_training_plan")).content)
    assert week["thursday"] == [("06:30", "Upper", "lift", False), ("18:00", "Wrestling", "wrestling", False)]
    assert week["friday"] == [(None, "Easy run", "run", True)]
    assert week["monday"][0][1] == "Pull"  # untouched days stay
    last_friday = training_plan.plan_for(restarted, datetime.date(2026, 11, 6))
    assert [s["name"] for s in last_friday["days"]["friday"]] == ["Wrestling", "Easy run"]
    next_friday = training_plan.plan_for(restarted, datetime.date(2026, 11, 13))
    assert [s["name"] for s in next_friday["days"]["friday"]] == ["Easy run"]


async def test_a_lasting_change_can_edit_exercise_lists(coach, model):
    result = await _tool(
        coach, model, "update_training_plan",
        exercise_lists={"Push": ["Bench Press", "(Dips)"], "Legs B": None},
    )

    lists = result.content["plan"]["exercise_lists"]
    assert lists["Push"] == [
        {"text": "Bench Press", "names": ["Bench Press"], "optional": False},
        {"text": "(Dips)", "names": ["Dips"], "optional": True},
    ]
    assert "Legs B" not in lists
    assert training_plan.exercise_lists(coach)["Push"][0]["names"] == ["Bench Press"]


async def test_a_lasting_change_cannot_start_in_an_earlier_week(coach, model):
    result = await _tool(coach, model, "update_training_plan", days={"monday": []}, **{"from": "2026-11-01"})

    assert result.is_error
    assert training_plan.plan_for(coach, datetime.date(2026, 11, 9))["days"]["monday"][0]["name"] == "Pull"


async def test_this_week_changes_touch_only_their_day(coach, model, outbox):
    model.script(
        tool_calls(
            ("set_session_status", {"date": "2026-11-13", "status": "skipped", "session_id": "fri-1"}),
            ("set_session_status", {"date": "2026-11-11", "status": "extra", "type": "other",
                                    "name": "Climbing", "kcal": 350}),
        ),
        reply("Noted: no wrestling this Friday; climbing on Wednesday adds 350 kcal."),
    )

    await coach.on_message("no wrestling this friday, and I went climbing on wednesday, about 350 kcal")

    assert not any(r.is_error for r in model.results(0))
    assert outbox.texts == ["Noted: no wrestling this Friday; climbing on Wednesday adds 350 kcal."]
    week = {d["date"]: d for d in (await _tool(coach, model, "get_training_plan")).content["this_week"]}
    assert [(s["name"], s["status"]) for s in week["2026-11-13"]["sessions"]] == [
        ("Wrestling", "skipped"), ("Easy run", None)]
    assert [(e["name"], e["kcal"]) for e in week["2026-11-11"]["extras"]] == [("Climbing", 350)]
    assert training_plan.statuses(coach, datetime.date(2026, 11, 20)) == []
    # the saved plan itself is unchanged
    assert training_plan.plan_for(coach, datetime.date(2026, 11, 20))["days"]["friday"][0]["name"] == "Wrestling"


async def test_a_status_can_be_changed_and_cleared(coach, model):
    await _tool(coach, model, "set_session_status", date="2026-11-13", status="skipped", session_id="fri-1")
    await _tool(coach, model, "set_session_status", date="2026-11-13", status="done", session_id="fri-1")
    assert [s["status"] for s in training_plan.statuses(coach, datetime.date(2026, 11, 13))] == ["done"]

    await _tool(coach, model, "set_session_status", date="2026-11-13", status="clear", session_id="fri-1")
    assert training_plan.statuses(coach, datetime.date(2026, 11, 13)) == []


@pytest.mark.parametrize(
    "args",
    [
        {"date": "2026-11-13", "status": "skipped", "session_id": "fri-9"},  # not in the plan that day
        {"date": "2026-11-13", "status": "skipped"},  # which session?
        {"date": "2026-11-11", "status": "extra", "type": "other"},  # an extra needs its kcal
        {"date": "2026-11-20", "status": "skipped", "session_id": "fri-1"},  # next week
        {"date": "2026-10-30", "status": "skipped", "session_id": "fri-1"},  # two weeks back
    ],
)
async def test_bad_session_reports_are_refused(coach, model, args):
    result = await _tool(coach, model, "set_session_status", **args)

    assert result.is_error
    assert training_plan.statuses(coach, datetime.date.fromisoformat(args["date"])) == []
