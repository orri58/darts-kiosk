# Device Runtime Package — Wave 1

## What was added

A new additive builder was introduced:

- `release/build_runtime_package.sh`

It creates a separate Windows runtime-only archive:

- `release/build/darts-kiosk-v<version>-windows-runtime.zip`

This does **not** replace or alter the existing `release/build_release.sh` flow.

## Runtime package shape

```text
app/
  backend/
  frontend/build/
  agent/
  bin/
config/
  backend.env.example
  frontend.env.example
  VERSION
data/
  db/
  logs/
  backups/
  app_backups/
  downloads/
  assets/
  chrome_profile/
  kiosk_ui_profile/
```

## Builder behavior

The runtime builder:

- rebuilds the frontend by default
- stages backend runtime without tests / pycache / sqlite / `.env`
- stages frontend build output only
- stages agent runtime files
- places runtime-specific Windows launcher scripts into `app/bin/`
- copies env examples + version into `config/`
- creates empty writable roots in `data/`
- runs the advisory allowlist audit at the end

Optional shortcut:

```bash
./release/build_runtime_package.sh --reuse-frontend
```

Use that only when `frontend/build/` is already known-good.

## Current limitations

This is intentionally wave 1, not the final runtime deploy format.

Wave-2 additions now landed on top of the wave-1 package track:

- runtime validation helper (`app/bin/validate_runtime.bat`)
- runtime cleanup/retention helper (`app/bin/cleanup_runtime.bat` + `runtime_maintenance.py`)
- update wrapper now validates runtime layout before launching the updater
- retention overrides documented via `config/runtime_retention.env.example`

Still pending:

- runtime-specific updater should eventually target `app/` replacement semantics explicitly
- better Windows kiosk launcher parity with the top-level package
- board-PC validation on real hardware
- deciding whether any support docs should remain in-package or move out entirely

## Recommended next step

Validate one extracted runtime package on a board PC and confirm:

1. `setup_runtime.bat` installs the required Python runtime successfully
2. `validate_runtime.bat` passes before first launch
3. backend starts from `app/backend/`
4. frontend serves correctly from `app/frontend/build/`
5. agent still starts from `app/agent/`
6. logs/state stay confined to `data/`
7. `cleanup_runtime.bat --apply` prunes only disposable runtime artifacts

After that, the next packaging move should be a real staged update rehearsal on device using `update_runtime.bat` plus a generated `data/update_manifest.json`.
