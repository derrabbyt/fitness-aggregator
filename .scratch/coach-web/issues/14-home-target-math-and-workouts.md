# 14: Home refinements: target math and the Workouts card

**What to build:** User feedback on the finished Home (2026-11-11).

**Food block:**
- A small line at the top shows how today's daily target is built, e.g. `base 2,050 · steps −95 · workouts +300 · activities +450 · surplus −250 = 2,455`.
  - "workouts" is the counted lifting kcal and "activities" is runs, wrestling and extra sessions. Fixed per-session values count too.
  - A part that is 0 is left out.
  - Before a phase there is no target, so no math line.
- The big numbers stay: kcal left, then "1,980 / 2,455" without the word "eaten".

**Workouts card** (renamed from Gym, always shown, also on days without a workout):
- **Session lines:** each lifting session on one line with its PRs in parentheses, e.g. "Push (2 PRs) · 06:32 · 64 min". With no workout that day, one quiet line says so ("No workout").
- **Chart:** the strength trend over the 14 days up to the shown day, styled like the weight card's 14-day line.
  - Each day's point is the mean, over the counting lifts trained in the 28 days before that day, of the lift's latest estimated 1RM as % of its value at the start of that 28-day window. Use the effective load for bodyweight lifts, and start from the latest baseline reset where a lift has one.
  - The line steps when sessions happen.
- **Beside the chart:** the progress rate in % per week, measured over the last 28 days, coloured like the weight rate: green when rising, neutral within the ±1 % band, red when falling.
- **Below the chart:** one line, "5 of 7 lifts progressing · 1 stall · 2 PRs". It covers the last 14 days, the same recency window the lift status uses (`lift_recency_days`).

**Unchanged:** Other activities keeps its session lines (distance, duration, pace for runs); its kcal appear in the food line's math. The Training tab's larger strength trend (ticket 08) should use the same computation when it resumes.

**Blocked by:** 03, 04, 05 (all merged)

**Status:** ready-for-agent

- [ ] **Read model:** the Home food part carries the target build-up (base at goal, steps, workouts, activities, surplus, total), as of the shown day and from the same code as the daily target. The math line adds up exactly to the target.
- [ ] **Read model:** the Home training part has `workouts` (sessions with PR counts, a 14-day strength series, a rate in % per week over 28 days, and the 14-day summary) and `other_activities`. Old fields are removed or renamed; schemas and examples are updated.
- [ ] **Tests through the Coach seam:**
  - the build-up for a rest day, a lifting day, a run plus wrestling day, a below-goal steps day and a not-tracked steps day;
  - the build-up before a phase;
  - PR counts per session;
  - the series and rate rising, flat and falling;
  - a reset lift;
  - a day with no workout;
  - a past day.
- [ ] **UI:**
  - food math line, small and muted, and no "eaten";
  - the Workouts card with session lines, the 14-day chart and the rate number, styled like the weight card;
  - the summary line below the chart;
  - the "No workout" state;
  - Other activities unchanged.
  Build plus phone and desktop screenshots (light and dark) in Comments.
- [ ] The strength-trend code is shared with ticket 08's larger chart (which is paused; note in 08's file what changed).
