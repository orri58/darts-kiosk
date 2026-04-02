# UI Redesign Notes

## Scope completed in this pass

This pass focused on **removing pricing confusion from the active local product surface**.

Primary goal:

> make freischalten/unlock feel like one obvious credits-only action instead of a mini billing system.

Concretely, this pass targeted:
- admin unlock / extend flow
- admin pricing settings framing
- kiosk locked / setup / in-game / result messaging
- a light cleanup of portal unlock/config wording
- legacy/stale files that polluted repo/build context

This was not a licensing pass and not a finance-ledger redesign.

---

## What changed

### 1) Dashboard unlock flow is now credits-only

The biggest behavioral change is on the admin dashboard:
- removed the pricing-mode toggle from the main unlock dialog
- removed the player-count field from unlock
- unlock now asks only for:
  - credits
  - derived total price
- copy now explains that real deduction happens later at authoritative match start

Why:
- the old flow forced the operator to guess player count too early
- that guess was exactly the wrong source of truth once the real match started
- it made the product feel more complex than it actually needs to be today

### 2) Credits are the active product language now

Across the active local UI, the visible model is now:
- board gets unlocked with credits
- match start consumes credits according to real player count
- staff can top up credits if needed

That means the UI now prefers language like:
- `Credits verfügbar`
- `Credits nachladen`
- `Credits / Matchstart`

instead of pushing operators into raw `per_game` / `per_time` / `per_player` terminology.

### 3) Settings page now reflects the real product, not future complexity

The pricing tab was simplified:
- credits tariff stays editable (`price_per_credit`, default unlock credits)
- max players and allowed game types remain available
- time-based pricing controls were removed from the active operator view
- summary card now frames the pricing model as `Credits-only`

Important design choice:
- legacy/future pricing structures are still allowed to exist in backend/config shape where reasonable
- but they are no longer presented like equally current operator choices

### 4) Kiosk locked screen no longer advertises time pricing

The locked screen previously showed a mixed pricing wall that suggested multiple parallel offers.

Now it shows:
- price per credit
- match-start rule (`1 Credit / Spieler`)
- typical starting credit bundle

Why this is better:
- guests and staff see the current commercial model immediately
- no fake “30/60 minute” choice architecture on the start screen
- the board feels simpler and more venue-realistic

### 5) Setup / in-game / result screens were aligned with per-player credits flow

Important correctness and UX fixes:
- setup screen now shows credits availability for `per_player` sessions
- in-game screen now correctly treats `per_player` as a credits mode instead of accidentally rendering the time card branch
- result screen now shows remaining credits instead of a misleading generic session summary
- overlay copy now says `Credits verfügbar` instead of `Spiele übrig` where that was wrong for the active model

This is not just wording cleanup; one bug here was genuinely functional/misleading UI behavior.

### 6) Reports now distinguish active vs legacy pricing semantics

Reports still need to show historical data, so legacy rows cannot simply disappear.

What changed:
- `per_player` is labeled `Credits / Matchstart`
- `per_game` is labeled `Spielbasiert (Legacy)`
- `per_time` is labeled `Zeitbasiert (Legacy)`

This keeps the data visible without pretending all three are equally active product paths.

### 7) Portal unlock/config received a light cleanup

Portal is not the main local-core surface, but it still had obvious pricing confusion.

Light cleanup applied:
- remote unlock dialog now follows the credits-only unlock framing
- pricing summary/config wording now points at the active `Credits / Matchstart` model

This is intentionally smaller than the local admin cleanup, but enough to avoid the most obvious mismatch.

### 8) Backend/UI contract was adjusted to match the new flow

Under the hood:
- default pricing mode now resolves to `per_player`
- unlock request defaults no longer assume a player-count prompt
- `per_player` unlock seed now comes from entered credits, not player count
- sessions can start with `players_count = 0` until real setup/observer data exists

This matters because the UI change would be fake if the backend still assumed the old model.

---

## Design principles used

### Current product > future menu sprawl
If a capability is not part of the real day-to-day venue flow right now, it should not dominate the operator UI.

### Real authority beats early guesses
The system should bill/deduct on the strongest available match signal, not on an operator guess made before play starts.

### Legacy visibility without legacy promotion
Historical/compatibility modes may still exist in code and reports, but they should be clearly marked as legacy instead of presented as primary choices.

### Keep local-first intact
All changes stayed within the current local-first, observer-based operating model.

---

## Remaining UI gaps

What still remains after this pass:

1. **Real-machine operator validation**
   - the new flow still needs a real board-PC run with real staff behavior

2. **Portal/central surfaces are only partially normalized**
   - the worst confusion is reduced
   - but a full secondary cleanup pass could still make those screens feel more consistent

3. **No richer settlement/receipt UX exists yet**
   - credits-only unlock is now simpler
   - but if operators later want cashier-style totals/receipts/history, that is a separate product pass

4. **Legacy wording may still exist in smaller corners**
   - the big confusing surfaces were fixed first
   - smaller screens/helpers may still need a sweep later

---

## Validation notes for this pass

Validated here:
- focused backend suite passed: `34 passed`
- frontend production build succeeded
- active unlock path, per-player start deduction, and local-core lifecycle stayed green in the focused backend suite

Build note:
- one pre-existing ESLint warning remains in `src/pages/admin/SetupWizard.js` (`react-hooks/exhaustive-deps`)

Repo cleanup note:
- tracked generated `test_reports/*` artifacts were removed
- stale packaging/build leftovers were removed from tracked repo/build context
- `.dockerignore` was added to keep noisy local artifacts out of Docker builds

---

## Recommendation for next pass

Highest-value next step:
- stop redesigning in the abstract
- run the new credits-only unlock flow on a real machine with real Autodarts sessions
- verify one-player, multi-player, and blocked-pending top-up cases end-to-end

That will tell us whether the remaining work is real product polish or just residual cleanup.
