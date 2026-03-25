# Darts Kiosk SaaS — Product Requirements Document

## Original Problem Statement
Production-ready Darts Kiosk SaaS platform for cafes. MASTER/AGENT architecture.

## Current State: v4.0.0-recovery — BASELINE RESTORED

### Recovery Source
- **Commit:** `77887ee` (v3.3.1-hotfix2)
- **Branch:** `recovery/from-v3.3.1-hotfix2`
- **Pre-recovery snapshot:** `snapshot/pre-recovery-current`

### What Was Removed (caused regression cluster)
- Central server integration (all 16 post-baseline services)
- Licensing cache + enforcement + auto-recover logic
- Action poller (central-driven board control)
- WS push client (central WebSocket)
- Portal frontend (PortalDeviceDetail, PortalLogin, etc.)
- Registration overlay
- Config sync client
- Central rejection handler
- License overlay

### What Remains (Frozen Core)
- Local admin panel (full CRUD)
- Board control (unlock/lock)
- Session flow (create/end)
- Autodarts observer (start/stop)
- Local settings (branding, pricing, language, sound, palettes)
- Revenue tracking
- Player stats + leaderboards
- QR match sharing
- Backup/restore
- mDNS discovery
- Health monitoring
- i18n (DE/EN)

### Phase 2: Frozen Core
See `/app/memory/FROZEN_CORE.md` for complete list of frozen files.

### Phase 3: Controlled Reintegration (NOT STARTED)
Must follow this exact order:
- **Layer A:** Central read-only visibility (device list, heartbeat, telemetry)
- **Layer B:** License status sync only (active/suspended/blocked, fail-closed)
- **Layer C:** Portal board control (unlock/lock via central)
- **Layer D:** Portal config sync

Each layer must be verified before next layer starts.
If a layer breaks baseline, REVERT immediately.

## Testing
- 18/18 backend tests passed
- All frontend flows verified (Playwright)
- Test report: `/app/test_reports/iteration_87.json`
