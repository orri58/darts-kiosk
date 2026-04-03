# Installation

This is the practical local-first install path for a board PC.

## Scope

This guide is for:
- Windows board machines running the kiosk locally
- single-device or small local deployments
- setups where play must continue even if the central server is offline

This guide is **not** a cloud deployment guide.

## What you need

### Required
- Windows 10 or Windows 11, 64-bit
- Python 3.11+ available as `python`
- Node.js 18+ available as `node`
- Google Chrome
- Microsoft Visual C++ Redistributable x64
- local admin rights for first-time setup

### Strongly recommended
- wired Ethernet on the board PC
- a dedicated Windows user for kiosk operation
- Windows auto-login only if the machine is physically controlled
- a UPS if the board PC is in a venue

### Optional
- internet for first-time dependency install, updates, and Autodarts sign-in
- central server connectivity for licensing/telemetry sync

Local play should still work without the central server once the machine is set up.

## Files that matter

Windows operators mainly use:
- `release/windows/check_requirements.bat`
- `release/windows/install.bat`
- `release/windows/setup_windows.bat`
- `release/windows/setup_profile.bat`
- `release/windows/start.bat`
- `release/windows/stop.bat`
- `release/windows/smoke_test.bat`

## First-time setup

From the repo root on the Windows machine:

1. Easiest path: run `release/windows/install.bat`
2. If you want the manual path: `release/windows/check_requirements.bat` → `release/windows/setup_windows.bat`
3. Review `backend\.env`
4. Run `release/windows/setup_profile.bat`
5. Run `release/windows/start.bat`
6. Open `http://localhost:8001/setup` (or `http://localhost:8001/admin/login` and let it redirect)
7. Complete the setup wizard
8. Run `release/windows/smoke_test.bat`

If step 8 passes, you have a usable local runtime baseline.

What the setup wizard now does:
- rotates the admin password away from the seeded default
- rotates the quick PIN for existing admin/staff users so the old seeded quick PIN cannot linger
- can generate fresh JWT / agent secrets into `data/.secrets`
- shows local URLs + basic preflight state instead of making the operator infer them

## Minimum `backend\.env` review

At minimum, verify these keys:

```env
JWT_SECRET=change-this
BOARD_ID=BOARD-1
AUTODARTS_URL=https://play.autodarts.io
AUTODARTS_MODE=observer
AUTODARTS_HEADLESS=false
AUTODARTS_MOCK=false
```

Notes:
- `BOARD_ID` controls which board the Windows helper scripts open and which Chrome observer profile they reuse.
- For first bring-up, keep `AUTODARTS_HEADLESS=false` so failures are visible.
- `AUTODARTS_MOCK=true` is useful only for demo/testing without a real Autodarts session.
- Central variables are optional for local-first runtime. Do not block bring-up on them.

## Board assignment

The app now seeds only the local default board (`BOARD-1`) on first startup.

Recommended flow:
1. decide which physical board this PC owns
2. set that value in `backend\.env` as `BOARD_ID`
3. start the app once
4. open the admin UI
5. confirm that a board with the same `board_id` exists
6. rename the board/location in Admin if needed

If you want a different board id, create/update it in Admin first, then align `BOARD_ID` in `backend\.env`.

Important current default runtime values:
- `AGENT_PORT=8003`
- `GITHUB_REPO=orri58/darts-kiosk`

## Autodarts setup

### One-time profile preparation
Run:

```bat
release\windows\setup_profile.bat
```

That opens Chrome using the persistent profile for the configured `BOARD_ID`.

Inside that Chrome window:
1. sign in to Google if required
2. open `https://play.autodarts.io`
3. sign in to Autodarts
4. install required extensions
5. close Chrome normally

Profile data is stored in:
- `data\chrome_profile\<BOARD_ID>`

### Runtime verification
After `start.bat`, verify observer state via:
- `http://localhost:8001/api/kiosk/<BOARD_ID>/observer-status`
- or `release/windows/smoke_test.bat`

What you want to see:
- the backend is healthy
- the board exists
- observer status endpoint responds cleanly
- no repeating observer/browser crash loop in logs

## Local URLs

Default local URLs:
- Kiosk UI: `http://localhost:3000/kiosk/<BOARD_ID>` in dev / `http://localhost:8001/kiosk/<BOARD_ID>` when served by backend build
- Admin UI: `http://localhost:3000/admin/login` in dev / `http://localhost:8001/admin` when served by backend build
- Setup wizard: `http://localhost:3000/setup` in dev
- Health: `http://localhost:8001/api/health`
- Observer status: `http://localhost:8001/api/kiosk/<BOARD_ID>/observer-status`
- Version: `http://localhost:8001/api/system/version`

Default seeded admin credentials on a fresh database:
- admin user: `admin` / `admin123`
- admin quick PIN before setup: `1234`

Treat those as bootstrap-only. The first-run setup wizard is expected to replace them.

## Device ops / recovery after install

Once the board is up, the main operator-maintenance surface is:
- `System -> Device Ops`

Use it for:
- Autodarts ensure / restart
- backend restart
- Windows reboot / shutdown
- Explorer restore if kiosk shell/lockdown went wrong
- kiosk-shell re-enable after repair
- Task Manager enable / disable
- agent autostart register / remove

Recovery rule of thumb:
- if the box feels "too kiosked" or hard to recover, switch to **Explorer** first
- after shell changes, expect a reboot or sign-out/sign-in
- export a support bundle before risky repair work when possible

## Updates

### Source checkout workflow
If this machine runs directly from a git checkout:
1. stop the app
2. pull the new version
3. rerun `setup_windows.bat` if dependencies changed
4. start the app
5. run `smoke_test.bat`

### Bundle/update script workflow
If your release bundle ships `update.bat`, use that bundle’s documented flow and still finish with `smoke_test.bat`.

Admin-side update flow expectation:
1. check for updates in **System → Updates**
2. use **Jetzt installieren** for the direct Windows flow, or inspect packages manually if needed
3. the system creates an app backup automatically
4. download + validation + install are prepared for you
5. let the updater perform restart + health/version check
6. keep rollback material available until the board passes smoke + operator checks

## Logs

Main places to look:
- `data\logs\app.log`
- `logs\backend.log`
- `logs\*.log`
- `data\autodarts_debug\` for captured screenshots if observer/browser failures occur

## Fast failure checklist

If setup fails:
- Python missing -> install Python 3.11+ and enable PATH
- Node missing -> install Node 18+
- `greenlet` import fails -> install VC++ Redistributable x64
- Chrome missing -> install Google Chrome
- Playwright install fails -> rerun setup with internet access
- observer fails immediately -> rerun `setup_profile.bat`, log in again, keep headful mode for debugging
- wrong board opens -> fix `BOARD_ID` in `backend\.env`

## Recommended post-install checks

Run these every time you install or update a board PC:

```bat
release\windows\start.bat
release\windows\smoke_test.bat
```

Then manually verify:
- kiosk page loads
- admin page loads
- correct board id is shown
- credits overlay appears if enabled
- Autodarts login survives restart
- stopping and restarting does not leave stale Chrome profile processes behind
