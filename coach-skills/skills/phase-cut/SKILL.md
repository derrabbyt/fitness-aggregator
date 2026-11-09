---
name: phase-cut
description: Active-phase rules for a cut or a mini-cut during a bulk (phase_id cut). DRAFT – band and limits in params.yaml must be decided before the phase is started. Load in every coach call while this phase is active.
---

# Phase: cut (draft)

**Draft status.** `params.yaml` has `draft: true` and open values marked TO DECIDE
(`weight_band_kg_per_week`, `weight_lower_limit_kg_per_week`). The phase-start skill must
not start this phase until they are filled. Everything else reuses the core: same timing
rules, adherence gate, guardrails and reports.

## Start

- **CUT-START** – `surplus_kcal` = minus `start.deficit_kcal` against base maintenance plus
  counted activity. Phase first change: the max-change guardrail doesn't apply to it.
- A mini-cut during a bulk uses this same phase; the user ends it.

## Weight classes

The band is signed and negative (losing). Code gives `weight.vs_band` numerically:

| `vs_band` | Means |
| --- | --- |
| `above_band`, `above_limit` | **losing too slowly / stalled** |
| `in_band` | **on track** |
| `below_band` | **losing faster than the band** – watched |
| `below_limit` | **losing too fast** |

## Decision table

Strength rule: holding lifts is success (`same` counts as fine). Progression is not
required. Several lifts declining (`training.deload_signal`) flags the deficit or recovery.

| Rule | Weight | Strength | Scenario | Direction | Action |
| --- | --- | --- | --- | --- | --- |
| **CUT-ON** | on track or faster than band | holding | on_track | hold | Keep unchanged. |
| **CUT-STALL** | too slowly / stalled | holding | stalled | decrease | Lower calories through carbs: `carb_step_g` per step (`stall_lever`). |
| **CUT-STRENGTH** | any | several lifts declining | strength_drop | hold | Don't deepen the deficit; flag `deload_signal` (deficit or recovery). |
| **CUT-FAST** | too fast | any | too_fast | increase | Propose a small increase (`decisions.small_step_kcal`). |

- CUT-STRENGTH wins over CUT-STALL in the same week.
- Confirmation: `decisions.confirmation_weeks` usable weeks for every change
  (CUT-FAST uses `decisions.confirmation_weeks_fast_lane`).

## Macros

- **CUT-MACROS** – Protein `macros.protein_g_per_kg`, fat at the floor
  `macros.fat_g_per_kg_min`, carbs = remainder.

## Phase end

- **CUT-END** – The user decides. Advise at a target they set (body fat or weight) or at
  `time_goal_weeks`, and when hunger notes pile up in the context log. Then ask what comes
  next (`on_phase_end`).
