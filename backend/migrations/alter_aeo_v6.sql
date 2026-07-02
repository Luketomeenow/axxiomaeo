-- AEO platform v6 — hot-path indexes (safe to re-run)
-- Dashboards order citation_records by checked_at and content_pieces by
-- published_at. Inbox pages filter drafts/deployments by brand_id + status.
-- Note: keep comments semicolon-free — run_alter_migrations splits on that char.
-- (v5 is reserved by the per-brand authors/phone PR: feat/content-enhancements.)

CREATE INDEX IF NOT EXISTS idx_citation_records_checked_at ON aeo.citation_records (checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_pieces_brand_published ON aeo.content_pieces (brand_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_drafts_brand_status ON aeo.content_drafts (brand_id, status);
CREATE INDEX IF NOT EXISTS idx_schema_deployments_brand_status ON aeo.schema_deployments (brand_id, status);
