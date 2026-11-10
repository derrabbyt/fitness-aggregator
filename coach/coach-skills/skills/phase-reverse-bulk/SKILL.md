---
name: phase-reverse-bulk
description: Active-phase rules for the reverse into a lean bulk (phase_id reverse_bulk). Load in every coach call while this phase is active. Contains the A–E decision table, the start rule, glycogen handling, macro rules and body-fat advice. All numbers are in params.yaml next to this file.
---

# Phase: reverse into bulk

One continuous phase. The reverse is the first stage of the bulk: calories step up from the
last diet intake until the weight trend sits in the target band, and from then on the A–E
table keeps it there. There is no separate maintenance hold and no separate gain-rate
calibration.

All numbers below are keys in this phase's `params.yaml` (or `coach-core/params.yaml`);
read their values from `params` in the facts.

## Start (phase-start skill uses this)

- **RB-START** – The first week's target = last diet intake + an increase within
  `start.week1_increase_kcal`. Activity unchanged (`start.week1_activity_change`).
  No bigger jumps. When unsure, pick the lower end of the range.
- This is the phase's first change: the `decisions.max_change_kcal` guardrail doesn't
  apply to it, the range above does.

## Glycogen window

- **RB-GLY** – During the first `glycogen_window_weeks` phase weeks
  (`week.in_glycogen_window`), an early weight jump from glycogen and water
  (`glycogen_jump_kg`) is expected.
  Say so in advance and when it happens. Do not classify the weight trend, do not propose a
  decrease, and do not count these weeks toward confirmation. Scenario = `glycogen_window`,
  direction = `hold`.
- Later carb increases in the bulk are small; they get no special window.

## Weight classes

Code gives `weight.vs_band` against the band for the current phase week
(`weight_band_kg_per_week`) and `weight_upper_limit_kg_per_week`:

| `vs_band` | Means | 
| --- | --- |
| `below_band` | **not gaining** |
| `in_band` | **gaining, on target** |
| `above_band` | **gaining, upper edge** – watched, not acted on (flag `weight_watch_zone`) |
| `above_limit` | **gaining too fast** |

## A–E decision table

Gym progression = `training.progression_met` (at least `training.progression_min_share` of
the counting lifts improved vs the best of their recent sessions; excluded lifts never decide
it). Single-lift stalls are flags
only and never decide the scenario.

| Rule | Weight | Progression | Scenario | Direction | Action |
| --- | --- | --- | --- | --- | --- |
| **RB-A** | gaining (on target or upper edge) | yes | A | hold | Keep calories and activity unchanged. |
| **RB-B** | not gaining | yes | B | hold | Keep unchanged; strength gains show muscle building is working (possible recomp). |
| **RB-C** | not gaining | no | C | increase | Raise calories (lever: `default_lever`, not activity). |
| **RB-D** | gaining (on target or upper edge) | no | D | hold | Don't add calories; flag `training_needs_look`. Flag only; the user changes training. |
| **RB-E** | too fast | any | E | decrease | Lower calories; the last increase was set too high. |

- If `training.progression_met` is `null` (no lift could be counted), progression is
  `not_evaluated`: only RB-E can lead to a proposal; otherwise hold and say why.
- Confirmation (see weekly-decision): C needs `decisions.confirmation_weeks` usable weeks
  pointing to increase; E needs `decisions.confirmation_weeks_fast_lane`.

## Change size

- **RB-SIZE** – Small step (`decisions.small_step_kcal`) when the trend is outside the band
  by less than `decisions.far_off_margin_kg_per_week`; large step
  (`decisions.large_step_kcal`) when it is further off. When unsure, choose the smaller
  one: a shortfall is fixed next time, extra fat gain isn't.
- Changes go to carbs once fat is at `macros.fat_g_per_kg_max` (code handles the macro
  split; you only state the calorie change).

## Macros (code computes, you explain)

- **RB-MACROS** – Protein `macros.protein_g_per_kg`, fat between `macros.fat_g_per_kg_min`
  and `macros.fat_g_per_kg_max` (start at `macros.fat_g_per_kg_start`), carbs = remainder.
  Judge daily totals, not single meals.

## Body fat and phase end

- **RB-BF** – When the latest body-fat estimate (user's own, or photo estimate) reaches
  `body_fat.advise_near_pct`, advise a mini-cut or ending the bulk. It is advice, not a stop;
  if the user chooses to continue, accept it and don't repeat the advice every week (repeat
  only at the next phase review or if the estimate rises further). Never use the scale's
  body-fat reading. Waist trend is reported, never a trigger.
- **RB-TIME** – If `time_goal_weeks` is set, mention when the phase is within the last
  block of it and at the goal; the user decides.
- **RB-END** – Ending the phase is the user's call. When it ends, ask what comes next
  (`on_phase_end`). A mini-cut uses the cut phase.

## Reading the body during a bulk

- **RB-SOFT** – Looking softer or flatter mid-bulk is expected. Point back to logbook
  progress instead of reacting. Photos compare like for like; mid-bulk vs start is
  unreliable.
- **RB-RECOMP** – Stable weight with a leaner waist or photos means muscle was gained.
