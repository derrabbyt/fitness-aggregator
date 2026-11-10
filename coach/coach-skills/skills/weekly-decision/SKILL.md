---
name: weekly-decision
description: Weekly job, step 1. Turns one week's weekly_facts into a structured verdict (scenario, direction, confirmation, optional calorie proposal, flags). Load together with coach-core and the active phase skill. Output is JSON only, validated against weekly_verdict.schema.json; the weekly-report skill writes the message afterwards.
---

# Weekly decision

Input: `weekly_facts` for the week that just ended (with `params`, context notes, history).
Output: **one JSON object matching `weekly_verdict.schema.json`, nothing else.**

You make the call; code computed the numbers and will re-check every guardrail when your
proposal goes through `propose_change`. Work through the steps in order. Record the id of
every rule you applied in `rules_applied`.

## Step 1 – Is the week usable?

- **WD-USABLE-CODE** – If `data_quality.code_usable` is false, the week is unusable; copy
  `code_unusable_reasons`. Add flag `data_stale` if `stale_sync` is among them.
- **WD-USABLE-CONTEXT** – Read `context_notes` for the week. Illness, travel or anything else
  that makes the weight trend unreliable makes the week unusable (`illness`, `travel`,
  `other_context`). Use `suggest_unusable` as a hint, not a verdict: one salty meal or one
  late night does not; several sick days do.
- An unusable week gets scenario `unusable`, direction `hold`, no proposal. It is skipped for
  confirmation and does not break a streak. Still add useful flags and say what's missing.

## Step 2 – Glycogen window

- **WD-GLYCOGEN** – If `week.in_glycogen_window`, apply the phase's glycogen rule (e.g.
  RB-GLY): scenario `glycogen_window`, direction `hold`, weight `not_evaluated`, flag
  `glycogen_jump` if weight rose. Continue with step 6 for flags; no proposal.

## Step 3 – Adherence gate

- **WD-ADHERENCE** – If `intake.adherence_ok` is false, set `adherence_gate: fail`, scenario
  `adherence_gate`, direction `hold`, no proposal, flag `adherence_fail` (say whether logging
  was incomplete or the weekly average was off, using `intake.deviation_pct`). Note in
  `reasoning` which scenario the data would otherwise point to. Like unusable weeks, these
  weeks are skipped for confirmation and don't break a streak.

## Step 4 – Phase decision table

- **WD-TABLE** – Take `weight.vs_band` and `training.progression_met`, map them with the
  active phase skill's weight classes and decision table, and set `scenario`, `direction`,
  `weight_assessment`, `progression`. Cite the phase rule id (e.g. RB-C).
- **WD-REVERSAL** – If the trend flipped unexpectedly versus `history.previous_verdicts`, or
  `weight.prediction_miss` is true (error above `decisions.prediction_miss_kg`), check the logs first: incomplete or odd days, or a
  context note, explain it → treat the week as unusable (step 1). Otherwise continue with
  `confidence: low` and flag `trend_reversal` / `prediction_miss`.
- **WD-SPORT** – If `activity.sport_load_high` (a context note tagged `sport_load` covers
  part of the week) and the table result is a "no progression" scenario that would change
  calories or flag training (reverse_bulk: C or D), don't make that call: direction `hold`,
  no proposal, no `training_needs_look` flag, `sport_load_applied: true`, flag
  `sport_load_week`. Stalls that week are explained by load. The week is skipped for
  confirmation: it neither counts nor breaks a streak. Code enforces this on the stored
  verdict.

## Step 5 – Confirmation and proposal

- **WD-CONFIRM** – Code already counted the earlier weeks: `history.confirmation_streaks`
  holds the consecutive earlier weeks pointing to an increase or a decrease since the last
  change, with skipped weeks (`previous_verdicts[].counts_for_confirmation` false: unusable,
  glycogen window, adherence gate, sport load) left out – they neither count nor break a
  streak. If this week counts (steps 1–4 didn't skip it) and points the same way, the
  consecutive count is that streak plus this week; a skipped week (this one included)
  never counts. Required: `decisions.confirmation_weeks`, or
  `decisions.confirmation_weeks_fast_lane` for the phase's "too fast" scenario (reverse_bulk
  E). Fill `confirmation`.
- **WD-PROPOSE** – Propose only if direction is `increase` or `decrease`, the week is usable,
  `adherence_gate` is `pass`, and confirmation is met. Size per the phase's size rule
  (reverse_bulk RB-SIZE); `delta_kcal` is signed. Otherwise `proposal: null` and say in
  `reasoning` when the earliest change could come.
- **WD-REJECTED** – If `history.last_rejected` has the same direction, propose only when the
  consecutive count since the rejection reaches `decisions.rejected_return_weeks`; then set
  `returning_rejected_proposal_id`, add flag `rejected_proposal_returning` and mention the
  user's reason in `reasoning`.
- **WD-OPEN** – If `history.open_proposals` already has an open proposal in the same
  direction, don't create a duplicate: `proposal: null`, point to the open one in
  `reasoning`. Open proposals in the other direction may stay; say the older one no longer
  fits the data.
- **WD-FIRST** – If `week.phase_first_change_pending` is still true, the phase start was not
  confirmed: no proposal; ask the user to confirm the phase start.

## Step 6 – Flags (always, also in unusable weeks where data allows)

Add a flag only when it's true and worth the user's attention. Severity `info` = report it,
`watch` = keep an eye on it, `action` = the user should do something.

- **WD-F-WEIGHT** – `weight_spike` for `weight.outlier_days` (explain with context notes if
  possible); `weight_watch_zone` per phase rule.
- **WD-F-INTAKE** – `intake_overshoot` / `intake_undershoot` when the weekly average misses
  the tolerance (if the previous verdict also showed it, add a question asking why);
  `intake_pattern` when the daily logs show a repeated pattern (e.g. certain
  days far above target) – no hard weekday/weekend rule; `macro_off` when protein or fat is
  clearly off target on most days (judge daily totals, never single meals); `fiber_off` when
  fiber is outside `intake.fiber_target_g` on most days; `produce_low` when `produce_g` is
  below `intake.produce_min_g` on most days (skip if `produce_g` is null); `odd_log` for an
  implausible entry, with a question.
- **WD-F-TRAINING** – `lift_stall` per lift in `training.stalls` (counting lifts whose
  `no_progress_streak` reached `training.stall_sessions`; excluded lifts never get one),
  judged with that exercise's normal behaviour in mind (isolation lifts stall more often),
  with `exercise_id`; `deload_signal` if `training.deload_signal`;
  `training_needs_look` for scenario D (flag only); `missed_session_pattern` if planned
  sessions were missed repeatedly, with a suggestion to change the schedule.
- **WD-F-STEPS** – `step_floor` only if `activity.days_below_floor` reached
  `activity.soft_floor_min_days` and no other training happened those days. Skip if that
  param is null. Steps are a measuring tool; large swings are normal.
- **WD-F-BODY** – `bodyfat_near_ceiling` per the phase body-fat rule (respect a recent
  "continue" from the user, see context notes / coach profile); `time_goal_near` per the
  phase time rule.

## Step 7 – Write the rest

- `confidence`: high when data is complete and signals agree; low after reversals, borderline
  bands or conflicting signals.
- `reasoning`: 2–5 plain sentences: what the data shows, which rule decided, what happens
  next. The weekly-report skill builds the message from it.
- `questions_for_user`: only what the data can't answer (CORE-ASK).

## Example (reverse_bulk, phase week 9)

Facts: usable, adherence ok, `vs_band: below_band` (rate under `low`), `progression_met:
false`, not a sport-load week, previous usable verdict also C/increase, last change three
usable weeks ago, no rejection. → scenario C, direction increase, confirmation 2/2 met,
proposal `calorie_change` small step, rules `WD-USABLE-CODE, WD-ADHERENCE, WD-TABLE, RB-C,
WD-CONFIRM, WD-PROPOSE, RB-SIZE`.

Same week but `sport_load_high: true` (wrestling camp) → WD-SPORT: direction hold, no
proposal, `sport_load_applied: true`, flag `sport_load_week`; the week is skipped for
confirmation, so the increase streak neither grows nor resets.
