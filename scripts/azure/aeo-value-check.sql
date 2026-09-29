-- AEO value check — READ-ONLY. Answers "is the AEO program producing anything?"
-- with the platform's own data in axxiom_hub (aeo schema + the marketing warehouse).
--
-- Run in Azure Cloud Shell:
--   curl -sO https://raw.githubusercontent.com/Luketomeenow/axxiomaeo/feat/azure-app-service/scripts/azure/aeo-value-check.sql
--   PGPASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)" \
--   psql "host=psql-axxiom-marketing.postgres.database.azure.com dbname=axxiom_hub user=luke.fernandez@axxiomelevator.com sslmode=require" \
--     -f aeo-value-check.sql > aeo-value-check.txt; cat aeo-value-check.txt
--
-- Nothing here writes. Paste the output back for analysis.
\set ON_ERROR_STOP off
\pset pager off
\pset footer off

-- Normalized "host/path" for matching URLs across GA4, CallRail and WordPress.
CREATE OR REPLACE FUNCTION pg_temp.norm_url(u text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT lower(regexp_replace(regexp_replace(split_part(split_part(coalesce(u,''), '?', 1), '#', 1),
                                             '^https?://(www\.)?', ''), '/+$', ''))
$$;
CREATE OR REPLACE FUNCTION pg_temp.url_path(u text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT lower(regexp_replace(regexp_replace(split_part(split_part(coalesce(u,''), '?', 1), '#', 1),
                                             '^https?://[^/]+', ''), '/+$', ''))
$$;

\echo '=== 1. Published AEO articles by brand and month ==='
SELECT brand_id, to_char(date_trunc('month', published_at), 'YYYY-MM') AS month, count(*) AS published
FROM aeo.content_pieces WHERE status = 'published' AND published_at IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2;

\echo '=== 2. Citation audits: per run, brand mentioned / own URL cited / our article cited ==='
SELECT to_char(min(checked_at), 'YYYY-MM-DD') AS run_date,
       count(*) AS checks,
       round(100.0 * avg(CASE WHEN is_mentioned THEN 1 ELSE 0 END), 1) AS mentioned_pct,
       round(100.0 * avg(CASE WHEN is_url_cited THEN 1 ELSE 0 END), 1) AS own_url_cited_pct,
       count(cited_post_id) AS answers_citing_an_aeo_article
FROM aeo.citation_records GROUP BY audit_run_id ORDER BY min(checked_at);

\echo '=== 3. Citation share, first vs latest month, by brand and engine ==='
WITH m AS (
  SELECT brand_id, platform, date_trunc('month', checked_at) AS month,
         avg(CASE WHEN is_mentioned THEN 1 ELSE 0 END) AS mentioned,
         avg(CASE WHEN is_url_cited THEN 1 ELSE 0 END) AS url_cited, count(*) AS n
  FROM aeo.citation_records GROUP BY 1, 2, 3)
SELECT brand_id, platform, to_char(month, 'YYYY-MM') AS month, n,
       round(100.0 * mentioned, 1) AS mentioned_pct, round(100.0 * url_cited, 1) AS url_cited_pct
FROM m ORDER BY brand_id, platform, month;

\echo '=== 4. Which of our articles AI engines actually cite (all time) ==='
SELECT c.brand_id, p.title, count(*) AS times_cited, string_agg(DISTINCT c.platform, ',') AS engines
FROM aeo.citation_records c JOIN aeo.content_pieces p ON p.id = c.cited_post_id
GROUP BY 1, 2 ORDER BY times_cited DESC LIMIT 25;
SELECT count(DISTINCT cited_post_id) AS distinct_articles_ever_cited,
       (SELECT count(*) FROM aeo.content_pieces WHERE status = 'published') AS published_articles
FROM aeo.citation_records WHERE cited_post_id IS NOT NULL;

\echo '=== 5. Who AI engines recommend instead (top competitors named, last 60 days) ==='
SELECT brand_id, competitor_cited, count(*) AS answers
FROM aeo.citation_records
WHERE competitor_cited IS NOT NULL AND competitor_cited <> '' AND checked_at > now() - interval '60 days'
GROUP BY 1, 2 ORDER BY answers DESC LIMIT 30;

\echo '=== 6. Queries where we ARE mentioned (last 60 days) — what works ==='
SELECT brand_id, platform, query, query_source
FROM aeo.citation_records
WHERE is_mentioned AND checked_at > now() - interval '60 days'
ORDER BY brand_id, platform LIMIT 60;

-- Latest GA4 snapshot per property/day (the warehouse keeps rolling snapshots).
CREATE TEMP TABLE ga AS
SELECT t.* FROM public.fact_ga4_traffic_daily t
JOIN (SELECT property_id, activity_date, max(snapshot_date) AS s
      FROM public.fact_ga4_traffic_daily WHERE activity_date >= date '2026-06-01'
      GROUP BY 1, 2) l
  ON l.property_id = t.property_id AND l.activity_date = t.activity_date AND l.s = t.snapshot_date;
CREATE TEMP TABLE aeo_brand_prop AS
SELECT id AS brand_id, regexp_replace(coalesce(ga4_property_id, ''), '\D', '', 'g') AS prop
FROM aeo.brands WHERE coalesce(ga4_property_id, '') <> '';
CREATE TEMP TABLE aeo_paths AS
SELECT brand_id, pg_temp.url_path(wp_post_url) AS path, pg_temp.norm_url(wp_post_url) AS url
FROM aeo.content_pieces WHERE status = 'published' AND wp_post_url NOT LIKE '%?p=%';

\echo '=== 7. Sessions per month by brand: all, AI-referred, and landing on AEO articles (organic / AI / other) ==='
SELECT b.brand_id, to_char(date_trunc('month', g.activity_date), 'YYYY-MM') AS month,
  sum(g.sessions) AS all_sessions,
  sum(g.sessions) FILTER (WHERE g.source ~* '(chatgpt|openai|perplexity|gemini|bard|copilot|claude|you\.com|meta\.ai|deepseek|grok)') AS ai_sessions,
  sum(g.sessions) FILTER (WHERE a.path IS NOT NULL) AS on_aeo_articles,
  sum(g.sessions) FILTER (WHERE a.path IS NOT NULL AND g.medium = 'organic') AS aeo_organic,
  sum(g.sessions) FILTER (WHERE a.path IS NOT NULL AND g.source ~* '(chatgpt|openai|perplexity|gemini|bard|copilot|claude)') AS aeo_ai,
  round(sum(g.conversions) FILTER (WHERE a.path IS NOT NULL), 1) AS aeo_conversions
FROM ga g
JOIN aeo_brand_prop b ON b.prop = regexp_replace(g.property_id, '\D', '', 'g')
LEFT JOIN aeo_paths a ON a.brand_id = b.brand_id AND a.path = pg_temp.url_path(g.landing_page)
GROUP BY 1, 2 ORDER BY 1, 2;

\echo '=== 8. Top 20 AEO articles by sessions since July ==='
SELECT a.brand_id, a.path, sum(g.sessions) AS sessions,
       sum(g.sessions) FILTER (WHERE g.medium = 'organic') AS organic,
       sum(g.sessions) FILTER (WHERE g.source ~* '(chatgpt|openai|perplexity|gemini|copilot|claude)') AS ai
FROM ga g
JOIN aeo_brand_prop b ON b.prop = regexp_replace(g.property_id, '\D', '', 'g')
JOIN aeo_paths a ON a.brand_id = b.brand_id AND a.path = pg_temp.url_path(g.landing_page)
GROUP BY 1, 2 ORDER BY sessions DESC LIMIT 20;
SELECT count(*) FILTER (WHERE s.sessions IS NULL) AS aeo_articles_with_zero_sessions, count(*) AS aeo_articles
FROM aeo_paths a LEFT JOIN (
  SELECT b.brand_id, pg_temp.url_path(g.landing_page) AS path, sum(g.sessions) AS sessions
  FROM ga g JOIN aeo_brand_prop b ON b.prop = regexp_replace(g.property_id, '\D', '', 'g')
  GROUP BY 1, 2) s ON s.brand_id = a.brand_id AND s.path = a.path;

\echo '=== 9. Phone calls that started on an AEO article, by month (CallRail) vs all calls ==='
CREATE TEMP TABLE calls AS
SELECT DISTINCT ON (call_id) call_id, start_time, answered, first_time_caller, source,
       pg_temp.norm_url(landing_page_url) AS landing, call_summary
FROM public.fact_callrail_call WHERE start_time >= date '2026-06-01'
ORDER BY call_id, snapshot_date DESC;
SELECT to_char(date_trunc('month', c.start_time), 'YYYY-MM') AS month,
       count(*) AS all_calls,
       count(*) FILTER (WHERE a.url IS NOT NULL) AS calls_on_aeo_articles,
       count(*) FILTER (WHERE a.url IS NOT NULL AND c.first_time_caller) AS first_time_on_aeo
FROM calls c LEFT JOIN aeo_paths a ON a.url = c.landing
GROUP BY 1 ORDER BY 1;
\echo '--- the calls themselves (first 300 chars of summary) ---'
SELECT to_char(c.start_time, 'YYYY-MM-DD') AS day, a.brand_id, a.path, c.first_time_caller,
       left(coalesce(c.call_summary, ''), 300) AS summary
FROM calls c JOIN aeo_paths a ON a.url = c.landing ORDER BY c.start_time;

\echo '=== 10. Program cost by month (cost ledger) ==='
SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS month, provider, operation,
       round(sum(cost_usd), 2) AS usd, count(*) AS events
FROM aeo.cost_events GROUP BY 1, 2, 3 ORDER BY 1, usd DESC;

\echo '=== 11. Monthly report rollups ==='
SELECT report_month, overall_citation_share, ai_referred_sessions, ai_referred_conversions,
       aeo_attributed_calls, content_pieces_published
FROM aeo.monthly_reports ORDER BY report_month;
