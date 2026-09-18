#!/bin/bash
# Install a modern PostgreSQL client into $HOME — no root required.
#
# Why: Azure Cloud Shell blocks sudo ("no new privileges" flag), and its stock
# pg_dump is older than Supabase's server, which makes pg_dump abort with
# "server version mismatch". This unpacks the PGDG .deb packages (the same ones
# apt would install) into ~/pgclient with dpkg-deb, which needs no privileges.
#
#   bash cloudshell-pg-client.sh          # installs client 18
#   bash cloudshell-pg-client.sh 17       # or a specific major
#
# Then either `source ~/pgclient/env.sh`, or just run aeo-data-cutover.sh —
# it finds this install on its own.
set -euo pipefail

MAJOR="${1:-18}"
PREFIX="$HOME/pgclient"
BASE="https://apt.postgresql.org/pub/repos/apt"

. /etc/os-release
CODENAME="${VERSION_CODENAME:?cannot read distro codename from /etc/os-release}"
ARCH="$(dpkg --print-architecture)"
echo "== $ID $VERSION_ID ($CODENAME/$ARCH) → $PREFIX =="

mkdir -p "$PREFIX"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

echo "== package index =="
if ! curl -fsSL "$BASE/dists/$CODENAME-pgdg/main/binary-$ARCH/Packages.gz" | gunzip > "$work/Packages"; then
  echo "STOP: no PGDG index for $CODENAME/$ARCH — tell me the codename above and I'll pick another."
  exit 1
fi

# Newest version of each package (the index lists several).
newest_deb() {
  awk -v pkg="$1" '
    $1=="Package:"  {cur=$2}
    $1=="Version:"  {ver=$2}
    $1=="Filename:" {if (cur==pkg) print ver "\t" $2}
  ' "$work/Packages" | sort -V | tail -1 | cut -f2
}

for pkg in libpq5 "postgresql-client-common" "postgresql-client-$MAJOR"; do
  deb="$(newest_deb "$pkg")"
  if [[ -z "$deb" ]]; then
    echo "STOP: $pkg not found in the $CODENAME-pgdg index"; exit 1
  fi
  echo "   $pkg  ←  $(basename "$deb")"
  curl -fsSL -o "$work/p.deb" "$BASE/$deb"
  dpkg-deb -x "$work/p.deb" "$PREFIX"
done

BIN="$PREFIX/usr/lib/postgresql/$MAJOR/bin"
LIB="$(dirname "$(find "$PREFIX" -name 'libpq.so.5*' | head -1)")"
[[ -x "$BIN/pg_dump" ]] || { echo "STOP: $BIN/pg_dump missing after unpack"; exit 1; }

cat > "$PREFIX/env.sh" <<ENVEOF
# source this to use the unpacked client: source ~/pgclient/env.sh
export PATH="$BIN:\$PATH"
export LD_LIBRARY_PATH="$LIB\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
ENVEOF

export LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
echo "== installed: $("$BIN/pg_dump" --version) =="
echo "   $BIN"
echo "   aeo-data-cutover.sh picks this up automatically; or: source ~/pgclient/env.sh"
