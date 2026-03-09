# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture: Autodarts Observer MVP

### Interaction Model (AUTODARTS_MODE=observer)
- Our system handles: lock/unlock, session/credits/time control, auto-lock
- Autodarts handles: game setup, player entry, scoring (native UI)
- On unlock → opens Autodarts browser automatically
- Observer polls DOM every 4s to detect: idle / in_game / finished
- On game finished → decrements credits or checks time
- On credits/time exhausted → closes Autodarts browser → locked screen
- Feature flag: `AUTODARTS_MODE=observer` (default) or `automation` (legacy)

### Key Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/boards/{id}/unlock` | POST | Start session + open Autodarts browser |
| `/api/boards/{id}/lock` | POST | End session + close Autodarts browser |
| `/api/kiosk/{id}/start-game` | POST | Records players/game type (no-op for Autodarts) |
| `/api/kiosk/{id}/end-game` | POST | Decrement credits, auto-lock if exhausted |
| `/api/kiosk/{id}/observer-status` | GET | Observer state per board |
| `/api/kiosk/observers/all` | GET | All observer statuses (admin) |
| `/api/kiosk/{id}/observer-reset` | POST | Close + reopen observer |

## Implemented Features (v1.0.0)
- [x] Core MVP: Kiosk UI, Admin Panel, JWT+PIN Auth, Board CRUD, Pricing
- [x] Stammkunde Mode (PIN/QR login, player stats, leaderboard)
- [x] Autodarts Observer Integration (replaces fragile automation)
- [x] mDNS Discovery + Secure Pairing
- [x] QR Match Links (24h expiry)
- [x] Custom Palette Editor (live preview, WCAG contrast)
- [x] Sound Effects (synthetic WAV, admin controls)
- [x] EN/DE i18n (180+ keys)
- [x] Top Stammkunden Rotation on Locked Screen
- [x] System Management (health, backups, logs)
- [x] Package-safe imports (from backend.xxx)
- [x] LAN access fix (HOST=0.0.0.0, auto IP detection, CORS=*)
- [x] Release packages (Windows/Linux/Source)

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests (validate observer selectors against real Autodarts)
- [ ] Refine observer selectors after real-world Windows testing

### P2
- [ ] mDNS Discovery Enhancements
