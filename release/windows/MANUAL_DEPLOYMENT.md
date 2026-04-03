# Darts Kiosk — Windows board PC deployment guide

## What this guide is for

This is the practical deployment path for a **local board machine**.

The baseline assumption is:
- the board PC must be able to run locally
- local admin + kiosk surfaces are the primary operator path
- optional central/portal/licensing adapters may exist, but they are **not the dependency that defines whether local play works**

If you want the short version, use `README.md` in this same folder.
This document is the more detailed step-by-step path.

---

## 1. System requirements

Recommended:
- Windows 10/11 64-bit
- Python 3.11 or 3.12
- Node.js 20 or 22 LTS
- Google Chrome
- Microsoft Visual C++ Redistributable x64

Notes:
- use the official LTS Node builds, not odd-numbered/preview variants
- internet access helps for package downloads and optional sync/update checks
- once set up, the local board runtime should still be usable without central connectivity

---

## 2. Package layout after unpacking

Typical target path:

```text
C:\DartsKiosk\
```

Expected top-level contents in the Windows bundle:

```text
backend\
frontend\
agent\
central_server\        optional/in-tree, not required for local play
kiosk\                 experimental hard-kiosk helpers
VERSION
check_requirements.bat
setup_windows.bat
setup_profile.bat
start.bat
stop.bat
smoke_test.bat
run_backend.py
credits_overlay.py
README.md
```

Runtime state will be created locally during setup/start, especially:

```text
data\
logs\
.venv\
backend\.env
frontend\.env
```

---

## 3. Step-by-step bring-up

### Step 1 — unpack the Windows package

Example:

```text
Rechtsklick auf darts-kiosk-v4.0.0-recovery-windows.zip -> "Alle extrahieren..."
Ziel: C:\DartsKiosk
```

### Step 2 — run the requirement check

Double-click:

```text
check_requirements.bat
```

This verifies:
- Python
- Node.js
- npm
- VC++ Redistributable hinting

### Step 3 — run the one-time setup

Double-click:

```text
setup_windows.bat
```

What it does:
1. creates runtime directories
2. creates `backend\.env` / `frontend\.env` from examples if missing
3. creates `.venv`
4. installs backend dependencies
5. installs Playwright Chromium
6. installs frontend dependencies via **npm**

### Step 4 — review `backend\.env`

At minimum, check and adjust:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
DATA_DIR=./data
JWT_SECRET=CHANGE-ME
AGENT_SECRET=CHANGE-ME
CORS_ORIGINS=*
MODE=STANDALONE
BOARD_ID=BOARD-1
AUTODARTS_URL=https://play.autodarts.io
AUTODARTS_MODE=observer
AUTODARTS_HEADLESS=false
AUTODARTS_MOCK=false
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL_HOURS=24
GITHUB_REPO=
GITHUB_TOKEN=
```

Important:
- change `JWT_SECRET`
- change `AGENT_SECRET`
- set a correct `BOARD_ID` for the physical board PC
- review the `AUTODARTS_*` values for the actual observer setup
- GitHub update variables are optional

### Step 5 — prepare the persistent Chrome/Autodarts profile

Double-click:

```text
setup_profile.bat
```

Use that profile window to:
- sign into Autodarts if needed
- install required extension(s)
- confirm the intended board/browser state

### Step 6 — start the system

Double-click:

```text
start.bat
```

What it does:
- activates `.venv` if present
- starts the backend watchdog
- starts the Windows agent if present
- starts the credits overlay if present
- opens the kiosk UI in Chrome kiosk mode

### Step 7 — run the smoke test

Double-click:

```text
smoke_test.bat
```

The smoke test checks:
- `/api/health`
- `/api/system/version`
- `/api/boards`
- observer status for the configured `BOARD_ID`

---

## 4. Main local URLs

Assuming default port `8001`:

### On the board PC itself
- Kiosk UI: `http://localhost:8001/kiosk/BOARD_ID`
- Admin UI: `http://localhost:8001/admin`
- Health: `http://localhost:8001/api/health`

### From another device on the LAN
- Kiosk UI: `http://<LAN-IP>:8001/kiosk/BOARD_ID`
- Admin UI: `http://<LAN-IP>:8001/admin`
- Health: `http://<LAN-IP>:8001/api/health`

`start.bat` prints the detected LAN IP during bring-up.

---

## 5. Important runtime facts

- `BOARD_ID` in `backend\.env` controls which board the Windows helpers target.
- Chrome board profile data lives in `data\chrome_profile\<BOARD_ID>`.
- Kiosk UI profile data lives in `data\kiosk_ui_profile`.
- Backend/runtime logs go to `data\logs\app.log`.
- Windows helper/watchdog logs go to the top-level `logs\` folder.
- Local play should not depend on central reachability once the board machine is configured.

---

## 6. Troubleshooting

### Backend does not come up
Check:
- `logs\backend.log`
- `data\logs\app.log`
- whether port `8001` is already in use

Quick check:

```cmd
netstat -an | findstr 8001
```

### Smoke test fails
Check:
- `data\logs\app.log`
- `logs\backend.log`
- whether `BOARD_ID` in `backend\.env` matches an actual board row

### Agent does not respond
Check:
- `data\logs\agent.log`
- whether `AGENT_SECRET` exists in `backend\.env`
- whether the system is running on Windows (many agent functions are Windows-only)

### Autodarts/observer problems
Check:
- Chrome is installed
- the persistent profile was prepared via `setup_profile.bat`
- Playwright Chromium installed successfully during setup
- the observer target and board/login state are valid on the actual machine

### Central/portal surfaces are unavailable
That is not the first thing to debug for a board PC.
First confirm:
- local backend health
- board/admin local access
- observer state
- smoke test status

Optional central connectivity can be debugged afterwards.

---

## 7. Stop / restart

To stop the local services cleanly:

```text
stop.bat
```

Or stop them from the still-open `start.bat` window.

---

## 8. Updates

Preferred path:
- use the admin UI maintenance/update surface
- or replace app files with a newer Windows release bundle while preserving runtime state

Do **not** casually overwrite these during an update:
- `data\`
- `logs\`
- `backend\.env`
- `frontend\.env`
- Chrome profiles under `data\chrome_profile\...`

---

## 9. What still needs real-machine confirmation

This guide reflects the repo/product surface, but the following still need actual machine confirmation:
- Chrome kiosk/focus behavior on the target hardware
- Autodarts login/session stability over real runtime
- shell/device recovery actions on a live Windows machine
- update/rollback behavior using packaged artifacts on the real board PC
