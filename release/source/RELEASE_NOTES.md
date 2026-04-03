# Darts Kiosk — Release Notes v4.2.3

## Hardening patch: setup, update extraction, auth boundaries

Darts Kiosk 4.2.3 is a security and hardening patch for the local product.
It focuses on preventing takeover of already-initialized systems, rejecting unsafe update archives, and removing a few unnecessarily weak defaults.

## What changed

### 1. Setup cannot be rerun after initialization
- `POST /api/setup/complete` now refuses to run once setup has already been completed
- this closes the biggest local/LAN takeover hole for initialized installs

### 2. Update ZIP extraction is hardened
- update staging now validates ZIP members before extraction
- absolute paths and `..` traversal entries are rejected
- unsafe archives are refused before files are unpacked into staging

### 3. Secret handling is less predictable
- JWT and agent auth no longer fall back to static hardcoded secrets
- if real secrets are missing, the runtime now uses ephemeral generated secrets instead of predictable defaults

### 4. Rebind-device action is stricter
- device rebind now requires superadmin rather than any admin user

### 5. CSV export no longer needs token-in-URL
- admin reports now export CSV through authenticated header-based download flow
- this avoids leaking JWTs into copied URLs, browser history, or logs

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
```

Observed result:
- backend compile check passed
- focused backend suite passed (39 tests)
- frontend production build passed

## Still worth doing next
- safer SQLite backup creation
- lifecycle unification for scheduler-triggered session endings
- more explicit support/trust indicators in admin UI
