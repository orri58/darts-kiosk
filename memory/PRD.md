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
- Guest-first model: Nickname only, no PII, no accounts required
- Stats per player: games_played, games_won, win_rate, avg_score, best_checkout, highest_throw
- Leaderboard API with period and sort_by filters
- Admin Leaderboard Page with podium and detailed table

### P0: Stammkunde Mode (2026-03-04) - COMPLETED
- **Player model**: nickname, nickname_lower, pin_hash, qr_token, is_registered, games_played, games_won
- **Backend endpoints** (routers/players.py):
  - `POST /api/players/check` - Check if nickname is registered (case-insensitive)
  - `POST /api/players/register` - Register guest→Stammkunde with 4-6 digit PIN, generates QR token
  - `POST /api/players/pin-login` - Authenticate with nickname+PIN (rate limited: 5/min/IP)
  - `POST /api/players/qr-login` - Authenticate with QR token
  - `GET /api/players/registered` - List all Stammkunden
- **Kiosk end-game** (routers/kiosk.py): Auto-creates guest Player records, updates games_played/games_won
- **Stats enrichment** (routers/stats.py): Leaderboard returns `is_registered` and `player_id` fields
- **Frontend SetupScreen**: 
  - Auto-checks nickname on keyboard OK press
  - PIN modal with 6-dot display for registered players
  - Registration flow with 2-step PIN confirmation
  - Verified "Stammkunde" badge (green ShieldCheck) for authenticated players
  - UserPlus button for guest→Stammkunde registration
- **Tests**: 21 backend tests + full frontend E2E tests, 100% pass rate

## Code Architecture
```
/app/backend/routers/
  auth.py, boards.py, kiosk.py, settings.py, admin.py,
  backups.py, updates.py, agent.py, discovery.py, matches.py, stats.py, players.py

/app/backend/services/
  autodarts_integration.py, scheduler.py, backup_service.py,
  health_monitor.py, update_service.py, setup_wizard.py,
  system_service.py, ws_manager.py, mdns_service.py, pairing_service.py

/app/backend/models/
  User, Board, Session, AuditLog, Settings, TrustedPeer, MatchResult, Player

/app/frontend/src/pages/
  admin: Dashboard, Boards, Settings, Users, Logs, Revenue, Health, System, Discovery, Leaderboard
  kiosk: LockedScreen, SetupScreen (with Stammkunde auth), InGameScreen, MatchResultScreen, ErrorScreen
  MatchPublicPage
```

## Remaining Backlog

### P1 - Upcoming
- [ ] Autodarts DOM Selector Tests (stability against Autodarts website changes)

### P2 - Future
- [ ] mDNS Discovery Enhancements
- [ ] Custom palette editor
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)
