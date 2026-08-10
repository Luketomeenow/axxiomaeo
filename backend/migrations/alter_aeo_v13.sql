-- AEO platform v13 -- demand-driven citation audits (safe to re-run)
-- query_source: where an audited query came from (custom | published | gsc | ghl | bank)
-- cited_post_id: ContentPiece.id when the AI engine cited a page we published
-- observed_questions: real customer questions pushed by the Foundry ghl-agent
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char

ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS query_source VARCHAR(20);

ALTER TABLE aeo.citation_records ADD COLUMN IF NOT EXISTS cited_post_id INTEGER;

CREATE TABLE IF NOT EXISTS aeo.observed_questions (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) REFERENCES aeo.brands(id),
    question TEXT NOT NULL,
    source VARCHAR(20),
    asked_at TIMESTAMP,
    external_ref VARCHAR(200),
    detail JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_observed_questions_brand_created ON aeo.observed_questions (brand_id, created_at DESC);

-- Backfill provenance for historical audit rows -- custom stays custom, everything else was bank
UPDATE aeo.citation_records SET query_source = CASE WHEN query_category = 'custom' THEN 'custom' ELSE 'bank' END WHERE query_source IS NULL;

-- Best-effort cited-post backfill on normalized URL equality (IS NULL guard keeps re-runs cheap)
UPDATE aeo.citation_records cr SET cited_post_id = cp.id FROM aeo.content_pieces cp
  WHERE cr.cited_post_id IS NULL AND cr.citation_url IS NOT NULL AND cp.wp_post_url IS NOT NULL
  AND cr.brand_id = cp.brand_id
  AND lower(regexp_replace(trim(trailing '/' from cr.citation_url), '^https?://(www\.)?', '')) = lower(regexp_replace(trim(trailing '/' from cp.wp_post_url), '^https?://(www\.)?', ''))
