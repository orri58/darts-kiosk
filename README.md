# Darts Kiosk

Local-first darts board control and kiosk software for venue operation.

Current product release line: **v4.1.0**

The current repo state is centered on a **protected local core**:
- local auth, boards, sessions, settings, admin UI
- observer-first Autodarts integration via Playwright/Chrome
- pricing / credits / session lifecycle in local SQLite
- local WebSocket updates with polling fallback
- Windows operator scripts for bring-up and smoke checks

There is also an **optional central adapter ring** in the tree, but it is **not required** for local play and is **not the production baseline validated in this repo**.

## Current reality

What is in good shape now:
- one-click Windows bring-up via `release/windows/install.bat`
- board unlock / lock flow
- local session persistence
- authoritative match start/finish handling for the protected local core
- credits-only unlock flow for the active operator surface
- authoritative per-player credit deduction based on the real match/player situation
- legacy-compatible per-game and per-time capacity rules in backend logic
- local revenue summary from recorded session sale totals
- Windows setup/start/stop/smoke helper scripts
- focused in-process backend validation for the local core

What is **not** fully proven here:
- a real Windows board PC end-to-end run
- live Autodarts login/session stability over long runtimes
- Chrome/window-focus behavior on a physical kiosk machine
- full operator UX around every optional or legacy surface still present in the repo

Short version: the repo is now understandable, testable, and honest about its boundaries, but it still needs **real-machine validation** before anyone calls it done.

## Architecture in one paragraph

A staff/admin user unlocks a board by adding credits, which creates a local `Session` row and moves the board to `unlocked`. In observer mode, the backend launches a persistent Chrome/Playwright observer against the configured Autodarts URL. Authoritative WebSocket signals drive `_on_game_started()` and `finalize_match()`, which update board/session state, deduct the correct credit amount from the real match/player situation, decide whether the session stays alive or locks, and coordinate kiosk/observer UI behavior. Settings, reporting, and revenue all read from the local database; central outages are supposed to stay non-fatal to local play.

More detail:
- `docs/ARCHITECTURE.md`
- `docs/ANALYSIS.md`
- `docs/CREDITS_PRICING.md`
- `docs/RUNBOOK.md`
- `docs/TESTING.md`
- `docs/STATUS.md`

## Repository layout

```text
backend/            FastAPI app, models, routers, services, tests
frontend/           React admin + kiosk UI
release/windows/    Windows setup/start/stop/smoke scripts
scripts/            Helper scripts, including local smoke tooling
docs/               Architecture, analysis, status, runbook, testing notes
central_server/     Central-side code and experiments (not local-core baseline)
```

## Protected local-core modules

These are the modules to treat as the real product spine:
- `backend/server.py`
- `backend/models/__init__.py`
- `backend/database.py`
- `backend/dependencies.py`
- `backend/runtime_features.py`
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/routers/settings.py`
- `backend/routers/admin.py`
- `backend/services/session_pricing.py`
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`
- `backend/services/scheduler.py`
- `frontend/src/pages/kiosk/*`
- `frontend/src/pages/admin/*`
- `frontend/src/context/*`

If you change behavior there, update tests and docs in the same branch.

## Developer quick start

### Backend

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.server:app --reload --port 8001
```

Notes:
- run `uvicorn` from the **repo root**, not from inside `backend/`
- review `backend/.env` for local settings when using a real runtime
- default local URLs assume port `8001`

### Frontend

```bash
cd frontend
npm ci
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

### Local URLs

- API root: `http://localhost:8001/api`
- Health: `http://localhost:8001/api/health`
- Admin UI: `http://localhost:8001/admin`
- Kiosk UI: `http://localhost:8001/kiosk/BOARD-1`
- Observer status: `http://localhost:8001/api/kiosk/BOARD-1/observer-status`

## Windows operator path

For a real board PC, the intended operator flow is via:
- `release/windows/install.bat`
- `release/windows/check_requirements.bat`
- `release/windows/setup_windows.bat`
- `release/windows/setup_profile.bat`
- `release/windows/start.bat`
- `release/windows/stop.bat`
- `release/windows/smoke_test.bat`

See:
- `docs/RUNBOOK.md`
- `docs/STATUS.md`
- `release/windows/README.md`

## Testing

The current authoritative local-core subset is:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
```

This validates:
- Autodarts trigger classification boundaries
- credits-only unlock seeding + pricing / credit consumption rules
- optional adapter-service startup hardening
- board unlock / lock
- session lifecycle transitions
- authoritative start/finish handling
- revenue summary behavior for local accounting

It does **not** replace live Windows / Autodarts verification.

## Documentation index

- `docs/ARCHITECTURE.md` — current runtime structure and source-of-truth modules
- `docs/ANALYSIS.md` — synthesis of baseline, local-core, and Autodarts analysis
- `docs/AUTODARTS_ANALYSIS.md` — detailed observer/trigger evidence
- `docs/CREDITS_PRICING.md` — billing and capacity semantics
- `docs/RUNBOOK.md` — operator actions and troubleshooting
- `docs/STATUS.md` — what is validated, what is risky, what is pending
- `docs/TESTING.md` — test strategy and exact commands
- `CONTRIBUTING.md` — contribution expectations for the protected local core
- `FINAL_REPORT.md` — final phase 7/8/9 wrap-up

## Known limits / honesty section

Please do not overread the current state.

This repo is **not yet proven** as a finished production deployment because the missing evidence is outside this sandbox:
- no physical Windows kiosk validation pass
- no live Autodarts session exercised here
- no proof of long-running observer resilience on a venue machine

What this repo now provides is a coherent, documented, locally testable baseline that an external developer or operator can actually understand and continue from without guesswork or archaeology.
