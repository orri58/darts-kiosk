# Device Runtime Package — Wave 19

## Goal

Wave 19 makes the final handoff exports a little harder to misuse.

After wave 18, operators had a single finalize command, but the last field step still relied on a human reading the handoff and deciding which files to actually attach to the ticket.
That is small friction, but it is exactly the kind of sleepy service-step ambiguity that leads to:
- the paired bundle getting attached without the matching handoff manifest
- a ticket comment being pasted without the actual evidence bundle
- support saying "looks green" while one required artifact is still missing

This wave adds explicit attachment-readiness guidance inside the existing handoff and ticket-comment exports, still without touching `updater.py`, the legacy release lane, or the protected local runtime core.

## What changed

### 1. Handoff and ticket exports now carry attachment readiness

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The drill refresh path now derives one compact `attachment_readiness` block with:
- `ready_to_attach`
- `attach_now`
- `missing_required`
- `missing_optional`
- the required attachment keys for the current lane

This keeps the attach/send decision in the same generated artifacts operators already use.

### 2. Ticket comments now tell operators exactly what to attach

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`DRILL_TICKET_COMMENT.txt/.md/.json` now include:
- an explicit attachment-ready flag
- an `Attach now` list
- a `Missing before ship` list

So a field tech no longer has to infer the best attachment set from the folder contents.

### 3. The handoff manifest mirrors the same attach-now guidance

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`DRILL_HANDOFF.json/.md` now surface the same attachment-readiness state.
That keeps the recommendation, freshness checks, and upload guidance aligned in one place instead of leaving attachment discipline implicit.

### 4. Runtime README documents the new last-mile guardrail

Updated:
- `release/runtime_windows/README_RUNTIME.md`

The runtime package notes now mention that the final exports include explicit attachment readiness and missing-required-artifact guidance.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all logic stays in generated support/handoff artifacts only
- attachment readiness is derived from current handoff state; it does not alter update or rollback execution semantics

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - imports + assertions passed in-process
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Use the wave-19 lane in one realistic board-PC finalization pass:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. perform the normal update + rollback drill and evidence capture
5. run `app/bin/finalize_drill_handoff.bat board-pc-drill`
6. inspect:
   - `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
   - `data/support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt`
7. confirm both now show:
   - `Attachment ready: yes`
   - an `Attach now` section containing the paired bundle and handoff manifest
8. deliberately remove or rename the paired bundle once and confirm the handoff falls back to a missing-required warning before a real field ticket uses it

## Next likely wave

Best next move after this: keep reducing final handoff ambiguity without touching core update logic. Good candidates:
- optional operator observations captured during finalize so the ticket export includes board-specific notes
- explicit upload/result acknowledgment fields if the real field drill still shows ticketing gaps
- a very small wrapper for the evidence-capture leg order if board-PC testing still exposes command-order mistakes
