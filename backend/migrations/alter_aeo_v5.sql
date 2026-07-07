-- AEO platform v5 — per-brand author name for content bylines (safe to re-run)
ALTER TABLE aeo.brands ADD COLUMN IF NOT EXISTS author_name VARCHAR(200);
