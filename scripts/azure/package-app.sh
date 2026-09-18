#!/bin/zsh
# Package the AEO platform (FastAPI backend + built React dashboard) for Azure
# App Service and (optionally) deploy it.
#   ./scripts/azure/package-app.sh            # build + zip to .azure-stage/app.zip
#   ./scripts/azure/package-app.sh --deploy   # ...and `az webapp deploy` it
# Zip root = backend/ (app/, migrations/, requirements.txt, startup.sh) plus
# frontend_dist/ (Vite build with VITE_API_URL="" → same-origin API). Oryx
# runs `pip install -r requirements.txt` on the server
# (SCM_DO_BUILD_DURING_DEPLOYMENT=true); startup command = bash startup.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."

APP="${APP:-app-axxiom-aeo}"
RG="${RG:-Axxiom-devs-foundry}"
STAGE=".azure-stage"
FRONTEND_ENV="${FRONTEND_ENV:-frontend/.env}"

envval() {
  [[ -f "$FRONTEND_ENV" ]] || return 0
  awk -F= -v key="$1" '$0 ~ "^"key"=" {print substr($0, index($0,"=")+1); exit}' "$FRONTEND_ENV" |
    sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

echo "== building dashboard (same-origin API) =="
export VITE_API_URL=""
export VITE_SUPABASE_URL="${VITE_SUPABASE_URL:-$(envval VITE_SUPABASE_URL)}"
export VITE_SUPABASE_ANON_KEY="${VITE_SUPABASE_ANON_KEY:-$(envval VITE_SUPABASE_ANON_KEY)}"
[[ -n "$VITE_SUPABASE_URL" && -n "$VITE_SUPABASE_ANON_KEY" ]] || { echo "STOP: VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY missing (login would be disabled)"; exit 1; }
(cd frontend && [[ -d node_modules ]] || npm install --no-audit --no-fund --loglevel=error)
(cd frontend && npm run build >/dev/null)

echo "== staging =="
rm -rf "$STAGE" && mkdir -p "$STAGE"
rsync -a --exclude '__pycache__' --exclude '.env*' --exclude 'venv' --exclude 'tests' --exclude '.DS_Store' \
  backend/app backend/migrations backend/scripts backend/requirements.txt backend/startup.sh "$STAGE/"
cp -R frontend/dist "$STAGE/frontend_dist"
(cd "$STAGE" && rm -f app.zip && zip -qr app.zip . -x app.zip)
ls -lh "$STAGE/app.zip" | awk '{print "package:", $5, $9}'

if [[ "${1:-}" == "--deploy" ]]; then
  echo "== deploying to $APP (Oryx pip install runs server-side; ~3-5 min) =="
  az webapp deploy -g "$RG" -n "$APP" --src-path "$STAGE/app.zip" --type zip --async true \
    --query "{status: status, message: message}" -o json
  echo "poll: az webapp log deployment show -g $RG -n $APP   |  tail: az webapp log tail -g $RG -n $APP"
fi
