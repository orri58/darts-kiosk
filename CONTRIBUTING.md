# Contributing to Darts Kiosk

## Current Project Status

The project is in **recovery mode** (v4.0.0-recovery). The local core has been restored to a stable baseline. Central server features are disabled and will be reintroduced in controlled layers.

**All contributions must follow the rules below.**

---

## Rules

### 1. Do Not Modify Frozen Core

The following modules are frozen. No modifications without explicit approval:

- `backend/server.py`
- `backend/routers/` (all files)
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`
- `backend/database.py`
- `backend/models/__init__.py`
- `backend/dependencies.py`
- `backend/schemas.py`
- `frontend/src/App.js`
- `frontend/src/pages/admin/*`
- `frontend/src/pages/kiosk/*`
- `frontend/src/context/*`

See `memory/FROZEN_CORE.md` for the complete list.

### 2. No New Features During Recovery

Until the reintegration layers are complete:
- No new user-facing features
- No UI changes
- Only stabilization, documentation, and controlled reintegration

### 3. Each Reintegration Layer Must Be Verified

Layers must be added in order: A → B → C → D. Each must pass all existing tests plus its own new tests before the next layer begins.

### 4. Fail-Closed Policy

Any check that determines whether an action should be allowed (license, auth, rate limit):
- If the check succeeds → allow
- If the check fails → **block**
- If the check errors → **block**
- Never use `except: allow` patterns

---

## Branch Naming

```
recovery/from-v3.3.1-hotfix2    # Current recovery branch
layer-a/central-visibility       # Layer A reintegration
layer-b/license-sync             # Layer B
layer-c/portal-board-control     # Layer C
layer-d/config-sync              # Layer D
fix/<short-description>          # Bug fixes
```

---

## Commit Expectations

- One logical change per commit
- Prefix: `fix:`, `feat:`, `docs:`, `test:`, `refactor:`
- Include the component: `fix(boards): prevent double unlock`
- No "WIP" or "tmp" commits in PR branches

---

## Testing Requirements

Before merging any change:

1. Run baseline tests: `python -m pytest backend/tests/test_v400_recovery_baseline.py -v`
2. All tests must pass
3. No new import errors in backend logs
4. No new compile errors in frontend
5. Manual verification of affected flows

For reintegration layers, also run:
- Layer-specific test suite
- Full regression suite to verify no baseline breakage

---

## Code Style

- **Python:** Follow existing patterns. Use type hints. Use `logger` (not `print`).
- **JavaScript:** Follow existing patterns. Functional components. Hooks.
- **Documentation:** Update relevant docs when behavior changes.
