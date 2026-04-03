# Darts Kiosk — Release Notes v4.2.2

## Patch release: local leaderboard reliability

Darts Kiosk 4.2.2 is a focused patch for local stats and leaderboard reliability on standalone devices.

## What changed

### 1. Local match results are now saved independently of match sharing
- local leaderboard/statistics are based on `MatchResult` entries
- previously those results could be missing unless certain sharing/session-end conditions were met
- completed local matches now save a result record even if:
  - match sharing is disabled
  - the session still has remaining credits/time

### 2. Better local consistency across devices
- standalone devices should now build their own local leaderboard much more reliably
- player names and rankings will still remain local per device for now, as requested

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
```

Observed result:
- backend compile check passed
- focused backend suite passed (37 tests)

## Scope note
- leaderboard remains local-only for now
- central/shared leaderboard behavior can be expanded later once the central server architecture returns
