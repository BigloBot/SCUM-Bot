-- Where stocked aircraft came from: 'Produced', 'Purchased' or 'Other'.
-- Only set on rows added through Add Aircraft Stock. Older rows (and returned / unregistered rows) stay NULL;
-- the production stats count NULL as 'Other'.
ALTER TABLE plane_instances ADD COLUMN source TEXT;
