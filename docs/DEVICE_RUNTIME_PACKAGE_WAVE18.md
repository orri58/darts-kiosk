# Device Runtime Package — Wave 18

## Goal

Wave 18 adds the final operator-facing handoff wrapper for the closed-loop drill lane.

After wave 17, all the right artifacts existed, but the last operator motion still involved a tiny bit of memory and command selection:
- rebuild the paired summary
- rebuild the paired support bundle
- refresh the handoff manifest
- then copy the ticket comment

That is not hard, but it is exactly the kind of sleepy field-tech footgun that turns a clean drill into an inconsistent handoff.

This wave adds one explicit finalize step that reuses the existing maintenance logic, still without touching `updater.py`, the legacy release builder, or the protected local runtime core.

## What changed

### 1. New finalize command in the runtime helper

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New CLI command:
- `finalize-drill-handoff`

The command:
- rebuilds the paired summary from the current update/rollback leg summaries
- rebuilds the paired support bundle
- refreshes `DRILL_HANDOFF.json/.md`
- refreshes `DRILL_TICKET_COMMENT.txt/.md/.json`
- returns a combined payload with the final key paths
- exits green only when the refreshed recommendation is `ship`

So support can treat it as the final gate without inventing any new trust logic.

### 2. New operator wrapper for the last mile

Added:
- `release/runtime_windows/finalize_drill_handoff.bat`

The BAT wrapper points at the canonical drill-folder artifacts by default and runs the new finalize command in one step.

Operator outcome:
- one command to refresh the final handoff set
- one exit status that says whether the folder is actually ready to ship
- the same manifest/ticket-comment paths echoed every time

### 3. Runtime README documents the new handoff step

Updated:
- `release/runtime_windows/README_RUNTIME.md`

The runtime notes now describe the finalize wrapper as the final explicit handoff command for the board-PC drill lane.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update or rollback execution semantics
- the new wrapper only composes already-existing paired-summary, support-bundle, and handoff-refresh behavior

## Validation done in this pass

Executed:

1. Python syntax check for `release/runtime_windows/runtime_maintenance.py`
2. targeted tests covering:
   - finalize command producing paired summary + paired bundle + refreshed handoff exports in one pass
   - finalize command returning exit-ready `ship` when the drill folder is clean
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC field drill using the new last-mile command:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. run the normal update and rollback legs with the existing capture flow
5. run `app/bin/finalize_drill_handoff.bat board-pc-drill`
6. inspect:
   - `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
   - `data/support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt`
7. if the wrapper exits green, attach the paired bundle and paste the ticket comment into the service ticket

## Next likely wave

Best next move after this: stay in ergonomics/guardrails, not core churn. Good candidates:
- explicit attachment checklist text inside the ticket comment for “attach these files now” discipline
- optional operator note capture at finalize time so the final ticket export includes board-specific observations
- a tiny wrapper around update/rollback evidence capture if the real board-PC trial still shows command-order confusion
