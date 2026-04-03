# Darts Kiosk — Release Notes v4.0.0-recovery

## Local-first hardening / release polish

This release is not about adding new central-heavy product scope.
It is mainly a cleanup and stabilization release around the current board-PC baseline.

### Highlights

#### 1. Local operator surface is clearer
- admin runtime surfaces are more deliberately split between **Health**, **System**, and **Device Ops**
- diagnostics and support-bundle contents are visible before export
- operator messaging is more explicit about what is local-first vs optional

#### 2. Credits-only active flow stays the baseline
- active local unlock flow stays credits-first
- authoritative billing still happens on real match start using the actual player situation
- older time/game wording was further reduced where it was misleading in the main operator path

#### 3. Packaging/release surface is less noisy
- Windows setup now installs frontend dependencies via **npm**, matching the shared release build
- release automation is aligned around the shared `release/build_release.sh` script
- stale version-pinned release docs/examples were refreshed to the current repo/product shape
- Windows/manual deployment docs now describe the local-first board-PC path instead of implying central dependency as the norm

#### 4. Diagnostics/operator polish
- start/smoke helper messaging now points operators at the right logs
- Windows helper output emphasizes that local play does not depend on external reachability
- agent runtime/version output now follows the repo `VERSION` file instead of stale hardcoded version strings

## Validation performed for this repo-side pass

Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend agent
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
cd .. && bash release/build_release.sh
```

Observed result:
- backend + agent compile cleanly
- focused backend suite passed
- frontend production build passed cleanly
- release artifacts were generated successfully for Windows/Linux/source

## Still not proven by this repo-side release pass

Real-machine validation is still required for:
- actual Windows board-PC installation
- Autodarts login/profile handling on the target machine
- kiosk/window focus behavior on real hardware
- install/update/rollback behavior using the packaged release on a real machine
