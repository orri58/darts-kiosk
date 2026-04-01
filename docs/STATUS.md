# Status

## Executive summary

The repo is now in a **coherent local-core state**:
- core docs are aligned with the current runtime
- the protected local board/session/autodarts/pricing flows have focused in-process coverage
- Windows operator scripts and smoke tooling are documented
- central/adapter code is described as optional rather than magically absent

That said, this is **not yet fully production-proven**.

The missing proof is outside this sandbox:
- no real Windows board PC validation here
- no live Autodarts session exercised here
- no long-duration venue-style soak test here

## What is currently validated

Validated in-process with the focused backend subset:
- board unlock creates an active session and unlocks the board
- board lock cancels the active session and returns the board to `locked`
- kiosk start-game registration persists player names and count
- authoritative Autodarts start charges `per_player` once and only once
- authoritative finish charges `per_game` once per completed game
- assistive finish hints do not consume `per_game` credits
- abort-before-start does not consume `per_player` capacity
- keep-alive vs teardown follows remaining capacity
- optional adapter/background services start non-blockingly
- revenue summary excludes active sessions and handles nullable sale totals safely

## What was actually run

Executed command:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
```

Observed result:
- `21 passed`

## What those tests cover

### Trigger authority
- `backend/tests/test_phase34_autodarts_triggers.py`
- validates authoritative vs assistive signal handling inside observer logic

### Pricing / credits core
- `backend/tests/test_phase34_credits_pricing.py`
- validates per-player start billing, per-game finish billing, and abort behavior

### Optional adapter hardening
- `backend/tests/test_phase56_stability_installation.py`
- validates non-blocking startup and fixed WS broadcast usage for optional sync/poller paths

### Local-core lifecycle validation
- `backend/tests/test_phase789_local_core_validation.py`
- validates unlock/lock, session lifecycle, authoritative start/finish behavior, assistive no-charge behavior, and revenue summary behavior

## What is only partially validated

These areas are better documented and partly simulated, but not field-proven here:
- persistent Chrome profile reuse on a real board PC
- window focus / foreground choreography between kiosk and Autodarts on Windows
- live Autodarts account state, reconnects, and real WS event variations
- real operator workflows around every remaining legacy/optional surface
- accounting expectations beyond local session-sale summaries

## What still needs live validation before strong production claims

Minimum live checklist:
1. real Windows machine install via `release/windows/setup_windows.bat`
2. real Autodarts login/profile prep via `release/windows/setup_profile.bat`
3. successful `start.bat` + `smoke_test.bat`
4. real unlock on the target board
5. real authoritative match start observed
6. real authoritative finish observed
7. one keep-alive case (`per_game` credits remain)
8. one session-end case (credits exhausted or time expired)
9. manual lock during active session
10. restart/recovery behavior after a stop/start cycle

## Production-readiness statement

### Production-ready enough for
- developer handoff
- continued local-core stabilization work
- code review / maintenance by an external engineer
- controlled lab validation of backend behavior
- preparing a real board-PC validation pass

### Not yet proven enough for
- blanket “deploy everywhere” claims
- unattended venue rollout without a real-machine test pass
- claiming long-running Autodarts/Windows reliability from repository tests alone

## Current recommendation

The next highest-value step is not more architecture prose.

It is one disciplined live validation pass on a real Windows board PC with a real Autodarts session, while collecting:
- `data/logs/app.log`
- `logs/backend.log`
- `data/autodarts_debug/*`
- smoke test output

That is the remaining gap between “good repo state” and “credible production claim.”
