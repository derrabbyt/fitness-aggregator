"""Reviews and body-fat estimates (coach-reviews ticket 01): a review (block,
phase or photo) is stored and sent in Telegram once per key; the Week page
lists the reviews sent in its week; Setup › Measurements lists the body-fat
estimates, the user's own winning for its date.

Uses the phase of test_weekly_checkin: the reverse starts Mon 9 Nov 2026,
Monday 09:00 check-ins, so check-in week W46 is 9-15 Nov and W47 16-22 Nov.
"""

import pytest

from fa_coach import body_fat, reviews, views
from test_weekly_checkin import at, phase  # noqa: F401


def block_review(coach, *, key: str = "1", text: str = "Block 1 went well.", now=None):
    p = coach.db.one("SELECT id FROM phases ORDER BY start_date DESC LIMIT 1")
    return reviews.send(coach, kind="block", key=key, phase_row_id=p["id"], period_start="2026-11-09",
                        period_end="2026-12-13", facts={"stalls": []}, text=text, now=now or at("2026-11-14", 10))


# --- send once ------------------------------------------------------------------------------


async def test_a_review_is_stored_and_sent_once_per_key(phase, outbox):
    first = block_review(phase)
    again = block_review(phase, text="Block 1, again.")

    assert first is not None and again is None
    assert outbox.texts == ["Block 1 went well."]
    assert reviews.sent(phase, "block", "1") and not reviews.sent(phase, "block", "2")
    assert not reviews.sent(phase, "phase", "1")  # keys are per kind
    stored = reviews.get(phase, first)
    assert (stored["kind"], stored["period_start"], stored["period_end"]) == ("block", "2026-11-09", "2026-12-13")
    assert (stored["facts"], stored["text"], stored["created_at"]) == (
        {"stalls": []}, "Block 1 went well.", "2026-11-14T10:00:00+01:00")


async def test_a_review_goes_out_even_when_the_days_message_limit_is_reached(phase, outbox, monkeypatch):
    monkeypatch.setattr(reviews.messaging, "limit", lambda coach: 0)
    assert block_review(phase) is not None
    assert outbox.texts == ["Block 1 went well."]


async def test_an_unknown_kind_is_refused(phase):
    with pytest.raises(ValueError):
        reviews.send(phase, kind="monthly", key="1", phase_row_id=None, period_start="2026-11-09",
                     period_end="2026-11-15", facts={}, text="x", now=at("2026-11-14"))


# --- Week page ------------------------------------------------------------------------------


async def test_the_week_lists_the_reviews_sent_in_it_oldest_first(phase, clock):
    block_review(phase, key="1", text="Block review.", now=at("2026-11-14", 10))
    reviews.send(phase, kind="photo", key="2026-11-15", phase_row_id=None, period_start="2026-11-15",
                 period_end="2026-11-15", facts={}, text="Photo review.", now=at("2026-11-15", 8))
    block_review(phase, key="2", text="Next week's.", now=at("2026-11-16", 10))
    clock.current = at("2026-11-18")

    w = phase.view("week", {"week": "2026-W46"})

    assert views.errors(phase, "week", w) == []
    assert [(r["kind"], r["title"], r["text"], r["sent_at"]) for r in w["reviews"]] == [
        ("block", "Block review", "Block review.", "2026-11-14T10:00:00+01:00"),
        ("photo", "Photo review", "Photo review.", "2026-11-15T08:00:00+01:00"),
    ]
    assert (w["reviews"][0]["period_start"], w["reviews"][0]["period_end"]) == ("2026-11-09", "2026-12-13")
    assert [r["text"] for r in phase.view("week", {})["reviews"]] == ["Next week's."]  # the week in progress


async def test_a_week_without_reviews_lists_none(phase, clock):
    clock.current = at("2026-11-18")
    assert phase.view("week", {"week": "2026-W46"})["reviews"] == []


# --- Setup › Measurements -------------------------------------------------------------------


async def test_measurements_list_body_fat_estimates_newest_first_the_users_winning_for_its_date(phase, clock):
    review = block_review(phase)
    body_fat.add(phase, "2026-11-09", 19.5, "model", at("2026-11-09", 10), review_id=review)
    body_fat.add(phase, "2026-11-23", 21.0, "model", at("2026-11-23", 10))
    body_fat.add(phase, "2026-11-23", 20.0, "user", at("2026-11-23", 12))
    body_fat.add(phase, "2026-11-23", 22.5, "model", at("2026-11-23", 14))  # a later model estimate doesn't win
    clock.current = at("2026-11-24")

    m = phase.view("setup/measurements")

    assert views.errors(phase, "setup/measurements", m) == []
    assert m["body_fat"] == [
        {"date": "2026-11-23", "pct": 20.0, "source": "user", "model_pct": 22.5},
        {"date": "2026-11-09", "pct": 19.5, "source": "model", "model_pct": None},
    ]
    assert body_fat.on(phase, "2026-11-23") == {"date": "2026-11-23", "pct": 20.0, "source": "user",
                                                "model_pct": 22.5}
    assert body_fat.on(phase, "2026-11-10") is None


@pytest.mark.parametrize("pct, source", [(2, "user"), (51, "model"), (20, "guess")])
async def test_a_body_fat_estimate_out_of_range_or_from_an_unknown_source_is_refused(phase, pct, source):
    with pytest.raises(ValueError):
        body_fat.add(phase, "2026-11-23", pct, source, at("2026-11-23"))
    assert body_fat.estimates(phase) == []
