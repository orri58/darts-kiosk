# Device Runtime Package — Wave 26

## Goal

Wave 26 keeps working in the same safe post-attach lane as Waves 23–25:

- support can already see whether an upload was acknowledged
- support can already see when paired artifacts drift after that upload
- support can already compare current vs acknowledged fingerprints

But the reviewer still has to mentally interpret that block and the operator still gets a slightly too-long attachment list for the common case.
This wave makes those two last-mile calls more explicit without touching updater/release behavior.

## What changed

### 1. Fingerprint state now emits an explicit verdict

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness.fingerprint_summary` now carries:
- `verdict`
- `verdict_text`

Current verdict states:
- `match`
- `mismatch`
- `snapshot_missing`
- `no_acknowledgment_recorded`

That means `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` can say plainly whether the currently visible paired files still match the last acknowledged upload instead of forcing support to infer that from hash lists and warnings.

### 2. Attachment readiness now exposes a minimal default attach set

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now also carries:
- `attach_now_minimal`

It currently contains the smallest normal handoff set:
- `paired_bundle`
- `handoff_manifest_md`

The existing `attach_now` list still remains for fuller context, but the minimal list answers the practical field question faster: what should I attach right now if the drill is ready?

### 3. Operator-facing exports now print both signals directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

`DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now include:
- one-line fingerprint verdict text
- minimal attach-now section
- full attach-now section

This is purely additive display/metadata polish around the already-existing drill workspace state.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update, rollback, finalize, acknowledge, or re-acknowledge semantics
- behavior is additive and limited to runtime drill metadata + generated support artifacts

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms the acknowledged case now emits fingerprint verdict `match`
   - confirms the drifted case now emits fingerprint verdict `mismatch`
   - confirms the minimal attach-now list is emitted as `paired_bundle` + `handoff_manifest_md`
   - confirms ticket/handoff exports print the new verdict + minimal attach sections
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill and verify the operator-facing readability rather than just raw artifact presence:

1. finalize a clean paired drill
2. inspect `DRILL_HANDOFF.md`
3. confirm it now shows:
   - fingerprint verdict: `match`
   - attach now (minimal): paired bundle + handoff manifest
4. regenerate the paired artifacts deliberately
5. confirm the handoff now shows:
   - fingerprint verdict: `mismatch`
   - re-attach block still present
   - minimal attach set still stays obvious
6. re-attach and run `reacknowledge_drill_handoff.bat`
7. confirm the verdict returns to `match`

## Next likely wave

Best next move after this: stay in the same sleepy-safe field lane.
Good candidates:
- add a tiny attachment-only helper view/command that prints just the current minimal/full attach sets
- add a small explicit note when the stored ticket destination is missing and re-ack cannot safely reuse context
- add reviewer-facing compact diff text for which paired fingerprint entries changed, not just that they changed
