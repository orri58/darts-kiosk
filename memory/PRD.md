# Darts Kiosk SaaS — Product Requirements Document

## Original Problem Statement
Production-ready Darts Kiosk SaaS platform for cafes. MASTER/AGENT architecture.

## Current State: v4.0.0-recovery + Layer A

### Recovery Source
- **Commit:** `77887ee` (v3.3.1-hotfix2)
- **Branch:** `recovery/from-v3.3.1-hotfix2`

### Frozen Local Core (unchanged)
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

### Layer A: Central Read-Only Visibility (COMPLETED)
- Device heartbeat client (60s interval, exponential backoff)
- Central proxy router (/api/central/* → port 8002, read-only)
- Portal UI (login, dashboard, device list)
- Layer A security: all write operations blocked except login
- 16/16 tests passed (iteration_88)

### Phase 3: Controlled Reintegration
- **Layer A:** Central read-only visibility — DONE
- **Layer B:** License status sync only (active/suspended/blocked, fail-closed)
- **Layer C:** Portal board control (unlock/lock via central)
- **Layer D:** Portal config sync

Each layer must be verified before next layer starts.
If a layer breaks baseline, REVERT immediately.

## Testing
- 18/18 baseline tests passed (iteration_87)
- 16/16 Layer A tests passed (iteration_88)
- All frontend flows verified (Playwright)

## Architecture
See `/app/docs/ARCHITECTURE.md` and `/app/memory/FROZEN_CORE.md`
