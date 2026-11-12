# 06: Maintenance phase (small)

**What to build:** Phase start accepts `maintenance`: start kcal = maintenance estimate. Band +-0.1 kg/wk; drift beyond +-0.2 kg/wk for 2 confirming weeks -> `small_step_kcal` toward flat. Macros as the bulk's. Keep it minimal.

**Blocked by:** follow-ups 01, follow-ups 05

**Status:** ready-for-agent

- [x] Skill params finalized; validator green
- [x] Tests: flat holds, drift for 2 weeks proposes
- [x] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.

## Comments

- Start: no new code. `start.surplus_kcal: 0` already makes `phases.preview` start at the maintenance estimate; removing `draft` lets phase start accept it. `starting_calories_kcal` is still asked (a phase-start key for every phase), but unused.
- Weekly decision: a phase-specific guard rule. `weekly_checkin.phase_expected_change[phase_id]` replaces `expected_change` for that phase (used by `apply_band_rules` and `streak_direction`); `features/maintenance.py` registers maintenance's: hold inside the ±0.2 limits (small drift ±0.1–0.2 is stored as hold, so it counts for no streak), beyond them always `small_step_kcal` toward flat.
- Confirmation: the core's `decisions.confirmation_weeks` (2), no fast lane. Dropped `drift_threshold_kg_per_week` / `drift_confirmation_weeks` from params (the limits and the core value say the same).
- Not added to `proposals.SCENARIO_DIRECTION`: its band-distance step check would call a 0.15 kg/week overshoot "large"; the guard in `weekly_checkin` already fixes the size. So `_size_or_direction` skips maintenance (as before).
- Macros: same values as the bulk's; the TO DECIDE marks are gone.
- Tests: `coach/tests/test_maintenance_phase.py` (start at the estimate; flat and small drift hold; one drifting week isn't enough; two drifting weeks propose −100).
