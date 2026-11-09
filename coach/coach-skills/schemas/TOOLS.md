# Coach tools (contract for code)

Tools the coach model can call in the **coach chat** and in jobs that need them. All return
pre-aggregated JSON, never raw MyFitnessPal dumps. Names are suggestions; Claude Code can
rename them to fit the codebase as long as SKILL.md references are updated in the same change.

Rule for every write tool: **code validates, code applies.** The model only asks.

## Read

| Tool | Input | Returns |
| --- | --- | --- |
| `get_weekly_facts` | `iso_week` | `weekly_facts.schema.json` |
| `get_daily_facts` | `date`, `kind` | `daily_facts.schema.json` |
| `get_lift_history` | `exercise_id`, `n_sessions` | sessions since last baseline: date, sets (load, reps), effective load, status, notes |
| `get_context_notes` | `from`, `to` | list of `context_note.schema.json` |
| `get_targets` | – | current `targets` block + per-day targets for the current week |
| `get_training_plan` | – | saved default week + this week's changes |
| `get_proposals` | `status` (optional) | list of `proposal.schema.json` |
| `get_coach_profile` | – | small free-text profile (preferences, known issues) |
| `load_skill` | `name` | SKILL.md of another skill from the index |

## Write

| Tool | Input | What code does |
| --- | --- | --- |
| `propose_change` | `type`, `delta_kcal` or `new_values`, `reason`, `source`, `based_on_week`, `is_phase_first_change`, `counter_of`, `returning_rejected_proposal_id`, `agent_disagrees` | Runs guardrails (below). Stores a `proposal` with status `open` or `blocked_by_guardrail` and returns it with `guardrail.violations`. Never applies anything. |
| `add_rejection_reason` | `proposal_id`, `reason` | Stores `user_reason` on a rejected proposal. |
| `add_context_note` | `context_note` without `id` / `created_at` | Stores note; returns id. |
| `mark_baseline_reset` | `exercise_id`, `date`, `reason` | Starts a new baseline for that exercise from `date`. |
| `set_exercise_paused` | `exercise_id`, `paused`, `reason` | Injury pause on/off. |
| `set_week_sport_load` | `iso_week`, `high` (bool) | User tag/untag; overrides the plan-derived value. |
| `set_session_status` | `date`, `type`, `status` (`done`/`skipped`), optional `kcal` | Planned session confirmed, skipped, or an extra session added. |
| `update_training_plan` | `changes` (day → sessions) | Edits the saved default week. |
| `repull_training_plan` | – | Re-reads the Google Sheet into the saved plan; returns the diff. |
| `record_setup_value` | `key`, `value` | Stores a setup value (run discount, wrestling kcal, logistics, …). Validates against `phase_setup.schema.json` / `core_params.schema.json`. |
| `start_phase` | `phase_setup` | Validates, stores as pending, returns a **week-1 preview** computed by code (daily targets by day type, macros, MFP goal). The phase starts only when the user taps `confirm_phase_start`. |
| `update_coach_profile` | `patch` | Stores and shows the change to the user. |

Buttons (`approve_proposal`, `reject_proposal`, `counter_proposal`, `confirm_phase_start`, …)
are handled by code directly; the model is only called afterwards if a reply needs writing.

## `propose_change` guardrails (code)

A proposal is `blocked_by_guardrail` if any of these hold:

1. `calorie_change` and `|delta_kcal| > decisions.max_change_kcal`, unless `is_phase_first_change`
   and the delta is within the phase's start range → `exceeds_max_change`.
2. Fewer than `decisions.confirmation_weeks` usable weeks since the last applied change
   (`confirmation_weeks_fast_lane` when the verdict's scenario is the phase's "too fast"
   scenario: reverse_bulk `E`, cut `too_fast`). The week after a change counts as week 1
   → `lockout`.
3. Stored verdicts don't show the required consecutive usable weeks pointing the same
   direction → `confirmation_not_met`. A `user_counter` in the same direction as the
   proposal it replaces inherits that proposal's confirmation; a counter in the other
   direction, and any `user_request`, is checked normally. `phase_start` skips 2–4.
4. Same direction as the last rejected proposal and fewer than
   `decisions.rejected_return_weeks` usable weeks since the rejection still pointed that way
   → `rejected_return_too_early`.
5. `based_on_week` was unusable → `week_unusable`; weekly adherence failed → `adherence_gate`.
6. `calibration_change` with out-of-range values → `invalid_values`.

Not a guardrail: other open proposals may coexist (no stacking rule). An identical open
proposal should be referenced, not duplicated (idempotency).

On **approve**: apply delta to `surplus_kcal` (or new calibration values), recompute targets,
set the MyFitnessPal calorie goal to the new average daily target, log the change.
On **reject**: store `user_reason` if given. On **counter**: new proposal with
`source=user_counter`, `counter_of` set; the old one becomes `superseded`.
