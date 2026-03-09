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
- [x] Credits Overlay (/overlay/:boardId)
- [x] Admin Reports with CSV export
- [x] Data Management (reset stats, delete matches/guests)
- [x] Release packages (Windows/Linux/Source)

### v1.1.0 - White-Label & Polish (2026-03-09)
- [x] Removed ALL Emergent branding (index.html, PostHog, overlays, favicon)
- [x] PWA installable app (manifest.json, icons, Apple touch icon, standalone mode)
- [x] Custom Kiosk Text Settings (9 fields: locked_title, locked_subtitle, pricing_hint, game_running, game_finished, call_staff, credits_label, time_label, staff_hint)
- [x] Admin Sidebar Responsive (scrollable nav via flexbox, no overlap)
- [x] PWA Config tab (app_name, short_name, theme_color, background_color)
- [x] CSV export auth fix (token as query param)
- [x] Logo deletion persistence fix (flag_modified)

### v1.2.0 - Update System, Tests, QR (2026-03-09)
- [x] GitHub-based Update System (manual check, version comparison, backup before update, release download links)
- [x] Autodarts DOM Selector Tests (13 pytest tests: state detection, false-positive prevention, coverage)
- [x] Optional QR on lock screen (configurable via admin, links to public leaderboard)
- [x] Public Leaderboard page (/public/leaderboard) - mobile-optimized, no auth required
- [x] LAN-safe base URL detection (never localhost, uses X-Forwarded-Host or detected LAN IP)
- [x] Admin QR toggle in Kiosk-Texte tab (enabled/disabled, custom label, custom path)

## Key API Endpoints
- GET/PUT /api/settings/kiosk-texts - Kiosk text configuration
- GET/PUT /api/settings/pwa - PWA app configuration
- GET/PUT /api/settings/lockscreen-qr - Lock screen QR config
- GET /api/system/base-url - LAN-safe base URL for QR generation
- GET /api/updates/check - Check GitHub for new releases
- GET /api/updates/status - Current version + repo info
- POST /api/updates/prepare - Backup + update instructions

## Remaining Backlog

### P1
- [ ] Overlay strategy refinement (Chromium extension consideration)

### P2
- [ ] mDNS Discovery Enhancements
- [ ] Remove legacy autodarts_integration.py
- [ ] Auto-update from GitHub (currently manual only)
