---
name: phase-maintenance
description: Active-phase rules for holding weight (phase_id maintenance). DRAFT – macro values are reused from reverse_bulk until decided. Load in every coach call while this phase is active.
---

# Phase: maintenance (draft)

**Draft status.** Macros in `params.yaml` are placeholders reused from reverse_bulk (TO
DECIDE). Everything else reuses the core: timing rules, adherence gate, guardrails, reports.

## Weight classes

Flat band from `weight_band_kg_per_week`; drift limits from `drift_threshold_kg_per_week`
(mirrored in `weight_lower_limit_kg_per_week` / `weight_upper_limit_kg_per_week`).

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

- A change needs `drift_confirmation_weeks` usable weeks drifting the same way.
- Size per the core step sizes (`decisions.small_step_kcal` / `decisions.large_step_kcal`,
  using `decisions.far_off_margin_kg_per_week` beyond the drift limit).
- Strength: report trends; several lifts declining flags `deload_signal`.

## Phase end

- **MAINT-END** – The user decides; advise at `time_goal_weeks` if set, then ask what comes
  next (`on_phase_end`).
