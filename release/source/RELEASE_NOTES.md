# Darts Kiosk — Release Notes v4.4.12

## Settings system foundation for professional kiosk/admin customization

Darts Kiosk 4.4.12 does not just add more knobs — it strengthens the configuration foundation that future kiosk and admin customization will build on.

## What changed

### 1. Normalized customization bundle
A new backend settings read model now exposes a merged/defaulted customization bundle for the core kiosk/admin settings family.
This gives the frontend a more consistent payload instead of many partially-shaped JSON blobs.

Covered settings include:
- branding
- pricing
- palettes
- kiosk theme
- admin theme
- kiosk layout
- kiosk texts
- PWA config
- lock-screen QR
- overlay config
- post-match delay
- language
- match sharing

### 2. Settings contract layer
A dedicated settings-contract service now normalizes and sanitizes contract-managed settings before they are persisted or returned.
That means:
- nested defaults are filled reliably
- invalid enum values fall back safely
- kiosk/admin settings drift less over time
- future settings expansion has a cleaner backend foundation

### 3. Frontend settings context cleanup
The frontend settings context now consumes the normalized bundle directly and exposes dedicated update actions for:
- kiosk texts
- PWA config
- lock-screen QR

This reduces ad hoc settings patchwork and moves the project toward a cleaner configuration architecture.

### 4. Better config-apply compatibility
Contract-managed settings are now normalized when applied from synced/imported config sources, improving consistency across update and config workflows.

## Why this release matters

This is the first real foundation step toward making the kiosk/admin system behave more like a professional configurable product instead of an accumulation of one-off settings.
It is intentionally a structural release so later work — modular settings UI, better previews, stronger branding/layout composition, and presets — can land on a more stable base.

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
- focused settings contract regression suite passed (`3 passed`)
- backend compile sanity passed
- frontend production build passed
- release artifacts were rebuilt for `v4.4.12`
