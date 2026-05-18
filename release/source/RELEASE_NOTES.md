# Darts Kiosk — Release Notes v4.4.20

## Manual unlock without credits

This release adds a new explicit admin unlock option for boards that should be opened without charging credits or time.

## What changed

### 1. New manual unlock mode in Admin
Operators can now choose between a normal billed unlock and a **manual unlock without credits**.

Manual unlock means:
- no credits are consumed
- no time window is started
- the board remains open until staff manually lock it again

### 2. Backend session handling understands manual unlocks
Manual unlock sessions are now tagged explicitly so normal credit/time consumption logic does not block or charge those sessions.

### 3. Kiosk UI shows the correct mode
The kiosk setup and in-game screens now show that the board is manually unlocked instead of pretending the session runs on credits or time.

## Validation performed

Executed successfully:

```bash
.venv/bin/python -m pytest -q backend/tests/test_manual_unlock_pricing.py tests/test_runtime_field_evidence.py tests/test_runtime_maintenance_closed_loop.py backend/tests/test_central_security_hardening.py
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- focused backend/manual-unlock and readiness/security suites passed
- frontend production build passed
- release artifacts were rebuilt for `v4.4.20`
