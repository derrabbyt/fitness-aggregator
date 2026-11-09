-- Weekly check-ins (ticket 07). Written by features/weekly_checkin.py, read
-- through weekly_facts.py (verdict history) and weekly_checkin.stored().

-- One row per check-in attempt. A successful one stores the facts the verdict
-- was based on, the verdict (after code's own rules), its rule ids, and how
-- the week counts for confirmation. A failed one stores the facts (if any)
-- and why it failed; a later /checkin may add a successful row for the week.
CREATE TABLE weekly_checkins (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_row_id            TEXT NOT NULL REFERENCES phases (id),
    iso_week                TEXT NOT NULL,
    start_date              TEXT NOT NULL,  -- ISO date, first day of the evaluated week
    end_date                TEXT NOT NULL,  -- ISO date, last day
    status                  TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
    facts                   TEXT,           -- JSON: weekly_facts.schema.json
    verdict                 TEXT,           -- JSON: weekly_verdict.schema.json, as stored
    rules_applied           TEXT,           -- JSON array of rule ids
    direction               TEXT,           -- the verdict's direction
    counts_for_confirmation INTEGER,        -- 0 for skipped weeks
    skip_reason             TEXT,           -- unusable | glycogen_window | adherence_gate | sport_load
    code_adjustments        TEXT,           -- JSON array: what code's rules changed in the model's verdict
    errors                  TEXT,           -- JSON array, failed check-ins
    report                  TEXT,           -- the report text sent
    created_at              TEXT NOT NULL
);
CREATE INDEX weekly_checkins_week ON weekly_checkins (iso_week, status);

-- Observations held back from daily messages for the weekly report
-- (ticket 11 writes them with deferred.add; the report marks them reported).
CREATE TABLE deferred_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,  -- ISO date the observation is about
    source        TEXT NOT NULL,  -- e.g. 'evening-recap'
    text          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    reported_week TEXT            -- iso_week of the report that carried it
);
CREATE INDEX deferred_items_open ON deferred_items (reported_week, date);
