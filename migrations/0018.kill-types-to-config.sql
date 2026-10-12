-- Kill types are now configuration (app/features/airfield/kill_types.py). Reports store the type's key
-- instead of a row id, and the kill_types table goes away.
CREATE TABLE kill_report_items_new (
    report_id INTEGER NOT NULL REFERENCES kill_reports(id),
    kill_type TEXT NOT NULL,
    count INTEGER NOT NULL CHECK (count > 0),
    PRIMARY KEY (report_id, kill_type)
);

INSERT INTO kill_report_items_new (report_id, kill_type, count)
SELECT i.report_id,
       CASE t.label
           WHEN 'Toxot-902' THEN 'toxot'
           WHEN 'Harpy' THEN 'harpy'
           WHEN 'Myrmidon' THEN 'myrmidon'
           WHEN 'Pegasus' THEN 'pegasus'
           WHEN 'Tzykalia' THEN 'tzykalia'
           ELSE lower(t.label)
       END,
       i.count
FROM kill_report_items i JOIN kill_types t ON t.id = i.kill_type_id;

DROP TABLE kill_report_items;
ALTER TABLE kill_report_items_new RENAME TO kill_report_items;
DROP TABLE kill_types;
