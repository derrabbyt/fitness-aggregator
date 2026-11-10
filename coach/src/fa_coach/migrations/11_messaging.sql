-- Unprompted messages and deferred items (ticket 11), read and written through
-- fa_coach/messaging.py.

-- One row per unprompted message sent (jobs, not chat replies). Non-exempt
-- rows count toward the daily message limit.
CREATE TABLE unprompted_messages (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    day    TEXT NOT NULL,     -- local ISO date the message was sent
    kind   TEXT NOT NULL,     -- the sender, e.g. 'evening-reminder', 'evening-recap'
    exempt INTEGER NOT NULL,  -- 1 = not counted (the reset question)
    at     TEXT NOT NULL
);
CREATE INDEX unprompted_messages_day ON unprompted_messages (day);

-- Observations held back from daily messages for the weekly report.
CREATE TABLE deferred_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    day        TEXT NOT NULL,  -- ISO date the item is about
    source     TEXT NOT NULL,  -- e.g. 'evening-recap'
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX deferred_items_day ON deferred_items (day);
