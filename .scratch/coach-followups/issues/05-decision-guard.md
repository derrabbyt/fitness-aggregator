# 05: Weekly change direction and size in code

**What to build:** In `weekly_checkin.py` next to the sport-load hold: from `vs_band` and the distance to the band edge, code computes the expected direction (increase below, decrease above, hold in band) and step (`small_step_kcal` within `far_off_margin_kg_per_week` of the edge, `large_step_kcal` beyond). A proposed change with the wrong direction becomes a hold; with the wrong size gets the expected size; each correction goes into `code_adjustments`; the stored `direction` is code's. Holds and skipped weeks are untouched. Symmetric, so cut/maintenance can reuse it.

**Blocked by:** None

**Status:** ready-for-agent

- [x] Tests: wrong direction -> hold, wrong size -> corrected, correct verdict unchanged, hold untouched, streak uses code's direction
- [x] Skill text (weekly-decision / RB-SIZE) notes code enforces it
- [x] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- Code: `expected_change` and `apply_band_rules` in `features/weekly_checkin.py`, run in `_run` after
  WD-SPORT, only when `skip_reason` is None. Rule id `WD-GUARD` in the weekly-decision skill; RB-SIZE
  in phase-reverse-bulk points to it. Tests: `coach/tests/test_decision_guard.py`.
- "Proposes a change" = `direction` increase/decrease. A `hold` verdict is untouched entirely, even if
  it carries a proposal (`propose_change` still blocks that as `size_or_direction_mismatch`).
- `below_limit` counts as below the band, `above_limit` as above; distance is measured from the band
  edge (`low`/`high`). `not_evaluated` (or no rate) in a week that counts expects a hold.
- Far = distance `>=` `far_off_margin_kg_per_week` (as `proposals._size_or_direction`). A size within
  `proposals.STEP_TOLERANCE_KCAL` (±25) is kept; outside it, `delta_kcal` becomes ±step. The `size`
  label is corrected to small/large too (recorded). A phase's first change (`is_phase_first_change`)
  keeps its size (start range), only its direction is checked.
- A proposal whose sign disagrees with the trend is dropped; the verdict's direction stays when that
  matches the trend.
- Test data: the old worked example's weeks (+0.1 to +0.2 kg/week) were in the band, yet many tests
  had increase verdicts. `test_weekly_checkin.below_band` (fixture: W48+ gain 0.05/week) and
  explicit averages in `test_proposals.two_c_weeks` (`BELOW`, `ABOVE` for decreases) now give the
  trend each verdict claims. Guardrail tests that relied on the model's size reaching
  `propose_change` were rewritten: the max-change test uses a chat request (+300), a too-large
  verdict step is now opened at code's size, the scenario mismatch uses scenario A with an increase,
  and the web week's blocked-proposal example uses the lockout.
- `proposals._size_or_direction` is kept (scenario check; chat/user sources); for weekly verdicts
  its size branch is now normally redundant.
- **Review fixes:** for a week that counts, the stored `direction` (what streaks count) is always code's (`streak_direction`), even when the model holds; the hold stays a hold, no proposal is forced, no code adjustment is recorded. `stored()` returns it as `direction`. `expected_change` returns the size label too. Changed test: `test_proposals::test_a_change_the_scenario_doesnt_call_for_is_blocked` no longer expects `confirmation_not_met` (W49 and W50 are both below the band, so the streak is met).
