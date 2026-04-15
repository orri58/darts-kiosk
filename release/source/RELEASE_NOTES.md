# Darts Kiosk — Release Notes v4.4.10

## Credit reconciliation fix for late player detection

Darts Kiosk 4.4.10 fixes a real per-player credit issue that showed up in live board-PC testing.
The affected case was a two-player match that first started through an early fallback path as if only one player was present and only later got corrected to the real authoritative player count.

## What changed

### 1. Late player reconciliation now uses the missing delta
- per-player authoritative start billing now calculates how many player credits were already effectively consumed
- if the player count is corrected later, the system now only charges or blocks for the missing delta
- this prevents the kiosk from incorrectly demanding the full player-count total again after one credit had already effectively been accounted for

### 2. Pending-credit overlay wording is clearer
- the overlay wording now focuses on the missing additional credits instead of reading like the full total must be paid again
- this reduces operator and player confusion in blocked-pending cases

### 3. Bull-off / non-bull-off behavior is now consistent
- the bug was easier to see in non-bull-off starts because the fallback start happened earlier there
- with the reconciliation fix, both paths now align correctly around the same per-player credit logic

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m pytest -q backend/tests/test_phase34_credits_pricing.py
bash release/build_release.sh
```

Observed result:
- focused pricing regression suite passed (`15 passed`)
- release artifacts were rebuilt for `v4.4.10`
- the fix was derived from and checked against a real support bundle from field testing
