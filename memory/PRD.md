# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture
- **Autodarts Observer MVP** (`AUTODARTS_MODE=observer`): Opens Autodarts fullscreen, observes game states passively
- **Master/Agent**: MASTER controls all boards, AGENTs are autonomous offline
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Implemented Features (Complete)

### v1.0.0 - Core
- [x] Kiosk UI (Locked/Setup/InGame/Finished states)
- [x] Admin Panel (Dashboard, Boards, Users, Settings, System, Health, Revenue, Logs, Discovery, Leaderboard, Reports)
- [x] JWT+PIN Auth (Admin/Staff roles), Stammkunde mode
- [x] Autodarts Observer Integration
- [x] mDNS Discovery + Secure Pairing
- [x] Custom Palette Editor, Sound Effects, EN/DE i18n
- [x] QR Match Sharing (configurable, default OFF)
- [x] Admin Reports with CSV export
- [x] Data Management (reset stats, delete matches/guests)
- [x] Release packages (Windows/Linux/Source)

### v1.1.0 - White-Label & Polish (2026-03-09)
- [x] Removed ALL Emergent branding
- [x] PWA installable app (manifest.json, icons, Apple touch icon)
- [x] Custom Kiosk Text Settings (9 configurable fields)
- [x] Admin Sidebar Responsive (scrollable, no overlap)
- [x] PWA Config tab in admin
- [x] CSV export auth fix, Logo deletion fix

### v1.2.0 - Update System, Tests, QR (2026-03-09)
- [x] GitHub-based Update System (manual check, version comparison, backup)
- [x] Autodarts DOM Selector Tests (13 pytest tests)
- [x] Optional QR on lock screen → public leaderboard
- [x] Public Leaderboard page (/public/leaderboard)
- [x] LAN-safe base URL detection

### v1.3.0 - Credits Overlay (2026-03-09)
- [x] Real-time credits overlay during gameplay (WebSocket + polling fallback)
- [x] 3 display modes: credit count, time remaining, "LETZTES SPIEL" warning
- [x] Auto-show on board unlock, auto-hide on lock
- [x] Admin toggle (Settings > Kiosk-Texte > Credits-Overlay)
- [x] Game simulation endpoints for testing (simulate-game-start/end)
- [x] Flash animation on credit decrement
- [x] Green/red WebSocket connection indicator
- [x] Credits decrement on game START (idle→in_game)
- [x] Auto-lock after last game finishes

## Key API Endpoints
- GET /api/kiosk/{boardId}/overlay - Credits overlay data (public)
- POST /api/kiosk/{boardId}/simulate-game-start - Test endpoint (admin)
- POST /api/kiosk/{boardId}/simulate-game-end - Test endpoint (admin)
- GET/PUT /api/settings/overlay - Overlay toggle config
- GET/PUT /api/settings/kiosk-texts - Kiosk text configuration
- GET/PUT /api/settings/pwa - PWA app configuration
- GET/PUT /api/settings/lockscreen-qr - Lock screen QR config
- GET /api/system/base-url - LAN-safe base URL
- GET /api/updates/check - GitHub release check
- POST /api/updates/prepare - Backup + update instructions

## Remaining Backlog

### P1
- [ ] Overlay strategy refinement (Chromium extension for tighter integration)

### P2
- [ ] mDNS Discovery Enhancements
- [ ] Remove legacy autodarts_integration.py
- [ ] Auto-update from GitHub (currently manual)
- [ ] PWA install prompt on public leaderboard
