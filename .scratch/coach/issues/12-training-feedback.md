# 12: Training feedback after lifting

**What to build:** When a new lifting session syncs from Hevy, the coach looks at it: PRs are named, a stall on a tracked lift is flagged once, and a sudden big load drop triggers "was this a technique/ROM change or exercise swap?" with buttons. In chat the user can also mark a baseline reset or pause an exercise around an injury.

**Blocked by:** 08 (Lift progression in the weekly decision)

**Status:** ready-for-agent

- [x] A newly synced lifting session triggers daily facts (kind training) and the training-feedback skill once per session
- [x] PRs are named; stalls on tracked lifts are flagged the first time only; new baselines are mentioned only on their first session; paused exercises aren't judged
- [x] A possible reset sends the question with mark-reset / not-a-reset buttons (urgent, exempt from the message limit); mark-reset starts a new baseline from that session; either tap removes the buttons
- [x] Unremarkable sessions send nothing; minor notes are deferred to the weekly report
- [x] `mark_baseline_reset` and `set_exercise_paused` work from chat (technique change, ROM change, swap, injury); an injury note leads to an offer to pause, not an automatic pause
- [x] Tests cover a PR, a first stall flag and no repeat, a reset question with both buttons, a paused exercise, and a silent session

## Decisions (user, 2026-11-09)

Use ticket 08's "Decisions" section: no PR on an exercise's first session; sessions on a day with an `other_location` context note get no PR, no stall flag and no reset question; the reset question compares the heaviest working set (4–20 reps) by estimated 1RM.

## Comments

- Code: `features/training_feedback.py` (job `training-feedback`, buttons `mark_reset` /
  `not_a_reset`, tools `mark_baseline_reset` / `set_exercise_paused`), migration
  `12_training_feedback.sql` (`training_feedback` messages, `reset_questions`).
- "New session": first synced after the phase started (`first_seen_at >= started_at`), dated
  today or up to 2 days back, once per session. No phase, no feedback (the facts need a phase).
- A session where nothing was judged or started a baseline (after a break, other gym,
  paused, no working sets) gets no model call at all.
- Code decides what goes out: only a PR, a `new_stall` or a reset question; any other model
  text is deferred to the weekly report. The reset question and its buttons are written by
  code (one row per exercise, ref = question id), appended under the model's text and sent
  exempt; without a usable model answer the question goes out alone. The skill's TF-RESET
  now tells the model not to ask it itself (like the proposal buttons in ticket 09).
- `mark_baseline_reset`: `reason` is an enum (technique_change / rom_change / exercise_swap /
  other); `date` defaults to today (the first session on or after it starts the baseline).
- Daily facts `session.exercises` now carry the full `progression.session` view (`counts`
  and `classification` instead of `tracked`, `top_set`, `best_recent`, `not_judged_reason`,
  `decline_streak`, `stalled`, `new_stall`, `bodyweight_exercise`); example updated.
- Progression fix (owned here): load and reps both ≥ with one > is improved, both ≤ with one
  < declined, both equal same; the ±1 % e1RM band applies only when they move in opposite
  directions (micro-progressions now count). SPEC.md, `.scratch/coach/spec.md`, the
  coach-skills README, params comment and schema description updated. Side effect: for
  bodyweight lifts at the same reps, any change in the 7-day trend weight now reads as
  improved / declined (test D's pull-ups: 82.0 → 81.91 kg is now "declined", was "same").
