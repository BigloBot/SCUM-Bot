--
-- file: migrations/0010.aircraft-types.sql
--
-- Predetermined aircraft list, shared by stock management and flight checkout.
-- `label` is exactly what plane_instances.plane_type stores, so existing rows keep matching.
-- Retire an aircraft by setting active = 0 (history is unaffected); add new ones with an INSERT.
--

CREATE TABLE IF NOT EXISTS aircraft_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    label TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

INSERT INTO aircraft_types (name, role, label, sort_order) VALUES
    ('Harbinger',  'Fighter',               'Harbinger (Fighter)',                1),
    ('Welkinrive', 'Heavy Bomber',          'Welkinrive (Heavy Bomber)',          2),
    ('Austringer', 'Torpedo Bomber',        'Austringer (Torpedo Bomber)',        3),
    ('Zealot',     'Paratrooper Transport', 'Zealot (Paratrooper Transport)',     4),
    ('White Raven','SeaFighter',            'White Raven (SeaFighter)',           5);
