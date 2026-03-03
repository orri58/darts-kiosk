#!/bin/bash
#===============================================================================
# Darts Kiosk System - One-Command Installer for Ubuntu Server
# Version: 1.0.0
# 
# Usage:
#   sudo ./install.sh              # Full installation
#   sudo ./install.sh --check      # Dry-run / check mode
#   sudo ./install.sh --uninstall  # Remove services (keeps data)
#
# Requirements:
#   - Ubuntu Server 20.04 / 22.04 / 24.04 LTS
#   - Root privileges (sudo)
#   - At least 4GB RAM, 10GB disk space
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="darts-kiosk"
INSTALL_DIR="/opt/${APP_NAME}"
DATA_DIR="/data/darts"
CONFIG_DIR="${DATA_DIR}/config"
BACKUP_DIR="${DATA_DIR}/backups"
LOGS_DIR="${DATA_DIR}/logs"
ASSETS_DIR="${DATA_DIR}/assets"

# Systemd service files
STACK_SERVICE="darts-stack"
KIOSK_SERVICE="darts-kiosk"

# Default ports
HTTP_PORT=80
API_PORT=8001

# Parse arguments
DRY_RUN=false
UNINSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--check|--uninstall]"
            echo "  --check      Dry-run mode, shows what would be done"
            echo "  --uninstall  Remove services (keeps data)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

#===============================================================================
# Helper Functions
#===============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${CYAN}==>${NC} ${BLUE}$1${NC}"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_ubuntu() {
    if [[ ! -f /etc/os-release ]]; then
        log_warn "Cannot detect OS, proceeding anyway..."
        return
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        log_warn "This script is designed for Ubuntu, detected: $ID"
    else
        log_info "Detected Ubuntu $VERSION_ID"
    fi
}

generate_secret() {
    local length=${1:-64}
    openssl rand -base64 $length | tr -d '=/+' | head -c $length
}

get_local_ip() {
    # Get primary LAN IP (not localhost)
    ip route get 1 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}'
}

#===============================================================================
# Uninstall Function
#===============================================================================

do_uninstall() {
    log_step "Uninstalling Darts Kiosk services..."
    
    # Stop and disable services
    systemctl stop ${STACK_SERVICE}.service 2>/dev/null || true
    systemctl stop ${KIOSK_SERVICE}.service 2>/dev/null || true
    systemctl disable ${STACK_SERVICE}.service 2>/dev/null || true
    systemctl disable ${KIOSK_SERVICE}.service 2>/dev/null || true
    
    # Remove service files
    rm -f /etc/systemd/system/${STACK_SERVICE}.service
    rm -f /etc/systemd/system/${KIOSK_SERVICE}.service
    rm -f ${INSTALL_DIR}/kiosk-watchdog.sh
    
    systemctl daemon-reload
    
    log_info "Services removed"
    log_info "Data preserved in ${DATA_DIR}"
    log_info "Application files preserved in ${INSTALL_DIR}"
    log_info "To completely remove, run: rm -rf ${INSTALL_DIR} ${DATA_DIR}"
    
    exit 0
}

#===============================================================================
# Installation Steps
#===============================================================================

install_docker() {
    log_step "Installing Docker..."
    
    if command -v docker &> /dev/null; then
        log_info "Docker already installed: $(docker --version)"
        if $DRY_RUN; then return; fi
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Would install Docker"
            return
        fi
        
        # Install dependencies
        apt-get update
        apt-get install -y \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg \
            lsb-release
        
        # Add Docker's official GPG key
        mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        
        # Set up repository
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        
        # Start Docker
        systemctl enable docker
        systemctl start docker
        
        log_info "Docker installed successfully"
    fi
}

install_chromium() {
    log_step "Installing Chromium browser for kiosk..."
    
    if command -v chromium-browser &> /dev/null || command -v chromium &> /dev/null; then
        log_info "Chromium already installed"
        if $DRY_RUN; then return; fi
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Would install Chromium"
            return
        fi
        
        apt-get install -y chromium-browser xdotool unclutter || \
        apt-get install -y chromium xdotool unclutter
        
        log_info "Chromium installed"
    fi
}

create_directories() {
    log_step "Creating directory structure..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would create:"
        log_info "  ${INSTALL_DIR}"
        log_info "  ${DATA_DIR}"
        log_info "  ${CONFIG_DIR}"
        log_info "  ${BACKUP_DIR}"
        log_info "  ${LOGS_DIR}"
        log_info "  ${ASSETS_DIR}"
        return
    fi
    
    mkdir -p ${INSTALL_DIR}
    mkdir -p ${DATA_DIR}
    mkdir -p ${CONFIG_DIR}
    mkdir -p ${BACKUP_DIR}
    mkdir -p ${LOGS_DIR}
    mkdir -p ${ASSETS_DIR}
    mkdir -p ${DATA_DIR}/autodarts_debug
    mkdir -p ${DATA_DIR}/browser_data
    
    # Set permissions
    chmod 755 ${INSTALL_DIR}
    chmod 755 ${DATA_DIR}
    chmod 700 ${CONFIG_DIR}
    
    log_info "Directories created"
}

generate_secrets_file() {
    log_step "Generating secure secrets..."
    
    local secrets_file="${CONFIG_DIR}/.secrets"
    
    if [[ -f "$secrets_file" ]]; then
        log_info "Secrets file already exists, keeping existing secrets"
        if $DRY_RUN; then return; fi
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Would generate secrets in ${secrets_file}"
            return
        fi
        
        local jwt_secret=$(generate_secret 64)
        local agent_secret=$(generate_secret 32)
        
        cat > "$secrets_file" << EOF
# Darts Kiosk Secrets - Generated $(date -Iseconds)
# DO NOT SHARE OR COMMIT THIS FILE
JWT_SECRET=${jwt_secret}
AGENT_SECRET=${agent_secret}
EOF
        
        chmod 600 "$secrets_file"
        log_info "Secrets generated and saved"
    fi
}

create_env_file() {
    log_step "Creating environment configuration..."
    
    local env_file="${CONFIG_DIR}/.env"
    
    if [[ -f "$env_file" ]]; then
        log_info "Environment file already exists"
        if $DRY_RUN; then return; fi
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Would create ${env_file}"
            return
        fi
        
        local local_ip=$(get_local_ip)
        
        cat > "$env_file" << EOF
# Darts Kiosk Configuration
# Generated $(date -Iseconds)

# Mode: STANDALONE (single board), MASTER (central), AGENT (board PC)
MODE=STANDALONE

# Board identification
BOARD_ID=BOARD-1

# Network
LOCAL_IP=${local_ip}
HTTP_PORT=${HTTP_PORT}
API_PORT=${API_PORT}

# Master URL (for AGENT mode)
MASTER_URL=http://${local_ip}:${API_PORT}

# Autodarts
AUTODARTS_URL=https://play.autodarts.io
AUTODARTS_MOCK=false

# Data paths
DATA_DIR=/data
BACKUP_INTERVAL_HOURS=6
MAX_BACKUPS=30

# Security
CORS_ORIGINS=http://${local_ip},http://localhost
ALLOWED_HOSTS=${local_ip},localhost

# Setup status
SETUP_COMPLETE=false
EOF
        
        chmod 600 "$env_file"
        log_info "Environment configuration created"
    fi
}

create_docker_compose() {
    log_step "Creating Docker Compose configuration..."
    
    local compose_file="${INSTALL_DIR}/docker-compose.yml"
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would create ${compose_file}"
        return
    fi
    
    cat > "$compose_file" << 'COMPOSE_EOF'
version: '3.8'

services:
  app:
    image: darts-kiosk:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: darts-kiosk-app
    restart: unless-stopped
    env_file:
      - /data/darts/config/.env
      - /data/darts/config/.secrets
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/db.sqlite
      - SYNC_DATABASE_URL=sqlite:///data/db.sqlite
      - DATA_DIR=/data
    volumes:
      - /data/darts:/data
      - /data/darts/config:/app/backend/config:ro
    ports:
      - "${API_PORT:-8001}:8001"
      - "${HTTP_PORT:-3000}:3000"
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
        max-file: "3"

  nginx:
    image: nginx:alpine
    container_name: darts-kiosk-nginx
    restart: unless-stopped
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

volumes:
  darts_data:
    driver: local

networks:
  darts-network:
    driver: bridge
COMPOSE_EOF
    
    log_info "Docker Compose configuration created"
}

create_kiosk_watchdog() {
    log_step "Creating kiosk watchdog script..."
    
    local watchdog_script="${INSTALL_DIR}/kiosk-watchdog.sh"
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would create ${watchdog_script}"
        return
    fi
    
    cat > "$watchdog_script" << 'WATCHDOG_EOF'
#!/bin/bash
#===============================================================================
# Darts Kiosk Watchdog - Keeps Chromium running in kiosk mode
#===============================================================================

# Configuration
CONFIG_FILE="/data/darts/config/.env"
KIOSK_USER="${KIOSK_USER:-$(logname 2>/dev/null || echo $USER)}"
DISPLAY="${DISPLAY:-:0}"

# Load configuration
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

LOCAL_IP="${LOCAL_IP:-localhost}"
KIOSK_URL="http://${LOCAL_IP}/kiosk/${BOARD_ID:-BOARD-1}"

# Logging
log() {
    echo "[$(date -Iseconds)] $1" >> /var/log/darts-kiosk.log
}

# Find Chromium binary
find_chromium() {
    for bin in chromium-browser chromium google-chrome; do
        if command -v $bin &> /dev/null; then
            echo $bin
            return
        fi
    done
    echo "chromium-browser"
}

CHROMIUM_BIN=$(find_chromium)

# Disable screen blanking
disable_screensaver() {
    export DISPLAY=$DISPLAY
    xset s off 2>/dev/null || true
    xset -dpms 2>/dev/null || true
    xset s noblank 2>/dev/null || true
}

# Hide mouse cursor
hide_cursor() {
    unclutter -idle 0.1 -root &
}

# Launch Chromium in kiosk mode
launch_kiosk() {
    log "Starting Chromium kiosk at $KIOSK_URL"
    
    export DISPLAY=$DISPLAY
    
    # Kill any existing instances
    pkill -f "chromium.*kiosk" 2>/dev/null || true
    sleep 2
    
    # Clear crash flags
    rm -rf /home/${KIOSK_USER}/.config/chromium/Singleton* 2>/dev/null || true
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
        /home/${KIOSK_USER}/.config/chromium/Default/Preferences 2>/dev/null || true
    
    # Launch Chromium
    $CHROMIUM_BIN \
        --kiosk \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-restore-session-state \
        --noerrdialogs \
        --disable-translate \
        --no-first-run \
        --fast \
        --fast-start \
        --disable-features=TranslateUI \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        --check-for-update-interval=31536000 \
        --disable-background-networking \
        --disable-sync \
        --disable-default-apps \
        --disable-extensions \
        --user-data-dir=/data/darts/browser_data \
        "$KIOSK_URL" &
    
    CHROMIUM_PID=$!
    log "Chromium started with PID $CHROMIUM_PID"
}

# Main watchdog loop
main() {
    log "Kiosk watchdog starting..."
    
    # Wait for X server
    while ! xdpyinfo -display $DISPLAY &>/dev/null; do
        log "Waiting for X server on $DISPLAY..."
        sleep 5
    done
    
    disable_screensaver
    hide_cursor
    
    # Initial launch
    launch_kiosk
    
    # Monitor and restart if needed
    while true; do
        sleep 10
        
        if ! pgrep -f "chromium.*kiosk" > /dev/null; then
            log "Chromium crashed or stopped, restarting..."
            launch_kiosk
        fi
    done
}

# Run
main
WATCHDOG_EOF
    
    chmod +x "$watchdog_script"
    log_info "Kiosk watchdog script created"
}

create_systemd_services() {
    log_step "Creating systemd services..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would create systemd services"
        return
    fi
    
    # Docker Stack Service
    cat > /etc/systemd/system/${STACK_SERVICE}.service << EOF
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
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF
    
    # Kiosk Watchdog Service
    cat > /etc/systemd/system/${KIOSK_SERVICE}.service << EOF
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
    
    # Reload systemd
    systemctl daemon-reload
    
    log_info "Systemd services created"
}

configure_firewall() {
    log_step "Configuring firewall..."
    
    if ! command -v ufw &> /dev/null; then
        log_warn "UFW not installed, skipping firewall configuration"
        return
    fi
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would configure UFW firewall"
        return
    fi
    
    # Enable UFW if not active
    ufw --force enable
    
    # Allow SSH
    ufw allow ssh
    
    # Allow HTTP/HTTPS from LAN only
    ufw allow from 192.168.0.0/16 to any port 80 proto tcp
    ufw allow from 192.168.0.0/16 to any port 443 proto tcp
    ufw allow from 10.0.0.0/8 to any port 80 proto tcp
    ufw allow from 10.0.0.0/8 to any port 443 proto tcp
    ufw allow from 172.16.0.0/12 to any port 80 proto tcp
    ufw allow from 172.16.0.0/12 to any port 443 proto tcp
    
    # Allow API port from LAN
    ufw allow from 192.168.0.0/16 to any port ${API_PORT} proto tcp
    ufw allow from 10.0.0.0/8 to any port ${API_PORT} proto tcp
    ufw allow from 172.16.0.0/12 to any port ${API_PORT} proto tcp
    
    # Allow localhost
    ufw allow from 127.0.0.1
    
    log_info "Firewall configured for LAN-only access"
}

enable_services() {
    log_step "Enabling services..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would enable and start services"
        return
    fi
    
    systemctl enable ${STACK_SERVICE}.service
    systemctl enable ${KIOSK_SERVICE}.service
    
    log_info "Services enabled for autostart"
}

copy_application_files() {
    log_step "Copying application files..."
    
    if $DRY_RUN; then
        log_info "[DRY-RUN] Would copy application files to ${INSTALL_DIR}"
        return
    fi
    
    # Copy from current directory if available
    local source_dir="$(dirname "$(readlink -f "$0")")"
    
    if [[ -f "${source_dir}/docker-compose.yml" ]]; then
        cp -r "${source_dir}"/* "${INSTALL_DIR}/" 2>/dev/null || true
        log_info "Application files copied"
    else
        log_warn "No application files found in ${source_dir}"
        log_info "Please copy the application files to ${INSTALL_DIR}"
    fi
}

print_qr_code() {
    local url=$1
    
    # Simple ASCII QR-like box (actual QR would need qrencode)
    if command -v qrencode &> /dev/null; then
        qrencode -t ANSIUTF8 "$url"
    else
        echo ""
        echo "┌─────────────────────────────────┐"
        echo "│                                 │"
        echo "│   $url"
        echo "│                                 │"
        echo "└─────────────────────────────────┘"
    fi
}

print_completion() {
    local local_ip=$(get_local_ip)
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}          DARTS KIOSK INSTALLATION COMPLETE!                   ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}Access URLs:${NC}"
    echo -e "  Setup Wizard: ${YELLOW}http://${local_ip}/setup${NC}"
    echo -e "  Admin Panel:  ${YELLOW}http://${local_ip}/admin${NC}"
    echo -e "  Kiosk:        ${YELLOW}http://${local_ip}/kiosk${NC}"
    echo ""
    
    print_qr_code "http://${local_ip}/setup"
    
    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Open the Setup Wizard URL in a browser"
    echo "  2. Configure MODE (Standalone/Master/Agent)"
    echo "  3. Set admin password and staff PIN"
    echo "  4. Configure branding and pricing"
    echo "  5. Click 'Apply & Restart'"
    echo ""
    echo -e "${CYAN}Service Commands:${NC}"
    echo "  Start stack:    sudo systemctl start ${STACK_SERVICE}"
    echo "  Stop stack:     sudo systemctl stop ${STACK_SERVICE}"
    echo "  Restart stack:  sudo systemctl restart ${STACK_SERVICE}"
    echo "  View logs:      sudo docker compose -f ${INSTALL_DIR}/docker-compose.yml logs -f"
    echo ""
    echo -e "${CYAN}Start kiosk (after setup):${NC}"
    echo "  sudo systemctl start ${KIOSK_SERVICE}"
    echo ""
    echo -e "${GREEN}Installation directory: ${INSTALL_DIR}${NC}"
    echo -e "${GREEN}Data directory: ${DATA_DIR}${NC}"
    echo ""
}

#===============================================================================
# Main Installation
#===============================================================================

main() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}          DARTS KIOSK SYSTEM INSTALLER v1.0.0                  ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    if $DRY_RUN; then
        echo -e "${YELLOW}Running in DRY-RUN mode - no changes will be made${NC}"
        echo ""
    fi
    
    check_root
    check_ubuntu
    
    if $UNINSTALL; then
        do_uninstall
    fi
    
    # Installation steps
    install_docker
    install_chromium
    create_directories
    generate_secrets_file
    create_env_file
    copy_application_files
    create_docker_compose
    create_kiosk_watchdog
    create_systemd_services
    configure_firewall
    enable_services
    
    if ! $DRY_RUN; then
        # Start the stack
        log_step "Starting Docker stack..."
        cd ${INSTALL_DIR}
        docker compose up -d --build 2>/dev/null || \
        docker-compose up -d --build 2>/dev/null || \
        log_warn "Could not start stack automatically. Run manually: docker compose up -d"
    fi
    
    print_completion
}

# Run main
main "$@"
