# Device Runtime Package — Wave 24

## Goal

Wave 24 trims the last annoying manual step after Wave 23's drift warning:

- paired artifacts are regenerated after upload
- the handoff correctly says re-attach is required
- but the operator still has to retype or remember the ticket destination details when stamping the new acknowledgment

That is needless friction during a real board-PC field update/rollback drill.
This wave adds a tiny re-acknowledge helper in the additive runtime lane only.

## What changed

### 1. New re-acknowledge command for post-drift refresh

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New CLI command:
- `reacknowledge-drill-handoff`

The command:
- requires an existing initial acknowledgment
- reuses the stored `ticket_reference` / `ticket_url` by default
- optionally accepts override values if support moved the ticket destination
- refreshes `attached_at` and the generated handoff/ticket exports after the operator re-attaches the refreshed paired artifacts

This keeps the workflow explicit while removing repetitive typing from the board-PC lane.

### 2. Drift guidance now says whether stored ticket destination is reusable

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now also emits:
- `reacknowledge_ready`
- `reacknowledge_destination_ready`
- `reacknowledge_command`

That means `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now tell support not just that re-attach is needed, but also whether the stored ticket destination is ready for a sleepy-safe re-acknowledge pass.

### 3. New operator BAT wrapper for the re-attach follow-up

Added:
- `release/runtime_windows/reacknowledge_drill_handoff.bat`

Example:

```bat
app\bin\reacknowledge_drill_handoff.bat board-pc-drill orri attachments_reuploaded "Re-attached refreshed paired bundle + summaries"
```

If the earlier acknowledgment already stored `TICKET-2048` / its URL, the wrapper can reuse that state automatically.

### 4. Finalize/readme guidance now points at the recovery step

Updated:
- `release/runtime_windows/finalize_drill_handoff.bat`
- `release/runtime_windows/README_RUNTIME.md`

Operators now get an explicit next command for the "artifacts changed after upload" case instead of being left with only a warning block.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update, rollback, finalize, or ship recommendation semantics
- behavior is additive and limited to runtime drill metadata + generated support artifacts

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms drift exports now show `reacknowledge_destination_ready` and the helper command
   - confirms re-acknowledge reuses stored ticket reference / URL and restores `acknowledgment_current`
   - confirms re-acknowledge fails cleanly when no initial acknowledgment or reusable ticket destination exists
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill that explicitly exercises the full upload → drift → re-attach path:

1. finalize the drill as usual
2. acknowledge the first upload with ticket reference / URL
3. rerun finalize to regenerate paired artifacts deliberately
4. confirm the exports show:
   - `re-attach required: yes`
   - `stored destination ready: yes`
   - the `reacknowledge_drill_handoff` helper command
5. re-attach the refreshed paired artifacts to the same ticket
6. run:
   - `app/bin/reacknowledge_drill_handoff.bat board-pc-drill <operator> attachments_reuploaded "refreshed paired artifacts re-attached"`
7. confirm `DRILL_HANDOFF.md` and `DRILL_TICKET_COMMENT.txt` return to:
   - `Attachment acknowledged: yes`
   - `Acknowledgment current: yes`

## Next likely wave

Best next move after this: stay in the same reviewer-safe lane.
Good candidates:
- compact attachment fingerprints for paired bundle/summary comparison
- one-line reviewer summary that says whether the currently acknowledged artifact set still matches the visible paired files
- a tiny support-facing mismatch note when the ticket destination is missing and re-acknowledge cannot safely reuse context
