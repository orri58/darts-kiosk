# Device Runtime Package — Wave 11

## Goal

Wave 11 closes a real servicing gap left after wave 10: the evidence lane still proved boundary shape and drill metadata, but it did not reliably preserve **what the updater actually did**.

That is annoying in the field. A support ZIP without updater action/exit context still leaves people asking:
- was this an install update or a rollback?
- did the wrapper actually run the updater?
- what exit code came back?
- was `update_result.json` present?
- where was the updater log written?

This wave adds a tiny updater-run artifact and threads it through the runtime evidence path. Still additive. Still no change to `updater.py`, `release/build_release.sh`, or the protected local core.

## What changed

### 1. Wrapper now records each updater run

Updated:
- `release/runtime_windows/update_runtime.bat`
- `release/runtime_windows/runtime_maintenance.py`

After invoking `python app/bin/updater.py ...`, the wrapper now writes:

```text
data/last_updater_run.json
```

Captured fields include:
- manifest path + manifest action (`install_update` or `rollback`)
- target version / backup path when present
- updater exit code
- whether the run is marked `ok`
- whether `data/update_result.json` existed
- updater log path + size when found
- timestamp + optional notes field

This is intentionally wrapper-side so we do not have to touch the existing updater implementation.

### 2. Field-state captures now include updater evidence summary

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`capture-field-state` now records an `updater_artifacts` section summarizing:
- last updater-run record presence/data
- `update_result.json` presence/data
- updater log presence/path
- derived action / exit code / ok status

That means the before/after JSON is no longer blind to the actual update or rollback attempt.

### 3. Field report now surfaces updater action/exit/result/log status

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`compare-field-state` and `data/field_report.md` now include:
- updater manifest action after capture
- updater exit code after capture
- updater ok status
- `update_result.json` presence
- updater log presence

So the Markdown report now reads like a real service artifact instead of only a boundary diff.

### 4. Support bundle now carries the updater-run artifact automatically

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`build-support-bundle` now includes these files when present:
- `last_updater_run.json`
- `update_result.json`

That makes the ZIP self-contained enough for remote support or drill review without asking the operator for another screenshot or console snippet.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- wrapper-side evidence capture is additive and runtime-lane only
- rollback support comes "for free" because the wrapper records the manifest action it was asked to execute

## Validation done in this pass

Executed and/or recommended:

1. python syntax check for `runtime_maintenance.py`
2. targeted pytest for runtime field evidence/support bundle behavior
3. runtime package build dry-run to confirm updated helper files still land in the runtime ZIP

## Recommended next packaging step

Run one full board-PC closed-loop drill and confirm the support ZIP now contains updater-proof artifacts too:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/capture_field_evidence.bat before update-to-X.Y.Z BOARD-XX <operator> <ticket>`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. run `app/bin/update_runtime.bat`
6. run `app/bin/capture_field_evidence.bat after update-to-X.Y.Z BOARD-XX <operator> <ticket>`
7. inspect `data/field_report.md` for updater action/exit/result/log lines
8. inspect the generated ZIP under `data/support/` for `last_updater_run.json`
9. switch to rollback manifest, run `app/bin/update_runtime.bat` again, and repeat after-capture if paired rollback evidence is wanted

## Next likely wave

Best next move after this: pair update and rollback evidence into a single drill-status summary so support can see "update leg passed / rollback leg passed" without opening multiple artifacts.
