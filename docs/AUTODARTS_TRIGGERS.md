# Autodarts Trigger Strategy

## Goal

Autodarts detection is now split into three classes:
- **authoritative** — allowed to drive billing/finalization
- **assistive** — useful hints, but not enough on their own
- **diagnostic** — visibility only

This prevents DOM/console noise from becoming checkout authority.

---

## Default trigger policy

Stored backend setting key:
- `autodarts_triggers`

Default shape:
- `authoritative_start`
  - `match_start_throw`
  - `match_start_turn_start`
- `authoritative_finish`
  - `match_end_state_finished`
  - `match_end_game_finished`
- `authoritative_abort`
  - `match_abort_delete`
- `assistive_finish`
  - `match_end_gameshot_match`
  - `match_finished_matchshot`
- `diagnostic_interpretations`
  - `round_transition_gameshot`
  - `subscription`
  - `match_other`

Additional safety flags:
- `require_prior_active_for_finish = true`
- `require_prior_active_for_abort = true`
- `allow_console_finish_authority = false`
- `allow_dom_finish_authority = false`

---

## Signal classes

## 1) Authoritative start

Accepted signals:
- `turn_start`
- `throw`

Mapped interpretations:
- `match_start_turn_start`
- `match_start_throw`

What they do:
- mark the match as active
- revoke stale/premature finish state if necessary
- emit the authoritative start callback into kiosk billing/session logic

Why these are safe enough:
- they come from WS gameplay traffic
- they represent real start-of-play, not a UI animation or stale result screen

---

## 2) Authoritative finish

Accepted signals:
- state frame with `finished=true`
- state frame with `gameFinished=true`

Mapped interpretations:
- `match_end_state_finished`
- `match_end_game_finished`

What they do:
- mark `ws.match_finished = true`
- clear any pending assistive finish hint
- schedule immediate finalize
- stay eligible for finalize safety-net dispatch if needed

These are the only WS finish signals allowed to become direct billing/finalization authority by default.

---

## 3) Assistive finish

Accepted signals:
- `game_shot` with `body.type = "match"`
- `matchshot` keyword fallback

Mapped interpretations:
- `match_end_gameshot_match`
- `match_finished_matchshot`

What they do:
- mark `finish_pending = true`
- store `pending_finish_trigger`
- do **not** mark `match_finished`
- do **not** dispatch finalize on their own

Why they stay assistive:
- they can be early in multi-leg / transition situations
- the Phase 2/analysis docs showed they were too risky to trust as direct finish authority

---

## 4) Abort / delete handling

Delete/reset is now stricter.

A delete event only becomes an authoritative abort when **all** of this is true:
- interpretation is `match_reset_delete`
- channel matches a qualified Autodarts match/board topic
- there was a prior active match
- the match was not already finalized

Otherwise the delete is treated as diagnostic/reset noise and ignored for billing authority.

This closes the gap where broad delete/reset handling could accidentally end a session.

---

## 5) Console and DOM

Console capture and DOM polling still exist, but their role is downgraded:
- console finish hints are **diagnostic only** by default
- DOM finish hints are **diagnostic only** by default
- neither may create billing authority unless the trigger policy is explicitly changed later

Practical result:
- if WS authority is missing but DOM/console says "looks finished", the observer may show degraded state in logs
- it must not silently finalize and charge anyway

That is intentional.

---

## Runtime behavior

### Finish path
1. assistive hint may arrive (`gameshot_match`)
2. observer records it as pending
3. confirmed state frame arrives (`finished=true` or `gameFinished=true`)
4. observer upgrades to authoritative finish
5. finalize dispatch runs

### False-finish protection
If a new authoritative start-of-play signal arrives after a pending/stale finish:
- pending/finished state is revoked
- match returns to active tracking
- no finish billing authority survives that contradiction

---

## Configuration surface

Phase 3/4 adds the backend config model now so UI can surface it later.

Available today:
- setting seeded at startup: `autodarts_triggers`
- API endpoints:
  - `GET /settings/autodarts-triggers`
  - `PUT /settings/autodarts-triggers`

Not done yet:
- admin/superadmin form for editing it
- higher-level validation UI / safety warnings

---

## Operational rule of thumb

If a trigger did **not** come from strong WS lifecycle data,
assume it is useful for debugging, not for charging.
