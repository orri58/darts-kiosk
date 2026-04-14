# Device Runtime Package — Wave 21

## Goal

Wave 21 closes the last small gap between "the drill handoff is ready" and "the final ticket step really happened".

After wave 20, the runtime lane could already:
- prove the update/rollback drill passed
- produce the paired bundle + handoff manifest
- tell the operator exactly what to attach
- preserve short board-side notes

But one sleepy field-service gap still remained:
- support could see that artifacts were attach-ready
- the drill folder had no explicit place to record that the upload/paste step actually happened
- that made "ready to attach" and "attached" look too similar during later review

This wave adds a tiny post-attach acknowledgment block in the additive runtime lane only.

## What changed

### 1. New post-attach acknowledgment command

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New CLI command:
- `acknowledge-drill-handoff`

The command persists a compact acknowledgment back into the drill workspace:
- `attached_by`
- `attached_at`
- `ticket_status`
- optional note

It then refreshes `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` so the generated artifacts reflect not just readiness, but confirmed ticket upload state.

### 2. Handoff and ticket exports now distinguish readiness from acknowledgment

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now carries the post-attach acknowledgment block.

Operator-facing exports now show:
- whether the package is `ready_to_attach`
- whether the attach step was actually `acknowledged`
- the recorded `attached_by`, `attached_at`, and `ticket_status` values when present

That keeps the final evidence set support-friendly without changing update, rollback, or finalize semantics.

### 3. New operator BAT wrapper for the final ticketing proof step

Added:
- `release/runtime_windows/acknowledge_drill_handoff.bat`

The wrapper gives the board-PC lane one small explicit command after the actual ticket upload, for example:

```bat
app\bin\acknowledge_drill_handoff.bat board-pc-drill orri attachments_uploaded "Paired bundle + handoff attached to Jira"
```

### 4. Finalize wrapper now points at the optional follow-up command

Updated:
- `release/runtime_windows/finalize_drill_handoff.bat`
- `release/runtime_windows/README_RUNTIME.md`

After a clean finalize, operators are now reminded how to stamp the post-attach acknowledgment once the real ticket step is done.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update, rollback, or finalize decision logic
- behavior is additive and limited to drill-folder metadata + generated support artifacts

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms the existing closed-loop handoff tests still pass
   - confirms post-attach acknowledgment persists into the drill workspace
   - confirms handoff/ticket exports show the acknowledgment state and metadata
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill with the new final acknowledgment path:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. perform the normal update + rollback drill and evidence capture
5. run `app/bin/finalize_drill_handoff.bat board-pc-drill`
6. attach the paired bundle + handoff manifest to the service ticket
7. run `app/bin/acknowledge_drill_handoff.bat board-pc-drill <operator> attachments_uploaded "paired bundle + manifest attached"`
8. inspect:
   - `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
   - `data/support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt`
9. confirm they now show both:
   - `Attachment ready: yes`
   - `Attachment acknowledged: yes`

## Next likely wave

Best next move after this: keep reducing sleepy operator ambiguity in the handoff lane without touching the protected core.
Good candidates:
- optional ticket URL / ticket ID normalization in the acknowledgment block
- a tiny one-shot wrapper that chains finalize + acknowledgment only after the operator confirms the upload happened
- lightweight mismatch warnings when an acknowledgment exists but the paired bundle/manifest later changes afterward
