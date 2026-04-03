# Darts Kiosk — Release Notes v4.1.0

## Productization pass: installer, update UX, admin cleanup

Darts Kiosk 4.1.0 is a product-shaping release.
The focus is not on adding new central-heavy scope, but on making the local board-PC runtime feel and behave more like a real installable product.

## Highlights

### 1. Better Windows installation path
- new `release/windows/install.bat` provides a one-click bootstrap for a board PC
- `setup_windows.bat` now builds the frontend during setup instead of stopping at dependency install
- Windows setup/runtime now aligns around the real local stack: backend, agent, frontend build, logs, downloads, and app backups
- generated Windows bundle examples now include the correct GitHub repo and agent port defaults

### 2. Agent startup and health are cleaner
- Windows startup now prepares and launches the agent more deliberately
- agent defaults now align on port `8003`
- agent health monitoring now checks the actual status endpoint and normalizes malformed agent URLs
- pairing code visibility is now conditional instead of always-on kiosk clutter

### 3. Update flow is closer to a real product
- System → Updates now exposes a direct **Jetzt installieren** path for Windows release packages
- the flow is now framed as: backup → download → validate → install → restart
- trailing-slash repo config issues (`owner/repo/`) no longer break update checks

### 4. Operator UI is less noisy
- admin sidebar is slimmer and less label-heavy
- long titles/descriptions wrap more safely instead of crashing into edges
- dashboard control area keeps boards visible after unlock so top-ups are immediate
- system/update surfaces push the primary action forward instead of burying it in explanation text
- kiosk lockscreen removes admin/footer noise and shows pairing only when needed

### 5. Board bootstrap behavior is saner
- startup no longer recreates `BOARD-2`
- the local-first default is a single seeded board (`BOARD-1`), with additional boards created intentionally by the operator

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
cd .. && bash release/build_release.sh
```

Observed result:
- focused backend suite passed
- frontend production build passed cleanly
- release artifacts were generated successfully for Windows/Linux/source

## Still not proven by this repo-side pass

Real-machine validation is still required for:
- a full Windows board-PC installation from a fresh host
- long-running Autodarts desktop/session behavior on venue hardware
- live update/rollback behavior on a real machine after the new direct-install flow
