# 15: Home: kcal per activity, a cleaner target line, Workouts layout

**What to build:** User feedback on the live Home (2026-11-11):

- **kcal on every activity line** (Workouts and Other activities): each session shows the kcal it adds to the day's target, e.g. "Push (2 PRs) · 06:32 · 64 min · 300 kcal" and "Run · 18:05 · 11.5 km · 5:23 /km · 390 kcal". This is the counted kcal (runs: Strava kcal × run discount; lifting and wrestling: their per-session values; extra sessions: reported or estimated), so the lines agree with the target line. A session that adds nothing (skipped, not counted) shows no kcal.
- **The target line, simpler:** `2,050 (base) + 600 (activity) + 250 (surplus) = 2,900` (each label in parentheses after its number; user, 2026-11-11).
  - **"activity"** is one number: workouts, other activities and steps ± together.
  - **The last part** reads "(surplus)" when positive, "(deficit)" when negative (shown as `− 250 (deficit)`), and is left out at 0 (maintenance).
  - **Before a phase:** no line.
  - **Look:** small and muted as before; thousands separators; the sum stays exact.
- **Workouts card layout,** top to bottom:
  1. the session lines (or "No workout");
  2. the 14-day strength graph, full width, with the rate number under it, not beside the session data;
  3. the "5 of 7 lifts progressing · 1 stall · 2 PRs" line.

**Blocked by:** 14 (merged)

**Status:** ready-for-agent

- [x] Read model: each session in `workouts` and `other_activities` carries `kcal_counted` (null when nothing is counted). The food build-up exposes `base`, `activity` (one total incl. steps ±), and `surplus` (signed), with a total equal to the target; schemas and examples updated
- [x] Tests through the Coach seam: kcal per session for lifting, a run (discounted), wrestling, an extra session and a skipped one; the build-up with surplus, a deficit, zero, and a below-goal steps day folded into activity
- [x] UI: kcal on each line; the new target line; the stacked Workouts layout. Build + phone and desktop screenshots (light and dark) in Comments

## Comments

- Build-up keys are now `base_kcal`, `activity_kcal` (sessions + step kcal ±; takes the rounding), `surplus_kcal` (signed), `total_kcal`. A negative activity (below the step goal, no session) reads `− 95 (activity)`; activity at 0 is left out like the surplus.
- Per-line kcal: `training_plan.counted_activity(..., refs=True)` tags each counted session with the line it comes from (Strava index, Hevy id, plan id, extra id); only the Home view asks for refs, so the weekly-facts shape is unchanged. Lines get null without a target (before a phase), when skipped, or when they count 0.
- Screenshots (phone only, light and dark, by the coordinator's request): /tmp/claude-1000/-home-debian-projects-fitness-aggregator/5741d455-db4e-4fd2-8a29-efc585325ab1/scratchpad/coach-web-notes/screenshots/15/
