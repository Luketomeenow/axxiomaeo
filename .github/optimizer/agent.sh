#!/usr/bin/env bash
# Runs Claude Code headlessly for the AEO optimizer, with file tools only.
#   agent.sh <prompt-file> <result-json>
# Model access goes through Microsoft Foundry (CLAUDE_CODE_USE_FOUNDRY and the
# ANTHROPIC_FOUNDRY_* variables come from the workflow step). The settings
# file the workflow writes outside the checkout allows only Read, Edit, Write,
# Glob and Grep and denies the shell, the network and .env files. The flags
# below say the same again, so nothing in the repository can loosen it.
set -uo pipefail
prompt_file="$1"
result_json="$2"

help="$(claude --help 2>&1 || true)"
has() { grep -q -- "$1" <<<"$help"; }

args=(
  -p "$(cat "$prompt_file")"
  --output-format json
  --max-turns "${MAX_TURNS:-40}"
  --settings "$RUNNER_TEMP/claude-settings.json"
  --allowedTools "Read,Edit,Write,Glob,Grep"
  --append-system-prompt "$(cat .github/optimizer/rules.md)"
)
# Flag names have changed between Claude Code releases: add these only when
# the installed version lists them.
has "--disallowedTools" && args+=(--disallowedTools "Bash,WebFetch,WebSearch,NotebookEdit")
if has "dontAsk"; then args+=(--permission-mode dontAsk); else args+=(--permission-mode acceptEdits); fi

claude "${args[@]}" > "$result_json"
code=$?
# A run that stops early (turn limit, quota) can still leave useful edits;
# the workflow decides from the diff and the checks, and says so in the PR.
[[ $code -eq 0 ]] || echo "::warning::Claude Code exited with $code"
jq -r '"Claude Code: \(.subtype // "unknown"), \(.num_turns // "?") turns, est. $\(.total_cost_usd // 0)"' \
  "$result_json" 2>/dev/null || echo "Claude Code returned no JSON result"
exit 0
