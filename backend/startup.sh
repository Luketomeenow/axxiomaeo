#!/bin/bash
# Azure App Service startup command (Linux, PYTHON|3.12). Oryx has already
# installed requirements.txt into the antenv virtualenv at deploy time
# (SCM_DO_BUILD_DURING_DEPLOYMENT=true) and activated it for this script.
#
# ONE worker on purpose: APScheduler runs in-process and would double-fire
# every job (content generation, publishing, audits) under multiple workers.
# The App Service plan is likewise pinned to one instance.
set -euo pipefail
cd "$(dirname "$0")"
export FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-$(pwd)/frontend_dist}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
