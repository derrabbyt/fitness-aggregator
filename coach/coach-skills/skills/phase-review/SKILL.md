---
name: phase-review
description: Runs every reviews.phase_review_every_weeks weeks during a phase and when the user ends a phase. Reviews progress vs plan, maintenance estimate, photos and body fat, the goal, and activity calibration; may propose calibration changes. Load with coach-core and the active phase skill. Input phase_summary.schema.json; output coach_message.schema.json.
---

# Phase review

Input: `phase_summary` (code), the latest photo review if any, the coach profile.

## Content

1. **PR-PROGRESS** – Weight change and average rate over usable weeks vs the phase band;
   how many weeks sat in, below and above the band; calorie target now vs at the start.
2. **PR-TRAINING** – Lifts improving / holding / declining over the phase (from the summary).
   Resets explain short histories.
3. **PR-MAINTENANCE** – How the maintenance estimate moved, in one line; it's a rough number.
4. **PR-BODY** – Waist start vs now (reported, not a trigger). If photos are on: body-fat
   estimates over time and the comparability caveat (like for like; mid-phase vs start is
   unreliable). Apply the phase's body-fat advice rule (reverse_bulk RB-BF) – this is the
   place to repeat it if the user chose to continue earlier.
5. **PR-GOAL** – Ask whether the goal and any time goal still stand
   (`time_goal_weeks`); mention the phase time rule if near.
6. **PR-CALIBRATION** – For each item in `calibration_check` with `drifted: true`, propose
   the `suggested` value with `propose_change` (`type: calibration_change`,
   `source: phase_review`) and explain the evidence in one sentence. The user confirms.
7. **PR-PHOTOS** – On `is_first_review_of_phase` (and photos on): ask whether photos are
   worth keeping, given `comparable_check_ins` vs `check_ins`.
8. **PR-END** – If `reason` is `phase_end`: summarise, then ask what comes next (phase
   options: reverse_bulk, cut, maintenance; draft phases need their open values decided).

## Rules

- No calorie proposals here; calorie changes come only from the weekly decision.
- Numbers only from the summary (CORE-NO-MATH).
- Longer than a weekly report is fine, but keep each section to a few lines.
