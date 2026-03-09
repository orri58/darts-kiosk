# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture: Autodarts Observer MVP
- `AUTODARTS_MODE=observer` (default): Open Autodarts browser, observe game state passively
- On unlock → opens Autodarts browser; on lock → closes it
- Observer detects: idle / in_game / finished → auto-decrements credits → auto-locks

## Implemented Features (v1.0.0)
- [x] Core MVP: Kiosk UI, Admin Panel, JWT+PIN Auth, Board CRUD, Pricing
- [x] Stammkunde Mode, QR Match Links, Leaderboards
- [x] Autodarts Observer Integration (stable MVP)
- [x] mDNS Discovery + Secure Pairing
- [x] Custom Palette Editor, Sound Effects, EN/DE i18n
- [x] Package-safe imports (from backend.xxx), sys.path dual-mode
- [x] LAN access fix (HOST=0.0.0.0, CORS=*, auto IP detection)
- [x] Release packages (Windows/Linux/Source)

## Windows Bundle Fixes (2026-03-09)
- [x] **greenlet/DLL fix:** Dedicated `.venv`, greenlet installed+validated first, early fail with VC++ Redistributable download link
- [x] **HOST whitespace fix:** Helper scripts `_run_frontend.bat`/`_run_backend.bat` use `set "HOST=0.0.0.0"` (quoted, no trailing spaces)
- [x] **Node version:** `check_requirements.bat` warns on Node 23+, rejects <18, recommends Node 20 LTS
- [x] **VC++ Redistributable:** Detected in check_requirements, documented in README

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests
- [ ] Refine observer selectors after real-world testing

### P2
- [ ] mDNS Discovery Enhancements
