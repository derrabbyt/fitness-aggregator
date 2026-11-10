-- Partial days and day confirmations (ticket 20), read through fa_coach/daycheck.py
-- and written by fa_coach/features/day_questions.py. The coach never writes to the
-- MFP diary; a confirmation lives only here.

-- The user's word that a day's synced kcal are right: 'complete' (that's all
-- they ate) or 'real' (a high day is not a typo). It holds only while the day's
-- kcal are still the ones it was confirmed at.
CREATE TABLE day_confirmations (
    date         TEXT PRIMARY KEY,  -- ISO date of the day
    kind         TEXT NOT NULL,     -- 'complete' | 'real'
    kcal         REAL NOT NULL,     -- the synced kcal the day was confirmed at
    source       TEXT NOT NULL,     -- 'button' | 'chat'
    confirmed_at TEXT NOT NULL
);

-- Questions about a suspected day, one per day, kind and kcal: asked once.
CREATE TABLE day_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    kind        TEXT NOT NULL,      -- 'partial' | 'implausible'
    kcal        REAL NOT NULL,      -- the day's kcal when it was found
    status      TEXT NOT NULL,      -- 'pending' (not sent yet), 'asked', 'answered', 'dropped'
    answer      TEXT,               -- the tapped answer: 'complete' | 'log_rest' | 'real' | 'typo'
    found_at    TEXT NOT NULL,
    asked_at    TEXT,
    answered_at TEXT,
    UNIQUE (date, kind, kcal)
);
CREATE INDEX day_questions_status ON day_questions (status);
