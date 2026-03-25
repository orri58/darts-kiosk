# Component Status Matrix

Current version: **v4.0.0-recovery + Layer A**

## Local Core (Frozen — Stable)

| Component | Status | Module | Notes |
|-----------|--------|--------|-------|
| Authentication | **Stable** | `routers/auth.py` | JWT + PIN login |
| Board Management | **Stable** | `routers/boards.py` | CRUD, unlock, lock |
| Kiosk State Machine | **Stable** | `routers/kiosk.py` | Locked → Unlocked → InGame → Finished |
| Session Flow | **Stable** | `routers/boards.py` | Create on unlock, end on lock/game-end |
| Admin Dashboard | **Stable** | `pages/admin/Dashboard.js` | Board cards, status, controls |
| Kiosk UI | **Stable** | `pages/kiosk/KioskLayout.js` | 5 screens: Locked, Setup, InGame, Result, Error |
| Settings | **Stable** | `routers/settings.py` | Branding, pricing, language, sound, palettes |
| Revenue & Reports | **Stable** | `routers/admin.py` | Session-based revenue, CSV export |
| Autodarts Observer | **Stable** | `services/autodarts_observer.py` | Playwright automation (requires Chrome) |
| Player Stats | **Stable** | `routers/players.py`, `stats.py` | Stammkunde, leaderboards, QR sharing |
| WebSocket (local) | **Stable** | `services/ws_manager.py` | Board state broadcasts to kiosk UI |
| Sound Effects | **Stable** | `services/sound_generator.py` | WAV generation for game events |
| Health Monitor | **Stable** | `services/health_monitor.py` | System health checks |
| mDNS Discovery | **Stable** | `services/mdns_service.py` | Network device discovery |
| Backup/Restore | **Stable** | `services/backup_service.py` | SQLite database backup |
| i18n (DE/EN) | **Stable** | `i18n/translations.js` | Full German + English support |

## Layer A — Central Read-Only Visibility (Active)

| Component | Status | Module | Notes |
|-----------|--------|--------|-------|
| Heartbeat Client | **Active** | `services/central_heartbeat_client.py` | 60s interval, exponential backoff |
| Central Proxy | **Active** | `routers/central_proxy.py` | Read-only proxy to central server |
| Portal Login | **Active** | `pages/portal/PortalLogin.js` | Central server auth |
| Portal Dashboard | **Active** | `pages/portal/PortalDashboard.js` | Device table with status |
| Portal Devices | **Active** | `pages/portal/PortalDevices.js` | Device cards with health details |
| Layer A Security | **Active** | `routers/central_proxy.py` | Blocks all write operations |

## Central / Portal (Disabled — Deferred)

| Component | Status | Module | Recovery Layer | Notes |
|-----------|--------|--------|---------------|-------|
| Central Server | **Disabled** | `central_server/server.py` | — | Separate FastAPI app, not started |
| Device List | **Disabled** | `central_server/server.py` | Layer A | Read-only visibility |
| Heartbeat | **Disabled** | `services/telemetry_sync_client.py` | Layer A | Device → Central status |
| Telemetry | **Disabled** | `services/telemetry_sync_client.py` | Layer A | Events, stats |
| License Sync | **Disabled** | `services/license_service.py` | Layer B | active/suspended/blocked |
| License Enforcement | **Disabled** | (was in boards.py, kiosk.py) | Layer B | Fail-closed checks |
| Portal Board Control | **Disabled** | `services/action_poller.py` | Layer C | Remote unlock/lock |
| Config Sync | **Disabled** | `services/config_sync_client.py` | Layer D | Push config to device |
| Portal UI | **Disabled** | `pages/portal/*` | Layer A+ | React portal pages |
| Operator UI | **Disabled** | `pages/operator/*` | Layer A+ | Operator dashboard |
| WS Push Client | **Disabled** | `services/ws_push_client.py` | Layer A | Real-time to central |
| Device Registration | **Disabled** | `services/device_registration_client.py` | Layer A | Initial device setup |
| License Overlay | **Disabled** | `pages/kiosk/LicenseOverlay.js` | Layer B | Kiosk blocked screen |

## Legend

| Status | Meaning |
|--------|---------|
| **Stable** | Tested, frozen, production-ready |
| **Disabled** | Code exists on disk but is not imported or executed |
| **Deferred** | Planned for future reintegration |
