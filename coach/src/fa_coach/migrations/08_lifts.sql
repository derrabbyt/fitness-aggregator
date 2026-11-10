-- Lift progression (ticket 08). Written by features/lifts.py (and ticket 12's
-- reset / pause tools through progression.py), read through progression.py.

-- Every exercise logged in Hevy is recorded. Per exercise: the model's
-- classification (counts for progression, or excluded: prehab/rehab and slow
-- movers; the user can flip it) and an injury pause. No row or a null
-- classification = not classified yet, which counts (the default).
CREATE TABLE exercise_settings (
    exercise_id    TEXT PRIMARY KEY,  -- Hevy exercise template id
    title          TEXT,
    classification TEXT CHECK (classification IN ('counts', 'excluded')),
    class_reason   TEXT,
    paused         INTEGER NOT NULL DEFAULT 0,  -- injury pause: not judged
    paused_reason  TEXT,
    updated_at     TEXT NOT NULL
);

-- Baseline resets (technique / ROM change, exercise swap): the given session,
-- else the first session of the exercise on or after `from_date`, starts a
-- new history.
CREATE TABLE baseline_resets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id TEXT NOT NULL,
    from_date   TEXT NOT NULL,  -- ISO date
    session_id  TEXT,
    reason      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX baseline_resets_exercise ON baseline_resets (exercise_id, from_date);

-- Tracked lifts are no longer picked at phase start (every Hevy exercise is
-- recorded and classified): drop the old setup value from stored setups and previews.
UPDATE phases SET setup = json_remove(setup, '$.tracked_lifts');
UPDATE phase_setups SET setup_values = json_remove(setup_values, '$.tracked_lifts');
UPDATE phase_setups SET preview = json_remove(preview, '$.setup.tracked_lifts') WHERE preview IS NOT NULL;
