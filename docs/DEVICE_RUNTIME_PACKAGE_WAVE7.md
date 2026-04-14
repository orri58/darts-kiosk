# Device Runtime Package — Wave 7

## Goal

Wave 7 tightens the runtime package into a more realistic board-PC update/rollback rehearsal lane:

- create the rollback point first
- turn the downloaded runtime ZIP into update staging
- write both install and rollback manifests
- validate that rollback backups are actually app-only and complete

Still additive. The existing release flow stays untouched. The updater core stays untouched.

## What changed

### 1. Closed-loop rehearsal command added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py prepare-closed-loop-rehearsal \
  --runtime-zip data/downloads/darts-kiosk-v4.4.4-windows-runtime.zip \
  --target-version 4.4.4
```

Behavior:
1. creates an app-only backup of the current runtime payload
2. stages `app/` from the downloaded runtime ZIP
3. writes install manifest to `data/update_manifest.json`
4. writes rollback manifest to `data/rollback_manifest.json`
5. validates both manifests
6. runs the usual rehearsal preflight on the update side

That gives operators one obvious command to prepare the whole drill instead of hopping between multiple helpers.

### 2. Rollback backup ZIP validation got stricter

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`validate-update` now inspects rollback backup ZIPs and rejects them when they are not runtime-safe.

Enforced backup shape:
- top-level `app/` only
- required payload roots:
  - `app/backend`
  - `app/frontend/build`
  - `app/agent`
  - `app/bin`

That closes a weak point from wave 6 where rollback prep checked existence, but not whether the backup actually matched the intended replacement boundary.

### 3. New Windows wrapper added

Added:
- `release/runtime_windows/prepare_closed_loop_rehearsal.bat`

Usage:

```bat
app\bin\prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version> [output-dir] [backup-path] [rollback-manifest]
```

Result:
- `data\update_manifest.json` is ready for `app\bin\update_runtime.bat`
- `data\rollback_manifest.json` is prepared for rollback rehearsal / fallback usage

## Why this is safe

- `release/build_release.sh` remains untouched
- `release/build_runtime_package.sh` only keeps copying `*.bat`, so the new wrapper is automatically included
- `updater.py` remains untouched
- runtime-specific policy still lives entirely in the runtime lane
- rollback validation is stricter, not looser

## Validation done in this pass

Recommended and/or executed validation:

1. syntax-check `runtime_maintenance.py`
2. build a fresh runtime package ZIP
3. run `prepare-closed-loop-rehearsal` against that ZIP in a synthetic runtime root
4. confirm both manifests are written
5. confirm rollback manifest validation now checks backup ZIP shape
6. run targeted pytest coverage for the new helper/validation paths

## Recommended next packaging step

Next useful move: run the closed-loop lane on an actual board PC.

Suggested device drill:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
4. run `app/bin/update_runtime.bat`
5. verify app swap preserved `config/` and `data/`
6. copy `data/rollback_manifest.json` to `data/update_manifest.json` or point updater directly to it
7. run rollback via unchanged updater wrapper
8. verify previous app payload returns cleanly

After that, the next logical wave is probably hardware-grade evidence capture:
- before/after version proof
- config/data preservation assertions
- rollback timing/log collection
- operator checklist / signoff artifact for board-PC servicing
