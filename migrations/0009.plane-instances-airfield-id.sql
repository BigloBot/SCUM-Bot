--
-- file: migrations/0009.plane-instances-airfield-id.sql
--
-- Tie every plane_instance to its airfield row by id. Airfields are only ever soft-deleted
-- (status = 'DELETED'), so plane history always stays attached to the depot it belonged to,
-- even if that depot's name/code is later reused by a new depot in the same war.
--

-- Safety net: create a placeholder (deleted) airfield for any plane whose depot row is missing,
-- so no plane history is lost or left unlinked.
INSERT INTO airfields (code, name, location, war_number, status)
SELECT DISTINCT p.airfield_code, p.airfield_code, 'Unknown', p.war_number, 'DELETED'
FROM plane_instances p
WHERE NOT EXISTS (
    SELECT 1 FROM airfields a WHERE a.code = p.airfield_code AND a.war_number = p.war_number
);

CREATE TABLE plane_instances_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    war_number INTEGER NOT NULL,
    airfield_id INTEGER NOT NULL,
    plane_type TEXT NOT NULL,
    added_by TEXT NOT NULL,
    removed_by TEXT,
    status TEXT DEFAULT 'IN_STOCK',
    kills INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    usecase TEXT,
    target_killed TEXT,
    FOREIGN KEY (airfield_id) REFERENCES airfields(id)
);

-- Several rows can share (war_number, code) once a depot was deleted and recreated;
-- historic planes map to the most recent active-or-latest row (best available guess).
INSERT INTO plane_instances_new
    (id, war_number, airfield_id, plane_type, added_by, removed_by, status, kills, created_at, usecase, target_killed)
SELECT p.id, p.war_number,
       (SELECT a.id FROM airfields a
         WHERE a.code = p.airfield_code AND a.war_number = p.war_number
         ORDER BY (a.status = 'ACTIVE') DESC, a.id DESC LIMIT 1),
       p.plane_type, p.added_by, p.removed_by, p.status, p.kills, p.created_at, p.usecase, p.target_killed
FROM plane_instances p;

-- Stock retired by the previous delete behaviour goes back to being plain stock of its (soft-deleted) depot.
UPDATE plane_instances_new SET status = 'IN_STOCK' WHERE status = 'DEPOT_DELETED';

DROP TABLE plane_instances;
ALTER TABLE plane_instances_new RENAME TO plane_instances;

CREATE INDEX idx_plane_instances_airfield ON plane_instances (airfield_id, status);
CREATE INDEX idx_plane_instances_war ON plane_instances (war_number, status);
