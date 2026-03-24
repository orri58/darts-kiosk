# Darts Kiosk SaaS — Product Requirements Document

## Original Problem Statement
Production-ready "Darts Kiosk + Admin Control" SaaS platform for cafes. MASTER/AGENT architecture over LAN.

## Current Focus: Stabilization v3.15.2 (NO NEW FEATURES)

## Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Tailwind + Shadcn/UI
- **Central Server:** Separate FastAPI on port 8002
- **Proxy:** Local backend proxies via `/api/central/`

## v3.15.2 Fixes (2026-03-24)

### Fix 1: Board Control Import (BLOCKER)
- **Root Cause:** `action_poller.py:348` — `from backend.database.database import AsyncSessionLocal` — `database.py` is a file, NOT a package
- **Fix:** Changed to `from backend.database import AsyncSessionLocal` + fallback `from database import`
- **Files:** `backend/services/action_poller.py` (6 import blocks fixed)

### Fix 2: License Enforcement — Fail-Closed
- **Root Cause:** `boards.py:177`, `kiosk.py:748`, `action_poller.py:411` all had `except: allow` pattern
- **Fix:** Central `BLOCKED_STATES` + `ALLOWED_STATES` in `license_service.py`, all catch blocks now BLOCK on error
- **Files:** `backend/services/license_service.py`, `backend/routers/boards.py`, `backend/routers/kiosk.py`, `backend/services/action_poller.py`

### Fix 3: Config Sync
- **Status:** Already working correctly. Version comparison + callbacks + DB apply + logging all functional.
- **Priority chain verified:** Global → Customer → Location → Device

### Fix 4: Heartbeat / Online Status — Single Rule
- **Root Cause:** `_ser_device()` had no `is_online`/`connectivity` field. Dashboard used `last_sync_at` (600s), Detail used `last_heartbeat_at` (300s) — inconsistent.
- **Fix:** New `_compute_device_connectivity()` function (online < 5min, degraded < 15min, offline > 15min). Used by ALL 4 endpoints.
- **Files:** `central_server/server.py` (4 endpoints unified)

### Fix 5: Autodarts Default URL
- **Root Cause:** `kiosk.py:692` returned early if `autodarts_url` was empty instead of using default
- **Fix:** Fall back to `AUTODARTS_URL = 'https://play.autodarts.io'`
- **Files:** `backend/routers/kiosk.py`

### Fix 6: Central Server in Preview — Already running

### Fix 7: Config Duplication — No duplication found. Priority chain correct.

### Fix 8: Build Consistency — Import fallback pattern in all critical services

### Fix 9: E2E Tests — 40 tests (14 new), all passing

## Testing: 40/40 E2E tests passing
- Board control actions (4 tests)
- License fail-closed (4 tests)
- Connectivity consistency (4 tests)
- Action poller import (2 tests)
- All existing tests still passing

## Pending: User Verification of v3.15.2 Windows Build

## Backlog
- P2: Autodarts DOM Selector Tests
- P2: mDNS Discovery Enhancements
