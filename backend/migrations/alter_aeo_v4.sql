-- AEO platform v4 — content draft images
ALTER TABLE aeo.content_drafts ADD COLUMN IF NOT EXISTS images_json JSONB DEFAULT '[]';
ALTER TABLE aeo.content_drafts ADD COLUMN IF NOT EXISTS featured_media_id INTEGER;
