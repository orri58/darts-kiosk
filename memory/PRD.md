# Darts Kiosk SaaS Platform — PRD

## Original Problem Statement
Production-ready, local-first "Darts Kiosk + Admin Control" system for cafes. MASTER/AGENT architecture over LAN with central portal management, kiosk UI, admin panel, Autodarts integration, sound effects, i18n (DE/EN), white-label branding, Stammkunde mode, and licensing.

## Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite (local), Central Server (SQLAlchemy + SQLite)
- **Frontend:** React + Tailwind CSS + Shadcn/UI
- **Integration:** Playwright (Autodarts), WebSockets, mDNS, Zeroconf
- **Deployment:** Docker Compose (prod), install.sh (Linux), start.bat (Windows)

## Current Version: v3.15.0

## Core Completed Features
- Kiosk UI (Locked/Setup/In-Game/Finished states)
- Admin Panel (boards, users, settings, system health)
- Real-time WebSocket dashboard updates
- mDNS discovery and secure pairing
- Public QR-code match summaries
- Guest and Stammkunde statistics + leaderboards
- Top Stammkunden rotation on locked screen
- Configurable sound effects
- Full i18n (DE/EN) for Kiosk + Admin
- Custom color palette editor
- Release packaging (Linux .tar.gz, Windows .zip, Source .zip)
- Absolute path resolution for all data files
- Central Portal with device management
- License system with grace periods and device binding
- Telemetry sync, config sync, action polling
- Health monitoring and offline resilience

## v3.15.0 P0 Fixes (Completed)
1. **Block A — Portal Board Control:** VALID_ACTIONS expanded to include unlock_board, lock_board, start_session, stop_session. RemoteAction model has params JSON column. action_poller executes board control via local DB operations.
2. **Block B — Portal Device Config:** Refactored to tabbed interface (Branding, Preise, Sound, Stammkunde, Farben, Kiosk, Sharing) matching local admin Settings.js structure.
3. **Block C — License Lock Enforcement:** get_effective_status() checks local cache FIRST for suspended/blocked/inactive. is_session_allowed() explicitly blocks these statuses.

## Key Files
- `central_server/server.py` — Central server API
- `central_server/models.py` — RemoteAction with params
- `backend/services/action_poller.py` — Executes remote actions locally
- `backend/services/license_service.py` — License enforcement with cache-first logic
- `backend/services/central_rejection_handler.py` — Sets suspended state
- `frontend/src/pages/portal/PortalDeviceDetail.js` — Portal device control + config
- `frontend/src/pages/admin/Dashboard.js` — Local admin board control
- `frontend/src/pages/admin/Settings.js` — Local admin settings

## Backlog
- P2: Autodarts DOM Selector Tests
- P2: mDNS Discovery Enhancements

Refer to CHANGELOG.md for history and ROADMAP.md for upcoming work.
