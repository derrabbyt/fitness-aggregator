# 03: Setup values as of the day

**What to build:** Migration `setup_changes (phase_row_id, key, value, valid_from, source, ref, created_at)`, seeded from each phase's `setup` at its start date. Every setup change (chat, web, approved calibration) adds a row valid from the day it takes effect; `phases.setup` keeps the latest. `phases.params_on(coach, day)` merges the values in force that day for the phase of that day (`phases.on`); daily target, steps kcal, session kcal, Home/Week read models and weekly facts use it. An ended phase's days keep their targets and band on the web.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Migration with seeding, tested on a DB with an existing phase
- [x] Tests: past day after a calibration change and after a step-goal change; an ended phase's day shows target and band
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- **Migration `23_setup_history.sql`:** `setup_changes (id, phase_row_id, key, value JSON, valid_from, source, ref, created_at)`. Keys are flat: top-level setup keys, logistics as `logistics.<field>` (so changing one logistics value keeps the others). Seeded from every phase's `setup` at its `start_date` (source `phase_start`, ref the setup id). Sources: `phase_start` (confirm), `setup_value` (`record_setup_value`, chat and web alike: the web runs the same tool), `calibration` (ref = proposal id). Same key and day: the later row wins.
- **`phases`:** `params_on(coach, day)` = `params_for` of the phase of the day (`on`) with `setup_on(coach, phase, day)` (per key the latest row valid on/before the day; keys with no history fall back to `phases.setup`); core params outside a phase. `record_setup_change`, `flat_setup` added. `targets(coach, day)` and `daily_target` now use the phase of the day (`on`), so an ended phase's days keep their targets; `macro_reference_weight` and `in_glycogen_window(coach, day)` likewise.
- **Readers switched to `params_on`:** `daily_target` (so steps kcal, session kcal and macros), `weekdata.intake`, `weekly_facts.compute` (the week's last day), Home steps (`web_home_steps.day_steps(coach, day)` now looks up its own params; the detail's goal is the day shown's), Home food (day check, fiber), Home training kcal per line, Training activities (per day; days outside a phase keep today's values as before), Week numbers (`_params`: the week's last day so far, clamped to an ended phase's last day; steps `days_at_goal` judges each day by its own goal), weight bands (`web_weight.Bands` now per day: the phase of the day and its params, so an ended phase keeps its band and corridor).
- **Planned wrestling on an ended phase's days:** `counted_activity_on` defaults to the *active* phase's start for counting planned sessions, so after ending, the ended phase's planned wrestling dropped out of its past targets. `daily_target` (and Home training's kcal per line) now pass the day's phase start as `planned_from`. The default is unchanged elsewhere (maintenance windows, calibration), so those computations don't change.
- **`erase`:** `setup_changes` is a row in `_erase_parts` (before `phases`); no LABELS entry: the undo card's "the phase and its setup" covers it.
- **Changed test:** `test_steps.py::test_a_day_at_the_goal_after_the_goal_changed_in_chat` asserted the old behaviour (a past day took a new goal); it now checks the change on its own day; the past-day case is in `test_setup_history.py`.
- **Skills:** PS-CHANGE-MIDWAY and the TOOLS.md row for `record_setup_value` say a change applies from today and earlier days keep their values; the tool returns `applies_from`.
- **Left as today's values (no day in question):** `params(coach)` for jobs and settings views (evening, check-in time, messaging limits, setup pages, session-kcal MET table, day-question thresholds).
