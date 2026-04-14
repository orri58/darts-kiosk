# Device Runtime Package — Wave 35

## Goal

Wave 35 keeps the same additive runtime-only drill lane and targets one small field-review pain point left after Wave 34.

By Wave 34, drill folders preserved acknowledgment/re-acknowledgment history.
But reviewers still had to manually diff entries to answer a practical service question:
**did the latest re-ack reuse the same ticket destination, or did the operator move the evidence to a different ticket/URL/status path?**

This wave adds compact change hints so attachment review stays reviewer-safe but more field-usable.

## What changed

### 1. Acknowledgment history entries now carry operator-visible change hints

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Each stored acknowledgment history event now also records:
- `ticket_destination_display`
- prior destination display fields
- `destination_changed`
- `change_summary`

The summary only tracks reviewer-safe deltas that matter during handoff review:
- ticket destination changes
- attached-by changes
- ticket-status changes

That means support can read one compact line instead of reconstructing the delta from two full events.

### 2. Attachment review and ticket exports now surface the latest change directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

These reviewer-facing outputs now expose:
- `destination_change_count`
- `latest_change_summary`

Affected outputs:
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`
- `data/support/drills/<label>/DRILL_HANDOFF.json`
- `data/support/drills/<label>/DRILL_HANDOFF.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.txt`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.json`

So the reviewer can tell at a glance whether the latest re-ack:
- reused the same ticket target
- only changed operator/status wording
- or moved the evidence to a different ticket destination entirely

### 3. `show-attachment-readiness` now includes stored history context

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The CLI review view now passes the persisted acknowledgment history through instead of rebuilding a review from latest-state-only data.

That keeps the console wrapper aligned with the JSON/MD/TXT exports and avoids the tiny but annoying mismatch where the saved drill docs knew more than the live review command.

## Why this is safe

- no change to updater/install/rollback core behavior
- no change to runtime package layout
- no change to protected local core
- no change to current release build flow
- additive reviewer metadata only inside the drill/handoff lane
- old callers that only read latest `ticket_acknowledgment` still work

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms same-destination re-ack shows a compact assignee-only change summary
   - confirms destination-changing re-ack increments destination-change count and persists the latest change hint into ticket/review exports
   - keeps existing closed-loop runtime handoff assertions green

## Recommended next packaging step

Run one runtime dry drill with both re-ack shapes:

1. finalize + acknowledge a clean paired drill
2. force paired artifact regeneration
3. re-ack once with the same stored ticket target
4. confirm `show_attachment_readiness.bat` / `ATTACHMENT_READINESS_REVIEW.json` show:
   - `destination_change_count = 0`
   - latest change explains only operator/status deltas if any
5. re-ack again to a replacement ticket reference/URL
6. confirm the same outputs now show:
   - `destination_change_count = 1`
   - latest change explicitly calls out the old and new ticket destination

## Next likely wave

Stay in the same runtime-only field-safety lane. Good next candidates:
- one shorter operator-facing TXT export of the attachment review for clipboard/ticket paste workflows
- a tiny readiness verdict focused purely on “safe to reuse same destination vs must supply new destination”
- optional stale-history warning when the latest acknowledgment event predates a newer service-ticket context stamp
