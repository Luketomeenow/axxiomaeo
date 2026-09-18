#!/bin/bash
# Install a modern PostgreSQL client into $HOME — no root required.
#
# Why: pg_dump refuses to dump a server newer than itself, Azure Cloud Shell's
# stock client is older than Supabase's server, and Cloud Shell blocks sudo
# ("no new privileges"), so no package manager is available. Two rootless
# strategies, picked automatically:
#
#   1. Debian/Ubuntu  → unpack the PGDG .debs with dpkg-deb
#   2. anything else  → micromamba + conda-forge (Azure Linux, RHEL, …)
#
#   bash cloudshell-pg-client.sh          # newest client (>= 17)
#   bash cloudshell-pg-client.sh 17       # pin a major
#
# Afterwards `source ~/pgclient/env.sh`, or just run aeo-data-cutover.sh —
# it finds this install on its own.
set -euo pipefail

MAJOR="${1:-}"
PREFIX="$HOME/pgclient"
mkdir -p "$PREFIX"

ID=""; VERSION_ID=""; VERSION_CODENAME=""
[[ -r /etc/os-release ]] && . /etc/os-release
echo "== host: ${ID:-unknown} ${VERSION_ID:-} (${VERSION_CODENAME:-no codename}) $(uname -m) =="

install_deb() {
  local codename="$1" major="${2:-18}" base="https://apt.postgresql.org/pub/repos/apt"
  local arch work deb
  arch="$(dpkg --print-architecture)"
  work="$(mktemp -d)"; trap 'rm -rf "$work"' RETURN
  echo "== PGDG packages ($codename/$arch) =="
  curl -fsSL "$base/dists/$codename-pgdg/main/binary-$arch/Packages.gz" | gunzip > "$work/Packages" || return 1
  for pkg in libpq5 postgresql-client-common "postgresql-client-$major"; do
    deb="$(awk -v p="$pkg" '
      $1=="Package:"{c=$2} $1=="Version:"{v=$2}
      $1=="Filename:"{if(c==p) print v"\t"$2}' "$work/Packages" | sort -V | tail -1 | cut -f2)"
    [[ -n "$deb" ]] || { echo "   $pkg not in index"; return 1; }
    echo "   $pkg  ←  $(basename "$deb")"
    curl -fsSL -o "$work/p.deb" "$base/$deb" || return 1
    dpkg-deb -x "$work/p.deb" "$PREFIX" || return 1
  done
  BIN="$PREFIX/usr/lib/postgresql/$major/bin"
  LIB="$(dirname "$(find "$PREFIX" -name 'libpq.so.5*' | head -1)")"
}

install_conda() {
  local spec mm_arch
  spec="postgresql${MAJOR:+=$MAJOR}"; [[ -z "$MAJOR" ]] && spec="postgresql>=17"
  case "$(uname -m)" in
    x86_64) mm_arch=linux-64 ;;
    aarch64|arm64) mm_arch=linux-aarch64 ;;
    *) echo "STOP: unsupported architecture $(uname -m)"; return 1 ;;
  esac
  echo "== micromamba + conda-forge ($mm_arch, $spec) — a ~100 MB download =="
  if [[ ! -x "$PREFIX/bin/micromamba" ]]; then
    mkdir -p "$PREFIX/bin"
    curl -Ls "https://micro.mamba.pm/api/micromamba/$mm_arch/latest" \
      | tar -xj -C "$PREFIX" --strip-components=1 bin/micromamba || return 1
    chmod +x "$PREFIX/bin/micromamba"
  fi
  "$PREFIX/bin/micromamba" create -y -q -p "$PREFIX/pg" -c conda-forge "$spec" >/dev/null || return 1
  BIN="$PREFIX/pg/bin"
  LIB="$PREFIX/pg/lib"
}

BIN=""; LIB=""
if [[ -n "$VERSION_CODENAME" ]] && command -v dpkg-deb >/dev/null && command -v dpkg >/dev/null; then
  install_deb "$VERSION_CODENAME" "${MAJOR:-18}" || { echo "== .deb path failed, falling back =="; BIN=""; }
fi
if [[ -z "$BIN" || ! -x "$BIN/pg_dump" ]]; then
  install_conda || { echo "STOP: could not install a client. Paste /etc/os-release and I'll adapt this."; exit 1; }
fi

[[ -x "$BIN/pg_dump" ]] || { echo "STOP: $BIN/pg_dump missing after install"; exit 1; }
cat > "$PREFIX/env.sh" <<ENVEOF
# source this to use the installed client: source ~/pgclient/env.sh
export PATH="$BIN:\$PATH"
export LD_LIBRARY_PATH="$LIB\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
ENVEOF
export LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
echo "== installed: $("$BIN/pg_dump" --version) =="
echo "   $BIN"
echo "   aeo-data-cutover.sh picks this up automatically; or: source ~/pgclient/env.sh"
