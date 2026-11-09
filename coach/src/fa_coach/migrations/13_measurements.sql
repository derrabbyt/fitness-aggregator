-- Waist and photo check-ins (ticket 13). Written and read by features/measurements.py.

-- One row per waist value the user sends, with the date it was taken.
CREATE TABLE waist_measurements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,  -- ISO date
    cm          REAL NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX waist_measurements_date ON waist_measurements (date);

-- Photos the user sends, grouped into one set per day. `path` is relative to
-- the coach's state directory (e.g. photos/2026-11-09/1.jpg).
CREATE TABLE photos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_date    TEXT NOT NULL,  -- ISO date: the photo set it belongs to
    path        TEXT NOT NULL UNIQUE,
    caption     TEXT,
    received_at TEXT NOT NULL
);
CREATE INDEX photos_set_date ON photos (set_date);
