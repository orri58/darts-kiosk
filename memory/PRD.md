# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Implementation History

### Phase 1-1.5 (2026-03-03) - Core MVP + Production
- SQLAlchemy models, JWT+PIN auth, Board CRUD, Kiosk + Admin UI
- Playwright Autodarts, Docker Compose, Session Scheduler

### Phase 3 (2026-03-03) - Enterprise Hardening
- Setup Wizard, Security, JSON logging, Backups, Updates, Circuit breaker

### Phase 4 (2026-03-03) - Installer + System Management
- install.sh v2.0.0, /admin/system page, System APIs

### P1: Live Stability (2026-03-04)
- Autodarts Soak Test: 200 cycles, 4 modes, 15 tests
- WebSocket real-time board status, Dashboard Live indicator
- Refactoring: server.py 1434→190 lines, 10 router modules
- mDNS Discovery + Secure Pairing (Zeroconf, rotating 6-digit code, challenge-response, TrustedPeer)

### P2: QR-Code Match-Link (2026-03-04)
- **MatchResult model**: public_token (128-bit, 32 hex chars), 24h expiry, game_type, players, winner, scores, duration, board_name
- **Kiosk QR Screen**: Shows QR code for 60s after game end, then auto-locks
  - QRCodeSVG rendering, countdown timer, match URL display
  - Bug fixed: polling override prevented via showingQrRef
- **Public Match Page** (`/match/:token`):
  - No auth required, rate limited (20 req/min/IP)
  - Shows: game mode, players (nicknames only), winner with trophy, board name, date/time, duration
  - No PII exposed
  - Error states: expired (410), not found (404), rate limited (429)
- **Backend**:
  - POST /api/matches – create match result (internal)
  - GET /api/match/{token} – public view with rate limiting
  - POST /api/kiosk/{id}/end-game – now returns match_token + match_url
- Tests: 14/14 backend + all frontend = 100% pass

## Code Architecture
```
/app/backend/
├── server.py           # App setup, lifespan, middleware (~200 lines)
├── schemas.py          # Pydantic models
├── dependencies.py     # Auth deps, helpers
├── database.py         # SQLAlchemy async
├── models/             # User, Board, Session, AuditLog, Settings, TrustedPeer, MatchResult
├── routers/
│   ├── auth.py, boards.py, kiosk.py, settings.py
│   ├── admin.py, backups.py, updates.py
│   ├── agent.py, discovery.py, matches.py
├── services/
│   ├── autodarts_integration.py, scheduler.py, backup_service.py
│   ├── health_monitor.py, update_service.py, setup_wizard.py
│   ├── system_service.py, ws_manager.py, mdns_service.py, pairing_service.py
└── tests/
    ├── test_autodarts_soak.py (15), test_discovery_pairing.py (20)
    ├── test_p2_match_link.py (14)

/app/frontend/src/
├── pages/
│   ├── admin/  (Dashboard, Boards, Settings, Users, Logs, Revenue, Health, System, Discovery)
│   ├── kiosk/  (LockedScreen, SetupScreen, InGameScreen, MatchResultScreen, ErrorScreen, KioskLayout)
│   └── MatchPublicPage.js
├── hooks/useBoardWS.js
└── context/ (AuthContext, SettingsContext)
```

## Remaining Backlog

### P2 - Upcoming
- [ ] Player statistics & leaderboard
- [ ] Stammkunde mode (QR/PIN login)
- [ ] Custom palette editor
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)
