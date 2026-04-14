# Device Runtime Package — Wave 5

## Goal

Wave 5 removes another very practical rehearsal gap in the runtime-only package lane:
operators may download a full runtime ZIP, but the rehearsal/update wrapper still expects an already-prepared staged `app/` tree.

This wave adds the missing bridge:

- accept a downloaded runtime ZIP
- extract only the replaceable `app/` payload into a staging directory
- keep `config/` and `data/` outside the staged replacement unit
- preserve the current release flow and avoid touching updater core semantics

## What changed

### 1. Runtime ZIP staging command added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:

```bash
python app/bin/runtime_maintenance.py stage-runtime-zip \
  --runtime-zip data/downloads/darts-kiosk-v4.4.4-windows-runtime.zip \
  --output-dir data/downloads/staged-v4.4.4
```

Behavior:
- opens a downloaded runtime ZIP
- detects whether the ZIP root is:
  - direct `app/ ...`, or
  - packaged under a single top-level runtime folder like `darts-kiosk-vX.Y.Z-windows-runtime/app/...`
- extracts only the `app/` subtree into the chosen staging directory
- rejects ZIPs that do not contain the expected runtime app shape:
  - `app/backend`
  - `app/frontend/build`
  - `app/agent`
  - `app/bin`

That keeps runtime update rehearsal aligned to the intended boundary contract:
replace `app/`, preserve `config/` + `data/`.

### 2. Windows helper for downloaded runtime ZIPs

Added:
- `release/runtime_windows/stage_runtime_update_zip.bat`

Usage:

```bat
app\bin\stage_runtime_update_zip.bat <runtime-zip> [output-dir]
```

Example:

```bat
app\bin\stage_runtime_update_zip.bat data\downloads\darts-kiosk-v4.4.4-windows-runtime.zip data\downloads\staged-v4.4.4
```

This gives operators a single obvious entry point for turning a downloaded artifact into rehearsal-ready staging.

### 3. Runtime README updated for ZIP-first rehearsal flow

Updated:
- `release/runtime_windows/README_RUNTIME.md`

The recommended operator path now explicitly supports:
1. download runtime ZIP
2. extract current runtime on device as usual
3. convert downloaded ZIP into app-only staging
4. prepare runtime-safe manifest
5. run rehearsal preflight
6. run update wrapper

## Why this is safe

- `release/build_release.sh` remains untouched
- existing repo-shaped release behavior remains untouched
- runtime package builder keeps copying `*.bat`, so the new helper is automatically included
- updater core behavior is still untouched
- stricter semantics remain inside the runtime package lane only

## Validation done in this pass

Recommended/attempted validation for this wave:

1. syntax-check `runtime_maintenance.py`
2. build a fresh runtime package ZIP
3. use `stage-runtime-zip` against that ZIP into a synthetic staging dir
4. run `prepare-update-manifest` against the staged output
5. run `validate-update`
6. run `rehearsal` against the synthetic runtime root

## Recommended next packaging step

If this behaves cleanly on a real board PC, the next useful move is to tighten rollback/update semantics around `app/` as the atomic replacement unit:

- explicit app backup naming per target version
- stronger staged-payload provenance metadata
- optional wrapper that chains:
  - ZIP staging
  - manifest prep
  - rehearsal preflight
- eventual core-updater awareness of runtime package boundaries instead of wrapper-only enforcement
