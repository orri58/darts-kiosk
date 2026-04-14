# Device Runtime Package — Wave 36

## Goal

Wave 36 stays in the same additive runtime-only handoff lane as Waves 33–35.

By Wave 35, drill folders already preserved acknowledgment/re-acknowledgment history plus a latest change hint.
But one tiny reviewer gap still remained:
**support still had to infer whether the latest event reused the same ticket destination, changed it, or had no previous destination context at all.**

This wave makes that destination relation explicit across the compact reviewer-safe outputs.

## What changed

### 1. Compact acknowledgment history now classifies the latest destination relation

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`ticket_acknowledgment_history` summaries now expose additive reviewer-safe fields:
- `latest_destination_relation`
- `latest_destination_relation_summary`
- `latest_destination_display`
- `previous_destination_display`

Current relation states include:
- `initial_acknowledgment`
- `same_destination_reused`
- `destination_changed`
- `destination_first_recorded_on_reack`
- `destination_cleared`
- `no_destination_to_compare`

This lets support read the practical outcome directly instead of reverse-engineering it from raw history rows.

### 2. Reviewer-safe exports now print that relation directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

The latest destination relation now appears in:
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`
- `data/support/drills/<label>/DRILL_HANDOFF.json`
- `data/support/drills/<label>/DRILL_HANDOFF.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.txt`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.md`
- `data/support/drills/<label>/DRILL_TICKET_COMMENT.json`
- `app/bin/show_attachment_readiness.bat`

That means reviewers can answer the boring field question faster:
- was this only the first acknowledgment?
- did the latest re-ack reuse the same ticket destination?
- or did the evidence move to a different ticket target?

### 3. Focused closed-loop tests now pin the three main reviewer cases

Updated:
- `tests/test_runtime_maintenance_closed_loop.py`

Coverage now explicitly checks:
- initial acknowledgment → `initial_acknowledgment`
- same-destination re-ack → `same_destination_reused`
- destination-changing re-ack → `destination_changed`

So future cleanup in the handoff lane cannot quietly collapse those reviewer distinctions.

## Why this is safe

- no change to updater/install/rollback execution
- no change to `release/build_release.sh`
- no change to runtime package layout
- no change to protected local gameplay/runtime behavior
- additive reviewer metadata only inside existing drill/handoff outputs

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
3. `bash release/build_runtime_package.sh --reuse-frontend`

## Recommended next packaging step

Run one board-PC dry drill with both re-ack shapes and verify the compact exports are enough without opening raw history:

1. finalize + acknowledge a clean paired drill
2. confirm the review export says `latest_destination_relation = initial_acknowledgment`
3. force paired-artifact regeneration and re-ack using the same stored ticket destination
4. confirm the review export flips to `same_destination_reused`
5. re-ack again to a replacement ticket reference/URL
6. confirm the same export flips to `destination_changed`

## Next likely wave

Stay in the same runtime-only reviewer ergonomics lane.
Good next candidates:
- one ultra-short clipboard-safe TXT export focused only on current attach/re-attach decision
- compact counts for same-destination reuse vs destination-change events across the full ack history
- a tiny reviewer-safe marker for “ticket destination changed but fingerprints stayed current” vs “ticket destination changed because paired evidence drifted too”
