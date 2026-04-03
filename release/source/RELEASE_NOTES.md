# Darts Kiosk — Release Notes v4.2.0

## Revenue correctness, operator-first admin redesign, kiosk branding split

Darts Kiosk 4.2.0 is a product pass focused on real venue operation.
The release closes a revenue bug around top-ups, restructures the admin experience for operators, and begins the proper separation between kiosk presentation and admin presentation.

## Highlights

### 1. Top-ups now belong to revenue
- additional credits / time extensions can now be booked as real session charges
- revenue and reports no longer only reflect the initial unlock sale
- the accounting direction is now compatible with proper audit-style session booking history
- dashboard top-up flow shows the booked amount directly

### 2. Admin panel is less noisy and more operator-first
- dashboard header and KPI area were reduced so the board controls dominate instead of the chrome
- dashboard now keeps one clearer primary action flow with smaller summary cards and a less showy hero
- shared admin page shell was softened to look more like a product surface and less like an internal control room
- top-up dialog now clearly shows the booked amount

### 3. Admin theme is now separated from kiosk theme
- theme selection is no longer effectively one global palette for every surface
- admin and kiosk can now use different palettes
- kiosk branding remains venue-facing while admin can stay calmer and more operational

### 4. Kiosk branding is now actually visible
- kiosk screens now render the configured logo through a shared header component
- locked screen, setup, in-game, and match-result flows now share the branding header direction
- pairing code position and some lockscreen behavior are now controlled via kiosk layout settings

### 5. New kiosk surface settings direction
- branding is now moving toward identity-only responsibility: name, subtitle, logo
- kiosk theme, admin theme, and kiosk layout now have separate setting buckets
- kiosk layout uses practical preset/slot-style settings instead of a fragile freeform editor approach

## Validation performed for this release

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
```

Observed result:
- backend/agent compile check passed
- focused backend suite passed (37 tests)
- frontend production build passed cleanly

## Still worth validating on hardware
- mobile admin ergonomics on the real bartender workflow
- kiosk branding/layout behavior on the actual display hardware
- update/install flow after more UI cleanup in a later pass
- deeper accounting/reporting breakdowns if session charges are expanded further
