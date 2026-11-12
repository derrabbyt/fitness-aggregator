-- Exercise classification and pause as of the day (coach-followups ticket 04).
-- Written and read through progression.py. `exercise_settings` stays as the
-- latest values; each change adds the exercise's whole setting here, in force
-- from `valid_from` (the day it was made) until the next row. The setting in
-- force on a day is the row with the latest `valid_from` on or before it
-- (latest id on ties); no row = not classified yet (counts), not paused.
CREATE TABLE exercise_setting_changes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id    TEXT NOT NULL,
    classification TEXT CHECK (classification IN ('counts', 'excluded')),
    paused         INTEGER NOT NULL DEFAULT 0,
    paused_reason  TEXT,
    valid_from     TEXT NOT NULL,  -- ISO date
    created_at     TEXT NOT NULL
);
CREATE INDEX exercise_setting_changes_exercise ON exercise_setting_changes (exercise_id, valid_from, id);

-- Settings made before this history existed apply to the whole history.
INSERT INTO exercise_setting_changes (exercise_id, classification, paused, paused_reason, valid_from, created_at)
SELECT exercise_id, classification, paused, paused_reason, '0001-01-01', updated_at FROM exercise_settings;
