-- AEO platform v16 -- optimization agent proposals (safe to re-run)
-- One row per change the optimization agent proposes on System Health, with the
-- human decision and, for code changes, the GitHub Actions run and pull request
-- the Claude Code agent produced. Rejected rows stay so they are not re-proposed
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char

CREATE TABLE IF NOT EXISTS aeo.optimization_proposals (
    id SERIAL PRIMARY KEY,
    trigger VARCHAR(20) DEFAULT 'manual',
    fingerprint VARCHAR(64) NOT NULL,
    title VARCHAR(300) NOT NULL,
    category VARCHAR(30) DEFAULT 'pipeline',
    priority VARCHAR(10) DEFAULT 'medium',
    brand_id VARCHAR(50),
    change_type VARCHAR(20) DEFAULT 'code',
    problem TEXT,
    proposed_change TEXT,
    instructions TEXT,
    acceptance TEXT,
    expected_impact TEXT,
    risk TEXT,
    evidence JSONB DEFAULT '[]'::jsonb,
    files_hint JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(20) DEFAULT 'proposed',
    decided_at TIMESTAMP,
    decided_by VARCHAR(100),
    decision_note TEXT,
    dispatched_at TIMESTAMP,
    branch VARCHAR(200),
    run_id BIGINT,
    run_url VARCHAR(500),
    pr_number INTEGER,
    pr_url VARCHAR(500),
    error TEXT,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_optimization_proposals_fingerprint ON aeo.optimization_proposals (fingerprint);

CREATE INDEX IF NOT EXISTS idx_optimization_proposals_status_created ON aeo.optimization_proposals (status, created_at DESC);
