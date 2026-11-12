"""Home's banner (coach-web ticket 05): only on today, only when a proposal is
open (it links to the Week page) or a coach question waits in Telegram."""

from fa_coach import views
from test_evening import at as evening, log, reverse  # noqa: F401 (fixture)
from test_proposals import approve_tap, two_c_weeks
from test_weekly_checkin import phase  # noqa: F401 (fixture)


def banner(coach, day: str | None = None):
    data = coach.view("home", {"day": day} if day else {})
    assert views.errors(coach, "home", data) == []
    return data["banner"]


async def test_nothing_waiting_shows_no_banner(phase):
    assert banner(phase) is None


async def test_an_open_proposal_shows_the_banner_with_the_change(phase, api, clock, model):
    await two_c_weeks(phase, api, clock, model)  # W49's check-in proposes +100 kcal

    b = banner(phase)

    assert b["proposal"]["type"] == "calorie_change"
    assert b["proposal"]["change"] == "+100 kcal a day on average"
    assert b["questions"] == 0


async def test_the_banner_is_absent_on_past_days(phase, api, clock, model):
    await two_c_weeks(phase, api, clock, model)

    assert banner(phase, "2026-12-06") is None


async def test_the_banner_goes_once_the_proposal_is_decided(phase, api, clock, model, outbox):
    await two_c_weeks(phase, api, clock, model)
    await approve_tap(phase, outbox)

    assert banner(phase) is None


async def asked_about_a_partial_day(coach, api, clock) -> None:
    """Tue 10 Nov: 158 kcal logged, a suspected partial day; the evening asks about it (test_day_confirmation)."""
    log(api, "2026-11-10", 158)
    clock.current = evening("2026-11-10")
    await coach.run_due_jobs()


async def test_a_question_waiting_in_telegram_shows_the_banner(reverse, api, clock):
    await asked_about_a_partial_day(reverse, api, clock)

    assert banner(reverse) == {"proposal": None, "questions": 1}


async def test_an_answered_question_leaves_no_banner(reverse, api, clock, outbox):
    await asked_about_a_partial_day(reverse, api, clock)
    [card] = [s for s in outbox.sent if (s.ref or "").startswith("day-question:")]

    await reverse.on_button(card.buttons[0][0].action, card.buttons[0][0].ref_id)

    assert banner(reverse) is None
