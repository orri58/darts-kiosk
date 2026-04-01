# Baseline Analysis (repo @ `cef9724`)

## Scope and evidence

Analyzed from git history, runtime wiring, and test files in this repository.

Key commits:

| Commit | Date (UTC) | Evidence |
|---|---:|---|
| `77887ee` | 2026-03-18 20:00 | Last stable pre-central local-core reference named in `docs/RECOVERY.md` |
| `15202ae` | 2026-03-19 15:11 | Licensing stack introduced: `backend/models/licensing.py`, `backend/routers/licensing.py`, `backend/services/license_service.py`, `frontend/src/pages/admin/Licensing.js`, `backend/tests/test_v341_licensing.py` |
| `9ed21c6` | 2026-03-19 18:09 | Central server introduced: `central_server/server.py`, `backend/tests/test_v350_central_sync.py` |
| `2c4c5c5` | 2026-03-19 19:47 | Central proxy + portal/operator UI introduced: `backend/routers/central_proxy.py`, `frontend/src/context/CentralAuthContext.js`, `backend/tests/test_v353_operator_portal.py` |
| `a7897f0` | 2026-03-25 08:16 | Recovery reset commit: baseline test `backend/tests/test_v400_recovery_baseline.py`; large removals/reverts in `backend/server.py`, `backend/routers/*`, `frontend/src/App.js` |
| `aa64ca6` | 2026-03-25 08:36 | Layer A reintroduced: `backend/integrations/layer_a.py`, `backend/services/central_heartbeat_client.py`, `backend/tests/test_layer_a_integration.py`; `backend/server.py` and `frontend/src/App.js` rewired |
| `cef9724` | 2026-03-25 08:37 | Current HEAD; docs/status update only |

Two hard facts from the tree:

1. The runtime local core is still the `77887ee` code for nearly all core files.
   - Verified unchanged from `77887ee..cef9724`: `backend/database.py`, `backend/models/__init__.py`, `backend/dependencies.py`, `backend/schemas.py`, routers `auth.py`, `boards.py`, `kiosk.py`, `settings.py`, `admin.py`, `backups.py`, `updates.py`, `agent.py`, `discovery.py`, `matches.py`, `stats.py`, `players.py`, and services `autodarts_observer.py`, `ws_manager.py`, `scheduler.py`, `backup_service.py`, `health_monitor.py`, `mdns_service.py`, `sound_generator.py`, `system_service.py`, `update_service.py`, `setup_wizard.py`, `watchdog_service.py`.
2. The only active post-recovery runtime coupling added after the reset is Layer A glue.
   - `backend/server.py`: starts/stops Layer A heartbeat and includes `central_proxy.router`.
   - `frontend/src/App.js`: adds `/portal` routes and `CentralAuthProvider`.

---

## 1) Current architecture map

### A. Local device runtime (active)

**Frontend (`frontend/src`)**
- `App.js` currently mounts three surfaces:
  - `/kiosk` → kiosk UI (`pages/kiosk/*`)
  - `/admin` → local admin UI (`pages/admin/*`)
  - `/portal` → central visibility UI (`pages/portal/PortalLogin.js`, `PortalLayout.js`, `PortalDashboard.js`, `PortalDevices.js`)
- Local contexts are still the baseline set:
  - `context/AuthContext.js`
  - `context/SettingsContext.js`
  - `context/I18nContext.js`
- Central visibility adds one separate context:
  - `context/CentralAuthContext.js`

**Backend (`backend/server.py`)**
- Startup lifecycle still initializes local services first:
  - DB init (`init_db`)
  - scheduler (`services/scheduler.py`)
  - backup service (`services/backup_service.py`)
  - health monitor (`services/health_monitor.py`)
  - mDNS (`services/mdns_service.py`)
  - update checker (`services/update_service.py`)
  - watchdog (`services/watchdog_service.py`)
- Active API routers:
  - local core: `auth`, `boards`, `kiosk`, `settings`, `admin`, `backups`, `updates`, `agent`, `discovery`, `matches`, `stats`, `players`
  - Layer A only: `central_proxy`
- Local persistence and domain model stay in:
  - `backend/database.py`
  - `backend/models/__init__.py`
- Local realtime/game orchestration stays in:
  - `backend/services/autodarts_observer.py`
  - `backend/services/ws_manager.py`
  - `backend/services/sound_generator.py`

**Local-first data/control path**
- Admin auth → `routers/auth.py`
- Board unlock/lock/session lifecycle → `routers/boards.py`
- Kiosk state machine/game finalize/observer endpoints → `routers/kiosk.py`
- Branding/pricing/language/sound/etc. → `routers/settings.py`
- Revenue/logs/reports/health/system → `routers/admin.py`
- WebSocket board updates → `services/ws_manager.py`
- Autodarts automation → `services/autodarts_observer.py`

### B. Central / licensing stack on disk (mostly dormant)

**Device-side central/licensing code present on disk**
- `backend/models/licensing.py`
- `backend/routers/licensing.py`
- `backend/services/license_service.py`
- `backend/services/license_sync_client.py`
- `backend/services/device_registration_client.py`
- `backend/services/config_sync_client.py`
- `backend/services/action_poller.py`
- `backend/services/telemetry_sync_client.py`
- `backend/services/ws_push_client.py`
- related support files: `audit_log_service.py`, `offline_queue.py`, `device_identity_service.py`, `config_apply.py`, `cyclic_license_checker.py`, `central_rejection_handler.py`

**Central server is a separate backend, not a shared module**
- `central_server/server.py`
- `central_server/database.py`
- `central_server/models.py`
- `central_server/auth.py`
- There are no `central_server -> backend` imports. It is a separate FastAPI app with its own DB/auth/RBAC.

**Current active Layer A adapter**
- `backend/integrations/layer_a.py`
- `backend/services/central_heartbeat_client.py`
- `backend/routers/central_proxy.py`
- `frontend/src/context/CentralAuthContext.js`
- portal pages listed above

### C. What is wired vs merely present

**Wired at HEAD (`cef9724`)**
- Layer A heartbeat startup/shutdown in `backend/server.py`
- `/api/central/*` proxy in `backend/routers/central_proxy.py`
- `/portal` routes in `frontend/src/App.js`

**Present but not wired into current runtime**
- `backend/routers/licensing.py` is not included by `backend/server.py`
- `frontend/src/pages/admin/Licensing.js` is not routed in `App.js`
- `frontend/src/pages/admin/OnboardingWizard.js` is not routed in `App.js`
- `frontend/src/pages/operator/*` are on disk but not routed in `App.js`
- `central_server/*` is not started by `docker-compose.yml`

---

## 2) Stable local-core modules that must be protected

These are the baseline modules that survived the recovery and remained unchanged from `77887ee` to `cef9724`.

### Backend core
- Persistence/contracts:
  - `backend/database.py`
  - `backend/models/__init__.py`
  - `backend/dependencies.py`
  - `backend/schemas.py`
- Local API routers:
  - `backend/routers/auth.py`
  - `backend/routers/boards.py`
  - `backend/routers/kiosk.py`
  - `backend/routers/settings.py`
  - `backend/routers/admin.py`
  - `backend/routers/backups.py`
  - `backend/routers/updates.py`
  - `backend/routers/agent.py`
  - `backend/routers/discovery.py`
  - `backend/routers/matches.py`
  - `backend/routers/stats.py`
  - `backend/routers/players.py`
- Local services:
  - `backend/services/autodarts_observer.py`
  - `backend/services/ws_manager.py`
  - `backend/services/scheduler.py`
  - `backend/services/backup_service.py`
  - `backend/services/health_monitor.py`
  - `backend/services/mdns_service.py`
  - `backend/services/sound_generator.py`
  - `backend/services/system_service.py`
  - `backend/services/update_service.py`
  - `backend/services/setup_wizard.py`
  - `backend/services/watchdog_service.py`

### Frontend core
Verified unchanged representatives in the recovered UI:
- `frontend/src/context/AuthContext.js`
- `frontend/src/context/SettingsContext.js`
- `frontend/src/context/I18nContext.js`
- `frontend/src/pages/admin/Dashboard.js`
- `frontend/src/pages/admin/Boards.js`
- `frontend/src/pages/admin/Settings.js`
- `frontend/src/pages/kiosk/KioskLayout.js`

### Local-first invariants that these modules enforce

1. **Board/session control is local.**
   - `boards.py` and `kiosk.py` do not import the licensing stack.
   - Unlock/lock/finalize flows operate on local DB state and local observer state.
2. **Admin auth is local.**
   - `auth.py` uses local users/JWT; it is not delegated to central auth.
3. **Kiosk rendering depends on local state + local websocket only.**
   - `ws_manager.py` is still the local event fanout path.
4. **Revenue/settings/reporting are local SQLite responsibilities.**
   - `admin.py` and `settings.py` remain baseline code.
5. **Central outage must not block local operation.**
   - Current Layer A heartbeat explicitly self-disables if `CENTRAL_SERVER_URL` or `CENTRAL_API_KEY` is unset, and catches send failures without touching local board flow.

### Test evidence for the protected baseline
- `backend/tests/test_v400_recovery_baseline.py`
  - recovery acceptance test for health, auth, boards, settings, revenue, observer status.
- `backend/tests/test_layer_a_integration.py`
  - tests 1-5 explicitly re-check local auth, boards, and settings before Layer A portal assertions.

Authoritative current acceptance boundary in this repo is therefore:
- baseline local core = `test_v400_recovery_baseline.py`
- additive Layer A only = `test_layer_a_integration.py`

---

## 3) Regression suspects and coupling points

### A. Historical regression window is narrow and identifiable

The unstable expansion started immediately after the stable baseline:
- `15202ae` → licensing enters the device runtime
- `9ed21c6` → central server enters the repo
- `2c4c5c5` → central proxy + portal/operator UI enter the frontend/backend boundary
- `4263212`, `4986d5e`, `cc2ed81`, `3f8d89f` → telemetry, config sync, action poller, WS push expand the coupling surface further

This matches `docs/RECOVERY.md`: regressions are tied to licensing/central/portal work, not the local board/kiosk core.

### B. Current source-of-truth drift

These files disagree with the actual runtime at `cef9724`:
- `README.md` says central/portal is disabled and `App.js` routes are “admin + kiosk only”
- `docs/ARCHITECTURE.md`, `docs/RECOVERY.md`, `docs/STATUS.md` describe central as disabled / not active
- header in `backend/tests/test_v400_recovery_baseline.py` says all central/licensing/portal features were removed
- actual code in `backend/server.py` and `frontend/src/App.js` wires Layer A today

This is not cosmetic drift. It makes recovery boundaries ambiguous.

### C. Runtime seam where central can leak into core

Post-recovery, the only core files changed are:
- `backend/server.py`
- `frontend/src/App.js`

Those two files are the active coupling seam between local core and central add-ons.

Risk:
- any future central/licensing reactivation will almost certainly land here first
- both files are listed as frozen in `CONTRIBUTING.md`, but they were already modified for Layer A

### D. Dormant licensing stack still carries policy contradictions

`backend/services/license_service.py` states “FAIL-CLOSED policy” but still allows `no_license` in `ALLOWED_STATES` and documents “no_license: ALLOWED`. Historical tests reinforce that older behavior:
- `backend/tests/test_v343_device_binding.py`
- `backend/tests/test_v343_device_binding_e2e.py`

That is a direct mismatch with current recovery docs and `CONTRIBUTING.md`, which say failed checks must block.

Conclusion: the licensing stack is not safe to re-enable as-is, even if it is currently isolated.

### E. Portal/operator surface is stale relative to current central RBAC

Current central server RBAC in `central_server/server.py` / `central_server/auth.py` is:
- `superadmin > installer > owner > staff`
- includes migration from legacy `operator` to `installer`

But the repo still contains legacy operator assets/tests:
- `frontend/src/pages/operator/*`
- `backend/tests/test_v353_operator_portal.py` uses `operator1`

That surface is stale. Treat it as historical residue, not a valid baseline.

### F. Deployment and ops artifacts still assume central exists

Evidence:
- `docker-compose.yml` injects `CENTRAL_SERVER_URL` into the app container but does not define a `central_server` service
- `release/windows/start.bat` reads `CENTRAL_SERVER_URL`
- `deploy_server.sh` health-checks `http://localhost:8002/api/health` and prints “Betreiber-Portal” URLs

This is operational coupling, not just code coupling. It can reintroduce “central is expected” assumptions into otherwise local deployments.

### G. Safe separation that should be preserved

Two separations are good and should remain:
- `central_server/*` is process-separated from `backend/*`
- licensing models are not imported into `backend/models/__init__.py`

That separation is the main reason the recovery succeeded.

---

## 4) Recommended freeze line / recovery path

### Freeze line

Use **two references, for two different purposes**:

1. **Historical stable local-core source:** `77887ee`
   - last pre-licensing/pre-central commit
   - use this as the canonical source for “what local-first means”

2. **Practical recovery anchor in current branch:** `a7897f0`
   - this is the recovery reset commit that restored the baseline and added `backend/tests/test_v400_recovery_baseline.py`
   - `a7897f0..cef9724` contains only docs/PRD plus Layer A portal/heartbeat additions

### Recommended operating stance

**If the goal is the safest local-only product:**
- freeze on `a7897f0`
- do not ship `aa64ca6` Layer A runtime hooks
- optionally keep docs from `75ee5c8`/`cef9724` after reconciling them with actual runtime

**If the goal is to keep the current HEAD (`cef9724`):**
- treat Layer A as the only allowed extension
- freeze everything listed in section 2
- restrict central-related changes to this adapter ring only:
  - `backend/integrations/layer_a.py`
  - `backend/services/central_heartbeat_client.py`
  - `backend/routers/central_proxy.py`
  - `frontend/src/context/CentralAuthContext.js`
  - `frontend/src/pages/portal/PortalLogin.js`
  - `frontend/src/pages/portal/PortalLayout.js`
  - `frontend/src/pages/portal/PortalDashboard.js`
  - `frontend/src/pages/portal/PortalDevices.js`
  - minimal glue in `backend/server.py` and `frontend/src/App.js`

### Recovery path from current tree

1. **Lock the baseline definition.**
   - baseline local core = section 2 files + `backend/tests/test_v400_recovery_baseline.py`
2. **Resolve source-of-truth drift immediately.**
   - either revert Layer A (`aa64ca6`) or update `README.md`, `docs/ARCHITECTURE.md`, `docs/RECOVERY.md`, `docs/STATUS.md`, and `test_v400_recovery_baseline.py` headers to state that Layer A is active
3. **Keep licensing/central control features dark.**
   - do not include `backend/routers/licensing.py`
   - do not route `frontend/src/pages/admin/Licensing.js`, `admin/OnboardingWizard.js`, or `frontend/src/pages/operator/*`
   - do not wire `action_poller.py`, `config_sync_client.py`, `telemetry_sync_client.py`, `ws_push_client.py`
4. **Before any Layer B work, clean policy drift first.**
   - remove fail-open `no_license` behavior if fail-closed is the rule
   - retire legacy `operator` UI/tests or align them to `installer`
   - make deployment scripts consistent with whether central is optional or provisioned
5. **Protect with tests, not memory.**
   - keep `test_v400_recovery_baseline.py` green as the non-negotiable gate
   - keep `test_layer_a_integration.py` only if Layer A remains in scope
   - treat `test_v341_*` through `test_v394_*` as historical evidence, not release gates, until each area is deliberately recovered

### Bottom line

- **Stable local-core baseline:** `77887ee` (materialized again by `a7897f0`)
- **Current runtime state:** recovered local core + limited Layer A wiring at `cef9724`
- **Main regression cluster:** licensing + central server + portal/operator + sync/control expansion introduced after `77887ee`
- **Main protection rule:** no central/licensing logic may re-enter local board/auth/kiosk/settings/admin flows; only adapter-style additions around the edge are acceptable
