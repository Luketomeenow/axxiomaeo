-- AEO platform v2 — additive columns (safe to re-run)
-- Run in Supabase SQL Editor after pulling roadmap changes.

ALTER TABLE aeo.brands ADD COLUMN IF NOT EXISTS target_queries JSONB DEFAULT '[]';
ALTER TABLE aeo.brands ADD COLUMN IF NOT EXISTS service_page_urls JSONB DEFAULT '{}';

ALTER TABLE aeo.content_pieces ADD COLUMN IF NOT EXISTS source_citation_id INTEGER;
ALTER TABLE aeo.content_queue ADD COLUMN IF NOT EXISTS source_citation_id INTEGER;

ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS audit_run_id VARCHAR(36);

CREATE INDEX IF NOT EXISTS idx_citation_records_audit_run ON aeo.citation_records(audit_run_id);
