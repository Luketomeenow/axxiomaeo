-- AEO platform v12 -- store AI-referred conversions (GA4 key events) on monthly reports (safe to re-run)
-- GA4 already returns conversions for AI-referred sessions but the number was dropped --
-- this column snapshots it monthly so conversion trends render without live GA4 access
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char

ALTER TABLE aeo.monthly_reports ADD COLUMN IF NOT EXISTS ai_referred_conversions INTEGER;
