-- Estimated kcal for reported sessions (ticket 14, features/training_plan.py).

-- Where a reported session's kcal came from, and the inputs of an estimate.
-- kcal_source: 'reported' (the user's number), 'estimated' (code: MET x
-- trend weight x hours), 'model_estimate' (the model's own number when code
-- couldn't estimate); NULL when there is no kcal (skipped, or a lift or
-- wrestling session that counts its per-session setup value).
ALTER TABLE session_statuses ADD COLUMN kcal_source TEXT
    CHECK (kcal_source IN ('reported', 'estimated', 'model_estimate'));
ALTER TABLE session_statuses ADD COLUMN activity TEXT;        -- MET table key, or the model's word
ALTER TABLE session_statuses ADD COLUMN duration_min REAL;
ALTER TABLE session_statuses ADD COLUMN met REAL;             -- set when code estimated
ALTER TABLE session_statuses ADD COLUMN trend_weight_kg REAL; -- set when code estimated
