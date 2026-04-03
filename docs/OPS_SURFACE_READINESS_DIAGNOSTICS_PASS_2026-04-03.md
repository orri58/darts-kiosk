# Ops surface pass — readiness, diagnostics, device-ops polish (2026-04-03)

## Intent

The previous ops/maintenance/install pass made the backend and update flows much more capable.
This pass closes the product gap: make those capabilities usable **inside the admin UI** for a real local board PC operator.

The rule for this pass was simple:
- do not invent parallel services
- surface the existing truth clearly
- reduce guesswork during troubleshooting
- avoid duplicate or misleading maintenance controls

## What was added

### 1. Readiness / preflight snapshot

New backend endpoint:
- `GET /api/system/readiness`

Purpose:
- answer the practical question: **is this board PC actually locally ready?**

Checks included:
- setup completion
- admin password rotation state
- quick PIN rotation state
- JWT / agent secret presence
- whether secrets are loaded into the current process
- `backend/.env` and `frontend/.env` presence
- data dir / DB / logs / backups / frontend build / VERSION presence
- local board id source and board-row lookup
- observer target URL prerequisites
- mock/headless visibility
- Windows Autodarts desktop EXE visibility

Shape:
- grouped checks (`Setup & access`, `Runtime & artifacts`, `Local board`, `Observer & device`)
- summary counts (`fail`, `warn`, `ok`)
- local URLs
- recommended next actions

### 2. Support snapshot

New backend endpoint:
- `GET /api/system/support-snapshot`

Purpose:
- show in the UI what the support bundle actually contains before exporting it
- make diagnostics readable even when the operator does not yet want to download a tarball

Included surfaces:
- system info
- health snapshot
- setup status
- readiness snapshot
- agent/device-ops status
- downloaded assets
- app backups
- last updater result
- secrets load state
- available log files + current log tail
- screenshot count/location

### 3. Support bundle alignment

`GET /api/system/logs/bundle` now uses the same support snapshot story and additionally includes:
- `snapshot/readiness.json`

That keeps the exported artifact aligned with what the UI shows.

## UI changes

### Health page

Added a real **Board-PC readiness** block near the top.

It now shows:
- overall readiness status
- blocker / warning counts
- grouped check cards
- local board identity and URLs
- DB path
- recommended next actions

Why here:
- Health is where the operator asks “what is wrong?”
- readiness/preflight belongs there more than in Setup or in a hidden backend endpoint

### System page

`Logs` became a broader **Diagnostics** surface.

It now shows:
- support snapshot summary cards
- support-bundle contents preview
- update/download/backup artifact counts
- screenshot/log counts
- current live log tail

This makes diagnostics useful even before exporting a bundle.

### Device Ops

The action surface was kept, but polished:
- inline last-action result card added
- success/failure remains visible after the toast disappears
- top copy now reinforces the safe recovery order

### Host & Dienste

Cleaned into a **read-only inventory** view.

Removed duplicate action buttons for:
- backend restart
- reboot / shutdown
- Autodarts ensure / restart

Reason:
- those actions already exist in Device Ops
- duplicated controls made the maintenance surface feel inconsistent and half-dead

### Updates

Downloaded assets now show whether they are:
- directly installable here
- or only manual / not directly installable

That avoids the old “some rows have buttons, some silently do not” ambiguity.

## Why this matters operationally

This pass deliberately optimizes for the first 2-5 minutes of troubleshooting on a board PC.

Before:
- setup/preflight truth was scattered
- support bundle was powerful but opaque
- maintenance controls were duplicated across tabs
- operators had to infer too much

After:
- readiness has a single operator-facing home
- diagnostics show what matters before export
- action surfaces are more coherent
- support can ask for a bundle without the operator feeling blind first

## Validation

Executed:

```bash
python3 -m compileall backend
cd frontend && npm run build
```

Outcome:
- backend compiles cleanly
- frontend production build succeeds

Not covered here:
- live Windows board-PC validation
- real shell switching / reboot / shutdown confirmation on hardware
- real observer recovery behaviour on an Autodarts-installed machine

Those still need a real-machine pass.
