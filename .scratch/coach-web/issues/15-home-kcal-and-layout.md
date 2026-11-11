# 15: Home: kcal per activity, a cleaner target line, Workouts layout

**What to build:** User feedback on the live Home (2026-11-11):

- **kcal on every activity line** (Workouts and Other activities): each session shows the kcal it adds to the day's target, e.g. "Push (2 PRs) · 06:32 · 64 min · 300 kcal" and "Run · 18:05 · 11.5 km · 5:23 /km · 390 kcal". This is the counted kcal (runs: Strava kcal × run discount; lifting and wrestling: their per-session values; extra sessions: reported or estimated), so the lines agree with the target line. A session that adds nothing (skipped, not counted) shows no kcal.
- **The target line, simpler:** `2,050 base + 600 activity + 250 surplus = 2,900`.
  - **"activity"** is one number: workouts, other activities and steps ± together.
  - **The last part** reads "surplus" when positive, "deficit" when negative (shown as `− 250 deficit`), and is left out at 0 (maintenance).
  - **Before a phase:** no line.
  - **Look:** small and muted as before; thousands separators; the sum stays exact.
- **Workouts card layout,** top to bottom:
  1. the session lines (or "No workout");
  2. the 14-day strength graph, full width, with the rate number under it, not beside the session data;
  3. the "5 of 7 lifts progressing · 1 stall · 2 PRs" line.

**Blocked by:** 14 (merged)

**Status:** ready-for-agent

- [ ] Read model: each session in `workouts` and `other_activities` carries `kcal_counted` (null when nothing is counted). The food build-up exposes `base`, `activity` (one total incl. steps ±), and `surplus` (signed), with a total equal to the target; schemas and examples updated
- [ ] Tests through the Coach seam: kcal per session for lifting, a run (discounted), wrestling, an extra session and a skipped one; the build-up with surplus, a deficit, zero, and a below-goal steps day folded into activity
- [ ] UI: kcal on each line; the new target line; the stacked Workouts layout. Build + phone and desktop screenshots (light and dark) in Comments
