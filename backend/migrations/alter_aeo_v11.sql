-- AEO platform v11 -- cost_events ledger for billing-grade API cost tracking (safe to re-run)
-- One row per billable API call (Claude tokens, Ideogram images, Bright Data records)
-- with cost_usd computed at write time. Summed per month on the Reports page.
-- ORM create_all also builds this -- IF NOT EXISTS keeps this a no-op on fresh
-- installs and backfills it on any DB where create_all did not run.
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char.

CREATE TABLE IF NOT EXISTS aeo.cost_events (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(30) NOT NULL,
    operation VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    units INTEGER,
    cost_usd NUMERIC(10, 5) DEFAULT 0,
    brand_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_cost_events_created_at ON aeo.cost_events (created_at);
CREATE INDEX IF NOT EXISTS ix_cost_events_provider ON aeo.cost_events (provider);
