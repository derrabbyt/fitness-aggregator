-- Context notes (context_note.schema.json): the user's words, dates, tags.
-- applies_to NULL = ongoing from applies_from; a single day has applies_to = applies_from.
CREATE TABLE context_notes (
    id                 TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    text               TEXT NOT NULL,
    applies_from       TEXT NOT NULL,  -- ISO date
    applies_to         TEXT,           -- ISO date or NULL
    tags               TEXT NOT NULL,  -- JSON array
    exercise_id        TEXT,
    suggest_unusable   TEXT NOT NULL CHECK (suggest_unusable IN ('yes', 'maybe', 'no')),
    follow_up_question TEXT
);
CREATE INDEX context_notes_dates ON context_notes (applies_from, applies_to);
