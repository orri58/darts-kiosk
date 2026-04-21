# Darts Kiosk — Release Notes v4.4.13

## Customization profiles for professional admin workflows

Darts Kiosk 4.4.13 builds on the new settings-contract foundation and adds practical admin tooling for moving, backing up, restoring, and resetting kiosk/admin customization safely.

## What changed

### 1. Customization profile export
Admin settings can now export the current kiosk/admin customization state as a JSON profile.
This gives operators a clean backup and rollout format for venue-specific styling/content setups.

### 2. Customization profile import
The exported JSON profile can now be imported back into the system.
Imports run through the normalized settings contract, so the incoming bundle is sanitized and restored as a full contract-managed configuration set.

### 3. Customization reset
Admin settings now expose a clean reset action for the contract-managed customization family.
That makes it much easier to return a kiosk/admin setup to a known-good baseline without manually editing lots of separate fields.

### 4. Better admin workflow foundation
This is a practical professionalization step for operators:
- backup current look & feel
- clone venue configuration to another device
- test bold changes and recover quickly
- restore baseline customization without database surgery

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q backend/tests/test_settings_contract.py
python -m compileall backend
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- focused settings contract regression suite passed (`4 passed`)
- backend compile sanity passed
- frontend production build passed
- release artifacts were rebuilt for `v4.4.13`
