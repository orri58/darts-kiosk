# Device Runtime Package — Wave 15

## Goal

Wave 15 makes the drill-folder handoff less interpretive and more ticket-ready.

After wave 14, support could finally see whether a drill folder was complete, but the last judgment call still sat in a human head:
- is this evidence clean enough to ship?
- is rollback the part that needs another pass?
- or is the folder simply incomplete and not ready for review yet?

That is tiny friction, but tiny friction is exactly how field handoffs get vague.

This wave adds an explicit recommendation layer to the existing drill handoff artifacts, still without touching `updater.py`, the old release path, or the protected local core.

## What changed

### 1. Handoff manifests now carry an explicit recommendation

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Each drill folder’s `DRILL_HANDOFF.json/.md` now includes:
- `recommendation.status`
- `recommendation.summary`
- `recommendation.reasons[]`
- `recommendation.operator_action`

Current statuses:
- `ship`
- `retry_rollback`
- `needs_manual_review`

### 2. Recommendation logic follows the real closed-loop evidence

The runtime helper now derives the recommendation from artifact presence plus the paired summary result:

- `ship`
  - all expected drill artifacts exist
  - paired summary passed
  - rollback restored the starting version
- `retry_rollback`
  - paired summary exists
  - but the closed loop failed and/or rollback did not restore the starting version
- `needs_manual_review`
  - drill folder is still incomplete, or the paired summary/bundle is not ready yet

This keeps the handoff conservative: it only goes green when the evidence actually supports it.

### 3. The paired-summary wrapper now points the operator to the handoff manifest

Updated:
- `release/runtime_windows/summarize_paired_drill.bat`

After rebuilding the paired summary and support bundle, the wrapper now prints the exact `DRILL_HANDOFF.md/.json` paths for the service ticket handoff.

That removes one more tiny “which file should I attach?” moment from the field flow.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all behavior stays in the additive runtime packaging lane
- recommendation text is derived from existing evidence only; it does not alter update or rollback execution semantics

## Validation done in this pass

Executed and/or recommended:

1. Python syntax check for `runtime_maintenance.py`
2. targeted pytest for:
   - incomplete drill folder → `needs_manual_review`
   - fully green paired drill → `ship`
   - paired drill with rollback mismatch → `retry_rollback`
3. runtime package build dry-run to confirm the updated BAT wrapper still lands in the runtime ZIP

## Recommended next packaging step

Run one realistic board-PC update/rollback drill and verify the new final handoff behavior:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. run `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version>`
5. capture update before/after and rollback before/after through `capture_field_evidence.bat`
6. run `app/bin/summarize_paired_drill.bat board-pc-drill`
7. inspect `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
8. confirm the recommendation is accurate (`ship`, `retry_rollback`, or `needs_manual_review`)
9. attach the paired bundle plus handoff manifest to the service ticket

## Next likely wave

Best next move after this: reduce operator hopping one step further, for example:
- add one higher-level BAT wrapper for the full closed-loop evidence/handoff refresh lane
- surface artifact timestamp skew/freshness warnings directly in the handoff recommendation
- optionally emit one final ticket-comment snippet that support can paste verbatim
