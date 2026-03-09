# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture
- **Autodarts Observer MVP** (`AUTODARTS_MODE=observer`): Opens Autodarts fullscreen, observes game states passively
- **Master/Agent**: MASTER controls all boards, AGENTs are autonomous offline
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Implemented Features (Complete)

### v1.0.0 - Core
- [x] Kiosk UI, Admin Panel, JWT+PIN Auth, Boards, Pricing, Sessions
- [x] Stammkunde Mode, QR Match Links, Leaderboards
- [x] Autodarts Observer Integration, mDNS Discovery, Sound Effects, i18n
- [x] Reports/CSV, Data Management, Release packages

### v1.1.0 - White-Label & Polish
- [x] Removed ALL Emergent branding, PWA installable app
- [x] Custom Kiosk Text Settings, Admin Sidebar Responsive

### v1.2.0 - Update System, Tests, QR
- [x] GitHub-based Update System, Autodarts DOM Selector Tests (13 pytest)
- [x] Optional QR on lock screen → public leaderboard

### v1.3.0 - Credits Overlay
- [x] Real-time credits overlay (WebSocket + polling)
- [x] 3 modes: credit count, time remaining, "LETZTES SPIEL" warning
- [x] Auto-show on unlock, auto-hide on lock
- [x] Admin toggle + configurable upsell message and pricing hint
- [x] Upsell only shown on last game in credit mode (not time mode)
- [x] Game simulation endpoints for testing

## Remaining Backlog
### P1
- [ ] Chromium extension for tighter Autodarts overlay integration
### P2
- [ ] mDNS Discovery Enhancements
- [ ] Remove legacy autodarts_integration.py
- [ ] Auto-update from GitHub
