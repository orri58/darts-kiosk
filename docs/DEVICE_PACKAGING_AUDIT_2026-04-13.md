# Device Packaging Audit — 2026-04-13

## Scope

Repo reviewed:
- `release/`
- `release/windows/`
- packaging/build docs
- current repo/runtime layout

Goal of this pass:
- audit current device footprint
- prepare a safe foundation for a future runtime-only device payload
- avoid breaking the existing release flow

## Executive read

Current release artifacts are **cleaner than a raw repo checkout**, but the Windows payload is still fundamentally **repo-shaped**, not **runtime-shaped**.

That means the bundle is usable for bring-up, but it still mixes:
- actual runtime assets
- build/setup material
- optional surfaces not required for local board play
- documentation/operator content

So the right next move is **not** a risky packaging rewrite.
The right next move is:
1. freeze a runtime allowlist,
2. add an audit step,
3. then introduce a second runtime-only packaging target once validated on a board PC.

## What the current packaging does well

`release/build_release.sh` already avoids some obvious junk:
- excludes `.git`, `.env`, SQLite DB files, `__pycache__`, `*.pyc`
- excludes backend tests from Windows/Linux runtime bundles
- excludes `frontend/node_modules`
- builds frontend deterministically with `npm ci`
- keeps runtime state out of the shipped bundle (`data/`, logs, live env files)

That is a decent baseline.

## Main footprint findings

### 1. Windows bundle is still repo-shaped

Current Windows package includes:
- `backend/`
- `frontend/` source
- `frontend/build/`
- `agent/`
- `central_server/`
- `kiosk_experimental/`
- root-level helper scripts/docs

Implication:
- the device gets both runtime output **and** development/setup-oriented source layout.

### 2. Device setup still depends on dev-style frontend installation

`release/windows/setup_windows.bat` currently:
- requires Node.js
- runs `npm ci` or `npm install`
- runs `npm run build`

That is the clearest sign the package is still optimized for **board-PC bootstrap from semi-source bundle**, not for **runtime-only deployment**.

### 3. `frontend/` source ships even though `frontend/build/` is already present

The release script copies both:
- built frontend assets
- frontend source tree (minus `node_modules` and `build`)

For a runtime-only payload, only `frontend/build/` should be needed.

### 4. `central_server/` ships into board-device packages

Docs already say it is optional / not required for local play.
That makes it a good candidate for removal from the future board-runtime artifact.

Recommendation:
- keep it in source export,
- likely keep it out of the future board-runtime package unless a self-hosted all-in-one SKU is explicitly intended.

### 5. `kiosk_experimental/` is explicitly non-production but still shipped

Current release script copies the old kiosk helpers into `kiosk_experimental/` with an experimental warning.
That is fine for repo/recovery convenience, but it is noise on a production device.

### 6. Operator docs/scripts are mixed into app root

The current Windows ZIP puts everything at top level.
This works, but it makes update boundaries fuzzy.

A runtime-shaped payload should move toward a clearer split:
- `app/` → replaceable program payload
- `config/` → stable env/version examples and device metadata
- `data/` → persistent writable state

### 7. Current built Windows artifact size is modest, but shape is the real problem

Observed packaged Windows artifact (`release/build/darts-kiosk-v4.4.3-windows.zip`):
- about `300` entries
- about `9.8 MB` uncompressed content represented in the archive listing summary
- dominated by `frontend/`

So this is **not** mainly a size emergency.
It is a **boundary / update-discipline** problem.

## Risk assessment

### Low-risk to change now
- add an allowlist manifest draft
- add a dry-run audit script
- document retention/cleanup expectations
- plan a future `runtime` packaging target alongside the current release target

### Higher-risk to change immediately
- rewriting `release/build_release.sh` to ship a different layout now
- removing `frontend/` source from the existing Windows bundle immediately
- making Windows install skip Node before validating the runtime path on real hardware
- dropping optional trees that current support/recovery flow may still rely on

## Recommended target shape for board devices

### Future board-runtime payload

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
  chrome_profile/
  kiosk_ui_profile/
```

### Likely keep out of board-runtime payload
- `frontend/src`
- `frontend/public`
- `central_server/`
- `kiosk_experimental/`
- repo docs not needed by operator on-device
- test and analysis files
- build-system-only material

## Concrete artifacts added in this pass

### 1. Draft allowlist manifest
- `release/runtime_package_allowlist.json`

Purpose:
- defines the future runtime-only target shape
- documents allowed roots, exclusions, required paths, and retention intent
- advisory only for now

### 2. Dry-run audit helper
- `scripts/audit_runtime_package.py`

Purpose:
- audits an extracted package directory or built archive against the allowlist
- safe by default
- does not mutate files
- can later become part of a release gate

Example usage:

```bash
python3 scripts/audit_runtime_package.py release/build/darts-kiosk-v4.4.3-windows.zip
python3 scripts/audit_runtime_package.py release/build/darts-kiosk-v4.4.3-windows.zip --strict
```

## Recommended cleanup / retention policy

### Device retention
- keep only current update payload + last rollback payload
- keep only last 2 app backups by default
- rotate logs by size/file-count
- auto-expire support bundles after short TTL

### Packaging cleanup targets
First removal candidates for runtime-only board package:
1. `frontend/` source
2. `central_server/`
3. `kiosk_experimental/`
4. non-operator repo docs

## Recommended next packaging step

**Best next step:**
add a **second packaging target**, not a replacement.

Suggested approach:
1. keep `release/build_release.sh` behavior unchanged for current operators,
2. add a new `runtime-only` Windows package builder beside it,
3. shape that new artifact to the allowlist layout,
4. adapt Windows scripts in that new package so they no longer require local frontend build tooling,
5. validate on one real board PC before promoting it.

That gives a migration path from repo-deploys to runtime-deploys without breaking the current release line.

## Bottom line

The repo is already partway toward controlled packaging, but not yet at a true device-runtime artifact.

This pass adds the safe missing foundation:
- explicit allowlist draft
- audit tooling
- concrete packaging boundary notes

That is enough to start a controlled runtime-only package track without touching local core behavior or destabilizing the current release flow.
