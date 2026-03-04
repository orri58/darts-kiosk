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

### Phase 1.5 (2026-03-03) - Production Ready
- Playwright Autodarts Integration service layer
- Docker Compose with nginx reverse proxy
- Session Scheduler (expiry + idle timeout)

### Phase 3 (2026-03-03) - Enterprise Hardening
- First-Run Setup Wizard, Security (LAN-only CORS, rate limiting)
- JSON logging with rotation, Admin Health page
- Auto SQLite backups, Updates & Rollback, Circuit breaker

### Phase 4 (2026-03-03) - One-Command Installer + System Management
- install.sh v2.0.0: Ubuntu 24.04/22.04, idempotent, offline, systemd, firewall
- /admin/system page with 4 tabs (Backups, Updates, Logs, Details)
- Backend APIs: /api/system/info, /api/system/logs, /api/system/logs/bundle

### P1: Live Stability (2026-03-04)
- **Autodarts Soak Test**: 200 cycles across 4 game modes (301, 501, Cricket, Training) - 100% pass
  - Circuit Breaker unit tests (6 tests)
  - Selector Fallback learning tests (3 tests)
  - Mock Integration lifecycle tests (2 tests)
  - Full soak test + integration tests (4 tests)
- **WebSocket Real-Time Board Status**: Replaces 5s HTTP polling
  - /api/ws/boards endpoint with auto-reconnect
  - Broadcasts on: unlock, lock, extend, start-game, end-game
  - Dashboard shows Live/Polling indicator
  - Fallback to 30s polling if WS disconnects
- **Refactoring**: server.py (1434 lines) -> modular architecture
  - server.py: ~190 lines (config, lifespan, app setup, WS endpoint)
  - schemas.py: All Pydantic models
  - dependencies.py: Auth, password hashing, token management, DB helpers
  - routers/auth.py: Authentication + User CRUD
  - routers/boards.py: Board CRUD + Session Control (unlock/lock/extend)
  - routers/kiosk.py: Kiosk Actions (start-game/end-game/call-staff)
  - routers/settings.py: Settings + Asset Upload
  - routers/admin.py: Logs, Revenue, Health, Setup, System
  - routers/backups.py: Backup Management
  - routers/updates.py: Update & Rollback
  - routers/agent.py: Agent API (Master-Agent communication)
  - 100% regression: 32/32 API tests passed, all soak + WS tests pass

## Code Architecture
```
/app/backend/
├── server.py           # App setup, lifespan, middleware, router includes (~190 lines)
├── schemas.py          # All Pydantic request/response models
├── dependencies.py     # Auth deps, helpers, shared DB utils
├── database.py         # SQLAlchemy async setup
├── models/             # SQLAlchemy ORM models
├── routers/
│   ├── auth.py         # /auth/login, /auth/pin-login, /auth/me, /users CRUD
│   ├── boards.py       # /boards CRUD + /boards/{id}/unlock|lock|extend|session
│   ├── kiosk.py        # /kiosk/{id}/start-game|end-game|call-staff
│   ├── settings.py     # /settings/branding|pricing|palettes + /assets
│   ├── admin.py        # /logs, /revenue, /health, /setup, /system
│   ├── backups.py      # /backups CRUD
│   ├── updates.py      # /updates management
│   └── agent.py        # /agent/health|status|update
├── services/
│   ├── autodarts_integration.py  # Playwright automation + Circuit Breaker
│   ├── scheduler.py              # Session expiry scheduler
│   ├── backup_service.py         # Auto backups
│   ├── health_monitor.py         # Health monitoring
│   ├── update_service.py         # Version management
│   ├── setup_wizard.py           # First-run wizard
│   ├── system_service.py         # System info, logs
│   └── ws_manager.py             # WebSocket broadcast manager
└── tests/
    ├── test_autodarts_soak.py    # 15 tests: soak + circuit breaker + selectors
    ├── test_phase4_system.py     # Phase 4 system tests
    ├── test_refactored_api.py    # 32 regression tests
    └── test_websocket_p1.py      # WebSocket broadcast tests
```

## Remaining Backlog

### P1 - Next
- [ ] mDNS Discovery with secure pairing (discovery != trust)

### P2 - Upcoming
- [ ] QR-Code Match Link (expiring public link, random token, 24h, no PII)
- [ ] Player statistics & leaderboard
- [ ] Stammkunde mode (QR/PIN login)
- [ ] Custom palette editor
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)
