# Windows Runtime Package (Wave 29)

This package track is additive and experimental.
It is meant to validate a runtime-shaped device payload without replacing the current Windows release flow.

## Layout

```text
app/
  backend/
  frontend/build/
  agent/
  bin/
config/
  backend.env.example
  frontend.env.example
  VERSION
data/
  db/
  logs/
  backups/
  app_backups/
  downloads/
  assets/
  chrome_profile/
  kiosk_ui_profile/
```

## Included in wave 8

- packaged backend runtime
- prebuilt frontend assets only
- packaged Windows agent runtime
- runtime-oriented launcher scripts in `app/bin/`
- config examples in `config/`
- empty writable data roots in `data/`
- runtime validation helper: `app/bin/validate_runtime.bat`
- runtime retention/cleanup helper: `app/bin/cleanup_runtime.bat`
- runtime maintenance engine: `app/bin/runtime_maintenance.py`
- writable-path verification during validation
- runtime update preflight for staged `app/` replacement semantics
- rehearsal preflight command: `python app/bin/runtime_maintenance.py rehearsal`
- runtime manifest preparation command: `python app/bin/runtime_maintenance.py prepare-update-manifest`
- operator wrapper for update drills: `app/bin/prepare_update_rehearsal.bat`
- runtime ZIP staging helper: `app/bin/stage_runtime_update_zip.bat`
- app-only extraction command: `python app/bin/runtime_maintenance.py stage-runtime-zip`
- app-only backup creation command: `python app/bin/runtime_maintenance.py create-app-backup`
- rollback manifest prep command: `python app/bin/runtime_maintenance.py prepare-rollback-manifest`
- chained ZIP → manifest → rehearsal command: `python app/bin/runtime_maintenance.py prepare-runtime-update`
- Windows wrappers:
  - `app/bin/create_runtime_app_backup.bat`
  - `app/bin/prepare_runtime_update_from_zip.bat`
  - `app/bin/prepare_runtime_rollback.bat`
  - `app/bin/prepare_closed_loop_rehearsal.bat`
  - `app/bin/capture_field_evidence.bat`
  - `app/bin/build_support_bundle.bat`
- closed-loop rehearsal command:
  - `python app/bin/runtime_maintenance.py prepare-closed-loop-rehearsal`
- rollback backup ZIP validation now enforces app-only payload shape before rollback prep/use
- field evidence commands:
  - `python app/bin/runtime_maintenance.py capture-field-state`
  - `python app/bin/runtime_maintenance.py compare-field-state`
- field evidence wrapper writes before/after snapshots plus `data/field_report.md`
- support bundle command:
  - `python app/bin/runtime_maintenance.py build-support-bundle`
- support bundle wrapper:
  - `app/bin/build_support_bundle.bat`
- paired drill summary wrapper:
  - `app/bin/summarize_paired_drill.bat`
- final drill handoff wrapper:
  - `app/bin/finalize_drill_handoff.bat`
- post-attach acknowledgment wrapper:
  - `app/bin/acknowledge_drill_handoff.bat`
- post-drift re-acknowledgment wrapper:
  - `app/bin/reacknowledge_drill_handoff.bat`
- compact attachment review wrapper:
  - `app/bin/show_attachment_readiness.bat`
  - compact output now also classifies acknowledgment drift as `timestamp_only`, `fingerprint_changed`, `mixed`, or `current`
  - compact output, ticket comment, and handoff manifest now also print an attachment timeline block (`paired_summary_built_at`, `paired_bundle_built_at`, `attached_at`, `latest_regenerated_at`) so reviewers can see post-ack/re-ack ordering faster
  - acknowledgment history summaries now also surface destination-change count plus a latest change hint (`destination ...`, `attached_by ...`, `ticket_status ...`) so support can tell whether a re-ack reused the same ticket target or moved to a new one
  - reviewer-safe outputs now also stamp the latest destination relation explicitly (`initial_acknowledgment`, `same_destination_reused`, `destination_changed`, etc.) so support does not need to infer post-ack/re-ack ticket-target behavior from raw history rows
  - reviewer-safe outputs now also stamp a compact destination-history pattern verdict (`no_destination_change_recorded`, `same_destination_reuse_only`, `latest_is_only_destination_change`, `latest_is_one_of_multiple_destination_changes`, etc.) so support can tell whether the latest visible ticket move is the only one in history or one of several
- drill workspace initializer:
  - `app/bin/init_drill_workspace.bat`
- self-refreshing drill checklist + handoff manifest inside each drill folder:
  - `data/support/drills/<label>/DRILL_CHECKLIST.md`
  - `data/support/drills/<label>/DRILL_HANDOFF.json`
  - `data/support/drills/<label>/DRILL_HANDOFF.md`
- ticket-ready comment/export files now emit alongside the handoff docs:
  - `data/support/drills/<label>/DRILL_TICKET_COMMENT.txt`
  - `data/support/drills/<label>/DRILL_TICKET_COMMENT.md`
  - `data/support/drills/<label>/DRILL_TICKET_COMMENT.json`
- explicit handoff recommendation inside `DRILL_HANDOFF.*`:
  - `ship`
  - `retry_rollback`
  - `needs_manual_review`
- freshness/timestamp checks inside `DRILL_HANDOFF.*` now flag stale or misaligned paired evidence before support ships it:
  - warns when key drill artifacts age past the support-review window
  - downgrades the final recommendation to `needs_manual_review` when paired summary/bundle timestamps are stale or older than the evidence they summarize
- optional drill metadata stamping on field-state/support artifacts:
  - `--device-id`
  - `--operator`
  - `--service-ticket`
  - `--drill-phase`

## Still intentionally unchanged

- existing `release/build_release.sh`
- existing top-level Windows bundle
- core app/runtime behavior
- final device installer/autostart polish

## Expected operator flow

1. Extract package
2. Run `app/bin/setup_runtime.bat`
3. Review `app/backend/.env`
4. Run `app/bin/validate_runtime.bat`
5. Run `app/bin/start_runtime.bat`
6. Optionally run `app/bin/smoke_test_runtime.bat`
7. Create an app-only rollback point with `app/bin/create_runtime_app_backup.bat`
8. If the update arrives as a full runtime ZIP, either:
   - extract only its `app/` payload with `app/bin/stage_runtime_update_zip.bat <runtime-zip> [output-dir]`, then run `app/bin/prepare_update_rehearsal.bat <staging-dir> <target-version>`
   - or do the whole ZIP-first preflight in one step with `app/bin/prepare_runtime_update_from_zip.bat <runtime-zip> <target-version> [output-dir] [backup-path]`
9. If needed, rerun `python app/bin/runtime_maintenance.py rehearsal`
10. For explicit rollback prep from an app backup ZIP: `app/bin/prepare_runtime_rollback.bat <backup-path>`
11. For one-shot closed-loop prep: `app/bin/prepare_closed_loop_rehearsal.bat <runtime-zip> <target-version> [output-dir] [backup-path] [rollback-manifest]`

For housekeeping:
- preview cleanup: `app/bin/cleanup_runtime.bat`
- apply cleanup: `app/bin/cleanup_runtime.bat --apply`
- create an app-only runtime backup: `app/bin/create_runtime_app_backup.bat`
- turn a downloaded runtime ZIP into app-only staging: `app/bin/stage_runtime_update_zip.bat data\downloads\darts-kiosk-vX.Y.Z-windows-runtime.zip data\downloads\staged-vX.Y.Z`
- prepare a rehearsal manifest: `app/bin/prepare_update_rehearsal.bat data\downloads\staged-vX.Y.Z X.Y.Z`
- do ZIP staging + manifest prep + rehearsal in one shot: `app/bin/prepare_runtime_update_from_zip.bat data\downloads\darts-kiosk-vX.Y.Z-windows-runtime.zip X.Y.Z`
- prepare an explicit rollback manifest from an app backup: `app/bin/prepare_runtime_rollback.bat data\app_backups\runtime-app-....zip`
- prepare a full update+rollback rehearsal lane in one shot: `app/bin/prepare_closed_loop_rehearsal.bat data\downloads\darts-kiosk-vX.Y.Z-windows-runtime.zip X.Y.Z`
- initialize a dedicated drill folder/checklist: `app/bin/init_drill_workspace.bat board-pc-drill BOARD-17 orri TICKET-2048`
- print the compact current attach/re-attach review for a drill folder: `app/bin/show_attachment_readiness.bat board-pc-drill`
  - this view now includes acknowledgment history change hints when a re-ack changed ticket destination, assignee, or status
- capture leg-specific evidence without overwriting the shared defaults:
  - `app/bin/capture_field_evidence.bat before board-pc-drill BOARD-17 orri TICKET-2048 update`
  - `app/bin/capture_field_evidence.bat after board-pc-drill BOARD-17 orri TICKET-2048 update`
  - `app/bin/capture_field_evidence.bat before board-pc-drill BOARD-17 orri TICKET-2048 rollback`
  - `app/bin/capture_field_evidence.bat after board-pc-drill BOARD-17 orri TICKET-2048 rollback`
- update path: `app/bin/update_runtime.bat`
- update preflight only: `python app/bin/runtime_maintenance.py validate-update --manifest data/update_manifest.json`

Update preflight now expects the staged payload to be runtime-shaped:
- top-level `app/` only
- required staged subtrees: `app/backend`, `app/frontend/build`, `app/agent`, `app/bin`
- `project_root` in the manifest must match the extracted runtime root
- protected paths must stay aligned to runtime semantics: `config`, `data`, `logs`

That keeps the runtime package aligned with a future "replace app/, preserve config/ + data/" deployment model even while the current core updater remains unchanged.

`stage-runtime-zip` closes the next operator gap: it opens a downloaded runtime ZIP, finds the packaged runtime root, and extracts only its `app/` tree into an update staging folder. That means rehearsal can start from the actual downloaded artifact instead of a manually prepared directory.

`prepare-update-manifest` writes a runtime-safe `data/update_manifest.json` with the expected protected roots and then validates it immediately. Together with `stage-runtime-zip`, this becomes the missing bridge between “I downloaded a runtime package” and “I can rehearse an update without hand-editing JSON on the board PC”.

Wave 6 added the missing rollback-side glue for that rehearsal lane:
- `create-app-backup` makes a ZIP containing only the replaceable `app/` payload
- default backup naming now includes the current version and target version when known
- `prepare-rollback-manifest` lets operators point the existing updater wrapper at a known app-only backup ZIP without hand-editing JSON
- `prepare-runtime-update` chains ZIP staging, manifest generation, and rehearsal so downloaded artifacts can move through the runtime lane with one command

Wave 7 closes the prep loop one step further:
- `prepare-closed-loop-rehearsal` creates the app backup, stages the downloaded runtime ZIP, writes the install manifest, writes a dedicated rollback manifest, and validates both sides
- rollback prep now rejects backup ZIPs that are not app-only or that miss required runtime payload roots
- the operator can rehearse the entire board-PC lane before running the unchanged updater wrapper

Wave 8 adds proof capture around that drill:
- capture a before snapshot with `app/bin/capture_field_evidence.bat before <label>`
- run the prepared update/rollback step
- capture an after snapshot with `app/bin/capture_field_evidence.bat after <label>`
- compare boundary state in `data/field_report.md`

Wave 9 closes the operator-handoff gap:
- after evidence capture, `build-support-bundle` can zip the before/after states, field report, update manifest, rollback manifest, and recent logs
- `capture_field_evidence.bat after <label>` now tries to create that support artifact automatically
- bundle output lands under `data/support/`
- this gives update/rollback drills a single evidence artifact for ticketing, remote review, or service retention without changing the updater core

Wave 10 makes those artifacts more serviceable in the real world:
- `capture-field-state` can stamp optional drill metadata into the before/after JSON (`label`, `device_id`, `operator`, `service_ticket`, `drill_phase`, `notes`)
- `compare-field-state` carries that context into `data/field_report.md` and flags before/after metadata mismatches
- `build-support-bundle` includes the same drill metadata in `bundle_summary.json`
- the BAT wrappers now accept optional board/operator/ticket arguments so a field tech can produce traceable evidence without editing JSON by hand

Wave 11 closes the "what actually happened during the updater run?" gap:
- `app/bin/update_runtime.bat` now writes `data/last_updater_run.json` after every updater invocation, capturing manifest action, exit code, update-result presence, and updater-log location
- this works for both install-update and rollback drills because the wrapper records the manifest action that was actually executed
- `capture-field-state` now includes an `updater_artifacts` summary
- `compare-field-state` carries updater action/exit/result/log presence into `data/field_report.md`
- `build-support-bundle` now includes `last_updater_run.json` and `update_result.json` when present

That gives a support ZIP enough context to answer the boring but critical question: did the drill actually run, in which mode, and what exit/result evidence exists?

Wave 12 adds the missing paired closed-loop view:
- `build-drill-leg-summary` turns one before/after evidence pair into a durable per-leg JSON summary with explicit pass/fail checks
- `build-paired-drill-summary` combines one update leg and one rollback leg into a single closed-loop summary (`paired-drill-summary-<label>.json/.md`)
- `capture_field_evidence.bat after ... [update|rollback]` can now stamp the current leg summary automatically
- `summarize_paired_drill.bat <label>` builds the update+rollback pair summary and refreshes the support bundle
- support bundles now include matching per-leg and paired summary artifacts when present

That means support can answer the next boring but critical question too: did the board survive the update *and* return cleanly on rollback, without opening multiple JSON files by hand?

Wave 13 reduces the remaining operator footgun: one label now gets its own `data/support/drills/<label>/` workspace with a checklist and dedicated update/rollback filenames. That keeps update-before, update-after, rollback-before, rollback-after, both leg summaries, the paired summary, and their ZIP handoff artifacts together instead of reusing one shared set of generic files.

Wave 14 makes that folder more support-ready instead of just better organized:
- the drill checklist now auto-refreshes as expected artifacts appear
- each drill folder now emits `DRILL_HANDOFF.json/.md` with completeness, next-step, and key-artifact status
- support bundles now include the checklist + handoff manifest from the drill folder when present

That reduces the last bit of “open five files and guess what’s missing” during a field update/rollback review.

Wave 15 tightens the final handoff language for an actual service ticket:
- `DRILL_HANDOFF.json/.md` now includes an explicit recommendation status plus reasons and operator action text
- current recommendation values are:
  - `ship` → closed loop passed, rollback restored the starting version, and the folder is complete
  - `retry_rollback` → paired evidence exists but the rollback result is not yet clean
  - `needs_manual_review` → the folder is incomplete or the paired evidence is not ready yet
- `app/bin/summarize_paired_drill.bat <label>` now points the operator straight at the handoff manifest after rebuilding the pair summary/bundle

That means the drill folder no longer stops at “here are the files”; it now also tells support what the current outcome means.

Wave 16 adds one more real-field guardrail:
- `DRILL_HANDOFF.json/.md` now includes a `freshness` block with artifact age checks and timestamp-order warnings
- the paired handoff is downgraded to `needs_manual_review` if the final summary/bundle is stale or predates the leg evidence it is supposed to represent
- this helps support spot copied-forward or out-of-order artifacts before a board-PC ticket is closed on bad evidence

Wave 17 removes one more boring field-service tax:
- each drill folder now emits `DRILL_TICKET_COMMENT.txt/.md/.json` with a paste-ready service update built from the current handoff recommendation, freshness state, and best attachment set
- the ticket comment points at the paired bundle/summary when present and falls back cleanly when the drill is still incomplete or stale
- support bundles now include those ticket-comment exports too, so remote reviewers get a ready-made status blurb inside the ZIP instead of reconstructing one from raw artifacts
- `app/bin/summarize_paired_drill.bat <label>` now prints the ticket-comment paths next to the handoff manifest paths

Wave 18 adds the last operator-facing handoff wrapper for the current field lane:
- `app/bin/finalize_drill_handoff.bat <label>` rebuilds the paired summary, paired support bundle, handoff manifest, and ticket-comment exports in one explicit command
- optional note capture now fits the same step, for example: `app/bin/finalize_drill_handoff.bat board-pc-drill "" "" "" "Rollback looked clean; launcher reopened without operator intervention"`
- the matching `runtime_maintenance.py finalize-drill-handoff` command exits green only when the refreshed recommendation is `ship`
- that gives board-PC operators one final “refresh everything and tell me if this is actually handoff-ready” step without changing update/rollback execution semantics

Wave 19 tightens the actual attach/send step inside those same exports:
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now carry explicit attachment readiness state
- operators get an `Attach now` list for the current ticket plus a `Missing before ship` list for required artifacts that still block a clean handoff
- the readiness stays conservative: it only goes green when the recommendation is `ship`, freshness checks are clean, and the required paired bundle + handoff manifest exist

Wave 20 closes a small but very real field gap: operator observations from finalization now persist into the actual handoff artifacts instead of disappearing into chat or memory.
- `finalize-drill-handoff --notes "..."` now updates the drill context before rebuilding the paired summary/bundle/handoff exports
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now include those operator notes so support sees the same board-side observation the field tech entered
- `finalize_drill_handoff.bat` accepts an optional 5th argument for a short operator note after any path overrides

Wave 21 adds the last tiny proof-of-handoff step after a clean finalize:
- `acknowledge-drill-handoff --attached-by <name> --ticket-status <state> [--notes "..."]` persists a post-attach acknowledgment into the drill workspace

Wave 31 adds one more reviewer-safe guardrail for real field servicing:
- `attachment_readiness` now carries a compact `attachment_timeline` block with the key board-side timestamps support actually cares about during attach/re-attach review: paired summary build time, paired bundle build time, recorded upload acknowledgment time, and latest paired-artifact regeneration time
- `show_attachment_readiness.bat`, `DRILL_HANDOFF.*`, and `DRILL_TICKET_COMMENT.*` now print that timeline status/summary directly, plus a tiny attach-timing note when regenerated artifacts landed before or after the recorded upload
- attachment review surfaces now also print one compact `action_verdict` line so support can tell directly whether the drill is in `attach_and_acknowledge`, `reattach_and_reack_same_destination`, `reattach_and_reack_with_destination`, `current_no_action`, or `blocked_missing_required` state without combining multiple nearby fields by hand
- this does not change updater or release semantics; it only reduces reviewer guesswork around post-ack/re-ack timing
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now show whether the attachment step was merely ready or actually acknowledged, plus `attached_by`, `attached_at`, and `ticket_status` when supplied
- `app/bin/acknowledge_drill_handoff.bat <label> <attached-by> <ticket-status> [note]` gives operators a sleepy-safe final command after the paired bundle and handoff manifest were really attached to the service ticket
- `finalize_drill_handoff.bat` now points directly at that optional follow-up command so the field lane no longer stops at “ready to attach” without a clean place to record “done”

Wave 22 adds one small but important anti-footgun after that acknowledgment:
- the handoff/ticket exports now show whether the recorded acknowledgment is still current, not just whether it once happened
- if the paired bundle or paired summary files are regenerated after `attached_at`, the exports emit an acknowledgment-drift warning instead of quietly leaving an old “uploaded” marker looking fresh
- the original acknowledgment is preserved for audit trail, but support gets an explicit nudge to re-attach the refreshed artifacts before trusting the old ticket step

Wave 23 makes that last handoff state more explicit and less chat-dependent:
- `acknowledge-drill-handoff` can now persist a concrete `ticket_reference` and optional `ticket_url` alongside `attached_by`, `attached_at`, and `ticket_status`
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now emit an explicit `reattach_required` block with the exact paired artifacts to re-attach when acknowledgment drift is detected
- the Windows acknowledgment wrapper now accepts optional trailing `[ticket-reference] [ticket-url]`, so board-side operators can stamp the real ticket destination without editing JSON

Wave 27 tightens the reviewer/operator readback around that same re-attach lane:
- fingerprint verdicts now also print a compact diff line like `Changed paired entries: paired_bundle, paired_summary_json, paired_summary_md`
- each mismatch entry carries a tiny reviewer-safe `change_summary`, so support can see which paired file moved without manually comparing hash blocks
- when re-attach is required but the earlier acknowledgment did not store a ticket destination, the exports now say that explicitly and print a placeholder-filled `reacknowledge_drill_handoff.bat` command showing where ticket reference / URL must be supplied

Wave 24 reduces the last sleepy follow-up after that drift warning:
- `reacknowledge-drill-handoff` re-stamps the upload acknowledgment after a re-attach using the stored ticket reference / URL by default, so the operator does not need to retype the destination details when only the paired artifacts changed
- the helper refuses to run unless an initial acknowledgment already exists and a reusable ticket destination is available, which keeps the lane explicit instead of silently inventing ticket context
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now show whether a stored ticket destination is ready for re-acknowledgment and print the helper command directly inside the re-attach warning block
- the Windows wrapper is:
  - `app/bin/reacknowledge_drill_handoff.bat <label> [attached-by] [ticket-status] [note] [ticket-reference] [ticket-url]`

Wave 25 adds a tiny reviewer-side guardrail on top:
- `acknowledge-drill-handoff` and `reacknowledge-drill-handoff` now persist a compact snapshot of the paired artifact set (`paired_bundle`, `paired_summary_json`, `paired_summary_md`) including size, modified timestamp, and SHA-256 fingerprint
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now show both the current paired artifact fingerprints and the last acknowledged fingerprint snapshot
- when the current paired files no longer match the acknowledged snapshot, the exports emit an explicit attachment fingerprint warning so support can spot a stale or wrong upload faster during a board-PC drill
- fingerprints are shown compactly (short SHA prefix + size + modified time) so reviewers can compare attachment sets without opening the ZIP or recomputing hashes manually

Wave 26 trims the same last-mile review step a bit further:
- the handoff/ticket exports now print a one-line fingerprint verdict (`match`, `mismatch`, `snapshot_missing`, or `no_acknowledgment_recorded`) so support does not have to infer status from hash blocks alone
- `attachment_readiness` now also emits `attach_now_minimal`, the smallest normal handoff set (`paired_bundle` + `handoff_manifest_md`) alongside the broader `attach_now` list
- that keeps the richer attachment list for context, but gives sleepy field operators a clearer default answer to “what exactly do I attach right now?”

Wave 28 adds one more tiny reviewer-safe readback near the same handoff step:
- `attachment_readiness.destination_summary` now classifies the stored ticket destination as `reference_and_url`, `reference_only`, `url_only`, or `none`
- the same block also emits a one-line reuse verdict (`stored_destination_ready`, `destination_missing_for_reattach`, `acknowledged_destination_missing`, `no_acknowledgment_recorded`) plus display text showing exactly which ticket destination is on record
- `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now surface that destination summary near the header/attachment section so reviewers can tell faster whether re-ack can safely reuse stored ticket context without hunting through the raw acknowledgment block

Wave 29 adds a tiny reviewer/operator helper around that same handoff step:
- `python app/bin/runtime_maintenance.py show-attachment-readiness --label <label>` now prints one compact review block with recommendation state, attachment readiness, acknowledgment current-ness, stored ticket destination status, fingerprint verdict/diff, minimal attach-now list, and any required re-attach helper commands
- `app/bin/show_attachment_readiness.bat <label>` exposes the same view directly inside the packaged runtime lane for board-PC reviewers who just need the current attach/re-attach answer without opening the full handoff markdown first
- this is intentionally read-only and additive: no updater behavior, release flow, or protected local runtime semantics changed

Wave 30 keeps that same runtime-only lane but removes one sleepy reviewer ambiguity:
- acknowledgment drift now emits an explicit verdict plus one-line summary: `timestamp_only`, `fingerprint_changed`, `timestamp_changed_snapshot_missing`, `mixed`, `current`, or `no_acknowledgment_recorded`
- the compact attachment review, `DRILL_HANDOFF.*`, and `DRILL_TICKET_COMMENT.*` all print that drift summary directly
- semantics stay conservative on purpose: regenerated paired artifacts still require review/re-attach, but reviewers can now tell faster whether the visible delta is just timestamp churn or a real content/fingerprint change

Wave 33 adds one more low-risk handoff/reviewer guardrail:
- each drill folder now also persists `ATTACHMENT_READINESS_REVIEW.json`, a reviewer-safe compact JSON export of the same current attach/re-attach state used by `show_attachment_readiness`
- each drill folder now also persists `ATTACHMENT_READINESS_REVIEW.txt`, an ultra-compact clipboard-safe sibling for board-side attach/re-attach review without opening JSON or markdown
- the export is refreshed automatically during the normal handoff refresh/finalize/acknowledge/re-acknowledge path, so it stays aligned with `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*`
- paired support bundles now include that JSON as well, which makes remote ticket/review tooling less dependent on scraping markdown or rerunning the helper locally

Wave 34 adds one more tiny post-ack/re-ack guardrail:
- drill state now persists `ticket_acknowledgment_history`, a small ordered trail of initial acknowledgment plus later re-acknowledgments instead of only overwriting the current acknowledgment block
- `ATTACHMENT_READINESS_REVIEW.json`, `DRILL_HANDOFF.*`, and `DRILL_TICKET_COMMENT.*` now surface compact history counts plus the latest ack event summary, so sleepy reviewers can tell whether they are looking at an untouched initial upload or a later re-ack after drift
- this stays additive and runtime-only: no updater behavior, no release flow, and no protected local core behavior changed

Wave 36 tightens the same reviewer-safe lane one notch further:
- compact acknowledgment history summaries now classify the latest ticket-destination relation directly instead of making support infer it from the raw history event (`initial_acknowledgment`, `same_destination_reused`, `destination_changed`, `destination_first_recorded_on_reack`, `no_destination_to_compare`, etc.)
- `ATTACHMENT_READINESS_REVIEW.json`, `DRILL_HANDOFF.*`, `DRILL_TICKET_COMMENT.*`, and `show_attachment_readiness.bat` now all carry the same one-line destination-relation summary alongside the existing latest change text
- this remains additive reviewer metadata only; updater/install/rollback behavior and the protected local core stay untouched

Wave 37 trims the final sleepy-review friction a little further:
- each drill folder now also persists `ATTACHMENT_READINESS_REVIEW.txt`, a plain-text sibling of the review JSON for quick clipboard/paste use during board-PC handoff checks
- compact acknowledgment history summaries now also expose stable relation rollups (`same_destination_reuse_count` plus per-relation counts), so support can tell faster whether the drill mostly reused the same ticket target or bounced across destinations
- paired support bundles now include the TXT review export too, keeping remote reviewers aligned with the same compact board-side readback

The evidence layer is intentionally boring and strict:
- config hash drift is flagged
- disappearance of `data/` or `data/logs/` is flagged
- app/config/data/log file-count deltas are recorded for service notes

That keeps the replacement unit explicit:
- update/rollback payload = `app/`
- preserved boundaries = `config/`, `data/`, `logs`

Retention defaults live in `config/runtime_retention.env.example` and can be copied selectively into `app/backend/.env`.

## Why this exists

The current Windows package is still repo-shaped.
This runtime package is the first safe step toward a device-shaped payload that cleanly separates:

- replaceable app payload (`app/`)
- stable config (`config/`)
- persistent writable state (`data/`)
