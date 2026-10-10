--
-- file: migrations/0004.depot-forum-threads.sql
--
ALTER TABLE airfields ADD COLUMN name TEXT;
ALTER TABLE airfields ADD COLUMN thread_id TEXT;