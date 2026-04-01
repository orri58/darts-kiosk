# Contributing to Darts Kiosk

Contribute as if you are touching a venue machine that people want to play on tonight.

That means:
- protect the local core first
- prefer clarity over cleverness
- do not hide uncertainty
- keep docs, tests, and behavior aligned

## 1. Working assumptions

The current baseline is a **local-first protected core** with optional adapter/central code around it.

Treat these statements as true unless you are deliberately changing them:
- local unlock/play/lock must not depend on central availability
- authoritative observer signals outrank console/DOM guesses
- `finalize_match()` is the main lifecycle authority
- `Session` remains the current local source of truth for capacity and recorded sale totals
- real Windows/Autodarts validation is still required for strong production claims

## 2. Protected areas

Changes in these areas require focused review, matching docs updates, and the authoritative local-core test subset:
- `backend/server.py`
- `backend/models/__init__.py`
- `backend/database.py`
- `backend/dependencies.py`
- `backend/runtime_features.py`
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/routers/admin.py`
- `backend/routers/settings.py`
- `backend/services/session_pricing.py`
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`
- `frontend/src/pages/admin/*`
- `frontend/src/pages/kiosk/*`
- `frontend/src/context/*`

## 3. Required mindset

### Do
- make one logical change per commit
- prefer small, testable behavioral changes
- update docs when behavior or status changes
- state clearly what was validated and what was not
- keep central/optional failures from breaking local runtime

### Do not
- overclaim production readiness
- silently broaden the trusted runtime surface
- tie local play to optional remote success paths
- treat assistive Autodarts hints as billing authority without strong evidence
- leave architecture/status/testing docs stale after changing behavior

## 4. Testing expectations

For local-core behavior changes, run:

```bash
source .venv/bin/activate
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
```

If your change affects Windows/operator or live observer behavior, that pytest subset is necessary but **not sufficient**. Do a real-machine pass when possible and document the result.

## 5. Commit style

Use clear commit prefixes:
- `fix:`
- `test:`
- `docs:`
- `refactor:`
- `feat:` only when you are intentionally adding supported behavior, not just touching legacy surfaces

Recommended pattern:
- `fix(admin): harden revenue summary null handling`
- `test(local-core): cover unlock lock and finalize flows`
- `docs(status): align testing and readiness notes`

Avoid:
- `WIP`
- `tmp`
- giant dump commits

## 6. Documentation expectations

If you change the local-core contract, check these files:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CREDITS_PRICING.md`
- `docs/STATUS.md`
- `docs/TESTING.md`
- `docs/RUNBOOK.md`
- `FINAL_REPORT.md` if you are finishing a milestone/fix round

## 7. Honesty policy

If something cannot be validated in this environment, say so.

Good examples:
- “In-process tests pass; live Windows focus behavior still needs confirmation.”
- “Pricing logic is covered locally; real Autodarts WS event variability still needs field validation.”

Bad examples:
- “Production ready” with no live machine evidence
- “Fixed” when only the happy-path unit tests were run

## 8. Review checklist

Before opening or merging a change, ask:
1. Did I change protected local-core behavior?
2. If yes, did I run the authoritative local-core subset?
3. Did I update docs to match the current truth?
4. Did I accidentally increase dependence on optional remote systems?
5. Am I claiming more confidence than the validation supports?

If the answer to the last question is “maybe,” tone it down.
