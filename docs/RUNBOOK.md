# Runbook

This runbook is for operating a local board PC in the real world.

## Daily operator commands

### Start
```bat
release\windows\start.bat
```

### Stop
```bat
release\windows\stop.bat
```

### Quick smoke check
```bat
release\windows\smoke_test.bat
```

## Expected healthy state

A healthy local machine should have all of these:
- `/api/health` returns 200
- `/api/boards` returns the configured board id
- `/api/kiosk/<BOARD_ID>/observer-status` returns JSON, not a crash/timeout
- kiosk page loads in Chrome
- board status changes are reflected without backend exceptions
- local play still works if central connectivity disappears

## Main URLs

Replace `<BOARD_ID>` with the value from `backend\.env`.

- Kiosk UI: `http://localhost:8001/kiosk/<BOARD_ID>`
- Admin UI: `http://localhost:8001/admin`
- Health: `http://localhost:8001/api/health`
- Boards: `http://localhost:8001/api/boards`
- Observer status: `http://localhost:8001/api/kiosk/<BOARD_ID>/observer-status`
- Version: `http://localhost:8001/api/system/version`

## Core operational checks

### 1. Board assignment
- open Admin
- confirm the configured `BOARD_ID` exists
- confirm the physical board PC is pointed at the same id in `backend\.env`
- if the wrong board is used, fix `BOARD_ID`, stop, then start again

### 2. Autodarts observer
If observer-related play automation is expected:
- verify `AUTODARTS_MODE=observer`
- verify `AUTODARTS_HEADLESS=false` during debugging
- run `setup_profile.bat` again if login/session looks stale
- inspect `data\autodarts_debug\` for screenshots

### 3. Session / credits flow
For a pay-to-play board:
- unlock or start a session from the UI
- verify the board transitions from `locked` -> `unlocked` / `in_game`
- verify credits decrement as matches complete
- verify the board returns to `locked` when credits/session end

## Logs

Look here first:
- `data\logs\app.log`
- `logs\backend.log`
- `data\autodarts_debug\`

What to search for:
- `AUTODARTS`
- `SESSION_`
- `CREDIT`
- `ACTION-POLL`
- `CONFIG-SYNC`
- `HEARTBEAT`
- `TELEMETRY`
- `OFFLINE-Q`

## Local-first / central outage behavior

Central connectivity is optional for the local core.

If the central side is down, the expected behavior is:
- backend stays up
- observer/session flow keeps working locally
- central heartbeat/config/telemetry paths back off and log warnings
- local operator actions do not block on central responses

If local play stops because of a central outage, that is a bug.

## Troubleshooting

### Backend does not come up
Check:
- `logs\backend.log`
- `data\logs\app.log`
- Python/venv activation
- VC++ redistributable if import errors mention `greenlet`

Quick response:
1. `release\windows\stop.bat`
2. rerun `release\windows\setup_windows.bat` if dependencies changed
3. `release\windows\start.bat`
4. `release\windows\smoke_test.bat`

### Wrong board opens in kiosk mode
Cause:
- `BOARD_ID` mismatch between Windows scripts and app data

Fix:
1. edit `backend\.env`
2. set correct `BOARD_ID`
3. stop/start again
4. verify `/api/boards`

### Chrome or observer looks stuck after restart
Cause:
- stale profile-tied Chrome processes

Fix:
1. `release\windows\stop.bat`
2. verify Chrome is gone in Task Manager
3. start again

Phase 5/6 scripts now kill Chrome using profile paths, not flaky window-title matching.

### Autodarts login keeps disappearing
Fix path:
1. stop the app
2. run `release\windows\setup_profile.bat`
3. sign in again
4. close Chrome normally
5. start again

### Observer status endpoint returns errors or empty data
Check:
- board exists in `/api/boards`
- `BOARD_ID` matches
- `AUTODARTS_MODE` is correct
- Playwright/Chrome are installed
- `data\autodarts_debug\` for screenshots

### Credits/session behavior looks wrong
Check:
- board status in Admin/API
- observer status endpoint
- recent app logs for match finalization / credit consumption
- pricing settings in Admin

## Recovery actions

### Rebuild a machine after dependency drift
```bat
release\windows\stop.bat
release\windows\setup_windows.bat
release\windows\start.bat
release\windows\smoke_test.bat
```

### Reset only the kiosk UI browser profile
Delete or archive:
- `data\kiosk_ui_profile`

Then start again.

### Reset only the Autodarts observer browser profile
Delete or archive:
- `data\chrome_profile\<BOARD_ID>`

Then rerun:
```bat
release\windows\setup_profile.bat
```

Do **not** delete both profiles casually on a live board unless you want a re-login session.

## Validation commands

### API smoke test
```bat
release\windows\smoke_test.bat
```

### Direct Python smoke test
```bat
python scripts\local_smoke.py --base-url http://localhost:8001 --board-id BOARD-1
```

### Observer status check
```text
GET /api/kiosk/BOARD-1/observer-status
```

## Escalate / still broken

If the machine still fails after the runbook steps, capture:
- `data\logs\app.log`
- `logs\backend.log`
- the output of `smoke_test.bat`
- any files from `data\autodarts_debug\`
- the exact `BOARD_ID` and Autodarts-related env settings

That is enough to debug most real failures without doing séance work in production.
