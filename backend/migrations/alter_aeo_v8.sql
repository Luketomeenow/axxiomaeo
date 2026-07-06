-- AEO platform v8 — correct the axxiom brand identity (safe to re-run)
-- The axxiom row was seeded as the corporate site. The operating brand is
-- Axxiom Elevator Florida on axxiomelevatorfl.com (Pompano Beach + Sarasota).
-- Guarded on the old wp_url so it fires exactly once — manual Brand Settings
-- edits made after this migration are never clobbered on later restarts.
-- Note: keep comments semicolon-free — run_alter_migrations splits on that char.

UPDATE aeo.brands
SET name = 'Axxiom Elevator Florida',
    wp_url = 'https://axxiomelevatorfl.com',
    is_corporate = FALSE,
    markets = '["Pompano Beach FL", "Sarasota FL"]'::jsonb
WHERE id = 'axxiom'
  AND wp_url = 'https://axxiomelevator.com';
