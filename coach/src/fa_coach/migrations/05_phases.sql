-- Phases, their setup and targets (ticket 05). Written by features/phase_start.py,
-- read through fa_coach/phases.py.

-- A phase setup being collected in chat ("start reverse"). At most one is open
-- (collecting or pending) at a time; code supersedes the old one. `preview_no`
-- counts previews, so a tap on an older preview card can't start anything.
CREATE TABLE phase_setups (
    id           TEXT PRIMARY KEY,
    phase_id     TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('collecting', 'pending', 'confirming', 'confirmed', 'cancelled', 'superseded')),
    setup_values TEXT NOT NULL DEFAULT '{}',  -- JSON: recorded values (logistics as a nested object)
    preview      TEXT,                        -- JSON: the latest start_phase preview
    preview_no   INTEGER NOT NULL DEFAULT 0,
    turns        TEXT NOT NULL DEFAULT '[]',  -- JSON: short history of this setup's chat
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    confirmed_at TEXT
);

-- Phases. At most one is active; starting a new one ends it.
CREATE TABLE phases (
    id                      TEXT PRIMARY KEY,
    phase_id                TEXT NOT NULL,
    setup_id                TEXT NOT NULL REFERENCES phase_setups (id),
    status                  TEXT NOT NULL CHECK (status IN ('active', 'ended')),
    start_date              TEXT NOT NULL,
    setup                   TEXT NOT NULL,  -- JSON: phase_setup.schema.json
    first_change_applied_at TEXT,           -- the phase's first change (the start itself)
    started_at              TEXT NOT NULL,
    ended_at                TEXT
);
CREATE UNIQUE INDEX phases_one_active ON phases (status) WHERE status = 'active';

-- Targets: one row per change (phase start, approved proposals), newest
-- valid_from wins for a date. Daily target = base + counted activity + surplus.
CREATE TABLE targets (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_row_id              TEXT NOT NULL REFERENCES phases (id),
    valid_from                TEXT NOT NULL,  -- ISO date
    source                    TEXT NOT NULL,  -- 'phase_start' or a proposal source
    ref                       TEXT,           -- e.g. the proposal id
    base_maintenance_kcal     REAL NOT NULL,
    surplus_kcal              REAL NOT NULL,
    avg_activity_kcal         REAL NOT NULL,  -- expected counted activity per day
    maintenance_estimate_kcal REAL NOT NULL,
    avg_daily_target_kcal     REAL NOT NULL,
    mfp_goal                  TEXT NOT NULL,  -- JSON: {kcal, protein_g, carbs_g, fat_g}
    created_at                TEXT NOT NULL
);
CREATE INDEX targets_valid_from ON targets (valid_from);
