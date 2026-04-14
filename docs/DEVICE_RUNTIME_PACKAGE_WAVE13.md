# Device Runtime Package — Wave 13

## Goal

Wave 13 makes the closed-loop runtime drill less easy to misuse on a real board PC.

After wave 12, the evidence lane could already prove update + rollback cleanly, but operators still had one annoying footgun:
- too many generic filenames
- too much reuse of the same `field_state_before.json` / `field_state_after.json`
- paired artifacts split between the shared support root and whatever the tech happened to remember

That is survivable in a lab and mildly cursed in the field.

This wave adds a dedicated per-drill workspace so one servicing run can keep its own checklist, update/rollback snapshots, summaries, and ZIP handoff artifacts together under one label — still without touching `updater.py`, the old release builder, or the protected local runtime core.

## What changed

### 1. Drill workspace initializer added

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/init_drill_workspace.bat`

New command:

```bash
python app/bin/runtime_maintenance.py init-drill-workspace \
  --label board-pc-drill \
  --device-id BOARD-17 \
  --operator orri \
  --service-ticket TICKET-2048
```

It creates:

```text
data/support/drills/<label>/
  DRILL_CHECKLIST.md
  drill-checklist.json
```

The checklist pre-stamps the expected artifact paths for:
- update before/after
- rollback before/after
- per-leg summaries
- paired summary
- per-leg and paired bundle locations

### 2. Evidence wrapper now supports leg-specific filenames in the drill folder

Updated:
- `release/runtime_windows/capture_field_evidence.bat`

When called with `update` or `rollback`, the wrapper now writes the leg artifacts into:

```text
data/support/drills/<label>/
```

Examples:

```bat
app\bin\capture_field_evidence.bat before board-pc-drill BOARD-17 orri TICKET-2048 update
app\bin\capture_field_evidence.bat after board-pc-drill BOARD-17 orri TICKET-2048 update
app\bin\capture_field_evidence.bat before board-pc-drill BOARD-17 orri TICKET-2048 rollback
app\bin\capture_field_evidence.bat after board-pc-drill BOARD-17 orri TICKET-2048 rollback
```

That produces leg-specific filenames instead of reusing one shared pair.

### 3. Paired summary wrapper now follows the same drill folder

Updated:
- `release/runtime_windows/summarize_paired_drill.bat`

The wrapper now defaults to:
- leg summaries inside `data/support/drills/<label>/`
- paired summary output inside the same folder
- paired support bundle beside those artifacts

So the closed-loop run behaves more like one service job and less like a pile of semi-related files.

### 4. Runtime helper can describe the drill workspace directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Added internal helper support for stable wave-13 drill paths so wrappers and tests use one source of truth for:
- checklist location
- update/rollback state paths
- report paths
- summary paths
- bundle paths

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all behavior stays in the additive runtime packaging lane
- this is ergonomics + artifact organization, not execution-semantics churn

## Validation done in this pass

Executed and/or recommended:

1. Python syntax check for `runtime_maintenance.py`
2. targeted pytest for:
   - drill workspace initialization
   - drill checklist creation
   - paired summary creation inside a wave-13 drill folder
3. runtime package build dry-run to confirm the new BAT wrapper is copied by the existing `*.bat` packaging path

## Recommended next packaging step

Run one realistic board-PC update/rollback drill entirely through the new folderized path:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. capture `before ... update`
6. run update
7. capture `after ... update`
8. capture `before ... rollback`
9. run rollback
10. capture `after ... rollback`
11. run `app/bin/summarize_paired_drill.bat board-pc-drill`
12. archive the folder under `data/support/drills/board-pc-drill/`

## Next likely wave

Best next move after this: make the drill folder even more support-friendly, for example:
- auto-mark checklist step completion as artifacts appear
- add one compact handoff manifest summarizing every file in the folder
- optionally emit one ticket-ready top-level README with the final recommendation/status
