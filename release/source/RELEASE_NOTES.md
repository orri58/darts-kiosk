# Darts Kiosk — Release Notes v4.4.17

## Central / Operator hardening and release-grade workflow maturity

Darts Kiosk 4.4.17 is a central/operator release.
This wave tightens what central is actually willing to do remotely, makes approval and audit handling much more explicit, and gives operators a clearer surface for seeing trust/commercial posture without pretending those advisory signals are local enforcement.

In short: less ambiguity, better reviewability, and fewer ways for the operator UI to drift away from the real central policy.

## What changed

### 1. Remote actions are now governed by an explicit central policy
The release introduces a dedicated remote-action policy layer for central.
That policy now defines:
- the action catalog that is actually shippable
- which actions require approval
- which legacy/high-risk actions are intentionally blocked
- expiry behavior and delivery guards

This matters because remote execution should be boringly predictable.
If the UI offers actions central no longer accepts, that is not flexibility — that is a support bug waiting to happen.

### 2. Approval, review, and audit flow grew up
Remote actions now carry richer lifecycle state instead of only a thin pending/acked model.
The central side now tracks request, approval, delivery, finalization, reviewer metadata, and outcome signals more explicitly.

That gives operators and reviewers a much clearer answer to questions like:
- what is waiting for approval
- what was refused
- what was delivered
- what expired
- who reviewed it and why

### 3. Advisory trust/commercial posture is visible where operators actually work
This version adds a central advisory posture rollup that combines:
- trust status
- credential state
- lease state
- license state
- replacement/lifecycle findings

Those signals are then surfaced into operator-facing views so staff can spot degraded or blocked posture faster.
Important nuance: this is intentionally advisory/read-only central posture, not a surprise local enforcement switch.

### 4. The operator surface is more coherent
The operator app now has stronger auth/session handling and a dedicated Remote Actions page.
Dashboard/layout/device/license surfaces were aligned so the operator experience reflects the tightened central policy rather than stale assumptions.

That includes making blocked board/session actions visible for history/audit context without falsely suggesting they remain executable.

## Why this matters

This release is mostly about operational trust.
When a system can issue remote actions, show posture, and mediate approvals, the worst possible state is half-consistent behavior where backend policy, audit trail, and UI vocabulary disagree.

Version 4.4.17 narrows that gap substantially.
It is a safer and more honest release: central does what it says, operators see what is really true, and the release artifacts match that behavior.

## Validation performed for this release

Executed successfully:

```bash
./.venv/bin/python -m pytest backend/tests/test_central_security_hardening.py -q
./.venv/bin/python -m compileall central_server backend
cd frontend && npm run build
cd .. && bash release/build_release.sh
```

Observed result:
- focused backend central/operator regression suite passed (`82 passed`)
- Python compile sanity passed for `central_server` and `backend`
- frontend production build passed cleanly
- release artifacts were rebuilt for `v4.4.17`
- release packages are ready for Windows, Linux, and Source distribution
