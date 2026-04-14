# Device Runtime Package — Wave 23

## Goal

Wave 23 tightens the last post-attach part of the board-PC drill lane without touching update/rollback mechanics:

- make the final upload acknowledgment point at a real ticket destination instead of a vague "uploaded" state
- make re-attach requirements explicit when paired evidence is regenerated after that upload

Wave 22 already detected acknowledgment drift.
This wave makes that drift more actionable for sleepy field use.

## What changed

### 1. Acknowledgment can now carry real ticket destination details

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/acknowledge_drill_handoff.bat`

`acknowledge-drill-handoff` now supports two additive fields:
- `ticket_reference`
- `ticket_url`

Those values are persisted next to:
- `attached_by`
- `attached_at`
- `ticket_status`
- optional note

That means the drill folder can now say not just that artifacts were uploaded, but also where support should look.

### 2. Handoff/ticket exports now emit an explicit re-attach block

Updated:
- `release/runtime_windows/runtime_maintenance.py`

When acknowledgment drift is detected, `attachment_readiness` now includes:
- `reattach_required`
- `reattach_reason`
- `reattach_targets`

The generated exports now spell out the exact paired artifacts that should be re-attached:
- paired bundle
- handoff manifest markdown
- paired summary markdown
- paired summary json

So the field lane no longer stops at "acknowledgment is stale"; it now tells the operator what to re-send.

### 3. Operator wrapper supports ticket reference / URL stamping

Updated:
- `release/runtime_windows/acknowledge_drill_handoff.bat`
- `release/runtime_windows/finalize_drill_handoff.bat`
- `release/runtime_windows/README_RUNTIME.md`

The acknowledgment BAT wrapper now accepts optional trailing arguments:

```bat
app\bin\acknowledge_drill_handoff.bat <label> <attached-by> <ticket-status> [note] [ticket-reference] [ticket-url]
```

That keeps the runtime lane additive while making the last service step more traceable.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to update, rollback, or finalize semantics
- behavior is additive and limited to runtime drill metadata + generated support artifacts

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms acknowledgment still persists cleanly
   - confirms ticket reference / URL flow into the generated exports
   - confirms drift now produces explicit `reattach_required` + target artifact guidance
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill with the new post-attach traceability path:

1. finalize the drill as usual
2. attach the paired bundle + handoff manifest to the real ticket
3. stamp the upload with something like:
   - `app/bin/acknowledge_drill_handoff.bat board-pc-drill orri attachments_uploaded "paired bundle + manifest attached" TICKET-2048 https://tickets.example/TICKET-2048`
4. confirm both exports show the ticket destination:
   - `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
   - `data/support/drills/board-pc-drill/DRILL_TICKET_COMMENT.txt`
5. rerun `app/bin/finalize_drill_handoff.bat board-pc-drill`
6. confirm the exports now show:
   - acknowledgment current: no
   - re-attach required: yes
   - explicit re-attach target list

## Next likely wave

Best next move after this: stay in last-mile field guardrails.
Good candidates:
- compact artifact fingerprint display in the handoff so support can compare the uploaded bundle/summary set faster
- a tiny wrapper that re-acknowledges after a detected drift using the same stored ticket reference / URL
- optional normalization/validation for ticket URL/reference formats if the real support system settles down
