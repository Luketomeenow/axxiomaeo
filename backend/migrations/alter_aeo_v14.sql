-- AEO platform v14 -- flow health, improvement advisor, per-brand topic boost (safe to re-run)
-- topic_boost: extra daily topics/posts for a brand on top of the global limits
-- content_queue.updated_at: lets the health check spot stuck in_progress rows
-- advisor_reports: persisted AI improvement reports (history survives redeploys)
-- job_runs: outcome record per scheduled job firing (ran vs errored vs missed)
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char

ALTER TABLE aeo.brands ADD COLUMN IF NOT EXISTS topic_boost INTEGER DEFAULT 0;

ALTER TABLE aeo.content_queue ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS aeo.advisor_reports (
    id SERIAL PRIMARY KEY,
    trigger VARCHAR(20) DEFAULT 'manual',
    payload JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_advisor_reports_created ON aeo.advisor_reports (created_at DESC);

CREATE TABLE IF NOT EXISTS aeo.job_runs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50),
    status VARCHAR(20),
    detail TEXT,
    scheduled_for TIMESTAMP,
    finished_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_runs_job_finished ON aeo.job_runs (job_id, finished_at DESC);
