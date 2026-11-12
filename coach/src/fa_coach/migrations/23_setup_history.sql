-- Setup values as of the day (coach-followups ticket 03). Every change to a
-- phase's setup value adds a row valid from the day it takes effect;
-- phases.setup keeps the latest values. `key` is a setup key, with
-- logistics values as `logistics.<field>`; `value` is JSON. Readers take, per
-- key, the latest row with valid_from <= the day (phases.params_on).
-- source: phase_start (ref: the phase_setups id), setup_value (chat or web,
-- record_setup_value) or calibration (ref: the proposal id).
CREATE TABLE setup_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_row_id TEXT NOT NULL REFERENCES phases(id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    source TEXT NOT NULL,
    ref TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX setup_changes_phase ON setup_changes (phase_row_id, key, valid_from);

-- Seed: each phase's current setup, valid from its start date.
INSERT INTO setup_changes (phase_row_id, key, value, valid_from, source, ref, created_at)
SELECT p.id, j.key,
       CASE j.type WHEN 'object' THEN j.value WHEN 'array' THEN j.value WHEN 'true' THEN 'true'
                   WHEN 'false' THEN 'false' WHEN 'null' THEN 'null' ELSE json_quote(j.value) END,
       p.start_date, 'phase_start', p.setup_id, datetime('now')
FROM phases p, json_each(p.setup) j
WHERE j.key != 'logistics';

INSERT INTO setup_changes (phase_row_id, key, value, valid_from, source, ref, created_at)
SELECT p.id, 'logistics.' || j.key,
       CASE j.type WHEN 'object' THEN j.value WHEN 'array' THEN j.value WHEN 'true' THEN 'true'
                   WHEN 'false' THEN 'false' WHEN 'null' THEN 'null' ELSE json_quote(j.value) END,
       p.start_date, 'phase_start', p.setup_id, datetime('now')
FROM phases p, json_each(p.setup, '$.logistics') j
WHERE json_type(p.setup, '$.logistics') = 'object';
