-- The day a source last read its whole history window (coach-web ticket 13):
-- Hevy is re-read in full once a week, so sessions logged late still land.
ALTER TABLE sync_state ADD COLUMN full_read_on TEXT;
