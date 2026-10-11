-- When a sortie was reported, so a pilot's most recent report can be found and corrected.
ALTER TABLE plane_instances ADD COLUMN completed_at TEXT;
