#!/bin/bash
#===============================================================================
# Darts Kiosk System - One-Command Installer for Ubuntu Server
# Version: 2.0.0
#
# Usage:
#   sudo ./install.sh              # Full installation (online)
#   sudo ./install.sh --offline    # Offline install (USB/local packages)
#   sudo ./install.sh --check      # Dry-run / check mode
#   sudo ./install.sh --uninstall  # Remove services (keeps data)
#
# Target OS: Ubuntu Server 24.04 LTS (primary), 22.04 LTS (secondary)
# Idempotent: Safe to run multiple times.
#===============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Paths
APP_NAME="darts-kiosk"
INSTALL_DIR="/opt/${APP_NAME}"
DATA_DIR="/data/darts"
CONFIG_DIR="${DATA_DIR}/config"
SECRETS_FILE="${CONFIG_DIR}/.secrets"
ENV_FILE="${CONFIG_DIR}/.env"
BACKUP_DIR="${DATA_DIR}/backups"
LOGS_DIR="${DATA_DIR}/logs"
ASSETS_DIR="${DATA_DIR}/assets"

# Services
STACK_SERVICE="darts-stack"
KIOSK_SERVICE="darts-kiosk"

# Defaults
HTTP_PORT=80
API_PORT=8001
MIN_RAM_MB=2048
MIN_DISK_GB=5

# Flags
DRY_RUN=false
UNINSTALL=false
OFFLINE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check|--dry-run) DRY_RUN=true; shift ;;
        --uninstall)       UNINSTALL=true; shift ;;
        --offline)         OFFLINE=true; shift ;;
        -h|--help)
            echo "Darts Kiosk Installer v2.0.0"
            echo ""
            echo "Usage: sudo $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --check      Dry-run mode (shows what would happen)"
            echo "  --offline    Use local packages (USB/LAN install)"
            echo "  --uninstall  Remove services (data is preserved)"
            echo "  -h, --help   Show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

#===============================================================================
# Helpers
#===============================================================================
log_info()  { echo -e "${GREEN}[OK]${NC}   $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; }
log_step()  { echo -e "\n${CYAN}==> ${BOLD}$1${NC}"; }
log_dry()   { echo -e "${BLUE}[DRY]${NC}  $1"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Dieses Script muss als root ausgefuehrt werden (sudo ./install.sh)"
        exit 1
    fi
}

generate_secret() {
    openssl rand -base64 "${1:-64}" | tr -d '=/+\n' | head -c "${1:-64}"
}

get_local_ip() {
    ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}' \
        || hostname -I 2>/dev/null | awk '{print $1}' \
        || echo "127.0.0.1"
}

#===============================================================================
# Pre-flight checks
#===============================================================================
preflight() {
    log_step "Systemvoraussetzungen pruefen"

    # OS check
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        if [[ "$ID" == "ubuntu" ]]; then
            case "$VERSION_ID" in
                24.04|22.04) log_info "Ubuntu $VERSION_ID LTS erkannt" ;;
                *)           log_warn "Ubuntu $VERSION_ID erkannt (unterstuetzt: 24.04/22.04)" ;;
            esac
        else
            log_warn "Erkanntes OS: $ID $VERSION_ID (nicht Ubuntu)"
        fi
    fi

    # RAM
    local ram_mb
    ram_mb=$(awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)
    if (( ram_mb < MIN_RAM_MB )); then
        log_warn "RAM: ${ram_mb} MB (empfohlen: >= ${MIN_RAM_MB} MB)"
    else
        log_info "RAM: ${ram_mb} MB"
    fi

    # Disk
    local disk_gb
    disk_gb=$(df -BG / | awk 'NR==2 {gsub("G",""); print $4}')
    if (( disk_gb < MIN_DISK_GB )); then
        log_error "Zu wenig Speicher: ${disk_gb} GB frei (benoetigt: ${MIN_DISK_GB} GB)"
        exit 1
    else
        log_info "Festplatte: ${disk_gb} GB frei"
    fi
}

#===============================================================================
# Uninstall
#===============================================================================
do_uninstall() {
    log_step "Darts Kiosk deinstallieren..."

    systemctl stop  ${STACK_SERVICE}.service  2>/dev/null || true
    systemctl stop  ${KIOSK_SERVICE}.service  2>/dev/null || true
    systemctl disable ${STACK_SERVICE}.service 2>/dev/null || true
    systemctl disable ${KIOSK_SERVICE}.service 2>/dev/null || true

    rm -f /etc/systemd/system/${STACK_SERVICE}.service
    rm -f /etc/systemd/system/${KIOSK_SERVICE}.service
    rm -f ${INSTALL_DIR}/kiosk-watchdog.sh
    systemctl daemon-reload

    log_info "Services entfernt"
    log_info "Daten bleiben erhalten unter ${DATA_DIR}"
    log_info "Zum vollstaendigen Entfernen: rm -rf ${INSTALL_DIR} ${DATA_DIR}"
    exit 0
}

#===============================================================================
# Installation Steps
#===============================================================================
install_docker() {
    log_step "Docker installieren"

    if command -v docker &>/dev/null; then
        log_info "Docker bereits installiert: $(docker --version)"
        # Ensure docker compose plugin exists
        if docker compose version &>/dev/null; then
            log_info "Docker Compose Plugin vorhanden"
        else
            $DRY_RUN && { log_dry "Wuerde Docker Compose Plugin installieren"; return; }
            apt-get install -y docker-compose-plugin
        fi
        return
    fi

    $DRY_RUN && { log_dry "Wuerde Docker installieren"; return; }

    if $OFFLINE; then
        # Offline: expect .deb packages in ./packages/
        local pkg_dir
        pkg_dir="$(dirname "$(readlink -f "$0")")/packages"
        if [[ -d "$pkg_dir" ]] && ls "$pkg_dir"/*.deb &>/dev/null; then
            log_info "Offline-Modus: Installiere .deb Pakete aus $pkg_dir"
            dpkg -i "$pkg_dir"/*.deb || apt-get install -f -y
        else
            log_error "Offline-Modus aber keine Pakete unter $pkg_dir/*.deb gefunden"
            log_error "Bitte Docker .deb Pakete in ./packages/ bereitstellen"
            exit 1
        fi
    else
        apt-get update -qq
        apt-get install -y -qq \
            apt-transport-https ca-certificates curl gnupg lsb-release

        mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
            > /etc/apt/sources.list.d/docker.list

        apt-get update -qq
        apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    fi

    systemctl enable --now docker
    log_info "Docker installiert"
}

install_chromium() {
    log_step "Chromium (Kiosk-Browser) installieren"

    if command -v chromium-browser &>/dev/null || command -v chromium &>/dev/null; then
        log_info "Chromium bereits installiert"
        return
    fi

    $DRY_RUN && { log_dry "Wuerde Chromium installieren"; return; }

    if $OFFLINE; then
        local pkg_dir
        pkg_dir="$(dirname "$(readlink -f "$0")")/packages"
        if [[ -d "$pkg_dir" ]]; then
            dpkg -i "$pkg_dir"/chromium*.deb 2>/dev/null || apt-get install -f -y 2>/dev/null || true
        fi
    else
        apt-get install -y -qq chromium-browser xdotool unclutter 2>/dev/null \
            || apt-get install -y -qq chromium xdotool unclutter 2>/dev/null \
            || log_warn "Chromium konnte nicht installiert werden (optional fuer Kiosk-Modus)"
    fi
}

create_directories() {
    log_step "Verzeichnisse erstellen"

    $DRY_RUN && {
        log_dry "${INSTALL_DIR}, ${DATA_DIR}, ${CONFIG_DIR}, ${BACKUP_DIR}, ${LOGS_DIR}, ${ASSETS_DIR}"
        return
    }

    mkdir -p "${INSTALL_DIR}"
    mkdir -p "${DATA_DIR}"
    mkdir -p "${CONFIG_DIR}"
    mkdir -p "${BACKUP_DIR}"
    mkdir -p "${LOGS_DIR}"
    mkdir -p "${ASSETS_DIR}"
    mkdir -p "${DATA_DIR}/autodarts_debug"
    mkdir -p "${DATA_DIR}/browser_data"

    chmod 755 "${INSTALL_DIR}"
    chmod 755 "${DATA_DIR}"
    chmod 700 "${CONFIG_DIR}"

    log_info "Verzeichnisse erstellt"
}

generate_secrets() {
    log_step "Secrets generieren"

    if [[ -f "$SECRETS_FILE" ]]; then
        log_info "Secrets-Datei existiert bereits (wird beibehalten)"
        return
    fi

    $DRY_RUN && { log_dry "Wuerde Secrets in ${SECRETS_FILE} generieren"; return; }

    local jwt_secret agent_secret
    jwt_secret=$(generate_secret 64)
    agent_secret=$(generate_secret 32)

    cat > "$SECRETS_FILE" <<EOF
JWT_SECRET=${jwt_secret}
AGENT_SECRET=${agent_secret}
EOF

    chmod 600 "$SECRETS_FILE"
    log_info "Secrets generiert (chmod 600)"
}

create_env() {
    log_step "Umgebungskonfiguration erstellen"

    if [[ -f "$ENV_FILE" ]]; then
        log_info "Konfiguration existiert bereits (wird beibehalten)"
        return
    fi

    $DRY_RUN && { log_dry "Wuerde ${ENV_FILE} erstellen"; return; }

    local local_ip
    local_ip=$(get_local_ip)

    cat > "$ENV_FILE" <<EOF
MODE=STANDALONE
BOARD_ID=BOARD-1
LOCAL_IP=${local_ip}
HTTP_PORT=${HTTP_PORT}
API_PORT=${API_PORT}
MASTER_URL=http://${local_ip}:${API_PORT}
AUTODARTS_URL=https://play.autodarts.io
AUTODARTS_MOCK=false
DATA_DIR=/data
BACKUP_INTERVAL_HOURS=6
MAX_BACKUPS=30
CORS_ORIGINS=http://${local_ip},http://localhost
ALLOWED_HOSTS=${local_ip},localhost
APP_VERSION=1.0.0
EOF

    chmod 600 "$ENV_FILE"
    log_info "Konfiguration erstellt"
}

copy_app_files() {
    log_step "Anwendungsdateien kopieren"

    $DRY_RUN && { log_dry "Wuerde Dateien nach ${INSTALL_DIR} kopieren"; return; }

    local src
    src="$(dirname "$(readlink -f "$0")")"

    if [[ -f "${src}/docker-compose.yml" ]]; then
        # Selective copy – preserve existing config
        for item in backend frontend nginx docker-compose.yml Dockerfile .dockerignore; do
            if [[ -e "${src}/${item}" ]]; then
                cp -a "${src}/${item}" "${INSTALL_DIR}/" 2>/dev/null || true
            fi
        done
        log_info "Dateien kopiert"
    else
        log_warn "Keine Anwendungsdateien im Quellverzeichnis gefunden"
    fi
}

create_production_compose() {
    log_step "Docker Compose (Production) erstellen"

    local compose_file="${INSTALL_DIR}/docker-compose.yml"

    # Only create if no compose file exists or if we copied one from source
    if [[ -f "$compose_file" ]]; then
        log_info "docker-compose.yml existiert bereits"
        return
    fi

    $DRY_RUN && { log_dry "Wuerde ${compose_file} erstellen"; return; }

    cat > "$compose_file" << 'COMPOSE_EOF'
version: '3.8'

services:
  app:
    image: darts-kiosk:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: darts-kiosk-app
    restart: always
    env_file:
      - /data/darts/config/.env
      - /data/darts/config/.secrets
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/db.sqlite
      - SYNC_DATABASE_URL=sqlite:///data/db.sqlite
      - DATA_DIR=/data
    volumes:
      - /data/darts:/data
    ports:
      - "${API_PORT:-8001}:8001"
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - darts-network
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  nginx:
    image: nginx:alpine
    container_name: darts-kiosk-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      app:
        condition: service_healthy
    networks:
      - darts-network
    profiles:
      - production

networks:
  darts-network:
    driver: bridge
COMPOSE_EOF

    log_info "docker-compose.yml erstellt"
}

create_kiosk_watchdog() {
    log_step "Kiosk-Watchdog erstellen"

    local script="${INSTALL_DIR}/kiosk-watchdog.sh"

    if [[ -f "$script" ]]; then
        log_info "Watchdog existiert bereits"
        return
    fi

    $DRY_RUN && { log_dry "Wuerde ${script} erstellen"; return; }

    cat > "$script" << 'WATCHDOG_EOF'
#!/bin/bash
# Darts Kiosk Watchdog - haelt Chromium im Kiosk-Modus

CONFIG_FILE="/data/darts/config/.env"
DISPLAY="${DISPLAY:-:0}"

[[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"

LOCAL_IP="${LOCAL_IP:-localhost}"
KIOSK_URL="http://${LOCAL_IP}/kiosk/${BOARD_ID:-BOARD-1}"

log() { echo "[$(date -Iseconds)] $1" >> /var/log/darts-kiosk.log; }

find_chromium() {
    for bin in chromium-browser chromium google-chrome; do
        command -v "$bin" &>/dev/null && { echo "$bin"; return; }
    done
    echo "chromium-browser"
}

CHROMIUM_BIN=$(find_chromium)

launch_kiosk() {
    log "Starte Chromium kiosk: $KIOSK_URL"
    export DISPLAY=$DISPLAY

    pkill -f "chromium.*kiosk" 2>/dev/null || true
    sleep 2

    # Disable screensaver
    xset s off 2>/dev/null || true
    xset -dpms  2>/dev/null || true
    unclutter -idle 0.1 -root &

    # Clear crash flags
    local profile="/home/${SUDO_USER:-$USER}/.config/chromium"
    rm -rf "${profile}/Singleton"* 2>/dev/null || true
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
        "${profile}/Default/Preferences" 2>/dev/null || true

    $CHROMIUM_BIN \
        --kiosk --disable-infobars --disable-session-crashed-bubble \
        --disable-restore-session-state --noerrdialogs --disable-translate \
        --no-first-run --fast --fast-start --disable-features=TranslateUI \
        --disable-pinch --overscroll-history-navigation=0 \
        --check-for-update-interval=31536000 --disable-background-networking \
        --disable-sync --disable-default-apps --disable-extensions \
        --user-data-dir=/data/darts/browser_data \
        "$KIOSK_URL" &

    log "Chromium PID $!"
}

main() {
    log "Watchdog gestartet"

    # Warte auf X Server
    while ! xdpyinfo -display "$DISPLAY" &>/dev/null; do
        log "Warte auf X Server..."
        sleep 5
    done

    launch_kiosk

    while true; do
        sleep 10
        pgrep -f "chromium.*kiosk" >/dev/null || { log "Chromium neu starten..."; launch_kiosk; }
    done
}

main
WATCHDOG_EOF

    chmod +x "$script"
    log_info "Watchdog erstellt"
}

create_systemd_services() {
    log_step "Systemd-Services erstellen"

    $DRY_RUN && { log_dry "Wuerde systemd-Units erstellen"; return; }

    # --- Docker Stack Service ---
    cat > "/etc/systemd/system/${STACK_SERVICE}.service" <<EOF
[Unit]
Description=Darts Kiosk Docker Stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart
Restart=on-failure
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

    # --- Kiosk Watchdog ---
    cat > "/etc/systemd/system/${KIOSK_SERVICE}.service" <<EOF
[Unit]
Description=Darts Kiosk Browser Watchdog
After=graphical.target ${STACK_SERVICE}.service
Wants=${STACK_SERVICE}.service

[Service]
Type=simple
User=${SUDO_USER:-root}
Environment=DISPLAY=:0
ExecStart=${INSTALL_DIR}/kiosk-watchdog.sh
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

    systemctl daemon-reload
    log_info "Systemd-Services erstellt (restart=always)"
}

configure_firewall() {
    log_step "Firewall konfigurieren (LAN-only)"

    if ! command -v ufw &>/dev/null; then
        log_warn "UFW nicht installiert, Firewall wird uebersprungen"
        return
    fi

    $DRY_RUN && { log_dry "Wuerde UFW konfigurieren"; return; }

    ufw --force enable 2>/dev/null || true

    # SSH (immer erlauben)
    ufw allow ssh

    # LAN-Bereiche fuer HTTP/HTTPS und API
    for cidr in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
        ufw allow from "$cidr" to any port 80  proto tcp 2>/dev/null || true
        ufw allow from "$cidr" to any port 443 proto tcp 2>/dev/null || true
        ufw allow from "$cidr" to any port "${API_PORT}" proto tcp 2>/dev/null || true
    done

    # Localhost
    ufw allow from 127.0.0.1 2>/dev/null || true

    log_info "Firewall: LAN-only Zugriff konfiguriert"
}

enable_services() {
    log_step "Services aktivieren"

    $DRY_RUN && { log_dry "Wuerde Services aktivieren"; return; }

    systemctl enable "${STACK_SERVICE}.service"
    systemctl enable "${KIOSK_SERVICE}.service"
    log_info "Autostart aktiviert"
}

start_stack() {
    log_step "Docker Stack starten"

    $DRY_RUN && { log_dry "Wuerde Stack starten"; return; }

    cd "${INSTALL_DIR}"

    if docker compose up -d --build 2>/dev/null; then
        log_info "Stack gestartet"
    elif docker-compose up -d --build 2>/dev/null; then
        log_info "Stack gestartet (docker-compose v1)"
    else
        log_warn "Stack konnte nicht automatisch gestartet werden"
        log_warn "Bitte manuell starten: cd ${INSTALL_DIR} && docker compose up -d"
        return
    fi
}

verify_health() {
    log_step "Health-Check ausfuehren"

    $DRY_RUN && { log_dry "Wuerde /api/health pruefen"; return; }

    local max_attempts=20
    local attempt=0
    local url="http://localhost:${API_PORT}/api/health"

    echo -n "  Warte auf Backend"
    while (( attempt < max_attempts )); do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo ""
            local response
            response=$(curl -sf "$url")
            log_info "Backend antwortet: ${response}"
            return 0
        fi
        echo -n "."
        sleep 3
        (( attempt++ ))
    done

    echo ""
    log_warn "Backend antwortet nicht nach ${max_attempts} Versuchen"
    log_warn "Pruefe Logs: docker compose -f ${INSTALL_DIR}/docker-compose.yml logs"
    return 1
}

print_completion() {
    local local_ip
    local_ip=$(get_local_ip)

    echo ""
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${GREEN}${BOLD}     DARTS KIOSK INSTALLATION ABGESCHLOSSEN!${NC}"
    echo -e "${GREEN}================================================================${NC}"
    echo ""
    echo -e "  ${CYAN}Setup-Wizard:${NC}  ${BOLD}http://${local_ip}/setup${NC}"
    echo -e "  ${CYAN}Admin-Panel:${NC}   http://${local_ip}/admin"
    echo -e "  ${CYAN}Kiosk:${NC}         http://${local_ip}/kiosk"
    echo ""
    echo -e "  ${YELLOW}Naechster Schritt:${NC}"
    echo -e "  Oeffnen Sie ${BOLD}http://${local_ip}/setup${NC} im Browser"
    echo -e "  und konfigurieren Sie Admin-Passwort, Staff-PIN und Branding."
    echo ""
    echo -e "  ${CYAN}Service-Befehle:${NC}"
    echo "    sudo systemctl start   ${STACK_SERVICE}"
    echo "    sudo systemctl stop    ${STACK_SERVICE}"
    echo "    sudo systemctl restart ${STACK_SERVICE}"
    echo "    docker compose -f ${INSTALL_DIR}/docker-compose.yml logs -f"
    echo ""
    echo -e "  ${CYAN}Verzeichnisse:${NC}"
    echo "    Anwendung: ${INSTALL_DIR}"
    echo "    Daten:     ${DATA_DIR}"
    echo "    Secrets:   ${SECRETS_FILE} (chmod 600)"
    echo ""

    # QR code if qrencode is available
    if command -v qrencode &>/dev/null; then
        echo -e "  ${CYAN}QR-Code zum Setup:${NC}"
        qrencode -t ANSIUTF8 "http://${local_ip}/setup" 2>/dev/null || true
    fi

    echo ""
}

#===============================================================================
# Main
#===============================================================================
main() {
    echo ""
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}${BOLD}     DARTS KIOSK INSTALLER v2.0.0${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo ""

    $DRY_RUN && echo -e "${YELLOW}${BOLD}  DRY-RUN Modus – keine Aenderungen werden vorgenommen${NC}\n"
    $OFFLINE  && echo -e "${YELLOW}  Offline-Modus aktiv${NC}\n"

    check_root

    if $UNINSTALL; then
        do_uninstall
    fi

    preflight
    install_docker
    install_chromium
    create_directories
    generate_secrets
    create_env
    copy_app_files
    create_production_compose
    create_kiosk_watchdog
    create_systemd_services
    configure_firewall
    enable_services
    start_stack
    verify_health

    print_completion
}

main "$@"
