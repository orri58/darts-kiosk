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
- Refactoring: server.py 1434->190 lines, 10 router modules
- mDNS Discovery + Secure Pairing (Zeroconf, challenge-response, TrustedPeer)

### P2: QR-Code Match-Link (2026-03-04)
- MatchResult model with 128-bit public token, 24h expiry
- Kiosk QR screen for 60s after game end, public match page
- Rate limited public endpoint (20 req/min/IP)

### P2: Player Statistics & Leaderboard (2026-03-04)
- **Guest-first model**: Nickname only, no PII, no accounts required
- **Stats per player**: games_played, games_won, win_rate, avg_score, best_checkout, highest_throw
- **Computed from MatchResult records** (not public links)
- **Leaderboard API**: `/api/stats/leaderboard` with period (today/week/month/all) and sort_by (games_won/games_played/win_rate/avg_score)
- **Player API**: `/api/stats/player/{nickname}` with case-insensitive search
- **Top Today API**: `/api/stats/top-today` for kiosk idle screen
- **End-game enhanced**: Accepts optional winner, scores, best_checkout, highest_throw in request body
- **Admin Leaderboard Page** (`/admin/leaderboard`):
  - Top 3 podium with crown/medal icons
  - Full player table with rank, games, wins, win rate, details
  - Period tabs: Heute, Woche, Monat, Gesamt
  - Sort buttons: Siege, Spiele, Quote
- **Kiosk Idle Rotation**: Top players of the day rotate every 5s on locked screen
- Tests: 100% pass rate (backend + frontend)

## Code Architecture
```
/app/backend/routers/
  auth.py, boards.py, kiosk.py, settings.py, admin.py,
  backups.py, updates.py, agent.py, discovery.py, matches.py, stats.py

/app/backend/services/
  autodarts_integration.py, scheduler.py, backup_service.py,
  health_monitor.py, update_service.py, setup_wizard.py,
  system_service.py, ws_manager.py, mdns_service.py, pairing_service.py

/app/backend/models/
  User, Board, Session, AuditLog, Settings, TrustedPeer, MatchResult

/app/frontend/src/pages/
  admin: Dashboard, Boards, Settings, Users, Logs, Revenue, Health, System, Discovery, Leaderboard
  kiosk: LockedScreen (with TopPlayersRotation + PairingCode), SetupScreen, InGameScreen, MatchResultScreen, ErrorScreen
  MatchPublicPage
```

## Remaining Backlog

### P2 - Upcoming
- [ ] Stammkunde mode (QR/PIN login) – builds on existing stats
- [ ] Custom palette editor
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)
