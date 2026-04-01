# LOCAL CORE AUDIT

Repo state audited: `cef9724`

Scope: **local core only** — board lock/unlock, kiosk flow, session lifecycle, pricing/credits, revenue/accounting, local settings, offline/local-only behavior.

This audit is based on the current runtime wiring, not the older recovery docs alone. Several docs/tests in the repo still describe a cleaner split than the code actually enforces.

---

## 0. Executive read

The **working local core is real**, but it is narrower than the current UI/API surface suggests.

### The real stable core
- local auth + board/session persistence
- admin unlock/lock/extend
- **observer-first** kiosk flow
- centralized `finalize_match()` logic for per-game / per-time sessions
- local settings in SQLite-backed JSON
- local revenue based on `Session.price_total`
- local WS + polling fallback
- central/portal outages do **not** block local play

### What looks core but is actually shaky
- manual/setup-mode kiosk flow
- `per_player` pricing lifecycle
- call-staff flow
- match-sharing/result QR in keep-alive sessions
- reporting/accounting consistency
- “offline” status semantics
- old tests/docs that still describe removed or half-removed behavior

### Short verdict
If you want to preserve the currently working local product, freeze around the **observer-based local session flow** and treat everything else as adapter/overlay until re-proven.

---

## 1. Flow map

## 1.1 Boot/runtime flow

### Backend startup
Primary runtime entry: `backend/server.py`

Startup does the following:
1. initializes DB via `backend/database.py`
2. creates default users/boards/settings if missing
3. starts local background services:
   - `services/scheduler.py`
   - `services/backup_service.py`
   - `services/health_monitor.py`
   - `services/mdns_service.py`
   - `services/update_service.py`
   - `services/watchdog_service.py`
4. starts Layer A heartbeat via `backend/integrations/layer_a.py`
5. mounts routers under `/api`
6. exposes local WS at `/api/ws/boards`

### Important startup fact
Fresh startup seeds `BOARD-1` and `BOARD-2` **without** `autodarts_target_url`. Since runtime default is `AUTODARTS_MODE=observer`, a fresh install can unlock a board into an observer-first kiosk flow that has no target URL to open.

---

## 1.2 Board unlock / active session creation

### Admin path
Frontend:
- `frontend/src/pages/admin/Dashboard.js`

Backend:
- `backend/routers/boards.py` → `POST /boards/{board_id}/unlock`

Flow:
1. admin picks mode/credits/minutes/players in dashboard
2. backend creates a `Session` row
3. board status becomes `unlocked`
4. WS broadcast emits `board_status=unlocked`
5. if board has `autodarts_target_url`, observer startup is triggered

### Persisted state created on unlock
Model: `backend/models/__init__.py`
- `Session.pricing_mode`
- `credits_total` / `credits_remaining`
- `minutes_total` / `expires_at`
- `price_total`
- `players_count`
- `status=active`

### Must-preserve behavior here
- unlock is **local DB-first**
- session exists before observer/browser side effects
- central services are not required for unlock

---

## 1.3 Kiosk screen-state flow

Primary frontend state machine:
- `frontend/src/pages/kiosk/KioskLayout.js`

Primary read model:
- `GET /api/boards/{board_id}/session` in `backend/routers/boards.py`

Kiosk chooses screen from:
- `board_status`
- `autodarts_mode`
- observer status fields
- active session payload

### Effective current flow

#### A. Locked
- `board.status=locked`
- screen: `LockedScreen`

#### B. Observer-active path (current real core)
- if `AUTODARTS_MODE=observer` and board is `unlocked` or `in_game`
- screen: `ObserverActiveScreen`
- real gameplay is expected to happen in Autodarts, not in the kiosk browser UI

#### C. Setup / In-game path (legacy-looking path, not authoritative today)
- `SetupScreen` / `InGameScreen` still exist
- `start-game` writes players/game_type to session
- but actual `board.status=in_game` comes from observer callback `_on_game_started()`
- without observer, this path has no authoritative backend transition to `in_game`

#### D. Finished / result QR
- `handleEndGame()` calls `/api/kiosk/{board_id}/end-game`
- if `match_token` exists, kiosk shows `MatchResultScreen`
- if `should_lock`, kiosk returns to locked
- else it returns to observer/setup flow

### Realtime model
- push: `backend/services/ws_manager.py`
- pull fallback: polling in `KioskLayout.js`

This mixed model is good and should be kept.

---

## 1.4 Observer-driven session lifecycle

Primary lifecycle authority:
- `backend/routers/kiosk.py`
  - `_on_game_started()`
  - `_on_game_ended()`
  - `_finalize_match_inner()`
  - `finalize_match()`

### Current authoritative game-end logic
`finalize_match()` is the real center of the local core.

It currently handles:
- idempotency / duplicate-finalize protection
- credit deduction policy
- keep-alive vs lock decision
- match-result creation
- player stat increments
- observer teardown when session truly ends
- kiosk UI restoration when session ends
- WS event fanout
- timeout recovery

### Effective rules

#### Per-game
- deduct one credit on `finished`, `manual`, `aborted`, and match-end/abort triggers
- keep board alive if credits remain
- lock board when credits hit zero

#### Per-time
- no per-game credit deduction
- lock when `expires_at` has passed
- if not expired, session can continue after a game

#### Manual lock
- `POST /boards/{board_id}/lock`
- cancels active session immediately
- forces board to locked
- closes observer

### Must-preserve behavior here
- **deduct credit exactly once per finished match**
- **keep observer alive when credits remain**
- **restore kiosk UI only on true session end**
- **timeout recovery fails safe toward locked**, not hung

---

## 1.5 Pricing / credits / extension flow

Primary backend modules:
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/models/__init__.py`

Primary admin UI:
- `frontend/src/pages/admin/Dashboard.js`

### Supported-in-practice modes

#### `per_game`
This is the strongest mode in the current local core.
- unlock seeds credits
- finalize deducts exactly one credit
- overlay + WS `credit_update` support it
- keep-alive branch is built around it

#### `per_time`
Mostly works.
- unlock sets `expires_at`
- scheduler can auto-expire idle/unlocked sessions
- finalize checks expiry after a game

#### `per_player`
Exposed in UI/settings, but **not truly implemented as a lifecycle mode**.
- unlock can create such sessions
- finalize does not consume or resolve it
- scheduler does not end it
- accounting treats it like a normal sold session, but lifecycle does not

This is an unstable overlay, not a proven core mode.

---

## 1.6 Revenue / accounting flow

Primary backend modules:
- `backend/routers/admin.py`

Endpoints:
- `/revenue/summary`
- `/reports/sessions`
- `/reports/sessions/csv`

### Effective accounting model today
Revenue is derived from `Session.price_total`, i.e. **booking-at-unlock**, not from a separate payments ledger and not from actual usage consumed.

That means:
- manual lock/cancelled sessions still count toward revenue
- extensions affect session quantity/time/credits, but there is no dedicated payment ledger
- “revenue” is really “session sale totals recorded on the session row”

This can be okay, but it needs to be made explicit and kept consistent.

---

## 1.7 Local settings flow

Primary backend source:
- `backend/routers/settings.py`
- defaults in `backend/models/__init__.py`
- helper in `backend/dependencies.py` (`get_or_create_setting`)

Primary frontend source:
- `frontend/src/context/SettingsContext.js`
- admin editor: `frontend/src/pages/admin/Settings.js`

### Effective behavior
- settings are stored as JSON blobs in `settings.value`
- missing keys are lazily created from defaults
- frontend also ships with fallback defaults, so kiosk/admin can still render with backend/settings failures

This local-first settings model is part of the working core and worth preserving.

---

## 1.8 Offline / degraded behavior

### What is genuinely resilient
- central heartbeat/proxy failures do not stop local board/session logic
- kiosk/admin both have polling paths in addition to WS
- settings context has frontend defaults
- observer finalize has timeout recovery

### What is weak
- there is no strong local “board offline” state machine in the core flow
- `BoardStatus.OFFLINE` exists in the model but is not a strong active transition in the local lifecycle
- kiosk fetch failures mostly collapse to locked/default behavior rather than a true degraded/offline UX

---

## 2. Source-of-truth modules

## 2.1 Must-preserve local core modules

| Domain | Primary source of truth | Secondary/UI source | Why it matters |
|---|---|---|---|
| DB/session primitives | `backend/models/__init__.py` | `backend/schemas.py` | Canonical board/session/settings shapes |
| DB/session access | `backend/database.py`, `backend/dependencies.py` | — | Transaction boundaries and `get_active_session_for_board()` |
| Unlock/lock/extend | `backend/routers/boards.py` | `frontend/src/pages/admin/Dashboard.js` | Admin cash-desk control path |
| Observer/game lifecycle | `backend/routers/kiosk.py` | `frontend/src/pages/kiosk/KioskLayout.js`, `ObserverActiveScreen.js` | Real local gameplay control path |
| Observer runtime | `backend/services/autodarts_observer.py` | watchdog/window manager services | Autodarts launch, match event detection |
| Realtime local events | `backend/services/ws_manager.py` | `frontend/src/hooks/useBoardWS.js` | Non-blocking board/session UI updates |
| Background expiry/idle | `backend/services/scheduler.py` | kiosk/admin polling | Auto-expire safety net |
| Settings defaults/storage | `backend/models/__init__.py`, `backend/routers/settings.py` | `frontend/src/context/SettingsContext.js` | Local-first configuration |
| Revenue/report export | `backend/routers/admin.py` | `frontend/src/pages/admin/Revenue.js`, `Reports.js` | Accounting view over session rows |
| Runtime composition | `backend/server.py` | `frontend/src/App.js` | Defines what is truly active |

## 2.2 Must-preserve behaviors

These behaviors are the local core contract worth protecting during cleanup:

1. **Unlock is local and immediate**
   - no central dependency
   - session row is created before observer side effects

2. **Observer flow is authoritative**
   - board enters `in_game` from observer callback, not from kiosk optimism alone

3. **Finalization is centralized**
   - one place decides credit deduction, keep-alive, lock, observer teardown, and UI restoration

4. **Per-game keep-alive is intentional**
   - if credits remain, board should stay playable without a full teardown

5. **Central failures are non-fatal**
   - Layer A may fail, but local core keeps running

6. **Settings are local-first**
   - default config exists even before customization

## 2.3 Unstable overlays / drift zones

These are in the tree, sometimes even routed, but should **not** be treated as stable local-core truth:

| Area | Current status |
|---|---|
| `per_player` pricing | UI-visible, lifecycle-incomplete |
| Setup/InGame manual kiosk path | present in UI, not backed by authoritative backend transitions without observer |
| Call-staff flow | frontend wired, backend endpoint missing |
| Match-sharing/result QR in keep-alive sessions | logically conflicts with observer-foreground behavior |
| Portal / `/api/central/*` Layer A | active adapter ring, not local-core authority |
| Licensing/device-registration/offline-queue stack | on disk, largely dormant from local-core standpoint |
| Duplicate settings exposure (`/settings/stammkunde-display`) | split across `settings.py` and `stats.py` |
| Docs/tests claiming old recovery boundaries | stale relative to current runtime |

---

## 3. Current failure risks

## 3.1 Fresh install can unlock into a dead observer path

**Files:** `backend/server.py`, `backend/routers/boards.py`, `frontend/src/pages/kiosk/KioskLayout.js`

- default seeded boards have no `autodarts_target_url`
- runtime default is observer mode
- unlock still succeeds
- kiosk moves into observer-oriented state/fallback UI, but there is no real Autodarts target to launch

**Impact:** fresh clone/demo can appear broken even though core code “works” structurally.

---

## 3.2 Manual/setup path is not authoritative

**Files:** `frontend/src/pages/kiosk/KioskLayout.js`, `backend/routers/kiosk.py`

`/kiosk/{board}/start-game` updates players/game_type but does **not** set `board.status=in_game`.
That transition currently comes from observer callback `_on_game_started()`.

**Impact:** if observer is disabled/unavailable, setup/in-game UI can drift or bounce back to setup after refresh/poll.

---

## 3.3 `per_player` is exposed as if complete, but lifecycle is incomplete

**Files:** `frontend/src/pages/admin/Dashboard.js`, `frontend/src/pages/admin/Settings.js`, `backend/routers/boards.py`, `backend/routers/kiosk.py`, `backend/services/scheduler.py`

- admin can unlock in `per_player`
- session is created
- no finalize rule consumes it
- no scheduler rule expires it
- no clear auto-end rule exists

**Impact:** sessions can remain logically active without a proper closing rule.

---

## 3.4 Scheduler expiry/idle lock is not integrated with observer/UI teardown

**Files:** `backend/services/scheduler.py`

Scheduler directly mutates session/board rows for:
- time expiry
- idle timeout

But it does **not** go through the same lifecycle path as `finalize_match()` / manual lock:
- no observer teardown
- no kiosk window restoration
- no WS broadcast
- unused `force_lock_if_expired()` suggests unfinished integration

**Impact:** stale browser/window/UI state after scheduler-driven lock is very plausible.

---

## 3.5 Revenue summary and reports are not one coherent accounting model

**Files:** `backend/routers/admin.py`

Problems:
- `/revenue/summary` only includes `finished/expired/cancelled`
- `/reports/sessions` includes **all sessions**, including active ones
- `/revenue/summary` sums `s.price_total` without null-guarding
- `by_board` is initialized in summary but never populated
- both endpoints use session rows, but with different rules

**Impact:** admin revenue page vs report export can disagree; bookkeeping is fragile.

---

## 3.6 Call-staff is wired in UI but missing in backend

**Files:** `frontend/src/pages/kiosk/KioskLayout.js`, `InGameScreen.js`, `ObserverActiveScreen.js`, `ErrorScreen.js`

UI posts to:
- `POST /api/kiosk/{board_id}/call-staff`

But no such route exists in current `backend/routers/kiosk.py`.

**Impact:** visible button, guaranteed failure.

---

## 3.7 Match-sharing can conflict with keep-alive observer behavior

**Files:** `backend/routers/kiosk.py`, `frontend/src/pages/kiosk/KioskLayout.js`

`finalize_match()` can generate `match_token` whenever match-sharing is enabled, even when credits remain and the observer is intentionally kept alive.
But in keep-alive branch the kiosk UI is **not restored**; Autodarts is kept foreground.

**Impact:** QR/result screen may be logically produced but not actually visible to players.

---

## 3.8 Observer-first flow under-populates players/stats unless `start-game` was used

**Files:** `backend/routers/kiosk.py`, `backend/routers/stats.py`

Default observer path can finish sessions without ever collecting `session.players`, because player names are only persisted by `/kiosk/{board}/start-game`.

**Impact:** match results, player stats, and public sharing can be incomplete in the real observer-based flow.

---

## 3.9 Offline semantics are underspecified

**Files:** `backend/models/__init__.py`, `frontend/src/pages/admin/Dashboard.js`, `KioskLayout.js`

- model exposes `BoardStatus.OFFLINE`
- admin UI styles it
- core local lifecycle barely drives it
- kiosk request failures mostly degrade to locked/default display

**Impact:** “offline” is more a UI idea than a reliable local state machine.

---

## 3.10 Source-of-truth drift is now a real maintenance risk

**Files:** `docs/ARCHITECTURE.md`, `docs/RECOVERY.md`, `docs/STATUS.md`, `backend/tests/test_v400_recovery_baseline.py`, `backend/tests/test_regression_e2e.py`, runtime files above

Current docs/tests still describe a cleaner post-recovery baseline than the active runtime actually has.

**Impact:** future cleanup work can easily preserve the wrong thing.

---

## 4. Gaps in tests

## 4.1 There are effectively no frontend state-machine tests

I found **no frontend test files** under `frontend/src`.

Missing coverage:
- `KioskLayout` state transitions
- observer-active vs setup/manual transitions
- result-screen timeout behavior
- settings fallback behavior
- call-staff button contract

---

## 4.2 The real core path lacks a tight in-process local test suite

There are many backend tests, but a lot of them are:
- preview/remote URL tests
- historical regression snapshots
- central/licensing-era tests
- smoke tests rather than precise local-core invariants

What is missing is a compact, authoritative **local-only TestClient suite** for:
- unlock / extend / lock
- observer game-start / game-end / finalize keep-alive
- scheduler expiry + observer cleanup
- revenue/report consistency
- seeded-board fresh-install behavior

---

## 4.3 Existing recovery tests are stale in important places

### `backend/tests/test_v400_recovery_baseline.py`
Problems:
- still claims all portal/central features were removed
- unlock test sends `player_names`, which current schema does not define
- validates broad smoke behavior, not current real lifecycle edges

### `backend/tests/test_regression_e2e.py`
Problems:
- still references removed/non-wired license-status behavior
- mixes local-core and central assumptions
- not a trustworthy gate for the local-only product

---

## 4.4 No meaningful tests for the risky edges found above

Missing focused tests for:
- observer mode + missing `autodarts_target_url`
- manual/setup mode without observer
- `per_player` lifecycle behavior
- scheduler-driven lock with observer/browser cleanup
- match-sharing when credits remain
- `reports/sessions` vs `revenue/summary` agreement
- missing `call-staff` endpoint contract
- offline/degraded UI semantics

---

## 5. Concrete recommendations for cleanup that preserves the working local core

## 5.1 Freeze the actual local-core boundary first

Treat these as the protected local-core boundary:
- `backend/models/__init__.py`
- `backend/database.py`
- `backend/dependencies.py`
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`
- `backend/services/scheduler.py`
- `backend/routers/settings.py`
- `backend/routers/admin.py`
- `frontend/src/pages/kiosk/KioskLayout.js`
- `frontend/src/pages/admin/Dashboard.js`
- `frontend/src/context/SettingsContext.js`

Everything else should be treated as optional surface or adapter until proven otherwise.

---

## 5.2 Make observer-first explicit, or stop defaulting to it

Pick one of these and enforce it in code:

### Preferred
If `AUTODARTS_MODE=observer`, require `autodarts_target_url` before unlock.
- fail unlock with a clear admin-facing error
- or mark board as misconfigured in dashboard

### Acceptable alternative
If no target URL exists, automatically downgrade that board to a supported manual mode **only after manual mode is repaired**.

Do **not** keep the current ambiguous “observer default but maybe no target URL” behavior.

---

## 5.3 Hide or remove incomplete modes/features from the stable surface

Until implemented end-to-end:
- remove/hide `per_player` from dashboard/settings
- remove/hide call-staff button or implement backend endpoint
- disable match-sharing for keep-alive sessions, or only show QR when `should_lock=true`
- treat setup/manual path as non-production unless fixed

This is the fastest way to preserve the working core without cosmetic lies.

---

## 5.4 Extract one lifecycle service from router code

Create a dedicated local service, e.g. `services/session_lifecycle.py`, and move these responsibilities into it:
- unlock policy validation
- session start/update helpers
- finalize decision
- observer teardown/keep-alive decision
- scheduler-driven expiry/idle close
- WS broadcasts for lifecycle state

Then make:
- `boards.py`
- `kiosk.py`
- `scheduler.py`

call the same service instead of each mutating state differently.

This preserves current behavior while reducing the drift risk.

---

## 5.5 Extract accounting into one source of truth

Create a small `services/accounting.py` used by both:
- `/revenue/summary`
- `/reports/sessions`
- CSV export

Define explicitly whether accounting means:
- **sales booked at unlock**, or
- **consumed gameplay**, or
- a future **payment ledger**

Right now the code implicitly chooses the first model, but inconsistently.

---

## 5.6 Give settings typed validation, not raw JSON replacement

Current settings writes replace whole JSON blobs with minimal validation.

Recommended cleanup:
- typed Pydantic schemas per setting family
- merge-with-default behavior for partial updates
- one canonical owner router for each setting key
- remove duplicated `/settings/stammkunde-display` exposure from `stats.py`

This keeps the flexible local settings model while making it safer.

---

## 5.7 Make scheduler-driven ends use the same teardown path as manual/finalize ends

When a session ends because of:
- time expiry
- idle timeout

it should trigger the same side-effect path as a real end:
- close observer if needed
- restore kiosk UI if needed
- broadcast state refresh
- write consistent end reason

Right now scheduler mutates rows directly; that is too low-level for a UI-heavy local kiosk product.

---

## 5.8 Rebuild the local-core tests around real contracts

Create one fast local-only suite that becomes the release gate.

Minimum contract set:
1. fresh install bootstraps usable defaults
2. unlock creates active session locally
3. observer start transitions board to `in_game`
4. finalize finished game deducts exactly one credit
5. remaining credits keep observer alive and board unlocked
6. last credit locks board and closes observer
7. per-time expiry locks via shared lifecycle path
8. revenue summary and reports agree on ended sessions
9. settings fallback/defaults always render kiosk/admin
10. central proxy/heartbeat failure does not affect local unlock/play/lock

Add lightweight frontend tests for `KioskLayout` state transitions on mocked API payloads.

---

## 5.9 Keep Layer A in an adapter ring

Current Layer A pieces should stay isolated:
- `backend/integrations/layer_a.py`
- `backend/services/central_heartbeat_client.py`
- `backend/routers/central_proxy.py`
- `frontend/src/context/CentralAuthContext.js`
- `frontend/src/pages/portal/*`

Rule: no Layer A or future central/licensing behavior should become a dependency of:
- `boards.py`
- `kiosk.py`
- `admin.py`
- local settings/session models

That is how the working local core stays intact.

---

## 6. Recommended preservation stance

### Preserve as-is
- local session persistence model
- centralized finalize semantics
- per-game credit keep-alive behavior
- local settings/defaults model
- local WS + polling redundancy
- central-outage non-blocking behavior

### Repair next
- observer default vs board configuration mismatch
- scheduler teardown integration
- accounting/report consistency
- manual/setup-mode truthfulness

### Hide or demote until proven
- `per_player`
- call-staff
- match-sharing in keep-alive flow
- anything central/licensing beyond current Layer A adapter ring

---

## Bottom line

The **working local core** at `cef9724` is not “everything still routed locally.”
It is specifically the **observer-first local session engine** built around:
- `boards.py`
- `kiosk.py`
- `autodarts_observer.py`
- `scheduler.py`
- `settings.py`
- `admin.py`
- `KioskLayout.js`
- `Dashboard.js`

Preserve that spine, shrink the public surface to match it, and move incomplete/overlay features out of the core path until they are truly end-to-end again.
