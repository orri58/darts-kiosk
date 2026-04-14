# Device Runtime Package — Wave 27

## Goal

Wave 27 keeps working in the same additive post-attach lane as Waves 24–26:

- support can already see whether paired artifacts were acknowledged
- support can already see when those artifacts drift after upload
- support can already compare current vs acknowledged fingerprints

But two sleepy-time annoyances remained:

1. fingerprint mismatch output still forced reviewers to mentally decode the hash block to see which paired entries changed
2. if re-attach was required but the initial acknowledgment forgot the ticket destination, the exports warned about drift without clearly telling the operator what exact recovery command to run next

This wave fixes both without touching updater/release/local-core behavior.

## What changed

### 1. Fingerprint summaries now include compact diff guidance

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness.fingerprint_summary` now also exposes:
- `mismatch_keys`
- `mismatch_summary`
- per-entry `change_summary`

Examples:
- `All acknowledged paired artifact fingerprints still match the current files.`
- `Changed paired entries: paired_bundle, paired_summary_json, paired_summary_md`

This gives remote reviewers a one-line verdict plus a one-line diff instead of making them eyeball short hashes.

### 2. Re-attach guidance now explains blocked reuse more clearly

Updated:
- `release/runtime_windows/runtime_maintenance.py`

When `reattach_required` is true but no stored `ticket_reference` / `ticket_url` exists, `attachment_readiness` now also emits:
- `reacknowledge_blocked_reason`
- `reacknowledge_command_with_destination`

That means operator-facing exports now say plainly that the stored destination is missing and show the exact placeholder-based recovery shape, e.g.:

```bat
app\bin\reacknowledge_drill_handoff.bat board-pc-drill [attached-by] [ticket-status] [note] [ticket-reference] [ticket-url]
```

### 3. Handoff/ticket exports print both signals directly

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

`DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now include:
- explicit fingerprint diff text alongside the existing fingerprint verdict
- explicit blocked re-ack reason when stored destination reuse is unavailable
- the destination-supplying helper command when that blocked case occurs

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- no change to finalize, acknowledge, or re-acknowledge semantics
- behavior is additive and limited to runtime drill metadata + generated support artifacts

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py`
2. `python3 tests/test_runtime_maintenance_closed_loop.py`
   - confirms matching snapshots now emit the compact all-clear diff summary
   - confirms drifted snapshots emit the changed-entry summary and per-entry change text
   - confirms missing-destination re-attach exports now surface the blocked reason plus the placeholder recovery command
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one board-PC dry drill that intentionally exercises the "operator forgot to store ticket destination" branch:

1. finalize a clean paired drill
2. acknowledge the first upload **without** ticket reference / URL
3. regenerate paired artifacts deliberately
4. confirm `DRILL_HANDOFF.md` now shows:
   - fingerprint diff with the changed paired entries
   - stored destination ready: `no`
   - blocked reason explaining why reuse cannot happen
   - placeholder `reacknowledge_drill_handoff.bat` command with ticket reference / URL slots
5. re-attach using the shown full command with the real destination values
6. confirm the handoff returns to acknowledgment current = yes and fingerprint verdict = match

## Next likely wave

Best next move after this: stay in the same additive reviewer-safe lane.
Good candidates:
- a tiny attachment-only helper command that prints just the current attach-now / reattach-now view
- one-line acknowledgment destination summary (`ticket_reference`/`ticket_url` presence) near the handoff header
- compact reviewer text for timestamp drift vs fingerprint drift when only one of those moved
