---
name: phase-maintenance
description: Active-phase rules for holding weight (phase_id maintenance). Load in every coach call while this phase is active. Flat band, drift limits and the MAINT decision table; all numbers are in params.yaml next to this file.
---

# Phase: maintenance

Kept small. Everything not here reuses the core: timing rules, adherence gate, guardrails,
reports.

## Start (phase-start skill uses this)

- **MAINT-START** – Start kcal = the maintenance estimate plus `start.surplus_kcal`. No
  first-week increase and no glycogen window (`glycogen_window_weeks`): the first week is
  judged.

## Macros (code computes, you explain)

- **MAINT-MACROS** – As the bulk's: protein `macros.protein_g_per_kg`, fat between
  `macros.fat_g_per_kg_min` and `macros.fat_g_per_kg_max` (start at
  `macros.fat_g_per_kg_start`), carbs the rest.

## Weight classes

Flat band from `weight_band_kg_per_week`; drift limits `weight_lower_limit_kg_per_week` /
`weight_upper_limit_kg_per_week`.

| `vs_band` | Means |
| --- | --- |
| `in_band` | **flat** |
| `above_band`, `below_band` | **small drift** – watched, not acted on |
| `above_limit` | **drifting up** |
| `below_limit` | **drifting down** |

## Decision table

| Rule | Weight | Scenario | Direction | Action |
| --- | --- | --- | --- | --- |
| **MAINT-FLAT** | flat or small drift | flat | hold | Keep unchanged. |
| **MAINT-UP** | drifting up | drift_up | decrease | Propose a calorie decrease. |
| **MAINT-DOWN** | drifting down | drift_down | increase | Propose a calorie increase. |

- A change needs `decisions.confirmation_weeks` counted weeks drifting the same way (no fast
  lane).
- **MAINT-SIZE** – Always `decisions.small_step_kcal`, toward flat (a decrease when drifting
  up, an increase when drifting down). Code enforces the direction and size and stores a
  small drift (inside the limits) as `hold` (weekly-decision, WD-GUARD).
- Strength: report trends; several lifts declining flags `deload_signal`.

## Phase end

- **MAINT-END** – The user decides; advise at `time_goal_weeks` if set, then ask what comes
  next (`on_phase_end`).
