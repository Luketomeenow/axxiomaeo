#!/bin/bash
# AEO DATA COPY — run inside Azure Cloud Shell (bash) as Luke.
# Copies the `aeo` schema from Supabase into Azure Postgres (axxiom_hub.aeo) and
# proves row-for-row equality. Safe to re-run. Two modes:
#
#   bash aeo-data-cutover.sh --init     FIRST RUN: schema + data (creates the tables
#                                       under your login → owned by dataservices,
#                                       mirrored to Fabric). Azure aeo must be empty.
#   bash aeo-data-cutover.sh            CUTOVER: data-only — wipe Azure aeo rows, reload,
#                                       verify. Railway must be STOPPED first (one writer).
#
# Prereqs: export SUPABASE_DB_PASSWORD='...' (Supabase → Project Settings → Database;
# same value as the vault secret supabase-db-password). `az` is logged in (Cloud Shell is).
set -uo pipefail

SUPA="host=aws-1-ap-northeast-1.pooler.supabase.com port=5432 dbname=postgres user=postgres.cdlssoeqqfrgckpxewhn sslmode=require"
AZ_HOST=psql-axxiom-marketing.postgres.database.azure.com
AZ_USER="${AZ_USER:-luke.fernandez@axxiomelevator.com}"
AZ="host=$AZ_HOST dbname=axxiom_hub user=$AZ_USER sslmode=require"
DUMP=./aeo.dump
MODE="${1:-data}"

az_token() { az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv; }
: "${SUPABASE_DB_PASSWORD:?export SUPABASE_DB_PASSWORD first}"

if [[ "$MODE" == "--init" ]]; then
  echo "== 1/4 dump Supabase aeo (schema + data) =="
  PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump "$SUPA" --schema=aeo -Fc --no-owner --no-privileges -f "$DUMP" || exit 1
  ls -lh "$DUMP"

  echo "== 2/4 Azure aeo must be empty =="
  n=$(PGPASSWORD="$(az_token)" psql "$AZ" -tA -c "select count(*) from information_schema.tables where table_schema='aeo'")
  if [[ "$n" != "0" ]]; then echo "STOP: aeo already has $n tables on Azure — use data mode (no --init)"; exit 1; fi

  echo "== 3/4 restore schema + data into Azure (tables created as $AZ_USER → default role dataservices) =="
  PGPASSWORD="$(az_token)" pg_restore -h "$AZ_HOST" -U "$AZ_USER" -d axxiom_hub \
    --no-owner --no-privileges --schema=aeo "$DUMP" 2>&1 | grep -iE "error|warning" | grep -v "already exists" | head -10
  echo "restore finished"
else
  echo "== 1/4 dump Supabase aeo (data only) =="
  PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump "$SUPA" --schema=aeo --data-only -Fc --no-owner --no-privileges -f "$DUMP" || exit 1
  ls -lh "$DUMP"

  echo "== 2/4 wipe Azure aeo rows (reverse dependency order, one transaction) =="
  pg_restore -l "$DUMP" | grep "TABLE DATA" | awk '{print $6}' | tac > /tmp/aeo_tables_rev.txt
  { echo "begin;"; awk '{printf "delete from aeo.\"%s\";\n", $1}' /tmp/aeo_tables_rev.txt; echo "commit;"; } > /tmp/aeo_wipe.sql
  if PGPASSWORD="$(az_token)" psql "$AZ" -q -v ON_ERROR_STOP=1 -f /tmp/aeo_wipe.sql >/dev/null 2>/tmp/aeo_wipe.err; then
    echo "wiped $(wc -l < /tmp/aeo_tables_rev.txt) tables"
  else
    echo "transactional wipe failed — $(grep -m1 -iE 'error' /tmp/aeo_wipe.err)"; echo "STOP: nothing was loaded."; exit 1
  fi

  echo "== 3/4 load data into Azure =="
  PGPASSWORD="$(az_token)" pg_restore -h "$AZ_HOST" -U "$AZ_USER" -d axxiom_hub \
    --data-only --no-owner --no-privileges --schema=aeo "$DUMP" 2>&1 | grep -iE "error|warning" | head -10
  echo "load finished"
fi

echo "== 4/4 verify exact counts (Supabase vs Azure) =="
PGPASSWORD="$SUPABASE_DB_PASSWORD" psql "$SUPA" -tA -c "
  select string_agg(format('select %L as t, count(*) as n from aeo.%I', table_name, table_name), ' union all ')
  from information_schema.tables where table_schema='aeo' and table_type='BASE TABLE'" > /tmp/aeo_countq.sql
PGPASSWORD="$SUPABASE_DB_PASSWORD" psql "$SUPA" -tA -F $'\t' -f /tmp/aeo_countq.sql | sort > /tmp/aeo_counts_supabase.tsv
PGPASSWORD="$(az_token)" psql "$AZ" -tA -F $'\t' -f /tmp/aeo_countq.sql | sort > /tmp/aeo_counts_azure.tsv
echo "table	supabase	azure	status"
join -t $'\t' /tmp/aeo_counts_supabase.tsv /tmp/aeo_counts_azure.tsv | awk -F'\t' '{s=($2==$3)?"MATCH":"MISMATCH"; if(s=="MISMATCH")m++; print $1"\t"$2"\t"$3"\t"s} END{print "---"; print (m+0)" mismatches / "NR" tables"}'

echo "== app identity can use the tables? (must be true/true) =="
PGPASSWORD="$(az_token)" psql "$AZ" -tA -c "
  select has_schema_privilege('umi-marketing-functions','aeo','USAGE'),
         bool_and(has_table_privilege('umi-marketing-functions', format('aeo.%I', table_name), 'SELECT,INSERT,UPDATE,DELETE'))
  from information_schema.tables where table_schema='aeo' and table_type='BASE TABLE'"
