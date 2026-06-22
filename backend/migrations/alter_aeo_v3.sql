-- AEO platform v3 — probabilistic visibility + fan-out traceability
-- Run in Supabase SQL Editor after pulling AEO visibility improvements.

ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS is_mentioned BOOLEAN;
ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS is_url_cited BOOLEAN;
ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS visibility_pct DOUBLE PRECISION;
ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS sample_runs INTEGER DEFAULT 1;
ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS parent_query TEXT;
ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS funnel_stage VARCHAR(30);
