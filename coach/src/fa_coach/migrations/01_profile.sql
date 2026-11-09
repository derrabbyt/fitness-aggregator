-- The coach profile: short, user-visible entries (preferences, known issues),
-- shown by /profile and changed through the chat.
CREATE TABLE profile (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
