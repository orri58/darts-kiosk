# Windows board PC quick reference

This folder is the operator-facing entrypoint for a local board machine.

## Fast path

1. `check_requirements.bat`
2. `setup_windows.bat`
3. Edit `backend\.env`
   - set `JWT_SECRET`
   - set `BOARD_ID`
   - review `AUTODARTS_*`
4. `setup_profile.bat`
   - sign into Autodarts in the persistent Chrome profile
   - install the required extension(s)
5. `start.bat`
6. `smoke_test.bat`

## What the scripts do

- `setup_windows.bat` — creates `.venv`, installs backend/frontend deps, installs Playwright Chromium
- `setup_profile.bat` — opens the persistent Chrome profile for the board from `backend\.env` (`BOARD_ID`)
- `start.bat` — starts backend, optional agent, overlay, then opens the kiosk UI for the configured board
- `stop.bat` — stops backend/overlay/agent and kills Chrome instances tied to the kiosk or board profile
- `smoke_test.bat` — verifies `/api/health`, `/api/system/version`, `/api/boards`, and observer status for the configured board

## Important runtime facts

- Local play does **not** depend on the central server being reachable.
- `BOARD_ID` in `backend\.env` controls which board profile/UI the Windows scripts use.
- Chrome profile data lives in `data\chrome_profile\<BOARD_ID>`.
- Kiosk UI profile data lives in `data\kiosk_ui_profile`.
- Logs are written to `data\logs\app.log` and the `logs\` folder used by the Windows helpers.

## Main docs

- `docs/INSTALLATION.md`
- `docs/RUNBOOK.md`
- `docs/STATUS.md`
- `docs/PHASE5_6_IMPLEMENTATION.md`
