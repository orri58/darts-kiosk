# Device Runtime Package — Wave 14

## Goal

Wave 14 turns the wave-13 drill folder from "better organized evidence" into a more realistic field handoff surface.

After wave 13, update/rollback artifacts finally stopped trampling each other, but support still had two annoying jobs:
- visually inspect whether the drill was actually complete
- figure out which artifact was still missing before closing a ticket or asking the operator for one more file

That is exactly the kind of tiny coordination tax that causes sloppy field evidence.

This wave adds a self-refreshing checklist and a compact handoff manifest inside each drill folder, still without touching `updater.py`, the old release flow, or the protected local core.

## What changed

### 1. Drill checklist now auto-refreshes from real artifact presence

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The drill checklist JSON/Markdown is no longer a static scaffold only.
Whenever drill-folder artifacts are written, the runtime helper now refreshes step completion from actual files, including:
- update before/after captures
- update leg summary + bundle
- rollback before/after captures
- rollback leg summary + bundle
- paired summary + paired bundle

That means operators and support can glance at one file and see what is done instead of guessing from filenames.

### 2. Each drill folder now emits a compact handoff manifest

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Every initialized drill folder now gets:

```text
data/support/drills/<label>/DRILL_HANDOFF.json
data/support/drills/<label>/DRILL_HANDOFF.md
```

The handoff manifest includes:
- drill metadata
- step completion state
- next suggested operator step
- key artifact presence/paths
- closed-loop result when the paired summary exists
- rollback-restored-start-version status when available

So support gets one ticket-ready status document instead of spelunking through the whole folder.

### 3. Bundle builder now carries checklist + handoff docs too

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Support ZIPs now include the drill-folder support docs when present:
- `drill-checklist.json`
- `DRILL_CHECKLIST.md`
- `DRILL_HANDOFF.json`
- `DRILL_HANDOFF.md`

That makes the ZIP better for remote review or escalation because the bundle contains both raw evidence and the operator-facing completion view.

### 4. Refresh happens on the normal runtime lane, not via a new fragile ritual

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The drill status refresh is triggered during the existing runtime flow:
- drill workspace initialization
- drill-folder field-state capture
- drill-leg summary generation
- paired summary generation
- support-bundle generation

So operators do not need to remember a separate maintenance step just to keep the drill folder truthful.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all logic stays in the additive runtime packaging lane
- artifacts are support/readback only; they do not alter update or rollback execution semantics

## Validation done in this pass

Executed and/or recommended:

1. Python syntax check for `runtime_maintenance.py`
2. targeted pytest for:
   - drill workspace initialization now producing handoff docs
   - checklist auto-refresh when drill artifacts appear
   - support bundles carrying checklist/handoff files from the drill folder
3. runtime package build dry-run to confirm the helper remains package-safe

## Recommended next packaging step

Run one full board-PC drill using the wave-14 handoff lane:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. capture update before/after and rollback before/after through `capture_field_evidence.bat`
6. run `app/bin/summarize_paired_drill.bat board-pc-drill`
7. inspect `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
8. confirm the paired support ZIP now contains the checklist + handoff docs alongside the evidence artifacts

## Next likely wave

Best next move after this: make the drill folder even more ticket-ready, for example:
- emit a one-page operator README with final recommendation text (`ship`, `retry rollback`, `needs manual review`)
- add explicit manifest/status fields for updater log freshness and artifact timestamp skew
- optionally add a single wrapper for the whole closed-loop evidence drill so operators stop hopping between multiple BAT entrypoints
