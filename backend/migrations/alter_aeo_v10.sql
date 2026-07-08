-- AEO platform v10 -- recommendation_actions table for the Recommendations Inbox (safe to re-run)
-- One row per approve/dismiss on a live-computed content recommendation. Approved
-- recs also enqueue a content_queue row and kick generation. Dismissed keys are
-- filtered out of the inbox for a cooldown window (see RecommendationService).
-- The ORM create_all also builds this table -- IF NOT EXISTS keeps this a no-op on
-- fresh installs and backfills it on any DB where create_all did not run.
-- Note: keep comments semicolon-free -- run_alter_migrations splits on that char.

CREATE TABLE IF NOT EXISTS aeo.recommendation_actions (
    id SERIAL PRIMARY KEY,
    key VARCHAR(300) NOT NULL,
    brand_id VARCHAR(50),
    query TEXT,
    action VARCHAR(30) NOT NULL,
    user_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_recommendation_actions_key ON aeo.recommendation_actions (key);
CREATE INDEX IF NOT EXISTS ix_recommendation_actions_action ON aeo.recommendation_actions (action);
