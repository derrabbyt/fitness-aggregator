---
name: phase-cut
description: Active-phase rules for a cut, or a mini-cut (a cut with an end date) during a bulk (phase_id cut). Load in every coach call while this phase is active, and at its phase start. Contains the start rule (level or goal), the band, the weekly decision table, macros and the phase end. All numbers are in params.yaml next to this file.
---

# Phase: cut

Reuses the core: same timing rules, adherence gate, guardrails and reports. All numbers below
are keys in this phase's `params.yaml` (or `coach-core/params.yaml`); read their values from
`params` in the facts. Code computes every number; you explain them.

## Start (phase-start skill uses this)

- **CUT-START** – The user picks a level (`cut_level`: conservative, moderate, aggressive;
  deficits in `cut.levels_kcal`, `cut.default_level` is the default) or gives a `goal` (a
  goal weight, or a goal body fat with their current estimate, and a date). From a goal code
  derives the rate and the deficit it needs, caps it at `cut.max_deficit_kcal` and suggests
  the level. With both, the level decides and the goal is shown against it.
  Start kcal = the maintenance estimate minus the deficit (setup `deficit_kcal`, code's).
- **CUT-WARN** – Past `cut.warn_above_kcal` (aggressive, or a goal that needs more than
  moderate) code adds a warning: aggressive deficits are for experienced dieters; hunger and
  adherence get hard. Say it once, plainly, and offer the suggested or default level. The user
  decides.
- **CUT-MINI** – A mini-cut is a cut with an `end_date`. The user can move it during the
  phase (`record_setup_value`); the level and the goal are fixed for the phase.
- This is the phase's first change: the `decisions.max_change_kcal` guardrail doesn't apply.

## First weeks

- **CUT-FIRST-WEEK** – There is no glycogen window (`glycogen_window_weeks`), but a water drop is
  expected in the first `unjudged_weeks` phase weeks. Say so in advance and when it happens.
  Code doesn't judge those weeks against the band (`weight.vs_band` is `not_evaluated`):
  scenario `target_met` or the week's other facts, direction `hold`, no proposal.

## Weight classes

The band is signed and negative (losing): the target rate (deficit x seven / `kcal_per_kg`)
times one plus or minus `cut.band_tolerance`. Code gives `weight.vs_band`:

| `vs_band` | Means |
| --- | --- |
| `above_band` | **stalled** – losing slower than the band (or gaining) |
| `in_band` | **target met** |
| `below_band` | **too fast** – losing faster than the band |

## Decision table

Strength rule: holding lifts is success (`same` counts as fine); progression is not required.
Several lifts declining (`training.deload_signal`) flags the deficit or recovery.

| Rule | Weight | Strength | Adherence | Scenario | Direction | Action |
| --- | --- | --- | --- | --- | --- | --- |
| **CUT-ON** | target met | holding | ok | target_met | hold | Keep food, steps and cardio unchanged. |
| **CUT-STALL** | stalled | holding | ok | stalled | decrease | Eat less, carbs first (`stall_lever`, `carb_step_g`): the small or large step by the distance from the band (code's RB-SIZE rule). In the text, offer more steps instead (`cut.stall_activity_steps` a day more). |
| **CUT-NOADH** | stalled | any | not ok | adherence_gate | hold | No change: a clean week of full adherence first (WD-ADHERENCE). Say so without blame. |
| **CUT-STRENGTH** | any | several lifts declining | ok | strength_drop | hold | Don't deepen the deficit; flag `deload_signal` (deficit or recovery). |
| **CUT-FAST** | too fast | any | ok | too_fast | increase | Eat `decisions.increase_step_kcal` more a day, to protect muscle. |

- CUT-STRENGTH wins over CUT-STALL in the same week.
- Confirmation: `decisions.confirmation_weeks` usable weeks for a decrease; CUT-FAST uses
  `decisions.confirmation_weeks_fast_lane`.
- Code enforces the direction and the step on the stored verdict (weekly-decision,
  WD-GUARD): a decrease only above the band, an increase only below it, always
  `decisions.increase_step_kcal`.

## Macros (code computes, you explain)

- **CUT-MACROS** – Protein `macros.protein_g_per_kg`, fat at the floor
  `macros.fat_g_per_kg_min` (not asked at setup), carbs = remainder. A calorie change goes to
  carbs.

## Phase end

- **CUT-END** – A mini-cut: from the day after its `end_date` code sends the end card; the
  user confirms or keeps going. Otherwise the user decides. Advise at their goal (weight or
  body fat, the goal date), at `time_goal_weeks`, and when hunger notes pile up in the context
  log. Then ask what comes next (`on_phase_end`).
