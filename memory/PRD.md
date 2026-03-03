# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Each dartboard has its own Mini-PC running the full stack. Owner controls ALL boards from one central admin panel on local network.

## User Personas
1. **Cafe Owner (Admin)**: Full system access - branding, pricing, boards, users, logs, revenue, health monitoring, system management
2. **Staff/Wirt**: Quick unlock/extend/lock sessions, view board status (PIN login in 2s)
3. **Customers**: Touch kiosk - select game, enter names, play

## Core Requirements
- **Kiosk States**: LOCKED -> UNLOCKED_SETUP -> IN_GAME -> FINISHED/ERROR -> LOCKED
- **Pricing Models**: per_game (credits), per_time (minutes), per_player
- **Authentication**: JWT + PIN quick-login for staff
- **Multi-Board**: Master/Agent architecture, local LAN only
- **Database**: SQLite (Postgres-ready via SQLAlchemy)
- **Theme**: Dark, industrial minimal, 8 color palettes

## Implementation History

### Phase 1 (2026-03-03) - Core MVP
- SQLAlchemy models: User, Board, Session, AuditLog, Settings
- JWT + PIN authentication with RBAC
- Board management APIs
- Kiosk UI: Locked, Setup, In-Game screens
- Admin Panel: Dashboard, Boards, Settings, Users, Logs, Revenue
- 8 color palettes, touch-optimized UI

### Phase 1.5 (2026-03-03) - Production Ready
- Playwright Autodarts Integration service layer
- Docker Compose with nginx reverse proxy
- Session Scheduler (expiry + idle timeout)
- SETUP_GUIDE.md documentation
- Error screen with staff notification

### Phase 3 (2026-03-03) - Enterprise Hardening
- First-Run Setup Wizard (/setup)
- Security: LAN-only CORS, rate limiting, TrustedHostMiddleware
- Observability: JSON logging with rotation, Admin Health page
- Backups: Auto SQLite backups (6h interval, 30 retention)
- Updates & Rollback: Version tracking, agent update endpoints
- Automation Robustness: Circuit breaker, selector fallback

### Phase 4 (2026-03-03) - One-Command Installer + System Management
- **install.sh v2.0.0**: Idempotent installer for Ubuntu 24.04/22.04 LTS
  - Offline/USB support (--offline flag)
  - Dry-run mode (--check flag)
  - Creates /opt/darts-kiosk and /data/darts with proper permissions
  - Generates secrets with chmod 600
  - Systemd services (darts-stack + darts-kiosk watchdog) with restart=always
  - UFW firewall: LAN-only access
  - Health verification after startup
  - Prints /setup URL with detected IP
- **System Management Page** (/admin/system):
  - Overview: Version, Uptime, Disk Usage, Mode
  - Backups tab: Create, list, download, restore, delete
  - Updates tab: Current version, available versions, update history
  - Logs tab: Live log viewer (color-coded), downloadable log bundle
  - Details tab: Full system info (hostname, OS, Python, disk breakdown)
- **Backend APIs**:
  - GET /api/system/info - version, uptime, disk, OS info
  - GET /api/system/logs - tail recent application logs
  - GET /api/system/logs/bundle - downloadable tar.gz of all logs

## Technical Stack
- **Backend**: FastAPI, SQLAlchemy, SQLite, bcrypt, PyJWT
- **Frontend**: React 19, Tailwind CSS, shadcn/ui, Recharts
- **Browser Automation**: Playwright
- **Deployment**: Docker Compose + nginx + systemd
- **Logging**: JSON format with rotation

## API Endpoints Summary
```
Auth:     POST /api/auth/login, /api/auth/pin-login
Boards:   GET/POST/PUT/DELETE /api/boards, /api/boards/{id}/unlock|lock|extend
Kiosk:    POST /api/kiosk/{id}/start-game|end-game|call-staff
Settings: GET/PUT /api/settings/branding|pricing|palettes
Users:    GET/POST/PUT/DELETE /api/users
Logs:     GET /api/logs/audit|sessions
Revenue:  GET /api/revenue/summary
Health:   GET /api/health, /api/health/detailed, /api/health/screenshots
Backups:  GET /api/backups, POST create|restore, DELETE
Setup:    GET /api/setup/status, POST /api/setup/complete
Updates:  GET /api/updates/status, POST agent|all-agents|rollback
System:   GET /api/system/info|logs|logs/bundle
```

## Remaining Backlog

### P1 - Important
- [ ] Real Autodarts DOM selector testing (requires Autodarts access)
- [ ] WebSocket for real-time board status updates
- [ ] mDNS board auto-discovery

### P2 - Nice-to-Have
- [ ] Player statistics & leaderboard
- [ ] Stammkunde mode (QR/PIN login)
- [ ] Custom palette editor
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)

### Refactoring
- [ ] Break server.py (~1400 lines) into APIRouter modules
