#!/bin/bash
#===============================================================================
# Darts Kiosk - Runtime-Only Windows Package Builder (Wave 1)
# Additive packaging path. Does NOT replace or modify build_release.sh behavior.
#===============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${SCRIPT_DIR}/build"
RUNTIME_TEMPLATE_DIR="${SCRIPT_DIR}/runtime_windows"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "${GREEN}[OK]${NC}   $1"; }
step() { echo -e "\n${CYAN}==> ${BOLD}$1${NC}"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

VERSION_FILE="${APP_DIR}/VERSION"
if [[ -f "$VERSION_FILE" ]]; then
    VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
else
    fail "VERSION file not found at ${VERSION_FILE}"
fi

REBUILD_FRONTEND=1
if [[ "${1:-}" == "--reuse-frontend" ]]; then
    REBUILD_FRONTEND=0
fi

RUNTIME_DIR="${BUILD_DIR}/darts-kiosk-v${VERSION}-windows-runtime"
FRONTEND_BUILD="${APP_DIR}/frontend/build"
AUDIT_SCRIPT="${APP_DIR}/scripts/audit_runtime_package.py"
ALLOWLIST="${SCRIPT_DIR}/runtime_package_allowlist.json"

step "Runtime-only Windows-Paket v${VERSION} vorbereiten"
rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/app/backend" \
         "$RUNTIME_DIR/app/frontend" \
         "$RUNTIME_DIR/app/agent" \
         "$RUNTIME_DIR/app/bin" \
         "$RUNTIME_DIR/config" \
         "$RUNTIME_DIR/data/db" \
         "$RUNTIME_DIR/data/logs" \
         "$RUNTIME_DIR/data/backups" \
         "$RUNTIME_DIR/data/app_backups" \
         "$RUNTIME_DIR/data/downloads" \
         "$RUNTIME_DIR/data/assets" \
         "$RUNTIME_DIR/data/chrome_profile" \
         "$RUNTIME_DIR/data/kiosk_ui_profile"
log "Runtime-Verzeichnisstruktur erstellt"

if [[ "$REBUILD_FRONTEND" -eq 1 ]]; then
    step "Frontend fuer Runtime-Paket neu bauen"
    cd "${APP_DIR}/frontend"
    [[ -f package-lock.json ]] || fail "package-lock.json fehlt in frontend/"
    npm ci --loglevel=error >/dev/null
    export REACT_APP_BACKEND_URL=
    npm run build >/dev/null
    log "Frontend neu gebaut"
else
    step "Vorhandenen Frontend-Build wiederverwenden"
    [[ -f "${FRONTEND_BUILD}/index.html" ]] || fail "frontend/build/index.html fehlt; ohne --reuse-frontend neu bauen"
    log "Vorhandener Frontend-Build wird verwendet"
fi

[[ -f "${FRONTEND_BUILD}/index.html" ]] || fail "Frontend-Build fehlt"

step "Runtime-Inhalte kopieren"
rsync -a --exclude='__pycache__' --exclude='.pytest_cache' --exclude='*.pyc' --exclude='tests/' \
    --exclude='.env' --exclude='*.sqlite*' \
    "${APP_DIR}/backend/" "${RUNTIME_DIR}/app/backend/"
cp "${APP_DIR}/release/build/requirements-core.txt" "${RUNTIME_DIR}/app/backend/requirements.txt" 2>/dev/null || cp "${APP_DIR}/backend/requirements.txt" "${RUNTIME_DIR}/app/backend/requirements.txt"
cp -r "${FRONTEND_BUILD}" "${RUNTIME_DIR}/app/frontend/build"

cp "${APP_DIR}/agent/darts_agent.py" "${RUNTIME_DIR}/app/agent/"
cp "${APP_DIR}/agent/start_agent.bat" "${RUNTIME_DIR}/app/agent/"
cp "${APP_DIR}/agent/start_agent_silent.vbs" "${RUNTIME_DIR}/app/agent/"
cp "${APP_DIR}/agent/setup_autostart.py" "${RUNTIME_DIR}/app/agent/"
cp "${APP_DIR}/agent/requirements.txt" "${RUNTIME_DIR}/app/agent/"
cp "${APP_DIR}/agent/AGENT_DEPLOYMENT.md" "${RUNTIME_DIR}/app/agent/"

cp "${SCRIPT_DIR}/windows/run_backend.py" "${RUNTIME_DIR}/app/bin/run_backend.py"
cp "${SCRIPT_DIR}/windows/credits_overlay.py" "${RUNTIME_DIR}/app/bin/credits_overlay.py"
cp "${APP_DIR}/scripts/local_smoke.py" "${RUNTIME_DIR}/app/bin/local_smoke.py"
cp "${APP_DIR}/updater.py" "${RUNTIME_DIR}/app/bin/updater.py"
cp "${RUNTIME_TEMPLATE_DIR}/runtime_maintenance.py" "${RUNTIME_DIR}/app/bin/runtime_maintenance.py"
cp "${APP_DIR}/VERSION" "${RUNTIME_DIR}/app/bin/VERSION"
cp "${RUNTIME_TEMPLATE_DIR}/"*.bat "${RUNTIME_DIR}/app/bin/"
cp "${RUNTIME_TEMPLATE_DIR}/README_RUNTIME.md" "${RUNTIME_DIR}/app/bin/README.md"
cp "${RUNTIME_TEMPLATE_DIR}/runtime_retention.env.example" "${RUNTIME_DIR}/config/runtime_retention.env.example"

cat > "${RUNTIME_DIR}/config/backend.env.example" << 'EOF'
DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
DATA_DIR=./data
JWT_SECRET=darts-local-dev-secret-change-in-production
AGENT_SECRET=agent-local-dev-secret
AGENT_PORT=8003
CORS_ORIGINS=*
MODE=STANDALONE
BOARD_ID=BOARD-1
AUTODARTS_URL=https://play.autodarts.io
AUTODARTS_MODE=observer
AUTODARTS_HEADLESS=false
AUTODARTS_MOCK=false
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL_HOURS=24
GITHUB_REPO=orri58/darts-kiosk
GITHUB_TOKEN=
CENTRAL_SERVER_URL=https://api.dartcontrol.io
EOF

cat > "${RUNTIME_DIR}/config/frontend.env.example" << 'EOF'
REACT_APP_BACKEND_URL=http://localhost:8001
EOF

cp "${APP_DIR}/VERSION" "${RUNTIME_DIR}/config/VERSION"
log "Runtime-Dateien kopiert"

step "Runtime-Paket archivieren"
cd "$BUILD_DIR"
ZIP_NAME="darts-kiosk-v${VERSION}-windows-runtime.zip"
rm -f "$ZIP_NAME"
zip -r "$ZIP_NAME" "$(basename "$RUNTIME_DIR")" -q
log "${ZIP_NAME} ($(du -sh "$ZIP_NAME" | cut -f1))"

step "Allowlist-Audit (advisory)"
python3 "$AUDIT_SCRIPT" "$RUNTIME_DIR" --manifest "$ALLOWLIST"

step "Fertig"
echo ""
echo -e "${GREEN}${BOLD}Runtime-only Paket erstellt:${NC} ${BUILD_DIR}/${ZIP_NAME}"
echo "Optional: ./release/build_runtime_package.sh --reuse-frontend"
