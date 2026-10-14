-- A kill report belongs to the sortie it was reported for when one can be identified.
-- Older reports and reports made without a current-war flight remain valid but unbound.
ALTER TABLE kill_reports ADD COLUMN flight_id INTEGER REFERENCES plane_instances(id);
CREATE INDEX idx_kill_reports_flight ON kill_reports(flight_id);