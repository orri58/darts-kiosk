# Darts Kiosk — Release Notes v4.4.15

## Admin settings modularization continues

Darts Kiosk 4.4.15 continues the work started in 4.4.14 by pulling more of the oversized Admin settings page into dedicated section components.

## What changed

### 1. Language settings extracted
The language tab now lives in its own dedicated Admin settings section component.
This keeps a simple but important operator setting isolated and easier to evolve.

### 2. Match Sharing settings extracted
The QR match-sharing area now has its own section component instead of living directly inside the main monolithic settings page.

### 3. PWA / installable app settings extracted
The PWA/App configuration tab has been moved into its own dedicated section component, reducing central page complexity and making future app/installation improvements easier to manage.

### 4. Kiosk Control settings extracted
The Kiosk Control area, including post-match delay and Autodarts desktop path/auto-start controls, now lives in its own dedicated section component.

## Why this matters

This release continues the shift from a large feature pile in `Settings.js` toward a more professional, modular admin surface.
That reduces regression risk and makes future work — especially deeper grouping, draft/preview flows, and additional customization controls — much safer to implement.

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q backend/tests/test_settings_contract.py
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- focused settings contract regression suite passed (`4 passed`)
- frontend production build passed
- release artifacts were rebuilt for `v4.4.15`
