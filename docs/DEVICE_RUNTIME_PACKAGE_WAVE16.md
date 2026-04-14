# Device Runtime Package — Wave 16

## Goal

Wave 16 makes the drill-folder handoff a little less gullible.

After wave 15, the runtime lane could already say whether a closed-loop drill looked good enough to ship, but it still trusted the artifact set a bit too easily:
- an old paired summary could linger in the folder after someone captured newer leg evidence
- an old paired bundle could still look attachable even if it no longer matched the latest summary
- support had no compact way to see “these files exist, but they smell stale”

That is exactly the kind of subtle ticketing mess that happens during real field servicing.

This wave adds conservative freshness and timestamp-order checks to the drill handoff, still without touching `updater.py`, the old release builder, or the protected local runtime core.

## What changed

### 1. Drill handoff now includes artifact freshness status

Updated:
- `release/runtime_windows/runtime_maintenance.py`

Each drill folder’s `DRILL_HANDOFF.json` now carries a `freshness` block with:
- checked artifact timestamps
- age in hours where available
- warning/stale thresholds
- warning strings for support use
- `ok: true/false` summary

This gives support one place to answer the annoying but important question: are these really the current artifacts for this drill, or just artifacts that happen to exist?

### 2. Timestamp-order checks catch obviously misaligned handoffs

Updated:
- `release/runtime_windows/runtime_maintenance.py`

The handoff now warns when final artifacts predate the evidence they are supposed to summarize, for example:
- update leg summary older than update-after evidence
- rollback leg summary older than rollback-after evidence
- paired summary older than one of the leg summaries
- paired bundle older than the paired summary

That catches the practical field failure mode where someone regenerates one part of the folder but attaches an older final artifact.

### 3. Recommendation logic now respects freshness

Updated:
- `release/runtime_windows/runtime_maintenance.py`

A previously green closed-loop result is now downgraded to `needs_manual_review` when the paired handoff artifacts are stale or timestamp-misaligned.

The recommendation remains conservative:
- still `ship` only when the folder is complete, closed-loop evidence passed, rollback restored the start version, and freshness checks are clean
- still `retry_rollback` when paired evidence exists but rollback recovery is not clean
- now `needs_manual_review` when the folder may be complete but the final evidence looks stale or out of order

### 4. Runtime README now documents the new support guardrail

Updated:
- `release/runtime_windows/README_RUNTIME.md`

The runtime package notes now mention the freshness layer so operators know why a seemingly complete folder might still be held for manual review.

## Why this is safe

- no change to `updater.py`
- no change to `release/build_release.sh`
- no change to protected local gameplay/runtime behavior
- all logic stays in the additive runtime packaging lane
- freshness checks only shape support/handoff artifacts; they do not alter update or rollback execution semantics

## Validation done in this pass

Executed:

1. `python3 -m py_compile release/runtime_windows/runtime_maintenance.py tests/test_runtime_maintenance_closed_loop.py tests/test_runtime_field_evidence.py`
2. custom Python import/dry-run that proved:
   - a complete fresh drill folder still yields `ship`
   - aging the paired summary/bundle past the stale threshold downgrades the handoff to `needs_manual_review`
3. `bash release/build_runtime_package.sh --reuse-frontend`
   - runtime ZIP rebuilt successfully
   - allowlist audit stayed clean

Could not run here:
- `pytest` / `python3 -m pytest` (module not installed in this environment)

## Recommended next packaging step

Run one realistic board-PC closed-loop drill and deliberately test the freshness behavior too:

1. extract runtime package
2. run `app/bin/setup_runtime.bat`
3. run `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 <operator> <ticket>`
4. run the normal update/rollback drill through the wave-15/16 lane
5. run `app/bin/summarize_paired_drill.bat board-pc-drill`
6. inspect `data/support/drills/board-pc-drill/DRILL_HANDOFF.md`
7. confirm the recommendation is `ship`
8. then regenerate one leg or age/copy an older paired artifact on purpose and confirm the recommendation falls back to `needs_manual_review`

## Next likely wave

Best next move after this: improve support artifact ergonomics one more step, for example:
- emit a compact ticket-comment snippet directly from the drill handoff
- add an all-in-one closed-loop wrapper that refreshes the final pair/handoff in one command
- optionally separate “aging but acceptable” from truly stale evidence with a more explicit support note in the Markdown handoff
