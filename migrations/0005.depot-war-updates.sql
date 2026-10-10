--
-- file: migrations/0005.depot-war-updates.sql
--
ALTER TABLE airfields ADD COLUMN war_number INTEGER DEFAULT 1;
ALTER TABLE airfields ADD COLUMN location TEXT DEFAULT 'Unknown';
ALTER TABLE airfields ADD COLUMN status TEXT DEFAULT 'ACTIVE';