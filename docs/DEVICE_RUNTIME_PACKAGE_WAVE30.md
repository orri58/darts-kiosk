# Device Runtime Package — Wave 30

## Goal

Wave 30 stays in the same additive post-attach/runtime-review lane as Waves 24–29.

By Wave 29, operators/support could already see:
- whether paired artifacts were acknowledged
- whether that acknowledgment had drifted after regeneration
- whether current vs acknowledged fingerprints matched
- a compact `show-attachment-readiness` review on the board-PC runtime lane

But one reviewer ambiguity remained:
**acknowledgment drift was still effectively binary in the compact readback, even when the only visible change was timestamp churn and not a real payload change.**

This wave makes that distinction explicit without loosening the conservative field workflow.

## What changed

### 1. Acknowledgment drift now classifies the kind of post-upload change

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness.acknowledgment_drift` now also emits:
- `drift_verdict`
- `drift_summary`
- `timestamp_only_keys`
- `fingerprint_changed_keys`
- `snapshot_missing_keys`
- per-entry `changed_after_ack[].drift_kind`

Current drift verdicts:
- `timestamp_only`
- `fingerprint_changed`
- `timestamp_changed_snapshot_missing`
- `mixed`
- `current`
- `no_acknowledgment_recorded`

That means reviewers no longer have to infer “mtime moved but hash still matches” from raw fingerprint blocks.

### 2. Compact review and handoff exports print the drift summary directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

The following outputs now show the drift verdict + one-line summary explicitly:
- `show-attachment-readiness`
- `DRILL_HANDOFF.*`
- `DRILL_TICKET_COMMENT.*`

So the field question becomes easier to answer quickly:
- **did the upload become stale because the paired payload really changed?**
- or
- **did something merely get regenerated/re-timestamped after upload?**

### 3. Re-attach semantics stay conservative

Important: this wave does **not** change the workflow gate.

If paired artifacts were regenerated after the recorded upload, the lane still flags that the acknowledgment is no longer current and still requires review/re-attach.

The change is purely reviewer/operator clarity:
- timestamp-only drift is now visible as such
- real fingerprint/content drift is now visible as such
- missing historical snapshot coverage is visible too

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
   - confirms timestamp-only post-ack drift is classified explicitly
   - confirms real fingerprint/content drift is classified explicitly
   - confirms compact review output now prints drift status
   - confirms handoff/ticket export coverage still passes
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one board-PC dry drill that exercises both reviewer branches deliberately:

1. finalize + acknowledge a clean paired drill
2. regenerate paired artifacts in a way that only changes timestamps/packaging metadata
3. confirm `show_attachment_readiness.bat <label>` and `DRILL_HANDOFF.md` now say `drift_status: timestamp_only`
4. then change one paired summary payload for real and refresh again
5. confirm the same surfaces flip to `fingerprint_changed`
6. re-attach/re-ack and confirm the drill returns to `acknowledgment_current = yes`

## Next likely wave

Best next move after this: stay in the same runtime-only reviewer-safe lane.
Good candidates:
- a tiny JSON export for `show-attachment-readiness` so service tooling can scrape current attachment state
- an explicit “same ticket destination, only re-ack remains” reviewer line when everything else is already green
- a compact attachment/history timeline block (`finalized_at`, `attached_at`, `last_regenerated_at`) for faster support audit reading
