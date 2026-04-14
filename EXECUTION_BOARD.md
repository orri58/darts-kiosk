# EXECUTION_BOARD

## Purpose

This file is the durable execution handoff for `darts-kiosk`.
Any model/session swap must be able to resume work from this file plus the core docs without depending on chat history.

## Current Program Direction

- Project mode: **autonomous block-by-block execution**
- Primary objective: rebuild the central/control-plane side professionally without destabilizing the protected local core
- Protected-core rule: local runtime stays frozen unless a change is explicitly justified, gated, and regression-tested
- Working style: Jarvis remains the single visible interface and delegates internally to specialists

## Current State Snapshot

### Active execution mode
- Repo is currently in **test-readiness / reality-check mode**.
- Runtime package lane remains the **healthiest practical lane** for the first real board-PC dry drill.
- Scope in this mode: validate the existing runtime package/drill lane, reconcile only direct readiness blockers, and hand over the exact drill sequence / current truth.
- Explicitly not doing here: resuming new runtime waves/polish work until the current drill/readiness picture is reconciled.
- Explicitly not doing here either: resuming fresh central/trust wave progression just because more additive slices are available.

### Local product core
- Local runtime is treated as the protected baseline.
- Work is intentionally happening around it, not through reckless core churn.

### Central progress already landed
- Central auth hardening in place (bcrypt migration path, legacy token constrained, insecure bootstrap behavior tightened)
- Sensitive config / remote-action access tightened
- CORS and production safety improved
- WS auth transport improved away from URL query dependence
- Operator-safe vs internal response shaping added on several central readbacks
- WS per-device diagnostics now follow the same operator-safe vs internal split as other central readbacks
- Device-trust detail/readback now follows the same operator-safe vs internal split: owners get safe trust summaries while installer/internal roles keep raw verification/registry detail
- Central security-focused regression tests expanded substantially

### Device trust progress already landed
- Device trust/credential/lease scaffold exists
- Enrollment placeholder flow exists
- Credential issue/revoke and lease issue/revoke placeholder flows exist
- Placeholder signed lease bundles + verification + reconciliation exist
- Signing registry diagnostics/readback layer exists
- Still placeholder/HMAC-based, not final PKI

### Runtime packaging progress already landed
- Runtime-only packaging path exists in parallel to old release path
- Runtime allowlist + package audit tooling exist
- Runtime maintenance helper exists
- Update/rehearsal/rollback prep flows exist
- Closed-loop rehearsal prep exists
- Field evidence capture/reporting exists
- Goal is now real board-PC rehearsal, not just package theory

## Highest-Priority Active Themes

### Temporary execution note (2026-04-14)
- Wave progression is **temporarily frozen** across the active lanes.
- Central/trust lane switched from wave-polish to **test-readiness mode** for a focused contract/reality pass.
- Runtime lane is also being treated as **validate-first**, not “keep shipping waves because the lane is going well”.
- Durable readiness report: `docs/TEST_READINESS.md`.


### Temporary execution focus: test-readiness first

Before launching more maturity waves, the immediate priority is to reconcile the current repo reality and prove current work in one owner-facing field pass.
See `docs/TEST_READINESS.md` for the practical runbook and current pass/fail framing.

1. **Runtime package / field rehearsal proof**
   - run one disciplined real board-PC closed-loop update+rollback drill
   - require clean paired evidence, handoff artifacts, and a `ship` recommendation
   - keep old release flow untouched while this runtime lane is being proven
   - treat runtime as the **comparatively healthiest lane**, not as already fully green

2. **Trust / Signing maturity**
   - keep treating trust as central-side diagnostic maturity, not field-proven enforcement
   - placeholder/HMAC-based trust is not yet the thing to "prove in field" as production-ready identity/licensing
   - current focused trust/security slices are still materially red and need reconciliation before any more maturity-wave narration

3. **Central response / diagnostics hardening**
   - keep reducing unnecessary sensitive detail on scoped/operator surfaces
   - maintain operator-safe vs internal consistency
   - prefer reconciling current compact-contract/test drift over adding new shape layers

## Current Working Rule for Model Swaps

If a new model/session takes over, it must:
1. Read this file first
2. Read `docs/IMPLEMENTATION_GOVERNANCE.md`
3. Read `docs/IMPLEMENTATION_PLAN.md`
4. Read `docs/CENTRAL_CONTRACT.md`
5. Read `docs/DEVICE_TRUST_MODEL.md`
6. Continue from the latest unfinished wave, not restart strategy from zero

## Do Not Lose These Constraints

- Do not destabilize protected local core casually
- Do not replace repo/release flow blindly; add safe parallel lanes first
- Do not jump straight to local enforcement until central trust/runtime packaging are more mature
- Do not rely on chat history as the system of record

## Near-Term Next Block

### Immediate next block: first test-readiness pass
- Do **not** resume more waves first.
- First reconcile the current readiness picture documented in `docs/TEST_READINESS.md`.
- Then run the first real Windows board-PC closed-loop runtime-package drill described there.
- Success bar:
  - update leg + rollback leg both captured
  - paired summary closed-loop pass
  - rollback restored start version
  - `finalize_drill_handoff.bat` yields `ship`
  - handoff/attachment artifacts are complete and current
- Current truth to preserve during handoff:
  - full-suite state is still broadly red
  - runtime lane is comparatively healthy but not fully green
  - kiosk/UI state is materially improved: loading shell exists, unlock lane is intact, observer fallback/headless behavior is explicit, and kiosk hide waits for observer health confirmation
- If the drill falls short, treat the gap as the next work item instead of resuming general wave progression.

### Wave 9 currently in progress / just landed around this point
- Central Wave 9: more central scope/safe diagnostics tightening
- Trust Wave 9: richer signing-registry diagnostics/readback
- Runtime Package Wave 8: field evidence layer for before/after update drills
- Runtime Package Wave 9: support-bundle layer to zip manifests/report/state/log evidence for board-PC servicing handoff
- Runtime Package Wave 10: operator/device/ticket drill metadata now stamps before/after field state, flows into the Markdown report + support bundle summary, and is mismatch-checked so service artifacts stay traceable across update drills

### Next recommended block after that
- Wave 13 has now been launched in parallel (trust, runtime, central) under the no-nudge autopilot rule.
- Trust/Credential Wave 12:
  - continue issuer/signing maturity and support diagnostics
  - latest slices landed:
    - explicit central `issuer_profiles` readback/history scaffolding now exposes `active_profile`, `configured_profile`, `effective_profile`, effective-key lineage, and credential-backed issuer history without enabling local enforcement
    - device-trust detail and device lease/current readbacks now include this issuer-profile block, and a dedicated read-only support endpoint (`/api/device-trust/devices/{device_id}/support-diagnostics`) exposes condensed trust/issuer/signing diagnostics for support use
    - `reconciliation_summary` now carries compact issuer-profile hints (`effective_key_id`, `effective_source`, `history_count`, `rotation_depth`) alongside existing signing-registry support summaries
  - latest slice landed:
    - support-diagnostics readback now applies the same operator-safe trust redaction to singular `credential`/`lease` payloads as the main trust detail endpoint, and focused regression tests now pin owner-safe vs installer/internal behavior for that endpoint
  - latest slice landed:
    - issuer-profile support summaries now expose compact transition/drift reasons (`transition_state`, `mismatch_reasons`, compared key_ids), reconciliation summaries mirror that transition block, and operator-safe signing-registry shaping now keeps compact credential-rotation counts + terminal key status without exposing raw lineage internals
  - latest slice landed:
    - issuer-profile diagnostics now also expose a compact `readback_summary` explanation block (effective-source reason, active/configured-vs-effective match flags, visible history-status counts, lineage state/note, mismatch summary); support-diagnostics and reconciliation summaries carry it without widening raw internals
  - latest slice landed:
    - support-diagnostics endpoint now stamps an explicit `diagnostics_timestamp` and a compact `endpoint_summary` (issuer/signing narrative + credential/lease material timestamps) so support can read key-rotation/drift state faster without parsing full lineage blocks
  - latest slice landed:
    - issuer-profile diagnostics now expose a compact `history_summary` (latest/previous credential, status counts, one-line replacement/revocation narrative), reconciliation summaries mirror it, and support-diagnostics now surface the same narrative in `endpoint_summary.support_notes.history_narrative`
  - latest slice landed:
    - support/reconciliation readbacks now also expose compact `material_history` for credential/lease records themselves (visible counts, latest/previous entries, active/current-vs-latest narrative), and the support endpoint mirrors this in `endpoint_summary.support_notes` so support can see material drift without reading full lists
  - latest slice landed:
    - compact `material_history.readback_summary` now normalizes credential/lease alignment (`aligned` / `drifted` / `latest_only` / `empty`) plus narrative/status counts, `reconciliation_summary` mirrors that compact block, and `support-diagnostics.endpoint_summary` exposes the same alignment hints so support can reconcile current-vs-latest material without parsing the full history payloads
  - latest slice landed:
    - support/reconciliation summaries now share one compact `issuer_profiles.lineage_explanation` block (`effective_key_id`, source, lineage state/note, transition state, rotation depth, parent, terminal status), reducing drift between support endpoint notes and reconciliation output while staying central-only and non-enforcing
  - latest slice landed:
    - compact issuer-history summaries now distinguish plain revocation from "replacement happened and the newest visible credential is now revoked" via additive `replacement_relation` / `narrative_state` markers
    - wording is now consistent across issuer diagnostics, reconciliation summaries, and support-facing history narratives for replacement-vs-revoked edge cases without widening local enforcement or touching protected core
  - latest slice landed:
    - `issuer_profiles.readback_summary` now carries the same compact `lineage_explanation` block directly instead of forcing downstream support/reconciliation views to reconstruct it separately
    - operator-safe issuer-profile shaping backfills that block from compact summary metadata when older/incomplete payloads are encountered, keeping support/internal wording and key paths consistent without widening raw internals
  - latest slice landed:
    - compact support summaries now prefer an already-computed `readback_summary.lineage_explanation` block instead of rebuilding a slightly different fallback explanation downstream
    - `endpoint_summary.support_notes` now carries compact issuer-history state markers (`history_state`, `replacement_relation`, `narrative_state`, `history_count`) alongside the free-text narrative so support/operator-safe views can classify rotation-vs-revocation wording consistently
  - latest slice landed:
    - compact trust/readback summaries now also stamp nested `material_readback_summary.summary` dict blocks with explicit `detail_level`, closing a small operator-safe/support-compact consistency gap for edge-shaped diagnostic payloads
    - focused regression coverage now pins that nested readback-summary stamping behavior so future shaping cleanups do not silently regress
  - latest slice landed:
    - `reconciliation_summary.issuer_profiles` now mirrors the same compact `source_contracts` provenance block already exposed in `endpoint_summary.support_notes`, so support/detail/device-safe summary consumers can tell which upstream compact contracts (`issuer_profile_readback`, `issuer_history`, `material_history_readback`) shaped the narrative without switching endpoints
    - operator-safe reconciliation shaping now stamps those mirrored provenance sub-blocks with explicit `detail_level` markers as well, keeping compact/internal wording consistency additive and central-side only
  - latest slice landed:
    - compact `source_contracts` provenance blocks now carry a few extra stable presence/classification markers (`has_effective_source_reason`, `has_mismatch_summary`, issuer-history `replacement_relation`/`has_narrative`, and material history counts), so support/detail/device-safe consumers can reason about upstream compact contracts without inferring missing-vs-present state from neighboring narrative text
    - focused trust tests now pin both the sparse/default and fully-populated variants of that provenance contract while staying additive, central-only, and non-enforcing
  - latest slice landed:
    - `source_contract_summary` now also distinguishes missing expected compact contracts from unexpected observed extras (`missing_expected_names`, `unexpected_names`, count/bool markers), so support/detail/device-safe clients can read provenance/readback drift directly from the rollup instead of diffing name lists themselves
    - focused trust tests now pin both canonical/full-set and extra-contract rollup behavior without widening local enforcement or touching protected core
  - latest slice landed:
    - compact support summaries now expose `contract_summary.provenance_state`, a small top-level rollup of upstream compact-contract availability (`overall_state`, `coverage_state`, present/derived/missing counts) so support/detail/device-safe consumers can classify provenance/readback completeness without drilling into `support_notes.source_contract_summary`
    - endpoint-summary finalization now stamps that nested `provenance_state` block with the caller-facing `detail_level`, keeping operator-safe/internal shaping consistent with the rest of the compact support contract
  - latest slice landed:
    - Wave 36 extends that same top-level `contract_summary.provenance_state` with compact drift/gap markers (`missing_expected_count`, `observed_extra_count`, `has_missing_expected_contracts`, `has_unexpected_contracts`) plus the same one-line rollup `summary` already emitted by the deeper provenance contract
    - this keeps support/detail/device-safe readbacks more self-contained for common provenance triage, without touching local enforcement or widening raw central internals
  - latest slice landed:
    - Wave 37 makes top-level compact provenance readbacks more self-contained: `contract_summary.provenance_state` now mirrors the stable contract-name buckets (`present_names`, `derived_names`, `missing_names`, plus `missing_expected_names` / `unexpected_names`) already available in the deeper `source_contract_summary`
    - this keeps support/detail/device-safe consumers from drilling into `support_notes.source_contract_summary` just to identify which upstream compact contracts are present, derived, missing, or unexpectedly observed, while remaining central-only and non-enforcing
  - latest slice landed:
    - Wave 38 extends that same top-level provenance rollup with the deeper coverage/inventory metadata too: `contract_summary.provenance_state` now mirrors `total_contracts`, `expected_contract_count`, `observed_contract_count`, `expected_names`, and `observed_names`
    - this keeps support/detail/device-safe consumers from drilling into `support_notes.source_contract_summary` just to answer whether the full canonical compact-contract set was observed, while staying additive, central-only, and read-only
  - latest validation/hardening slice:
    - targeted central security coverage now pins the raw compact `contract_summary.provenance_state` contract directly: detail level, counts/flags, stable name buckets, and summary text
    - endpoint-summary finalization coverage now also pins that same provenance block for both operator-safe and internal shaping, reducing the chance of a future compact-summary cleanup silently dropping those mirrored provenance buckets from support/detail/device-safe readbacks
    - Wave 39 adds one more tiny provenance/readback polish on top: both `source_contract_summary` and mirrored `contract_summary.provenance_state` now emit a stable reviewer/support-facing `verdict` + `verdict_text` (`canonical_complete`, `canonical_derived`, `contracts_incomplete`, `contracts_extended`, `contracts_drifted`, etc.) so compact consumers can classify upstream contract completeness/drift without diffing name arrays or mentally combining `overall_state` + coverage flags
  - next clean slice: keep polishing support-facing issuer/signing diagnostics around compact/internal split consistency or further lineage/readback explanation clarity, while staying read-only and central-side
- Runtime Package Wave 10:
  - operator/device/ticket stamping landed for field-state/report/support-bundle artifacts
  - next clean slice: fuller closed-loop update+rollback pair evidence, especially updater result capture and rollback-side paired bundle/reporting
 - Runtime Package Wave 11:
   - updater wrapper now records `data/last_updater_run.json` with manifest action, exit code, result/log presence and paths
   - field-state/report/support-bundle artifacts now carry updater evidence, so update vs rollback drill outcomes are visible without reading console scraps
- Runtime Package Wave 12:
   - per-leg drill summaries now turn one before/after evidence pair into explicit update/rollback pass-fail JSON under `data/support/`
   - paired closed-loop summary now combines update + rollback legs into `paired-drill-summary-<label>.json/.md`, including "rollback restored start version" status
   - `capture_field_evidence.bat after ... [update|rollback]` can stamp the leg summary automatically, and `summarize_paired_drill.bat <label>` refreshes the support bundle with the paired view
   - drill-phase comparison now treats `before -> after` as expected progression instead of a false mismatch
   - next clean slice: reduce operator file juggling further with dedicated update/rollback snapshot filenames or a drill-folder/checklist helper so the whole closed-loop run becomes harder to misuse
- Runtime Package Wave 13:
   - per-drill workspace helper now creates `data/support/drills/<label>/` with checklist + canonical artifact paths for update/rollback legs
   - `capture_field_evidence.bat before/after ... [update|rollback]` now writes leg-specific snapshots/reports/bundles into that drill folder so operators stop overwriting one shared before/after pair during a closed-loop run
   - `summarize_paired_drill.bat <label>` now defaults to the same drill folder, keeping both leg summaries plus the paired summary/bundle in one support handoff location
- Runtime Package Wave 14:
   - drill checklist now auto-refreshes from actual artifact presence, including update/rollback leg bundles and the paired bundle
   - each drill folder now emits `DRILL_HANDOFF.json/.md` with completeness, next-step, key artifact presence, and paired closed-loop result when available
   - support bundles now include the drill checklist + handoff docs so remote reviewers get both raw evidence and the compact status view in one ZIP
   - next clean slice: add a single higher-level closed-loop drill wrapper or final recommendation/status text so operators can run and hand off the whole field exercise with even less judgment/load
- Runtime Package Wave 15:
   - drill handoff now carries an explicit recommendation block (`ship`, `retry_rollback`, `needs_manual_review`) with reasons + operator action text derived from checklist completeness and paired closed-loop evidence
   - `summarize_paired_drill.bat` now points operators directly at `DRILL_HANDOFF.md/.json` after rebuilding the paired summary + bundle, reducing final ticket-handoff ambiguity
- Runtime Package Wave 16:
   - `DRILL_HANDOFF.json/.md` now includes artifact freshness/timestamp-order checks for update/rollback leg summaries, paired summary, and paired bundle
   - a previously green closed-loop recommendation is now downgraded to `needs_manual_review` when paired evidence is stale or clearly older than the evidence it summarizes
   - latest validation: helper syntax check passed, custom import/dry-run proved fresh `ship` vs stale `needs_manual_review`, and `release/build_runtime_package.sh --reuse-frontend` rebuilt the runtime ZIP with a clean allowlist audit
- Runtime Package Wave 17:
   - each drill folder now emits `DRILL_TICKET_COMMENT.txt/.md/.json`, a ticket-ready status export derived from the current handoff recommendation, freshness block, and best attachment set
   - support bundles now include those ticket-comment exports, so remote reviewers receive a paste-ready service summary inside the same ZIP as the raw evidence
   - `summarize_paired_drill.bat` now points operators directly at the ticket-comment files as well as the handoff manifest
- Runtime Package Wave 18:
   - new `finalize-drill-handoff` runtime-maintenance command now rebuilds the paired summary, paired support bundle, handoff manifest, and ticket-comment exports in one pass using the canonical drill-folder artifacts by default
   - new `finalize_drill_handoff.bat` gives operators a single last-mile handoff command and exits green only when the refreshed recommendation is `ship`
   - latest validation target: syntax check + targeted runtime maintenance tests for finalize-path artifact refresh, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 19:
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now emit an explicit `attachment_readiness` block (`ready_to_attach`, `attach_now`, `missing_required`, `missing_optional`) derived from the current handoff state
   - operator-facing handoff/ticket exports now spell out exactly which artifacts to attach now and which required artifacts still block a clean ship recommendation, reducing sleepy final-ticket mistakes during board-PC drills
   - latest validation target: syntax check + targeted closed-loop tests for attachment-readiness green/missing-required behavior, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 20:
   - `finalize-drill-handoff --notes` now persists operator observations back into the drill workspace context before rebuilding paired summary/bundle/handoff exports, instead of letting them die inside the bundle summary only
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now surface those operator notes directly, so board-side observations survive into the two artifacts support actually reads/pastes
   - `finalize_drill_handoff.bat` now accepts an optional 5th argument for a short operator note after any path overrides, keeping the ergonomics additive and runtime-lane-only
   - latest validation: syntax check passed, targeted closed-loop test now proves finalize-note persistence into checklist + handoff/ticket exports, and `release/build_runtime_package.sh --reuse-frontend` rebuilt the runtime ZIP with a clean allowlist audit
- Runtime Package Wave 21:
   - new `acknowledge-drill-handoff` runtime-maintenance command now persists a compact post-attach acknowledgment (`attached_by`, `attached_at`, `ticket_status`, optional note) into the drill workspace and refreshes the handoff/ticket exports
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now distinguish `ready_to_attach` from `acknowledged`, so support can see the final ticket step really happened instead of only seeing readiness guidance
   - new `acknowledge_drill_handoff.bat` gives operators a tiny sleepy-safe last command after they actually attach the paired bundle + handoff manifest, and `finalize_drill_handoff.bat` now points directly at it
- Runtime Package Wave 22:
   - handoff/ticket exports now also distinguish `acknowledged once` from `acknowledgment still current` via additive `acknowledgment_current` + `acknowledgment_drift` fields inside `attachment_readiness`
   - if `paired_bundle` / `paired_summary_json` / `paired_summary_md` are regenerated after the recorded `attached_at`, the exports now emit an explicit drift warning instead of quietly leaving an old upload acknowledgment looking fresh
   - the original acknowledgment is preserved for audit trail, but support/operator views now make the re-attach need visible when paired evidence changed after upload
   - latest validation target: syntax check + targeted closed-loop tests for both baseline acknowledgment persistence and post-regeneration drift warning behavior, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 23:
   - post-attach acknowledgment now accepts additive `ticket_reference` + `ticket_url` fields, so the drill folder can point at the real service ticket instead of only saying "uploaded"
   - `attachment_readiness` now emits explicit `reattach_required` / `reattach_reason` / `reattach_targets` guidance when paired artifacts changed after the recorded upload, so support sees exactly what must be re-attached
   - `acknowledge_drill_handoff.bat` now supports optional trailing `[ticket-reference] [ticket-url]`, and the handoff/ticket exports surface those values plus the re-attach block without changing updater/release semantics
   - latest validation: syntax check passed, focused closed-loop runtime tests passed, and `release/build_runtime_package.sh --reuse-frontend` rebuilt the runtime ZIP with a clean allowlist audit
 - Runtime Package Wave 24:
   - new `reacknowledge-drill-handoff` runtime-maintenance command now re-stamps a drifted upload acknowledgment using the stored ticket reference / URL by default, so operators can re-attach refreshed paired artifacts without retyping the ticket destination
   - new `reacknowledge_drill_handoff.bat` exposes that flow directly in the runtime package, and finalize/handoff text now points at it when re-attach guidance is shown
   - `attachment_readiness` now also exposes whether a reusable stored destination exists (`reacknowledge_destination_ready`) plus a concrete helper command string, making drift follow-up clearer in `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*`
   - latest validation target: syntax check + focused closed-loop runtime tests for re-acknowledgment reuse/failure behavior, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 25:
   - upload acknowledgment now persists a compact paired-artifact fingerprint snapshot (`paired_bundle`, `paired_summary_json`, `paired_summary_md`) with sha256/size/modified-at metadata at both initial acknowledge and re-acknowledge time
   - `attachment_readiness` now exposes a compact `fingerprint_summary` block comparing the current paired files against the last acknowledged snapshot, including mismatch warnings when the visible artifact set no longer matches what was uploaded
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now print both the current fingerprints and the acknowledged snapshot, making reviewer-side re-attach verification faster without opening the ZIP or touching protected local core
   - latest validation target: syntax check + focused closed-loop runtime tests for snapshot persistence + mismatch display, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 26:
   - `attachment_readiness.fingerprint_summary` now also emits a one-line reviewer-safe verdict (`match`, `mismatch`, `snapshot_missing`, `no_acknowledgment_recorded`) plus `verdict_text`, so support can classify the upload-vs-current state without mentally decoding hash blocks
   - `attachment_readiness` now also emits `attach_now_minimal` (`paired_bundle` + `handoff_manifest_md`) alongside the existing broader `attach_now` list, reducing sleepy field ambiguity around the normal ticket attachment set
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now print both the explicit fingerprint verdict and the minimal/full attach-now sections while keeping updater/release semantics unchanged
   - latest validation target: syntax check + focused closed-loop runtime tests for verdict/minimal-attach output, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 27:
   - `attachment_readiness.fingerprint_summary` now also carries compact changed-entry guidance (`mismatch_keys`, `mismatch_summary`, per-entry `change_summary`) so reviewer-safe exports can say exactly which paired artifacts changed instead of only saying "mismatch"
   - re-attach exports now also emit explicit missing-destination guidance (`reacknowledge_blocked_reason` + placeholder `reacknowledge_command_with_destination`) when a drifted upload cannot safely reuse stored ticket context
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now print both the compact fingerprint diff text and the blocked re-ack helper path while keeping updater/release semantics unchanged
   - latest validation target: syntax check + focused closed-loop runtime tests for diff-text + blocked re-ack guidance, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 28:
   - `attachment_readiness` now also emits a compact `destination_summary` block that classifies the stored ticket destination (`reference_and_url`, `reference_only`, `url_only`, `none`) and gives a one-line reuse verdict (`stored_destination_ready`, `destination_missing_for_reattach`, `acknowledged_destination_missing`, `no_acknowledgment_recorded`)
   - `DRILL_HANDOFF.*` and `DRILL_TICKET_COMMENT.*` now surface that destination summary near the header/attachment section so reviewers can see faster which ticket destination is on record and whether re-ack can safely reuse it
   - latest validation target: syntax check + focused closed-loop runtime tests for stored-vs-missing destination summaries, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 29:
   - new read-only runtime-maintenance helper `show-attachment-readiness` now prints one compact reviewer/operator view with recommendation state, attach-ready/ack-current state, stored destination status, fingerprint verdict/diff, minimal attach-now guidance, and any re-attach/re-ack helper commands
   - new packaged wrapper `show_attachment_readiness.bat` exposes that same compact handoff review directly on the board-PC runtime lane, reducing the need to open the full handoff/ticket exports for a quick attach/re-attach decision
   - focused runtime tests now pin both the drifted re-attach review path and the missing-required-artifact blocked path; runtime ZIP rebuilt with allowlist audit still clean
- Runtime Package Wave 30:
   - `attachment_readiness.acknowledgment_drift` now classifies post-upload regeneration more explicitly with additive `drift_verdict` / `drift_summary` (`timestamp_only`, `fingerprint_changed`, `timestamp_changed_snapshot_missing`, `mixed`, `current`, `no_acknowledgment_recorded`) plus per-entry `drift_kind`
   - compact reviewer/operator surfaces (`show-attachment-readiness`, `DRILL_HANDOFF.*`, `DRILL_TICKET_COMMENT.*`) now print that drift summary directly, so support can tell faster whether a stale acknowledgment reflects timestamp churn or a real paired-payload change
   - semantics stay conservative: regenerated paired artifacts still require review/re-attach, but the reason is clearer and reviewer-safe
   - latest validation target: syntax check + focused closed-loop runtime tests for timestamp-only vs fingerprint-changed drift, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 31:
   - `attachment_readiness` now also emits a compact `attachment_timeline` block (`paired_summary_built_at`, `paired_bundle_built_at`, `attached_at`, `latest_regenerated_at`, compact timing deltas/verdict/summary) so support can see post-ack/re-ack ordering without manually comparing scattered timestamps
   - compact reviewer/operator surfaces (`show-attachment-readiness`, `DRILL_HANDOFF.*`, `DRILL_TICKET_COMMENT.*`) now print that timeline state directly, including a short attach-timing note when paired artifacts were regenerated before/at/after the recorded upload acknowledgment
   - semantics stay unchanged and conservative: this is reviewer/readback clarity only, additive and runtime-lane-only
   - latest validation: syntax check passed, focused closed-loop runtime tests passed, and `release/build_runtime_package.sh --reuse-frontend` rebuilt the runtime ZIP with a clean allowlist audit
 - Runtime Package Wave 32:
   - `attachment_readiness` now also emits a compact `action_verdict` block (`verdict`, `summary`, `operator_action`, minimal/missing key lists, `same_destination_reack_only`) so support can read the remaining attach/re-attach action directly instead of reconstructing it from destination/drift/fingerprint fields
   - compact reviewer/operator surfaces (`show-attachment-readiness`, `DRILL_HANDOFF.*`, `DRILL_TICKET_COMMENT.*`) now print that action verdict directly, including the explicit sleepy-safe branch where the same stored ticket destination can be reused and only re-attach + re-ack remain
   - semantics stay unchanged and conservative: this is reviewer/readback clarity only, additive and runtime-lane-only
   - latest validation target: syntax check + focused closed-loop runtime tests for clean current / same-destination re-ack / missing-destination / blocked-missing-required verdicts, then rebuild the runtime ZIP with the allowlist audit still clean
- Runtime Package Wave 33:
   - each drill folder now also emits `ATTACHMENT_READINESS_REVIEW.json`, a persisted reviewer-safe compact export of the current attach/re-attach state (`action_verdict`, destination/fingerprint/drift/timeline summaries, next operator step) so support tooling no longer has to scrape markdown or rerun the helper to read the current state
   - the export is refreshed automatically during normal handoff refresh/finalize/acknowledge/re-acknowledge flows and is included in the paired support bundle for remote servicing handoff
   - latest validation target: syntax check + focused closed-loop runtime tests for persisted review export/current-vs-drift states + bundle inclusion, then rebuild the runtime ZIP with the allowlist audit still clean
   - next clean slice: keep reducing sleepy final review friction, for example a tiny re-ack history trail or another compact reviewer-safe audit note
- Central Wave 10/11/12/16:
  - continue safe summary/internal split on diagnostics/readbacks
  - latest slices landed:
    - WS device-status readback now redacts connection timing/event counters for operator-safe roles while preserving installer/internal visibility
    - device-trust device detail now redacts raw verification payloads/fingerprints/registry entries for operator-safe roles while preserving installer/internal visibility
    - remote-action history readback now enforces per-device scope checks and applies the same operator-safe/internal split: owner-safe views get action summaries with `has_params` instead of raw params/issuer detail, while installer/internal roles keep full action metadata
    - reconciliation-summary shaping now preserves `bundle_source` consistently even when operator-safe/device-safe compact views are rebuilt from a precomputed summary without the full reconciliation payload, reducing support/readback drift in compact trust diagnostics
    - owner-safe remote-action readbacks now also suppress raw `result_message` text and expose `has_result_message` instead, so device-side error/result strings do not leak through central history/detail views while installer/internal roles still retain the full message
  - latest slice landed:
    - license detail readback now routes embedded device rows through the shared operator-safe/internal device-summary shaping, so owner-safe license views no longer leak API-key previews, trust notes, credential fingerprints, lease IDs, or last-error text while installer/internal roles still retain those fields
  - latest slice landed:
    - owner-safe telemetry device detail now redacts recent trust-material summaries consistently with other operator-safe central readbacks: `recent_credentials` hide credential fingerprints and `recent_leases` hide lease IDs, while installer/internal views keep the raw values
    - focused regression tests now pin owner-safe vs installer/internal behavior for those recent trust-summary blocks
  - latest slice landed:
    - device-facing current-lease readback now uses the lease-bound credential when building verification/reconciliation/issuer/signing diagnostics instead of loosely defaulting to the latest active credential
    - current-lease readback now also carries `diagnostics_timestamp` plus the same compact `endpoint_summary` shape already used by support diagnostics, so trust/support narratives stay consistent across central readbacks without widening scope or touching local enforcement
    - focused regression coverage now pins both the compact summary presence and the lease-bound-credential reconciliation path
  - latest slice landed:
    - main device-trust detail readback now carries the same compact `diagnostics_timestamp` + `endpoint_summary` block already used by support-diagnostics/current-lease, so owners/installers get one consistent summary narrative across central trust readbacks without widening raw internals
    - focused regression coverage now pins that compact summary on both operator-safe and installer/internal trust-detail views
  - latest slice landed:
    - device-facing current-lease readback now follows a stricter `device_safe` diagnostics shape instead of returning raw central trust internals: singular credential/lease payloads keep compact validity/timing info but drop fingerprint payload echoes, signed bundles, lease signatures/metadata, and raw signing-registry entry/reference dumps
    - current-lease reconciliation summary is now normalized to the same compact summary contract already used on operator-safe support/trust readbacks, reducing drift between device-facing and operator-facing trust summaries
    - focused regression coverage now pins that device-safe current-lease shaping so future trust-summary work does not accidentally re-expose raw central registry/verification detail to devices
  - latest slice landed:
    - operator-safe/device-safe trust readbacks now share one central compact reconciliation-summary helper instead of rebuilding that block separately in multiple endpoints
    - operator-safe credential/lease/reconciliation payloads now stamp explicit nested `detail_level` markers, making support/current-lease/detail responses more self-describing and harder to let drift silently
    - focused regression coverage now pins those nested summary/detail markers on trust detail, support diagnostics, and device-facing current-lease readbacks
  - latest slice landed (Wave 23):
    - support/current compact trust summaries now expose an explicit `endpoint_summary.contract_summary` block (`schema`, `detail_level`, issuer/material/signing classification) so operator-safe/support consumers can key off one stable compact contract instead of re-deriving state from scattered note fields
    - focused trust tests now pin both the new compact contract markers and the existing full support summary payload so future wording/shape cleanup stays additive instead of silently drifting
    - docs now document the compact contract layer as part of the central-only support diagnostics model; no local enforcement or protected-core behavior changed
  - latest slice landed:
    - compact trust `endpoint_summary` blocks now stamp explicit shaping metadata (`detail_level`) on the top-level summary and nested issuer/signing/material/support note blocks
    - operator-safe `issuer_profiles` and `signing_registry` summary payloads now also self-identify as `operator_safe`, matching adjacent reconciliation/material summary shaping
    - focused regression coverage now pins owner/installler consistency for trust detail, support diagnostics, and device-facing current-lease summary metadata
  - latest slice landed (Wave 24):
    - compact trust `endpoint_summary` subcontracts now also self-identify at the nested block level: `contract_summary.issuer_state|material_state|signing_state` plus `support_notes.lineage_explanation|history_state|material_alignment` all carry explicit shaping metadata instead of relying on parent context
    - central summary finalization now normalizes those nested markers for operator-safe/internal readbacks too, reducing drift between raw support summaries and redacted endpoint payloads
    - focused regression coverage now pins both raw compact-summary output and finalized operator-safe shaping for the remaining nested support-contract blocks
  - latest slice landed (Wave 25):
    - support compact summaries now expose `endpoint_summary.support_notes.source_contracts`, a small contract-origin map for `issuer_profile_readback`, `issuer_history`, and `material_history_readback`, so support/internal consumers can see which upstream compact summaries fed the final support narrative without reconstructing that lineage from neighboring fields
    - endpoint-summary finalization now stamps those per-source contract markers with the caller-facing `detail_level`, keeping operator-safe/internal shaping consistent with the rest of the compact support contract
    - compact operator-safe reconciliation readbacks now also normalize nested summary blocks under `reconciliation_summary.issuer_profiles` (`lineage_explanation`, `readback_summary`, `history_summary`) and `reconciliation_summary.material_readback_summary` (`credential_history`, `lease_history`) so support/readback payloads stop mixing explicitly-shaped parent blocks with unstamped nested summaries
    - focused regression coverage now pins both the raw support-summary source-contract block and the finalized operator-safe shaping for it, plus the newly-normalized nested reconciliation summary blocks across trust detail, support diagnostics, and device-facing current-lease readbacks
  - latest slice landed (Wave 26):
    - raw compact support summaries now self-identify the remaining top-level summary blocks with explicit `detail_level` markers too (`issuer_state`, `signing_state`, `material_timestamps`, `support_notes`, `history_state`, `material_history`, `material_readback_summary`)
    - raw `material_readback_summary.credential_history` / `lease_history` now also self-identify as `support_compact`, so compact support payloads stop mixing stamped parents with unstamped child summaries before endpoint finalization runs
    - operator-safe reconciliation readbacks now also stamp the remaining nested issuer/readback compact blocks that support tooling still had to special-case: `reconciliation_summary.issuer_profiles.transition` plus embedded `readback_summary.lineage_explanation` now carry explicit `detail_level` markers alongside the already-shaped parent summaries
    - focused regression coverage now pins both the raw compact-summary contract shape and the finalized operator-safe support-diagnostics/reconciliation shaping for those history/material/transition blocks
  - latest slice landed (Wave 28):
    - raw compact trust support summaries now also self-identify nested `material_history.summary`, `material_history.credential_history`, and `material_history.lease_history` blocks instead of leaving those child summaries to inherit context implicitly from the parent
    - endpoint-summary finalization now normalizes nested compact `summary` blocks too, so operator-safe/internal trust readbacks keep the same explicit shaping markers after redaction/finalization passes
    - focused regression coverage now pins both the raw compact-summary contract and finalized operator-safe/device-safe shaping for those remaining `material_history` child blocks
  - latest slice landed (Wave 29):
    - `endpoint_summary.support_notes.source_contracts` now also exposes explicit provenance presence markers (`present`, `source_state`) for each upstream compact contract, so support/operator-safe consumers can tell whether a compact source block was present, missing, or reconstructed from `material_history`
    - `material_history_readback` provenance now distinguishes a real upstream readback from a fallback reconstruction via `source_state=derived_from_material_history`, improving support diagnostics/readback clarity without touching protected local core or enabling any local enforcement
    - focused regression coverage now pins all three provenance states (`present`, `missing`, `derived_from_material_history`) across raw support compact summaries and operator-safe finalized reconciliation/source-contract views
  - latest slice landed (Wave 30):
    - compact trust support/reconciliation summaries now also expose a small provenance rollup block (`source_contract_summary`) next to the existing per-contract `source_contracts` map, so support/operator-safe/device-safe consumers can classify upstream compact-contract availability without scanning each child block manually
    - the new rollup stays central-only/read-only and reports additive classification only (`overall_state`, state counts, present/derived/missing names, one-line summary) while operator-safe finalization stamps it with explicit `detail_level` markers like neighboring support contracts
    - focused trust regression coverage now pins both the raw compact support payload and the finalized operator-safe reconciliation/support views for this provenance rollup contract
  - latest slice landed (Wave 31):
    - compact provenance rollup `source_contract_summary` now also exposes stable count/flag fields (`total_contracts`, `present|derived|missing_contract_count`, `has_*_contracts`) so support/operator-safe/device-safe consumers can read contract availability directly from the rollup instead of inferring it from name arrays or state-count maps
    - operator-safe issuer-profile shaping now also stamps compact profile blocks (`active_profile`, `configured_profile`, `effective_profile`) with explicit `detail_level=operator_safe` markers instead of relying on the parent summary context alone
    - this stays central-only/read-only and improves provenance/readback clarity for issuer/support diagnostics without touching protected local core or enabling local enforcement
    - focused trust regression coverage now pins both the new provenance rollup counters/booleans and the operator-safe issuer-profile block markers
  - latest slice landed (Wave 32):
    - compact provenance rollup `source_contract_summary` now also declares whether the canonical upstream compact-contract set was fully observed or only partially seen via additive coverage/readback markers (`coverage_state`, `expected_contract_count`, `observed_contract_count`, `expected_names`, `observed_names`)
    - this keeps support/operator-safe/device-safe provenance summaries honest when older or hand-shaped payloads only include a subset of contract blocks, without widening trust internals or touching local enforcement
    - focused trust regression coverage now pins both the normal full-set path and a partial-observation fallback path so provenance/readback drift is easier to spot
  - latest slice landed (Wave 33):
    - compact provenance rollup maps now self-identify one level deeper: raw `source_contract_summary.state_counts` and `source_contract_summary.source_states` both carry explicit `detail_level` markers, and operator-safe/finalized central readbacks preserve the same nested shaping metadata
    - this is a narrow central-only summary-consistency cleanup for support/owner/device-safe trust diagnostics; no local enforcement or protected-core behavior changed
    - focused regression coverage now pins both the raw compact-summary rollup maps and the operator-safe reconciliation/support-diagnostics shaping for them
  - latest slice landed (Wave 34):
    - the remaining compact trust history/readback count maps now also self-identify explicitly: raw support summaries stamp `history_state.status_counts`, `material_history.{credential,lease}_history.status_counts`, and `material_readback_summary.{credential,lease}_history.status_counts` with `detail_level=support_compact`
    - operator-safe/finalized trust readbacks preserve the same nested shaping markers, so support/owner/device-safe consumers no longer need to inherit count-map context from parent history/readback blocks
    - this stays central-only/read-only and only tightens summary-contract consistency for issuer/support diagnostics; no local enforcement or protected-core behavior changed
  - latest slice landed (runtime package Wave 34):
    - drill-folder handoff state now persists a tiny ordered `ticket_acknowledgment_history` trail instead of only overwriting the latest acknowledgment block, preserving whether reviewers are looking at the initial upload acknowledgment or a later re-ack after drift
    - reviewer-safe runtime outputs now surface compact history counts + latest-event summary in `ATTACHMENT_READINESS_REVIEW.json`, `DRILL_HANDOFF.*`, and `DRILL_TICKET_COMMENT.*`, improving post-ack/re-ack clarity without changing updater behavior or touching protected local core
    - focused runtime closed-loop coverage now pins both the initial-ack path and the later re-ack path so future handoff cleanup cannot silently drop the audit trail again
  - latest slice landed (runtime package Wave 36):
    - compact acknowledgment-history summaries now classify the latest ticket-destination relation directly (`initial_acknowledgment`, `same_destination_reused`, `destination_changed`, etc.) instead of making support infer that from raw history rows
    - reviewer-safe runtime outputs now surface that destination-relation summary in `ATTACHMENT_READINESS_REVIEW.json`, `DRILL_HANDOFF.*`, and `DRILL_TICKET_COMMENT.*`, improving post-ack/re-ack clarity without changing updater behavior or touching protected local core
    - focused runtime closed-loop coverage now pins initial-ack, same-destination re-ack, and destination-changing re-ack behavior so future handoff cleanup cannot silently blur those reviewer states
  - latest slice landed (runtime package Wave 37):
    - each drill folder now also persists `ATTACHMENT_READINESS_REVIEW.txt`, a plain-text sibling of the reviewer JSON so board-PC operators/support can read the current attach/re-attach verdict without opening JSON or markdown
    - compact acknowledgment-history summaries now also expose stable relation rollups (`same_destination_reuse_count` plus `destination_relation_counts`), so reviewers can see faster whether the visible trail mostly reused the same ticket destination or bounced across destinations
    - paired support bundles now include that TXT review export too, keeping remote handoff ZIPs aligned with the same compact board-side readback while staying additive/runtime-only
  - latest slice landed (runtime package Wave 38):
    - compact acknowledgment-history summaries now also expose a small `destination_history_pattern` verdict/summary block (`no_destination_change_recorded`, `same_destination_reuse_only`, `latest_is_only_destination_change`, `latest_is_one_of_multiple_destination_changes`, etc.)
    - reviewer-safe runtime outputs now surface that pattern in `ATTACHMENT_READINESS_REVIEW.json/.txt`, `DRILL_HANDOFF.*`, and `DRILL_TICKET_COMMENT.*`, so support can tell faster whether the latest visible ticket-target move is the only one in history or part of a noisier chain
    - focused runtime closed-loop coverage now pins the three key field-review cases: no destination change, same-destination reuse only, and latest destination change being one of multiple visible moves
  - next clean slice: keep tightening runtime reviewer ergonomics in the same additive lane (for example even tighter current-vs-history destination-change rollups or shorter handoff wording around same-ticket re-attach vs destination-change re-attach) while staying runtime-only and release-safe

## Required Habit Going Forward

After each substantial wave:
- update this `EXECUTION_BOARD.md`
- update relevant docs if the contract/architecture changed
- record only durable/project-relevant memory in workspace memory files
- immediately launch the next queued wave when safe, instead of waiting for another user nudge

## No-Nudge Autopilot Rule

For `darts-kiosk`, continuing execution is the default.
Do not pause after reporting a completed wave if there is a clear next safe block available.
The user should not have to repeatedly re-kick the project after each completed batch.

This file is the handoff anchor.
