# Autodarts Integration Analysis

This document preserves the **detailed evidence** behind the current observer-first Autodarts model.

For the cross-repo synthesis, read `docs/ANALYSIS.md`.
For the current billing/capacity rules tied to these signals, read `docs/CREDITS_PRICING.md`.

Commit audited: `cef9724`

## Executive summary

This integration is **not** a server-to-server Autodarts API integration. It is a **browser observer** around `play.autodarts.io`, with business actions driven by a reverse-engineered mix of:

1. Playwright WebSocket frame capture
2. injected console heuristics
3. DOM fallback polling

That architecture is workable, but only if billing-critical decisions stay tied to the most authoritative signals.

### Bottom line

- **Best current start signal:** `turn_start` / `throw`
- **Best current end signal for credit deduction:** `finished=true` or `gameFinished=true` on match-related WS payloads, after the observer has already seen the match become active
- **Unsafe as sole billing trigger:** `game_shot + body.type=match`, raw `matchshot`, console keywords, DOM buttons/classes
- **Player count is not sourced from Autodarts at all** in current code; it is operator/UI input only
- **The code/docs/tests are materially out of sync**, which raises production change-risk

---

## 1) Event / API inventory

## 1.1 Internal app APIs that drive the integration

These are the local APIs / data paths that matter operationally:

| Surface | Purpose | Notes |
|---|---|---|
| `POST /api/boards/{board_id}/unlock` | Starts a paid session and, if configured, starts the observer | Seeds `players_count` from unlock UI; starts observer if `board.autodarts_target_url` exists |
| `POST /api/kiosk/{board_id}/start-game` | Registers `game_type` and `players` in the session | **No Autodarts verification**; `players_count` becomes `len(players)` here |
| `POST /api/kiosk/{board_id}/end-game` | Manual staff override | Goes through centralized finalization |
| `GET /api/kiosk/{board_id}/observer-status` | Operational status | Returns observer state, browser open, lifecycle, credits remaining |
| `GET /api/kiosk/{board_id}/ws-diagnostic` | Deep diagnostics | Exposes captured WS frames and observer WS state |
| `POST /api/kiosk/{board_id}/observer-reset` | Reopen observer | Useful after auth/cookies/profile trouble |
| `POST /api/kiosk/{board_id}/simulate-game-start` / `simulate-game-end` / `simulate-game-abort` | Test hooks | Only local simulation; not Autodarts-backed |
| `board.autodarts_target_url` | Entry URL into Autodarts | Observer launches a persistent Chrome profile to this URL |

Related runtime components:

- `backend/services/autodarts_observer.py` — primary integration logic
- `backend/routers/kiosk.py` — session finalization / credit policy
- `backend/services/watchdog_service.py` — recovery policy for crashed/unhealthy observers
- `backend/services/window_manager.py` — foreground/hide/restore choreography on Windows

## 1.2 External Autodarts interfaces actually used

### Browser/session layer

- Navigates to configured Autodarts URL (normally `https://play.autodarts.io/...`)
- Detects auth redirects to `login.autodarts.io` or `/login` / `/auth` / `signin`
- Uses a persistent Chrome profile per board

### WebSocket layer (primary source)

The observer captures frames via Playwright `page.on("websocket")` and listens to both `framereceived` and selected `framesent` events.

Observed channel families documented in code:

| Channel / family | Intended meaning | Current usage |
|---|---|---|
| `autodarts.matches.{id}.state` | Match lifecycle/state | Used indirectly via `finished` / `gameFinished` booleans |
| `autodarts.matches.{id}.game-events` | Throws / shots / match events | Used for start, `game_shot`, `matchshot` |
| `autodarts.boards.{id}.matches` | Board-level match events | Observed, but current code does not strongly channel-qualify delete handling |
| `autodarts.boards.{id}.state` | Board state changes | Mostly diagnostic right now |

### Console layer (secondary source)

An injected init script watches console output for strings like:

- `winner animation`
- `matchshot`
- `gameshot`
- `match finish` / `match end` / `match complete`

This is not just telemetry: console-derived `FINISHED` can influence finalization through the merged detector.

### DOM layer (fallback source)

Current runtime DOM detection looks for broad CSS/text heuristics:

**In-game heuristics**
- `[class*="scoreboard"]`
- `[class*="dart-input"]`
- `[class*="throw"]`
- `[class*="scoring"]`
- `[class*="game-view"]`
- `[class*="match-view"]`
- `[class*="player-score"]`
- `[class*="turn"]`
- `[class*="match"][class*="running"]`
- `[data-testid*="match"]`
- `#match`

**Strong post-match heuristics**
- button text containing rematch / share / new game (including German variants)
- classes like `post-match`, `match-summary`, `match-end`, `game-over`

**Generic result heuristics**
- classes like `result`, `winner`, `finished`, `match-result`, `leg-result`

## 1.3 WS event classification inventory

Current runtime classification in `AutodartsObserver._classify_frame()`:

| Classification | Trigger | Current meaning |
|---|---|---|
| `match_start_turn_start` | `event == turn_start` | Match/gameplay started |
| `match_start_throw` | `event == throw` | Match/gameplay started |
| `match_end_gameshot_match` | `event in {game_shot,gameshot,game-shot}` and `body.type == match` | Potential match end |
| `round_transition_gameshot` | same `game_shot*` events, but not `body.type == match` | Leg/round transition |
| `match_end_state_finished` | `finished == true` | Confirmed match end |
| `match_end_game_finished` | `gameFinished == true` | Confirmed match end |
| `match_finished_matchshot` | raw text contains `matchshot` (but not `gameshot`) | Backward-compat finish hint |
| `match_reset_delete` | `event == delete` | Reset / abort depending on prior active state |
| `subscription` | subscribe/attach style traffic | Diagnostic |
| `match_other` | other Autodarts-related traffic | Diagnostic |
| `irrelevant` | everything else | Ignored |

## 1.4 Public/official interface note

Light web research found:

- `play.autodarts.io` (web app)
- `login.autodarts.io` (auth flow)
- `open.autodarts.io` (Open portal)

But I did **not** find a fetchable/readable public contract for the specific runtime WS topics/fields used here (`autodarts.matches.*`, `finished`, `gameFinished`, `game_shot`, etc.). Practically, this means the current integration depends on **reverse-engineered webapp behavior**, not a documented stable API.

---

## 2) Reliable vs brittle signals

## 2.1 Recommended trust ladder

### Tier A — reliable enough for billing/session finalization

| Signal | Why it is strong | Caveats |
|---|---|---|
| `finished=true` | Explicit end-state boolean | Still reverse-engineered; should be tied to prior active match |
| `gameFinished=true` | Same class of explicit boolean | Same caveat |
| `delete` during active match, but **only** on match/board-match channels and with prior active state | Useful abort signal | Current code is too broad here; see risk section |

### Tier B — reliable enough for start-of-play, not for billing end

| Signal | Why it is useful | Caveats |
|---|---|---|
| `throw` | Strong evidence real gameplay began | Late if you want “match created” semantics |
| `turn_start` | Strong evidence first turn began | May fire before first dart, depending on Autodarts flow |

### Tier C — provisional / not good enough alone for billing

| Signal | Why it is weaker |
|---|---|
| `game_shot + body.type=match` | Better than raw keyword matching, but code comments themselves acknowledge it can be premature in multi-leg / variant flows |
| raw `matchshot` keyword | String heuristic only; no schema/field guarantee |
| console `winner animation` / `matchshot` logs | UI/debug side-effect, not contract |
| DOM post-match buttons/classes | Highly coupled to UI, CSS, localization, and A/B changes |

## 2.2 What the code currently does

Current behavior is more aggressive than the safest production policy:

- `finished=true` / `gameFinished=true` cause **immediate finalize dispatch**
- `game_shot + body.type=match` and `matchshot` are treated as **pending finish** signals, but they still finalize after debounce / safety-net if no contradictory start signal arrives
- console `FINISHED` and DOM `FINISHED` can also drive finalization through the merged detector

So the runtime already knows some signals are weaker, but it still lets those weaker signals eventually affect billing/session end.

### Production recommendation

Use this rule set:

- **Start of play:** `turn_start` or `throw`
- **Final credit deduction / session completion:** only `finished=true` or `gameFinished=true` after prior active state
- **Abort handling:** `delete` only if channel-qualified and corroborated by prior active state
- **Console/DOM:** observability + degraded fallback only, not standalone billing authority

---

## 3) When player count becomes trustworthy

### Current state

It does **not** become trustworthy from Autodarts, because the integration does not derive player count from Autodarts at all.

Current sources are purely local UI/session data:

1. `unlock_board` seeds `session.players_count` from `UnlockRequest.players_count`
2. `kiosk_start_game` overwrites it with `len(data.players)`

That means:

- the observer does **not** confirm player count from WS frames
- the observer does **not** parse participant lists from match state
- the observer does **not** compare Autodarts players vs kiosk-entered players

### Operational answer

**Player count becomes “trustworthy” only when the operator submits `/kiosk/{board_id}/start-game` and you trust the operator input.**

That is not Autodarts truth; it is kiosk truth.

### If true Autodarts-ground-truth is required

Add one of these before using player count operationally:

1. parse players/participants from match-state WS payloads, or
2. fetch a documented Autodarts match object if/when an official API exists, or
3. snapshot and reconcile kiosk-entered players against Autodarts match metadata

Until then, any workflow that assumes “Autodarts confirmed N players” is overstating reality.

---

## 4) When game start is definitive enough for credit deduction

## 4.1 Important implementation reality

The codebase is internally inconsistent here:

- `backend/services/autodarts_observer.py` header comment says credits are decremented on **game start**
- actual business logic in `backend/routers/kiosk.py::_finalize_match_inner()` decrements credits on **finalization/end**, based on trigger policy

The router is authoritative in runtime behavior.

## 4.2 Current runtime credit policy

`_should_deduct_credit(trigger)` returns true for:

- `finished`
- `manual`
- `aborted`
- any `match_end_*`
- any `match_abort_*`

So today, credits can be deducted on:

- confirmed WS finish
- provisional WS finish that survives debounce
- abort path
- manual staff end
- console/DOM-driven “finished” if no better signal exists

## 4.3 Recommended “definitive enough” rule

If the question is **“when is it safe to deduct credit?”**, the production answer should be:

### For end-based charging (recommended with current architecture)

Deduct **only after**:

1. the observer previously saw an active match (`turn_start` or `throw`), and
2. a **confirmed end-state boolean** arrives: `finished=true` or `gameFinished=true`

This is the cleanest contract available in current code.

### For start-based charging (if product policy changes later)

The earliest defensible start moment is:

- `throw` preferred
- `turn_start` acceptable fallback

… and only after the kiosk has already registered a game via `/start-game`.

Do **not** use DOM visibility, raw console strings, or just entering a match page as the billing start point.

## 4.4 Specific call on `game_shot + body.type=match`

This should be treated as **preliminary**, not final, for credit deduction.

Reason:

- the code comments already acknowledge it “may be premature for multi-leg matches”
- historical tests in the repo show the project has repeatedly had to rework false-finish behavior
- there is stale test coverage around Gotcha/variant handling, but current runtime no longer contains variant-aware guards

So `game_shot + body.type=match` is fine as:

- a pending UI cue
- a short-lived pre-finalize state
- a hint to wait for `finished=true` / `gameFinished=true`

It is **not** the best standalone billing trigger.

---

## 5) DOM-observation vs API strategy

## 5.1 Current architecture assessment

The high-level architecture choice is correct:

- WS first
- console second
- DOM last

The issue is not the ordering. The issue is that the weaker layers can still become **business-authoritative** when WS confirmation is absent.

## 5.2 Recommended production strategy

### Use WS as the source of truth for business state

**Authoritative WS uses**
- `throw` / `turn_start` => active game
- `finished=true` / `gameFinished=true` => finished game
- channel-qualified `delete` during active game => abort

### Use console only for observability / diagnostics

Good uses:
- post-mortem breadcrumbs
- operator support
- “something just finished” UI hints

Bad use:
- standalone billing/session-finalization trigger

### Use DOM only as degraded fallback

Good uses:
- showing “observer degraded” but still roughly understanding page state
- helping manual recovery
- non-billing UX

Bad uses:
- definitive credit deduction
- authoritative match-end in a multilingual/CSS-changing third-party UI

## 5.3 Concrete design recommendation

### Recommended state machine

1. **Idle -> In game**
   - trigger on `throw` / `turn_start`

2. **In game -> Finish pending**
   - trigger on `game_shot + body.type=match`, `matchshot`, console hints, DOM strong-end hints
   - no billing yet

3. **Finish pending -> Finished authoritative**
   - trigger on `finished=true` / `gameFinished=true`
   - deduct credit / finalize

4. **In game -> Aborted**
   - trigger on channel-qualified `delete` during active game
   - apply abort policy

5. **WS unavailable / degraded**
   - do not silently promote DOM/console to billing authority
   - either require manual staff action or record a degraded non-billing state

That will cut false charges far more than adding more DOM selectors ever will.

---

## 6) Failure modes and change-risk

## 6.1 Runtime failure modes

### 1. Auth/cookie expiry

Handled explicitly:
- redirect to `login.autodarts.io` / login-like URLs sets lifecycle to `AUTH_REQUIRED`
- requires manual login into the persistent Chrome profile

**Risk:** medium operational pain, low billing ambiguity if noticed quickly.

### 2. Chrome profile lock / process collision

The observer checks for lock files and attempts to avoid reusing a profile already held by another Chrome.

**Risk:** medium. Operationally common on kiosk PCs.

### 3. Page/context crash

Observed and handed to watchdog recovery logic.

**Risk:** medium. Better than nothing, but crash timing during finalize can still be messy.

### 4. WS schema drift

This is the largest structural risk.

The integration depends on reverse-engineered fields and topics such as:
- `finished`
- `gameFinished`
- `game_shot`
- `matchshot`
- channel naming under `autodarts.matches.*`

If Autodarts renames or reshapes these, business behavior changes immediately.

**Risk:** high.

### 5. DOM drift / localization drift

Current selectors are broad substring matches against CSS classes and translated button labels.

**Risk:** high for fallback correctness, especially across UI redesigns or locale changes.

### 6. Over-broad delete handling

Current runtime classifies **any** `event == delete` as `match_reset_delete`, without strong channel gating.

That means an unrelated delete while `match_active=True` could be interpreted as an abort and end up deducting credit through the abort path.

**Risk:** high. This should be tightened.

### 7. Provisional finish signals still affect billing

`game_shot + body.type=match`, raw `matchshot`, console finish hints, and DOM finish hints can all eventually produce finalization.

**Risk:** high for false positives in variants / multi-leg flows.

### 8. Player metadata not verified from Autodarts

Players and player count come from kiosk input, not Autodarts.

**Risk:** medium, especially if payouts, player stats, or sharing depend on correctness.

## 6.2 Code/docs/test drift risk

This repo has notable drift around the Autodarts integration.

### Drift examples found in this audit

1. **Credit timing drift**
   - observer file header says credits decrement on start
   - runtime router decrements on finalize/end

2. **Selector-module drift**
   - `backend/autodarts_selectors.py` claims to be the canonical runtime selector source
   - current observer does **not** import it at all
   - runtime uses hard-coded JS in `_detect_state_dom()`

3. **State-name drift**
   - `docs/RUNBOOK.md` says observer state should be `monitoring`
   - current enum states are `closed`, `idle`, `in_game`, `round_transition`, `finished`, `unknown`, `error`

4. **Test/runtime drift**
   - Autodarts tests reference methods that do not exist in the current observer anymore, including `_detect_state`, `_extract_variant`, `_is_gotcha`, `_test_selector`
   - this means portions of the test corpus describe a different implementation than the one shipping now

5. **Stale report drift**
   - `test_reports/pytest/pytest_autodarts.xml` reports failures for `backend/tests/test_autodarts_integration.py`
   - that referenced test file is not present in the current tree

6. **Coverage drift across variants**
   - `test_reports/autodarts_soak_report.json` reports 301/501/Cricket/Training only
   - no equivalent evidence there for Gotcha / tricky variant behavior

### Why this matters

This drift means green-looking artifacts are not enough. The only safe confidence sources are:

- current runtime code
- fresh real-frame captures
- fresh tests directly tied to current code paths

---

## 7) Direct answers to the six requested questions

## 7.1 Event/API inventory

- **Primary external interface:** browser session to `play.autodarts.io`
- **Primary machine-readable channel:** Playwright-observed WebSocket frames on match/board topics
- **Secondary machine-readable channel:** injected console capture
- **Last-resort channel:** DOM polling
- **Internal business APIs:** unlock, start-game, manual end-game, observer-status, ws-diagnostic, reset

## 7.2 Reliable vs brittle signals

**Reliable:**
- `finished=true`
- `gameFinished=true`
- `throw`
- `turn_start`
- channel-qualified delete during active match (abort only)

**Brittle:**
- `game_shot + body.type=match`
- raw `matchshot`
- console winner/match logs
- DOM button texts / CSS substrings
- any signal dependent on undocumented Autodarts UI internals

## 7.3 When player count becomes trustworthy

Only when kiosk staff submits `/start-game` and you trust that input.
It is **not** currently Autodarts-verified.

## 7.4 When game start is definitive enough for credit deduction

For the current architecture, the best production answer is:

- **do not deduct on start at all**
- deduct on **confirmed end** (`finished=true` / `gameFinished=true`) after a previously active match

If start-based charging is ever required, use first `throw` (or `turn_start`) after `/start-game`, not DOM/UI hints.

## 7.5 DOM-observation vs API strategy

- WS = authoritative business state
- console = diagnostics only
- DOM = degraded fallback only
- never let DOM be the sole silent billing authority in production

## 7.6 Failure modes and change-risk

Highest risk items:

1. reverse-engineered WS contract changes
2. over-broad delete handling
3. provisional finish signals still affecting billing
4. stale tests/docs creating false confidence
5. DOM/CSS/localization drift
6. lack of Autodarts-ground-truth for players/variant metadata

---

## 8) Recommended next moves

1. **Make billing authority stricter**
   - finalize/deduct only on `finished=true` or `gameFinished=true`

2. **Tighten abort logic**
   - require channel-qualified delete and prior active match

3. **Separate “pending finish” from “billable finish”**
   - keep `game_shot + body.type=match` and `matchshot` as hints only

4. **Either wire `backend/autodarts_selectors.py` into runtime or delete its canonical-language claims**
   - current state is misleading

5. **Refresh the Autodarts test corpus against current runtime**
   - especially around variants, multi-leg flows, delete semantics, and degraded WS/DOM conditions

6. **Capture golden WS fixtures from real Autodarts sessions**
   - at minimum: x01 single-leg, x01 multi-leg, Cricket, Gotcha, manual abort, auth redirect, reconnect/crash recovery

7. **If player metadata matters, parse it from Autodarts explicitly**
   - current session/player model is kiosk-entered only

---

## Final assessment

The integration is structurally sound **only if treated as a reverse-engineered observer with strict trust boundaries**.

Right now, the biggest production weakness is not Playwright itself. It is that **weak signals can still become billing-authoritative**, while tests/docs imply a cleaner contract than the runtime actually enforces.

If you tighten billing to explicit WS end-state booleans and demote console/DOM to degraded fallbacks, this becomes much safer without rewriting the whole integration.
