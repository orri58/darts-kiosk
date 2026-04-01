# Testing

This project has a lot of historical test artifacts. Not all of them are equally useful.

This document defines the **current authoritative local-core validation path**.

## 1. Test strategy

The protected baseline is validated with focused backend tests that run entirely in-process against isolated SQLite databases or directly exercised services.

Why this is the current best fit:
- the critical logic is backend lifecycle/state logic
- it avoids pretending preview URLs or stale environments are trustworthy gates
- it lets us validate local-core behavior without needing a real Windows box for every change

## 2. Authoritative test subset

Run from the repo root:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
```

Current observed result for this documentation pass:
- `21 passed`

## 3. What each suite proves

### `backend/tests/test_phase34_autodarts_triggers.py`
Validates:
- authoritative finish classification
- assistive finish classification
- pending-finish upgrade behavior
- delete/reset staying diagnostic unless qualified
- console/DOM finish hints staying non-authoritative

### `backend/tests/test_phase34_credits_pricing.py`
Validates:
- `per_player` start charge for 1 or multiple players
- no double charge on repeated authoritative starts
- `per_game` authoritative finish consumes one credit
- abort-before-start does not consume `per_player` capacity

### `backend/tests/test_phase56_stability_installation.py`
Validates:
- `ConfigSyncClient.start()` is non-blocking
- `ActionPoller.start()` is non-blocking
- remote board updates use the correct WebSocket broadcast signature
- central heartbeat health payload uses the actual health monitor snapshot

### `backend/tests/test_phase789_local_core_validation.py`
Validates:
- board unlock -> active session -> unlocked board
- board lock -> cancelled session -> locked board
- kiosk start-game session registration
- authoritative `per_game` finish keep-alive vs final lock
- assistive finish hint does not consume a `per_game` credit
- `per_player` start charge happens once and finish does not double-charge
- revenue summary excludes active sessions and tolerates nullable recorded prices

## 4. What this subset does **not** prove

It does not prove:
- real Windows focus/foreground behavior
- real Playwright/Chrome profile stability on a board PC
- live Autodarts traffic in the wild
- operator ergonomics on a touch/kiosk deployment
- full frontend rendering behavior across all pages
- long-running soak stability

Those require live validation.

## 5. Live validation checklist

After code changes that affect runtime behavior, perform at least one real-machine pass:

1. `release/windows/setup_windows.bat`
2. `release/windows/setup_profile.bat`
3. `release/windows/start.bat`
4. `release/windows/smoke_test.bat`
5. unlock board
6. observe real match start
7. observe real match finish
8. verify next-game or lock behavior matches pricing mode
9. test manual lock
10. restart the machine/app path if possible

## 6. Historical / non-authoritative tests

These files still exist and may still be useful as historical artifacts or ad-hoc smoke checks, but they are **not** the main release gate for the protected local core:
- `backend/tests/test_v400_recovery_baseline.py`
- `backend/tests/test_layer_a_integration.py`
- preview/deployment-specific request suites under older regression names

Why they are not the main gate:
- some target external preview URLs or old assumptions
- some describe recovery states more than current architecture
- some are broader but less reliable for day-to-day local-core changes

## 7. Recommended workflow for contributors

### For docs-only changes
- read the current docs set for consistency
- no mandatory runtime test unless behavior claims changed

### For local-core backend changes
Run the authoritative subset above.

### For Windows/operator changes
Run the authoritative subset **and** a live Windows smoke pass.

### For observer/Autodarts changes
Run the authoritative subset **and** a live Autodarts validation pass before strong claims.

## 8. Failure policy

If one of the authoritative tests fails:
- do not wave it away with “works on the real board probably”
- fix the code or update the docs/status to explain the limitation
- if a behavior cannot be reproduced in-process but is real-machine-only, document the exact gap

The goal here is not to make the suite look pretty. It is to keep the protected local core understandable and trustworthy.
