# Architecture

This document describes the **current runtime architecture**, not the repo's old recovery mythology.

The key design decision is simple:

> protect the local board runtime first; treat central, portal, and experimental surfaces as optional overlays unless they are re-proven end to end.

## 1. System model

The application is split into three practical layers.

### 1.1 Protected local core

This is the part that must keep a board usable even when central services are unavailable.

Core responsibilities:
- local authentication and admin control
- board unlock / extend / lock
- session persistence in SQLite
- settings stored locally in SQLite JSON blobs
- observer-first Autodarts integration
- authoritative start/finish handling
- pricing / credits / time-capacity enforcement
- local WebSocket fanout and polling fallback
- local revenue/reporting views based on stored session rows

Primary modules:
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

### 1.2 Optional adapter ring

This exists in the repo but is **not** the protected production baseline.

Typical examples:
- Layer A heartbeat / central visibility
- central proxy routes
- config sync / telemetry / offline queue / action poller
- portal-facing surfaces

Current expectation:
- adapters may be enabled explicitly
- adapter failure must not block local unlock/play/lock
- local-core modules must not depend on central success to function

### 1.3 Legacy / incomplete surfaces

These still exist in the tree or UI, but should not be mistaken for battle-tested core behavior.

Examples:
- call-staff UX path
- some manual/setup-mode assumptions in kiosk flow
- assorted legacy regression suites that target preview deployments rather than the current local-core contract

## 2. Runtime composition

## 2.1 Startup

Entrypoint: `backend/server.py`

Startup does the following:
1. loads env/secrets
2. initializes the database
3. seeds default admin/staff users if missing
4. seeds `BOARD-1` and `BOARD-2` if missing
5. seeds default settings blobs if missing
6. starts local background services such as scheduler, backup, health monitor, update checks, watchdog, and mDNS
7. mounts local-core API routers under `/api`
8. mounts optional adapter routes only when runtime flags permit them

Important nuance:
- the codebase contains central/adapter wiring
- the **default design intent** is still local-first
- docs and validation should describe that honestly, not pretend the repo is purely local or purely centralized

## 2.2 Data model

Core persistent entities:
- `Board` — local board identity and status (`locked`, `unlocked`, `in_game`, `offline`)
- `Session` — pricing mode, capacity, price, timestamps, players, and end reason
- `Settings` — local JSON config blobs
- `AuditLog` — operator/admin actions
- `MatchResult` — optional public result sharing tokenized record
- `Player` — guest/registered nickname stats

### Session truth model

A `Session` is the local source of truth for:
- capacity sold (`credits_total`, `minutes_total`, `players_count`)
- capacity remaining (`credits_remaining`, `expires_at`)
- recorded sale amount (`price_total`)
- lifecycle state (`active`, `finished`, `expired`, `cancelled`)
- player names if captured

There is **no dedicated payment ledger** yet. Revenue and accounting views derive from `Session.price_total`.

## 3. Board/session lifecycle

## 3.1 Unlock

Route: `POST /api/boards/{board_id}/unlock`

Flow:
1. validate board exists
2. validate pricing mode is supported by the local core
3. in observer mode, require an Autodarts target URL
4. ensure no active session already exists
5. seed session capacity from pricing mode
6. create `Session(status=active)`
7. set board status to `unlocked`
8. broadcast local state update
9. if configured, start observer / desktop side effects

Protected behavior:
- local DB state is written before observer side effects matter
- central connectivity is not part of the unlock path

## 3.2 Start of play

Authoritative path: observer callback `_on_game_started()` in `backend/routers/kiosk.py`

What happens:
- observer match/lobby payloads can override kiosk-entered player count with the authoritative Autodarts player count
- if `per_player` credits are sufficient, board moves to `in_game` and charges exactly once at authoritative start-of-play
- if `per_player` credits are insufficient, board moves to `blocked_pending` instead of hard-locking
- `per_game` and `per_time` sessions do not charge at start
- a start sound/event is broadcast

This is why the repo is described as **observer-first**. The kiosk UI can register names/game type, but the authoritative gameplay start is the observer callback.

## 3.3 Finish of play

Authoritative path: `finalize_match(board_id, trigger)` in `backend/routers/kiosk.py`

Responsibilities:
- duplicate-finalize protection
- capacity consumption on authoritative finish when applicable
- keep-alive vs teardown decision
- session close / board lock when capacity is exhausted
- optional match-result record creation
- player stat increments when match completion is recorded
- observer teardown or return-home behavior
- local WebSocket fanout and kiosk refresh coordination
- timeout recovery path

This is the main lifecycle choke point and the most important contract to protect.

## 3.4 Manual lock

Route: `POST /api/boards/{board_id}/lock`

Behavior:
- active session becomes `cancelled`
- `ended_reason=manual_lock`
- board moves to `locked`
- observer shutdown is requested

Manual lock is an operator override, not a match finish.

## 4. Pricing and capacity rules

Implementation spine:
- `backend/services/session_pricing.py`
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`

### `per_game`
- capacity is `credits_remaining`
- one authoritative finish consumes one credit
- assistive finish hints do not consume credit
- if credits remain, board stays unlocked and observer remains alive
- if credits hit zero, board locks and session ends

### `per_player`
- unlock seeds credits from player count
- authoritative start-of-play uses Autodarts-derived player count when available
- if credits cover that count, the whole resolved player count is consumed once
- if credits do not cover that count, the board enters `blocked_pending` and waits for staff top-up instead of locking
- once topped up, the pending gate resolves exactly once and play continues
- finish does not add a second charge

### `per_time`
- no credit deduction per match
- capacity is time until `expires_at`
- match finish only decides whether time remains; if yes, session stays alive

Full billing notes live in `docs/CREDITS_PRICING.md`.

## 5. Autodarts integration model

This is **not** a clean server-to-server API integration.

It is a browser observer around `play.autodarts.io` using:
- Playwright WebSocket capture
- console heuristics
- DOM fallback heuristics
- Windows foreground/window choreography for kiosk vs Autodarts

Practical trust ladder:
1. authoritative WebSocket signals
2. assistive WebSocket hints
3. console/DOM diagnostics

Billing-critical actions should stay tied to the top of that ladder.

See `docs/AUTODARTS_ANALYSIS.md` for the detailed evidence.

## 6. Local settings and realtime model

### Settings
- stored in `Settings.value` JSON blobs
- lazily created with defaults
- frontend also has some fallback defaults so kiosk/admin can still render in degraded conditions

### Realtime
- push: `/api/ws/boards` via `backend/services/ws_manager.py`
- pull fallback: frontend polling in kiosk/admin flows

That push+poll redundancy is intentional and should stay.

## 7. Revenue and reporting model

Current accounting model:
- revenue is derived from `Session.price_total`
- revenue summary is booked revenue from closed sessions in the selected period
- reports expose session history and local bookkeeping views
- there is still no payment ledger or reconciliation layer

Important limitation:
- this is acceptable for local operator reporting
- it is not yet a full finance/accounting subsystem

## 8. Deployment modes

### Developer / local Linux workflow
- run backend from repo root via `python -m uvicorn backend.server:app`
- run frontend separately with `npm start`
- use pytest suites for local-core validation

### Windows board PC workflow
- use `release/windows/*.bat`
- prepare persistent Autodarts profile via `setup_profile.bat`
- validate with `smoke_test.bat`
- perform live observer/kiosk checks on the actual machine

## 9. Known risks and intentionally deferred areas

Still risky / not fully validated:
- real Windows foreground/focus behavior
- long-running live Autodarts observer reliability
- stale legacy tests that still describe older recovery assumptions
- optional/legacy surfaces that look more complete than they are

The architectural stance for now is conservative:
- keep the local core small and explicit
- document incomplete surfaces honestly
- do not pretend sandbox validation replaced real-machine proof
