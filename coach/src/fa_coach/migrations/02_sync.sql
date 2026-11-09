-- Synced history (ticket 02). Filled only by features/sync.py from the api;
-- read through fa_coach/history.py.

-- One row per MFP diary day that was synced. Food totals are null when the
-- day has no food; fiber_g is null when the diary has no Fiber column;
-- produce_g is null (not derivable from MFP yet).
CREATE TABLE mfp_days (
    date         TEXT PRIMARY KEY,
    kcal         REAL,
    protein_g    REAL,
    carbs_g      REAL,
    fat_g        REAL,
    fiber_g      REAL,
    produce_g    REAL,
    complete     INTEGER NOT NULL,  -- MFP's "Complete this entry" pressed
    food_entries INTEGER NOT NULL,
    steps        INTEGER,
    synced_at    TEXT NOT NULL
);

-- MFP exercise entries (e.g. Strava runs), replaced per day on every sync.
CREATE TABLE mfp_exercises (
    date        TEXT NOT NULL,
    position    INTEGER NOT NULL,
    name        TEXT,
    source      TEXT,
    is_run      INTEGER NOT NULL,
    kcal        REAL,
    distance_km REAL,
    minutes     REAL,
    start_at    TEXT,
    PRIMARY KEY (date, position)
);

-- Weigh-ins (kg). `outlier` is set by code (features/sync.py) and keeps the
-- weigh-in out of trend inputs; it is never messaged about.
CREATE TABLE weigh_ins (
    date      TEXT PRIMARY KEY,
    weight_kg REAL NOT NULL,
    outlier   INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT NOT NULL
);

-- Hevy lifting sessions. `first_seen_at` tells later jobs which sessions are new.
CREATE TABLE lift_sessions (
    id            TEXT PRIMARY KEY,
    date          TEXT NOT NULL,
    name          TEXT,
    start_at      TEXT,
    end_at        TEXT,
    minutes       REAL,
    first_seen_at TEXT NOT NULL,
    synced_at     TEXT NOT NULL
);
CREATE INDEX lift_sessions_date ON lift_sessions (date);

CREATE TABLE lift_exercises (
    session_id    TEXT NOT NULL REFERENCES lift_sessions (id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    exercise_id   TEXT,  -- Hevy exercise template id (null if Hevy sent none)
    title         TEXT,
    exercise_type TEXT,  -- Hevy's, e.g. weight_reps, bodyweight_reps (null if none)
    PRIMARY KEY (session_id, position)
);

CREATE TABLE lift_sets (
    session_id        TEXT NOT NULL REFERENCES lift_sessions (id) ON DELETE CASCADE,
    exercise_position INTEGER NOT NULL,
    position          INTEGER NOT NULL,
    type              TEXT,  -- Hevy's set indicator: normal, warmup, dropset, failure
    weight_kg         REAL,
    reps              INTEGER,
    distance_m        REAL,
    duration_s        REAL,
    rpe               REAL,
    PRIMARY KEY (session_id, exercise_position, position)
);

-- Per source ("mfp", "hevy"): last attempt and success, how far the history
-- is complete, and what the last run brought in (for /sync).
CREATE TABLE sync_state (
    source          TEXT PRIMARY KEY,
    last_attempt_at TEXT,
    last_success_at TEXT,
    synced_through  TEXT,
    last_error      TEXT,
    last_start      TEXT,
    last_end        TEXT,
    last_count      INTEGER,
    last_new        INTEGER
);
