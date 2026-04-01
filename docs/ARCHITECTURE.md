# Architecture

## Current target architecture (Phase 2)

The repo is **not** a single homogeneous system anymore.

The correct mental model is:

1. **stable local core** first
2. **operator surfaces** on top of that core
3. **optional adapters** outside the core
4. **dormant / not-yet-reintegrated modules** kept off the default runtime path

That is the only layering consistent with the recovered code, the local-core audit, and the current Phase 2 cleanup.

---

## 1. Layer map

### Layer 0 — Local core (default, protected)

This is the product that must keep working even if every central/licensing piece is absent.

**Responsibilities**
- local auth
- local board/session persistence
- unlock / extend / lock
- observer-first kiosk session lifecycle
- session finalization
- local settings
- local revenue / reports
- local websocket fanout
- local watchdog / backup / health / update helpers

**Primary backend modules**
- `backend/database.py`
- `backend/models/__init__.py`
- `backend/dependencies.py`
- `backend/schemas.py`
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
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`

**Primary frontend surfaces**
- `/kiosk`
- `/admin`
- local contexts: `AuthContext`, `SettingsContext`, `I18nContext`

**Local-core rules**
- local play must not depend on central reachability
- observer lifecycle stays local and authoritative
- board unlock creates local DB state before side effects
- session finalization remains local and idempotent
- unsupported modes must not be advertised as stable

---

### Layer 1 — Operator-facing local surfaces

These are still part of the local product, but they must stay aligned with the real local-core capabilities.

**Currently operator-facing and supported**
- board unlock / extend / lock
- `per_game`
- `per_time`
- branding / pricing / sound / language / kiosk texts / PWA / kiosk control
- public leaderboard QR on lock screen
- QR match sharing only when a session truly ends

**Stable in backend lifecycle, but not fully surfaced in local UI yet**
- `per_player`
- Autodarts trigger policy config

**Explicitly hidden/degraded in current local UI**
- call-staff UI is hidden by default
- observer-mode unlock now fails clearly if the board has no `autodarts_target_url`

That last point is intentional: observer-first local runtime is safer with an honest block than with a fake unlocked state that cannot launch the real gameplay surface.

---

### Layer 2 — Optional adapter ring (opt-in)

This layer is allowed to exist, but it is **outside** the stable local runtime path.

**Examples**
- Layer A central heartbeat
- `/api/central/*` visibility proxy
- `/portal` frontend routes

**Phase 2 rule**
- adapters are mounted only through explicit seams
- adapters are opt-in
- adapters may observe local state, but must not destabilize local play

**Current gates**
- backend: `backend/runtime_features.py`
- route composition: `backend/app_layers.py`
- frontend route surface: `frontend/src/runtimeFeatures.js`

**Default behavior**
- `ENABLE_CENTRAL_ADAPTERS` unset/false → no central adapter startup, no mounted central proxy
- `ENABLE_PORTAL_SURFACE` only matters when central adapters are enabled

So the default product path is again: **local only**.

---

### Layer 3 — Dormant / not yet reintegrated modules

These modules may stay in the repo, but they are **not** current product truth.

Examples:
- `backend/routers/licensing.py`
- `backend/services/license_service.py`
- `backend/services/license_sync_client.py`
- `backend/services/config_sync_client.py`
- `backend/services/action_poller.py`
- `backend/services/telemetry_sync_client.py`
- `backend/services/ws_push_client.py`
- `central_server/*`
- legacy portal/operator pages not mounted in the default app flow

They are staging material for later reintegration, not part of the baseline runtime contract.

---

## 2. Explicit seams added in Phase 2

### Runtime feature seam
- `backend/runtime_features.py`
- `frontend/src/runtimeFeatures.js`

Purpose:
- central surface is explicit instead of ambient
- local supported pricing modes are explicit
- incomplete UI surfaces can be hidden without rewriting the whole app

### Route composition seam
- `backend/app_layers.py`

Purpose:
- local-core routers mount by default
- adapter routers mount only when explicitly enabled
- `backend/server.py` stops being a grab-bag of local + central wiring

---

## 3. Supported local flow

### Board/session flow
1. admin unlocks board locally
2. local DB session is created
3. if runtime is observer mode, board must already have `autodarts_target_url`
4. observer starts against the configured target
5. `finalize_match()` remains the authority for credit/time/session-end decisions
6. if credits/time remain, observer stays alive
7. if session truly ends, board locks and kiosk UI is restored

### Supported pricing modes in backend lifecycle
- `per_game`
- `per_player`
- `per_time`

### Still not fully surfaced in local operator UI
- `per_player`
- trigger-policy editing

---

## 4. Match result / QR sharing rule

QR match sharing is now aligned with the real session lifecycle:
- if the session actually ends, a match token may be created
- if credits/time remain and the board stays active, the local kiosk flow wins and no operator-facing result QR interrupts it

This matches the observer-first local core better than the previous hybrid behavior.

---

## 5. What must stay true in future phases

Any central/licensing reintegration must satisfy all of these:

1. **Local auth remains local unless explicitly replaced with a proven boundary.**
2. **Board unlock/finalize must continue to work with no central connectivity.**
3. **Adapters fail detached, not by corrupting local runtime flow.**
4. **New modes are hidden until lifecycle/accounting semantics are complete.**
5. **Mounted routes and startup services must reflect reality, not aspiration.**

If a change violates one of those, it belongs outside the local-core path until proven safe.
