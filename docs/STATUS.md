# Status

## Executive summary

The repo is in a better product state again:
- the active operator flow is now **credits-only**
- unlock/freischalten no longer asks for player count
- actual credit deduction happens later on authoritative match start, using the real player situation
- time-based and other pricing variants are no longer exposed as first-class operator choices in the main local UI
- stale generated test-report artifacts and old packaging noise were removed from the tracked repo/build surface

This is a meaningful cleanup/product pass, not just copy polish.

It is still **not fully production-proven** until somebody does a real Windows + Autodarts validation pass.

## Latest pass: credits-only unlock cleanup

### Product decisions implemented
- board unlock now uses a credits-only operator flow
- operator enters credits and unlocks the board
- player count is no longer part of the unlock dialog
- `per_player` remains the active backend mode under the hood, but it now seeds from entered credits instead of player count
- actual deduction happens on authoritative match start using detected/setup player count
- `per_time` and similar pricing complexity were removed from the active admin/kiosk unlock surfaces
- reports now label legacy pricing modes honestly instead of presenting them like current product defaults

### UI surfaces updated
- **Admin dashboard**
  - freischalten dialog simplified to credits + price only
  - no more pricing-mode toggle in the main unlock flow
  - no more player-count field in unlock
  - session cards now describe credits-based vs legacy sessions more honestly
- **Admin settings**
  - pricing tab now presents the current product as credits-only
  - per-time tuning is no longer shown as an active operator choice
  - pricing saves normalize back to `per_player` as the active local mode
- **Kiosk screens**
  - locked screen now explains credits / match-start billing instead of showing time offers
  - setup screen shows credits availability for the active flow
  - in-game screen correctly treats `per_player` as a credits mode instead of falling into the time UI branch
  - result/overlay copy now says credits rather than “games left” where that was misleading
- **Portal surfaces (light cleanup)**
  - remote unlock dialog also follows the credits-only unlock model
  - portal pricing summary now frames the active model as credits / matchstart instead of time-heavy mode switching
- **Reports**
  - current mode is labeled `Credits / Matchstart`
  - old `per_game` / `per_time` entries are explicitly marked legacy

### Backend/runtime changes
- default pricing mode is now `per_player`
- pricing settings sanitize invalid mode → `per_player`
- unlock schema defaults to `per_player` and no longer assumes a player prompt
- `initial_credit_seed()` for `per_player` now uses entered credits when present
- board unlock validates credits/time more explicitly
- remote action poller defaults were aligned with the credits-only model
- unlock sessions can start with `players_count = 0` until real setup/match data exists

## What is currently validated

Validated in-process with the focused backend subset:
- credits-only unlock creates an active `per_player` session seeded from entered credits
- unlock no longer requires a player-count prompt to create the session
- kiosk setup still records player names/count for the current session
- authoritative start deducts the actual player count from the credit seed
- insufficient credits still enter `blocked_pending` safely
- authoritative finish still handles legacy `per_game` correctly
- assistive finish hints do not consume `per_game` credits
- abort-before-start does not consume `per_player` capacity
- keep-alive vs teardown still follows remaining capacity
- revenue summary still excludes active sessions and tolerates nullable sale totals

## What was actually run

Executed commands:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
```

Result:
- `34 passed`

And:

```bash
cd frontend
npm run build
```

Result:
- production build completed successfully
- one pre-existing ESLint warning remains in `src/pages/admin/SetupWizard.js` (`react-hooks/exhaustive-deps`)

## Repo/build-surface cleanup done in this pass

Cleaned up:
- tracked historical files under `test_reports/` (generated snapshots / XML outputs)
- stale generated file `release/build/requirements-core.txt`
- stale version-pinned doc `release/INSTALL_GUIDE_v345.md`
- broken/noisy root `.gitignore` replaced with a clean deterministic version
- new `.dockerignore` added so local build context stops dragging along runtime/build/test clutter

This is intentionally conservative cleanup:
- remove misleading generated artifacts and packaging noise
- keep the working local-core codebase intact
- avoid aggressive deletion of potentially useful implementation history

## What is only partially validated

Still only partly proven here:
- real Windows board-PC operator flow with the new copy/order of actions
- live Autodarts sessions and reconnect behavior over long runtimes
- touch-first operator usage on actual kiosk/admin devices
- whether every optional central/licensing surface now feels equally current

## What still needs live validation before strong production claims

Minimum live checklist:
1. real Windows machine install via `release/windows/setup_windows.bat`
2. real Autodarts login/profile prep via `release/windows/setup_profile.bat`
3. successful `start.bat` + `smoke_test.bat`
4. real credits-only unlock on the target board
5. real authoritative match start observed with correct player-count deduction
6. real blocked-pending recovery via staff top-up
7. real authoritative finish observed
8. one keep-alive case with credits remaining
9. one session-end case with credits exhausted
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
- unattended venue rollout without a real-machine validation pass
- claiming long-running Autodarts/Windows reliability from repo tests alone

## Current recommendation

The next highest-value step is now a **real-machine operator validation pass**, not another abstract pricing redesign.

Specifically:
- run the new credits-only unlock flow on a real Windows board PC
- observe one real match start with 1 player and one with multiple players
- verify blocked-pending + top-up behavior in the field
- capture logs/screenshots while doing it

That is the remaining gap between “clean repo/product surface” and “credible production claim.”
