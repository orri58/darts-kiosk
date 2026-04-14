# Device Runtime Package — Wave 33

## Goal

Wave 33 stays in the same additive attachment/review lane as Waves 24–32.

By Wave 32, board-PC operators and remote reviewers could already read the compact current attach/re-attach state via:
- `show_attachment_readiness.bat`
- `DRILL_HANDOFF.*`
- `DRILL_TICKET_COMMENT.*`

But one small field-ops gap remained:
**the compact reviewer-safe state was still transient unless someone reran the helper or re-parsed larger handoff exports.**

This wave persists that compact review as a drill-folder JSON export so attachment/readiness review can be handed off or scraped directly.

## What changed

### 1. Each drill folder now emits a persisted compact review export

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Each drill workspace now gets:
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`

It contains the same reviewer-safe compact state produced by `build_attachment_review_summary`, plus:
- `exported_at`
- `review_json_path`
- `contract.schema = runtime_attachment_review_v1`
- `contract.detail_level = reviewer_safe`

So support tooling or a sleepy human can read one JSON file instead of reconstructing the current state from several neighboring artifacts.

### 2. The export is refreshed as part of normal handoff flows

The compact review JSON is now regenerated automatically when the drill handoff state is refreshed, which means it stays in step with:
- finalize
- acknowledge
- re-acknowledge
- manual refreshes that rebuild `DRILL_HANDOFF.*` / `DRILL_TICKET_COMMENT.*`

No new operator workflow was added; the export rides the existing refresh path.

### 3. Support bundles now include the compact review JSON

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Paired support bundles now include:
- `support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`

That makes remote reviewer handoff a bit cleaner: the ZIP now contains
- the full handoff manifest
- the ticket-ready comment exports
- the compact machine-friendly attachment review snapshot

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no new mutation beyond writing an additive drill-folder export during the existing handoff refresh path
- release flow stays untouched; runtime package lane only

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms the persisted compact review JSON is emitted into the drill folder
   - confirms acknowledged/current and drifted re-attach states land in the persisted export
   - confirms the paired support bundle now carries `ATTACHMENT_READINESS_REVIEW.json`
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one board-PC dry drill and verify the reviewer JSON is genuinely useful outside Python:

1. finalize + acknowledge a clean paired drill
2. open `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.json`
3. confirm it says `action_verdict = current_no_action`
4. regenerate paired artifacts to force a drifted state
5. confirm the same file flips to the expected re-attach/re-ack verdict
6. confirm the paired support bundle contains that refreshed JSON alongside the handoff/ticket exports

## Next likely wave

Best next move after this: keep trimming final reviewer friction in the same runtime-only lane.
Good candidates:
- a tiny persisted re-ack history trail (`initial_ack`, `latest_reack`, last destination reuse)
- one compact reviewer-safe `attachment_decision` string for ultra-simple ticket automation
- optional `.txt` sibling export if field tooling wants scrape-friendly non-JSON output without parsing markdown
