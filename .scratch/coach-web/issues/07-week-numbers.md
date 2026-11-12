# 07: Week: numbers

**What to build:** The Week page's numbers: a weight block (trend vs the target band, weekly rate, weigh-in count), an intake block (each day eaten vs target, weekly average, adherence result, macros vs targets), a training block (lifts progressing, stalls, PRs, sessions done vs planned, steps per day) and a notes and flags block (context notes of the week, flags, deferred items, what's due next week).

**Blocked by:** 06

**Status:** ready-for-agent

- [x] Read model and schema extended; tests cover each block for a finished and an in-progress week, partial days marked, flags present / absent
- [x] UI blocks; build + screenshots in Comments; tests green

## Decisions

- **Default week (orchestrator, 2026-11-11):** on the check-in day and the day after, the Week tab opens on the week just judged (so the new decision is the first thing seen); otherwise on the week in progress. Change the `week` default in ticket 06's read model accordingly and test it.

## Comments

- **Default week (the Decision):** `web_week.resolve` without `?week=` opens the week just judged on the check-in day and the day after (once its check-in has run, ok or failed); otherwise the week in progress. Without a check-in day nothing changes. Two of ticket 06's tests moved their clock / asked for W50 explicitly; two new tests cover the default (Mon 10:00 and Tue 23:00 → W48, Wed 00:00 → W49; before the 09:00 check-in → the week in progress).
- **Read model:** four parts of `week` in `coach/src/fa_coach/features/web_week_numbers.py`, schemas `web_week_weight|intake|training|notes.schema.json` (+ examples). `source: check_in` reads the stored weekly facts and verdict (what the coach judged); any other week inside a phase is `so_far`, computed by the same code as the facts (`weekdata.intake`/`intake_summary`, `weekly_facts._intake`, `progression.week`) over the days up to today. All four are null when no phase was active during the week (and it wasn't judged). `web_week._phase_during` became public `phase_during`.
  - **Weight:** trend, previous trend, rate, band, vs_band, weigh-ins of the days so far (+ needed), and a chart series from the day before the week (where the rate starts) with the band corridor rising from that day's trend (null corridor when not judged). Decision: a week in progress shows the rolling 7-day rate ending today (`rate_window: last_7_days`, Home's number) rather than a part-week rate.
  - **Intake:** each day eaten vs target with `logged` complete/partial/missing; average eaten and target over the complete days; adherence pass/fail from the check-in, `not_judged` so far; macros a day vs the week's average targets; fiber as Home's whole-gram range. Decision: today is never partial (as on Home's food).
  - **Training:** lifts progressing of counted, stalls and PRs by name, deload signal (null without tracked lifts); sessions done (counted sessions, planned wrestling included) vs planned (non-optional plan sessions, all 7 days) and skipped; steps per day (Home's tracked rule), average, days at the current goal.
  - **Notes:** context notes (live), the verdict's flags (null until judged, `[]` when judged without), deferred items (`messaging.deferred`), due next week (`measurements.measurements_due`, the 7 days after the week).
- **Tests:** `coach/tests/test_web_week_numbers.py` (11, through the Coach seam): weight judged / so far; intake judged, a partial day in a judged week (marked, out of average and adherence), so far with today not partial; training judged (TWO_WEEKS lifts in W47: 2 of 3, Squat stalled, 3 PRs, 3 done of 8 planned) / so far / no lifts; notes judged with flags, deferred item and due measurements, in progress (flags null) and judged without flags; a week before any phase (all null). Deviation from strict red-first: each block's first test went red, then the implementation; the follow-up tests for the same block passed on their first run.
- **UI:** `web/src/app/pages/week/blocks/` (`week-weight-block`, `week-intake-block`, `week-training-block`, `week-notes-block`), registered in `WEEK_BLOCKS`, types in `week.types.ts`. Weight reuses ticket 03's `WeightChart`; steps use the shared `ColumnChart` (all 7 days, days to come as stubs); macros as on Home. Colour only for verdicts: rate vs band, adherence pass/fail, macros, steps at goal, stalls, weigh-ins too few to make up, flag severity dots.
- **Screenshots** (`/tmp/claude-1000/-home-debian-projects-fitness-aggregator/5741d455-db4e-4fd2-8a29-efc585325ab1/scratchpad/coach-web-notes/screenshots/07/`; fixtures validated per part, tooling in `scratchpad/shots07/`, phone shots on a 390×2700 viewport so the whole page shows): phone `-light`/`-dark`: `phone-week-decided-open`, `phone-week-decided-hold`, `phone-week-decided-unusable`, `phone-week-progress`, `phone-week-none`; desktop (1280×1500) `-light`/`-dark`: `desktop-week-decided-open`, `desktop-week-progress`, `desktop-week-decided-unusable`.
