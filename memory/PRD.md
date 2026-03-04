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

### P2: Player Statistics & Leaderboard (2026-03-04)
- Guest-first model, stats per player, leaderboard API, admin page

### P0: Stammkunde Mode (2026-03-04) - COMPLETED
- Player model with nickname+PIN, QR token, registration/login
- Auto guest Player creation on game end, stats tracking
- Frontend PIN dialog, registration flow, verified badges

### Top Stammkunden Rotation (2026-03-04) - COMPLETED
- **Backend**: `GET /api/stats/top-registered?period=&limit=` with 45s in-memory cache
- **Settings**: `stammkunde_display` (enabled=false, period=month, interval_seconds=6, max_entries=3, nickname_max_length=15)
- **Admin UI**: Settings > Stammkunde tab with toggle, period selector, interval/entries/nickname length controls
- **Kiosk LockedScreen**: Dedicated rotation slide with rank badge, truncated nickname, ShieldCheck badge, stats (S/G + Quote), highlight stat
- **Highlight priority**: 180+ throw > checkout >= 80 > throw >= 100 > win rate fallback
- **Fallback**: CTA "Werde Stammkunde!" when no registered players exist
- **Fade transition** on player rotation, no UI flicker
- Tests: 15 backend + full frontend, 100% pass

### Custom Palette Editor (2026-03-04) - COMPLETED
- **Palette Selection**: Grid of all palettes (default + custom) with hover edit/delete actions
- **Palette Editor**: Inline editor below grid with:
  - Name field
  - 6 color inputs (bg, surface, primary, secondary, accent, text) with native color pickers
  - Live preview panel showing actual UI elements
  - WCAG contrast warnings (critical <3:1, warning <4.5:1) for text/bg, text/surface, primary/bg
- **Custom palette CRUD**: Create new, edit existing, delete (cannot delete active palette)
- **JSON Import/Export**: Import from JSON textarea, export to clipboard
- **Default palettes**: 8 built-in (Industrial, Midnight, Forest, Crimson, Ocean, Sunset, Slate, Emerald) — not deletable
- **Schema fix**: SettingsUpdate.value changed to Union[dict, list] to support palette lists
- Tests: Full backend + frontend, 100% pass

## Code Architecture
```
/app/backend/routers/
  auth.py, boards.py, kiosk.py, settings.py, admin.py,
  backups.py, updates.py, agent.py, discovery.py, matches.py, stats.py, players.py

/app/backend/models/
  User, Board, Session, AuditLog, Settings, TrustedPeer, MatchResult, Player

/app/frontend/src/pages/
  admin: Dashboard, Boards, Settings (Branding/Preise/Farbschema+Editor/Stammkunde), Users, Logs, Revenue, Health, System, Discovery, Leaderboard
  kiosk: LockedScreen (TopStammkunden+TopPlayers+PairingCode), SetupScreen (Stammkunde auth), InGameScreen, MatchResultScreen, ErrorScreen
  MatchPublicPage
```

## Remaining Backlog

### P1 - Upcoming
- [ ] Autodarts DOM Selector Tests (stability against Autodarts website changes)

### P2 - Future
- [ ] mDNS Discovery Enhancements
- [ ] Sound effects for kiosk
- [ ] Multi-language (EN/DE toggle)
