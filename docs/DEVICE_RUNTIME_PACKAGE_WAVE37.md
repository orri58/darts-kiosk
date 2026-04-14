# Device Runtime Package — Wave 37

## Goal

Wave 37 stays in the same additive runtime-only reviewer ergonomics lane as Waves 33–36.

By Wave 36, reviewers could already see the latest acknowledgment destination relation.
But two small field-review annoyances remained:

1. the persisted compact review only lived in JSON, which is clumsy for sleepy board-side clipboard checks
2. support still had to infer the overall destination-history shape from individual events instead of one compact rollup

This wave adds a plain-text review sibling and a tiny destination-relation rollup.

## What changed

### 1. Drill folders now persist a plain-text attachment review export

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

Each drill folder now also writes:
- `data/support/drills/<label>/ATTACHMENT_READINESS_REVIEW.txt`

It contains the same compact attach/re-attach verdict already used by `show_attachment_readiness`, but as a saved plain-text artifact that can be:
- opened quickly on the board PC
- pasted into a service comment
- zipped into the support bundle without requiring JSON parsing

### 2. Acknowledgment history summaries now expose compact destination-relation rollups

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Compact reviewer-safe history summaries now also include:
- `same_destination_reuse_count`
- `destination_relation_counts`

This keeps the latest-event summary intact while also answering a practical reviewer question faster:
- was this drill mostly a same-destination re-ack path?
- or did ticket destination changes happen across the visible history?

### 3. Support bundles now include the TXT review sibling too

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Paired support bundles now carry both:
- `ATTACHMENT_READINESS_REVIEW.json`
- `ATTACHMENT_READINESS_REVIEW.txt`

So remote reviewers receive both a machine-readable export and a quick human-readable version in one ZIP.

## Why this is safe

- no change to `updater.py`
- no change to install/update/rollback semantics
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- additive review/export metadata only inside the runtime drill/handoff lane

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
3. `bash release/build_runtime_package.sh --reuse-frontend`

Coverage now also checks:
- support bundle inclusion of `ATTACHMENT_READINESS_REVIEW.txt`
- persisted review JSON exposing `review_txt_path`
- same-destination reuse count/readback in compact reviewer-safe exports
- saved TXT review content for both acknowledged and re-attach-needed states

## Recommended next packaging step

Run one board-PC dry drill and verify the TXT review is sufficient for the final attach/re-attach decision without opening markdown:

1. finalize + acknowledge a clean paired drill
2. open `ATTACHMENT_READINESS_REVIEW.txt` and confirm it shows:
   - current action verdict
   - destination status
   - latest destination relation
   - same-destination reuse count
3. regenerate paired artifacts to force drift
4. reopen the same TXT review and confirm it now shows the re-attach/re-ack helper guidance clearly
5. confirm the paired support bundle contains both the JSON and TXT review exports

## Next likely wave

Stay in the same runtime-only reviewer ergonomics lane.
Good next candidates:
- one tiny reviewer-safe `latest_upload_path_kind` rollup for “same ticket, new evidence” vs “new ticket destination”
- a compact current-vs-history note that says whether the latest event is the only destination change in the whole visible trail
- optional handoff/ticket wording that prefers the TXT review path when operators just need the shortest next-step readback
