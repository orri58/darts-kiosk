# Device Runtime Package — Wave 4

## Goal

Wave 4 closes the most annoying rehearsal gap in the runtime-only package lane:
operators should not have to hand-author `data/update_manifest.json` on a board PC just to test a staged runtime update.

The additive runtime package now gets a small opinionated manifest-prep step that:

- writes a runtime-safe update manifest
- enforces the runtime boundary contract during manifest validation
- keeps current release flow and core updater untouched

This is deliberately still wrapper-layer policy, not a risky updater rewrite.

## What changed

### 1. Runtime manifest preparation command added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py prepare-update-manifest \
  --staging-dir data/downloads/staged-v4.4.4 \
  --target-version 4.4.4
```

Behavior:
- writes `data/update_manifest.json` by default
- auto-fills runtime-safe defaults:
  - `action=install_update`
  - `project_root=<current runtime root>`
  - `protected_paths=["config", "data", "logs"]`
  - backup default: `data/app_backups/runtime-pre-update.zip`
- immediately validates the generated manifest against runtime staging semantics

That means the operator no longer has to remember or manually type the protected roots and update shape contract.

### 2. Update validation is stricter about manifest semantics

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`validate-update` now checks not only staged payload shape, but also manifest discipline:

- `project_root` must match the current extracted runtime root
- protected paths must include the runtime-preserved roots:
  - `config`
  - `data`
  - `logs`
- unexpected protected paths are flagged early
- protected paths outside the runtime boundary contract are flagged early

This matters because a hand-written manifest can otherwise silently drift back toward repo-shaped or legacy update assumptions.

### 3. Windows helper for board-PC rehearsal prep

Added:
- `release/runtime_windows/prepare_update_rehearsal.bat`

Usage:

```bat
app\bin\prepare_update_rehearsal.bat <staging-dir> <target-version> [backup-path]
```

Example:

```bat
app\bin\prepare_update_rehearsal.bat data\downloads\staged-v4.4.4 4.4.4
```

Behavior:
1. writes a runtime-safe `data/update_manifest.json`
2. validates the staged runtime payload
3. runs rehearsal preflight

So the board-PC drill becomes a one-command prep instead of “open JSON and hope”.

### 4. Runtime README updated for the new rehearsal path

Updated:
- `release/runtime_windows/README_RUNTIME.md`

It now documents:
- manifest preparation
- protected-root semantics
- the recommended operator flow for update rehearsal

## Why this is safe

- `release/build_release.sh` is still untouched
- the current repo-shaped release line is still untouched
- `updater.py` core behavior is untouched
- the stricter rules only apply in the runtime package lane
- manifest prep is additive and operator-facing, not invasive

## Validation done in this pass

Recommended validation targets for this wave:

1. dry-run manifest generation against a synthetic runtime-shaped staging folder
2. `validate-update` against the generated manifest
3. `rehearsal` against the same runtime root
4. optional rebuild of the runtime package to confirm the new helper is included automatically via the existing `*.bat` copy rule

## Recommended next packaging step

If this wave behaves cleanly on one real Windows board PC, the next move should be to reduce wrapper-only policy debt and teach the updater path more explicit runtime semantics:

- replace `app/` as the intended unit
- preserve `config/` and `data/` by contract
- make app-backup / rollback naming and placement reflect runtime packaging directly
- optionally add a staged-payload unpack helper so runtime update rehearsal can start from a downloaded ZIP instead of a manually prepared folder
