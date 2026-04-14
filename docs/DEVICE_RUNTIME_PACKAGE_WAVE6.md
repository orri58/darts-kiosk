# Device Runtime Package — Wave 6

## Goal

Wave 6 tightens the runtime-package rehearsal lane around the most practical missing operator steps:

- create an explicit app-only rollback point before a runtime update drill
- prepare a rollback manifest without hand-editing JSON
- optionally chain ZIP staging + manifest prep + rehearsal in one runtime-safe command

This stays additive. The release flow is unchanged. The core updater is untouched. The runtime lane just gets better guardrails and less manual glue.

## What changed

### 1. App-only backup helper added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py create-app-backup
```

Behavior:
- zips only `app/`
- requires the runtime app shape to be complete:
  - `app/backend`
  - `app/frontend/build`
  - `app/agent`
  - `app/bin`
- writes into `data/app_backups/` by default
- default filename includes the current version and UTC timestamp

That makes rollback rehearsal reflect the runtime contract directly: backup the replaceable unit, not the whole device-shaped tree.

### 2. Update manifests now default to versioned app-backup names

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`prepare-update-manifest` now defaults `backup_path` to a more explicit runtime backup name:

```text
data/app_backups/runtime-app-<current>-to-<target>-<timestamp>.zip
```

This is still just manifest-layer policy, but it gives clearer operator breadcrumbs during update/rollback drills.

### 3. Rollback manifest preparation added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py prepare-rollback-manifest \
  --backup-path data/app_backups/runtime-app-4.4.3-to-4.4.4-20260413-120000Z.zip
```

Behavior:
- writes a runtime-safe rollback manifest into `data/update_manifest.json`
- enforces the same runtime protected roots:
  - `config`
  - `data`
  - `logs`
- validates that:
  - `project_root` matches the runtime root
  - backup parent exists
  - backup file exists

This gives the existing `update_runtime.bat` wrapper a clean rollback entry point without teaching the updater new semantics.

### 4. ZIP-first rehearsal chain added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py prepare-runtime-update \
  --runtime-zip data/downloads/darts-kiosk-v4.4.4-windows-runtime.zip \
  --target-version 4.4.4
```

Behavior:
1. extracts app-only staging from the runtime ZIP
2. writes a runtime-safe update manifest
3. validates the manifest
4. runs the same rehearsal checklist logic

So operators can start from the actual downloaded runtime artifact and reach a rollback-ready rehearsal state with one command.

### 5. New Windows helpers added

Added:
- `release/runtime_windows/create_runtime_app_backup.bat`
- `release/runtime_windows/prepare_runtime_update_from_zip.bat`
- `release/runtime_windows/prepare_runtime_rollback.bat`

These wrap the new commands into simple board-PC operator entry points.

## Why this is safe

- `release/build_release.sh` remains untouched
- the current repo-shaped release path remains untouched
- `updater.py` is untouched
- runtime-specific policy stays in the runtime lane
- new helpers only reinforce the intended boundary:
  - replace `app/`
  - preserve `config/`, `data/`, `logs`

## Validation done in this pass

Recommended validation for this wave:

1. syntax-check `runtime_maintenance.py`
2. build a fresh runtime package ZIP
3. dry-run `create-app-backup`
4. run `prepare-runtime-update` against the freshly built ZIP
5. run `prepare-rollback-manifest` against a synthetic app backup ZIP
6. confirm the new BAT files are packaged automatically by the existing `*.bat` copy rule

## Recommended next packaging step

If this behaves cleanly on a real board PC, the next useful step is to rehearse a full closed loop on hardware:

1. extract runtime package
2. create app-only backup
3. prepare runtime update from downloaded ZIP
4. run update wrapper
5. validate app swap preserved `config/` + `data/`
6. prepare rollback from created app backup
7. run rollback wrapper
8. validate the board returns to the previous runtime app payload cleanly
