-- AEO platform v15 -- store AEO-attributed phone calls on monthly reports (safe to re-run)
-- CallRail calls whose landing page is an AEO-published article -- snapshotted per month
-- so the Reports tab shows lead trends without live warehouse access
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char

ALTER TABLE aeo.monthly_reports ADD COLUMN IF NOT EXISTS aeo_attributed_calls INTEGER;
