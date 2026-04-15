# Windows board PC quick reference

This folder is the operator-facing entrypoint for a local board machine.

## Fast path

1. `install.bat`
2. Review `backend\.env`
   - set `JWT_SECRET`
   - set `BOARD_ID`
   - review `AUTODARTS_*`
3. `setup_profile.bat`
   - sign into Autodarts in the persistent Chrome profile
   - install the required extension(s)
4. `start.bat`
5. `smoke_test.bat`

Manual path if needed:
- `check_requirements.bat`
- `setup_windows.bat`
- `setup_profile.bat`
- `start.bat`
- `smoke_test.bat`

## What the scripts do

- `setup_windows.bat` — creates `.venv`, installs backend/frontend deps, installs Playwright Chromium
- `install.bat` — one-click board-PC bootstrap (setup + optional autostart + immediate start)
- `setup_profile.bat` — opens the persistent Chrome profile for the board from `backend\.env` (`BOARD_ID`)
- `start.bat` — validates runtime, starts backend + agent, bootstraps Autodarts if configured, then opens the kiosk UI
- `stop.bat` — stops backend/overlay/agent and kills Chrome instances tied to the kiosk or board profile
- `smoke_test.bat` — verifies `/api/health`, `/api/system/version`, `/api/boards`, and observer status for the configured board
- `capture_autodarts.bat` — opens a local Autodarts capture harness and writes JSONL traces to `data\autodarts_capture\...` for debugging lobby / tournament / match lifecycle behavior

## Important runtime facts

- Local play does **not** depend on the central server being reachable.
- `BOARD_ID` in `backend\.env` controls which board profile/UI the Windows scripts use.
- `AGENT_PORT` defaults to `8003`.
- `GITHUB_REPO` defaults to `orri58/darts-kiosk` for built release bundles.
- Chrome profile data lives in `data\chrome_profile\<BOARD_ID>`.
- Kiosk UI profile data lives in `data\kiosk_ui_profile`.
- Logs are written to `data\logs\app.log` and the `logs\` folder used by the Windows helpers.

## Main docs

- `docs/INSTALLATION.md`
- `docs/RUNBOOK.md`
- `docs/STATUS.md`
- `docs/PHASE5_6_IMPLEMENTATION.md`
- `docs/AUTODARTS_CAPTURE.md`
