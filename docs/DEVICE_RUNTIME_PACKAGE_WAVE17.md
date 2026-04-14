# Device Runtime Package — Wave 17

## Goal

Wave 17 turns the drill folder into something support can paste, not just inspect.

After wave 16, the handoff was already conservative and freshness-aware, but the final service step still had needless operator friction:
- someone still had to open the handoff, decide what two or three lines mattered, and rewrite them into a ticket comment
- the best attachment set was obvious to us, but not yet emitted explicitly for a tired field tech
- remote reviewers opening the bundle still had to reconstruct a concise status blurb from raw artifacts

That is exactly the kind of tiny manual step that creates inconsistent field updates.

This wave adds a ticket-ready export layer inside each drill folder, still without touching `updater.py`, the legacy release flow, or the protected local runtime core.

## What changed

### 1. Each drill folder now emits ticket-ready comment exports

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Every drill-folder refresh now also writes:

```text
data/support/drills/<label>/DRILL_TICKET_COMMENT.txt
data/support/drills/<label>/DRILL_TICKET_COMMENT.md
data/support/drills/<label>/DRILL_TICKET_COMMENT.json
```

The export is built from the existing handoff state and includes:
- recommendation status
- closed-loop / rollback-restored flags
- freshness status and warnings when present
- operator action text
- recommendation reasons
- suggested attachments based on the current artifact set
- source handoff manifest references

So support gets a pasteable summary instead of having to improvise one from `DRILL_HANDOFF.md`.

### 2. The ticket comment follows the same conservative guardrails as the handoff

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The ticket comment does not invent new logic.
It mirrors the current recommendation and freshness state already produced by the handoff manifest.

That means:
- fresh green closed-loop drills produce a clean `ship`-style ticket comment
- stale or misaligned paired evidence still lands as manual review instead of a misleading green paste
- incomplete drill folders produce an honest “not ready” comment instead of pretending the handoff is complete

### 3. Support bundles now carry the ticket comment too

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The bundle candidate list now includes:
- `DRILL_TICKET_COMMENT.txt`
- `DRILL_TICKET_COMMENT.md`
- `DRILL_TICKET_COMMENT.json`

So the ZIP contains:
- raw evidence
- the compact handoff manifest
- a ready-made ticket/update blurb

That improves remote support handoff ergonomics without changing any update behavior.

### 4. The paired-summary wrapper now points operators at the paste-ready files

Updated:
- `release/runtime_windows/summarize_paired_drill.bat`
- `release/runtime_windows/README_RUNTIME.md`

After rebuilding the paired summary and support bundle, the wrapper now prints the ticket-comment paths alongside the handoff-manifest paths.

That removes one more tiny “which file do I copy into the ticket?” decision.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all logic stays in the additive runtime packaging lane
- ticket comments are derived readback/export artifacts only; they do not alter update or rollback execution semantics

## Validation done in this pass

Executed and/or recommended:

1. Python syntax check for `runtime_maintenance.py`
2. targeted tests for:
   - ticket-comment export files appearing in the drill folder
   - ticket-comment JSON carrying the current recommendation + attachment hints
   - support bundles including the new ticket-comment files
3. runtime package build dry-run to confirm the new exports remain package-safe

## Recommended next packaging step

Run one realistic board-PC closed-loop drill and use the export exactly as intended:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. run the normal update/rollback drill through the existing lane
5. run `app/bin/summarize_paired_drill.bat board-pc-drill`
6. inspect:
   - `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
   - `data/support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt`
7. paste the ticket comment into the service note and attach the paired bundle
8. confirm the support ZIP also contains the ticket-comment exports for remote review

## Next likely wave

Best next move after this: one more operator guardrail around final handoff execution, for example:
- a single “finalize drill handoff” wrapper that refreshes pair summary, bundle, and ticket comment in one command
- an explicit attachment-readiness/status line for upload success/manual attach gaps
- a more explicit distinction between “aging but acceptable” and “stale enough to block shipping” in the operator-facing Markdown handoff
