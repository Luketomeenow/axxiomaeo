-- AEO platform v17 -- CallRail calls already scanned for customer questions (safe to re-run)
-- One row per call whose summary the daily scan has read, so no call is sent
-- to the model twice -- questions is how many customer questions it produced
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char

CREATE TABLE IF NOT EXISTS aeo.call_question_scans (
    call_id VARCHAR(100) PRIMARY KEY,
    brand_id VARCHAR(50),
    questions INTEGER DEFAULT 0,
    scanned_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_call_question_scans_scanned ON aeo.call_question_scans (scanned_at DESC);
