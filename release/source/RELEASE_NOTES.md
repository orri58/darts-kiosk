# Darts Kiosk — Release Notes v4.2.1

## Patch release: fix direct update downloads

Darts Kiosk 4.2.1 is a targeted patch release for the update pipeline.
The goal is simple: direct installs from the admin update screen must fetch a real release package and reject broken download responses early.

## What changed

### 1. Correct asset URL preference for public releases
- direct Windows install now prefers the public release asset download URL
- public repositories no longer accidentally route installs through the GitHub API asset endpoint
- if an API asset URL still slips through, the backend rewrites it back to the matching public download URL when possible

### 2. Download validation before install
- downloaded `.zip` assets are checked for a valid ZIP header
- downloaded `.gz` assets are checked for a valid GZip header
- bad HTML/JSON/download-error payloads are rejected before they can be treated as update packages

### 3. No behavior change intended outside updates
- leaderboard remains local for now
- kiosk/admin feature set from 4.2.0 stays unchanged

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- backend compile check passed
- focused backend suite passed
- frontend production build passed
- release artifacts rebuilt successfully
