-- Ending a phase (coach-followups ticket 01). Written by features/phase_end.py
-- and features/phase_start.py (a new start ends the active phase), read
-- through phases.on(day).

-- A phase's last day. NULL while active (the phase runs on). An ended phase
-- ends the day before it was ended; a phase replaced on its start day gets
-- an empty span (end_date < start_date) and covers no day.
ALTER TABLE phases ADD COLUMN end_date TEXT;
UPDATE phases SET end_date = date(substr(ended_at, 1, 10), '-1 day')
 WHERE status = 'ended' AND ended_at IS NOT NULL;

-- End cards: one per request (`/endphase`, the chat tool `request_phase_end`).
-- A tap claims an open card once (status = 'open' -> 'confirmed'/'cancelled');
-- a newer card supersedes the older open ones. `mode` is what was asked:
-- 'end' (ticket 01; on the phase's start day it erases the phase, said on the
-- card) or 'undo' (ticket 02). `effect` is what the card promised ('end' or
-- 'erase'); a tap that would now do something else changes nothing.
CREATE TABLE phase_end_requests (
    id           TEXT PRIMARY KEY,
    phase_row_id TEXT NOT NULL,     -- no foreign key: an erased phase's card stays
    mode         TEXT NOT NULL,
    effect       TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('open', 'confirmed', 'cancelled', 'superseded')),
    reason       TEXT,
    text         TEXT NOT NULL,     -- the card's text, so a tap can edit it
    created_at   TEXT NOT NULL,
    decided_at   TEXT
);
