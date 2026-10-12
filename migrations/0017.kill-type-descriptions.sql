-- The kill type text is now only shown as the dropdown description, so drop the word "Kills" from it.
UPDATE kill_types SET modal_label = REPLACE(modal_label, ' Kills', '');
