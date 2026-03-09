# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture: Autodarts Observer MVP
- `AUTODARTS_MODE=observer` (default): Open Autodarts browser, observe game state passively
- On unlock: opens Autodarts browser; on lock: closes it
- Observer detects: idle / in_game / finished -> auto-decrements credits -> auto-locks

## Implemented Features (v1.0.0)
- [x] Core MVP: Kiosk UI, Admin Panel, JWT+PIN Auth, Board CRUD, Pricing
- [x] Stammkunde Mode, QR Match Links, Leaderboards
- [x] Autodarts Observer Integration (stable MVP)
- [x] mDNS Discovery + Secure Pairing
- [x] Custom Palette Editor, Sound Effects, EN/DE i18n
- [x] Package-safe imports (from backend.xxx), sys.path dual-mode
- [x] LAN access fix (HOST=0.0.0.0, CORS=*, auto IP detection)
- [x] Release packages (Windows/Linux/Source)
- [x] Admin Reports page with date filters and CSV export
- [x] Data Management controls (reset guest/all stats, delete match history)
- [x] Remove Logo button in branding settings
- [x] QR Match Sharing as configurable option (default: OFF)
- [x] Credits Overlay page (/overlay/:boardId)

## Implemented Features (v1.1.0 - 2026-03-09)
- [x] P0: Removed ALL Emergent branding (index.html, PostHog, overlays, favicon)
- [x] P0: PWA / Installable Web App (manifest.json, 192/512px icons, Apple touch icon, standalone mode)
- [x] P0: Custom Kiosk Text Settings (9 configurable fields: locked_title, locked_subtitle, pricing_hint, game_running, game_finished, call_staff, credits_label, time_label, staff_hint)
- [x] P0: Admin Sidebar Responsive (scrollable nav via flexbox, no overlap, mobile drawer)
- [x] P0: PWA Config tab in admin (app_name, short_name, theme_color, background_color)
- [x] P0: Kiosk-Texte tab in admin (all 9 fields editable with persistence)
- [x] Bug fix: CSV export auth (token as query parameter for window.open)
- [x] Bug fix: Logo deletion persistence (flag_modified for SQLAlchemy JSON mutation)
- [x] Bug fix: Reports.js import paths (context instead of hooks)

## Key API Endpoints
- GET/PUT /api/settings/kiosk-texts - Kiosk text configuration
- GET/PUT /api/settings/pwa - PWA app configuration
- DELETE /api/settings/branding/logo - Logo removal (with flag_modified fix)
- POST /api/reports/sessions - Session reports with filtering
- GET /api/reports/sessions/csv - CSV export (supports token as query param)

## Remaining Backlog

### P1
- [ ] GitHub-based Update System (manual check, version comparison, backup before update)
- [ ] Autodarts DOM Selector Tests (deferred multiple times)
- [ ] Overlay strategy refinement (Chromium extension consideration)

### P2
- [ ] mDNS Discovery Enhancements
- [ ] Remove legacy autodarts_integration.py (deprecated by observer model)
