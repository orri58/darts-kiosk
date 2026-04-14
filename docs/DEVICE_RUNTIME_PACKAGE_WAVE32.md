# Device Runtime Package — Wave 32

## Goal

Wave 32 stays in the same additive attachment/review lane as Waves 24–31.

By Wave 31, operators and reviewers could already see:
- whether paired artifacts were acknowledged
- whether the acknowledgment had drifted
- whether drift was timestamp-only vs real fingerprint/content change
- the ticket destination state
- the attachment timeline

But one sleepy field gap remained:
**reviewers still had to mentally combine several fields to answer the practical question "what exact handoff action remains right now?"**

This wave adds one explicit compact action verdict so the board-PC/runtime lane can say that directly, especially for the common post-regeneration case where the same stored ticket destination is still reusable and only re-attach + re-ack remain.

## What changed

### 1. Attachment readiness now emits an explicit action verdict

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now includes a compact additive block:
- `action_verdict.verdict`
- `action_verdict.summary`
- `action_verdict.operator_action`
- `action_verdict.attach_now_minimal_keys`
- `action_verdict.missing_required_keys`
- `action_verdict.same_destination_reack_only`

Current verdicts:
- `blocked_missing_required`
- `reattach_and_reack_same_destination`
- `reattach_and_reack_with_destination`
- `attach_and_acknowledge`
- `current_no_action`
- `acknowledged_review_state`
- `awaiting_handoff_readiness`

The important new reviewer-safe distinction is:
- if paired artifacts changed after upload **and** a reusable ticket destination is already stored, the lane now says that explicitly instead of forcing reviewers to infer it from destination/fingerprint/drift fields.

### 2. Compact review, handoff, and ticket exports print that verdict directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

The following outputs now surface the action verdict directly:
- `show-attachment-readiness`
- `DRILL_HANDOFF.*`
- `DRILL_TICKET_COMMENT.*`

That means reviewers now get a direct one-line answer such as:
- attach and acknowledge
- re-attach and re-ack the same stored destination
- re-attach and re-ack with destination details
- no action needed
- blocked because required artifacts are missing

### 3. Tests now pin the reviewer-safe action classification

Updated:
- `tests/test_runtime_maintenance_closed_loop.py`

Coverage now confirms:
- a clean acknowledged drill emits `current_no_action`
- a drifted acknowledgment with no stored destination emits `reattach_and_reack_with_destination`
- a drifted acknowledgment with stored destination reuse emits `reattach_and_reack_same_destination`
- a missing-required-artifact review emits `blocked_missing_required`

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to finalize / acknowledge / re-acknowledge persistence semantics
- behavior is additive and limited to runtime drill review/readback ergonomics

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
3. `python3 release/runtime_windows/runtime_maintenance.py show-attachment-readiness --root /tmp/... --label board-pc-drill --json`
   - validated the new compact `action_verdict` block in reviewer output
4. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one board-PC dry drill that checks the new action-verdict path explicitly:

1. finalize + acknowledge a clean paired drill
2. confirm `app/bin/show_attachment_readiness.bat <label>` prints `action_verdict: current_no_action`
3. regenerate paired artifacts after acknowledgment
4. confirm it flips to `reattach_and_reack_same_destination` when the stored ticket destination is reusable
5. repeat once without stored destination data and confirm it instead prints `reattach_and_reack_with_destination`

## Next likely wave

Best next move after this: stay in the same runtime-only reviewer-safe lane.
Good candidates:
- a persisted compact JSON review export inside the drill folder for remote ingestion/scraping
- a tiny re-ack history trail (`initial_ack`, `latest_reack`) if service reviewers need clearer audit sequence than the current single current-state view
- a final reviewer-safe "attachment set unchanged since last re-ack" note in the packaged BAT wrapper output
