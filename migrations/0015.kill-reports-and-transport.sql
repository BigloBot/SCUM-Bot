-- Kills are reported on their own, independent of flight returns.
CREATE TABLE kill_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    war_number INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    toxot INTEGER NOT NULL DEFAULT 0,
    harpy INTEGER NOT NULL DEFAULT 0,
    myrmidon INTEGER NOT NULL DEFAULT 0,
    pegasus INTEGER NOT NULL DEFAULT 0,
    tzykalia INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_kill_reports_war ON kill_reports (war_number, user_id);

-- Where a sortie delivered its aircraft (a transport flight's destination depot; the source depot otherwise).
ALTER TABLE plane_instances ADD COLUMN destination_airfield_id INTEGER REFERENCES airfields(id);

-- Carry over kills already reported on sorties so the kill board keeps its history.
INSERT INTO kill_reports (war_number, user_id, toxot, harpy, myrmidon, pegasus, tzykalia, created_at)
SELECT war_number, removed_by, toxot_kills, harpy_kills, myrmidon_kills, pegasus_kills, tzykalia_kills,
       COALESCE(completed_at, created_at)
FROM plane_instances
WHERE status IN ('Returned', 'Loss') AND removed_by IS NOT NULL
  AND (toxot_kills + harpy_kills + myrmidon_kills + pegasus_kills + tzykalia_kills) > 0;
