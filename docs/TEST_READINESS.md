# Test Readiness

_Last updated: 2026-04-14 (repo-doc consolidation pass)_

## Mode

The repo is currently in **test-readiness / reality-check mode**.

That means:
- **wave mode is frozen for now**
- do **not** resume trust/runtime/central wave progression just because more additive slices are available
- use the next work only to reconcile the current contract, validate the real board-PC/runtime path, and document the actual state cleanly

## Current verdict

**Mixed readiness.**

Short version:
- the **full suite should still not be described as generally green**
- the previously red **central / trust slice has now been reconciled and is green in its focused form**
- the **runtime lane is comparatively healthy** and still the closest thing to a practical field-ready path, but it is **not perfectly green either** in the current repo snapshot
- the **live kiosk/UI state is materially better than before**: loading state exists, unlock path still exists, and observer behavior is now explicit for real UI handoff vs headless/browser-smoke fallback

## What was checked

### Docs / durable state reviewed
- `docs/TEST_READINESS.md`
- `EXECUTION_BOARD.md`
- `docs/DEVICE_RUNTIME_PACKAGE_WAVE34.md` through `docs/DEVICE_RUNTIME_PACKAGE_WAVE38.md`

### Repo-state signals reviewed
- `frontend/src/pages/kiosk/KioskLayout.js`
- `frontend/src/pages/kiosk/ObserverActiveScreen.js`
- `backend/services/autodarts_observer.py`
- `backend/routers/kiosk.py`
- `kiosk-check.spec.js`

### Focused pytest reality check runs

#### Earlier mixed-slice reality check
Command:

```bash
.venv/bin/python -m pytest -q \
  tests/test_runtime_field_evidence.py \
  tests/test_runtime_maintenance_closed_loop.py \
  tests/test_device_trust.py \
  backend/tests/test_central_security_hardening.py \
  --maxfail=20
```

Historical result from that mixed slice:
- **111 passed**
- **11 failed**
- **2 warnings**
- runtime: about **64s**

#### Current central / trust focused result
Command:

```bash
.venv/bin/python -m pytest -q \
  backend/tests/test_central_security_hardening.py \
  tests/test_device_trust.py
```

Current result:
- **95 passed**
- **0 failed**
- **2 warnings**

## What is actually healthy vs not

### 1) Full-suite / broad repo health
Not ready to call green.

The current repo state still shows broad red/drift outside a narrow “one lane is usable” narrative. The right summary is:
- there is real progress
- a lot of targeted tests pass
- but the suite is **not** in a presentable all-green state

### 2) Central / trust lane
Useful, runnable, and the focused reconciliation slice is now **green**.

What changed:
- compact summary / provenance contract drift was reconciled
- internal vs operator-safe detail shaping was tightened
- missing internal support-summary shaping was fixed
- source-contract rollup / name-list expectations were aligned with the intended contracts

Current focused result:
- `backend/tests/test_central_security_hardening.py`
- `tests/test_device_trust.py`
- **95 passed / 0 failed**

Important caveat:
- this means the **focused trust/security slice is healthy now**
- it does **not** mean the broader repo/full suite is generally green
- trust still remains an evolving central-side capability, not a finished production PKI/enforcement story

### 3) Runtime lane
**Comparatively healthiest lane**, but not clean.

The runtime package/handoff lane still looks materially better than the trust/full-suite picture:
- Waves 34–38 are all additive reviewer/handoff ergonomics work
- they stay confined to runtime drill artifacts and do not destabilize updater/install/rollback semantics
- the board-PC/service handoff story is substantially more mature and more operator-safe than before

But in the current repo snapshot, the runtime sample is **not 100% green** either.
The same combined pytest run still shows runtime-lane failures in:
- `tests/test_runtime_maintenance_closed_loop.py::test_acknowledge_drill_handoff_persists_post_attach_metadata`
- `tests/test_runtime_maintenance_closed_loop.py::test_reacknowledge_drill_handoff_reuses_stored_ticket_destination`
- `tests/test_runtime_maintenance_closed_loop.py::test_acknowledgment_history_pattern_marks_latest_as_one_of_multiple_destination_changes`

So the correct readiness phrasing is:
- runtime lane = **closest to usable / healthiest**
- not runtime lane = magically green

## Live UI / observer reality now

### Kiosk loading state is present
`frontend/src/pages/kiosk/KioskLayout.js` explicitly renders a loading shell with:
- `data-testid="kiosk-loading"`

That aligns with `kiosk-check.spec.js` and means the previously missing/unclear loading state is now a durable part of the UI contract.

### Unlock path still exists
The board unlock route still exists in `backend/routers/boards.py`, and kiosk state flow in `KioskLayout.js` still moves:
- `locked -> unlocked`
- `unlocked -> observer_active` when observer mode is active
- `blocked_pending` and normal locked/setup/in-game states remain explicit

So the repo state still supports the practical claim that **unlock works as a first-class lane**, even though broader suite health is not clean.

### Observer handoff vs fallback is now explicit
The kiosk frontend now distinguishes two real observer states:
- **real handoff screen** when `observerBrowserOpen && !observerHeadless`
  - renders `data-testid="observer-handoff-screen"`
  - effectively means the kiosk should hand off visually to the external observer browser
- **fallback screen** otherwise
  - renders `data-testid="observer-fallback-screen"`
  - gives retry / staff / end-session controls

### Headless behavior is clarified instead of ambiguous
`ObserverActiveScreen.js` now states plainly that when the observer runs **headless**, the kiosk remains visible for browser smokes instead of pretending there is an external visible observer screen.

On the backend side, `backend/services/autodarts_observer.py` also makes the intended runtime behavior clearer:
- non-headless observer launch uses fullscreen browser behavior
- kiosk hide happens **only after** health checks confirm a valid authenticated session
- auth redirect / broken session cases abort cleanly and do **not** hide the kiosk

That is the key “live UI state achieved” point worth preserving in docs:
**kiosk loading fixed, unlock path intact, observer fallback explicit, headless/browser-smoke behavior clarified, and kiosk hide delayed until observer health is actually confirmed.**

## Practical next steps

### Do next
1. **Do not resume random wave work just because one slice is green.**
2. Keep the next step practical:
   - validate / finish the board-PC closed-loop drill path
   - reconcile remaining runtime-lane failures and real operator flow gaps
3. Treat the green central/trust slice as a maintained contract:
   - keep it green while changing adjacent central surfaces
   - update tests/docs together when contracts intentionally move
4. Continue broader-suite cleanup by cluster, not by blind all-suite thrashing

### Suggested immediate commands
```bash
.venv/bin/python -m pytest tests/test_runtime_maintenance_closed_loop.py -q -vv
.venv/bin/python -m pytest tests/test_device_trust.py backend/tests/test_central_security_hardening.py -q -vv
```

## Bottom line

Use this wording in future handoffs unless the repo state changes materially:
- **Wave mode should remain disciplined, not opportunistic.**
- **The focused central/trust slice is green.**
- **The full repo should still not be described as broadly green without qualification.**
- **Runtime lane is comparatively healthy, but not clean.**
- **Live kiosk/UI state is materially improved and explicit.**
- **Next work is practical validation + broader cluster reconciliation, not decorative progress narration.**
