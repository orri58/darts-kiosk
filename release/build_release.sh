#!/bin/bash
#===============================================================================
# Darts Kiosk - Release Builder v3.5.3
# Creates Windows Production Bundle + Linux + Source packages
#===============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${SCRIPT_DIR}/build"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

VERSION_FILE="${APP_DIR}/VERSION"
if [[ -f "$VERSION_FILE" ]]; then
    VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
else
    echo "ERROR: VERSION file not found at ${VERSION_FILE}"
    exit 1
fi

echo -e "${CYAN}Building release v${VERSION}${NC}"

log() { echo -e "${GREEN}[OK]${NC}   $1"; }
step() { echo -e "\n${CYAN}==> ${BOLD}$1${NC}"; }

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

#===============================================================================
# 1. Build Frontend
#===============================================================================
step "Frontend bauen..."
cd "${APP_DIR}/frontend"

export REACT_APP_BACKEND_URL=
yarn build 2>&1 | tail -5
FRONTEND_BUILD="${APP_DIR}/frontend/build"
log "Frontend gebaut: $(du -sh "$FRONTEND_BUILD" | cut -f1)"

#===============================================================================
# 2. Core requirements
#===============================================================================
step "Backend requirements filtern..."
cd "${APP_DIR}/backend"

cat > "${BUILD_DIR}/requirements-core.txt" << 'EOF'
fastapi==0.110.1
uvicorn==0.25.0
sqlalchemy==2.0.48
aiosqlite==0.22.1
pydantic==2.12.5
python-jose==3.5.0
passlib==1.7.4
bcrypt==4.1.3
python-multipart==0.0.22
python-dotenv==1.2.1
websockets==16.0
httpx==0.28.1
pillow==12.1.1
slowapi>=0.1.9
apscheduler>=3.10
zeroconf==0.148.0
ifaddr==0.2.0
starlette==0.37.2
h11==0.16.0
anyio==4.12.1
sniffio==1.3.1
click==8.3.1
PyJWT==2.11.0
annotated-types==0.7.0
typing_extensions==4.15.0
pydantic_core==2.41.5
idna==3.11
certifi==2026.2.25
greenlet==3.3.2
MarkupSafe==3.0.3
Jinja2==3.1.6
playwright==1.58.0
EOF

log "requirements-core.txt erstellt"

#===============================================================================
# 3. Windows Production Bundle
#===============================================================================
step "Windows Production Bundle erstellen..."
WIN_DIR="${BUILD_DIR}/darts-kiosk-v${VERSION}-windows"
mkdir -p "${WIN_DIR}/backend" "${WIN_DIR}/frontend" \
         "${WIN_DIR}/data/db" "${WIN_DIR}/data/assets" "${WIN_DIR}/data/backups" \
         "${WIN_DIR}/data/chrome_profile" "${WIN_DIR}/data/kiosk_ui_profile" \
         "${WIN_DIR}/logs"

# Backend (without __pycache__, .pyc, tests, .env, sqlite)
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='tests/' \
    --exclude='.env' --exclude='*.sqlite*' \
    "${APP_DIR}/backend/" "${WIN_DIR}/backend/"

# Pre-built frontend
cp -r "$FRONTEND_BUILD" "${WIN_DIR}/frontend/build"
# Frontend source for dev mode
rsync -a --exclude='node_modules' --exclude='build' --exclude='.env' \
    "${APP_DIR}/frontend/" "${WIN_DIR}/frontend/"

# Requirements
cp "${BUILD_DIR}/requirements-core.txt" "${WIN_DIR}/backend/requirements.txt"

# Windows scripts
cp "${SCRIPT_DIR}/windows/"*.bat "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/run_backend.py" "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/credits_overlay.py" "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/setup_profile.bat" "${WIN_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/windows/README.md" "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/MANUAL_DEPLOYMENT.md" "${WIN_DIR}/" 2>/dev/null || true

# v3.4.0: Windows Agent
mkdir -p "${WIN_DIR}/agent"
cp "${APP_DIR}/agent/darts_agent.py" "${WIN_DIR}/agent/"
cp "${APP_DIR}/agent/start_agent.bat" "${WIN_DIR}/agent/"
cp "${APP_DIR}/agent/start_agent_silent.vbs" "${WIN_DIR}/agent/"
cp "${APP_DIR}/agent/setup_autostart.py" "${WIN_DIR}/agent/"
cp "${APP_DIR}/agent/requirements.txt" "${WIN_DIR}/agent/"
cp "${APP_DIR}/agent/AGENT_DEPLOYMENT.md" "${WIN_DIR}/agent/"
log "Windows Agent kopiert"

# v3.5.0: Central Server (optional, for self-hosting)
mkdir -p "${WIN_DIR}/central_server/data"
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.sqlite*' --exclude='data/' \
    "${APP_DIR}/central_server/" "${WIN_DIR}/central_server/"
# Central server requirements (same as backend + aiosqlite)
cat > "${WIN_DIR}/central_server/requirements.txt" << 'EOF'
fastapi==0.110.1
uvicorn==0.25.0
sqlalchemy==2.0.48
aiosqlite==0.22.1
PyJWT==2.11.0
starlette==0.37.2
httpx==0.28.1
pydantic==2.12.5
greenlet==3.3.2
EOF
log "Central Server kopiert"

# Kiosk experimental
mkdir -p "${WIN_DIR}/kiosk_experimental"
if [[ -d "${APP_DIR}/kiosk" ]]; then
    cp "${APP_DIR}/kiosk/"*.bat "${WIN_DIR}/kiosk_experimental/" 2>/dev/null || true
    cp "${APP_DIR}/kiosk/"*.vbs "${WIN_DIR}/kiosk_experimental/" 2>/dev/null || true
    cp "${APP_DIR}/kiosk/README_KIOSK.md" "${WIN_DIR}/kiosk_experimental/" 2>/dev/null || true
    cat > "${WIN_DIR}/kiosk_experimental/EXPERIMENTAL_WARNING.txt" << 'EXPEOF'
=== EXPERIMENTELL / DEPRECATED ===
Diese Dateien sind NICHT fuer Produktion empfohlen.
Siehe MANUAL_DEPLOYMENT.md im Hauptverzeichnis.
EXPEOF
    log "Kiosk-Experimental-Dateien kopiert"
fi

# VERSION + updater
cp "${APP_DIR}/VERSION" "${WIN_DIR}/"
cp "${APP_DIR}/updater.py" "${WIN_DIR}/"

# Backend .env.example (Production defaults for api.dartcontrol.io)
cat > "${WIN_DIR}/backend/.env.example" << 'EOF'
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
GITHUB_REPO=
GITHUB_TOKEN=
CENTRAL_SERVER_URL=https://api.dartcontrol.io
EOF

# Frontend .env.example
cat > "${WIN_DIR}/frontend/.env.example" << 'EOF'
REACT_APP_BACKEND_URL=http://localhost:8001
EOF

# Central server .env.example (for self-hosting)
cat > "${WIN_DIR}/central_server/.env.example" << 'EOF'
CENTRAL_DATA_DIR=./data
CENTRAL_JWT_SECRET=central-jwt-secret-change-in-production
CENTRAL_ADMIN_PASSWORD=admin
CENTRAL_ADMIN_TOKEN=admin-secret-token
EOF

# Package
cd "$BUILD_DIR"
zip -r "darts-kiosk-v${VERSION}-windows.zip" "$(basename "$WIN_DIR")" -q
log "darts-kiosk-v${VERSION}-windows.zip ($(du -sh "darts-kiosk-v${VERSION}-windows.zip" | cut -f1))"

#===============================================================================
# 4. Linux Production Bundle
#===============================================================================
step "Linux Production Bundle erstellen..."
LINUX_DIR="${BUILD_DIR}/darts-kiosk-v${VERSION}-linux"
mkdir -p "${LINUX_DIR}/backend" "${LINUX_DIR}/frontend/build" "${LINUX_DIR}/nginx"

rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='tests/' --exclude='.env' --exclude='*.sqlite*' \
    "${APP_DIR}/backend/" "${LINUX_DIR}/backend/"
cp "${BUILD_DIR}/requirements-core.txt" "${LINUX_DIR}/backend/requirements.txt"

cp -r "$FRONTEND_BUILD"/* "${LINUX_DIR}/frontend/build/"

if [[ -d "${APP_DIR}/nginx" ]]; then
    cp -r "${APP_DIR}/nginx/"* "${LINUX_DIR}/nginx/" 2>/dev/null || true
fi

cp "${APP_DIR}/install.sh" "${LINUX_DIR}/" 2>/dev/null || true
chmod +x "${LINUX_DIR}/install.sh" 2>/dev/null || true
cp "${APP_DIR}/VERSION" "${LINUX_DIR}/"
cp "${APP_DIR}/updater.py" "${LINUX_DIR}/"
cp "${APP_DIR}/docker-compose.yml" "${LINUX_DIR}/" 2>/dev/null || true
cp "${APP_DIR}/Dockerfile" "${LINUX_DIR}/" 2>/dev/null || true

# Agent (Linux)
mkdir -p "${LINUX_DIR}/agent"
cp "${APP_DIR}/agent/darts_agent.py" "${LINUX_DIR}/agent/"
cp "${APP_DIR}/agent/requirements.txt" "${LINUX_DIR}/agent/"
cp "${APP_DIR}/agent/AGENT_DEPLOYMENT.md" "${LINUX_DIR}/agent/"

# Central server (Linux)
mkdir -p "${LINUX_DIR}/central_server/data"
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.sqlite*' --exclude='data/' \
    "${APP_DIR}/central_server/" "${LINUX_DIR}/central_server/"

cd "$BUILD_DIR"
tar czf "darts-kiosk-v${VERSION}-linux.tar.gz" "$(basename "$LINUX_DIR")"
log "darts-kiosk-v${VERSION}-linux.tar.gz ($(du -sh "darts-kiosk-v${VERSION}-linux.tar.gz" | cut -f1))"

#===============================================================================
# 5. Source Export
#===============================================================================
step "Source Export erstellen..."
SRC_DIR="${BUILD_DIR}/darts-kiosk-v${VERSION}-source"
mkdir -p "$SRC_DIR"

rsync -a \
    --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.env' --exclude='*.sqlite*' --exclude='build' \
    --exclude='data/' --exclude='logs/' --exclude='.git' \
    --exclude='.emergent' --exclude='release/build' \
    --exclude='test_reports/' --exclude='test_result.md' \
    --exclude='memory/' \
    "${APP_DIR}/" "${SRC_DIR}/"

# .env examples
cp "${SCRIPT_DIR}/source/backend.env.example" "${SRC_DIR}/backend/.env.example" 2>/dev/null || true
cp "${SCRIPT_DIR}/source/frontend.env.example" "${SRC_DIR}/frontend/.env.example" 2>/dev/null || true
cp "${SCRIPT_DIR}/source/.gitignore" "${SRC_DIR}/.gitignore" 2>/dev/null || true
cp "${SCRIPT_DIR}/source/RELEASE_NOTES.md" "${SRC_DIR}/" 2>/dev/null || true

cd "$BUILD_DIR"
zip -r "darts-kiosk-v${VERSION}-source.zip" "$(basename "$SRC_DIR")" -q
log "darts-kiosk-v${VERSION}-source.zip ($(du -sh "darts-kiosk-v${VERSION}-source.zip" | cut -f1))"

#===============================================================================
# Summary
#===============================================================================
echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}${BOLD}     RELEASE BUILD v${VERSION} ABGESCHLOSSEN!${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "  Pakete in: ${BUILD_DIR}/"
echo ""
ls -lh "$BUILD_DIR"/*.{zip,tar.gz} 2>/dev/null | awk '{printf "  %-50s %s\n", $NF, $5}'
echo ""
echo -e "  ${CYAN}Windows:${NC}  darts-kiosk-v${VERSION}-windows.zip"
echo -e "  ${CYAN}Linux:${NC}    darts-kiosk-v${VERSION}-linux.tar.gz"
echo -e "  ${CYAN}Source:${NC}   darts-kiosk-v${VERSION}-source.zip"
echo ""
