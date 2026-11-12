"""The web page's Week read model (coach-web ticket 06): the check-in week (the
7 days the coach judges), its decision in plain words from the stored
check-in, the proposals shown read-only, a skipped week's one-line reason,
and the week in progress without a decision.

Uses the worked example of test_weekly_checkin and test_proposals: the
reverse starts Mon 9 Nov 2026, Monday 09:00 check-ins, so a check-in week
runs Monday to Sunday and is named by its ISO week (W48 = 23-29 Nov, judged
on Mon 30 Nov). W46-W47 are the glycogen window; W48 and W49 count. Two
weeks pointing up give the +100 proposal on Mon 7 Dec; approving it makes the
average daily target 2400 kcal (was 2300) and MFP's goal 2400 kcal.
"""

from fa_coach import views
from fakes import reply, tool_call
from test_proposals import approve_tap, c_week, two_c_weeks
from test_weekly_checkin import at, check_in, fill_week, phase, three_weeks, verdict  # noqa: F401


def week(coach, iso: str | None = None) -> dict:
    data = coach.view("week", {"week": iso} if iso else {})
    assert views.errors(coach, "week", data) == []
    return data


# --- a finished check-in ------------------------------------------------------------------


async def test_a_finished_week_without_a_proposal_reads_hold_and_why(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"), report="Week 3: on track.")

    w = week(phase, "2026-W48")

    assert (w["iso_week"], w["start"], w["end"], w["state"]) == ("2026-W48", "2026-11-23", "2026-11-29", "decided")
    assert w["phase_week"] == 3
    d = w["decision"]
    assert (d["outcome"], d["change_kcal"], d["direction"]) == ("hold", None, "hold")
    assert d["why"] == "Weight is in the band."
    assert d["counts"] is True and d["skip"] is None
    assert d["decided_at"] == "2026-11-30T09:00:00+01:00"
    assert w["proposals"] == []
    assert w["report"] == "Week 3: on track."
    assert (w["prev_week"], w["next_week"]) == ("2026-W47", "2026-W49")


async def test_a_week_with_an_open_proposal_shows_it_read_only_with_when_it_would_apply(phase, api, clock, model):
    await two_c_weeks(phase, api, clock, model)

    w = week(phase, "2026-W49")

    d = w["decision"]
    assert (d["outcome"], d["change_kcal"], d["direction"]) == ("change", 100, "increase")
    [p] = w["proposals"]
    assert (p["status"], p["type"], p["source"], p["based_on_week"]) == ("open", "calorie_change", "weekly_decision",
                                                                         "2026-W49")
    assert p["change"] == "+100 kcal a day on average"
    assert p["reason"] == "Gaining below the band."
    assert p["guardrail"] == {"passed": True, "details": []}
    assert p["avg_daily_target_kcal"] == {"before": 2300, "after": 2400}
    assert p["mfp_goal_after_kcal"] == 2400
    assert p["applied_on"] is None


async def test_the_week_in_progress_has_no_decision_and_carries_the_open_proposal(phase, api, clock, model):
    await two_c_weeks(phase, api, clock, model)  # now Mon 7 Dec 09:00
    api.days["2026-12-07"] = {"weight_kg": 82.2, "steps": 9000}
    await phase.sync()
    clock.current = at("2026-12-09")  # Wednesday: the default is the week in progress again

    w = week(phase)

    assert (w["iso_week"], w["start"], w["end"]) == ("2026-W50", "2026-12-07", "2026-12-13")
    assert (w["state"], w["is_current"], w["decision"], w["report"]) == ("in_progress", True, None, None)
    assert w["so_far"] == {"days": 3, "weigh_ins": 1, "food_days_logged": 0}
    assert w["checkin_at"] == "2026-12-14T09:00:00+01:00"
    assert (w["prev_week"], w["next_week"]) == ("2026-W49", None)
    assert [(p["status"], p["based_on_week"]) for p in w["proposals"]] == [("open", "2026-W49")]


async def test_an_approved_change_shows_when_it_applied(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await approve_tap(phase, outbox)

    [p] = week(phase, "2026-W49")["proposals"]

    assert (p["status"], p["applied_on"]) == ("approved", "2026-12-07")
    assert p["avg_daily_target_kcal"] == {"before": 2300, "after": 2400}
    assert p["mfp_goal_after_kcal"] is None
    assert week(phase, "2026-W50")["proposals"] == []  # nothing open any more


async def test_a_blocked_proposal_is_a_hold_with_the_guardrails_reasons(phase, api, clock, model):
    await two_c_weeks(phase, api, clock, model, delta=300)

    w = week(phase, "2026-W49")

    assert (w["decision"]["outcome"], w["decision"]["change_kcal"]) == ("hold", None)
    [p] = w["proposals"]
    assert (p["status"], p["guardrail"]["passed"]) == ("blocked_by_guardrail", False)
    assert [x["violation"] for x in p["guardrail"]["details"]] == ["exceeds_max_change", "size_or_direction_mismatch"]
    assert "±200 kcal" in p["guardrail"]["details"][0]["text"]
    assert p["mfp_goal_after_kcal"] is None and p["avg_daily_target_kcal"] is None


# --- skipped weeks: one line each ---------------------------------------------------------


async def test_an_unusable_week_says_why_in_one_line(phase, api, clock, model):
    await three_weeks(phase, api, clock, model, weigh_ins=3)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="unusable", usable=False))

    d = week(phase, "2026-W48")["decision"]

    assert (d["outcome"], d["counts"]) == ("hold", False)
    assert d["skip"] == {"reason": "unusable", "text": "This week didn't count: 3 weigh-ins (5 needed)."}


async def test_a_glycogen_window_week_says_it_isnt_judged(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)

    skip = week(phase, "2026-W47")["decision"]["skip"]

    assert skip == {"reason": "glycogen_window",
                    "text": "Phase week 2 isn't judged: early weight change is mostly water and glycogen."}


async def test_an_adherence_gate_week_says_how_far_intake_was_off(phase, api, clock, model):
    await three_weeks(phase, api, clock, model, kcal=2600)  # 18200 vs 16700: +9.0 %
    await check_in(phase, clock, model, "2026-11-30",
                   verdict("2026-W48", scenario="adherence_gate", adherence="fail"))

    skip = week(phase, "2026-W48")["decision"]["skip"]

    assert skip == {"reason": "adherence_gate",
                    "text": "This week didn't count: intake was 9.0 % over target (within ±5 % counts)."}


async def test_a_sport_load_week_is_a_hold_that_doesnt_count(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", scenario="C", direction="increase"))
    clock.current = at("2026-11-30", 12)
    model.script(tool_call("add_context_note", applies_from="2026-11-30", applies_to="2026-12-06",
                           tags=["sport_load"], suggest_unusable="no"), reply("Noted: camp week."))
    await phase.on_message("wrestling camp all week")
    fill_week(api, 4)
    await check_in(phase, clock, model, "2026-12-07", c_week("2026-W49"))

    w = week(phase, "2026-W49")

    d = w["decision"]
    assert (d["outcome"], d["change_kcal"], d["direction"], d["counts"]) == ("hold", None, "hold", False)
    assert d["skip"] == {"reason": "sport_load",
                         "text": "A heavy sport week: it doesn't count and gives no calorie increase."}
    assert w["proposals"] == []


# --- weeks without a decision, and navigation ---------------------------------------------


async def test_a_finished_week_before_its_check_in_waits_for_it(phase, api, clock, model):
    fill_week(api, 1)
    clock.current = at("2026-11-16", 8)  # the check-in runs at 09:00
    await phase.sync()

    w = week(phase, "2026-W46")

    assert (w["state"], w["decision"], w["checkin_at"]) == ("awaiting", None, "2026-11-16T09:00:00+01:00")
    assert w["note"] == "The check-in judges this week on Mon 16 Nov at 09:00."


async def test_a_failed_check_in_says_nothing_changed(phase, api, clock, model):
    fill_week(api, 1)
    clock.current = at("2026-11-16")
    await phase.sync()
    model.script(reply("not JSON"))
    await phase.run_due_jobs()

    w = week(phase, "2026-W46")

    assert (w["state"], w["decision"]) == ("failed", None)
    assert "Send /checkin in Telegram" in w["note"]


async def test_weeks_go_back_to_the_phase_start_and_not_into_the_future(phase, api, clock, model):
    clock.current = at("2026-11-11")

    first = week(phase, "2026-W46")
    before = week(phase, "2026-W45")

    assert (first["state"], first["prev_week"], first["next_week"]) == ("in_progress", None, None)
    assert (before["state"], before["phase_week"], before["prev_week"]) == ("none", None, None)
    assert before["note"] == "No phase was active, so the coach didn't judge this week."
    for bad, reason in (("2026-W47", "That week hasn't started yet."),
                        ("2026-47", "'2026-47' is not a week (YYYY-Www).")):
        try:
            phase.view("week", {"week": bad})
        except views.WebError as exc:
            assert (exc.status, exc.message) == (400, reason)
        else:
            raise AssertionError(bad)


# --- the default week (ticket 07's decision) ----------------------------------------------


async def test_on_the_check_in_day_and_the_day_after_the_default_is_the_week_just_judged(phase, api, clock, model):
    await three_weeks(phase, api, clock, model)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48"))

    for now, expected in ((at("2026-11-30", 10), "2026-W48"), (at("2026-12-01", 23), "2026-W48"),
                          (at("2026-12-02", 0), "2026-W49")):
        clock.current = now
        w = week(phase)
        assert w["iso_week"] == expected, now
        assert w["state"] == ("decided" if expected == "2026-W48" else "in_progress")
    clock.current = at("2026-12-01")
    assert week(phase)["next_week"] == "2026-W49"


async def test_before_the_check_in_has_run_the_default_is_the_week_in_progress(phase, api, clock, model):
    fill_week(api, 1)
    clock.current = at("2026-11-16", 8)  # the check-in runs at 09:00
    await phase.sync()

    assert week(phase)["iso_week"] == "2026-W47"
