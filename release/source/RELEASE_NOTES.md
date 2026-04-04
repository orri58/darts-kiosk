# Darts Kiosk — Release Notes v4.3.0

## Stability wave 1: safer backups and stronger realtime foundations

Darts Kiosk 4.3.0 starts the dedicated stability phase after the 4.2.x product/hardening releases.
This first wave focuses on two practical areas that matter on real board PCs: safer SQLite backups and more resilient realtime transport behavior.

## What changed

### 1. SQLite backups are now snapshot-based and validated
- backup creation now uses SQLite's native backup mechanism instead of copying the live DB file directly
- backup snapshots are validated with `PRAGMA integrity_check`
- restore flow validates backup contents before replacing the live database
- this improves confidence in recovery, support exports, and pre-update safety

### 2. WebSocket fanout is more robust
- websocket broadcast fanout now avoids holding the connection lock while awaiting every client send
- dead/slow sockets are pruned more safely
- this reduces the chance that one problematic client degrades all other realtime consumers

### 3. Realtime transport foundation is stronger
- board websocket hook now uses reconnect backoff and heartbeat behavior
- server websocket endpoint now understands `ping` / `pong`
- this gives kiosk/admin realtime transport a more reliable base for the next stability passes

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend
python -m pytest -q \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
```

Observed result:
- backend compile check passed
- focused backend validation suite passed
- frontend production build passed

## Still planned for the next stability pass
- unified session-end lifecycle between scheduler and kiosk finalize path
- adaptive kiosk polling / more push-first board state handling
- stricter support-bundle/runtime diagnostics flow
