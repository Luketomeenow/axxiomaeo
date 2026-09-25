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

echo "== checks =="
psql "$AZ" -X -tA -F ' | ' -c "
  select 'tables with RLS (expect 0)', count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'aeo' and c.relkind = 'r' and c.relrowsecurity
  union all
  select 'tables the app cannot read/write (expect 0)', count(*) from pg_tables
   where schemaname = 'aeo'
     and not has_table_privilege('umi-marketing-functions', format('aeo.%I', tablename), 'SELECT,INSERT,UPDATE,DELETE')"
echo "done. If a check is not 0: run drop-supabase-rls.sql for RLS; ask Zach about missing grants."
