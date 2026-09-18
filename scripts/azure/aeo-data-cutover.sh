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
# Prereqs:
#   export SUPABASE_DB_PASSWORD='...'   (or read it from the vault:
#     export SUPABASE_DB_PASSWORD="$(az keyvault secret show --vault-name kv-axxiom-marketing \
#       --name supabase-db-password --query value -o tsv)")
#   `az` logged in (Cloud Shell already is), and a pg client at least as new as
#   Supabase's server — Cloud Shell's stock pg_dump is older and refuses
#   ("aborting because of server version mismatch"). This script picks the
#   newest client under /usr/lib/postgresql/*/bin automatically; install one with
#   the commands it prints if none is new enough. Override with PG_BIN=/path/bin.
set -uo pipefail

SUPA="host=aws-1-ap-northeast-1.pooler.supabase.com port=5432 dbname=postgres user=postgres.cdlssoeqqfrgckpxewhn sslmode=require"
AZ_HOST=psql-axxiom-marketing.postgres.database.azure.com
AZ_USER="${AZ_USER:-luke.fernandez@axxiomelevator.com}"
AZ="host=$AZ_HOST dbname=axxiom_hub user=$AZ_USER sslmode=require"
DUMP=./aeo.dump
MODE="${1:-data}"

az_token() { az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv; }
: "${SUPABASE_DB_PASSWORD:?export SUPABASE_DB_PASSWORD first}"

# --- client version preflight -------------------------------------------------
# pg_dump refuses to dump a server NEWER than itself. Prefer the newest client
# installed on this machine (Debian/Ubuntu keep them side by side).
if [[ -z "${PG_BIN:-}" ]]; then
  PG_BIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)"
fi
[[ -n "${PG_BIN:-}" && -x "$PG_BIN/pg_dump" ]] && export PATH="$PG_BIN:$PATH"

client_major="$(pg_dump --version | sed -E 's/.* ([0-9]+).*/\1/')"
server_major="$(PGPASSWORD="$SUPABASE_DB_PASSWORD" psql "$SUPA" -tA -c 'show server_version' 2>/dev/null | cut -d. -f1)"
if [[ -z "$server_major" ]]; then
  echo "STOP: cannot reach Supabase — check SUPABASE_DB_PASSWORD."; exit 1
fi
echo "clients: pg_dump $client_major ($(command -v pg_dump))  |  supabase server: $server_major"
if (( client_major < server_major )); then
  cat <<HINT
STOP: pg_dump $client_major cannot dump a version-$server_major server.
Install a newer client, then re-run this script (Azure Cloud Shell, ~1 min):

  sudo install -d /usr/share/postgresql-common/pgdg
  sudo curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
  . /etc/os-release
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt \$VERSION_CODENAME-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
  sudo apt-get update -qq && sudo apt-get install -y postgresql-client-18

Cloud Shell containers are recycled, so this may need repeating in a new session.
HINT
  exit 1
fi
# -----------------------------------------------------------------------------

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
