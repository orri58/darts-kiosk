# Device Runtime Package — Wave 8

## Goal

Wave 8 adds field-evidence capture around the rehearsal/update/rollback lane.

The missing gap after wave 7 was simple: we could prepare a realistic drill, but we still lacked a clean way to prove on a board PC that the runtime boundary stayed intact across the exercise.

This wave adds a tiny evidence layer that records:
- version before/after
- app/config/data/log boundary shape before/after
- tracked config/runtime file hashes
- update/rollback manifest status
- a Markdown field report operators can keep as proof

Still additive. No change to the protected local core. No change to the existing updater core.

## What changed

### 1. Runtime field-state capture

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py capture-field-state --state data/field_state_before.json
```

It records:
- `config/VERSION`
- `app/bin/VERSION`
- app/config/data/logs file counts and sizes
- current update/rollback manifest metadata
- hashes for a small tracked boundary set:
  - `config/VERSION`
  - `app/bin/VERSION`
  - `config/backend.env.example`
  - `config/frontend.env.example`

### 2. Before/after comparison and operator report

New command:

```bash
python app/bin/runtime_maintenance.py compare-field-state \
  --before data/field_state_before.json \
  --after data/field_state_after.json \
  --report data/field_report.md \
  --label update-to-4.4.4
```

It compares:
- version change
- app/config/data/log file-count deltas
- tracked config hash changes
- manifest state after the capture

It fails when the runtime boundary looks wrong, especially when:
- `data/` disappears
- `data/logs/` disappears
- tracked config files changed unexpectedly

### 3. Simple Windows wrapper for real device drills

Added:
- `release/runtime_windows/capture_field_evidence.bat`

Usage:

```bat
app\bin\capture_field_evidence.bat before update-to-4.4.4
app\bin\update_runtime.bat
app\bin\capture_field_evidence.bat after update-to-4.4.4
```

Result:
- `data\field_state_before.json`
- `data\field_state_after.json`
- `data\field_report.md`

That gives the runtime lane something much closer to an actual service drill artifact instead of only console output.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no invasive packaging changes
- new behavior is opt-in and runtime-lane only
- failure conditions are conservative and boundary-oriented

## Validation done in this pass

Recommended and/or executed validation:

1. syntax-check `runtime_maintenance.py`
2. targeted pytest for field-state capture/compare
3. verify the new wrapper is included automatically by existing `*.bat` copy logic
4. confirm the comparison flags tracked config changes while tolerating normal app/version movement

## Recommended next packaging step

Take this onto a real board PC and capture proof for both directions:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/capture_field_evidence.bat before update-to-X.Y.Z`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. run `app/bin/update_runtime.bat`
6. run `app/bin/capture_field_evidence.bat after update-to-X.Y.Z`
7. inspect `data/field_report.md`
8. perform rollback using the existing rollback manifest path
9. repeat capture for rollback proof if desired

After that, the next logical step is packaging/operator polish rather than more helper mechanics:
- stamp device/service ticket metadata into the report
- collect updater result/log references automatically
- optionally bundle the report + manifests + updater result into a support artifact
