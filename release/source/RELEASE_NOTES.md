# Darts Kiosk — Release Notes v4.5.0

## A real consolidated release

This release rolls up the larger local product, control-plane, and field-readiness work that was still sitting outside the previous narrower cut.

## What changed

### 1. Central control plane is structurally cleaner
A large portion of the old `central_server/server.py` monolith has been split into dedicated route and service seams for remote actions, trust, config, licensing token flows, admin CRUD, websocket status/device handshake, device details, and telemetry helpers.

### 2. Admin / Operator / Portal behave more like one product family
Shared shell, data/page, detail/dashboard, fleet, and device/commercial drill-in primitives now drive much more of the visible product surface, reducing the old generation gaps between admin, operator, and portal.

### 3. Field-readiness evidence is stronger
Board-PC validation now has explicit preflight and postflight capture, certification exports, RC evidence artifacts, and support-bundle inclusion so real machine runs are easier to execute, review, and compare.

### 4. Manual unlock without credits
Admins can now unlock a board without credits or time as a dedicated option. The board stays manually unlocked until staff lock it again, and the kiosk surfaces show that mode correctly.

## Validation performed

Executed successfully:

```bash
.venv/bin/python -m pytest -q backend/tests/test_central_security_hardening.py tests/test_device_trust.py tests/test_runtime_field_evidence.py tests/test_runtime_maintenance_closed_loop.py backend/tests/test_manual_unlock_pricing.py
cd frontend && CI=true npm test -- --runInBand --watchAll=false --runTestsByPath src/pages/operator/operatorCommercialFlow.test.js
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- focused backend security/trust/runtime/manual-unlock suites passed
- focused frontend operator flow test passed
- frontend production build passed
- release artifacts were rebuilt for `v4.5.0`
