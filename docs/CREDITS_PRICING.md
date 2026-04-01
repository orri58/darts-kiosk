# Credits & Pricing

## Ground truth after Phase 3/4

Billing now depends on **pricing mode** and **authority level** of the gameplay signal.

The backend distinguishes between:
- **authoritative start** — strong WS start-of-play signal from Autodarts
- **authoritative finish** — strong WS finish signal or explicit staff/manual end
- **abort/reset** — delete/cancel paths that end or reset a match but do not themselves create billable authority
- **diagnostic hints** — DOM/console observations used for visibility, never for billing authority

---

## Mode matrix

| Mode | Capacity model | Bill moment | Units consumed | Next-game rule |
| --- | --- | --- | --- | --- |
| `per_game` | session credits | authoritative finish / manual end | `1` per finished game | stay alive while credits remain |
| `per_player` | session credits seeded from player count | authoritative start-of-play | resolved player count once | no next game after that match unless extended/unlocked again |
| `per_time` | wall-clock expiry | no credit deduction | `0` | stay alive until `expires_at` |

---

## `per_game`

### What charges
- `match_end_state_finished`
- `match_end_game_finished`
- `manual`
- compatibility trigger `finished`

### What does **not** charge
- `aborted`
- `match_abort_delete`
- console-only finish hints
- DOM-only finish hints
- assistive WS hints like `match_end_gameshot_match`

### Behavior
- one finished game consumes exactly one credit
- if credits remain, observer stays alive and returns Autodarts to the lobby/home flow
- if credits hit zero, the session closes and the board locks

---

## `per_player`

### Seed state
At unlock time the backend seeds:
- `credits_total = players_count`
- `credits_remaining = players_count`

This keeps the existing session schema usable without adding a new ledger table.

### Bill moment
`per_player` is now billed on **authoritative start-of-play**, not on finish.

The resolved player count is:
1. `len(session.players)` if player names were registered
2. else `session.players_count`
3. else fallback `1`

### Guarantees
- 1 player start => 1 credit consumed
- 3 player start => 3 credits consumed
- repeated start signals / observer retries do not double-charge
- abort before authoritative start does not charge
- abort after an authoritative start does not add a second charge

### Why this model
This matches the product intent better than finish-time deduction:
- the billable unit is participation, not checkout
- the match may still be aborted later, but only a real start can consume the player charge
- observer-first local flow stays intact because the charge is tied to the first strong WS start signal

---

## `per_time`

`per_time` never consumes credits.

Session end is derived only from time capacity:
- if `expires_at` is still in the future, keep the board/session alive
- if the session is out of time, finalize and lock

---

## Finalization rules

`finalize_match()` is still the single backend authority for session closure.

It now asks one question after any finalize-time charge logic:

> Does this session still have capacity for another game?

Capacity rules:
- `per_game`: `credits_remaining > 0`
- `per_player`: `credits_remaining > 0` before authoritative start, then normally `0` after the one match begins
- `per_time`: `now < expires_at`

If no capacity remains:
- session closes
- board locks
- observer tears down
- kiosk UI is restored

If capacity remains:
- session stays active
- board stays unlocked
- observer stays alive
- Autodarts is returned to a ready state for the next game

---

## Idempotency / double-charge protection

Two layers matter:

### 1. Start-time idempotency (`per_player`)
The backend refuses to charge again when:
- the board is already `in_game`, or
- the session's player charge has already been consumed

### 2. Finish-time idempotency (`per_game`)
The backend refuses to charge twice for the same finalized match by using:
- in-flight finalize guard
- finalized-state guard
- last finalized `match_id` guard

---

## Reporting notes

The current repo still books revenue into `Session.price_total` rather than a dedicated payments ledger.

That means:
- revenue reports still read from session sale data
- the new charging rules improve **session capacity correctness**
- they do **not** yet create a new accounting ledger layer

That is intentional for Phase 3/4: correctness first, ledger redesign later.
