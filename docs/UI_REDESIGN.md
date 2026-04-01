# UI Redesign Notes

## Scope completed in this pass

This pass focused on **operator-facing local product quality** before deeper licensing/central work:
- admin information architecture and navigation cleanup
- dashboard / boards / revenue / settings usability upgrades
- guarded trigger-policy UI on top of the existing backend foundation
- kiosk surface polish for locked / in-game / result / observer-fallback states

The goal was not paint-only styling. The main principle was:

> make local venue operation feel coherent, fast to read, and hard to misuse.

---

## What changed

### 1) Admin IA / navigation

The admin shell now groups navigation by actual operator jobs instead of a flatter legacy list:
- **Operations** → dashboard, boards, revenue, reports
- **Experience** → settings, leaderboard
- **System** → users, discovery, health, system

Key decisions:
- emphasize **local operations first**
- remove logs from primary navigation because it was not a primary operator destination and overlapped with system-level flows
- keep the sidebar explicitly venue-oriented, with local-mode/status cues instead of central/licensing language

### 2) Dashboard

The dashboard was changed from a mostly-card grid into a more useful operator surface:
- top KPI strip for total boards / active boards / live matches / issues
- update banner kept, but framed more clearly
- board cards now include:
  - status
  - observer state / error hint
  - active session context fetched per board
  - direct kiosk link
  - unlock / extend / lock actions
- unlock flow now includes **player count** instead of silently omitting it

This fixes a practical gap: the page is no longer only decorative status, it is a usable control surface.

### 3) Boards page

The boards page now exposes the configuration that operators/admins actually need to verify:
- location
- Autodarts target URL
- Agent API base URL
- kiosk launch shortcut

Important bug fixed:
- `BoardResponse` previously did **not** return `autodarts_target_url` / `agent_api_base_url`
- this made edit flows effectively half-finished because existing values could not be shown reliably

### 4) Revenue page

Revenue is now framed as a venue operations surface rather than a single chart:
- KPI cards
- daily revenue chart
- top boards ranking
- readable daily list
- explicit note that this page stays local-first and is not pretending to be central accounting

### 5) Settings page

Settings now has a better top-level framing and a new trigger policy area:
- summary cards for theme / pricing / trigger guard posture
- new **Trigger Policy** tab
- guarded trigger editor with:
  - presets
  - source/role visibility
  - grouped signal toggles
  - protected delete-channel rules shown as read-only guardrails
  - explicit recovery overrides instead of raw JSON editing

### 6) Trigger configuration UX model

The trigger UI intentionally does **not** allow arbitrary free-form configuration.

Safe model used:
- known signal catalog only
- grouped by role:
  - authoritative
  - assistive
  - diagnostic
- server keeps delete-channel qualifiers locked
- no raw regex/channel editing
- advanced behavior limited to explicit recovery toggles

Presets exposed:
- `strict_ws` → recommended default
- `console_recovery` → venue fallback
- `dom_last_resort` → last-resort recovery mode

### 7) Backend safety added for trigger settings

The backend now sanitizes and validates trigger policy writes:
- unknown interpretations rejected
- only known signal groups accepted
- delete-channel prefixes/suffixes forced back to protected defaults
- returned config is normalized/canonicalized
- metadata endpoint added for the UI

This keeps the UI honest and prevents future unsafe writes outside the UI too.

### 8) Kiosk polish

Updated kiosk surfaces:
- **Locked screen**
  - stronger hierarchy
  - clearer pricing tiles
  - pairing code + optional QR + loyalty/top-player blocks organized into a coherent side rail
- **In-game screen**
  - better session framing
  - clearer time/credit state
  - safer action treatment
- **Match result screen**
  - cleaner share/result layout
  - better session summary
  - clearer countdown back to locked state
- **Observer fallback screen**
  - more production-like recovery UI instead of a bare error slab
- **Setup screen**
  - added explicit setup flow + summary block so players/operators have context while configuring a match

---

## Design principles used

### Local-first clarity
- no central/licensing noise on venue-critical screens
- local actions should be readable at a glance
- if a control affects billing/session state, it should feel heavier and more deliberate

### Guarded configuration
- operators can see what the system uses
- operators can choose between safe, named behaviors
- operators cannot casually invent new trigger/billing rules from the browser

### Readability before density
- more section framing
- more consistent headers and summary blocks
- more explicit empty/instructional states
- less “mystery meat” navigation

### Action proximity
- relevant action buttons live near the data they affect
- dashboard board cards now behave more like operational tiles, not just status tiles

---

## Remaining UI gaps

These are intentionally left for later passes, not forgotten:

1. **Admin reports / system surfaces** still carry some older layout patterns and could be brought onto the new admin shell more fully.
2. **Discovery / health / system** still have some legacy spacing and state treatment.
3. **Setup flow** could still benefit from deeper restructuring if we later want a true step wizard with clearer operator vs player modes.
4. A real **superadmin-only review/diff flow** for trigger-policy changes does not exist yet; for now the local admin UI stays deliberately constrained.
5. Central/licensing-facing surfaces should be cleaned later so they do not visually compete with the now stronger local operator product.

---

## Validation notes for this pass

Validated here:
- frontend production build succeeded
- trigger-policy backend tests passed after new validation logic
- trigger metadata + board response shape were smoke-checked by direct import/runtime checks

Limits in this sandbox:
- broader backend suite is currently constrained by missing environment dependencies in the provided venv (`httpx`, `requests` in some tests)
- no live kiosk touchscreen or real venue session validation happened here

---

## Recommendation for next pass

Highest-value next UI step:
- bring **Reports / Discovery / System / Health** onto the same polished admin surface language
- then do a short real-device operator pass (tablet + kiosk screen + admin laptop) to tighten touch targets, copy, and action ordering
