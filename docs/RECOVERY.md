# Recovery Documentation

## Why Recovery Was Needed

Between v3.4 and v3.15, the system accumulated a series of interconnected regressions caused by the introduction of central server management, licensing, and portal features. These features were built on top of a stable local core but introduced structural inconsistencies:

1. **License auto-recover bug:** The device would set itself to `suspended` after a central 403, then immediately flip back to `active` on the next config sync (which always returned 200). This made license enforcement impossible.

2. **Import path errors:** `action_poller.py` used `from backend.database.database import ...` — a path that doesn't exist (`database.py` is a file, not a package). This broke all remote board control actions.

3. **Action mapping conflation:** `start_session` was mapped to `unlock_board`, and `stop_session` to `lock_board`. Four distinct operations were reduced to two.

4. **WebSocket reconnect loop:** A 5-second minimum backoff caused rapid reconnection attempts when the central server was unreachable, flooding logs and destabilizing the system.

5. **Config sync silent failure:** Config changes saved in the portal were not applied on devices. No logging existed to diagnose the issue.

6. **Inconsistent online status:** Dashboard, device list, and device detail each calculated online/offline status differently (different fields, different thresholds).

7. **Revenue aggregation crash:** `None` values in `price_total` caused revenue calculations to fail silently.

8. **License enforcement bypass:** Multiple endpoints had `except: allow` patterns — on any error during license checking, the operation was allowed instead of blocked.

These issues compounded. Fixing one often exposed or triggered another. After multiple patching attempts (v3.15.0 through v3.15.3), the decision was made to stop incremental patching and perform a full system recovery.

---

## Baseline Version

**v3.3.1-hotfix2** (Git commit: `77887ee`)

This was the last version where the local core worked reliably:
- Board unlock/lock
- Session flow
- Autodarts observer
- Local settings
- Revenue tracking
- Admin dashboard
- Kiosk UI

This version did NOT have:
- Central server integration
- Licensing system
- Portal UI
- Action poller (remote board control)
- Config sync
- WebSocket push to central
- Device registration
- Telemetry sync

---

## What Was Done

### Phase 1: Restore Baseline (COMPLETED)

1. Identified `77887ee` as the last stable commit via git history
2. Created branches:
   - `snapshot/pre-recovery-current` — snapshot of the broken state
   - `recovery/from-v3.3.1-hotfix2` — active recovery branch
3. Restored all core files from baseline:
   - `backend/server.py` (352 lines, was 659)
   - `backend/routers/boards.py` (301 lines, was 351+)
   - `backend/routers/kiosk.py` (816 lines, was 1038)
   - All admin, settings, auth, players, matches, stats routers
   - All frontend pages (admin, kiosk)
   - All contexts, hooks, i18n
4. Verified all 6 core flows via automated testing (18/18 tests passed)

### Phase 2: Freeze Local Core (COMPLETED)

Documented in `memory/FROZEN_CORE.md`. All local modules are marked as frozen — no rewrites, no refactors allowed. Only adapter-style integrations permitted.

### Phase 3: Controlled Reintegration (NOT STARTED)

Central features will be reintroduced in strict order:

#### Layer A — Central Visibility (Read-Only)
- Device list in portal
- Heartbeat reporting
- Telemetry events
- **No control actions**
- Must not modify any frozen core file
- Implementation: new router + new service, registered in server.py startup

#### Layer B — License Status Sync
- Sync active/suspended/blocked from central
- Fail-closed: if check fails → block
- Central server is authoritative for status
- No local auto-recover
- No config sync yet

#### Layer C — Portal Board Control
- unlock_board / lock_board via central portal
- Requires Layer A + B to be stable
- Implementation: action poller as separate service

#### Layer D — Portal Config Sync
- Push config from portal to device
- Requires Layer C to be stable
- Version-based application (only apply if newer)
- Explicit logging: CONFIG RECEIVED / APPLIED / SKIPPED

#### Rules for Each Layer
1. Layer N must be fully verified before Layer N+1 starts
2. If Layer N breaks any baseline flow, revert immediately
3. Each layer adds NEW files only — no modifications to frozen core
4. Each layer has its own test suite

---

## Files on Disk but Not Active

The following files exist on disk from the pre-recovery state but are **NOT imported or used** by the current `server.py`:

### Backend Services (disabled)
- `backend/services/action_poller.py`
- `backend/services/config_sync_client.py`
- `backend/services/config_apply.py`
- `backend/services/license_service.py`
- `backend/services/device_identity_service.py`
- `backend/services/central_rejection_handler.py`
- `backend/services/ws_push_client.py`
- `backend/services/device_log_buffer.py`
- `backend/services/telemetry_sync_client.py`
- `backend/services/license_sync_client.py`
- `backend/services/cyclic_license_checker.py`
- `backend/services/device_registration_client.py`
- `backend/services/offline_queue.py`
- `backend/services/agent_client.py`

### Backend Routers (disabled)
- `backend/routers/central_proxy.py`
- `backend/routers/licensing.py`

### Frontend Pages (disabled)
- `frontend/src/pages/portal/*`
- `frontend/src/pages/operator/*`
- `frontend/src/pages/admin/Licensing.js`
- `frontend/src/pages/kiosk/LicenseOverlay.js`
- `frontend/src/context/CentralAuthContext.js`

### Central Server (disabled)
- `central_server/*` — entire directory

These files are preserved for reference during reintegration but have no effect on the running system.

---

## Branch Strategy

| Branch | Purpose | Status |
|--------|---------|--------|
| `recovery/from-v3.3.1-hotfix2` | Active recovery branch | CURRENT |
| `snapshot/pre-recovery-current` | Frozen snapshot of broken v3.15.3 state | REFERENCE ONLY |
| `main` | Production branch | To be updated after recovery is confirmed |
