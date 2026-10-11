--
-- file: migrations/0011.bank.sql
--
-- Bank feature: officer stockpiles and the rare materials held in each.
-- Balances are never stored directly. They are the sum of bank_transactions, so every
-- change is kept for end-of-war reporting. Stockpiles are only ever soft-deleted.
--

-- The materials tracked in every stockpile. Add a row to track another, or set active = 0 to retire one.
CREATE TABLE bank_resource_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

INSERT INTO bank_resource_types (label, sort_order) VALUES
    ('Rare Metal', 1),
    ('Rare Alloy', 2);

CREATE TABLE bank_stockpiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    war_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    message_id TEXT,
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Name and code only need to be unique among active stockpiles in a war, so deleted ones free them up.
CREATE UNIQUE INDEX idx_bank_stockpiles_active_code ON bank_stockpiles (war_number, code) WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX idx_bank_stockpiles_active_name ON bank_stockpiles (war_number, name COLLATE NOCASE) WHERE status = 'ACTIVE';

CREATE TABLE bank_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stockpile_id INTEGER NOT NULL,
    resource TEXT NOT NULL,
    amount INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stockpile_id) REFERENCES bank_stockpiles(id)
);

CREATE INDEX idx_bank_transactions_stockpile ON bank_transactions (stockpile_id, resource);
