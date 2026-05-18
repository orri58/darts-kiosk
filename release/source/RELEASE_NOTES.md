# Darts Kiosk — Release Notes v4.4.21

## Full follow-up release after the too-narrow 4.4.20 cut

`v4.4.20` only shipped the manual-unlock slice. This release packages the broader coherent work that was still sitting in the local tree.

## What is included

### 1. Central server modularization actually ships
The central server is no longer effectively a giant single-file change waiting in the wings.

This release includes the extracted route/service layout for:
- config profiles
- effective device config
- device detail reads
- device remote actions
- trust enrollment and trust/detail shaping
- licensing token flows
- websocket/device status helpers
- shared audit/auth helpers

That means the broader central control-plane work is now part of the release instead of being stranded locally.

### 2. Operator and portal surfaces got the broader product-shell refresh
A new shared product-shell layer now backs the main operator/portal experience, and the updated release includes the broader pending UI work across:
- operator dashboard, licenses, devices, customers, locations, users, audit, and layout
- portal dashboard, devices, layouts, and license/device detail flows
- shared product data/detail/system display primitives

The result is a more coherent operational/commercial surface instead of the narrower one-feature 4.4.20 cut.

### 3. Runtime field-handoff/certification tooling is included
This release also includes the pending runtime-support lane work:
- board-PC certification runbook
- RC field-evidence checklist
- Windows preflight/postflight capture scripts
- runtime maintenance/readiness documentation improvements
- closed-loop runtime evidence test coverage already present in the tree

## Release-prep fixes folded into this cut

During release validation two real issues were repaired:
- pending device remote actions now evaluate TTL against the injected validation clock, avoiding false expiry in deterministic runs
- session pricing restored compatibility with the older manual-unlock regression contract used by the repo’s legacy test lane

## Validation performed

Executed successfully:

```bash
.venv/bin/python -m pytest -q \
  tests/test_device_remote_action_service.py \
  tests/test_device_remote_action_router_structure.py \
  tests/test_remote_action_service_summary.py \
  tests/test_remote_action_router_structure.py \
  backend/tests/test_central_security_hardening.py \
  tests/test_device_trust.py \
  tests/test_config_profiles_service.py \
  tests/test_effective_config_service.py \
  tests/test_licensing_token_service.py \
  tests/test_device_detail_service.py \
  tests/test_device_trust_detail_service.py \
  tests/test_device_trust_enrollment_service.py \
  tests/test_ws_status_service.py \
  tests/test_runtime_field_evidence.py \
  tests/test_runtime_maintenance_closed_loop.py

.venv/bin/python -m pytest -q backend/tests/test_manual_unlock_pricing.py
.venv/bin/python -m compileall central_server release/runtime_windows
cd frontend && npm run build
```

Observed result:
- focused central/runtime regression suite passed: **166 passed**
- manual-unlock compatibility suite passed: **2 passed**
- compile sanity passed for `central_server` and `release/runtime_windows`
- frontend production build passed

Important honesty note:
- the repo’s broad historical `pytest -q` sweep is still not generally green
- this release is validated on the strongest realistic focused lanes for the shipped scope, consistent with the repo’s own readiness/testing docs
