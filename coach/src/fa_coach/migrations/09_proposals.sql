-- Proposals (ticket 09). Written and read through fa_coach/proposals.py.

-- One row per proposal (proposal.schema.json). `propose_change` stores it as
-- 'open' or 'blocked_by_guardrail'; a tap moves an open one on, claimed with
-- one conditional UPDATE (status = 'open'), so it is decided exactly once.
CREATE TABLE proposals (
    id                             TEXT PRIMARY KEY,
    phase_row_id                   TEXT NOT NULL REFERENCES phases (id),
    type                           TEXT NOT NULL CHECK (type IN ('calorie_change', 'calibration_change')),
    source                         TEXT NOT NULL,
    status                         TEXT NOT NULL CHECK (status IN ('open', 'approved', 'rejected', 'superseded', 'blocked_by_guardrail')),
    based_on_week                  TEXT,
    reason                         TEXT NOT NULL,
    delta_kcal                     REAL,
    is_phase_first_change          INTEGER NOT NULL DEFAULT 0,
    new_values                     TEXT,           -- JSON, calibration_change
    counter_of                     TEXT,
    returning_rejected_proposal_id TEXT,
    agent_disagrees                TEXT,
    user_reason                    TEXT,
    violations                     TEXT NOT NULL DEFAULT '[]',  -- JSON array of guardrail ids
    details                        TEXT NOT NULL DEFAULT '[]',  -- JSON: [{violation, text, earliest_checkin}]
    outcome                        TEXT,           -- JSON: what approval applied (targets before/after, MFP goal)
    reported_in                    TEXT,           -- iso week of the report that listed the applied change
    created_at                     TEXT NOT NULL,
    decided_at                     TEXT
);
CREATE INDEX proposals_status ON proposals (phase_row_id, status);

-- Messages that show a proposal's buttons (a weekly report, a proposal card).
-- After a tap each one is edited: buttons removed, the outcome shown.
CREATE TABLE proposal_cards (
    proposal_id TEXT NOT NULL REFERENCES proposals (id),
    ref         TEXT NOT NULL,  -- the message ref, e.g. 'weekly:12' or 'proposal:p_ab12cd34'
    text        TEXT,           -- the card's text; NULL for weekly reports (weekly_checkins.report)
    PRIMARY KEY (proposal_id, ref)
);
