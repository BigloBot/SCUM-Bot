-- The passcode is just the access code for a stockpile, so it no longer has to be unique.
-- Names stay unique per war among ACTIVE rows.
DROP INDEX IF EXISTS idx_airfields_active_code;
DROP INDEX IF EXISTS idx_bank_stockpiles_active_code;
