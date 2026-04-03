# Runbook

This runbook is for operating or debugging a **local board PC**.

Use it for:
- normal startup/shutdown
- smoke validation after updates
- observer/profile recovery
- checking whether a board is actually usable for local play

This document assumes the current baseline is **local-first**. Central connectivity may exist, but local play should not depend on it.

## 1. Daily operator commands

### Start
```bat
release\windows\start.bat
```

### Stop
```bat
release\windows\stop.bat
```

### Smoke check
```bat
release\windows\smoke_test.bat
```

### Rebuild dependencies / environment
```bat
release\windows\setup_windows.bat
```

### Recreate the persistent Autodarts profile
```bat
release\windows\setup_profile.bat
```

### First-run completion
If `/admin/login` redirects to `/setup`, finish the setup wizard there first.
It now sets:
- admin password
- quick PIN for existing admin/staff users
- generated JWT / agent secrets (optional, but recommended)

After setup, use **Admin -> Health -> Board-PC readiness** as the practical preflight view.
That screen now tells you, in one place, whether this machine is actually locally operable:
- setup/credential rotation state
- board-id and board-row alignment
- observer target prerequisites
- secrets load state
- DB/data/log/build presence
- local operator URLs

## 2. Expected healthy state

A healthy board PC should have all of the following:
- `GET /api/health` returns `200`
- `GET /api/boards` returns the expected board id
- `GET /api/kiosk/<BOARD_ID>/observer-status` returns JSON instead of timing out/crashing
- admin UI loads
- kiosk UI loads
- unlocking creates an active session
- locking cancels the active session and restores locked state
- if the observer is configured, it can open the correct Autodarts profile/session
- central outages do not prevent local unlock/play/lock flows

## 3. Main URLs

Replace `<BOARD_ID>` with the board id configured on that machine.

- Kiosk UI: `http://localhost:8001/kiosk/<BOARD_ID>`
- Admin UI: `http://localhost:8001/admin`
- Health: `http://localhost:8001/api/health`
- Boards: `http://localhost:8001/api/boards`
- Board session: `http://localhost:8001/api/boards/<BOARD_ID>/session`
- Observer status: `http://localhost:8001/api/kiosk/<BOARD_ID>/observer-status`
- Version: `http://localhost:8001/api/system/version`

## 4. First checks when something feels off

### 4.1 Confirm board identity
First look at **Admin -> Health -> Board-PC readiness**.

Then, if needed, check `backend\.env`:
- `BOARD_ID`
- `AUTODARTS_MODE`
- `AUTODARTS_HEADLESS`
- `AUTODARTS_MOCK`

Then confirm:
- the same board exists in `/api/boards`
- the kiosk URL uses the same board id
- the Autodarts profile path belongs to the same board

A wrong `BOARD_ID` causes a shocking amount of fake mystery.

### 4.2 Confirm board/session state
Check:
- `/api/boards/<BOARD_ID>`
- `/api/boards/<BOARD_ID>/session`
- `/api/kiosk/<BOARD_ID>/observer-status`

Questions to answer quickly:
- is the board `locked`, `unlocked`, or `in_game`?
- is there an active session?
- how many credits remain, or what is the time state?
- is the observer actually open/running?

### 4.3 Confirm local backend health before blaming Autodarts
If these fail, stop looking at browser/observer symptoms first:
- `/api/health`
- `/api/system/version`
- `/api/boards`

If the backend is not healthy, observer recovery will not save you.

## 5. Core operational flows

## 5.1 Unlock flow
Expected:
1. board starts `locked`
2. admin/staff unlocks board
3. active session is created
4. board becomes `unlocked`
5. if observer mode is configured, observer starts for that board

If unlock fails, check:
- board exists
- board has an Autodarts target URL when observer mode requires it
- board does not already have an active session
- pricing mode is one of `per_game`, `per_player`, `per_time`

## 5.2 Start-of-play flow
Expected:
1. session already exists
2. observer sees authoritative gameplay start
3. Autodarts-derived player count is captured from match/lobby payloads when available
4. if `per_player` credits are sufficient, board becomes `in_game` and charges once here
5. if credits are short, board enters `blocked_pending` and kiosk shows a fullscreen top-up overlay until staff adds enough credits

If `per_player` sessions look wrong, check:
- whether observer payloads actually exposed the player list/count
- whether `players_count` on the active session was updated to the authoritative Autodarts value
- whether the board is intentionally sitting in `blocked_pending` waiting for a top-up

## 5.3 Finish-of-play flow
Expected:
1. observer sees authoritative finish or staff ends manually
2. `finalize_match()` runs
3. credit/time capacity is evaluated
4. board either:
   - stays alive for next game, or
   - locks and tears down observer

If a board locks too early or not at all, inspect:
- pricing mode
- `credits_remaining`
- `expires_at`
- observer trigger reason in logs

## 5.4 Manual lock flow
Expected:
1. operator locks board
2. active session becomes `cancelled`
3. `ended_reason=manual_lock`
4. board returns to `locked`
5. observer shutdown is requested

## 6. Logs and artifacts

Look here first:
- `data\logs\app.log`
- `logs\backend.log`
- `data\autodarts_debug\`
- Admin UI -> `System` -> `Diagnostics` -> `Support snapshot`
- Admin UI -> `System` -> `Diagnostics` -> `Support-Bundle exportieren`

The support bundle now contains:
- application logs
- supervisor logs when present
- system info snapshot
- health snapshot
- setup/preflight snapshot
- readiness snapshot
- agent/device-ops snapshot
- downloaded update assets + app backup snapshot
- last updater result snapshot

Practical rule:
- if you only need a quick read, use the in-product **Diagnostics** snapshot first
- if the issue is unclear or you are about to escalate, export the full support bundle before poking at the machine further

Useful search terms:
- `SESSION`
- `AUTODARTS`
- `Observer->Kiosk`
- `RETURN_HOME`
- `KIOSK_UI`
- `board_status`
- `CONFIG-SYNC`
- `ACTION-POLL`
- `TELEMETRY`

## 7. Troubleshooting recipes

## 7.1 Backend will not come up

Check:
- `logs\backend.log`
- `data\logs\app.log`
- Python/venv activation
- VC++ redistributable if imports fail around `greenlet`

Recovery:
1. `release\windows\stop.bat`
2. `release\windows\setup_windows.bat`
3. `release\windows\start.bat`
4. `release\windows\smoke_test.bat`

## 7.2 Wrong board opens or wrong profile is reused

Cause:
- `BOARD_ID` mismatch between backend config and operator assumptions

Fix:
1. edit `backend\.env`
2. correct `BOARD_ID`
3. stop/start again
4. re-check `/api/boards`

## 7.3 Observer opens but login/session is gone

Fix:
1. stop the app
2. run `release\windows\setup_profile.bat`
3. sign in again inside the persistent profile
4. close Chrome normally
5. start the app again

Artifacts to inspect after failure:
- `data\autodarts_debug\`
- observer status endpoint

## 7.4 Chrome/observer looks stuck after restart

Cause:
- stale Chrome processes or broken profile reuse

Fix:
1. `release\windows\stop.bat`
2. confirm Chrome is really gone in Task Manager
3. start again

Phase 5/6 already improved Chrome cleanup by targeting profile paths instead of window titles.

## 7.5 Credits/session behavior looks wrong

Check:
- board status in Admin or `/api/boards/<BOARD_ID>`
- active session row via `/api/boards/<BOARD_ID>/session`
- recent finalize/start logs
- pricing settings in Admin

Remember:
- `per_player` charges at authoritative start, not finish
- `blocked_pending` means the match really started, but the current session balance is short for the authoritative player count
- topping up a `blocked_pending` session should immediately clear the overlay and resume play without double-charging
- `per_game` charges at authoritative finish/manual end
- `per_time` uses `expires_at`, not credit deduction

## 7.6 Central outage suspicion

Expected behavior during central trouble:
- local backend still runs
- local observer/session flow still works
- optional sync/heartbeat loops log warnings/backoff
- unlock/play/lock does not block on remote success

If central problems stop local play, treat that as a bug.

## 8. Recovery actions

### Safe local recovery via admin UI
Use `System -> Device Ops` for the host-near controls that should not be buried in generic health pages:
- Autodarts ensure / restart
- backend restart
- Windows reboot / shutdown
- Explorer restore
- kiosk-shell re-enable
- Task Manager enable / disable
- agent autostart register / remove

Practical rule:
- if the kiosk shell or lockdown behaviour is the problem, switch to **Explorer** first so the machine becomes operable again
- only then change shell/task-manager/autostart settings further
- after shell changes, expect a sign-out/sign-in or reboot to be required
- Device Ops now keeps the last result inline; do not rely only on short-lived toast messages when confirming whether an action actually landed

### Full rebuild after drift
```bat
release\windows\stop.bat
release\windows\setup_windows.bat
release\windows\start.bat
release\windows\smoke_test.bat
```

### Reset kiosk UI browser profile only
Archive/delete:
- `data\kiosk_ui_profile`

Then start again.

### Reset Autodarts observer profile only
Archive/delete:
- `data\chrome_profile\<BOARD_ID>`

Then rerun:
```bat
release\windows\setup_profile.bat
```

Do not casually delete both profiles on a live board unless you want to rebuild the whole login/session state.

## 9. Validation checklist after update

Update/rollback intent is now:
1. create backup before install
2. stage + validate package
3. write manifest
4. launch external updater
5. let updater perform health/version checks
6. keep rollback artifact available if install/health fails

When an update looked suspicious, do **not** guess blindly:
- check `System -> Updates` for downloaded packages, backup artifacts, and updater result
- check `System -> Diagnostics` for readiness/support snapshot context
- export a support bundle before further repair work
- only then decide whether to retry install or trigger rollback

Minimum:
1. `start.bat`
2. `smoke_test.bat`
3. open Admin and Kiosk UI
4. verify correct board id
5. unlock board
6. verify active session and observer status
7. lock board
8. verify session is cancelled and board returns to locked

Live validation still required beyond this repo:
- real Autodarts match start
- real authoritative finish
- real keep-alive / next-game behavior
- real window-focus behavior on Windows kiosk hardware

## 10. Escalation bundle

If the board still fails after runbook steps, collect:
- `data\logs\app.log`
- `logs\backend.log`
- output from `smoke_test.bat`
- any files in `data\autodarts_debug\`
- `BOARD_ID` and Autodarts-related env settings
- whether the failure happened on unlock, start-of-play, finish, or lock

That is enough to debug most real failures without guessing wildly.
