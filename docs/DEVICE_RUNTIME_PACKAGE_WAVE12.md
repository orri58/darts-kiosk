# Device Runtime Package — Wave 12

## Goal

Wave 12 adds the missing closed-loop servicing summary for a real board-PC update/rollback drill.

After wave 11, the runtime lane could already prove a lot:
- what the updater was asked to do
- whether it exited cleanly
- whether result/log artifacts existed
- whether boundary state stayed sane

But support still had to manually stitch together the **update leg** and the **rollback leg** to answer the obvious field question:

> Did the board survive the update, and did rollback bring it back cleanly?

That is boring work, and boring work gets skipped in the field.

This wave adds paired drill summaries on top of the existing evidence path, still without touching `updater.py`, the old release flow, or the protected local core.

## What changed

### 1. Per-leg drill summaries added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New helper command:

```bash
python app/bin/runtime_maintenance.py build-drill-leg-summary \
  --label board-pc-drill \
  --leg update \
  --before data/field_state_before.json \
  --after data/field_state_after.json \
  --report data/field_report.md
```

It writes a durable JSON summary under `data/support/`, for example:

```text
data/support/drill-leg-update-board-pc-drill.json
```

The leg summary carries:
- comparison payload
- drill context
- updater action/exit/result/log checks
- explicit pass/fail checklist for support review

### 2. Closed-loop pair summary added

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New helper command:

```bash
python app/bin/runtime_maintenance.py build-paired-drill-summary \
  --label board-pc-drill \
  --update-leg data/support/drill-leg-update-board-pc-drill.json \
  --rollback-leg data/support/drill-leg-rollback-board-pc-drill.json
```

Outputs:

```text
data/support/paired-drill-summary-board-pc-drill.json
data/support/paired-drill-summary-board-pc-drill.md
```

The pair summary answers, in one place:
- did the update leg pass?
- did the rollback leg pass?
- did rollback restore the starting version?
- is the whole closed loop green?

### 3. Evidence wrapper can stamp the current leg

Updated:
- `release/runtime_windows/capture_field_evidence.bat`

`after` mode now accepts an optional sixth arg:
- `update`
- `rollback`

Examples:

```bat
app\bin\capture_field_evidence.bat after update-to-4.4.4 BOARD-17 orri TICKET-2048 update
app\bin\capture_field_evidence.bat after rollback-to-4.4.3 BOARD-17 orri TICKET-2048 rollback
```

If provided, the wrapper writes the matching leg summary automatically after generating `data/field_report.md`.

### 4. Operator helper for the paired view added

Added:
- `release/runtime_windows/summarize_paired_drill.bat`

Usage:

```bat
app\bin\summarize_paired_drill.bat board-pc-drill
```

It:
1. builds the closed-loop pair summary
2. refreshes the support bundle so the pair summary rides along with the ZIP

### 5. Support bundles now carry the paired evidence too

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`build-support-bundle` now includes matching files when present:
- `support/drill-leg-update-<label>.json`
- `support/drill-leg-rollback-<label>.json`
- `support/paired-drill-summary-<label>.json`
- `support/paired-drill-summary-<label>.md`

That makes the bundle closer to a real operator handoff artifact instead of a pile of raw evidence.

### 6. Drill-phase comparison relaxed the right way

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Before/after evidence pairs now treat `drill_phase=before` → `drill_phase=after` as the expected progression instead of flagging it as a mismatch.

That removes an annoying false-negative from the real field flow while preserving mismatch checks for the important identifiers (board/operator/ticket/label).

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all logic stays in the additive runtime lane
- pair summaries are derived artifacts only; they do not change update execution semantics

## Validation done in this pass

Executed and/or recommended:

1. Python syntax check for `runtime_maintenance.py`
2. targeted pytest for runtime field evidence
3. test coverage for:
   - before/after drill-phase progression without false mismatch
   - per-leg summary generation
   - paired update+rollback closed-loop summary generation
4. runtime package build dry-run to confirm the new BAT wrapper lands in the runtime ZIP via existing `*.bat` copy behavior

## Recommended next packaging step

Run one full board-PC drill using the new paired summary lane:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. prepare update + rollback manifests with `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
4. capture update-before state
5. run update
6. capture update-after state with `... update`
7. capture rollback-before state
8. run rollback
9. capture rollback-after state with `... rollback`
10. run `app/bin/summarize_paired_drill.bat <label>`
11. archive the ZIP from `data/support/` plus the generated pair summary files

## Next likely wave

Best next move after this: tighten the operator path from “good evidence” to “mistake-resistant evidence”, for example:
- explicit wrapper support for dedicated update-before/update-after/rollback-before/rollback-after filenames so the paired flow needs less manual file juggling
- bundle a tiny service checklist/status file that marks prep/update/rollback/pair-summary completion steps
- optionally preserve both leg reports side-by-side in a single named drill folder under `data/support/`
