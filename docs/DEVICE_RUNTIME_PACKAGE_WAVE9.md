# Device Runtime Package — Wave 9

## Goal

Wave 9 turns field evidence into an operator-handoff artifact.

After wave 8, a board-PC drill could produce the right proof pieces, but they still lived as separate files under `data/`. That is annoying in real servicing: people forget one JSON, upload the wrong log, or send screenshots instead of the actual manifests.

This wave adds a support-bundle step that packages the runtime drill evidence into one ZIP without changing the updater core or the old release flow.

## What changed

### 1. Support bundle command added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py build-support-bundle --label update-to-4.4.4
```

Default bundle contents:
- `field_state_before.json`
- `field_state_after.json`
- `field_report.md`
- `update_manifest.json`
- `rollback_manifest.json`
- recent files from `data/logs/`
- generated `bundle_summary.json`

Default output:
- `data/support/runtime-support-bundle-<label>-<timestamp>.zip`

### 2. Evidence wrapper now closes the loop

Updated:
- `release/runtime_windows/capture_field_evidence.bat`

`after` mode now:
1. captures `data/field_state_after.json`
2. writes/validates `data/field_report.md`
3. tries to build a support ZIP under `data/support/`

That means the normal operator path now leaves behind a single artifact suitable for service notes, remote review, or retention.

### 3. Dedicated bundle wrapper added

Added:
- `release/runtime_windows/build_support_bundle.bat`

Usage:

```bat
app\bin\build_support_bundle.bat update-to-4.4.4
```

Optional second arg:
- custom output path

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local game/runtime logic
- runtime-only lane remains additive
- support bundling reads existing drill artifacts; it does not alter app/config/data boundaries

## Validation done in this pass

Executed and/or recommended:

1. python syntax check for `runtime_maintenance.py`
2. targeted pytest for field evidence + support bundle creation
3. fresh runtime package build dry-run to confirm the new BAT wrapper is included by existing `*.bat` copy behavior
4. synthetic bundle inspection to confirm manifests/report/logs are present in the ZIP

## Recommended next packaging step

Run one real board-PC rehearsal and keep the produced support ZIP as the service artifact:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/capture_field_evidence.bat before update-to-X.Y.Z`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. run `app/bin/update_runtime.bat`
6. run `app/bin/capture_field_evidence.bat after update-to-X.Y.Z`
7. archive the generated file from `data/support/`
8. perform rollback using the rollback manifest path and optionally repeat the same evidence flow

## Next likely wave

Best next move after this: stricter operator metadata and drill traceability, for example:
- service ticket / device ID / operator stamp in the field report and support bundle summary
- explicit updater exit-code/result capture
- optional rollback-side second bundle for a full update+rollback evidence pair
