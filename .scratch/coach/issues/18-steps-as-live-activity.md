# 18: Steps as live activity with a step goal

**What to build:** Steps move each day's target, measured against a step goal (user decision, 2026-11-10). Base is shown "at the step goal"; every day gets `step kcal × (today's steps − goal)` on top, with run steps removed. The math stays anchored to the measured maintenance, so the step goal only moves where "0" is shown, not how much energy the user gets. A `/today` command shows the live balance.

**Blocked by:** 17

**Status:** ready-for-agent

- [ ] New setup value `step_goal` (default 10,000; changeable in chat via `record_setup_value`, not a calibration proposal) and core params: `steps.kcal_per_step_at_70kg: 0.04`, `steps.share: 0.75`, `steps.not_tracked_below: 2500`, `steps.run_steps_per_km: 1200` (schema, params, README assumption rows; validator green)
- [ ] `k = kcal_per_step_at_70kg × trend weight / 70 × share`. Day steps for targets = MFP steps − Strava run distance × `run_steps_per_km` (floor 0). A day under `not_tracked_below` raw steps counts as not tracked: no step adjustment, and it's left out of averages
- [ ] Base at goal = maintenance estimate − average counted sessions − k × (average day steps − goal), over the same window as the maintenance estimate. Daily target = base at goal + k × (day steps − goal) + counted sessions + surplus. On an average-steps day this equals the current formula (test it)
- [ ] Runs stay separate (Strava kcal × run discount); their steps never count twice. Other reported sessions with distance (walks, hikes) also remove their steps if a distance is known
- [ ] **MFP goal = base at average steps + surplus** (= base at goal + k × (average day steps − goal) + surplus): a normal-step rest day. This refines ticket 17's "base + surplus"; macros at that kcal
- [ ] `/today` (and a chat read tool for the same view): syncs first, then shows steps / goal and steps to go, step kcal so far vs goal (labelled "so far"; today is provisional until the day ends), the target build-up (base at goal, steps, each session, surplus), eaten and left. Past days use final steps
- [ ] Daily facts, weekly facts (intake vs target, adherence), the evening recap and the phase-start preview use step-adjusted targets; schemas and skills (coach-core, evening-recap, weekly-report, phase-start, coach-chat, TOOLS.md) explain base at goal and step kcal. The soft step-floor note stays as it is
- [ ] Tests: a day at goal, above and below goal, a not-tracked day (1,800 steps), a run day with run steps removed, base at goal vs current formula on an average day, the MFP goal value, `/today` output, and `step_goal` changed in chat
