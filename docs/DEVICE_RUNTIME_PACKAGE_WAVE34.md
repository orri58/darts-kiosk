# Device Runtime Package — Wave 34

## Goal

Wave 34 stays in the same additive runtime-only handoff lane as Waves 31–33.

By Wave 33, the drill folder already persisted a reviewer-safe compact attachment/readiness export in `ATTACHMENT_READINESS_REVIEW.json`.
But one small field-review gap remained:
**the current acknowledgment block still overwrote the prior one, so reviewers could see the latest state but not whether it was the first upload acknowledgment or a later re-ack after drift.**

This wave adds a tiny persisted acknowledgment history trail and surfaces it in the same reviewer-safe outputs.

## What changed

### 1. Drill folders now persist acknowledgment history

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The drill checklist state now carries:
- `ticket_acknowledgment_history`

Each entry stores a compact reviewer-safe record of:
- sequence number
- event type (`acknowledge` or `reacknowledge`)
- attached_by
- attached_at
- ticket_status
- ticket destination fields
- note
- paired artifact snapshot
- previous attached/status hints for quick readback

The existing `ticket_acknowledgment` block remains the current/latest state for compatibility.
The new history trail is additive.

### 2. Reviewer-safe outputs now show compact ack/re-ack history summary

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

These outputs now include a compact history summary:
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`
- `data/support/drills/<label>/DRILL_HANDOFF.json`
- `data/support/drills/<label>/DRILL_HANDOFF.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.txt`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.json`

The summary answers the boring but useful reviewer question directly:
- how many acknowledgment events exist
- whether any re-acknowledgment happened
- what the latest event was

So support can distinguish:
- initial upload acknowledged once
- refreshed artifacts re-attached and re-acknowledged later

without opening raw checklist state or reconstructing the sequence from timestamps alone.

### 3. Re-acknowledge now appends history instead of just replacing state

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`reacknowledge-drill-handoff` still refreshes the current acknowledgment exactly as before,
but it now also appends a new history entry instead of leaving only the latest overwrite.

That keeps existing reviewer logic intact while preserving a minimal audit trail inside the drill folder.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to runtime package layout
- additive metadata only inside existing drill/handoff artifacts
- current `ticket_acknowledgment` behavior remains intact for callers that only read the latest state

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms initial acknowledgment exports now show history count `1`
   - confirms re-acknowledge appends a second history event instead of losing the first
   - confirms the compact review JSON and ticket/handoff exports expose the new history summary

## Recommended next packaging step

Run one board-PC dry drill that includes an actual re-ack path:

1. finalize + acknowledge a clean paired drill
2. confirm `ATTACHMENT_READINESS_REVIEW.json` reports one acknowledgment event and no re-acknowledgments
3. regenerate paired artifacts to force re-attach/re-ack state
4. run `reacknowledge_drill_handoff.bat`
5. confirm the same review JSON and `DRILL_HANDOFF.md` now show:
   - acknowledgment history count = 2
   - re-acknowledgments recorded = 1
   - latest event = `reacknowledge`

## Next likely wave

Keep shaving reviewer/operator friction in the same runtime-only lane.
Good next candidates:
- one compact `latest_destination_reused`/`destination_changed` marker in the history summary
- optional `.txt` sibling for the reviewer JSON export if external tooling wants zero-JSON scraping
- tiny per-event diff hints when only destination/status changed but artifact fingerprints stayed current
