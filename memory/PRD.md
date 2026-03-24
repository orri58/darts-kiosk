# Darts Kiosk SaaS — Product Requirements Document

## Original Problem Statement
Production-ready Darts Kiosk SaaS platform. MASTER/AGENT architecture.

## Current Focus: System Stability v3.15.3 (NO NEW FEATURES)

## v3.15.3 System Stability Corrections

### 1. License Auto-Recover REMOVED
- **Root Cause:** `central_rejection_handler.py:75` — `handle_central_reactivation()` wrote `status: "active"` to cache after ANY 200 from config sync, overriding central suspension
- **Fix:** Removed cache write. Handler now only logs. Only central server can restore active status via real license check.
- **Files:** `backend/services/central_rejection_handler.py`
- **Nachweis:** Test `TestLicenseNoAutoRecover` — cache bleibt suspended nach reactivation handler

### 2. WebSocket Stabilized
- **Root Cause:** MIN_BACKOFF=5s caused rapid reconnect loop when central WS unreachable
- **Fix:** MIN_BACKOFF=15s, MAX_BACKOFF=120s, STABLE_AFTER=3 failures → max backoff. Disconnect reason logged.
- **Files:** `backend/services/ws_push_client.py`
- **Nachweis:** Backoff progression verified: 15s → 30s → 120s → 120s...

### 3. Action Mapping — 4 Separate Handlers
- **Root Cause:** `action_poller.py:390` — `start_session` mapped to `_do_unlock`, `stop_session` mapped to `_do_lock`
- **Fix:** Added `_do_start_session` (starts game, board stays unlocked) and `_do_stop_session` (ends session, board stays UNLOCKED — distinct from lock)
- **Files:** `backend/services/action_poller.py`
- **Nachweis:** Real board test: unlock → start_session → stop_session (board=unlocked) → lock (board=locked)

### 4. Config Sync — Explicit Logging
- **Root Cause:** No explicit logs for config application pipeline
- **Fix:** Added "CONFIG RECEIVED", "CONFIG APPLIED", "CONFIG SKIPPED" at every decision point
- **Files:** `backend/services/config_sync_client.py`, `backend/services/config_apply.py`
- **Nachweis:** Log strings verified in code

### 5. Autodarts — Start/Fail Logging
- **Root Cause:** `kiosk.py:692` returned early on empty URL; no start/fail logs
- **Fix:** URL default fallback + "AUTODARTS STARTED" / "AUTODARTS FAILED" with exc_info
- **Files:** `backend/routers/kiosk.py`
- **Nachweis:** Log strings verified in code

### 6. Online/Offline Consistent
- **Root Cause:** Dashboard used `last_sync_at` (600s), Detail used `last_heartbeat_at` (300s)
- **Fix:** Single `_compute_device_connectivity()` function: online (<5min) / degraded (<15min) / offline
- **Files:** `central_server/server.py` (all 4 endpoints)
- **Nachweis:** All 4 endpoints return identical connectivity for same device

### 7. Revenue Null-Safe
- **Root Cause:** `admin.py:102` — `s.price_total` can be None, causing incorrect aggregation
- **Fix:** `float(s.price_total or 0)` everywhere
- **Files:** `backend/routers/admin.py`
- **Nachweis:** Revenue endpoint returns 856.5 for 395 sessions

## Testing: 47/47 E2E tests passing

## Pending: User verification of v3.15.3 Windows build

## Backlog
- P2: Autodarts DOM Selector Tests
- P2: mDNS Discovery Enhancements
