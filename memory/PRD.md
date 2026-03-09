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

## Bug Fixes (2026-03-09)
- [x] Fixed Reports.js import paths (useAuth/useI18n from context, not hooks)
- [x] Fixed CSV export authentication (accept token as query parameter for window.open)

## Windows Bundle Fixes
- [x] greenlet/DLL fix: Dedicated .venv, greenlet installed+validated first
- [x] HOST whitespace fix: Helper scripts use set "HOST=0.0.0.0" (quoted)
- [x] Node version: check_requirements.bat warns on Node 23+, rejects <18
- [x] VC++ Redistributable: Detected in check_requirements, documented in README

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests (deferred multiple times)
- [ ] Refine observer selectors after real-world testing
- [ ] Overlay strategy refinement (Chromium extension consideration)

### P2
- [ ] mDNS Discovery Enhancements
