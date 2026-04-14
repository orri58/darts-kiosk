# Device Runtime Package — Wave 2

## Goal

Wave 2 hardens the additive runtime-only package path so it is closer to an actual board-device deployment target without changing the existing release flow or touching the local core.

The focus here is not a packaging rewrite.
It is operator ergonomics and runtime hygiene:

- validate that an extracted package is structurally sane
- add a safe cleanup/retention hook for persistent device folders
- make the update entry point fail earlier when the runtime shape is broken
- keep support/retention knobs outside the code path

## What changed

### 1. Runtime maintenance engine

Added:
- `release/runtime_windows/runtime_maintenance.py`

This script supports:
- `validate`
- `cleanup`
- `report`

It is safe by default and supports `--dry-run`.

### 2. Windows operator wrappers

Added:
- `release/runtime_windows/validate_runtime.bat`
- `release/runtime_windows/cleanup_runtime.bat`

Behavior:
- validation can be run before first launch or before update
- cleanup defaults to preview mode
- actual pruning requires `--apply`

### 3. Update wrapper now validates first

Updated:
- `release/runtime_windows/update_runtime.bat`

Before launching the Python updater, it now:
- checks that `app/.venv` exists
- validates the runtime package layout
- runs a cleanup preview

This gives earlier failure and clearer operator feedback on broken extractions.

### 4. Runtime retention overrides documented

Added:
- `release/runtime_windows/runtime_retention.env.example`

This file is copied into the runtime package as:
- `config/runtime_retention.env.example`

Operators can copy selected keys into `app/backend/.env` to tune retention without changing code.

## Retention defaults

Current defaults in the maintenance helper:

- logs: keep latest 8 files, cap combined size to 50 MB
- app backups: keep latest 2 files
- downloads: keep latest 3 files, max age 14 days
- support bundles: keep latest 2 files, max age 7 days

These are intentionally conservative and align with the packaging audit guidance.

## Why this is safe

- current `release/build_release.sh` is untouched
- runtime package remains additive
- local core behavior is untouched
- cleanup defaults to dry-run
- retention tuning is externalized into env values

## Recommended next packaging step

Do one real board-PC rehearsal with the runtime package:

1. extract fresh package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/validate_runtime.bat`
4. start runtime and smoke test
5. create a realistic `data/update_manifest.json`
6. run `app/bin/update_runtime.bat`
7. confirm only `app/` payload changes while `config/` and `data/` survive intact

If that passes, the next wave should tighten the updater around explicit runtime-package semantics instead of the older repo-shaped assumptions.
