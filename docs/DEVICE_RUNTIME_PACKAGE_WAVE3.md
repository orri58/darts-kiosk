# Device Runtime Package — Wave 3

## Goal

Wave 3 pushes the additive runtime package closer to a real board-PC rehearsal flow without changing the current release path and without rewriting the core updater.

The key move is simple:

- make runtime validation care about writable device paths, not just folder presence
- make the runtime update wrapper reject repo-shaped or mixed payloads early
- provide one rehearsal-oriented preflight command that operators can run before a board-PC update drill

## What changed

### 1. Writable-path validation is now part of runtime validation

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/validate_runtime.bat`

`validate` now checks that the expected writable runtime paths are actually writable:

- `data/`
- `data/db/`
- `data/logs/`
- `data/backups/`
- `data/app_backups/`
- `data/downloads/`
- `data/assets/`
- `data/chrome_profile/`
- `data/kiosk_ui_profile/`

This catches a very real board-PC failure mode: extracted package looks structurally fine, but the runtime cannot write logs, DB, or profile state.

### 2. Runtime update preflight now enforces app-only staging shape

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/update_runtime.bat`

Added command:
- `validate-update`

Before `update_runtime.bat` launches the Python updater, it now checks that `data/update_manifest.json` points to a staging directory that looks like a runtime payload:

- staged top level must be `app/` only
- required staged subtrees:
  - `app/backend`
  - `app/frontend/build`
  - `app/agent`
  - `app/bin`

This is intentionally stricter than the current core updater logic.
It does not change the updater itself.
It just prevents the runtime wrapper from applying a repo-shaped update by accident.

### 3. Rehearsal preflight command added

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

Added command:

```bash
python app/bin/runtime_maintenance.py rehearsal
```

This combines:
- runtime layout validation
- writable-path checks
- update manifest presence
- staged payload shape validation

It gives a compact pass/fail checklist for an operator before doing a board-PC update rehearsal.

## Why this is safe

- `release/build_release.sh` remains untouched
- existing runtime builder remains additive
- no local core behavior was rewritten
- updater core semantics remain untouched
- stricter checks only live in the runtime package lane

## Recommended board-PC rehearsal flow

1. build fresh runtime package
2. extract to a clean Windows board-PC folder
3. run `app/bin/setup_runtime.bat`
4. run `app/bin/validate_runtime.bat`
5. run `app/bin/start_runtime.bat`
6. run `app/bin/smoke_test_runtime.bat`
7. prepare `data/update_manifest.json` with a runtime-shaped staged payload
8. run `python app/bin/runtime_maintenance.py rehearsal`
9. run `app/bin/update_runtime.bat`
10. verify:
   - only `app/` content changed
   - `config/` survived untouched
   - `data/` survived untouched
   - backend restarts cleanly
   - logs still land in `data/logs/`

## Recommended next packaging step

If the board-PC rehearsal passes, the next wave should stop relying on wrapper-only policy and move toward explicit updater support for runtime-package semantics:

- replace `app/` as a unit
- treat `config/` and `data/` as permanent protected roots
- make rollback/app-backup behavior reflect that contract directly
