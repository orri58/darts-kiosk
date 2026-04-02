# Credits & Pricing

This document describes the **current active local-core pricing model**.

## 1. Active product surface

The operator-facing product is now intentionally **credits-only**:
- staff unlocks a board by adding credits
- the unlock flow does **not** ask for player count
- the real credit deduction happens later on authoritative match start
- the actual player count is taken from the strongest available runtime signal

Important distinction:
- **sale recording** = `Session.price_total`, still written when the session is created/unlocked
- **capacity consumption** = credits deducted later, when real play actually starts

The repo still keeps legacy `per_game` / `per_time` support in backend internals for compatibility and older data, but those modes are no longer the intended operator UX.

## 2. Signal authority

Billing-critical credit consumption depends on signal quality.

Hierarchy:
1. authoritative WebSocket start/finish signals
2. assistive WebSocket hints
3. console / DOM diagnostics

Only authoritative start-of-play should deduct `per_player` credits.

## 3. Active credits-only model (`per_player` under the hood)

### Unlock-time seed
At unlock:
- `pricing_mode = per_player`
- `credits_total = entered credits`
- `credits_remaining = entered credits`
- `players_count = 0` until a real setup/match provides stronger information

This keeps the existing schema while making the operator flow simple again.

### Charge moment
Credits are deducted on **authoritative match start**, not on unlock and not on finish.

Resolved player count is:
1. Autodarts-derived player list/count from observer payloads when available
2. else non-empty `len(session.players)` if kiosk setup already collected names
3. else `session.players_count`
4. else fallback `1`

### Guarantees
- repeated start signals do not double-charge
- insufficient credits at authoritative start move the board into `blocked_pending`
- staff top-up resolves the pending gate and charges exactly once when capacity becomes sufficient
- finish does not add a second charge
- abort before authoritative start does not charge
- abort while still `blocked_pending` does not charge and returns to ready/unlocked state
- abort after a charged start does not add another charge

### Practical meaning
The operator now thinks in **credit balance**, not pricing modes:
- add 5 credits
- board unlocks
- real match starts with 3 players
- 3 credits are deducted
- 2 credits remain for later matches or a staff top-up

## 4. Legacy-compatible modes still in backend

These still exist for compatibility, older sessions, and future extensibility, but they are **not the active operator surface**.

| Mode | Current status | Capacity model | Charge moment |
| --- | --- | --- | --- |
| `per_player` | active UX | credit balance | authoritative start |
| `per_game` | legacy-compatible | credits on session | authoritative finish / manual end |
| `per_time` | legacy-compatible | wall-clock time until `expires_at` | no per-match charge |

## 5. Finalization rules

`finalize_match()` remains the backend authority for closing or continuing a session.

Capacity rules:
- `per_player`: `credits_remaining > 0`
- `per_game`: `credits_remaining > 0`
- `per_time`: `now < expires_at`

If capacity remains:
- session stays active
- board returns to `unlocked`
- observer remains alive
- kiosk returns to ready state

If capacity is exhausted:
- session ends
- board locks
- observer tears down
- kiosk returns to locked state

## 6. Revenue / reporting implications

Current reporting still uses `Session.price_total` as booked sale value.

That means:
- local revenue/report pages continue to work from stored session rows
- the main correctness improvement in this pass is **when credits are consumed**, not a full finance-ledger redesign
- this is acceptable for local venue operation, but it is still not finance-grade accounting

## 7. What is validated in tests

Covered in the focused in-process backend suite:
- credits-only unlock creates a `per_player` session seeded from entered credits, without a player-count prompt
- kiosk setup still records players for the current session
- authoritative start deducts the actual player count from the credit seed
- insufficient credits enter `blocked_pending` without a silent double-charge
- finish/abort rules remain idempotent and local-first
- revenue summary still excludes active sessions and tolerates nullable sale totals

See `docs/TESTING.md` for the exact command.

## 8. What still needs live validation

Still not field-proven here:
- real Autodarts WS behavior across long-running venue sessions
- Windows kiosk/operator flow with the new credits-only unlock copy
- whether live operators want any extra receipt/settlement cues around credit sales

So the active pricing model is now simpler and better aligned with product intent, but still needs real-machine validation before anyone should call it finished.
