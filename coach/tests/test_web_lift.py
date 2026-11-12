"""The web page's lift detail (coach-web ticket 09): the `lift` view (history
chart of the heaviest working set as estimated 1RM with PRs and baseline
resets marked, the last sessions with "show more" paging, the controls'
state) and its controls: `lift/reset`, plus Setup › Exercises' classify and
pause commands (ticket 12), all running the chat tools.

e1RM = load x (1 + reps / 30): 100 kg x 8 = 126.67, 105 x 8 = 133.0.
"""

import datetime

import pytest

from fa_coach import views
from fakes import TZ, exercise, session

D = datetime.date
DAY = datetime.timedelta(days=1)


def lift_view(coach, exercise_id: str, **query: str) -> dict:
    data = coach.view("lift", {"exercise_id": exercise_id, **query})
    assert views.errors(coach, "lift", data) == []
    return data


async def synced(coach, api, clock, sessions, *, weigh_ins: dict[str, float] | None = None,
                 now: str = "2026-11-20") -> None:
    api.sessions = list(sessions)
    for day, kg in (weigh_ins or {}).items():
        api.days.setdefault(day, {})["weight_kg"] = kg
    clock.current = datetime.datetime.combine(D.fromisoformat(now), datetime.time(9), tzinfo=TZ)
    await coach.sync()


def bench(kg: float | None, reps: int = 8) -> dict:
    return exercise("Bench Press", (kg, reps))


def bench_history() -> list[dict]:
    """Bench: 100, 102.5 (PR), 102.5 (same), 105 (PR), 100 (declined)."""
    return [
        session("a", "2026-11-02", bench(100)),
        session("b", "2026-11-05", bench(102.5)),
        session("c", "2026-11-09", bench(102.5)),
        session("d", "2026-11-12", bench(105)),
        session("e", "2026-11-16", bench(100)),
    ]


# --- the chart ---------------------------------------------------------------------------


async def test_the_chart_is_every_session_as_estimated_1rm_with_prs_marked(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    lift = lift_view(coach, "bench-press")

    assert (lift["name"], lift["status"], lift["counts"], lift["paused"]) == ("Bench Press", "declining", True, False)
    assert [(p["date"], p["e1rm_kg"], p["pr"], p["baseline_reset"]) for p in lift["chart"]] == [
        ("2026-11-02", 126.67, False, False),
        ("2026-11-05", 129.83, True, False),
        ("2026-11-09", 129.83, False, False),
        ("2026-11-12", 133.0, True, False),
        ("2026-11-16", 126.67, False, False),
    ]


async def test_a_bodyweight_lift_is_charted_on_its_effective_load(coach, api, clock):
    pull = lambda kg: exercise("Pull Up", (kg, 8), exercise_type="bodyweight_weighted")  # noqa: E731
    weigh_ins = {(D(2026, 11, 1) + k * DAY).isoformat(): 80.0 for k in range(20)}
    await synced(coach, api, clock, [session("a", "2026-11-09", pull(None)), session("b", "2026-11-16", pull(10))],
                 weigh_ins=weigh_ins)

    lift = lift_view(coach, "pull-up")

    assert lift["bodyweight_exercise"] is True
    assert [(p["load_kg"], p["effective_load_kg"], p["e1rm_kg"]) for p in lift["chart"]] == [
        (0.0, 80.0, 101.33), (10.0, 90.0, 114.0)]
    assert lift["sessions"]["items"][0]["top_set"]["effective_load_kg"] == 90.0


async def test_a_baseline_reset_is_marked_on_the_chart_with_its_reason(coach, api, clock):
    await synced(coach, api, clock, bench_history())
    await coach.command("lift/reset", {"exercise_id": "bench-press", "reason": "technique_change",
                                       "date": "2026-11-10"})

    lift = lift_view(coach, "bench-press")

    assert [(p["date"], p["pr"], p["baseline_reset"]) for p in lift["chart"]][2:] == [
        ("2026-11-09", False, False), ("2026-11-12", False, True), ("2026-11-16", False, False)]
    assert lift["resets"] == [{"from_date": "2026-11-10", "reason": "technique_change", "session_date": "2026-11-12"}]


# --- sessions and paging -----------------------------------------------------------------


async def test_the_last_three_sessions_come_first_and_show_more_pages_through_the_rest(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    first = lift_view(coach, "bench-press")["sessions"]
    more = lift_view(coach, "bench-press", offset="3")["sessions"]

    assert [(s["date"], s["top_set"]["load_kg"], s["top_set"]["reps"], s["status"], s["pr"])
            for s in first["items"]] == [
        ("2026-11-16", 100, 8, "declining", False),
        ("2026-11-12", 105, 8, "progressing", True),
        ("2026-11-09", 102.5, 8, "same", False),
    ]
    assert (first["total"], first["next_offset"]) == (5, 3)
    assert [(s["date"], s["status"]) for s in more["items"]] == [
        ("2026-11-05", "progressing"), ("2026-11-02", "new_baseline")]
    assert more["next_offset"] is None


async def test_a_session_without_a_working_set_is_listed_but_not_charted(coach, api, clock):
    await synced(coach, api, clock, [*bench_history(), session("f", "2026-11-19", bench(40, 25))])

    lift = lift_view(coach, "bench-press")

    assert lift["sessions"]["items"][0] == {"date": "2026-11-19", "session_id": "f", "top_set": None,
                                            "status": "not_judged", "not_judged_reason": "no_working_sets",
                                            "pr": False}
    assert lift["chart"][-1]["date"] == "2026-11-16"


async def test_a_past_day_shows_the_lift_as_it_stood_that_day(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    lift = lift_view(coach, "bench-press", day="2026-11-12")

    assert (lift["date"], lift["status"], lift["last_session_date"]) == ("2026-11-12", "progressing", "2026-11-12")
    assert len(lift["chart"]) == 4


async def test_an_unknown_lift_or_a_bad_page_is_refused(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    with pytest.raises(views.WebError) as unknown:
        coach.view("lift", {"exercise_id": "nope"})
    with pytest.raises(views.WebError) as bad_page:
        coach.view("lift", {"exercise_id": "bench-press", "offset": "-1"})

    assert unknown.value.status == 404
    assert (bad_page.value.status, bad_page.value.message) == (400, "offset must be at least 0.")


# --- controls ------------------------------------------------------------------------------


async def test_switching_a_lift_to_not_counted_moves_it_on_the_training_list(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    await coach.command("setup/exercises/classify", {"exercise_id": "bench-press", "classification": "excluded"})

    lift = lift_view(coach, "bench-press")
    assert (lift["counts"], lift["controls"]["classification"]) == (False, "excluded")
    training = coach.view("training")
    assert ([x["name"] for x in training["lifts"]], [x["name"] for x in training["not_counted"]]) == \
        ([], ["Bench Press"])

    await coach.command("setup/exercises/classify", {"exercise_id": "bench-press", "classification": "counts"})
    assert lift_view(coach, "bench-press")["counts"] is True


async def test_pausing_a_lift_stops_judging_it_until_it_is_unpaused(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    await coach.command("setup/exercises/pause", {"exercise_id": "bench-press", "paused": True, "reason": "left shoulder"})

    paused = lift_view(coach, "bench-press")
    assert (paused["status"], paused["paused"], paused["controls"]["paused_reason"]) == \
        ("paused", True, "left shoulder")
    assert not any(p["pr"] for p in paused["chart"])

    await coach.command("setup/exercises/pause", {"exercise_id": "bench-press", "paused": False})

    resumed = lift_view(coach, "bench-press")
    assert (resumed["status"], resumed["paused"], resumed["controls"]["paused_reason"]) == \
        ("declining", False, None)


async def test_a_reset_from_today_waits_for_the_next_session(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    said = await coach.command("lift/reset", {"exercise_id": "bench-press", "reason": "exercise_swap"})

    assert said["say"] == "New baseline for Bench Press from the next session."
    lift = lift_view(coach, "bench-press")
    assert lift["resets"] == [{"from_date": "2026-11-20", "reason": "exercise_swap", "session_date": None}]
    assert not any(p["baseline_reset"] for p in lift["chart"])


async def test_a_control_with_a_bad_value_is_refused_with_the_chat_tools_reason(coach, api, clock):
    await synced(coach, api, clock, bench_history())

    refusals = []
    for name, body in [
        ("setup/exercises/pause", {"exercise_id": "nope", "paused": True}),
        ("lift/reset", {"exercise_id": "bench-press", "reason": "felt like it"}),
        ("setup/exercises/classify", {"exercise_id": "bench-press", "classification": "no"}),
        ("lift/reset", {"exercise_id": "bench-press"}),
    ]:
        with pytest.raises(views.WebError) as refused:
            await coach.command(name, body)
        refusals.append((refused.value.status, refused.value.message))

    assert refusals[0] == (400, "exercise_id 'nope' is not in the synced Hevy history; see get_tracked_exercises")
    assert refusals[1][0] == 400 and refusals[1][1].startswith("reason: 'felt like it' is not one of")
    assert refusals[2][0] == 400 and refusals[2][1].startswith("exercises/0/classification: 'no' is not one of")
    assert refusals[3] == (400, "reason is missing.")
    lift = lift_view(coach, "bench-press")
    assert (lift["resets"], lift["paused"], lift["counts"]) == ([], False, True)
