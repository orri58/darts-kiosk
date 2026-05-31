# Darts Kiosk — Release Notes v4.5.5

## Emergency backend recovery fix

This release fixes a backend crash that can make the system unusable when corrupted session state leaves more than one active session on the same board.

## What changed

Version `v4.5.5` hardens the runtime against duplicate active sessions:

- board/session reads no longer crash with `500` on duplicate active sessions
- the backend now keeps the newest active session and auto-cancels older duplicates
- scheduler flows now use the same hardened lookup path
- remote lock / stop-session flows also use the hardened path instead of assuming the database is perfectly clean

## Why this release matters

A support bundle from a live Windows installation showed the updater had succeeded on `v4.5.4`, but the runtime was still failing because `BOARD-1` had multiple active sessions in the database. That produced `sqlalchemy.exc.MultipleResultsFound` and broke endpoints like:

- `GET /api/boards/BOARD-1/session`
- `GET /api/kiosk/BOARD-1/overlay`

`v4.5.5` turns that from a fatal runtime error into a self-healing condition.

## Validation performed

Executed successfully in isolated test databases:

```bash
PYTHONPATH=. DATA_DIR=<tmp> .venv/bin/pytest backend/tests/test_v440_session_consistency.py -q
PYTHONPATH=. DATA_DIR=<tmp> .venv/bin/pytest backend/tests/test_v430_scheduler_terminal_cleanup.py -q
PYTHONPATH=. DATA_DIR=<tmp> .venv/bin/pytest backend/tests/test_manual_unlock_pricing.py -q
bash release/build_release.sh
```

Observed result:
- session consistency suite passed (`6 passed`)
- scheduler terminal cleanup suite passed (`4 passed`)
- manual unlock pricing suite passed (`2 passed`)
- release artifacts were rebuilt for `v4.5.5`
- release assets were published for automatic system update discovery
