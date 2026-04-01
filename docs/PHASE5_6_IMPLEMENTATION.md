# Phase 5 / 6 implementation

## Goal

Finish the shift from "feature demo that mostly works" to "local board runtime that an operator can actually bring up and keep alive."

The emphasis stayed on local-first behavior, not on adding more central coupling.

## Code changes

### 1. Optional central/background loops hardened
Updated services:
- `backend/services/action_poller.py`
- `backend/services/config_sync_client.py`
- `backend/services/offline_queue.py`
- `backend/services/telemetry_sync_client.py`
- `backend/services/central_heartbeat_client.py`

Main changes:
- `start()` now spawns/owns background tasks instead of potentially blocking forever in a loop
- `stop()` or shutdown paths now cancel owned tasks more cleanly
- cancellation handling was added to loop bodies
- repeated central failures back off/log without dragging local runtime into the mess

Why this matters:
- optional adapter services should behave like optional adapter services
- callers should not accidentally hang on startup because a helper loop never returns

### 2. Fixed a real remote-action stability bug
In `action_poller.py` the code used:
- `board_ws.broadcast({...})`

But the real API is:
- `board_ws.broadcast(event, data)`

That meant remote-action driven board status updates were on a bad path.

Fixed to:
- `board_ws.broadcast("board_update", {...})`

### 3. Fixed central heartbeat health snapshot bug
In `central_heartbeat_client.py`, heartbeat health collection called a non-existent `health_monitor.get_status()` method and silently fell back to `{}`.

Now it reads `health_monitor.get_health()` and serializes the useful fields.

Result:
- heartbeat payload contains actual local health data again
- central-side observability is less fake

### 4. Windows bring-up scripts made less flaky
Updated:
- `release/windows/start.bat`
- `release/windows/stop.bat`
- `release/windows/setup_profile.bat`
- `release/windows/setup_windows.bat`
- `release/windows/README.md`

Main changes:
- scripts read `BOARD_ID` from `backend\.env`
- start/stop now kill Chrome by profile path, not by window title
- setup flow points operators through profile prep and smoke validation
- README now reflects the local-first operator path instead of stale central-heavy assumptions

Why this matters:
- the old window-title-based Chrome cleanup was unreliable
- hardcoding `BOARD-1` in operator scripts is fine right until it isn’t

### 5. Smoke tooling added
Added:
- `scripts/local_smoke.py`
- `release/windows/smoke_test.bat`

Smoke checks cover:
- `/api/health`
- `/api/system/version`
- `/api/boards`
- `/api/kiosk/<BOARD_ID>/observer-status`

This is intentionally small and boring. Good smoke tests should be boring.

## Test coverage added

Added:
- `backend/tests/test_phase56_stability_installation.py`

Covers:
- non-blocking startup for `ConfigSyncClient`
- non-blocking startup for `ActionPoller`
- correct WebSocket broadcast signature for remote board updates
- heartbeat health payload using the real health monitor snapshot

## Validation run

Executed:

```bash
. .venv/bin/activate && python -m pytest -q \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py
```

Observed result:
- `14 passed`

Additional script validation:
- `python -m py_compile scripts/local_smoke.py`
- smoke helper exercised against a stub HTTP server during validation

## What changed operationally

### Better now
- optional central/background services are less likely to interfere with local runtime
- remote board actions no longer use a broken WS update path
- operators have a documented first-time setup and smoke-test path
- board-specific Windows scripts now actually follow configured board identity
- Chrome cleanup on restart is more deterministic

### Still not solved by code alone
- no physical board/Autodarts end-to-end proof in this environment
- no guarantee every developer venv already has all optional runtime deps installed
- observer/browser behavior still needs one real Windows validation pass

## Recommended next step

Do exactly one thing next:
- run the documented install + smoke flow on a real Windows board PC with a real Autodarts login and capture logs/screenshots for any remaining edge cases

That will flush out the last 10 percent far faster than another round of architecture poetry.
