#!/bin/bash
# Apply the AEO schema migrations to Azure Postgres (axxiom_hub.aeo) by hand.
#
# On Azure the app never runs DDL (DB_MIGRATIONS_ON_STARTUP=false — the database
# admin's decision, 2026-09-25): the app identity also runs the hub functions,
# and making it an owner would give it owner rights over all of axxiom_hub. So
# on each deploy that adds a backend/migrations/alter_aeo_vN.sql file, run this
# in Azure Cloud Shell as Luke or Trey (default role dataservices, which owns
# the aeo tables, so new objects are owned correctly and mirror to Fabric):
#
#   curl -sO https://raw.githubusercontent.com/Luketomeenow/axxiomaeo/main/scripts/azure/apply-migrations.sh
#   bash apply-migrations.sh            # migrations from main
#   bash apply-migrations.sh my-branch  # or from a branch/tag being deployed
#
# Every alter_aeo_v*.sql file is idempotent (IF NOT EXISTS / IF EXISTS), so
# re-running the whole set is safe and is how the app applied them on Railway.
set -euo pipefail

REF="${1:-main}"
AZ_HOST=psql-axxiom-marketing.postgres.database.azure.com
AZ_USER="${AZ_USER:-luke.fernandez@axxiomelevator.com}"
AZ="host=$AZ_HOST dbname=axxiom_hub user=$AZ_USER sslmode=require"

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
echo "== fetching migrations from $REF =="
git clone -q --depth 1 --branch "$REF" https://github.com/Luketomeenow/axxiomaeo "$work/repo"
mapfile -t files < <(ls "$work/repo/backend/migrations"/alter_aeo_v*.sql | sort -V)
echo "   ${#files[@]} files"

export PGPASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
for f in "${files[@]}"; do
  printf '   %-24s ' "$(basename "$f")"
  psql "$AZ" -X -q -v ON_ERROR_STOP=1 -f "$f" >/dev/null && echo ok
done

# A table a migration creates is owned by dataservices (this login's default
# role) and starts with no grants for the app identity, so the app would get
# "permission denied" on it. Give the app the same rights it already has on
# every other aeo table (the grants from the cutover, AZURE_DEPLOY.md step 1).
echo "== app identity grants on aeo =="
psql "$AZ" -X -q -v ON_ERROR_STOP=1 -c "
  GRANT USAGE ON SCHEMA aeo TO \"umi-marketing-functions\";
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA aeo TO \"umi-marketing-functions\";
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA aeo TO \"umi-marketing-functions\";" && echo "   ok"

# The privilege check takes the table's OID, never a name. Postgres may run a
# WHERE condition on every table in the database before the schema filter,
# and "aeo.<name>" built for one of the hub's public tables doesn't exist: on
# 2026-10-05 that stopped this check with 'relation
# "aeo.fact_brightdata_place" does not exist'. An OID is always valid.
echo "== checks =="
psql "$AZ" -X -tA -F ' | ' -c "
  select 'tables with RLS (expect 0)', count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'aeo' and c.relkind = 'r' and c.relrowsecurity
  union all
  select 'tables the app cannot read/write (expect 0)', count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'aeo' and c.relkind in ('r', 'p')
     and not has_table_privilege('umi-marketing-functions', c.oid, 'SELECT,INSERT,UPDATE,DELETE')"
echo "done. If a check is not 0: run drop-supabase-rls.sql for RLS; ask Zach about missing grants."
