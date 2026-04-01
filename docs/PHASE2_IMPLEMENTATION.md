# Phase 2 implementation notes

## What changed

### 1. Central/licensing coupling was pushed out of the default runtime path
- Added `backend/runtime_features.py`
- Added `backend/app_layers.py`
- `backend/server.py` now mounts local-core routers by default and mounts central proxy routes only through the adapter seam
- Layer A startup/shutdown now runs only when `ENABLE_CENTRAL_ADAPTERS` is enabled
- `frontend/src/App.js` now exposes `/portal` only when `REACT_APP_ENABLE_PORTAL_SURFACE` is enabled
- Added `frontend/src/runtimeFeatures.js`

### 2. Local-core seams were made explicit
- route composition is split into local-core vs optional-adapter wiring
- feature flags are centralized instead of being implied by scattered imports/env checks

### 3. Incomplete operator-facing modes were hidden/degraded
- `per_player` removed from admin unlock/settings surfaces
- pricing settings are sanitized server-side so stale `mode=per_player` data does not leak back into the operator UI as the default mode
- call-staff UI is hidden by default behind `ENABLE_CALL_STAFF` / `REACT_APP_ENABLE_CALL_STAFF`
- match-sharing QR only appears on true session end

### 4. Observer-first local behavior was protected
- board unlock now rejects observer mode if the board has no `autodarts_target_url`
- this avoids a fake-unlocked local state that cannot launch the real gameplay surface

---

## Files touched

### Backend
- `backend/server.py`
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/routers/settings.py`
- `backend/runtime_features.py` *(new)*
- `backend/app_layers.py` *(new)*

### Frontend
- `frontend/src/App.js`
- `frontend/src/runtimeFeatures.js` *(new)*
- `frontend/src/pages/admin/Dashboard.js`
- `frontend/src/pages/admin/Settings.js`
- `frontend/src/pages/kiosk/KioskLayout.js`
- `frontend/src/pages/kiosk/InGameScreen.js`
- `frontend/src/pages/kiosk/ObserverActiveScreen.js`
- `frontend/src/pages/kiosk/ErrorScreen.js`

### Docs
- `docs/ARCHITECTURE.md`
- `docs/STATUS.md`
- `docs/PHASE2_IMPLEMENTATION.md` *(new)*

---

## What remains

1. The licensing stack is still on disk and still needs a proper adapter-by-adapter re-entry plan.
2. `central_server/*` remains a separate system, but deployment/docs cleanup outside the app runtime still needs follow-up.
3. Revenue/accounting is still session-sale based, not ledger based.
4. Manual/setup-mode flow still exists in code, but the real stable product remains observer-first.
5. Historical tests/docs around central/licensing/operator surfaces still need a focused audit/update pass.

---

## Practical toggle summary

### Backend
- `ENABLE_CENTRAL_ADAPTERS=1` → start Layer A + mount central proxy
- `ENABLE_CALL_STAFF=1` → allow call-staff surface again

### Frontend
- `REACT_APP_ENABLE_PORTAL_SURFACE=1` → expose `/portal`
- `REACT_APP_ENABLE_CALL_STAFF=1` → show call-staff UI again

Default intent: keep the local core clean, predictable, and hard to destabilize.
