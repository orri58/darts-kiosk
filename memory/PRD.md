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
- [x] GitHub-based Update System, Autodarts DOM Selector Tests
- [x] Optional QR on lock screen -> public leaderboard

### v1.3.0 - Credits Overlay
- [x] Real-time credits overlay, "LETZTES SPIEL" warning, upsell message

### v1.4.0 - Update System, Legacy Cleanup, mDNS
- [x] Enhanced GitHub-based Update System (download, changelog, history, backup-before-update)
- [x] Legacy Code Removal (autodarts_integration.py, health_monitor refactored)
- [x] mDNS Discovery Improvements (periodic cleanup, re-scan, stats)

### v1.4.1 - Background Update Checker
- [x] Background scheduler checks GitHub once per 24h (configurable)
- [x] Dashboard notification banner with Release Notes, Update starten buttons

### v1.4.2 - Snooze/Dismiss Notification (2026-03-09)
- [x] **[Spaeter erinnern]** button: snoozes banner for 48h per-version
- [x] **[X] dismiss**: permanently hides banner for that specific version
- [x] Both snooze and dismiss reset when a newer version appears
- [x] `snooze_until` and `dismissed_version` persisted in DB (survives restart)
- [x] Frontend logic: hides if (snoozed + not expired) OR (dismissed for this version)
- [x] Release packages rebuilt

## Configuration (.env)
```
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL_HOURS=24
GITHUB_REPO=owner/darts-kiosk
GITHUB_TOKEN=ghp_...              # Optional
```

## API Endpoints (Notification)
- `GET /api/updates/notification` - Get cached result (returns snoozed_version, snooze_until, dismissed_version)
- `POST /api/updates/notification/dismiss?version=X` - Permanent dismiss per-version
- `POST /api/updates/notification/snooze?version=X&hours=48` - Snooze for N hours

## Remaining Backlog
### P2
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
