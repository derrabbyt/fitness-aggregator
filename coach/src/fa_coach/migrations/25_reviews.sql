-- Reviews and body-fat estimates (coach-reviews ticket 01). Written and read
-- through fa_coach/reviews.py and fa_coach/body_fat.py; the block, phase and
-- photo reviews (tickets 02-04) store and send through reviews.send().

-- One row per review sent in Telegram. `key` is "<kind>:<caller's key>"
-- (e.g. "block:<phase id>:2"): a review is sent at most once per key.
CREATE TABLE reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    key          TEXT NOT NULL UNIQUE,
    kind         TEXT NOT NULL CHECK (kind IN ('block', 'phase', 'photo')),
    phase_row_id TEXT,              -- the phase it reviews; no foreign key (an erased phase's review stays)
    period_start TEXT NOT NULL,     -- ISO date: the first day it looks back over
    period_end   TEXT NOT NULL,     -- ISO date: the last day
    facts        TEXT NOT NULL,     -- JSON: the numbers code computed for it
    text         TEXT NOT NULL,     -- the message as sent
    created_at   TEXT NOT NULL      -- when it was sent (local time, with offset)
);
CREATE INDEX reviews_created_at ON reviews (created_at);

-- Body-fat estimates: the photo review's (source 'model') and the user's own
-- ('user'). For a date the user's latest wins over any model estimate.
CREATE TABLE body_fat_estimates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,       -- ISO date the estimate is for (the photo set's date)
    pct        REAL NOT NULL,
    source     TEXT NOT NULL CHECK (source IN ('model', 'user')),
    review_id  INTEGER REFERENCES reviews (id),  -- the photo review that made it (model)
    created_at TEXT NOT NULL
);
CREATE INDEX body_fat_estimates_date ON body_fat_estimates (date);
