-- MFP goal writes (ticket 06), written by fa_coach/mfp_goal.py. One row per
-- change that sets the goal (a confirmed phase start, an approved proposal),
-- keyed by that change: inserting the row claims the write, so it is sent at
-- most once, even across restarts. A row left at 'sending' means the coach
-- stopped mid-write; it is never resent.
CREATE TABLE mfp_goal_writes (
    key         TEXT PRIMARY KEY,  -- e.g. 'phase-start:<phase row id>', 'proposal:<id>'
    requested   TEXT NOT NULL,     -- JSON: {kcal, protein_g, carbs_g, fat_g}
    status      TEXT NOT NULL CHECK (status IN ('sending', 'set', 'not_set', 'uncertain')),
    write       TEXT,              -- what the write call said: sent | rejected | no_reply
    stored      TEXT,              -- JSON: the goal MFP showed when read back, if read
    error       TEXT,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);
