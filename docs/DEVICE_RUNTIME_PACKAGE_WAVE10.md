# Device Runtime Package — Wave 10

## Goal

Wave 10 adds operator-grade drill traceability to the runtime evidence lane.

After wave 9, board-PC update drills could already leave behind a clean support ZIP. The remaining gap was annoying but real: the artifact still did not reliably say **which board**, **which operator**, or **which service ticket** it belonged to. In a real field loop, that creates avoidable ambiguity.

This wave adds lightweight metadata stamping to the existing runtime helper and wrappers so update/rollback evidence can be tied to a concrete servicing event without changing the updater core, the old release path, or the protected local runtime logic.

## What changed

### 1. Drill metadata can be stamped into field-state captures

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`capture-field-state` now accepts optional context fields:

```bash
python app/bin/runtime_maintenance.py capture-field-state \
  --state data/field_state_before.json \
  --label update-to-4.4.4 \
  --device-id BOARD-17 \
  --operator orri \
  --service-ticket TICKET-2048 \
  --drill-phase before
```

Captured context is written into the JSON under `drill_context`.

### 2. Field report now carries and validates drill context

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`compare-field-state` now:
- carries drill metadata into `data/field_report.md`
- reports mismatches between before/after context
- fails if the context changes unexpectedly across the pair

That helps catch operator mistakes like mixing before/after snapshots from different boards or tickets.

### 3. Support bundle summary now includes the same metadata

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`build-support-bundle` now writes drill metadata into `bundle_summary.json`, so the ZIP itself remains traceable even when copied away from the runtime root.

### 4. Windows wrappers accept board/operator/ticket parameters

Updated:
- `release/runtime_windows/capture_field_evidence.bat`
- `release/runtime_windows/build_support_bundle.bat`
- `release/runtime_windows/README_RUNTIME.md`

Examples:

```bat
app\bin\capture_field_evidence.bat before update-to-4.4.4 BOARD-17 orri TICKET-2048
app\bin\capture_field_evidence.bat after update-to-4.4.4 BOARD-17 orri TICKET-2048
app\bin\build_support_bundle.bat update-to-4.4.4 "" BOARD-17 orri TICKET-2048
```

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- metadata stamping is additive and optional
- comparison only gets stricter about evidence consistency; it does not widen the replacement boundary

## Validation done in this pass

Executed and/or recommended:

1. Python syntax check for `runtime_maintenance.py`
2. targeted pytest for field evidence metadata/report/bundle behavior
3. runtime package build dry-run to confirm updated BAT wrappers still land in the runtime ZIP via the existing `*.bat` copy path

## Recommended next packaging step

Run one full board-PC drill with explicit service metadata:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/capture_field_evidence.bat before update-to-X.Y.Z BOARD-XX <operator> <ticket>`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. run `app/bin/update_runtime.bat`
6. run `app/bin/capture_field_evidence.bat after update-to-X.Y.Z BOARD-XX <operator> <ticket>`
7. archive the produced ZIP from `data/support/`
8. perform rollback and repeat the same metadata-stamped capture if rollback evidence is also needed

## Next likely wave

Best next move after this: push from traceable evidence to fuller closed-loop servicing proof, for example:
- auto-capture updater exit/result details into the bundle summary
- add a rollback-side second bundle or paired drill summary
- produce a tiny operator checklist/status file that marks update complete vs rollback complete vs both
