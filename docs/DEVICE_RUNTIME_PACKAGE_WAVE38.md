# Device Runtime Package — Wave 38

## Goal

Wave 38 stays in the same additive runtime-only reviewer ergonomics lane as Waves 33–37.

By Wave 37, support could already see:
- the latest destination relation
- same-destination reuse counts
- destination-change counts
- a TXT review export

But one small reviewer question still took manual interpretation:
**is the latest visible ticket-destination move the only one in history, or just one move inside a noisier chain of re-acks?**

This wave adds one compact history-pattern verdict so reviewers can answer that faster without opening the raw event trail.

## What changed

### 1. Acknowledgment history now emits a compact destination-history pattern

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`acknowledgment_history` summaries now also expose:
- `destination_history_pattern.verdict`
- `destination_history_pattern.summary`
- `destination_history_pattern.latest_is_only_destination_change`

Current pattern states include:
- `no_history`
- `no_destination_change_recorded`
- `same_destination_reuse_only`
- `latest_is_only_destination_change`
- `latest_is_one_of_multiple_destination_changes`
- `historical_destination_change_present`

This keeps the raw history intact while giving support one reviewer-safe answer to the practical ticket question:
- no visible destination move yet
- same destination reused only
- latest move is the only visible destination change
- latest move is just one of several destination changes already visible

### 2. Reviewer-safe runtime outputs now print that pattern directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`
- `EXECUTION_BOARD.md`

The compact pattern now appears in:
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.txt`
- `data/support/drills/<label>/DRILL_HANDOFF.json`
- `data/support/drills/<label>/DRILL_HANDOFF.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.txt`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.json`

That means support can now tell faster whether a visible ticket-target switch is a one-off correction or part of a more churny drill history.

### 3. Focused runtime tests now pin the key reviewer patterns

Updated:
- `tests/test_runtime_maintenance_closed_loop.py`

Coverage now explicitly checks:
- initial acknowledgment with no destination-change history
- same-destination re-ack path with no destination-change events
- one destination-changing re-ack where the latest event is the only visible move
- two destination-changing re-acks where the latest event is one of multiple visible moves

## Why this is safe

- no change to updater/install/rollback behavior
- no change to runtime package layout
- no change to `release/build_release.sh`
- no change to protected local core
- additive reviewer metadata only inside the runtime drill/handoff lane

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
3. `bash release/build_runtime_package.sh --reuse-frontend`

## Recommended next packaging step

Run one board-PC dry drill with two ticket-target moves and verify the compact history pattern is enough without reading raw history:

1. finalize + acknowledge a clean paired drill
2. re-ack once to a replacement ticket destination
3. confirm the review export says `latest_is_only_destination_change`
4. force another paired refresh and re-ack to a second replacement destination
5. confirm the same export now says `latest_is_one_of_multiple_destination_changes`
6. verify `ATTACHMENT_READINESS_REVIEW.txt` is enough to explain the state without opening JSON/markdown

## Next likely wave

Stay in the same runtime-only reviewer ergonomics lane.
Good next candidates:
- a tiny current-vs-history destination note for “latest move was the first and only correction” vs “history already bounced across multiple tickets” in even shorter wording
- shorter handoff/ticket phrasing for same-ticket re-attach vs replacement-ticket re-attach
- a small re-ack destination-stability verdict that focuses only on whether support can safely stay on the same ticket path
