# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Each dartboard has its own Mini-PC running the full stack. Owner controls ALL boards from one central admin panel on local network.

## User Personas
1. **Cafe Owner (Admin)**: Full system access - branding, pricing, boards, users, logs, revenue, health monitoring, system management, discovery
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
- SQLAlchemy models, JWT + PIN auth, Board management, Kiosk + Admin UI

### Phase 1.5 (2026-03-03) - Production Ready
- Playwright Autodarts, Docker Compose, Session Scheduler

### Phase 3 (2026-03-03) - Enterprise Hardening
- Setup Wizard, Security, JSON logging, Backups, Updates, Circuit breaker

### Phase 4 (2026-03-03) - Installer + System Management
- install.sh v2.0.0, /admin/system page, System APIs

### P1: Live Stability (2026-03-04)
- **Autodarts Soak Test**: 200 cycles, 4 modes, 100% pass, 15 tests
- **WebSocket**: Real-time board status, auto-reconnect, Live/Polling indicator
- **Refactoring**: server.py 1434→190 lines, 10 router modules, 32/32 regression

### P1: mDNS Discovery + Secure Pairing (2026-03-04)
- **mDNS Service** (Zeroconf):
  - Agent advertises: `darts-kiosk-<BOARD_ID>._darts-kiosk._tcp.local.`
  - TXT records: board_id, role=agent, version, api=/api/agent, fingerprint
  - Master discovers agents on LAN, tracks ip/port/version/last_seen
  - Stale entry removal (300s timeout), duplicate board_id handling
- **Secure Pairing**:
  - Rotating 6-digit code on Agent kiosk screen (60s rotation)
  - Master admin enters code to initiate pairing
  - Challenge-response handshake: verify code → nonce → HMAC sign → paired token
  - Replay prevention (used nonce tracking)
  - TrustedPeer model stores paired relationships
  - Unpair/revoke trust support
- **Admin Discovery Page** (`/admin/discovery`):
  - Discovered agents list with IP, port, version, fingerprint, pair status
  - Paired peers (Vertrauensbeziehungen) with unpair button
  - mDNS active/inactive status indicator
  - Pairing dialog with 6-digit code input
- **Kiosk Pairing Code Display**:
  - Footer shows rotating 6-digit code with countdown bar
  - Auto-refreshes every 5 seconds
- **Tests**: 20 unit tests (code gen/verify, challenge-response, replay, HMAC, fingerprint) + 16 API tests = 36 total, all passing

## Code Architecture
```
/app/backend/
├── server.py           # App setup, lifespan, middleware (~200 lines)
├── schemas.py          # Pydantic models
├── dependencies.py     # Auth deps, helpers
├── database.py         # SQLAlchemy async setup
├── models/             # ORM models (User, Board, Session, AuditLog, Settings, TrustedPeer)
├── routers/
│   ├── auth.py         # Auth + User CRUD
│   ├── boards.py       # Board CRUD + Session Control
│   ├── kiosk.py        # Kiosk Actions
│   ├── settings.py     # Settings + Assets
│   ├── admin.py        # Logs, Revenue, Health, Setup, System
│   ├── backups.py      # Backup Management
│   ├── updates.py      # Update Management
│   ├── agent.py        # Agent API
│   └── discovery.py    # mDNS Discovery + Secure Pairing
├── services/
│   ├── autodarts_integration.py  # Playwright + Circuit Breaker
│   ├── scheduler.py              # Session expiry
│   ├── backup_service.py         # Auto backups
│   ├── health_monitor.py         # Health monitoring
│   ├── update_service.py         # Version management
│   ├── setup_wizard.py           # First-run wizard
│   ├── system_service.py         # System info, logs
│   ├── ws_manager.py             # WebSocket broadcasts
│   ├── mdns_service.py           # Zeroconf mDNS
│   └── pairing_service.py        # Secure pairing
└── tests/
    ├── test_autodarts_soak.py    # 15 tests
    ├── test_discovery_pairing.py # 20 tests
    └── test_p1_discovery_api.py  # 16 API tests
```

## Remaining Backlog

### P2 - Upcoming
- [ ] QR-Code Match Link (expiring public link, random token, 24h, no PII)
- [ ] Player statistics & leaderboard
- [ ] Stammkunde mode (QR/PIN login)
- [ ] Custom palette editor
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)
