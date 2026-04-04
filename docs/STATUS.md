# Status

## Executive summary

The repo is in a better product state again:
- Windows bring-up now has a real one-click entry (`release/windows/install.bat`) instead of only a loose collection of helper scripts
- startup/runtime defaults are cleaner: single seeded board, normalized agent health checks, and aligned agent port defaults
- update flow is closer to a product surface: direct install is promoted in the admin UI instead of only exposing package-prep internals
- admin shell and maintenance surfaces are less verbose and wrap more safely on narrow screens
- board-PC readiness / preflight is now surfaced as a real in-product admin view instead of being half-hidden across setup and backend endpoints
- diagnostics and support-bundle contents are now visible in the admin UI before export, so support can see what they are about to collect
- maintenance/device/update surfaces are less self-contradictory: action buttons live in Device Ops, diagnostics live in Health/System, and dead-end duplicate controls were removed
- the active operator flow is now **credits-only**
- palette selection now propagates through a proper frontend theme-token pipeline instead of only touching a few isolated raw vars
- live kiosk/overlay/public surfaces refresh settings so runtime theme changes can actually show up without manual reloads
- dashboard board activation is faster via a new quick-unlock section near the top
- unlock / top-up dialogs and the main admin shell are visibly tighter on both mobile and desktop
- unlock/freischalten no longer asks for player count
- actual credit deduction happens later on authoritative match start, using the real player situation
- time-based and other pricing variants are no longer exposed as first-class operator choices in the main local UI
- stale generated test-report artifacts and old packaging noise were removed from the tracked repo/build surface
- setup / install / maintenance / recovery flows are now more coherent across backend, Windows scripts, and admin UI
- release/build/docs now align better around the current product shape: npm-based frontend packaging on Windows, shared release-script usage in CI, and less misleading central-heavy deployment copy

This is a meaningful cleanup/product pass, not just copy polish.

## Latest pass: installer + update UX + admin professional pass

### What changed in this pass
- added `release/windows/install.bat` as the new one-click Windows bootstrap/install entrypoint
- `setup_windows.bat` now builds the frontend during setup and prepares app-backup/runtime folders
- built Windows env examples now default to `AGENT_PORT=8003` and `GITHUB_REPO=orri58/darts-kiosk`
- agent defaults/docs were aligned on port `8003`
- agent health monitor now normalizes malformed agent URLs and checks the real `/status` endpoint before falling back
- update-service repo parsing now strips a trailing slash so misconfigured `owner/repo/` values do not break GitHub checks
- admin sidebar and page shells were reduced in label/meta noise and improved for text wrapping / responsive overflow
- System → Updates now exposes a direct **Jetzt installieren** path for installable Windows release assets
- startup no longer recreates `BOARD-2`; only the local default board is seeded automatically

### Validation for this pass
Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
cd .. && bash release/build_release.sh
```

Result:
- focused backend validation passed
- frontend production build succeeded
- release artifacts for Windows/Linux/source were generated successfully

## Latest pass: 4.2.0 operator/product pass

### What changed in this pass
- introduced `SessionCharge` booking rows so unlocks and top-ups can be accounted for as real session revenue events
- reports/revenue now include booked top-ups instead of only the initial unlock amount
- split theme direction into `kiosk_theme` and `admin_theme`
- added `kiosk_layout` settings for practical logo/header/lockscreen control
- major kiosk screens now render the configured logo through a shared kiosk header
- dashboard and admin shells were tightened to reduce noise and feel more operator-first on mobile and desktop

### Validation for this pass
Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend agent
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
```

Result:
- backend/agent compile check passed
- focused backend validation passed (37 tests)
- frontend production build succeeded

## Latest pass: 4.4.0 consistency diagnostics + safe repair

### What changed in this pass
- added a dedicated `session_consistency_service` that inspects each board against its latest/active sessions and emits deterministic lifecycle findings
- detects key field-failure states such as:
  - active-looking board without an active session
  - locked board with a still-active stale/terminal session
  - multiple active sessions on one board
  - `blocked_pending` without a matching per-player credit-gate scenario
  - `in_game` boards whose session is already terminal by expiry/capacity
  - finished/expired/cancelled latest sessions where the board never returned to locked
- added admin API endpoints for runtime consistency inspection and safe per-board repair
- safe repair can now normalize common contradictions by:
  - locking orphan-active boards
  - collapsing duplicate active sessions to the newest survivor
  - finalizing stale terminal sessions
  - restoring a wrongly locked board to unlocked when an actually valid active session remains
  - triggering shared terminal cleanup when repair closes a terminal lifecycle state
- expanded Admin Health with a dedicated Session/Board consistency surface, including findings, per-board issue counts, and a one-click safe repair action
- added focused regression tests for detection + repair of the main stale/orphan/duplicate session states

### Validation for this pass
Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_v430_scheduler_terminal_cleanup.py \
  backend/tests/test_v440_session_consistency.py
cd frontend && npm run build
```

Result:
- scheduler terminal cleanup regression suite passed
- new session consistency detection/repair suite passed
- frontend production build succeeded with the new admin diagnostics surface
- live Windows + Autodarts field validation is still the next required step before claiming full recovery proof

## Latest pass: 4.3.1 scheduler terminal cleanup hardening

### What changed in this pass
- extracted shared `run_terminal_session_cleanup(...)` in kiosk lifecycle code so true terminal session endings now use one aligned cleanup path
- session-end finalize now delegates observer close + kiosk restore + websocket refresh semantics to that shared cleanup helper instead of partially duplicating the chain
- scheduler-driven `time_expired` and `idle_timeout` board locks now trigger the same terminal cleanup path after DB commit
- added focused regression tests that verify:
  - expired per-time sessions trigger terminal cleanup exactly once
  - in-game expired sessions still defer cleanup/locking until the game actually ends
  - idle-timeout session cancellation triggers terminal cleanup exactly once
  - scheduler → kiosk import bridge forwards the expected cleanup reason and lock intent

### Validation for this pass
Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q backend/tests/test_v430_scheduler_terminal_cleanup.py
```

Result:
- targeted scheduler terminal-cleanup regression suite passed (`4 passed`)
- confirms scheduler expiry/idle lock flows now align with the shared kiosk terminal cleanup path
- broader live Windows + Autodarts runtime validation is still required before claiming full field proof

## Latest pass: 4.3.0 stability wave 1

### What changed in this pass
- websocket fanout was hardened so one slow/dead client is less likely to stall the whole realtime path
- client websocket transport got reconnect backoff and heartbeat behavior
- server websocket endpoint now understands ping/pong keepalive messages
- SQLite backups now use native snapshotting plus integrity validation instead of raw live-file copies
- restore flow validates backup contents before replacing the live database

### Validation for this pass
Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend
python -m pytest -q \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
```

Result:
- backend compile check passed
- focused backend validation passed
- frontend production build succeeded

It is still **not fully production-proven** until somebody does a real Windows + Autodarts validation pass.

## Latest pass: final hardening + release polish

### What changed in this pass
- Windows release/setup helpers now install frontend dependencies via **npm**, matching the shared release build instead of inventing a separate yarn-only board-PC path
- GitHub release automation now calls the shared `release/build_release.sh` script so CI packaging follows the same artifact/content rules as local releases
- Windows helper output is clearer about the local-first baseline: `start.bat` now foregrounds local kiosk/admin/health URLs and stops advertising optional central surfaces as if they were the main board-PC runtime story
- smoke-test failure output now points operators directly at `data\\logs\\app.log` and `logs\\backend.log`
- Windows agent version/status output now follows the repo `VERSION` file instead of stale hardcoded v3.x strings
- release docs were refreshed to the current product shape (`RELEASE_GUIDE.md`, `release/source/RELEASE_NOTES.md`, `release/windows/MANUAL_DEPLOYMENT.md`, `frontend/README.md`)
- dev docs now consistently use the npm-based frontend path

### Validation for this pass
Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend agent
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
cd .. && bash release/build_release.sh
```

Result:
- backend + agent compile cleanly
- focused backend validation passed (`36 passed`)
- frontend production build succeeds cleanly
- release artifacts were generated successfully in `release/build/`
- live Windows install/update/rollback behavior is still only claimable after real-machine validation

## Latest pass: board-PC readiness + diagnostics surface

### What changed in this pass
- added an authenticated `/api/system/readiness` snapshot focused on what a local board PC actually needs to be usable:
  - setup completion
  - default credential rotation state
  - JWT / agent secrets presence + load state
  - board-id / board-row alignment
  - observer target prerequisites
  - DB path, data/log/backup dirs, VERSION file, frontend build presence
  - Windows Autodarts desktop prerequisite visibility
- added `/api/system/support-snapshot`, mirroring the major support-bundle snapshots in readable JSON for the admin UI
- support bundle export now includes the new `snapshot/readiness.json` so the exported artifact matches the visible diagnostics story
- Health page now opens with a real **Board-PC readiness** surface:
  - blocker/warning summary
  - grouped checks
  - local board identity
  - local URLs / DB path
  - recommended next actions
- System page now treats **Diagnostics** as a first-class surface instead of just a raw log tail:
  - visible support snapshot summary
  - bundle contents preview
  - current log files / screenshot counts / update artifact counts
  - still includes the live log tail, but no longer makes that the only troubleshooting affordance
- Device Ops now keeps the dangerous host controls in one place and surfaces the last action result inline, so success/failure is visible even after the toast disappears
- Host & Dienste was cleaned up into a read-only inventory view; duplicate restart/reboot/autodarts buttons were removed so operators no longer see multiple competing control surfaces for the same thing
- downloaded update assets now make installability explicit (`installierbar` vs `manuell / nicht direkt installierbar`) instead of silently showing a partial action model

### Validation for this pass
Executed successfully:

```bash
python3 -m compileall backend
cd frontend && npm run build
```

Result:
- backend compiles cleanly with the new readiness/support snapshot service
- frontend production build succeeds with the new Health/System/Device Ops surfaces
- no live Windows validation was performed here; real-machine confirmation is still required for shell/device/autodarts recovery claims

## Latest pass: ops / maintenance / installation completion

### What changed in this pass
- added a dedicated **Device Ops** admin surface that finally wires the existing AgentTab into live backend routes
- implemented agent-first backend routes for:
  - agent status
  - Autodarts ensure/restart
  - backend restart
  - Windows reboot/shutdown
  - Explorer ↔ kiosk shell switching
  - Task Manager enable/disable
  - agent autostart register/remove
- kept safe fallback behavior when the Windows agent is offline by reusing existing backend services instead of creating parallel code paths
- first-run setup now exposes lightweight preflight data and local URLs directly in the setup wizard
- admin login now redirects incomplete systems to `/setup` instead of leaving operators to guess the right first-run step
- setup completion now rotates the quick PIN for existing **admin/staff** users, closing the old foot-gun where the seeded admin quick PIN could remain active even after setup
- support bundle export now includes runtime snapshots (system info, health, setup status, agent status, update/download state) in addition to raw logs
- update downloads listing now returns the metadata that the install path actually expects (`filename`, `path`, byte size), fixing the broken handoff between download and install
- DB-aware backup/system info paths now use the configured SQLite file instead of assuming a stale hardcoded default path

### Validation for this pass
Executed successfully:

```bash
python3 -m compileall backend agent
cd frontend && npm run build
```

Result:
- backend + agent sources compile cleanly
- frontend production build succeeds
- focused pytest execution was **not run here** because the host environment lacks `pytest`
- live Windows/Autodarts validation is still required before making strong production claims about shell switching, reboot/shutdown, or scheduled-task autostart on a real board PC

## Latest pass: credits-only unlock cleanup

## Latest pass: responsive polish + palette propagation fix

### Product / UX changes implemented
- dashboard now surfaces locked boards in a dedicated **quick unlock** area above the longer board list
- one-tap default unlock is available for the common operator case
- unlock / extend dialogs were compacted so credits can be changed and confirmed faster
- admin shell spacing, hierarchy, and mobile density were tightened
- settings tabs are denser and more navigable on smaller screens
- palette settings now include a stronger live preview surface
- kiosk locked / setup / in-game / blocked / observer / overlay screens were visually tightened and aligned better with the chosen palette

### Theme runtime fix implemented
- palette selection now feeds both the raw app color variables and the semantic shadcn token set
- this means cards, dialogs, buttons, background shells, and other token-driven surfaces actually react to the selected palette
- SettingsContext now reapplies theme tokens from the active palette instead of only pushing a few hex vars
- live surfaces (`/kiosk`, `/overlay`, `/public`) now refresh settings periodically and on focus/visibility return so runtime palette changes propagate to already-open windows
- `/admin/settings` is intentionally excluded from live polling to avoid overwriting in-progress edits

### Validation for this pass
- frontend production build succeeded
- the historical SetupWizard hook warning from this pass has since been resolved

Executed command:

```bash
cd frontend
npm run build
```

Result:
- build completed successfully
- frontend build is now clean again in the current repo state

---

## Previous pass: credits-only unlock cleanup

### Product decisions implemented
- board unlock now uses a credits-only operator flow
- operator enters credits and unlocks the board
- player count is no longer part of the unlock dialog
- `per_player` remains the active backend mode under the hood, but it now seeds from entered credits instead of player count
- actual deduction happens on authoritative match start using detected/setup player count
- `per_time` and similar pricing complexity were removed from the active admin/kiosk unlock surfaces
- reports now label legacy pricing modes honestly instead of presenting them like current product defaults

### UI surfaces updated
- **Admin dashboard**
  - freischalten dialog simplified to credits + price only
  - no more pricing-mode toggle in the main unlock flow
  - no more player-count field in unlock
  - session cards now describe credits-based vs legacy sessions more honestly
- **Admin settings**
  - pricing tab now presents the current product as credits-only
  - per-time tuning is no longer shown as an active operator choice
  - pricing saves normalize back to `per_player` as the active local mode
- **Kiosk screens**
  - locked screen now explains credits / match-start billing instead of showing time offers
  - setup screen shows credits availability for the active flow
  - in-game screen correctly treats `per_player` as a credits mode instead of falling into the time UI branch
  - result/overlay copy now says credits rather than “games left” where that was misleading
- **Portal surfaces (light cleanup)**
  - remote unlock dialog also follows the credits-only unlock model
  - portal pricing summary now frames the active model as credits / matchstart instead of time-heavy mode switching
- **Reports**
  - current mode is labeled `Credits / Matchstart`
  - old `per_game` / `per_time` entries are explicitly marked legacy

### Backend/runtime changes
- default pricing mode is now `per_player`
- pricing settings sanitize invalid mode → `per_player`
- unlock schema defaults to `per_player` and no longer assumes a player prompt
- `initial_credit_seed()` for `per_player` now uses entered credits when present
- board unlock validates credits/time more explicitly
- remote action poller defaults were aligned with the credits-only model
- unlock sessions can start with `players_count = 0` until real setup/match data exists

## What is currently validated

Validated in-process with the focused backend subset:
- credits-only unlock creates an active `per_player` session seeded from entered credits
- unlock no longer requires a player-count prompt to create the session
- kiosk setup still records player names/count for the current session
- authoritative start deducts the actual player count from the credit seed
- insufficient credits still enter `blocked_pending` safely
- authoritative finish still handles legacy `per_game` correctly
- assistive finish hints do not consume `per_game` credits
- abort-before-start does not consume `per_player` capacity
- keep-alive vs teardown still follows remaining capacity
- revenue summary still excludes active sessions and tolerates nullable sale totals

## What was actually run

Executed commands:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
```

Result:
- `34 passed`

And:

```bash
cd frontend
npm run build
```

Result:
- production build completed successfully
- current frontend production builds are now expected to complete without that older SetupWizard warning

## Repo/build-surface cleanup done in this pass

Cleaned up:
- tracked historical files under `test_reports/` (generated snapshots / XML outputs)
- stale generated file `release/build/requirements-core.txt`
- stale version-pinned doc `release/INSTALL_GUIDE_v345.md`
- broken/noisy root `.gitignore` replaced with a clean deterministic version
- new `.dockerignore` added so local build context stops dragging along runtime/build/test clutter

This is intentionally conservative cleanup:
- remove misleading generated artifacts and packaging noise
- keep the working local-core codebase intact
- avoid aggressive deletion of potentially useful implementation history

## What is only partially validated

Still only partly proven here:
- real Windows board-PC operator flow with the new copy/order of actions
- live Autodarts sessions and reconnect behavior over long runtimes
- touch-first operator usage on actual kiosk/admin devices
- whether every optional central/licensing surface now feels equally current

## What still needs live validation before strong production claims

Minimum live checklist:
1. real Windows machine install via `release/windows/setup_windows.bat`
2. real Autodarts login/profile prep via `release/windows/setup_profile.bat`
3. successful `start.bat` + `smoke_test.bat`
4. real credits-only unlock on the target board
5. real authoritative match start observed with correct player-count deduction
6. real blocked-pending recovery via staff top-up
7. real authoritative finish observed
8. one keep-alive case with credits remaining
9. one session-end case with credits exhausted
10. restart/recovery behavior after a stop/start cycle

## Production-readiness statement

### Production-ready enough for
- developer handoff
- continued local-core stabilization work
- code review / maintenance by an external engineer
- controlled lab validation of backend behavior
- preparing a real board-PC validation pass

### Not yet proven enough for
- blanket “deploy everywhere” claims
- unattended venue rollout without a real-machine validation pass
- claiming long-running Autodarts/Windows reliability from repo tests alone

## Current recommendation

The next highest-value step is now a **real-machine operator validation pass**, not another abstract pricing redesign.

Specifically:
- run the new credits-only unlock flow on a real Windows board PC
- observe one real match start with 1 player and one with multiple players
- verify blocked-pending + top-up behavior in the field
- capture logs/screenshots while doing it

That is the remaining gap between “clean repo/product surface” and “credible production claim.”
