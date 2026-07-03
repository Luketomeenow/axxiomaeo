-- AEO platform v7 — content_queue topic-discovery provenance (safe to re-run)
-- source marks where an auto-queued topic came from (citation_gap, search_demand,
-- coverage, manual) and source_detail stores the why (impressions, platform, etc).
-- Note: keep comments semicolon-free — run_alter_migrations splits on that char.

ALTER TABLE aeo.content_queue ADD COLUMN IF NOT EXISTS source VARCHAR(30);
ALTER TABLE aeo.content_queue ADD COLUMN IF NOT EXISTS source_detail JSONB;
