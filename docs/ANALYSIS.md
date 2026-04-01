# Analysis Synthesis

This file is the **current synthesis** of the preserved analysis work in:
- `docs/ANALYSIS_BASELINE.md`
- `docs/LOCAL_CORE_AUDIT.md`
- `docs/AUTODARTS_ANALYSIS.md`
- `docs/PHASE3_4_IMPLEMENTATION.md`
- `docs/PHASE5_6_IMPLEMENTATION.md`

Those source documents remain intentionally preserved as evidence. This file turns them into one operator/developer-readable picture of the repo.

---

## 1. What the repo actually is now

The repo is **not** a clean-room rewrite and **not** a pure central-platform product.

It is a recovered and hardened codebase whose most trustworthy part is the **local observer-first board runtime**:
- local auth/admin
- local board/session persistence
- local pricing and credits/time capacity
- local WebSocket updates with polling fallback
- browser-observer integration for Autodarts
- Windows operator scripts for setup/start/stop/smoke testing

There is also:
- an optional central adapter ring
- historical recovery docs and tests
- legacy or incomplete UI/API surfaces that still exist in the tree

That combination is why earlier docs drifted: some files described the repo as “pure local baseline,” while the runtime still contained adapter wiring and unfinished edges.

## 2. Main findings from the preserved evidence

## 2.1 Baseline history finding

From `docs/ANALYSIS_BASELINE.md`:
- the recovery work did restore the local runtime spine
- but later commits kept some Layer A / adapter seams alive
- older docs and tests continued to describe a cleaner separation than the running code actually enforced

Practical conclusion:
- documentation had to stop pretending the repo was either fully de-featured or fully re-centralized
- the honest answer is: **local core first, optional adapters present, live validation still pending**

## 2.2 Local-core audit finding

From `docs/LOCAL_CORE_AUDIT.md`:
- the real stable product spine is narrower than the visible UI/API surface
- the strongest local path is the observer-based unlock -> play -> finalize lifecycle
- `finalize_match()` is the main backend authority worth protecting
- central outages are supposed to be non-fatal to local play
- settings are local-first and should remain so

Practical conclusion:
- the protected boundary is the local session engine, not every routed endpoint in the repo
- optional/legacy surfaces should be documented as such instead of being silently treated as production baseline

## 2.3 Autodarts analysis finding

From `docs/AUTODARTS_ANALYSIS.md`:
- Autodarts integration is a browser observer, not a stable formal API integration
- the signal hierarchy matters:
  1. authoritative WS signals
  2. assistive WS hints
  3. console/DOM heuristics
- billing-critical actions must stay attached to authoritative signals only

Practical conclusion:
- per-player billing belongs at authoritative start-of-play
- per-game billing belongs at authoritative finish/manual stop
- assistive hints are useful for resilience, not for final billing authority

## 2.4 Phase 3/4 implementation finding

From `docs/PHASE3_4_IMPLEMENTATION.md` and `docs/CREDITS_PRICING.md`:
- billing logic was tightened around authoritative start/finish semantics
- per-player charging moved to authoritative start-of-play
- per-game charging stayed on authoritative finish/manual end
- abort/reset paths should not charge by themselves

Practical conclusion:
- the repo now has a sharper and more testable capacity model than the older hybrid behavior
- docs had to explain the distinction between **capacity consumption** and **session price recording**

## 2.5 Phase 5/6 implementation finding

From `docs/PHASE5_6_IMPLEMENTATION.md`:
- optional background/central loops were hardened to avoid interfering with local runtime startup
- Windows scripts were made more deterministic
- local smoke tooling was added

Practical conclusion:
- the repo became materially easier to operate and validate locally
- but those changes still did not replace real Windows/Autodarts proof

---

## 3. Current source-of-truth decisions

These are the architecture decisions that now define the repo.

### 3.1 Protected local-core boundary

Treat these as source-of-truth modules:
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/routers/admin.py`
- `backend/services/session_pricing.py`
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`
- `backend/services/scheduler.py`
- `backend/models/__init__.py`
- `backend/runtime_features.py`
- `frontend/src/pages/kiosk/*`
- `frontend/src/pages/admin/*`

### 3.2 Authoritative gameplay rule

Gameplay truth comes from the observer lifecycle, not from kiosk optimism alone.

That means:
- operator/admin unlock creates the local session
- observer callback marks real start-of-play
- centralized finalization decides charge, keep-alive, lock, teardown

### 3.3 Revenue truth

Revenue is still derived from `Session.price_total`, i.e. booked sale data recorded on the session row.

That means:
- this repo has local operator accounting, not a payment ledger
- tests can validate summary logic
- they cannot prove external reconciliation or payment correctness, because no dedicated ledger exists yet

### 3.4 Validation truth

The repo now has meaningful in-process backend validation for the protected local core.

That validation does **not** prove:
- real Chrome/window behavior on Windows
- a live Autodarts account/session
- full-day operational stability on venue hardware

---

## 4. What was still wrong before phase 7/8/9

Before this final pass, the main problems were not just code issues. They were **understanding issues**:

1. core docs did not line up with the current runtime
2. historical tests were still presented like authoritative release gates
3. the protected local-core contract was only implicit
4. revenue/reporting semantics were under-documented
5. an external developer/operator had to reverse-engineer too much from scattered files

That is why phase 7/8/9 focused on:
- documentation completion
- targeted validation expansion
- explicit final reporting

---

## 5. What phase 7/8/9 adds on top of the preserved evidence

### 5.1 Documentation normalization

The following docs are now intended to be read together and stay consistent:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/ANALYSIS.md`
- `docs/AUTODARTS_ANALYSIS.md`
- `docs/CREDITS_PRICING.md`
- `docs/RUNBOOK.md`
- `docs/STATUS.md`
- `docs/TESTING.md`
- `CONTRIBUTING.md`
- `FINAL_REPORT.md`

### 5.2 Authoritative local-core validation suite

The most useful local test subset is now the focused in-process backend suite:
- `backend/tests/test_phase34_autodarts_triggers.py`
- `backend/tests/test_phase34_credits_pricing.py`
- `backend/tests/test_phase56_stability_installation.py`
- `backend/tests/test_phase789_local_core_validation.py`

This covers:
- authoritative vs assistive trigger handling
- board unlock/lock
- session lifecycle
- credit deduction / keep-alive / lock behavior
- per-player start charging
- local revenue summary behavior
- optional background-service startup hardening

### 5.3 Honest status framing

The repo is now described as:
- understandable
- locally testable
- coherent enough for handoff or continuation
- **not yet fully production-proven** without live Windows/Autodarts validation

---

## 6. Remaining risks that the evidence still points to

The preserved analysis still matters because these risks are real:
- observer/browser behavior needs live machine proof
- some UI/API surfaces remain broader than the validated core
- historical external/preview tests can still mislead contributors if treated as release gates
- revenue is still sale-summary logic, not ledger-backed accounting

Those risks are documented, not hidden.

---

## Bottom line

The repo's honest current shape is:

> a recovered, observer-first, local board runtime with optional adapters around it; now better documented and better validated in-process, but still awaiting real Windows/Autodarts confirmation.

That is the correct foundation for future work. Anything glossier would be fiction.
