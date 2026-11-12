"""Photo review and body-fat estimates (coach-reviews ticket 04): once a photo
set has arrived (no new photo for a few minutes), the model gets the set and
the most recent earlier set at similar leanness (its estimate within +-2 % of
the latest estimate before the new set; else the phase start set) as images,
plus the waist trend, and estimates body fat. Code stores the estimate
(source model; the user's own, chat tool `record_body_fat`, wins for its
date), sends the review once, and in a bulk advises a mini-cut or ending the
bulk at `body_fat.advise_near_pct` (23 %), at most once per 4 weeks.

The reverse starts Mon 9 Nov 2026 (test_measurements' `activate`); photo
sets are due every 2 weeks on Mondays: 9 Nov, 23 Nov, 7 Dec, 21 Dec, ...
"""

import json

from fa_coach import body_fat, reviews, weekly_facts
from fa_coach.ports import ModelError
from fakes import reply, reply_json, tool_call
from test_measurements import activate as activate_reverse
from test_measurements import at
from test_weekly_checkin import phase  # noqa: F401


def activate(coach, **changes) -> None:
    """The reverse with 12-week blocks: no block review (ticket 02) within these tests' dates."""
    activate_reverse(coach, **{"block_weeks": 12, **changes})


def review_json(day: str, low: float, high: float, *, compared: str | None = None,
                notes: str = "Looks a bit leaner around the waist.") -> dict:
    return {"schema_version": 1, "date": day, "photo_set_id": day, "previous_photo_set_id": compared,
            "comparability": "good" if compared else "no_previous", "comparability_issues": [],
            "change_vs_previous": "leaner" if compared else "not_comparable",
            "bf_estimate": {"low_pct": low, "high_pct": high}, "confidence": "medium", "notes": notes}


async def send_set(coach, day: str, *photos: bytes) -> None:
    for n, data in enumerate(photos or (b"front-" + day.encode(), b"side-" + day.encode())):
        await coach.on_photo(data, None, at(day, 7, 30 + n))


def photo_requests(model) -> list:
    return [r for r in model.requests if r.task_skills == ("photo-review",)]


def review_texts(coach) -> list[str]:
    return [r["text"] for r in reviews.sent_between(coach, at("2026-01-01").date(), at("2027-12-31").date())]


async def reviewed_set(coach, model, day: str, low: float, high: float, compared: str | None = None) -> None:
    await send_set(coach, day)
    model.script(reply_json(review_json(day, low, high, compared=compared)))
    await coach.run_due_jobs(at(day, 8))


# --- the review --------------------------------------------------------------------------------


async def test_a_set_is_reviewed_once_it_has_arrived_with_its_images(coach, model, outbox):
    activate(coach)
    await send_set(coach, "2026-11-09", b"front", b"side")
    await coach.run_due_jobs(at("2026-11-09", 7, 33))  # still arriving: not yet
    assert photo_requests(model) == []

    model.script(reply_json(review_json("2026-11-09", 18, 20)))
    await coach.run_due_jobs(at("2026-11-09", 8))
    await coach.run_due_jobs(at("2026-11-09", 9))  # once

    [request] = photo_requests(model)
    assert request.decision and request.output_schema == "photo_review"
    assert [(i.label, i.data) for i in request.images] == [
        ("New set 2026-11-09, photo 1", b"front"), ("New set 2026-11-09, photo 2", b"side")]
    assert request.input["photo_set"] == {"id": "2026-11-09", "date": "2026-11-09", "photos": 2, "phase_week": 1}
    assert request.input["comparison_set"] is None
    assert body_fat.on(coach, "2026-11-09") == {"date": "2026-11-09", "pct": 19.0, "source": "model",
                                                "model_pct": None}
    [text] = review_texts(coach)
    assert "Looks a bit leaner" in text and "18–20 %" in text
    assert outbox.texts[-1] == text


async def test_the_comparison_is_the_latest_set_at_similar_leanness(coach, model, clock):
    """Start set 12 %, 23 Nov 14.5 %, 7 Dec 18 %; the user says 14 % on 14 Dec. The 21 Dec set is
    compared with 23 Nov (within 2 %), not the newer but softer 7 Dec set."""
    activate(coach)
    await reviewed_set(coach, model, "2026-11-09", 11, 13)
    await reviewed_set(coach, model, "2026-11-23", 14, 15, compared="2026-11-09")
    await reviewed_set(coach, model, "2026-12-07", 17, 19, compared="2026-11-23")
    model.script(tool_call("record_body_fat", pct=14, date="2026-12-14"), reply("Noted, 14 %."))
    await coach.on_message("I think I'm at 14% body fat", at("2026-12-14", 12))

    await reviewed_set(coach, model, "2026-12-21", 14, 16, compared="2026-11-23")

    request = photo_requests(model)[-1]
    assert request.input["comparison_set"] == {
        "id": "2026-11-23", "date": "2026-11-23", "photos": 2, "picked": "similar_leanness",
        "estimate": {"date": "2026-11-23", "pct": 14.5, "source": "model", "model_pct": None}}
    assert request.input["previous_estimate"]["pct"] == 14
    assert [i.label for i in request.images] == [
        "New set 2026-12-21, photo 1", "New set 2026-12-21, photo 2",
        "Comparison set 2026-11-23, photo 1", "Comparison set 2026-11-23, photo 2"]
    assert request.images[2].data == b"front-2026-11-23"
    assert "compared with the 2026-11-23 set" in review_texts(coach)[-1]


async def test_without_a_set_at_similar_leanness_the_phase_start_set_is_the_comparison(coach, model):
    activate(coach)
    await reviewed_set(coach, model, "2026-11-09", 11, 13)
    await reviewed_set(coach, model, "2026-11-23", 14, 15, compared="2026-11-09")
    model.script(tool_call("record_body_fat", pct=20), reply("Noted."))
    await coach.on_message("I'd say 20 % now", at("2026-12-06", 12))

    await reviewed_set(coach, model, "2026-12-07", 19, 21, compared="2026-11-09")

    compared = photo_requests(model)[-1].input["comparison_set"]
    assert (compared["date"], compared["picked"]) == ("2026-11-09", "phase_start")


async def test_the_users_estimate_wins_for_its_date_over_the_photo_estimate(coach, model):
    activate(coach)
    await reviewed_set(coach, model, "2026-11-23", 17, 19)

    model.script(tool_call("record_body_fat", pct=16.5, date="2026-11-23"), reply("Noted."))
    await coach.on_message("those photos were 16.5 % I think", at("2026-11-23", 12))

    [result] = model.results(len(model.requests) - 2)
    assert result.content == {"recorded": {"date": "2026-11-23", "pct": 16.5}, "photo_estimate_pct": 18.0,
                              "advice_sent": False}
    assert body_fat.on(coach, "2026-11-23")["pct"] == 16.5


async def test_record_body_fat_refuses_an_implausible_value_or_a_future_date(coach, model):
    activate(coach)
    model.script(tool_call("record_body_fat", pct=70), tool_call("record_body_fat", pct=15, date="2026-11-10"),
                 reply("?"))
    await coach.on_message("70 %", at("2026-11-09", 12))

    assert model.results(0)[0].is_error and model.results(1)[0].is_error
    assert body_fat.estimates(coach) == []


# --- when there is no review ---------------------------------------------------------------


async def test_no_review_with_photos_off_without_a_phase_or_for_an_old_set(coach, model, outbox):
    await send_set(coach, "2026-11-09")  # no phase yet
    await coach.run_due_jobs(at("2026-11-09", 8))
    activate(coach, photos_enabled=False)
    await send_set(coach, "2026-11-23")
    await coach.run_due_jobs(at("2026-11-23", 8))
    coach.db.execute("UPDATE phases SET setup = json_set(setup, '$.photos_enabled', json('true'))")
    await coach.run_due_jobs(at("2026-11-26", 8))  # the 23 Nov set is too old by now

    assert photo_requests(model) == []
    assert review_texts(coach) == []


async def test_a_model_failure_sends_nothing_and_is_not_retried(coach, model, outbox):
    activate(coach)
    await send_set(coach, "2026-11-09")
    model.script(ModelError("connection failed"))
    await coach.run_due_jobs(at("2026-11-09", 8))
    await coach.run_due_jobs(at("2026-11-09", 9))

    assert len(photo_requests(model)) == 1
    assert review_texts(coach) == [] and body_fat.estimates(coach) == []


# --- advice --------------------------------------------------------------------------------


def advice(outbox) -> list[str]:
    return [t for t in outbox.texts if t.startswith("🧭")]


async def test_in_a_bulk_an_estimate_at_23_percent_advises_at_most_once_per_4_weeks(coach, model, outbox):
    activate(coach)
    await reviewed_set(coach, model, "2026-11-09", 21, 22)  # 21.5: below
    assert advice(outbox) == []

    await reviewed_set(coach, model, "2026-11-23", 22, 24)  # 23
    [first] = advice(outbox)
    assert "23 %" in first and "mini-cut" in first and "advice, not a stop" in first

    await reviewed_set(coach, model, "2026-12-07", 23, 25)  # 2 weeks later: not again
    model.script(tool_call("record_body_fat", pct=24), reply("Noted."))
    await coach.on_message("24 % I'd say", at("2026-12-20", 12))
    assert len(advice(outbox)) == 1

    await reviewed_set(coach, model, "2026-12-21", 23, 25)  # 4 weeks after the first
    assert len(advice(outbox)) == 2


async def test_the_users_estimate_below_the_level_holds_the_advice_back(coach, model, outbox):
    activate(coach)
    model.script(tool_call("record_body_fat", pct=21, date="2026-11-23"), reply("Noted."))
    await coach.on_message("21 % today", at("2026-11-23", 7))

    await reviewed_set(coach, model, "2026-11-23", 23, 24)

    assert body_fat.on(coach, "2026-11-23")["pct"] == 21
    assert advice(outbox) == []


async def test_the_weekly_facts_carry_the_latest_estimate_up_to_the_weeks_end(phase):
    """With the phase of test_weekly_checkin (reverse from Mon 9 Nov)."""
    body_fat.add(phase, "2026-11-09", 19.5, "model", at("2026-11-09", 8))
    body_fat.add(phase, "2026-11-12", 18.0, "user", at("2026-11-12", 8))
    body_fat.add(phase, "2026-11-23", 20.0, "model", at("2026-11-23", 8))

    facts = weekly_facts.compute(phase, at("2026-11-15").date(), at("2026-11-16"))

    assert facts["measurements"]["latest_bf_estimate"] == {"low_pct": 18.0, "high_pct": 18.0, "source": "user",
                                                           "date": "2026-11-12"}
    assert phase.skills.errors(facts, "weekly_facts") == []


async def test_no_advice_outside_a_bulk(coach, model, outbox):
    activate(coach)
    coach.db.execute("UPDATE phases SET phase_id = 'cut'")
    await reviewed_set(coach, model, "2026-11-09", 24, 26)

    assert len(review_texts(coach)) == 1 and advice(outbox) == []
