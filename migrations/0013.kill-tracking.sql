-- Per-aircraft-type kill counts for each finished sortie, for the kill board and end-of-war reports.
-- `kills` stays as the sortie total.
ALTER TABLE plane_instances ADD COLUMN toxot_kills INTEGER NOT NULL DEFAULT 0;
ALTER TABLE plane_instances ADD COLUMN harpy_kills INTEGER NOT NULL DEFAULT 0;
ALTER TABLE plane_instances ADD COLUMN myrmidon_kills INTEGER NOT NULL DEFAULT 0;
ALTER TABLE plane_instances ADD COLUMN pegasus_kills INTEGER NOT NULL DEFAULT 0;
ALTER TABLE plane_instances ADD COLUMN tzykalia_kills INTEGER NOT NULL DEFAULT 0;
