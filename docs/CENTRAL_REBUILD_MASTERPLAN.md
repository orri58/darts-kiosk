# Central Rebuild Masterplan

## Goal

Rebuild the central platform as a **professional, secure, marketable control plane** around the existing **frozen local product core**.

The local runtime remains the product of record for:
- board/session lifecycle
- local pricing/capacity truth
- observer-authoritative start/finish handling
- offline-safe operation

The central platform becomes responsible for:
- identity and access control
- customer / location / device hierarchy
- licensing / entitlement management
- support / diagnostics / fleet visibility
- safe remote maintenance
- commercial truth for revenue/event durability
- future billing foundations

## Non-negotiable principles

1. **Frozen local core first**
   - Central work must not destabilize unlock/start/finish/lock/reporting flows.
2. **Split runtime truth from commercial truth**
   - Local remains authoritative for live board/session state.
   - Central becomes authoritative for license validity, commercial entitlements, and durable revenue/event ledger.
3. **Central starts read-only for runtime, then earns tightly scoped write authority**
   - Visibility first, remote control later.
4. **Everything central is feature-flagged**
   - Safe defaults remain local-only.
5. **Security is a gate, not a polish pass**
   - No public rollout before auth, secrets, device identity, and action safety are hardened.
6. **Docs + tests move with code**
   - No architecture drift.
7. **Real hardware validation is mandatory**
   - Windows + Autodarts proof is required before production claims.

## Current diagnosis

### Local side
The local product core is now materially stronger and must be treated as the protected baseline.

### Central side
The existing `central_server` contains useful domain seeds, but is not a safe or clean production foundation in its current form.

Key central weaknesses identified:
- default/fallback secrets and legacy bypass paths
- weak password hashing in central auth
- inconsistent auth modes across portal/device flows
- unsafe remote action surfaces
- insufficient tenant/isolation rigor
- overbroad exposure defaults
- no professional-grade device identity model
- immature operational governance for public deployment

## Target architecture

## Bounded contexts

### 1. Local Runtime Core
Owns:
- board state
- session lifecycle
- pricing/capacity logic
- observer integration
- local admin/kiosk runtime
- local persistence

### 2. Central Control Plane
Owns:
- user identity / RBAC / support roles
- customer / location / device inventory
- licensing / entitlements / activation state
- fleet visibility / telemetry / diagnostics
- remote maintenance orchestration
- config governance
- durable commercial ledger for revenue-critical events
- future billing prerequisites

### 3. Device Enrollment & Trust
Owns:
- secure enrollment
- device credentials / certificates / token lifecycle
- re-enrollment / replace / revoke flows
- trust status for remote commands

### 4. Telemetry & Support Plane
Owns:
- health snapshots
- readiness snapshots
- diagnostics / support bundles
- event ingestion and retention policy

## Source-of-truth rules

- **Local runtime** is authoritative for live play and session state.
- **Central** is authoritative for licensing intent, role assignments, support orchestration, fleet metadata, and the durable commercial ledger.
- **Central config** may propose desired state; local runtime applies only through explicit, safe rules.
- **Revenue/commercial truth** must be written to central as append-only events in real time; local keeps a cache/read model and retry queue, not the only copy.
- **No-license policy:** without a valid central-issued license/lease, the device may boot only into provisioning/support mode and must not allow monetized operation.

## Program phases

## Phase 0 — Freeze and define
- freeze protected local-core boundary
- document contracts and ownership
- define runtime flags and safe defaults
- create governance/test/release gates

## Phase 1 — Security baseline
- remove default secrets and legacy superadmin bypasses
- redesign central auth/authz model
- redesign device identity / enrollment model
- define remote action safety model
- define production deployment hardening baseline

## Phase 2 — Central seam extraction
- isolate central adapter interfaces from local core
- ensure adapters can be disabled completely
- formalize event/snapshot contracts

## Phase 3 — Read-only central visibility
- central dashboards for board/session/device health
- telemetry/readiness/support surfaces
- strict read-only posture first

## Phase 4 — Safe remote operations
- introduce audited, scoped, idempotent remote actions
- start only with reversible maintenance actions
- no remote billing/play authority

## Phase 5 — Licensing / entitlement v1
- customer/location/device hierarchy
- activation / license status / suspend / renew / rebind flows
- device-bound license leases and anti-cloning rules
- offline-safe but time-bounded enforcement boundaries

## Phase 6 — Config sync / fleet governance
- define central-owned vs local-owned settings
- staged rollout / per-board overrides
- conflict-resolution model

## Phase 7 — Commercial foundation
- entitlement-aware plan structure
- operator/account support workflows
- future-ready billing integration boundaries
- revenue visibility that does not corrupt local runtime truth

## Phase 8 — Field validation and rollout
- real Windows/Autodarts validation
- outage drills
- rollback drills
- support-bundle proof
- staged deployment

## Clarifications from owner requirements

- The system must be designed so a copied install or copied data folder is not enough to run another licensed device.
- License enforcement must be device-bound and centrally controlled.
- Revenue-critical events must be streamed to central in real time and stored durably there.
- If a local PC dies, the central platform must remain the retained source for already-acknowledged revenue and operational events.
- Absolute zero-loss is only achievable for events that were acknowledged by central before failure; therefore revenue-critical flows must be designed around central append/ack semantics.
- If connectivity is lost, operation may continue only within a short signed lease / bounded grace policy; after that, monetized operation must stop.

## Security must-haves before public exposure

1. remove `CENTRAL_ADMIN_TOKEN`-style bypasses
2. fail startup on weak/default production secrets
3. replace weak password hashing with Argon2id/bcrypt
4. authenticate every device-facing sensitive endpoint
5. stop exposing/storing plaintext reusable device secrets where avoidable
6. replace ad-hoc device auth with proper enrollment + rotatable trust model
7. lock down CORS/origin policy
8. move central DB off SQLite for real public control-plane use
9. add rate limits / abuse protection / audit coverage
10. classify remote actions by risk and require stronger controls for high-risk actions

## Product v1 scope

Build now:
- customer / location / device inventory
- roles and scoped access
- activation / entitlement basics
- support / diagnostics / readiness
- safe remote maintenance (limited scope)
- central fleet visibility

Do **not** build first:
- giant all-in-one multi-tenant portal
- full billing engine
- too many pricing/business variants
- central authority over local match lifecycle
- overdesigned finance/accounting stack

## Guardrails

Protected modules must not be casually changed:
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

Defaults must remain local-safe:
- central adapters off by default
- portal surfaces off by default
- optional staff-call surfaces off by default

## Release gates

A central phase cannot ship unless:
- focused local-core backend suite is green
- frontend build is green
- release build is green
- adapters off shows no local behavior regression
- adapters on degrade gracefully when central is unavailable
- one real Windows + Autodarts validation pass succeeds
- rollback path is documented and tested

## First concrete execution block

### Sprint 1 — Freeze core / define contracts
- create governance doc
- create central contract doc
- document protected modules and ownership boundaries
- lock runtime flag matrix
- add focused merge gates for protected-core validation
- define settings ownership map

### Sprint 2 — Read-only central overlay
- define/export read model for board/session/device status
- add safe heartbeat/status publishing
- central diagnostics/support visibility
- validate central outage has zero impact on local runtime

## Recommended next implementation start

Start with:
1. governance docs
2. central contract + ownership docs
3. security baseline design
4. adapter seam extraction

Do **not** start with billing or flashy central UI.

## Operating mantra

**Protect local runtime. Build central as a professional control plane. Visibility first. Authority later. Security before marketing.**
