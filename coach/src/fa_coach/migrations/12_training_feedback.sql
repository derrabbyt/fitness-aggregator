-- Training feedback (ticket 12). Written and read by features/training_feedback.py.

-- The feedback message sent about one session (ref "training:<session id>"),
-- kept so a tap on its reset buttons can edit it.
CREATE TABLE training_feedback (
    session_id TEXT PRIMARY KEY,
    ref        TEXT NOT NULL,
    text       TEXT NOT NULL,
    sent_at    TEXT NOT NULL
);

-- "Was this a reset?" questions: one per exercise with a possible reset in a
-- session. A tap claims the open question once: `reset` starts a new
-- baseline from that session, `not_reset` leaves the history as it is.
CREATE TABLE reset_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    name        TEXT NOT NULL,
    session_date TEXT NOT NULL,
    drop_pct    REAL,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reset', 'not_reset')),
    created_at  TEXT NOT NULL,
    answered_at TEXT,
    UNIQUE (session_id, exercise_id)
);
