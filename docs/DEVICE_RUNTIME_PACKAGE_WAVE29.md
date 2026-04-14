# Device Runtime Package — Wave 29

## Goal

Wave 29 stays in the same additive handoff lane as Waves 24–28:

- support can already see whether artifacts were acknowledged
- support can already see destination reuse state
- support can already see fingerprint match vs drift
- support can already read the full handoff/ticket exports

But there was still one boring field gap:
when someone just wants the current attach/re-attach answer, they still have to open and scan the larger handoff markdown or ticket comment.

This wave adds one tiny read-only reviewer/operator helper so the current attachment state is faster to read on a board PC without changing updater, release, or protected local runtime behavior.

## What changed

### 1. Runtime maintenance now exposes a compact attachment review helper

Updated:
- `release/runtime_windows/runtime_maintenance.py`

New command:
- `python app/bin/runtime_maintenance.py show-attachment-readiness --label <label>`

It emits one compact review block containing:
- recommendation status
- attachment ready / acknowledged / acknowledgment current
- stored destination status + display
- fingerprint verdict + compact diff summary
- minimal attach-now list
- re-attach targets and re-ack helpers when drift exists
- missing-required artifacts when ship readiness is still blocked
- a one-line `next_operator_step`

This is intentionally built from the existing drill-folder contracts instead of inventing a parallel state source.

### 2. Packaged runtime now includes a direct BAT wrapper

Added:
- `release/runtime_windows/show_attachment_readiness.bat`

Runtime package path after build:
- `app/bin/show_attachment_readiness.bat <label>`

That gives field reviewers a tiny sleepy-safe command for the practical question:
what do I attach now, and do I need to re-ack this ticket?

### 3. Tests now pin the compact review output

Updated:
- `tests/test_runtime_maintenance_closed_loop.py`

Coverage now confirms:
- drifted acknowledged artifacts produce a compact review with re-attach + re-ack guidance
- missing required artifacts produce a blocked review with the right next-step text

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to manifest/update/rollback semantics
- no change to acknowledge/re-acknowledge persistence semantics
- behavior is additive and limited to runtime drill review/readback ergonomics

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
3. `python3 release/runtime_windows/runtime_maintenance.py show-attachment-readiness --root /tmp/... --label board-pc-drill`
   - validated compact review output shape and non-green exit in a blocked/missing-required case during local dry fixture usage
4. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one board-PC dry drill with the new helper as the reviewer-facing entrypoint:

1. finalize a clean paired drill
2. run `app/bin/show_attachment_readiness.bat <label>`
3. confirm it shows:
   - destination status
   - fingerprint verdict
   - minimal attach-now list
   - next operator step
4. regenerate paired artifacts after acknowledgment
5. rerun the helper and confirm it flips to:
   - acknowledgment current = false
   - fingerprint mismatch
   - explicit re-attach targets
   - re-ack helper command

## Next likely wave

Best next move after this: stay in the same runtime-only field ergonomics lane.
Good candidates:
- distinguish timestamp-only drift vs fingerprint-content drift in the compact review helper
- print a tiny reviewer-safe “same ticket destination, new artifact set” one-liner when re-ack is the only remaining action
- add a compact JSON-only attachment review export for remote ingestion if service tooling wants to scrape the current drill folder state
