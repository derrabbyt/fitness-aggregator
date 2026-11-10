-- Counter taps (ticket 10). The counter button asks for the user's number;
-- the reply within a day, if it is just a number, becomes a user_counter
-- proposal (features/proposals.py). A row is removed once its counter is made.
CREATE TABLE counter_taps (
    proposal_id TEXT PRIMARY KEY REFERENCES proposals (id),
    tapped_at   TEXT NOT NULL
);
