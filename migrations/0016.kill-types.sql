-- Kill types are data: the Report Kills form and the kill board are built from this list.
-- `label` is the short name on the board; `modal_label` is the form field text (Discord caps it at 45 chars).
CREATE TABLE kill_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL UNIQUE,
    modal_label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);
INSERT INTO kill_types (label, modal_label, sort_order) VALUES
    ('Toxot-902', 'Toxot-902 “Blind Silver” Kills (Fighter)', 1),
    ('Harpy', 'Daimon aK-5 “Harpy” Kills (Heavy Fighter)', 2),
    ('Myrmidon', 'Mergo-4 “Myrmidon” Kills (Dive Bomber)', 3),
    ('Pegasus', 'V-5b Pegasus Kills (Paratrooper Plane)', 4),
    ('Tzykalia', 'Tzykalia Kills (Heavy Bomber)', 5);

-- Rebuild kill_reports without the fixed per-type columns; counts move to kill_report_items.
DROP INDEX IF EXISTS idx_kill_reports_war;
ALTER TABLE kill_reports RENAME TO kill_reports_old;

CREATE TABLE kill_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    war_number INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    media_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_kill_reports_war ON kill_reports (war_number, user_id);

CREATE TABLE kill_report_items (
    report_id INTEGER NOT NULL REFERENCES kill_reports(id),
    kill_type_id INTEGER NOT NULL REFERENCES kill_types(id),
    count INTEGER NOT NULL CHECK (count > 0),
    PRIMARY KEY (report_id, kill_type_id)
);

INSERT INTO kill_reports (id, war_number, user_id, created_at)
SELECT id, war_number, user_id, created_at FROM kill_reports_old;

INSERT INTO kill_report_items (report_id, kill_type_id, count)
SELECT id, (SELECT id FROM kill_types WHERE label = 'Toxot-902'), toxot FROM kill_reports_old WHERE toxot > 0;
INSERT INTO kill_report_items (report_id, kill_type_id, count)
SELECT id, (SELECT id FROM kill_types WHERE label = 'Harpy'), harpy FROM kill_reports_old WHERE harpy > 0;
INSERT INTO kill_report_items (report_id, kill_type_id, count)
SELECT id, (SELECT id FROM kill_types WHERE label = 'Myrmidon'), myrmidon FROM kill_reports_old WHERE myrmidon > 0;
INSERT INTO kill_report_items (report_id, kill_type_id, count)
SELECT id, (SELECT id FROM kill_types WHERE label = 'Pegasus'), pegasus FROM kill_reports_old WHERE pegasus > 0;
INSERT INTO kill_report_items (report_id, kill_type_id, count)
SELECT id, (SELECT id FROM kill_types WHERE label = 'Tzykalia'), tzykalia FROM kill_reports_old WHERE tzykalia > 0;

DROP TABLE kill_reports_old;
