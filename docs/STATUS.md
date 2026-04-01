# Status

## Honest status after Phase 2 cleanup

The repo now has a cleaner split between the **stable local product** and the **optional central/licensing ring**.

### Stable local product
These are the flows the codebase is actively protecting:
- local admin auth
- local board/session persistence
- local unlock / extend / lock
- observer-first Autodarts flow
- centralized local `finalize_match()` lifecycle
- `per_game`
- `per_time`
- local settings
- local revenue/reports based on `Session.price_total`
- local WS + polling fallback

### Newly enforced guardrails
- central/portal surfaces are **not** on the default runtime path anymore
- observer-mode unlock requires a configured `autodarts_target_url`
- `per_player` is hidden from operator pricing/unlock surfaces
- call-staff UI is hidden by default
- match-result QR sharing only appears on true session end, not mid-session keep-alive

---

## What is optional now

These are no longer treated as baseline runtime behavior:
- Layer A heartbeat startup
- `/api/central/*` proxy surface
- `/portal` routes/UI

They exist behind explicit feature gates:
- backend: `ENABLE_CENTRAL_ADAPTERS`
- frontend: `REACT_APP_ENABLE_PORTAL_SURFACE`

Default posture: **local-only runtime**.

---

## What remains incomplete / not operator-stable

### Hidden or degraded on purpose
- `per_player` lifecycle/accounting mode
- call-staff flow
- portal/central visibility as a default operator path

### Still on disk but not current product truth
- device-side licensing stack
- central sync clients
- telemetry/action/ws push clients
- `central_server/*`
- legacy operator/portal residue not mounted in the default flow

---

## Known constraints

1. Revenue is still booking-at-session-sale, not a dedicated payments ledger.
2. Autodarts integration is still a browser observer around `play.autodarts.io`, not an official documented backend API integration.
3. Historical `per_player` config values may still exist in stored settings/data for compatibility, but the local UI no longer treats them as a supported mode.
4. Central/licensing code still needs a later adapter-by-adapter reintegration pass if it is ever brought back.

---

## Recommended operating assumption

Treat the product as:
- **production candidate:** local observer-first kiosk/admin system
- **optional lab mode:** central visibility / portal surfaces
- **not production-ready:** licensing / central control reactivation beyond the current guarded seams

That is the most accurate description of the repo today.
