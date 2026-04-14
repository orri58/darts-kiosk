# Device Runtime Package — Wave 22

## Goal

Wave 22 closes a very specific sleepy-service failure mode:

- a board drill is finalized
- the paired bundle + handoff are attached and acknowledged
- later, someone regenerates the paired summary or bundle
- the drill folder still says the upload was acknowledged, even though the uploaded artifact set may now be stale

That is exactly the kind of small operational mismatch that causes support confusion during a real board-PC update/rollback drill.

This wave keeps the post-attach acknowledgment flow, but teaches the generated handoff exports to warn when that acknowledgment no longer matches the current paired artifacts.

## What changed

### 1. Acknowledgment drift detection for paired artifacts

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The runtime handoff layer now derives a compact `acknowledgment_drift` block from:
- the persisted `attached_at` timestamp
- the current modification times of:
  - `paired_bundle`
  - `paired_summary_json`
  - `paired_summary_md`

If any of those paired artifacts are newer than the recorded acknowledgment, the exports now flag that the acknowledgment predates regenerated evidence.

### 2. Exports now distinguish “acknowledged once” from “acknowledgment still current”

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now includes:
- `acknowledged`
- `acknowledgment_current`
- `acknowledgment_drift`

That means support can tell the difference between:
- “yes, someone did upload a set of artifacts earlier” and
- “yes, that acknowledgment still matches the currently visible paired evidence”

### 3. Ticket/handoff text now surfaces the mismatch explicitly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

Both `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now show:
- whether the acknowledgment exists
- whether it is still current
- explicit drift warnings when the paired bundle/summary changed afterward

So the folder no longer quietly implies “already uploaded” when the upload proof has drifted behind the latest artifact set.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update/rollback/finalize semantics
- logic is additive and limited to runtime support metadata + generated handoff exports

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms baseline acknowledgment persistence still works
   - confirms acknowledgment stays current when artifacts have not changed
   - confirms drift is flagged when paired summary/bundle files are newer than `attached_at`
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill that exercises the new mismatch warning deliberately:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. complete the normal update + rollback drill
5. run `app/bin/finalize_drill_handoff.bat board-pc-drill`
6. attach the paired bundle + handoff manifest and stamp it with:
   - `app/bin/acknowledge_drill_handoff.bat board-pc-drill <operator> attachments_uploaded "paired bundle + manifest attached"`
7. then intentionally regenerate the paired artifacts once more by rerunning:
   - `app/bin/finalize_drill_handoff.bat board-pc-drill`
8. inspect:
   - `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
   - `data/support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt`
9. confirm they now show:
   - `Attachment acknowledged: yes`
   - `Acknowledgment current: no`
   - a drift warning telling the operator the paired artifacts changed after the recorded upload

## Next likely wave

Best next move after this: keep improving operator clarity around the final real-world ticket step without touching protected core. Good candidates:
- optional ticket URL / external reference capture in the acknowledgment block
- a tiny reminder/wrapper that says “artifacts changed since upload; re-attach and re-acknowledge now”
- compact attachment fingerprint display inside the handoff for even clearer reviewer-side comparison
