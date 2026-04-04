# Darts Kiosk — Release & Update Guide

## Purpose

This is the current release path for the repo as it exists now:
- local-first board PC baseline
- optional central/portal surfaces still in-tree, but not required for local play
- release artifacts built from the repo root via the shared release script

The goal is simple: **one source of truth for versioning and packaging**, with the Windows/Linux/source artifacts matching what the product actually ships.

---

## 1. Version source of truth

`VERSION` in the project root is the canonical release version.

Current example:

```text
4.3.0
```

That value is consumed by:
- backend version/status endpoints
- the Windows agent runtime/status surface
- `release/build_release.sh`
- generated artifact names in `release/build/`
- release/update UI flows that compare installed vs available versions

### Bump the version

```bash
echo "4.0.1" > VERSION
```

Use plain semver when possible (`MAJOR.MINOR.PATCH`).
Use stable semver for product releases (`4.1.0`, `4.1.1`, `4.2.0`).
Only use suffixes for real pre-releases (`-rc.1`, `-beta.1`) and keep the Git tag + uploaded assets identical.

---

## 2. The release build command

From the repo root:

```bash
bash release/build_release.sh
```

That script is the packaging source of truth.
It will:
- clean old generated artifacts
- run a deterministic frontend install/build via `npm ci && npm run build`
- generate filtered backend requirements for production bundles
- build the Windows package
- build the Linux package
- build the source export
- verify the expected release contents

Generated output lands in:

```text
release/build/
```

Expected artifact names:

```text
darts-kiosk-v{VERSION}-windows.zip
darts-kiosk-v{VERSION}-linux.tar.gz
darts-kiosk-v{VERSION}-source.zip
```

Example for the current repo state:

```text
darts-kiosk-v4.3.0-windows.zip
darts-kiosk-v4.3.0-linux.tar.gz
darts-kiosk-v4.3.0-source.zip
```

---

## 3. What the Windows package contains

The Windows artifact is meant for a board PC bring-up path.

It includes the current product shape:
- `backend/`
- `frontend/` source + `frontend/build/`
- `agent/`
- `central_server/` (optional/in-tree, not required for local play)
- `kiosk/` experimental hard-kiosk helpers
- `release/windows/*` operator scripts copied to package root
- `VERSION`
- env examples and runtime helper files

It intentionally does **not** include live runtime state such as:
- `data/`
- `logs/`
- `.env`
- local venvs / node_modules

---

## 4. Recommended release flow

### Step 1 — validate before shipping

Practical repo-side validation:

```bash
source .venv/bin/activate
python -m compileall backend agent
python -m pytest -q \
  backend/tests/test_phase34_autodarts_triggers.py \
  backend/tests/test_phase34_credits_pricing.py \
  backend/tests/test_phase56_stability_installation.py \
  backend/tests/test_phase789_local_core_validation.py
cd frontend && npm run build
```

Then run the packaging build:

```bash
cd ..
bash release/build_release.sh
```

### Step 2 — commit the version bump

```bash
git add VERSION CHANGELOG.md release/source/RELEASE_NOTES.md
git commit -m "Release v4.3.0"
```

### Step 3 — tag the release

```bash
git tag v4.3.0
git push origin main --tags
```

If the version includes a suffix, tag it exactly the same way:

```bash
git tag v4.0.0-recovery
```

### Step 4 — publish the GitHub release

Upload the files from `release/build/`.

Release assets should always be the three artifacts created by the shared build script:
- `darts-kiosk-v{VERSION}-windows.zip`
- `darts-kiosk-v{VERSION}-linux.tar.gz`
- `darts-kiosk-v{VERSION}-source.zip`

The GitHub workflow is expected to call the same release script so CI and local packaging stay aligned.

---

## 5. Update path in the product

The admin UI update flow is intentionally optional and maintenance-focused.

Typical operator flow:
1. **System → Updates**
2. check GitHub releases
3. use **Jetzt installieren** for the direct Windows path, or inspect packages manually if needed
4. let the app create a backup + download + validate the release package
5. let the updater restart + verify the install
6. if needed, roll back from an app backup

Protected runtime state is not supposed to be overwritten by normal app updates:
- `data/`
- `logs/`
- `backend/.env`
- `frontend/.env`
- persistent Chrome/observer profiles

---

## 6. Windows board-PC notes

The intended Windows operator path is:
1. `install.bat`
2. edit `backend\.env`
3. `setup_profile.bat`
4. `start.bat`
5. `smoke_test.bat`

Important current assumptions:
- frontend install on Windows now uses **npm**, matching the shared release build
- local play should stay usable without central connectivity
- `BOARD_ID` is the key board-local identity for scripts and kiosk URLs

For board-PC details see:
- `release/windows/README.md`
- `release/windows/MANUAL_DEPLOYMENT.md`
- `docs/RUNBOOK.md`
- `docs/STATUS.md`

---

## 7. CI / automation rule

Do not maintain a second independent packaging definition in CI.

The preferred rule is:
- local release build = `bash release/build_release.sh`
- CI release build = `bash release/build_release.sh`

If packaging changes, update the script first and let the workflow call it.

That keeps:
- file inclusion rules
- env examples
- filtered requirements
- artifact names
- build verification

in one place instead of drifting.

---

## 8. What still requires real-machine validation

Repo-side packaging/build validation is useful, but it does **not** replace:
- real Windows setup on a board PC
- live Autodarts login/profile handling
- kiosk/focus behavior on an actual machine
- smoke/start/update/rollback checks with the packaged Windows artifact on real hardware

Treat repo validation as necessary, not sufficient.
