# 05: Cut phase

**What to build:** Phase start accepts `cut`: `cut_level` (conservative 500 / moderate 750 default / aggressive 1000 with a warning) or `goal` {weight_kg|body_fat_pct, date} -> rate and deficit (cap 1000, warn past moderate, suggest the level); optional `end_date` (mini-cut). Start kcal = maintenance estimate - deficit (preview, confirm/change). Target rate = deficit x 7 / 7500; band = target x (1 +- 0.4). Weekly: on target -> hold; stalled + adherence -> 100-200 kcal less (carbs first; steps offered in text); stalled without adherence -> no change; too fast -> +100. Macros 2.5 g/kg protein, 0.6 g/kg fat floor. Week 1 not judged, no glycogen window. Reaching end_date asks to end the phase.

**Blocked by:** follow-ups 01, follow-ups 03, follow-ups 05

**Status:** ready-for-agent

- [x] Skill `phase-cut` params + schema finalized; validator green
- [x] Tests: start from level and from goal (cap, warning), band, the four weekly cases, macros, end_date
- [x] Phase start preview shows level, deficit, rate, band
- [x] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.

## Comments

- **Where it lives:** numbers in `fa_coach/cut.py` (`plan`, `apply`); the guard rule and the
  end-date job in `features/phase_cut.py` (registered on `weekly_checkin.phase_expected_change`,
  the hook from 06). Small hooks: `phases.params_for` applies the setup's `deficit_kcal`
  (deficit and band); `phase_start` takes the cut keys, computes the plan at `start_phase` and
  adds the cut lines to the card; `weekly_facts` leaves `unjudged_weeks` unjudged;
  `proposals` maps the cut's scenarios and its fixed increase step.
- **Deficit stored, not recomputed:** `start_phase` stores the derived `deficit_kcal` in the
  setup (a start key, code-only), so preview, confirm, band and targets agree even if confirm
  comes a day later.
- **Goal body fat** needs the current body fat: `goal` = {body_fat_pct, current_body_fat_pct,
  date} (ticket 04's estimates weren't available yet). Goal weight = same lean mass at the goal
  body fat. The needed deficit is rounded to 10 kcal.
- **Level and goal both given:** the level decides the deficit; the goal is shown against it.
- **Too fast:** `decisions.increase_step_kcal: 100` (phase override, phase_params schema) fixes
  every increase in a cut; stalled keeps the core small/large (100/200) by the distance.
- **Week 1:** new phase param `unjudged_weeks` (cut: 1): vs_band `not_evaluated`, no glycogen
  window; the week still counts (code direction hold), no new skip reason. The web's weight
  views treat `unjudged_weeks` like the glycogen window (review fixes, `web_weight.Bands`).
- **Fat:** the cut fixes fat at 0.6 g/kg (min = max = start), so phase start doesn't ask for
  it (generic: any phase with min = max).
- **End date:** from the day after `end_date`, at 09:00 or later, the end card is sent once per
  end date; `end_date` can be moved during the phase, level and goal can't.
- **Draft test:** with no draft phase left, `test_a_draft_phase_...` uses a copied package
  with the cut marked draft.
