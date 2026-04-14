# Device Runtime Package — Wave 28

## Goal

Wave 28 stays in the same additive post-attach lane as Waves 24–27:

- support can already see whether the paired artifacts were acknowledged
- support can already see when that acknowledgment drifted
- support can already compare current vs acknowledged fingerprints
- support can already see whether a reusable destination exists in principle

But reviewers still had to scan the raw acknowledgment block to answer a sleepy but practical question:
**what ticket destination is actually on record right now, and can re-ack safely reuse it?**

This wave makes that readback explicit without changing updater, release, or protected local runtime behavior.

## What changed

### 1. Attachment readiness now emits a compact destination summary

Updated:
- `release/runtime_windows/runtime_maintenance.py`

`attachment_readiness` now includes a new additive block:
- `destination_summary`

It carries:
- `kind` — `reference_and_url`, `reference_only`, `url_only`, or `none`
- `display` — compact human-readable destination text
- `ticket_reference`
- `ticket_url`
- `stored_destination_ready`
- `verdict`
- `verdict_text`

Current verdict states:
- `stored_destination_ready`
- `destination_missing_for_reattach`
- `acknowledged_destination_missing`
- `no_acknowledgment_recorded`

That means callers no longer need to infer the effective destination state by separately checking `ticket_reference`, `ticket_url`, and `reacknowledge_destination_ready`.

### 2. Handoff and ticket exports surface that summary near the top

Updated:
- `release/runtime_windows/runtime_maintenance.py`
- `release/runtime_windows/README_RUNTIME.md`

`DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now show:
- the compact stored ticket destination display
- the destination verdict text
- the destination kind

So support/reviewers can answer these two questions faster:
- which ticket destination is currently stored?
- is that destination reusable for re-acknowledging refreshed paired artifacts?

### 3. Closed-loop tests now pin both the green and blocked cases

Updated:
- `tests/test_runtime_maintenance_closed_loop.py`

Coverage now confirms:
- an acknowledged upload with both ticket reference + URL emits `destination_summary.kind = reference_and_url` and verdict `stored_destination_ready`
- a drifted upload with no stored destination emits `destination_summary.kind = none` and verdict `destination_missing_for_reattach`
- both the handoff and ticket-comment exports print the new destination summary text

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
   - confirms stored-destination summaries for acknowledged uploads
   - confirms missing-destination summaries for drifted re-attach cases
   - confirms handoff/ticket exports print the new destination guidance
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

## Recommended next packaging step

Run one realistic board-PC dry drill that checks the reviewer header/readback, not just the command path:

1. finalize a clean paired drill
2. acknowledge upload with both ticket reference + URL
3. confirm `DRILL_HANDOFF.md` now shows the compact stored ticket destination near the top
4. regenerate paired artifacts and confirm the destination summary still shows the reusable destination while re-attach guidance appears
5. repeat once with an acknowledgment that omitted ticket reference / URL and confirm the summary flips to the blocked missing-destination verdict

## Next likely wave

Best next move after this: stay in the same additive field-review lane.
Good candidates:
- a tiny attachment-only/destination-only helper command for sleepy support review
- one-line distinction between timestamp drift vs fingerprint drift when only one moved
- compact reviewer guidance for `reference_only` vs `url_only` destination records if one proves materially better in field practice
