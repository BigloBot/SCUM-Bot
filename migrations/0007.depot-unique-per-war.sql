--
-- file: migrations/0007.depot-unique-per-war.sql
--
-- Depot code/name were globally unique (code was the PRIMARY KEY), so the same
-- depot could not be recreated in a later war. Make them unique per war instead.
-- plane_instances now references airfields by (war_number, code).
--

CREATE TABLE airfields_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT,
    location TEXT DEFAULT 'Unknown',
    thread_id TEXT,
    war_number INTEGER NOT NULL DEFAULT 1,
    status TEXT DEFAULT 'ACTIVE',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (war_number, code),
    UNIQUE (war_number, name)
);

INSERT INTO airfields_new (code, name, location, thread_id, war_number, status, created_at)
SELECT code, name, location, thread_id, COALESCE(war_number, 1), status, created_at
FROM airfields;

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
    target_killed TEXT,
    FOREIGN KEY (war_number, airfield_code) REFERENCES airfields(war_number, code) ON DELETE CASCADE
);

-- Old codes were globally unique, so each plane maps to exactly one depot; take the war from the depot.
INSERT INTO plane_instances_new
    (id, war_number, airfield_code, plane_type, added_by, removed_by, status, kills, created_at, usecase, target_killed)
SELECT p.id, COALESCE(a.war_number, p.war_number), p.airfield_code, p.plane_type, p.added_by,
       p.removed_by, p.status, p.kills, p.created_at, p.usecase, p.target_killed
FROM plane_instances p
LEFT JOIN airfields a ON a.code = p.airfield_code;

DROP TABLE plane_instances;
DROP TABLE airfields;
ALTER TABLE airfields_new RENAME TO airfields;
ALTER TABLE plane_instances_new RENAME TO plane_instances;
