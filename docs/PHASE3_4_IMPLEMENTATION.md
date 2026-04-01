# Phase 3 / Phase 4 Implementation

## Scope completed

This pass implemented both of the remaining backend-heavy goals:
1. reliable Autodarts trigger authority model
2. clean credit/pricing behavior across `per_game`, `per_player`, `per_time`

The focus stayed on correctness and testability, not on adding a new operator UI.

---

## What changed

## 1) New trigger policy layer

Added:
- `backend/services/autodarts_triggers.py`

This introduces a configurable trigger policy with explicit categories:
- authoritative start
- authoritative finish
- authoritative abort
- assistive finish
- diagnostic / ignored

The observer now consumes that policy instead of treating all finish-like signals equally.

### Practical effect
- WS state frames (`finished=true`, `gameFinished=true`) are the finish authority
- `gameshot match` / `matchshot` remain hints only
- console/DOM are not billing-authoritative by default
- delete/reset handling is channel-qualified and requires a prior active match

---

## 2) Observer state machine tightened

Changed in:
- `backend/services/autodarts_observer.py`

Key changes:
- added `finish_pending` + `pending_finish_trigger`
- assistive finish signals no longer set `match_finished`
- authoritative finish signals schedule immediate finalize
- authoritative start callback is emitted only from WS-backed start signals
- non-authoritative DOM/console finish hints are ignored for billing/finalize authority
- observer status/diagnostics now expose the active trigger policy

This is the biggest safety change of the phase.

---

## 3) Pricing logic extracted and normalized

Added:
- `backend/services/session_pricing.py`

This centralizes:
- unlock-time credit seeding
- authoritative start charging for `per_player`
- finalize-time charging for `per_game`
- remaining-capacity checks for all pricing modes
- match-completion vs abort distinction

### Billing rules now
- `per_game` => deduct 1 on authoritative finish/manual end
- `per_player` => deduct resolved player count once on authoritative start
- `per_time` => no credit deduction; capacity comes from expiry only

---

## 4) Backend unlock flows updated

Changed in:
- `backend/routers/boards.py`
- `backend/services/action_poller.py`
- `backend/runtime_features.py`

`per_player` is now supported in backend local-core logic again.

Unlock/session creation uses `initial_credit_seed()` so the session starts with the right capacity model for the chosen pricing mode.

---

## 5) Kiosk finalize/start integration updated

Changed in:
- `backend/routers/kiosk.py`

Key changes:
- `_on_game_started()` now applies `per_player` authoritative-start charging exactly once
- `finalize_match()` now uses shared finalize-capacity logic instead of ad-hoc per-game-only deduction rules
- match completion side-effects are now tied to true match completion, not abort paths
- observer start now loads the stored trigger policy and passes it into the observer

---

## 6) Settings seeded for future UI work

Changed in:
- `backend/models/__init__.py`
- `backend/routers/settings.py`
- `backend/server.py`

Added backend setting:
- `autodarts_triggers`

Available now through API:
- `GET /settings/autodarts-triggers`
- `PUT /settings/autodarts-triggers`

So the config model exists now and can later be surfaced in admin/superadmin without reworking observer internals again.

---

## Tests added

Added:
- `backend/tests/test_phase34_autodarts_triggers.py`
- `backend/tests/test_phase34_credits_pricing.py`

Coverage added for:
- authoritative vs assistive finish classification
- assistive finish staying pending-only
- confirmed finish upgrading pending signal
- delete/reset safety on unqualified channels
- console/DOM finish staying non-authoritative
- `per_player`: 1 player => 1 credit
- `per_player`: 3 players => 3 credits
- retry/restart does not double-charge
- abort before authoritative start does not charge
- `per_game` authoritative finish still consumes exactly one credit

Validated locally with:
- `. .venv/bin/activate && python -m pytest -q backend/tests/test_phase34_autodarts_triggers.py backend/tests/test_phase34_credits_pricing.py`

Result:
- `10 passed`

---

## What remains

Not done in this phase:
- admin/superadmin UI for editing `autodarts_triggers`
- local admin UI for exposing `per_player` again in a polished way
- dedicated billing/revenue ledger beyond session capacity accounting
- broader end-to-end observer integration tests with captured real WS fixtures
- migration story if old sessions/settings expect earlier Phase 2 operator assumptions

---

## Net effect

The repo is now in a much saner state:
- observer authority is explicit instead of mushy
- billing rules are mode-aware instead of finish-only hacks
- `per_player` is real backend behavior now, not a ghost mode
- aborts and UI hints are much less likely to cause silent overcharging
