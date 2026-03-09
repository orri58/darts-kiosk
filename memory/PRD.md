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
- [x] Auto-show on unlock, auto-hide on lock
- [x] Admin toggle + configurable upsell message and pricing hint
- [x] Upsell only shown on last game in credit mode (not time mode)
- [x] Game simulation endpoints for testing

### v1.4.0 - Update System, Legacy Cleanup, mDNS (2026-03-09)
- [x] Enhanced GitHub-based Update System:
  - Asset download with progress tracking (server-side + browser link)
  - Changelog display for each release (collapsible)
  - Update history persisted to database (Settings table)
  - Backup-before-update with rollback info
  - Download management (list, delete downloaded assets)
  - Recommended platform asset auto-detection
  - Manual step-by-step update instructions
- [x] Legacy Code Removal:
  - Deleted `autodarts_integration.py` (700+ lines legacy automation)
  - Deleted `test_autodarts_integration.py` and `test_autodarts_soak.py`
  - Refactored `health_monitor.py`: `AutomationMetrics` -> `ObserverMetrics`
  - Unified API: `record_observer_event()` replaces old automation methods
  - `/api/health/detailed` returns `observer_metrics` (clean terminology)
- [x] mDNS Discovery Improvements:
  - Periodic stale agent cleanup (configurable timeout + interval)
  - Network re-scan capability (`POST /discovery/rescan`)
  - Discovery statistics (scan count, total discovered, stale/paired counts)
  - Agent status indicators: Online, Stale, Paired
  - `seen_count` tracking for connection stability assessment
  - Configurable via env: MDNS_STALE_TIMEOUT, MDNS_CLEANUP_INTERVAL
- [x] Release packages rebuilt with all changes

## Remaining Backlog
### P2
- [ ] Chromium extension for tighter Autodarts overlay integration
- [ ] PWA Install Prompt for public leaderboard page

## API Endpoints (New in v1.4.0)
- `POST /api/updates/download` - Start downloading a release asset (background)
- `GET /api/updates/download/{id}` - Get download progress
- `GET /api/updates/downloads` - List downloaded assets
- `DELETE /api/updates/downloads/{name}` - Delete a downloaded asset
- `GET /api/updates/history` - Get persisted update history
- `POST /api/discovery/rescan` - Force mDNS re-scan
- `GET /api/discovery/stats` - Get discovery statistics
