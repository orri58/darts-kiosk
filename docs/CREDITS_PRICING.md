# Credits & Pricing

This document describes the **current local-core billing and capacity model**.

Two separate ideas matter:
- **sale recording** — `Session.price_total`, written when the session is created/unlocked
- **capacity consumption** — when credits or time are actually consumed during play

The repo currently has correctable local accounting and capacity control, but it does **not** yet have a dedicated payments ledger.

## 1. Ground truth

Billing now depends on both:
- the configured `pricing_mode`
- the **authority level** of the gameplay signal

Signal hierarchy:
1. authoritative WebSocket start/finish signals
2. assistive WebSocket hints
3. console/DOM diagnostics

Only the first category should drive billing-critical actions.

## 2. Pricing-mode matrix

| Mode | Capacity model | Charge moment | Units consumed | Session-end rule |
| --- | --- | --- | --- | --- |
| `per_game` | credits on session | authoritative finish / manual end | `1` per finished game | end when no credits remain |
| `per_player` | credits seeded from player count | authoritative start-of-play | full resolved player count once | usually ends after that paid match unless extended |
| `per_time` | wall-clock time until `expires_at` | no per-match charge | `0` | end when time expires |

## 3. `per_game`

### Charges on authoritative finish
- `match_end_state_finished`
- `match_end_game_finished`
- `manual`
- compatibility trigger `finished`

### Does **not** charge
- `aborted`
- `match_abort_delete`
- assistive hint `match_end_gameshot_match`
- console-only finish hints
- DOM-only finish hints

### Behavior
- one authoritative finish consumes one credit
- if credits remain, observer stays alive and board returns to `unlocked`
- if credits reach zero, session closes and board locks

## 4. `per_player`

### Unlock-time seed
At unlock:
- `credits_total = players_count`
- `credits_remaining = players_count`

That preserves the existing `Session` schema without inventing a separate participation ledger.

### Charge moment
`per_player` is billed on **authoritative start-of-play**, not on finish.

Resolved player count is:
1. Autodarts-derived player list/count from observer match/lobby payloads when available
2. else non-empty `len(session.players)` if player names exist
3. else `session.players_count`
4. else fallback `1`

### Guarantees
- repeated start signals do not double-charge
- insufficient credits at authoritative start do not hard-lock the board; they move it into `blocked_pending`
- staff top-up resolves the pending gate and charges exactly once when capacity becomes sufficient
- finish does not add a second charge
- abort before authoritative start does not charge
- abort while still `blocked_pending` does not charge and returns to ready/unlocked state
- abort after a charged start does not add another charge

### Why it works better
This matches the actual product intent:
- you are charging for participation, not only checkout success
- the start signal is the strongest proof that the paid match really began

## 5. `per_time`

`per_time` never consumes credits on match events.

Capacity comes only from elapsed time:
- if `now < expires_at`, the session may stay alive after a match
- if time is exhausted, finalization locks the board and ends the session

## 6. Finalization rules

`finalize_match()` remains the backend authority for closing or continuing a session.

After any finalize-time logic, it decides whether the session still has remaining capacity.

Capacity rules:
- `per_game`: `credits_remaining > 0`
- `per_player`: typically `credits_remaining == 0` immediately after authoritative start charge
- `per_time`: `now < expires_at`

If capacity remains:
- session stays active
- board stays available
- observer remains alive
- Autodarts is returned toward its home/ready state

If capacity is exhausted:
- session ends
- board locks
- observer tears down
- kiosk UI is restored

## 7. Idempotency / double-charge protection

Two protection layers matter.

### 7.1 Start-time idempotency (`per_player`)
The backend refuses to charge again when:
- the board is already `in_game`, or
- the session already consumed its start-time capacity

### 7.2 Finish-time idempotency (`per_game`)
The backend refuses duplicate finalize charges using:
- in-flight finalize guard
- finalized-state guard
- last-finalized `match_id` guard

## 8. Revenue/reporting implications

Current reporting uses `Session.price_total` as booked sale value.

That means:
- revenue summary is derived from stored session rows
- the new pricing logic improves **capacity correctness**
- it does **not** create a payment ledger, invoice model, or reconciliation layer

This is acceptable for local operator reporting and internal totals. It is not the same as finance-grade accounting.

## 9. What is validated in tests

Covered in the in-process backend suite:
- authoritative finish consumes one `per_game` credit
- assistive finish hints do not consume credit
- `per_player` charges at authoritative start and only once
- abort-before-start does not consume capacity
- session keep-alive vs lock behavior follows remaining capacity
- revenue summary excludes active sessions and tolerates null/zero sale totals

See `docs/TESTING.md` for the exact command.

## 10. What still needs live validation

Still not proven here:
- whether live Autodarts WebSocket traffic always maps cleanly to the expected authoritative events in a real venue session
- whether long-running observers or reconnect paths ever produce edge-case duplicate or missing signals
- whether every real operator flow sets the intended `price_total` at unlock time

So the pricing model is now documented and locally validated, but not yet fully field-proven.
