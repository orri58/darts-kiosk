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
- [x] Optional QR on lock screen -> public leaderboard

### v1.3.0 - Credits Overlay
- [x] Real-time credits overlay (WebSocket + polling)
- [x] 3 modes: credit count, time remaining, "LETZTES SPIEL" warning
- [x] Admin toggle + configurable upsell message and pricing hint

### v1.4.0 - Update System, Legacy Cleanup, mDNS (2026-03-09)
- [x] Enhanced GitHub-based Update System (asset download, changelog, history, backup-before-update, rollback)
- [x] Legacy Code Removal (autodarts_integration.py deleted, health_monitor refactored)
- [x] mDNS Discovery Improvements (periodic cleanup, re-scan, stats)

### v1.4.1 - Background Update Checker (2026-03-09)
- [x] Background scheduler checks GitHub once every configurable interval (default 24h)
- [x] Caches result to DB (Settings table, key `update_check_cache`)
- [x] Dashboard notification banner: "Neue Version verfuegbar: vX.X.X"
- [x] Banner buttons: [Release Notes ansehen] (toggles inline changelog), [Update starten] (navigates to System > Updates), [X] (dismiss)
- [x] Dismiss persisted per-version (won't re-show for same version)
- [x] Respects GitHub API rate limits, logs errors silently
- [x] Configurable via .env: UPDATE_CHECK_ENABLED, UPDATE_CHECK_INTERVAL_HOURS
- [x] NO automatic installation - updates remain manual
- [x] Release packages rebuilt

## Configuration (.env)
```
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL_HOURS=24
GITHUB_REPO=owner/darts-kiosk   # Required for update checks
GITHUB_TOKEN=ghp_...             # Optional, for private repos / higher rate limits
```

## API Endpoints (New in v1.4.1)
- `GET /api/updates/notification` - Get cached background check result (for dashboard banner)
- `POST /api/updates/notification/dismiss?version=X.X.X` - Dismiss notification for a version

## Remaining Backlog
### P2
- [ ] Chromium extension for tighter Autodarts overlay integration
- [ ] PWA Install Prompt for public leaderboard page
