# Device Runtime Package — Wave 25

## Goal

Wave 25 adds one more small field-safe guardrail around the last upload/re-upload step:

- support can already see whether the paired artifacts were acknowledged
- support can already see when that acknowledgment drifted after regeneration
- but reviewers still have to infer whether the currently visible paired files match the last uploaded set

That is annoying during a real board-PC update/rollback drill.
This wave makes the attachment set itself easier to compare by surfacing compact fingerprints directly in the handoff artifacts.

## What changed

### 1. Acknowledgment now stores a paired-artifact fingerprint snapshot

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`acknowledge-drill-handoff` and `reacknowledge-drill-handoff` now persist a compact snapshot for:
- `paired_bundle`
- `paired_summary_json`
- `paired_summary_md`

Each snapshot item carries:
- path
- exists flag
- size in bytes
- modified timestamp
- SHA-256
- short SHA-256 display value

That means the drill folder now remembers not just that an upload happened, but which paired artifact set was acknowledged.

### 2. Attachment readiness now compares current files vs acknowledged snapshot

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now exposes a new additive block:
- `fingerprint_summary`

It includes:
- current paired artifact fingerprints
- acknowledged snapshot fingerprints
- whether an acknowledged snapshot is available
- whether the current paired files still match the acknowledged snapshot
- compact mismatch entries
- reviewer-facing warnings

This is additive and sits beside the existing timestamp-based drift logic.
It does not replace the current drift warning; it makes the mismatch easier to inspect.

### 3. Handoff/ticket exports now print those fingerprints directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

`DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now show:
- current paired artifact fingerprints
- last acknowledged fingerprint snapshot
- explicit fingerprint warnings when the sets differ

The display stays intentionally compact:
- short SHA prefix
- file size
- modified timestamp

That gives support a quick visual compare during re-attach review without opening the ZIP or recomputing hashes manually.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update, rollback, finalize, or recommendation semantics
- behavior is additive and limited to runtime drill metadata + generated support artifacts

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms acknowledgment persists the paired-artifact snapshot
   - confirms the ticket/handoff exports surface current + acknowledged fingerprint sections
   - confirms regenerated paired artifacts produce fingerprint mismatch warnings until re-acknowledged
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill that checks the reviewer experience, not just the operator path:

1. finalize a clean paired drill
2. acknowledge the first upload with ticket reference / URL
3. inspect `DRILL_HANDOFF.md` and note the acknowledged fingerprint block
4. regenerate the paired artifacts deliberately
5. confirm both exports now show:
   - acknowledgment current: no
   - fingerprint warning
   - current fingerprint block differing from the acknowledged snapshot
6. re-attach the refreshed paired set and run `reacknowledge_drill_handoff.bat`
7. confirm the exports return to a matching acknowledged fingerprint snapshot

## Next likely wave

Best next move after this: another tiny clarity/ergonomics slice in the same additive lane.
Good candidates:
- a one-line explicit verdict like "acknowledged attachment set matches current paired files"
- a helper view that prints only the must-attach subset with compact fingerprints
- a small fallback note for older drill folders whose acknowledgment predates fingerprint snapshots
