-- Remove the Supabase Row-Level Security policies from the aeo schema on Azure.
--
-- Approved by the database admin (Zach, 2026-09-25): the policies were written
-- for Supabase's anon/authenticated PostgREST roles and protect nothing on
-- Azure, where access is controlled by grants. The AEO app does not rely on
-- RLS anywhere — no SET ROLE, no auth.uid(), one application role, and the
-- FastAPI JWT check is the only gatekeeper. Left in place, the policies make
-- every aeo table read as empty to the app identity (umi-marketing-functions).
--
-- Run in Azure Cloud Shell as Luke (default role: dataservices, which owns the
-- restored tables):
--   PGPASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)" \
--   psql "host=psql-axxiom-marketing.postgres.database.azure.com dbname=axxiom_hub user=luke.fernandez@axxiomelevator.com sslmode=require" \
--     -f drop-supabase-rls.sql
--
-- Idempotent: safe to re-run; a second run changes nothing.
\set ON_ERROR_STOP on

\echo '== BEFORE: aeo tables with RLS, and their policies =='
SELECT c.relname AS table_name,
       c.relrowsecurity AS rls_on,
       (SELECT count(*) FROM pg_policies p WHERE p.schemaname = 'aeo' AND p.tablename = c.relname) AS policies
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'aeo' AND c.relkind = 'r' AND (c.relrowsecurity OR EXISTS (
  SELECT 1 FROM pg_policies p WHERE p.schemaname = 'aeo' AND p.tablename = c.relname))
ORDER BY 1;

BEGIN;
DO $$
DECLARE pol record; tbl record;
BEGIN
  FOR pol IN SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'aeo' LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON aeo.%I', pol.policyname, pol.tablename);
  END LOOP;
  FOR tbl IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'aeo' AND c.relkind = 'r' AND (c.relrowsecurity OR c.relforcerowsecurity) LOOP
    EXECUTE format('ALTER TABLE aeo.%I NO FORCE ROW LEVEL SECURITY', tbl.relname);
    EXECUTE format('ALTER TABLE aeo.%I DISABLE ROW LEVEL SECURITY', tbl.relname);
  END LOOP;
END $$;
COMMIT;

\echo '== AFTER: expect 0 and 0 =='
SELECT (SELECT count(*) FROM pg_policies WHERE schemaname = 'aeo') AS policies_left,
       (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'aeo' AND c.relkind = 'r' AND c.relrowsecurity) AS tables_with_rls;

\echo '== app identity can read and write every aeo table (expect t) =='
SELECT bool_and(has_table_privilege('umi-marketing-functions', format('aeo.%I', tablename),
                                    'SELECT,INSERT,UPDATE,DELETE'))
FROM pg_tables WHERE schemaname = 'aeo';
