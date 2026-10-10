--
-- file: migrations/0008.depot-unique-active-per-war.sql
--
-- Depot name/code only need to be unique among ACTIVE depots in a war, so a deleted
-- depot's name and code can be reused. That means (war_number, code) is no longer a
-- unique parent key, so plane_instances can no longer carry a foreign key to airfields.
--

CREATE TABLE airfields_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT,
    location TEXT DEFAULT 'Unknown',
    thread_id TEXT,
    war_number INTEGER NOT NULL DEFAULT 1,
    status TEXT DEFAULT 'ACTIVE',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO airfields_new (id, code, name, location, thread_id, war_number, status, created_at)
SELECT id, code, name, location, thread_id, war_number, status, created_at FROM airfields;

CREATE TABLE plane_instances_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    war_number INTEGER NOT NULL,
    airfield_code TEXT NOT NULL,
    plane_type TEXT NOT NULL,
    added_by TEXT NOT NULL,
    removed_by TEXT,
    status TEXT DEFAULT 'IN_STOCK',
    kills INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    usecase TEXT,
    target_killed TEXT
);

INSERT INTO plane_instances_new
    (id, war_number, airfield_code, plane_type, added_by, removed_by, status, kills, created_at, usecase, target_killed)
SELECT id, war_number, airfield_code, plane_type, added_by, removed_by, status, kills, created_at, usecase, target_killed
FROM plane_instances;

DROP TABLE plane_instances;
DROP TABLE airfields;
ALTER TABLE airfields_new RENAME TO airfields;
ALTER TABLE plane_instances_new RENAME TO plane_instances;

CREATE UNIQUE INDEX idx_airfields_active_code ON airfields (war_number, code) WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX idx_airfields_active_name ON airfields (war_number, name) WHERE status = 'ACTIVE';
CREATE INDEX idx_plane_instances_depot ON plane_instances (war_number, airfield_code, status);
