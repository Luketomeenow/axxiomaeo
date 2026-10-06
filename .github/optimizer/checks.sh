#!/usr/bin/env bash
# Deterministic checks around the optimizer agent. No secrets are present
# when these run.
#   checks.sh guard   stage the agent's edits; fail when there are none or
#                     when they touch a protected path
#   checks.sh test    backend tests, frontend type check, frontend build;
#                     logs in $RUNNER_TEMP/checks, exit 1 when any fails
set -uo pipefail
out="$RUNNER_TEMP/checks"
mkdir -p "$out"

case "${1:-}" in
  guard)
    git add -A
    changed="$(git diff --cached --name-only)"
    if [[ -z "$changed" ]]; then
      echo "::error::The agent made no changes."
      exit 1
    fi
    bad="$(grep -E '^(\.github/|\.claude/|scripts/azure/)|(^|/)\.env($|\.)' <<<"$changed" || true)"
    if [[ -n "$bad" ]]; then
      echo "::error::The agent changed protected paths, so the change is rejected:"
      echo "$bad"
      exit 1
    fi
    echo "Changed files:"
    echo "$changed"
    git diff --cached --shortstat
    ;;
  test)
    (cd backend && python -m pytest -q -p no:cacheprovider tests) > "$out/backend.txt" 2>&1
    b=$?
    (cd frontend && npx tsc --noEmit -p .) > "$out/typecheck.txt" 2>&1
    t=$?
    (cd frontend && npm run build) > "$out/build.txt" 2>&1
    f=$?
    printf 'backend=%s\ntypecheck=%s\nbuild=%s\n' "$b" "$t" "$f" | tee "$out/status"
    [[ $b -eq 0 && $t -eq 0 && $f -eq 0 ]]
    ;;
  *)
    echo "usage: checks.sh guard|test" >&2
    exit 2
    ;;
esac
