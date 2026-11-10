-- The training plan (ticket 04, features/training_plan.py).

-- Versions of the saved default week. The first row is seeded once from
-- coach/data/training_plan.csv (valid for all earlier dates); every lasting
-- change from the chat adds a row valid from its date. The plan for a date is
-- the newest row with valid_from <= that date.
CREATE TABLE training_plan (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    valid_from TEXT NOT NULL,  -- ISO date ('0001-01-01' for the seed)
    source     TEXT NOT NULL CHECK (source IN ('seed', 'chat')),
    plan       TEXT NOT NULL,  -- JSON: {days: {monday: [session]}, exercise_lists: {name: [item]}}
    created_at TEXT NOT NULL
);

-- What the user reported for single days: a planned session skipped or done,
-- or an extra session with its kcal.
CREATE TABLE session_statuses (
    id         TEXT PRIMARY KEY,
    date       TEXT NOT NULL,
    session_id TEXT,           -- the planned session (e.g. 'fri-1'); NULL for an extra
    status     TEXT NOT NULL CHECK (status IN ('skipped', 'done', 'extra')),
    type       TEXT NOT NULL CHECK (type IN ('lift', 'run', 'wrestling', 'other')),
    name       TEXT,
    kcal       REAL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX session_statuses_planned ON session_statuses (date, session_id) WHERE session_id IS NOT NULL;
CREATE INDEX session_statuses_date ON session_statuses (date);
