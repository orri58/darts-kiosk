# Device Runtime Package — Wave 31

## Goal

Wave 31 stays in the same additive attachment/review lane as Waves 24–30.

By Wave 30, operators and reviewers could already see:
- whether paired artifacts were acknowledged
- whether that acknowledgment drifted
- whether drift was timestamp-only vs real fingerprint/content change
- a compact attach/re-attach review via `show-attachment-readiness`

But one sleepy field question still required manual reconstruction:
**when were the key paired artifacts last built relative to the recorded upload acknowledgment?**

This wave makes that timing explicit across the existing reviewer-safe surfaces without changing updater, release, or protected local runtime behavior.

## What changed

### 1. Attachment readiness now emits a compact timeline block

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now includes a new additive block:
- `attachment_timeline`

It carries:
- `paired_summary_built_at`
- `paired_bundle_built_at`
- `attached_at`
- `latest_regenerated_at`
- `seconds_between_summary_and_bundle`
- `seconds_between_attach_and_latest_regeneration`
- `verdict`
- `summary`
- `summary_after_attach`

Current timeline verdicts:
- `artifacts_not_ready`
- `awaiting_acknowledgment`
- `current_after_ack`
- `regenerated_after_ack`

That means support/reviewers no longer need to mentally compare raw timestamps scattered across artifact metadata and acknowledgment blocks.

### 2. Compact review and handoff exports now print the timeline directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

The following outputs now surface the new timeline state directly:
- `show-attachment-readiness`
- `DRILL_HANDOFF.*`
- `DRILL_TICKET_COMMENT.*`

They now show:
- compact timeline status
- compact timeline summary
- key timestamp points
- a short attach-timing note when the latest paired regeneration happened before/at/after the recorded upload acknowledgment

So the practical reviewer question becomes faster to answer:
- are we still looking at the same acknowledged paired set?
- or did someone regenerate the paired artifacts after the upload and forget to re-attach/re-ack?

### 3. Closed-loop tests now pin both the current and stale timeline paths

Updated:
- `tests/test_runtime_maintenance_closed_loop.py`

Coverage now confirms:
- a clean acknowledged drill emits `attachment_timeline.verdict = current_after_ack`
- a timestamp-only drift case emits `attachment_timeline.verdict = regenerated_after_ack`
- compact review, handoff markdown, and ticket-comment text all print the new timeline status/details

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to finalize / acknowledge / re-acknowledge command semantics
- behavior is additive and limited to runtime drill review/readback ergonomics

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one board-PC dry drill that deliberately checks the new timing readback:

1. finalize + acknowledge a clean paired drill
2. confirm `show_attachment_readiness.bat <label>` prints timeline status `current_after_ack`
3. regenerate the paired summary/bundle
4. confirm the same helper flips to `regenerated_after_ack` and prints the attach-timing note
5. re-attach/re-ack and confirm the helper returns to a current timeline again

## Next likely wave

Best next move after this: stay in the same additive reviewer-safe lane.
Good candidates:
- a compact JSON export of the attachment review for remote tooling ingestion
- a stricter one-line “same destination, only re-ack remains” review verdict
- a tiny re-ack history trail (`initial_ack`, `latest_reack`) if field practice shows reviewers need more than the current single current-state view
