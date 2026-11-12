# 03: Phase review

**What to build:** Every `phase_review_weeks` (10) from phase start and on phase end (follow-ups 01). Facts in code: weight vs band and time goal, strength trend, maintenance estimate, waist trend, body-fat estimates, calibration drift (run discount from Strava vs trend-implied activity; wrestling likewise). Drift beyond a threshold makes calibration proposals through the existing path. Skill `phase-review` writes it; after a phase end it asks what comes next.

**Blocked by:** 01, 04, follow-ups 01, follow-ups 03

**Status:** ready-for-agent

- [x] Schedule (10 weeks, on end) tests
- [x] Calibration drift -> proposal test
- [x] Skill + schema; validator green
- [ ] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.

## Comments

Built in `coach/src/fa_coach/features/phase_review.py` (tests: `coach/tests/test_phase_review.py`). No migration.

- **Schedule:** core param `reviews.phase_review_every_weeks: 10` (was the unused range
  `[8, 12]`; integer now). Job `phase-review` (order 61) reviews phase weeks 1..10n from
  the day after week 10n (key `"<phase id>:week-<10n>"`, period start..end of week 10n);
  only the latest due one (no backlog after a deploy).
- **On end:** `confirm_phase_end` (features/phase_end.py) calls `phase_review.review_end`
  after its edits (key `"<phase id>:end"`, the whole span, the ended phase's skill in the
  prefix). A failure there is logged and never undoes the end; the job catches up on any
  phase ended within the last 2 days (`END_CATCH_UP`, an assumption) without an end review,
  which also covers a phase ended by a new phase start. An erase gets no review.
- **Always one review:** like the block review, code sends its own short summary without a
  usable model answer (`fallback_text`).
- **Facts** (`phase_summary.schema.json`, rewritten; example added): weight trend start
  (day before the start) vs now, rate, the band in force, the weekly check-ins' `vs_band`
  counts; time goal (`time_goal_weeks`, a cut's `goal` / `end_date`); targets start vs now
  and their changes; maintenance estimate at start vs `weekly_facts.maintenance_base` now
  (renamed from `_maintenance`); lifts and strength trend over the phase via
  `block_review.lifts_over` (extracted from `block_review.facts`, same output); waist,
  body-fat estimates (`body_fat.estimates`, the user's winning), photo set and photo
  review counts. No images: the photo comparison is the photo reviews' estimates.
- **Calibration drift** (an assumption on the method; thresholds in `reviews.calibration`,
  marked as assumptions): per usable phase week (the maintenance estimate's rules via the new
  `phases.unusable_days`, so the glycogen window is out) the trend-implied expenditure
  (intake - weekly rate x kcal_per_kg / 7, lifting and other counted activity taken off) is
  regressed (least squares, intercept) on raw run kcal a day and wrestling sessions a day;
  the slopes are the implied discount and kcal per session. Judged only with `min_weeks` (6)
  usable weeks and enough spread between weeks (runs: stdev >= 50 kcal/day; wrestling:
  >= 0.5 sessions/week, so a fixed weekly schedule is never judged). Drifted: plausible
  (discount 0.2-1.0; wrestling 100-1500) and >= 0.15 / >= 150 kcal from the value in force.
  Suggested = implied, rounded to 0.05 / 25 kcal.
- **Proposals:** code (not the model) makes one `calibration_change` per drifted value
  through `proposals.propose` with the new source `phase_review` (proposal and web_week
  schemas, `week.types.ts`; the chat's `propose_change` still refuses it), only at scheduled
  reviews of the active phase; the review text goes out first, then each new open
  proposal's card (`features.proposals.send_card`). At a phase end the drift is reported
  for the next setup, no proposal.
- **What next:** `ask_what_next` = a phase end with no phase active; the skill asks then.
  coach-chat CC-PHASE-END mentions the review.
- Small shared edits: `phases.get`, `phases.unusable_days`, `weekly_facts.maintenance_base`.
