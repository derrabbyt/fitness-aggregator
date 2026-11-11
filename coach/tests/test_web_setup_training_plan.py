"""Setup › Training plan on the web page (coach-web ticket 11): the saved week
(sessions with times, optional runs) and this week's reports, a lasting
change to a weekday (chat's `update_training_plan`) and this week's session
status (chat's `set_session_status`: skipped, done, extra with the user's kcal
or activity + duration estimated by code, or cleared), refused with the
tool's reason.

The plan is the seed CSV in coach/data. The clock is Monday 9 Nov 2026, 09:00
(this week: 9-15 Nov).
"""

import datetime

import pytest

from fa_coach import views
from fa_coach.features import training_plan


def view(coach, name: str = "setup/training-plan") -> dict:
    data = coach.view(name)
    assert views.errors(coach, name, data) == []
    return data


def week(v: dict) -> dict:
    return {d["weekday"]: [(s["time"], s["name"], s["type"], s["optional"]) for s in d["sessions"]] for d in v["days"]}


async def test_the_section_shows_the_saved_week_with_times_and_optional_runs(coach):
    v = view(coach)

    assert v["editable"] is True
    assert (v["valid_from"], v["upcoming"]) == (None, [])
    w = week(v)
    assert list(w) == ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    assert w["monday"] == [("06:30", "Pull", "lift", False), (None, "Easy run", "run", True)]
    assert w["tuesday"] == [("06:30", "Push", "lift", False), ("evening", "Workout run", "run", False)]
    assert w["sunday"] == [("morning", "Long Run", "run", False)]
    assert [d["date"] for d in v["this_week"]] == [f"2026-11-{n:02d}" for n in range(9, 16)]
    monday = v["this_week"][0]
    assert monday["today"] is True and v["this_week"][1]["today"] is False
    assert [(s["id"], s["status"]) for s in monday["sessions"]] == [("mon-1", None), ("mon-2", None)]
    assert monday["extras"] == []
    assert "football" in v["activities"]
    assert view(coach, "setup")["training_plan"]["summary"] == "5 lifts · 1 wrestling · 2 runs · 5 optional"


# --- a lasting change -------------------------------------------------------------------------


async def test_a_lasting_change_replaces_a_weekday_from_today_and_keeps_past_weeks(coach):
    thursday = [{"time": "06:30", "name": "Upper", "type": "lift"},
                {"time": "18:00", "name": "Wrestling", "type": "wrestling"}]

    result = await coach.command("setup/training-plan/day", {"weekday": "thursday", "sessions": thursday})

    assert views.errors(coach, "setup/training-plan", result) == []
    assert result["valid_from"] == "2026-11-09"
    assert week(result)["thursday"] == [("06:30", "Upper", "lift", False), ("18:00", "Wrestling", "wrestling", False)]
    assert week(result)["friday"] == [("12:00", "Wrestling", "wrestling", False), (None, "Easy run", "run", True)]
    assert [s["name"] for s in result["this_week"][3]["sessions"]] == ["Upper", "Wrestling"]
    last_thursday = training_plan.plan_for(coach, datetime.date(2026, 11, 5))["days"]["thursday"]
    assert [s["name"] for s in last_thursday] == ["Upper", "Easy run"]
    assert view(coach, "setup")["training_plan"]["summary"] == "5 lifts · 2 wrestling · 2 runs · 4 optional"


async def test_a_change_from_a_later_day_shows_as_upcoming(coach):
    result = await coach.command("setup/training-plan/day",
                                 {"weekday": "wednesday", "sessions": [], "from": "2026-11-16"})

    assert result["upcoming"] == [{"valid_from": "2026-11-16"}]
    assert week(result)["wednesday"][0][1] == "Legs"
    assert training_plan.plan_for(coach, datetime.date(2026, 11, 18))["days"]["wednesday"] == []
    assert view(coach, "setup")["training_plan"]["summary"].endswith("· changes from 2026-11-16")


@pytest.mark.parametrize("body, reason", [
    ({"weekday": "thursday", "sessions": [{"name": "Swim", "type": "swim"}]},
     "days/thursday/0/type: 'swim' is not one of ['lift', 'run', 'wrestling', 'other']"),
    ({"weekday": "thursday", "sessions": [{"name": "Upper", "type": "lift", "time": "25:00"}]},
     "days/thursday/0/time: '25:00' does not match"),
    ({"weekday": "thursday", "sessions": [], "from": "2026-11-02"},
     "a lasting change starts this week at the earliest; past weeks keep their plan"),
    ({"weekday": "someday", "sessions": []}, "weekday must be one of monday"),
    ({"sessions": []}, "weekday is missing."),
])
async def test_a_bad_change_is_refused_with_the_chat_reason_and_saves_nothing(coach, body, reason):
    before = view(coach)

    with pytest.raises(views.WebError) as refused:
        await coach.command("setup/training-plan/day", body)

    assert refused.value.status == 400
    assert refused.value.message.startswith(reason)
    assert view(coach) == before


# --- this week's session status -----------------------------------------------------------------


@pytest.fixture
async def weighed(coach, api):
    """Weigh-ins over the last days average 80.0 kg (the trend weight code estimates with)."""
    for day, kg in {"2026-11-05": 79.6, "2026-11-06": 80.4, "2026-11-07": 80.2, "2026-11-08": 79.8}.items():
        api.days[day] = {"weight_kg": kg}
    await coach.sync()
    return coach


def friday(v: dict) -> dict:
    return v["this_week"][4]


async def test_skipping_a_session_this_week_leaves_the_saved_plan(coach):
    result = await coach.command("setup/training-plan/session",
                                 {"date": "2026-11-13", "status": "skipped", "session_id": "fri-1"})

    assert views.errors(coach, "setup/training-plan", result["section"]) == []
    assert result["reported"] is None
    assert [(s["id"], s["status"]) for s in friday(result["section"])["sessions"]] == [("fri-1", "skipped"),
                                                                                      ("fri-2", None)]
    assert week(result["section"])["friday"][0] == ("12:00", "Wrestling", "wrestling", False)
    next_friday = [s["id"] for s in training_plan.plan_for(coach, datetime.date(2026, 11, 20))["days"]["friday"]]
    assert next_friday == ["fri-1", "fri-2"] and training_plan.statuses(coach, datetime.date(2026, 11, 20)) == []

    undone = await coach.command("setup/training-plan/session",
                                 {"date": "2026-11-13", "status": "clear", "session_id": "fri-1"})
    assert friday(undone["section"])["sessions"][0]["status"] is None


async def test_an_extra_session_by_activity_and_duration_is_estimated_by_code(weighed):
    result = await weighed.command("setup/training-plan/session", {
        "date": "2026-11-09", "status": "extra", "type": "other", "name": "Football", "activity": "football",
        "duration_min": 90})

    # football MET 7.0 x 80.0 kg x 1.5 h
    assert result["reported"] == {"kcal": 840, "kcal_source": "estimated", "kcal_counted": 840,
                                  "estimate": {"activity": "football", "met": 7.0, "trend_weight_kg": 80.0,
                                               "duration_min": 90}}
    [extra] = result["section"]["this_week"][0]["extras"]
    assert (extra["type"], extra["name"], extra["kcal"], extra["kcal_source"]) == ("other", "Football", 840,
                                                                                    "estimated")

    cleared = await weighed.command("setup/training-plan/session",
                                    {"date": "2026-11-09", "status": "clear", "extra_id": extra["extra_id"]})
    assert cleared["section"]["this_week"][0]["extras"] == []


async def test_the_users_kcal_win_and_a_done_run_counts_them_discounted(coach):
    result = await coach.command("setup/training-plan/session", {
        "date": "2026-11-09", "status": "done", "session_id": "mon-2", "kcal": 400})

    assert result["reported"]["kcal"] == 400 and result["reported"]["kcal_source"] == "reported"
    monday = result["section"]["this_week"][0]["sessions"]
    assert (monday[1]["status"], monday[1]["kcal"], monday[1]["kcal_source"]) == ("done", 400, "reported")


@pytest.mark.parametrize("body, reason", [
    ({"date": "2026-11-09", "status": "extra", "type": "other", "name": "Yoga", "activity": "yoga",
      "duration_min": 60}, "Code can't estimate the kcal: code has no MET for 'yoga'"),
    ({"date": "2026-11-09", "status": "extra", "type": "other", "name": "Football", "activity": "football",
      "duration_min": 60}, "Code can't estimate the kcal: there is no trend weight yet"),
    ({"date": "2026-11-09", "status": "extra", "type": "other", "name": "Football"},
     "Give the kcal, or an activity and a duration so code estimates them."),
    ({"date": "2026-11-09", "status": "extra", "type": "other", "name": "Football", "activity": "football"},
     "Give the duration (or the kcal)."),
    ({"date": "2026-11-09", "status": "extra", "name": "Football", "kcal": 500}, "an extra session needs its type"),
    ({"date": "2026-11-02", "status": "skipped", "session_id": "mon-1"}, "Only this week's sessions"),
    ({"date": "2026-11-16", "status": "skipped", "session_id": "mon-1"}, "Only this week's sessions"),
    ({"date": "2026-11-11", "status": "skipped", "session_id": "mon-1"},
     "give the session_id of a session planned on wednesday 2026-11-11: wed-1 (Legs), wed-2 (Easy run)"),
    ({"date": "2026-11-09", "status": "extra", "type": "other", "kcal": 99999}, "kcal: 99999 is greater than"),
    ({"date": "2026-11-09", "status": "extra", "type": "other", "kcal_estimate": 300}, "kcal_estimate isn't"),
])
async def test_a_report_code_cant_take_is_refused_with_its_reason_and_stores_nothing(coach, body, reason):
    with pytest.raises(views.WebError) as refused:
        await coach.command("setup/training-plan/session", body)

    assert refused.value.status == 400
    assert refused.value.message.startswith(reason)
    assert all(d["extras"] == [] and all(s["status"] is None for s in d["sessions"])
               for d in view(coach)["this_week"])
