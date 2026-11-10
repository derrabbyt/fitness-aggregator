-- Steps as live activity (ticket 18, fa_coach/phases.py and features/training_plan.py).

-- The step model of a targets row: k (kcal per step, at the trend weight when
-- the row's base was computed) and the average day steps (run steps removed,
-- untracked days left out) over the maintenance estimate's window. Base
-- maintenance stays the base at those average steps; base at the step goal =
-- base - k x (avg_day_steps - step goal). NULL (older rows, or no tracked day
-- in the window): no step adjustment.
ALTER TABLE targets ADD COLUMN step_kcal_per_step REAL;
ALTER TABLE targets ADD COLUMN avg_day_steps REAL;

-- A reported session's distance (walks, hikes, a run that won't sync): its
-- steps are taken off the day's steps (x steps.run_steps_per_km).
ALTER TABLE session_statuses ADD COLUMN distance_km REAL;
