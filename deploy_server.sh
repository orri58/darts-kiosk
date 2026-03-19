#!/bin/bash
# ==============================================================================
# Darts Kiosk — Live-Server Deploy Script
# Verwendung: ./deploy_server.sh
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

log()  { echo -e "${GREEN}[OK]${NC}    $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail() { echo -e "${RED}[FAIL]${NC}  $1"; }
step() { echo -e "\n${CYAN}==> ${BOLD}$1${NC}"; }

VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
echo ""
echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}  Darts Kiosk — Deploy v${VERSION}${NC}"
echo -e "${CYAN}================================================================${NC}"

# === 1. Git Pull ===
step "1/6  Neueste Änderungen holen (git pull)..."
if git diff --quiet HEAD 2>/dev/null; then
    git pull --ff-only 2>&1 | head -5
    NEW_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
    log "Stand aktualisiert: v${NEW_VERSION}"
else
    warn "Lokale Änderungen vorhanden. git stash oder manuell committen."
    warn "Fahre trotzdem fort mit aktuellem Stand..."
fi

# === 2. Docker Build ===
step "2/6  Docker Images bauen..."
docker compose build --no-cache 2>&1 | tail -5
log "Docker Build abgeschlossen"

# === 3. Container neu starten ===
step "3/6  Container neu starten..."
docker compose down 2>&1 | tail -3
docker compose up -d 2>&1 | tail -3
log "Container gestartet"

# === 4. Central Server (systemd) ===
step "4/6  Zentraler Lizenzserver (darts-central)..."
if systemctl is-active --quiet darts-central 2>/dev/null; then
    sudo systemctl restart darts-central
    sleep 2
    if systemctl is-active --quiet darts-central; then
        log "darts-central neu gestartet"
    else
        fail "darts-central konnte nicht gestartet werden"
        warn "Prüfe: sudo journalctl -u darts-central -n 20"
    fi
elif systemctl list-unit-files | grep -q darts-central; then
    warn "darts-central existiert, ist aber nicht aktiv"
    warn "Starte: sudo systemctl start darts-central"
else
    warn "darts-central Service nicht gefunden — übersprungen"
    warn "Falls gewünscht: systemd Unit Datei erstellen (siehe DEPLOY.md)"
fi

# === 5. Healthchecks ===
step "5/6  Healthchecks..."
echo -n "  Warte auf Kiosk-Backend"
HEALTHY=0
for i in $(seq 1 20); do
    if curl -sf http://localhost:8001/api/health > /dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$HEALTHY" = "1" ]; then
    HEALTH=$(curl -s http://localhost:8001/api/health)
    log "Kiosk-Backend: OK"
    echo "       $(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Version: {d.get(\"version\",\"?\")}')" 2>/dev/null || echo "$HEALTH")"
else
    fail "Kiosk-Backend nicht erreichbar nach 40s"
    fail "Prüfe: docker compose logs app"
fi

# Central server health
if curl -sf http://localhost:8002/api/health > /dev/null 2>&1; then
    log "Central Server: OK"
else
    warn "Central Server (Port 8002) nicht erreichbar"
fi

# === 6. Status-Übersicht ===
step "6/6  Status"
echo ""
echo -e "  ${BOLD}Container:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps

echo ""
echo -e "  ${BOLD}Services:${NC}"
echo -e "  Kiosk-Backend:     http://localhost:8001"
echo -e "  Central Server:    http://localhost:8002"
echo -e "  Admin-Panel:       http://localhost:8001/admin"
echo -e "  Betreiber-Portal:  http://localhost:8001/operator"

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}  Deploy abgeschlossen!${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
