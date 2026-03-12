#!/bin/bash
#===============================================================================
# Darts Kiosk - Release Builder
# Creates 3 release packages from the current codebase
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

# Read version from VERSION file (single source of truth)
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

# Clean previous builds
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

#===============================================================================
# 1. Build Frontend (shared by all packages)
#===============================================================================
step "Frontend bauen..."
cd "${APP_DIR}/frontend"

# Set empty backend URL for production — frontend uses relative /api/ paths
# when served by the same backend (FastAPI static files mount)
export REACT_APP_BACKEND_URL=
yarn build 2>&1 | tail -5
FRONTEND_BUILD="${APP_DIR}/frontend/build"
log "Frontend gebaut: $(du -sh "$FRONTEND_BUILD" | cut -f1)"

#===============================================================================
# 2. Create stripped requirements (remove dev/emergent-only packages)
#===============================================================================
step "Backend requirements filtern..."
cd "${APP_DIR}/backend"

# Core packages needed for the app
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
EOF

# Playwright is listed separately (optional for Autodarts)
log "requirements-core.txt erstellt"

#===============================================================================
# 3. Windows Test Bundle
#===============================================================================
step "Windows Test Bundle erstellen..."
WIN_DIR="${BUILD_DIR}/darts-kiosk-v${VERSION}-windows"
mkdir -p "${WIN_DIR}/backend" "${WIN_DIR}/frontend" "${WIN_DIR}/data/db" "${WIN_DIR}/data/assets" "${WIN_DIR}/data/backups" "${WIN_DIR}/logs"

# Copy backend (without __pycache__, .pyc, tests)
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='tests/' --exclude='.env' --exclude='*.sqlite*' \
    "${APP_DIR}/backend/" "${WIN_DIR}/backend/"

# Copy pre-built frontend
cp -r "$FRONTEND_BUILD" "${WIN_DIR}/frontend/build"
# Also copy source for dev mode
rsync -a --exclude='node_modules' --exclude='build' --exclude='.env' \
    "${APP_DIR}/frontend/" "${WIN_DIR}/frontend/"

# Use core requirements
cp "${BUILD_DIR}/requirements-core.txt" "${WIN_DIR}/backend/requirements.txt"

# Add playwright to requirements
echo "playwright==1.58.0" >> "${WIN_DIR}/backend/requirements.txt"

# Copy Windows scripts
cp "${SCRIPT_DIR}/windows/"*.bat "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/run_backend.py" "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/credits_overlay.py" "${WIN_DIR}/"
cp "${SCRIPT_DIR}/windows/setup_profile.bat" "${WIN_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/windows/README.md" "${WIN_DIR}/"

# Copy kiosk deployment files
mkdir -p "${WIN_DIR}/kiosk"
if [[ -d "${APP_DIR}/kiosk" ]]; then
    cp "${APP_DIR}/kiosk/"*.bat "${WIN_DIR}/kiosk/" 2>/dev/null || true
    cp "${APP_DIR}/kiosk/"*.vbs "${WIN_DIR}/kiosk/" 2>/dev/null || true
    cp "${APP_DIR}/kiosk/README_KIOSK.md" "${WIN_DIR}/kiosk/" 2>/dev/null || true
    log "Kiosk-Deployment-Dateien kopiert"
fi

# Copy VERSION file (single source of truth)
cp "${APP_DIR}/VERSION" "${WIN_DIR}/"

# Copy updater
cp "${APP_DIR}/updater.py" "${WIN_DIR}/"

# Create Windows .env.example files (template only — never overwrite user config)
cat > "${WIN_DIR}/backend/.env.example" << 'EOF'
DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
DATA_DIR=./data
JWT_SECRET=darts-local-dev-secret-change-in-production
AGENT_SECRET=agent-local-dev-secret
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
EOF

# Frontend .env.example
cat > "${WIN_DIR}/frontend/.env.example" << 'EOF'
REACT_APP_BACKEND_URL=http://localhost:8001
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

# Copy backend
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='tests/' --exclude='.env' --exclude='*.sqlite*' \
    "${APP_DIR}/backend/" "${LINUX_DIR}/backend/"
cp "${BUILD_DIR}/requirements-core.txt" "${LINUX_DIR}/backend/requirements.txt"
echo "playwright==1.58.0" >> "${LINUX_DIR}/backend/requirements.txt"

# Copy pre-built frontend (production ready, no node_modules needed)
cp -r "$FRONTEND_BUILD"/* "${LINUX_DIR}/frontend/build/"

# Copy nginx config
if [[ -d "${APP_DIR}/nginx" ]]; then
    cp -r "${APP_DIR}/nginx/"* "${LINUX_DIR}/nginx/" 2>/dev/null || true
fi

# Copy install.sh
cp "${APP_DIR}/install.sh" "${LINUX_DIR}/"
chmod +x "${LINUX_DIR}/install.sh"

# Copy VERSION file and updater
cp "${APP_DIR}/VERSION" "${LINUX_DIR}/"
cp "${APP_DIR}/updater.py" "${LINUX_DIR}/"

# Copy docker files
cp "${APP_DIR}/docker-compose.yml" "${LINUX_DIR}/" 2>/dev/null || true
cp "${APP_DIR}/Dockerfile" "${LINUX_DIR}/" 2>/dev/null || true

# Create offline-ready serve script (no node needed)
cat > "${LINUX_DIR}/serve-frontend.py" << 'PYEOF'
#!/usr/bin/env python3
"""Simple static file server for the pre-built frontend."""
import http.server
import os
import sys

PORT = int(os.environ.get("FRONTEND_PORT", "3000"))
BUILD_DIR = os.path.join(os.path.dirname(__file__), "frontend", "build")

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BUILD_DIR, **kwargs)

    def do_GET(self):
        # SPA: serve index.html for all non-file routes
        path = os.path.join(BUILD_DIR, self.path.lstrip("/"))
        if not os.path.isfile(path) and not self.path.startswith("/api"):
            self.path = "/index.html"
        return super().do_GET()

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), SPAHandler)
    print(f"Frontend serving {BUILD_DIR} on port {PORT}")
    server.serve_forever()
PYEOF
chmod +x "${LINUX_DIR}/serve-frontend.py"

# Package
cd "$BUILD_DIR"
tar czf "darts-kiosk-v${VERSION}-linux.tar.gz" "$(basename "$LINUX_DIR")"
log "darts-kiosk-v${VERSION}-linux.tar.gz ($(du -sh "darts-kiosk-v${VERSION}-linux.tar.gz" | cut -f1))"

#===============================================================================
# 5. Source Export
#===============================================================================
step "Source Export erstellen..."
SRC_DIR="${BUILD_DIR}/darts-kiosk-v${VERSION}-source"
mkdir -p "$SRC_DIR"

# Copy everything (excluding runtime artifacts)
rsync -a \
    --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.env' --exclude='*.sqlite*' --exclude='build' \
    --exclude='data/' --exclude='logs/' --exclude='.git' \
    --exclude='.emergent' --exclude='release/build' \
    --exclude='test_reports/' --exclude='test_result.md' \
    --exclude='memory/' \
    "${APP_DIR}/" "${SRC_DIR}/"

# Add .env.example files
cp "${SCRIPT_DIR}/source/backend.env.example" "${SRC_DIR}/backend/.env.example"
cp "${SCRIPT_DIR}/source/frontend.env.example" "${SRC_DIR}/frontend/.env.example"
cp "${SCRIPT_DIR}/source/.gitignore" "${SRC_DIR}/.gitignore"
cp "${SCRIPT_DIR}/source/RELEASE_NOTES.md" "${SRC_DIR}/"

# Add Windows scripts
mkdir -p "${SRC_DIR}/scripts/windows"
cp "${SCRIPT_DIR}/windows/"*.bat "${SRC_DIR}/scripts/windows/"
cp "${SCRIPT_DIR}/windows/run_backend.py" "${SRC_DIR}/scripts/windows/"
cp "${SCRIPT_DIR}/windows/credits_overlay.py" "${SRC_DIR}/scripts/windows/"
cp "${SCRIPT_DIR}/windows/README.md" "${SRC_DIR}/scripts/windows/"

# Package
cd "$BUILD_DIR"
zip -r "darts-kiosk-v${VERSION}-source.zip" "$(basename "$SRC_DIR")" -q
log "darts-kiosk-v${VERSION}-source.zip ($(du -sh "darts-kiosk-v${VERSION}-source.zip" | cut -f1))"

#===============================================================================
# Summary
#===============================================================================
echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}${BOLD}     RELEASE BUILD ABGESCHLOSSEN!${NC}"
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
