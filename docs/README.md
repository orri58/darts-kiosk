# Docs Map

This folder has grown into a mix of:
- **current source-of-truth docs**
- **implementation plans**
- **historical wave notes**
- **analysis / audit artifacts**

If you are new here, do **not** start by reading every file in alphabetical order.
That way lies madness, stale assumptions, and at least one avoidable coffee overdose.

Use this map instead.

---

## 1. Start here

If you need the fastest real orientation, read these in order:

1. `../README.md`
2. `EXTERNAL_DEVELOPER_HANDOFF.md`
3. `TEST_READINESS.md`
4. `../EXECUTION_BOARD.md`
5. `ARCHITECTURE.md`

That gets you:
- what the project is
- local core vs central control plane
- current real status
- what is healthy vs not
- where the next practical work should happen

---

## 2. Best docs by purpose

## I want the current plain-English truth
Read:
- `EXTERNAL_DEVELOPER_HANDOFF.md`
- `TEST_READINESS.md`
- `STATUS.md`

Use these when you want the current story without reconstructing it from wave files.

## I want to understand the runtime architecture
Read:
- `ARCHITECTURE.md`
- `CREDITS_PRICING.md`
- `RUNBOOK.md`
- `TESTING.md`

Use these when working on:
- board/session lifecycle
- kiosk flow
- unlock / pricing / match handling
- operator/runtime behavior

## I want to understand the central rebuild direction
Read:
- `CENTRAL_REBUILD_MASTERPLAN.md`
- `IMPLEMENTATION_PLAN.md`
- `IMPLEMENTATION_GOVERNANCE.md`
- `CENTRAL_CONTRACT.md`

Use these when working on:
- central auth
- central control-plane scope
- contracts between runtime and central
- phased implementation strategy

## I want device trust / licensing context
Read:
- `DEVICE_TRUST_MODEL.md`
- `ACCESS_CONTROL_MATRIX.md`
- `COMMERCIAL_LEDGER_FLOW.md`
- `DEVICE_FOOTPRINT_POLICY.md`

Use these when working on:
- enrollment / trust
- device identity
- anti-cloning assumptions
- licensing / lease semantics
- what should actually live on a production device

## I want packaging / board-PC drill context
Read:
- `TEST_READINESS.md`
- `DEVICE_PACKAGING_AUDIT_2026-04-13.md`
- latest `DEVICE_RUNTIME_PACKAGE_WAVE*.md` files only

Recommended starting point for this lane:
- `DEVICE_RUNTIME_PACKAGE_WAVE34.md`
- `DEVICE_RUNTIME_PACKAGE_WAVE35.md`
- `DEVICE_RUNTIME_PACKAGE_WAVE36.md`
- `DEVICE_RUNTIME_PACKAGE_WAVE37.md`
- `DEVICE_RUNTIME_PACKAGE_WAVE38.md`

Do **not** start by reading all 38 waves unless you enjoy self-inflicted archaeology.
Use the newest waves first, then go backwards only if something is unclear.

## I want historical analysis / audits
Read as needed:
- `ANALYSIS.md`
- `ANALYSIS_BASELINE.md`
- `AUTODARTS_ANALYSIS.md`
- `AUTODARTS_TRIGGERS.md`
- `LOCAL_CORE_AUDIT.md`

These are useful when you need deeper background, not as first-contact docs.

---

## 3. Source-of-truth vs history

## Current source-of-truth docs
These are the most important ongoing docs:
- `EXTERNAL_DEVELOPER_HANDOFF.md`
- `TEST_READINESS.md`
- `ARCHITECTURE.md`
- `CENTRAL_REBUILD_MASTERPLAN.md`
- `IMPLEMENTATION_PLAN.md`
- `CENTRAL_CONTRACT.md`
- `DEVICE_TRUST_MODEL.md`
- `RUNBOOK.md`
- `TESTING.md`

## Mostly historical / wave-log docs
Treat these as implementation history and supporting detail:
- `DEVICE_RUNTIME_PACKAGE_WAVE*.md`
- `PHASE2_IMPLEMENTATION.md`
- `PHASE3_4_IMPLEMENTATION.md`
- `PHASE5_6_IMPLEMENTATION.md`
- dated operational pass notes
- older analysis snapshots

These are useful, but they are **not** the best first entry point.

---

## 4. Suggested reading paths

## A) New external developer
Read in this order:
1. `../README.md`
2. `EXTERNAL_DEVELOPER_HANDOFF.md`
3. `TEST_READINESS.md`
4. `ARCHITECTURE.md`
5. `CENTRAL_REBUILD_MASTERPLAN.md`
6. `DEVICE_TRUST_MODEL.md`

## B) Local runtime / kiosk work
Read in this order:
1. `ARCHITECTURE.md`
2. `CREDITS_PRICING.md`
3. `RUNBOOK.md`
4. `TESTING.md`
5. `STATUS.md`

## C) Central / trust work
Read in this order:
1. `EXTERNAL_DEVELOPER_HANDOFF.md`
2. `TEST_READINESS.md`
3. `CENTRAL_REBUILD_MASTERPLAN.md`
4. `IMPLEMENTATION_PLAN.md`
5. `CENTRAL_CONTRACT.md`
6. `DEVICE_TRUST_MODEL.md`

## D) Runtime packaging / field drill work
Read in this order:
1. `TEST_READINESS.md`
2. `../EXECUTION_BOARD.md`
3. latest `DEVICE_RUNTIME_PACKAGE_WAVE*.md`
4. `RUNBOOK.md`
5. `DEVICE_FOOTPRINT_POLICY.md`

---

## 5. Practical rules for contributors

- Prefer the **current summary docs** before diving into wave history.
- When changing contracts, update **tests + docs in the same branch**.
- When a doc becomes the best current explanation, link to it from `../README.md` or from here.
- If a file is mostly history, treat it as history instead of pretending it is the active truth.

---

## 6. Short version

If you only remember one thing:

> Read the summary docs first. Use the wave files as supporting evidence, not as the front door.
