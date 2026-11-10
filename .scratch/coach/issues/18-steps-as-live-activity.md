# 18: Steps as live activity with a step goal

**What to build:** Steps move each day's target, measured against a step goal (user decision, 2026-11-10). Base is shown "at the step goal"; every day gets `step kcal × (today's steps − goal)` on top, with run steps removed. The math stays anchored to the measured maintenance, so the step goal only moves where "0" is shown, not how much energy the user gets. A `/today` command shows the live balance.

**Blocked by:** 17

**Status:** resolved

- [x] New setup value `step_goal` (default 10,000; changeable in chat via `record_setup_value`, not a calibration proposal) and core params: `steps.kcal_per_step_at_70kg: 0.04`, `steps.share: 0.75`, `steps.not_tracked_below: 2500`, `steps.run_steps_per_km: 1200` (schema, params, README assumption rows; validator green)
- [x] `k = kcal_per_step_at_70kg × trend weight / 70 × share`. Day steps for targets = MFP steps − Strava run distance × `run_steps_per_km` (floor 0). A day under `not_tracked_below` raw steps counts as not tracked: no step adjustment, and it's left out of averages
- [x] Base at goal = maintenance estimate − average counted sessions − k × (average day steps − goal), over the same window as the maintenance estimate. Daily target = base at goal + k × (day steps − goal) + counted sessions + surplus. On an average-steps day this equals the current formula (test it)
- [x] Runs stay separate (Strava kcal × run discount); their steps never count twice. Other reported sessions with distance (walks, hikes) also remove their steps if a distance is known
- [x] **MFP goal = base at average steps + surplus** (= base at goal + k × (average day steps − goal) + surplus): a normal-step rest day. This refines ticket 17's "base + surplus"; macros at that kcal
- [x] `/today` (and a chat read tool for the same view): syncs first, then shows steps / goal and steps to go, step kcal so far vs goal (labelled "so far"; today is provisional until the day ends), the target build-up (base at goal, steps, each session, surplus), eaten and left. Past days use final steps
- [x] Daily facts, weekly facts (intake vs target, adherence), the evening recap and the phase-start preview use step-adjusted targets; schemas and skills (coach-core, evening-recap, weekly-report, phase-start, coach-chat, TOOLS.md) explain base at goal and step kcal. The soft step-floor note stays as it is
- [x] Tests: a day at goal, above and below goal, a not-tracked day (1,800 steps), a run day with run steps removed, base at goal vs current formula on an average day, the MFP goal value, `/today` output, and `step_goal` changed in chat

## Comments

- **Stored model:** each targets row keeps base maintenance at the average day steps (as before) plus `step_kcal_per_step` (k) and `avg_day_steps` (migration `18_steps.sql`). Base at goal = base − k × (average − goal) is computed live with the current `step_goal`, so changing the goal in chat changes no day's target and needs no new targets row. Calorie and calibration changes carry k and the average over. Rows without them (older rows, or no tracked day in the window) get no step adjustment.
- **k is fixed per targets row** at the trend weight used for its base (the starting trend weight at phase start), not recomputed daily, so an average-steps day stays exactly base + sessions + surplus.
- **Not-tracked day = counted at the average** (target = base + sessions + surplus), not "step kcal 0 vs the goal". Conservative reading that keeps "the step goal doesn't change the energy" true on such days.
- **Reported distance:** `set_session_status` takes an optional `distance_km` (new column on `session_statuses`); done/extra sessions with a distance remove distance × `run_steps_per_km` steps, except a planned run marked done on a day Strava already synced (no double removal).
- `steps.step_goal` (10,000) is a core-param default that the setup value `step_goal` overrides. New skill rule ids: CORE-STEPS, CC-TODAY.
- Daily facts get `day.target_build_up`; weekly facts `targets` get `step_goal`, `avg_day_steps`, `step_kcal_per_1000_steps`, `base_at_step_goal_kcal`. The preview's day-type targets are at average steps; the card adds base at the step goal and kcal per 1,000 steps.
