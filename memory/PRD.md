# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture
- **Autodarts Observer MVP** (`AUTODARTS_MODE=observer`): Opens Autodarts fullscreen, observes game states passively. Kiosk skips internal setup UI - customer uses Autodarts directly.
- **Master/Agent**: MASTER controls all boards, AGENTs are autonomous offline
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Implemented Features (Complete)

### v1.0.0 - Core
- [x] Kiosk UI, Admin Panel, JWT+PIN Auth, Boards, Pricing, Sessions
- [x] Stammkunde Mode, QR Match Links, Leaderboards
- [x] Autodarts Observer, mDNS Discovery, Sound Effects, i18n
- [x] Reports/CSV, Data Management, Release packages

### v1.1.0 - White-Label & Polish
- [x] All Emergent branding removed, PWA, Custom Kiosk Texts, Responsive Sidebar

### v1.2.0 - Update System, Tests, QR
- [x] GitHub-based Update System, Autodarts DOM Selector Tests, Public Leaderboard QR

### v1.3.0 - Credits Overlay
- [x] Real-time overlay, "LETZTES SPIEL" warning, upsell message

### v1.4.0 - Update System, Legacy Cleanup, mDNS
- [x] Enhanced Updates (download, changelog, history, backup-before-update)
- [x] Legacy Code Removal (health_monitor refactored to observer terminology)
- [x] mDNS Improvements (periodic cleanup, re-scan, stats)

### v1.4.1 - Background Update Checker + Snooze
- [x] Background scheduler (24h), dashboard notification banner
- [x] Snooze (48h) + permanent dismiss per-version, survives restart

### v1.5.0 - Observer Mode Kiosk Flow Fix (2026-03-09)
- [x] **Unlock in observer mode skips old SetupScreen entirely**
- [x] New `ObserverActiveScreen` shows: Credits/Time, Observer-Status (Bereit/Laeuft/Beendet), Staff+End buttons
- [x] `GET /boards/{id}/session` returns `autodarts_mode` field
- [x] `KioskLayout` routes based on `autodartsMode`: observer→ObserverActiveScreen, legacy→SetupScreen
- [x] Both `unlocked` and `in_game` states render ObserverActiveScreen in observer mode
- [x] `start-game` endpoint NOT required for observer flow
- [x] Customer uses native Autodarts UI directly
- [x] Release packages rebuilt

## Key Files
- `frontend/src/pages/kiosk/ObserverActiveScreen.js` - NEW observer mode kiosk UI
- `frontend/src/pages/kiosk/KioskLayout.js` - Updated routing logic
- `backend/routers/boards.py` - `autodarts_mode` in session endpoint

## Remaining Backlog
### P2
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
