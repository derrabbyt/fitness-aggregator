"""The weekly decision guard: code derives the direction (increase below the
band, decrease above it, hold in it) and the step size (small within
`far_off_margin_kg_per_week` of the band edge, large beyond) from the week's
facts and corrects the model's verdict when it disagrees.

Week 3 of the worked example (test_weekly_checkin): band 0.1-0.3 kg/week,
upper limit 0.5, margin 0.1, steps 100 / 200 kcal. Week 2 averages 81.8 kg, so
week 3's average sets the rate: 82.0 -> +0.2 (in band), 81.85 -> +0.05
(0.05 below: small increase), 81.6 -> -0.2 (0.3 below: large increase),
82.15 -> +0.35 (0.05 above: small decrease).
"""

from fa_coach.features import weekly_checkin
from test_weekly_checkin import check_in, decision_requests, fill_week, phase, three_weeks, verdict  # noqa: F401


def change(delta: int, size: str = "small") -> dict:
    return {"type": "calorie_change", "delta_kcal": delta, "size": size, "reason": "the trend",
            "is_phase_first_change": False, "returning_rejected_proposal_id": None}


async def week3(phase, api, clock, model, avg: float, **kwargs) -> dict:
    await three_weeks(phase, api, clock, model, avg=avg)
    await check_in(phase, clock, model, "2026-11-30", verdict("2026-W48", **kwargs))
    return weekly_checkin.stored(phase, "2026-W48")


async def test_an_increase_in_the_band_becomes_a_hold(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 82.0, scenario="C", direction="increase", proposal=change(100))

    assert decision_requests(model)[-1].input["weight"]["vs_band"] == "in_band"
    v = stored["verdict"]
    assert (v["direction"], v["proposal"]) == ("hold", None)
    assert stored["code_adjustments"] == [
        "direction increase -> hold (the trend +0.20 kg/week is in the band 0.1 to 0.3)",
        "proposal +100 kcal dropped (the trend calls for no change)"]
    assert model.requests[-1].input["verdict"] == v  # the report gets code's verdict


async def test_a_decrease_below_the_band_becomes_a_hold(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 81.85, scenario="E", direction="decrease", proposal=change(-100))

    v = stored["verdict"]
    assert (v["direction"], v["proposal"]) == ("hold", None)
    assert stored["code_adjustments"] == [
        "direction decrease -> hold (the trend +0.05 kg/week is 0.05 below the band 0.1 to 0.3)",
        "proposal -100 kcal dropped (the trend calls for an increase)"]


async def test_a_large_step_just_below_the_band_becomes_the_small_one(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 81.85, scenario="C", direction="increase",
                         proposal=change(200, "large"))

    v = stored["verdict"]
    assert v["direction"] == "increase"
    assert (v["proposal"]["delta_kcal"], v["proposal"]["size"]) == (100, "small")
    assert stored["code_adjustments"] == [
        "proposal +200 -> +100 kcal (the small step: the trend +0.05 kg/week is 0.05 below the band 0.1 to 0.3)",
        "proposal size large -> small"]


async def test_a_small_step_far_below_the_band_becomes_the_large_one(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 81.6, scenario="C", direction="increase", proposal=change(100))

    p = stored["verdict"]["proposal"]
    assert (p["delta_kcal"], p["size"]) == (200, "large")
    assert stored["code_adjustments"][0].startswith("proposal +100 -> +200 kcal (the large step: the trend "
                                                    "-0.20 kg/week is 0.30 below")


async def test_a_verdict_that_matches_the_trend_is_unchanged(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 82.15, scenario="E", direction="decrease",
                         proposal=change(-110))  # within the step tolerance

    assert decision_requests(model)[-1].input["weight"]["vs_band"] == "above_band"
    v = stored["verdict"]
    assert (v["direction"], v["proposal"]["delta_kcal"], v["proposal"]["size"]) == ("decrease", -110, "small")
    assert stored["code_adjustments"] == []


async def test_a_hold_is_untouched_even_below_the_band(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 81.6, scenario="B", direction="hold")  # RB-B: strength gains

    assert stored["verdict"]["direction"] == "hold" and stored["code_adjustments"] == []


async def test_a_skipped_week_is_untouched(phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 82.0, scenario="unusable", usable=False, direction="increase")

    assert stored["verdict"]["direction"] == "increase" and stored["code_adjustments"] == []
    assert (stored["counts_for_confirmation"], stored["skip_reason"]) == (False, "unusable")


async def test_the_streak_counts_codes_direction(phase, api, clock, model):
    await week3(phase, api, clock, model, 82.0, scenario="C", direction="increase")  # in band: code holds
    fill_week(api, 4, avg=82.05)  # +0.05: below the band
    await check_in(phase, clock, model, "2026-12-07", verdict("2026-W49", scenario="C", direction="increase"))
    fill_week(api, 5, avg=82.1)
    await check_in(phase, clock, model, "2026-12-14", verdict("2026-W50", scenario="C", direction="increase"))

    history = decision_requests(model)[-1].input["history"]
    assert [(v["iso_week"], v["direction"]) for v in history["previous_verdicts"][:2]] == [
        ("2026-W49", "increase"), ("2026-W48", "hold")]
    assert history["confirmation_streaks"] == {"increase": 1, "decrease": 0}


async def test_a_hold_below_the_band_is_stored_with_codes_direction_and_counts_toward_the_streak(
        phase, api, clock, model):
    stored = await week3(phase, api, clock, model, 81.85, scenario="B", direction="hold")  # 0.05 below the band

    assert (stored["verdict"]["direction"], stored["verdict"]["proposal"]) == ("hold", None)
    assert stored["direction"] == "increase" and stored["code_adjustments"] == []
    fill_week(api, 4, avg=81.9)  # +0.05: still below the band
    await check_in(phase, clock, model, "2026-12-07", verdict("2026-W49", scenario="C", direction="increase"))

    history = decision_requests(model)[-1].input["history"]
    assert history["previous_verdicts"][0]["direction"] == "increase"
    assert history["confirmation_streaks"] == {"increase": 1, "decrease": 0}
