--
-- file: migrations/0002.airfields-and-wars.sql
--
CREATE TABLE IF NOT EXISTS airfields (
                                         code TEXT PRIMARY KEY,
                                         created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Recreate plane instances to bind with wars and airfields
DROP TABLE IF EXISTS plane_instances;
CREATE TABLE plane_instances (
                                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 war_number INTEGER NOT NULL,
                                 airfield_code TEXT NOT NULL,
                                 plane_type TEXT NOT NULL,
                                 added_by TEXT NOT NULL,
                                 removed_by TEXT,
                                 status TEXT DEFAULT 'IN_STOCK',
                                 kills INTEGER DEFAULT 0,
                                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                 FOREIGN KEY (airfield_code) REFERENCES airfields(code) ON DELETE CASCADE
);

-- Table to store configuration (like the persistent stockpile channel ID per guild/war)
CREATE TABLE IF NOT EXISTS bot_config (
                                          key TEXT PRIMARY KEY,
                                          value TEXT NOT NULL
);