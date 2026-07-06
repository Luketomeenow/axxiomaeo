-- AEO platform v9 — retire motion, evolution, ironhawk brands (safe to re-run)
-- Roster decision 2026-07-06: the AEO system covers five operating brands
-- (axxiom FL, ameritex, arizona_es, liftech, quality). Removes the retired
-- brands and their queue/draft/piece/citation/schema rows so workers, topic
-- discovery, and dashboards stop targeting them. Live WordPress posts on the
-- retired sites are not touched. Stored monthly report JSON keeps history.
-- Note: keep comments semicolon-free — run_alter_migrations splits on that char.

DELETE FROM aeo.citation_records WHERE brand_id IN ('motion', 'evolution', 'ironhawk');
DELETE FROM aeo.schema_jobs WHERE brand_id IN ('motion', 'evolution', 'ironhawk');
DELETE FROM aeo.schema_deployments WHERE brand_id IN ('motion', 'evolution', 'ironhawk');
DELETE FROM aeo.content_queue WHERE brand_id IN ('motion', 'evolution', 'ironhawk');
DELETE FROM aeo.content_drafts WHERE brand_id IN ('motion', 'evolution', 'ironhawk');
DELETE FROM aeo.content_pieces WHERE brand_id IN ('motion', 'evolution', 'ironhawk');
DELETE FROM aeo.brands WHERE id IN ('motion', 'evolution', 'ironhawk');
