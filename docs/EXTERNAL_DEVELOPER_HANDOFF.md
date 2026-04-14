# External Developer Handoff

_Last updated: 2026-04-14_

This document is the fastest honest way for a new external developer to understand the project without reading old chat history or reconstructing intent from dozens of wave notes.

---

## 1. What this project is

`darts-kiosk` is a **local-first darts board runtime** with an optional evolving **central control plane**.

At its core, the product runs a venue kiosk / board control flow:
- board unlock / lock
- session lifecycle
- credits / pricing
- Autodarts observer integration
- local admin + kiosk UI
- local persistence and operator-safe behavior

The repo also contains a growing `central_server/` side for:
- auth / roles / scoped access
- device trust / enrollment groundwork
- licensing / entitlement groundwork
- support / diagnostics / fleet visibility
- future commercial / ledger / remote operations foundation

The key architectural rule is:

> **The local runtime is the protected product core.**
> Central work is allowed to grow around it, but should not destabilize local board/session behavior casually.

---

## 2. The single most important mental model

There are really **two systems** in one repo:

### A) Local runtime core
This is the thing that must keep working on a real board PC.

It owns:
- board state
- kiosk state
- unlock / lock
- session truth
- pricing / credits
- observer-authoritative match start/finish behavior
- local DB-backed runtime behavior

### B) Central control plane
This is the surrounding management/security/fleet layer.

It is intended to own:
- user identity and RBAC
- customer / location / device relationships
- device trust and enrollment
- support diagnostics
- licensing / entitlement semantics
- future durable commercial truth

If you remember only one design rule, remember this:

> **Do not let central-side ambition break the local runtime.**

---

## 3. Current status (real, not marketing)

## 3.1 Local runtime / kiosk / observer
Current status: **materially improved and practically testable**.

Important recent reality:
- kiosk loading state exists and is explicit
- unlock path works
- observer start path was hardened
- headless observer behavior is now explicit instead of ambiguous
- kiosk no longer blindly hides itself before observer health is confirmed
- headless/browser-smoke environments no longer degrade into a useless black screen

### Practical live UI cycle validated
A real local smoke cycle was exercised recently around:
- locked state
- unlock
- observer-active fallback state
- retry path
- session-end behavior
- manual re-lock

Observed behavior worth preserving:
- `locked -> unlocked` works
- headless observer environments show a visible fallback instead of a black void
- `session end` is **not the same thing as hard immediate lock** when credits/session semantics keep the board alive
- explicit lock returns kiosk cleanly to locked state

### Important caveat
This is still **not the same as full physical venue proof**.
The local product is in a much better place, but real Windows board-PC / long-running observer validation still matters.

---

## 3.2 Central / trust slice
Current status: **one focused trust/security slice is now green**, but that does **not** mean the whole central platform is finished.

Recent focused result:
- `backend/tests/test_central_security_hardening.py`
- `tests/test_device_trust.py`

Result:
- **95 passed**
- **0 failed**

What that means:
- device-trust compact/internal shaping is substantially more coherent
- operator-safe vs internal readback separation is materially improved
- several compact provenance / reconciliation / endpoint-summary contracts are now pinned and green

What it does **not** mean:
- the complete repo-wide suite is now magically green
- central is production-ready just because one focused slice is strong
- real PKI / final trust enforcement is done (it is still placeholder/HMAC-oriented groundwork in important parts)

---

## 3.3 Runtime packaging / board-PC drill lane
Current status: **one of the healthiest practical lanes in the repo**.

There is now a serious runtime packaging lane with:
- runtime-only packaging path
- allowlist audit tooling
- Windows runtime scripts
- maintenance / update / rollback helpers
- drill handoff artifacts
- paired update/rollback evidence flow
- support bundle generation

This lane has progressed far beyond theory.
It is much closer to a real board-PC operational story than the repo used to be.

Still, the correct phrasing is:
- **healthy / promising / structured**
- not automatically “ship everything everywhere tomorrow”

---

## 3.4 Overall repo state
Current status: **mixed but much clearer than before**.

Best honest summary:
- the repo is now far more understandable than it was
- the local runtime path is materially better
- the focused central/trust slice is green
- runtime packaging/docs/handoff story is much stronger
- but this is still a project in active reconciliation and maturation, not a finished all-green product

---

## 4. What changed recently that matters to a new developer

The biggest practical shifts are:

1. **Observer behavior is more honest**
   - headless fallback is explicit
   - kiosk hide waits for observer health confirmation
   - UI smoke behavior is testable

2. **Device trust / support diagnostics became more structured**
   - compact summaries
   - operator-safe vs internal shaping
   - provenance/source-contract rollups
   - endpoint summary consistency

3. **Runtime package lane became a real operational subsystem**
   - packaging, validation, update, rollback, handoff, attachment readiness

4. **Docs became much broader**
   - there is now enough durable repo context that a new developer does not need chat archaeology to orient themselves

---

## 5. The repo map a new developer should care about

## Core runtime
- `backend/`
- `frontend/`

Especially important runtime files:
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/services/autodarts_observer.py`
- `backend/dependencies.py`
- `frontend/src/pages/kiosk/KioskLayout.js`
- `frontend/src/pages/kiosk/ObserverActiveScreen.js`

## Central / trust / auth
- `central_server/`

Especially important central files:
- `central_server/server.py`
- `central_server/device_trust.py`
- `central_server/auth.py`
- `central_server/models.py`

## Runtime packaging / Windows operational lane
- `release/`
- `release/runtime_windows/`
- `scripts/audit_runtime_package.py`

## Durable project docs
Start here:
- `README.md`
- `docs/EXTERNAL_DEVELOPER_HANDOFF.md`
- `docs/TEST_READINESS.md`
- `EXECUTION_BOARD.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/CENTRAL_REBUILD_MASTERPLAN.md`
- `docs/DEVICE_TRUST_MODEL.md`
- `docs/CENTRAL_CONTRACT.md`
- `docs/ACCESS_CONTROL_MATRIX.md`
- `docs/COMMERCIAL_LEDGER_FLOW.md`

---

## 6. How to start the project locally

## Backend
From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.server:app --reload --port 8001
```

## Frontend

```bash
cd frontend
npm ci
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

## Useful URLs
- API: `http://localhost:8001/api`
- Admin UI: `http://localhost:8001/admin`
- Kiosk UI: `http://localhost:8001/kiosk/BOARD-1`

---

## 7. How to think about tests

Do **not** assume “the suite” is a single trustworthy truth source.
Use slices.

### High-value focused slices

#### Central / trust slice
```bash
.venv/bin/python -m pytest -q \
  backend/tests/test_central_security_hardening.py \
  tests/test_device_trust.py
```

Current known result:
- **95 passed**
- **0 failed**

#### Runtime packaging / drill slice
Check current runtime/drill tests separately instead of assuming parity with central/trust.

### Practical rule
When touching one area, re-run the **focused slice that actually represents that area**.
Do not use full-suite noise as your only signal.

---

## 8. What is definitely *not* done yet

A new developer should not accidentally overclaim the project.

Not done / not fully proven yet:
- real final PKI-grade device trust
- finished licensing/enforcement model in production terms
- broad repo-wide all-green test posture
- final board-PC field proof for every operational claim
- polished productization of every optional/legacy surface still in the tree

---

## 9. Near-term plan

The next sensible plan is:

### 1) Keep the local runtime stable
- do not casually churn protected runtime/core files
- preserve unlock/session/observer behavior unless there is a very good reason

### 2) Keep documentation honest and centralized
- prefer updating durable docs over letting truth live only in chat
- keep external entry docs current

### 3) Continue practical board-PC/runtime validation
- use the runtime packaging/drill lane for real-world proof
- close the gap between “good repo mechanics” and “real operator confidence”

### 4) Continue central hardening deliberately
- keep auth / trust / diagnostics / contract shaping coherent
- avoid flashy central expansion before basics are boring and reliable

### 5) Reconcile remaining broader-suite red areas by cluster
- not by blind full-suite thrashing
- keep working cluster-by-cluster with explicit contracts

---

## 10. Recommended work order for an external developer

If you join this project fresh, the safest order is:

1. read `docs/README.md`
2. read this file
3. read `README.md`
4. read `docs/TEST_READINESS.md`
5. read `EXECUTION_BOARD.md`
6. read `docs/CENTRAL_REBUILD_MASTERPLAN.md`
7. read `docs/DEVICE_TRUST_MODEL.md`
8. inspect the core runtime files
9. run one focused test slice before changing anything
10. only then start implementing

---

## 11. Contribution rules that matter

- keep **local core** changes disciplined
- update **tests and docs in the same branch** when changing contracts
- prefer **small explicit contract changes** over large vague refactors
- do not introduce “theory architecture” that outruns the validated runtime reality
- when in doubt, make the repo **more understandable**, not more clever

---

## 12. Bottom line

If you are an external developer, this is the honest bottom line:

- there is a **real, understandable project** here now
- the **local runtime** is the product spine
- the **central/trust layer** has meaningful momentum and one important slice is green
- the **runtime packaging lane** is operationally serious
- the repo is **much more maintainable than before**
- but you should still approach it as a **maturing system**, not a finished cathedral

That is exactly the right mindset to be productive here.
