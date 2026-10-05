#!/bin/zsh
# Push the AEO backend's environment to app-axxiom-aeo as App Service settings:
# secrets become @Microsoft.KeyVault references into kv-axxiom-marketing (loaded
# into the vault from ENV_FILE when missing), config vars are plain values, and
# the Azure-specific platform settings are fixed below.
#   ./scripts/azure/sync-app-settings.sh                      # dry-run
#   ./scripts/azure/sync-app-settings.sh --apply              # settings + vault secrets
#   ./scripts/azure/sync-app-settings.sh --apply --no-secrets # platform/config only, no vault
#   ./scripts/azure/sync-app-settings.sh --apply --live       # cutover: SCHEDULER_ENABLED=true
#
# ENV_FILE is the source of secret VALUES and defaults to backend/.env, which is
# a developer file and can drift from what production actually runs. Before the
# cutover, export the live Railway variables and point ENV_FILE at them:
#   railway variables --json | python3 -c 'import json,sys; [print(f"{k}={v}") for k,v in json.load(sys.stdin).items()]' > backend/.env.railway
#   ENV_FILE=backend/.env.railway ./scripts/azure/sync-app-settings.sh --apply
# Vault names = env name lowercased, '_' → '-' (hub convention). The six
# wp-app-password-* and wp-username-* secrets already exist from the hub —
# they are shared, not duplicated.
set -euo pipefail
cd "$(dirname "$0")/../.."

APP="${APP:-app-axxiom-aeo}"
RG="${RG:-Axxiom-devs-foundry}"
VAULT="${VAULT:-kv-axxiom-marketing}"
ENV_FILE="${ENV_FILE:-backend/.env}"
APPLY=false; LIVE=false; NO_SECRETS=false
for arg in "$@"; do
  [[ "$arg" == "--apply" ]] && APPLY=true
  [[ "$arg" == "--live" ]] && LIVE=true
  [[ "$arg" == "--no-secrets" ]] && NO_SECRETS=true
done
HOST="https://$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"

SECRETS=(
  ANTHROPIC_API_KEY AZURE_IMAGE_API_KEY OPENAI_API_KEY BRIGHT_DATA_API_KEY PEEC_API_KEY BING_API_KEY
  GOOGLE_SERVICE_ACCOUNT_JSON SECRET_KEY AGENT_API_KEY OPTIMIZER_GITHUB_TOKEN
  DASHBOARD_PASSWORD DASHBOARD_SESSION_SECRET
  SLACK_WEBHOOK_URL DISCORD_WEBHOOK_URL DISCORD_SCHEMA_WEBHOOK_URL
  WP_APP_PASSWORD_AXXIOM WP_APP_PASSWORD_AMERITEX WP_APP_PASSWORD_ARIZONA_ES
  WP_APP_PASSWORD_LIFTECH WP_APP_PASSWORD_QUALITY WP_APP_PASSWORD_CAROLINA
)
# The vault already holds the marketing hub's wp-app-password-* secrets, but
# there is no way to confirm they are the same WordPress accounts AEO publishes
# with today. AEO gets its own aeo-* copies so behaviour on Azure is identical
# to Railway, and a rotation on one system cannot silently change the other.
# AEO-specific Discord channels must not collide with the hub's discord-webhook-url.
typeset -A VAULT_NAME_OVERRIDE
# ANTHROPIC_API_KEY is the Azure Foundry key (ANTHROPIC_BASE_URL points at Axxiom-AI), which may
# differ from the hub's anthropic-api-key — keep AEO's own copy rather than guess.
# DASHBOARD_PASSWORD reuses the marketing hub's dashboard password (same team,
# one password); the session secret is AEO's own.
VAULT_NAME_OVERRIDE=(ANTHROPIC_API_KEY aeo-anthropic-api-key
                     DASHBOARD_PASSWORD dashboard-password
                     DASHBOARD_SESSION_SECRET aeo-dashboard-session-secret
                     WP_APP_PASSWORD_AXXIOM aeo-wp-app-password-axxiom
                     WP_APP_PASSWORD_AMERITEX aeo-wp-app-password-ameritex
                     WP_APP_PASSWORD_ARIZONA_ES aeo-wp-app-password-arizona-es
                     WP_APP_PASSWORD_LIFTECH aeo-wp-app-password-liftech
                     WP_APP_PASSWORD_QUALITY aeo-wp-app-password-quality
                     WP_APP_PASSWORD_CAROLINA aeo-wp-app-password-carolina
                     DISCORD_WEBHOOK_URL aeo-discord-webhook-url DISCORD_SCHEMA_WEBHOOK_URL aeo-discord-schema-webhook-url
                     SECRET_KEY aeo-secret-key AGENT_API_KEY aeo-agent-api-key SLACK_WEBHOOK_URL aeo-slack-webhook-url
                     OPTIMIZER_GITHUB_TOKEN aeo-optimizer-github-token)
CONFIG=(
  ANTHROPIC_BASE_URL CLAUDE_MODEL
  IMAGE_PROVIDER AZURE_IMAGE_ENDPOINT AZURE_IMAGE_DEPLOYMENT AZURE_IMAGE_SIZE AZURE_IMAGE_QUALITY COST_PER_IMAGE_USD
  CITATION_PROVIDER BRIGHT_DATA_PROVIDERS
  WP_USERNAME_AXXIOM WP_USERNAME_AMERITEX WP_USERNAME_ARIZONA_ES WP_USERNAME_LIFTECH WP_USERNAME_QUALITY WP_USERNAME_CAROLINA
  WP_AUTHOR_ID_AXXIOM WP_AUTHOR_ID_AMERITEX WP_AUTHOR_ID_ARIZONA_ES WP_AUTHOR_ID_LIFTECH WP_AUTHOR_ID_QUALITY WP_AUTHOR_ID_CAROLINA
  CONTENT_GENERATION_MAX_PER_BRAND TOPIC_DISCOVERY_MAX_PER_BRAND AUTO_PUBLISH_ENABLED SCHEMA_AUTO_PUBLISH_ENABLED
  OPTIMIZER_ENABLED OPTIMIZER_BASE_BRANCH
)

envval() {
  awk -F= -v key="$1" '$0 ~ "^"key"=" {print substr($0, index($0,"=")+1); exit}' "$ENV_FILE" |
    sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

settings=(
  # platform
  "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
  "WEBSITES_PORT=8000"
  "ENVIRONMENT=production"
  "FRONTEND_URL=$HOST"
  "PUBLIC_API_URL=$HOST"
  "CORS_ORIGINS=$HOST"
  # database: Azure PG via managed identity (no password)
  "AZURE_PG_USER=umi-marketing-functions"
  "AZURE_PG_CLIENT_ID=d66356a2-e306-45a9-abc1-947002ff321c"
  "AZURE_PG_HOST=psql-axxiom-marketing.postgres.database.azure.com"
  "AZURE_PG_DATABASE=axxiom_hub"
  "DB_SCHEMA=aeo"
  # the app never runs DDL on Azure; migrations go through apply-migrations.sh
  "DB_MIGRATIONS_ON_STARTUP=false"
  # dashboard sign-in: password + session cookie, no Supabase Auth
  "AUTH_PROVIDER=password"
  # parallel run: API + dashboard up, NO jobs until Railway is stopped
  "SCHEDULER_ENABLED=$($LIVE && echo true || echo false)"
)
$NO_SECRETS && SECRETS=()
for var in "${SECRETS[@]}"; do
  name="${VAULT_NAME_OVERRIDE[$var]:-$(echo "$var" | tr 'A-Z_' 'a-z-')}"
  if ! az keyvault secret show --vault-name "$VAULT" --name "$name" --query name -o tsv >/dev/null 2>&1; then
    val="$(envval "$var")"
    if [[ -z "$val" ]]; then echo "skip   $var (not in vault, not in $ENV_FILE)"; continue; fi
    if $APPLY; then az keyvault secret set --vault-name "$VAULT" --name "$name" --value "$val" --query name -o tsv >/dev/null; fi
    echo "vault+ $name"
  fi
  settings+=("$var=@Microsoft.KeyVault(SecretUri=https://$VAULT.vault.azure.net/secrets/$name/)")
done
for var in "${CONFIG[@]}"; do
  val="$(envval "$var")"
  [[ -z "$val" ]] && continue
  settings+=("$var=$val")
done

echo "${#settings[@]} settings prepared for $APP ($(printf '%s\n' "${settings[@]}" | grep -c KeyVault) vault refs; SCHEDULER_ENABLED=$($LIVE && echo true || echo false)$($NO_SECRETS && echo "; --no-secrets"))"
if $APPLY; then
  az webapp config appsettings set -g "$RG" -n "$APP" --settings "${settings[@]}" --query "length(@)" -o tsv
  az webapp config set -g "$RG" -n "$APP" --startup-file "bash startup.sh" --always-on true --query "{startup:appCommandLine,alwaysOn:alwaysOn}" -o json
  az webapp config set -g "$RG" -n "$APP" --generic-configurations '{"healthCheckPath":"/health"}' --query healthCheckPath -o tsv
  echo "applied."
else
  printf '%s\n' "${settings[@]}" | sed -E '/KeyVault/!s/=(.+)/=<value>/'
  echo "dry run — add --apply to write."
fi
