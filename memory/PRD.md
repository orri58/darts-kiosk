# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Each dartboard has its own Mini-PC running the full stack. Owner controls ALL boards from one central admin panel on local network.

## User Personas
1. **Cafe Owner (Admin)**: Full system access - branding, pricing, boards, users, logs, revenue, health monitoring
2. **Staff/Wirt**: Quick unlock/extend/lock sessions, view board status (PIN login in 2s)
3. **Customers**: Touch kiosk - select game, enter names, play

## Core Requirements
- **Kiosk States**: LOCKED → UNLOCKED_SETUP → IN_GAME → FINISHED/ERROR → LOCKED
- **Pricing Models**: per_game (credits), per_time (minutes), per_player
- **Authentication**: JWT + PIN quick-login for staff
- **Multi-Board**: Master/Agent architecture, local LAN only
- **Database**: SQLite (Postgres-ready via SQLAlchemy)
- **Theme**: Dark, industrial minimal, 8 color palettes

## Implementation History

### Phase 1 (2026-03-03) - Core MVP ✅
- SQLAlchemy models: User, Board, Session, AuditLog, Settings
- JWT + PIN authentication with RBAC
- Board management APIs
- Kiosk UI: Locked, Setup, In-Game screens
- Admin Panel: Dashboard, Boards, Settings, Users, Logs, Revenue
- 8 color palettes, touch-optimized UI

### Phase 1.5 (2026-03-03) - Production Ready ✅
- Playwright Autodarts Integration service layer
- Docker Compose with nginx reverse proxy
- Session Scheduler (expiry + idle timeout)
- SETUP_GUIDE.md documentation
- Error screen with staff notification

### Phase 3 (2026-03-03) - Enterprise Hardening ✅
- **First-Run Setup Wizard**:
  - /setup route with secure credential form
  - Enforces admin password change (min 8 chars)
  - Enforces staff PIN change (4 digits)
  - Generates new JWT/Agent secrets securely
  - Secrets stored in /data/.secrets with restricted permissions

- **Security Hardening**:
  - LAN-only CORS configuration
  - Rate limiting (login: 3r/s, API: 10r/s)
  - TrustedHostMiddleware option
  - Agent API restriction to master IP (nginx config)
  - TLS-ready nginx configuration

- **Observability**:
  - JSON logging with rotation (10MB, 5 backups)
  - Admin Health page with 4 tabs:
    - Services: Scheduler, Backup, Health Monitor status
    - Agents: Online/offline status with latency
    - Backups: List, download, delete, create
    - Error Screenshots: Autodarts debug captures
  - Automation metrics: success rate, last error, screenshots

- **Backups**:
  - Automatic SQLite backups every 6 hours
  - Compressed (gzip) with 30-backup retention
  - Download/restore via admin UI
  - Pre-restore safety backup

- **Updates & Rollback**:
  - Version tracking service
  - Agent update endpoints
  - Local update instructions
  - Rollback capability

- **Automation Robustness**:
  - Circuit breaker pattern (3 failures → open)
  - Selector fallback with learning
  - Persistent browser context option
  - Manual fallback mode toggle

## Technical Stack
- **Backend**: FastAPI, SQLAlchemy, SQLite, bcrypt, PyJWT
- **Frontend**: React 19, Tailwind CSS, shadcn/ui, Recharts
- **Browser Automation**: Playwright
- **Deployment**: Docker Compose + nginx
- **Logging**: JSON format with rotation

## File Structure
\`\`\`
/app/
├── backend/
│   ├── server.py              # Main FastAPI (1300+ lines)
│   ├── database.py            # SQLAlchemy async config
│   ├── models/__init__.py     # User, Board, Session, etc.
│   └── services/
│       ├── autodarts_integration.py  # Playwright + Circuit Breaker
│       ├── scheduler.py              # Session expiry checker
│       ├── backup_service.py         # Auto backups
│       ├── health_monitor.py         # System health tracking
│       ├── update_service.py         # Version management
│       └── setup_wizard.py           # First-run security setup
├── frontend/src/
│   ├── pages/kiosk/           # Locked, Setup, InGame, Error
│   ├── pages/admin/           # Dashboard, Settings, Health, etc.
│   └── context/               # Auth, Settings providers
├── nginx/nginx.conf           # Reverse proxy with rate limiting
├── docker-compose.yml         # Production deployment
├── Dockerfile                 # Multi-stage build
├── SETUP_GUIDE.md             # Windows/Linux deployment guide
└── .env.example               # Configuration template
\`\`\`

## Default Credentials
- **Admin**: admin / admin123 (PIN: 1234) - **MUST CHANGE AT SETUP**
- **Staff**: wirt / wirt123 (PIN: 0000) - **MUST CHANGE AT SETUP**

## API Endpoints Summary
\`\`\`
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
\`\`\`

## Remaining Backlog (Phase 4)

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
