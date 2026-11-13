---
name: phase-review
description: Runs every reviews.phase_review_every_weeks weeks from the phase start and whenever a phase ends. Reviews progress against the plan (weight vs band and time goal, strength), the maintenance estimate, waist and body-fat estimates, the goal, and the activity calibration code checked; after a phase end it asks what comes next. Words only; code makes any calibration proposal. Load with coach-core and the phase's skill. Input phase_summary.schema.json; output coach_message.schema.json.
---

# Phase review

Input: `phase_summary` (code computed every number, over `start_date`..`end_date`).
`reason`: `scheduled` (the phase goes on) or `phase_end` (it ended; `end_date` is its last
day). Take every number as given (CORE-NO-MATH).

## Content

1. **PR-PROGRESS** – Weight trend `start_trend_kg` → `current_trend_kg` (`change_kg`,
   `avg_rate_kg_per_week`) against the phase's `band`, and how the weekly check-ins sat
   (`weight.weeks`: in, below, above the band; not evaluated). Calorie target start vs
   now and the changes made (`targets.changes`).
2. **PR-TIME-GOAL** – Only when `time_goal.weeks`, `time_goal.goal` or `time_goal.end_date`
   is set: where the phase stands against it (`weeks_left`; a cut's goal weight or body fat
   and date). Mention the phase's time rule if near.
3. **PR-TRAINING** – The strength trend over the phase (`training.strength_trend`), lifts
   improving / holding / declining (`lifts`: `change_pct`, statuses), PRs, stalls.
   Baseline resets explain short histories. In a cut, holding is success.
4. **PR-MAINTENANCE** – The estimate at the start (`at_start_kcal`) vs the
   back-calculated base now (`base_kcal`, `window_weeks`), in one line; it's a rough
   number. Null: not enough usable weeks yet.
5. **PR-BODY** – Waist start vs now (reported, not a trigger). With photos on: the
   body-fat estimates over the phase (`body_fat_estimates`; the user's own win), with the
   caveat that only like-for-like photo sets compare well. With `photos_compared`, the
   images after the input are the phase start set and the latest set (labelled): describe
   the visible change between them in a few words (waist, definition), as an estimate,
   next to the estimates; the start set alone (`latest_set` null) gets no comparison. Code already sends the
   body-fat advice; repeat it here only as one line if the phase's rule applies.
6. **PR-CALIBRATION** – For each `calibration` item:
   - `drifted` with a `proposal`: say what the weeks show (`evidence`) and that the card
     below asks to approve the new value; nothing changes until the tap.
   - `drifted` without a proposal (a phase end): name the suggested value for the next
     phase's setup.
   - not drifted: nothing, or half a line when `judged`. Never call `propose_change`.
7. **PR-PHOTOS** – On `is_first_review_of_phase` with photos on: ask whether the photos are
   worth keeping (`photo_sets`, `photo_reviews`).
8. **PR-NEXT** – `scheduled`: one or two points to watch until the next review, and ask
   whether the goal and any time goal still stand. `ask_what_next`: summarise the phase,
   then ask what comes next (a cut or mini-cut, maintenance, another bulk); the user
   starts it in the chat. `phase_end` without `ask_what_next`: a new phase already
   started; close with a line about carrying the lessons into it.

## Rules

- No calorie proposals and no buttons: calorie changes come only from the weekly
  decision, calibration proposals only from code (CORE-AUTHORITY).
- `send: true`, `buttons: []`, `deferred_to_weekly: []`. Longer than a weekly report is
  fine; keep each section to a few lines, Telegram-ready.
