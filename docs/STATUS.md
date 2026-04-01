# Status

## Current state after Phase 5 / Phase 6

The project is now materially better for **local-first board operation** than it was at the end of Phase 4.

### What is in place
- local core remains the primary runtime path
- central adapter ring is still optional and stays out of the way when disabled/unreachable
- observer/session/credits flow from Phase 3/4 remains covered by targeted tests
- Windows bring-up now has a clearer operator path
- local smoke tooling exists for repeatable post-install checks

## Phase 5 delivered

### Stability hardening
Implemented:
- fixed remote-action WebSocket board updates to use the real `board_ws.broadcast(event, data)` signature
- fixed central heartbeat health payload collection so it uses `health_monitor.get_health()` instead of a non-existent `get_status()` call
- converted optional background clients to real background-task startup patterns instead of potentially trapping callers inside endless loops:
  - `ActionPoller`
  - `ConfigSyncClient`
  - `OfflineQueue`
  - `TelemetrySyncClient`
- improved shutdown/cancellation behavior for optional background loops
- reduced central logging noise while still logging state transitions and repeated failures

### Operational stability impact
Result:
- local runtime is less likely to get wedged by optional central/background services
- remote board-control actions no longer hit an avoidable broadcast-path bug
- central heartbeat now sends an actual health snapshot instead of silently falling back to `{}`

## Phase 6 delivered

### Installation / ops
Added or updated:
- `docs/INSTALLATION.md`
- `docs/RUNBOOK.md`
- `release/windows/README.md`
- `release/windows/smoke_test.bat`
- `scripts/local_smoke.py`

Improved Windows scripts:
- `start.bat` now reads `BOARD_ID` from `backend\.env`
- `setup_profile.bat` now reads `BOARD_ID` from `backend\.env`
- `stop.bat` and `start.bat` now kill Chrome processes by profile path instead of unreliable window-title matching

### Why that matters
Before this, the Windows helper flow was half-true and half-vibes.
Now there is at least a reproducible story for:
- prerequisites
- board assignment
- Autodarts profile setup
- start/stop
- smoke validation
- logs/troubleshooting

## Validation completed

Ran successfully:

```bash
. .venv/bin/activate && python -m pytest -q \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py
```

Result:
- `14 passed`

This validates:
- phase 5 lifecycle hardening for config sync/action poller startup
- fixed board-update broadcast signature
- central heartbeat health snapshot path
- previously delivered Phase 3/4 Autodarts trigger + credit/session logic still passing

## What is still not fully proven

Honest version:
- no physical Windows board PC bring-up was executed in this environment
- no live Autodarts account/session was exercised here
- no end-to-end browser automation proof was run against a real local backend from the Windows scripts
- legacy tests that import optional runtime deps directly still depend on the local Python environment having those packages installed

## Remaining risk / next sensible work

### Still worth doing
- real hardware validation on one Windows board PC
- one end-to-end Autodarts session test with a real persistent Chrome profile
- optional CI/environment normalization so runtime deps like `httpx` are always present in the dev test venv
- broader observability dashboarding if central telemetry becomes more important later

### Not recommended
- re-coupling local session flow to central availability
- making operator bring-up depend on central registration before local smoke passes

## Bottom line

For local operation, this is now in a much better place:
- less crashy around optional background services
- cleaner Windows bring-up path
- better runbook/docs
- targeted stability fixes landed and tested

It is **closer to production-ready for local board use**, but it still needs one real machine validation pass before anyone should call it “done done.”
