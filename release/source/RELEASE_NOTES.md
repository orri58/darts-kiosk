# Darts Kiosk — Release Notes v4.4.14

## First real admin-panel modularization block

Darts Kiosk 4.4.14 starts breaking the oversized Admin settings page into dedicated section components instead of keeping all settings logic and rendering inside one giant file.

## What changed

### 1. Branding settings extracted
The Branding area now lives in its own dedicated Admin settings section component.
This includes:
- logo upload/removal
- venue name/subtitle
- kiosk branding layout controls
- admin-theme and lock-screen placement controls tied to branding/layout

### 2. Pricing settings extracted
The pricing area has been moved into its own dedicated section component.
This keeps commercial controls easier to evolve without making the main settings page even harder to maintain.

### 3. Customization profiles extracted
The new export/import/reset profile workflow is also now isolated in its own section component.
That gives us a cleaner foundation for further professional admin tooling.

## Why this matters

This release is less about visible end-user features and more about making the Admin panel behave like a product that can keep growing safely.
The goal is to stop treating `Settings.js` as a dumping ground and move toward a real module-based settings surface.

This is the first extraction block, not the end state.
More sections can now be moved out incrementally with lower regression risk.

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
- release artifacts were rebuilt for `v4.4.14`
